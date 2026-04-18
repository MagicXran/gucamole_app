"""
管理后台 API 路由 - 应用/用户/ACL/审计日志管理
"""

import json
import logging
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.database import db
from backend.auth import require_admin
from backend.audit import log_action
from backend.router import guac_service
from backend.resource_pool_service import ResourcePoolService
from backend.script_profiles import get_script_profile, list_script_profiles, resolve_script_runtime_settings
from backend.models import (
    UserInfo,
    AppCreateRequest, AppUpdateRequest, AppAdminResponse,
    UserCreateRequest, UserUpdateRequest, UserAdminResponse,
    AclUpdateRequest, AuditLogResponse, PaginatedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])
pool_service = ResourcePoolService(db=db)


def _ensure_pool_exists(pool_id: int | None, conn=None):
    if pool_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "应用必须绑定到资源池")
    pool = db.execute_query(
        "SELECT id FROM resource_pool WHERE id = %(id)s AND is_active = 1",
        {"id": pool_id},
        fetch_one=True,
        conn=conn,
    )
    if not pool:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "资源池不存在或已禁用")


def _ensure_pool_kind_consistency(pool_id: int | None, app_kind: str | None, *, app_id: int | None = None, conn=None):
    if pool_id is None or not app_kind:
        return
    rows = db.execute_query(
        """
        SELECT DISTINCT COALESCE(app_kind, 'commercial_software') AS app_kind
        FROM remote_app
        WHERE pool_id = %(pool_id)s
          AND (%(app_id)s IS NULL OR id <> %(app_id)s)
          AND is_active = 1
        """,
        {"pool_id": pool_id, "app_id": app_id},
        conn=conn,
    )
    existing_kinds = {
        str(row.get("app_kind") or "commercial_software")
        for row in rows
    }
    if existing_kinds and existing_kinds != {app_kind}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "资源池内应用分类必须一致")


def _get_last_insert_id(conn) -> int:
    row = db.execute_query(
        "SELECT LAST_INSERT_ID() AS id",
        fetch_one=True,
        conn=conn,
    )
    if not row or row.get("id") is None:
        raise RuntimeError("插入回读失败")
    return int(row["id"])


def _validate_script_config(
    script_enabled: bool | None,
    executor_key: str | None,
    worker_group_id: int | None,
    script_profile_key: str | None = None,
):
    if not script_enabled:
        return
    if not executor_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "启用脚本模式时必须指定执行器")
    if not worker_group_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "启用脚本模式时必须指定 Worker 节点组")
    if script_profile_key and not get_script_profile(script_profile_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "脚本软件预设不存在")


def _build_script_runtime_config(
    *,
    script_profile_key: str | None,
    executor_key: str | None,
    python_executable: str | None,
    python_env: dict[str, str] | None,
):
    return resolve_script_runtime_settings(
        script_profile_key=script_profile_key,
        script_executor_key=executor_key,
        python_executable=python_executable,
        python_env=python_env,
    )


def _parse_script_runtime_config(runtime_config_json):
    if not runtime_config_json:
        return {}
    if isinstance(runtime_config_json, str):
        try:
            runtime_config_json = json.loads(runtime_config_json)
        except json.JSONDecodeError:
            return {}
    if not isinstance(runtime_config_json, dict):
        return {}
    return runtime_config_json


def _upsert_catalog_bindings(app_row: dict, *, script_enabled: bool | None, script_profile_key: str | None, script_executor_key: str | None, script_worker_group_id: int | None, script_scratch_root: str | None, script_python_executable: str | None = None, script_python_env: dict[str, str] | None = None, conn=None):
    app_key = f"remote-app-{app_row['id']}"
    catalog = db.execute_query(
        "SELECT id FROM catalog_app WHERE app_key = %(app_key)s",
        {"app_key": app_key},
        fetch_one=True,
        conn=conn,
    )
    if catalog:
        db.execute_update(
            """
            UPDATE catalog_app
            SET name = %(name)s,
                icon = %(icon)s,
                is_active = %(is_active)s
            WHERE id = %(catalog_id)s
            """,
            {
                "catalog_id": catalog["id"],
                "name": app_row["name"],
                "icon": app_row.get("icon") or "desktop",
                "is_active": 1 if app_row.get("is_active", 1) else 0,
            },
            conn=conn,
        )
        catalog_id = int(catalog["id"])
    else:
        db.execute_update(
            """
            INSERT INTO catalog_app (app_key, name, app_kind, icon, review_status, is_active)
            VALUES (%(app_key)s, %(name)s, 'simulation_runtime', %(icon)s, 'internal', %(is_active)s)
            """,
            {
                "app_key": app_key,
                "name": app_row["name"],
                "icon": app_row.get("icon") or "desktop",
                "is_active": 1 if app_row.get("is_active", 1) else 0,
            },
            conn=conn,
        )
        catalog_id = _get_last_insert_id(conn)

    gui_binding = db.execute_query(
        "SELECT id FROM app_binding WHERE remote_app_id = %(remote_app_id)s AND binding_kind = 'gui_remoteapp' LIMIT 1",
        {"remote_app_id": app_row["id"]},
        fetch_one=True,
        conn=conn,
    )
    gui_payload = {
        "app_id": catalog_id,
        "name": f"{app_row['name']} GUI",
        "remote_app_id": app_row["id"],
        "resource_pool_id": app_row.get("pool_id"),
        "requires_resource_pool": 1 if app_row.get("pool_id") else 0,
        "is_enabled": 1 if app_row.get("is_active", 1) else 0,
    }
    if gui_binding:
        db.execute_update(
            """
            UPDATE app_binding
            SET app_id = %(app_id)s,
                name = %(name)s,
                resource_pool_id = %(resource_pool_id)s,
                requires_resource_pool = %(requires_resource_pool)s,
                is_enabled = %(is_enabled)s
            WHERE id = %(binding_id)s
            """,
            {**gui_payload, "binding_id": gui_binding["id"]},
            conn=conn,
        )
    else:
        db.execute_update(
            """
            INSERT INTO app_binding (
                app_id, binding_kind, name, remote_app_id, resource_pool_id,
                worker_group_id, requires_resource_pool, is_enabled
            )
            VALUES (
                %(app_id)s, 'gui_remoteapp', %(name)s, %(remote_app_id)s, %(resource_pool_id)s,
                NULL, %(requires_resource_pool)s, %(is_enabled)s
            )
            """,
            gui_payload,
            conn=conn,
        )

    if (
        script_enabled is None
        and script_profile_key is None
        and script_executor_key is None
        and script_worker_group_id is None
        and script_scratch_root is None
        and script_python_executable is None
        and script_python_env is None
    ):
        return

    if script_enabled:
        profile = db.execute_query(
            "SELECT id FROM remote_app_script_profile WHERE remote_app_id = %(remote_app_id)s",
            {"remote_app_id": app_row["id"]},
            fetch_one=True,
            conn=conn,
        )
        profile_payload = {
            "remote_app_id": app_row["id"],
            "is_enabled": 1,
            "executor_key": script_executor_key,
            "scratch_root": script_scratch_root or None,
        }
        if profile:
            db.execute_update(
                """
                UPDATE remote_app_script_profile
                SET is_enabled = %(is_enabled)s,
                    executor_key = %(executor_key)s,
                    scratch_root = %(scratch_root)s
                WHERE id = %(profile_id)s
                """,
                {**profile_payload, "profile_id": profile["id"]},
                conn=conn,
            )
        else:
            db.execute_update(
                """
                INSERT INTO remote_app_script_profile (
                    remote_app_id, is_enabled, executor_key, scratch_root
                )
                VALUES (
                    %(remote_app_id)s, %(is_enabled)s, %(executor_key)s, %(scratch_root)s
                )
                """,
                profile_payload,
                conn=conn,
            )
        script_binding = db.execute_query(
            "SELECT id FROM app_binding WHERE remote_app_id = %(remote_app_id)s AND binding_kind = 'worker_script' LIMIT 1",
            {"remote_app_id": app_row["id"]},
            fetch_one=True,
            conn=conn,
        )
        runtime_settings = _build_script_runtime_config(
            script_profile_key=script_profile_key,
            executor_key=script_executor_key,
            python_executable=script_python_executable,
            python_env=script_python_env,
        )
        script_binding_payload = {
            "app_id": catalog_id,
            "name": f"{app_row['name']} Script",
            "remote_app_id": app_row["id"],
            "resource_pool_id": app_row.get("pool_id"),
            "worker_group_id": script_worker_group_id,
            "requires_resource_pool": 1 if app_row.get("pool_id") else 0,
            "is_enabled": 1,
            "runtime_config_json": runtime_settings["runtime_config"],
        }
        if script_binding:
            db.execute_update(
                """
                UPDATE app_binding
                SET app_id = %(app_id)s,
                    name = %(name)s,
                    resource_pool_id = %(resource_pool_id)s,
                    worker_group_id = %(worker_group_id)s,
                    requires_resource_pool = %(requires_resource_pool)s,
                    is_enabled = %(is_enabled)s,
                    runtime_config_json = %(runtime_config_json)s
                WHERE id = %(binding_id)s
                """,
                {
                    **script_binding_payload,
                    "binding_id": script_binding["id"],
                    "runtime_config_json": json.dumps(script_binding_payload["runtime_config_json"], ensure_ascii=False) if script_binding_payload["runtime_config_json"] is not None else None,
                },
                conn=conn,
            )
        else:
            db.execute_update(
                """
                INSERT INTO app_binding (
                    app_id, binding_kind, name, remote_app_id, resource_pool_id,
                    worker_group_id, requires_resource_pool, is_enabled, runtime_config_json
                )
                VALUES (
                    %(app_id)s, 'worker_script', %(name)s, %(remote_app_id)s, %(resource_pool_id)s,
                    %(worker_group_id)s, %(requires_resource_pool)s, %(is_enabled)s, %(runtime_config_json)s
                )
                """,
                {
                    **script_binding_payload,
                    "runtime_config_json": json.dumps(script_binding_payload["runtime_config_json"], ensure_ascii=False) if script_binding_payload["runtime_config_json"] is not None else None,
                },
                conn=conn,
            )
    else:
        db.execute_update(
            """
            UPDATE remote_app_script_profile
            SET is_enabled = 0
            WHERE remote_app_id = %(remote_app_id)s
            """,
            {"remote_app_id": app_row["id"]},
            conn=conn,
        )
        db.execute_update(
            """
            UPDATE app_binding
            SET is_enabled = 0
            WHERE remote_app_id = %(remote_app_id)s
              AND binding_kind = 'worker_script'
            """,
            {"remote_app_id": app_row["id"]},
            conn=conn,
        )


def _get_app_admin_row(app_id: int, conn=None):
    row = db.execute_query(
        """
        SELECT
            a.*,
            COALESCE(sp.is_enabled, 0) AS script_enabled,
            sp.executor_key AS script_executor_key,
            sp.scratch_root AS script_scratch_root,
            sb.worker_group_id AS script_worker_group_id,
            sb.runtime_config_json AS script_runtime_config_json
        FROM remote_app a
        LEFT JOIN remote_app_script_profile sp
          ON sp.remote_app_id = a.id
        LEFT JOIN app_binding sb
          ON sb.remote_app_id = a.id
         AND sb.binding_kind = 'worker_script'
        WHERE a.id = %(id)s
        LIMIT 1
        """,
        {"id": app_id},
        fetch_one=True,
        conn=conn,
    )
    if row:
        runtime_config = _parse_script_runtime_config(row.get("script_runtime_config_json"))
        row["script_profile_key"] = runtime_config.get("script_profile_key")
        profile = get_script_profile(row["script_profile_key"]) if row.get("script_profile_key") else None
        row["script_profile_name"] = profile.get("display_name") if profile else None
        row["script_python_executable"] = runtime_config.get("python_executable")
        row["script_python_env"] = runtime_config.get("python_env")
    return row


# ============================================
# 应用管理
# ============================================

@router.get("/apps", response_model=list[AppAdminResponse])
def list_apps(admin: UserInfo = Depends(require_admin)):
    """列出所有应用（含 inactive）"""
    rows = db.execute_query(
        """
        SELECT
            a.*,
            COALESCE(sp.is_enabled, 0) AS script_enabled,
            sp.executor_key AS script_executor_key,
            sp.scratch_root AS script_scratch_root,
            sb.worker_group_id AS script_worker_group_id,
            sb.runtime_config_json AS script_runtime_config_json
        FROM remote_app a
        LEFT JOIN remote_app_script_profile sp
          ON sp.remote_app_id = a.id
        LEFT JOIN app_binding sb
          ON sb.remote_app_id = a.id
         AND sb.binding_kind = 'worker_script'
        ORDER BY a.id
        """
    )
    for row in rows:
        runtime_config = _parse_script_runtime_config(row.get("script_runtime_config_json"))
        row["script_profile_key"] = runtime_config.get("script_profile_key")
        profile = get_script_profile(row["script_profile_key"]) if row.get("script_profile_key") else None
        row["script_profile_name"] = profile.get("display_name") if profile else None
        row["script_python_executable"] = runtime_config.get("python_executable")
        row["script_python_env"] = runtime_config.get("python_env")
    return rows


@router.get("/script-profiles")
def list_script_profiles_api(admin: UserInfo = Depends(require_admin)):
    return {"items": list_script_profiles()}


@router.post("/apps", response_model=AppAdminResponse, status_code=201)
def create_app(
    req: AppCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    """创建应用"""
    _ensure_pool_exists(req.pool_id)
    _ensure_pool_kind_consistency(req.pool_id, req.app_kind)
    try:
        runtime_settings = _build_script_runtime_config(
            script_profile_key=req.script_profile_key,
            executor_key=req.script_executor_key,
            python_executable=req.script_python_executable,
            python_env=req.script_python_env,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    _validate_script_config(req.script_enabled, runtime_settings["executor_key"], req.script_worker_group_id, req.script_profile_key)

    with db.transaction() as conn:
        db.execute_update(
            """
            INSERT INTO remote_app
                (name, icon, app_kind, protocol, hostname, port,
                 rdp_username, rdp_password, domain, security, ignore_cert,
                 remote_app, remote_app_dir, remote_app_args,
                 color_depth, disable_gfx, resize_method,
                 enable_wallpaper, enable_font_smoothing,
                 disable_copy, disable_paste,
                 enable_audio, enable_audio_input, enable_printing,
                 disable_download, disable_upload,
                 timezone, keyboard_layout,
                 pool_id, member_max_concurrent)
            VALUES
                (%(name)s, %(icon)s, %(app_kind)s, %(protocol)s, %(hostname)s, %(port)s,
                 %(rdp_username)s, %(rdp_password)s, %(domain)s, %(security)s, %(ignore_cert)s,
                 %(remote_app)s, %(remote_app_dir)s, %(remote_app_args)s,
                 %(color_depth)s, %(disable_gfx)s, %(resize_method)s,
                 %(enable_wallpaper)s, %(enable_font_smoothing)s,
                 %(disable_copy)s, %(disable_paste)s,
                 %(enable_audio)s, %(enable_audio_input)s, %(enable_printing)s,
                 %(disable_download)s, %(disable_upload)s,
                 %(timezone)s, %(keyboard_layout)s,
                 %(pool_id)s, %(member_max_concurrent)s)
            """,
            {
                "name": req.name, "icon": req.icon, "app_kind": req.app_kind, "protocol": req.protocol,
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
                "disable_download": req.disable_download,
                "disable_upload": req.disable_upload,
                "timezone": req.timezone or None,
                "keyboard_layout": req.keyboard_layout or None,
                "pool_id": req.pool_id,
                "member_max_concurrent": req.member_max_concurrent,
            },
            conn=conn,
        )
        app_id = _get_last_insert_id(conn)
        app = db.execute_query(
            "SELECT * FROM remote_app WHERE id = %(id)s",
            {"id": app_id}, fetch_one=True, conn=conn,
        )
        if not app:
            raise RuntimeError("应用创建失败")
        _upsert_catalog_bindings(
            app,
            script_enabled=req.script_enabled,
            script_profile_key=req.script_profile_key,
            script_executor_key=runtime_settings["executor_key"],
            script_worker_group_id=req.script_worker_group_id,
            script_scratch_root=req.script_scratch_root,
            script_python_executable=runtime_settings["python_executable"],
            script_python_env=runtime_settings["python_env"],
            conn=conn,
        )
        app = _get_app_admin_row(int(app["id"]), conn=conn)
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

    updates = req.model_dump(exclude_unset=True)
    if not updates:
        return _get_app_admin_row(app_id)
    if "pool_id" in updates:
        _ensure_pool_exists(updates["pool_id"])
    target_pool_id = updates.get("pool_id", existing.get("pool_id"))
    target_app_kind = updates.get("app_kind", existing.get("app_kind") or "commercial_software")
    _ensure_pool_kind_consistency(target_pool_id, target_app_kind, app_id=app_id)
    script_updates = {
        key: updates.pop(key)
        for key in ("script_enabled", "script_profile_key", "script_executor_key", "script_worker_group_id", "script_scratch_root")
        if key in updates
    }
    for key in ("script_python_executable", "script_python_env"):
        if key in updates:
            script_updates[key] = updates.pop(key)

    merged_script = None
    if script_updates:
        current_script = _get_app_admin_row(app_id) or {}
        merged_script = {
            "script_enabled": script_updates.get("script_enabled", current_script.get("script_enabled")),
            "script_profile_key": script_updates.get("script_profile_key", current_script.get("script_profile_key")),
            "script_executor_key": script_updates.get("script_executor_key", current_script.get("script_executor_key")),
            "script_worker_group_id": script_updates.get("script_worker_group_id", current_script.get("script_worker_group_id")),
            "script_scratch_root": script_updates.get("script_scratch_root", current_script.get("script_scratch_root")),
            "script_python_executable": script_updates.get("script_python_executable", current_script.get("script_python_executable")),
            "script_python_env": script_updates.get("script_python_env", current_script.get("script_python_env")),
        }
        try:
            runtime_settings = _build_script_runtime_config(
                script_profile_key=merged_script.get("script_profile_key"),
                executor_key=merged_script.get("script_executor_key"),
                python_executable=merged_script.get("script_python_executable"),
                python_env=merged_script.get("script_python_env"),
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        merged_script["script_executor_key"] = runtime_settings["executor_key"]
        merged_script["script_python_executable"] = runtime_settings["python_executable"]
        merged_script["script_python_env"] = runtime_settings["python_env"]
        _validate_script_config(
            merged_script.get("script_enabled"),
            merged_script.get("script_executor_key"),
            merged_script.get("script_worker_group_id"),
            merged_script.get("script_profile_key"),
        )

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

    with db.transaction() as conn:
        if set_parts:
            db.execute_update(
                f"UPDATE remote_app SET {', '.join(set_parts)} WHERE id = %(id)s", params,
                conn=conn,
            )
        app_row = db.execute_query(
            "SELECT * FROM remote_app WHERE id = %(id)s", {"id": app_id}, fetch_one=True, conn=conn,
        )
        _upsert_catalog_bindings(
            app_row,
            script_enabled=merged_script.get("script_enabled") if merged_script else None,
            script_profile_key=merged_script.get("script_profile_key") if merged_script else None,
            script_executor_key=merged_script.get("script_executor_key") if merged_script else None,
            script_worker_group_id=merged_script.get("script_worker_group_id") if merged_script else None,
            script_scratch_root=merged_script.get("script_scratch_root") if merged_script else None,
            script_python_executable=merged_script.get("script_python_executable") if merged_script else None,
            script_python_env=merged_script.get("script_python_env") if merged_script else None,
            conn=conn,
        )
    guac_service.invalidate_all_sessions()
    pool_service.cleanup_invalid_queue_entries(requested_app_id=app_id)
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_update_app",
        "app", app_id, existing["name"], ip_address=client_ip,
    )
    return _get_app_admin_row(app_id)


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

    with db.transaction() as conn:
        db.execute_update(
            "UPDATE remote_app SET is_active = 0 WHERE id = %(id)s", {"id": app_id}, conn=conn,
        )
        app_row = db.execute_query(
            "SELECT * FROM remote_app WHERE id = %(id)s", {"id": app_id}, fetch_one=True, conn=conn,
        )
        _upsert_catalog_bindings(
            app_row,
            script_enabled=False,
            script_profile_key=None,
            script_executor_key=None,
            script_worker_group_id=None,
            script_scratch_root=None,
            script_python_executable=None,
            script_python_env=None,
            conn=conn,
        )
    guac_service.invalidate_all_sessions()
    pool_service.cleanup_invalid_queue_entries(requested_app_id=app_id)
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
        "SELECT id, username, display_name, department, is_admin, is_active, quota_bytes FROM portal_user ORDER BY id"
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
        INSERT INTO portal_user (username, password_hash, display_name, department, is_admin, quota_bytes)
        VALUES (%(username)s, %(hash)s, %(display)s, %(department)s, %(admin)s, %(quota)s)
        """,
        {
            "username": req.username, "hash": hashed,
            "display": req.display_name or req.username,
            "department": req.department,
            "admin": 1 if req.is_admin else 0,
            "quota": quota_bytes,
        },
    )
    user = db.execute_query(
        "SELECT id, username, display_name, department, is_admin, is_active FROM portal_user WHERE username = %(u)s",
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
    if req.department is not None:
        set_parts.append("department = %(department)s")
        params["department"] = req.department
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
            "SELECT id, username, display_name, department, is_admin, is_active FROM portal_user WHERE id = %(id)s",
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
        "SELECT id, username, display_name, department, is_admin, is_active FROM portal_user WHERE id = %(id)s",
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

    unique_app_ids = list(dict.fromkeys(req.app_ids))
    if unique_app_ids:
        app_id_params = {f"app_id_{index}": app_id for index, app_id in enumerate(unique_app_ids)}
        placeholders = ", ".join(f"%({key})s" for key in app_id_params)
        rows = db.execute_query(
            f"SELECT id FROM remote_app WHERE is_active = 1 AND id IN ({placeholders})",
            app_id_params,
        )
        valid_app_ids = {int(row["id"]) for row in rows}
        if len(valid_app_ids) != len(unique_app_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "应用不存在或已禁用")

    with db.transaction() as conn:
        db.execute_update(
            "DELETE FROM remote_app_acl WHERE user_id = %(uid)s", {"uid": user_id},
            conn=conn,
        )
        for app_id in unique_app_ids:
            db.execute_update(
                "INSERT IGNORE INTO remote_app_acl (user_id, app_id) VALUES (%(uid)s, %(aid)s)",
                {"uid": user_id, "aid": app_id},
                conn=conn,
            )
    guac_service.invalidate_all_sessions()
    pool_service.cleanup_invalid_queue_entries(user_id=user_id)

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
