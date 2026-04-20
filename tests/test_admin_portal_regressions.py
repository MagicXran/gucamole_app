import importlib
import sys
import types
from types import SimpleNamespace


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
            self.user_insert_params = None
            self.user_update_params = None

        @staticmethod
        def transaction():
            return FakeTransaction()

        def execute_query(self, query, params=None, fetch_one=False, conn=None):
            if "FROM resource_pool" in query:
                return {"id": 1} if fetch_one else [{"id": 1}]
            if "SELECT 1 FROM portal_user WHERE username = %(u)s" in query:
                return None if fetch_one else []
            if "SELECT * FROM remote_app WHERE name = %(name)s" in query:
                return {
                    "id": 9,
                    "name": params["name"],
                    "pool_id": 1,
                    "is_active": 1,
                    "app_kind": params.get("app_kind", "commercial_software"),
                }
            if "SELECT * FROM remote_app WHERE id = %(id)s" in query:
                return {
                    "id": params["id"],
                    "name": "demo-app",
                    "pool_id": 1,
                    "is_active": 1,
                    "app_kind": "simulation_app",
                }
            if "SELECT id, username, display_name, department, is_admin, is_active FROM portal_user WHERE username = %(u)s" in query:
                return {
                    "id": 5,
                    "username": params["u"],
                    "display_name": "张三",
                    "department": "技术中心",
                    "is_admin": 0,
                    "is_active": 1,
                }
            if "SELECT * FROM portal_user WHERE id = %(id)s" in query:
                return {
                    "id": params["id"],
                    "username": "zhangsan",
                    "display_name": "张三",
                    "department": "技术中心",
                    "is_admin": 0,
                    "is_active": 1,
                }
            if "SELECT id, username, display_name, department, is_admin, is_active FROM portal_user WHERE id = %(id)s" in query:
                return {
                    "id": params["id"],
                    "username": "zhangsan",
                    "display_name": params.get("display_name", "张三"),
                    "department": params.get("department", "技术中心"),
                    "is_admin": params.get("is_admin", 0),
                    "is_active": params.get("is_active", 1),
                }
            return {"id": 1} if fetch_one else []

        def execute_update(self, query, params, conn=None):
            if "INSERT INTO remote_app" in query:
                self.insert_params = dict(params)
            if "UPDATE remote_app SET" in query:
                self.update_params = dict(params)
            if "INSERT INTO portal_user" in query:
                self.user_insert_params = dict(params)
            if "UPDATE portal_user SET" in query:
                self.user_update_params = dict(params)

    fake_db = FakeDb()
    fake_database.db = fake_db
    fake_database.CONFIG = {"api": {"prefix": "/api/admin"}}
    fake_database.get_config = lambda: fake_database.CONFIG
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
    fake_script_profiles.list_script_profiles = lambda *args, **kwargs: []
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
        "app_kind": "simulation_app",
        "disable_download": None,
        "disable_upload": None,
        "is_active": 1,
    }
    admin_module.guac_service = SimpleNamespace(invalidate_all_sessions=lambda: None)
    admin_module.pool_service = SimpleNamespace(cleanup_invalid_queue_entries=lambda **kwargs: None)

    return admin_module, fake_db


def _load_admin_pool_router_module():
    fake_database = types.ModuleType("backend.database")
    fake_database.db = object()
    fake_database.CONFIG = {"api": {"prefix": "/api/admin"}}
    fake_database.get_config = lambda: fake_database.CONFIG
    sys.modules["backend.database"] = fake_database

    fake_auth = types.ModuleType("backend.auth")
    fake_auth.require_admin = lambda: None
    sys.modules["backend.auth"] = fake_auth

    fake_audit = types.ModuleType("backend.audit")
    fake_audit.log_action = lambda *args, **kwargs: None
    sys.modules["backend.audit"] = fake_audit

    fake_monitor = types.ModuleType("backend.monitor")
    fake_monitor.invalidate_user_session_if_safe = lambda *args, **kwargs: None
    sys.modules["backend.monitor"] = fake_monitor

    fake_service_module = types.ModuleType("backend.resource_pool_service")
    fake_service_module.ResourcePoolService = lambda *args, **kwargs: SimpleNamespace(
        list_admin_pools=lambda: [],
        create_pool=lambda payload: payload,
        update_pool=lambda **kwargs: kwargs["payload"],
        list_admin_queues=lambda: [],
        cancel_queue_admin=lambda **kwargs: {"queue_id": kwargs["queue_id"], "status": "cancelled"},
        reclaim_session=lambda **kwargs: {"session_id": kwargs["session_id"], "user_id": 1},
    )
    sys.modules["backend.resource_pool_service"] = fake_service_module

    fake_attachment_service_module = types.ModuleType("backend.app_attachment_service")

    class FakeAttachmentService:
        def __init__(self, db):
            self.db = db
            self.calls = []

        def list_pool_attachments_for_admin(self, pool_id: int):
            self.calls.append(("list", pool_id))
            return {"pool_id": pool_id, "tutorial_docs": [], "video_resources": [], "plugin_downloads": []}

        def replace_pool_attachments(self, *, pool_id: int, payload: dict):
            self.calls.append(("replace", pool_id, payload))
            return {"pool_id": pool_id, **payload}

    fake_attachment_service_module.AppAttachmentService = FakeAttachmentService
    sys.modules["backend.app_attachment_service"] = fake_attachment_service_module

    sys.modules.pop("backend.admin_pool_router", None)
    return importlib.import_module("backend.admin_pool_router")


def test_admin_create_app_persists_app_kind():
    admin_module, fake_db = _load_admin_router_module()

    req = admin_module.AppCreateRequest(
        name="模拟应用",
        hostname="rdp.example.local",
        pool_id=1,
        app_kind="simulation_app",
    )
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(user_id=1, username="admin", display_name="管理员", is_admin=True)

    admin_module.create_app(req=req, request=request, admin=admin)

    assert fake_db.insert_params["app_kind"] == "simulation_app"


def test_admin_create_and_update_user_persist_department():
    admin_module, fake_db = _load_admin_router_module()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    admin = admin_module.UserInfo(user_id=1, username="admin", display_name="管理员", is_admin=True)

    create_req = admin_module.UserCreateRequest(
        username="zhangsan",
        password="123456",
        display_name="张三",
        department="技术中心",
    )
    admin_module.create_user(req=create_req, request=request, admin=admin)
    assert fake_db.user_insert_params["department"] == "技术中心"

    update_req = admin_module.UserUpdateRequest(display_name="张三-新", department="数智中心")
    admin_module.update_user(user_id=5, req=update_req, request=request, admin=admin)
    assert fake_db.user_update_params["department"] == "数智中心"


def test_admin_pool_router_exposes_pool_attachment_management_routes():
    module = _load_admin_pool_router_module()
    attachment_routes = [
        route for route in module.router.routes
        if route.path == "/api/admin/pools/{pool_id}/attachments"
    ]

    assert attachment_routes
    assert any("GET" in route.methods for route in attachment_routes)
    assert any(
        route.path == "/api/admin/pools/{pool_id}/attachments" and "PUT" in route.methods
        for route in module.router.routes
    )
