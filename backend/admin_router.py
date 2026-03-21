"""
管理后台 API 路由 - 应用/用户/ACL/审计日志管理
"""

import logging
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.database import db
from backend.auth import require_admin
from backend.audit import log_action
from backend.router import guac_service
from backend.models import (
    UserInfo,
    AppCreateRequest, AppUpdateRequest, AppAdminResponse,
    UserCreateRequest, UserUpdateRequest, UserAdminResponse,
    AclUpdateRequest, AuditLogResponse, PaginatedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================
# 应用管理
# ============================================

@router.get("/apps", response_model=list[AppAdminResponse])
def list_apps(admin: UserInfo = Depends(require_admin)):
    """列出所有应用（含 inactive）"""
    return db.execute_query("SELECT * FROM remote_app ORDER BY id")


@router.post("/apps", response_model=AppAdminResponse, status_code=201)
def create_app(
    req: AppCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """创建应用"""
    db.execute_update(
        """
        INSERT INTO remote_app
            (name, icon, protocol, hostname, port,
             rdp_username, rdp_password, domain, security, ignore_cert,
             remote_app, remote_app_dir, remote_app_args,
             color_depth, disable_gfx, resize_method,
             enable_wallpaper, enable_font_smoothing,
             disable_copy, disable_paste,
             enable_audio, enable_audio_input, enable_printing,
             timezone, keyboard_layout)
        VALUES
            (%(name)s, %(icon)s, %(protocol)s, %(hostname)s, %(port)s,
             %(rdp_username)s, %(rdp_password)s, %(domain)s, %(security)s, %(ignore_cert)s,
             %(remote_app)s, %(remote_app_dir)s, %(remote_app_args)s,
             %(color_depth)s, %(disable_gfx)s, %(resize_method)s,
             %(enable_wallpaper)s, %(enable_font_smoothing)s,
             %(disable_copy)s, %(disable_paste)s,
             %(enable_audio)s, %(enable_audio_input)s, %(enable_printing)s,
             %(timezone)s, %(keyboard_layout)s)
        """,
        {
            "name": req.name, "icon": req.icon, "protocol": req.protocol,
            "hostname": req.hostname, "port": req.port,
            "rdp_username": req.rdp_username or None,
            "rdp_password": req.rdp_password or None,
            "domain": req.domain, "security": req.security,
            "ignore_cert": 1 if req.ignore_cert else 0,
            "remote_app": req.remote_app or None,
            "remote_app_dir": req.remote_app_dir or None,
            "remote_app_args": req.remote_app_args or None,
            "color_depth": req.color_depth,
            "disable_gfx": 1 if req.disable_gfx else 0,
            "resize_method": req.resize_method,
            "enable_wallpaper": 1 if req.enable_wallpaper else 0,
            "enable_font_smoothing": 1 if req.enable_font_smoothing else 0,
            "disable_copy": 1 if req.disable_copy else 0,
            "disable_paste": 1 if req.disable_paste else 0,
            "enable_audio": 1 if req.enable_audio else 0,
            "enable_audio_input": 1 if req.enable_audio_input else 0,
            "enable_printing": 1 if req.enable_printing else 0,
            "timezone": req.timezone or None,
            "keyboard_layout": req.keyboard_layout or None,
        },
    )
    app = db.execute_query(
        "SELECT * FROM remote_app WHERE name = %(name)s ORDER BY id DESC LIMIT 1",
        {"name": req.name}, fetch_one=True,
    )
    guac_service.invalidate_all_sessions()
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_create_app",
        "app", app["id"], req.name, ip_address=client_ip,
    )
    return app


@router.put("/apps/{app_id}", response_model=AppAdminResponse)
def update_app(
    app_id: int,
    req: AppUpdateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """修改应用"""
    existing = db.execute_query(
        "SELECT * FROM remote_app WHERE id = %(id)s", {"id": app_id}, fetch_one=True,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return existing

    # 构建动态 SET 子句
    _BOOL_COLUMNS = {
        "ignore_cert", "disable_gfx", "enable_wallpaper", "enable_font_smoothing",
        "disable_copy", "disable_paste", "enable_audio", "enable_audio_input",
        "enable_printing", "is_active",
    }
    set_parts = []
    params = {"id": app_id}
    for key, value in updates.items():
        if key in _BOOL_COLUMNS:
            value = 1 if value else 0
        set_parts.append(f"{key} = %({key})s")
        params[key] = value

    db.execute_update(
        f"UPDATE remote_app SET {', '.join(set_parts)} WHERE id = %(id)s", params,
    )
    guac_service.invalidate_all_sessions()
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_update_app",
        "app", app_id, existing["name"], ip_address=client_ip,
    )
    return db.execute_query(
        "SELECT * FROM remote_app WHERE id = %(id)s", {"id": app_id}, fetch_one=True,
    )


@router.delete("/apps/{app_id}")
def delete_app(
    app_id: int,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """软删除应用 (is_active=0)"""
    existing = db.execute_query(
        "SELECT id, name FROM remote_app WHERE id = %(id)s", {"id": app_id}, fetch_one=True,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")

    db.execute_update(
        "UPDATE remote_app SET is_active = 0 WHERE id = %(id)s", {"id": app_id},
    )
    guac_service.invalidate_all_sessions()
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_delete_app",
        "app", app_id, existing["name"], ip_address=client_ip,
    )
    return {"message": "已禁用"}


# ============================================
# 用户管理
# ============================================

@router.get("/users")
def list_users(admin: UserInfo = Depends(require_admin)):
    """列出所有用户（含配额信息）"""
    rows = db.execute_query(
        "SELECT id, username, display_name, is_admin, is_active, quota_bytes FROM portal_user ORDER BY id"
    )
    from backend.file_router import _get_usage_sync, _format_bytes, DEFAULT_QUOTA_BYTES
    for row in rows:
        used = _get_usage_sync(row["id"])
        row["used_bytes"] = used
        row["used_display"] = _format_bytes(used)
        qb = row.get("quota_bytes")
        row["quota_display"] = _format_bytes(qb) if qb else _format_bytes(DEFAULT_QUOTA_BYTES)
    return rows


@router.post("/users", response_model=UserAdminResponse, status_code=201)
def create_user(
    req: UserCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """创建用户"""
    # 检查用户名冲突
    dup = db.execute_query(
        "SELECT 1 FROM portal_user WHERE username = %(u)s", {"u": req.username}, fetch_one=True,
    )
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")

    hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    quota_bytes = None
    if req.quota_gb is not None and req.quota_gb > 0:
        quota_bytes = int(req.quota_gb * 1073741824)
    db.execute_update(
        """
        INSERT INTO portal_user (username, password_hash, display_name, is_admin, quota_bytes)
        VALUES (%(username)s, %(hash)s, %(display)s, %(admin)s, %(quota)s)
        """,
        {
            "username": req.username, "hash": hashed,
            "display": req.display_name or req.username,
            "admin": 1 if req.is_admin else 0,
            "quota": quota_bytes,
        },
    )
    user = db.execute_query(
        "SELECT id, username, display_name, is_admin, is_active FROM portal_user WHERE username = %(u)s",
        {"u": req.username}, fetch_one=True,
    )
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_create_user",
        "user", user["id"], req.username, ip_address=client_ip,
    )
    return user


@router.put("/users/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: int,
    req: UserUpdateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """修改用户"""
    existing = db.execute_query(
        "SELECT * FROM portal_user WHERE id = %(id)s", {"id": user_id}, fetch_one=True,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")

    set_parts = []
    params = {"id": user_id}

    if req.display_name is not None:
        set_parts.append("display_name = %(display_name)s")
        params["display_name"] = req.display_name
    if req.is_admin is not None:
        set_parts.append("is_admin = %(is_admin)s")
        params["is_admin"] = 1 if req.is_admin else 0
    if req.is_active is not None:
        set_parts.append("is_active = %(is_active)s")
        params["is_active"] = 1 if req.is_active else 0
    if req.password:
        hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        set_parts.append("password_hash = %(password_hash)s")
        params["password_hash"] = hashed
    if req.quota_gb is not None:
        if req.quota_gb <= 0:
            set_parts.append("quota_bytes = NULL")
        else:
            set_parts.append("quota_bytes = %(quota_bytes)s")
            params["quota_bytes"] = int(req.quota_gb * 1073741824)

    if not set_parts:
        return db.execute_query(
            "SELECT id, username, display_name, is_admin, is_active FROM portal_user WHERE id = %(id)s",
            {"id": user_id}, fetch_one=True,
        )

    db.execute_update(
        f"UPDATE portal_user SET {', '.join(set_parts)} WHERE id = %(id)s", params,
    )
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_update_user",
        "user", user_id, existing["username"], ip_address=client_ip,
    )
    return db.execute_query(
        "SELECT id, username, display_name, is_admin, is_active FROM portal_user WHERE id = %(id)s",
        {"id": user_id}, fetch_one=True,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """软删除用户 (is_active=0)"""
    existing = db.execute_query(
        "SELECT id, username FROM portal_user WHERE id = %(id)s", {"id": user_id}, fetch_one=True,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user_id == admin.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")

    db.execute_update(
        "UPDATE portal_user SET is_active = 0 WHERE id = %(id)s", {"id": user_id},
    )
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_delete_user",
        "user", user_id, existing["username"], ip_address=client_ip,
    )
    return {"message": "已禁用"}


# ============================================
# ACL 管理
# ============================================

@router.get("/users/{user_id}/acl")
def get_user_acl(user_id: int, admin: UserInfo = Depends(require_admin)):
    """获取用户权限（app_id 列表）"""
    rows = db.execute_query(
        "SELECT app_id FROM remote_app_acl WHERE user_id = %(uid)s",
        {"uid": user_id},
    )
    return {"user_id": user_id, "app_ids": [r["app_id"] for r in rows]}


@router.put("/users/{user_id}/acl")
def update_user_acl(
    user_id: int,
    req: AclUpdateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """覆盖式设置权限"""
    # 确认用户存在
    user = db.execute_query(
        "SELECT id, username FROM portal_user WHERE id = %(id)s", {"id": user_id}, fetch_one=True,
    )
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")

    # 先清空
    db.execute_update(
        "DELETE FROM remote_app_acl WHERE user_id = %(uid)s", {"uid": user_id},
    )
    # 再插入
    for app_id in req.app_ids:
        db.execute_update(
            "INSERT IGNORE INTO remote_app_acl (user_id, app_id) VALUES (%(uid)s, %(aid)s)",
            {"uid": user_id, "aid": app_id},
        )
    guac_service.invalidate_all_sessions()

    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_update_acl",
        "user", user_id, user["username"],
        detail={"app_ids": req.app_ids}, ip_address=client_ip,
    )
    return {"user_id": user_id, "app_ids": req.app_ids}


# ============================================
# 审计日志
# ============================================

@router.get("/audit-logs", response_model=PaginatedResponse)
def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    username: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_start: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    date_end: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    admin: UserInfo = Depends(require_admin),
):
    """分页查询审计日志"""
    where_parts = []
    params = {}

    if username:
        where_parts.append("username = %(username)s")
        params["username"] = username
    if action:
        where_parts.append("action = %(action)s")
        params["action"] = action
    if date_start:
        where_parts.append("created_at >= %(date_start)s")
        params["date_start"] = date_start
    if date_end:
        where_parts.append("created_at < DATE_ADD(%(date_end)s, INTERVAL 1 DAY)")
        params["date_end"] = date_end

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    # 总数
    count_row = db.execute_query(
        f"SELECT COUNT(*) AS cnt FROM audit_log WHERE {where_clause}", params, fetch_one=True,
    )
    total = count_row["cnt"] if count_row else 0

    # 分页数据
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    items = db.execute_query(
        f"""
        SELECT id, user_id, username, action, target_type, target_id,
               target_name, detail, ip_address, created_at
        FROM audit_log
        WHERE {where_clause}
        ORDER BY id DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )

    # datetime 序列化
    for item in items:
        if item.get("created_at"):
            item["created_at"] = str(item["created_at"])

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)
