import asyncio
import sys
import types

import httpx
from fastapi import FastAPI

import backend.admin_pool_router as admin_pool_router
import backend.monitor as monitor
from backend.models import UserInfo
from backend.resource_pool_service import ResourcePoolService


class FakeSessionDB:
    def __init__(self, active_sessions_by_user=None):
        self.active_sessions_by_user = {
            user_id: set(session_ids)
            for user_id, session_ids in (active_sessions_by_user or {}).items()
        }

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        params = params or {}
        if "FROM active_session" in query and "status = 'active'" in query:
            user_id = params["uid"]
            exclude_sid = params.get("exclude_sid")
            candidates = {
                sid for sid in self.active_sessions_by_user.get(user_id, set())
                if sid != exclude_sid
            }
            row = {"exists": 1} if candidates else None
            if fetch_one:
                return row
            return [row] if row else []
        if fetch_one:
            return None
        return []


class FakeGuacService:
    def __init__(self):
        self.invalidated = []

    def invalidate_user_session(self, username: str):
        self.invalidated.append(username)


class FakeMonitorPoolService:
    def __init__(self, reclaimed_items):
        self.reclaimed_items = reclaimed_items

    def reclaim_stale_sessions(self):
        return list(self.reclaimed_items)

    def reclaim_idle_sessions(self):
        return list(self.reclaimed_items)

    def dispatch_ready_entries(self):
        return []


class FakeAdminPoolService:
    def __init__(self, result):
        self.result = result

    def reclaim_session(self, session_id: str):
        return dict(self.result)


class FakeResourcePoolReclaimDB:
    def __init__(self, *, stale_rows=None, idle_rows=None):
        self.stale_rows = list(stale_rows or [])
        self.idle_rows = list(idle_rows or [])
        self.marked = []
        self.fallback_stale_timeout_seconds = None
        self.fallback_idle_timeout_seconds = None

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "/* rps:list_stale_sessions */" in query:
            if "LEFT JOIN resource_pool" in query and "COALESCE(p.stale_timeout_seconds" in query:
                self.fallback_stale_timeout_seconds = params.get("fallback_stale_timeout_seconds")
                return list(self.stale_rows)
            return []
        if "/* rps:list_idle_sessions */" in query:
            if "LEFT JOIN resource_pool" in query and "COALESCE(p.idle_timeout_seconds" in query:
                self.fallback_idle_timeout_seconds = params.get("fallback_idle_timeout_seconds")
                return list(self.idle_rows)
            return []
        if fetch_one:
            return None
        return []

    def execute_update(self, query: str, params=None) -> int:
        params = params or {}
        if "/* rps:session_mark_reclaimed */" not in query:
            return 0
        session_id = str(params.get("session_id") or "")
        known_ids = {str(row["session_id"]) for row in (self.stale_rows + self.idle_rows)}
        if session_id not in known_ids:
            return 0
        self.marked.append(
            (session_id, str(params.get("reason")), str(params.get("target_status")))
        )
        return 1


def _install_router_stub(monkeypatch, guac_service: FakeGuacService):
    module = types.ModuleType("backend.router")
    module.guac_service = guac_service
    monkeypatch.setitem(sys.modules, "backend.router", module)


def _build_admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_pool_router.router)
    app.dependency_overrides[admin_pool_router.require_admin] = lambda: UserInfo(
        user_id=1,
        username="admin",
        display_name="管理员",
        is_admin=True,
    )
    return app


def _request(app: FastAPI, method: str, path: str) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_cleanup_idle_sessions_skips_cache_invalidation_when_user_has_other_active_session(monkeypatch):
    guac = FakeGuacService()
    _install_router_stub(monkeypatch, guac)
    monkeypatch.setattr(
        monitor,
        "pool_service",
        FakeMonitorPoolService([
            {"session_id": "reclaimed-session", "user_id": 2},
        ]),
    )
    monkeypatch.setattr(
        monitor,
        "db",
        FakeSessionDB({2: {"reclaimed-session", "still-active"}}),
    )

    reclaimed_count = monitor.cleanup_idle_sessions()

    assert reclaimed_count == 1
    assert guac.invalidated == []


def test_cleanup_idle_sessions_invalidates_cache_when_reclaimed_session_is_last_active_one(monkeypatch):
    guac = FakeGuacService()
    _install_router_stub(monkeypatch, guac)
    monkeypatch.setattr(
        monitor,
        "pool_service",
        FakeMonitorPoolService([
            {"session_id": "reclaimed-session", "user_id": 2},
        ]),
    )
    monkeypatch.setattr(
        monitor,
        "db",
        FakeSessionDB({2: {"reclaimed-session"}}),
    )

    reclaimed_count = monitor.cleanup_idle_sessions()

    assert reclaimed_count == 1
    assert guac.invalidated == ["portal_u2"]


def test_cleanup_stale_sessions_skips_cache_invalidation_when_user_has_other_active_session(monkeypatch):
    guac = FakeGuacService()
    _install_router_stub(monkeypatch, guac)
    monkeypatch.setattr(
        monitor,
        "pool_service",
        FakeMonitorPoolService([
            {"session_id": "reclaimed-session", "user_id": 2},
        ]),
    )
    monkeypatch.setattr(
        monitor,
        "db",
        FakeSessionDB({2: {"reclaimed-session", "still-active"}}),
    )

    reclaimed_count = monitor.cleanup_stale_sessions()

    assert reclaimed_count == 1
    assert guac.invalidated == []


def test_admin_reclaim_skips_cache_invalidation_when_user_has_other_active_session(monkeypatch):
    guac = FakeGuacService()
    _install_router_stub(monkeypatch, guac)
    monkeypatch.setattr(
        admin_pool_router,
        "pool_service",
        FakeAdminPoolService({
            "session_id": "reclaimed-session",
            "status": "reclaim_pending",
            "user_id": 2,
        }),
    )
    monkeypatch.setattr(
        admin_pool_router,
        "db",
        FakeSessionDB({2: {"reclaimed-session", "still-active"}}),
    )
    monkeypatch.setattr(admin_pool_router, "log_action", lambda *args, **kwargs: None)
    app = _build_admin_app()

    response = _request(app, "POST", "/api/admin/pools/sessions/reclaimed-session/reclaim")

    assert response.status_code == 200
    assert guac.invalidated == []


def test_reclaim_stale_sessions_handles_orphan_rows_with_null_pool_id():
    db = FakeResourcePoolReclaimDB(
        stale_rows=[
            {"session_id": "stale-null-pool", "user_id": 9, "pool_id": None},
        ]
    )
    service = ResourcePoolService(db=db)

    reclaimed = service.reclaim_stale_sessions()

    assert reclaimed == [{"session_id": "stale-null-pool", "user_id": 9}]
    assert db.marked == [("stale-null-pool", "stale", "reclaimed")]
    assert db.fallback_stale_timeout_seconds == ResourcePoolService.DEFAULT_STALE_TIMEOUT_SECONDS


def test_reclaim_idle_sessions_handles_orphan_rows_with_null_pool_id():
    db = FakeResourcePoolReclaimDB(
        idle_rows=[
            {"session_id": "idle-null-pool", "user_id": 11, "pool_id": None},
        ]
    )
    service = ResourcePoolService(db=db)

    reclaimed = service.reclaim_idle_sessions()

    assert reclaimed == [{"session_id": "idle-null-pool", "user_id": 11}]
    assert db.marked == [("idle-null-pool", "idle", "reclaim_pending")]
    assert db.fallback_idle_timeout_seconds == ResourcePoolService.DEFAULT_ORPHAN_IDLE_TIMEOUT_SECONDS


def test_default_orphan_timeouts_follow_monitor_session_timeout_config():
    assert ResourcePoolService.DEFAULT_STALE_TIMEOUT_SECONDS == monitor.SESSION_TIMEOUT_SECONDS
    assert ResourcePoolService.DEFAULT_ORPHAN_IDLE_TIMEOUT_SECONDS == monitor.SESSION_TIMEOUT_SECONDS
