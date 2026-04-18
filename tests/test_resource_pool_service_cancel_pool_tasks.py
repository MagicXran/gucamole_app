import importlib
import sys
import types
from contextlib import contextmanager


def _load_resource_pool_service():
    fake_database = types.ModuleType("backend.database")
    fake_database.CONFIG = {"monitor": {}}
    sys.modules["backend.database"] = fake_database
    sys.modules.pop("backend.resource_pool_service", None)
    return importlib.import_module("backend.resource_pool_service").ResourcePoolService


class FakeCancelTaskDb:
    def __init__(self):
        self.update_calls = []

    def execute_update(self, query: str, params=None):
        self.update_calls.append((query, params))
        return 1


def test_cancel_pool_tasks_cancels_queue_entries_and_requests_running_work_to_stop():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeCancelTaskDb()
    service = ResourcePoolService(db=db)

    cancelled = service.cancel_pool_tasks(pool_id=3, reason="pool_disabled")

    assert len(db.update_calls) == 2
    queued_query, queued_params = db.update_calls[0]
    running_query, running_params = db.update_calls[1]
    assert cancelled == 2

    assert "SET status = 'cancelled'" in queued_query
    assert "status IN ('queued', 'submitted')" in queued_query
    assert queued_params == {"pool_id": 3, "reason": "pool_disabled"}

    assert "SET cancel_requested = 1" in running_query
    assert "status = 'cancelled'" not in running_query
    assert "status IN ('assigned', 'preparing', 'running', 'uploading')" in running_query
    assert running_params == {"pool_id": 3, "reason": "pool_disabled"}


class FakeDispatchDb:
    def __init__(self, queue_mode: str):
        self.queue_mode = queue_mode
        self.ready_updates = []

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "/* rps:list_dispatch_pools */" in query:
            return [{"id": 3, "dispatch_grace_seconds": 120}]
        if "/* rps:list_expired_ready_entries */" in query:
            return []
        if "/* rps:get_pool_by_id */" in query:
            return {"id": 3, "max_concurrent": 1} if fetch_one else [{"id": 3, "max_concurrent": 1}]
        if "/* rps:get_pool_active_count */" in query:
            return {"active_count": 0} if fetch_one else [{"active_count": 0}]
        if "/* rps:get_pool_running_task_count */" in query:
            return {"task_count": 0} if fetch_one else [{"task_count": 0}]
        if "/* rps:get_pool_reserved_count */" in query:
            return {"ready_count": 0} if fetch_one else [{"ready_count": 0}]
        if "/* rps:get_queue_head */" in query:
            if self.queue_mode == "task":
                return None if "COALESCE(request_mode, 'gui') = 'gui'" in query else {"id": 11, "user_id": 7}
            return {"id": 12, "user_id": 7}
        if "/* rps:has_accessible_member */" in query:
            return {"ok": 1} if fetch_one else [{"ok": 1}]
        if "/* rps:list_pool_members_with_load */" in query:
            return [{
                "id": 99,
                "pool_id": 3,
                "member_max_concurrent": 1,
                "active_count": 0,
            }]
        return None if fetch_one else []

    def execute_update(self, query: str, params=None):
        if "/* rps:queue_mark_ready */" in query:
            self.ready_updates.append((query, params))
        return 1


class NoLockResourcePoolServiceMixin:
    @contextmanager
    def _pool_lock(self, pool_id: int):
        yield


def _new_no_lock_service(db):
    ResourcePoolService = _load_resource_pool_service()

    class NoLockResourcePoolService(NoLockResourcePoolServiceMixin, ResourcePoolService):
        pass

    return NoLockResourcePoolService(db=db)


def test_dispatch_ready_entries_leaves_task_queue_queued_for_worker_claim():
    db = FakeDispatchDb(queue_mode="task")
    service = _new_no_lock_service(db)

    moved = service.dispatch_ready_entries()

    assert moved == []
    assert db.ready_updates == []


def test_dispatch_ready_entries_still_marks_gui_queue_ready():
    db = FakeDispatchDb(queue_mode="gui")
    service = _new_no_lock_service(db)

    moved = service.dispatch_ready_entries()

    assert moved == [12]
    assert len(db.ready_updates) == 1
    ready_query, ready_params = db.ready_updates[0]
    assert "SET status = 'ready'" in ready_query
    assert ready_params["queue_id"] == 12
    assert ready_params["assigned_app_id"] == 99


class FakeCancelQueueAdminTaskDb:
    def __init__(self):
        self.update_calls = []

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "/* rps:get_queue_for_admin_cancel */" in query:
            assert params == {"queue_id": 42}
            return {"id": 42, "request_mode": "task", "platform_task_id": 77}
        return None if fetch_one else []

    def execute_update(self, query: str, params=None):
        self.update_calls.append((query, params))
        return 1


def test_cancel_queue_admin_cancels_associated_task_queue_platform_task():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeCancelQueueAdminTaskDb()
    service = ResourcePoolService(db=db)

    result = service.cancel_queue_admin(queue_id=42)

    assert result == {"queue_id": 42, "status": "cancelled"}
    assert len(db.update_calls) == 2
    queue_query, queue_params = db.update_calls[0]
    task_query, task_params = db.update_calls[1]
    assert "/* rps:cancel_queue_admin */" in queue_query
    assert queue_params == {"queue_id": 42}
    assert "UPDATE platform_task" in task_query
    assert "SET status = 'cancelled'" in task_query
    assert task_params == {"platform_task_id": 77, "reason": "admin"}


class FakeCreatePoolDb:
    def __init__(self):
        self.query_log = []
        self.last_insert_id = None

    def execute_update(self, query: str, params=None, conn=None):
        self.query_log.append(query)
        if "/* rps:create_pool */" in query:
            self.last_insert_id = 44
        return 1

    def execute_query(self, query: str, params=None, fetch_one: bool = False, conn=None):
        self.query_log.append(query)
        if "SELECT LAST_INSERT_ID() AS id" in query:
            return {"id": self.last_insert_id}
        if "/* rps:get_latest_pool_by_name */" in query:
            raise AssertionError("create_pool 不该再按 name 回捞最新资源池")
        if "/* rps:get_pool_admin */" in query:
            assert params == {"pool_id": 44}
            return {
                "id": 44,
                "name": "池子",
                "icon": "desktop",
                "max_concurrent": 2,
                "auto_dispatch_enabled": 1,
                "dispatch_grace_seconds": 120,
                "stale_timeout_seconds": 180,
                "idle_timeout_seconds": None,
                "is_active": 1,
            }
        return None if fetch_one else []


def test_create_pool_uses_last_insert_id_instead_of_name_lookup():
    ResourcePoolService = _load_resource_pool_service()
    db = FakeCreatePoolDb()
    service = ResourcePoolService(db=db)

    created = service.create_pool(
        {
            "name": "池子",
            "icon": "desktop",
            "max_concurrent": 2,
            "auto_dispatch_enabled": 1,
            "dispatch_grace_seconds": 120,
            "stale_timeout_seconds": 180,
            "idle_timeout_seconds": None,
            "is_active": 1,
        }
    )

    assert created["id"] == 44
    assert any("SELECT LAST_INSERT_ID() AS id" in query for query in db.query_log)
    assert all("/* rps:get_latest_pool_by_name */" not in query for query in db.query_log)
