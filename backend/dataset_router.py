"""
结果中心 API - 浏览用户个人空间中的结果文件
"""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.database import CONFIG
from backend.models import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

_drive_cfg = CONFIG.get("guacamole", {}).get("drive", {})
DRIVE_BASE = Path(_drive_cfg.get("base_path", "/drive"))
RESULTS_ROOT_NAME = _drive_cfg.get("results_root", "Output")
SUPPORTED_EXTENSIONS = {".vtk", ".vtp", ".vtu", ".stl", ".obj", ".gltf", ".glb"}
_MIME_MAP = {
    ".vtk": "application/octet-stream",
    ".vtp": "application/xml",
    ".vtu": "application/xml",
    ".stl": "application/octet-stream",
    ".obj": "text/plain",
    ".gltf": "application/json",
    ".glb": "application/octet-stream",
}


class DatasetItem(BaseModel):
    """结果项"""
    name: str
    path: str
    is_dir: bool
    size_bytes: int
    size_human: str
    extension: str


class DatasetListResponse(BaseModel):
    """结果目录响应"""
    path: str
    items: List[DatasetItem]


def _human_size(size_bytes: int) -> str:
    """字节数转可读字符串"""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _normalize_relative_path(path: str) -> str:
    if not path or path in (".", "/", "\\"):
        return ""
    return path.replace("\\", "/").strip("/")


def _user_results_root(user_id: int) -> Path:
    user_dir = (DRIVE_BASE / f"portal_u{user_id}").resolve()
    results_root = (user_dir / RESULTS_ROOT_NAME).resolve()
    try:
        results_root.relative_to(user_dir)
    except ValueError:
        logger.error("结果目录配置越界: %s", RESULTS_ROOT_NAME)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="结果目录配置无效",
        )
    return results_root


def _resolve_results_path(user_id: int, relative_path: str) -> tuple[Path, Path]:
    results_root = _user_results_root(user_id)
    normalized_path = _normalize_relative_path(relative_path)
    target = (results_root / normalized_path).resolve() if normalized_path else results_root
    try:
        target.relative_to(results_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="非法路径",
        )
    return results_root, target


def _relative_path(results_root: Path, target: Path) -> str:
    if target == results_root:
        return ""
    return "/".join(target.relative_to(results_root).parts)


def _build_item(results_root: Path, entry: Path) -> DatasetItem | None:
    resolved_entry = entry.resolve()
    try:
        resolved_entry.relative_to(results_root)
    except ValueError:
        return None

    is_dir = resolved_entry.is_dir()
    if not is_dir and resolved_entry.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None

    size_bytes = 0
    size_human = ""
    extension = ""
    if not is_dir:
        stat = resolved_entry.stat()
        size_bytes = stat.st_size
        size_human = _human_size(stat.st_size)
        extension = resolved_entry.suffix.lower()

    return DatasetItem(
        name=resolved_entry.name,
        path=_relative_path(results_root, resolved_entry),
        is_dir=is_dir,
        size_bytes=size_bytes,
        size_human=size_human,
        extension=extension,
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    path: str = "",
    user: UserInfo = Depends(get_current_user),
):
    """列出当前用户结果目录中的目录和支持文件"""
    results_root, target = _resolve_results_path(user.user_id, path)
    current_path = _relative_path(results_root, target)

    if not target.exists():
        if current_path == "":
            return DatasetListResponse(path="", items=[])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目录不存在",
        )

    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不是目录",
        )

    items: list[DatasetItem] = []
    for entry in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if entry.name.startswith("."):
            continue
        item = _build_item(results_root, entry)
        if item is not None:
            items.append(item)

    return DatasetListResponse(path=current_path, items=items)


@router.get("/file")
def get_dataset_file(
    path: str,
    user: UserInfo = Depends(get_current_user),
):
    """读取当前用户结果目录中的支持文件"""
    _, target = _resolve_results_path(user.user_id, path)

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    extension = target.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件格式",
        )

    return FileResponse(
        path=str(target),
        media_type=_MIME_MAP.get(extension, "application/octet-stream"),
        filename=target.name,
    )


@router.get("/{file_path:path}")
def get_dataset_file_legacy(
    file_path: str,
    user: UserInfo = Depends(get_current_user),
):
    """兼容旧版 viewer 的直接文件路径下载"""
    return get_dataset_file(path=file_path, user=user)
