from pathlib import Path

from scripts.verify_portal_schema import REQUIRED_COLUMNS, REQUIRED_TABLES, verify_schema


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
    assert "missing column: remote_app.disable_download" in problems
    assert "missing column: remote_app.disable_upload" in problems
    assert "missing column: remote_app.member_max_concurrent" in problems
    assert "missing column: active_session.pool_id" in problems
    assert "missing column: active_session.reclaim_reason" in problems
    assert "missing column: launch_queue.request_mode" in problems
    assert "missing column: launch_queue.platform_task_id" in problems


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
