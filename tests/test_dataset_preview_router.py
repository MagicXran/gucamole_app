import importlib
import sys
import types

import pytest
from fastapi import HTTPException

from backend.models import UserInfo


@pytest.fixture
def preview_router_module(monkeypatch: pytest.MonkeyPatch):
    fake_database = types.ModuleType("backend.database")
    fake_database.CONFIG = {
        "guacamole": {
            "drive": {
                "base_path": "/drive",
                "results_root": "Output",
            }
        }
    }
    monkeypatch.setitem(sys.modules, "backend.database", fake_database)

    fake_auth = types.ModuleType("backend.auth")
    fake_auth.get_current_user = lambda: None
    monkeypatch.setitem(sys.modules, "backend.auth", fake_auth)

    sys.modules.pop("backend.dataset_router", None)
    module = importlib.import_module("backend.dataset_router")
    yield module
    sys.modules.pop("backend.dataset_router", None)


def test_preview_route_maps_config_errors_to_500(preview_router_module, monkeypatch: pytest.MonkeyPatch):
    def fake_ensure_preview_path(user_id: int, path: str) -> str:
        raise preview_router_module.DatasetPreviewConfigError("结果目录配置无效")

    monkeypatch.setattr(preview_router_module, "ensure_preview_path", fake_ensure_preview_path)

    with pytest.raises(HTTPException) as exc_info:
        preview_router_module.get_dataset_preview(
            path="nested/mesh.vtu",
            user=UserInfo(user_id=7, username="tester", display_name="Tester", is_admin=False),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "结果目录配置无效"
