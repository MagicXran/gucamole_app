import asyncio
import importlib
import sys
import types
from pathlib import Path

import httpx


class FakeDb:
    def execute_query(self, *args, **kwargs):
        return None if kwargs.get("fetch_one") else []

    def execute_update(self, *args, **kwargs):
        return 0


def _fake_config():
    return {
        "api": {
            "host": "127.0.0.1",
            "port": 8000,
            "prefix": "/api/remote-apps",
            "cors_origins": ["*"],
        },
        "auth": {
            "mode": "local",
            "jwt_secret": "test-secret-key-with-32-bytes-min!!",
            "token_expire_minutes": 480,
        },
        "guacamole": {
            "json_secret_key": "00112233445566778899aabbccddeeff",
            "internal_url": "http://guac-web:8080/guacamole",
            "external_url": "http://testserver/guacamole",
            "token_expire_minutes": 60,
            "drive": {"enabled": True, "base_path": "/drive", "name": "GuacDrive"},
        },
        "file_transfer": {},
        "monitor": {},
    }


def _load_app_module(monkeypatch):
    for module_name in list(sys.modules):
        if module_name.startswith("backend.") and module_name != "backend.config_loader":
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_database = types.ModuleType("backend.database")
    fake_database.db = FakeDb()
    fake_database.CONFIG = _fake_config()
    fake_database.get_config = lambda: fake_database.CONFIG
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)
    return importlib.import_module("backend.app")


def _request(app, method: str, path: str) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_health_endpoint_stays_backward_compatible(monkeypatch):
    app_module = _load_app_module(monkeypatch)

    response = _request(app_module.app, "GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_returns_200_when_schema_is_ready(monkeypatch):
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "check_live_schema",
        lambda: {
            "ok": True,
            "status": "ready",
            "checks": {
                "schema": {
                    "status": "ok",
                    "error_code": "",
                    "problems": [],
                }
            },
        },
        raising=False,
    )

    response = _request(app_module.app, "GET", "/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["schema"]["status"] == "ok"
    assert response.json()["checks"]["schema"]["problem_count"] == 0
    assert "problems" not in response.json()["checks"]["schema"]


def test_health_ready_returns_503_when_schema_is_incomplete(monkeypatch):
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "check_live_schema",
        lambda: {
            "ok": False,
            "status": "degraded",
            "checks": {
                "schema": {
                    "status": "fail",
                    "error_code": "schema_invalid",
                    "problems": ["missing table: portal_comment"],
                }
            },
        },
        raising=False,
    )

    response = _request(app_module.app, "GET", "/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["schema"]["error_code"] == "schema_invalid"
    assert response.json()["checks"]["schema"]["problem_count"] == 1
    assert "problems" not in response.json()["checks"]["schema"]


def test_lifespan_does_not_probe_live_schema(monkeypatch):
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "check_live_schema",
        lambda: (_ for _ in ()).throw(AssertionError("startup must not probe schema")),
        raising=False,
    )

    async def _run():
        async with app_module.lifespan(app_module.app):
            return None

    asyncio.run(_run())


def test_deploy_compose_healthcheck_uses_ready_probe():
    compose_text = Path("deploy/docker-compose.yml").read_text(encoding="utf-8")
    portal_backend_index = compose_text.index("portal-backend:")
    nginx_index = compose_text.index("nginx:")
    healthcheck_index = compose_text.index("healthcheck:", portal_backend_index, nginx_index)

    assert "/health/ready" in compose_text[healthcheck_index:nginx_index]
    assert "condition: service_healthy" in compose_text[nginx_index:]


def test_portal_dockerfile_copies_scripts_for_ready_probe():
    dockerfile_text = Path("deploy/portal.Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile_text.split("FROM python:3.11-slim", 1)[1]

    assert "COPY scripts/" in runtime_stage
