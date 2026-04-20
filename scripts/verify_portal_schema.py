import argparse
import sys
from pathlib import Path

import mysql.connector

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_TABLES = [
    "resource_pool",
    "launch_queue",
    "active_session",
    "portal_user",
    "remote_app",
    "catalog_app",
    "app_binding",
    "remote_app_script_profile",
    "worker_group",
    "worker_node",
    "worker_enrollment",
    "worker_auth_token",
    "platform_task",
    "platform_task_log",
    "platform_task_artifact",
    "app_attachment",
    "booking_register",
    "portal_comment",
    "sdk_package",
    "sdk_version",
    "sdk_asset",
    "simulation_case",
    "simulation_case_source",
    "simulation_case_package",
    "simulation_case_asset",
]

REQUIRED_COLUMNS = {
    "remote_app": {"app_kind", "pool_id", "member_max_concurrent", "disable_download", "disable_upload"},
    "launch_queue": {"request_mode", "platform_task_id"},
    "active_session": {"pool_id", "queue_id", "last_activity_at", "reclaim_reason"},
    "portal_user": {"quota_bytes", "department"},
    "app_binding": {"binding_kind", "worker_group_id", "runtime_config_json"},
    "remote_app_script_profile": {"executor_key", "scratch_root"},
    "worker_group": {"group_key", "max_claim_batch"},
    "worker_node": {"agent_id", "expected_hostname", "workspace_share", "runtime_state_json"},
    "worker_enrollment": {"token_hash", "status", "expires_at"},
    "worker_auth_token": {"token_hash", "status", "issued_at"},
    "platform_task": {"task_id", "task_kind", "executor_key", "status", "params_json"},
    "platform_task_log": {"task_id", "seq_no", "message"},
    "platform_task_artifact": {"task_id", "artifact_kind", "display_name"},
    "app_attachment": {"pool_id", "attachment_kind", "url", "is_active"},
    "booking_register": {"user_id", "app_name", "scheduled_for", "purpose", "status"},
    "portal_comment": {"target_type", "target_id", "user_id", "content"},
    "sdk_package": {"package_kind", "name", "is_active"},
    "sdk_version": {"package_id", "version", "is_active"},
    "sdk_asset": {"version_id", "download_url", "is_active"},
    "simulation_case": {"case_uid", "title", "visibility", "status", "published_by_user_id"},
    "simulation_case_package": {"case_id", "package_root", "archive_path", "asset_count"},
    "simulation_case_asset": {"case_id", "asset_kind", "display_name", "package_relative_path"},
}

REQUIRED_NULL_DEFAULT_COLUMNS = {
    ("remote_app", "disable_download"),
    ("remote_app", "disable_upload"),
}
SCHEMA_CONNECT_TIMEOUT_SECONDS = 5


def verify_schema(cursor) -> list[str]:
    cursor.execute(
        """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
        """
    )
    existing_tables = {row[0] for row in cursor.fetchall()}

    cursor.execute(
        """
        SELECT TABLE_NAME, COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        """
    )
    existing_columns = set()
    column_attrs = {}
    for row in cursor.fetchall():
        table_name = row[0]
        column_name = row[1]
        existing_columns.add((table_name, column_name))
        if len(row) >= 4:
            column_attrs[(table_name, column_name)] = {
                "is_nullable": str(row[2]).upper() == "YES",
                "column_default": row[3],
            }

    problems = []
    for table_name in REQUIRED_TABLES:
        if table_name not in existing_tables:
            problems.append(f"missing table: {table_name}")

    for table_name, columns in REQUIRED_COLUMNS.items():
        for column_name in sorted(columns):
            if (table_name, column_name) not in existing_columns:
                problems.append(f"missing column: {table_name}.{column_name}")

    for table_name, column_name in sorted(REQUIRED_NULL_DEFAULT_COLUMNS):
        attrs = column_attrs.get((table_name, column_name))
        if not attrs:
            continue
        if not attrs["is_nullable"]:
            problems.append(f"column should be nullable: {table_name}.{column_name}")
        if attrs["column_default"] is not None:
            problems.append(f"column default should be NULL: {table_name}.{column_name}")

    return problems


def _connect_live():
    from backend.database import CONFIG

    db_cfg = CONFIG["database"]
    return mysql.connector.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        database=db_cfg["database"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        connection_timeout=SCHEMA_CONNECT_TIMEOUT_SECONDS,
        charset="utf8mb4",
        use_unicode=True,
    )


def check_live_schema(connect_fn=None) -> dict:
    connect = connect_fn or _connect_live
    try:
        conn = connect()
        try:
            cursor = conn.cursor()
            problems = verify_schema(cursor)
        finally:
            conn.close()
    except Exception:
        return {
            "ok": False,
            "status": "degraded",
            "checks": {
                "schema": {
                    "status": "error",
                    "error_code": "schema_check_failed",
                    "problems": ["schema check failed"],
                }
            },
        }

    if problems:
        return {
            "ok": False,
            "status": "degraded",
            "checks": {
                "schema": {
                    "status": "fail",
                    "error_code": "schema_invalid",
                    "problems": problems,
                }
            },
        }

    return {
        "ok": True,
        "status": "ready",
        "checks": {
            "schema": {
                "status": "ok",
                "error_code": "",
                "problems": [],
            }
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify portal schema completeness")
    parser.add_argument(
        "--dsn",
        default="live",
        choices=["live"],
        help="schema target to verify",
    )
    _ = parser.parse_args(argv)

    result = check_live_schema()
    problems = result["checks"]["schema"]["problems"]

    if not result["ok"]:
        for problem in problems:
            print(problem)
        return 1

    print("schema ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
