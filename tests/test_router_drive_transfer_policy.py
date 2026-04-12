import importlib
import sys
import types
from types import SimpleNamespace

import pytest


def _load_router_module(
    app_disable_download,
    app_disable_upload,
    global_disable_download=True,
    global_disable_upload=True,
):
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def __init__(self):
            self.last_query = ""

        def execute_query(self, query, params):
            self.last_query = query
            return [{
                "id": 1,
                "hostname": "rdp.example.local",
                "port": 3389,
                "rdp_username": "",
                "rdp_password": "",
                "domain": "",
                "security": "nla",
                "ignore_cert": 1,
                "remote_app": "",
                "remote_app_dir": "",
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
                "disable_download": app_disable_download,
                "disable_upload": app_disable_upload,
            }]

    fake_database.db = FakeDb()
    fake_database.CONFIG = {
        "api": {"prefix": "/api/remote-apps"},
        "guacamole": {
            "json_secret_key": "00112233445566778899aabbccddeeff",
            "internal_url": "http://guac-web:8080/guacamole",
            "external_url": "http://portal.example/guacamole",
            "token_expire_minutes": 60,
            "drive": {
                "enabled": True,
                "name": "GuacDrive",
                "base_path": "/drive",
                "create_path": True,
                "disable_download": global_disable_download,
                "disable_upload": global_disable_upload,
            },
        },
    }
    sys.modules["backend.database"] = fake_database

    fake_auth = types.ModuleType("backend.auth")
    fake_auth.get_current_user = lambda: None
    sys.modules["backend.auth"] = fake_auth

    fake_audit = types.ModuleType("backend.audit")
    fake_audit.log_action = lambda *args, **kwargs: None
    sys.modules["backend.audit"] = fake_audit

    fake_guac_service = types.ModuleType("backend.guacamole_service")

    class FakeGuacamoleService:
        def __init__(self, *args, **kwargs):
            pass

    fake_guac_service.GuacamoleService = FakeGuacamoleService
    sys.modules["backend.guacamole_service"] = fake_guac_service

    fake_pool_service = types.ModuleType("backend.resource_pool_service")

    class FakeResourcePoolService:
        def __init__(self, *args, **kwargs):
            pass

    fake_pool_service.ResourcePoolService = FakeResourcePoolService
    sys.modules["backend.resource_pool_service"] = fake_pool_service

    sys.modules.pop("backend.router", None)
    return importlib.import_module("backend.router")


def test_build_all_connections_inherits_global_transfer_disable_flags():
    router_module = _load_router_module(None, None)

    connections = router_module._build_all_connections(7)
    params = connections["app_1"]["parameters"]

    assert "a.disable_download" in router_module.db.last_query
    assert "a.disable_upload" in router_module.db.last_query
    assert params["disable-download"] == "true"
    assert params["disable-upload"] == "true"


def test_build_all_connections_allows_per_app_transfer_override():
    router_module = _load_router_module(0, 0)

    connections = router_module._build_all_connections(7)
    params = connections["app_1"]["parameters"]

    assert "disable-download" not in params
    assert "disable-upload" not in params


def test_build_all_connections_enforces_per_app_disable_override():
    router_module = _load_router_module(
        1,
        1,
        global_disable_download=False,
        global_disable_upload=False,
    )

    connections = router_module._build_all_connections(7)
    params = connections["app_1"]["parameters"]

    assert params["disable-download"] == "true"
    assert params["disable-upload"] == "true"


def _load_admin_router_module():
    fake_database = types.ModuleType("backend.database")

    class FakeTransaction:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeDb:
        def __init__(self):
            self.insert_params = None
            self.update_params = None

        @staticmethod
        def transaction():
            return FakeTransaction()

        def execute_query(self, query, params=None, fetch_one=False, conn=None):
            if "FROM resource_pool" in query:
                return {"id": 1} if fetch_one else [{"id": 1}]
            if "SELECT * FROM remote_app WHERE name = %(name)s" in query:
                return {
                    "id": 9,
                    "name": params["name"],
                    "pool_id": 1,
                    "is_active": 1,
                }
            if "SELECT * FROM remote_app WHERE id = %(id)s" in query:
                return {
                    "id": params["id"],
                    "name": "demo-app",
                    "pool_id": 1,
                    "is_active": 1,
                }
            return {"id": 1} if fetch_one else []

        def execute_update(self, query, params, conn=None):
            if "INSERT INTO remote_app" in query:
                self.insert_params = dict(params)
            if "UPDATE remote_app SET" in query:
                self.update_params = dict(params)

    fake_db = FakeDb()
    fake_database.db = fake_db
    fake_database.CONFIG = {
        "api": {"prefix": "/api/admin"},
    }
    sys.modules["backend.database"] = fake_database

    fake_auth = types.ModuleType("backend.auth")
    fake_auth.require_admin = lambda: None
    sys.modules["backend.auth"] = fake_auth

    fake_audit = types.ModuleType("backend.audit")
    fake_audit.log_action = lambda *args, **kwargs: None
    sys.modules["backend.audit"] = fake_audit

    fake_router = types.ModuleType("backend.router")
    fake_router.guac_service = SimpleNamespace(invalidate_all_sessions=lambda: None)
    sys.modules["backend.router"] = fake_router

    fake_pool_service = types.ModuleType("backend.resource_pool_service")

    class FakeResourcePoolService:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def cleanup_invalid_queue_entries(**kwargs):
            return None

    fake_pool_service.ResourcePoolService = FakeResourcePoolService
    sys.modules["backend.resource_pool_service"] = fake_pool_service

    fake_script_profiles = types.ModuleType("backend.script_profiles")
    fake_script_profiles.get_script_profile = lambda *args, **kwargs: None
    fake_script_profiles.list_script_profiles = lambda: []
    fake_script_profiles.resolve_script_runtime_settings = (
        lambda **kwargs: {
            "executor_key": kwargs.get("script_executor_key"),
            "python_executable": kwargs.get("python_executable"),
            "python_env": kwargs.get("python_env"),
            "runtime_config": {},
        }
    )
    sys.modules["backend.script_profiles"] = fake_script_profiles

    sys.modules.pop("backend.admin_router", None)
    admin_module = importlib.import_module("backend.admin_router")

    admin_module._upsert_catalog_bindings = lambda *args, **kwargs: None
    admin_module._get_app_admin_row = lambda app_id, conn=None: {
        "id": app_id,
        "name": "demo-app",
        "disable_download": None,
        "disable_upload": None,
        "is_active": 1,
    }
    admin_module.guac_service = SimpleNamespace(invalidate_all_sessions=lambda: None)
    admin_module.pool_service = SimpleNamespace(cleanup_invalid_queue_entries=lambda **kwargs: None)

    return admin_module, fake_db


@pytest.mark.parametrize("policy_value", [None, 1, 0])
def test_admin_create_app_preserves_transfer_policy_values(policy_value):
    admin_module, fake_db = _load_admin_router_module()

    req = admin_module.AppCreateRequest(
        name=f"tri-state-create-{policy_value}",
        hostname="rdp.example.local",
        pool_id=1,
        disable_download=policy_value,
        disable_upload=policy_value,
    )
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    admin_module.create_app(req=req, request=request, admin=admin)

    assert fake_db.insert_params is not None
    assert fake_db.insert_params["disable_download"] == policy_value
    assert fake_db.insert_params["disable_upload"] == policy_value


@pytest.mark.parametrize("policy_value", [None, 1, 0])
def test_admin_update_app_preserves_transfer_policy_values(policy_value):
    admin_module, fake_db = _load_admin_router_module()

    req = admin_module.AppUpdateRequest(
        disable_download=policy_value,
        disable_upload=policy_value,
    )
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    admin_module.update_app(app_id=9, req=req, request=request, admin=admin)

    assert fake_db.update_params is not None
    assert fake_db.update_params["disable_download"] == policy_value
    assert fake_db.update_params["disable_upload"] == policy_value
