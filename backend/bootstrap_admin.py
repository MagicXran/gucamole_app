"""Bootstrap the first admin account from environment variables."""

from __future__ import annotations

import logging
import os

import bcrypt

logger = logging.getLogger(__name__)

DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME = "管理员"


def _bootstrap_admin_config(env=None) -> dict[str, str] | None:
    if env is None:
        env = os.environ
    username = (env.get("PORTAL_BOOTSTRAP_ADMIN_USERNAME") or "").strip()
    password = env.get("PORTAL_BOOTSTRAP_ADMIN_PASSWORD") or ""
    if not username or not password:
        return None
    display_name = (
        (env.get("PORTAL_BOOTSTRAP_ADMIN_DISPLAY_NAME") or "").strip()
        or DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME
    )
    return {
        "username": username,
        "password": password,
        "display_name": display_name,
    }


def ensure_bootstrap_admin(admin_db, env=None) -> dict[str, object]:
    if env is None:
        env = os.environ
    config = _bootstrap_admin_config(env)
    existing_admin = admin_db.execute_query(
        "SELECT id, username FROM portal_user WHERE is_admin = 1 AND is_active = 1 ORDER BY id LIMIT 1",
        fetch_one=True,
    )
    if not config:
        if not existing_admin:
            raise RuntimeError("未检测到管理员账号，请配置 PORTAL_BOOTSTRAP_ADMIN_USERNAME 和 PORTAL_BOOTSTRAP_ADMIN_PASSWORD")
        return {"created": False, "reason": "disabled"}

    existing = admin_db.execute_query(
        "SELECT id, is_admin, is_active FROM portal_user WHERE username = %(u)s",
        {"u": config["username"]},
        fetch_one=True,
    )
    if existing:
        if not bool(existing.get("is_admin")):
            raise RuntimeError("启动管理员用户名与现有非管理员用户冲突")
        if not bool(existing.get("is_active", 1)):
            hashed = bcrypt.hashpw(
                config["password"].encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            admin_db.execute_update(
                """
                UPDATE portal_user
                SET password_hash = %(password_hash)s,
                    display_name = %(display_name)s,
                    is_admin = 1,
                    is_active = 1
                WHERE id = %(id)s
                """,
                {
                    "id": int(existing["id"]),
                    "password_hash": hashed,
                    "display_name": config["display_name"],
                },
            )
            logger.warning("已重新启用启动管理员: %s", config["username"])
            return {
                "created": True,
                "reason": "reactivated",
                "user_id": int(existing["id"]),
                "username": config["username"],
            }
        return {
            "created": False,
            "reason": "exists",
            "user_id": int(existing["id"]),
            "username": config["username"],
        }

    hashed = bcrypt.hashpw(
        config["password"].encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    admin_db.execute_update(
        """
        INSERT INTO portal_user (username, password_hash, display_name, is_admin, is_active)
        VALUES (%(username)s, %(password_hash)s, %(display_name)s, 1, 1)
        """,
        {
            "username": config["username"],
            "password_hash": hashed,
            "display_name": config["display_name"],
        },
    )
    created = admin_db.execute_query(
        "SELECT id FROM portal_user WHERE username = %(u)s",
        {"u": config["username"]},
        fetch_one=True,
    )
    user_id = int(created["id"]) if created and created.get("id") is not None else None
    logger.warning("已根据环境变量创建启动管理员: %s", config["username"])
    return {
        "created": True,
        "reason": "created",
        "user_id": user_id,
        "username": config["username"],
    }
