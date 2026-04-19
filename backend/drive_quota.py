"""Helper utilities for drive usage and quotas."""

from __future__ import annotations

import time
from pathlib import Path

from backend.config_loader import get_config

_CONFIG = get_config()
_drive_cfg = _CONFIG["guacamole"]["drive"]
_ft_cfg = _CONFIG.get("file_transfer", {})

DRIVE_BASE = Path(_drive_cfg["base_path"])
DEFAULT_QUOTA_BYTES = int(_ft_cfg.get("default_quota_gb", 10)) * 1073741824
USAGE_CACHE_SECONDS = _ft_cfg.get("usage_cache_seconds", 60)

_usage_cache: dict[int, tuple[int, float]] = {}


def _user_dir(user_id: int) -> Path:
    return DRIVE_BASE / f"portal_u{user_id}"


def _calc_dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _get_usage_sync(user_id: int, force_refresh: bool = False) -> int:
    now = time.time()
    cached = _usage_cache.get(user_id)
    if not force_refresh and cached and now - cached[1] < USAGE_CACHE_SECONDS:
        return cached[0]
    udir = _user_dir(user_id)
    size = _calc_dir_size(udir) if udir.exists() else 0
    _usage_cache[user_id] = (size, now)
    return size


def _invalidate_usage_cache(user_id: int):
    _usage_cache.pop(user_id, None)


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1048576:
        return f"{size / 1024:.1f} KB"
    if size < 1073741824:
        return f"{size / 1048576:.1f} MB"
    return f"{size / 1073741824:.2f} GB"


def _get_quota(user_id: int) -> int:
    from backend.database import db

    row = db.execute_query(
        "SELECT quota_bytes FROM portal_user WHERE id = %(uid)s",
        {"uid": user_id},
        fetch_one=True,
    )
    if row and row.get("quota_bytes") is not None:
        return int(row["quota_bytes"])
    return DEFAULT_QUOTA_BYTES
