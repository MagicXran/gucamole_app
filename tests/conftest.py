from __future__ import annotations

import importlib
import re
import sys
import types
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class FakeDB:
    def __init__(self) -> None:
        self._query_results: deque[Any] = deque()
        self._update_results: deque[int] = deque()
        self.executed_queries: list[tuple[str, dict[str, Any] | None, bool]] = []
        self.executed_updates: list[tuple[str, dict[str, Any] | None]] = []
        self.last_insert_table: str | None = None

    def queue_query_result(self, result: Any) -> None:
        self._query_results.append(result)

    def queue_update_result(self, rows: int) -> None:
        self._update_results.append(rows)

    def execute_query(self, query: str, params: dict[str, Any] | None = None, fetch_one: bool = False):
        self.executed_queries.append((query, params, fetch_one))
        if not self._query_results:
            raise AssertionError(f"FakeDB.execute_query missing queued result: {query!r}")
        result = self._query_results.popleft()
        if fetch_one:
            if isinstance(result, list):
                return result[0] if result else None
            return result
        return result

    def execute_update(self, query: str, params: dict[str, Any] | None = None):
        self.executed_updates.append((query, params))
        match = re.search(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE)
        if match:
            self.last_insert_table = match.group(1).lower()
        if self._update_results:
            return self._update_results.popleft()
        return 1


class FakeGuacService:
    def __init__(self) -> None:
        self.redirect_url = "http://portal.test/guacamole/#/client/app_1?token=fake"
        self.launch_calls: list[dict[str, Any]] = []
        self.invalidate_calls = 0

    async def launch_connection(self, **kwargs):
        self.launch_calls.append(kwargs)
        return self.redirect_url

    def invalidate_all_sessions(self):
        self.invalidate_calls += 1


TEST_CONFIG = {
    "api": {
        "prefix": "/api/remote-apps",
        "cors_origins": ["*"],
    },
    "auth": {
        "jwt_secret": "test-secret-key-0123456789abcdef",
        "token_expire_minutes": 480,
    },
    "guacamole": {
        "json_secret_key": "00" * 16,
        "internal_url": "http://guac-internal",
        "external_url": "http://portal.test/guacamole",
        "token_expire_minutes": 10,
        "drive": {
            "enabled": True,
            "name": "GuacDrive",
            "base_path": "/drive",
            "create_path": True,
        },
    },
    "monitor": {
        "session_timeout_seconds": 120,
    },
    "file_transfer": {
        "default_quota_gb": 10,
        "max_file_size_gb": 50,
        "chunk_size_mb": 10,
        "usage_cache_seconds": 60,
        "cleanup_stale_uploads_hours": 24,
    },
}


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def fake_guac_service():
    return FakeGuacService()


@pytest.fixture
def backend_modules(monkeypatch, fake_db, fake_guac_service):
    database_stub = types.ModuleType("backend.database")
    database_stub.db = fake_db
    database_stub.CONFIG = TEST_CONFIG
    database_stub.Database = object

    audit_stub = types.ModuleType("backend.audit")
    audit_stub.log_action = lambda *args, **kwargs: None

    monkeypatch.setitem(sys.modules, "backend.database", database_stub)
    monkeypatch.setitem(sys.modules, "backend.audit", audit_stub)

    for name in (
        "backend.auth",
        "backend.router",
        "backend.monitor",
        "backend.file_router",
        "backend.resource_governance",
    ):
        sys.modules.pop(name, None)

    auth_module = importlib.import_module("backend.auth")
    resource_governance_module = importlib.import_module("backend.resource_governance")
    router_module = importlib.import_module("backend.router")
    monitor_module = importlib.import_module("backend.monitor")
    file_router_module = importlib.import_module("backend.file_router")

    monkeypatch.setattr(router_module, "guac_service", fake_guac_service)

    return {
        "auth": auth_module,
        "resource_governance": resource_governance_module,
        "router": router_module,
        "monitor": monitor_module,
        "file_router": file_router_module,
    }


@pytest.fixture
def app(backend_modules):
    auth_module = backend_modules["auth"]
    router_module = backend_modules["router"]
    monitor_module = backend_modules["monitor"]
    file_router_module = backend_modules["file_router"]

    app = FastAPI()
    app.include_router(auth_module.router)
    app.include_router(router_module.router)
    app.include_router(monitor_module.router)
    app.include_router(monitor_module.admin_monitor_router)
    app.include_router(file_router_module.router)
    return app


@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://portal.test") as client:
        yield client


@pytest.fixture
def file_router_module(backend_modules):
    return backend_modules["file_router"]


def _make_token(secret: str, algorithm: str, user_id: int, username: str, display_name: str, is_admin: bool) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def auth_header(backend_modules):
    auth_module = backend_modules["auth"]
    token = _make_token(
        auth_module.JWT_SECRET,
        auth_module.JWT_ALGORITHM,
        7,
        "test",
        "测试用户",
        False,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_header(backend_modules):
    auth_module = backend_modules["auth"]
    token = _make_token(
        auth_module.JWT_SECRET,
        auth_module.JWT_ALGORITHM,
        1,
        "admin",
        "管理员",
        True,
    )
    return {"Authorization": f"Bearer {token}"}
