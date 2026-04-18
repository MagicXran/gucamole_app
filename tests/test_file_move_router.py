import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI

from backend.models import UserInfo
from backend import file_router


def _build_app(tmp_path: Path, monkeypatch):
    app = FastAPI()
    app.include_router(file_router.router)
    monkeypatch.setattr(file_router, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(file_router, "_usage_cache", {})

    audit_calls = []
    monkeypatch.setattr(
        file_router,
        "log_action",
        lambda **kwargs: audit_calls.append(kwargs),
    )
    app.dependency_overrides[file_router.get_current_user] = lambda: UserInfo(
        user_id=7,
        username="tester",
        display_name="测试用户",
        is_admin=False,
    )
    return app, audit_calls


def _request(app: FastAPI, payload: dict):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/api/files/move", json=payload)

    return asyncio.run(_run())


def _user_root(tmp_path: Path) -> Path:
    root = tmp_path / "portal_u7"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_move_file_within_user_root_refreshes_cache_and_writes_audit(monkeypatch, tmp_path):
    app, audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "source.txt").write_text("hello", encoding="utf-8")
    file_router._usage_cache[7] = (123, 999.0)

    response = _request(
        app,
        {"source_path": "docs/source.txt", "target_path": "moved/target.txt"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "已移动"
    assert not (root / "docs" / "source.txt").exists()
    assert (root / "moved" / "target.txt").read_text(encoding="utf-8") == "hello"
    assert 7 not in file_router._usage_cache
    assert audit_calls == [
        {
            "user_id": 7,
            "username": "tester",
            "action": "file_move",
            "target_name": "docs/source.txt",
            "detail": {"target_path": "moved/target.txt"},
            "ip_address": "127.0.0.1",
        }
    ]


def test_move_rejects_path_traversal(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "../escape.txt"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "非法路径"
    assert (root / "source.txt").exists()
    assert not (tmp_path / "escape.txt").exists()


def test_move_rejects_root_source(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    _user_root(tmp_path)

    response = _request(
        app,
        {"source_path": "/", "target_path": "moved-root"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "不能移动根目录"


def test_move_rejects_missing_source(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    _user_root(tmp_path)

    response = _request(
        app,
        {"source_path": "missing.txt", "target_path": "target.txt"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "源文件不存在"


def test_move_rejects_same_source_and_target(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "same.txt").write_text("hello", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "same.txt", "target_path": "same.txt"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "源路径和目标路径相同"


def test_move_rejects_directory_into_its_child(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "parent" / "child").mkdir(parents=True)

    response = _request(
        app,
        {"source_path": "parent", "target_path": "parent/child/moved-parent"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "不能移动目录到自身内部"


def test_move_rejects_root_target(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "/"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "目标路径不能是根目录"


def test_move_rejects_when_target_parent_is_file(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")
    (root / "parent-file").write_text("not a dir", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "parent-file/child.txt"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目标父路径不是目录"
    assert (root / "source.txt").read_text(encoding="utf-8") == "hello"


def test_move_rejects_when_target_ancestor_is_file(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")
    (root / "parent-file").write_text("not a dir", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "parent-file/nested/child.txt"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目标父路径不是目录"
    assert (root / "source.txt").read_text(encoding="utf-8") == "hello"


def test_move_rejects_windows_reserved_target_name(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "folder/CON.txt"},
    )

    assert response.status_code == 400
    assert "Windows 保留名" in response.json()["detail"]
    assert (root / "source.txt").exists()


def test_move_rejects_existing_target(monkeypatch, tmp_path):
    app, _audit_calls = _build_app(tmp_path, monkeypatch)
    root = _user_root(tmp_path)
    (root / "source.txt").write_text("hello", encoding="utf-8")
    (root / "target.txt").write_text("exists", encoding="utf-8")

    response = _request(
        app,
        {"source_path": "source.txt", "target_path": "target.txt"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目标已存在"
    assert (root / "source.txt").read_text(encoding="utf-8") == "hello"
    assert (root / "target.txt").read_text(encoding="utf-8") == "exists"
