import importlib
import sys
import types
from pathlib import Path

import pytest

from backend.models import (
    AppAdminResponse,
    AppCreateRequest,
    AppUpdateRequest,
    ResourcePoolCardResponse,
)
from backend.task_repository import MySQLTaskRepository


def _load_resource_pool_service():
    fake_database = types.ModuleType("backend.database")
    fake_database.CONFIG = {"monitor": {}}
    sys.modules["backend.database"] = fake_database
    sys.modules.pop("backend.resource_pool_service", None)
    return importlib.import_module("backend.resource_pool_service").ResourcePoolService


class FakeListUserPoolsDb:
    def __init__(self, app_kind):
        self.app_kind = app_kind
        self.last_list_query = ""
        self.running_task_count = 0

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "/* rps:list_user_pools */" in query:
            self.last_list_query = query
            return [{
                "launch_app_id": 9,
                "pool_id": 3,
                "name": "计算资源池",
                "icon": "calculate",
                "protocol": "rdp",
                "app_kind": self.app_kind,
                "supports_script": 1 if self.app_kind == "simulation_app" else 0,
                "script_runtime_id": 9 if self.app_kind == "simulation_app" else None,
                "worker_group_id": 11 if self.app_kind == "simulation_app" else None,
                "executor_key": "python_api" if self.app_kind == "simulation_app" else None,
                "runtime_config_json": None,
                "max_concurrent": 2,
                "active_count": 1,
                "queued_count": 0,
            }]
        if "/* rps:list_pool_members_with_load */" in query:
            return [{
                "id": 9,
                "pool_id": 3,
                "member_max_concurrent": 2,
                "active_count": 1,
            }]
        if "/* rps:get_pool_by_id */" in query:
            return {"id": 3, "max_concurrent": 2} if fetch_one else [{"id": 3, "max_concurrent": 2}]
        if "/* rps:get_pool_active_count */" in query:
            return {"active_count": 1} if fetch_one else [{"active_count": 1}]
        if "/* rps:get_pool_running_task_count */" in query:
            return {"task_count": self.running_task_count} if fetch_one else [{"task_count": self.running_task_count}]
        if "/* rps:get_pool_reserved_count */" in query:
            return {"ready_count": 0} if fetch_one else [{"ready_count": 0}]
        if "FROM worker_node" in query:
            return [{
                "status": "active",
                "display_name": "worker-1",
                "supported_executor_keys_json": ["python_api"],
                "capabilities_json": {},
                "runtime_state_json": {},
            }]
        if fetch_one:
            return None
        return []


class FakePrepareLaunchDb:
    def __init__(self):
        self.last_launch_query = ""

    def execute_query(self, query: str, params=None, fetch_one: bool = False, conn=None):
        if "/* rps:get_launch_target */" in query:
            self.last_launch_query = query
            return None if fetch_one else []
        if fetch_one:
            return None
        return []


class FakeTaskLaunchTargetDb:
    def __init__(self):
        self.last_query = ""

    def execute_query(self, query: str, params=None, fetch_one: bool = False, conn=None):
        if "FROM remote_app a" in query and "remote_app_script_profile sp" in query:
            self.last_query = query
            return None if fetch_one else []
        if fetch_one:
            return None
        return []


class FakeAccessibleMemberDb:
    def __init__(self):
        self.last_has_access_query = ""
        self.last_requested_query = ""
        self.task_cancel_queries = []

    def execute_query(self, query: str, params=None, fetch_one: bool = False, conn=None):
        if "/* rps:has_accessible_member */" in query:
            self.last_has_access_query = query
            return None if fetch_one else []
        if "/* rps:list_live_queues */" in query:
            return [{
                "id": 1,
                "pool_id": 2,
                "user_id": 7,
                "requested_app_id": 99,
                "assigned_app_id": None,
                "status": "queued",
                "platform_task_id": 55,
                "request_mode": "task",
            }]
        if "/* rps:get_launch_target */" in query:
            self.last_requested_query = query
            return None if fetch_one else []
        if fetch_one:
            return None
        return []

    def execute_update(self, query: str, params=None):
        if "UPDATE platform_task" in query:
            self.task_cancel_queries.append((query, params))
        return 1


@pytest.mark.parametrize("app_kind", ["commercial_software", "simulation_app", "compute_tool"])
def test_models_accept_supported_app_kind_values(app_kind):
    create_req = AppCreateRequest(
        name="模型校验",
        hostname="rdp.example.local",
        pool_id=1,
        app_kind=app_kind,
    )
    update_req = AppUpdateRequest(app_kind=app_kind)
    admin_resp = AppAdminResponse(
        id=1,
        name="模型校验",
        icon="desktop",
        protocol="rdp",
        hostname="rdp.example.local",
        port=3389,
        app_kind=app_kind,
    )
    pool_resp = ResourcePoolCardResponse(
        id=1,
        pool_id=1,
        name="模型校验",
        app_kind=app_kind,
    )

    assert create_req.app_kind == app_kind
    assert update_req.app_kind == app_kind
    assert admin_resp.app_kind == app_kind
    assert pool_resp.app_kind == app_kind


@pytest.mark.parametrize("model_factory", [
    lambda: AppCreateRequest(name="bad", hostname="rdp.example.local", pool_id=1, app_kind="bad_kind"),
    lambda: AppUpdateRequest(app_kind="bad_kind"),
    lambda: AppAdminResponse(
        id=1,
        name="bad",
        icon="desktop",
        protocol="rdp",
        hostname="rdp.example.local",
        port=3389,
        app_kind="bad_kind",
    ),
    lambda: ResourcePoolCardResponse(id=1, pool_id=1, name="bad", app_kind="bad_kind"),
])
def test_models_reject_unknown_app_kind(model_factory):
    with pytest.raises(ValueError):
        model_factory()


def test_resource_pool_service_list_user_pools_returns_app_kind_and_defaults_null():
    ResourcePoolService = _load_resource_pool_service()
    service = ResourcePoolService(db=FakeListUserPoolsDb(app_kind=None))

    rows = service.list_user_pools(user_id=7)

    assert rows == [{
        "id": 9,
        "pool_id": 3,
        "name": "计算资源池",
        "icon": "calculate",
        "protocol": "rdp",
        "app_kind": "commercial_software",
        "supports_gui": True,
        "supports_script": False,
        "script_runtime_id": None,
        "script_profile_key": None,
        "script_profile_name": None,
        "script_schedulable": False,
        "script_status_code": "",
        "script_status_label": "",
        "script_status_tone": "",
        "script_status_summary": "",
        "script_status_reason": "",
        "resource_status_code": "available",
        "resource_status_label": "可用",
        "resource_status_tone": "success",
        "active_count": 1,
        "queued_count": 0,
        "max_concurrent": 2,
        "has_capacity": True,
    }]


def test_resource_pool_service_list_user_pools_preserves_stored_app_kind():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeListUserPoolsDb(app_kind="compute_tool")
    service = ResourcePoolService(db=db)

    rows = service.list_user_pools(user_id=7)

    assert "COALESCE(a.app_kind, 'commercial_software')" in db.last_list_query
    assert "COUNT(DISTINCT COALESCE(a.app_kind, 'commercial_software'))" in db.last_list_query
    assert rows[0]["app_kind"] == "compute_tool"


def test_resource_pool_service_sets_script_and_resource_status_fields():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeListUserPoolsDb(app_kind="simulation_app")
    service = ResourcePoolService(db=db)

    rows = service.list_user_pools(user_id=7)

    assert rows[0]["supports_script"] is True
    assert rows[0]["script_runtime_id"] == 9
    assert rows[0]["script_schedulable"] is True
    assert rows[0]["script_status_code"] == "ready"
    assert rows[0]["script_status_label"] == "脚本可调度"
    assert rows[0]["resource_status_code"] == "available"
    assert rows[0]["resource_status_label"] == "可用"


def test_resource_pool_service_counts_running_script_tasks_in_pool_capacity():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeListUserPoolsDb(app_kind="commercial_software")
    db.running_task_count = 1
    service = ResourcePoolService(db=db)

    rows = service.list_user_pools(user_id=7)

    assert rows[0]["has_capacity"] is False
    assert rows[0]["resource_status_code"] == "busy"
    assert rows[0]["resource_status_label"] == "忙碌"


def test_prepare_launch_requires_active_pool_in_launch_target_query():
    ResourcePoolService = _load_resource_pool_service()
    db = FakePrepareLaunchDb()
    service = ResourcePoolService(db=db)

    with pytest.raises(ValueError):
        service.prepare_launch(user_id=7, requested_app_id=99)

    assert "p.is_active = 1" in db.last_launch_query


def test_task_repository_script_launch_target_requires_active_pool():
    db = FakeTaskLaunchTargetDb()
    repo = MySQLTaskRepository(db)

    assert repo.get_script_launch_target(user_id=7, requested_runtime_id=5) is None
    assert "p.is_active = 1" in db.last_query


def test_pool_access_queries_require_active_pool():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeAccessibleMemberDb()
    service = ResourcePoolService(db=db)

    assert service._has_accessible_member(user_id=7, pool_id=2) is False
    service.cleanup_invalid_queue_entries(pool_id=2)

    assert "p.is_active = 1" in db.last_has_access_query
    assert "p.is_active = 1" in db.last_requested_query
    assert db.task_cancel_queries


@pytest.mark.parametrize("sql_path", [
    Path("database/init.sql"),
    Path("deploy/initdb/01-portal-init.sql"),
    Path("database/migrate_remote_app_app_kind.sql"),
])
def test_sql_scripts_define_remote_app_app_kind(sql_path):
    sql = sql_path.read_text(encoding="utf-8")

    assert "app_kind" in sql
    assert "commercial_software" in sql


def test_app_kind_migration_avoids_mysql8_unsupported_add_column_if_not_exists():
    sql = Path("database/migrate_remote_app_app_kind.sql").read_text(encoding="utf-8")

    assert "information_schema.COLUMNS" in sql
    assert "ADD COLUMN IF NOT EXISTS" not in sql
