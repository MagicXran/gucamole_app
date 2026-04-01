"""
FastAPI 路由 - RemoteApp 门户 API
"""

import logging
import uuid
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from backend.database import db, CONFIG
from backend.models import (
    LaunchOrQueueResponse,
    LaunchQueueConsumeRequest,
    QueueStatusResponse,
    ResourcePoolCardResponse,
    UserInfo,
)
from backend.guacamole_crypto import GuacamoleCrypto
from backend.guacamole_service import GuacamoleService
from backend.resource_pool_service import ResourcePoolService
from backend.auth import get_current_user
from backend.audit import log_action
from backend.structured_logging import log_event

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
pool_service = ResourcePoolService(db=db)


def _build_all_connections(user_id: int) -> dict:
    """查询该用户所有可用应用，构建完整的 connections dict。

    将所有应用打包到一个 token 中，确保同一用户的所有标签
    共享同一个 Guacamole session（解决 localStorage 多标签冲突）。
    """
    query = """
        SELECT a.id, a.hostname, a.port, a.rdp_username, a.rdp_password,
               a.domain, a.security, a.ignore_cert,
               a.remote_app, a.remote_app_dir, a.remote_app_args,
               a.color_depth, a.disable_gfx, a.resize_method,
               a.enable_wallpaper, a.enable_font_smoothing,
               a.disable_copy, a.disable_paste,
               a.enable_audio, a.enable_audio_input,
               a.enable_printing, a.timezone, a.keyboard_layout
        FROM remote_app a
        JOIN remote_app_acl acl ON a.id = acl.app_id
        WHERE acl.user_id = %(user_id)s AND a.is_active = 1
    """
    apps = db.execute_query(query, {"user_id": user_id})

    # Drive redirection 全局配置
    drive_cfg = CONFIG.get("guacamole", {}).get("drive", {})
    drive_enabled = drive_cfg.get("enabled", False)
    drive_name = drive_cfg.get("name", "GuacDrive")
    drive_base = drive_cfg.get("base_path", "/drive")
    drive_create = drive_cfg.get("create_path", True)

    connections = {}
    for app in apps:
        # Per-user 隔离: /drive/portal_u{user_id}
        user_drive_path = f"{drive_base}/portal_u{user_id}" if drive_enabled else ""

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
            enable_drive=drive_enabled,
            drive_name=drive_name,
            drive_path=user_drive_path,
            create_drive_path=drive_create,
            # RDP 高级参数
            color_depth=app.get("color_depth"),
            disable_gfx=bool(app.get("disable_gfx", 1)),
            resize_method=app.get("resize_method") or "display-update",
            enable_wallpaper=bool(app.get("enable_wallpaper", 0)),
            enable_font_smoothing=bool(app.get("enable_font_smoothing", 1)),
            disable_copy=bool(app.get("disable_copy", 0)),
            disable_paste=bool(app.get("disable_paste", 0)),
            enable_audio=bool(app.get("enable_audio", 1)),
            enable_audio_input=bool(app.get("enable_audio_input", 0)),
            enable_printing=bool(app.get("enable_printing", 0)),
            timezone=app.get("timezone") or None,
            keyboard_layout=app.get("keyboard_layout") or None,
        )
        connections.update(conn)
    return connections


@router.get("/", response_model=List[ResourcePoolCardResponse])
def list_apps(user: UserInfo = Depends(get_current_user)):
    """获取当前用户可访问的资源池卡片列表"""
    return pool_service.list_user_pools(user.user_id)


@router.get("/queue/{queue_id}", response_model=QueueStatusResponse)
def get_queue_status(
    queue_id: int,
    user: UserInfo = Depends(get_current_user),
):
    try:
        return pool_service.get_queue_status(queue_id=queue_id, user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.delete("/queue/{queue_id}", response_model=QueueStatusResponse)
def cancel_queue(
    queue_id: int,
    user: UserInfo = Depends(get_current_user),
):
    try:
        result = pool_service.cancel_queue(queue_id=queue_id, user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    from backend.monitor import dispatch_ready_queue_entries
    dispatch_ready_queue_entries()
    return result


@router.post("/launch/{app_id}", response_model=LaunchOrQueueResponse)
async def launch_app(
    app_id: int,
    request: Request,
    req: LaunchQueueConsumeRequest | None = Body(default=None),
    user: UserInfo = Depends(get_current_user),
):
    """启动资源池成员或进入排队。"""
    try:
        decision = pool_service.prepare_launch(
            user_id=user.user_id,
            requested_app_id=app_id,
            queue_id=req.queue_id if req else None,
        )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_403_FORBIDDEN if "无权访问" in detail else status.HTTP_409_CONFLICT
        raise HTTPException(code, detail)

    if decision["status"] != "started":
        log_event(
            logger,
            logging.INFO,
            "launch_queued",
            request_id=getattr(request.state, "request_id", None),
            user_id=user.user_id,
            requested_app_id=app_id,
            pool_id=int(decision.get("pool_id") or 0),
            queue_id=int(decision.get("queue_id") or 0),
            position=int(decision.get("position") or 0),
            status=str(decision["status"]),
        )
        return LaunchOrQueueResponse(
            status=str(decision["status"]),
            queue_id=int(decision.get("queue_id") or 0),
            position=int(decision.get("position") or 0),
            pool_id=int(decision.get("pool_id") or 0),
        )

    # 构建该用户所有可用成员的连接参数；token 继续按用户复用
    connection_name = str(decision["connection_name"])
    connections = _build_all_connections(user.user_id)
    if connection_name not in connections:
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error="连接构建异常",
            )
            log_event(
                logger,
                logging.WARNING,
                "launch_requeued",
                request_id=getattr(request.state, "request_id", None),
                user_id=user.user_id,
                requested_app_id=app_id,
                pool_id=int(decision["pool_id"]),
                queue_id=int(decision["queue_id"]),
                reason="connections_missing",
            )
        log_event(
            logger,
            logging.ERROR,
            "launch_failed",
            request_id=getattr(request.state, "request_id", None),
            user_id=user.user_id,
            requested_app_id=app_id,
            pool_id=int(decision["pool_id"]),
            queue_id=int(decision.get("queue_id") or 0),
            reason="connections_missing",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="连接构建异常",
        )

    # 4. 复用或创建 session → 拿 URL
    #    动态跟随请求的 Host，确保 redirect 指向客户端实际访问的地址
    host = request.headers.get("host") or request.headers.get("x-forwarded-host", "")
    scheme = request.headers.get("x-forwarded-proto", "http")
    dynamic_external_url = f"{scheme}://{host}/guacamole" if host else ""

    guac_username = f"portal_u{user.user_id}"
    try:
        redirect_url = await guac_service.launch_connection(
            username=guac_username,
            connections=connections,
            target_connection_name=connection_name,
            external_url=dynamic_external_url,
        )
    except Exception as exc:
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error=str(exc),
            )
            log_event(
                logger,
                logging.WARNING,
                "launch_requeued",
                request_id=getattr(request.state, "request_id", None),
                user_id=user.user_id,
                requested_app_id=app_id,
                pool_id=int(decision["pool_id"]),
                queue_id=int(decision["queue_id"]),
                reason="guacamole_unavailable",
            )
        log_event(
            logger,
            logging.ERROR,
            "launch_failed",
            request_id=getattr(request.state, "request_id", None),
            user_id=user.user_id,
            requested_app_id=app_id,
            pool_id=int(decision["pool_id"]),
            queue_id=int(decision.get("queue_id") or 0),
            reason="guacamole_unavailable",
        )
        logger.exception("启动 Guacamole 连接失败: app_id=%d", app_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="远程连接服务暂时不可用",
        )

    # 5. 审计: 启动应用
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        user_id=user.user_id, username=user.username, action="launch_app",
        target_type="app",
        target_id=int(decision["member_app_id"]),
        target_name=str(decision["requested_app_name"]),
        ip_address=client_ip,
    )

    # 6. 创建活跃会话记录 (实时监控 + 资源池占用)
    session_id = str(uuid.uuid4())
    try:
        inserted = db.execute_update(
            """
            INSERT INTO active_session (session_id, user_id, app_id, pool_id, queue_id, last_activity_at)
            VALUES (%(sid)s, %(uid)s, %(aid)s, %(pid)s, %(qid)s, NOW())
            """,
            {
                "sid": session_id,
                "uid": user.user_id,
                "aid": int(decision["member_app_id"]),
                "pid": int(decision["pool_id"]),
                "qid": decision.get("queue_id"),
            },
        )
        if inserted <= 0:
            raise RuntimeError("active_session 未写入")
    except Exception as exc:
        logger.warning("插入 active_session 失败", exc_info=True)
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error=str(exc),
            )
            log_event(
                logger,
                logging.WARNING,
                "launch_requeued",
                request_id=getattr(request.state, "request_id", None),
                user_id=user.user_id,
                requested_app_id=app_id,
                pool_id=int(decision["pool_id"]),
                queue_id=int(decision["queue_id"]),
                reason="active_session_insert_failed",
            )
        log_event(
            logger,
            logging.ERROR,
            "launch_failed",
            request_id=getattr(request.state, "request_id", None),
            user_id=user.user_id,
            requested_app_id=app_id,
            pool_id=int(decision["pool_id"]),
            queue_id=int(decision.get("queue_id") or 0),
            reason="active_session_insert_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话记录写入失败，请重试",
        )

    if decision.get("queue_id"):
        pool_service.mark_queue_fulfilled(
            queue_id=int(decision["queue_id"]),
            assigned_app_id=int(decision["member_app_id"]),
        )

    log_event(
        logger,
        logging.INFO,
        "launch_started",
        request_id=getattr(request.state, "request_id", None),
        user_id=user.user_id,
        requested_app_id=app_id,
        member_app_id=int(decision["member_app_id"]),
        pool_id=int(decision["pool_id"]),
        queue_id=int(decision.get("queue_id") or 0),
    )

    return LaunchOrQueueResponse(
        status="started",
        redirect_url=redirect_url,
        connection_name=connection_name,
        session_id=session_id,
        pool_id=int(decision["pool_id"]),
        queue_id=int(decision.get("queue_id") or 0),
    )
