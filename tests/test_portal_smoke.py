import jwt
import pytest


@pytest.mark.anyio
async def test_login_returns_portal_jwt(async_client, fake_db, backend_modules):
    fake_db.queue_query_result(
        {
            "id": 7,
            "username": "test",
            "password_hash": "$2b$12$L91JPIXfv6upob1STuLlJuIZqese8iUsJdf9G/YwYCw3mIzm7TJs6",
            "display_name": "测试用户",
            "is_admin": 0,
        }
    )

    resp = await async_client.post(
        "/api/auth/login",
        json={"username": "test", "password": "test123"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "test"
    assert body["display_name"] == "测试用户"

    auth_module = backend_modules["auth"]
    payload = jwt.decode(
        body["token"],
        auth_module.JWT_SECRET,
        algorithms=[auth_module.JWT_ALGORITHM],
    )
    assert payload["user_id"] == 7
    assert payload["username"] == "test"
    assert payload["display_name"] == "测试用户"
    assert payload["is_admin"] is False


@pytest.mark.anyio
async def test_launch_returns_redirect_payload_and_records_session(
    async_client, auth_header, fake_db, fake_guac_service
):
    fake_db.queue_query_result({"id": 1})
    fake_db.queue_query_result({"id": 1, "name": "记事本"})
    fake_db.queue_query_result([{"id": 1, "hostname": "rdp-host", "port": 3389}])
    fake_guac_service.redirect_url = "http://portal.test/guacamole/#/client/app_1?token=abc"

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["connection_name"] == "app_1"
    assert body["redirect_url"] == fake_guac_service.redirect_url
    assert body["session_id"]
    assert fake_db.last_insert_table == "active_session"
    assert len(fake_guac_service.launch_calls) == 1
    assert fake_guac_service.launch_calls[0]["username"] == "portal_u7"
    assert fake_guac_service.launch_calls[0]["target_connection_name"] == "app_1"


@pytest.mark.anyio
async def test_monitor_overview_counts_only_fresh_active_sessions(
    async_client, admin_header, fake_db
):
    fake_db.queue_query_result([{"id": 1, "name": "记事本", "icon": "edit"}])
    fake_db.queue_query_result([{"app_id": 1, "cnt": 2}])
    fake_db.queue_query_result({"cnt": 2})
    fake_db.queue_query_result([])

    resp = await async_client.get("/api/admin/monitor/overview", headers=admin_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_online"] == 2
    assert body["apps"][0]["active_count"] == 2
