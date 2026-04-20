from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from backend.audit import log_action
from backend.auth import get_current_user
from backend.case_center_service import CaseCenterService, CaseCenterServiceError
from backend.database import CONFIG, db
from backend.models import (
    CaseDetailResponse,
    CaseListItemResponse,
    CaseTransferResponse,
    UserInfo,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])

_drive_root = Path(CONFIG.get("guacamole", {}).get("drive", {}).get("base_path", "/drive"))
service = CaseCenterService(db=db, drive_root=_drive_root)


def _raise_http_error(exc: CaseCenterServiceError):
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("", response_model=list[CaseListItemResponse])
def list_cases(_user: UserInfo = Depends(get_current_user)):
    return service.list_public_cases()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: int, request: Request, user: UserInfo = Depends(get_current_user)):
    try:
        payload = service.get_public_case(case_id)
    except CaseCenterServiceError as exc:
        _raise_http_error(exc)
    log_action(
        user_id=user.user_id,
        username=user.username,
        action="view_case_detail",
        target_type="case",
        target_id=case_id,
        target_name=str(payload.get("title") or payload.get("case_uid") or case_id),
        ip_address=_client_ip(request),
    )
    return payload


@router.get("/{case_id}/download")
def download_case(case_id: int, request: Request, user: UserInfo = Depends(get_current_user)):
    try:
        payload = service.get_case_download(case_id)
    except CaseCenterServiceError as exc:
        _raise_http_error(exc)
    log_action(
        user_id=user.user_id,
        username=user.username,
        action="download_case",
        target_type="case",
        target_id=case_id,
        target_name=str(payload.get("case_uid") or case_id),
        ip_address=_client_ip(request),
    )
    return FileResponse(
        path=payload["archive_path"],
        filename=payload["filename"],
        media_type="application/zip",
    )


@router.post("/{case_id}/transfer", response_model=CaseTransferResponse)
def transfer_case(case_id: int, request: Request, user: UserInfo = Depends(get_current_user)):
    try:
        payload = service.transfer_case_to_workspace(case_id=case_id, user_id=user.user_id)
    except CaseCenterServiceError as exc:
        _raise_http_error(exc)
    log_action(
        user_id=user.user_id,
        username=user.username,
        action="transfer_case",
        target_type="case",
        target_id=case_id,
        target_name=str(payload.get("case_uid") or case_id),
        ip_address=_client_ip(request),
    )
    return payload
