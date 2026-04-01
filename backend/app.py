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
from fastapi.staticfiles import StaticFiles

from backend.database import CONFIG, db
from backend.auth import router as auth_router
from backend.bootstrap_admin import ensure_bootstrap_admin
from backend.router import router
from backend.admin_router import router as admin_router
from backend.admin_pool_router import router as admin_pool_router
from backend.monitor import (
    router as monitor_router,
    admin_monitor_router,
    cleanup_stale_sessions,
    cleanup_idle_sessions,
    dispatch_ready_queue_entries,
)
from backend.dataset_router import router as dataset_router
from backend.file_router import router as file_router, cleanup_stale_uploads

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

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
    bootstrap_result = ensure_bootstrap_admin(db)
    if bootstrap_result.get("created"):
        logger.warning("启动管理员已创建: %s", bootstrap_result.get("username"))
    task = asyncio.create_task(_cleanup_loop())
    upload_task = asyncio.create_task(_upload_cleanup_loop())
    logger.info("会话清理任务已启动 (间隔 %ds)", CLEANUP_INTERVAL)
    logger.info("上传清理任务已启动 (间隔 3600s)")
    yield
    task.cancel()
    upload_task.cancel()
    for t in (task, upload_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


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
app.include_router(router)
app.include_router(admin_router)
app.include_router(admin_pool_router)
app.include_router(monitor_router)
app.include_router(admin_monitor_router)
app.include_router(dataset_router)
app.include_router(file_router)

# 静态文件（前端）
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=CONFIG["api"]["host"],
        port=CONFIG["api"]["port"],
        log_level="info",
    )
