"""
FastAPI 路由 - RemoteApp 门户 API
"""

import logging
import re
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
from backend.vscode_policy_service import (
    VscodePolicyError,
    build_vscode_arguments,
    profile_from_row,
    validate_restricted_arguments,
)
from backend.auth import get_current_user
from backend.audit import log_action

logger = logging.getLogger(__name__)

_RDP_DRIVE_NAME_BAD_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_AUTO_REMOTE_APP_DIRS = {
    r"\\tsclient\GuacDrive",
    r"\\tsclient\用户数据目录",
}
_DRIVE_NAME_MAX_LENGTH = 64

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


def _resolve_transfer_policy(override_value, global_value: bool) -> bool:
    """解析 tri-state 传输策略：NULL=继承, 1=禁用, 0=允许。"""
    if override_value is None:
        return bool(global_value)
    if isinstance(override_value, str):
        value = override_value.strip().lower()
        if value in ("", "null", "none"):
            return bool(global_value)
        if value in ("1", "true"):
            return True
        if value in ("0", "false"):
            return False
    return bool(override_value)


def _build_rdp_drive_name(drive_label: object = "GuacDrive") -> str:
    """生成仅含 ASCII 的 RDPDR 共享名，规避 guacd 多字节名称截断。"""
    candidate = str(drive_label or "GuacDrive").strip()
    safe_name = _RDP_DRIVE_NAME_BAD_CHARS.sub("_", candidate).strip("._-")
    safe_name = safe_name[:_DRIVE_NAME_MAX_LENGTH].rstrip("._-")
    return safe_name or "GuacDrive"


def _build_all_connections_with_errors(user_id: int) -> tuple[dict, dict[str, str]]:
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
               a.enable_printing, a.disable_download, a.disable_upload,
               a.timezone, a.keyboard_layout,
               a.security_mode, a.vscode_control_profile_id,
               vcp.id AS vcp_id,
               vcp.profile_key AS vcp_profile_key,
               vcp.display_name AS vcp_display_name,
               vcp.description AS vcp_description,
               vcp.policy_version AS vcp_policy_version,
               vcp.is_active AS vcp_is_active,
               vcp.revision AS vcp_revision,
               vcp.permissions_json AS vcp_permissions_json,
               vcp.allowed_shells_json AS vcp_allowed_shells_json,
               vcp.allowed_tools_json AS vcp_allowed_tools_json,
               vcp.allowed_debuggers_json AS vcp_allowed_debuggers_json,
               vcp.allowed_extensions_json AS vcp_allowed_extensions_json,
               vcp.allowed_network_targets_json AS vcp_allowed_network_targets_json,
               vcp.user_data_root AS vcp_user_data_root,
               vcp.extensions_root AS vcp_extensions_root,
               vcp.default_workspace_template AS vcp_default_workspace_template,
               vcp.created_at AS vcp_created_at,
               vcp.updated_at AS vcp_updated_at
        FROM remote_app a
        JOIN remote_app_acl acl ON a.id = acl.app_id
        JOIN portal_user u ON u.id = acl.user_id
        LEFT JOIN vscode_control_profile vcp ON vcp.id = a.vscode_control_profile_id
        WHERE acl.user_id = %(user_id)s
          AND a.is_active = 1
          AND (a.security_mode <> 'admin_desktop' OR u.is_admin = 1)
    """
    apps = db.execute_query(query, {"user_id": user_id})

    # Drive redirection 全局配置
    drive_cfg = CONFIG.get("guacamole", {}).get("drive", {})
    drive_enabled = drive_cfg.get("enabled", False)
    drive_name = _build_rdp_drive_name(drive_cfg.get("name", "GuacDrive"))
    drive_base = drive_cfg.get("base_path", "/drive")
    drive_create = drive_cfg.get("create_path", True)
    drive_disable_download = bool(drive_cfg.get("disable_download", False))
    drive_disable_upload = bool(drive_cfg.get("disable_upload", False))

    connections = {}
    errors: dict[str, str] = {}
    for app in apps:
        connection_name = f"app_{app['id']}"
        # Per-user 隔离: /drive/portal_u{user_id}
        user_drive_path = f"{drive_base}/portal_u{user_id}" if drive_enabled else ""
        try:
            security_mode = str(app.get("security_mode") or "restricted_remoteapp")
            remote_app = str(app.get("remote_app") or "").strip()
            remote_app_dir = str(app.get("remote_app_dir") or "").strip()
            remote_app_args = str(app.get("remote_app_args") or "")
            if security_mode in {"restricted_remoteapp", "restricted_vscode"} and not remote_app:
                raise VscodePolicyError("受限模式缺少 remote_app，已阻止完整桌面回退")
            if remote_app and drive_enabled and (
                not remote_app_dir or remote_app_dir in _AUTO_REMOTE_APP_DIRS
            ):
                remote_app_dir = f"\\\\tsclient\\{drive_name}"

            app_disable_download = _resolve_transfer_policy(app.get("disable_download"), drive_disable_download)
            app_disable_upload = _resolve_transfer_policy(app.get("disable_upload"), drive_disable_upload)
            disable_copy = bool(app.get("disable_copy", 0))
            disable_paste = bool(app.get("disable_paste", 0))
            enable_audio = bool(app.get("enable_audio", 1))
            enable_audio_input = bool(app.get("enable_audio_input", 0))
            enable_printing = bool(app.get("enable_printing", 0))

            if security_mode == "restricted_remoteapp":
                remote_app_args = validate_restricted_arguments(remote_app_args)
                disable_copy = True
                disable_paste = True
                app_disable_download = True
                app_disable_upload = True
                enable_audio_input = False
                enable_printing = False
            elif security_mode == "restricted_vscode":
                if not app.get("vcp_id"):
                    raise VscodePolicyError("受限 VSCode 未绑定控制策略")
                validate_restricted_arguments(remote_app_args, allow_user_id=True)
                profile = profile_from_row(app, prefix="vcp_")
                remote_app_args = build_vscode_arguments(
                    profile,
                    user_id,
                    drive_name=drive_name,
                )
                permissions = profile["permissions"]
                disable_copy = not permissions["copy_remote_to_local"]
                disable_paste = not permissions["paste_local_to_remote"]
                app_disable_upload = not permissions["browser_upload"]
                app_disable_download = not permissions["browser_download"]
                enable_printing = permissions["printing"]
                enable_audio = permissions["audio_output"]
                enable_audio_input = permissions["audio_input"]
            elif security_mode != "admin_desktop":
                raise VscodePolicyError("未知安全模式")

            conn = GuacamoleCrypto.build_rdp_connection(
                name=connection_name,
                hostname=app["hostname"],
                port=app["port"],
                username=app.get("rdp_username") or "",
                password=app.get("rdp_password") or "",
                domain=app.get("domain") or "",
                security=app.get("security") or "nla",
                ignore_cert=bool(app.get("ignore_cert", True)),
                remote_app=remote_app,
                remote_app_dir=remote_app_dir,
                remote_app_args=remote_app_args,
                enable_drive=drive_enabled,
                drive_name=drive_name,
                drive_path=user_drive_path,
                create_drive_path=drive_create,
                disable_download=app_disable_download,
                disable_upload=app_disable_upload,
                color_depth=app.get("color_depth"),
                disable_gfx=bool(app.get("disable_gfx", 1)),
                resize_method=app.get("resize_method") or "display-update",
                enable_wallpaper=bool(app.get("enable_wallpaper", 0)),
                enable_font_smoothing=bool(app.get("enable_font_smoothing", 1)),
                disable_copy=disable_copy,
                disable_paste=disable_paste,
                enable_audio=enable_audio,
                enable_audio_input=enable_audio_input,
                enable_printing=enable_printing,
                timezone=app.get("timezone") or None,
                keyboard_layout=app.get("keyboard_layout") or None,
            )
            connections.update(conn)
        except (VscodePolicyError, ValueError, TypeError, KeyError, UnicodeError) as exc:
            errors[connection_name] = str(exc)
            logger.warning("跳过无效受限连接: app_id=%s reason=%s", app.get("id"), exc)
    return connections, errors


def _build_all_connections(user_id: int) -> dict:
    connections, _ = _build_all_connections_with_errors(user_id)
    return connections


@router.get("/", response_model=List[ResourcePoolCardResponse])
def list_apps(user: UserInfo = Depends(get_current_user)):
    """获取当前用户可访问的启动卡片列表"""
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
        return LaunchOrQueueResponse(
            status=str(decision["status"]),
            queue_id=int(decision.get("queue_id") or 0),
            position=int(decision.get("position") or 0),
            pool_id=decision.get("pool_id"),
        )

    # 构建该用户所有可用成员的连接参数；token 继续按用户复用
    connection_name = str(decision["connection_name"])
    connections, connection_errors = _build_all_connections_with_errors(user.user_id)
    if connection_name not in connections:
        failure_reason = connection_errors.get(connection_name, "连接构建异常")
        pool_service.mark_runtime_launch_failure(int(decision["member_app_id"]), failure_reason)
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error=failure_reason,
            )
        client_ip = request.client.host if request.client else "unknown"
        log_action(
            user_id=user.user_id,
            username=user.username,
            action="launch_blocked_by_security_policy",
            target_type="app",
            target_id=int(decision["member_app_id"]),
            target_name=str(decision["requested_app_name"]),
            detail={"reason": failure_reason},
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=failure_reason,
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
        pool_service.mark_runtime_launch_failure(int(decision["member_app_id"]), str(exc))
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error=str(exc),
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
                "pid": decision.get("session_pool_id"),
                "qid": decision.get("queue_id"),
            },
        )
        if inserted <= 0:
            raise RuntimeError("active_session 未写入")
    except Exception as exc:
        pool_service.mark_runtime_launch_failure(int(decision["member_app_id"]), str(exc))
        logger.warning("插入 active_session 失败", exc_info=True)
        if decision.get("queue_id"):
            pool_service.requeue_after_launch_failure(
                queue_id=int(decision["queue_id"]),
                last_error=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话记录写入失败，请重试",
        )

    pool_service.mark_runtime_launch_success(int(decision["member_app_id"]))

    if decision.get("queue_id"):
        pool_service.mark_queue_fulfilled(
            queue_id=int(decision["queue_id"]),
            assigned_app_id=int(decision["member_app_id"]),
        )

    return LaunchOrQueueResponse(
        status="started",
        redirect_url=redirect_url,
        connection_name=connection_name,
        session_id=session_id,
        pool_id=decision.get("pool_id"),
        queue_id=int(decision.get("queue_id") or 0),
    )
