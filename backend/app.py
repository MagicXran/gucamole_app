"""
Guacamole RemoteApp 门户 - FastAPI 主应用
"""

import sys
import asyncio
import logging
import importlib
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

# 确保项目根目录在 sys.path 中（支持 python backend/app.py 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend import configure_logging, log_extra
from scripts.verify_portal_schema import check_live_schema

logger = logging.getLogger(__name__)
APP_UPLOAD_CLEANUP_INTERVAL = 3600
DEFAULT_CLEANUP_INTERVAL = 60


def _frontend_root() -> Path:
    return Path(__file__).parent.parent / "frontend"


def _portal_ui_root() -> Path:
    return _frontend_root() / "portal"


def _portal_ui_available() -> bool:
    return _portal_ui_root().exists()


def _get_runtime_config():
    database_module = sys.modules.get("backend.database")
    if database_module is None:
        database_module = importlib.import_module("backend.database")

    if hasattr(database_module, "get_config"):
        return database_module.get_config()
    return database_module.CONFIG


async def _cleanup_loop(cleanup_interval_seconds: int):
    """后台循环: 定期清理占用并自动放行队首"""
    from backend.monitor import (
        cleanup_stale_sessions,
        cleanup_idle_sessions,
        dispatch_ready_queue_entries,
    )
    from backend.worker_monitor import (
        reconcile_offline_workers,
        reconcile_stalled_assigned_tasks,
    )

    while True:
        await asyncio.sleep(cleanup_interval_seconds)
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
    from backend.file_router import cleanup_stale_uploads

    while True:
        await asyncio.sleep(APP_UPLOAD_CLEANUP_INTERVAL)
        try:
            cleanup_stale_uploads()
        except Exception:
            logger.exception("清理过期上传异常")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期: 启动后台清理任务"""
    configure_logging(logging.INFO)
    cleanup_interval_seconds = int(getattr(app.state, "cleanup_interval_seconds", DEFAULT_CLEANUP_INTERVAL))
    task = asyncio.create_task(_cleanup_loop(cleanup_interval_seconds))
    upload_task = asyncio.create_task(_upload_cleanup_loop())
    logger.info(
        "Portal 启动完成",
        extra=log_extra(
            "portal_startup",
            cleanup_interval_seconds=cleanup_interval_seconds,
            upload_cleanup_interval_seconds=APP_UPLOAD_CLEANUP_INTERVAL,
        ),
    )
    logger.info(
        "会话清理任务已启动",
        extra=log_extra(
            "session_cleanup_loop_started",
            cleanup_interval_seconds=cleanup_interval_seconds,
        ),
    )
    logger.info(
        "上传清理任务已启动",
        extra=log_extra(
            "upload_cleanup_loop_started",
            cleanup_interval_seconds=APP_UPLOAD_CLEANUP_INTERVAL,
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


def health():
    return {"status": "ok"}


def ready():
    readiness = check_live_schema()
    schema_check = dict(readiness["checks"]["schema"])
    problems = list(schema_check.pop("problems", []))
    schema_check["problem_count"] = len(problems)
    http_payload = {
        "ok": readiness["ok"],
        "status": readiness["status"],
        "checks": {
            "schema": schema_check,
        },
    }
    status_code = 200 if readiness["ok"] else 503
    return JSONResponse(status_code=status_code, content=http_payload)


def root_redirect():
    return RedirectResponse(url="/portal", status_code=307)


def index_redirect():
    return RedirectResponse(url="/portal", status_code=307)


def admin_redirect():
    return RedirectResponse(url="/portal/admin/apps", status_code=307)


def viewer_entry(request: Request):
    viewer_path = _frontend_root() / "viewer.html"
    if request.query_params.get("path", "").strip():
        return FileResponse(str(viewer_path))
    return RedirectResponse(url="/portal/my/workspace", status_code=307)


def _register_core_routes(app: FastAPI):
    app.add_api_route("/health", health, methods=["GET"], tags=["ops"])
    app.add_api_route("/health/ready", ready, methods=["GET"], tags=["ops"])
    app.add_api_route("/", root_redirect, methods=["GET"], include_in_schema=False)
    app.add_api_route("/index.html", index_redirect, methods=["GET"], include_in_schema=False)
    app.add_api_route("/admin.html", admin_redirect, methods=["GET"], include_in_schema=False)
    app.add_api_route("/viewer.html", viewer_entry, methods=["GET"], include_in_schema=False)


def _mount_portal_frontend(app: FastAPI):
    portal_ui_path = _portal_ui_root()
    portal_ui_assets_path = portal_ui_path / "assets"
    if portal_ui_path.exists():
        if portal_ui_assets_path.exists():
            app.mount(
                "/portal/assets",
                StaticFiles(directory=str(portal_ui_assets_path)),
                name="portal-ui-assets",
            )

        def portal_ui_index(full_path: str = ""):
            return FileResponse(str(portal_ui_path / "index.html"))

        app.add_api_route("/portal", portal_ui_index, methods=["GET"], include_in_schema=False)
        app.add_api_route("/portal/", portal_ui_index, methods=["GET"], include_in_schema=False)
        app.add_api_route("/portal/{full_path:path}", portal_ui_index, methods=["GET"], include_in_schema=False)

    frontend_path = _frontend_root()
    if frontend_path.exists():
        app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


def create_app() -> FastAPI:
    config = _get_runtime_config()
    from backend.auth import router as auth_router
    from backend.router import router as remote_apps_router
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
    from backend.monitor import router as monitor_router, admin_monitor_router
    from backend.dataset_router import router as dataset_router
    from backend.file_router import router as file_router
    from backend.task_router import router as task_router
    from backend.worker_router import router as worker_router

    app = FastAPI(
        title="Guacamole RemoteApp 门户",
        description="通过 Encrypted JSON Auth 集成 Apache Guacamole 的 RemoteApp 门户",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.cleanup_interval_seconds = int(
        config.get("monitor", {}).get("cleanup_interval_seconds", DEFAULT_CLEANUP_INTERVAL)
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["api"]["cors_origins"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    _register_core_routes(app)

    app.include_router(auth_router)
    app.include_router(session_router)
    app.include_router(sdk_center_router)
    app.include_router(app_attachment_router)
    app.include_router(booking_router)
    app.include_router(case_center_router)
    app.include_router(comment_router)
    app.include_router(remote_apps_router)
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

    _mount_portal_frontend(app)
    return app


class _LazyFastAPIApp:
    def __init__(self, factory):
        self._factory = factory
        self._app = None
        self._lock = Lock()

    def _ensure_app(self) -> FastAPI:
        if self._app is not None:
            return self._app
        with self._lock:
            if self._app is None:
                self._app = self._factory()
            return self._app

    async def __call__(self, scope, receive, send):
        app = self._ensure_app()
        await app(scope, receive, send)

    def __getattr__(self, item):
        return getattr(self._ensure_app(), item)


def get_app() -> FastAPI:
    return app._ensure_app()


app = _LazyFastAPIApp(create_app)


if __name__ == "__main__":
    import uvicorn

    config = _get_runtime_config()
    runtime_app = get_app()
    configure_logging(logging.INFO, replace_handlers=True)
    uvicorn.run(
        runtime_app,
        host=config["api"]["host"],
        port=config["api"]["port"],
        log_level="info",
        log_config=None,
    )
