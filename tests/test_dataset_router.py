import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI

import backend.dataset_router as dataset_router
from backend.models import UserInfo


def _build_app(tmp_path: Path, monkeypatch) -> FastAPI:
    user_id = 7
    root = tmp_path / f"portal_u{user_id}" / "Output"
    root.mkdir(parents=True)
    (root / "root.vtp").write_text("<VTKFile />", encoding="utf-8")
    (root / "skip.txt").write_text("ignore", encoding="utf-8")
    nested_dir = root / "nested"
    nested_dir.mkdir()
    (nested_dir / "mesh.obj").write_text("o cube", encoding="utf-8")

    monkeypatch.setattr(dataset_router, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(dataset_router, "RESULTS_ROOT_NAME", "Output")

    app = FastAPI()
    app.include_router(dataset_router.router)
    app.dependency_overrides[dataset_router.get_current_user] = lambda: UserInfo(
        user_id=user_id,
        username="tester",
        display_name="Tester",
        is_admin=False,
    )
    return app


def _request(app: FastAPI, method: str, path: str) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(_run())


def test_list_datasets_returns_directory_payload(tmp_path: Path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    response = _request(app, "GET", "/api/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == ""
    assert payload["items"] == [
        {
            "name": "nested",
            "path": "nested",
            "is_dir": True,
            "size_bytes": 0,
            "size_human": "",
            "extension": "",
        },
        {
            "name": "root.vtp",
            "path": "root.vtp",
            "is_dir": False,
            "size_bytes": 11,
            "size_human": "11.0 B",
            "extension": ".vtp",
        },
    ]


def test_legacy_download_route_supports_nested_relative_paths(tmp_path: Path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    response = _request(app, "GET", "/api/datasets/nested/mesh.obj")

    assert response.status_code == 200
    assert response.content == b"o cube"
