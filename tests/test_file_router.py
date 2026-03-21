"""
file_router.py 综合测试 — Mock DB, 测试所有关键逻辑
"""

import sys
import os
import json
import tempfile
import shutil
import re
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

# ================================================================
# Phase 0: Mock DB layer BEFORE any backend import
# ================================================================

# Load config
config_path = Path(__file__).parent.parent / "config" / "config.json"
mock_config = json.loads(config_path.read_text(encoding="utf-8-sig"))

# Create mock database module and inject into sys.modules BEFORE import
mock_db = MagicMock()
mock_database_module = MagicMock()
mock_database_module.db = mock_db
mock_database_module.CONFIG = mock_config
mock_database_module.Database = MagicMock
sys.modules["backend.database"] = mock_database_module

# Mock audit module
mock_audit_module = MagicMock()
mock_audit_module.log_action = MagicMock()
sys.modules["backend.audit"] = mock_audit_module

# Mock auth module — create real JWT functions
import jwt as pyjwt
mock_auth_module = MagicMock()
mock_auth_module.JWT_SECRET = "test-secret-key"
mock_auth_module.JWT_ALGORITHM = "HS256"

# Real get_current_user (will be overridden in TestClient)
from backend.models import UserInfo
mock_auth_module.get_current_user = MagicMock()
sys.modules["backend.auth"] = mock_auth_module

# Now import file_router
from backend.file_router import (
    _safe_resolve, _validate_filename, _validate_upload_id,
    _format_bytes, _create_download_token, _verify_download_token,
    _calc_dir_size, _user_dir, DRIVE_BASE,
)
import backend.file_router as fr

print("[OK] file_router imported successfully")

all_errors = []


def run_test(name, fn):
    try:
        fn()
        print(f"  {name}: [OK]")
    except AssertionError as e:
        all_errors.append(f"{name}: {e}")
        print(f"  {name}: [FAIL] {e}")
    except Exception as e:
        all_errors.append(f"{name}: {e}")
        print(f"  {name}: [ERROR] {e}")


# ================================================================
# Phase 1: _format_bytes
# ================================================================

print("\n" + "=" * 60)
print("Phase 1: _format_bytes")
print("=" * 60)

tests_fb = [
    (0, "0 B"), (512, "512 B"), (1024, "1.0 KB"),
    (1048576, "1.0 MB"), (1073741824, "1.00 GB"),
    (5368709120, "5.00 GB"),
]
for inp, exp in tests_fb:
    def test(i=inp, e=exp):
        result = _format_bytes(i)
        assert result == e, f"expected '{e}', got '{result}'"
    run_test(f"_format_bytes({inp})", test)

# ================================================================
# Phase 2: _validate_filename
# ================================================================

print("\n" + "=" * 60)
print("Phase 2: _validate_filename")
print("=" * 60)

valid_names = ["report.pdf", "my file.docx", "\u4e2d\u6587\u6587\u4ef6.txt", "data_2024.csv"]
for name in valid_names:
    def test(n=name):
        _validate_filename(n)  # should not raise
    run_test(f"accept '{name}'", test)

invalid_names = ["", ".", "..", "CON", "CON.txt", "NUL", "file<name", "a:b"]
for name in invalid_names:
    def test(n=name):
        try:
            _validate_filename(n)
            raise AssertionError("should have been rejected")
        except Exception as e:
            if "AssertionError" in str(type(e)):
                raise
    run_test(f"reject '{name}'", test)

# ================================================================
# Phase 3: _validate_upload_id
# ================================================================

print("\n" + "=" * 60)
print("Phase 3: _validate_upload_id (path traversal defense)")
print("=" * 60)

valid_ids = ["a1b2c3d4e5f67890", "0000000000000000", "abcdef0123456789"]
for uid in valid_ids:
    def test(u=uid):
        _validate_upload_id(u)
    run_test(f"accept '{uid}'", test)

invalid_ids = [
    ("empty", ""),
    ("traversal", "../../etc/passwd"),
    ("too_short", "a1b2c3d4e5f6789"),
    ("too_long", "a1b2c3d4e5f678901"),
    ("uppercase", "ABCDEF0123456789"),
    ("bad_char", "a1b2c3d4e5f6789g"),
    ("path_attack", "../../../evil.meta"),
]
for label, uid in invalid_ids:
    def test(u=uid):
        try:
            _validate_upload_id(u)
            raise AssertionError("should have been rejected")
        except Exception as e:
            if "AssertionError" in str(type(e)):
                raise
    run_test(f"reject {label}: '{uid}'", test)

# ================================================================
# Phase 4: _safe_resolve (path traversal)
# ================================================================

print("\n" + "=" * 60)
print("Phase 4: _safe_resolve path traversal")
print("=" * 60)

tmpdir = Path(tempfile.mkdtemp())
original_base = fr.DRIVE_BASE
fr.DRIVE_BASE = tmpdir

user_dir = tmpdir / "portal_u1"
user_dir.mkdir()
(user_dir / "test.txt").write_text("hello")
(user_dir / "subdir").mkdir()
(user_dir / "subdir" / "nested.txt").write_text("nested")

# Valid paths
valid_paths = ["", ".", "/", "test.txt", "subdir", "subdir/nested.txt"]
for p in valid_paths:
    def test(path=p):
        result = _safe_resolve(1, path)
        # Must be inside user_dir
        resolved_user = user_dir.resolve()
        resolved_result = result.resolve()
        assert str(resolved_result).startswith(str(resolved_user)), \
            f"result {resolved_result} outside user dir {resolved_user}"
    run_test(f"valid path '{p}'", test)

# Attack paths
attack_paths = [
    ("parent traversal", "../../../etc/passwd"),
    ("backslash traversal", "..\\..\\..\\etc\\passwd"),
    ("mid-path traversal", "subdir/../../etc/passwd"),
    ("user escape", "../portal_u2/secret.txt"),
]
for label, p in attack_paths:
    def test(path=p):
        try:
            result = _safe_resolve(1, path)
            # If it returned, check it's still inside user_dir
            resolved_user = user_dir.resolve()
            resolved_result = result.resolve()
            if not str(resolved_result).startswith(str(resolved_user)):
                raise AssertionError(f"ESCAPED to {resolved_result}")
        except Exception as e:
            if "AssertionError" in str(type(e)):
                raise
            # HTTPException = correctly blocked
            pass
    run_test(f"block {label}", test)

fr.DRIVE_BASE = original_base
shutil.rmtree(tmpdir)

# ================================================================
# Phase 5: Download token security
# ================================================================

print("\n" + "=" * 60)
print("Phase 5: Download token security")
print("=" * 60)

import jwt as pyjwt

# Valid token
def test_valid_token():
    token = _create_download_token(1, "test/file.pdf")
    payload = _verify_download_token(token)
    assert payload["user_id"] == 1
    assert payload["path"] == "test/file.pdf"
    assert payload["type"] == "download"
run_test("valid download token", test_valid_token)

# Regular JWT should be rejected
def test_regular_jwt():
    regular = pyjwt.encode(
        {"user_id": 1, "username": "test",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "test-secret-key", algorithm="HS256"
    )
    try:
        _verify_download_token(regular)
        raise AssertionError("regular JWT accepted as download token")
    except Exception as e:
        if "AssertionError" in str(type(e)):
            raise
run_test("reject regular JWT as download token", test_regular_jwt)

# Expired token
def test_expired():
    expired = pyjwt.encode(
        {"user_id": 1, "path": "x.txt", "type": "download",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        "test-secret-key", algorithm="HS256"
    )
    try:
        _verify_download_token(expired)
        raise AssertionError("expired token accepted")
    except Exception as e:
        if "AssertionError" in str(type(e)):
            raise
run_test("reject expired token", test_expired)

# Wrong secret
def test_wrong_secret():
    bad = pyjwt.encode(
        {"user_id": 1, "path": "x.txt", "type": "download",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "wrong-secret", algorithm="HS256"
    )
    try:
        _verify_download_token(bad)
        raise AssertionError("wrong-secret token accepted")
    except Exception as e:
        if "AssertionError" in str(type(e)):
            raise
run_test("reject wrong-secret token", test_wrong_secret)

# ================================================================
# Phase 6: _calc_dir_size
# ================================================================

print("\n" + "=" * 60)
print("Phase 6: _calc_dir_size")
print("=" * 60)

tmpdir = Path(tempfile.mkdtemp())
(tmpdir / "a.txt").write_bytes(b"x" * 1000)
(tmpdir / "sub").mkdir()
(tmpdir / "sub" / "b.txt").write_bytes(b"y" * 2000)
(tmpdir / ".hidden").write_bytes(b"z" * 500)

def test_dir_size():
    total = _calc_dir_size(tmpdir)
    assert total == 3500, f"expected 3500, got {total}"
run_test("dir size (1000+2000+500=3500)", test_dir_size)

def test_empty_dir():
    empty = tmpdir / "empty"
    empty.mkdir()
    assert _calc_dir_size(empty) == 0
run_test("empty dir = 0", test_empty_dir)

def test_nonexistent():
    assert _calc_dir_size(tmpdir / "nonexistent") == 0
run_test("nonexistent dir = 0", test_nonexistent)

shutil.rmtree(tmpdir)

# ================================================================
# Phase 7: Upload/Download E2E flow (mocked)
# ================================================================

print("\n" + "=" * 60)
print("Phase 7: Upload + Download E2E (with TestClient)")
print("=" * 60)

from fastapi import FastAPI
import httpx

# Build test app with file_router
test_app = FastAPI()

test_user = UserInfo(user_id=99, username="tester", display_name="Tester")

def mock_current_user():
    return test_user

# Override the get_current_user reference used by file_router
get_current_user_ref = mock_auth_module.get_current_user
test_app.include_router(fr.router)
test_app.dependency_overrides[get_current_user_ref] = mock_current_user

# Override DRIVE_BASE to temp dir
e2e_tmpdir = Path(tempfile.mkdtemp())
fr.DRIVE_BASE = e2e_tmpdir

# Mock DB for quota
mock_db.execute_query.return_value = None  # quota_bytes = None -> use default

transport = httpx.ASGITransport(app=test_app)
client = httpx.Client(transport=transport, base_url="http://test")

# Test: GET /api/files/space
def test_space():
    resp = client.get("/api/files/space")
    assert resp.status_code == 200
    data = resp.json()
    assert "used_bytes" in data
    assert "quota_bytes" in data
    assert "usage_percent" in data
    assert data["used_bytes"] == 0
run_test("GET /api/files/space", test_space)

# Test: GET /api/files/list (auto-create root)
def test_list_root():
    resp = client.get("/api/files/list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    # user dir should now exist
    assert (e2e_tmpdir / "portal_u99").exists()
run_test("GET /api/files/list (auto-create)", test_list_root)

# Test: POST /api/files/mkdir
def test_mkdir():
    resp = client.post("/api/files/mkdir", json={"path": "Documents"})
    assert resp.status_code == 200
    assert (e2e_tmpdir / "portal_u99" / "Documents").is_dir()
run_test("POST /api/files/mkdir", test_mkdir)

# Test: mkdir with Windows reserved name
def test_mkdir_con():
    resp = client.post("/api/files/mkdir", json={"path": "CON"})
    assert resp.status_code == 400
run_test("POST /api/files/mkdir CON (reject)", test_mkdir_con)

# Test: Upload init + chunk + completion
def test_upload_flow():
    file_content = b"Hello World! " * 100  # 1300 bytes
    file_size = len(file_content)

    # Init
    resp = client.post("/api/files/upload/init", data={
        "path": "Documents/test.txt",
        "size": str(file_size),
    })
    assert resp.status_code == 200, f"init failed: {resp.text}"
    init_data = resp.json()
    upload_id = init_data["upload_id"]
    assert init_data["offset"] == 0

    # Chunk (single chunk for small file)
    import io
    resp = client.post("/api/files/upload/chunk", data={
        "upload_id": upload_id,
        "offset": "0",
    }, files={"chunk": ("test.txt", io.BytesIO(file_content), "application/octet-stream")})
    assert resp.status_code == 200, f"chunk failed: {resp.text}"
    chunk_data = resp.json()
    assert chunk_data["complete"] is True
    assert chunk_data["offset"] == file_size

    # Verify file exists
    final_path = e2e_tmpdir / "portal_u99" / "Documents" / "test.txt"
    assert final_path.exists(), "file not found after upload"
    assert final_path.read_bytes() == file_content, "file content mismatch"
run_test("Upload flow (init + chunk + complete)", test_upload_flow)

# Test: List files after upload
def test_list_after_upload():
    resp = client.get("/api/files/list?path=Documents")
    assert resp.status_code == 200
    items = resp.json()["items"]
    names = [i["name"] for i in items]
    assert "test.txt" in names
run_test("GET /api/files/list after upload", test_list_after_upload)

# Test: Download token + download
def test_download_flow():
    # Get download token
    resp = client.post("/api/files/download-token", json={"path": "Documents/test.txt"})
    assert resp.status_code == 200
    token = resp.json()["token"]

    # Download (will return X-Accel-Redirect header)
    resp = client.get(f"/api/files/download?path=Documents/test.txt&_token={token}")
    assert resp.status_code == 200
    assert "X-Accel-Redirect" in resp.headers
    accel = resp.headers["X-Accel-Redirect"]
    assert accel.startswith("/internal-drive/portal_u99/")
    assert "Content-Disposition" in resp.headers
run_test("Download flow (token + X-Accel-Redirect)", test_download_flow)

# Test: Delete file
def test_delete_file():
    resp = client.delete("/api/files/file?path=Documents/test.txt")
    assert resp.status_code == 200
    assert not (e2e_tmpdir / "portal_u99" / "Documents" / "test.txt").exists()
run_test("DELETE /api/files/file", test_delete_file)

# Test: Delete root (should fail)
def test_delete_root():
    resp = client.delete("/api/files/file?path=")
    assert resp.status_code == 400
run_test("DELETE root (reject)", test_delete_root)

# Test: Path traversal via API
def test_api_traversal():
    resp = client.get("/api/files/list?path=../../etc")
    assert resp.status_code == 400
run_test("API path traversal (reject)", test_api_traversal)

# Test: Upload with oversized file (exceed declared size)
def test_upload_oversize():
    # Init with size=100
    resp = client.post("/api/files/upload/init", data={
        "path": "oversize.txt",
        "size": "100",
    })
    assert resp.status_code == 200
    upload_id = resp.json()["upload_id"]

    # Send chunk larger than declared size
    import io
    big_data = b"x" * 200
    resp = client.post("/api/files/upload/chunk", data={
        "upload_id": upload_id,
        "offset": "0",
    }, files={"chunk": ("oversize.txt", io.BytesIO(big_data), "application/octet-stream")})
    assert resp.status_code == 400, f"oversize accepted: {resp.status_code} {resp.text}"
run_test("Upload oversize chunk (reject)", test_upload_oversize)

# Test: Cancel upload
def test_cancel_upload():
    resp = client.post("/api/files/upload/init", data={
        "path": "cancel_me.txt",
        "size": "10000",
    })
    assert resp.status_code == 200
    upload_id = resp.json()["upload_id"]

    resp = client.delete(f"/api/files/upload/{upload_id}")
    assert resp.status_code == 200

    # Verify cleanup
    uploads_dir = e2e_tmpdir / "portal_u99" / ".uploads"
    meta = uploads_dir / f"{upload_id}.meta"
    tmp = uploads_dir / f"{upload_id}.tmp"
    assert not meta.exists()
    assert not tmp.exists()
run_test("Cancel upload (cleanup)", test_cancel_upload)

# Test: Upload ID traversal attack via API
def test_upload_id_attack():
    resp = client.delete("/api/files/upload/../../etc/passwd")
    assert resp.status_code in (400, 422), f"traversal accepted: {resp.status_code}"
run_test("Upload ID traversal attack (reject)", test_upload_id_attack)

# Cleanup
fr.DRIVE_BASE = Path(mock_config["guacamole"]["drive"]["base_path"])
shutil.rmtree(e2e_tmpdir)

# ================================================================
# Summary
# ================================================================

print("\n" + "=" * 60)
print("FINAL SUMMARY")
print("=" * 60)
if all_errors:
    print(f"TOTAL ERRORS: {len(all_errors)}")
    for e in all_errors:
        print(f"  [ERROR] {e}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
    sys.exit(0)
