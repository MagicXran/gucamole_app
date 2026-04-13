"""
Software adapter registry for simulation runtimes.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SoftwarePreflightError(RuntimeError):
    def __init__(self, *, adapter_key: str, software_name: str, issues: list[str]):
        self.adapter_key = adapter_key
        self.software_name = software_name
        self.issues = issues
        message = f"{software_name} preflight failed: {', '.join(issues)}"
        super().__init__(message)


@dataclass(frozen=True)
class SoftwareProbeResult:
    adapter_key: str
    software_name: str
    ready: bool
    issues: list[str]
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_key": self.adapter_key,
            "software_name": self.software_name,
            "ready": self.ready,
            "issues": list(self.issues),
            "details": dict(self.details),
        }


class BaseSoftwareAdapter:
    key = ""
    display_name = ""

    def probe(self, runtime_config: dict[str, Any] | None = None) -> SoftwareProbeResult:
        raise NotImplementedError

    def preflight(self, runtime_config: dict[str, Any] | None = None) -> None:
        result = self.probe(runtime_config)
        if not result.ready:
            raise SoftwarePreflightError(
                adapter_key=self.key,
                software_name=result.software_name,
                issues=result.issues,
            )


class AnsysMapdlAdapter(BaseSoftwareAdapter):
    key = "ansys_mapdl"
    display_name = "ANSYS MAPDL"
    required_python_module = "ansys.mapdl.core"

    @staticmethod
    def _module_exists(module_name: str) -> bool:
        try:
            return importlib.util.find_spec(module_name) is not None
        except ModuleNotFoundError:
            return False

    def probe(self, runtime_config: dict[str, Any] | None = None) -> SoftwareProbeResult:
        runtime_config = runtime_config or {}
        issues: list[str] = []
        details: dict[str, Any] = {
            "required_python_module": self.required_python_module,
        }
        if not self._module_exists(self.required_python_module):
            issues.append(f"missing_python_module:{self.required_python_module}")

        mapdl_executable = str(runtime_config.get("mapdl_executable") or "").strip()
        if mapdl_executable:
            details["mapdl_executable"] = mapdl_executable
            executable_exists = Path(mapdl_executable).exists() or shutil.which(mapdl_executable) is not None
            if not executable_exists:
                issues.append(f"missing_executable:{mapdl_executable}")

        return SoftwareProbeResult(
            adapter_key=self.key,
            software_name=self.display_name,
            ready=len(issues) == 0,
            issues=issues,
            details=details,
        )


class AbaqusCliAdapter(BaseSoftwareAdapter):
    key = "abaqus_cli"
    display_name = "Abaqus CLI"

    def probe(self, runtime_config: dict[str, Any] | None = None) -> SoftwareProbeResult:
        runtime_config = runtime_config or {}
        issues: list[str] = []
        abaqus_executable = str(runtime_config.get("abaqus_executable") or "").strip() or "abaqus"
        executable_exists = Path(abaqus_executable).exists() or shutil.which(abaqus_executable) is not None
        if not executable_exists:
            issues.append(f"missing_executable:{abaqus_executable}")
        return SoftwareProbeResult(
            adapter_key=self.key,
            software_name=self.display_name,
            ready=len(issues) == 0,
            issues=issues,
            details={"abaqus_executable": abaqus_executable},
        )


_ADAPTERS: dict[str, BaseSoftwareAdapter] = {
    AnsysMapdlAdapter.key: AnsysMapdlAdapter(),
    AbaqusCliAdapter.key: AbaqusCliAdapter(),
}


def get_software_adapter(adapter_key: str | None) -> BaseSoftwareAdapter | None:
    if not adapter_key:
        return None
    return _ADAPTERS.get(str(adapter_key).strip())
