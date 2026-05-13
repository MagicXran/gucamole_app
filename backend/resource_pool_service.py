"""资源池与排队调度服务。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import socket
from typing import Any, Callable

from backend.database import CONFIG


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
    DEFAULT_RUNTIME_FAILURE_COOLDOWN_SECONDS = int(_monitor_cfg.get("runtime_failure_cooldown_seconds", 300))
    DEFAULT_RUNTIME_MAX_COOLDOWN_SECONDS = int(_monitor_cfg.get("runtime_failure_max_cooldown_seconds", 1800))
    DEFAULT_RUNTIME_PROBE_TIMEOUT_SECONDS = float(_monitor_cfg.get("runtime_probe_timeout_seconds", 1.5))

    def __init__(self, db, now_provider: Callable[[], datetime] | None = None):
        self._db = db
        self._now_provider = now_provider or datetime.now

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _same_user_same_app_limit() -> int:
        launch_policy = CONFIG.get("launch_policy", {}) or {}
        raw_limit = launch_policy.get("same_user_same_app_limit", 0)
        try:
            return max(0, int(raw_limit or 0))
        except (TypeError, ValueError):
            return 0

    @contextmanager
    def _named_lock(self, lock_name: str):
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

    @contextmanager
    def _pool_lock(self, pool_id: int):
        with self._named_lock(f"resource_pool:{pool_id}"):
            yield

    @contextmanager
    def _runtime_lock(self, runtime_id: int):
        with self._named_lock(f"remote_app:{runtime_id}"):
            yield

    @staticmethod
    def _runtime_health_status_meta(status: str) -> dict[str, str]:
        normalized = str(status or "unknown").strip().lower() or "unknown"
        meta = {
            "healthy": {"label": "健康", "tone": "success"},
            "unknown": {"label": "未探测", "tone": "neutral"},
            "cooldown": {"label": "冷却中", "tone": "warning"},
            "unreachable": {"label": "不可达", "tone": "danger"},
        }.get(normalized)
        if meta:
            return {"status": normalized, **meta}
        return {"status": normalized, "label": normalized, "tone": "neutral"}

    @staticmethod
    def _runtime_health_sort_rank(status: str) -> int:
        normalized = str(status or "unknown").strip().lower() or "unknown"
        if normalized == "healthy":
            return 0
        if normalized == "unknown":
            return 1
        if normalized == "cooldown":
            return 2
        if normalized == "unreachable":
            return 3
        return 4

    def _build_runtime_health_payload(self, row: dict[str, Any] | None) -> dict[str, Any]:
        row = row or {}
        meta = self._runtime_health_status_meta(str(row.get("health_status") or "unknown"))
        return {
            "status": meta["status"],
            "label": meta["label"],
            "tone": meta["tone"],
            "consecutive_failures": int(row.get("consecutive_failures") or 0),
            "cooldown_until": row.get("cooldown_until"),
            "last_failure_reason": str(row.get("last_failure_reason") or "") or None,
            "last_probe_ok": row.get("last_probe_ok"),
        }

    def get_runtime_health(self, runtime_id: int) -> dict[str, Any]:
        row = self._db.execute_query(
            """
            /* rps:get_runtime_health */
            SELECT remote_app_id, health_status, consecutive_failures, cooldown_until,
                   last_failure_reason, last_probe_ok
            FROM remote_app_health
            WHERE remote_app_id = %(runtime_id)s
            LIMIT 1
            """,
            {"runtime_id": runtime_id},
            fetch_one=True,
        )
        return self._build_runtime_health_payload(row)

    def runtime_is_launchable(self, runtime_id: int) -> tuple[bool, dict[str, Any]]:
        health = self.get_runtime_health(runtime_id)
        cooldown_until = health.get("cooldown_until")
        if cooldown_until and cooldown_until > self._now():
            return False, health
        if health["status"] == "unreachable":
            return False, health
        return True, health

    def _count_runtime_active_sessions(self, runtime_id: int) -> int:
        row = self._db.execute_query(
            """
            /* rps:get_runtime_active_session_count */
            SELECT COUNT(*) AS active_count
            FROM active_session
            WHERE app_id = %(runtime_id)s
              AND status IN ('active', 'reclaim_pending')
            """,
            {"runtime_id": runtime_id},
            fetch_one=True,
        ) or {"active_count": 0}
        return int(row.get("active_count") or 0)

    def mark_runtime_launch_success(self, runtime_id: int):
        self._db.execute_update(
            """
            /* rps:mark_runtime_launch_success */
            INSERT INTO remote_app_health (
                remote_app_id, health_status, consecutive_failures, cooldown_until,
                last_failure_at, last_failure_reason, last_success_at, last_probe_at, last_probe_ok
            )
            VALUES (
                %(runtime_id)s, 'healthy', 0, NULL, NULL, NULL, %(event_at)s, %(event_at)s, 1
            )
            ON DUPLICATE KEY UPDATE
                health_status = 'healthy',
                consecutive_failures = 0,
                cooldown_until = NULL,
                last_failure_at = NULL,
                last_failure_reason = NULL,
                last_success_at = VALUES(last_success_at),
                last_probe_at = VALUES(last_probe_at),
                last_probe_ok = VALUES(last_probe_ok)
            """,
            {"runtime_id": runtime_id, "event_at": self._now()},
        )

    def mark_runtime_launch_failure(self, runtime_id: int, reason: str):
        current = self.get_runtime_health(runtime_id)
        failures = int(current.get("consecutive_failures") or 0) + 1
        cooldown_seconds = min(
            self.DEFAULT_RUNTIME_FAILURE_COOLDOWN_SECONDS * (2 ** max(0, failures - 1)),
            self.DEFAULT_RUNTIME_MAX_COOLDOWN_SECONDS,
        )
        event_at = self._now()
        self._db.execute_update(
            """
            /* rps:mark_runtime_launch_failure */
            INSERT INTO remote_app_health (
                remote_app_id, health_status, consecutive_failures, cooldown_until,
                last_failure_at, last_failure_reason, last_success_at, last_probe_at, last_probe_ok
            )
            VALUES (
                %(runtime_id)s, 'cooldown', %(failures)s, %(cooldown_until)s,
                %(event_at)s, %(reason)s, NULL, %(event_at)s, 0
            )
            ON DUPLICATE KEY UPDATE
                health_status = 'cooldown',
                consecutive_failures = %(failures)s,
                cooldown_until = %(cooldown_until)s,
                last_failure_at = %(event_at)s,
                last_failure_reason = %(reason)s,
                last_probe_at = %(event_at)s,
                last_probe_ok = 0
            """,
            {
                "runtime_id": runtime_id,
                "failures": failures,
                "cooldown_until": event_at + timedelta(seconds=cooldown_seconds),
                "event_at": event_at,
                "reason": (reason or "launch failed")[:500],
            },
        )

    def probe_runtime_health(self) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_runtime_probe_targets */
            SELECT
                a.id,
                a.hostname,
                a.port,
                h.health_status,
                h.cooldown_until,
                h.consecutive_failures
            FROM remote_app a
            LEFT JOIN remote_app_health h
              ON h.remote_app_id = a.id
            WHERE a.is_active = 1
            ORDER BY a.id ASC
            """
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            runtime_id = int(row["id"])
            probe_ok = False
            try:
                with socket.create_connection(
                    (str(row["hostname"]), int(row.get("port") or 3389)),
                    timeout=self.DEFAULT_RUNTIME_PROBE_TIMEOUT_SECONDS,
                ):
                    probe_ok = True
            except OSError:
                probe_ok = False

            event_at = self._now()
            if probe_ok:
                health_status = str(row.get("health_status") or "unknown")
                cooldown_until = row.get("cooldown_until")
                if health_status == "cooldown" and cooldown_until and cooldown_until > event_at:
                    self._db.execute_update(
                        """
                        /* rps:update_runtime_probe */
                        INSERT INTO remote_app_health (
                            remote_app_id, health_status, consecutive_failures, cooldown_until,
                            last_probe_at, last_probe_ok
                        )
                        VALUES (
                            %(runtime_id)s, %(health_status)s, %(consecutive_failures)s, %(cooldown_until)s,
                            %(event_at)s, 1
                        )
                        ON DUPLICATE KEY UPDATE
                            last_probe_at = %(event_at)s,
                            last_probe_ok = 1
                        """,
                        {
                            "runtime_id": runtime_id,
                            "health_status": health_status,
                            "consecutive_failures": int(row.get("consecutive_failures") or 0),
                            "cooldown_until": cooldown_until,
                            "event_at": event_at,
                        },
                    )
                else:
                    self.mark_runtime_launch_success(runtime_id)
            else:
                health_status = str(row.get("health_status") or "unknown")
                cooldown_until = row.get("cooldown_until")
                if health_status == "cooldown" and cooldown_until and cooldown_until > event_at:
                    self._db.execute_update(
                        """
                        /* rps:update_runtime_probe */
                        INSERT INTO remote_app_health (
                            remote_app_id, health_status, consecutive_failures, cooldown_until,
                            last_probe_at, last_probe_ok
                        )
                        VALUES (
                            %(runtime_id)s, %(health_status)s, %(consecutive_failures)s, %(cooldown_until)s,
                            %(event_at)s, 0
                        )
                        ON DUPLICATE KEY UPDATE
                            last_probe_at = %(event_at)s,
                            last_probe_ok = 0
                        """,
                        {
                            "runtime_id": runtime_id,
                            "health_status": health_status,
                            "consecutive_failures": int(row.get("consecutive_failures") or 0),
                            "cooldown_until": cooldown_until,
                            "event_at": event_at,
                        },
                    )
                else:
                    self._db.execute_update(
                        """
                        /* rps:mark_runtime_probe_failed */
                        INSERT INTO remote_app_health (
                            remote_app_id, health_status, consecutive_failures, cooldown_until,
                            last_failure_reason, last_probe_at, last_probe_ok
                        )
                        VALUES (
                            %(runtime_id)s, 'unreachable', 0, NULL, 'tcp connect failed', %(event_at)s, 0
                        )
                        ON DUPLICATE KEY UPDATE
                            health_status = 'unreachable',
                            last_failure_reason = 'tcp connect failed',
                            last_probe_at = %(event_at)s,
                            last_probe_ok = 0
                        """,
                        {"runtime_id": runtime_id, "event_at": event_at},
                    )
            results.append({"runtime_id": runtime_id, "probe_ok": probe_ok})
        return results

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

    def _count_user_app_live_entries(
        self,
        *,
        user_id: int,
        app_id: int,
        exclude_queue_id: int | None = None,
    ) -> int:
        row = self._db.execute_query(
            """
            /* rps:get_user_app_live_count */
            SELECT
                (
                    SELECT COUNT(*)
                    FROM active_session s
                    WHERE s.user_id = %(user_id)s
                      AND s.app_id = %(app_id)s
                      AND s.status IN ('active', 'reclaim_pending')
                ) + (
                    SELECT COUNT(*)
                    FROM launch_queue q
                    WHERE q.user_id = %(user_id)s
                      AND q.assigned_app_id = %(app_id)s
                      AND q.status IN ('ready', 'launching')
                      AND (%(exclude_queue_id)s IS NULL OR q.id <> %(exclude_queue_id)s)
                ) AS live_count
            """,
            {
                "user_id": user_id,
                "app_id": app_id,
                "exclude_queue_id": exclude_queue_id,
            },
            fetch_one=True,
        ) or {"live_count": 0}
        return int(row.get("live_count") or 0)

    def pick_launchable_member(self, user_id: int, pool_id: int, *, exclude_queue_id: int | None = None) -> dict[str, Any] | None:
        rows = self._db.execute_query(
            """
            /* rps:list_pool_members_with_load */
            SELECT
                a.id,
                a.pool_id,
                a.member_max_concurrent,
                COALESCE(h.health_status, 'unknown') AS health_status,
                COALESCE(h.consecutive_failures, 0) AS consecutive_failures,
                h.cooldown_until,
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
            LEFT JOIN remote_app_health h
              ON h.remote_app_id = a.id
            JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
            WHERE a.pool_id = %(pool_id)s
              AND a.is_active = 1
              AND (h.cooldown_until IS NULL OR h.cooldown_until <= NOW())
              AND COALESCE(h.health_status, 'unknown') NOT IN ('cooldown', 'unreachable')
            HAVING active_count < a.member_max_concurrent
            ORDER BY
                CASE COALESCE(h.health_status, 'unknown')
                    WHEN 'healthy' THEN 0
                    WHEN 'unknown' THEN 1
                    ELSE 9
                END ASC,
                COALESCE(h.consecutive_failures, 0) ASC,
                active_count ASC,
                a.id ASC
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
            "health_status": str(row.get("health_status") or "unknown"),
            "consecutive_failures": int(row.get("consecutive_failures") or 0),
            "cooldown_until": row.get("cooldown_until"),
        }

    def _build_resource_status_payload(
        self,
        *,
        has_capacity: bool,
        queued_count: int,
        active_count: int,
        max_concurrent: int,
        healthy_member_available: bool = True,
    ) -> dict[str, str]:
        if queued_count > 0:
            return {
                "resource_status_code": "queued",
                "resource_status_label": "排队中",
                "resource_status_tone": "warning",
            }
        if active_count >= max_concurrent:
            return {
                "resource_status_code": "busy",
                "resource_status_label": "忙碌",
                "resource_status_tone": "warning",
            }
        if has_capacity and healthy_member_available:
            return {
                "resource_status_code": "available",
                "resource_status_label": "可用",
                "resource_status_tone": "success",
            }
        return {
            "resource_status_code": "runtime_unavailable",
            "resource_status_label": "运行实例异常",
            "resource_status_tone": "danger",
        }

    def _list_standalone_runtime_cards(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_standalone_runtimes */
            SELECT
                a.id,
                a.id AS runtime_id,
                a.name,
                a.icon,
                a.app_kind,
                a.protocol,
                a.member_max_concurrent AS max_concurrent,
                COALESCE(sp.is_enabled, 0) AS supports_script,
                CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN a.id ELSE NULL END AS script_runtime_id,
                COALESCE(h.health_status, 'unknown') AS runtime_health_status,
                COALESCE(h.consecutive_failures, 0) AS runtime_consecutive_failures,
                h.cooldown_until AS runtime_cooldown_until,
                h.last_failure_reason AS runtime_last_failure_reason,
                COUNT(DISTINCT CASE WHEN s.status IN ('active', 'reclaim_pending') THEN s.id END) AS active_count
            FROM remote_app a
            JOIN remote_app_acl acl
              ON acl.app_id = a.id
             AND acl.user_id = %(user_id)s
            LEFT JOIN remote_app_script_profile sp
              ON sp.remote_app_id = a.id
            LEFT JOIN active_session s
              ON s.app_id = a.id
             AND s.status IN ('active', 'reclaim_pending')
            LEFT JOIN remote_app_health h
              ON h.remote_app_id = a.id
            WHERE a.pool_id IS NULL
              AND a.is_active = 1
            GROUP BY a.id, a.name, a.icon, a.app_kind, a.protocol, a.member_max_concurrent,
                     sp.is_enabled, h.health_status, h.consecutive_failures, h.cooldown_until, h.last_failure_reason
            ORDER BY a.name ASC, a.id ASC
            """,
            {"user_id": user_id},
        )
        cards: list[dict[str, Any]] = []
        for row in rows:
            health = self._build_runtime_health_payload(
                {
                    "health_status": row.get("runtime_health_status"),
                    "consecutive_failures": row.get("runtime_consecutive_failures"),
                    "cooldown_until": row.get("runtime_cooldown_until"),
                    "last_failure_reason": row.get("runtime_last_failure_reason"),
                }
            )
            active_count = int(row.get("active_count") or 0)
            max_concurrent = int(row.get("max_concurrent") or 1)
            runtime_launchable, _ = self.runtime_is_launchable(int(row["runtime_id"]))
            has_capacity = runtime_launchable and active_count < max_concurrent
            cards.append(
                {
                    "id": int(row["id"]),
                    "pool_id": None,
                    "capacity_pool_id": None,
                    "runtime_id": int(row["runtime_id"]),
                    "launch_target_kind": "standalone_runtime",
                    "launch_target_label": "独立运行",
                    "name": str(row["name"]),
                    "icon": str(row.get("icon") or "desktop"),
                    "app_kind": str(row.get("app_kind") or "commercial_software"),
                    "protocol": str(row.get("protocol") or "rdp"),
                    "supports_gui": True,
                    "supports_script": bool(row.get("supports_script")),
                    "script_runtime_id": int(row["script_runtime_id"]) if row.get("script_runtime_id") else None,
                    "runtime_health_status": health["status"],
                    "runtime_health_status_label": health["label"],
                    "runtime_health_status_tone": health["tone"],
                    "active_count": active_count,
                    "queued_count": 0,
                    "max_concurrent": max_concurrent,
                    "has_capacity": has_capacity,
                    **self._build_resource_status_payload(
                        has_capacity=has_capacity,
                        queued_count=0,
                        active_count=active_count,
                        max_concurrent=max_concurrent,
                        healthy_member_available=runtime_launchable,
                    ),
                }
            )
        return cards

    def _prepare_standalone_launch(self, *, user_id: int, launch_target: dict[str, Any]) -> dict[str, Any]:
        runtime_id = int(launch_target["requested_app_id"])
        runtime_name = str(launch_target.get("name") or launch_target.get("pool_name") or runtime_id)
        same_user_same_app_limit = self._same_user_same_app_limit()
        with self._runtime_lock(runtime_id):
            runtime_launchable, health = self.runtime_is_launchable(runtime_id)
            if not runtime_launchable:
                if health["status"] == "cooldown" and health.get("cooldown_until"):
                    raise ValueError(f"运行实例“{runtime_name}”冷却中，请稍后重试")
                raise ValueError(f"运行实例“{runtime_name}”当前不可用，请联系管理员")

            active_count = self._count_runtime_active_sessions(runtime_id)
            max_concurrent = int(launch_target.get("member_max_concurrent") or 1)
            if active_count >= max_concurrent:
                raise ValueError(f"运行实例“{runtime_name}”已满，请稍后重试")

            if same_user_same_app_limit > 0:
                live_count = self._count_user_app_live_entries(user_id=user_id, app_id=runtime_id)
                if live_count >= same_user_same_app_limit:
                    raise ValueError(
                        f"同一用户最多同时打开 {same_user_same_app_limit} 个“{runtime_name}”实例，请先关闭现有窗口"
                    )

            return {
                "status": "started",
                "pool_id": None,
                "session_pool_id": None,
                "member_app_id": runtime_id,
                "requested_app_name": runtime_name,
                "connection_name": f"app_{runtime_id}",
                "queue_id": None,
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

    def _invalidate_queue_if_unusable(self, *, queue_id: int, user_id: int, pool_id: int, reason: str = "member_unavailable") -> dict[str, Any]:
        self._cancel_queue_as_invalid(queue_id, reason)
        return self.get_queue_status(queue_id=queue_id, user_id=user_id)

    def list_user_pools(self, user_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute_query(
            """
            /* rps:list_user_pools */
            SELECT
                MIN(a.id) AS launch_app_id,
                p.id AS pool_id,
                p.name,
                p.icon,
                MAX(a.app_kind) AS app_kind,
                MAX(a.protocol) AS protocol,
                MAX(COALESCE(sp.is_enabled, 0)) AS supports_script,
                MIN(CASE WHEN COALESCE(sp.is_enabled, 0) = 1 THEN a.id ELSE NULL END) AS script_runtime_id,
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
            member = self.pick_launchable_member(user_id=user_id, pool_id=pool_id)
            has_member_capacity = member is not None
            runtime_health = self._runtime_health_status_meta("healthy" if member else "unreachable")
            result.append({
                "id": int(row["launch_app_id"]),
                "pool_id": pool_id,
                "capacity_pool_id": pool_id,
                "runtime_id": int(row["launch_app_id"]),
                "launch_target_kind": "capacity_pool",
                "launch_target_label": "容量池",
                "name": str(row["name"]),
                "icon": str(row.get("icon") or "desktop"),
                "app_kind": str(row.get("app_kind") or "commercial_software"),
                "protocol": str(row.get("protocol") or "rdp"),
                "supports_gui": True,
                "supports_script": bool(row.get("supports_script")),
                "script_runtime_id": int(row["script_runtime_id"]) if row.get("script_runtime_id") else None,
                "runtime_health_status": runtime_health["status"],
                "runtime_health_status_label": "有可用成员" if member else "无健康成员",
                "runtime_health_status_tone": "success" if member else "danger",
                "active_count": active_count,
                "queued_count": queued_count,
                "max_concurrent": max_concurrent,
                "has_capacity": queued_count == 0 and active_count < max_concurrent and has_member_capacity,
                **self._build_resource_status_payload(
                    has_capacity=queued_count == 0 and active_count < max_concurrent and has_member_capacity,
                    queued_count=queued_count,
                    active_count=active_count,
                    max_concurrent=max_concurrent,
                    healthy_member_available=has_member_capacity,
                ),
            })
        result.extend(self._list_standalone_runtime_cards(user_id))
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
                a.name,
                a.pool_id,
                a.member_max_concurrent,
                COALESCE(p.name, a.name) AS pool_name
            FROM remote_app a
            JOIN remote_app_acl acl
              ON acl.app_id = a.id
             AND acl.user_id = %(user_id)s
            LEFT JOIN resource_pool p
              ON p.id = a.pool_id
            WHERE a.id = %(app_id)s
              AND a.is_active = 1
            LIMIT 1
            """,
            {"user_id": user_id, "app_id": requested_app_id},
            fetch_one=True,
        )
        if not launch_target:
            raise ValueError("无权访问该应用")
        if launch_target.get("pool_id") is None:
            return self._prepare_standalone_launch(user_id=user_id, launch_target=launch_target)

        pool_id = int(launch_target["pool_id"])
        pool_name = str(launch_target["pool_name"])
        same_user_same_app_limit = self._same_user_same_app_limit()

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

                if same_user_same_app_limit > 0:
                    live_count = self._count_user_app_live_entries(
                        user_id=user_id,
                        app_id=int(entry["assigned_app_id"]),
                        exclude_queue_id=int(queue_id),
                    )
                    if live_count >= same_user_same_app_limit:
                        self._cancel_queue_as_invalid(int(queue_id), "same_user_app_limit")
                        raise ValueError(
                            f"同一用户最多同时打开 {same_user_same_app_limit} 个“{pool_name}”实例，请先关闭现有窗口"
                        )

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
                    "session_pool_id": pool_id,
                    "member_app_id": int(entry["assigned_app_id"]),
                    "requested_app_name": pool_name,
                    "connection_name": f"app_{int(entry['assigned_app_id'])}",
                    "queue_id": int(queue_id),
                }

            live_state = self.get_live_user_pool_state(user_id=user_id, pool_id=pool_id)
            if live_state:
                if live_state["state_kind"] == "queue":
                    return self.get_queue_status(queue_id=int(live_state["id"]), user_id=user_id)

            member = self.pick_launchable_member(user_id=user_id, pool_id=pool_id)
            if self._count_pool_live_queue_entries(pool_id) > 0 or not self._pool_has_capacity(pool_id) or not member:
                return self._enqueue_request(user_id, pool_id, requested_app_id)

            if same_user_same_app_limit > 0:
                live_count = self._count_user_app_live_entries(
                    user_id=user_id,
                    app_id=int(member["id"]),
                )
                if live_count >= same_user_same_app_limit:
                    raise ValueError(
                        f"同一用户最多同时打开 {same_user_same_app_limit} 个“{pool_name}”实例，请先关闭现有窗口"
                    )

            reservation_id = self._create_launch_reservation(
                user_id=user_id,
                pool_id=pool_id,
                requested_app_id=requested_app_id,
                assigned_app_id=int(member["id"]),
            )
            return {
                "status": "started",
                "pool_id": pool_id,
                "session_pool_id": pool_id,
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
        rows = self._db.execute_query(
            """
            /* rps:list_live_queues */
            SELECT id, pool_id, user_id, requested_app_id, assigned_app_id, status
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
                LIMIT 1
                """,
                {"user_id": q_user_id, "app_id": int(row["requested_app_id"])},
                fetch_one=True,
            )
            if not requested or requested.get("pool_id") is None or int(requested["pool_id"]) != q_pool_id:
                if self._cancel_queue_as_invalid(qid, "config_changed") > 0:
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
                        cancelled.append(qid)
                    continue
            if not self._has_accessible_member(q_user_id, q_pool_id):
                if self._cancel_queue_as_invalid(qid, "member_unavailable") > 0:
                    cancelled.append(qid)
        return cancelled

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
