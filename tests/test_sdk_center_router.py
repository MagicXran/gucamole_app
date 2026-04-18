import asyncio
import importlib
import sys
import types
from pathlib import Path

import httpx
from fastapi import FastAPI

from backend.models import UserInfo


def _install_fake_database():
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

    fake_database.db = FakeDb()
    fake_database.CONFIG = {"auth": {"jwt_secret": "test-secret-key-with-32-bytes-min!!"}}
    sys.modules["backend.database"] = fake_database


class FakeSdkDb:
    def __init__(self):
        self.packages = [
            {
                "id": 1,
                "package_kind": "cloud_platform",
                "name": "云平台 Python SDK",
                "summary": "调用云平台 API",
                "homepage_url": "javascript:alert(1)",
                "is_active": 1,
                "sort_order": 10,
            },
            {
                "id": 2,
                "package_kind": "simulation_app",
                "name": "仿真 App SDK",
                "summary": "构建仿真 App",
                "homepage_url": "https://example.test/sim",
                "is_active": 1,
                "sort_order": 20,
            },
            {
                "id": 3,
                "package_kind": "cloud_platform",
                "name": "停用云 SDK",
                "summary": "不应显示",
                "homepage_url": "",
                "is_active": 0,
                "sort_order": 30,
            },
        ]
        self.versions = [
            {
                "id": 11,
                "package_id": 1,
                "version": "1.2.0",
                "release_notes": "新增任务查询",
                "released_at": "2026-04-17 09:00:00",
                "is_active": 1,
                "sort_order": 10,
            },
            {
                "id": 12,
                "package_id": 1,
                "version": "1.1.0",
                "release_notes": "旧版",
                "released_at": "2026-04-10 09:00:00",
                "is_active": 0,
                "sort_order": 20,
            },
            {
                "id": 21,
                "package_id": 2,
                "version": "0.9.0",
                "release_notes": "App 模板",
                "released_at": "2026-04-15 09:00:00",
                "is_active": 1,
                "sort_order": 10,
            },
        ]
        self.assets = [
            {
                "id": 101,
                "version_id": 11,
                "asset_kind": "wheel",
                "display_name": "cloud-sdk-1.2.0.whl",
                "download_url": " https://downloads.example.test/cloud-sdk-1.2.0.whl ",
                "size_bytes": 4096,
                "is_active": 1,
                "sort_order": 10,
            },
            {
                "id": 102,
                "version_id": 11,
                "asset_kind": "docs",
                "display_name": "停用文档",
                "download_url": "https://downloads.example.test/inactive-doc.zip",
                "size_bytes": 2048,
                "is_active": 0,
                "sort_order": 20,
            },
            {
                "id": 103,
                "version_id": 11,
                "asset_kind": "docs",
                "display_name": "bad-link.js",
                "download_url": "javascript:alert(1)",
                "size_bytes": 16,
                "is_active": 1,
                "sort_order": 15,
            },
            {
                "id": 201,
                "version_id": 21,
                "asset_kind": "zip",
                "display_name": "simulation-app-sdk.zip",
                "download_url": "https://downloads.example.test/simulation-app-sdk.zip",
                "size_bytes": 8192,
                "is_active": 1,
                "sort_order": 10,
            },
        ]
        self.query_log: list[tuple[str, dict | None]] = []

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        normalized = " ".join(str(query).split())
        self.query_log.append((normalized, dict(params or {})))

        if "FROM sdk_package" in normalized and "package_kind = %(package_kind)s" in normalized:
            rows = [
                dict(row)
                for row in self.packages
                if row["is_active"] and row["package_kind"] == params["package_kind"]
            ]
            rows.sort(key=lambda row: (row["sort_order"], row["id"]))
            return rows[0] if fetch_one and rows else rows

        if "FROM sdk_package" in normalized and "id = %(package_id)s" in normalized:
            rows = [
                dict(row)
                for row in self.packages
                if row["is_active"] and int(row["id"]) == int(params["package_id"])
            ]
            return (rows[0] if rows else None) if fetch_one else rows

        if "FROM sdk_version" in normalized:
            rows = [
                dict(row)
                for row in self.versions
                if row["is_active"] and int(row["package_id"]) == int(params["package_id"])
            ]
            rows.sort(key=lambda row: (row["sort_order"], row["id"]))
            return rows[0] if fetch_one and rows else rows

        if "FROM sdk_asset" in normalized and "version_id = %(version_id)s" in normalized:
            rows = [
                dict(row)
                for row in self.assets
                if row["is_active"] and int(row["version_id"]) == int(params["version_id"])
            ]
            rows.sort(key=lambda row: (row["sort_order"], row["id"]))
            return rows[0] if fetch_one and rows else rows

        if "FROM sdk_asset a" in normalized:
            rows = []
            for asset in self.assets:
                if not asset["is_active"] or int(asset["id"]) != int(params["asset_id"]):
                    continue
                version = next((row for row in self.versions if row["id"] == asset["version_id"]), None)
                package = next((row for row in self.packages if version and row["id"] == version["package_id"]), None)
                if not version or not package or not version["is_active"] or not package["is_active"]:
                    continue
                rows.append(dict(asset))
            return (rows[0] if rows else None) if fetch_one else rows

        raise AssertionError(f"unexpected query: {query}")


def _request(app: FastAPI, method: str, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=False,
        ) as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def _request_json(app: FastAPI, method: str, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=False,
        ) as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def _build_client():
    _install_fake_database()
    sys.modules.pop("backend.auth", None)
    sys.modules.pop("backend.sdk_center_router", None)
    sys.modules.pop("backend.sdk_center_service", None)

    auth_module = importlib.import_module("backend.auth")
    sdk_center_router = importlib.import_module("backend.sdk_center_router")
    from backend.sdk_center_service import SdkCenterService

    fake_db = FakeSdkDb()
    sdk_center_router.service = SdkCenterService(db=fake_db)

    app = FastAPI()
    app.include_router(sdk_center_router.router)
    app.dependency_overrides[auth_module.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="测试用户",
        is_admin=False,
    )
    return app, fake_db


def test_list_filters_cloud_platform_and_hides_inactive_packages():
    app, _db = _build_client()

    response = _request(app, "GET", "/api/sdks?package_kind=cloud_platform")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "package_kind": "cloud_platform",
            "name": "云平台 Python SDK",
            "summary": "调用云平台 API",
            "homepage_url": "",
        }
    ]


def test_list_filters_simulation_app_packages():
    app, _db = _build_client()

    response = _request(app, "GET", "/api/sdks?package_kind=simulation_app")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 2,
            "package_kind": "simulation_app",
            "name": "仿真 App SDK",
            "summary": "构建仿真 App",
            "homepage_url": "https://example.test/sim",
        }
    ]


def test_detail_contains_versions_release_notes_and_active_assets_only():
    app, _db = _build_client()

    response = _request(app, "GET", "/api/sdks/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "package_kind": "cloud_platform",
        "name": "云平台 Python SDK",
        "summary": "调用云平台 API",
        "homepage_url": "",
        "versions": [
            {
                "id": 11,
                "package_id": 1,
                "version": "1.2.0",
                "release_notes": "新增任务查询",
                "released_at": "2026-04-17 09:00:00",
                "assets": [
                    {
                        "id": 101,
                            "version_id": 11,
                            "asset_kind": "wheel",
                            "display_name": "cloud-sdk-1.2.0.whl",
                            "download_url": "https://downloads.example.test/cloud-sdk-1.2.0.whl",
                        "size_bytes": 4096,
                        "sort_order": 10,
                    }
                ],
            }
        ],
    }


def test_detail_hides_inactive_package():
    app, _db = _build_client()

    response = _request(app, "GET", "/api/sdks/3")

    assert response.status_code == 404


def test_download_redirects_active_asset_and_rejects_inactive_or_missing_asset():
    app, _db = _build_client()

    token_response = _request_json(app, "POST", "/api/sdks/assets/101/download-token")
    assert token_response.status_code == 200
    token = token_response.json()["token"]

    unauthenticated_response = _request(app, "GET", "/api/sdks/assets/101/download")
    active_response = _request(app, "GET", f"/api/sdks/assets/101/download?_token={token}")
    invalid_scheme_response = _request_json(app, "POST", "/api/sdks/assets/103/download-token")
    inactive_response = _request_json(app, "POST", "/api/sdks/assets/102/download-token")
    missing_response = _request_json(app, "POST", "/api/sdks/assets/999/download-token")

    assert unauthenticated_response.status_code == 401
    assert active_response.status_code == 307
    assert active_response.headers["location"] == "https://downloads.example.test/cloud-sdk-1.2.0.whl"
    assert invalid_scheme_response.status_code == 404
    assert inactive_response.status_code == 404
    assert missing_response.status_code == 404


def test_download_rejects_token_for_different_asset():
    app, _db = _build_client()

    token_response = _request_json(app, "POST", "/api/sdks/assets/101/download-token")
    token = token_response.json()["token"]

    response = _request(app, "GET", f"/api/sdks/assets/201/download?_token={token}")

    assert response.status_code == 403


def test_schema_defines_sdk_package_version_and_asset_tables(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(Path(__file__).resolve().parents[1].parent)
    init_sql = (repo_root / "database/init.sql").read_text(encoding="utf-8")
    deploy_sql = (repo_root / "deploy/initdb/01-portal-init.sql").read_text(encoding="utf-8")
    migrate_sql = (repo_root / "database/migrate_sdk_center.sql").read_text(encoding="utf-8")

    for sql in (init_sql, deploy_sql, migrate_sql):
        assert "CREATE TABLE IF NOT EXISTS sdk_package" in sql
        assert "CREATE TABLE IF NOT EXISTS sdk_version" in sql
        assert "CREATE TABLE IF NOT EXISTS sdk_asset" in sql
        assert "cloud_platform" in sql
        assert "simulation_app" in sql
