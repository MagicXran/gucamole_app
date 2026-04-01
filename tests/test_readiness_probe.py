import asyncio

import httpx

import backend.app as backend_app
from backend.database import Database


def _request(method: str, path: str) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=backend_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_health_stays_200_even_if_db_is_broken(monkeypatch):
    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(backend_app.db, "ping", _boom, raising=False)

    resp = _request("GET", "/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_200_when_db_is_available(monkeypatch):
    monkeypatch.setattr(backend_app.db, "ping", lambda: True, raising=False)

    resp = _request("GET", "/ready")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_ready_returns_503_with_reason_when_db_is_unavailable(monkeypatch):
    monkeypatch.setattr(backend_app.db, "ping", lambda: False, raising=False)

    resp = _request("GET", "/ready")

    assert resp.status_code == 503
    assert resp.json().get("reason") == "database_unavailable"


def test_database_exposes_ping_method():
    assert callable(getattr(Database, "ping", None))


def test_lifespan_survives_bootstrap_admin_db_failure(monkeypatch):
    async def _run():
        monkeypatch.setattr(backend_app, "ensure_bootstrap_admin", lambda _db: (_ for _ in ()).throw(Exception("db unavailable")))
        async with backend_app.app.router.lifespan_context(backend_app.app):
            transport = httpx.ASGITransport(app=backend_app.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/health")
        return response

    resp = asyncio.run(_run())

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
