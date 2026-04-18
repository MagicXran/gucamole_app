import asyncio
from contextlib import contextmanager
import importlib
import sys
import types
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI

from backend.models import UserInfo


def _install_fake_database(fake_db):
    fake_database = types.ModuleType("backend.database")
    fake_database.db = fake_db
    fake_database.CONFIG = {"auth": {"jwt_secret": "test-secret-key-with-32-bytes-min!!"}}
    sys.modules["backend.database"] = fake_database


class FakeCommentDb:
    def __init__(self):
        self.apps = {
            11: {"is_active": 1, "allowed_users": {7, 8}},
            12: {"is_active": 1, "allowed_users": {8}},
            13: {"is_active": 0, "allowed_users": {7}},
        }
        self.cases = {
            21: {"visibility": "public", "status": "published"},
            22: {"visibility": "private", "status": "published"},
            23: {"visibility": "public", "status": "draft"},
        }
        self.users = {
            7: {"username": "tester", "display_name": "测试用户"},
            8: {"username": "another", "display_name": "另一个用户"},
        }
        self.comments = [
            {
                "id": 1,
                "target_type": "app",
                "target_id": 11,
                "user_id": 8,
                "content": "已有评论",
                "created_at": "2026-04-18 09:00:00",
            }
        ]
        self.transaction_token = object()

    @contextmanager
    def transaction(self):
        yield self.transaction_token

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        normalized = " ".join(str(query).split())
        params = params or {}

        if "JOIN remote_app_acl" in normalized and "FROM remote_app" in normalized:
            assert "WHERE remote_app.id = %(target_id)s" in normalized
            app = self.apps.get(int(params["target_id"]))
            user_id = int(params["user_id"])
            row = (
                {"ok": 1}
                if app and int(app["is_active"]) == 1 and user_id in app["allowed_users"]
                else None
            )
            return row if fetch_one else ([row] if row else [])

        if "FROM remote_app" in normalized:
            app = self.apps.get(int(params["target_id"]))
            row = {"ok": 1} if app else None
            return row if fetch_one else ([row] if row else [])

        if "FROM simulation_case" in normalized:
            case = self.cases.get(int(params["target_id"]))
            row = (
                {"ok": 1}
                if case and case["visibility"] == "public" and case["status"] == "published"
                else None
            )
            return row if fetch_one else ([row] if row else [])

        if "SELECT LAST_INSERT_ID() AS id" in normalized:
            assert conn is self.transaction_token
            return {"id": self.comments[-1]["id"]} if fetch_one else [{"id": self.comments[-1]["id"]}]

        if "FROM portal_comment c" in normalized and "WHERE c.id = %(comment_id)s" in normalized:
            assert conn is self.transaction_token
            comment_id = int(params["comment_id"])
            row = next((comment for comment in self.comments if int(comment["id"]) == comment_id), None)
            if not row:
                return None if fetch_one else []
            user = self.users[row["user_id"]]
            payload = {
                **row,
                "username": user["username"],
                "display_name": user["display_name"],
                "author_name": user["display_name"] or user["username"],
            }
            return payload if fetch_one else [payload]

        if "FROM portal_comment c" in normalized:
            rows = []
            for comment in self.comments:
                if comment["target_type"] != params["target_type"] or int(comment["target_id"]) != int(params["target_id"]):
                    continue
                user = self.users[comment["user_id"]]
                rows.append(
                    {
                        **comment,
                        "username": user["username"],
                        "display_name": user["display_name"],
                    }
                )
            rows.sort(key=lambda row: (row["created_at"], row["id"]))
            return rows[0] if fetch_one and rows else rows

        raise AssertionError(f"unexpected query: {query}")

    def execute_update(self, query, params=None, conn=None):
        normalized = " ".join(str(query).split())
        if "INSERT INTO portal_comment" not in normalized:
            raise AssertionError(f"unexpected update: {query}")
        assert conn is self.transaction_token
        self.comments.append(
            {
                "id": len(self.comments) + 1,
                "target_type": params["target_type"],
                "target_id": params["target_id"],
                "user_id": params["user_id"],
                "content": params["content"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return 1


def _build_client(*, override_auth: bool, user_id: int = 7, username: str = "tester", display_name: str = "测试用户"):
    fake_db = FakeCommentDb()
    _install_fake_database(fake_db)
    sys.modules.pop("backend.auth", None)
    sys.modules.pop("backend.comment_router", None)

    auth_module = importlib.import_module("backend.auth")
    comment_router = importlib.import_module("backend.comment_router")
    app = FastAPI()
    app.include_router(comment_router.router)

    if override_auth:
        app.dependency_overrides[auth_module.get_current_user] = lambda: UserInfo(
            user_id=user_id,
            username=username,
            display_name=display_name,
            is_admin=False,
        )
    return app, fake_db


def _request(app: FastAPI, method: str, path: str, json=None):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=json)

    return asyncio.run(_run())


def test_list_and_create_app_comments():
    app, db = _build_client(override_auth=True)

    list_response = _request(app, "GET", "/api/comments?target_type=app&target_id=11")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": 1,
            "target_type": "app",
            "target_id": 11,
            "user_id": 8,
            "author_name": "另一个用户",
            "content": "已有评论",
            "created_at": "2026-04-18 09:00:00",
        }
    ]

    create_response = _request(
        app,
        "POST",
        "/api/comments",
        json={"target_type": "app", "target_id": 11, "content": "  新评论  "},
    )

    assert create_response.status_code == 201
    assert create_response.json()["id"] == 2
    assert create_response.json()["content"] == "新评论"
    assert create_response.json()["author_name"] == "测试用户"
    assert db.comments[-1]["content"] == "新评论"


def test_create_comment_requires_authentication():
    app, db = _build_client(override_auth=False)

    response = _request(
        app,
        "POST",
        "/api/comments",
        json={"target_type": "app", "target_id": 11, "content": "游客评论"},
    )

    assert response.status_code == 401
    assert len(db.comments) == 1


def test_rejects_invalid_targets_and_unpublished_cases():
    app, _db = _build_client(override_auth=True)

    invalid_type_response = _request(app, "GET", "/api/comments?target_type=sdk&target_id=1")
    missing_app_response = _request(
        app,
        "POST",
        "/api/comments",
        json={"target_type": "app", "target_id": 404, "content": "不存在"},
    )
    private_case_response = _request(app, "GET", "/api/comments?target_type=case&target_id=22")
    draft_case_response = _request(
        app,
        "POST",
        "/api/comments",
        json={"target_type": "case", "target_id": 23, "content": "草稿不该评论"},
    )

    assert invalid_type_response.status_code == 400
    assert missing_app_response.status_code == 404
    assert private_case_response.status_code == 404
    assert draft_case_response.status_code == 404


def test_rejects_cross_acl_and_inactive_app_comments():
    app, db = _build_client(override_auth=True, user_id=7, username="tester", display_name="测试用户")

    cross_acl_list_response = _request(app, "GET", "/api/comments?target_type=app&target_id=12")
    cross_acl_create_response = _request(
        app,
        "POST",
        "/api/comments",
        json={"target_type": "app", "target_id": 12, "content": "越权评论"},
    )
    inactive_app_list_response = _request(app, "GET", "/api/comments?target_type=app&target_id=13")

    assert cross_acl_list_response.status_code == 404
    assert cross_acl_create_response.status_code == 404
    assert inactive_app_list_response.status_code == 404
    assert all(comment["target_id"] != 12 for comment in db.comments)


def test_app_registers_comment_router():
    app_py = Path("backend/app.py").read_text(encoding="utf-8")

    assert "comment_router" in app_py
    assert "app.include_router(comment_router)" in app_py
