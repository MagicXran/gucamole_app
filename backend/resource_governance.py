"""
资源治理服务：并发限制与排队的纯后端规则。
"""

from typing import Any


def _positive_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def governance_enabled(app_row: dict) -> bool:
    """只要有一个正数限制，就认为治理开启。"""
    return bool(
        _positive_limit(app_row.get("max_concurrent_sessions"))
        or _positive_limit(app_row.get("max_concurrent_per_user"))
    )


def limits_reached(active_count: int, user_active_count: int, app_row: dict) -> bool:
    """判断应用总并发或单用户并发是否触顶。"""
    app_limit = _positive_limit(app_row.get("max_concurrent_sessions"))
    user_limit = _positive_limit(app_row.get("max_concurrent_per_user"))
    if app_limit and active_count >= app_limit:
        return True
    if user_limit and user_active_count >= user_limit:
        return True
    return False


def get_waiting_entry(db, app_id: int, user_id: int) -> dict | None:
    """读取当前用户在某应用上的等待记录。"""
    return db.execute_query(
        """
        SELECT id, app_id, user_id, status
        FROM launch_queue
        WHERE app_id = %(app_id)s
          AND user_id = %(user_id)s
          AND status = 'waiting'
        ORDER BY id DESC
        LIMIT 1
        """,
        {"app_id": app_id, "user_id": user_id},
        fetch_one=True,
    )


def next_queue_position(db, app_id: int) -> int:
    """返回当前排队尾部位置。"""
    row = db.execute_query(
        """
        SELECT COUNT(*) AS position
        FROM launch_queue
        WHERE app_id = %(app_id)s
          AND status = 'waiting'
        """,
        {"app_id": app_id},
        fetch_one=True,
    )
    if not row:
        return 0
    return int(row.get("position", 0) or 0)


def current_queue_position(db, app_id: int, queue_id: int) -> int:
    """返回某条等待记录的真实排队位次。"""
    row = db.execute_query(
        """
        SELECT COUNT(*) AS position
        FROM launch_queue
        WHERE app_id = %(app_id)s
          AND status = 'waiting'
          AND id <= %(queue_id)s
        """,
        {"app_id": app_id, "queue_id": queue_id},
        fetch_one=True,
    )
    if not row:
        return 0
    return int(row.get("position", 0) or 0)


def enqueue_or_refresh(db, app_id: int, user_id: int) -> dict:
    """入队或刷新现有等待项。"""
    waiting = get_waiting_entry(db, app_id=app_id, user_id=user_id)
    created = waiting is None

    if created:
        db.execute_update(
            """
            INSERT INTO launch_queue (app_id, user_id, status)
            VALUES (%(app_id)s, %(user_id)s, 'waiting')
            """,
            {"app_id": app_id, "user_id": user_id},
        )
    else:
        db.execute_update(
            """
            UPDATE launch_queue
            SET updated_at = NOW()
            WHERE id = %(queue_id)s
            """,
            {"queue_id": waiting["id"]},
        )

    return {
        "position": (
            next_queue_position(db, app_id=app_id)
            if created else
            current_queue_position(db, app_id=app_id, queue_id=waiting["id"])
        ),
        "created": created,
    }


def is_queue_head(db, app_id: int, user_id: int) -> bool:
    """判断当前用户是否位于队首。"""
    row = db.execute_query(
        """
        SELECT user_id
        FROM launch_queue
        WHERE app_id = %(app_id)s
          AND status = 'waiting'
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        {"app_id": app_id},
        fetch_one=True,
    )
    if not row:
        return False
    return int(row.get("user_id", 0) or 0) == user_id


def has_waiting_entries(db, app_id: int) -> bool:
    """判断应用当前是否存在等待队列。"""
    row = db.execute_query(
        """
        SELECT COUNT(*) AS waiting_count
        FROM launch_queue
        WHERE app_id = %(app_id)s
          AND status = 'waiting'
        """,
        {"app_id": app_id},
        fetch_one=True,
    )
    return bool(row and int(row.get("waiting_count", 0) or 0) > 0)


def remove_waiting_entry(db, app_id: int, user_id: int) -> int:
    """移除用户当前的等待项。"""
    return db.execute_update(
        """
        DELETE FROM launch_queue
        WHERE app_id = %(app_id)s
          AND user_id = %(user_id)s
          AND status = 'waiting'
        """,
        {"app_id": app_id, "user_id": user_id},
    )


def get_active_counts(db, app_id: int, user_id: int, timeout_seconds: int) -> dict:
    """统计新鲜活跃会话数。"""
    row = db.execute_query(
        """
        SELECT
            COUNT(*) AS active_count,
            SUM(CASE WHEN user_id = %(user_id)s THEN 1 ELSE 0 END) AS user_active_count
        FROM active_session
        WHERE app_id = %(app_id)s
          AND status = 'active'
          AND last_heartbeat > DATE_SUB(NOW(), INTERVAL %(timeout)s SECOND)
        """,
        {"app_id": app_id, "user_id": user_id, "timeout": timeout_seconds},
        fetch_one=True,
    )
    if not row:
        return {"active_count": 0, "user_active_count": 0}
    return {
        "active_count": int(row.get("active_count", 0) or 0),
        "user_active_count": int(row.get("user_active_count", 0) or 0),
    }


def expire_stale_queue_entries(db) -> int:
    """将长时间不刷新的等待项标记为 expired。"""
    return db.execute_update(
        """
        UPDATE launch_queue q
        JOIN remote_app a ON a.id = q.app_id
        SET q.status = 'expired'
        WHERE q.status = 'waiting'
          AND q.updated_at < DATE_SUB(
                NOW(),
                INTERVAL COALESCE(a.queue_timeout_seconds, 300) SECOND
          )
        """
    )
