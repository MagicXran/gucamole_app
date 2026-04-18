from fastapi import APIRouter, Depends

from backend.admin_analytics_service import AdminAnalyticsService
from backend.auth import require_admin
from backend.database import db
from backend.models import AdminAnalyticsOverviewResponse, UserInfo

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])
analytics_service = AdminAnalyticsService(db=db)


@router.get("/overview", response_model=AdminAnalyticsOverviewResponse)
def get_admin_analytics_overview(_admin: UserInfo = Depends(require_admin)):
    return analytics_service.get_overview()
