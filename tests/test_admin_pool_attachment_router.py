import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from backend.app_attachment_service import AppAttachmentService
from backend.models import UserInfo


def _load_admin_pool_router():
    fake_database = types.ModuleType("backend.database")
    fake_auth = types.ModuleType("backend.auth")
    fake_monitor = types.ModuleType("backend.monitor")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

        def execute_update(self, *args, **kwargs):
            return 0

    fake_database.db = FakeDb()
    fake_database.CONFIG = {"monitor": {}, "api": {"prefix": "/api/remote-apps"}}
    fake_auth.require_admin = lambda: None
    fake_auth.get_current_user = lambda: None
    fake_monitor.invalidate_user_session_if_safe = lambda *args, **kwargs: None
    sys.modules["backend.database"] = fake_database
    sys.modules["backend.auth"] = fake_auth
    sys.modules["backend.monitor"] = fake_monitor

    sys.modules.pop("backend.admin_pool_router", None)
    return importlib.import_module("backend.admin_pool_router")


def _request(app: FastAPI, method: str, path: str, payload: dict | None = None):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            kwargs = {"json": payload} if payload is not None else {}
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


class FakeAdminAttachmentDb:
    def __init__(self, rows):
        self.rows = rows
        self.access_checks = []
        self.last_query = ""
        self.last_params = None

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        if "SELECT 1 AS ok FROM remote_app" in query:
            self.access_checks.append(params)
            return None if fetch_one else []
        self.last_query = query
        self.last_params = params
        if fetch_one:
            return self.rows[0] if self.rows else None
        return list(self.rows)


def _build_app(fake_service):
    admin_pool_router = _load_admin_pool_router()
    app = FastAPI()
    app.include_router(admin_pool_router.router)
    app.dependency_overrides[admin_pool_router.require_admin] = lambda: UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )
    admin_pool_router.attachment_service = fake_service
    admin_pool_router.log_action = lambda *args, **kwargs: None
    return app


def test_admin_pool_attachment_get_returns_grouped_payload():
    db = FakeAdminAttachmentDb(
        rows=[
            {
                "id": 1,
                "pool_id": 7,
                "attachment_kind": "tutorial_doc",
                "title": "手册",
                "summary": "管理员可见",
                "url": "https://example/doc",
                "sort_order": 1,
            }
        ]
    )
    app = _build_app(AppAttachmentService(db=db))
    response = _request(app, "GET", "/api/admin/pools/7/attachments")

    assert response.status_code == 200
    assert db.access_checks == []
    assert db.last_params == {"pool_id": 7}
    assert response.json() == {
        "pool_id": 7,
        "tutorial_docs": [
            {
                "id": 1,
                "title": "手册",
                "summary": "管理员可见",
                "link_url": "https://example/doc",
                "sort_order": 1,
            }
        ],
        "video_resources": [],
        "plugin_downloads": [],
    }


def test_admin_pool_attachment_put_replaces_payload():
    calls = []

    class FakeService:
        def replace_pool_attachments(self, *, pool_id, payload):
            calls.append((pool_id, payload))
            return {
                "pool_id": pool_id,
                "tutorial_docs": [{"id": 0, **item} for item in payload["tutorial_docs"]],
                "video_resources": [{"id": 0, **item} for item in payload["video_resources"]],
                "plugin_downloads": [{"id": 0, **item} for item in payload["plugin_downloads"]],
            }

    app = _build_app(FakeService())
    request = {
        "tutorial_docs": [{"title": "手册", "summary": "PDF", "link_url": "https://example/doc", "sort_order": 1}],
        "video_resources": [{"title": "视频", "summary": "MP4", "link_url": "https://example/video", "sort_order": 2}],
        "plugin_downloads": [{"title": "插件", "summary": "ZIP", "link_url": "https://example/plugin", "sort_order": 3}],
    }
    response = _request(app, "PUT", "/api/admin/pools/7/attachments", request)

    assert response.status_code == 200
    assert calls == [(7, request)]
    assert response.json()["plugin_downloads"][0]["title"] == "插件"


def test_admin_pool_attachment_put_rejects_unsafe_link_scheme():
    class FakeService:
        def replace_pool_attachments(self, *, pool_id, payload):
            raise AssertionError("unsafe payload should be rejected before service call")

    app = _build_app(FakeService())
    request = {
        "tutorial_docs": [{"title": "危险", "summary": "XSS", "link_url": "javascript:alert(1)", "sort_order": 1}],
        "video_resources": [],
        "plugin_downloads": [],
    }

    response = _request(app, "PUT", "/api/admin/pools/7/attachments", request)

    assert response.status_code == 422
    assert "http" in str(response.json())
