"""
Configuration loading without database side effects.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock


_CONFIG_UNSET = object()
_config_cache = _CONFIG_UNSET
_config_lock = Lock()


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    config["database"]["password"] = os.environ.get(
        "PORTAL_DB_PASSWORD", config["database"]["password"]
    )
    config.setdefault("guacamole", {})["json_secret_key"] = os.environ.get(
        "GUACAMOLE_JSON_SECRET_KEY", config["guacamole"]["json_secret_key"]
    )
    config.setdefault("auth", {})["jwt_secret"] = os.environ.get(
        "PORTAL_JWT_SECRET", config["auth"]["jwt_secret"]
    )

    config["database"]["host"] = os.environ.get(
        "PORTAL_DB_HOST", config["database"]["host"]
    )
    config["database"]["port"] = int(os.environ.get(
        "PORTAL_DB_PORT", config["database"]["port"]
    ))
    config["guacamole"]["internal_url"] = os.environ.get(
        "GUACAMOLE_INTERNAL_URL", config["guacamole"]["internal_url"]
    )
    config["guacamole"]["external_url"] = os.environ.get(
        "GUACAMOLE_EXTERNAL_URL", config["guacamole"]["external_url"]
    )
    drive_cfg = config.setdefault("guacamole", {}).setdefault("drive", {})
    drive_cfg["base_path"] = os.environ.get(
        "GUACAMOLE_DRIVE_BASE_PATH", drive_cfg.get("base_path", "/drive")
    )
    drive_cfg["results_root"] = os.environ.get(
        "GUACAMOLE_DRIVE_RESULTS_ROOT", drive_cfg.get("results_root", "Output")
    )
    storage_cfg = config.setdefault("object_storage", {})
    storage_cfg["enabled"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_ENABLED",
        str(storage_cfg.get("enabled", False)),
    ).lower() in {"1", "true", "yes", "on"}
    storage_cfg["endpoint"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_ENDPOINT", storage_cfg.get("endpoint", "")
    )
    storage_cfg["access_key"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_ACCESS_KEY", storage_cfg.get("access_key", "")
    )
    storage_cfg["secret_key"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_SECRET_KEY", storage_cfg.get("secret_key", "")
    )
    storage_cfg["bucket"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_BUCKET", storage_cfg.get("bucket", "")
    )
    storage_cfg["secure"] = os.environ.get(
        "PORTAL_OBJECT_STORAGE_SECURE",
        str(storage_cfg.get("secure", False)),
    ).lower() in {"1", "true", "yes", "on"}
    return config


def get_config() -> dict:
    global _config_cache
    if _config_cache is not _CONFIG_UNSET:
        return _config_cache
    with _config_lock:
        if _config_cache is _CONFIG_UNSET:
            _config_cache = load_config()
        return _config_cache
