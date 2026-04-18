"""
Worker enrollment, authentication, heartbeat, and task-claim orchestration.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path, PurePosixPath
from secrets import token_urlsafe
from typing import Any, BinaryIO, Callable

from pydantic import BaseModel, Field

from backend.config_loader import load_config


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15
DEFAULT_PULL_INTERVAL_SECONDS = 5
WORKER_MUTABLE_TASK_STATUSES = {"assigned", "preparing", "running", "uploading"}
WORKER_TRANSIENT_STATUS_UPDATES = {"preparing", "running", "uploading"}


class WorkerServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class WorkerRegistrationRequest(BaseModel):
    enrollment_token: str = Field(..., min_length=1, max_length=255)
    hostname: str = Field(..., min_length=1, max_length=255)
    machine_fingerprint: str = Field(..., min_length=1, max_length=128)
    agent_version: str = Field(..., min_length=1, max_length=50)
    os_type: str = Field(..., min_length=1, max_length=50)
    os_version: str = Field(default="", max_length=100)
    ip_addresses: list[str] = Field(default_factory=list)
    scratch_root: str = Field(..., min_length=1, max_length=500)
    workspace_share: str = Field(..., min_length=1, max_length=500)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=9999)
    supported_executor_keys: list[str] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkerHeartbeatRequest(BaseModel):
    running_task_ids: list[str] = Field(default_factory=list)
    occupied_slots: int = Field(default=0, ge=0)
    available_slots: int = Field(default=0, ge=0)
    last_error_summary: str = Field(default="", max_length=500)
    software_inventory: dict[str, Any] = Field(default_factory=dict)


class WorkerTaskStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)
    scratch_path: str | None = Field(default=None, max_length=1000)
    external_task_id: str | None = Field(default=None, max_length=200)


class WorkerTaskLogItem(BaseModel):
    seq_no: int = Field(..., ge=1)
    level: str = Field(default="info", max_length=20)
    message: str = Field(..., min_length=1)


class WorkerTaskLogRequest(BaseModel):
    items: list[WorkerTaskLogItem] = Field(default_factory=list)


class WorkerTaskArtifactItem(BaseModel):
    artifact_kind: str = Field(..., min_length=1, max_length=30)
    display_name: str = Field(..., min_length=1, max_length=255)
    relative_path: str | None = Field(default=None, max_length=1000)
    minio_bucket: str | None = Field(default=None, max_length=255)
    minio_object_key: str | None = Field(default=None, max_length=1000)
    external_url: str | None = Field(default=None, max_length=1000)
    size_bytes: int | None = Field(default=None, ge=0)


class WorkerTaskCompleteRequest(BaseModel):
    result_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[WorkerTaskArtifactItem] = Field(default_factory=list)


class WorkerTaskFailRequest(BaseModel):
    error_message: str = Field(..., min_length=1, max_length=500)


@dataclass
class WorkerService:
    repo: Any
    now_provider: Callable[[], datetime] | None = None
    token_factory: Callable[[], str] | None = None
    drive_root: str | Path | None = None

    def __post_init__(self):
        self._now_provider = self.now_provider or datetime.now
        self._token_factory = self.token_factory or (lambda: token_urlsafe(32))
        config = load_config()
        default_drive_root = config.get("guacamole", {}).get("drive", {}).get("base_path", "/drive")
        self._drive_root = Path(self.drive_root or default_drive_root)

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _value(obj: Any, key: str, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _ensure_task_mutable(task: Any) -> None:
        status = str(WorkerService._value(task, "status", "") or "")
        if status not in WORKER_MUTABLE_TASK_STATUSES:
            raise WorkerServiceError(409, "task_not_mutable", "worker task already finished")

    @staticmethod
    def _ensure_status_update_allowed(status: str) -> None:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in WORKER_TRANSIENT_STATUS_UPDATES:
            raise WorkerServiceError(400, "invalid_task_status", "worker status updates only accept transient statuses")

    @staticmethod
    def _safe_relative_path(value: str | None) -> Path:
        normalized = PurePosixPath(str(value or "").strip())
        if not normalized.parts:
            raise WorkerServiceError(400, "invalid_task_path", "task path is empty")
        if normalized.is_absolute() or ".." in normalized.parts:
            raise WorkerServiceError(400, "invalid_task_path", "task path escapes the workspace root")
        return Path(*normalized.parts)

    def _user_root(self, user_id: int) -> Path:
        return (self._drive_root / f"portal_u{user_id}").resolve()

    def _resolve_task_snapshot_dir(self, task: Any) -> Path:
        user_root = self._user_root(int(self._value(task, "user_id")))
        relative_snapshot = self._safe_relative_path(self._value(task, "input_snapshot_path"))
        snapshot_dir = (user_root / relative_snapshot).resolve()
        try:
            snapshot_dir.relative_to(user_root)
        except ValueError as exc:
            raise WorkerServiceError(400, "invalid_task_path", "task snapshot path escapes the user workspace") from exc
        if not snapshot_dir.exists() or not snapshot_dir.is_dir():
            raise WorkerServiceError(404, "task_snapshot_not_found", "task snapshot does not exist")
        return snapshot_dir

    def _resolve_task_output_dir(self, task: Any) -> Path:
        user_root = self._user_root(int(self._value(task, "user_id")))
        output_dir = (user_root / "Output" / str(self._value(task, "task_id"))).resolve()
        try:
            output_dir.relative_to(user_root)
        except ValueError as exc:
            raise WorkerServiceError(400, "invalid_task_path", "task output path escapes the user workspace") from exc
        return output_dir

    def register_worker(self, req: WorkerRegistrationRequest, *, client_ip: str) -> dict[str, Any]:
        enrollment = self.repo.get_enrollment_by_hash(self.hash_token(req.enrollment_token))
        if not enrollment:
            raise WorkerServiceError(401, "invalid_enrollment_token", "enrollment token is invalid")

        node = self.repo.get_worker_node(int(self._value(enrollment, "worker_node_id")))
        if not node:
            raise WorkerServiceError(409, "worker_identity_conflict", "worker node is missing")

        now = self._now()
        expires_at = self._value(enrollment, "expires_at")
        if expires_at and expires_at < now:
            raise WorkerServiceError(403, "enrollment_token_not_usable", "enrollment token is expired or already consumed")

        self._validate_registration_identity(node, req)

        status = str(self._value(enrollment, "status", "") or "")
        if status == "consumed":
            return {
                "agent_id": str(self._value(node, "agent_id")),
                "already_registered": True,
                "message": "worker already registered; re-enrollment required to issue a new token",
            }
        if status != "issued":
            raise WorkerServiceError(403, "enrollment_token_not_usable", "enrollment token is expired or already consumed")

        if str(self._value(node, "status", "") or "") not in {"pending_enrollment", "active"}:
            raise WorkerServiceError(409, "worker_identity_conflict", "worker node is not available for enrollment")

        payload = req.model_dump()
        activated_node = self.repo.activate_worker_node(
            int(self._value(node, "id")),
            payload,
            now,
            client_ip,
        )
        self.repo.consume_enrollment(int(self._value(enrollment, "id")), client_ip, now)

        access_token = self._token_factory()
        self.repo.rotate_worker_token(int(self._value(node, "id")), self.hash_token(access_token), now)
        return {
            "agent_id": str(self._value(activated_node, "agent_id", self._value(node, "agent_id"))),
            "access_token": access_token,
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            "pull_interval_seconds": DEFAULT_PULL_INTERVAL_SECONDS,
            "portal_time": now.isoformat(),
            "worker_profile": {
                "display_name": self._value(activated_node, "display_name", None),
                "group_id": int(self._value(activated_node, "group_id", self._value(node, "group_id"))),
                "expected_hostname": str(self._value(activated_node, "expected_hostname", self._value(node, "expected_hostname"))),
                "workspace_share": str(self._value(activated_node, "workspace_share", req.workspace_share)),
                "scratch_root": str(self._value(activated_node, "scratch_root", req.scratch_root)),
                "max_concurrent_tasks": int(self._value(activated_node, "max_concurrent_tasks", req.max_concurrent_tasks)),
            },
        }

    def _validate_registration_identity(self, node: Any, req: WorkerRegistrationRequest) -> None:
        if str(self._value(node, "expected_hostname", "") or "") != req.hostname:
            raise WorkerServiceError(409, "worker_identity_conflict", "hostname or machine fingerprint does not match the expected node")

        registered_hostname = str(self._value(node, "hostname", "") or "")
        registered_fp = str(self._value(node, "machine_fingerprint", "") or "")
        if registered_hostname and registered_hostname != req.hostname:
            raise WorkerServiceError(409, "worker_identity_conflict", "hostname or machine fingerprint does not match the expected node")
        if registered_fp and registered_fp != req.machine_fingerprint:
            raise WorkerServiceError(409, "worker_identity_conflict", "hostname or machine fingerprint does not match the expected node")

        expected_workspace_share = str(self._value(node, "workspace_share", "") or "")
        if expected_workspace_share and expected_workspace_share != req.workspace_share:
            raise WorkerServiceError(409, "worker_identity_conflict", "workspace share does not match the expected node")

        expected_scratch_root = str(self._value(node, "scratch_root", "") or "")
        if expected_scratch_root and expected_scratch_root != req.scratch_root:
            raise WorkerServiceError(409, "worker_identity_conflict", "scratch root does not match the expected node")

        if req.os_type.lower() != "windows":
            raise WorkerServiceError(400, "invalid_request", "os_type must be windows")

    def heartbeat(self, access_token: str, req: WorkerHeartbeatRequest, *, client_ip: str) -> dict[str, Any]:
        _, node = self._authenticate_worker(access_token)

        updated_node = self.repo.update_worker_heartbeat(
            int(self._value(node, "id")),
            req.model_dump(),
            self._now(),
            client_ip,
        )
        return {
            "ok": True,
            "worker_status": str(self._value(updated_node, "status", self._value(node, "status"))),
            "heartbeat_interval_seconds": DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
            "pull_interval_seconds": DEFAULT_PULL_INTERVAL_SECONDS,
            "cancel_task_ids": list(self.repo.list_cancel_requested_task_ids(int(self._value(node, "id")))),
        }

    def pull_task(self, access_token: str, *, client_ip: str) -> dict[str, Any]:
        _auth_token, node = self._authenticate_worker(access_token)
        active_count = int(self.repo.count_worker_active_tasks(int(self._value(node, "id"))))
        if active_count >= int(self._value(node, "max_concurrent_tasks", 1) or 1):
            return {"task": None, "pull_interval_seconds": DEFAULT_PULL_INTERVAL_SECONDS}

        supported_executor_keys = list(self._value(node, "supported_executor_keys_json", []) or [])
        task = self.repo.claim_next_task_for_worker(
            int(self._value(node, "id")),
            int(self._value(node, "group_id", 0) or 0),
            supported_executor_keys,
            self._now(),
        )
        return {
            "task": task,
            "pull_interval_seconds": DEFAULT_PULL_INTERVAL_SECONDS,
        }

    def _authenticate_worker(self, access_token: str) -> tuple[Any, Any]:
        auth_token = self.repo.get_auth_token_by_hash(self.hash_token(access_token))
        if not auth_token:
            raise WorkerServiceError(401, "invalid_worker_token", "worker token is invalid")
        if str(self._value(auth_token, "status", "") or "") != "active":
            raise WorkerServiceError(403, "worker_not_active", "worker token is not active")

        node = self.repo.get_worker_node(int(self._value(auth_token, "worker_node_id")))
        if not node:
            raise WorkerServiceError(403, "worker_not_active", "worker node is not active")
        if str(self._value(node, "status", "") or "") in {"disabled", "revoked"}:
            raise WorkerServiceError(403, "worker_not_active", "worker node is not active")
        return auth_token, node

    def _get_owned_task(self, access_token: str, task_id: str) -> tuple[Any, Any]:
        _auth_token, node = self._authenticate_worker(access_token)
        task = self.repo.get_task_for_worker(task_id, int(self._value(node, "id")))
        if not task:
            raise WorkerServiceError(404, "task_not_found", "worker task does not exist")
        return node, task

    def _get_mutable_owned_task(self, access_token: str, task_id: str) -> tuple[Any, Any]:
        node, task = self._get_owned_task(access_token, task_id)
        if bool(self._value(task, "cancel_requested", 0)):
            task = self.repo.cancel_task_if_requested(
                task_id,
                int(self._value(node, "id")),
                self._now(),
            ) or task
        self._ensure_task_mutable(task)
        return node, task

    def report_task_status(self, access_token: str, task_id: str, req: WorkerTaskStatusRequest) -> dict[str, Any]:
        node, task = self._get_mutable_owned_task(access_token, task_id)
        self._ensure_status_update_allowed(req.status)
        updated = self.repo.update_task_status_for_worker(
            task_id,
            int(self._value(node, "id")),
            req.model_dump(),
            self._now(),
        )
        if not updated:
            raise WorkerServiceError(404, "task_not_found", "worker task does not exist")
        return updated

    def append_task_logs(self, access_token: str, task_id: str, req: WorkerTaskLogRequest) -> dict[str, Any]:
        node, task = self._get_owned_task(access_token, task_id)
        self._ensure_task_mutable(task)
        accepted = self.repo.append_task_logs(
            task_id,
            int(self._value(node, "id")),
            [item.model_dump() for item in req.items],
            self._now(),
        )
        return {"accepted": int(accepted)}

    def complete_task(self, access_token: str, task_id: str, req: WorkerTaskCompleteRequest) -> dict[str, Any]:
        node, task = self._get_mutable_owned_task(access_token, task_id)
        completed = self.repo.complete_task_for_worker(
            task_id,
            int(self._value(node, "id")),
            {
                "result_summary": req.result_summary,
                "artifacts": [item.model_dump() for item in req.artifacts],
            },
            self._now(),
        )
        if not completed:
            raise WorkerServiceError(404, "task_not_found", "worker task does not exist")
        return completed

    def fail_task(self, access_token: str, task_id: str, req: WorkerTaskFailRequest) -> dict[str, Any]:
        node, task = self._get_mutable_owned_task(access_token, task_id)
        failed = self.repo.fail_task_for_worker(
            task_id,
            int(self._value(node, "id")),
            req.model_dump(),
            self._now(),
        )
        if not failed:
            raise WorkerServiceError(404, "task_not_found", "worker task does not exist")
        return failed

    @staticmethod
    def _spill_archive_source(
        archive_source: bytes | bytearray | BinaryIO | str | Path,
    ) -> tuple[BinaryIO | str | Path, Path | None]:
        if isinstance(archive_source, (str, Path)):
            return archive_source, None
        if isinstance(archive_source, (bytes, bytearray)):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                temp_file.write(archive_source)
                return temp_file.name, Path(temp_file.name)
        if hasattr(archive_source, "seek"):
            archive_source.seek(0)
        return archive_source, None

    def download_task_snapshot(self, access_token: str, task_id: str) -> Path:
        _node, task = self._get_owned_task(access_token, task_id)
        self._ensure_task_mutable(task)
        snapshot_dir = self._resolve_task_snapshot_dir(task)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            archive_path = Path(temp_file.name)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(snapshot_dir.rglob("*")):
                if not path.is_file():
                    continue
                archive.write(path, arcname=path.relative_to(snapshot_dir).as_posix())
        return archive_path

    def store_task_output_archive(
        self,
        access_token: str,
        task_id: str,
        archive_source: bytes | bytearray | BinaryIO | str | Path,
    ) -> dict[str, Any]:
        _node, task = self._get_mutable_owned_task(access_token, task_id)
        output_dir = self._resolve_task_output_dir(task)
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        file_count = 0
        zip_source, cleanup_path = self._spill_archive_source(archive_source)
        try:
            with zipfile.ZipFile(zip_source, "r") as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    relative_path = self._safe_relative_path(member.filename)
                    target_path = (output_dir / relative_path).resolve()
                    try:
                        target_path.relative_to(output_dir)
                    except ValueError as exc:
                        raise WorkerServiceError(400, "invalid_task_archive", "task archive contains an unsafe path") from exc
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member, "r") as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    file_count += 1
        except zipfile.BadZipFile as exc:
            raise WorkerServiceError(400, "invalid_task_archive", "task output archive is not a valid zip file") from exc
        finally:
            if cleanup_path is not None:
                cleanup_path.unlink(missing_ok=True)

        return {
            "output_root": f"Output/{task_id}",
            "file_count": file_count,
        }

    def recover_stalled_assigned_tasks(self, *, timeout_seconds: int) -> dict[str, Any]:
        deadline = self._now().replace(microsecond=0)
        stale_cutoff = deadline - timedelta(seconds=timeout_seconds)
        stale_tasks = self.repo.list_stalled_assigned_tasks(stale_cutoff)
        failed_task_ids: list[str] = []
        skipped_task_ids: list[str] = []
        for task in stale_tasks:
            task_id = str(task["task_id"])
            runtime_state = self._value(task, "runtime_state_json", {}) or {}
            running_task_ids = {str(item) for item in (runtime_state.get("running_task_ids") or [])}
            occupied_slots = int(runtime_state.get("occupied_slots") or 0)
            available_slots = int(runtime_state.get("available_slots") or 0)
            if task_id in running_task_ids:
                skipped_task_ids.append(task_id)
                continue
            if occupied_slots > 0 and available_slots <= 0:
                skipped_task_ids.append(task_id)
                continue
            worker_node_id = int(self._value(task, "worker_node_id"))
            last_error = str(self._value(task, "last_error", "") or "").strip()
            reason = last_error or f"worker heartbeat resumed but task stayed assigned for over {timeout_seconds}s"
            failed = self.repo.fail_stalled_assigned_task(task_id, worker_node_id, deadline, reason)
            if failed:
                failed_task_ids.append(task_id)
        return {
            "stale_task_count": len(stale_tasks),
            "failed_task_ids": failed_task_ids,
            "skipped_task_ids": skipped_task_ids,
        }

    def reconcile_offline_workers(self, *, timeout_seconds: int) -> dict[str, Any]:
        deadline = self._now().replace(microsecond=0)
        stale_cutoff = deadline - timedelta(seconds=timeout_seconds)
        stale_nodes = self.repo.list_stale_worker_nodes(stale_cutoff)
        requeued_task_ids: list[str] = []
        failed_task_ids: list[str] = []
        for node in stale_nodes:
            worker_node_id = int(self._value(node, "id"))
            self.repo.mark_worker_offline(worker_node_id, deadline)
            for task in self.repo.list_worker_tasks_for_recovery(worker_node_id):
                task_id = str(task["task_id"])
                status = str(task.get("status") or "")
                if status == "assigned":
                    self.repo.requeue_task_after_worker_loss(task_id, worker_node_id)
                    requeued_task_ids.append(task_id)
                else:
                    self.repo.fail_task_after_worker_loss(task_id, worker_node_id, deadline, "worker_offline")
                    failed_task_ids.append(task_id)
        return {
            "offline_worker_count": len(stale_nodes),
            "requeued_task_ids": requeued_task_ids,
            "failed_task_ids": failed_task_ids,
        }
