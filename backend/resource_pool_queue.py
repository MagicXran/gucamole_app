"""Launch/queue coordinator for the resource pool state machine."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable


class ResourcePoolQueueService:
    def __init__(
        self,
        db,
        queries,
        *,
        now_provider: Callable[[], Any],
        pool_lock: Callable[[int], Any],
        get_live_user_pool_state: Callable[[int, int], dict[str, Any] | None],
        pick_launchable_member: Callable[..., dict[str, Any] | None],
        has_accessible_member: Callable[[int, int], bool],
        count_pool_live_queue_entries: Callable[[int], int],
        available_slots: Callable[..., int],
        live_queue_states: tuple[str, ...],
    ):
        self._db = db
        self._queries = queries
        self._now_provider = now_provider
        self._pool_lock = pool_lock
        self._get_live_user_pool_state = get_live_user_pool_state
        self._pick_launchable_member = pick_launchable_member
        self._has_accessible_member = has_accessible_member
        self._count_pool_live_queue_entries = count_pool_live_queue_entries
        self._available_slots = available_slots
        self._live_queue_states = set(live_queue_states)

    def _now(self):
        return self._now_provider()

    def _enqueue_request(self, user_id: int, pool_id: int, requested_app_id: int) -> dict[str, Any]:
        self._db.execute_update(
            """
            /* rps:insert_queue_entry */
            INSERT INTO launch_queue (pool_id, user_id, requested_app_id)
            VALUES (%(pool_id)s, %(user_id)s, %(requested_app_id)s)
            """,
            {"pool_id": pool_id, "user_id": user_id, "requested_app_id": requested_app_id},
        )
        row = self._queries.get_latest_user_queue(pool_id=pool_id, user_id=user_id)
        if not row:
            raise RuntimeError("排队创建失败")
        result = self.get_queue_status(queue_id=int(row["id"]), user_id=user_id)
        result["status"] = "queued"
        return result

    def _create_launch_reservation(
        self,
        user_id: int,
        pool_id: int,
        requested_app_id: int,
        assigned_app_id: int,
    ) -> int:
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
        row = self._queries.get_latest_user_queue(
            pool_id=pool_id,
            user_id=user_id,
            include_launching=True,
        )
        if not row:
            raise RuntimeError("占位创建失败")
        return int(row["id"])

    def expire_ready_entries(self, *, pool_id: int | None = None) -> list[int]:
        now = self._now()
        rows = self._queries.list_expired_ready_entries(now_ts=now, pool_id=pool_id)
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
        launch_target = self._queries.get_launch_target(user_id=user_id, app_id=requested_app_id)
        if not launch_target:
            raise ValueError("无权访问该应用")
        if launch_target.get("pool_id") is None:
            raise ValueError("应用未分配资源池")

        pool_id = int(launch_target["pool_id"])
        pool_name = str(launch_target["pool_name"])

        with self._pool_lock(pool_id):
            self.expire_ready_entries(pool_id=pool_id)

            if queue_id is not None:
                entry = self._queries.get_queue_entry_for_consume(queue_id=queue_id, user_id=user_id)
                if not entry:
                    raise ValueError("排队记录不存在")
                if int(entry["pool_id"]) != pool_id:
                    return self._invalidate_queue_if_unusable(
                        queue_id=int(queue_id),
                        user_id=user_id,
                        pool_id=pool_id,
                        reason="pool_mismatch",
                    )
                if str(entry["status"]) != "ready":
                    return self.get_queue_status(queue_id=queue_id, user_id=user_id)
                if entry.get("ready_expires_at") and entry["ready_expires_at"] < self._now():
                    self.expire_ready_entries(pool_id=pool_id)
                    return self.get_queue_status(queue_id=queue_id, user_id=user_id)

                member = self._queries.get_member_for_user(
                    member_app_id=int(entry["assigned_app_id"]),
                    user_id=user_id,
                )
                if not member or int(member["pool_id"]) != pool_id:
                    return self._invalidate_queue_if_unusable(
                        queue_id=int(queue_id),
                        user_id=user_id,
                        pool_id=pool_id,
                        reason="member_unavailable",
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
                    "member_app_id": int(entry["assigned_app_id"]),
                    "requested_app_name": pool_name,
                    "connection_name": f"app_{int(entry['assigned_app_id'])}",
                    "queue_id": int(queue_id),
                }

            live_state = self._get_live_user_pool_state(user_id=user_id, pool_id=pool_id)
            if live_state:
                if live_state["state_kind"] == "queue":
                    return self.get_queue_status(queue_id=int(live_state["id"]), user_id=user_id)
                raise ValueError("当前资源池已有运行中的会话")

            member = self._pick_launchable_member(user_id=user_id, pool_id=pool_id)
            if (
                self._count_pool_live_queue_entries(pool_id) > 0
                or self._available_slots(pool_id) <= 0
                or not member
            ):
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
        row = self._queries.get_queue_status_row(queue_id=queue_id, user_id=user_id)
        if not row:
            raise ValueError("排队记录不存在")

        if str(row["status"]) in self._live_queue_states and not self._has_accessible_member(
            user_id=user_id,
            pool_id=int(row["pool_id"]),
        ):
            self._cancel_queue_as_invalid(int(row["id"]), "member_unavailable")
            row = self._queries.get_queue_status_row(queue_id=queue_id, user_id=user_id)
            if not row:
                raise ValueError("排队记录不存在")

        if str(row["status"]) == "ready" and row.get("ready_expires_at") and row["ready_expires_at"] < self._now():
            self.expire_ready_entries(pool_id=int(row["pool_id"]))
            row = self._queries.get_queue_status_row(queue_id=queue_id, user_id=user_id)
            if not row:
                raise ValueError("排队记录不存在")

        if str(row["status"]) in self._live_queue_states:
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
        if str(row["status"]) in self._live_queue_states:
            pos = self._queries.get_queue_position(pool_id=int(row["pool_id"]), queue_id=queue_id) or {"position": 0}
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
        row = self._queries.get_queue_status_row(queue_id=queue_id, user_id=user_id)
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

    def _invalidate_queue_if_unusable(self, *, queue_id: int, user_id: int, pool_id: int, reason: str = "member_unavailable") -> dict[str, Any]:
        self._cancel_queue_as_invalid(queue_id, reason)
        return self.get_queue_status(queue_id=queue_id, user_id=user_id)

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
        row = self._queries.get_launching_row(queue_id=queue_id)
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
        pools = self._queries.list_dispatch_pools()
        for pool in pools:
            pool_id = int(pool["id"])
            with self._pool_lock(pool_id):
                self.expire_ready_entries(pool_id=pool_id)
                available_slots = self._available_slots(pool_id)
                while available_slots > 0:
                    queue_head = self._queries.get_queue_head(pool_id=pool_id)
                    if not queue_head:
                        break
                    if not self._has_accessible_member(user_id=int(queue_head["user_id"]), pool_id=pool_id):
                        self._cancel_queue_as_invalid(int(queue_head["id"]), "member_unavailable")
                        continue
                    member = self._pick_launchable_member(user_id=int(queue_head["user_id"]), pool_id=pool_id)
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

    def cleanup_invalid_queue_entries(
        self,
        *,
        user_id: int | None = None,
        requested_app_id: int | None = None,
        pool_id: int | None = None,
    ) -> list[int]:
        rows = self._queries.list_live_queues(
            user_id=user_id,
            requested_app_id=requested_app_id,
            pool_id=pool_id,
        )
        cancelled: list[int] = []
        for row in rows:
            qid = int(row["id"])
            q_pool_id = int(row["pool_id"])
            q_user_id = int(row["user_id"])
            requested = self._queries.get_launch_target(
                user_id=q_user_id,
                app_id=int(row["requested_app_id"]),
            )
            if not requested or requested.get("pool_id") is None or int(requested["pool_id"]) != q_pool_id:
                if self._cancel_queue_as_invalid(qid, "config_changed") > 0:
                    cancelled.append(qid)
                continue
            if row.get("assigned_app_id") and str(row["status"]) in {"ready", "launching"}:
                assigned = self._queries.get_member_for_user(
                    member_app_id=int(row["assigned_app_id"]),
                    user_id=q_user_id,
                )
                if not assigned or int(assigned["pool_id"]) != q_pool_id:
                    if self._cancel_queue_as_invalid(qid, "member_unavailable") > 0:
                        cancelled.append(qid)
                    continue
            if not self._has_accessible_member(q_user_id, q_pool_id):
                if self._cancel_queue_as_invalid(qid, "member_unavailable") > 0:
                    cancelled.append(qid)
        return cancelled
