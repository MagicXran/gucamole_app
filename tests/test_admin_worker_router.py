import asyncio
import importlib
import sys
import types

import httpx
from fastapi import FastAPI, HTTPException, status

from backend.models import UserInfo


def _load_admin_worker_router(monkeypatch):
    fake_database = types.ModuleType("backend.database")
    fake_auth = types.ModuleType("backend.auth")
    fake_database.db = object()
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    def _deny_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    fake_auth.require_admin = _deny_admin
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth)
    monkeypatch.delitem(sys.modules, "backend.admin_worker_router", raising=False)
    return importlib.import_module("backend.admin_worker_router")


def _request(app: FastAPI, method: str, path: str, payload: dict | None = None):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            kwargs = {"json": payload} if payload is not None else {}
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _build_app(fake_service, monkeypatch):
    admin_worker_router = _load_admin_worker_router(monkeypatch)
    admin_worker_router.worker_admin_service = fake_service
    admin_worker_router.log_action = lambda *args, **kwargs: None

    app = FastAPI()
    app.include_router(admin_worker_router.router)
    app.dependency_overrides[admin_worker_router.require_admin] = lambda: UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )
    return app


def test_admin_worker_groups_returns_items(monkeypatch):
    class FakeService:
        def list_worker_groups(self):
            return [
                {
                    "id": 3,
                    "group_key": "solver",
                    "name": "求解节点组",
                    "description": "求解器",
                    "max_claim_batch": 1,
                    "is_active": True,
                    "node_count": 2,
                    "active_node_count": 1,
                }
            ]

    app = _build_app(FakeService(), monkeypatch)
    response = _request(app, "GET", "/api/admin/workers/groups")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 3,
                "group_key": "solver",
                "name": "求解节点组",
                "description": "求解器",
                "max_claim_batch": 1,
                "is_active": True,
                "node_count": 2,
                "active_node_count": 1,
            }
        ]
    }


def test_admin_worker_nodes_returns_items(monkeypatch):
    class FakeService:
        def list_worker_nodes(self):
            return [
                {
                    "id": 8,
                    "group_id": 3,
                    "group_name": "求解节点组",
                    "display_name": "worker-8",
                    "expected_hostname": "solver-08",
                    "workspace_share": "\\\\server\\share",
                    "scratch_root": "D:/scratch",
                    "status": "active",
                    "last_heartbeat_at": "2026-04-18 10:00:00",
                    "latest_enrollment_status": "issued",
                    "software_ready_count": 1,
                    "software_total_count": 2,
                    "software_inventory": {},
                }
            ]

    app = _build_app(FakeService(), monkeypatch)
    response = _request(app, "GET", "/api/admin/workers/nodes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["id"] == 8
    assert payload["items"][0]["group_name"] == "求解节点组"
    assert payload["items"][0]["status"] == "active"


def test_admin_worker_groups_require_admin(monkeypatch):
    app = _build_app(fake_service=type("FakeService", (), {
        "list_worker_groups": lambda self: [],
        "list_worker_nodes": lambda self: [],
    })(), monkeypatch=monkeypatch)
    app.dependency_overrides = {}

    response = _request(app, "GET", "/api/admin/workers/groups")

    assert response.status_code == 403


def test_admin_worker_nodes_require_admin(monkeypatch):
    app = _build_app(fake_service=type("FakeService", (), {
        "list_worker_groups": lambda self: [],
        "list_worker_nodes": lambda self: [],
    })(), monkeypatch=monkeypatch)
    app.dependency_overrides = {}

    response = _request(app, "GET", "/api/admin/workers/nodes")

    assert response.status_code == 403
