import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "windows" / "migrate-portal-filespace-labels.ps1"


def test_windows_label_migration_plan_targets_neutral_unc_and_restricted_users():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-PlanOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["action"] == "planned"
    assert payload["target_path"] == r"\\tsclient\UserFiles"
    assert payload["users"] == ["GuacRemoteApp", "GuacVscode"]
    assert r"\\tsclient\GuacDrive" in payload["legacy_paths"]
    assert payload["quick_access_app_id"] == "f01b4d95cf55d32a"


def test_windows_label_migration_is_standalone_and_updates_user_shell_folders():
    source = SCRIPT_PATH.read_text(encoding="utf-8-sig")

    assert "GuacDriveRestriction.Common.psm1" not in source
    assert "Explorer\\User Shell Folders" in source
    assert "'Desktop'" in source
    assert "'Personal'" in source
    assert "'{374DE290-123F-4565-9164-39C4925E467B}'" in source
    assert "MountPoints2" in source
    assert "AutomaticDestinations" in source
    assert "requires_logoff" in source


def test_windows_label_migration_rejects_unknown_legacy_path():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-LegacyPaths",
            r"\\tsclient\UnrelatedShare",
            "-PlanOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert "LegacyPaths" in (result.stderr + result.stdout)


def test_windows_label_migration_uses_exact_mountpoint_names_and_change_status():
    source = SCRIPT_PATH.read_text(encoding="utf-8-sig")

    assert "legacyMountPointNames" in source
    assert "status = if ($changeCount -gt 0) { 'updated' } else { 'unchanged' }" in source
    assert "requires_logoff = ($changeCount -gt 0 -and $hasActiveSession)" in source
    assert "-match '(?i)GuacDrive|用户数据目录'" not in source
