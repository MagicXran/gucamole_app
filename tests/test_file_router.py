import asyncio
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi import FastAPI, HTTPException

import backend.file_router as file_router
from backend.models import UserInfo


TEST_USER = UserInfo(
    user_id=99,
    username="tester",
    display_name="Tester",
    is_admin=False,
)


class FakeDB:
    def __init__(self, quota_bytes=None):
        self.quota_bytes = quota_bytes

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        if "quota_bytes" in query:
            return {"quota_bytes": self.quota_bytes}
        return None if fetch_one else []


def _build_app(tmp_path: Path, monkeypatch, quota_bytes=None) -> FastAPI:
    file_router._usage_cache.clear()
    monkeypatch.setattr(file_router, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(file_router, "db", FakeDB(quota_bytes=quota_bytes))
    monkeypatch.setattr(file_router, "log_action", lambda **kwargs: None)

    app = FastAPI()
    app.include_router(file_router.router)
    app.dependency_overrides[file_router.get_current_user] = lambda: TEST_USER
    return app


def _request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


@pytest.fixture(autouse=True)
def clear_usage_cache():
    file_router._usage_cache.clear()
    yield
    file_router._usage_cache.clear()


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.00 GB"),
        (5368709120, "5.00 GB"),
    ],
)
def test_format_bytes(size, expected):
    assert file_router._format_bytes(size) == expected


@pytest.mark.parametrize("name", ["report.pdf", "my file.docx", "中文文件.txt", "data_2024.csv"])
def test_validate_filename_accepts_safe_names(name):
    file_router._validate_filename(name)


@pytest.mark.parametrize("name", ["", ".", "..", "CON", "CON.txt", "NUL", "file<name", "a:b"])
def test_validate_filename_rejects_unsafe_names(name):
    with pytest.raises(HTTPException):
        file_router._validate_filename(name)


@pytest.mark.parametrize("upload_id", ["a1b2c3d4e5f67890", "0000000000000000", "abcdef0123456789"])
def test_validate_upload_id_accepts_hex_ids(upload_id):
    file_router._validate_upload_id(upload_id)


@pytest.mark.parametrize(
    "upload_id",
    [
        "",
        "../../etc/passwd",
        "a1b2c3d4e5f6789",
        "a1b2c3d4e5f678901",
        "ABCDEF0123456789",
        "a1b2c3d4e5f6789g",
        "../../../evil.meta",
    ],
)
def test_validate_upload_id_rejects_path_attacks(upload_id):
    with pytest.raises(HTTPException):
        file_router._validate_upload_id(upload_id)


def test_safe_resolve_keeps_paths_inside_user_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(file_router, "DRIVE_BASE", tmp_path)
    user_dir = tmp_path / "portal_u1"
    user_dir.mkdir()
    (user_dir / "test.txt").write_text("hello", encoding="utf-8")
    (user_dir / "subdir").mkdir()
    (user_dir / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")

    for relative_path in ["", ".", "/", "test.txt", "subdir", "subdir/nested.txt"]:
        resolved = file_router._safe_resolve(1, relative_path).resolve()
        resolved.relative_to(user_dir.resolve())

    for attack_path in [
        "../../../etc/passwd",
        "..\\..\\..\\etc\\passwd",
        "subdir/../../etc/passwd",
        "../portal_u2/secret.txt",
    ]:
        with pytest.raises(HTTPException):
            file_router._safe_resolve(1, attack_path)


def test_download_token_security():
    token = file_router._create_download_token(1, "test/file.pdf")
    payload = file_router._verify_download_token(token)

    assert payload["user_id"] == 1
    assert payload["path"] == "test/file.pdf"
    assert payload["type"] == "download"

    regular_jwt = jwt.encode(
        {
            "user_id": 1,
            "username": "test",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        file_router.JWT_SECRET,
        algorithm=file_router.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        file_router._verify_download_token(regular_jwt)

    expired = jwt.encode(
        {
            "user_id": 1,
            "path": "x.txt",
            "type": "download",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        file_router.JWT_SECRET,
        algorithm=file_router.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        file_router._verify_download_token(expired)

    wrong_secret = jwt.encode(
        {
            "user_id": 1,
            "path": "x.txt",
            "type": "download",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "wrong-secret-key-with-safe-length-1234",
        algorithm=file_router.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        file_router._verify_download_token(wrong_secret)


def test_calc_dir_size_counts_nested_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 1000)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 2000)
    (tmp_path / ".hidden").write_bytes(b"z" * 500)

    assert file_router._calc_dir_size(tmp_path) == 3500
    empty = tmp_path / "empty"
    empty.mkdir()
    assert file_router._calc_dir_size(empty) == 0
    assert file_router._calc_dir_size(tmp_path / "missing") == 0


def test_file_api_space_list_and_mkdir(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    space = _request(app, "GET", "/api/files/space")
    assert space.status_code == 200
    assert space.json()["used_bytes"] == 0

    root = _request(app, "GET", "/api/files/list")
    assert root.status_code == 200
    assert root.json()["items"] == []
    assert (tmp_path / "portal_u99").exists()

    mkdir = _request(app, "POST", "/api/files/mkdir", json={"path": "Documents"})
    assert mkdir.status_code == 200
    assert (tmp_path / "portal_u99" / "Documents").is_dir()

    reserved = _request(app, "POST", "/api/files/mkdir", json={"path": "CON"})
    assert reserved.status_code == 400


def test_file_api_upload_download_and_delete_flow(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    file_content = b"Hello World! " * 100

    init = _request(
        app,
        "POST",
        "/api/files/upload/init",
        data={"path": "Documents/test.txt", "size": str(len(file_content))},
    )
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]

    chunk = _request(
        app,
        "POST",
        "/api/files/upload/chunk",
        data={"upload_id": upload_id, "offset": "0"},
        files={"chunk": ("test.txt", io.BytesIO(file_content), "application/octet-stream")},
    )
    assert chunk.status_code == 200
    assert chunk.json()["complete"] is True

    final_path = tmp_path / "portal_u99" / "Documents" / "test.txt"
    assert final_path.read_bytes() == file_content

    listed = _request(app, "GET", "/api/files/list?path=Documents")
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["items"]] == ["test.txt"]

    token = _request(
        app,
        "POST",
        "/api/files/download-token",
        json={"path": "Documents/test.txt"},
    )
    assert token.status_code == 200

    download = _request(
        app,
        "GET",
        f"/api/files/download?path=Documents/test.txt&_token={token.json()['token']}",
    )
    assert download.status_code == 200
    assert download.headers["X-Accel-Redirect"].startswith("/internal-drive/portal_u99/")
    assert "Content-Disposition" in download.headers

    deleted = _request(app, "DELETE", "/api/files/file?path=Documents/test.txt")
    assert deleted.status_code == 200
    assert not final_path.exists()


def test_file_api_rejects_root_delete_and_path_traversal(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    delete_root = _request(app, "DELETE", "/api/files/file?path=")
    assert delete_root.status_code == 400

    traversal = _request(app, "GET", "/api/files/list?path=../../etc")
    assert traversal.status_code == 400


def test_file_api_rejects_bad_upload_offsets_and_oversize_chunks(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    init = _request(
        app,
        "POST",
        "/api/files/upload/init",
        data={"path": "bad-offset.txt", "size": "100"},
    )
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]

    bad_offset = _request(
        app,
        "POST",
        "/api/files/upload/chunk",
        data={"upload_id": upload_id, "offset": "1"},
        files={"chunk": ("bad-offset.txt", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert bad_offset.status_code == 409

    oversize = _request(
        app,
        "POST",
        "/api/files/upload/chunk",
        data={"upload_id": upload_id, "offset": "0"},
        files={"chunk": ("bad-offset.txt", io.BytesIO(b"x" * 200), "application/octet-stream")},
    )
    assert oversize.status_code == 400
    uploads_dir = tmp_path / "portal_u99" / ".uploads"
    assert not (uploads_dir / f"{upload_id}.meta").exists()
    assert not (uploads_dir / f"{upload_id}.tmp").exists()


def test_file_api_cancel_upload_cleans_temp_files(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    init = _request(
        app,
        "POST",
        "/api/files/upload/init",
        data={"path": "cancel-me.txt", "size": "10000"},
    )
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]

    canceled = _request(app, "DELETE", f"/api/files/upload/{upload_id}")
    assert canceled.status_code == 200
    uploads_dir = tmp_path / "portal_u99" / ".uploads"
    assert not (uploads_dir / f"{upload_id}.meta").exists()
    assert not (uploads_dir / f"{upload_id}.tmp").exists()


def test_file_api_rejects_quota_exhaustion_on_init(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, quota_bytes=10)

    rejected = _request(
        app,
        "POST",
        "/api/files/upload/init",
        data={"path": "too-large.txt", "size": "11"},
    )

    assert rejected.status_code == 422
