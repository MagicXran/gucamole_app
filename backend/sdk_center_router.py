"""
SDK 中心公开只读 API。
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from backend.auth import JWT_ALGORITHM, JWT_SECRET, get_current_user
from backend.database import db
from backend.models import SdkPackageDetailResponse, SdkPackageListItemResponse, UserInfo
from backend.sdk_center_service import SdkCenterService, SdkCenterServiceError

router = APIRouter(prefix="/api/sdks", tags=["sdks"])
service = SdkCenterService(db=db)


def _raise_http_error(exc: SdkCenterServiceError):
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


def _create_download_token(asset_id: int) -> str:
    payload = {
        "type": "sdk_download",
        "asset_id": asset_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_download_token(token: str, asset_id: int):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="下载链接已过期，请重新获取")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="无效的下载令牌")

    if payload.get("type") != "sdk_download" or int(payload.get("asset_id") or 0) != asset_id:
        raise HTTPException(status_code=403, detail="无效的下载令牌")


@router.get("", response_model=list[SdkPackageListItemResponse])
def list_sdks(
    package_kind: Literal["cloud_platform", "simulation_app"] = Query(...),
    _user: UserInfo = Depends(get_current_user),
):
    return service.list_packages(package_kind)


@router.post("/assets/{asset_id}/download-token")
def create_sdk_asset_download_token(asset_id: int, _user: UserInfo = Depends(get_current_user)):
    try:
        service.get_download_asset(asset_id)
    except SdkCenterServiceError as exc:
        _raise_http_error(exc)
    return {"token": _create_download_token(asset_id), "expires_in": 300}


@router.get("/assets/{asset_id}/download")
def download_sdk_asset(asset_id: int, _token: str = Query(default="")):
    if not _token:
        raise HTTPException(status_code=401, detail="未提供下载令牌")
    _verify_download_token(_token, asset_id)
    try:
        asset = service.get_download_asset(asset_id)
    except SdkCenterServiceError as exc:
        _raise_http_error(exc)
    return RedirectResponse(url=asset["download_url"])


@router.get("/{package_id}", response_model=SdkPackageDetailResponse)
def get_sdk(package_id: int, _user: UserInfo = Depends(get_current_user)):
    try:
        return service.get_package_detail(package_id)
    except SdkCenterServiceError as exc:
        _raise_http_error(exc)
