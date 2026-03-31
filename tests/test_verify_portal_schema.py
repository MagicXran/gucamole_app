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
            return [(table_name, column_name) for table_name, column_name in self.columns]
        raise AssertionError("fetchall called before execute")


def test_verify_schema_reports_no_issues_when_required_objects_exist():
    cursor = FakeCursor(
        tables=REQUIRED_TABLES,
        columns=[item for table_name, cols in REQUIRED_COLUMNS.items() for item in [(table_name, col) for col in cols]],
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
    assert "missing column: remote_app.member_max_concurrent" in problems
    assert "missing column: active_session.pool_id" in problems
    assert "missing column: active_session.reclaim_reason" in problems
