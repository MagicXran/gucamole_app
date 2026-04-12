"""
Config-driven script software profiles.
"""

from __future__ import annotations

import os
from typing import Any

from backend.config_loader import load_config


def _normalize_env(raw_env: Any) -> dict[str, str]:
    if not isinstance(raw_env, dict):
        return {}
    return {str(key): str(value) for key, value in raw_env.items()}


def _normalize_profile(profile_key: str, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    executor_key = str(raw.get("executor_key") or "").strip()
    if not executor_key:
        return None
    python_executable_env = str(raw.get("python_executable_env") or "").strip()
    python_executable = str(raw.get("python_executable") or "").strip() or None
    if python_executable_env:
        python_executable = os.environ.get(python_executable_env, python_executable) or None
    return {
        "profile_key": profile_key,
        "adapter_key": str(raw.get("adapter_key") or profile_key),
        "display_name": str(raw.get("display_name") or profile_key),
        "description": str(raw.get("description") or "").strip(),
        "executor_key": executor_key,
        "python_executable": python_executable,
        "python_env": _normalize_env(raw.get("python_env")),
    }


def list_script_profiles(*, config: dict | None = None) -> list[dict[str, Any]]:
    runtime_config = config or load_config()
    raw_profiles = runtime_config.get("script_profiles") or {}
    items: list[dict[str, Any]] = []
    for profile_key in sorted(raw_profiles.keys()):
        normalized = _normalize_profile(profile_key, raw_profiles.get(profile_key))
        if normalized is not None:
            items.append(normalized)
    return items


def get_script_profile(profile_key: str | None, *, config: dict | None = None) -> dict[str, Any] | None:
    if not profile_key:
        return None
    runtime_config = config or load_config()
    raw_profiles = runtime_config.get("script_profiles") or {}
    return _normalize_profile(profile_key, raw_profiles.get(profile_key))


def resolve_script_runtime_settings(
    *,
    script_profile_key: str | None,
    script_executor_key: str | None,
    python_executable: str | None,
    python_env: dict[str, str] | None,
    config: dict | None = None,
) -> dict[str, Any]:
    profile = get_script_profile(script_profile_key, config=config)
    if script_profile_key and profile is None:
        raise ValueError(f"unknown script profile: {script_profile_key}")

    if profile is not None and script_executor_key and script_executor_key != profile["executor_key"]:
        raise ValueError("script profile executor mismatch")

    effective_executor_key = script_executor_key or (profile["executor_key"] if profile else None)
    merged_env = dict(profile.get("python_env") or {}) if profile else {}
    if python_env:
        merged_env.update({str(key): str(value) for key, value in python_env.items()})

    runtime_config: dict[str, Any] = {}
    if script_profile_key:
        runtime_config["script_profile_key"] = script_profile_key
    if profile is not None:
        runtime_config["software_adapter_key"] = profile["adapter_key"]
        runtime_config["software_display_name"] = profile["display_name"]
    effective_python_executable = python_executable or (profile.get("python_executable") if profile else None)
    if effective_python_executable:
        runtime_config["python_executable"] = effective_python_executable
    if merged_env:
        runtime_config["python_env"] = merged_env

    return {
        "profile": profile,
        "executor_key": effective_executor_key,
        "python_executable": effective_python_executable,
        "python_env": merged_env or None,
        "runtime_config": runtime_config or None,
    }
