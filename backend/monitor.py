"""
实时监控 - 心跳追踪与会话管理
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.database import db, CONFIG
from backend.auth import get_current_user, require_admin
from backend.models import UserInfo
from backend.resource_pool_service import ResourcePoolService
from backend.structured_logging import log_event

logger = logging.getLogger(__name__)

_monitor_cfg = CONFIG.get("monitor", {})
SESSION_TIMEOUT_SECONDS = _monitor_cfg.get("session_timeout_seconds", 120)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])
admin_monitor_router = APIRouter(prefix="/api/admin/monitor", tags=["admin-monitor"])
pool_service = ResourcePoolService(db=db)
SESSION_RECLAIMED_RESPONSES = {
    "admin": {
        "detail": "会话已被管理员回收",
        "code": "session_reclaimed",
        "reason": "admin",
    },
    "idle": {
        "detail": "会话因长时间空闲被系统回收",
        "code": "session_reclaimed",
        "reason": "idle",
    },
}
DEFAULT_SESSION_RECLAIM_REASON = "admin"


# ---- 请求模型 ----

class HeartbeatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=36)


class SessionEndRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=36)


class ActivityRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=36)


def _get_reclaim_pending_reason(session_id: str, user_id: int) -> str | None:
    row = db.execute_query(
        """
        SELECT reclaim_reason
        FROM active_session
        WHERE session_id = %(sid)s AND user_id = %(uid)s AND status = 'reclaim_pending'
        LIMIT 1
        """,
        {"sid": session_id, "uid": user_id},
        fetch_one=True,
    )
    if not row:
        return None
    reason = str(row.get("reclaim_reason") or "").strip()
    return reason or DEFAULT_SESSION_RECLAIM_REASON


def _reclaimed_response(reclaim_reason: str) -> JSONResponse:
    payload = SESSION_RECLAIMED_RESPONSES.get(
        reclaim_reason,
        SESSION_RECLAIMED_RESPONSES[DEFAULT_SESSION_RECLAIM_REASON],
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=payload,
    )


def user_has_other_active_sessions(
    user_id: int,
    exclude_session_id: str | None = None,
    session_db=None,
) -> bool:
    session_db = session_db or db
    params = {"uid": user_id}
    extra_where = ""
    if exclude_session_id:
        extra_where = " AND session_id <> %(exclude_sid)s"
        params["exclude_sid"] = exclude_session_id

    row = session_db.execute_query(
        f"""
        SELECT 1 AS exists_flag
        FROM active_session
        WHERE user_id = %(uid)s AND status = 'active'{extra_where}
        LIMIT 1
        """,
        params,
        fetch_one=True,
    )
    return bool(row)


def invalidate_user_session_if_safe(
    guac_service,
    user_id: int,
    exclude_session_id: str | None = None,
    session_db=None,
) -> bool:
    if user_has_other_active_sessions(
        user_id,
        exclude_session_id=exclude_session_id,
        session_db=session_db,
    ):
        return False
    guac_service.invalidate_user_session(f"portal_u{user_id}")
    return True


# ---- 普通用户端点 ----

@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, user: UserInfo = Depends(get_current_user)):
    """心跳续命: 更新 last_heartbeat"""
    rows = db.execute_update(
        """
        UPDATE active_session
        SET last_heartbeat = NOW()
        WHERE session_id = %(sid)s AND user_id = %(uid)s AND status = 'active'
        """,
        {"sid": req.session_id, "uid": user.user_id},
    )
    if rows == 0:
        reclaim_reason = _get_reclaim_pending_reason(req.session_id, user.user_id)
        if reclaim_reason is not None:
            return _reclaimed_response(reclaim_reason)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在或已结束")
    return {"ok": True}


@router.post("/session-end")
def session_end(req: SessionEndRequest):
    """关闭会话: sendBeacon 调用, 无 JWT (浏览器限制).
    安全性依赖 session_id UUID 的不可猜测性。
    """
    rows = db.execute_update(
        """
        UPDATE active_session
        SET status = 'disconnected', ended_at = NOW()
        WHERE session_id = %(sid)s AND status IN ('active', 'reclaim_pending')
        """,
        {"sid": req.session_id},
    )
    if rows > 0:
        dispatch_ready_queue_entries()
    return {"ok": True}


@router.post("/activity")
def activity(req: ActivityRequest, user: UserInfo = Depends(get_current_user)):
    """显式用户活动上报: 更新 last_activity_at。"""
    rows = db.execute_update(
        """
        UPDATE active_session
        SET last_activity_at = NOW()
        WHERE session_id = %(sid)s AND user_id = %(uid)s AND status = 'active'
        """,
        {"sid": req.session_id, "uid": user.user_id},
    )
    if rows == 0:
        reclaim_reason = _get_reclaim_pending_reason(req.session_id, user.user_id)
        if reclaim_reason is not None:
            return _reclaimed_response(reclaim_reason)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在或已结束")
    return {"ok": True}


# ---- 管理监控端点 ----

@admin_monitor_router.get("/overview")
def monitor_overview(admin: UserInfo = Depends(require_admin)):
    """总览: 每个应用的活跃用户数"""
    timeout = SESSION_TIMEOUT_SECONDS
    # 所有应用 (含无活跃连接的)
    apps = db.execute_query(
        "SELECT id, name, icon FROM remote_app WHERE is_active = 1 ORDER BY id"
    )

    # 活跃会话按 app 分组计数 (查询时兜底: heartbeat 超时的不算)
    counts = db.execute_query(
        """
        SELECT app_id, COUNT(*) AS cnt
        FROM active_session s
        LEFT JOIN resource_pool p ON p.id = s.pool_id
        WHERE status IN ('active', 'reclaim_pending')
          AND TIMESTAMPDIFF(SECOND, s.last_heartbeat, NOW()) <= COALESCE(p.stale_timeout_seconds, %(timeout)s)
        GROUP BY app_id
        """,
        {"timeout": timeout},
    )
    count_map = {r["app_id"]: r["cnt"] for r in counts}

    result_apps = []
    total_sessions = 0
    for app in apps:
        cnt = count_map.get(app["id"], 0)
        total_sessions += cnt
        result_apps.append({
            "app_id": app["id"],
            "app_name": app["name"],
            "icon": app["icon"],
            "active_count": cnt,
        })

    # 总在线人数 (去重 user_id)
    online_row = db.execute_query(
        """
        SELECT COUNT(DISTINCT user_id) AS cnt
        FROM active_session s
        LEFT JOIN resource_pool p ON p.id = s.pool_id
        WHERE status IN ('active', 'reclaim_pending')
          AND TIMESTAMPDIFF(SECOND, s.last_heartbeat, NOW()) <= COALESCE(p.stale_timeout_seconds, %(timeout)s)
        """,
        {"timeout": timeout},
        fetch_one=True,
    )
    total_online = online_row["cnt"] if online_row else 0

    return {
        "total_online": total_online,
        "total_sessions": total_sessions,
        "apps": result_apps,
    }


@admin_monitor_router.get("/sessions")
def monitor_sessions(admin: UserInfo = Depends(require_admin)):
    """活跃会话明细"""
    timeout = SESSION_TIMEOUT_SECONDS

    rows = db.execute_query(
        """
        SELECT s.session_id, s.user_id, u.username, u.display_name,
               a.name AS app_name, s.started_at, s.last_heartbeat, s.status,
               TIMESTAMPDIFF(SECOND, s.started_at, NOW()) AS duration_seconds
        FROM active_session s
        JOIN portal_user u ON s.user_id = u.id
        JOIN remote_app a ON s.app_id = a.id
        LEFT JOIN resource_pool p ON p.id = s.pool_id
        WHERE s.status IN ('active', 'reclaim_pending')
          AND TIMESTAMPDIFF(SECOND, s.last_heartbeat, NOW()) <= COALESCE(p.stale_timeout_seconds, %(timeout)s)
        ORDER BY s.started_at DESC
        """,
        {"timeout": timeout},
    )

    for r in rows:
        if r.get("started_at"):
            r["started_at"] = str(r["started_at"])
        if r.get("last_heartbeat"):
            r["last_heartbeat"] = str(r["last_heartbeat"])

    return {"sessions": rows}


# ---- 后台清理任务 ----

def cleanup_stale_sessions():
    """按资源池 stale 策略回收失联会话。"""
    reclaimed = pool_service.reclaim_stale_sessions()
    if reclaimed:
        from backend.router import guac_service
        for item in reclaimed:
            log_event(
                logger,
                logging.INFO,
                "session_reclaimed",
                reason="stale",
                user_id=int(item["user_id"]),
                session_id=str(item["session_id"]),
            )
            invalidate_user_session_if_safe(
                guac_service,
                int(item["user_id"]),
                exclude_session_id=str(item["session_id"]),
            )
        log_event(logger, logging.INFO, "cleanup_batch", reason="stale", count=len(reclaimed))
        dispatch_ready_queue_entries()
    return len(reclaimed)


def cleanup_idle_sessions():
    """按资源池 idle 策略回收空闲会话。"""
    reclaimed = pool_service.reclaim_idle_sessions()
    if reclaimed:
        from backend.router import guac_service
        for item in reclaimed:
            log_event(
                logger,
                logging.INFO,
                "session_reclaimed",
                reason="idle",
                user_id=int(item["user_id"]),
                session_id=str(item["session_id"]),
            )
            invalidate_user_session_if_safe(
                guac_service,
                int(item["user_id"]),
                exclude_session_id=str(item["session_id"]),
            )
        log_event(logger, logging.INFO, "cleanup_batch", reason="idle", count=len(reclaimed))
    return len(reclaimed)


def dispatch_ready_queue_entries():
    """有容量时自动把队首放行到 ready。"""
    try:
        moved = pool_service.dispatch_ready_entries()
    except RuntimeError:
        log_event(logger, logging.INFO, "queue_auto_dispatched", count=0, status="lock_contended")
        return 0
    if moved:
        log_event(logger, logging.INFO, "queue_auto_dispatched", count=len(moved), status="moved")
    return len(moved)
