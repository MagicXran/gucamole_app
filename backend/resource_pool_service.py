"""资源池与排队调度服务。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Callable

from backend.database import CONFIG
from backend.resource_pool_queue import ResourcePoolQueueService
from backend.resource_pool_queries import ResourcePoolQueryService
from backend.resource_pool_reclaim import ResourcePoolReclaimService


def build_default_pool_seed_rows(app_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "remote_app_id": int(app["id"]),
            "pool_name": str(app["name"]),
            "pool_icon": str(app.get("icon") or "desktop"),
            "pool_max_concurrent": 1,
            "member_max_concurrent": 1,
        }
        for app in app_rows
    ]


_monitor_cfg = CONFIG.get("monitor", {})


class ResourcePoolService:
    LIVE_QUEUE_STATES = ("queued", "ready", "launching")
    OCCUPIED_SESSION_STATUSES = ("active", "reclaim_pending")
    DEFAULT_STALE_TIMEOUT_SECONDS = int(_monitor_cfg.get("session_timeout_seconds", 120))
    DEFAULT_ORPHAN_IDLE_TIMEOUT_SECONDS = int(_monitor_cfg.get("session_timeout_seconds", 120))

    def __init__(self, db, now_provider: Callable[[], datetime] | None = None):
        self._db = db
        self._now_provider = now_provider or datetime.now
        self._queries = ResourcePoolQueryService(db)
        self._queue_service = ResourcePoolQueueService(
            db,
            self._queries,
            now_provider=self._now_provider,
            pool_lock=self._pool_lock,
            get_live_user_pool_state=self.get_live_user_pool_state,
            pick_launchable_member=self.pick_launchable_member,
            has_accessible_member=self._has_accessible_member,
            count_pool_live_queue_entries=self._count_pool_live_queue_entries,
            available_slots=self._available_slots,
            live_queue_states=self.LIVE_QUEUE_STATES,
        )
        self._reclaim_service = ResourcePoolReclaimService(
            db,
            now_provider=self._now_provider,
            fallback_stale_timeout_seconds=self.DEFAULT_STALE_TIMEOUT_SECONDS,
            fallback_idle_timeout_seconds=self.DEFAULT_ORPHAN_IDLE_TIMEOUT_SECONDS,
        )

    def _now(self) -> datetime:
        return self._now_provider()

    @contextmanager
    def _pool_lock(self, pool_id: int):
        lock_name = f"resource_pool:{pool_id}"
        if hasattr(self._db, "get_connection"):
            conn = self._db.get_connection()
            cursor = None
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT GET_LOCK(%(lock_name)s, 5) AS locked", {"lock_name": lock_name})
                row = cursor.fetchone() or {"locked": 0}
                if int(row["locked"]) != 1:
                    raise RuntimeError("资源池繁忙，请重试")
                yield
            finally:
                try:
                    if cursor is not None:
                        cursor.execute("SELECT RELEASE_LOCK(%(lock_name)s) AS released", {"lock_name": lock_name})
                        cursor.fetchone()
                finally:
                    if cursor is not None:
                        cursor.close()
                    conn.close()
            return

        row = self._db.execute_query(
            "/* rps:get_lock */ SELECT GET_LOCK(%(lock_name)s, 5) AS locked",
            {"lock_name": lock_name},
            fetch_one=True,
        ) or {"locked": 0}
        if int(row["locked"]) != 1:
            raise RuntimeError("资源池繁忙，请重试")
        try:
            yield
        finally:
            self._db.execute_query(
                "/* rps:release_lock */ SELECT RELEASE_LOCK(%(lock_name)s) AS released",
                {"lock_name": lock_name},
                fetch_one=True,
            )

    def get_live_user_pool_state(self, user_id: int, pool_id: int) -> dict[str, Any] | None:
        row = self._db.execute_query(
            """
            /* rps:get_live_queue_state */
            SELECT id, status
            FROM launch_queue
            WHERE user_id = %(user_id)s
              AND pool_id = %(pool_id)s
              AND status IN ('queued', 'ready', 'launching')
            ORDER BY id ASC
            LIMIT 1
            """,
            {"user_id": user_id, "pool_id": pool_id},
            fetch_one=True,
        )
        if row:
            return {"state_kind": "queue", "id": int(row["id"]), "status": str(row["status"])}

        row = self._db.execute_query(
            """
            /* rps:get_live_active_session */
            SELECT session_id, status
            FROM active_session
            WHERE user_id = %(user_id)s
              AND pool_id = %(pool_id)s
              AND status IN ('active', 'reclaim_pending')
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """,
            {"user_id": user_id, "pool_id": pool_id},
            fetch_one=True,
        )
        if not row:
            return None
        return {"state_kind": "session", "id": str(row["session_id"]), "status": str(row["status"])}

    def pick_launchable_member(self, user_id: int, pool_id: int, *, exclude_queue_id: int | None = None) -> dict[str, Any] | None:
        rows = self._db.execute_query(
            """
            /* rps:list_pool_members_with_load */
            SELECT
                a.id,
                a.pool_id,
                a.member_max_concurrent,
                (
                    SELECT COUNT(*)
                    FROM active_session s
                    WHERE s.app_id = a.id AND s.status IN ('active', 'reclaim_pending')
                ) + (
                    SELECT COUNT(*)
                    FROM launch_queue q
                    WHERE q.assigned_app_id = a.id
                      AND q.status IN ('ready', 'launching')
                      AND (%(exclude_queue_id)s IS NULL OR q.id <> %(exclude_queue_id)s)
                ) AS active_count
            FROM remote_app a
            JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
            WHERE a.pool_id = %(pool_id)s
              AND a.is_active = 1
            HAVING active_count < a.member_max_concurrent
            ORDER BY active_count ASC, a.id ASC
            """,
            {"user_id": user_id, "pool_id": pool_id, "exclude_queue_id": exclude_queue_id},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "id": int(row["id"]),
            "pool_id": int(row["pool_id"]),
            "member_max_concurrent": int(row["member_max_concurrent"]),
            "active_count": int(row["active_count"]),
        }

    def _has_accessible_member(self, user_id: int, pool_id: int) -> bool:
        row = self._db.execute_query(
            """
            /* rps:has_accessible_member */
            SELECT 1 AS ok
            FROM remote_app a
            JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
            WHERE a.pool_id = %(pool_id)s
              AND a.is_active = 1
            LIMIT 1
            """,
            {"user_id": user_id, "pool_id": pool_id},
            fetch_one=True,
        )
        return bool(row)

    def list_user_pools(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_user_pools */
            SELECT
                MIN(a.id) AS launch_app_id,
                p.id AS pool_id,
                p.name,
                p.icon,
                MAX(a.protocol) AS protocol,
                p.max_concurrent,
                COUNT(DISTINCT CASE WHEN s.status IN ('active', 'reclaim_pending') THEN s.id END) AS active_count,
                COUNT(DISTINCT CASE WHEN q.status IN ('queued', 'ready', 'launching') THEN q.id END) AS queued_count
            FROM resource_pool p
            JOIN remote_app a
              ON a.pool_id = p.id
             AND a.is_active = 1
            JOIN remote_app_acl acl
              ON acl.app_id = a.id
             AND acl.user_id = %(user_id)s
            LEFT JOIN active_session s
              ON s.pool_id = p.id
             AND s.status IN ('active', 'reclaim_pending')
            LEFT JOIN launch_queue q
              ON q.pool_id = p.id
             AND q.status IN ('queued', 'ready', 'launching')
            WHERE p.is_active = 1
            GROUP BY p.id, p.name, p.icon, p.max_concurrent
            ORDER BY p.name ASC, p.id ASC
            """,
            {"user_id": user_id},
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            pool_id = int(row["pool_id"])
            active_count = int(row.get("active_count") or 0)
            queued_count = int(row.get("queued_count") or 0)
            max_concurrent = int(row.get("max_concurrent") or 1)
            has_member_capacity = self.pick_launchable_member(user_id=user_id, pool_id=pool_id) is not None
            result.append({
                "id": int(row["launch_app_id"]),
                "pool_id": pool_id,
                "name": str(row["name"]),
                "icon": str(row.get("icon") or "desktop"),
                "protocol": str(row.get("protocol") or "rdp"),
                "active_count": active_count,
                "queued_count": queued_count,
                "max_concurrent": max_concurrent,
                "has_capacity": queued_count == 0 and active_count < max_concurrent and has_member_capacity,
            })
        return result

    def _count_pool_live_queue_entries(self, pool_id: int) -> int:
        row = self._db.execute_query(
            """
            /* rps:get_pool_live_queue_count */
            SELECT COUNT(*) AS live_queue_count
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND status IN ('queued', 'ready', 'launching')
            """,
            {"pool_id": pool_id},
            fetch_one=True,
        ) or {"live_queue_count": 0}
        return int(row["live_queue_count"])

    def _available_slots(self, pool_id: int, *, exclude_queue_id: int | None = None) -> int:
        pool = self._db.execute_query(
            """
            /* rps:get_pool_by_id */
            SELECT id, max_concurrent
            FROM resource_pool
            WHERE id = %(pool_id)s
              AND is_active = 1
            LIMIT 1
            """,
            {"pool_id": pool_id},
            fetch_one=True,
        )
        if not pool:
            return 0
        active_row = self._db.execute_query(
            """
            /* rps:get_pool_active_count */
            SELECT COUNT(*) AS active_count
            FROM active_session
            WHERE pool_id = %(pool_id)s
              AND status IN ('active', 'reclaim_pending')
            """,
            {"pool_id": pool_id},
            fetch_one=True,
        ) or {"active_count": 0}
        reserved_row = self._db.execute_query(
            """
            /* rps:get_pool_reserved_count */
            SELECT COUNT(*) AS ready_count
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND status IN ('ready', 'launching')
              AND (%(exclude_queue_id)s IS NULL OR id <> %(exclude_queue_id)s)
            """,
            {"pool_id": pool_id, "exclude_queue_id": exclude_queue_id},
            fetch_one=True,
        ) or {"ready_count": 0}
        return int(pool["max_concurrent"]) - int(active_row["active_count"]) - int(reserved_row["ready_count"])

    def _pool_has_capacity(self, pool_id: int, *, exclude_queue_id: int | None = None) -> bool:
        return self._available_slots(pool_id, exclude_queue_id=exclude_queue_id) > 0

    def expire_ready_entries(self, *, pool_id: int | None = None) -> list[int]:
        return self._queue_service.expire_ready_entries(pool_id=pool_id)

    def prepare_launch(self, *, user_id: int, requested_app_id: int, queue_id: int | None = None) -> dict[str, Any]:
        return self._queue_service.prepare_launch(
            user_id=user_id,
            requested_app_id=requested_app_id,
            queue_id=queue_id,
        )

    def get_queue_status(self, *, queue_id: int, user_id: int) -> dict[str, Any]:
        return self._queue_service.get_queue_status(queue_id=queue_id, user_id=user_id)

    def cancel_queue(self, *, queue_id: int, user_id: int) -> dict[str, Any]:
        return self._queue_service.cancel_queue(queue_id=queue_id, user_id=user_id)

    def _cancel_queue_as_invalid(self, queue_id: int, reason: str) -> int:
        return self._queue_service._cancel_queue_as_invalid(queue_id, reason)

    def mark_queue_fulfilled(self, *, queue_id: int, assigned_app_id: int):
        self._queue_service.mark_queue_fulfilled(queue_id=queue_id, assigned_app_id=assigned_app_id)

    def requeue_after_launch_failure(self, *, queue_id: int, last_error: str):
        self._queue_service.requeue_after_launch_failure(queue_id=queue_id, last_error=last_error)

    def dispatch_ready_entries(self) -> list[int]:
        return self._queue_service.dispatch_ready_entries()

    def _mark_session_reclaimed(self, *, session_id: str, reason: str, ended_at: datetime, target_status: str = "reclaimed") -> int:
        return self._reclaim_service.mark_session_reclaimed(
            session_id=session_id,
            reason=reason,
            ended_at=ended_at,
            target_status=target_status,
        )

    def reclaim_stale_sessions(self) -> list[dict[str, Any]]:
        return self._reclaim_service.reclaim_stale_sessions()

    def reclaim_idle_sessions(self) -> list[dict[str, Any]]:
        return self._reclaim_service.reclaim_idle_sessions()

    def list_admin_pools(self) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_admin_pools */
            SELECT
                p.id, p.name, p.icon, p.max_concurrent, p.auto_dispatch_enabled,
                p.dispatch_grace_seconds, p.stale_timeout_seconds, p.idle_timeout_seconds, p.is_active,
                COUNT(DISTINCT CASE WHEN s.status IN ('active', 'reclaim_pending') THEN s.id END) AS active_count,
                COUNT(DISTINCT CASE WHEN q.status IN ('queued', 'ready', 'launching') THEN q.id END) AS queued_count
            FROM resource_pool p
            LEFT JOIN active_session s ON s.pool_id = p.id AND s.status IN ('active', 'reclaim_pending')
            LEFT JOIN launch_queue q ON q.pool_id = p.id AND q.status IN ('queued', 'ready', 'launching')
            GROUP BY p.id, p.name, p.icon, p.max_concurrent, p.auto_dispatch_enabled,
                     p.dispatch_grace_seconds, p.stale_timeout_seconds, p.idle_timeout_seconds, p.is_active
            ORDER BY p.name ASC, p.id ASC
            """
        )
        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "icon": str(row.get("icon") or "desktop"),
                "max_concurrent": int(row.get("max_concurrent") or 1),
                "auto_dispatch_enabled": bool(row.get("auto_dispatch_enabled")),
                "dispatch_grace_seconds": int(row.get("dispatch_grace_seconds") or 120),
                "stale_timeout_seconds": int(row.get("stale_timeout_seconds") or 120),
                "idle_timeout_seconds": row.get("idle_timeout_seconds"),
                "is_active": bool(row.get("is_active")),
                "active_count": int(row.get("active_count") or 0),
                "queued_count": int(row.get("queued_count") or 0),
            }
            for row in rows
        ]

    def create_pool(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._db.execute_update(
            """
            /* rps:create_pool */
            INSERT INTO resource_pool (
                name, icon, max_concurrent, auto_dispatch_enabled,
                dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active
            )
            VALUES (
                %(name)s, %(icon)s, %(max_concurrent)s, %(auto_dispatch_enabled)s,
                %(dispatch_grace_seconds)s, %(stale_timeout_seconds)s, %(idle_timeout_seconds)s, %(is_active)s
            )
            """,
            payload,
        )
        row = self._db.execute_query(
            """
            /* rps:get_latest_pool_by_name */
            SELECT id, name, icon, max_concurrent, auto_dispatch_enabled,
                   dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active
            FROM resource_pool
            WHERE name = %(name)s
            ORDER BY id DESC
            LIMIT 1
            """,
            {"name": payload["name"]},
            fetch_one=True,
        )
        if not row:
            raise RuntimeError("资源池创建失败")
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "icon": str(row.get("icon") or "desktop"),
            "max_concurrent": int(row.get("max_concurrent") or 1),
            "auto_dispatch_enabled": bool(row.get("auto_dispatch_enabled")),
            "dispatch_grace_seconds": int(row.get("dispatch_grace_seconds") or 120),
            "stale_timeout_seconds": int(row.get("stale_timeout_seconds") or 120),
            "idle_timeout_seconds": row.get("idle_timeout_seconds"),
            "is_active": bool(row.get("is_active")),
        }

    def update_pool(self, *, pool_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload:
            raise ValueError("没有可更新的字段")
        set_parts = []
        params = {"pool_id": pool_id}
        for key, value in payload.items():
            set_parts.append(f"{key} = %({key})s")
            params[key] = value
        updated = self._db.execute_update(
            f"/* rps:update_pool */ UPDATE resource_pool SET {', '.join(set_parts)} WHERE id = %(pool_id)s",
            params,
        )
        if updated <= 0:
            raise ValueError("资源池不存在")
        row = self._db.execute_query(
            """
            /* rps:get_pool_admin */
            SELECT id, name, icon, max_concurrent, auto_dispatch_enabled,
                   dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active
            FROM resource_pool
            WHERE id = %(pool_id)s
            LIMIT 1
            """,
            {"pool_id": pool_id},
            fetch_one=True,
        )
        if not row:
            raise ValueError("资源池不存在")
        return {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "icon": str(row.get("icon") or "desktop"),
            "max_concurrent": int(row.get("max_concurrent") or 1),
            "auto_dispatch_enabled": bool(row.get("auto_dispatch_enabled")),
            "dispatch_grace_seconds": int(row.get("dispatch_grace_seconds") or 120),
            "stale_timeout_seconds": int(row.get("stale_timeout_seconds") or 120),
            "idle_timeout_seconds": row.get("idle_timeout_seconds"),
            "is_active": bool(row.get("is_active")),
        }

    def list_admin_queues(self) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_admin_queues */
            SELECT q.id, q.pool_id, p.name AS pool_name, q.user_id,
                   u.username, u.display_name, q.status, q.created_at, q.ready_expires_at, q.cancel_reason
            FROM launch_queue q
            JOIN resource_pool p ON p.id = q.pool_id
            JOIN portal_user u ON u.id = q.user_id
            WHERE q.status IN ('queued', 'ready', 'launching')
            ORDER BY q.created_at ASC, q.id ASC
            """
        )
        return [
            {
                "queue_id": int(row["id"]),
                "pool_id": int(row["pool_id"]),
                "pool_name": str(row["pool_name"]),
                "user_id": int(row["user_id"]),
                "username": str(row["username"]),
                "display_name": str(row.get("display_name") or row["username"]),
                "status": str(row["status"]),
                "created_at": str(row["created_at"]) if row.get("created_at") else "",
                "ready_expires_at": str(row["ready_expires_at"]) if row.get("ready_expires_at") else "",
                "cancel_reason": str(row["cancel_reason"]) if row.get("cancel_reason") else "",
            }
            for row in rows
        ]

    def cleanup_invalid_queue_entries(self, *, user_id: int | None = None, requested_app_id: int | None = None, pool_id: int | None = None) -> list[int]:
        return self._queue_service.cleanup_invalid_queue_entries(
            user_id=user_id,
            requested_app_id=requested_app_id,
            pool_id=pool_id,
        )

    def cancel_queue_admin(self, *, queue_id: int) -> dict[str, Any]:
        updated = self._db.execute_update(
            """
            /* rps:cancel_queue_admin */
            UPDATE launch_queue
            SET status = 'cancelled',
                cancel_reason = 'admin',
                cancelled_at = NOW()
            WHERE id = %(queue_id)s
              AND status IN ('queued', 'ready', 'launching')
            """,
            {"queue_id": queue_id},
        )
        if updated <= 0:
            raise ValueError("排队记录不存在或已结束")
        return {"queue_id": queue_id, "status": "cancelled"}

    def reclaim_session(self, *, session_id: str) -> dict[str, Any]:
        row = self._db.execute_query(
            """
            /* rps:get_reclaim_session */
            SELECT session_id, user_id
            FROM active_session
            WHERE session_id = %(session_id)s
              AND status = 'active'
            LIMIT 1
            """,
            {"session_id": session_id},
            fetch_one=True,
        )
        if not row:
            raise ValueError("会话不存在或已结束")
        updated = self._mark_session_reclaimed(session_id=session_id, reason="admin", ended_at=self._now(), target_status="reclaim_pending")
        if updated <= 0:
            raise ValueError("会话不存在或已结束")
        return {"session_id": session_id, "status": "reclaim_pending", "user_id": int(row["user_id"])}
