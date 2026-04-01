"""
Guacamole RemoteApp 门户 - FastAPI 主应用
"""

import sys
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持 python backend/app.py 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
from backend.structured_logging import StructuredLogFormatter, log_event

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.setFormatter(
        StructuredLogFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
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
    try:
        bootstrap_result = ensure_bootstrap_admin(db)
    except RuntimeError:
        raise
    except Exception:
        logger.warning("启动管理员检查失败，继续启动以保留 liveness", exc_info=True)
        bootstrap_result = {"created": False, "reason": "startup_check_failed"}
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


@app.middleware("http")
async def request_access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.ERROR,
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else "unknown",
        )
        raise

    response.headers["X-Request-ID"] = request_id
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_event(
        logger,
        logging.INFO,
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        duration_ms=duration_ms,
        client_ip=request.client.host if request.client else "unknown",
    )
    return response


# 健康检查
@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
def ready():
    try:
        if db.ping():
            return {"status": "ready"}
    except Exception:
        pass
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "reason": "database_unavailable"},
    )


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
        access_log=False,
    )
