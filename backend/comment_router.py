from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth import get_current_user
from backend.comment_service import CommentService, CommentServiceError
from backend.database import db
from backend.models import CommentCreateRequest, CommentItemResponse, UserInfo

router = APIRouter(prefix="/api/comments", tags=["comments"])
router.service = CommentService(db=db)


def _raise_http_error(exc: CommentServiceError):
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("", response_model=list[CommentItemResponse])
def list_comments(
    target_type: str = Query(...),
    target_id: int = Query(..., ge=1),
    user: UserInfo = Depends(get_current_user),
):
    try:
        return router.service.list_comments(target_type=target_type, target_id=target_id, user=user)
    except CommentServiceError as exc:
        _raise_http_error(exc)


@router.post("", response_model=CommentItemResponse, status_code=status.HTTP_201_CREATED)
def create_comment(payload: CommentCreateRequest, user: UserInfo = Depends(get_current_user)):
    try:
        return router.service.create_comment(
            target_type=payload.target_type,
            target_id=payload.target_id,
            content=payload.content,
            user=user,
        )
    except CommentServiceError as exc:
        _raise_http_error(exc)
