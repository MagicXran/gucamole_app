import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

import pytest

import backend.dataset_preview_service as preview_service


def test_ensure_preview_for_vtu_builds_and_reuses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user_id = 7
    results_root = tmp_path / f"portal_u{user_id}" / "Output"
    source_file = results_root / "nested" / "mesh.vtu"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("<VTKFile />", encoding="utf-8")

    monkeypatch.setattr(preview_service, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(preview_service, "RESULTS_ROOT_NAME", "Output")

    convert_calls = {"count": 0}

    def fake_convert(source: Path, target: Path):
        convert_calls["count"] += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("converted-vtp", encoding="utf-8")

    monkeypatch.setattr(preview_service, "_convert_vtu_to_vtp", fake_convert)

    preview_path = preview_service.ensure_preview_path(user_id, "nested/mesh.vtu")
    assert preview_path == ".preview_cache/nested/mesh.vtp"
    assert convert_calls["count"] == 1

    preview_path_again = preview_service.ensure_preview_path(user_id, "nested/mesh.vtu")
    assert preview_path_again == preview_path
    assert convert_calls["count"] == 1

    new_mtime = source_file.stat().st_mtime + 5
    os.utime(source_file, (new_mtime, new_mtime))

    preview_path_after_touch = preview_service.ensure_preview_path(user_id, "nested/mesh.vtu")
    assert preview_path_after_touch == preview_path
    assert convert_calls["count"] == 2


def test_ensure_preview_path_rejects_illegal_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(preview_service, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(preview_service, "RESULTS_ROOT_NAME", "Output")

    with pytest.raises(preview_service.DatasetPreviewPathError):
        preview_service.ensure_preview_path(7, "../escape.vtu")


def test_ensure_preview_for_vtu_is_safe_under_concurrent_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user_id = 7
    results_root = tmp_path / f"portal_u{user_id}" / "Output"
    source_file = results_root / "nested" / "mesh.vtu"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("<VTKFile />", encoding="utf-8")

    monkeypatch.setattr(preview_service, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(preview_service, "RESULTS_ROOT_NAME", "Output")

    convert_calls = {"count": 0}
    def fake_convert(source: Path, target: Path):
        convert_calls["count"] += 1
        time.sleep(0.1)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("converted-vtp", encoding="utf-8")

    monkeypatch.setattr(preview_service, "_convert_vtu_to_vtp", fake_convert)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(preview_service.ensure_preview_path, user_id, "nested/mesh.vtu")
            for _ in range(2)
        ]

    results = [future.result() for future in futures]
    assert results == [".preview_cache/nested/mesh.vtp", ".preview_cache/nested/mesh.vtp"]
    assert (results_root / ".preview_cache" / "nested" / "mesh.vtp").exists()
    assert convert_calls["count"] == 1


def test_ensure_preview_path_raises_config_error_for_invalid_results_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(preview_service, "DRIVE_BASE", tmp_path)
    monkeypatch.setattr(preview_service, "RESULTS_ROOT_NAME", "../escape")

    with pytest.raises(preview_service.DatasetPreviewConfigError):
        preview_service.ensure_preview_path(7, "nested/mesh.vtu")
