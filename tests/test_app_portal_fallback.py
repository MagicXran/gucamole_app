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


def test_root_and_admin_fall_back_to_legacy_frontend_when_portal_build_missing(tmp_path, monkeypatch):
    app_module = _load_app_module(monkeypatch)
    fake_backend_dir = tmp_path / "backend"
    fake_frontend_dir = tmp_path / "frontend"
    fake_backend_dir.mkdir()
    fake_frontend_dir.mkdir()
    (fake_frontend_dir / "index.html").write_text("Legacy Portal Index", encoding="utf-8")
    (fake_frontend_dir / "admin.html").write_text("Legacy Admin Page", encoding="utf-8")
    (fake_frontend_dir / "viewer.html").write_text("Legacy Viewer Page", encoding="utf-8")
    monkeypatch.setattr(app_module, "__file__", str(fake_backend_dir / "app.py"))

    response = _request(app_module.app, "GET", "/")
    assert response.status_code == 200
    assert "Legacy Portal Index" in response.text

    response = _request(app_module.app, "GET", "/index.html")
    assert response.status_code == 200
    assert "Legacy Portal Index" in response.text

    response = _request(app_module.app, "GET", "/admin.html")
    assert response.status_code == 200
    assert "Legacy Admin Page" in response.text
