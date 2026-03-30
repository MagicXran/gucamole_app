"""
实时监控 - 心跳追踪与会话管理
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.database import db, CONFIG
from backend.auth import get_current_user, require_admin
from backend.models import UserInfo
import backend.resource_governance as rg

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
        """
        SELECT id, name, icon, max_concurrent_sessions, max_concurrent_per_user,
               queue_enabled, queue_timeout_seconds
        FROM remote_app
        WHERE is_active = 1
        ORDER BY id
        """
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

    queue_counts = db.execute_query(
        """
        SELECT app_id, COUNT(*) AS cnt
        FROM launch_queue
        WHERE status = 'waiting'
        GROUP BY app_id
        """
    )
    queue_count_map = {r["app_id"]: r["cnt"] for r in queue_counts}

    result_apps = []
    total_sessions = 0
    total_queued = 0
    for app in apps:
        cnt = count_map.get(app["id"], 0)
        queued_cnt = queue_count_map.get(app["id"], 0)
        total_sessions += cnt
        total_queued += queued_cnt
        result_apps.append({
            "app_id": app["id"],
            "app_name": app["name"],
            "icon": app["icon"],
            "active_count": cnt,
            "queued_count": queued_cnt,
            "max_concurrent_sessions": app.get("max_concurrent_sessions"),
            "max_concurrent_per_user": app.get("max_concurrent_per_user"),
            "queue_enabled": bool(app.get("queue_enabled", 0)),
            "queue_timeout_seconds": app.get("queue_timeout_seconds", 300),
        })

    return {
        "total_online": total_online,
        "total_sessions": total_sessions,
        "total_queued": total_queued,
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


@admin_monitor_router.get("/queue")
def monitor_queue(admin: UserInfo = Depends(require_admin)):
    """等待队列明细"""
    rows = db.execute_query(
        """
        SELECT q.id AS queue_id, q.app_id, a.name AS app_name,
               q.user_id, u.username, u.display_name,
               q.created_at, q.updated_at,
               (
                   SELECT COUNT(*)
                   FROM launch_queue q2
                   WHERE q2.app_id = q.app_id
                     AND q2.status = 'waiting'
                     AND q2.id <= q.id
               ) AS position
        FROM launch_queue q
        JOIN portal_user u ON q.user_id = u.id
        JOIN remote_app a ON q.app_id = a.id
        WHERE q.status = 'waiting'
        ORDER BY q.created_at ASC, q.id ASC
        """
    )

    for row in rows:
        if row.get("created_at"):
            row["created_at"] = str(row["created_at"])
        if row.get("updated_at"):
            row["updated_at"] = str(row["updated_at"])

    return {"items": rows}


@admin_monitor_router.delete("/queue/{queue_id}")
def cancel_queue_entry(queue_id: int, admin: UserInfo = Depends(require_admin)):
    """管理员移出等待队列"""
    rows = db.execute_update(
        """
        UPDATE launch_queue
        SET status = 'cancelled'
        WHERE id = %(queue_id)s
          AND status = 'waiting'
        """,
        {"queue_id": queue_id},
    )
    if rows == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "队列项不存在或已失效")
    return {"message": "已移出队列"}


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
    queue_rows = rg.expire_stale_queue_entries(db)
    if queue_rows > 0:
        logger.info("清理过期排队项: %d 条", queue_rows)
