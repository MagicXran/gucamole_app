import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import httpx
from fastapi import HTTPException, status
from fastapi import FastAPI


def _load_admin_pool_router(monkeypatch):
    fake_database = types.ModuleType("backend.database")
    fake_auth = types.ModuleType("backend.auth")
    fake_monitor = types.ModuleType("backend.monitor")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

        def execute_update(self, *args, **kwargs):
            return 0

    fake_database.db = FakeDb()
    fake_database.CONFIG = {"monitor": {}, "api": {"prefix": "/api/remote-apps"}}
    def _deny_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    fake_auth.require_admin = _deny_admin
    fake_auth.get_current_user = lambda: None
    fake_monitor.invalidate_user_session_if_safe = lambda *args, **kwargs: None
    fake_monitor.dispatch_ready_queue_entries = lambda: None
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth)
    monkeypatch.setitem(sys.modules, "backend.monitor", fake_monitor)
    monkeypatch.delitem(sys.modules, "backend.admin_pool_router", raising=False)
    return importlib.import_module("backend.admin_pool_router")


def _request(app: FastAPI, method: str, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_update_pool_disabling_pool_cleans_invalid_queue_entries(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    cleanup_calls = []
    invalidate_calls = []

    class FakePoolService:
        def update_pool(self, *, pool_id, payload):
            return {"id": pool_id, "name": "pool", **payload}

        def cleanup_invalid_queue_entries(self, **kwargs):
            cleanup_calls.append(kwargs)
            return []

        def reclaim_pool_sessions(self, **kwargs):
            cleanup_calls.append({"reclaim": kwargs})
            return []

        def cancel_pool_tasks(self, **kwargs):
            cleanup_calls.append({"tasks": kwargs})
            return 0

    monkeypatch.setattr(admin_pool_router, "pool_service", FakePoolService())
    monkeypatch.setattr(admin_pool_router, "log_action", lambda *args, **kwargs: None)
    fake_router_module = types.ModuleType("backend.router")
    fake_router_module.guac_service = SimpleNamespace(invalidate_all_sessions=lambda: invalidate_calls.append("all"))
    monkeypatch.setitem(sys.modules, "backend.router", fake_router_module)

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_pool_router.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    response = admin_pool_router.update_pool(
        pool_id=3,
        req=admin_pool_router.ResourcePoolUpdateRequest(is_active=False),
        request=request,
        admin=admin,
    )

    assert response["is_active"] is False
    assert {"pool_id": 3} in cleanup_calls
    assert {"reclaim": {"pool_id": 3, "reason": "admin"}} in cleanup_calls
    assert {"tasks": {"pool_id": 3, "reason": "pool_disabled"}} in cleanup_calls
    assert invalidate_calls == ["all"]


def test_list_queues_returns_pool_queue_items(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)

    class FakePoolService:
        def list_admin_queues(self):
            return [
                {
                    "queue_id": 12,
                    "pool_id": 3,
                    "pool_name": "求解池",
                    "user_id": 7,
                    "username": "tester",
                    "display_name": "测试员",
                    "status": "queued",
                    "created_at": "2026-04-18 10:00:00",
                    "ready_expires_at": "",
                    "cancel_reason": "",
                }
            ]

    monkeypatch.setattr(admin_pool_router, "pool_service", FakePoolService())

    admin = admin_pool_router.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    response = admin_pool_router.list_queues(admin=admin)

    assert response == {
        "items": [
            {
                "queue_id": 12,
                "pool_id": 3,
                "pool_name": "求解池",
                "user_id": 7,
                "username": "tester",
                "display_name": "测试员",
                "status": "queued",
                "created_at": "2026-04-18 10:00:00",
                "ready_expires_at": "",
                "cancel_reason": "",
            }
        ]
    }


def test_cancel_queue_dispatches_ready_entries(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    dispatch_calls = []
    log_calls = []

    class FakePoolService:
        def cancel_queue_admin(self, *, queue_id):
            assert queue_id == 12
            return {"queue_id": 12, "status": "cancelled"}

    monkeypatch.setattr(admin_pool_router, "pool_service", FakePoolService())
    monkeypatch.setattr(admin_pool_router, "log_action", lambda *args, **kwargs: log_calls.append((args, kwargs)))
    fake_monitor_module = types.ModuleType("backend.monitor")
    fake_monitor_module.dispatch_ready_queue_entries = lambda: dispatch_calls.append("dispatched")
    monkeypatch.setitem(sys.modules, "backend.monitor", fake_monitor_module)

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_pool_router.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    response = admin_pool_router.cancel_queue(queue_id=12, request=request, admin=admin)

    assert response == {"queue_id": 12, "status": "cancelled"}
    assert dispatch_calls == ["dispatched"]
    assert len(log_calls) == 1


def test_list_queues_requires_admin(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    app = FastAPI()
    app.include_router(admin_pool_router.router)

    response = _request(app, "GET", "/api/admin/pools/queues")

    assert response.status_code == 403


def test_reclaim_session_calls_service_and_invalidates_user(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    invalidate_calls = []
    log_calls = []

    class FakePoolService:
        def reclaim_session(self, *, session_id):
            assert session_id == "session-1"
            return {"session_id": "session-1", "user_id": 7, "status": "reclaim_pending"}

    fake_router_module = types.ModuleType("backend.router")
    fake_router_module.guac_service = object()
    monkeypatch.setitem(sys.modules, "backend.router", fake_router_module)
    monkeypatch.setattr(admin_pool_router, "pool_service", FakePoolService())
    monkeypatch.setattr(admin_pool_router, "log_action", lambda *args, **kwargs: log_calls.append((args, kwargs)))
    monkeypatch.setattr(
        admin_pool_router,
        "invalidate_user_session_if_safe",
        lambda guac_service, user_id, **kwargs: invalidate_calls.append((guac_service, user_id, kwargs)),
    )

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_pool_router.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    response = admin_pool_router.reclaim_session(session_id="session-1", request=request, admin=admin)

    assert response == {"session_id": "session-1", "user_id": 7, "status": "reclaim_pending"}
    assert invalidate_calls == [(fake_router_module.guac_service, 7, {"exclude_session_id": "session-1", "session_db": admin_pool_router.db})]
    assert len(log_calls) == 1


def test_reclaim_session_requires_admin(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    app = FastAPI()
    app.include_router(admin_pool_router.router)

    response = _request(app, "POST", "/api/admin/pools/sessions/session-1/reclaim")

    assert response.status_code == 403


def test_cancel_queue_requires_admin(monkeypatch):
    admin_pool_router = _load_admin_pool_router(monkeypatch)
    app = FastAPI()
    app.include_router(admin_pool_router.router)

    response = _request(app, "POST", "/api/admin/pools/queues/12/cancel")

    assert response.status_code == 403
