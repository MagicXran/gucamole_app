"""
Admin-side worker provisioning service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any, Callable


@dataclass
class WorkerAdminService:
    repo: Any
    now_provider: Callable[[], datetime] | None = None
    enrollment_token_factory: Callable[[], str] | None = None
    access_token_factory: Callable[[], str] | None = None

    def __post_init__(self):
        self._now_provider = self.now_provider or datetime.now
        self._enrollment_token_factory = self.enrollment_token_factory or (lambda: f"enr_{token_urlsafe(24)}")
        self._access_token_factory = self.access_token_factory or (lambda: f"wkr_{token_urlsafe(32)}")

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return sha256(raw_token.encode("utf-8")).hexdigest()

    def create_worker_group(self, *, group_key: str, name: str, description: str = "", max_claim_batch: int = 1):
        payload = {
            "group_key": group_key,
            "name": name,
            "description": description or None,
            "max_claim_batch": max_claim_batch,
            "is_active": 1,
        }
        return self.repo.create_worker_group(payload)

    def list_worker_groups(self):
        rows = self.repo.list_worker_groups()
        normalized = []
        for row in rows:
            item = dict(row)
            item["node_count"] = int(item.get("node_count") or 0)
            item["active_node_count"] = int(item.get("active_node_count") or 0)
            normalized.append(item)
        return normalized

    def create_worker_node(
        self,
        *,
        group_id: int,
        display_name: str,
        expected_hostname: str,
        scratch_root: str,
        workspace_share: str,
        max_concurrent_tasks: int,
    ):
        payload = {
            "agent_id": f"wrk_{token_urlsafe(12)}",
            "group_id": group_id,
            "display_name": display_name,
            "expected_hostname": expected_hostname,
            "scratch_root": scratch_root,
            "workspace_share": workspace_share,
            "max_concurrent_tasks": max_concurrent_tasks,
        }
        return self.repo.create_worker_node(payload)

    def list_worker_nodes(self):
        rows = self.repo.list_worker_nodes()
        normalized = []
        for row in rows:
            item = dict(row)
            runtime_state = dict(item.get("runtime_state_json") or {})
            capabilities = dict(item.get("capabilities_json") or {})
            software_inventory = dict(runtime_state.get("software_inventory") or capabilities.get("software_inventory") or {})
            item["software_inventory"] = software_inventory
            item["software_total_count"] = len(software_inventory)
            item["software_ready_count"] = sum(
                1 for value in software_inventory.values()
                if isinstance(value, dict) and value.get("ready")
            )
            item["latest_enrollment_status"] = str(item.get("latest_enrollment_status") or "")
            normalized.append(item)
        return normalized

    def issue_enrollment(self, *, worker_node_id: int, issued_by: int, expires_hours: int = 24):
        plain_token = self._enrollment_token_factory()
        expires_at = self._now() + timedelta(hours=expires_hours)
        record = self.repo.insert_enrollment(
            {
                "worker_node_id": worker_node_id,
                "token_hash": self._hash_token(plain_token),
                "status": "issued",
                "issued_by": issued_by,
                "issued_at": self._now(),
                "expires_at": expires_at,
            }
        )
        return {
            "id": record["id"],
            "worker_node_id": worker_node_id,
            "plain_token": plain_token,
            "expires_at": expires_at,
        }

    def revoke_worker_node(self, *, worker_node_id: int):
        self.repo.revoke_worker_node(worker_node_id, self._now())
        return {"worker_node_id": worker_node_id, "status": "revoked"}

    def rotate_worker_token(self, *, worker_node_id: int):
        plain_token = self._access_token_factory()
        self.repo.rotate_worker_token(worker_node_id, self._hash_token(plain_token), self._now())
        return {
            "worker_node_id": worker_node_id,
            "plain_token": plain_token,
        }
