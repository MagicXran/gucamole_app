import re
from pathlib import PureWindowsPath


_ABSOLUTE_WINDOWS_PATH = re.compile(r"^(?:[A-Za-z]:\\|\\\\)")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f]")


def _clean_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def _merge_raw_existing(raw, existing):
    merged = dict(existing or {})
    for key, value in (raw or {}).items():
        if value is not None:
            merged[key] = value
    return merged


def _normalize_server_path(value):
    cleaned = _clean_string(value)
    if cleaned is None:
        raise ValueError("server_file_path is required")
    if _CONTROL_CHARS.search(cleaned):
        raise ValueError("server_file_path contains control characters")
    normalized = str(PureWindowsPath(cleaned))
    if not _ABSOLUTE_WINDOWS_PATH.match(normalized):
        raise ValueError("server_file_path must be an absolute Windows path")
    return normalized


def _apply_custom_output(merged):
    merged["launch_preset"] = "custom"
    merged["server_file_path"] = None
    merged["launch_arg_template"] = None
    merged["remote_app"] = _clean_string(merged.get("remote_app"))
    merged["remote_app_dir"] = _clean_string(merged.get("remote_app_dir"))
    merged["remote_app_args"] = _clean_string(merged.get("remote_app_args"))
    return merged


def prepare_launch_payload(raw: dict, existing: dict | None = None) -> dict:
    merged = _merge_raw_existing(raw, existing)
    launch_preset = _clean_string(merged.get("launch_preset"))
    if launch_preset:
        merged["launch_preset"] = launch_preset

    if launch_preset == "custom":
        return _apply_custom_output(merged)

    if launch_preset is None:
        return _apply_custom_output(merged)
    if launch_preset not in ("comsol_open_file", "generic_file_template"):
        raise ValueError("launch_preset is not supported")

    remote_app = _clean_string(merged.get("remote_app"))
    if not remote_app:
        raise ValueError("remote_app is required")
    merged["remote_app"] = remote_app

    server_file_path = _normalize_server_path(merged.get("server_file_path"))
    merged["server_file_path"] = server_file_path

    remote_app_dir = _clean_string(merged.get("remote_app_dir"))
    if remote_app_dir is None:
        remote_app_dir = str(PureWindowsPath(server_file_path).parent)
    merged["remote_app_dir"] = remote_app_dir

    if launch_preset == "comsol_open_file":
        merged["launch_arg_template"] = None
        merged["remote_app_args"] = f'-open "{server_file_path}"'
        return merged

    launch_arg_template = _clean_string(merged.get("launch_arg_template"))
    if not launch_arg_template or "{file}" not in launch_arg_template:
        raise ValueError("launch_arg_template must include {file}")
    merged["launch_arg_template"] = launch_arg_template
    merged["remote_app_args"] = launch_arg_template.replace("{file}", server_file_path)
    return merged
