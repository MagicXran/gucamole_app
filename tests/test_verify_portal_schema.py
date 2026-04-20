import json
import sys
import types
from pathlib import Path

import scripts.verify_portal_schema as schema_verifier
from scripts.verify_portal_schema import REQUIRED_COLUMNS, REQUIRED_TABLES, check_live_schema, verify_schema


class FakeCursor:
    def __init__(self, tables, columns):
        self.tables = list(tables)
        self.columns = list(columns)
        self._mode = None

    def execute(self, query: str):
        if "FROM information_schema.TABLES" in query:
            self._mode = "tables"
        elif "FROM information_schema.COLUMNS" in query:
            self._mode = "columns"
        else:
            raise AssertionError(f"Unexpected query: {query}")

    def fetchall(self):
        if self._mode == "tables":
            return [(name,) for name in self.tables]
        if self._mode == "columns":
            return list(self.columns)
        raise AssertionError("fetchall called before execute")


def test_verify_schema_reports_no_issues_when_required_objects_exist():
    columns = []
    for table_name, cols in REQUIRED_COLUMNS.items():
        for col in cols:
            if (table_name, col) in {
                ("remote_app", "disable_download"),
                ("remote_app", "disable_upload"),
            }:
                columns.append((table_name, col, "YES", None))
            else:
                columns.append((table_name, col))
    cursor = FakeCursor(
        tables=REQUIRED_TABLES,
        columns=columns,
    )

    problems = verify_schema(cursor)

    assert problems == []


def test_verify_schema_reports_missing_tables_and_columns():
    cursor = FakeCursor(
        tables=["portal_user", "remote_app"],
        columns=[
            ("portal_user", "quota_bytes"),
            ("remote_app", "pool_id"),
        ],
    )

    problems = verify_schema(cursor)

    assert "missing table: resource_pool" in problems
    assert "missing table: launch_queue" in problems
    assert "missing table: worker_group" in problems
    assert "missing table: worker_node" in problems
    assert "missing table: remote_app_script_profile" in problems
    assert "missing table: app_binding" in problems
    assert "missing table: app_attachment" in problems
    assert "missing table: booking_register" in problems
    assert "missing table: portal_comment" in problems
    assert "missing table: sdk_package" in problems
    assert "missing table: sdk_version" in problems
    assert "missing table: sdk_asset" in problems
    assert "missing table: simulation_case" in problems
    assert "missing table: simulation_case_source" in problems
    assert "missing table: simulation_case_package" in problems
    assert "missing table: simulation_case_asset" in problems
    assert "missing column: remote_app.disable_download" in problems
    assert "missing column: remote_app.disable_upload" in problems
    assert "missing column: remote_app.member_max_concurrent" in problems
    assert "missing column: remote_app.app_kind" in problems
    assert "missing column: portal_user.department" in problems
    assert "missing column: active_session.pool_id" in problems
    assert "missing column: active_session.reclaim_reason" in problems
    assert "missing column: launch_queue.request_mode" in problems
    assert "missing column: launch_queue.platform_task_id" in problems
    assert "missing column: app_attachment.attachment_kind" in problems
    assert "missing column: booking_register.scheduled_for" in problems
    assert "missing column: portal_comment.content" in problems
    assert "missing column: sdk_package.package_kind" in problems
    assert "missing column: sdk_version.version" in problems
    assert "missing column: sdk_asset.download_url" in problems
    assert "missing column: simulation_case.case_uid" in problems
    assert "missing column: simulation_case_package.package_root" in problems
    assert "missing column: simulation_case_asset.package_relative_path" in problems


def test_verify_schema_reports_nullable_default_violations():
    columns = []
    for table_name, cols in REQUIRED_COLUMNS.items():
        for col in cols:
            if (table_name, col) == ("remote_app", "disable_download"):
                columns.append((table_name, col, "NO", 0))
            elif (table_name, col) == ("remote_app", "disable_upload"):
                columns.append((table_name, col, "YES", 0))
            else:
                columns.append((table_name, col))

    cursor = FakeCursor(
        tables=REQUIRED_TABLES,
        columns=columns,
    )

    problems = verify_schema(cursor)

    assert "column should be nullable: remote_app.disable_download" in problems
    assert "column default should be NULL: remote_app.disable_download" in problems
    assert "column default should be NULL: remote_app.disable_upload" in problems


def test_check_live_schema_redacts_connection_error_details():
    result = check_live_schema(connect_fn=lambda: (_ for _ in ()).throw(RuntimeError("root password leaked")))

    assert result["ok"] is False
    assert result["status"] == "degraded"
    assert result["checks"]["schema"]["status"] == "error"
    assert result["checks"]["schema"]["error_code"] == "schema_check_failed"
    assert result["checks"]["schema"]["problems"] == ["schema check failed"]
    assert "password" not in json.dumps(result, ensure_ascii=False)
    assert "root" not in json.dumps(result, ensure_ascii=False)


def test_connect_live_uses_short_connection_timeout(monkeypatch):
    fake_database = types.ModuleType("backend.database")
    fake_database.CONFIG = {
        "database": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "portal_db",
            "user": "portal_user",
            "password": "portal_password",
        }
    }
    captured = {}

    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    monkeypatch.setattr(
        schema_verifier.mysql.connector,
        "connect",
        lambda **kwargs: captured.setdefault("kwargs", kwargs) or object(),
    )

    schema_verifier._connect_live()

    assert captured["kwargs"]["connection_timeout"] == 5


def test_init_sql_creates_worker_group_before_app_binding():
    repo_root = Path(__file__).resolve().parents[1]

    for sql_path in (
        repo_root / "database" / "init.sql",
        repo_root / "deploy" / "initdb" / "01-portal-init.sql",
    ):
        sql_text = sql_path.read_text(encoding="utf-8")
        worker_group_index = sql_text.index("CREATE TABLE IF NOT EXISTS worker_group")
        app_binding_index = sql_text.index("CREATE TABLE IF NOT EXISTS app_binding")

        assert worker_group_index < app_binding_index, f"{sql_path} 里 app_binding 先于 worker_group，冷启动会炸"


def test_portal_ui_support_migration_defines_required_schema():
    sql = Path("database/migrate_portal_ui_support.sql").read_text(encoding="utf-8")

    assert "ALTER TABLE portal_user ADD COLUMN department" in sql
    assert "ALTER TABLE remote_app ADD COLUMN app_kind" in sql
    assert "CREATE TABLE IF NOT EXISTS app_attachment" in sql
    assert "CREATE TABLE IF NOT EXISTS booking_register" in sql
    assert "CREATE TABLE IF NOT EXISTS portal_comment" in sql
    assert "CREATE TABLE IF NOT EXISTS sdk_package" in sql
    assert "CREATE TABLE IF NOT EXISTS sdk_version" in sql
    assert "CREATE TABLE IF NOT EXISTS sdk_asset" in sql
    assert "CREATE TABLE IF NOT EXISTS simulation_case" in sql
    assert "INDEX idx_case_source_case (case_id)" in sql
    assert "UNIQUE KEY uk_case_source_case" not in sql
