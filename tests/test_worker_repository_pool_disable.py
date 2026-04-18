from datetime import datetime

import pytest

from backend.worker_repository import MySQLWorkerRepository
from backend.worker_service import (
    WorkerService,
    WorkerServiceError,
    WorkerTaskCompleteRequest,
    WorkerTaskFailRequest,
    WorkerTaskStatusRequest,
)


class FakeWorkerRecoveryDb:
    def __init__(self):
        self.update_calls = []
        self.fetch_final_called = False

    def execute_update(self, query: str, params=None):
        self.update_calls.append((query, params))
        return 1

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "SELECT t.id, t.resource_pool_id" in query:
            return {
                "id": 12,
                "resource_pool_id": 3,
                "pool_active": 0,
                "queue_status": "cancelled",
            } if fetch_one else []
        if "SELECT *" in query and "FROM platform_task" in query:
            self.fetch_final_called = True
            return {"task_id": params["task_id"], "status": "cancelled"} if fetch_one else []
        if fetch_one:
            return None
        return []


def test_requeue_task_after_worker_loss_cancels_task_when_pool_inactive():
    db = FakeWorkerRecoveryDb()
    repo = MySQLWorkerRepository(db)

    result = repo.requeue_task_after_worker_loss("task_demo", 12)

    assert result == {"task_id": "task_demo", "status": "cancelled"}
    assert any("SET status = 'cancelled'" in query for query, _params in db.update_calls)
    assert any("status IN ('assigned', 'preparing', 'running', 'uploading')" in query for query, _params in db.update_calls)
    assert db.fetch_final_called is True


class FakeCancelRequestedDb:
    def __init__(self):
        self.update_calls = []
        self.task_by_status = {
            "status_update": {"task_id": "task_demo", "worker_node_id": 12, "id": 77, "status": "cancelled", "cancel_requested": 0},
            "complete": {"task_id": "task_demo", "worker_node_id": 12, "id": 77, "status": "cancelled", "cancel_requested": 0},
            "fail": {"task_id": "task_demo", "worker_node_id": 12, "id": 77, "status": "cancelled", "cancel_requested": 0},
        }

    def execute_update(self, query: str, params=None):
        self.update_calls.append((query, params))
        return 1

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "FROM platform_task" in query and "task_id = %(task_id)s" in query and fetch_one:
            status = None
            if params == {"task_id": "task_demo", "worker_node_id": 12}:
                status = self.task_by_status.get("status_update")
            return status
        return None if fetch_one else []


def test_cancel_task_if_requested_marks_task_cancelled_before_worker_can_overwrite():
    db = FakeCancelRequestedDb()
    repo = MySQLWorkerRepository(db)

    task = repo.cancel_task_if_requested("task_demo", 12, datetime(2026, 4, 16, 12, 0, 0))

    assert task == {"task_id": "task_demo", "worker_node_id": 12, "id": 77, "status": "cancelled", "cancel_requested": 0}
    assert len(db.update_calls) == 1
    query, params = db.update_calls[0]
    assert "SET status = 'cancelled'" in query
    assert "cancel_requested = 0" in query
    assert "cancel_requested = 1" in query
    assert params["task_id"] == "task_demo"
    assert params["worker_node_id"] == 12
    assert params["event_at"] == datetime(2026, 4, 16, 12, 0, 0)


class _CancelAwareRepo:
    def __init__(self):
        self.status_updates = []
        self.completions = []
        self.failures = []
        self.cancel_events = []

    def get_auth_token_by_hash(self, _token_hash):
        return {"worker_node_id": 12, "status": "active"}

    def get_worker_node(self, worker_node_id):
        assert worker_node_id == 12
        return {"id": 12, "status": "active"}

    def get_task_for_worker(self, task_id, worker_node_id):
        assert task_id == "task_demo"
        assert worker_node_id == 12
        return {
            "id": 77,
            "task_id": task_id,
            "worker_node_id": worker_node_id,
            "user_id": 3,
            "status": "running",
            "cancel_requested": 1,
            "input_snapshot_path": "system/tasks/task_demo/input",
        }

    def cancel_task_if_requested(self, task_id, worker_node_id, event_at):
        self.cancel_events.append((task_id, worker_node_id, event_at))
        return {
            "id": 77,
            "task_id": task_id,
            "worker_node_id": worker_node_id,
            "user_id": 3,
            "status": "cancelled",
            "cancel_requested": 0,
            "input_snapshot_path": "system/tasks/task_demo/input",
        }

    def update_task_status_for_worker(self, task_id, worker_node_id, payload, event_at):
        self.status_updates.append((task_id, worker_node_id, payload, event_at))
        return {"task_id": task_id}

    def complete_task_for_worker(self, task_id, worker_node_id, payload, event_at):
        self.completions.append((task_id, worker_node_id, payload, event_at))
        return {"task_id": task_id}

    def fail_task_for_worker(self, task_id, worker_node_id, payload, event_at):
        self.failures.append((task_id, worker_node_id, payload, event_at))
        return {"task_id": task_id}


@pytest.mark.parametrize(
    ("action", "request_factory"),
    [
        ("status", lambda service: service.report_task_status("token", "task_demo", WorkerTaskStatusRequest(status="running"))),
        ("complete", lambda service: service.complete_task("token", "task_demo", WorkerTaskCompleteRequest(result_summary={"ok": True}))),
        ("fail", lambda service: service.fail_task("token", "task_demo", WorkerTaskFailRequest(error_message="boom"))),
        ("upload", lambda service: service.store_task_output_archive("token", "task_demo", b"not-even-read")),
    ],
)
def test_worker_service_finalizes_cancel_requested_tasks_before_rejecting_worker_mutations(monkeypatch, action, request_factory):
    monkeypatch.setattr("backend.worker_service.load_config", lambda: {"guacamole": {"drive": {"base_path": "D:/drive"}}})
    repo = _CancelAwareRepo()
    service = WorkerService(repo=repo, now_provider=lambda: datetime(2026, 4, 16, 12, 30, 0))

    with pytest.raises(WorkerServiceError) as exc_info:
        request_factory(service)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "task_not_mutable"
    assert repo.cancel_events == [("task_demo", 12, datetime(2026, 4, 16, 12, 30, 0))]
    assert repo.status_updates == []
    assert repo.completions == []
    assert repo.failures == []


class _StatusWhitelistRepo:
    def __init__(self):
        self.status_updates = []

    def get_auth_token_by_hash(self, _token_hash):
        return {"worker_node_id": 12, "status": "active"}

    def get_worker_node(self, worker_node_id):
        assert worker_node_id == 12
        return {"id": 12, "status": "active"}

    def get_task_for_worker(self, task_id, worker_node_id):
        assert task_id == "task_demo"
        assert worker_node_id == 12
        return {
            "id": 77,
            "task_id": task_id,
            "worker_node_id": worker_node_id,
            "user_id": 3,
            "status": "running",
            "cancel_requested": 0,
            "input_snapshot_path": "system/tasks/task_demo/input",
        }

    def update_task_status_for_worker(self, task_id, worker_node_id, payload, event_at):
        self.status_updates.append((task_id, worker_node_id, payload, event_at))
        return {"task_id": task_id, "status": payload["status"]}


@pytest.mark.parametrize("terminal_status", ["succeeded", "failed", "cancelled"])
def test_worker_service_rejects_terminal_status_updates_via_status_endpoint(monkeypatch, terminal_status):
    monkeypatch.setattr("backend.worker_service.load_config", lambda: {"guacamole": {"drive": {"base_path": "D:/drive"}}})
    repo = _StatusWhitelistRepo()
    service = WorkerService(repo=repo, now_provider=lambda: datetime(2026, 4, 16, 13, 0, 0))

    with pytest.raises(WorkerServiceError) as exc_info:
        service.report_task_status("token", "task_demo", WorkerTaskStatusRequest(status=terminal_status))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "invalid_task_status"
    assert repo.status_updates == []


@pytest.mark.parametrize("transient_status", ["preparing", "running", "uploading"])
def test_worker_service_allows_transient_status_updates_via_status_endpoint(monkeypatch, transient_status):
    monkeypatch.setattr("backend.worker_service.load_config", lambda: {"guacamole": {"drive": {"base_path": "D:/drive"}}})
    repo = _StatusWhitelistRepo()
    service = WorkerService(repo=repo, now_provider=lambda: datetime(2026, 4, 16, 13, 0, 0))

    result = service.report_task_status("token", "task_demo", WorkerTaskStatusRequest(status=transient_status))

    assert result == {"task_id": "task_demo", "status": transient_status}
    assert repo.status_updates == [
        (
            "task_demo",
            12,
            {"status": transient_status, "scratch_path": None, "external_task_id": None},
            datetime(2026, 4, 16, 13, 0, 0),
        )
    ]
