from __future__ import annotations

from typing import Any

import jwt
from fastapi import Request

from backend.auth import JWT_ALGORITHM, JWT_SECRET
from backend.database import CONFIG, db

BASE_MENU_TREE = [
    {
        "key": "compute",
        "title": "计算资源",
        "children": [
            {"key": "compute-commercial", "title": "商业软件", "path": "/compute/commercial"},
            {"key": "compute-simulation", "title": "仿真APP", "path": "/compute/simulation"},
            {"key": "compute-tools", "title": "计算工具", "path": "/compute/tools"},
        ],
    },
    {
        "key": "my",
        "title": "我的",
        "children": [
            {"key": "my-workspace", "title": "个人空间", "path": "/my/workspace"},
            {"key": "my-tasks", "title": "App任务", "path": "/my/tasks"},
            {"key": "my-bookings", "title": "预约登记", "path": "/my/bookings"},
        ],
    },
    {
        "key": "cases",
        "title": "任务案例",
        "path": "/cases",
    },
    {
        "key": "sdk",
        "title": "SDK中心",
        "children": [
            {"key": "sdk-cloud", "title": "云平台SDK", "path": "/sdk/cloud"},
            {"key": "sdk-simulation-app", "title": "仿真AppSDK", "path": "/sdk/simulation-app"},
        ],
    },
]

ADMIN_MENU_ITEMS = [
    {"key": "admin-apps", "title": "App管理", "path": "/admin/apps"},
    {"key": "admin-queues", "title": "任务调度", "path": "/admin/queues"},
    {"key": "admin-monitor", "title": "资源监控", "path": "/admin/monitor"},
    {"key": "admin-workers", "title": "Worker状态", "path": "/admin/workers"},
    {"key": "admin-analytics", "title": "统计看板", "path": "/admin/analytics"},
]

ADMIN_MENU_GROUP = {
    "key": "admin",
    "title": "系统管理",
    "children": ADMIN_MENU_ITEMS,
}

BASE_CAPABILITIES = ["compute.view"]


def _get_auth_mode() -> str:
    return str(CONFIG.get("auth", {}).get("mode", "local")).strip().lower() or "local"


def _build_menu_tree(is_admin: bool) -> list[dict[str, Any]]:
    menu_tree = [*BASE_MENU_TREE]
    if is_admin:
        menu_tree.append(ADMIN_MENU_GROUP)
    return menu_tree


def _build_anonymous_context() -> dict[str, Any]:
    return {
        "authenticated": False,
        "user": None,
        "auth_source": "anonymous",
        "capabilities": [],
        "menu_tree": [],
        "org_context": {},
    }


def _decode_local_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["user_id"])
        str(payload["username"])
        bool(payload.get("is_admin", False))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None

    user = db.execute_query(
        """
        /* identity:get_current_user */
        SELECT id, username, display_name, is_admin, is_active
        FROM portal_user
        WHERE id = %(user_id)s
        LIMIT 1
        """,
        {"user_id": user_id},
        fetch_one=True,
    )
    if not user or int(user.get("is_active") or 0) != 1:
        return None

    username = str(user["username"])
    display_name = str(user.get("display_name") or username)
    is_admin = bool(user.get("is_admin", False))
    return {
        "authenticated": True,
        "user": {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "is_admin": is_admin,
        },
        "auth_source": "local",
        "capabilities": BASE_CAPABILITIES.copy(),
        "menu_tree": _build_menu_tree(is_admin),
        "org_context": {},
    }


def resolve_session_context(request: Request) -> dict[str, Any]:
    authorization = request.headers.get("authorization", "").strip()
    if not authorization.lower().startswith("bearer "):
        return _build_anonymous_context()

    token = authorization[7:].strip()
    if not token:
        return _build_anonymous_context()

    if _get_auth_mode() in {"local", "hybrid"}:
        context = _decode_local_token(token)
        if context:
            return context

    return _build_anonymous_context()
