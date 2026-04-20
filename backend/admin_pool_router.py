"""
资源池管理后台 API
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.auth import require_admin
from backend.audit import log_action
from backend.app_attachment_service import AppAttachmentService
from backend.database import db
from backend.monitor import invalidate_user_session_if_safe
from backend.models import (
    PoolAttachmentResponse,
    PoolAttachmentUpdateRequest,
    ResourcePoolAdminResponse,
    ResourcePoolCreateRequest,
    ResourcePoolUpdateRequest,
    UserInfo,
)
from backend.resource_pool_service import ResourcePoolService

router = APIRouter(prefix="/api/admin/pools", tags=["admin-pools"])
pool_service = ResourcePoolService(db=db)
attachment_service = AppAttachmentService(db=db)


@router.get("", response_model=list[ResourcePoolAdminResponse])
def list_pools(admin: UserInfo = Depends(require_admin)):
    return pool_service.list_admin_pools()


@router.post("", response_model=ResourcePoolAdminResponse, status_code=201)
def create_pool(
    req: ResourcePoolCreateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    payload = req.model_dump()
    pool = pool_service.create_pool(payload)
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_create_pool",
        "pool", pool["id"], pool["name"], ip_address=client_ip,
    )
    return pool


@router.put("/{pool_id}", response_model=ResourcePoolAdminResponse)
def update_pool(
    pool_id: int,
    req: ResourcePoolUpdateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    payload = req.model_dump(exclude_none=True)
    try:
        pool = pool_service.update_pool(pool_id=pool_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_update_pool",
        "pool", pool_id, pool["name"], ip_address=client_ip,
    )
    return pool


@router.get("/{pool_id}/attachments", response_model=PoolAttachmentResponse)
def get_pool_attachments(
    pool_id: int,
    admin: UserInfo = Depends(require_admin),
):
    _ = admin
    return attachment_service.list_pool_attachments_for_admin(pool_id)


@router.put("/{pool_id}/attachments", response_model=PoolAttachmentResponse)
def replace_pool_attachments(
    pool_id: int,
    req: PoolAttachmentUpdateRequest,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    payload = req.model_dump()
    result = attachment_service.replace_pool_attachments(pool_id=pool_id, payload=payload)
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id,
        admin.username,
        "admin_update_pool_attachments",
        "pool",
        pool_id,
        f"pool_{pool_id}",
        detail=payload,
        ip_address=client_ip,
    )
    return result


@router.get("/queues")
def list_queues(admin: UserInfo = Depends(require_admin)):
    return {"items": pool_service.list_admin_queues()}


@router.post("/queues/{queue_id}/cancel")
def cancel_queue(
    queue_id: int,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    try:
        result = pool_service.cancel_queue_admin(queue_id=queue_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_cancel_queue",
        "queue", queue_id, f"queue_{queue_id}", ip_address=client_ip,
    )
    from backend.monitor import dispatch_ready_queue_entries
    dispatch_ready_queue_entries()
    return result


@router.post("/sessions/{session_id}/reclaim")
def reclaim_session(
    session_id: str,
    request: Request,
    admin: UserInfo = Depends(require_admin),
):
    try:
        result = pool_service.reclaim_session(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    client_ip = request.client.host if request.client else "unknown"
    log_action(
        admin.user_id, admin.username, "admin_reclaim_session",
        "session", None, session_id, ip_address=client_ip,
    )
    from backend.router import guac_service
    invalidate_user_session_if_safe(
        guac_service,
        int(result["user_id"]),
        exclude_session_id=session_id,
        session_db=db,
    )
    return result
