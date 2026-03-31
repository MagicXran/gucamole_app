import argparse
import sys
from pathlib import Path

import mysql.connector

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.database import CONFIG

REQUIRED_TABLES = [
    "resource_pool",
    "launch_queue",
    "active_session",
    "portal_user",
    "remote_app",
]

REQUIRED_COLUMNS = {
    "remote_app": {"pool_id", "member_max_concurrent"},
    "active_session": {"pool_id", "queue_id", "last_activity_at", "reclaim_reason"},
    "portal_user": {"quota_bytes"},
}


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
        SELECT TABLE_NAME, COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        """
    )
    existing_columns = {(row[0], row[1]) for row in cursor.fetchall()}

    problems = []
    for table_name in REQUIRED_TABLES:
        if table_name not in existing_tables:
            problems.append(f"missing table: {table_name}")

    for table_name, columns in REQUIRED_COLUMNS.items():
        for column_name in sorted(columns):
            if (table_name, column_name) not in existing_columns:
                problems.append(f"missing column: {table_name}.{column_name}")

    return problems


def _connect_live():
    db_cfg = CONFIG["database"]
    return mysql.connector.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        database=db_cfg["database"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        charset="utf8mb4",
        use_unicode=True,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify portal schema completeness")
    parser.add_argument(
        "--dsn",
        default="live",
        choices=["live"],
        help="schema target to verify",
    )
    _ = parser.parse_args(argv)

    conn = _connect_live()
    try:
        cursor = conn.cursor()
        problems = verify_schema(cursor)
    finally:
        conn.close()

    if problems:
        for problem in problems:
            print(problem)
        return 1

    print("schema ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
