import importlib
import sys
import types

import pytest
from fastapi import HTTPException

from backend.models import AppCreateRequest, AppUpdateRequest, UserInfo


class DummyDB:
    def __init__(self):
        self.update_calls = []
        self.query_calls = []
        self.query_results = []

    def execute_update(self, query: str, params=None):
        self.update_calls.append((query, params))
        return 1

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        self.query_calls.append((query, params, fetch_one))
        if self.query_results:
            return self.query_results.pop(0)
        return None


class DummyGuacService:
    def __init__(self):
        self.invalidate_calls = 0

    def invalidate_all_sessions(self):
        self.invalidate_calls += 1


class DummyClient:
    host = "127.0.0.1"


class DummyRequest:
    client = DummyClient()


@pytest.fixture
def admin_env(monkeypatch):
    dummy_db = DummyDB()
    dummy_guac = DummyGuacService()
    actions = []

    def log_action(*args, **kwargs):
        actions.append((args, kwargs))

    monkeypatch.setitem(sys.modules, "backend.database", types.SimpleNamespace(db=dummy_db))
    monkeypatch.setitem(sys.modules, "backend.auth", types.SimpleNamespace(require_admin=lambda: None))
    monkeypatch.setitem(sys.modules, "backend.audit", types.SimpleNamespace(log_action=log_action))
    monkeypatch.setitem(sys.modules, "backend.router", types.SimpleNamespace(guac_service=dummy_guac))
    if "backend.admin_router" in sys.modules:
        del sys.modules["backend.admin_router"]

    admin_router = importlib.import_module("backend.admin_router")
    return admin_router, dummy_db, dummy_guac, actions


def test_create_app_builds_generic_template_payload(admin_env):
    admin_router, db, _, _ = admin_env
    req = AppCreateRequest(
        name="tool-app",
        icon="tool",
        protocol="rdp",
        hostname="10.0.0.1",
        port=3389,
        rdp_username="user",
        rdp_password="pass",
        domain="",
        security="nla",
        ignore_cert=True,
        remote_app="tool",
        launch_preset="generic_file_template",
        server_file_path="C:\\Data\\input.txt",
        launch_arg_template="--file {file}",
    )
    admin = UserInfo(user_id=1, username="admin", display_name="Admin", is_admin=True)
    db.query_results = [
        {"id": 99, "name": "tool-app"},
    ]

    admin_router.create_app(req, DummyRequest(), admin)

    params = db.update_calls[0][1]
    assert params["launch_preset"] == "generic_file_template"
    assert params["server_file_path"] == "C:\\Data\\input.txt"
    assert params["launch_arg_template"] == "--file {file}"
    assert params["remote_app_dir"] == "C:\\Data"
    assert params["remote_app_args"] == "--file C:\\Data\\input.txt"


def test_update_app_rebuilds_args_when_server_file_path_changes(admin_env):
    admin_router, db, _, _ = admin_env
    existing = {
        "id": 1,
        "name": "tool-app",
        "launch_preset": "generic_file_template",
        "remote_app": "tool",
        "server_file_path": "C:\\Old\\input.txt",
        "launch_arg_template": "run {file}",
        "remote_app_dir": "C:\\Old",
        "remote_app_args": "run C:\\Old\\input.txt",
    }
    db.query_results = [existing, existing]
    req = AppUpdateRequest(
        server_file_path="C:\\New\\input.txt",
    )
    admin = UserInfo(user_id=1, username="admin", display_name="Admin", is_admin=True)

    admin_router.update_app(1, req, DummyRequest(), admin)

    params = db.update_calls[0][1]
    assert params["launch_preset"] == "generic_file_template"
    assert params["server_file_path"] == "C:\\New\\input.txt"
    assert params["launch_arg_template"] == "run {file}"
    assert params["remote_app_dir"] == "C:\\New"
    assert params["remote_app_args"] == "run C:\\New\\input.txt"


def test_create_app_rejects_template_without_file_placeholder(admin_env):
    admin_router, db, _, _ = admin_env
    req = AppCreateRequest(
        name="tool-app",
        icon="tool",
        protocol="rdp",
        hostname="10.0.0.1",
        port=3389,
        rdp_username="user",
        rdp_password="pass",
        domain="",
        security="nla",
        ignore_cert=True,
        remote_app="tool",
        launch_preset="generic_file_template",
        server_file_path="C:\\Data\\input.txt",
        launch_arg_template="--file input.txt",
    )
    admin = UserInfo(user_id=1, username="admin", display_name="Admin", is_admin=True)
    db.query_results = [
        {"id": 99, "name": "tool-app"},
    ]

    with pytest.raises(HTTPException) as exc:
        admin_router.create_app(req, DummyRequest(), admin)

    assert exc.value.status_code == 422


def test_update_app_custom_with_stale_server_file_preserves_dir_and_args(admin_env):
    admin_router, db, _, _ = admin_env
    existing = {
        "id": 7,
        "name": "custom-app",
        "launch_preset": "custom",
        "remote_app": "||notepad",
        "server_file_path": None,
        "launch_arg_template": None,
        "remote_app_dir": " C:\\Work ",
        "remote_app_args": "  --foo bar  ",
    }
    db.query_results = [existing, existing]
    req = AppUpdateRequest(
        launch_preset="custom",
        server_file_path="C:\\Stale\\input.txt",
    )
    admin = UserInfo(user_id=1, username="admin", display_name="Admin", is_admin=True)

    admin_router.update_app(7, req, DummyRequest(), admin)

    params = db.update_calls[0][1]
    assert params["launch_preset"] == "custom"
    assert params["server_file_path"] is None
    assert params["launch_arg_template"] is None
    assert params["remote_app_dir"] == "C:\\Work"
    assert params["remote_app_args"] == "--foo bar"
