import pytest

from backend.app_launch_presets import prepare_launch_payload


def test_custom_mode_preserves_fields_and_clears_fixed_file_settings():
    existing = {
        "launch_preset": "comsol_open_file",
        "remote_app": "comsol",
        "server_file_path": "C:\\Data\\model.mph",
        "launch_arg_template": "-open {file}",
        "remote_app_dir": " C:\\Data ",
        "remote_app_args": "  -open X  ",
        "extra": "keep",
    }
    result = prepare_launch_payload({"launch_preset": "custom"}, existing)
    assert result["launch_preset"] == "custom"
    assert result["server_file_path"] is None
    assert result["launch_arg_template"] is None
    assert result["remote_app_dir"] == "C:\\Data"
    assert result["remote_app_args"] == "-open X"
    assert result["remote_app"] == "comsol"
    assert result["extra"] == "keep"


def test_comsol_open_file_builds_args_and_derives_remote_app_dir():
    raw = {
        "launch_preset": "comsol_open_file",
        "remote_app": "comsol",
        "server_file_path": "C:\\Data\\model.mph",
    }
    result = prepare_launch_payload(raw)
    assert result["remote_app_args"] == '-open "C:\\Data\\model.mph"'
    assert result["remote_app_dir"] == "C:\\Data"
    assert result["launch_arg_template"] is None


def test_generic_file_template_compiles_file_placeholder():
    raw = {
        "launch_preset": "generic_file_template",
        "remote_app": "tool",
        "server_file_path": "C:\\Data\\input.txt",
        "launch_arg_template": "--file {file} --flag",
    }
    result = prepare_launch_payload(raw)
    assert result["remote_app_args"] == "--file C:\\Data\\input.txt --flag"
    assert result["launch_arg_template"] == "--file {file} --flag"


def test_generic_file_template_requires_file_placeholder():
    raw = {
        "launch_preset": "generic_file_template",
        "remote_app": "tool",
        "server_file_path": "C:\\Data\\input.txt",
        "launch_arg_template": "--file input.txt --flag",
    }
    with pytest.raises(ValueError, match=r"\{file\}"):
        prepare_launch_payload(raw)


def test_fixed_file_modes_reject_relative_paths():
    for preset in ("comsol_open_file", "generic_file_template"):
        raw = {
            "launch_preset": preset,
            "remote_app": "tool",
            "server_file_path": "data\\input.txt",
            "launch_arg_template": "--file {file}",
        }
        with pytest.raises(ValueError):
            prepare_launch_payload(raw)


def test_control_characters_rejected_in_server_path():
    raw = {
        "launch_preset": "comsol_open_file",
        "remote_app": "comsol",
        "server_file_path": "C:\\Data\\bad\x01name.mph",
    }
    with pytest.raises(ValueError):
        prepare_launch_payload(raw)


def test_missing_launch_preset_falls_back_to_custom():
    existing = {
        "remote_app_args": "  -open X  ",
    }
    result = prepare_launch_payload({"description": "legacy"}, existing)
    assert result["launch_preset"] == "custom"
    assert result["server_file_path"] is None
    assert result["launch_arg_template"] is None
    assert result["remote_app"] is None
    assert result["remote_app_dir"] is None
    assert result["remote_app_args"] == "-open X"
    assert result["description"] == "legacy"


def test_unc_path_is_accepted_and_compiled():
    raw = {
        "launch_preset": "generic_file_template",
        "remote_app": "tool",
        "server_file_path": "\\\\server\\share\\file.txt",
        "launch_arg_template": "--file {file}",
    }
    result = prepare_launch_payload(raw)
    assert result["remote_app_args"] == "--file \\\\server\\share\\file.txt"
    assert result["remote_app_dir"] == "\\\\server\\share\\"


def test_merge_keeps_existing_preset_metadata_on_unrelated_updates():
    existing = {
        "launch_preset": "generic_file_template",
        "remote_app": "tool",
        "server_file_path": "C:\\Data\\input.txt",
        "launch_arg_template": "run {file}",
        "remote_app_dir": "C:\\Data",
        "remote_app_args": "run C:\\Data\\input.txt",
    }
    result = prepare_launch_payload({"description": "new"}, existing)
    assert result["launch_preset"] == "generic_file_template"
    assert result["server_file_path"] == "C:\\Data\\input.txt"
    assert result["launch_arg_template"] == "run {file}"
    assert result["remote_app_args"] == "run C:\\Data\\input.txt"
    assert result["description"] == "new"
