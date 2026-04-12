"""
Worker-side local task execution runtime.
"""

from __future__ import annotations

import os
import subprocess
import sys
import shutil
from pathlib import Path

from backend.software_adapters import SoftwarePreflightError, get_software_adapter


class BaseExecutor:
    def execute(self, task: dict, scratch_dir: Path) -> dict:
        raise NotImplementedError


class PythonApiExecutor(BaseExecutor):
    @staticmethod
    def _validate_python_executable(params: dict) -> list[str]:
        python_executable = str(params.get("python_executable") or "").strip()
        if not python_executable:
            return []
        if Path(python_executable).exists() or shutil.which(python_executable):
            return []
        return [f"missing_python_executable:{python_executable}"]

    def execute(self, task: dict, scratch_dir: Path) -> dict:
        entry_name = Path(task["entry_path"]).name
        entry_file = scratch_dir / entry_name
        params = task.get("params_json") or {}
        adapter_key = params.get("software_adapter_key") or params.get("script_profile_key")
        software_name = str(params.get("software_display_name") or adapter_key or "software")
        preflight_issues = self._validate_python_executable(params)
        adapter = get_software_adapter(adapter_key)
        if adapter is not None:
            probe_result = adapter.probe(params)
            preflight_issues.extend(probe_result.issues)
        if preflight_issues:
            return {
                "status": "failed",
                "returncode": -1,
                "stdout": "",
                "stderr": f"software_preflight_failed:{software_name}:{', '.join(preflight_issues)}",
            }
        if adapter is not None:
            try:
                adapter.preflight(params)
            except SoftwarePreflightError as exc:
                return {
                    "status": "failed",
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"software_preflight_failed:{exc.software_name}:{', '.join(exc.issues)}",
                }
        python_executable = params.get("python_executable") or sys.executable
        env = dict(os.environ)
        env.update({str(k): str(v) for k, v in (params.get("python_env") or {}).items()})
        result = subprocess.run(
            [python_executable, str(entry_file)],
            cwd=str(scratch_dir),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        return {
            "status": "succeeded" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }


class CommandStatusFileExecutor(BaseExecutor):
    def execute(self, task: dict, scratch_dir: Path) -> dict:
        entry_name = Path(task["entry_path"]).name
        entry_file = scratch_dir / entry_name
        params = task.get("params_json") or {}
        adapter_key = params.get("software_adapter_key") or params.get("script_profile_key")
        software_name = str(params.get("software_display_name") or adapter_key or "software")
        adapter = get_software_adapter(adapter_key)
        if adapter is not None:
            try:
                adapter.preflight(params)
            except SoftwarePreflightError as exc:
                return {
                    "status": "failed",
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"software_preflight_failed:{exc.software_name}:{', '.join(exc.issues)}",
                }
        status_file_value = str(params.get("status_file") or "").strip()
        status_file = Path(status_file_value) if status_file_value else None
        result = subprocess.run(
            ["cmd.exe", "/c", str(entry_file)],
            cwd=str(scratch_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        final_status = "succeeded" if result.returncode == 0 else "failed"
        if status_file is not None:
            resolved = scratch_dir / status_file
            if resolved.exists():
                content = resolved.read_text(encoding="utf-8", errors="ignore").lower()
                if "fail" in content or "error" in content:
                    final_status = "failed"
                elif "success" in content or "ok" in content:
                    final_status = "succeeded"
        return {
            "status": final_status,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }


class LocalTaskRunner:
    def __init__(self, archive_service=None):
        self._executors = {
            "python_api": PythonApiExecutor(),
            "command_statusfile": CommandStatusFileExecutor(),
        }
        self._archive_service = archive_service

    def _collect_artifacts(self, scratch_dir: Path) -> list[dict]:
        artifacts = []
        for path in sorted(scratch_dir.rglob("*")):
            if not path.is_file():
                continue
            artifacts.append(
                {
                    "artifact_kind": "workspace_output",
                    "display_name": path.name,
                    "relative_path": path.relative_to(scratch_dir).as_posix(),
                    "size_bytes": path.stat().st_size,
                }
            )
        return artifacts

    def run(self, task: dict, portal_client) -> None:
        executor_key = task.get("executor_key")
        executor = self._executors.get(executor_key)
        if executor is None:
            portal_client.fail_task(task["task_id"], {"error_message": f"unsupported executor: {executor_key}"})
            return

        scratch_dir = Path(task["scratch_path"])
        portal_client.report_task_status(
            task["task_id"],
            {
                "status": "running",
                "scratch_path": str(scratch_dir),
                "external_task_id": None,
            },
        )
        result = executor.execute(task, scratch_dir)
        log_text = (result.get("stdout") or "") + (("\n" + result.get("stderr")) if result.get("stderr") else "")
        if log_text.strip():
            portal_client.append_task_logs(
                task["task_id"],
                [{"seq_no": 1, "level": "info", "message": log_text.strip()}],
            )
        if result["status"] == "succeeded":
            artifacts = self._collect_artifacts(scratch_dir)
            if self._archive_service is not None:
                artifacts.extend(self._archive_service.archive_directory(task["task_id"], scratch_dir))
            portal_client.complete_task(
                task["task_id"],
                {
                    "result_summary": {
                        "returncode": result.get("returncode"),
                        "stdout_tail": (result.get("stdout") or "")[-1000:],
                    },
                    "artifacts": artifacts,
                },
            )
            return
        portal_client.fail_task(
            task["task_id"],
            {"error_message": (result.get("stderr") or result.get("stdout") or "task failed").strip()},
        )
