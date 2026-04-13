from datetime import datetime
from pathlib import Path
import io
import zipfile

import pytest
from pydantic import ValidationError

from backend.worker_agent import WorkerAgent
from backend.worker_service import WorkerService, WorkerTaskStatusRequest


class _FakeCredentialStore:
    def __init__(self):
        self.saved = None

    def load(self):
        return {
            "agent_id": "wrk_test",
            "access_token": "token",
            "worker_profile": {
                "scratch_root": "/tmp/worker-scratch",
                "workspace_share": "/tmp/worker-share-missing",
            },
        }

    def save(self, payload):
        self.saved = payload


class _FakePortalClient:
    def __init__(self):
        self.heartbeat_calls = []
        self.log_calls = []
        self.fail_calls = []
        self.snapshot_calls = []
        self.upload_calls = []
        self.upload_archive_entries = []
        self.complete_calls = []

    def heartbeat(self, token, payload):
        self.heartbeat_calls.append((token, payload))
        return {"ok": True}

    def pull_task(self, token):
        return {
            "task": {
                "task_id": "task_demo",
                "user_id": 1,
                "input_snapshot_path": "system/tasks/task_demo/input",
                "entry_path": "main.py",
            }
        }

    def append_task_logs(self, token, task_id, items):
        self.log_calls.append((token, task_id, items))
        return {"accepted": len(items)}

    def report_task_status(self, token, task_id, payload):
        return {"ok": True}

    def fail_task(self, token, task_id, payload):
        self.fail_calls.append((token, task_id, payload))
        return {"ok": True}

    def download_task_snapshot(self, token, task_id):
        self.snapshot_calls.append((token, task_id))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("main.py", "print('ok')\n")
        return buffer.getvalue()

    def upload_task_output_archive(self, token, task_id, archive_path):
        self.upload_calls.append((token, task_id, Path(archive_path).name))
        with zipfile.ZipFile(archive_path, "r") as archive:
            self.upload_archive_entries.append(sorted(archive.namelist()))
        return {"ok": True}

    def complete_task(self, token, task_id, payload):
        self.complete_calls.append((token, task_id, payload))
        return {"ok": True}


class _SnapshotFailingPortalClient(_FakePortalClient):
    def download_task_snapshot(self, token, task_id):
        self.snapshot_calls.append((token, task_id))
        raise FileNotFoundError("snapshot missing on portal")


def test_worker_task_status_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        WorkerTaskStatusRequest(status="potato")


def test_worker_agent_reports_stage_failure_with_log_items_list():
    portal = _SnapshotFailingPortalClient()
    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": "/tmp/worker-scratch",
            "workspace_share": "/tmp/worker-share-missing",
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
    )

    agent.run_once()

    assert len(portal.log_calls) == 1
    _, task_id, items = portal.log_calls[0]
    assert task_id == "task_demo"
    assert isinstance(items, list)
    assert items[0]["level"] == "error"
    assert "FileNotFoundError" in items[0]["message"]

    assert len(portal.fail_calls) == 1
    assert portal.fail_calls[0][1] == "task_demo"
    assert "FileNotFoundError" in portal.fail_calls[0][2]["error_message"]


class _RunnerThatWritesResult:
    def run(self, task, portal_client):
        scratch_dir = Path(task["scratch_path"])
        (scratch_dir / "result.txt").write_text("done\n", encoding="utf-8")
        portal_client.complete_task(
            task["task_id"],
            {
                "result_summary": {"returncode": 0},
                "artifacts": [
                    {
                        "artifact_kind": "workspace_output",
                        "display_name": "result.txt",
                        "relative_path": "result.txt",
                        "size_bytes": 5,
                    }
                ],
            },
        )


class _RunnerThatWritesNestedResultWithBackslashArtifact:
    def run(self, task, portal_client):
        scratch_dir = Path(task["scratch_path"])
        output_path = scratch_dir / "nested" / "result.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("done\n", encoding="utf-8")
        portal_client.complete_task(
            task["task_id"],
            {
                "result_summary": {"returncode": 0},
                "artifacts": [
                    {
                        "artifact_kind": "workspace_output",
                        "display_name": "nested\\result.txt",
                        "relative_path": "nested\\result.txt",
                        "size_bytes": 5,
                    }
                ],
            },
        )


def test_worker_agent_downloads_snapshot_and_uploads_outputs_without_workspace_share(tmp_path):
    portal = _FakePortalClient()
    scratch_root = tmp_path / "scratch"
    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": str(scratch_root),
            "workspace_share": str(tmp_path / "definitely-missing-share"),
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
        runner=_RunnerThatWritesResult(),
    )

    agent.run_once()

    assert portal.snapshot_calls == [("token", "task_demo")]
    assert portal.upload_calls == [("token", "task_demo", "task_demo-output.zip")]
    assert portal.upload_archive_entries == [["result.txt"]]
    assert portal.complete_calls
    payload = portal.complete_calls[0][2]
    assert payload["artifacts"][0]["relative_path"] == "Output/task_demo/result.txt"


class _FakeWorkerRepo:
    def __init__(self):
        self.failed = []

    def list_stalled_assigned_tasks(self, cutoff):
        return [
            {
                "task_id": "task_fail_me",
                "worker_node_id": 12,
                "runtime_state_json": {
                    "running_task_ids": [],
                    "occupied_slots": 0,
                    "available_slots": 1,
                },
                "last_error": "snapshot copy failed",
            },
            {
                "task_id": "task_skip_me",
                "worker_node_id": 12,
                "runtime_state_json": {
                    "running_task_ids": ["task_skip_me"],
                    "occupied_slots": 1,
                    "available_slots": 0,
                },
                "last_error": "",
            },
        ]

    def fail_stalled_assigned_task(self, task_id, worker_node_id, event_at, reason):
        self.failed.append((task_id, worker_node_id, event_at, reason))
        return {"task_id": task_id}


def test_worker_service_only_fails_truly_stalled_assigned_tasks():
    repo = _FakeWorkerRepo()
    service = WorkerService(repo=repo, now_provider=lambda: datetime(2026, 4, 8, 20, 0, 0))

    result = service.recover_stalled_assigned_tasks(timeout_seconds=30)

    assert result == {
        "stale_task_count": 2,
        "failed_task_ids": ["task_fail_me"],
        "skipped_task_ids": ["task_skip_me"],
    }
    assert repo.failed == [
        ("task_fail_me", 12, datetime(2026, 4, 8, 20, 0, 0), "snapshot copy failed")
    ]


class _TransferRepo:
    def __init__(self, task):
        self.task = task

    def get_auth_token_by_hash(self, _token_hash):
        return {"worker_node_id": 12, "status": "active"}

    def get_worker_node(self, worker_node_id):
        assert worker_node_id == 12
        return {"id": 12, "status": "active"}

    def get_task_for_worker(self, task_id, worker_node_id):
        assert task_id == self.task["task_id"]
        assert worker_node_id == 12
        return dict(self.task)


def test_worker_service_builds_snapshot_archive_and_stores_output_archive(tmp_path):
    task = {
        "id": 9,
        "task_id": "task_demo",
        "user_id": 3,
        "worker_node_id": 12,
        "status": "assigned",
        "input_snapshot_path": "system/tasks/task_demo/input",
    }
    source_root = tmp_path / "portal_u3" / "system" / "tasks" / "task_demo" / "input"
    source_root.mkdir(parents=True)
    (source_root / "main.py").write_text("print('ok')\n", encoding="utf-8")

    service = WorkerService(
        repo=_TransferRepo(task),
        now_provider=lambda: datetime(2026, 4, 9, 0, 0, 0),
        drive_root=tmp_path,
    )

    archive_bytes = service.download_task_snapshot("token", "task_demo")
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
        assert sorted(zf.namelist()) == ["main.py"]

    output_buffer = io.BytesIO()
    with zipfile.ZipFile(output_buffer, "w") as zf:
        zf.writestr("nested/result.txt", "done\n")

    result = service.store_task_output_archive("token", "task_demo", output_buffer.getvalue())

    assert result == {"output_root": "Output/task_demo", "file_count": 1}
    assert (tmp_path / "portal_u3" / "Output" / "task_demo" / "nested" / "result.txt").read_text(encoding="utf-8") == "done\n"


def test_worker_service_respects_custom_results_root(tmp_path, monkeypatch):
    task = {
        "id": 9,
        "task_id": "task_demo",
        "user_id": 3,
        "worker_node_id": 12,
        "status": "assigned",
        "input_snapshot_path": "system/tasks/task_demo/input",
    }
    source_root = tmp_path / "portal_u3" / "system" / "tasks" / "task_demo" / "input"
    source_root.mkdir(parents=True)
    (source_root / "main.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(
        "backend.worker_service.load_config",
        lambda: {"guacamole": {"drive": {"results_root": "Results"}}},
    )

    service = WorkerService(
        repo=_TransferRepo(task),
        now_provider=lambda: datetime(2026, 4, 9, 0, 0, 0),
        drive_root=tmp_path,
    )

    output_buffer = io.BytesIO()
    with zipfile.ZipFile(output_buffer, "w") as zf:
        zf.writestr("nested/result.txt", "done\n")

    result = service.store_task_output_archive("token", "task_demo", output_buffer.getvalue())

    assert result == {"output_root": "Results/task_demo", "file_count": 1}
    assert (tmp_path / "portal_u3" / "Results" / "task_demo" / "nested" / "result.txt").read_text(encoding="utf-8") == "done\n"


def test_worker_agent_respects_custom_results_root(tmp_path, monkeypatch):
    portal = _FakePortalClient()
    scratch_root = tmp_path / "scratch"
    monkeypatch.setattr(
        "backend.worker_agent.load_config",
        lambda: {"guacamole": {"drive": {"results_root": "Results"}}},
    )
    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": str(scratch_root),
            "workspace_share": str(tmp_path / "startup"),
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
        runner=_RunnerThatWritesResult(),
    )

    agent.run_once()

    payload = portal.complete_calls[0][2]
    assert payload["artifacts"][0]["relative_path"] == "Results/task_demo/result.txt"


def test_worker_agent_normalizes_backslash_artifact_paths(tmp_path, monkeypatch):
    portal = _FakePortalClient()
    scratch_root = tmp_path / "scratch"
    monkeypatch.setattr(
        "backend.worker_agent.load_config",
        lambda: {"guacamole": {"drive": {"results_root": "Results"}}},
    )
    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": str(scratch_root),
            "workspace_share": str(tmp_path / "startup"),
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
        runner=_RunnerThatWritesNestedResultWithBackslashArtifact(),
    )

    agent.run_once()

    payload = portal.complete_calls[0][2]
    assert payload["artifacts"][0]["relative_path"] == "Results/task_demo/nested/result.txt"


def test_worker_agent_falls_back_to_output_for_invalid_results_root(tmp_path, monkeypatch):
    portal = _FakePortalClient()
    scratch_root = tmp_path / "scratch"
    monkeypatch.setattr(
        "backend.worker_agent.load_config",
        lambda: {"guacamole": {"drive": {"results_root": "../escape"}}},
    )
    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": str(scratch_root),
            "workspace_share": str(tmp_path / "startup"),
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
        runner=_RunnerThatWritesResult(),
    )

    agent.run_once()

    payload = portal.complete_calls[0][2]
    assert payload["artifacts"][0]["relative_path"] == "Output/task_demo/result.txt"


def test_worker_agent_falls_back_to_output_when_load_config_fails(tmp_path, monkeypatch):
    portal = _FakePortalClient()
    scratch_root = tmp_path / "scratch"

    def _raise_missing_config():
        raise FileNotFoundError("config/config.json is missing")

    monkeypatch.setattr("backend.worker_agent.load_config", _raise_missing_config)

    agent = WorkerAgent(
        portal_client=portal,
        credential_store=_FakeCredentialStore(),
        registration_payload={
            "hostname": "worker-host",
            "machine_fingerprint": "fp-worker-host",
            "agent_version": "1.0.0",
            "os_type": "windows",
            "os_version": "Windows",
            "ip_addresses": ["127.0.0.1"],
            "scratch_root": str(scratch_root),
            "workspace_share": str(tmp_path / "startup"),
            "max_concurrent_tasks": 1,
            "supported_executor_keys": ["python_api"],
            "capabilities": {},
        },
        runner=_RunnerThatWritesResult(),
    )

    agent.run_once()

    payload = portal.complete_calls[0][2]
    assert payload["artifacts"][0]["relative_path"] == "Output/task_demo/result.txt"
