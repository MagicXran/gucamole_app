"""
个人空间文件管理 API — 上传/下载/删除/配额
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import jwt
from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, Request, UploadFile, status,
)
from fastapi.responses import Response
from pydantic import BaseModel

from backend.database import db, CONFIG
from backend.auth import get_current_user, JWT_SECRET, JWT_ALGORITHM
from backend.models import UserInfo
from backend.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# ---- 配置 ----
_ft_cfg = CONFIG.get("file_transfer", {})
_drive_cfg = CONFIG.get("guacamole", {}).get("drive", {})
DRIVE_BASE = Path(CONFIG["guacamole"]["drive"]["base_path"])  # /drive
DEFAULT_QUOTA_BYTES = int(_ft_cfg.get("default_quota_gb", 10)) * 1073741824
MAX_FILE_SIZE = int(_ft_cfg.get("max_file_size_gb", 50)) * 1073741824
CHUNK_SIZE_MB = _ft_cfg.get("chunk_size_mb", 10)
USAGE_CACHE_SECONDS = _ft_cfg.get("usage_cache_seconds", 60)
CLEANUP_STALE_HOURS = _ft_cfg.get("cleanup_stale_uploads_hours", 24)
UPLOAD_TEMP_DIR = ".uploads"
HIDDEN_ROOT_DIR_NAMES = frozenset(
    str(name).strip().casefold()
    for name in _drive_cfg.get("hidden_root_dirs", ["Download"])
    if str(name).strip()
)

_executor = ThreadPoolExecutor(max_workers=4)
_usage_cache: dict[int, tuple[int, float]] = {}  # user_id -> (bytes, ts)


# ---- 请求模型 ----

class DownloadTokenRequest(BaseModel):
    path: str


class MkdirRequest(BaseModel):
    path: str


# ============================================
# 工具函数
# ============================================

def _user_dir(user_id: int) -> Path:
    return DRIVE_BASE / f"portal_u{user_id}"


def _safe_resolve(user_id: int, relative_path: str) -> Path:
    """路径防穿越: resolve() + 前缀校验"""
    base = _user_dir(user_id).resolve()
    if not relative_path or relative_path in (".", "/"):
        return base
    cleaned = relative_path.lstrip("/").lstrip("\\")
    target = (base / cleaned).resolve()
    base_str = str(base)
    target_str = str(target)
    if target_str != base_str and not target_str.startswith(base_str + os.sep):
        raise HTTPException(400, "非法路径")
    return target


_UPLOAD_ID_RE = re.compile(r'^[a-f0-9]{16}$')


def _validate_upload_id(upload_id: str):
    """upload_id 必须是纯 hex — 防路径穿越"""
    if not _UPLOAD_ID_RE.match(upload_id):
        raise HTTPException(400, "无效的上传 ID")


_FILENAME_BLACKLIST = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4",
    "LPT1", "LPT2", "LPT3", "LPT4",
})
_FILENAME_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _validate_filename(name: str):
    if not name or name.strip() in (".", ".."):
        raise HTTPException(400, "非法文件名")
    if name.upper().split(".")[0] in _FILENAME_BLACKLIST:
        raise HTTPException(400, f"'{name}' 是 Windows 保留名")
    if _FILENAME_BAD_CHARS.search(name):
        raise HTTPException(400, "文件名含非法字符")
    if len(name.encode("utf-8")) > 255:
        raise HTTPException(400, "文件名过长")


def _calc_dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _get_usage_sync(user_id: int, force_refresh: bool = False) -> int:
    now = time.time()
    cached = _usage_cache.get(user_id)
    if not force_refresh and cached and now - cached[1] < USAGE_CACHE_SECONDS:
        return cached[0]
    udir = _user_dir(user_id)
    size = _calc_dir_size(udir) if udir.exists() else 0
    _usage_cache[user_id] = (size, now)
    return size


def _invalidate_usage_cache(user_id: int):
    _usage_cache.pop(user_id, None)


def _get_quota(user_id: int) -> int:
    row = db.execute_query(
        "SELECT quota_bytes FROM portal_user WHERE id = %(uid)s",
        {"uid": user_id}, fetch_one=True,
    )
    if row and row.get("quota_bytes") is not None:
        return int(row["quota_bytes"])
    return DEFAULT_QUOTA_BYTES


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1048576:
        return f"{size / 1024:.1f} KB"
    if size < 1073741824:
        return f"{size / 1048576:.1f} MB"
    return f"{size / 1073741824:.2f} GB"


def _create_download_token(user_id: int, path: str, username: str = "") -> str:
    payload = {
        "user_id": user_id,
        "path": path,
        "username": username,
        "type": "download",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_download_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "download":
            raise HTTPException(403, "无效的下载令牌")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(403, "下载链接已过期，请重新获取")
    except jwt.InvalidTokenError:
        raise HTTPException(403, "无效的下载令牌")


def _sync_append(path: Path, data: bytes):
    with open(path, "ab") as f:
        f.write(data)


def _should_hide_entry(relative_path: str, entry_name: str, is_dir: bool) -> bool:
    if not is_dir:
        return False
    normalized_path = str(relative_path or "").strip().strip("/\\")
    if normalized_path:
        return False
    return entry_name.casefold() in HIDDEN_ROOT_DIR_NAMES


# ============================================
# API 端点
# ============================================

@router.get("/space")
def get_space_info(
    refresh: bool = Query(default=False),
    user: UserInfo = Depends(get_current_user),
):
    """配额概览"""
    used = _get_usage_sync(user.user_id, force_refresh=refresh)
    quota = _get_quota(user.user_id)
    pct = round(used / quota * 100, 1) if quota > 0 else 0
    return {
        "used_bytes": used,
        "quota_bytes": quota,
        "used_display": _format_bytes(used),
        "quota_display": _format_bytes(quota),
        "usage_percent": min(pct, 100),
    }


@router.get("/list")
def list_files(
    path: str = "",
    user: UserInfo = Depends(get_current_user),
):
    """列出目录内容"""
    target = _safe_resolve(user.user_id, path)
    if not target.exists():
        if target == _user_dir(user.user_id).resolve():
            target.mkdir(parents=True, exist_ok=True)
        else:
            raise HTTPException(404, "目录不存在")

    if not target.is_dir():
        raise HTTPException(400, "不是目录")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            name = entry.name
            if name.startswith("."):
                continue
            if _should_hide_entry(path, name, entry.is_dir()):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            items.append({
                "name": name,
                "is_dir": entry.is_dir(),
                "size": st.st_size if entry.is_file() else 0,
                "mtime": int(st.st_mtime),
            })
    except PermissionError:
        raise HTTPException(403, "无权限访问该目录")

    return {"path": path, "items": items}


@router.post("/download-token")
def create_download_token(
    req: DownloadTokenRequest,
    user: UserInfo = Depends(get_current_user),
):
    """生成短时效下载 token (5分钟)"""
    target = _safe_resolve(user.user_id, req.path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "文件不存在")
    token = _create_download_token(user.user_id, req.path, user.username)
    return {"token": token, "expires_in": 300}


@router.get("/download")
def download_file(
    request: Request,
    path: str = "",
    _token: str = "",
):
    """X-Accel-Redirect 下载 — 支持 download token 或 JWT header"""
    user_id = None
    username = None

    if _token:
        payload = _verify_download_token(_token)
        user_id = payload["user_id"]
        username = payload.get("username")
        path = payload.get("path", path)
    else:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth_header[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM],
                )
                user_id = payload["user_id"]
                username = payload.get("username")
            except jwt.InvalidTokenError:
                raise HTTPException(401, "认证失败")
        else:
            raise HTTPException(401, "未提供认证")

    target = _safe_resolve(user_id, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "文件不存在")

    filename = target.name
    # 清除可能导致 HTTP header injection 的字符
    safe_filename = re.sub(r'[\r\n\x00]', '_', filename)
    ascii_name = safe_filename.encode("ascii", "replace").decode()
    encoded_name = quote(safe_filename)
    content_disp = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{encoded_name}"
    )

    user_dir_name = f"portal_u{user_id}"
    rel = target.relative_to(_user_dir(user_id).resolve())
    # 路径每段分别 URL 编码 — HTTP header 只能是 Latin-1
    rel_encoded = "/".join(quote(part) for part in rel.parts)
    accel_path = f"/internal-drive/{user_dir_name}/{rel_encoded}"

    try:
        log_action(
            user_id=user_id, username=username or f"user_{user_id}",
            action="file_download", target_name=path,
            ip_address=request.client.host if request.client else "unknown",
        )
    except Exception:
        pass

    return Response(
        content="",
        headers={
            "X-Accel-Redirect": accel_path,
            "Content-Disposition": content_disp,
            "Content-Type": "application/octet-stream",
        },
    )


@router.post("/upload/init")
def upload_init(
    request: Request,
    path: str = Form(...),
    size: int = Form(...),
    user: UserInfo = Depends(get_current_user),
):
    """初始化上传 / 恢复断点"""
    if size <= 0:
        raise HTTPException(400, "文件大小无效")
    if size > MAX_FILE_SIZE:
        raise HTTPException(422, f"文件超过大小限制 ({_format_bytes(MAX_FILE_SIZE)})")

    filename = Path(path).name
    _validate_filename(filename)

    used = _get_usage_sync(user.user_id)
    quota = _get_quota(user.user_id)
    if used + size > quota:
        raise HTTPException(
            422,
            f"空间不足: 已用 {_format_bytes(used)}, 配额 {_format_bytes(quota)}, "
            f"需要 {_format_bytes(size)}",
        )

    target = _safe_resolve(user.user_id, path)
    target.parent.mkdir(parents=True, exist_ok=True)

    uploads_dir = _user_dir(user.user_id) / UPLOAD_TEMP_DIR
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # 断点恢复
    for meta_file in uploads_dir.glob("*.meta"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("path") == path and meta.get("size") == size:
                upload_id = meta_file.stem
                tmp_file = uploads_dir / f"{upload_id}.tmp"
                offset = tmp_file.stat().st_size if tmp_file.exists() else 0
                return {
                    "upload_id": upload_id,
                    "offset": offset,
                    "chunk_size": CHUNK_SIZE_MB * 1048576,
                }
        except (json.JSONDecodeError, OSError):
            continue

    upload_id = uuid.uuid4().hex[:16]
    meta_path = uploads_dir / f"{upload_id}.meta"
    tmp_path = uploads_dir / f"{upload_id}.tmp"

    meta_path.write_text(
        json.dumps({
            "path": path, "size": size,
            "user_id": user.user_id, "created": time.time(),
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp_path.touch()

    return {
        "upload_id": upload_id,
        "offset": 0,
        "chunk_size": CHUNK_SIZE_MB * 1048576,
    }


@router.post("/upload/chunk")
async def upload_chunk(
    request: Request,
    upload_id: str = Form(...),
    offset: int = Form(...),
    chunk: UploadFile = File(...),
    user: UserInfo = Depends(get_current_user),
):
    """上传分片"""
    _validate_upload_id(upload_id)
    uploads_dir = _user_dir(user.user_id) / UPLOAD_TEMP_DIR
    meta_path = uploads_dir / f"{upload_id}.meta"
    tmp_path = uploads_dir / f"{upload_id}.tmp"

    if not meta_path.exists():
        raise HTTPException(404, "上传任务不存在")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    current_size = tmp_path.stat().st_size if tmp_path.exists() else 0
    if offset != current_size:
        raise HTTPException(409, f"偏移量不匹配: 期望 {current_size}, 收到 {offset}")

    chunk_data = await chunk.read()
    chunk_len = len(chunk_data)

    # 配额二次检查
    used = _get_usage_sync(user.user_id)
    quota = _get_quota(user.user_id)
    if used + chunk_len > quota:
        raise HTTPException(422, "空间不足，上传中止")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _sync_append, tmp_path, chunk_data)

    new_size = current_size + chunk_len
    if new_size > meta["size"]:
        # 数据超过声明大小 — 清理并拒绝
        try:
            tmp_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(400, "数据量超过声明的文件大小")
    complete = new_size >= meta["size"]

    if complete:
        final_path = _safe_resolve(user.user_id, meta["path"])
        final_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(tmp_path), str(final_path))
        except OSError as e:
            raise HTTPException(500, f"文件保存失败: {e}")
        try:
            meta_path.unlink()
        except OSError:
            pass
        _invalidate_usage_cache(user.user_id)
        client_ip = request.client.host if request.client else "unknown"
        log_action(
            user_id=user.user_id, username=user.username,
            action="file_upload", target_name=meta["path"],
            detail={"size": meta["size"], "size_display": _format_bytes(meta["size"])},
            ip_address=client_ip,
        )

    return {"offset": new_size, "complete": complete}


@router.delete("/upload/{upload_id}")
def cancel_upload(
    upload_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """取消上传"""
    _validate_upload_id(upload_id)
    uploads_dir = _user_dir(user.user_id) / UPLOAD_TEMP_DIR
    meta_path = uploads_dir / f"{upload_id}.meta"
    tmp_path = uploads_dir / f"{upload_id}.tmp"

    deleted = False
    for p in (meta_path, tmp_path):
        try:
            if p.exists():
                p.unlink()
                deleted = True
        except OSError:
            pass

    if deleted:
        _invalidate_usage_cache(user.user_id)
    return {"message": "已取消"}


@router.delete("/file")
def delete_file(
    path: str = "",
    request: Request = None,
    user: UserInfo = Depends(get_current_user),
):
    """删除文件或目录"""
    if not path or path in (".", "/"):
        raise HTTPException(400, "不能删除根目录")

    target = _safe_resolve(user.user_id, path)
    if not target.exists():
        raise HTTPException(404, "文件不存在")

    name = target.name
    try:
        if target.is_dir():
            shutil.rmtree(str(target))
        else:
            target.unlink()
    except PermissionError:
        raise HTTPException(
            423, f"'{name}' 正在被占用，请关闭远程应用中的文件后重试",
        )
    except OSError as e:
        raise HTTPException(500, f"删除失败: {e}")

    _invalidate_usage_cache(user.user_id)
    client_ip = request.client.host if request and request.client else "unknown"
    log_action(
        user_id=user.user_id, username=user.username,
        action="file_delete", target_name=path,
        ip_address=client_ip,
    )
    return {"message": "已删除"}


@router.post("/mkdir")
def make_directory(
    req: MkdirRequest,
    user: UserInfo = Depends(get_current_user),
):
    """新建文件夹"""
    parts = req.path.rstrip("/").split("/")
    folder_name = parts[-1] if parts else ""
    _validate_filename(folder_name)

    target = _safe_resolve(user.user_id, req.path)
    if target.exists():
        raise HTTPException(409, "文件夹已存在")

    target.mkdir(parents=True, exist_ok=True)
    return {"message": "已创建"}


# ============================================
# 清理函数 (由 app.py 后台任务调用)
# ============================================

def cleanup_stale_uploads():
    """清理超过 N 小时的过期上传临时文件"""
    cutoff = time.time() - CLEANUP_STALE_HOURS * 3600
    cleaned = 0

    if not DRIVE_BASE.exists():
        return

    for user_dir in DRIVE_BASE.iterdir():
        if not user_dir.is_dir() or not user_dir.name.startswith("portal_u"):
            continue
        uploads_dir = user_dir / UPLOAD_TEMP_DIR
        if not uploads_dir.exists():
            continue
        for meta_file in uploads_dir.glob("*.meta"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("created", 0) < cutoff:
                    upload_id = meta_file.stem
                    tmp_file = uploads_dir / f"{upload_id}.tmp"
                    meta_file.unlink(missing_ok=True)
                    if tmp_file.exists():
                        tmp_file.unlink(missing_ok=True)
                    cleaned += 1
            except (json.JSONDecodeError, OSError):
                continue

    if cleaned:
        logger.info("清理了 %d 个过期上传任务", cleaned)
