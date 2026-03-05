"""
FastAPI 路由 - RemoteApp 门户 API
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.database import db, CONFIG
from backend.models import RemoteAppResponse, LaunchResponse, UserInfo
from backend.guacamole_crypto import GuacamoleCrypto
from backend.guacamole_service import GuacamoleService
from backend.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=CONFIG["api"]["prefix"],
    tags=["remote-apps"],
)

# 初始化 Guacamole 服务
_guac_cfg = CONFIG["guacamole"]
guac_service = GuacamoleService(
    secret_key_hex=_guac_cfg["json_secret_key"],
    internal_url=_guac_cfg["internal_url"],
    external_url=_guac_cfg["external_url"],
    expire_minutes=_guac_cfg["token_expire_minutes"],
    db=db,
)


def _build_all_connections(user_id: int) -> dict:
    """查询该用户所有可用应用，构建完整的 connections dict。

    将所有应用打包到一个 token 中，确保同一用户的所有标签
    共享同一个 Guacamole session（解决 localStorage 多标签冲突）。
    """
    query = """
        SELECT a.id, a.hostname, a.port, a.rdp_username, a.rdp_password,
               a.domain, a.security, a.ignore_cert,
               a.remote_app, a.remote_app_dir, a.remote_app_args
        FROM remote_app a
        JOIN remote_app_acl acl ON a.id = acl.app_id
        WHERE acl.user_id = %(user_id)s AND a.is_active = 1
    """
    apps = db.execute_query(query, {"user_id": user_id})
    connections = {}
    for app in apps:
        conn = GuacamoleCrypto.build_rdp_connection(
            name=f"app_{app['id']}",
            hostname=app["hostname"],
            port=app["port"],
            username=app.get("rdp_username") or "",
            password=app.get("rdp_password") or "",
            domain=app.get("domain") or "",
            security=app.get("security") or "nla",
            ignore_cert=bool(app.get("ignore_cert", True)),
            remote_app=app.get("remote_app") or "",
            remote_app_dir=app.get("remote_app_dir") or "",
            remote_app_args=app.get("remote_app_args") or "",
        )
        connections.update(conn)
    return connections


@router.get("/", response_model=List[RemoteAppResponse])
def list_apps(user: UserInfo = Depends(get_current_user)):
    """获取当前用户可访问的 RemoteApp 列表"""
    query = """
        SELECT a.id, a.name, a.icon, a.protocol, a.hostname,
               a.port, a.remote_app, a.is_active
        FROM remote_app a
        JOIN remote_app_acl acl ON a.id = acl.app_id
        WHERE acl.user_id = %(user_id)s
          AND a.is_active = 1
        ORDER BY a.name
    """
    return db.execute_query(query, {"user_id": user.user_id})


@router.post("/launch/{app_id}", response_model=LaunchResponse)
async def launch_app(app_id: int, user: UserInfo = Depends(get_current_user)):
    """启动 RemoteApp，返回 Guacamole 重定向 URL"""

    # 1. ACL 权限校验
    acl_query = """
        SELECT 1 FROM remote_app_acl
        WHERE user_id = %(user_id)s AND app_id = %(app_id)s
    """
    acl = db.execute_query(acl_query, {"user_id": user.user_id, "app_id": app_id}, fetch_one=True)
    if not acl:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该应用",
        )

    # 2. 验证目标应用存在
    app_check = """
        SELECT id FROM remote_app WHERE id = %(app_id)s AND is_active = 1
    """
    app = db.execute_query(app_check, {"app_id": app_id}, fetch_one=True)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="应用不存在或已禁用",
        )

    # 3. 构建该用户所有可用应用的连接参数
    #    全部打包到一个 token，确保多标签共享同一 session
    connection_name = f"app_{app_id}"
    connections = _build_all_connections(user.user_id)
    if connection_name not in connections:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="连接构建异常",
        )

    # 4. 复用或创建 session → 拿 URL
    guac_username = f"portal_u{user.user_id}"
    try:
        redirect_url = await guac_service.launch_connection(
            username=guac_username,
            connections=connections,
            target_connection_name=connection_name,
        )
    except Exception:
        logger.exception("启动 Guacamole 连接失败: app_id=%d", app_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="远程连接服务暂时不可用",
        )

    return LaunchResponse(
        redirect_url=redirect_url,
        connection_name=connection_name,
    )
