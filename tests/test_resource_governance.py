import pytest

import backend.resource_governance as rg


@pytest.mark.parametrize(
    "app_row, expected",
    [
        ({}, False),
        ({"max_concurrent_sessions": None, "max_concurrent_per_user": None}, False),
        ({"max_concurrent_sessions": 0, "max_concurrent_per_user": 0}, False),
        ({"max_concurrent_sessions": -1, "max_concurrent_per_user": 0}, False),
        ({"max_concurrent_sessions": 1, "max_concurrent_per_user": None}, True),
        ({"max_concurrent_sessions": 0, "max_concurrent_per_user": 2}, True),
    ],
)
def test_governance_enabled_only_when_any_limit_positive(app_row, expected):
    assert rg.governance_enabled(app_row) is expected


def test_limits_reached_by_app_limit():
    app_row = {"max_concurrent_sessions": 2, "max_concurrent_per_user": None}
    assert rg.limits_reached(active_count=2, user_active_count=0, app_row=app_row) is True


def test_limits_reached_by_per_user_limit():
    app_row = {"max_concurrent_sessions": None, "max_concurrent_per_user": 1}
    assert rg.limits_reached(active_count=0, user_active_count=1, app_row=app_row) is True


def test_enqueue_or_refresh_creates_waiting_entry_and_returns_position(fake_db):
    fake_db.queue_query_result(None)
    fake_db.queue_query_result({"position": 1})

    result = rg.enqueue_or_refresh(fake_db, app_id=10, user_id=7)

    assert result["position"] == 1
    assert result["created"] is True
    assert len(fake_db.executed_updates) == 1
    assert "INSERT INTO launch_queue" in fake_db.executed_updates[0][0]


def test_enqueue_or_refresh_reuses_existing_waiting_entry(fake_db):
    fake_db.queue_query_result({"id": 3, "app_id": 10, "user_id": 7, "status": "waiting"})
    fake_db.queue_query_result({"position": 2})

    result = rg.enqueue_or_refresh(fake_db, app_id=10, user_id=7)

    assert result["position"] == 2
    assert result["created"] is False
    assert len(fake_db.executed_updates) == 1
    assert "UPDATE launch_queue" in fake_db.executed_updates[0][0]


def test_is_queue_head_respects_oldest_waiting_row(fake_db):
    fake_db.queue_query_result({"user_id": 7})
    assert rg.is_queue_head(fake_db, app_id=1, user_id=7) is True

    fake_db.queue_query_result({"user_id": 8})
    assert rg.is_queue_head(fake_db, app_id=1, user_id=7) is False


def test_expire_stale_queue_entries_issues_expected_update(fake_db):
    fake_db.queue_update_result(4)

    rows = rg.expire_stale_queue_entries(fake_db)

    assert rows == 4
    assert len(fake_db.executed_updates) == 1
    sql, params = fake_db.executed_updates[0]
    assert "UPDATE launch_queue q" in sql
    assert "SET q.status = 'expired'" in sql
    assert params is None


@pytest.mark.anyio
async def test_launch_returns_queued_response_when_limit_hit_and_queue_enabled(
    async_client, auth_header, fake_db, backend_modules, fake_guac_service, monkeypatch
):
    router_module = backend_modules["router"]
    rg_module = backend_modules["resource_governance"]

    fake_db.queue_query_result({"ok": 1})
    fake_db.queue_query_result(
        {
            "id": 1,
            "name": "记事本",
            "queue_enabled": 1,
            "max_concurrent_sessions": 1,
            "max_concurrent_per_user": None,
            "queue_timeout_seconds": 300,
        }
    )

    monkeypatch.setattr(rg_module, "expire_stale_queue_entries", lambda db: 0)
    monkeypatch.setattr(rg_module, "governance_enabled", lambda app_row: True)
    monkeypatch.setattr(rg_module, "get_active_counts", lambda db, app_id, user_id, timeout_seconds: {
        "active_count": 1,
        "user_active_count": 0,
    })
    monkeypatch.setattr(rg_module, "get_waiting_entry", lambda db, app_id, user_id: None)
    monkeypatch.setattr(rg_module, "has_waiting_entries", lambda db, app_id: False)
    monkeypatch.setattr(rg_module, "limits_reached", lambda active_count, user_active_count, app_row: True)
    monkeypatch.setattr(rg_module, "enqueue_or_refresh", lambda db, app_id, user_id: {"position": 2, "created": True})

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["queue_position"] == 2
    assert body["retry_after_seconds"] == 5
    assert fake_guac_service.launch_calls == []


@pytest.mark.anyio
async def test_launch_rejects_when_limit_hit_and_queue_disabled(
    async_client, auth_header, fake_db, backend_modules, monkeypatch
):
    rg_module = backend_modules["resource_governance"]

    fake_db.queue_query_result({"ok": 1})
    fake_db.queue_query_result(
        {
            "id": 1,
            "name": "记事本",
            "queue_enabled": 0,
            "max_concurrent_sessions": 1,
            "max_concurrent_per_user": None,
            "queue_timeout_seconds": 300,
        }
    )

    monkeypatch.setattr(rg_module, "expire_stale_queue_entries", lambda db: 0)
    monkeypatch.setattr(rg_module, "governance_enabled", lambda app_row: True)
    monkeypatch.setattr(rg_module, "get_active_counts", lambda db, app_id, user_id, timeout_seconds: {
        "active_count": 1,
        "user_active_count": 0,
    })
    monkeypatch.setattr(rg_module, "get_waiting_entry", lambda db, app_id, user_id: None)
    monkeypatch.setattr(rg_module, "has_waiting_entries", lambda db, app_id: False)
    monkeypatch.setattr(rg_module, "limits_reached", lambda active_count, user_active_count, app_row: True)

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 409
    assert resp.json()["detail"] == "当前应用占用已满，请稍后再试"


@pytest.mark.anyio
async def test_launch_does_not_bypass_existing_wait_queue(
    async_client, auth_header, fake_db, backend_modules, fake_guac_service, monkeypatch
):
    rg_module = backend_modules["resource_governance"]

    fake_db.queue_query_result({"ok": 1})
    fake_db.queue_query_result(
        {
            "id": 1,
            "name": "记事本",
            "queue_enabled": 1,
            "max_concurrent_sessions": 1,
            "max_concurrent_per_user": None,
            "queue_timeout_seconds": 300,
        }
    )

    monkeypatch.setattr(rg_module, "expire_stale_queue_entries", lambda db: 0)
    monkeypatch.setattr(rg_module, "governance_enabled", lambda app_row: True)
    monkeypatch.setattr(rg_module, "get_active_counts", lambda db, app_id, user_id, timeout_seconds: {
        "active_count": 0,
        "user_active_count": 0,
    })
    monkeypatch.setattr(rg_module, "get_waiting_entry", lambda db, app_id, user_id: None)
    monkeypatch.setattr(rg_module, "has_waiting_entries", lambda db, app_id: True)
    monkeypatch.setattr(rg_module, "limits_reached", lambda active_count, user_active_count, app_row: False)
    monkeypatch.setattr(rg_module, "enqueue_or_refresh", lambda db, app_id, user_id: {"position": 3, "created": True})

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["queue_position"] == 3
    assert fake_guac_service.launch_calls == []


@pytest.mark.anyio
async def test_head_of_queue_can_launch_when_capacity_frees_up(
    async_client, auth_header, fake_db, backend_modules, fake_guac_service, monkeypatch
):
    rg_module = backend_modules["resource_governance"]

    fake_db.queue_query_result({"ok": 1})
    fake_db.queue_query_result(
        {
            "id": 1,
            "name": "记事本",
            "queue_enabled": 1,
            "max_concurrent_sessions": 1,
            "max_concurrent_per_user": None,
            "queue_timeout_seconds": 300,
        }
    )
    fake_db.queue_query_result([{"id": 1, "hostname": "rdp-host", "port": 3389}])

    removed = []
    monkeypatch.setattr(rg_module, "expire_stale_queue_entries", lambda db: 0)
    monkeypatch.setattr(rg_module, "governance_enabled", lambda app_row: True)
    monkeypatch.setattr(rg_module, "get_active_counts", lambda db, app_id, user_id, timeout_seconds: {
        "active_count": 0,
        "user_active_count": 0,
    })
    monkeypatch.setattr(rg_module, "get_waiting_entry", lambda db, app_id, user_id: {"id": 9})
    monkeypatch.setattr(rg_module, "has_waiting_entries", lambda db, app_id: True)
    monkeypatch.setattr(rg_module, "limits_reached", lambda active_count, user_active_count, app_row: False)
    monkeypatch.setattr(rg_module, "is_queue_head", lambda db, app_id, user_id: True)
    monkeypatch.setattr(rg_module, "remove_waiting_entry", lambda db, app_id, user_id: removed.append((app_id, user_id)))
    fake_guac_service.redirect_url = "http://portal.test/guacamole/#/client/app_1?token=xyz"

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["redirect_url"] == fake_guac_service.redirect_url
    assert removed == [(1, 7)]
    assert len(fake_guac_service.launch_calls) == 1


def test_cleanup_stale_sessions_expires_waiting_queue_entries(backend_modules, fake_db, monkeypatch):
    monitor_module = backend_modules["monitor"]
    rg_module = backend_modules["resource_governance"]

    fake_db.queue_update_result(2)
    calls = []
    monkeypatch.setattr(rg_module, "expire_stale_queue_entries", lambda db: calls.append(db) or 3)

    monitor_module.cleanup_stale_sessions()

    assert calls == [fake_db]


@pytest.mark.anyio
async def test_monitor_overview_includes_queued_counts(async_client, admin_header, fake_db):
    fake_db.queue_query_result([{"id": 1, "name": "记事本", "icon": "edit"}])
    fake_db.queue_query_result([{"app_id": 1, "cnt": 2}])
    fake_db.queue_query_result({"cnt": 2})
    fake_db.queue_query_result([{"app_id": 1, "cnt": 4}])

    resp = await async_client.get("/api/admin/monitor/overview", headers=admin_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_queued"] == 4
    assert body["apps"][0]["queued_count"] == 4


@pytest.mark.anyio
async def test_monitor_queue_endpoint_returns_waiting_entries(async_client, admin_header, fake_db):
    fake_db.queue_query_result(
        [
            {
                "queue_id": 9,
                "app_id": 1,
                "app_name": "记事本",
                "user_id": 7,
                "username": "test",
                "display_name": "测试用户",
                "created_at": "2026-03-30 18:00:00",
                "updated_at": "2026-03-30 18:01:00",
                "position": 1,
            }
        ]
    )

    resp = await async_client.get("/api/admin/monitor/queue", headers=admin_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["queue_id"] == 9
    assert body["items"][0]["position"] == 1


@pytest.mark.anyio
async def test_admin_can_cancel_waiting_queue_entry(async_client, admin_header, fake_db):
    fake_db.queue_update_result(1)

    resp = await async_client.delete("/api/admin/monitor/queue/9", headers=admin_header)

    assert resp.status_code == 200
    assert resp.json()["message"] == "已移出队列"
