import importlib
import sys
import types
from types import SimpleNamespace


def _load_admin_router_module(monkeypatch):
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def __init__(self):
            self.query_log = []
            self.update_log = []
            self.users = {
                "alice": {
                    "id": 2,
                    "username": "alice",
                    "display_name": "Alice",
                    "department": "研发一部",
                    "is_admin": 0,
                    "is_active": 1,
                },
            }

        def execute_query(self, query, params=None, fetch_one=False, conn=None):
            self.query_log.append((query, dict(params or {}), fetch_one))
            if "SELECT 1 FROM portal_user WHERE username" in query:
                return None
            if "FROM portal_user WHERE username" in query:
                return self.users[params["u"]]
            if "SELECT * FROM portal_user WHERE id" in query:
                return {
                    "id": params["id"],
                    "username": "bob",
                    "display_name": "Bob",
                    "department": "销售部",
                    "is_admin": 0,
                    "is_active": 1,
                }
            if "FROM portal_user WHERE id" in query:
                return {
                    "id": params["id"],
                    "username": "bob",
                    "display_name": "Bob",
                    "department": "研发二部",
                    "is_admin": 1,
                    "is_active": 1,
                }
            if "FROM portal_user ORDER BY id" in query:
                return [
                    {
                        "id": 1,
                        "username": "admin",
                        "display_name": "管理员",
                        "department": "平台部",
                        "is_admin": 1,
                        "is_active": 1,
                        "quota_bytes": None,
                    }
                ]
            return {} if fetch_one else []

        def execute_update(self, query, params, conn=None):
            self.update_log.append((query, dict(params)))
            return 1

    fake_db = FakeDb()
    fake_database.db = fake_db
    fake_database.CONFIG = {"api": {"prefix": "/api/admin"}}
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)

    fake_auth = types.ModuleType("backend.auth")
    fake_auth.require_admin = lambda: None
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth)

    fake_audit = types.ModuleType("backend.audit")
    fake_audit.log_action = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "backend.audit", fake_audit)

    fake_router = types.ModuleType("backend.router")
    fake_router.guac_service = SimpleNamespace(invalidate_all_sessions=lambda: None)
    monkeypatch.setitem(sys.modules, "backend.router", fake_router)

    fake_file_router = types.ModuleType("backend.file_router")
    fake_file_router.DEFAULT_QUOTA_BYTES = 1024
    fake_file_router._format_bytes = lambda value: f"{value}B"
    fake_file_router._get_usage_sync = lambda user_id: 128
    monkeypatch.setitem(sys.modules, "backend.file_router", fake_file_router)

    fake_pool_service = types.ModuleType("backend.resource_pool_service")
    fake_pool_service.ResourcePoolService = lambda *args, **kwargs: SimpleNamespace(
        cleanup_invalid_queue_entries=lambda **kwargs: None
    )
    monkeypatch.setitem(sys.modules, "backend.resource_pool_service", fake_pool_service)

    fake_script_profiles = types.ModuleType("backend.script_profiles")
    fake_script_profiles.get_script_profile = lambda *args, **kwargs: None
    fake_script_profiles.list_script_profiles = lambda: []
    fake_script_profiles.resolve_script_runtime_settings = lambda **kwargs: {}
    monkeypatch.setitem(sys.modules, "backend.script_profiles", fake_script_profiles)

    monkeypatch.delitem(sys.modules, "backend.admin_router", raising=False)
    admin_module = importlib.import_module("backend.admin_router")
    return admin_module, fake_db


def _admin():
    return SimpleNamespace(user_id=1, username="root")


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def test_list_users_returns_department_from_portal_user(monkeypatch):
    admin_module, fake_db = _load_admin_router_module(monkeypatch)

    users = admin_module.list_users(admin=_admin())

    assert users[0]["department"] == "平台部"
    assert "department" in fake_db.query_log[0][0]


def test_create_user_persists_and_returns_department(monkeypatch):
    admin_module, fake_db = _load_admin_router_module(monkeypatch)
    req = admin_module.UserCreateRequest(
        username="alice",
        password="secret123",
        display_name="Alice",
        department="研发一部",
    )

    user = admin_module.create_user(req=req, request=_request(), admin=_admin())

    insert_sql, insert_params = fake_db.update_log[0]
    assert "department" in insert_sql
    assert insert_params["department"] == "研发一部"
    assert user["department"] == "研发一部"
    assert admin_module.UserAdminResponse(**user).department == "研发一部"


def test_update_user_updates_department(monkeypatch):
    admin_module, fake_db = _load_admin_router_module(monkeypatch)
    req = admin_module.UserUpdateRequest(department="研发二部")

    user = admin_module.update_user(user_id=2, req=req, request=_request(), admin=_admin())

    update_sql, update_params = fake_db.update_log[0]
    assert "department = %(department)s" in update_sql
    assert update_params["department"] == "研发二部"
    assert user["department"] == "研发二部"
