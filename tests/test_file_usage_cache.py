from pathlib import Path

import backend.file_router as file_router


def test_get_usage_sync_force_refresh_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(file_router, "DRIVE_BASE", tmp_path)
    file_router._usage_cache.clear()

    user_dir = tmp_path / "portal_u7"
    user_dir.mkdir()
    (user_dir / "first.bin").write_bytes(b"abc")

    assert file_router._get_usage_sync(7) == 3

    (user_dir / "second.bin").write_bytes(b"defg")

    assert file_router._get_usage_sync(7) == 3
    assert file_router._get_usage_sync(7, force_refresh=True) == 7


def test_should_hide_entry_hides_legacy_download_dir_only_at_root():
    assert file_router._should_hide_entry("", "Download", True) is True
    assert file_router._should_hide_entry("/", "download", True) is True
    assert file_router._should_hide_entry("Output", "Download", True) is False
    assert file_router._should_hide_entry("", "Download", False) is False
    assert file_router._should_hide_entry("", "Output", True) is False
