import asyncio
import importlib
from pathlib import Path
import sys
import types

import pytest
from fastapi import FastAPI
import httpx

from backend.models import UserInfo


def _install_fake_database():
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

    fake_database.db = FakeDb()
    fake_database.CONFIG = {"auth": {"jwt_secret": "test-secret-key-with-32-bytes-min!!"}}
    sys.modules["backend.database"] = fake_database


class FakeAttachmentDb:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = ""
        self.last_params = None
        self.access_query = ""
        self.access_params = None

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        if "SELECT 1 AS ok FROM remote_app" in query:
            self.access_query = query
            self.access_params = params
            if params["pool_id"] == 999:
                return None if fetch_one else []
            return {"ok": 1} if fetch_one else [{"ok": 1}]
        self.last_query = query
        self.last_params = params
        if fetch_one:
            return self.rows[0] if self.rows else None
        return list(self.rows)


class TransactionalAttachmentDb:
    def __init__(self, rows, *, fail_on_title=None):
        self.rows = [dict(row) for row in rows]
        self.fail_on_title = fail_on_title
        self.committed = False
        self.rolled_back = False
        self.transaction_started = False
        self._working_rows = None

    class _Transaction:
        def __init__(self, owner):
            self.owner = owner
            self.conn = object()

        def __enter__(self):
            self.owner.transaction_started = True
            self.owner._working_rows = [dict(row) for row in self.owner.rows]
            return self.conn

        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                self.owner.rows = self.owner._working_rows
                self.owner.committed = True
            else:
                self.owner.rolled_back = True
            self.owner._working_rows = None
            return False

    def transaction(self):
        return self._Transaction(self)

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        active_rows = [row for row in self.rows if row["pool_id"] == params["pool_id"] and row.get("is_active", 1) == 1]
        if fetch_one:
            return active_rows[0] if active_rows else None
        return active_rows

    def execute_update(self, query, params=None, conn=None):
        target_rows = self._working_rows if conn is not None else self.rows
        if "UPDATE app_attachment" in query:
            for row in target_rows:
                if row["pool_id"] == params["pool_id"]:
                    row["is_active"] = 0
            return 1
        if self.fail_on_title and params["title"] == self.fail_on_title:
            raise RuntimeError("insert failed")
        next_id = max((int(row["id"]) for row in target_rows), default=0) + 1
        target_rows.append(
            {
                "id": next_id,
                "pool_id": params["pool_id"],
                "attachment_kind": params["attachment_kind"],
                "title": params["title"],
                "summary": params["summary"],
                "url": params["url"],
                "sort_order": params["sort_order"],
                "is_active": 1,
            }
        )
        return 1


def _build_client(*, rows, override_auth):
    _install_fake_database()
    sys.modules.pop("backend.auth", None)
    sys.modules.pop("backend.audit", None)
    auth_module = importlib.import_module("backend.auth")
    sys.modules.pop("backend.app_attachment_router", None)
    router = importlib.import_module("backend.app_attachment_router").router
    from backend.app_attachment_service import AppAttachmentService

    app = FastAPI()
    app.include_router(router)

    if override_auth:
        app.dependency_overrides[auth_module.get_current_user] = lambda: UserInfo(
            user_id=7,
            username="tester",
            display_name="测试用户",
            is_admin=False,
        )

    db = FakeAttachmentDb(rows)
    router.service = AppAttachmentService(db=db)
    return app, db


def _request(app: FastAPI, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_get_pool_attachments_requires_authentication():
    app, _db = _build_client(rows=[], override_auth=False)

    response = _request(app, "/api/app-attachments/pools/9")

    assert response.status_code == 401
    assert response.json()["detail"] in {"未提供认证令牌", "Not authenticated"}


def test_get_pool_attachments_returns_grouped_payload():
    app, db = _build_client(
        rows=[
            {
                "id": 11,
                "pool_id": 9,
                "attachment_kind": "tutorial_doc",
                "title": "新手手册",
                "summary": "PDF 指南",
                "url": "https://example.com/tutorial.pdf",
                "sort_order": 2,
            },
            {
                "id": 12,
                "pool_id": 9,
                "attachment_kind": "video_resource",
                "title": "演示视频",
                "summary": "录播",
                "url": "https://example.com/demo.mp4",
                "sort_order": 1,
            },
            {
                "id": 13,
                "pool_id": 9,
                "attachment_kind": "plugin_download",
                "title": "插件包",
                "summary": "ZIP 压缩包",
                "url": "https://example.com/plugin.zip",
                "sort_order": 3,
            },
        ],
        override_auth=True,
    )

    response = _request(app, "/api/app-attachments/pools/9")

    assert response.status_code == 200
    assert db.last_params == {"pool_id": 9}
    assert response.json() == {
        "pool_id": 9,
        "tutorial_docs": [
            {
                "id": 11,
                "title": "新手手册",
                "summary": "PDF 指南",
                "link_url": "https://example.com/tutorial.pdf",
                "sort_order": 2,
            }
        ],
        "video_resources": [
            {
                "id": 12,
                "title": "演示视频",
                "summary": "录播",
                "link_url": "https://example.com/demo.mp4",
                "sort_order": 1,
            }
        ],
        "plugin_downloads": [
            {
                "id": 13,
                "title": "插件包",
                "summary": "ZIP 压缩包",
                "link_url": "https://example.com/plugin.zip",
                "sort_order": 3,
            }
        ],
    }


def test_service_returns_empty_groups_for_unknown_pool():
    from backend.app_attachment_service import AppAttachmentService

    db = FakeAttachmentDb(rows=[])
    service = AppAttachmentService(db=db)

    payload = service.list_pool_attachments(pool_id=404, user_id=7)

    assert db.last_params == {"pool_id": 404}
    assert payload == {
        "pool_id": 404,
        "tutorial_docs": [],
        "video_resources": [],
        "plugin_downloads": [],
    }


def test_service_returns_empty_groups_for_inaccessible_pool():
    from backend.app_attachment_service import AppAttachmentService

    db = FakeAttachmentDb(rows=[{"id": 99, "pool_id": 999, "attachment_kind": "tutorial_doc", "title": "秘密", "summary": "保密", "url": "https://secret", "sort_order": 1}])
    service = AppAttachmentService(db=db)

    payload = service.list_pool_attachments(pool_id=999, user_id=7)

    assert db.access_params == {"pool_id": 999, "user_id": 7}
    assert payload == {
        "pool_id": 999,
        "tutorial_docs": [],
        "video_resources": [],
        "plugin_downloads": [],
    }
    assert "p.is_active = 1" in db.access_query


def test_service_filters_unsafe_historical_attachment_links():
    from backend.app_attachment_service import AppAttachmentService

    db = FakeAttachmentDb(
        rows=[
            {
                "id": 11,
                "pool_id": 9,
                "attachment_kind": "tutorial_doc",
                "title": "安全手册",
                "summary": "PDF",
                "url": "https://example.com/tutorial.pdf",
                "sort_order": 1,
            },
            {
                "id": 12,
                "pool_id": 9,
                "attachment_kind": "tutorial_doc",
                "title": "脏数据",
                "summary": "别返回",
                "url": "javascript:alert(1)",
                "sort_order": 2,
            },
        ]
    )
    service = AppAttachmentService(db=db)

    payload = service.list_pool_attachments_for_admin(pool_id=9)

    assert payload == {
        "pool_id": 9,
        "tutorial_docs": [
            {
                "id": 11,
                "title": "安全手册",
                "summary": "PDF",
                "link_url": "https://example.com/tutorial.pdf",
                "sort_order": 1,
            }
        ],
        "video_resources": [],
        "plugin_downloads": [],
    }


def test_replace_pool_attachments_rolls_back_when_insert_fails():
    from backend.app_attachment_service import AppAttachmentService

    db = TransactionalAttachmentDb(
        rows=[
            {
                "id": 1,
                "pool_id": 9,
                "attachment_kind": "tutorial_doc",
                "title": "旧手册",
                "summary": "旧摘要",
                "url": "https://example.com/old.pdf",
                "sort_order": 0,
                "is_active": 1,
            }
        ],
        fail_on_title="坏附件",
    )
    service = AppAttachmentService(db=db)

    with pytest.raises(RuntimeError, match="insert failed"):
        service.replace_pool_attachments(
            pool_id=9,
            payload={
                "tutorial_docs": [
                    {
                        "title": "坏附件",
                        "summary": "会失败",
                        "link_url": "https://example.com/bad.pdf",
                        "sort_order": 0,
                    }
                ],
                "video_resources": [],
                "plugin_downloads": [],
            },
        )

    assert db.transaction_started is True
    assert db.rolled_back is True
    assert db.committed is False
    assert db.rows == [
        {
            "id": 1,
            "pool_id": 9,
            "attachment_kind": "tutorial_doc",
            "title": "旧手册",
            "summary": "旧摘要",
            "url": "https://example.com/old.pdf",
            "sort_order": 0,
            "is_active": 1,
        }
    ]


def test_app_registers_app_attachment_router():
    app_py = Path("backend/app.py").read_text(encoding="utf-8")

    assert "app_attachment_router" in app_py
    assert "app.include_router(app_attachment_router)" in app_py


@pytest.mark.parametrize(
    "sql_path",
    [
        Path("database/migrate_app_attachment.sql"),
        Path("database/init.sql"),
        Path("deploy/initdb/01-portal-init.sql"),
    ],
)
def test_sql_scripts_define_app_attachment_schema(sql_path):
    sql = sql_path.read_text(encoding="utf-8")

    assert "app_attachment" in sql
    assert "tutorial_doc" in sql
    assert "video_resource" in sql
    assert "plugin_download" in sql
