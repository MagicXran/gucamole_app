from backend.config_loader import load_config
from backend.router import _build_rdp_client_name, _build_rdp_drive_name


def test_rdp_label_environment_overrides(monkeypatch):
    monkeypatch.setenv("GUACAMOLE_CLIENT_NAME", "EnvironmentWorkspace")
    monkeypatch.setenv("GUACAMOLE_DRIVE_NAME", "EnvironmentFiles")

    config = load_config()

    assert config["guacamole"]["client_name"] == "EnvironmentWorkspace"
    assert config["guacamole"]["drive"]["name"] == "EnvironmentFiles"


def test_rdp_label_environment_overrides_still_cross_router_sanitization(monkeypatch):
    monkeypatch.setenv("GUACAMOLE_CLIENT_NAME", "Workspace 技术名")
    monkeypatch.setenv("GUACAMOLE_DRIVE_NAME", "用户文件")

    config = load_config()

    assert _build_rdp_client_name(config["guacamole"]["client_name"]) == "Workspace"
    assert _build_rdp_drive_name(config["guacamole"]["drive"]["name"]) == "UserFiles"
