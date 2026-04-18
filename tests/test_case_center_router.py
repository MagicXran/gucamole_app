import asyncio
import importlib
import sys
import types
import zipfile
from pathlib import Path

import httpx
from fastapi import FastAPI

from backend.models import UserInfo


def _install_fake_database(*, drive_root: Path):
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

        def execute_update(self, *args, **kwargs):
            raise AssertionError("router tests should not write through backend.database.db")

    fake_database.db = FakeDb()
    fake_database.CONFIG = {
        "auth": {"jwt_secret": "test-secret-key-with-32-bytes-min!!"},
        "guacamole": {
            "drive": {
                "base_path": str(drive_root),
                "results_root": "Output",
            }
        },
    }
    sys.modules["backend.database"] = fake_database


class FakeCaseDb:
    def __init__(self, *, cases, assets):
        self.cases = [dict(row) for row in cases]
        self.assets = [dict(row) for row in assets]
        self.query_log: list[str] = []

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        normalized = " ".join(str(query).split())
        self.query_log.append(normalized)

        if "FROM simulation_case c" in normalized and "JOIN simulation_case_package p" in normalized:
            rows = [
                dict(row)
                for row in self.cases
                if row["visibility"] == "public" and row["status"] == "published"
            ]
            if params and params.get("case_id") is not None:
                rows = [row for row in rows if int(row["id"]) == int(params["case_id"])]
                return (rows[0] if rows else None) if fetch_one else rows
            rows.sort(key=lambda row: (row["published_at"], row["id"]), reverse=True)
            return rows[0] if fetch_one and rows else rows

        if "FROM simulation_case_asset" in normalized:
            case_id = int(params["case_id"])
            rows = [dict(row) for row in self.assets if int(row["case_id"]) == case_id]
            rows.sort(key=lambda row: (row.get("sort_order", 0), row["id"]))
            return rows[0] if fetch_one and rows else rows

        raise AssertionError(f"unexpected query: {query}")


def _request(app: FastAPI, method: str, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def _seed_public_case(tmp_path: Path, *, case_id: int, case_uid: str, title: str):
    package_root = tmp_path / "_public_case_packages" / case_uid / "package"
    package_root.mkdir(parents=True, exist_ok=True)
    guide_path = package_root / "assets" / "docs" / "guide.txt"
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    guide_path.write_text(f"{title} public guide", encoding="utf-8")

    archive_path = package_root.parent / f"{case_uid}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(guide_path, arcname="assets/docs/guide.txt")

    case_row = {
        "id": case_id,
        "case_uid": case_uid,
        "title": title,
        "summary": f"{title} summary",
        "app_id": 11,
        "visibility": "public",
        "status": "published",
        "published_at": "2026-04-17 10:00:00",
        "package_root": str(package_root),
        "archive_path": str(archive_path),
        "archive_size_bytes": archive_path.stat().st_size,
        "asset_count": 1,
    }
    asset_rows = [
        {
            "id": case_id * 100,
            "case_id": case_id,
            "asset_kind": "workspace_output",
            "display_name": "guide.txt",
            "package_relative_path": "assets/docs/guide.txt",
            "size_bytes": guide_path.stat().st_size,
            "sort_order": 0,
        }
    ]
    return case_row, asset_rows, archive_path.read_bytes()


def _build_client(tmp_path: Path, *, cases, assets):
    drive_root = tmp_path / "drive"
    _install_fake_database(drive_root=drive_root)
    sys.modules.pop("backend.auth", None)
    sys.modules.pop("backend.case_center_router", None)

    auth_module = importlib.import_module("backend.auth")
    case_center_router = importlib.import_module("backend.case_center_router")
    from backend.case_center_service import CaseCenterService

    fake_db = FakeCaseDb(cases=cases, assets=assets)
    case_center_router.service = CaseCenterService(
        db=fake_db,
        drive_root=drive_root,
        package_root=tmp_path / "_public_case_packages",
    )

    app = FastAPI()
    app.include_router(case_center_router.router)
    app.dependency_overrides[auth_module.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="测试用户",
        is_admin=False,
    )
    return app, fake_db, drive_root


def test_list_and_detail_only_expose_published_public_cases(tmp_path: Path):
    public_case, public_assets, _archive_bytes = _seed_public_case(
        tmp_path,
        case_id=1,
        case_uid="case_alpha",
        title="公开案例",
    )
    private_case = {
        **public_case,
        "id": 2,
        "case_uid": "case_private",
        "title": "私有案例",
        "visibility": "private",
    }
    draft_case = {
        **public_case,
        "id": 3,
        "case_uid": "case_draft",
        "title": "草稿案例",
        "status": "draft",
    }

    app, db, _drive_root = _build_client(
        tmp_path,
        cases=[public_case, private_case, draft_case],
        assets=public_assets,
    )

    list_response = _request(app, "GET", "/api/cases")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": 1,
            "case_uid": "case_alpha",
            "title": "公开案例",
            "summary": "公开案例 summary",
            "app_id": 11,
            "published_at": "2026-04-17 10:00:00",
            "asset_count": 1,
        }
    ]

    detail_response = _request(app, "GET", "/api/cases/1")

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["case_uid"] == "case_alpha"
    assert detail_payload["assets"] == [
        {
            "id": 100,
            "asset_kind": "workspace_output",
            "display_name": "guide.txt",
            "package_relative_path": "assets/docs/guide.txt",
            "size_bytes": public_assets[0]["size_bytes"],
            "sort_order": 0,
        }
    ]
    assert "package_root" not in detail_payload
    assert "archive_path" not in detail_payload

    missing_response = _request(app, "GET", "/api/cases/2")
    assert missing_response.status_code == 404
    assert all("simulation_case_source" not in query for query in db.query_log)


def test_download_returns_public_archive_without_private_task_path(tmp_path: Path):
    public_case, public_assets, archive_bytes = _seed_public_case(
        tmp_path,
        case_id=9,
        case_uid="case_download",
        title="下载案例",
    )
    private_task_root = tmp_path / "drive" / "portal_u7" / "Output" / "task-secret"
    private_task_root.mkdir(parents=True, exist_ok=True)
    private_task_file = private_task_root / "secret.txt"
    private_task_file.write_text("private task payload", encoding="utf-8")

    app, db, _drive_root = _build_client(tmp_path, cases=[public_case], assets=public_assets)

    response = _request(app, "GET", "/api/cases/9/download")

    assert response.status_code == 200
    assert response.content == archive_bytes
    assert "case_download.zip" in response.headers["content-disposition"]
    assert b"private task payload" not in response.content
    assert all("simulation_case_source" not in query for query in db.query_log)
    assert private_task_file.read_text(encoding="utf-8") == "private task payload"


def test_download_rejects_private_and_draft_cases(tmp_path: Path):
    public_case, public_assets, _archive_bytes = _seed_public_case(
        tmp_path,
        case_id=21,
        case_uid="case_hidden",
        title="隐藏案例",
    )
    private_case = {
        **public_case,
        "id": 22,
        "case_uid": "case_private_download",
        "visibility": "private",
    }
    draft_case = {
        **public_case,
        "id": 23,
        "case_uid": "case_draft_download",
        "status": "draft",
    }

    app, _db, _drive_root = _build_client(
        tmp_path,
        cases=[private_case, draft_case],
        assets=public_assets,
    )

    private_response = _request(app, "GET", "/api/cases/22/download")
    draft_response = _request(app, "GET", "/api/cases/23/download")

    assert private_response.status_code == 404
    assert draft_response.status_code == 404


def test_transfer_copies_public_package_into_current_users_workspace(tmp_path: Path):
    public_case, public_assets, _archive_bytes = _seed_public_case(
        tmp_path,
        case_id=12,
        case_uid="case_transfer",
        title="转存案例",
    )
    private_task_root = tmp_path / "drive" / "portal_u7" / "Output" / "task-private"
    private_task_root.mkdir(parents=True, exist_ok=True)
    (private_task_root / "secret.txt").write_text("private-only", encoding="utf-8")

    app, db, drive_root = _build_client(tmp_path, cases=[public_case], assets=public_assets)

    response = _request(app, "POST", "/api/cases/12/transfer")

    assert response.status_code == 200
    assert response.json() == {
        "case_id": 12,
        "case_uid": "case_transfer",
        "target_path": "Cases/case_transfer",
        "asset_count": 1,
    }

    transferred_file = drive_root / "portal_u7" / "Cases" / "case_transfer" / "assets" / "docs" / "guide.txt"
    assert transferred_file.exists()
    assert transferred_file.read_text(encoding="utf-8") == "转存案例 public guide"
    assert all("simulation_case_source" not in query for query in db.query_log)
    assert (private_task_root / "secret.txt").read_text(encoding="utf-8") == "private-only"


def test_transfer_rejects_private_and_draft_cases(tmp_path: Path):
    public_case, public_assets, _archive_bytes = _seed_public_case(
        tmp_path,
        case_id=31,
        case_uid="case_hidden_transfer",
        title="隐藏转存案例",
    )
    private_case = {
        **public_case,
        "id": 32,
        "case_uid": "case_private_transfer",
        "visibility": "private",
    }
    draft_case = {
        **public_case,
        "id": 33,
        "case_uid": "case_draft_transfer",
        "status": "draft",
    }

    app, _db, drive_root = _build_client(
        tmp_path,
        cases=[private_case, draft_case],
        assets=public_assets,
    )

    private_response = _request(app, "POST", "/api/cases/32/transfer")
    draft_response = _request(app, "POST", "/api/cases/33/transfer")

    assert private_response.status_code == 404
    assert draft_response.status_code == 404
    assert not (drive_root / "portal_u7" / "Cases" / "case_private_transfer").exists()
    assert not (drive_root / "portal_u7" / "Cases" / "case_draft_transfer").exists()


def test_transfer_returns_business_error_when_target_parent_chain_contains_file(tmp_path: Path):
    public_case, public_assets, _archive_bytes = _seed_public_case(
        tmp_path,
        case_id=41,
        case_uid="case_conflict",
        title="父链冲突案例",
    )
    app, _db, drive_root = _build_client(tmp_path, cases=[public_case], assets=public_assets)
    user_root = drive_root / "portal_u7"
    user_root.mkdir(parents=True, exist_ok=True)
    (user_root / "Cases").write_text("not a directory", encoding="utf-8")

    response = _request(app, "POST", "/api/cases/41/transfer")

    assert response.status_code == 409
    payload = response.json()
    assert payload["detail"]["code"] == "case_transfer_conflict"
    assert "target workspace path" in payload["detail"]["message"]
    assert not (user_root / "Cases" / "case_conflict").exists()


def test_app_registers_case_center_router():
    app_py = Path("backend/app.py").read_text(encoding="utf-8")

    assert "case_center_router" in app_py
    assert "app.include_router(case_center_router)" in app_py
