[CmdletBinding()]
param(
    [int[]]$PortalUserIds = @(),
    [switch]$DiscoverExistingProfiles,
    [string]$ProfileRoot = "C:\PortalProfiles",
    [string[]]$AllowedUNCHosts = @("tsclient"),
    [string]$StateRoot = "C:\ProgramData\GuacDriveRestriction\backups"
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator privileges are required."
}

$ids = [Collections.Generic.HashSet[int]]::new()
foreach ($portalUserId in $PortalUserIds) {
    if ($portalUserId -le 0) {
        throw "PortalUserIds must contain positive integers."
    }
    [void]$ids.Add($portalUserId)
}

if ($DiscoverExistingProfiles -and (Test-Path -LiteralPath $ProfileRoot)) {
    foreach ($directory in Get-ChildItem -LiteralPath $ProfileRoot -Directory -ErrorAction Stop) {
        $portalUserId = 0
        if ([int]::TryParse($directory.Name, [ref]$portalUserId) -and $portalUserId -gt 0) {
            [void]$ids.Add($portalUserId)
        }
    }
}

if ($ids.Count -eq 0) {
    throw "No portal user profiles were selected."
}

$hosts = @(
    $AllowedUNCHosts |
        ForEach-Object { [string]$_ } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and $_ -notmatch "[\\/]" } |
        Sort-Object -Unique
)
if ($hosts.Count -eq 0) {
    throw "AllowedUNCHosts must contain at least one host name without slashes."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDirectory = Join-Path $StateRoot "$timestamp-vscode-profile-settings"
$utf8WithoutBom = [Text.UTF8Encoding]::new($false)
$results = New-Object Collections.Generic.List[object]

foreach ($portalUserId in @($ids | Sort-Object)) {
    $profileDirectory = Join-Path $ProfileRoot ([string]$portalUserId)
    $userDirectory = Join-Path $profileDirectory "User"
    $settingsPath = Join-Path $userDirectory "settings.json"
    New-Item -ItemType Directory -Force -Path $userDirectory | Out-Null

    $settings = [ordered]@{}
    $backedUp = $false
    if (Test-Path -LiteralPath $settingsPath) {
        $existing = Get-Content -LiteralPath $settingsPath -Raw -Encoding utf8
        try {
            $document = $existing | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            throw "Existing VSCode settings are not valid JSON: $settingsPath"
        }
        foreach ($property in $document.PSObject.Properties) {
            $settings[$property.Name] = $property.Value
        }

        $relativeBackupPath = Join-Path ([string]$portalUserId) "User\settings.json"
        $backupPath = Join-Path $backupDirectory $relativeBackupPath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupPath) | Out-Null
        Copy-Item -LiteralPath $settingsPath -Destination $backupPath -Force
        $backedUp = $true
    }

    $settings["security.allowedUNCHosts"] = $hosts
    $settings["security.restrictUNCAccess"] = $true
    $json = $settings | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($settingsPath, $json + "`r`n", $utf8WithoutBom)

    [void]$results.Add([ordered]@{
        portal_user_id = $portalUserId
        settings_path = $settingsPath
        backed_up = $backedUp
        allowed_unc_hosts = $hosts
    })
}

[ordered]@{
    changed_at = (Get-Date).ToString("o")
    backup_directory = $(if (Test-Path -LiteralPath $backupDirectory) { $backupDirectory } else { $null })
    profiles = $results
}
