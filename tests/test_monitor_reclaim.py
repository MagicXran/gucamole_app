import asyncio

import httpx
from fastapi import FastAPI

import backend.monitor as monitor
from backend.models import UserInfo


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


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(monitor.router)
    app.dependency_overrides[monitor.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="Tester",
        is_admin=False,
    )
    return app


def _request(app: FastAPI, method: str, path: str, payload: dict) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(_run())


def test_heartbeat_and_activity_return_200_when_session_is_active(monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(active_session_ids={"session-active"}),
    )
    app = _build_app()

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


def test_heartbeat_and_activity_return_409_when_session_is_admin_reclaimed(monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(reclaimed_sessions={"session-reclaimed": "admin"}),
    )
    app = _build_app()

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


def test_heartbeat_and_activity_return_409_when_session_is_idle_reclaimed(monkeypatch):
    monkeypatch.setattr(
        monitor,
        "db",
        FakeDB(reclaimed_sessions={"session-idle-reclaimed": "idle"}),
    )
    app = _build_app()

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


def test_heartbeat_and_activity_keep_404_when_session_missing(monkeypatch):
    monkeypatch.setattr(monitor, "db", FakeDB())
    app = _build_app()

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
