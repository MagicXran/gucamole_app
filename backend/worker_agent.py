"""
Runnable Worker Agent pieces for Windows nodes.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import tempfile
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from backend.software_inventory import probe_registered_software
from backend.worker_runtime import LocalTaskRunner


class FileCredentialStore:
    def __init__(self, path: Path):
        self._path = Path(path)

    def load(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        return json.loads(self._path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class DpapiCredentialStore(FileCredentialStore):
    def save(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        protected = self._protect(raw)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(base64.b64encode(protected).decode("ascii"), encoding="utf-8")

    def load(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        protected = base64.b64decode(self._path.read_text(encoding="utf-8"))
        raw = self._unprotect(protected)
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def _protect(raw: bytes) -> bytes:
        if os.name != "nt":
            return raw
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(raw)
        in_blob = DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptProtectData(ctypes.byref(in_blob), "worker", None, None, None, 0, ctypes.byref(out_blob)):
            raise OSError("CryptProtectData failed")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    @staticmethod
    def _unprotect(protected: bytes) -> bytes:
        if os.name != "nt":
            return protected
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(protected)
        in_blob = DATA_BLOB(len(protected), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            raise OSError("CryptUnprotectData failed")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)


def build_credential_store(path: Path, mode: str = "dpapi"):
    if str(mode or "").lower() == "file":
        return FileCredentialStore(path)
    return DpapiCredentialStore(path)


class PortalWorkerClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=30.0)

    def _headers(self, token: str | None = None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        return headers

    def register(self, payload: dict):
        return self._client.post("/api/worker/register", json=payload).raise_for_status().json()

    def heartbeat(self, token: str, payload: dict):
        return self._client.post("/api/worker/heartbeat", headers=self._headers(token), json=payload).raise_for_status().json()

    def pull_task(self, token: str):
        return self._client.post("/api/worker/pull", headers=self._headers(token)).raise_for_status().json()

    def report_task_status(self, token: str, task_id: str, payload: dict):
        return self._client.post(f"/api/worker/tasks/{task_id}/status", headers=self._headers(token), json=payload).raise_for_status().json()

    def append_task_logs(self, token: str, task_id: str, items: list[dict]):
        return self._client.post(f"/api/worker/tasks/{task_id}/logs", headers=self._headers(token), json={"items": items}).raise_for_status().json()

    def complete_task(self, token: str, task_id: str, payload: dict):
        return self._client.post(f"/api/worker/tasks/{task_id}/complete", headers=self._headers(token), json=payload).raise_for_status().json()

    def fail_task(self, token: str, task_id: str, payload: dict):
        return self._client.post(f"/api/worker/tasks/{task_id}/fail", headers=self._headers(token), json=payload).raise_for_status().json()

    def download_task_snapshot(self, token: str, task_id: str) -> bytes:
        return self._client.get(f"/api/worker/tasks/{task_id}/snapshot", headers=self._headers(token)).raise_for_status().content

    def upload_task_output_archive(self, token: str, task_id: str, archive_path: Path | str):
        archive_path = Path(archive_path)
        with open(archive_path, "rb") as handle:
            files = {"archive": (archive_path.name, handle, "application/zip")}
            return self._client.post(
                f"/api/worker/tasks/{task_id}/output-archive",
                headers=self._headers(token),
                files=files,
            ).raise_for_status().json()


@dataclass
class WorkerAgent:
    portal_client: Any
    credential_store: Any
    registration_payload: dict[str, Any]
    runner: LocalTaskRunner | None = None

    def __post_init__(self):
        self.runner = self.runner or LocalTaskRunner()
        self._credentials = self.credential_store.load() or {}
        self._last_error_summary = ""

    @property
    def access_token(self) -> str | None:
        return self._credentials.get("access_token")

    def _software_inventory(self) -> dict[str, Any]:
        return probe_registered_software(self.registration_payload)

    def _build_registration_payload(self) -> dict[str, Any]:
        payload = dict(self.registration_payload)
        capabilities = dict(payload.get("capabilities") or {})
        capabilities["software_inventory"] = self._software_inventory()
        payload["capabilities"] = capabilities
        return payload

    def ensure_registered(self):
        if self.access_token:
            return self._credentials
        registered = self.portal_client.register(self._build_registration_payload())
        if registered.get("already_registered") and not registered.get("access_token"):
            raise RuntimeError(registered.get("message") or "worker already registered but access token is unavailable")
        self._credentials = {
            "agent_id": registered["agent_id"],
            "access_token": registered["access_token"],
            "worker_profile": registered.get("worker_profile") or {},
        }
        self.credential_store.save(self._credentials)
        return self._credentials

    def _worker_profile(self) -> dict[str, Any]:
        profile = dict(self._credentials.get("worker_profile") or {})
        if not profile:
            profile = {
                "scratch_root": self.registration_payload.get("scratch_root"),
                "workspace_share": self.registration_payload.get("workspace_share"),
            }
        return profile

    def _stage_task_to_scratch(self, token: str, task: dict) -> Path:
        profile = self._worker_profile()
        scratch_root = Path(profile.get("scratch_root") or self.registration_payload.get("scratch_root"))
        scratch_dir = scratch_root / "jobs" / task["task_id"]
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)
        scratch_dir.parent.mkdir(parents=True, exist_ok=True)
        snapshot_bytes = self.portal_client.download_task_snapshot(token, task["task_id"])
        with zipfile.ZipFile(io.BytesIO(snapshot_bytes), "r") as archive:
            archive.extractall(scratch_dir)
        return scratch_dir

    @staticmethod
    def _file_digest(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _build_manifest(self, scratch_dir: Path) -> dict[str, str]:
        manifest = {}
        for path in sorted(scratch_dir.rglob("*")):
            if not path.is_file():
                continue
            manifest[path.relative_to(scratch_dir).as_posix()] = self._file_digest(path)
        return manifest

    @staticmethod
    def _changed_paths(scratch_dir: Path, baseline_manifest: dict[str, str]) -> list[Path]:
        changed = []
        for path in sorted(scratch_dir.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(scratch_dir).as_posix()
            digest = WorkerAgent._file_digest(path)
            if baseline_manifest.get(relative_path) != digest:
                changed.append(path)
        return changed

    def _create_output_archive(self, task: dict, scratch_dir: Path, changed_paths: list[Path]) -> Path:
        archive_path = Path(tempfile.gettempdir()) / f"{task['task_id']}-output.zip"
        if archive_path.exists():
            archive_path.unlink()
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in changed_paths:
                archive.write(path, arcname=path.relative_to(scratch_dir).as_posix())
        return archive_path

    def _sync_outputs_to_workspace(self, token: str, task: dict, scratch_dir: Path, payload: dict) -> dict:
        baseline_manifest = dict(task.get("_baseline_manifest") or {})
        changed_paths = self._changed_paths(scratch_dir, baseline_manifest)
        archive_path = self._create_output_archive(task, scratch_dir, changed_paths)
        try:
            self.portal_client.upload_task_output_archive(token, task["task_id"], archive_path)
        finally:
            if archive_path.exists():
                archive_path.unlink()

        artifacts = []
        changed_rel_paths = {path.relative_to(scratch_dir).as_posix() for path in changed_paths}
        for artifact in payload.get("artifacts") or []:
            item = dict(artifact)
            if item.get("artifact_kind") == "workspace_output" and item.get("relative_path"):
                if item["relative_path"] not in changed_rel_paths:
                    continue
                item["relative_path"] = f"Output/{task['task_id']}/{item['relative_path']}".replace('\\', '/')
            artifacts.append(item)
        payload["artifacts"] = artifacts
        return payload

    def run_once(self):
        self.ensure_registered()
        token = self.access_token
        heartbeat = self.portal_client.heartbeat(token, {
            "running_task_ids": [],
            "occupied_slots": 0,
            "available_slots": 1,
            "last_error_summary": self._last_error_summary,
            "software_inventory": self._software_inventory(),
        })
        self._last_error_summary = ""
        task = self.portal_client.pull_task(token).get("task")
        if not task:
            return heartbeat

        scratch_dir = None
        try:
            scratch_dir = self._stage_task_to_scratch(token, task)
            task = dict(task)
            task["scratch_path"] = str(scratch_dir)
            task["_baseline_manifest"] = self._build_manifest(scratch_dir)

            class _PortalCallbacks:
                def __init__(self, outer, access_token, current_task, current_scratch_dir):
                    self._outer = outer
                    self._token = access_token
                    self._task = current_task
                    self._scratch_dir = current_scratch_dir

                def report_task_status(self, task_id: str, payload: dict):
                    return self._outer.portal_client.report_task_status(self._token, task_id, payload)

                def append_task_logs(self, task_id: str, items: list[dict]):
                    return self._outer.portal_client.append_task_logs(self._token, task_id, items)

                def complete_task(self, task_id: str, payload: dict):
                    self._outer.portal_client.report_task_status(
                        self._token,
                        task_id,
                        {
                            "status": "uploading",
                            "scratch_path": str(self._scratch_dir),
                            "external_task_id": None,
                        },
                    )
                    synced_payload = self._outer._sync_outputs_to_workspace(self._token, self._task, self._scratch_dir, dict(payload))
                    return self._outer.portal_client.complete_task(self._token, task_id, synced_payload)

                def fail_task(self, task_id: str, payload: dict):
                    return self._outer.portal_client.fail_task(self._token, task_id, payload)

            self.runner.run(task=task, portal_client=_PortalCallbacks(self, token, task, scratch_dir))
        except Exception as exc:
            error_summary = f"{type(exc).__name__}: {exc}".strip()
            self._last_error_summary = error_summary[:500]
            traceback_text = traceback.format_exc().strip()
            try:
                self.portal_client.append_task_logs(
                    token,
                    task["task_id"],
                    [
                        {
                            "seq_no": 1,
                            "level": "error",
                            "message": traceback_text[:4000],
                        }
                    ],
                )
            except Exception:
                pass
            try:
                self.portal_client.fail_task(
                    token,
                    task["task_id"],
                    {
                        "error_message": self._last_error_summary or "worker_preflight_failed",
                    },
                )
            except Exception:
                pass
        return heartbeat
