param(
    [string]$OutputRoot = "C:\ProgramData\GuacDriveRestriction\baseline"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDirectory = Join-Path $OutputRoot $timestamp
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$result = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    computer_name = $env:COMPUTERNAME
    output_directory = $outputDirectory
    checks = [ordered]@{}
}

function Export-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    try {
        & $Action
        $result.checks[$Name] = "ok"
    }
    catch {
        $result.checks[$Name] = "error: $($_.Exception.Message)"
    }
}

Export-Check "computer" {
    Get-ComputerInfo |
        Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "computer.json") -Encoding utf8
}

Export-Check "gpresult" {
    & gpresult.exe /h (Join-Path $outputDirectory "gpresult.html") /f | Out-Null
}

Export-Check "local_users" {
    Get-LocalUser |
        Select-Object Name, Enabled, LastLogon, PasswordRequired, UserMayChangePassword |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "local-users.json") -Encoding utf8
}

Export-Check "local_groups" {
    Get-LocalGroup |
        ForEach-Object {
            [ordered]@{
                name = $_.Name
                members = @(Get-LocalGroupMember -Group $_.Name -ErrorAction SilentlyContinue | Select-Object Name, ObjectClass, PrincipalSource)
            }
        } |
        ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "local-groups.json") -Encoding utf8
}

Export-Check "applocker" {
    Get-AppLockerPolicy -Effective -Xml |
        Set-Content -LiteralPath (Join-Path $outputDirectory "applocker-effective.xml") -Encoding utf8
}

Export-Check "firewall" {
    Get-NetFirewallRule -Enabled True |
        Select-Object DisplayName, Direction, Action, Profile, PolicyStoreSourceType |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "firewall-enabled-rules.json") -Encoding utf8
}

Export-Check "remoteapps" {
    Get-CimInstance -Namespace "root\cimv2\terminalservices" -ClassName Win32_TSPublishedApplication -ErrorAction Stop |
        Select-Object Name, Path, CommandLineSetting, RequiredCommandLine |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "remoteapps.json") -Encoding utf8
}

Export-Check "vscode" {
    $candidates = @(
        "C:\Apps\Microsoft VS Code\Code.exe",
        "C:\Program Files\Microsoft VS Code\Code.exe",
        "C:\Program Files (x86)\Microsoft VS Code\Code.exe"
    )
    $installed = $candidates | Where-Object { Test-Path -LiteralPath $_ }
    $installed |
        ForEach-Object {
            $item = Get-Item -LiteralPath $_
            [ordered]@{
                path = $item.FullName
                version = $item.VersionInfo.FileVersion
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash
            }
        } |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $outputDirectory "vscode.json") -Encoding utf8
}

$result |
    ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $outputDirectory "manifest.json") -Encoding utf8

Write-Output $outputDirectory
