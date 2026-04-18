"""
MySQL-backed task repository for script-mode jobs.
"""

from __future__ import annotations

import json


class MySQLTaskRepository:
    def __init__(self, db):
        self._db = db

    @staticmethod
    def _decode_json(value):
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    def get_script_launch_target(self, user_id: int, requested_runtime_id: int):
        row = self._db.execute_query(
            """
            SELECT
                a.id AS requested_runtime_id,
                a.pool_id,
                sp.executor_key,
                ca.id AS app_id,
                ab.id AS binding_id,
                ab.worker_group_id,
                ab.runtime_config_json
            FROM remote_app a
            JOIN remote_app_acl acl
              ON acl.app_id = a.id
             AND acl.user_id = %(user_id)s
            JOIN resource_pool p
              ON p.id = a.pool_id
             AND p.is_active = 1
            JOIN remote_app_script_profile sp
              ON sp.remote_app_id = a.id
             AND sp.is_enabled = 1
            LEFT JOIN app_binding ab
              ON ab.remote_app_id = a.id
             AND ab.binding_kind = 'worker_script'
             AND ab.is_enabled = 1
            LEFT JOIN catalog_app ca
              ON ca.id = ab.app_id
            WHERE a.id = %(requested_runtime_id)s
              AND a.is_active = 1
              AND ab.worker_group_id IS NOT NULL
            LIMIT 1
            """,
            {"user_id": user_id, "requested_runtime_id": requested_runtime_id},
            fetch_one=True,
        )
        if row:
            row["runtime_config_json"] = self._decode_json(row.get("runtime_config_json"))
        return row

    def list_worker_dispatch_nodes(self, worker_group_id: int):
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

    def create_platform_task(self, payload: dict):
        self._db.execute_update(
            """
            INSERT INTO platform_task (
                task_id, user_id, app_id, binding_id, task_kind, executor_key,
                resource_pool_id, worker_group_id, worker_node_id,
                requested_runtime_id, assigned_runtime_id,
                entry_path, workspace_path, input_snapshot_path, scratch_path,
                status, external_task_id, cancel_requested,
                params_json, result_summary_json
            )
            VALUES (
                %(task_id)s, %(user_id)s, %(app_id)s, %(binding_id)s, %(task_kind)s, %(executor_key)s,
                %(resource_pool_id)s, %(worker_group_id)s, %(worker_node_id)s,
                %(requested_runtime_id)s, %(assigned_runtime_id)s,
                %(entry_path)s, %(workspace_path)s, %(input_snapshot_path)s, %(scratch_path)s,
                %(status)s, %(external_task_id)s, %(cancel_requested)s,
                %(params_json)s, %(result_summary_json)s
            )
            """,
            {
                **payload,
                "params_json": json.dumps(payload["params_json"], ensure_ascii=False) if payload.get("params_json") is not None else None,
                "result_summary_json": json.dumps(payload["result_summary_json"], ensure_ascii=False) if payload.get("result_summary_json") is not None else None,
            },
        )
        return self.get_task_by_task_id_for_user(payload["task_id"], payload["user_id"])

    def insert_task_queue(self, payload: dict):
        self._db.execute_update(
            """
            INSERT INTO launch_queue (
                pool_id, user_id, requested_app_id, request_mode, platform_task_id, status
            )
            VALUES (
                %(pool_id)s, %(user_id)s, %(requested_app_id)s, %(request_mode)s, %(platform_task_id)s, %(status)s
            )
            """,
            payload,
        )

    def get_task_by_task_id_for_user(self, task_id: str, user_id: int):
        row = self._db.execute_query(
            """
            SELECT *
            FROM platform_task
            WHERE task_id = %(task_id)s
              AND user_id = %(user_id)s
            LIMIT 1
            """,
            {"task_id": task_id, "user_id": user_id},
            fetch_one=True,
        )
        if row:
            row["params_json"] = self._decode_json(row.get("params_json"))
            row["result_summary_json"] = self._decode_json(row.get("result_summary_json"))
        return row

    def list_tasks_for_user(self, user_id: int):
        rows = self._db.execute_query(
            """
            SELECT task_id, status, task_kind, executor_key, entry_path, created_at, assigned_at, started_at, ended_at
            FROM platform_task
            WHERE user_id = %(user_id)s
            ORDER BY id DESC
            """,
            {"user_id": user_id},
        )
        for row in rows:
            for key in ("created_at", "assigned_at", "started_at", "ended_at"):
                if row.get(key) is not None:
                    row[key] = str(row[key])
        return rows

    def list_task_logs(self, task_db_id: int):
        return self._db.execute_query(
            """
            SELECT seq_no, level, message, created_at
            FROM platform_task_log
            WHERE task_id = %(task_db_id)s
            ORDER BY seq_no ASC, id ASC
            """,
            {"task_db_id": task_db_id},
        )

    def list_task_artifacts(self, task_db_id: int):
        return self._db.execute_query(
            """
            SELECT artifact_kind, display_name, relative_path, minio_bucket, minio_object_key, external_url, size_bytes, created_at
            FROM platform_task_artifact
            WHERE task_id = %(task_db_id)s
            ORDER BY id ASC
            """,
            {"task_db_id": task_db_id},
        )

    def cancel_queued_task(self, task_id: str, user_id: int):
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET status = 'cancelled',
                cancel_requested = 0,
                ended_at = NOW()
            WHERE task_id = %(task_id)s
              AND user_id = %(user_id)s
              AND status IN ('queued', 'submitted')
            """,
            {"task_id": task_id, "user_id": user_id},
        )
        if updated <= 0:
            return None
        task = self.get_task_by_task_id_for_user(task_id, user_id)
        if task:
            self._db.execute_update(
                """
                UPDATE launch_queue
                SET status = 'cancelled',
                    cancel_reason = 'user',
                    cancelled_at = NOW()
                WHERE platform_task_id = %(task_db_id)s
                  AND user_id = %(user_id)s
                  AND status IN ('queued', 'ready', 'launching')
                """,
                {"task_db_id": task["id"], "user_id": user_id},
            )
        return task

    def request_cancel_active_task(self, task_id: str, user_id: int):
        updated = self._db.execute_update(
            """
            UPDATE platform_task
            SET cancel_requested = 1
            WHERE task_id = %(task_id)s
              AND user_id = %(user_id)s
              AND status IN ('assigned', 'preparing', 'running', 'uploading')
            """,
            {"task_id": task_id, "user_id": user_id},
        )
        if updated <= 0:
            return None
        return self.get_task_by_task_id_for_user(task_id, user_id)
