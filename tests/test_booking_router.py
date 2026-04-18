import asyncio
import importlib
import sys
import types
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from backend.models import UserInfo


def _install_fake_database():
    fake_database = types.ModuleType("backend.database")

    class FakeDb:
        def execute_query(self, *args, **kwargs):
            return None if kwargs.get("fetch_one") else []

        def execute_update(self, *args, **kwargs):
            return 0

        def transaction(self):
            raise AssertionError("test should override router.service with a fake db-backed service")

    fake_database.db = FakeDb()
    fake_database.CONFIG = {"auth": {"jwt_secret": "test-secret-key-with-32-bytes-min!!"}}
    sys.modules["backend.database"] = fake_database


class FakeBookingDb:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.last_insert_params = None
        self.last_cancel_params = None
        self.list_params = None

    class _Transaction:
        def __init__(self, owner):
            self.owner = owner
            self.conn = object()

        def __enter__(self):
            return self.conn

        def __exit__(self, exc_type, exc, tb):
            return False

    def transaction(self):
        return self._Transaction(self)

    def execute_query(self, query, params=None, fetch_one=False, conn=None):
        if "LAST_INSERT_ID()" in query:
            last_id = max((int(row["id"]) for row in self.rows), default=0)
            return {"id": last_id} if fetch_one else [{"id": last_id}]

        if "FROM booking_register" in query and "WHERE user_id = %(user_id)s" in query and "ORDER BY" in query:
            self.list_params = params
            data = [dict(row) for row in self.rows if row["user_id"] == params["user_id"]]
            data.sort(key=lambda row: (row["scheduled_for"], row["id"]), reverse=True)
            return data[0] if fetch_one else data

        if "FROM booking_register" in query and "WHERE id = %(booking_id)s" in query:
            for row in self.rows:
                if row["id"] == params["booking_id"] and row["user_id"] == params["user_id"]:
                    return dict(row) if fetch_one else [dict(row)]
            return None if fetch_one else []

        raise AssertionError(f"unexpected query: {query}")

    def execute_update(self, query, params=None, conn=None):
        if "INSERT INTO booking_register" in query:
            self.last_insert_params = dict(params)
            next_id = max((int(row["id"]) for row in self.rows), default=0) + 1
            self.rows.append(
                {
                    "id": next_id,
                    "user_id": params["user_id"],
                    "app_name": params["app_name"],
                    "scheduled_for": params["scheduled_for"],
                    "purpose": params["purpose"],
                    "note": params["note"],
                    "status": "active",
                    "created_at": "2026-04-16 14:00:00",
                    "cancelled_at": None,
                }
            )
            return 1

        if "UPDATE booking_register" in query:
            self.last_cancel_params = dict(params)
            for row in self.rows:
                if row["id"] == params["booking_id"] and row["user_id"] == params["user_id"] and row["status"] == "active":
                    row["status"] = "cancelled"
                    row["cancelled_at"] = "2026-04-16 15:00:00"
                    return 1
            return 0

        raise AssertionError(f"unexpected update: {query}")


def _request(app: FastAPI, method: str, path: str, payload: dict | None = None):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            kwargs = {"json": payload} if payload is not None else {}
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _build_client(rows):
    _install_fake_database()
    sys.modules.pop("backend.auth", None)
    sys.modules.pop("backend.audit", None)
    sys.modules.pop("backend.booking_router", None)
    sys.modules.pop("backend.booking_service", None)

    auth_module = importlib.import_module("backend.auth")
    booking_router = importlib.import_module("backend.booking_router")
    from backend.booking_service import BookingService

    fake_db = FakeBookingDb(rows)
    booking_router.service = BookingService(db=fake_db)
    booking_router.log_action = lambda *args, **kwargs: None

    app = FastAPI()
    app.include_router(booking_router.router)
    app.dependency_overrides[auth_module.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="测试用户",
        is_admin=False,
    )
    return app, fake_db


def test_list_bookings_returns_only_current_user_rows():
    app, db = _build_client(
        rows=[
            {
                "id": 1,
                "user_id": 7,
                "app_name": "Fluent",
                "scheduled_for": "2026-04-20 09:00:00",
                "purpose": "算例复核",
                "note": "上午先跑一轮",
                "status": "active",
                "created_at": "2026-04-16 12:00:00",
                "cancelled_at": None,
            },
            {
                "id": 2,
                "user_id": 8,
                "app_name": "COMSOL",
                "scheduled_for": "2026-04-19 10:00:00",
                "purpose": "别人的预约",
                "note": "",
                "status": "active",
                "created_at": "2026-04-16 11:00:00",
                "cancelled_at": None,
            },
        ]
    )

    response = _request(app, "GET", "/api/bookings")

    assert response.status_code == 200
    assert db.list_params == {"user_id": 7}
    assert response.json() == [
        {
            "id": 1,
            "user_id": 7,
            "app_name": "Fluent",
            "scheduled_for": "2026-04-20 09:00:00",
            "purpose": "算例复核",
            "note": "上午先跑一轮",
            "status": "active",
            "created_at": "2026-04-16 12:00:00",
            "cancelled_at": None,
        }
    ]


def test_create_booking_returns_created_record_without_scheduler_coupling():
    app, db = _build_client(rows=[])

    response = _request(
        app,
        "POST",
        "/api/bookings",
        {
            "app_name": "Abaqus",
            "scheduled_for": "2026-04-21 13:30:00",
            "purpose": "热处理仿真预约",
            "note": "需要提前导入材料参数",
        },
    )

    assert response.status_code == 200
    assert db.last_insert_params == {
        "user_id": 7,
        "app_name": "Abaqus",
        "scheduled_for": "2026-04-21 13:30:00",
        "purpose": "热处理仿真预约",
        "note": "需要提前导入材料参数",
    }
    assert "pool_id" not in db.last_insert_params
    assert "resource_pool_id" not in db.last_insert_params
    assert response.json() == {
        "id": 1,
        "user_id": 7,
        "app_name": "Abaqus",
        "scheduled_for": "2026-04-21 13:30:00",
        "purpose": "热处理仿真预约",
        "note": "需要提前导入材料参数",
        "status": "active",
        "created_at": "2026-04-16 14:00:00",
        "cancelled_at": None,
    }


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("app_name", "   "),
        ("purpose", "   "),
    ],
)
def test_create_booking_rejects_blank_app_name_and_purpose(field_name, field_value):
    app, db = _build_client(rows=[])
    payload = {
        "app_name": "Abaqus",
        "scheduled_for": "2026-04-21 13:30:00",
        "purpose": "热处理仿真预约",
        "note": "需要提前导入材料参数",
    }
    payload[field_name] = field_value

    response = _request(app, "POST", "/api/bookings", payload)

    assert response.status_code == 422
    assert db.last_insert_params is None


def test_cancel_booking_only_allows_current_users_active_booking():
    app, db = _build_client(
        rows=[
            {
                "id": 3,
                "user_id": 7,
                "app_name": "Fluent",
                "scheduled_for": "2026-04-22 08:30:00",
                "purpose": "晨间校核",
                "note": "",
                "status": "active",
                "created_at": "2026-04-16 12:00:00",
                "cancelled_at": None,
            },
            {
                "id": 4,
                "user_id": 7,
                "app_name": "COMSOL",
                "scheduled_for": "2026-04-22 11:00:00",
                "purpose": "已取消的单子",
                "note": "",
                "status": "cancelled",
                "created_at": "2026-04-16 12:30:00",
                "cancelled_at": "2026-04-16 13:00:00",
            },
            {
                "id": 5,
                "user_id": 9,
                "app_name": "StarCCM+",
                "scheduled_for": "2026-04-22 15:00:00",
                "purpose": "别人的单子",
                "note": "",
                "status": "active",
                "created_at": "2026-04-16 12:40:00",
                "cancelled_at": None,
            },
        ]
    )

    response = _request(app, "POST", "/api/bookings/3/cancel")

    assert response.status_code == 200
    assert db.last_cancel_params == {"booking_id": 3, "user_id": 7}
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancelled_at"] == "2026-04-16 15:00:00"

    missing_response = _request(app, "POST", "/api/bookings/5/cancel")
    assert missing_response.status_code == 404

    inactive_response = _request(app, "POST", "/api/bookings/4/cancel")
    assert inactive_response.status_code == 409


def test_app_registers_booking_router():
    app_py = Path("backend/app.py").read_text(encoding="utf-8")

    assert "booking_router" in app_py
    assert "app.include_router(booking_router)" in app_py


@pytest.mark.parametrize(
    "sql_path",
    [
        Path("database/init.sql"),
        Path("deploy/initdb/01-portal-init.sql"),
        Path("database/migrate_booking_register.sql"),
    ],
)
def test_sql_scripts_define_booking_register_schema(sql_path):
    sql = sql_path.read_text(encoding="utf-8")

    assert "booking_register" in sql
    assert "scheduled_for" in sql
    assert "cancelled_at" in sql
