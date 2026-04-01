import asyncio
import json
import logging
from io import StringIO

import bcrypt
import httpx
from fastapi import FastAPI

import backend.app as backend_app
import backend.auth as backend_auth
import backend.router as backend_router
from backend.models import UserInfo
from backend.structured_logging import log_event


def _parse_structured_messages(caplog, logger_name: str, event: str):
    parsed = []
    for record in caplog.records:
        if record.name != logger_name:
            continue
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event:
            parsed.append(payload)
    return parsed


def _request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def test_request_access_log_is_json_with_request_id(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(backend_app, "ensure_bootstrap_admin", lambda _db: {"created": False})

    async def _run() -> httpx.Response:
        async with backend_app.app.router.lifespan_context(backend_app.app):
            transport = httpx.ASGITransport(app=backend_app.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/health", headers={"X-Request-ID": "req-123"})

    response = asyncio.run(_run())

    assert response.status_code == 200
    entries = _parse_structured_messages(caplog, "backend.app", "request_completed")
    assert entries
    entry = entries[-1]
    assert entry["request_id"] == "req-123"
    assert entry["path"] == "/health"
    assert entry["status_code"] == 200
    assert "duration_ms" in entry


def test_structured_log_formatter_emits_json_line():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.getLogger().handlers[0].formatter)
    logger = logging.getLogger("tests.structured")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_event(logger, logging.INFO, "test_event", request_id="req-456", path="/health")

    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "test_event"
    assert payload["request_id"] == "req-456"
    assert payload["path"] == "/health"


def test_login_log_does_not_leak_password_or_jwt(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    password = "super-secret-password"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    monkeypatch.setattr(
        backend_auth.db,
        "execute_query",
        lambda query, params=None, fetch_one=False: {
            "id": 7,
            "username": "tester",
            "password_hash": password_hash,
            "display_name": "Tester",
            "is_admin": False,
        },
    )
    monkeypatch.setattr(backend_auth, "log_action", lambda *args, **kwargs: None)

    app = FastAPI()
    app.include_router(backend_auth.router)

    response = _request(
        app,
        "POST",
        "/api/auth/login",
        json={"username": "tester", "password": password},
    )

    assert response.status_code == 200
    token = response.json()["token"]
    entries = _parse_structured_messages(caplog, "backend.auth", "login_succeeded")
    assert entries
    message = json.dumps(entries[-1], ensure_ascii=False)
    assert password not in message
    assert token not in message


def test_launch_queued_log_is_structured(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        backend_router.pool_service,
        "prepare_launch",
        lambda **kwargs: {"status": "queued", "queue_id": 12, "position": 3, "pool_id": 5},
    )
    app = FastAPI()
    app.include_router(backend_router.router)
    app.dependency_overrides[backend_router.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="Tester",
        is_admin=False,
    )

    response = _request(app, "POST", "/api/remote-apps/launch/101")

    assert response.status_code == 200
    entries = _parse_structured_messages(caplog, "backend.router", "launch_queued")
    assert entries
    entry = entries[-1]
    assert entry["user_id"] == 7
    assert entry["requested_app_id"] == 101
    assert entry["queue_id"] == 12
    assert entry["pool_id"] == 5
