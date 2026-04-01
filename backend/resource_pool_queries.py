"""Shared query helpers for the resource pool state machine."""

from __future__ import annotations


class ResourcePoolQueryService:
    def __init__(self, db):
        self._db = db

    def get_launch_target(self, *, user_id: int, app_id: int):
        return self._db.execute_query(
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
            {"user_id": user_id, "app_id": app_id},
            fetch_one=True,
        )

    def get_queue_entry_for_consume(self, *, queue_id: int, user_id: int):
        return self._db.execute_query(
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

    def get_latest_user_queue(self, *, pool_id: int, user_id: int, include_launching: bool = False):
        statuses = "'queued', 'launching'" if include_launching else "'queued'"
        return self._db.execute_query(
            f"""
            /* rps:get_latest_user_queue */
            SELECT id
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND user_id = %(user_id)s
              AND status IN ({statuses})
            ORDER BY id DESC
            LIMIT 1
            """,
            {"pool_id": pool_id, "user_id": user_id, "include_launching": include_launching},
            fetch_one=True,
        )

    def get_member_for_user(self, *, member_app_id: int, user_id: int):
        return self._db.execute_query(
            """
            /* rps:get_member_for_user */
            SELECT id, pool_id
            FROM remote_app a
            JOIN remote_app_acl acl ON acl.app_id = a.id AND acl.user_id = %(user_id)s
            WHERE a.id = %(member_app_id)s
              AND a.is_active = 1
            LIMIT 1
            """,
            {"member_app_id": member_app_id, "user_id": user_id},
            fetch_one=True,
        )

    def get_queue_status_row(self, *, queue_id: int, user_id: int):
        return self._db.execute_query(
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

    def list_expired_ready_entries(self, *, now_ts, pool_id: int | None = None):
        return self._db.execute_query(
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
            {"now_ts": now_ts, "pool_id": pool_id},
        )

    def get_queue_position(self, *, pool_id: int, queue_id: int):
        return self._db.execute_query(
            """
            /* rps:get_queue_position */
            SELECT COUNT(*) AS position
            FROM launch_queue
            WHERE pool_id = %(pool_id)s
              AND status IN ('queued', 'ready', 'launching')
              AND id <= %(queue_id)s
            """,
            {"pool_id": pool_id, "queue_id": queue_id},
            fetch_one=True,
        )

    def get_launching_row(self, *, queue_id: int):
        return self._db.execute_query(
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

    def list_dispatch_pools(self):
        return self._db.execute_query(
            """
            /* rps:list_dispatch_pools */
            SELECT id, dispatch_grace_seconds
            FROM resource_pool
            WHERE is_active = 1
              AND auto_dispatch_enabled = 1
            ORDER BY id ASC
            """
        )

    def get_queue_head(self, *, pool_id: int):
        return self._db.execute_query(
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

    def list_live_queues(
        self,
        *,
        user_id: int | None = None,
        requested_app_id: int | None = None,
        pool_id: int | None = None,
    ):
        return self._db.execute_query(
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
