import json
import zipfile
from pathlib import Path

import pytest


class FakeCaseDb:
    def __init__(self, *, tasks=None, artifacts=None):
        self.tasks = [dict(row) for row in (tasks or [])]
        self.artifacts = [dict(row) for row in (artifacts or [])]
        self.tables = {
            "simulation_case": [],
            "simulation_case_source": [],
            "simulation_case_asset": [],
            "simulation_case_package": [],
        }
        self.last_insert_id = 0

    class _Transaction:
        def __init__(self, owner):
            self.owner = owner
            self.conn = object()

        def __enter__(self):
            return self.conn

        def __exit__(self, exc_type, exc, tb):
            return False

    def transaction(self):
        return self._Transaction(self)

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        params = params or {}
        if "FROM platform_task" in query and "task_id = %(task_id)s" in query:
            for row in self.tasks:
                if row["task_id"] == params["task_id"]:
                    return dict(row) if fetch_one else [dict(row)]
            return None if fetch_one else []

        if "FROM platform_task_artifact" in query:
            rows = [
                dict(row)
                for row in self.artifacts
                if row["task_id"] == params["task_db_id"]
            ]
            return rows[0] if fetch_one and rows else rows

        if "LAST_INSERT_ID()" in query:
            return {"id": self.last_insert_id} if fetch_one else [{"id": self.last_insert_id}]

        raise AssertionError(f"unexpected query: {query}")

    def execute_update(self, query, params=None, conn=None):
        params = dict(params or {})
        for table_name in sorted(self.tables, key=len, reverse=True):
            if f"INSERT INTO {table_name} " in query:
                self.last_insert_id += 1
                self.tables[table_name].append({"id": self.last_insert_id, **params})
                return 1
        raise AssertionError(f"unexpected update: {query}")


def _json_dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def test_publish_rejects_non_succeeded_task_without_public_records(tmp_path):
    from backend.case_center_service import CaseCenterService, CaseCenterServiceError

    drive_root = tmp_path / "drive"
    private_root = drive_root / "portal_u7"
    output_file = private_root / "Output" / "task_failed" / "result.txt"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("bad\n", encoding="utf-8")
    db = FakeCaseDb(
        tasks=[
            {
                "id": 12,
                "task_id": "task_failed",
                "user_id": 7,
                "app_id": 5,
                "status": "failed",
                "result_summary_json": None,
            }
        ],
        artifacts=[
            {
                "id": 21,
                "task_id": 12,
                "artifact_kind": "workspace_output",
                "display_name": "result.txt",
                "relative_path": "Output/task_failed/result.txt",
                "size_bytes": 4,
            }
        ],
    )
    service = CaseCenterService(db=db, drive_root=drive_root)

    with pytest.raises(CaseCenterServiceError) as exc:
        service.publish_case_from_task(
            task_id="task_failed",
            publisher_user_id=7,
            title="失败任务不该公开",
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "task_not_publishable"
    assert all(not rows for rows in db.tables.values())
    assert not (drive_root / "_public_case_packages").exists()


def test_publish_rejects_non_owner_publisher(tmp_path):
    from backend.case_center_service import CaseCenterService, CaseCenterServiceError

    drive_root = tmp_path / "drive"
    output_file = drive_root / "portal_u7" / "Output" / "task_ok" / "result.txt"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("ok\n", encoding="utf-8")
    db = FakeCaseDb(
        tasks=[
            {
                "id": 20,
                "task_id": "task_ok",
                "user_id": 7,
                "app_id": 5,
                "status": "succeeded",
                "result_summary_json": None,
            }
        ],
        artifacts=[
            {
                "id": 30,
                "task_id": 20,
                "artifact_kind": "workspace_output",
                "display_name": "result.txt",
                "relative_path": "Output/task_ok/result.txt",
                "size_bytes": 3,
            }
        ],
    )
    service = CaseCenterService(db=db, drive_root=drive_root)

    with pytest.raises(CaseCenterServiceError) as exc:
        service.publish_case_from_task(
            task_id="task_ok",
            publisher_user_id=99,
            title="别人别乱发",
        )

    assert exc.value.status_code == 403
    assert exc.value.code == "task_publish_forbidden"
    assert all(not rows for rows in db.tables.values())
    assert not (drive_root / "_public_case_packages").exists()


def test_publish_copies_workspace_output_to_public_package_and_writes_four_tables(tmp_path):
    from backend.case_center_service import CaseCenterService

    drive_root = tmp_path / "drive"
    private_root = drive_root / "portal_u7"
    output_dir = private_root / "Output" / "task_ok"
    output_file = output_dir / "result.txt"
    ignored_input = private_root / "Input" / "secret.txt"
    output_file.parent.mkdir(parents=True)
    ignored_input.parent.mkdir(parents=True)
    output_file.write_text("public result\n", encoding="utf-8")
    ignored_input.write_text("private input\n", encoding="utf-8")
    db = FakeCaseDb(
        tasks=[
            {
                "id": 22,
                "task_id": "task_ok",
                "user_id": 7,
                "app_id": 5,
                "status": "succeeded",
                "result_summary_json": {"score": 98},
            }
        ],
        artifacts=[
            {
                "id": 31,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "result.txt",
                "relative_path": "Output/task_ok/result.txt",
                "size_bytes": 14,
            },
            {
                "id": 32,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "secret.txt",
                "relative_path": "Input/secret.txt",
                "size_bytes": 14,
            },
            {
                "id": 33,
                "task_id": 22,
                "artifact_kind": "external_link",
                "display_name": "external",
                "external_url": "https://example.com/result",
                "size_bytes": None,
            },
        ],
    )
    package_root = drive_root / "_public_case_packages"
    service = CaseCenterService(
        db=db,
        drive_root=drive_root,
        package_root=package_root,
        case_uid_factory=lambda: "case_fixed",
    )

    assert all(not rows for rows in db.tables.values())

    result = service.publish_case_from_task(
        task_id="task_ok",
        publisher_user_id=7,
        title="热仿真案例",
        summary="可公开结果",
    )

    assert result["case_uid"] == "case_fixed"
    assert len(db.tables["simulation_case"]) == 1
    assert len(db.tables["simulation_case_source"]) == 1
    assert len(db.tables["simulation_case_asset"]) == 1
    assert len(db.tables["simulation_case_package"]) == 1

    case_row = db.tables["simulation_case"][0]
    assert case_row["title"] == "热仿真案例"
    assert case_row["status"] == "published"
    assert case_row["visibility"] == "public"

    source_row = db.tables["simulation_case_source"][0]
    assert source_row["source_type"] == "platform_task"
    assert source_row["source_task_id"] == 22
    assert source_row["source_task_public_id"] == "task_ok"
    assert source_row["source_user_id"] == 7

    asset_row = db.tables["simulation_case_asset"][0]
    assert asset_row["asset_kind"] == "workspace_output"
    assert asset_row["package_relative_path"] == "assets/task_ok/result.txt"
    assert "private" not in _json_dump(asset_row).lower()
    assert str(private_root.resolve()) not in _json_dump(asset_row)

    package_row = db.tables["simulation_case_package"][0]
    package_path = Path(package_row["archive_path"])
    assert package_path.exists()
    assert package_root.resolve() in package_path.resolve().parents
    assert private_root.resolve() not in package_path.resolve().parents
    assert str(private_root.resolve()) not in _json_dump(db.tables)

    with zipfile.ZipFile(package_path) as archive:
        assert archive.namelist() == ["assets/task_ok/result.txt"]
        assert archive.read("assets/task_ok/result.txt") == output_file.read_bytes()


def test_publish_ignores_directory_entries_that_resolve_outside_artifact_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from backend.case_center_service import CaseCenterService

    class _FakeStat:
        st_size = 6

    class _EscapedChild:
        def __init__(self, directory: Path, resolved_target: Path):
            self._directory = directory
            self._resolved_target = resolved_target
            self.name = "escape.txt"

        def __lt__(self, other):
            return str(self) < str(other)

        def __str__(self):
            return str(self._directory / self.name)

        def is_file(self):
            return True

        def is_symlink(self):
            return True

        def resolve(self):
            return self._resolved_target.resolve()

        def relative_to(self, other):
            assert other == self._directory
            return Path(self.name)

        def stat(self):
            return _FakeStat()

    drive_root = tmp_path / "drive"
    private_root = drive_root / "portal_u7"
    safe_file = private_root / "Output" / "task_ok" / "result.txt"
    artifact_dir = private_root / "Output" / "task_ok" / "bundle"
    escaped_target = private_root / "Output" / "outside-secret.txt"
    safe_file.parent.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    safe_file.write_text("public result\n", encoding="utf-8")
    escaped_target.write_text("secret\n", encoding="utf-8")

    original_rglob = Path.rglob

    def _patched_rglob(self, pattern):
        if self == artifact_dir:
            return [_EscapedChild(artifact_dir, escaped_target)]
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _patched_rglob)

    db = FakeCaseDb(
        tasks=[
            {
                "id": 22,
                "task_id": "task_ok",
                "user_id": 7,
                "app_id": 5,
                "status": "succeeded",
                "result_summary_json": {"score": 98},
            }
        ],
        artifacts=[
            {
                "id": 31,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "result.txt",
                "relative_path": "Output/task_ok/result.txt",
                "size_bytes": 14,
            },
            {
                "id": 32,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "bundle",
                "relative_path": "Output/task_ok/bundle",
                "size_bytes": 0,
            },
        ],
    )
    service = CaseCenterService(
        db=db,
        drive_root=drive_root,
        package_root=drive_root / "_public_case_packages",
        case_uid_factory=lambda: "case_safe",
    )

    result = service.publish_case_from_task(
        task_id="task_ok",
        publisher_user_id=7,
        title="目录越界别进包",
    )

    assert result["case_uid"] == "case_safe"
    assert len(db.tables["simulation_case_asset"]) == 1
    assert db.tables["simulation_case_asset"][0]["package_relative_path"] == "assets/task_ok/result.txt"
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.namelist() == ["assets/task_ok/result.txt"]


def test_publish_ignores_artifact_root_that_is_symlink_or_resolves_outside_output(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from backend.case_center_service import CaseCenterService

    drive_root = tmp_path / "drive"
    private_root = drive_root / "portal_u7"
    safe_file = private_root / "Output" / "task_ok" / "result.txt"
    artifact_dir = private_root / "Output" / "task_ok" / "bundle"
    escaped_dir = private_root / "Input" / "bundle"
    safe_file.parent.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    escaped_dir.mkdir(parents=True)
    safe_file.write_text("public result\n", encoding="utf-8")
    (escaped_dir / "secret.txt").write_text("secret\n", encoding="utf-8")

    original_resolve = Path.resolve
    original_is_symlink = Path.is_symlink

    def _patched_resolve(self, strict=False):
        if self == artifact_dir:
            return escaped_dir
        return original_resolve(self, strict=strict)

    def _patched_is_symlink(self):
        if self == artifact_dir:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(Path, "resolve", _patched_resolve)
    monkeypatch.setattr(Path, "is_symlink", _patched_is_symlink)

    db = FakeCaseDb(
        tasks=[
            {
                "id": 22,
                "task_id": "task_ok",
                "user_id": 7,
                "app_id": 5,
                "status": "succeeded",
                "result_summary_json": {"score": 98},
            }
        ],
        artifacts=[
            {
                "id": 31,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "result.txt",
                "relative_path": "Output/task_ok/result.txt",
                "size_bytes": 14,
            },
            {
                "id": 32,
                "task_id": 22,
                "artifact_kind": "workspace_output",
                "display_name": "bundle",
                "relative_path": "Output/task_ok/bundle",
                "size_bytes": 0,
            },
        ],
    )
    service = CaseCenterService(
        db=db,
        drive_root=drive_root,
        package_root=drive_root / "_public_case_packages",
        case_uid_factory=lambda: "case_root_guard",
    )

    result = service.publish_case_from_task(
        task_id="task_ok",
        publisher_user_id=7,
        title="根链接别进包",
    )

    assert result["case_uid"] == "case_root_guard"
    assert len(db.tables["simulation_case_asset"]) == 1
    assert db.tables["simulation_case_asset"][0]["package_relative_path"] == "assets/task_ok/result.txt"
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.namelist() == ["assets/task_ok/result.txt"]


def test_sql_scripts_define_case_center_schema():
    sql_paths = [
        Path("database/init.sql"),
        Path("deploy/initdb/01-portal-init.sql"),
        Path("database/migrate_simulation_case_center.sql"),
    ]

    for sql_path in sql_paths:
        sql = sql_path.read_text(encoding="utf-8")
        assert "simulation_case" in sql
        assert "simulation_case_source" in sql
        assert "simulation_case_asset" in sql
        assert "simulation_case_package" in sql
        assert "source_task_public_id" in sql
        assert "package_relative_path" in sql
