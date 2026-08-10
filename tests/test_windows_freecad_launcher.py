import json
import subprocess
import tempfile
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = REPO_ROOT / "scripts" / "windows" / "PortalFreeCADLauncher.cs"
INSTALLER_PATH = REPO_ROOT / "scripts" / "windows" / "install-portal-freecad-launcher.ps1"


def test_freecad_launcher_file_encodings_match_windows_toolchains():
    assert not LAUNCHER_PATH.read_bytes().startswith(b"\xef\xbb\xbf")
    assert INSTALLER_PATH.read_bytes().startswith(b"\xef\xbb\xbf")


def test_freecad_launcher_installer_plan_is_fixed_and_machine_readable():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER_PATH),
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
    assert payload["alias"] == "portal-freecad"
    assert payload["launcher_path"] == r"C:\ProgramData\NercarPortal\PortalFreeCADLauncher.exe"
    assert payload["launcher_source_path"] == r"C:\ProgramData\NercarPortal\PortalFreeCADLauncher.cs"
    assert payload["freecad_path"] == r"C:\Program Files\FreeCAD 1.1\bin\freecad.exe"
    assert payload["target_path"] == r"\\tsclient\用户空间"
    assert payload["drive_letter"] == "U"


def test_freecad_launcher_waits_maps_starts_and_cleans_up():
    source = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "\\\\tsclient\\用户空间" in source
    assert 'private const string DriveName = "U:"' in source
    assert "WNetAddConnection2" in source
    assert "WNetCancelConnection2" in source
    assert "WNetGetConnection" in source
    assert "U: is already mapped to another target" in source
    assert "Directory.Exists(TargetPath)" in source
    assert "Thread.Sleep(1000)" in source
    assert "ProcessStartInfo" in source
    assert 'WorkingDirectory = @"U:\\"' in source
    assert "WaitForExit()" in source
    assert "FreeCADCmd.exe" in source
    assert "FileOpenSavePath" in source
    assert "SetString('FileOpenSavePath', 'U:/')" in source
    assert "SetShellLabel" not in source
    assert "_LabelFromReg" not in source
    assert "finally" in source
    assert "CleanupMapping" in source
    assert "mappingCreated" in source
    assert "args.Length != 0" in source


def test_freecad_launcher_uses_qt_file_dialog_to_hide_raw_rdpdr_entry():
    source = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "User parameter:BaseApp/Preferences/Dialog" in source
    assert "SetBool('DontUseNativeDialog', True)" in source


def test_freecad_launcher_installer_is_fail_closed_and_reversible():
    source = INSTALLER_PATH.read_text(encoding="utf-8-sig")

    assert "Test-Administrator" in source
    assert "TSAppAllowList\\Applications" in source
    assert "portal-freecad" in source
    assert "csc.exe" in source
    assert "CommandLineSetting" in source
    assert "RequiredCommandLine" in source
    assert "backup_directory" in source
    assert "managed_alias" in source
    assert "Refusing to overwrite" in source
    assert "Remove-Item -LiteralPath $remoteAppKey" in source
    assert "Remove-Item -LiteralPath $manifestPath" in source
    assert "$hasLauncherArtifacts" in source
    assert source.index("if ($hasLauncherArtifacts") < source.index(
        "Remove-Item -LiteralPath $remoteAppKey"
    )
    for property_name in ("VPath", "IconPath", "IconIndex", "ShowInTSWA"):
        assert property_name in source
    assert "$hasLegacyArtifact" in source
    assert "Refusing to remove unknown legacy Launcher artifact" in source
    assert "$rollbackRequired" in source
    assert "reg.exe import" in source
    assert "$manifestPath" in source
    assert "/codepage:65001" in source


def test_freecad_launcher_installer_detects_partial_source_only_deployment():
    source = INSTALLER_PATH.read_text(encoding="utf-8-sig")

    assert "launcher_source_sha256" in source
    assert "$deployedLauncherHash" in source
    assert "$manifestLauncherHash" in source
    assert "$manifestSourceHash" in source
    assert source.index("& $compilerPath") < source.index(
        "Copy-Item -LiteralPath $launcherSource -Destination $launcherSourcePath"
    )


def test_freecad_launcher_installer_parses_in_windows_powershell():
    installer = str(INSTALLER_PATH).replace("'", "''")
    command = (
        "$errors = @(); "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"  '{installer}', [ref]$null, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            command,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_freecad_launcher_compiles_with_windows_csharp_compiler():
    compiler = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    assert compiler.exists()
    output_path = Path(tempfile.gettempdir()) / f"PortalFreeCADLauncher-{uuid.uuid4().hex}.exe"
    try:
        result = subprocess.run(
            [
                str(compiler),
                "/nologo",
                "/target:winexe",
                "/optimize+",
                "/codepage:65001",
                f"/out:{output_path}",
                str(LAUNCHER_PATH),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert output_path.is_file()
    finally:
        output_path.unlink(missing_ok=True)
