"""
User-facing task APIs for script-mode execution.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.database import CONFIG, db
from backend.models import UserInfo
from backend.task_repository import MySQLTaskRepository
from backend.task_service import TaskService, TaskServiceError


class TaskSubmitRequest(BaseModel):
    requested_runtime_id: int = Field(..., ge=1)
    entry_path: str = Field(..., min_length=1, max_length=1000)


router = APIRouter(prefix="/api/tasks", tags=["tasks"])
task_service = TaskService(
    repo=MySQLTaskRepository(db),
    drive_root=Path(CONFIG.get("guacamole", {}).get("drive", {}).get("base_path", "/drive")),
)


def _translate_error(exc: TaskServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("", status_code=201)
def submit_task(req: TaskSubmitRequest, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.submit_script_task(
            user_id=user.user_id,
            requested_runtime_id=req.requested_runtime_id,
            entry_path=req.entry_path,
        )
    except TaskServiceError as exc:
        raise _translate_error(exc)


@router.get("/preflight")
def get_task_preflight(requested_runtime_id: int, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.get_script_submission_preflight(
            user_id=user.user_id,
            requested_runtime_id=requested_runtime_id,
        )
    except TaskServiceError as exc:
        raise _translate_error(exc)


@router.get("")
def list_tasks(user: UserInfo = Depends(get_current_user)):
    return task_service.list_tasks(user_id=user.user_id)


@router.get("/{task_id}")
def get_task(task_id: str, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.get_task(user_id=user.user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _translate_error(exc)


@router.get("/{task_id}/logs")
def get_task_logs(task_id: str, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.get_task_logs(user_id=user.user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _translate_error(exc)


@router.get("/{task_id}/artifacts")
def get_task_artifacts(task_id: str, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.get_task_artifacts(user_id=user.user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _translate_error(exc)


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, user: UserInfo = Depends(get_current_user)):
    try:
        return task_service.cancel_task(user_id=user.user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _translate_error(exc)
