import asyncio
import importlib
import sys
import types

import httpx
import pytest
from fastapi import FastAPI

from backend.models import UserInfo


class ImportSafeDb:
    def execute_update(self, *args, **kwargs):
        return 0

    def execute_query(self, *args, **kwargs):
        return None if kwargs.get("fetch_one") else []


@pytest.fixture
def monitor(monkeypatch):
    fake_database = types.ModuleType("backend.database")
    fake_database.db = ImportSafeDb()
    fake_database.CONFIG = {
        "monitor": {},
        "api": {"prefix": "/api/remote-apps"},
        "auth": {
            "jwt_secret": "test-secret-key-with-32-bytes-min!!",
            "token_expire_minutes": 480,
        },
    }
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    monkeypatch.delitem(sys.modules, "backend.auth", raising=False)
    monkeypatch.delitem(sys.modules, "backend.monitor", raising=False)
    return importlib.import_module("backend.monitor")


class FakeDB:
    def __init__(self, *, active_session_ids=None, reclaimed_sessions=None):
        self.active_session_ids = set(active_session_ids or [])
        self.reclaimed_sessions = dict(reclaimed_sessions or {})

    def execute_update(self, query: str, params=None) -> int:
        sid = (params or {}).get("sid")
        if "status = 'active'" in query and sid in self.active_session_ids:
            return 1
        return 0

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        sid = (params or {}).get("sid")
        if "status = 'reclaim_pending'" in query and sid in self.reclaimed_sessions:
            row = {"reclaim_reason": self.reclaimed_sessions[sid]}
            if fetch_one:
                return row
            return [row]
        if fetch_one:
            return None
        return []


class FakeAdminMonitorDB:
    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "SELECT id, name, icon FROM remote_app" in query:
            return [{"id": 3, "name": "远程桌面", "icon": "desktop"}]
        if "GROUP BY app_id" in query:
            rows = [{"app_id": 3, "cnt": 2 if "reclaim_pending" in query else 1}]
            return rows
        if "COUNT(DISTINCT user_id)" in query:
            row = {"cnt": 2 if "reclaim_pending" in query else 1}
            return row if fetch_one else [row]
        if "SELECT s.session_id" in query:
            active_row = {
                "session_id": "session-active",
                "user_id": 7,
                "username": "tester",
                "display_name": "Tester",
                "app_name": "远程桌面",
                "started_at": "2026-04-11 16:00:00",
                "last_heartbeat": "2026-04-11 16:00:05",
                "status": "active",
                "duration_seconds": 5,
            }
            reclaim_row = {
                "session_id": "session-reclaim-pending",
                "user_id": 8,
                "username": "tester2",
                "display_name": "Tester2",
                "app_name": "远程桌面",
                "started_at": "2026-04-11 16:00:00",
                "last_heartbeat": "2026-04-11 16:00:05",
                "status": "reclaim_pending",
                "duration_seconds": 5,
            }
            rows = [active_row, reclaim_row] if "reclaim_pending" in query else [active_row]
            return rows
        if fetch_one:
            return None
        return []


def _build_app(monitor) -> FastAPI:
    app = FastAPI()
    app.include_router(monitor.router)
    app.dependency_overrides[monitor.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="Tester",
        is_admin=False,
    )
    return app


def _build_admin_monitor_app(monitor) -> FastAPI:
    app = FastAPI()
    app.include_router(monitor.admin_monitor_router)
    app.dependency_overrides[monitor.require_admin] = lambda: UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )
    return app


def _build_unauthed_admin_monitor_app(monitor) -> FastAPI:
    app = FastAPI()
    app.include_router(monitor.admin_monitor_router)
    return app


def _request(app: FastAPI, method: str, path: str, payload: dict | None = None) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            kwargs = {"json": payload} if payload is not None else {}
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def test_heartbeat_and_activity_return_200_when_session_is_active(monitor, monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(active_session_ids={"session-active"}),
    )
    app = _build_app(monitor)

    heartbeat_resp = _request(
        app,
        "POST",
        "/api/monitor/heartbeat",
        {"session_id": "session-active"},
    )
    activity_resp = _request(
        app,
        "POST",
        "/api/monitor/activity",
        {"session_id": "session-active"},
    )

    assert heartbeat_resp.status_code == 200
    assert heartbeat_resp.json() == {"ok": True}
    assert activity_resp.status_code == 200
    assert activity_resp.json() == {"ok": True}


def test_heartbeat_and_activity_return_409_when_session_is_admin_reclaimed(monitor, monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(reclaimed_sessions={"session-reclaimed": "admin"}),
    )
    app = _build_app(monitor)

    heartbeat_resp = _request(
        app,
        "POST",
        "/api/monitor/heartbeat",
        {"session_id": "session-reclaimed"},
    )
    activity_resp = _request(
        app,
        "POST",
        "/api/monitor/activity",
        {"session_id": "session-reclaimed"},
    )

    assert heartbeat_resp.status_code == 409
    assert heartbeat_resp.json() == {
        "detail": "会话已被管理员回收",
        "code": "session_reclaimed",
        "reason": "admin",
    }
    assert activity_resp.status_code == 409
    assert activity_resp.json() == {
        "detail": "会话已被管理员回收",
        "code": "session_reclaimed",
        "reason": "admin",
    }


def test_heartbeat_and_activity_return_409_when_session_is_idle_reclaimed(monitor, monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(reclaimed_sessions={"session-idle-reclaimed": "idle"}),
    )
    app = _build_app(monitor)

    heartbeat_resp = _request(
        app,
        "POST",
        "/api/monitor/heartbeat",
        {"session_id": "session-idle-reclaimed"},
    )
    activity_resp = _request(
        app,
        "POST",
        "/api/monitor/activity",
        {"session_id": "session-idle-reclaimed"},
    )

    assert heartbeat_resp.status_code == 409
    assert heartbeat_resp.json() == {
        "detail": "会话因长时间空闲被系统回收",
        "code": "session_reclaimed",
        "reason": "idle",
    }
    assert activity_resp.status_code == 409
    assert activity_resp.json() == {
        "detail": "会话因长时间空闲被系统回收",
        "code": "session_reclaimed",
        "reason": "idle",
    }


def test_heartbeat_and_activity_keep_404_when_session_missing(monitor, monkeypatch):
    monkeypatch.setattr(monitor, "db", FakeDB())
    app = _build_app(monitor)

    heartbeat_resp = _request(
        app,
        "POST",
        "/api/monitor/heartbeat",
        {"session_id": "session-missing"},
    )
    activity_resp = _request(
        app,
        "POST",
        "/api/monitor/activity",
        {"session_id": "session-missing"},
    )

    assert heartbeat_resp.status_code == 404
    assert heartbeat_resp.json() == {"detail": "会话不存在或已结束"}
    assert activity_resp.status_code == 404
    assert activity_resp.json() == {"detail": "会话不存在或已结束"}


def test_admin_monitor_overview_excludes_reclaim_pending_sessions(monitor, monkeypatch):
    monkeypatch.setattr(monitor, "db", FakeAdminMonitorDB())
    app = _build_admin_monitor_app(monitor)

    response = _request(app, "GET", "/api/admin/monitor/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_online"] == 1
    assert payload["total_sessions"] == 1
    assert payload["apps"][0]["active_count"] == 1


def test_admin_monitor_sessions_excludes_reclaim_pending_sessions(monitor, monkeypatch):
    monkeypatch.setattr(monitor, "db", FakeAdminMonitorDB())
    app = _build_admin_monitor_app(monitor)

    response = _request(app, "GET", "/api/admin/monitor/sessions")

    assert response.status_code == 200
    payload = response.json()
    assert [row["session_id"] for row in payload["sessions"]] == ["session-active"]
    assert payload["sessions"][0]["status"] == "active"


def test_admin_monitor_routes_require_admin_without_override(monitor):
    app = _build_unauthed_admin_monitor_app(monitor)

    response = _request(app, "GET", "/api/admin/monitor/overview")

    assert response.status_code in {401, 403}
