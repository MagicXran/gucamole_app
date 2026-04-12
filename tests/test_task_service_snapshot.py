from pathlib import Path

import pytest

from backend.task_service import TaskService


class _TaskRepo:
    def get_script_launch_target(self, user_id, requested_runtime_id):
        return {
            "requested_runtime_id": requested_runtime_id,
            "pool_id": 4,
            "executor_key": "python_api",
            "app_id": 4,
            "binding_id": 6,
            "worker_group_id": 11,
            "runtime_config_json": None,
        }

    def list_worker_dispatch_nodes(self, worker_group_id):
        return [
            {
                "status": "active",
                "display_name": "worker-1",
                "supported_executor_keys_json": ["python_api"],
                "capabilities_json": {},
                "runtime_state_json": {},
            }
        ]

    def create_platform_task(self, payload):
        return {"id": 99, **payload}

    def insert_task_queue(self, payload):
        return payload


def test_submit_script_task_excludes_output_directory_from_snapshot(tmp_path, monkeypatch: pytest.MonkeyPatch):
    user_root = tmp_path / "portal_u1"
    user_root.mkdir()
    entry_file = user_root / "worker_smoke.py"
    entry_file.write_text("print('ok')\n", encoding="utf-8")
    (user_root / "input-data.txt").write_text("input\n", encoding="utf-8")
    (user_root / "Output").mkdir()
    (user_root / "Output" / "old-result.txt").write_text("old\n", encoding="utf-8")

    monkeypatch.setattr("backend.task_service._get_usage_sync", lambda user_id: 0)
    monkeypatch.setattr("backend.task_service._get_quota", lambda user_id: 10 * 1024 * 1024)

    service = TaskService(
        repo=_TaskRepo(),
        drive_root=tmp_path,
        task_id_factory=lambda: "task_test",
        results_root_name="Output",
    )

    created = service.submit_script_task(
        user_id=1,
        requested_runtime_id=4,
        entry_path="worker_smoke.py",
    )

    snapshot_root = user_root / "system" / "tasks" / "task_test" / "input"
    assert created["task_id"] == "task_test"
    assert (snapshot_root / "worker_smoke.py").exists()
    assert (snapshot_root / "input-data.txt").exists()
    assert not (snapshot_root / "Output").exists()
