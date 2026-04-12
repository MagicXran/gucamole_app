"""
MySQL-backed repository for worker enrollment and task claiming.
"""

from __future__ import annotations

import json
from datetime import datetime


class MySQLWorkerRepository:
    ACTIVE_TASK_STATUSES = ("assigned", "preparing", "running", "uploading")
    ACTIVE_SESSION_STATUSES = ("active", "reclaim_pending")

    def __init__(self, db):
        self._db = db

    @staticmethod
    def _decode_json(value):
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    @staticmethod
    def _encode_json(value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def _software_inventory_for_worker(self, worker_node: dict | None) -> dict:
        worker_node = worker_node or {}
        runtime_state = self._decode_json(worker_node.get("runtime_state_json")) or {}
        capabilities = self._decode_json(worker_node.get("capabilities_json")) or {}
        inventory = runtime_state.get("software_inventory")
        if isinstance(inventory, dict) and inventory:
            return inventory
        inventory = capabilities.get("software_inventory")
        if isinstance(inventory, dict):
            return inventory
        return {}

    def _software_gate_allows_task(self, worker_node: dict | None, candidate: dict | None) -> bool:
        candidate = candidate or {}
        params = self._decode_json(candidate.get("params_json")) or {}
        adapter_key = str(params.get("software_adapter_key") or params.get("script_profile_key") or "").strip()
        if not adapter_key:
            return True
        inventory = self._software_inventory_for_worker(worker_node)
        software_state = inventory.get(adapter_key) or {}
        return bool(software_state.get("ready"))

    def get_enrollment_by_hash(self, token_hash: str):
        row = self._db.execute_query(
            """
            SELECT *
            FROM worker_enrollment
            WHERE token_hash = %(token_hash)s
            LIMIT 1
            """,
            {"token_hash": token_hash},
            fetch_one=True,
        )
        return row

    def create_worker_group(self, payload: dict):
        self._db.execute_update(
            """
            INSERT INTO worker_group (group_key, name, description, max_claim_batch, is_active)
            VALUES (%(group_key)s, %(name)s, %(description)s, %(max_claim_batch)s, %(is_active)s)
            """,
            payload,
        )
        return self._db.execute_query(
            """
            SELECT *
            FROM worker_group
            WHERE group_key = %(group_key)s
            ORDER BY id DESC
            LIMIT 1
            """,
            {"group_key": payload["group_key"]},
            fetch_one=True,
        )

    def list_worker_groups(self):
        return self._db.execute_query(
            """
            SELECT
                g.*,
                (
                    SELECT COUNT(*)
                    FROM worker_node n
                    WHERE n.group_id = g.id
                ) AS node_count,
                (
                    SELECT COUNT(*)
                    FROM worker_node n
                    WHERE n.group_id = g.id
                      AND n.status = 'active'
                ) AS active_node_count
            FROM worker_group
            AS g
            ORDER BY name ASC, id ASC
            """
        )

    def create_worker_node(self, payload: dict):
        agent_id = payload["agent_id"]
        self._db.execute_update(
            """
            INSERT INTO worker_node (
                agent_id, group_id, display_name, expected_hostname, scratch_root,
                workspace_share, max_concurrent_tasks, status
            )
            VALUES (
                %(agent_id)s, %(group_id)s, %(display_name)s, %(expected_hostname)s, %(scratch_root)s,
                %(workspace_share)s, %(max_concurrent_tasks)s, 'pending_enrollment'
            )
            """,
            payload,
        )
        return self._db.execute_query(
            """
            SELECT *
            FROM worker_node
            WHERE agent_id = %(agent_id)s
            LIMIT 1
            """,
            {"agent_id": agent_id},
            fetch_one=True,
        )

    def list_worker_nodes(self):
        rows = self._db.execute_query(
            """
            SELECT
                n.*,
                g.group_key,
                g.name AS group_name,
                we.status AS latest_enrollment_status,
                we.issued_at AS latest_enrollment_issued_at,
                we.expires_at AS latest_enrollment_expires_at
            FROM worker_node n
            JOIN worker_group g ON g.id = n.group_id
            LEFT JOIN worker_enrollment we
              ON we.id = (
                    SELECT inner_we.id
                    FROM worker_enrollment inner_we
                    WHERE inner_we.worker_node_id = n.id
                    ORDER BY inner_we.id DESC
                    LIMIT 1
                )
            ORDER BY g.name ASC, n.display_name ASC, n.id ASC
            """
        )
        for row in rows:
            row["supported_executor_keys_json"] = self._decode_json(row.get("supported_executor_keys_json")) or []
            row["capabilities_json"] = self._decode_json(row.get("capabilities_json")) or {}
            row["runtime_state_json"] = self._decode_json(row.get("runtime_state_json")) or {}
        return rows

    def insert_enrollment(self, payload: dict):
        self._db.execute_update(
            """
            INSERT INTO worker_enrollment (
                worker_node_id, token_hash, status, issued_by, issued_at, expires_at
            )
            VALUES (
                %(worker_node_id)s, %(token_hash)s, %(status)s, %(issued_by)s, %(issued_at)s, %(expires_at)s
            )
            """,
            payload,
        )
        return self._db.execute_query(
            """
            SELECT *
            FROM worker_enrollment
            WHERE worker_node_id = %(worker_node_id)s
            ORDER BY id DESC
            LIMIT 1
            """,
            {"worker_node_id": payload["worker_node_id"]},
            fetch_one=True,
        )

    def revoke_worker_node(self, worker_node_id: int, revoked_at: datetime):
        self._db.execute_update(
            """
            UPDATE worker_node
            SET status = 'revoked',
                updated_at = %(revoked_at)s
            WHERE id = %(worker_node_id)s
            """,
            {"worker_node_id": worker_node_id, "revoked_at": revoked_at},
        )
        self._db.execute_update(
            """
            UPDATE worker_auth_token
            SET status = 'revoked',
                revoked_at = %(revoked_at)s
            WHERE worker_node_id = %(worker_node_id)s
              AND status = 'active'
            """,
            {"worker_node_id": worker_node_id, "revoked_at": revoked_at},
        )

    def rotate_worker_token(self, worker_node_id: int, token_hash: str, issued_at: datetime):
        self._db.execute_update(
            """
            UPDATE worker_auth_token
            SET status = 'rotated',
                revoked_at = %(issued_at)s
            WHERE worker_node_id = %(worker_node_id)s
              AND status = 'active'
            """,
            {"worker_node_id": worker_node_id, "issued_at": issued_at},
        )
        self._db.execute_update(
            """
            INSERT INTO worker_auth_token (worker_node_id, token_hash, status, issued_at)
            VALUES (%(worker_node_id)s, %(token_hash)s, 'active', %(issued_at)s)
            """,
            {"worker_node_id": worker_node_id, "token_hash": token_hash, "issued_at": issued_at},
        )

    def get_worker_node(self, worker_node_id: int):
        row = self._db.execute_query(
            """
            SELECT *
            FROM worker_node
            WHERE id = %(worker_node_id)s
            LIMIT 1
            """,
            {"worker_node_id": worker_node_id},
            fetch_one=True,
        )
        if row:
            row["supported_executor_keys_json"] = self._decode_json(row.get("supported_executor_keys_json")) or []
            row["capabilities_json"] = self._decode_json(row.get("capabilities_json")) or {}
            row["runtime_state_json"] = self._decode_json(row.get("runtime_state_json")) or {}
        return row

    def consume_enrollment(self, enrollment_id: int, client_ip: str, consumed_at: datetime):
        self._db.execute_update(
            """
            UPDATE worker_enrollment
            SET status = 'consumed',
                consumed_at = %(consumed_at)s,
                consumed_from_ip = %(client_ip)s
            WHERE id = %(enrollment_id)s
            """,
            {
                "enrollment_id": enrollment_id,
                "consumed_at": consumed_at,
                "client_ip": client_ip,
            },
        )

    def activate_worker_node(self, worker_node_id: int, payload: dict, activated_at: datetime, client_ip: str):
        self._db.execute_update(
            """
            UPDATE worker_node
            SET hostname = %(hostname)s,
                machine_fingerprint = %(machine_fingerprint)s,
                agent_version = %(agent_version)s,
                os_type = %(os_type)s,
                os_version = %(os_version)s,
                scratch_root = %(scratch_root)s,
                workspace_share = %(workspace_share)s,
                max_concurrent_tasks = %(max_concurrent_tasks)s,
                status = 'active',
                last_seen_at = %(activated_at)s,
                last_heartbeat_at = %(activated_at)s,
                last_ip = %(client_ip)s,
                supported_executor_keys_json = %(supported_executor_keys_json)s,
                capabilities_json = %(capabilities_json)s
            WHERE id = %(worker_node_id)s
            """,
            {
                "worker_node_id": worker_node_id,
                "hostname": payload["hostname"],
                "machine_fingerprint": payload["machine_fingerprint"],
                "agent_version": payload["agent_version"],
                "os_type": payload["os_type"],
                "os_version": payload["os_version"],
                "scratch_root": payload["scratch_root"],
                "workspace_share": payload["workspace_share"],
                "max_concurrent_tasks": payload["max_concurrent_tasks"],
                "activated_at": activated_at,
                "client_ip": client_ip,
                "supported_executor_keys_json": self._encode_json(payload["supported_executor_keys"]),
                "capabilities_json": self._encode_json(payload["capabilities"]),
            },
        )
        return self.get_worker_node(worker_node_id)

    def issue_auth_token(self, worker_node_id: int, token_hash: str, issued_at: datetime):
        self._db.execute_update(
            """
            INSERT INTO worker_auth_token (worker_node_id, token_hash, status, issued_at)
            VALUES (%(worker_node_id)s, %(token_hash)s, 'active', %(issued_at)s)
            """,
            {
                "worker_node_id": worker_node_id,
                "token_hash": token_hash,
                "issued_at": issued_at,
            },
        )

    def get_auth_token_by_hash(self, token_hash: str):
        return self._db.execute_query(
            """
            SELECT *
            FROM worker_auth_token
            WHERE token_hash = %(token_hash)s
            LIMIT 1
            """,
            {"token_hash": token_hash},
            fetch_one=True,
        )

    def update_worker_heartbeat(self, worker_node_id: int, payload: dict, heartbeat_at: datetime, client_ip: str):
        self._db.execute_update(
            """
            UPDATE worker_node
            SET status = CASE WHEN status IN ('offline', 'pending_enrollment') THEN 'active' ELSE status END,
                last_seen_at = %(heartbeat_at)s,
                last_heartbeat_at = %(heartbeat_at)s,
                last_ip = %(client_ip)s,
                last_error = %(last_error)s,
                runtime_state_json = %(runtime_state_json)s
            WHERE id = %(worker_node_id)s
            """,
            {
                "worker_node_id": worker_node_id,
                "heartbeat_at": heartbeat_at,
                "client_ip": client_ip,
                "last_error": payload.get("last_error_summary") or "",
                "runtime_state_json": self._encode_json(
                    {
                        "running_task_ids": list(payload.get("running_task_ids") or []),
                        "occupied_slots": int(payload.get("occupied_slots") or 0),
                        "available_slots": int(payload.get("available_slots") or 0),
                        "software_inventory": dict(payload.get("software_inventory") or {}),
                    }
                ),
            },
        )
        return self.get_worker_node(worker_node_id)

    def count_worker_active_tasks(self, worker_node_id: int) -> int:
        row = self._db.execute_query(
            """
            SELECT COUNT(*) AS cnt
            FROM platform_task
            WHERE worker_node_id = %(worker_node_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            """,
            {"worker_node_id": worker_node_id},
            fetch_one=True,
        ) or {"cnt": 0}
        return int(row["cnt"])

    def claim_next_task_for_worker(
        self,
        worker_node_id: int,
        worker_group_id: int,
        supported_executor_keys: list[str],
        claimed_at: datetime,
    ):
        if not supported_executor_keys:
            return None

        conn = self._db.get_connection()
        cursor = None
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT runtime_state_json, capabilities_json
                FROM worker_node
                WHERE id = %s
                LIMIT 1
                """,
                (worker_node_id,),
            )
            worker_node = cursor.fetchone() or {}
            placeholders = ", ".join(["%s"] * len(supported_executor_keys))
            cursor.execute(
                f"""
                SELECT *
                FROM platform_task
                WHERE worker_group_id = %s
                  AND status IN ('queued', 'submitted')
                  AND executor_key IN ({placeholders})
                ORDER BY created_at ASC, id ASC
                FOR UPDATE
                """,
                [worker_group_id, *supported_executor_keys],
            )
            candidates = cursor.fetchall()
            for candidate in candidates:
                if not self._software_gate_allows_task(worker_node, candidate):
                    continue
                if not self._pool_has_capacity(cursor, candidate):
                    continue
                cursor.execute(
                    """
                    UPDATE platform_task
                    SET status = 'assigned',
                        worker_node_id = %s,
                        assigned_at = %s,
                        assigned_runtime_id = COALESCE(assigned_runtime_id, requested_runtime_id)
                    WHERE id = %s
                    """,
                    (worker_node_id, claimed_at, candidate["id"]),
                )
                cursor.execute(
                    """
                    UPDATE launch_queue
                    SET status = 'fulfilled',
                        assigned_app_id = COALESCE(assigned_app_id, requested_app_id),
                        fulfilled_at = %s
                    WHERE platform_task_id = %s
                      AND status = 'queued'
                    """,
                    (claimed_at, candidate["id"]),
                )
                conn.commit()
                candidate["status"] = "assigned"
                candidate["worker_node_id"] = worker_node_id
                candidate["assigned_at"] = claimed_at
                candidate["assigned_runtime_id"] = candidate.get("assigned_runtime_id") or candidate.get("requested_runtime_id")
                return candidate
            conn.commit()
            return None
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

    def get_task_for_worker(self, task_id: str, worker_node_id: int):
        return self._db.execute_query(
            """
            SELECT *
            FROM platform_task
            WHERE task_id = %(task_id)s
              AND worker_node_id = %(worker_node_id)s
            LIMIT 1
            """,
            {"task_id": task_id, "worker_node_id": worker_node_id},
            fetch_one=True,
        )

    def update_task_status_for_worker(self, task_id: str, worker_node_id: int, payload: dict, event_at: datetime):
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = %(status)s,
                scratch_path = %(scratch_path)s,
                external_task_id = %(external_task_id)s,
                started_at = CASE
                    WHEN %(status)s = 'running' AND started_at IS NULL THEN %(event_at)s
                    ELSE started_at
                END
            WHERE task_id = %(task_id)s
              AND worker_node_id = %(worker_node_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            """,
            {
                "task_id": task_id,
                "worker_node_id": worker_node_id,
                "status": payload.get("status"),
                "scratch_path": payload.get("scratch_path"),
                "external_task_id": payload.get("external_task_id"),
                "event_at": event_at,
            },
        )
        if updated <= 0:
            return None
        return self.get_task_for_worker(task_id, worker_node_id)

    def append_task_logs(self, task_id: str, worker_node_id: int, items: list[dict], event_at: datetime):
        task = self.get_task_for_worker(task_id, worker_node_id)
        if not task or str(task.get("status") or "") not in {'assigned', 'preparing', 'running', 'uploading'}:
            return 0
        accepted = 0
        for item in items:
            self._db.execute_update(
                """
                INSERT INTO platform_task_log (task_id, seq_no, level, message, created_at)
                VALUES (%(task_db_id)s, %(seq_no)s, %(level)s, %(message)s, %(created_at)s)
                ON DUPLICATE KEY UPDATE
                    level = VALUES(level),
                    message = VALUES(message)
                """,
                {
                    "task_db_id": task["id"],
                    "seq_no": item["seq_no"],
                    "level": item.get("level") or "info",
                    "message": item["message"],
                    "created_at": event_at,
                },
            )
            accepted += 1
        return accepted

    def complete_task_for_worker(self, task_id: str, worker_node_id: int, payload: dict, event_at: datetime):
        task = self.get_task_for_worker(task_id, worker_node_id)
        if not task or str(task.get("status") or "") not in {'assigned', 'preparing', 'running', 'uploading'}:
            return None
        self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'succeeded',
                result_summary_json = %(result_summary_json)s,
                ended_at = %(event_at)s
            WHERE id = %(task_db_id)s
            """,
            {
                "task_db_id": task["id"],
                "result_summary_json": self._encode_json(payload.get("result_summary") or {}),
                "event_at": event_at,
            },
        )
        for artifact in payload.get("artifacts") or []:
            self._db.execute_update(
                """
                INSERT INTO platform_task_artifact (
                    task_id, artifact_kind, display_name, relative_path,
                    minio_bucket, minio_object_key, external_url, size_bytes
                )
                VALUES (
                    %(task_db_id)s, %(artifact_kind)s, %(display_name)s, %(relative_path)s,
                    %(minio_bucket)s, %(minio_object_key)s, %(external_url)s, %(size_bytes)s
                )
                """,
                {
                    "task_db_id": task["id"],
                    "artifact_kind": artifact.get("artifact_kind"),
                    "display_name": artifact.get("display_name"),
                    "relative_path": artifact.get("relative_path"),
                    "minio_bucket": artifact.get("minio_bucket"),
                    "minio_object_key": artifact.get("minio_object_key"),
                    "external_url": artifact.get("external_url"),
                    "size_bytes": artifact.get("size_bytes"),
                },
            )
        return self.get_task_for_worker(task_id, worker_node_id)

    def fail_task_for_worker(self, task_id: str, worker_node_id: int, payload: dict, event_at: datetime):
        task = self.get_task_for_worker(task_id, worker_node_id)
        if not task or str(task.get("status") or "") not in {'assigned', 'preparing', 'running', 'uploading'}:
            return None
        self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'failed',
                result_summary_json = %(result_summary_json)s,
                ended_at = %(event_at)s
            WHERE id = %(task_db_id)s
            """,
            {
                "task_db_id": task["id"],
                "result_summary_json": self._encode_json({"error": payload.get("error_message")}),
                "event_at": event_at,
            },
        )
        return self.get_task_for_worker(task_id, worker_node_id)

    def list_cancel_requested_task_ids(self, worker_node_id: int):
        rows = self._db.execute_query(
            """
            SELECT task_id
            FROM platform_task
            WHERE worker_node_id = %(worker_node_id)s
              AND cancel_requested = 1
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            ORDER BY id ASC
            """,
            {"worker_node_id": worker_node_id},
        )
        return [str(row["task_id"]) for row in rows]

    def list_stalled_assigned_tasks(self, assigned_deadline: datetime):
        rows = self._db.execute_query(
            """
            SELECT t.*, wn.last_heartbeat_at, wn.runtime_state_json, wn.last_error, wn.status AS worker_status
            FROM platform_task t
            JOIN worker_node wn ON wn.id = t.worker_node_id
            WHERE t.status = 'assigned'
              AND t.assigned_at IS NOT NULL
              AND t.assigned_at < %(assigned_deadline)s
              AND wn.status = 'active'
              AND wn.last_heartbeat_at IS NOT NULL
              AND wn.last_heartbeat_at > t.assigned_at
            ORDER BY t.assigned_at ASC, t.id ASC
            """,
            {"assigned_deadline": assigned_deadline},
        )
        for row in rows:
            row["runtime_state_json"] = self._decode_json(row.get("runtime_state_json")) or {}
        return rows

    def list_stale_worker_nodes(self, heartbeat_deadline: datetime):
        return self._db.execute_query(
            """
            SELECT *
            FROM worker_node
            WHERE status = 'active'
              AND last_heartbeat_at IS NOT NULL
              AND last_heartbeat_at < %(heartbeat_deadline)s
            ORDER BY id ASC
            """,
            {"heartbeat_deadline": heartbeat_deadline},
        )

    def mark_worker_offline(self, worker_node_id: int, offline_at: datetime):
        self._db.execute_update(
            """
            UPDATE worker_node
            SET status = 'offline',
                updated_at = %(offline_at)s
            WHERE id = %(worker_node_id)s
              AND status = 'active'
            """,
            {"worker_node_id": worker_node_id, "offline_at": offline_at},
        )

    def list_worker_tasks_for_recovery(self, worker_node_id: int):
        return self._db.execute_query(
            """
            SELECT *
            FROM platform_task
            WHERE worker_node_id = %(worker_node_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            ORDER BY id ASC
            """,
            {"worker_node_id": worker_node_id},
        )

    def requeue_task_after_worker_loss(self, task_id: str, worker_node_id: int):
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'queued',
                worker_node_id = NULL,
                assigned_at = NULL
            WHERE task_id = %(task_id)s
              AND worker_node_id = %(worker_node_id)s
              AND status = 'assigned'
            """,
            {"task_id": task_id, "worker_node_id": worker_node_id},
        )
        if updated <= 0:
            return None
        self._db.execute_update(
            """
            UPDATE launch_queue
            SET status = 'queued',
                fulfilled_at = NULL,
                assigned_app_id = NULL,
                cancel_reason = NULL,
                cancelled_at = NULL
            WHERE platform_task_id IN (
                SELECT id FROM platform_task WHERE task_id = %(task_id)s
            )
            """,
            {"task_id": task_id},
        )
        return self._db.execute_query(
            """
            SELECT *
            FROM platform_task
            WHERE task_id = %(task_id)s
            LIMIT 1
            """,
            {"task_id": task_id},
            fetch_one=True,
        )

    def fail_stalled_assigned_task(self, task_id: str, worker_node_id: int, event_at: datetime, reason: str):
        task = self.get_task_for_worker(task_id, worker_node_id)
        if not task or str(task.get("status") or "") != 'assigned':
            return None
        normalized_reason = str(reason or 'worker_assignment_stalled')[:500]
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'failed',
                ended_at = %(event_at)s,
                result_summary_json = %(result_summary_json)s
            WHERE task_id = %(task_id)s
              AND worker_node_id = %(worker_node_id)s
              AND status = 'assigned'
            """,
            {
                "task_id": task_id,
                "worker_node_id": worker_node_id,
                "event_at": event_at,
                "result_summary_json": self._encode_json({"error": normalized_reason}),
            },
        )
        if updated <= 0:
            return None
        seq_row = self._db.execute_query(
            """
            SELECT COALESCE(MAX(seq_no), 0) + 1 AS next_seq
            FROM platform_task_log
            WHERE task_id = %(task_db_id)s
            """,
            {"task_db_id": task["id"]},
            fetch_one=True,
        ) or {"next_seq": 1}
        self._db.execute_update(
            """
            INSERT INTO platform_task_log (task_id, seq_no, level, message, created_at)
            VALUES (%(task_db_id)s, %(seq_no)s, %(level)s, %(message)s, %(created_at)s)
            """,
            {
                "task_db_id": task["id"],
                "seq_no": int(seq_row.get("next_seq") or 1),
                "level": 'error',
                "message": f"worker_assignment_stalled: {normalized_reason}",
                "created_at": event_at,
            },
        )
        return self.get_task_for_worker(task_id, worker_node_id)

    def fail_task_after_worker_loss(self, task_id: str, worker_node_id: int, event_at: datetime, reason: str):
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'failed',
                ended_at = %(event_at)s,
                result_summary_json = %(result_summary_json)s
            WHERE task_id = %(task_id)s
              AND worker_node_id = %(worker_node_id)s
              AND status IN ('preparing', 'running', 'uploading')
            """,
            {
                "task_id": task_id,
                "worker_node_id": worker_node_id,
                "event_at": event_at,
                "result_summary_json": self._encode_json({"error": reason}),
            },
        )
        if updated <= 0:
            return None
        self._db.execute_update(
            """
            UPDATE launch_queue
            SET status = 'cancelled',
                cancel_reason = %(reason)s,
                cancelled_at = %(event_at)s
            WHERE platform_task_id IN (
                SELECT id FROM platform_task WHERE task_id = %(task_id)s
            )
            """,
            {"task_id": task_id, "reason": reason[:100], "event_at": event_at},
        )
        return self._db.execute_query(
            """
            SELECT *
            FROM platform_task
            WHERE task_id = %(task_id)s
            LIMIT 1
            """,
            {"task_id": task_id},
            fetch_one=True,
        )

    def _pool_has_capacity(self, cursor, candidate: dict) -> bool:
        pool_id = candidate.get("resource_pool_id")
        if pool_id is None:
            return True
        cursor.execute(
            """
            SELECT max_concurrent
            FROM resource_pool
            WHERE id = %s AND is_active = 1
            LIMIT 1
            """,
            (pool_id,),
        )
        pool_row = cursor.fetchone()
        if not pool_row:
            return False

        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM active_session
            WHERE pool_id = %s
              AND status IN ('active', 'reclaim_pending')
            """,
            (pool_id,),
        )
        session_count = int((cursor.fetchone() or {}).get("cnt") or 0)

        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM platform_task
            WHERE resource_pool_id = %s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
              AND id <> %s
            """,
            (pool_id, candidate["id"]),
        )
        task_count = int((cursor.fetchone() or {}).get("cnt") or 0)
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM launch_queue
            WHERE pool_id = %s
              AND status IN ('ready', 'launching')
              AND (request_mode = 'gui' OR platform_task_id IS NULL)
            """,
            (pool_id,),
        )
        gui_reserved_count = int((cursor.fetchone() or {}).get("cnt") or 0)
        return session_count + task_count + gui_reserved_count < int(pool_row["max_concurrent"])
