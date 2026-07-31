import json
import subprocess
from pathlib import Path
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "windows" / "set-portal-session-filespace-entry.ps1"
MODULE_PATH = REPO_ROOT / "scripts" / "windows" / "PortalSessionFileSpace.psm1"
EXPECTED_TARGET = r"\\tsclient\用户空间"


def _run_script(*args: str) -> dict:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _run_module_script(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    script_path = tmp_path / "module-boundary-test.ps1"
    script_path.write_text(source, encoding="utf-8-sig")
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_plan_uses_exact_friendly_name_and_session_scoped_directory(tmp_path):
    portal_session_id = "7c4359b1-149e-469b-ac9c-da82d247ddaa"

    payload = _run_script(
        "-Username",
        "zhangsan",
        "-DisplayName",
        "张三",
        "-PortalSessionId",
        portal_session_id,
        "-WindowsSessionId",
        "41",
        "-Root",
        str(tmp_path),
        "-PlanOnly",
    )

    assert payload["display_name"] == "用户空间"
    assert payload["owner_name"] == "张三"
    assert Path(payload["entry_path"]).name == "用户空间.lnk"
    assert Path(payload["entry_directory"]).name == f"session_41_{portal_session_id}"
    assert payload["target_path"] == EXPECTED_TARGET
    assert payload["windows_session_id"] == 41
    assert UUID(payload["portal_session_id"]) == UUID(portal_session_id)


def test_two_sessions_produce_different_entry_directories(tmp_path):
    first = _run_script(
        "-Username",
        "zhangsan",
        "-PortalSessionId",
        "11111111-1111-4111-8111-111111111111",
        "-WindowsSessionId",
        "10",
        "-Root",
        str(tmp_path),
        "-PlanOnly",
    )
    second = _run_script(
        "-Username",
        "lisi",
        "-PortalSessionId",
        "22222222-2222-4222-8222-222222222222",
        "-WindowsSessionId",
        "11",
        "-Root",
        str(tmp_path),
        "-PlanOnly",
    )

    assert first["entry_directory"] != second["entry_directory"]
    assert first["entry_path"] != second["entry_path"]


def test_create_is_idempotent_and_remove_cleans_only_the_session_entry(tmp_path):
    common_args = (
        "-Username",
        "zhangsan",
        "-DisplayName",
        "张三",
        "-PortalSessionId",
        "33333333-3333-4333-8333-333333333333",
        "-WindowsSessionId",
        "51",
        "-Root",
        str(tmp_path),
    )

    first = _run_script(*common_args)
    second = _run_script(*common_args)

    entry_path = Path(first["entry_path"])
    metadata_path = Path(first["metadata_path"])
    assert first["action"] == "created"
    assert second["action"] == "updated"
    assert entry_path.is_file()
    assert metadata_path.is_file()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["display_name"] == "用户空间"
    assert metadata["owner_name"] == "张三"
    assert metadata["target_path"] == EXPECTED_TARGET

    removed = _run_script(*common_args, "-Remove")
    assert removed["action"] == "removed"
    assert not Path(first["entry_directory"]).exists()
    assert tmp_path.exists()


def test_rejects_nonstandard_target_path(tmp_path):
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-Username",
            "zhangsan",
            "-PortalSessionId",
            "44444444-4444-4444-8444-444444444444",
            "-Root",
            str(tmp_path),
            "-TargetPath",
            r"C:\Windows",
            "-PlanOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert "TargetPath" in (result.stderr + result.stdout)


def test_rejects_drive_relative_root(tmp_path):
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-Username",
            "zhangsan",
            "-PortalSessionId",
            "55555555-5555-4555-8555-555555555555",
            "-Root",
            "C:relative",
            "-PlanOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert "Root" in (result.stderr + result.stdout)


def test_exported_set_rejects_tampered_plan(tmp_path):
    result = _run_module_script(
        tmp_path,
        f"""
Import-Module '{MODULE_PATH}' -Force
$plan = Get-PortalSessionFileSpacePlan -Username 'zhangsan' -PortalSessionId '66666666-6666-4666-8666-666666666666' -WindowsSessionId 61 -Root '{tmp_path}'
$plan.target_path = 'C:\\Windows'
Set-PortalSessionFileSpaceEntry -Plan $plan | Out-Null
""",
    )

    assert result.returncode != 0
    assert "TargetPath" in (result.stderr + result.stdout)


def test_remove_refuses_session_directory_with_unexpected_files(tmp_path):
    result = _run_module_script(
        tmp_path,
        f"""
Import-Module '{MODULE_PATH}' -Force
$plan = Get-PortalSessionFileSpacePlan -Username 'zhangsan' -PortalSessionId '77777777-7777-4777-8777-777777777777' -WindowsSessionId 71 -Root '{tmp_path}'
Set-PortalSessionFileSpaceEntry -Plan $plan | Out-Null
Set-Content -LiteralPath (Join-Path $plan.entry_directory 'unexpected.txt') -Value 'keep'
Remove-PortalSessionFileSpaceEntry -Plan $plan | Out-Null
""",
    )

    assert result.returncode != 0
    assert "非入口文件" in (result.stderr + result.stdout)
    assert any(path.name == "unexpected.txt" for path in tmp_path.rglob("unexpected.txt"))


def test_create_replaces_legacy_owner_named_shortcut(tmp_path):
    result = _run_module_script(
        tmp_path,
        f"""
Import-Module '{MODULE_PATH}' -Force
$plan = Get-PortalSessionFileSpacePlan -Username 'zhangsan' -DisplayName '张三' -PortalSessionId '88888888-8888-4888-8888-888888888888' -WindowsSessionId 81 -Root '{tmp_path}'
New-Item -ItemType Directory -Path $plan.entry_directory -Force | Out-Null
$legacyPath = Join-Path $plan.entry_directory '张三的文件空间.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($legacyPath)
$shortcut.TargetPath = '{EXPECTED_TARGET}'
$shortcut.Save()
$result = Set-PortalSessionFileSpaceEntry -Plan $plan
[ordered]@{{
    action = $result.action
    current_exists = Test-Path -LiteralPath $result.entry_path
    legacy_exists = Test-Path -LiteralPath $legacyPath
    display_name = $result.display_name
}} | ConvertTo-Json -Compress
""",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "action": "created",
        "current_exists": True,
        "legacy_exists": False,
        "display_name": "用户空间",
    }
