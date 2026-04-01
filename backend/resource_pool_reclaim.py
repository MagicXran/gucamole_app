"""Session reclaim helpers for the resource pool state machine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class ResourcePoolReclaimService:
    def __init__(
        self,
        db,
        *,
        now_provider: Callable[[], datetime],
        fallback_stale_timeout_seconds: int,
        fallback_idle_timeout_seconds: int,
    ):
        self._db = db
        self._now_provider = now_provider
        self._fallback_stale_timeout_seconds = fallback_stale_timeout_seconds
        self._fallback_idle_timeout_seconds = fallback_idle_timeout_seconds

    def _now(self) -> datetime:
        return self._now_provider()

    def mark_session_reclaimed(
        self,
        *,
        session_id: str,
        reason: str,
        ended_at: datetime,
        target_status: str = "reclaimed",
    ) -> int:
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
            {
                "session_id": session_id,
                "reason": reason,
                "ended_at": ended_at,
                "target_status": target_status,
            },
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
                "fallback_stale_timeout_seconds": self._fallback_stale_timeout_seconds,
            },
        )
        reclaimed: list[dict[str, Any]] = []
        for row in rows:
            if self.mark_session_reclaimed(
                session_id=str(row["session_id"]),
                reason="stale",
                ended_at=self._now(),
                target_status="reclaimed",
            ) > 0:
                reclaimed.append(
                    {"session_id": str(row["session_id"]), "user_id": int(row["user_id"])}
                )
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
                "fallback_idle_timeout_seconds": self._fallback_idle_timeout_seconds,
            },
        )
        reclaimed: list[dict[str, Any]] = []
        for row in rows:
            if self.mark_session_reclaimed(
                session_id=str(row["session_id"]),
                reason="idle",
                ended_at=self._now(),
                target_status="reclaim_pending",
            ) > 0:
                reclaimed.append(
                    {"session_id": str(row["session_id"]), "user_id": int(row["user_id"])}
                )
        return reclaimed
