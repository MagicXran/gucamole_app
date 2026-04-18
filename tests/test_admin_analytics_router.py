import asyncio
import importlib
import sys
import types
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, status

from backend.models import UserInfo


class FakeAnalyticsDb:
    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        normalized = " ".join(str(query).split())

        if "/* analytics:overview_totals */" in normalized:
            return {
                "software_launches": 17,
                "case_events": 18,
                "active_users": 12,
                "department_count": 11,
            } if fetch_one else [
                {
                    "software_launches": 17,
                    "case_events": 18,
                    "active_users": 12,
                    "department_count": 11,
                }
            ]

        if "/* analytics:software_ranking */" in normalized:
            return [
                {
                    "app_id": 11,
                    "app_name": "Abaqus",
                    "launch_count": 5,
                },
                {
                    "app_id": 12,
                    "app_name": "Fluent",
                    "launch_count": 2,
                },
            ]

        if "/* analytics:case_ranking */" in normalized:
            return [
                {
                    "case_id": 31,
                    "case_uid": "case-heat-001",
                    "case_title": "热轧工艺窗口案例",
                    "detail_count": 3,
                    "download_count": 2,
                    "transfer_count": 1,
                    "event_count": 6,
                },
                {
                    "case_id": 32,
                    "case_uid": "case-furnace-002",
                    "case_title": "加热炉燃烧优化案例",
                    "detail_count": 1,
                    "download_count": 0,
                    "transfer_count": 1,
                    "event_count": 2,
                },
            ]

        if "/* analytics:user_ranking */" in normalized:
            return [
                {
                    "user_id": 7,
                    "username": "alice",
                    "display_name": "Alice",
                    "department": "研发一部",
                    "software_launch_count": 4,
                    "case_event_count": 2,
                    "event_count": 6,
                },
                {
                    "user_id": 9,
                    "username": "bob",
                    "display_name": "Bob",
                    "department": "",
                    "software_launch_count": 1,
                    "case_event_count": 2,
                    "event_count": 3,
                },
            ]

        if "/* analytics:department_ranking */" in normalized:
            return [
                {
                    "department": "研发一部",
                    "user_count": 1,
                    "event_count": 6,
                },
                {
                    "department": "",
                    "user_count": 1,
                    "event_count": 3,
                },
            ]

        raise AssertionError(f"unexpected query: {query}")

    def execute_update(self, *args, **kwargs):
        return 0


def _load_admin_analytics_router(monkeypatch):
    fake_database = types.ModuleType("backend.database")
    fake_auth = types.ModuleType("backend.auth")
    fake_database.db = FakeAnalyticsDb()
    fake_database.CONFIG = {}

    def _deny_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    fake_auth.require_admin = _deny_admin
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth)
    monkeypatch.delitem(sys.modules, "backend.admin_analytics_service", raising=False)
    monkeypatch.delitem(sys.modules, "backend.admin_analytics_router", raising=False)
    return importlib.import_module("backend.admin_analytics_router")


def _request(app: FastAPI, method: str, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_admin_analytics_overview_returns_rankings_and_department_grouping(monkeypatch):
    admin_analytics_router = _load_admin_analytics_router(monkeypatch)
    app = FastAPI()
    app.include_router(admin_analytics_router.router)
    app.dependency_overrides[admin_analytics_router.require_admin] = lambda: UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    response = _request(app, "GET", "/api/admin/analytics/overview")

    assert response.status_code == 200
    assert response.json() == {
        "overview": {
            "software_launches": 17,
            "case_events": 18,
            "active_users": 12,
            "department_count": 11,
        },
        "software_ranking": [
            {
                "app_id": 11,
                "app_name": "Abaqus",
                "launch_count": 5,
            },
            {
                "app_id": 12,
                "app_name": "Fluent",
                "launch_count": 2,
            },
        ],
        "case_ranking": [
            {
                "case_id": 31,
                "case_uid": "case-heat-001",
                "case_title": "热轧工艺窗口案例",
                "detail_count": 3,
                "download_count": 2,
                "transfer_count": 1,
                "event_count": 6,
            },
            {
                "case_id": 32,
                "case_uid": "case-furnace-002",
                "case_title": "加热炉燃烧优化案例",
                "detail_count": 1,
                "download_count": 0,
                "transfer_count": 1,
                "event_count": 2,
            },
        ],
        "user_ranking": [
            {
                "user_id": 7,
                "username": "alice",
                "display_name": "Alice",
                "department": "研发一部",
                "software_launch_count": 4,
                "case_event_count": 2,
                "event_count": 6,
            },
            {
                "user_id": 9,
                "username": "bob",
                "display_name": "Bob",
                "department": "未设置",
                "software_launch_count": 1,
                "case_event_count": 2,
                "event_count": 3,
            },
        ],
        "department_ranking": [
            {
                "department": "研发一部",
                "user_count": 1,
                "event_count": 6,
            },
            {
                "department": "未设置",
                "user_count": 1,
                "event_count": 3,
            },
        ],
    }


def test_admin_analytics_route_requires_admin(monkeypatch):
    admin_analytics_router = _load_admin_analytics_router(monkeypatch)
    app = FastAPI()
    app.include_router(admin_analytics_router.router)

    response = _request(app, "GET", "/api/admin/analytics/overview")

    assert response.status_code == 403
    assert response.json()["detail"] == "需要管理员权限"


def test_sql_scripts_define_department_for_portal_user():
    init_sql = Path("database/init.sql").read_text(encoding="utf-8")
    deploy_init_sql = Path("deploy/initdb/01-portal-init.sql").read_text(encoding="utf-8")
    migrate_sql_path = Path("database/migrate_admin_analytics.sql")

    assert "department    VARCHAR(100)" in init_sql
    assert "department    VARCHAR(100)" in deploy_init_sql
    assert migrate_sql_path.exists()
    migrate_sql = migrate_sql_path.read_text(encoding="utf-8")
    assert "ALTER TABLE portal_user" in migrate_sql
    assert "ADD COLUMN department VARCHAR(100)" in migrate_sql


def test_app_registers_admin_analytics_router():
    app_py = Path("backend/app.py").read_text(encoding="utf-8")

    assert "admin_analytics_router" in app_py
    assert "app.include_router(admin_analytics_router)" in app_py
