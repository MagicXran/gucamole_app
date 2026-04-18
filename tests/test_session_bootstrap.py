import asyncio
import importlib
import sys
import types

import httpx
import jwt


class FakeDb:
    def __init__(self):
        self.users_by_id = {}

    def reset(self):
        self.users_by_id = {}

    def execute_query(self, *args, **kwargs):
        query = args[0] if args else ""
        params = args[1] if len(args) > 1 else {}
        if "/* identity:get_current_user */" in query:
            return self.users_by_id.get(int(params["user_id"]))
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


FAKE_DB = FakeDb()


def _load_app_and_auth():
    fake_database = types.ModuleType("backend.database")
    fake_database.db = FAKE_DB
    fake_database.CONFIG = _fake_config()
    sys.modules["backend.database"] = fake_database
    for module_name in [
        "backend.app",
        "backend.auth",
        "backend.identity_access",
        "backend.session_router",
        "backend.router",
        "backend.admin_router",
        "backend.admin_analytics_router",
        "backend.admin_analytics_service",
        "backend.admin_pool_router",
        "backend.admin_worker_router",
        "backend.app_attachment_router",
        "backend.booking_router",
        "backend.case_center_router",
        "backend.sdk_center_router",
        "backend.monitor",
        "backend.dataset_router",
        "backend.file_router",
        "backend.task_router",
        "backend.worker_monitor",
        "backend.worker_router",
    ]:
        sys.modules.pop(module_name, None)
    auth_module = importlib.import_module("backend.auth")
    app_module = importlib.import_module("backend.app")
    return app_module.app, auth_module


app, auth_module = _load_app_and_auth()
JWT_ALGORITHM = auth_module.JWT_ALGORITHM
JWT_SECRET = auth_module.JWT_SECRET


def setup_function():
    FAKE_DB.reset()


def _set_fake_user(user_id: int, username: str, display_name: str, is_admin: bool, is_active: int = 1):
    FAKE_DB.users_by_id[user_id] = {
        "id": user_id,
        "username": username,
        "display_name": display_name,
        "department": "研发一部" if is_admin else "",
        "is_admin": 1 if is_admin else 0,
        "is_active": is_active,
    }


def _request(method: str, path: str, headers: dict | None = None) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers)

    return asyncio.run(_run())


def test_session_bootstrap_route_exists():
    response = _request("GET", "/api/session/bootstrap")

    assert response.status_code == 200


def test_session_bootstrap_returns_expected_keys():
    response = _request("GET", "/api/session/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "authenticated",
        "user",
        "auth_source",
        "capabilities",
        "menu_tree",
        "org_context",
    }


def test_session_bootstrap_marks_missing_token_as_anonymous():
    response = _request("GET", "/api/session/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["auth_source"] == "anonymous"
    assert payload["user"] is None
    assert payload["capabilities"] == []
    assert payload["menu_tree"] == []


def test_session_bootstrap_handles_malformed_local_token_as_anonymous():
    token = jwt.encode({"user_id": 7}, JWT_SECRET, algorithm=JWT_ALGORITHM)

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is False
    assert payload["auth_source"] == "anonymous"
    assert payload["user"] is None


def test_session_bootstrap_returns_compute_first_and_my_routes_for_regular_user():
    _set_fake_user(7, "alice", "Alice", False)
    token = jwt.encode(
        {
            "user_id": 7,
            "username": "alice",
            "display_name": "Alice",
            "is_admin": False,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["auth_source"] == "local"
    assert payload["user"]["username"] == "alice"
    assert payload["capabilities"] == ["compute.view"]
    assert [item["key"] for item in payload["menu_tree"]] == ["compute", "my", "cases", "sdk"]
    assert [item["key"] for item in payload["menu_tree"][0]["children"]] == [
        "compute-commercial",
        "compute-simulation",
        "compute-tools",
    ]
    assert [item["path"] for item in payload["menu_tree"][1]["children"]] == [
        "/my/workspace",
        "/my/tasks",
        "/my/bookings",
    ]
    assert payload["menu_tree"][2]["key"] == "cases"
    assert payload["menu_tree"][2]["title"] == "任务案例"
    assert payload["menu_tree"][2]["path"] == "/cases"
    assert payload["menu_tree"][3]["key"] == "sdk"
    assert payload["menu_tree"][3]["title"] == "SDK中心"
    assert [item["path"] for item in payload["menu_tree"][3]["children"]] == [
        "/sdk/cloud",
        "/sdk/simulation-app",
    ]


def test_session_bootstrap_does_not_emit_dead_admin_routes_or_capabilities():
    _set_fake_user(1, "admin", "管理员", True)
    token = jwt.encode(
        {
            "user_id": 1,
            "username": "admin",
            "display_name": "管理员",
            "is_admin": True,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["capabilities"] == ["compute.view"]
    assert [item["key"] for item in payload["menu_tree"]] == ["compute", "my", "cases", "sdk", "admin"]
    assert [item["path"] for item in payload["menu_tree"][0]["children"]] == [
        "/compute/commercial",
        "/compute/simulation",
        "/compute/tools",
    ]
    assert [item["key"] for item in payload["menu_tree"][1]["children"]] == [
        "my-workspace",
        "my-tasks",
        "my-bookings",
    ]
    assert payload["menu_tree"][2]["key"] == "cases"
    assert payload["menu_tree"][2]["title"] == "任务案例"
    assert payload["menu_tree"][2]["path"] == "/cases"
    assert payload["menu_tree"][3]["key"] == "sdk"
    assert payload["menu_tree"][3]["title"] == "SDK中心"
    assert [item["key"] for item in payload["menu_tree"][3]["children"]] == [
        "sdk-cloud",
        "sdk-simulation-app",
    ]
    assert payload["menu_tree"][4]["key"] == "admin"
    assert payload["menu_tree"][4]["title"] == "系统管理"
    assert [item["path"] for item in payload["menu_tree"][4]["children"]] == [
        "/admin/apps",
        "/admin/queues",
        "/admin/monitor",
        "/admin/workers",
        "/admin/analytics",
    ]
    assert [item["title"] for item in payload["menu_tree"][4]["children"]] == [
        "App管理",
        "任务调度",
        "资源监控",
        "Worker状态",
        "统计看板",
    ]


def test_session_bootstrap_treats_disabled_token_user_as_anonymous():
    _set_fake_user(7, "alice", "Alice", False, is_active=0)
    token = jwt.encode(
        {
            "user_id": 7,
            "username": "alice",
            "display_name": "Alice",
            "is_admin": False,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is False


def test_session_bootstrap_keeps_admin_routes_hidden_for_regular_user():
    _set_fake_user(8, "bob", "Bob", False)
    token = jwt.encode(
        {
            "user_id": 8,
            "username": "bob",
            "display_name": "Bob",
            "is_admin": False,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert [item["key"] for item in payload["menu_tree"]] == ["compute", "my", "cases", "sdk"]
    assert payload["auth_source"] == "local"
    assert payload["user"] == {
        "user_id": 8,
        "username": "bob",
        "display_name": "Bob",
        "is_admin": False,
    }
    assert payload["capabilities"] == ["compute.view"]


def test_session_bootstrap_returns_current_user_state_after_admin_demotion():
    _set_fake_user(1, "admin", "普通用户", False)
    token = jwt.encode(
        {
            "user_id": 1,
            "username": "admin",
            "display_name": "旧管理员",
            "is_admin": True,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response = _request("GET", "/api/session/bootstrap", {"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["auth_source"] == "local"
    assert payload["user"] == {
        "user_id": 1,
        "username": "admin",
        "display_name": "普通用户",
        "is_admin": False,
    }
    assert payload["capabilities"] == ["compute.view"]
