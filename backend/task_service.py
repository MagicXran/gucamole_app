"""
User-facing platform task submission and cancellation flow.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Callable

from backend.config_loader import get_config
from backend.drive_quota import _format_bytes, _get_quota, _get_usage_sync
from backend.script_dispatch import evaluate_script_dispatch_target


class TaskServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class TaskService:
    repo: Any
    drive_root: Path
    results_root_name: str | None = None
    task_id_factory: Callable[[], str] | None = None

    def __post_init__(self):
        self.drive_root = Path(self.drive_root)
        config = get_config()
        drive_cfg = config.get("guacamole", {}).get("drive", {})
        self._results_root_name = str(self.results_root_name or drive_cfg.get("results_root", "Output")).strip() or "Output"
        self._task_id_factory = self.task_id_factory or (lambda: f"task_{token_urlsafe(12)}")

    def _user_root(self, user_id: int) -> Path:
        return (self.drive_root / f"portal_u{user_id}").resolve()

    def _resolve_entry_path(self, user_id: int, entry_path: str) -> tuple[Path, Path]:
        user_root = self._user_root(user_id)
        normalized = entry_path.replace("\\", "/").strip("/")
        if not normalized:
            raise TaskServiceError(400, "invalid_entry_path", "entry path is required")
        lowered = normalized.lower()
        if lowered == "system" or lowered.startswith("system/"):
            raise TaskServiceError(400, "invalid_entry_path", "entry path cannot use internal system workspace")
        target = (user_root / normalized).resolve()
        try:
            target.relative_to(user_root)
        except ValueError as exc:
            raise TaskServiceError(400, "invalid_entry_path", "entry path must stay within user workspace") from exc
        return user_root, target

    def _snapshot_ignore_factory(self, working_dir: Path, snapshot_dir: Path):
        try:
            snapshot_dir.relative_to(working_dir)
        except ValueError:
            return None
        results_root = None
        results_root_name = self._results_root_name.replace("\\", "/").strip("/")
        if results_root_name:
            results_root_candidate = (working_dir / Path(*results_root_name.split("/"))).resolve()
            try:
                results_root_candidate.relative_to(working_dir)
                results_root = results_root_candidate
            except ValueError:
                results_root = None

        def _ignore(dir_path: str, names: list[str]):
            current_dir = Path(dir_path)
            ignored = []
            for name in names:
                candidate = current_dir / name
                try:
                    candidate.relative_to(snapshot_dir)
                    ignored.append(name)
                    continue
                except ValueError:
                    pass
                if results_root is not None:
                    try:
                        candidate.relative_to(results_root)
                        ignored.append(name)
                        continue
                    except ValueError:
                        pass
            if current_dir == working_dir and "system" in names:
                ignored.append("system")
            return ignored

        return _ignore

    def _estimate_snapshot_size(self, working_dir: Path, snapshot_dir: Path) -> int:
        ignore = self._snapshot_ignore_factory(working_dir, snapshot_dir)
        total = 0
        for path in working_dir.rglob("*"):
            if not path.is_file():
                continue
            if ignore is not None:
                ignored = ignore(str(path.parent), [path.name])
                if path.name in ignored:
                    continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
        return total

    def get_script_submission_preflight(self, *, user_id: int, requested_runtime_id: int) -> dict:
        target = self.repo.get_script_launch_target(user_id, requested_runtime_id)
        worker_nodes = list(self.repo.list_worker_dispatch_nodes(int(target.get("worker_group_id") or 0))) if target else []
        result = evaluate_script_dispatch_target(
            target=target,
            worker_nodes=worker_nodes,
            requested_runtime_id=requested_runtime_id,
        )
        if result["reasons"] and result["reasons"][0]["code"] == "script_target_not_found":
            raise TaskServiceError(404, "script_target_not_found", "script mode is not configured for this app")
        return result

    def submit_script_task(self, *, user_id: int, requested_runtime_id: int, entry_path: str):
        preflight = self.get_script_submission_preflight(user_id=user_id, requested_runtime_id=requested_runtime_id)
        if not preflight["is_schedulable"]:
            message = preflight["reasons"][0]["message"] if preflight["reasons"] else "当前节点组不可调度"
            raise TaskServiceError(409, "script_not_schedulable", message)
        target = self.repo.get_script_launch_target(user_id, requested_runtime_id)

        user_root, entry_file = self._resolve_entry_path(user_id, entry_path)
        if not entry_file.exists() or not entry_file.is_file():
            raise TaskServiceError(404, "entry_path_not_found", "entry script does not exist")

        task_id = self._task_id_factory()
        working_dir = entry_file.parent
        snapshot_dir = user_root / "system" / "tasks" / task_id / "input"
        snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
        snapshot_size = self._estimate_snapshot_size(working_dir, snapshot_dir)
        used = _get_usage_sync(user_id)
        quota = _get_quota(user_id)
        if used + snapshot_size > quota:
            raise TaskServiceError(
                422,
                "snapshot_quota_exceeded",
                f"空间不足: 已用 {_format_bytes(used)}, 配额 {_format_bytes(quota)}, 快照需要 {_format_bytes(snapshot_size)}",
            )
        shutil.copytree(
            working_dir,
            snapshot_dir,
            dirs_exist_ok=True,
            ignore=self._snapshot_ignore_factory(working_dir, snapshot_dir),
        )

        relative_entry = str(entry_file.relative_to(user_root)).replace("\\", "/")
        relative_workspace = str(working_dir.relative_to(user_root)).replace("\\", "/")
        relative_snapshot = str(snapshot_dir.relative_to(user_root)).replace("\\", "/")
        task_payload = {
            "task_id": task_id,
            "user_id": user_id,
            "app_id": target.get("app_id"),
            "binding_id": target.get("binding_id"),
            "task_kind": "script_run",
            "executor_key": target.get("executor_key"),
            "resource_pool_id": target.get("pool_id"),
            "worker_group_id": target.get("worker_group_id"),
            "worker_node_id": None,
            "requested_runtime_id": target.get("requested_runtime_id") or requested_runtime_id,
            "assigned_runtime_id": None,
            "entry_path": relative_entry,
            "workspace_path": relative_workspace,
            "input_snapshot_path": relative_snapshot,
            "scratch_path": None,
            "status": "queued",
            "external_task_id": None,
            "cancel_requested": 0,
            "params_json": target.get("runtime_config_json"),
            "result_summary_json": None,
        }
        created = self.repo.create_platform_task(task_payload)
        if target.get("pool_id") is not None:
            self.repo.insert_task_queue(
                {
                    "pool_id": target.get("pool_id"),
                    "user_id": user_id,
                    "requested_app_id": requested_runtime_id,
                    "request_mode": "task",
                    "platform_task_id": created.get("id", task_id),
                    "status": "queued",
                }
            )
        return created

    def list_tasks(self, *, user_id: int):
        return self.repo.list_tasks_for_user(user_id)

    def get_task(self, *, user_id: int, task_id: str):
        task = self.repo.get_task_by_task_id_for_user(task_id, user_id)
        if not task:
            raise TaskServiceError(404, "task_not_found", "task does not exist")
        return task

    def get_task_logs(self, *, user_id: int, task_id: str):
        task = self.get_task(user_id=user_id, task_id=task_id)
        return {"items": self.repo.list_task_logs(task.get("id"))}

    def get_task_artifacts(self, *, user_id: int, task_id: str):
        task = self.get_task(user_id=user_id, task_id=task_id)
        return {"items": self.repo.list_task_artifacts(task.get("id"))}

    def cancel_task(self, *, user_id: int, task_id: str):
        task = self.repo.get_task_by_task_id_for_user(task_id, user_id)
        if not task:
            raise TaskServiceError(404, "task_not_found", "task does not exist")

        cancelled = self.repo.cancel_queued_task(task_id, user_id)
        if cancelled:
            return cancelled

        cancel_requested = self.repo.request_cancel_active_task(task_id, user_id)
        if cancel_requested:
            return cancel_requested

        raise TaskServiceError(409, "task_not_cancellable", "task cannot be cancelled in its current state")
