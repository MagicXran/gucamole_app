"""
Admin APIs for worker groups, worker nodes, and enrollment tokens.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request

from backend.admin_worker_service import WorkerAdminService
from backend.audit import log_action
from backend.auth import require_admin
from backend.database import db
from backend.models import UserInfo
from backend.worker_repository import MySQLWorkerRepository


class WorkerGroupCreateRequest(BaseModel):
    group_key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    max_claim_batch: int = Field(default=1, ge=1, le=100)


class WorkerNodeCreateRequest(BaseModel):
    group_id: int = Field(..., ge=1)
    display_name: str = Field(..., min_length=1, max_length=200)
    expected_hostname: str = Field(..., min_length=1, max_length=255)
    scratch_root: str = Field(..., min_length=1, max_length=500)
    workspace_share: str = Field(..., min_length=1, max_length=500)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=9999)


class WorkerEnrollmentIssueRequest(BaseModel):
    expires_hours: int = Field(default=24, ge=1, le=168)


router = APIRouter(prefix="/api/admin/workers", tags=["admin-workers"])
worker_admin_service = WorkerAdminService(repo=MySQLWorkerRepository(db))


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/groups", status_code=201)
def create_group(
    req: WorkerGroupCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    group = worker_admin_service.create_worker_group(**req.model_dump())
    log_action(
        admin.user_id,
        admin.username,
        "admin_create_worker_group",
        "worker_group",
        group["id"],
        group["name"],
        ip_address=_client_ip(request),
    )
    return group


@router.get("/groups")
def list_groups(admin: UserInfo = Depends(require_admin)):
    return {"items": worker_admin_service.list_worker_groups()}


@router.post("/nodes", status_code=201)
def create_node(
    req: WorkerNodeCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    node = worker_admin_service.create_worker_node(**req.model_dump())
    log_action(
        admin.user_id,
        admin.username,
        "admin_create_worker_node",
        "worker_node",
        node["id"],
        node["display_name"],
        ip_address=_client_ip(request),
    )
    return node


@router.get("/nodes")
def list_nodes(admin: UserInfo = Depends(require_admin)):
    return {"items": worker_admin_service.list_worker_nodes()}


@router.post("/nodes/{worker_node_id}/enrollment", status_code=201)
def issue_enrollment(
    worker_node_id: int,
    req: WorkerEnrollmentIssueRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    enrollment = worker_admin_service.issue_enrollment(
        worker_node_id=worker_node_id,
        issued_by=admin.user_id,
        expires_hours=req.expires_hours,
    )
    log_action(
        admin.user_id,
        admin.username,
        "admin_issue_worker_enrollment",
        "worker_node",
        worker_node_id,
        f"worker_{worker_node_id}",
        ip_address=_client_ip(request),
    )
    return enrollment


@router.post("/nodes/{worker_node_id}/revoke")
def revoke_worker_node(
    worker_node_id: int,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    result = worker_admin_service.revoke_worker_node(worker_node_id=worker_node_id)
    log_action(
        admin.user_id,
        admin.username,
        "admin_revoke_worker_node",
        "worker_node",
        worker_node_id,
        f"worker_{worker_node_id}",
        ip_address=_client_ip(request),
    )
    return result


@router.post("/nodes/{worker_node_id}/rotate-token")
def rotate_worker_token(
    worker_node_id: int,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    result = worker_admin_service.rotate_worker_token(worker_node_id=worker_node_id)
    log_action(
        admin.user_id,
        admin.username,
        "admin_rotate_worker_token",
        "worker_node",
        worker_node_id,
        f"worker_{worker_node_id}",
        ip_address=_client_ip(request),
    )
    return result
