from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from backend.database import db
from backend.models import PoolAttachmentResponse, UserInfo
from backend.app_attachment_service import AppAttachmentService

router = APIRouter(prefix="/api/app-attachments", tags=["app-attachments"])
router.service = AppAttachmentService(db=db)


@router.get("/pools/{pool_id}", response_model=PoolAttachmentResponse)
def get_pool_attachments(pool_id: int, user: UserInfo = Depends(get_current_user)):
    return router.service.list_pool_attachments(pool_id=pool_id, user_id=user.user_id)
