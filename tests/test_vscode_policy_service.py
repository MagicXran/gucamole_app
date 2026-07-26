import pytest

from backend.vscode_policy_service import (
    CONTROL_CODES,
    DEFAULT_PERMISSIONS,
    VscodePolicyError,
    build_effective_policy,
    build_vscode_arguments,
    catalog_payload,
    normalize_profile_document,
    validate_restricted_arguments,
)


def _valid_profile(**overrides):
    payload = {
        "profile_key": "default-controlled",
        "display_name": "默认受控开发模式",
        "description": "",
        "policy_version": 1,
        "is_active": True,
        "permissions": dict(DEFAULT_PERMISSIONS),
        "allowed_shells": [r"C:\Windows\System32\cmd.exe"],
        "allowed_tools": [r"C:\Program Files\Git\cmd\git.exe"],
        "allowed_debuggers": [r"C:\Tools\debugger.exe"],
        "allowed_extensions": ["ms-python.python"],
        "allowed_network_targets": ["https://packages.example.local"],
        "user_data_root": r"C:\PortalProfiles",
        "extensions_root": r"C:\PortalExtensions",
        "default_workspace_template": r"\\tsclient\GuacDrive",
    }
    payload.update(overrides)
    return normalize_profile_document(payload)


def test_catalog_is_single_source_and_defaults_all_controls_to_true():
    payload = catalog_payload()

    assert [item["code"] for item in payload["controls"]] == list(CONTROL_CODES)
    assert payload["default_permissions"] == DEFAULT_PERMISSIONS
    assert all(payload["default_permissions"].values())
    assert len(payload["locked_baseline"]) >= 8


def test_profile_with_enabled_permissions_and_empty_allowlists_is_invalid():
    profile = normalize_profile_document(
        {
            "profile_key": "default-controlled",
            "display_name": "默认受控开发模式",
            "is_active": False,
            "permissions": dict(DEFAULT_PERMISSIONS),
            "allowed_shells": [],
            "allowed_tools": [],
            "allowed_debuggers": [],
            "allowed_extensions": [],
            "allowed_network_targets": [],
            "user_data_root": r"C:\PortalProfiles",
            "extensions_root": r"C:\PortalExtensions",
            "default_workspace_template": r"\\tsclient\GuacDrive",
        }
    )

    effective = build_effective_policy(profile)

    assert effective["valid"] is False
    assert any("allowed_shells" in error for error in effective["validation_errors"])
    assert any("allowed_network_targets" in error for error in effective["validation_errors"])


def test_unknown_control_and_wildcard_allowlist_are_rejected():
    permissions = {**DEFAULT_PERMISSIONS, "unknown_control": True}

    with pytest.raises(VscodePolicyError, match="未知控制项"):
        _valid_profile(permissions=permissions)

    with pytest.raises(VscodePolicyError, match=r"不允许使用 \*"):
        _valid_profile(allowed_tools=["*"])


def test_profile_roots_are_locked_and_allowlist_formats_are_validated():
    with pytest.raises(VscodePolicyError, match="必须固定为"):
        _valid_profile(user_data_root=r"C:\Windows")

    with pytest.raises(VscodePolicyError, match="Windows 本地绝对路径"):
        _valid_profile(allowed_tools=[r"\\server\share\tool.exe"])

    with pytest.raises(VscodePolicyError, match="publisher.extension"):
        _valid_profile(allowed_extensions=["not-an-extension-id"])

    with pytest.raises(VscodePolicyError, match="http/https"):
        _valid_profile(allowed_network_targets=["file:///C:/Windows"])

    profile = _valid_profile(allowed_network_targets=["git.example.local:443", "10.0.0.0/24"])
    assert profile["allowed_network_targets"] == ["git.example.local:443", "10.0.0.0/24"]


def test_vscode_arguments_are_different_per_portal_user():
    profile = _valid_profile()

    user_a = build_vscode_arguments(profile, 11)
    user_b = build_vscode_arguments(profile, 12)

    assert user_a != user_b
    assert r"C:\PortalProfiles\11" in user_a
    assert r"C:\PortalExtensions\11" in user_a
    assert "{user_id}" not in user_a
    assert r"\\tsclient\GuacDrive" in user_a


def test_restricted_argument_validation_allows_only_fixed_user_id_token():
    assert validate_restricted_arguments("--profile={user_id}", allow_user_id=True) == "--profile={user_id}"

    with pytest.raises(VscodePolicyError, match="未知占位符"):
        validate_restricted_arguments("--profile={username}", allow_user_id=True)

    with pytest.raises(VscodePolicyError, match="危险 shell 字符"):
        validate_restricted_arguments("--file=a & calc.exe")
