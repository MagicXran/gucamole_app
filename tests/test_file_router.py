import pytest
from fastapi import HTTPException

def test_validate_upload_id_rejects_path_traversal(file_router_module):
    with pytest.raises(HTTPException):
        file_router_module._validate_upload_id("../../etc/passwd")


def test_download_token_round_trip(file_router_module):
    token = file_router_module._create_download_token(99, "docs/test.txt", "tester")
    payload = file_router_module._verify_download_token(token)
    assert payload["user_id"] == 99
    assert payload["path"] == "docs/test.txt"
    assert payload["type"] == "download"


def test_safe_resolve_blocks_parent_escape(tmp_path, monkeypatch, file_router_module):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    user_dir = tmp_path / "portal_u1"
    user_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(HTTPException):
        file_router_module._safe_resolve(1, "../portal_u2/secret.txt")


def test_safe_resolve_keeps_user_scope(tmp_path, monkeypatch, file_router_module):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    user_dir = tmp_path / "portal_u8"
    user_dir.mkdir(parents=True, exist_ok=True)

    resolved = file_router_module._safe_resolve(8, "sub/hello.txt")
    assert resolved == (user_dir / "sub" / "hello.txt").resolve()


@pytest.mark.anyio
async def test_space_api_returns_quota_contract(
    async_client, auth_header, fake_db, tmp_path, monkeypatch, file_router_module
):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    file_router_module._usage_cache.clear()
    fake_db.queue_query_result({"quota_bytes": None})

    resp = await async_client.get("/api/files/space", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["used_bytes"] == 0
    assert "quota_bytes" in body
    assert "usage_percent" in body


@pytest.mark.anyio
async def test_list_api_auto_creates_user_root(
    async_client, auth_header, tmp_path, monkeypatch, file_router_module
):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    file_router_module._usage_cache.clear()

    resp = await async_client.get("/api/files/list", headers=auth_header)

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert (tmp_path / "portal_u7").exists()


@pytest.mark.anyio
async def test_mkdir_api_creates_folder(
    async_client, auth_header, tmp_path, monkeypatch, file_router_module
):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    file_router_module._usage_cache.clear()

    resp = await async_client.post("/api/files/mkdir", headers=auth_header, json={"path": "Docs"})

    assert resp.status_code == 200
    assert (tmp_path / "portal_u7" / "Docs").is_dir()


@pytest.mark.anyio
async def test_upload_init_returns_upload_id_and_offset(
    async_client, auth_header, fake_db, tmp_path, monkeypatch, file_router_module
):
    monkeypatch.setattr(file_router_module, "DRIVE_BASE", tmp_path)
    file_router_module._usage_cache.clear()
    fake_db.queue_query_result({"quota_bytes": None})

    resp = await async_client.post(
        "/api/files/upload/init",
        headers=auth_header,
        files={
            "path": (None, "Docs/test.txt"),
            "size": (None, "12"),
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["upload_id"]) == 16
    assert body["offset"] == 0
