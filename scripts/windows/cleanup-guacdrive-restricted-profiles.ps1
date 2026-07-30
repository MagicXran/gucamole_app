param(
    [string[]]$RestrictedUsers = @("GuacRemoteApp", "GuacVscode"),
    [string]$PortalProfilesRoot = "C:\PortalProfiles",
    [string]$LogRoot = "C:\ProgramData\GuacDriveRestriction\cleanup"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$result = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    users = [ordered]@{}
    vscode_cache = [ordered]@{}
}

$sessionLines = @(quser.exe 2>$null | ForEach-Object { $_.ToString() })

function Test-UserHasSession {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName
    )

    foreach ($line in $sessionLines) {
        if ($line -match ("(^|\s)" + [regex]::Escape($UserName) + "(\s|$)")) {
            return $true
        }
    }
    return $false
}

function Clear-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    $items = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $items.Count
}

foreach ($userName in $RestrictedUsers) {
    $hasSession = Test-UserHasSession -UserName $userName
    $profilePath = "C:\Users\$userName"
    $userResult = [ordered]@{
        active_session = $hasSession
        cleared = [ordered]@{}
    }
    if (-not $hasSession) {
        $paths = [ordered]@{
            desktop = Join-Path $profilePath "Desktop"
            documents = Join-Path $profilePath "Documents"
            downloads = Join-Path $profilePath "Downloads"
            temp = Join-Path $profilePath "AppData\Local\Temp"
            recent = Join-Path $profilePath "AppData\Roaming\Microsoft\Windows\Recent"
        }
        foreach ($entry in $paths.GetEnumerator()) {
            $userResult.cleared[$entry.Key] = Clear-DirectoryContents -Path $entry.Value
        }
    }
    $result.users[$userName] = $userResult
}

$vscodeHasSession = Test-UserHasSession -UserName "GuacVscode"
$result.vscode_cache.active_session = $vscodeHasSession
$result.vscode_cache.cleared = [ordered]@{}
if (-not $vscodeHasSession -and (Test-Path -LiteralPath $PortalProfilesRoot)) {
    $cacheNames = @(
        "Cache",
        "CachedData",
        "Code Cache",
        "GPUCache",
        "logs",
        "Service Worker\CacheStorage",
        "User\workspaceStorage"
    )
    foreach ($profileDirectory in Get-ChildItem -LiteralPath $PortalProfilesRoot -Directory -ErrorAction SilentlyContinue) {
        $profileResult = [ordered]@{}
        foreach ($relativePath in $cacheNames) {
            $profileResult[$relativePath] = Clear-DirectoryContents -Path (Join-Path $profileDirectory.FullName $relativePath)
        }
        $result.vscode_cache.cleared[$profileDirectory.Name] = $profileResult
    }
}

$result |
    ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath (Join-Path $LogRoot "$timestamp.json") -Encoding utf8
