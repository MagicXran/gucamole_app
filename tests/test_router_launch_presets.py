import importlib
import sys
import types

import pytest


class FakeDb:
    def __init__(self):
        self.rows = []
        self.last_query = None

    def execute_query(self, query, params=None, fetch_one=False):
        self.last_query = query
        if fetch_one:
            return self.rows[0] if self.rows else None
        return self.rows

    def execute_update(self, query, params=None):
        return 0


def _load_router(monkeypatch):
    fake_db = FakeDb()
    fake_db_module = types.ModuleType("backend.database")
    fake_db_module.db = fake_db
    fake_db_module.CONFIG = {
        "api": {"prefix": "/api/remote-apps"},
        "guacamole": {
            "json_secret_key": "0" * 32,
            "internal_url": "http://guac-internal",
            "external_url": "http://guac-external",
            "token_expire_minutes": 5,
            "drive": {"enabled": False},
        },
    }
    monkeypatch.setitem(sys.modules, "backend.database", fake_db_module)

    fake_auth_module = types.ModuleType("backend.auth")

    def get_current_user():
        raise RuntimeError("get_current_user should not be called in tests")

    fake_auth_module.get_current_user = get_current_user
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth_module)

    fake_audit_module = types.ModuleType("backend.audit")

    def log_action(*args, **kwargs):
        return None

    fake_audit_module.log_action = log_action
    monkeypatch.setitem(sys.modules, "backend.audit", fake_audit_module)

    monkeypatch.delitem(sys.modules, "backend.router", raising=False)
    router = importlib.import_module("backend.router")
    return router, fake_db


def _base_row(**overrides):
    row = {
        "id": 1,
        "hostname": "rdp-host",
        "port": 3389,
        "rdp_username": "rdp-user",
        "rdp_password": "rdp-pass",
        "domain": "",
        "security": "nla",
        "ignore_cert": 1,
        "remote_app": "comsol",
        "remote_app_dir": "C:\\Program Files\\COMSOL",
        "remote_app_args": "",
        "color_depth": None,
        "disable_gfx": 1,
        "resize_method": "display-update",
        "enable_wallpaper": 0,
        "enable_font_smoothing": 1,
        "disable_copy": 0,
        "disable_paste": 0,
        "enable_audio": 1,
        "enable_audio_input": 0,
        "enable_printing": 0,
        "timezone": None,
        "keyboard_layout": None,
        "launch_preset": "none",
        "server_file_path": None,
        "launch_arg_template": None,
    }
    row.update(overrides)
    return row


def test_launch_query_ignores_metadata_columns(monkeypatch):
    router, fake_db = _load_router(monkeypatch)
    fake_db.rows = [_base_row()]
    router._build_all_connections(user_id=1)
    assert fake_db.last_query is not None
    query_lower = fake_db.last_query.lower()
    assert "remote_app_args" in query_lower
    assert "launch_preset" not in query_lower
    assert "server_file_path" not in query_lower
    assert "launch_arg_template" not in query_lower


def test_comsol_open_file_args_preserved(monkeypatch):
    router, fake_db = _load_router(monkeypatch)
    expected_args = "\"C:\\\\Data\\\\model.mph\" -batch"
    fake_db.rows = [
        _base_row(
            remote_app_args=expected_args,
            launch_preset="comsol_open_file",
            server_file_path="C:\\Data\\model.mph",
            launch_arg_template="\"{file}\" -batch",
        )
    ]
    connections = router._build_all_connections(user_id=7)
    params = connections["app_1"]["parameters"]
    assert params["remote-app-args"] == expected_args


def test_generic_file_template_args_preserved(monkeypatch):
    router, fake_db = _load_router(monkeypatch)
    expected_args = "--open \"D:\\\\Files\\\\sample.step\" --fullscreen"
    fake_db.rows = [
        _base_row(
            id=2,
            remote_app="generic_viewer",
            remote_app_args=expected_args,
            remote_app_dir="D:\\Tools\\Viewer",
            launch_preset="generic_file_template",
            server_file_path="D:\\Files\\sample.step",
            launch_arg_template="--open \"{file}\" --fullscreen",
        )
    ]
    connections = router._build_all_connections(user_id=9)
    params = connections["app_2"]["parameters"]
    assert params["remote-app-args"] == expected_args
