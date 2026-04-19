import sys
from pathlib import Path


def test_script_profiles_expose_config_driven_presets():
    sys.modules.pop("backend.script_profiles", None)
    from backend.script_profiles import list_script_profiles

    items = list_script_profiles(
        config={
            "script_profiles": {
                "solver_a": {
                    "adapter_key": "solver_a",
                    "display_name": "Solver A",
                    "description": "Primary CAE runtime",
                    "executor_key": "python_api",
                    "python_executable": "C:/Python/python.exe",
                    "python_env": {"LICENSE_SERVER": "10.0.0.1"},
                }
            }
        }
    )

    assert items == [
        {
            "profile_key": "solver_a",
            "adapter_key": "solver_a",
            "display_name": "Solver A",
            "description": "Primary CAE runtime",
            "executor_key": "python_api",
            "python_executable": "C:/Python/python.exe",
            "python_env": {"LICENSE_SERVER": "10.0.0.1"},
        }
    ]


def test_script_runtime_settings_merge_profile_defaults():
    sys.modules.pop("backend.script_profiles", None)
    from backend.script_profiles import resolve_script_runtime_settings

    result = resolve_script_runtime_settings(
        script_profile_key="solver_a",
        script_executor_key=None,
        python_executable=None,
        python_env={"EXTRA_FLAG": "1"},
        config={
            "script_profiles": {
                "solver_a": {
                    "adapter_key": "solver_a",
                    "display_name": "Solver A",
                    "description": "Primary CAE runtime",
                    "executor_key": "python_api",
                    "python_executable": "C:/Python/python.exe",
                    "python_env": {"LICENSE_SERVER": "10.0.0.1"},
                }
            }
        },
    )

    assert result["executor_key"] == "python_api"
    assert result["python_executable"] == "C:/Python/python.exe"
    assert result["python_env"] == {
        "LICENSE_SERVER": "10.0.0.1",
        "EXTRA_FLAG": "1",
    }
    assert result["runtime_config"] == {
        "script_profile_key": "solver_a",
        "software_adapter_key": "solver_a",
        "software_display_name": "Solver A",
        "python_executable": "C:/Python/python.exe",
        "python_env": {
            "LICENSE_SERVER": "10.0.0.1",
            "EXTRA_FLAG": "1",
        },
    }
