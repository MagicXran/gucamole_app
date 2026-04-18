import asyncio
import importlib
from pathlib import Path
import sys
import types

import httpx
import pytest


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


def _load_app():
    fake_database = types.ModuleType("backend.database")
    fake_database.db = FakeDb()
    fake_database.CONFIG = _fake_config()
    sys.modules["backend.database"] = fake_database
    return importlib.import_module("backend.app").app


app = _load_app()


def _request(method: str, path: str) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def _require_portal_build():
    portal_index = Path(__file__).resolve().parent.parent / "frontend" / "portal" / "index.html"
    if not portal_index.exists():
        pytest.skip("Vue portal build output is required for SPA fallback test")


def test_portal_ui_serves_index_for_history_deep_link():
    _require_portal_build()

    response = _request("GET", "/portal/compute/commercial")

    assert response.status_code == 200
    assert "Portal UI Shell" in response.text
