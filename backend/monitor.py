"""
实时监控 - 心跳追踪与会话管理
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.database import db, CONFIG
from backend.auth import get_current_user, require_admin
from backend.models import UserInfo

logger = logging.getLogger(__name__)

_monitor_cfg = CONFIG.get("monitor", {})
SESSION_TIMEOUT_SECONDS = _monitor_cfg.get("session_timeout_seconds", 120)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])
admin_monitor_router = APIRouter(prefix="/api/admin/monitor", tags=["admin-monitor"])


# ---- 请求模型 ----

class HeartbeatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=36)


class SessionEndRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=36)


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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在或已结束")
    return {"ok": True}


@router.post("/session-end")
def session_end(req: SessionEndRequest):
    """关闭会话: sendBeacon 调用, 无 JWT (浏览器限制).
    安全性依赖 session_id UUID 的不可猜测性。
    """
    db.execute_update(
        """
        UPDATE active_session
        SET status = 'disconnected', ended_at = NOW()
        WHERE session_id = %(sid)s AND status = 'active'
        """,
        {"sid": req.session_id},
    )
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
        FROM active_session
        WHERE status = 'active'
          AND last_heartbeat > DATE_SUB(NOW(), INTERVAL %(timeout)s SECOND)
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
        FROM active_session
        WHERE status = 'active'
          AND last_heartbeat > DATE_SUB(NOW(), INTERVAL %(timeout)s SECOND)
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
        WHERE s.status = 'active'
          AND s.last_heartbeat > DATE_SUB(NOW(), INTERVAL %(timeout)s SECOND)
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
    """清理超时会话: last_heartbeat 超过阈值且 status 仍为 active 的行"""
    timeout = SESSION_TIMEOUT_SECONDS
    rows = db.execute_update(
        """
        UPDATE active_session
        SET status = 'disconnected', ended_at = NOW()
        WHERE status = 'active'
          AND last_heartbeat < DATE_SUB(NOW(), INTERVAL %(timeout)s SECOND)
        """,
        {"timeout": timeout},
    )
    if rows > 0:
        logger.info("清理超时会话: %d 条", rows)
