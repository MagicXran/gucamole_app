"""
Shared bootstrap helpers for Worker CLI and Windows Service entrypoints.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.config_loader import load_config
from backend.object_storage import MinioArchiveService
from backend.worker_agent import build_credential_store, PortalWorkerClient, WorkerAgent
from backend.worker_runtime import LocalTaskRunner


def load_registration_payload(config_path: Path) -> dict:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def build_worker_agent(registration_path: Path) -> WorkerAgent:
    registration_payload = load_registration_payload(registration_path)
    portal_base_url = registration_payload.pop("portal_base_url", "").strip()
    if not portal_base_url:
        raise ValueError("registration payload missing portal_base_url")

    config = load_config()
    storage_cfg = config.get("object_storage", {})
    archive_service = MinioArchiveService(
        enabled=bool(storage_cfg.get("enabled")),
        endpoint=str(storage_cfg.get("endpoint") or ""),
        access_key=str(storage_cfg.get("access_key") or ""),
        secret_key=str(storage_cfg.get("secret_key") or ""),
        bucket=str(storage_cfg.get("bucket") or ""),
        secure=bool(storage_cfg.get("secure")),
    )

    scratch_root = registration_payload.get("scratch_root") or "C:\\sim-work"
    cred_root = Path(os.environ.get("PORTAL_WORKER_STATE_DIR", str(Path(scratch_root) / ".worker-state")))
    cred_root.mkdir(parents=True, exist_ok=True)
    credential_mode = os.environ.get("PORTAL_WORKER_CREDENTIAL_STORE", "dpapi")

    return WorkerAgent(
        portal_client=PortalWorkerClient(portal_base_url),
        credential_store=build_credential_store(cred_root / "worker-token.dat", mode=credential_mode),
        registration_payload=registration_payload,
        runner=LocalTaskRunner(archive_service=archive_service),
    )
