from fastapi import APIRouter, Depends, Request

from backend.audit import log_action
from backend.auth import get_current_user
from backend.booking_service import BookingService
from backend.models import BookingCreateRequest, BookingRecordResponse, UserInfo

router = APIRouter(prefix="/api/bookings", tags=["bookings"])
service = BookingService()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[BookingRecordResponse])
def list_bookings(user: UserInfo = Depends(get_current_user)):
    return service.list_bookings(user_id=user.user_id)


@router.post("", response_model=BookingRecordResponse)
def create_booking(
    payload: BookingCreateRequest,
    request: Request,
    user: UserInfo = Depends(get_current_user),
):
    booking = service.create_booking(user_id=user.user_id, payload=payload.model_dump())
    log_action(
        user_id=user.user_id,
        username=user.username,
        action="booking_create",
        target_type="booking",
        target_id=booking["id"],
        target_name=booking["app_name"],
        detail={
            "scheduled_for": booking["scheduled_for"],
            "purpose": booking["purpose"],
            "status": booking["status"],
        },
        ip_address=_client_ip(request),
    )
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingRecordResponse)
def cancel_booking(
    booking_id: int,
    request: Request,
    user: UserInfo = Depends(get_current_user),
):
    booking = service.cancel_booking(booking_id=booking_id, user_id=user.user_id)
    log_action(
        user_id=user.user_id,
        username=user.username,
        action="booking_cancel",
        target_type="booking",
        target_id=booking["id"],
        target_name=booking["app_name"],
        detail={"status": booking["status"]},
        ip_address=_client_ip(request),
    )
    return booking
