import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

FAKE_CONFIG_SNIPPET = r"""
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
            "drive": {
                "enabled": True,
                "base_path": "/drive",
                "name": "GuacDrive",
                "results_root": "Output",
            },
        },
        "file_transfer": {},
        "monitor": {},
        "object_storage": {},
        "database": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "portal",
            "user": "portal",
            "password": "portal",
        },
    }
"""


def _run_snippet(snippet: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_import_backend_database_does_not_load_config():
    payload = _run_snippet(
        FAKE_CONFIG_SNIPPET
        + r"""
import importlib
import json
import backend.config_loader as config_loader

calls = 0
def fake_load_config():
    global calls
    calls += 1
    return _fake_config()

config_loader.load_config = fake_load_config
importlib.import_module("backend.database")
print(json.dumps({"calls": calls}))
"""
    )

    assert payload == {"calls": 0}


def test_backend_database_loads_config_only_on_first_get_config():
    payload = _run_snippet(
        FAKE_CONFIG_SNIPPET
        + r"""
import importlib
import json
import backend.config_loader as config_loader

calls = 0
def fake_load_config():
    global calls
    calls += 1
    return _fake_config()

config_loader.load_config = fake_load_config
database_module = importlib.import_module("backend.database")
first_host = database_module.get_config()["database"]["host"]
second_port = database_module.get_config()["database"]["port"]
print(json.dumps({"calls": calls, "host": first_host, "port": second_port}))
"""
    )

    assert payload == {"calls": 1, "host": "127.0.0.1", "port": 3306}


def test_import_backend_app_does_not_load_config_until_first_request():
    payload = _run_snippet(
        FAKE_CONFIG_SNIPPET
        + r"""
import asyncio
import importlib
import json
import httpx
import backend.config_loader as config_loader

calls = 0
def fake_load_config():
    global calls
    calls += 1
    return _fake_config()

config_loader.load_config = fake_load_config
app_module = importlib.import_module("backend.app")
calls_after_import = calls

async def run_request():
    transport = httpx.ASGITransport(app=app_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")

response = asyncio.run(run_request())
print(json.dumps({
    "calls_after_import": calls_after_import,
    "calls_after_request": calls,
    "status_code": response.status_code,
    "body": response.json(),
}))
"""
    )

    assert payload == {
        "calls_after_import": 0,
        "calls_after_request": 1,
        "status_code": 200,
        "body": {"status": "ok"},
    }
