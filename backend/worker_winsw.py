"""
WinSW service configuration helpers.
"""

from __future__ import annotations


def build_winsw_xml(
    *,
    service_id: str,
    service_name: str,
    description: str,
    python_executable: str,
    script_path: str,
    registration_path: str,
    credential_mode: str,
    state_dir: str,
    log_dir: str,
) -> str:
    return f"""<service>
  <id>{service_id}</id>
  <name>{service_name}</name>
  <description>{description}</description>
  <executable>{python_executable}</executable>
  <arguments>-u "{script_path}" "{registration_path}"</arguments>
  <workingdirectory>%BASE%</workingdirectory>
  <env name="PORTAL_WORKER_CREDENTIAL_STORE" value="{credential_mode}" />
  <env name="PORTAL_WORKER_STATE_DIR" value="{state_dir}" />
  <logpath>{log_dir}</logpath>
  <log mode="append" />
  <onfailure action="restart" delay="10 sec" />
</service>
"""
