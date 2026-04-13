"""
Probe registered software capabilities on worker nodes.
"""

from __future__ import annotations

from typing import Any

from backend.script_profiles import list_script_profiles
from backend.software_adapters import get_software_adapter


def probe_registered_software(registration_payload: dict[str, Any]) -> dict[str, Any]:
    supported_executor_keys = {
        str(item)
        for item in (registration_payload.get("supported_executor_keys") or [])
    }
    inventory: dict[str, Any] = {}
    for profile in list_script_profiles():
        if profile.get("executor_key") not in supported_executor_keys:
            continue
        adapter = get_software_adapter(profile.get("adapter_key"))
        if adapter is None:
            continue
        result = adapter.probe(profile)
        inventory[profile["profile_key"]] = result.as_dict()
    return inventory
