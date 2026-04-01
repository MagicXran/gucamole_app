"""
Pytest coverage for backend.file_router helpers and endpoints.
"""

import asyncio
import importlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import jwt as pyjwt
import pytest
from fastapi import FastAPI, HTTPException

# Inject mocked upstream modules before importing backend.file_router so the
# tests stay isolated from the real DB/auth stack.
config_path = Path(__file__).resolve().parent.parent / "config" / "config.json"
mock_config = json.loads(config_path.read_text(encoding="utf-8-sig"))
original_backend_pkg = sys.modules.get("backend")
had_backend_file_router_attr = (
    hasattr(original_backend_pkg, "file_router") if original_backend_pkg else False
)
original_backend_file_router_attr = (
    getattr(original_backend_pkg, "file_router")
    if had_backend_file_router_attr
    else None
)
_original_modules = {
    "backend.database": sys.modules.get("backend.database"),
    "backend.audit": sys.modules.get("backend.audit"),
    "backend.auth": sys.modules.get("backend.auth"),
    "backend.file_router": sys.modules.get("backend.file_router"),
}

mock_db = Mock(spec_set=["execute_query"])
mock_db.execute_query.return_value = None
mock_database_module = SimpleNamespace(
    db=mock_db,
    CONFIG=mock_config,
    Database=object,
)
sys.modules["backend.database"] = mock_database_module

mock_audit_module = SimpleNamespace(log_action=Mock())
sys.modules["backend.audit"] = mock_audit_module

mock_auth_module = SimpleNamespace(
    JWT_SECRET="0123456789abcdef0123456789abcdef",
    JWT_ALGORITHM="HS256",
)

from backend.models import UserInfo

test_user = UserInfo(user_id=99, username="tester", display_name="Tester")


def _fake_get_current_user():
    return test_user


mock_auth_module.get_current_user = _fake_get_current_user
sys.modules["backend.auth"] = mock_auth_module

sys.modules.pop("backend.file_router", None)
fr = importlib.import_module("backend.file_router")
for module_name, original_module in _original_modules.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module
current_backend_pkg = sys.modules.get("backend")
if current_backend_pkg is not None:
    if had_backend_file_router_attr:
        current_backend_pkg.file_router = original_backend_file_router_attr
    elif hasattr(current_backend_pkg, "file_router"):
        delattr(current_backend_pkg, "file_router")


@pytest.fixture(autouse=True)
def reset_test_state():
    mock_db.reset_mock()
    mock_db.execute_query.return_value = None
    mock_audit_module.log_action.reset_mock()
    fr._usage_cache.clear()
    yield
    fr._usage_cache.clear()


@pytest.fixture
def drive_base(tmp_path, monkeypatch):
    base = tmp_path / "drive"
    base.mkdir()
    monkeypatch.setattr(fr, "DRIVE_BASE", base)
    return base


@pytest.fixture
def api_app(drive_base):
    app = FastAPI()
    app.include_router(fr.router)
    app.dependency_overrides[fr.get_current_user] = _fake_get_current_user
    return app


def run_request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def _prepare_user_dir(drive_base: Path) -> Path:
    user_dir = drive_base / f"portal_u{test_user.user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "test.txt").write_text("hello", encoding="utf-8")
    (user_dir / "subdir").mkdir(exist_ok=True)
    (user_dir / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")
    return user_dir


def _create_user_file(drive_base: Path, rel_path: str, content: bytes = b"data") -> Path:
    target = drive_base / f"portal_u{test_user.user_id}" / Path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _build_auth_header() -> dict[str, str]:
    token = pyjwt.encode(
        {
            "user_id": test_user.user_id,
            "username": test_user.username,
            "display_name": test_user.display_name,
            "is_admin": test_user.is_admin,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        mock_auth_module.JWT_SECRET,
        algorithm=mock_auth_module.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.00 GB"),
        (5368709120, "5.00 GB"),
    ],
)
def test_format_bytes(value, expected):
    assert fr._format_bytes(value) == expected


@pytest.mark.parametrize(
    "name",
    ["report.pdf", "my file.docx", "中文文件.txt", "data_2024.csv"],
)
def test_validate_filename_accepts(name):
    fr._validate_filename(name)


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "CON", "CON.txt", "file<name", "a:b", "NUL"],
)
def test_validate_filename_rejects(name):
    with pytest.raises(HTTPException):
        fr._validate_filename(name)


@pytest.mark.parametrize(
    "upload_id",
    ["a1b2c3d4e5f67890", "0000000000000000", "abcdef0123456789"],
)
def test_validate_upload_id_accepts(upload_id):
    fr._validate_upload_id(upload_id)


@pytest.mark.parametrize(
    "upload_id",
    [
        "",
        "../../etc/passwd",
        "a1b2c3d4e5f6789",
        "a1b2c3d4e5f678901",
        "ABCDEF0123456789",
        "a1b2c3d4e5f6789g",
    ],
)
def test_validate_upload_id_rejects(upload_id):
    with pytest.raises(HTTPException):
        fr._validate_upload_id(upload_id)


@pytest.mark.parametrize(
    "path",
    ["", ".", "/", "test.txt", "subdir", "subdir/nested.txt"],
)
def test_safe_resolve_accepts_paths(drive_base, path):
    user_dir = _prepare_user_dir(drive_base)
    resolved = fr._safe_resolve(test_user.user_id, path)
    assert str(resolved).startswith(str(user_dir.resolve()))


@pytest.mark.parametrize(
    "path",
    [
        "../../../etc/passwd",
        "..\\..\\..\\etc\\passwd",
        "subdir/../../etc/passwd",
        "../portal_u2/secret.txt",
    ],
)
def test_safe_resolve_blocks_traversal(drive_base, path):
    _prepare_user_dir(drive_base)
    with pytest.raises(HTTPException):
        fr._safe_resolve(test_user.user_id, path)


def test_create_download_token_roundtrip():
    token = fr._create_download_token(
        test_user.user_id,
        "documents/report.pdf",
        username="tester",
    )
    payload = fr._verify_download_token(token)
    assert payload["user_id"] == test_user.user_id
    assert payload["path"] == "documents/report.pdf"
    assert payload["type"] == "download"


def test_verify_download_token_rejects_regular_jwt():
    regular = pyjwt.encode(
        {
            "user_id": test_user.user_id,
            "username": test_user.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        mock_auth_module.JWT_SECRET,
        algorithm=mock_auth_module.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        fr._verify_download_token(regular)


def test_verify_download_token_rejects_expired():
    expired = pyjwt.encode(
        {
            "user_id": test_user.user_id,
            "path": "x.txt",
            "type": "download",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        mock_auth_module.JWT_SECRET,
        algorithm=mock_auth_module.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        fr._verify_download_token(expired)


def test_verify_download_token_rejects_wrong_secret():
    wrong = pyjwt.encode(
        {
            "user_id": test_user.user_id,
            "path": "x.txt",
            "type": "download",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "fedcba9876543210fedcba9876543210",
        algorithm=mock_auth_module.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException):
        fr._verify_download_token(wrong)


def test_calc_dir_size_counts_files(tmp_path):
    root = tmp_path / "dir"
    root.mkdir()
    (root / "a.txt").write_bytes(b"x" * 1000)
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_bytes(b"y" * 2000)
    (root / ".hidden").write_bytes(b"z" * 500)
    assert fr._calc_dir_size(root) == 3500


def test_calc_dir_size_handles_empty_and_missing_paths(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert fr._calc_dir_size(empty) == 0
    assert fr._calc_dir_size(empty / "nope") == 0


def test_space_info(api_app):
    resp = run_request(api_app, "GET", "/api/files/space")
    assert resp.status_code == 200
    data = resp.json()
    assert data["used_bytes"] == 0
    assert "quota_bytes" in data
    assert "usage_percent" in data


def test_list_root_auto_creates(api_app, drive_base):
    resp = run_request(api_app, "GET", "/api/files/list")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert (drive_base / f"portal_u{test_user.user_id}").exists()


def test_mkdir(api_app, drive_base):
    resp = run_request(api_app, "POST", "/api/files/mkdir", json={"path": "Documents"})
    assert resp.status_code == 200
    assert (drive_base / f"portal_u{test_user.user_id}" / "Documents").is_dir()


def test_mkdir_rejects_reserved_name(api_app):
    resp = run_request(api_app, "POST", "/api/files/mkdir", json={"path": "CON"})
    assert resp.status_code == 400


def test_upload_flow(api_app, drive_base):
    content = b"Hello World! " * 100
    size = len(content)

    resp = run_request(
        api_app,
        "POST",
        "/api/files/upload/init",
        data={"path": "Documents/test.txt", "size": str(size)},
    )
    assert resp.status_code == 200
    init_payload = resp.json()
    upload_id = init_payload["upload_id"]
    assert init_payload["offset"] == 0

    resp = run_request(
        api_app,
        "POST",
        "/api/files/upload/chunk",
        data={"upload_id": upload_id, "offset": "0"},
        files={"chunk": ("test.txt", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 200
    chunk_payload = resp.json()
    assert chunk_payload["complete"] is True
    assert chunk_payload["offset"] == size

    final_path = drive_base / f"portal_u{test_user.user_id}" / "Documents" / "test.txt"
    assert final_path.exists()
    assert final_path.read_bytes() == content


def test_list_shows_uploaded_file(api_app, drive_base):
    _create_user_file(drive_base, "Documents/test.txt", b"xyz")
    resp = run_request(api_app, "GET", "/api/files/list", params={"path": "Documents"})
    assert resp.status_code == 200
    names = [entry["name"] for entry in resp.json()["items"]]
    assert "test.txt" in names


def test_download_flow_returns_accel_header(api_app, drive_base):
    _create_user_file(drive_base, "Documents/keep.txt", b"download me")
    token_resp = run_request(
        api_app,
        "POST",
        "/api/files/download-token",
        json={"path": "Documents/keep.txt"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["token"]

    resp = run_request(
        api_app,
        "GET",
        "/api/files/download",
        params={"path": "Documents/keep.txt", "_token": token},
    )
    assert resp.status_code == 200
    assert "X-Accel-Redirect" in resp.headers
    assert resp.headers["X-Accel-Redirect"].startswith(
        f"/internal-drive/portal_u{test_user.user_id}/"
    )
    assert "Content-Disposition" in resp.headers


def test_download_flow_encodes_non_ascii_segments(api_app, drive_base):
    relative_path = "输出/中文 报告.txt"
    _create_user_file(drive_base, relative_path, "内容".encode("utf-8"))
    token_resp = run_request(
        api_app,
        "POST",
        "/api/files/download-token",
        json={"path": relative_path},
    )
    assert token_resp.status_code == 200

    resp = run_request(
        api_app,
        "GET",
        "/api/files/download",
        params={"path": relative_path, "_token": token_resp.json()["token"]},
    )
    assert resp.status_code == 200
    assert resp.headers["X-Accel-Redirect"].endswith(
        "/%E8%BE%93%E5%87%BA/%E4%B8%AD%E6%96%87%20%E6%8A%A5%E5%91%8A.txt"
    )
    assert (
        "filename*=UTF-8''%E4%B8%AD%E6%96%87%20%E6%8A%A5%E5%91%8A.txt"
        in resp.headers["Content-Disposition"]
    )


def test_download_flow_accepts_bearer_jwt(api_app, drive_base):
    _create_user_file(drive_base, "Documents/from-jwt.txt", b"download me")
    resp = run_request(
        api_app,
        "GET",
        "/api/files/download",
        params={"path": "Documents/from-jwt.txt"},
        headers=_build_auth_header(),
    )
    assert resp.status_code == 200
    assert resp.headers["X-Accel-Redirect"].endswith("/Documents/from-jwt.txt")


def test_delete_file(api_app, drive_base):
    target = _create_user_file(drive_base, "Documents/toremove.txt", b"bye")
    resp = run_request(
        api_app,
        "DELETE",
        "/api/files/file",
        params={"path": "Documents/toremove.txt"},
    )
    assert resp.status_code == 200
    assert not target.exists()


def test_delete_root_rejected(api_app):
    resp = run_request(api_app, "DELETE", "/api/files/file", params={"path": ""})
    assert resp.status_code == 400


def test_api_path_traversal_rejected(api_app):
    resp = run_request(api_app, "GET", "/api/files/list", params={"path": "../../etc"})
    assert resp.status_code == 400


def test_upload_oversize_chunk_rejected(api_app):
    resp = run_request(
        api_app,
        "POST",
        "/api/files/upload/init",
        data={"path": "oversize.txt", "size": "100"},
    )
    assert resp.status_code == 200
    upload_id = resp.json()["upload_id"]

    resp = run_request(
        api_app,
        "POST",
        "/api/files/upload/chunk",
        data={"upload_id": upload_id, "offset": "0"},
        files={"chunk": ("oversize.txt", io.BytesIO(b"x" * 200), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_cancel_upload_cleans_temp_files(api_app, drive_base):
    resp = run_request(
        api_app,
        "POST",
        "/api/files/upload/init",
        data={"path": "cancel_me.txt", "size": "10000"},
    )
    assert resp.status_code == 200
    upload_id = resp.json()["upload_id"]

    cancel = run_request(api_app, "DELETE", f"/api/files/upload/{upload_id}")
    assert cancel.status_code == 200

    uploads_dir = drive_base / f"portal_u{test_user.user_id}" / ".uploads"
    assert not (uploads_dir / f"{upload_id}.meta").exists()
    assert not (uploads_dir / f"{upload_id}.tmp").exists()


def test_upload_id_attack_rejected(api_app):
    resp = run_request(api_app, "DELETE", "/api/files/upload/not-hex-upload-id")
    assert resp.status_code == 400
