"""
Stable validation-node configuration helpers.
"""

from __future__ import annotations

from urllib.parse import urlparse

from backend.script_profiles import get_script_profile


def build_validation_runtime_state(*, portal_base_url: str, expected_hostname: str, worker_vm_host: str) -> dict:
    script_profile_key = "ansys_mapdl"
    profile = get_script_profile(script_profile_key) or {}
    return {
        "group_key": "validation-windows-node",
        "group_name": "Validation Windows Node",
        "pool_name": "验证池-桌面与脚本",
        "app_name": "验证节点-桌面与脚本",
        "portal_base_url": portal_base_url,
        "expected_hostname": expected_hostname,
        "worker_vm_host": worker_vm_host,
        "workspace_dir": "validation_workspace",
        "remote_root": r"C:\portal_worker_agent",
        "workspace_share": r"C:\portal_worker_share",
        "scratch_root": r"C:\portal_worker_agent\scratch",
        "script_profile_key": script_profile_key,
        "script_profile_name": profile.get("display_name") or script_profile_key,
        "script_executor_key": profile.get("executor_key") or "python_api",
    }


def build_validation_registration_payload(state: dict) -> dict:
    script_executor_key = state.get("script_executor_key") or "python_api"
    return {
        "portal_base_url": state["portal_base_url"],
        "enrollment_token": state["enrollment_token"],
        "hostname": state["expected_hostname"],
        "machine_fingerprint": "fp-" + state["expected_hostname"],
        "agent_version": "1.0.0",
        "os_type": "windows",
        "os_version": "Windows Server 2019",
        "ip_addresses": [state["worker_vm_host"]],
        "scratch_root": state.get("scratch_root", r"C:\portal_worker_agent\scratch"),
        "workspace_share": state.get("workspace_share", r"C:\portal_worker_share"),
        "max_concurrent_tasks": 1,
        "supported_executor_keys": [script_executor_key],
        "capabilities": {
            "can_run_script_binding": True,
            "can_run_gui_binding": False,
        },
    }


def validate_validation_runtime_state(state: dict) -> None:
    portal_base_url = str(state.get("portal_base_url") or "").strip()
    worker_vm_host = str(state.get("worker_vm_host") or "").strip()
    if not portal_base_url:
        raise ValueError("portal_base_url is required")
    parsed = urlparse(portal_base_url)
    hostname = (parsed.hostname or "").strip().lower()
    if worker_vm_host and worker_vm_host not in {"127.0.0.1", "localhost"} and hostname in {"127.0.0.1", "localhost"}:
        raise ValueError("portal_base_url must be reachable from the remote worker; loopback is invalid for remote nodes")


def render_validation_workspace_script(script_profile_key: str | None = None) -> str:
    if script_profile_key == "ansys_mapdl":
        return (
            "from pathlib import Path\n"
            "import json\n"
            "from ansys.mapdl.core import launch_mapdl\n\n"
            "run_dir = Path.cwd()\n"
            "mapdl = launch_mapdl(run_location=str(run_dir), override=True)\n"
            "try:\n"
            "    result = {\n"
            "        'software': 'ANSYS MAPDL',\n"
            "        'status': 'ok',\n"
            "        'version': str(mapdl.version),\n"
            "    }\n"
            "    Path('result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')\n"
            "    print('ansys mapdl validation ok')\n"
            "finally:\n"
            "    mapdl.exit()\n"
        )
    return (
        "from pathlib import Path\n"
        "Path('result.txt').write_text('validation worker ok\\n', encoding='utf-8')\n"
        "print('validation worker ok')\n"
    )


def build_worker_token_payload(access_token: str) -> dict:
    return {"agent_id": "wrk_validation", "access_token": access_token}
