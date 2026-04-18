"""资源池与排队调度服务。"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta
import json
from typing import Any, Callable

from backend.database import CONFIG
from backend.script_dispatch import evaluate_script_dispatch_target


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

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _decode_json(value):
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

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
            JOIN resource_pool p ON p.id = a.pool_id
            WHERE a.pool_id = %(pool_id)s
              AND a.is_active = 1
              AND p.is_active = 1
            LIMIT 1
            """,
            {"user_id": user_id, "pool_id": pool_id},
            fetch_one=True,
        )
        return bool(row)

    def _invalidate_queue_if_unusable(self, *, queue_id: int, user_id: int, pool_id: int, reason: str = "member_unavailable") -> dict[str, Any]:
        self._cancel_queue_as_invalid(queue_id, reason)
        return self.get_queue_status(queue_id=queue_id, user_id=user_id)

    def _cancel_task_for_queue(self, platform_task_id: int | None, reason: str):
        if not platform_task_id:
            return
        self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'cancelled',
                cancel_requested = 0,
                ended_at = NOW(),
                result_summary_json = JSON_OBJECT('error', %(reason)s)
            WHERE id = %(platform_task_id)s
              AND status IN ('queued', 'submitted')
            """,
            {"platform_task_id": platform_task_id, "reason": reason},
        )

    def _list_worker_dispatch_nodes(self, worker_group_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            SELECT status, display_name, supported_executor_keys_json, capabilities_json, runtime_state_json
            FROM worker_node
            WHERE group_id = %(worker_group_id)s
            ORDER BY display_name ASC, id ASC
            """,
            {"worker_group_id": worker_group_id},
        )
        for row in rows:
            row["supported_executor_keys_json"] = self._decode_json(row.get("supported_executor_keys_json")) or []
            row["capabilities_json"] = self._decode_json(row.get("capabilities_json")) or {}
            row["runtime_state_json"] = self._decode_json(row.get("runtime_state_json")) or {}
        return rows

    def list_user_pools(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_user_pools */
            SELECT
                MIN(a.id) AS launch_app_id,
                p.id AS pool_id,
                p.name,
                p.icon,
                CASE
                    WHEN COUNT(DISTINCT COALESCE(a.app_kind, 'commercial_software')) = 1
                    THEN MAX(COALESCE(a.app_kind, 'commercial_software'))
                    ELSE 'commercial_software'
                END AS app_kind,
                MAX(COALESCE(sp.is_enabled, 0)) AS supports_script,
                MIN(CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN a.id END) AS script_runtime_id,
                MIN(CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN ab.worker_group_id END) AS worker_group_id,
                MIN(CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN sp.executor_key END) AS executor_key,
                MIN(CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN ab.runtime_config_json END) AS runtime_config_json,
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
            LEFT JOIN remote_app_script_profile sp
              ON sp.remote_app_id = a.id
            LEFT JOIN app_binding ab
              ON ab.remote_app_id = a.id
             AND ab.binding_kind = 'worker_script'
             AND ab.is_enabled = 1
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
            available_slots = self._available_slots(pool_id)
            has_member_capacity = self.pick_launchable_member(user_id=user_id, pool_id=pool_id) is not None
            has_capacity = queued_count == 0 and available_slots > 0 and has_member_capacity
            supports_script = bool(row.get("supports_script"))
            script_runtime_id = row.get("script_runtime_id")
            worker_group_id = int(row.get("worker_group_id") or 0)
            executor_key = str(row.get("executor_key") or "")
            runtime_config = self._decode_json(row.get("runtime_config_json")) or {}
            if supports_script and worker_group_id:
                target = {
                    "requested_runtime_id": script_runtime_id,
                    "worker_group_id": worker_group_id,
                    "executor_key": executor_key,
                    "runtime_config_json": runtime_config,
                }
                script_status = evaluate_script_dispatch_target(
                    target=target,
                    worker_nodes=self._list_worker_dispatch_nodes(worker_group_id),
                    requested_runtime_id=int(script_runtime_id or 0),
                )
            else:
                script_status = {
                    "is_schedulable": False,
                    "script_status_code": "",
                    "script_status_label": "",
                    "script_status_tone": "",
                    "summary": "",
                    "reasons": [],
                }
            result.append({
                "id": int(row["launch_app_id"]),
                "pool_id": pool_id,
                "name": str(row["name"]),
                "icon": str(row.get("icon") or "desktop"),
                "app_kind": str(row.get("app_kind") or "commercial_software"),
                "protocol": str(row.get("protocol") or "rdp"),
                "supports_gui": True,
                "supports_script": supports_script,
                "script_runtime_id": script_runtime_id,
                "script_profile_key": runtime_config.get("script_profile_key"),
                "script_profile_name": runtime_config.get("software_display_name"),
                "script_schedulable": bool(script_status.get("is_schedulable")),
                "script_status_code": str(script_status.get("script_status_code") or ""),
                "script_status_label": str(script_status.get("script_status_label") or ""),
                "script_status_tone": str(script_status.get("script_status_tone") or ""),
                "script_status_summary": str(script_status.get("summary") or ""),
                "script_status_reason": str((script_status.get("reasons") or [{}])[0].get("message") or "") if script_status.get("reasons") else "",
                "resource_status_code": "available" if has_capacity else ("queued" if queued_count > 0 else "busy"),
                "resource_status_label": "可用" if has_capacity else ("排队中" if queued_count > 0 else "忙碌"),
                "resource_status_tone": "success" if has_capacity else "warning",
                "active_count": active_count,
                "queued_count": queued_count,
                "max_concurrent": max_concurrent,
                "has_capacity": has_capacity,
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
        task_row = self._db.execute_query(
            """
            /* rps:get_pool_running_task_count */
            SELECT COUNT(*) AS task_count
            FROM platform_task
            WHERE resource_pool_id = %(pool_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            """,
            {"pool_id": pool_id},
            fetch_one=True,
        ) or {"task_count": 0}
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
        return (
            int(pool["max_concurrent"])
            - int(active_row["active_count"])
            - int(task_row["task_count"])
            - int(reserved_row["ready_count"])
        )

    def _pool_has_capacity(self, pool_id: int, *, exclude_queue_id: int | None = None) -> bool:
        return self._available_slots(pool_id, exclude_queue_id=exclude_queue_id) > 0

    def _enqueue_request(self, user_id: int, pool_id: int, requested_app_id: int) -> dict[str, Any]:
        self._db.execute_update(
            """
            /* rps:insert_queue_entry */
            INSERT INTO launch_queue (pool_id, user_id, requested_app_id)
            VALUES (%(pool_id)s, %(user_id)s, %(requested_app_id)s)
            """,
            {"pool_id": pool_id, "user_id": user_id, "requested_app_id": requested_app_id},
        )
        row = self._db.execute_query(
            """
            /* rps:get_latest_user_queue */
            SELECT id
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND user_id = %(user_id)s
              AND status = 'queued'
            ORDER BY id DESC
            LIMIT 1
            """,
            {"pool_id": pool_id, "user_id": user_id},
            fetch_one=True,
        )
        if not row:
            raise RuntimeError("排队创建失败")
        result = self.get_queue_status(queue_id=int(row["id"]), user_id=user_id)
        result["status"] = "queued"
        return result

    def _create_launch_reservation(self, user_id: int, pool_id: int, requested_app_id: int, assigned_app_id: int) -> int:
        now = self._now()
        self._db.execute_update(
            """
            /* rps:insert_queue_entry */
            INSERT INTO launch_queue (
                pool_id, user_id, requested_app_id, assigned_app_id, status, ready_at, last_seen_at
            )
            VALUES (
                %(pool_id)s, %(user_id)s, %(requested_app_id)s, %(assigned_app_id)s, 'launching', %(ready_at)s, %(last_seen_at)s
            )
            """,
            {
                "pool_id": pool_id,
                "user_id": user_id,
                "requested_app_id": requested_app_id,
                "assigned_app_id": assigned_app_id,
                "ready_at": now,
                "last_seen_at": now,
            },
        )
        row = self._db.execute_query(
            """
            /* rps:get_latest_user_queue */
            SELECT id
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND user_id = %(user_id)s
              AND status IN ('queued', 'launching')
            ORDER BY id DESC
            LIMIT 1
            """,
            {"pool_id": pool_id, "user_id": user_id, "include_launching": True},
            fetch_one=True,
        )
        if not row:
            raise RuntimeError("占位创建失败")
        return int(row["id"])

    def expire_ready_entries(self, *, pool_id: int | None = None) -> list[int]:
        now = self._now()
        rows = self._db.execute_query(
            """
            /* rps:list_expired_ready_entries */
            SELECT id
            FROM launch_queue
            WHERE status = 'ready'
              AND ready_expires_at IS NOT NULL
              AND ready_expires_at < %(now_ts)s
              AND (%(pool_id)s IS NULL OR pool_id = %(pool_id)s)
            ORDER BY id ASC
            """,
            {"now_ts": now, "pool_id": pool_id},
        )
        if not rows:
            return []
        self._db.execute_update(
            """
            /* rps:expire_ready_entries */
            UPDATE launch_queue
            SET status = 'expired',
                cancel_reason = 'timeout',
                cancelled_at = %(now_ts)s
            WHERE status = 'ready'
              AND ready_expires_at IS NOT NULL
              AND ready_expires_at < %(now_ts)s
              AND (%(pool_id)s IS NULL OR pool_id = %(pool_id)s)
            """,
            {"now_ts": now, "pool_id": pool_id},
        )
        return [int(row["id"]) for row in rows]

    def prepare_launch(self, *, user_id: int, requested_app_id: int, queue_id: int | None = None) -> dict[str, Any]:
        launch_target = self._db.execute_query(
            """
            /* rps:get_launch_target */
            SELECT
                a.id AS requested_app_id,
                a.pool_id,
                COALESCE(p.name, a.name) AS pool_name
            FROM remote_app a
            JOIN remote_app_acl acl
              ON acl.app_id = a.id
             AND acl.user_id = %(user_id)s
            LEFT JOIN resource_pool p
              ON p.id = a.pool_id
            WHERE a.id = %(app_id)s
              AND a.is_active = 1
              AND p.is_active = 1
            LIMIT 1
            """,
            {"user_id": user_id, "app_id": requested_app_id},
            fetch_one=True,
        )
        if not launch_target:
            raise ValueError("无权访问该应用")
        if launch_target.get("pool_id") is None:
            raise ValueError("应用未分配资源池")

        pool_id = int(launch_target["pool_id"])
        pool_name = str(launch_target["pool_name"])

        with self._pool_lock(pool_id):
            self.expire_ready_entries(pool_id=pool_id)

            if queue_id is not None:
                entry = self._db.execute_query(
                    """
                    /* rps:get_queue_entry_for_consume */
                    SELECT id, pool_id, status, assigned_app_id, ready_expires_at
                    FROM launch_queue
                    WHERE id = %(queue_id)s
                      AND user_id = %(user_id)s
                    LIMIT 1
                    """,
                    {"queue_id": queue_id, "user_id": user_id},
                    fetch_one=True,
                )
                if not entry:
                    raise ValueError("排队记录不存在")
                if int(entry["pool_id"]) != pool_id:
                    return self._invalidate_queue_if_unusable(queue_id=int(queue_id), user_id=user_id, pool_id=pool_id, reason="pool_mismatch")
                if str(entry["status"]) != "ready":
                    return self.get_queue_status(queue_id=queue_id, user_id=user_id)
                if entry.get("ready_expires_at") and entry["ready_expires_at"] < self._now():
                    self.expire_ready_entries(pool_id=pool_id)
                    return self.get_queue_status(queue_id=queue_id, user_id=user_id)

                member = self._db.execute_query(
                    """
                    /* rps:get_member_for_user */
                    SELECT a.id, a.pool_id
                    FROM remote_app a
                    JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
                    WHERE a.id = %(member_app_id)s
                      AND a.is_active = 1
                    LIMIT 1
                    """,
                    {"member_app_id": int(entry["assigned_app_id"]), "user_id": user_id},
                    fetch_one=True,
                )
                if not member:
                    return self._invalidate_queue_if_unusable(queue_id=int(queue_id), user_id=user_id, pool_id=pool_id, reason="member_unavailable")

                updated = self._db.execute_update(
                    """
                    /* rps:queue_mark_launching */
                    UPDATE launch_queue
                    SET status = 'launching'
                    WHERE id = %(queue_id)s
                      AND user_id = %(user_id)s
                      AND status = 'ready'
                    """,
                    {"queue_id": queue_id, "user_id": user_id},
                )
                if updated <= 0:
                    return self.get_queue_status(queue_id=queue_id, user_id=user_id)

                return {
                    "status": "started",
                    "pool_id": pool_id,
                    "member_app_id": int(entry["assigned_app_id"]),
                    "requested_app_name": pool_name,
                    "connection_name": f"app_{int(entry['assigned_app_id'])}",
                    "queue_id": int(queue_id),
                }

            live_state = self.get_live_user_pool_state(user_id=user_id, pool_id=pool_id)
            if live_state:
                if live_state["state_kind"] == "queue":
                    return self.get_queue_status(queue_id=int(live_state["id"]), user_id=user_id)
                raise ValueError("当前资源池已有运行中的会话")

            member = self.pick_launchable_member(user_id=user_id, pool_id=pool_id)
            if self._count_pool_live_queue_entries(pool_id) > 0 or not self._pool_has_capacity(pool_id) or not member:
                return self._enqueue_request(user_id, pool_id, requested_app_id)

            reservation_id = self._create_launch_reservation(
                user_id=user_id,
                pool_id=pool_id,
                requested_app_id=requested_app_id,
                assigned_app_id=int(member["id"]),
            )
            return {
                "status": "started",
                "pool_id": pool_id,
                "member_app_id": int(member["id"]),
                "requested_app_name": pool_name,
                "connection_name": f"app_{int(member['id'])}",
                "queue_id": reservation_id,
            }

    def get_queue_status(self, *, queue_id: int, user_id: int) -> dict[str, Any]:
        row = self._db.execute_query(
            """
            /* rps:get_queue_status */
            SELECT id, pool_id, status, ready_expires_at, cancel_reason
            FROM launch_queue
            WHERE id = %(queue_id)s
              AND user_id = %(user_id)s
            LIMIT 1
            """,
            {"queue_id": queue_id, "user_id": user_id},
            fetch_one=True,
        )
        if not row:
            raise ValueError("排队记录不存在")

        if str(row["status"]) in self.LIVE_QUEUE_STATES and not self._has_accessible_member(user_id=user_id, pool_id=int(row["pool_id"])):
            self._cancel_queue_as_invalid(int(row["id"]), "member_unavailable")
            row = self._db.execute_query(
                """
                /* rps:get_queue_status */
                SELECT id, pool_id, status, ready_expires_at, cancel_reason
                FROM launch_queue
                WHERE id = %(queue_id)s
                  AND user_id = %(user_id)s
                LIMIT 1
                """,
                {"queue_id": queue_id, "user_id": user_id},
                fetch_one=True,
            )
            if not row:
                raise ValueError("排队记录不存在")

        if str(row["status"]) == "ready" and row.get("ready_expires_at") and row["ready_expires_at"] < self._now():
            self.expire_ready_entries(pool_id=int(row["pool_id"]))
            row = self._db.execute_query(
                """
                /* rps:get_queue_status */
                SELECT id, pool_id, status, ready_expires_at, cancel_reason
                FROM launch_queue
                WHERE id = %(queue_id)s
                  AND user_id = %(user_id)s
                LIMIT 1
                """,
                {"queue_id": queue_id, "user_id": user_id},
                fetch_one=True,
            )
            if not row:
                raise ValueError("排队记录不存在")

        if str(row["status"]) in self.LIVE_QUEUE_STATES:
            self._db.execute_update(
                """
                /* rps:touch_queue */
                UPDATE launch_queue
                SET last_seen_at = NOW()
                WHERE id = %(queue_id)s
                  AND user_id = %(user_id)s
                """,
                {"queue_id": queue_id, "user_id": user_id},
            )

        position = 0
        if str(row["status"]) in self.LIVE_QUEUE_STATES:
            pos = self._db.execute_query(
                """
                /* rps:get_queue_position */
                SELECT COUNT(*) AS position
                FROM launch_queue
                WHERE pool_id = %(pool_id)s
                  AND status IN ('queued', 'ready', 'launching')
                  AND id <= %(queue_id)s
                """,
                {"pool_id": row["pool_id"], "queue_id": queue_id},
                fetch_one=True,
            ) or {"position": 0}
            position = int(pos["position"])

        return {
            "queue_id": int(row["id"]),
            "pool_id": int(row["pool_id"]),
            "status": str(row["status"]),
            "position": position,
            "ready_expires_at": row.get("ready_expires_at"),
            "cancel_reason": row.get("cancel_reason"),
        }

    def cancel_queue(self, *, queue_id: int, user_id: int) -> dict[str, Any]:
        row = self._db.execute_query(
            """
            /* rps:get_queue_status */
            SELECT id, pool_id, status, ready_expires_at, cancel_reason
            FROM launch_queue
            WHERE id = %(queue_id)s
              AND user_id = %(user_id)s
            LIMIT 1
            """,
            {"queue_id": queue_id, "user_id": user_id},
            fetch_one=True,
        )
        if not row:
            raise ValueError("排队记录不存在或已结束")
        updated = self._db.execute_update(
            """
            /* rps:cancel_queue */
            UPDATE launch_queue
            SET status = 'cancelled',
                cancel_reason = 'user',
                cancelled_at = NOW()
            WHERE id = %(queue_id)s
              AND user_id = %(user_id)s
              AND status IN ('queued', 'ready', 'launching')
            """,
            {"queue_id": queue_id, "user_id": user_id},
        )
        if updated <= 0:
            raise ValueError("排队记录不存在或已结束")
        return {
            "queue_id": queue_id,
            "pool_id": int(row["pool_id"]),
            "status": "cancelled",
            "position": 0,
            "ready_expires_at": row.get("ready_expires_at"),
            "cancel_reason": "user",
        }

    def _cancel_queue_as_invalid(self, queue_id: int, reason: str) -> int:
        return self._db.execute_update(
            """
            /* rps:cancel_queue_invalid */
            UPDATE launch_queue
            SET status = 'cancelled',
                cancel_reason = %(reason)s,
                cancelled_at = NOW()
            WHERE id = %(queue_id)s
              AND status IN ('queued', 'ready', 'launching')
            """,
            {"queue_id": queue_id, "reason": reason[:100]},
        )

    def mark_queue_fulfilled(self, *, queue_id: int, assigned_app_id: int):
        self._db.execute_update(
            """
            /* rps:queue_mark_fulfilled */
            UPDATE launch_queue
            SET status = 'fulfilled',
                assigned_app_id = %(assigned_app_id)s,
                fulfilled_at = NOW()
            WHERE id = %(queue_id)s
            """,
            {"queue_id": queue_id, "assigned_app_id": assigned_app_id},
        )

    def requeue_after_launch_failure(self, *, queue_id: int, last_error: str):
        row = self._db.execute_query(
            """
            /* rps:get_launching_row */
            SELECT id, ready_at
            FROM launch_queue
            WHERE id = %(queue_id)s
            LIMIT 1
            """,
            {"queue_id": queue_id},
            fetch_one=True,
        )
        if not row:
            return
        if row.get("ready_at") is None:
            self._db.execute_update(
                """
                /* rps:cancel_queue_admin */
                UPDATE launch_queue
                SET status = 'cancelled',
                    cancel_reason = 'launch_failed',
                    cancelled_at = NOW()
                WHERE id = %(queue_id)s
                  AND status = 'launching'
                """,
                {"queue_id": queue_id},
            )
            return
        self._db.execute_update(
            """
            /* rps:queue_restore_queued */
            UPDATE launch_queue
            SET status = 'queued',
                failure_count = failure_count + 1,
                last_error = %(last_error)s
            WHERE id = %(queue_id)s
              AND status = 'launching'
            """,
            {"queue_id": queue_id, "last_error": last_error[:500]},
        )

    def dispatch_ready_entries(self) -> list[int]:
        moved_ids: list[int] = []
        pools = self._db.execute_query(
            """
            /* rps:list_dispatch_pools */
            SELECT id, dispatch_grace_seconds
            FROM resource_pool
            WHERE is_active = 1
              AND auto_dispatch_enabled = 1
            ORDER BY id ASC
            """
        )
        for pool in pools:
            pool_id = int(pool["id"])
            with self._pool_lock(pool_id):
                self.expire_ready_entries(pool_id=pool_id)
                available_slots = self._available_slots(pool_id)
                while available_slots > 0:
                    queue_head = self._db.execute_query(
                        """
                        /* rps:get_queue_head */
                        SELECT id, user_id
                        FROM launch_queue
                        WHERE pool_id = %(pool_id)s
                          AND status = 'queued'
                          AND COALESCE(request_mode, 'gui') = 'gui'
                        ORDER BY created_at ASC, id ASC
                        LIMIT 1
                        """,
                        {"pool_id": pool_id},
                        fetch_one=True,
                    )
                    if not queue_head:
                        break
                    if not self._has_accessible_member(user_id=int(queue_head["user_id"]), pool_id=pool_id):
                        self._cancel_queue_as_invalid(int(queue_head["id"]), "member_unavailable")
                        continue
                    member = self.pick_launchable_member(user_id=int(queue_head["user_id"]), pool_id=pool_id)
                    if not member:
                        break
                    ready_at = self._now()
                    ready_expires_at = ready_at + timedelta(seconds=int(pool.get("dispatch_grace_seconds") or 120))
                    updated = self._db.execute_update(
                        """
                        /* rps:queue_mark_ready */
                        UPDATE launch_queue
                        SET status = 'ready',
                            ready_at = %(ready_at)s,
                            ready_expires_at = %(ready_expires_at)s,
                            assigned_app_id = %(assigned_app_id)s
                        WHERE id = %(queue_id)s
                          AND status = 'queued'
                        """,
                        {
                            "queue_id": int(queue_head["id"]),
                            "ready_at": ready_at,
                            "ready_expires_at": ready_expires_at,
                            "assigned_app_id": int(member["id"]),
                        },
                    )
                    if updated <= 0:
                        break
                    moved_ids.append(int(queue_head["id"]))
                    available_slots -= 1
        return moved_ids

    def _mark_session_reclaimed(self, *, session_id: str, reason: str, ended_at: datetime, target_status: str = "reclaimed") -> int:
        return self._db.execute_update(
            """
            /* rps:session_mark_reclaimed */
            UPDATE active_session
            SET status = %(target_status)s,
                reclaim_reason = %(reason)s,
                ended_at = %(ended_at)s
            WHERE session_id = %(session_id)s
              AND status IN ('active', 'reclaim_pending')
            """,
            {"session_id": session_id, "reason": reason, "ended_at": ended_at, "target_status": target_status},
        )

    def reclaim_stale_sessions(self) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_stale_sessions */
            SELECT s.session_id, s.user_id
            FROM active_session s
            LEFT JOIN resource_pool p ON p.id = s.pool_id
            WHERE s.status IN ('active', 'reclaim_pending')
              AND TIMESTAMPDIFF(SECOND, s.last_heartbeat, %(now_ts)s) > COALESCE(p.stale_timeout_seconds, %(fallback_stale_timeout_seconds)s)
            ORDER BY s.session_id ASC
            """,
            {
                "now_ts": self._now(),
                "fallback_stale_timeout_seconds": self.DEFAULT_STALE_TIMEOUT_SECONDS,
            },
        )
        reclaimed: list[dict[str, Any]] = []
        for row in rows:
            if self._mark_session_reclaimed(session_id=str(row["session_id"]), reason="stale", ended_at=self._now(), target_status="reclaimed") > 0:
                reclaimed.append({"session_id": str(row["session_id"]), "user_id": int(row["user_id"])})
        return reclaimed

    def reclaim_idle_sessions(self) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_idle_sessions */
            SELECT s.session_id, s.user_id
            FROM active_session s
            LEFT JOIN resource_pool p ON p.id = s.pool_id
            WHERE s.status = 'active'
              AND s.last_activity_at IS NOT NULL
              AND (
                    (
                        s.pool_id IS NULL
                        AND TIMESTAMPDIFF(SECOND, s.last_activity_at, %(now_ts)s) > %(fallback_idle_timeout_seconds)s
                    )
                    OR (
                        s.pool_id IS NOT NULL
                        AND p.idle_timeout_seconds IS NOT NULL
                        AND TIMESTAMPDIFF(SECOND, s.last_activity_at, %(now_ts)s) > COALESCE(p.idle_timeout_seconds, %(fallback_idle_timeout_seconds)s)
                    )
              )
            ORDER BY s.session_id ASC
            """,
            {
                "now_ts": self._now(),
                "fallback_idle_timeout_seconds": self.DEFAULT_ORPHAN_IDLE_TIMEOUT_SECONDS,
            },
        )
        reclaimed: list[dict[str, Any]] = []
        for row in rows:
            if self._mark_session_reclaimed(session_id=str(row["session_id"]), reason="idle", ended_at=self._now(), target_status="reclaim_pending") > 0:
                reclaimed.append({"session_id": str(row["session_id"]), "user_id": int(row["user_id"])})
        return reclaimed

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
        transaction = self._db.transaction() if hasattr(self._db, "transaction") else nullcontext(None)
        with transaction as conn:
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
                conn=conn,
            )
            insert_row = self._db.execute_query(
                "SELECT LAST_INSERT_ID() AS id",
                fetch_one=True,
                conn=conn,
            )
            if not insert_row or insert_row.get("id") is None:
                raise RuntimeError("资源池创建失败")
            row = self._db.execute_query(
                """
                /* rps:get_pool_admin */
                SELECT id, name, icon, max_concurrent, auto_dispatch_enabled,
                       dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active
                FROM resource_pool
                WHERE id = %(pool_id)s
                LIMIT 1
                """,
                {"pool_id": int(insert_row["id"])},
                fetch_one=True,
                conn=conn,
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
        rows = self._db.execute_query(
            """
            /* rps:list_live_queues */
            SELECT id, pool_id, user_id, requested_app_id, assigned_app_id, status, platform_task_id, request_mode
            FROM launch_queue
            WHERE status IN ('queued', 'ready', 'launching')
              AND (%(user_id)s IS NULL OR user_id = %(user_id)s)
              AND (%(requested_app_id)s IS NULL OR requested_app_id = %(requested_app_id)s)
              AND (%(pool_id)s IS NULL OR pool_id = %(pool_id)s)
            ORDER BY id ASC
            """,
            {"user_id": user_id, "requested_app_id": requested_app_id, "pool_id": pool_id},
        )
        cancelled: list[int] = []
        for row in rows:
            qid = int(row["id"])
            q_pool_id = int(row["pool_id"])
            q_user_id = int(row["user_id"])
            requested = self._db.execute_query(
                """
                /* rps:get_launch_target */
                SELECT
                    a.id AS requested_app_id,
                    a.pool_id,
                    COALESCE(p.name, a.name) AS pool_name
                FROM remote_app a
                JOIN remote_app_acl acl
                  ON acl.app_id = a.id
                 AND acl.user_id = %(user_id)s
                LEFT JOIN resource_pool p
                  ON p.id = a.pool_id
                WHERE a.id = %(app_id)s
                  AND a.is_active = 1
                  AND p.is_active = 1
                LIMIT 1
                """,
                {"user_id": q_user_id, "app_id": int(row["requested_app_id"])},
                fetch_one=True,
            )
            if not requested or requested.get("pool_id") is None or int(requested["pool_id"]) != q_pool_id:
                if self._cancel_queue_as_invalid(qid, "config_changed") > 0:
                    self._cancel_task_for_queue(row.get("platform_task_id"), "config_changed")
                    cancelled.append(qid)
                continue
            if row.get("assigned_app_id") and str(row["status"]) in {"ready", "launching"}:
                assigned = self._db.execute_query(
                    """
                    /* rps:get_member_for_user */
                    SELECT id, pool_id
                    FROM remote_app a
                    JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
                    WHERE a.id = %(member_app_id)s
                      AND a.is_active = 1
                    LIMIT 1
                    """,
                    {"member_app_id": int(row["assigned_app_id"]), "user_id": q_user_id},
                    fetch_one=True,
                )
                if not assigned or int(assigned["pool_id"]) != q_pool_id:
                    if self._cancel_queue_as_invalid(qid, "member_unavailable") > 0:
                        self._cancel_task_for_queue(row.get("platform_task_id"), "member_unavailable")
                        cancelled.append(qid)
                    continue
            if not self._has_accessible_member(q_user_id, q_pool_id):
                if self._cancel_queue_as_invalid(qid, "member_unavailable") > 0:
                    self._cancel_task_for_queue(row.get("platform_task_id"), "member_unavailable")
                    cancelled.append(qid)
        return cancelled

    def reclaim_pool_sessions(self, *, pool_id: int, reason: str = "admin") -> list[str]:
        rows = self._db.execute_query(
            """
            SELECT session_id
            FROM active_session
            WHERE pool_id = %(pool_id)s
              AND status IN ('active', 'reclaim_pending')
            ORDER BY id ASC
            """,
            {"pool_id": pool_id},
        )
        session_ids = [str(row["session_id"]) for row in rows]
        if session_ids:
            self._db.execute_update(
                """
                UPDATE active_session
                SET status = 'reclaim_pending',
                    reclaim_reason = %(reason)s,
                    ended_at = NOW()
                WHERE pool_id = %(pool_id)s
                  AND status IN ('active', 'reclaim_pending')
                """,
                {"pool_id": pool_id, "reason": reason},
            )
        return session_ids

    def cancel_pool_tasks(self, *, pool_id: int, reason: str = "pool_disabled") -> int:
        cancelled = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'cancelled',
                cancel_requested = 0,
                ended_at = NOW(),
                result_summary_json = JSON_OBJECT('error', %(reason)s)
            WHERE resource_pool_id = %(pool_id)s
              AND status IN ('queued', 'submitted')
            """,
            {"pool_id": pool_id, "reason": reason},
        )
        cancelled += self._db.execute_update(
            """
            UPDATE platform_task
            SET cancel_requested = 1,
                result_summary_json = COALESCE(result_summary_json, JSON_OBJECT('error', %(reason)s))
            WHERE resource_pool_id = %(pool_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            """,
            {"pool_id": pool_id, "reason": reason},
        )
        return cancelled

    def cancel_queue_admin(self, *, queue_id: int) -> dict[str, Any]:
        row = self._db.execute_query(
            """
            /* rps:get_queue_for_admin_cancel */
            SELECT id, request_mode, platform_task_id
            FROM launch_queue
            WHERE id = %(queue_id)s
              AND status IN ('queued', 'ready', 'launching')
            LIMIT 1
            """,
            {"queue_id": queue_id},
            fetch_one=True,
        )
        if not row:
            raise ValueError("排队记录不存在或已结束")
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
        if str(row.get("request_mode") or "gui") == "task":
            self._cancel_task_for_queue(row.get("platform_task_id"), "admin")
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
