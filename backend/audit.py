"""
审计日志模块 - 记录用户操作
"""

import json
import logging

from backend.database import db

logger = logging.getLogger(__name__)


def log_action(
    user_id: int,
    username: str,
    action: str,
    target_type: str = None,
    target_id: int = None,
    target_name: str = None,
    detail: dict = None,
    ip_address: str = None,
):
    """写入审计日志（同步，单条 INSERT）"""
    try:
        db.execute_update(
            """
            INSERT INTO audit_log
                (user_id, username, action, target_type, target_id,
                 target_name, detail, ip_address)
            VALUES
                (%(user_id)s, %(username)s, %(action)s, %(target_type)s,
                 %(target_id)s, %(target_name)s, %(detail)s, %(ip_address)s)
            """,
            {
                "user_id": user_id,
                "username": username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "target_name": target_name,
                "detail": json.dumps(detail, ensure_ascii=False) if detail else None,
                "ip_address": ip_address,
            },
        )
    except Exception:
        logger.exception("审计日志写入失败: action=%s, user=%s", action, username)
