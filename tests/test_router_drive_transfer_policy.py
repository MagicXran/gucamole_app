import importlib
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.models import AppCreateRequest
from backend.vscode_policy_service import DEFAULT_PERMISSIONS


def _load_router_module(
    app_disable_download,
    app_disable_upload,
    global_disable_download=True,
    global_disable_upload=True,
    row_overrides=None,
):
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def __init__(self):
            self.last_query = ""

        def execute_query(self, query, params):
            self.last_query = query
            row = {
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
                "portal_username": "zhangsan",
                "portal_display_name": "张三",
                "security_mode": "admin_desktop",
                "vscode_control_profile_id": None,
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
            }
            row.update(row_overrides or {})
            return [row]

    fake_database.db = FakeDb()
    fake_database.CONFIG = {
        "api": {"prefix": "/api/remote-apps"},
        "guacamole": {
            "json_secret_key": "00112233445566778899aabbccddeeff",
            "internal_url": "http://guac-web:8080/guacamole",
            "external_url": "http://portal.example/guacamole",
            "token_expire_minutes": 60,
            "client_name": "用户空间",
            "drive": {
                "enabled": True,
                "name": "用户空间",
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


def test_restricted_remoteapp_forces_strict_channels():
    router_module = _load_router_module(
        0,
        0,
        global_disable_download=False,
        global_disable_upload=False,
        row_overrides={
            "security_mode": "restricted_remoteapp",
            "remote_app": "||notepad",
            "disable_copy": 0,
            "disable_paste": 0,
            "enable_printing": 1,
            "enable_audio_input": 1,
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]

    assert params["disable-copy"] == "true"
    assert params["disable-paste"] == "true"
    assert params["disable-download"] == "true"
    assert params["disable-upload"] == "true"
    assert "enable-printing" not in params
    assert "enable-audio-input" not in params


def test_remoteapp_uses_neutral_ascii_labels_for_default_directory():
    router_module = _load_router_module(
        0,
        0,
        row_overrides={
            "security_mode": "restricted_remoteapp",
            "remote_app": "||notepad",
            "remote_app_dir": "",
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]

    assert params["client-name"] == "用户空间"
    assert params["drive-name"] == "用户空间"
    assert params["drive-path"] == "/drive/portal_u7"
    assert params["remote-app-dir"] == r"\\tsclient\用户空间"


def test_rdp_drive_name_falls_back_to_ascii_for_unicode_or_unsafe_labels():
    router_module = _load_router_module(0, 0)

    assert router_module._build_rdp_drive_name("资料空间") == "用户空间"
    assert router_module._build_rdp_drive_name(" User Files & Data ") == "User_Files_Data"
    assert router_module._build_rdp_drive_name("***") == "用户空间"


def test_rdp_client_name_is_ascii_and_limited_to_31_characters():
    router_module = _load_router_module(0, 0)

    assert router_module._build_rdp_client_name("远程工作区") == "用户空间"
    assert router_module._build_rdp_client_name(" Engineering Workspace ") == "Engineering_Workspace"
    assert router_module._build_rdp_client_name("x" * 40) == "x" * 31


@pytest.mark.parametrize(
    "legacy_directory",
    [
        r"\\tsclient\GuacDrive",
        r"\\tsclient\用户数据目录",
        r"\\tsclient\UserFiles",
        r"\\tsclient\用户空间",
    ],
)
def test_remoteapp_normalizes_automatic_legacy_directories(legacy_directory):
    router_module = _load_router_module(
        0,
        0,
        row_overrides={
            "security_mode": "restricted_remoteapp",
            "remote_app": "||notepad",
            "remote_app_dir": legacy_directory,
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]
    assert params["remote-app-dir"] == r"\\tsclient\用户空间"


def test_remoteapp_preserves_explicit_application_directory():
    router_module = _load_router_module(
        0,
        0,
        row_overrides={
            "security_mode": "restricted_remoteapp",
            "remote_app": "||notepad",
            "remote_app_dir": r"C:\ApprovedWorkspace",
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]
    assert params["remote-app-dir"] == r"C:\ApprovedWorkspace"


def test_freecad_launcher_alias_keeps_per_user_drive_contract():
    router_module = _load_router_module(
        0,
        0,
        row_overrides={
            "security_mode": "restricted_remoteapp",
            "remote_app": "||portal-freecad",
            "remote_app_dir": "",
            "remote_app_args": "",
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]

    assert params["remote-app"] == "||portal-freecad"
    assert params["remote-app-dir"] == r"\\tsclient\用户空间"
    assert "remote-app-args" not in params
    assert params["drive-path"] == "/drive/portal_u7"


def test_restricted_vscode_expands_user_paths_and_uses_profile_channels():
    router_module = _load_router_module(
        1,
        1,
        row_overrides={
            "security_mode": "restricted_vscode",
            "remote_app": "||Visual Studio Code",
            "remote_app_args": "--user-data-dir=C:\\PortalProfiles\\{user_id}",
            "vscode_control_profile_id": 3,
            "vcp_id": 3,
            "vcp_profile_key": "default-controlled",
            "vcp_display_name": "默认受控开发模式",
            "vcp_description": "",
            "vcp_policy_version": 1,
            "vcp_is_active": 1,
            "vcp_revision": 1,
            "vcp_permissions_json": DEFAULT_PERMISSIONS,
            "vcp_allowed_shells_json": [r"C:\\Windows\\System32\\cmd.exe"],
            "vcp_allowed_tools_json": [r"C:\\Program Files\\Git\\cmd\\git.exe"],
            "vcp_allowed_debuggers_json": [r"C:\\Tools\\debugger.exe"],
            "vcp_allowed_extensions_json": ["ms-python.python"],
            "vcp_allowed_network_targets_json": ["https://packages.example.local"],
            "vcp_user_data_root": r"C:\\PortalProfiles",
            "vcp_extensions_root": r"C:\\PortalExtensions",
            "vcp_default_workspace_template": r"\\tsclient\{user_drive}",
            "vcp_created_at": None,
            "vcp_updated_at": None,
        },
    )

    params = router_module._build_all_connections(7)["app_1"]["parameters"]

    assert "{user_id}" not in params["remote-app-args"]
    assert r"C:\PortalProfiles\7" in params["remote-app-args"]
    assert r"C:\PortalExtensions\7" in params["remote-app-args"]
    assert r"\\tsclient\用户空间" in params["remote-app-args"]
    assert "disable-copy" not in params
    assert "disable-paste" not in params
    assert "disable-download" not in params
    assert "disable-upload" not in params
    assert params["enable-printing"] == "true"
    assert params["enable-audio-input"] == "true"


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
            if "FROM portal_user" in query:
                return {"id": params["id"], "username": "ordinary", "is_admin": 0}
            if "WHERE id IN" in query and "FROM remote_app" in query:
                return [{
                    "id": 3,
                    "name": "管理员桌面",
                    "remote_app": None,
                    "remote_app_args": None,
                    "security_mode": "admin_desktop",
                    "vscode_control_profile_id": None,
                }]
            if "SELECT * FROM remote_app WHERE name = %(name)s" in query:
                return {
                    "id": 9,
                    "name": params["name"],
                    "pool_id": 1,
                    "is_active": 1,
                    "security_mode": "admin_desktop",
                    "vscode_control_profile_id": None,
                    "remote_app": None,
                    "remote_app_args": None,
                }
            if "SELECT * FROM remote_app WHERE id = %(id)s" in query:
                return {
                    "id": params["id"],
                    "name": "demo-app",
                    "pool_id": 1,
                    "is_active": 1,
                    "security_mode": "admin_desktop",
                    "vscode_control_profile_id": None,
                    "remote_app": None,
                    "remote_app_args": None,
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
        security_mode="admin_desktop",
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


def test_admin_create_app_leaves_working_directory_for_runtime_user_expansion():
    req = AppCreateRequest(
        name="default-workdir",
        hostname="rdp.example.local",
        remote_app="||notepad",
    )

    assert req.remote_app_dir == ""


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


def test_admin_acl_rejects_admin_desktop_for_ordinary_user():
    admin_module, _ = _load_admin_router_module()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    with pytest.raises(HTTPException, match="普通用户不能授权管理员桌面") as exc_info:
        admin_module.update_user_acl(
            user_id=7,
            req=admin_module.AclUpdateRequest(app_ids=[3]),
            request=request,
            admin=admin,
        )

    assert exc_info.value.status_code == 400


def test_admin_create_restricted_app_rejects_empty_remote_app_with_400():
    admin_module, _ = _load_admin_router_module()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )

    with pytest.raises(HTTPException, match="必须配置非空 remote_app") as exc_info:
        admin_module.create_app(
            req=admin_module.AppCreateRequest(
                name="invalid-restricted-app",
                hostname="rdp.example.local",
            ),
            request=request,
            admin=admin,
        )

    assert exc_info.value.status_code == 400
