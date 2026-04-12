"""
Worker-facing API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import db
from backend.worker_repository import MySQLWorkerRepository
from backend.worker_service import (
    WorkerHeartbeatRequest,
    WorkerTaskCompleteRequest,
    WorkerTaskFailRequest,
    WorkerTaskLogRequest,
    WorkerTaskStatusRequest,
    WorkerRegistrationRequest,
    WorkerService,
    WorkerServiceError,
)

router = APIRouter(prefix="/api/worker", tags=["worker"])
_bearer_scheme = HTTPBearer(auto_error=False)

worker_service = WorkerService(repo=MySQLWorkerRepository(db))


def _require_worker_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 Worker 认证令牌",
        )
    return credentials.credentials


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _translate_service_error(exc: WorkerServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.code)


@router.post("/register")
def register_worker(req: WorkerRegistrationRequest, request: Request):
    try:
        return worker_service.register_worker(req, client_ip=_client_ip(request))
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/heartbeat")
def heartbeat(
    req: WorkerHeartbeatRequest,
    request: Request,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.heartbeat(worker_token, req, client_ip=_client_ip(request))
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/pull")
def pull_task(
    request: Request,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.pull_task(worker_token, client_ip=_client_ip(request))
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/tasks/{task_id}/status")
def report_task_status(
    task_id: str,
    req: WorkerTaskStatusRequest,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.report_task_status(worker_token, task_id, req)
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/tasks/{task_id}/logs")
def append_task_logs(
    task_id: str,
    req: WorkerTaskLogRequest,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.append_task_logs(worker_token, task_id, req)
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    req: WorkerTaskCompleteRequest,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.complete_task(worker_token, task_id, req)
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/tasks/{task_id}/fail")
def fail_task(
    task_id: str,
    req: WorkerTaskFailRequest,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        return worker_service.fail_task(worker_token, task_id, req)
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.get("/tasks/{task_id}/snapshot")
def download_task_snapshot(
    task_id: str,
    worker_token: str = Depends(_require_worker_token),
):
    try:
        archive_bytes = worker_service.download_task_snapshot(worker_token, task_id)
        return Response(
            content=archive_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{task_id}-snapshot.zip"',
            },
        )
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)


@router.post("/tasks/{task_id}/output-archive")
async def upload_task_output_archive(
    task_id: str,
    archive: UploadFile = File(...),
    worker_token: str = Depends(_require_worker_token),
):
    try:
        archive_bytes = await archive.read()
        return worker_service.store_task_output_archive(worker_token, task_id, archive_bytes)
    except WorkerServiceError as exc:
        raise _translate_service_error(exc)
