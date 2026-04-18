"""
Guacamole RemoteApp 门户 - FastAPI 主应用
"""

import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持 python backend/app.py 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import configure_logging, log_extra
from backend.database import CONFIG
from backend.auth import router as auth_router
from backend.router import router
from backend.admin_router import router as admin_router
from backend.admin_analytics_router import router as admin_analytics_router
from backend.admin_pool_router import router as admin_pool_router
from backend.admin_worker_router import router as admin_worker_router
from backend.app_attachment_router import router as app_attachment_router
from backend.booking_router import router as booking_router
from backend.case_center_router import router as case_center_router
from backend.comment_router import router as comment_router
from backend.session_router import router as session_router
from backend.sdk_center_router import router as sdk_center_router
from backend.monitor import (
    router as monitor_router,
    admin_monitor_router,
    cleanup_stale_sessions,
    cleanup_idle_sessions,
    dispatch_ready_queue_entries,
)
from backend.dataset_router import router as dataset_router
from backend.file_router import router as file_router, cleanup_stale_uploads
from backend.task_router import router as task_router
from backend.worker_monitor import reconcile_offline_workers, reconcile_stalled_assigned_tasks
from backend.worker_router import router as worker_router

logger = logging.getLogger(__name__)

_monitor_cfg = CONFIG.get("monitor", {})
CLEANUP_INTERVAL = _monitor_cfg.get("cleanup_interval_seconds", 60)


async def _cleanup_loop():
    """后台循环: 定期清理占用并自动放行队首"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            cleanup_stale_sessions()
            cleanup_idle_sessions()
            reconcile_offline_workers()
            reconcile_stalled_assigned_tasks()
            dispatch_ready_queue_entries()
        except Exception:
            logger.exception("资源池清理/放行异常")


async def _upload_cleanup_loop():
    """后台循环: 每小时清理过期上传临时文件"""
    while True:
        await asyncio.sleep(3600)
        try:
            cleanup_stale_uploads()
        except Exception:
            logger.exception("清理过期上传异常")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期: 启动后台清理任务"""
    configure_logging(logging.INFO)
    task = asyncio.create_task(_cleanup_loop())
    upload_task = asyncio.create_task(_upload_cleanup_loop())
    logger.info(
        "Portal 启动完成",
        extra=log_extra(
            "portal_startup",
            cleanup_interval_seconds=CLEANUP_INTERVAL,
            upload_cleanup_interval_seconds=3600,
        ),
    )
    logger.info(
        "会话清理任务已启动",
        extra=log_extra(
            "session_cleanup_loop_started",
            cleanup_interval_seconds=CLEANUP_INTERVAL,
        ),
    )
    logger.info(
        "上传清理任务已启动",
        extra=log_extra(
            "upload_cleanup_loop_started",
            cleanup_interval_seconds=3600,
        ),
    )
    yield
    logger.info("Portal 开始关闭", extra=log_extra("portal_shutdown_started"))
    task.cancel()
    upload_task.cancel()
    for t in (task, upload_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    logger.info("Portal 已关闭", extra=log_extra("portal_shutdown_completed"))


app = FastAPI(
    title="Guacamole RemoteApp 门户",
    description="通过 Encrypted JSON Auth 集成 Apache Guacamole 的 RemoteApp 门户",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG["api"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# 健康检查
@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


# API 路由
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(sdk_center_router)
app.include_router(app_attachment_router)
app.include_router(booking_router)
app.include_router(case_center_router)
app.include_router(comment_router)
app.include_router(router)
app.include_router(admin_router)
app.include_router(admin_analytics_router)
app.include_router(admin_pool_router)
app.include_router(admin_worker_router)
app.include_router(monitor_router)
app.include_router(admin_monitor_router)
app.include_router(dataset_router)
app.include_router(file_router)
app.include_router(task_router)
app.include_router(worker_router)

# Vue3 门户（独立挂载，支持 history 模式深链刷新）
portal_ui_path = Path(__file__).parent.parent / "frontend" / "portal"
portal_ui_assets_path = portal_ui_path / "assets"
if portal_ui_path.exists():
    if portal_ui_assets_path.exists():
        app.mount(
            "/portal/assets",
            StaticFiles(directory=str(portal_ui_assets_path)),
            name="portal-ui-assets",
        )

    @app.get("/portal", include_in_schema=False)
    @app.get("/portal/", include_in_schema=False)
    @app.get("/portal/{full_path:path}", include_in_schema=False)
    def portal_ui_index(full_path: str = ""):
        return FileResponse(str(portal_ui_path / "index.html"))

# 静态文件（前端）
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    configure_logging(logging.INFO, replace_handlers=True)
    uvicorn.run(
        app,
        host=CONFIG["api"]["host"],
        port=CONFIG["api"]["port"],
        log_level="info",
        log_config=None,
    )
