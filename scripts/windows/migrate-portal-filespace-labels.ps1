[CmdletBinding()]
param(
    [string[]]$Users = @('GuacRemoteApp', 'GuacVscode'),

    [string]$TargetPath = '\\tsclient\用户空间',

    [string[]]$LegacyPaths = @(
        '\\tsclient\GuacDrive',
        '\\tsclient\用户数据目录',
        '\\tsclient\UserFiles'
    ),

    [switch]$PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
try {
    [Console]::OutputEncoding = $utf8WithoutBom
}
catch {
    # WinRM/Scheduled Task 可能没有可用控制台句柄，JSON 仍通过 PowerShell 管道返回。
}
$OutputEncoding = $utf8WithoutBom

$expectedTargetPath = '\\tsclient\用户空间'
$userVisibleName = '用户空间'
$currentMountPointName = '##tsclient#用户空间'
$allowedLegacyPaths = @(
    '\\tsclient\GuacDrive',
    '\\tsclient\用户数据目录',
    '\\tsclient\UserFiles'
)
$quickAccessAppId = 'f01b4d95cf55d32a'
$userShellFolderNames = @(
    'Desktop',
    'Personal',
    '{374DE290-123F-4565-9164-39C4925E467B}'
)

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-LegacyPath {
    param(
        [AllowNull()]
        [object]$Value
    )

    $candidate = [string]$Value
    foreach ($legacyPath in $LegacyPaths) {
        if ([string]::Equals(
            $candidate,
            $legacyPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            return $true
        }
    }
    return $false
}

function Test-UserHasSession {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Username
    )

    $sessionLines = @(quser.exe 2>$null | ForEach-Object { $_.ToString() })
    foreach ($line in $sessionLines) {
        if ($line -match ("(^|\s)" + [regex]::Escape($Username) + "(\s|$)")) {
            return $true
        }
    }
    return $false
}

function Get-UserProfilePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Sid,

        [Parameter(Mandatory = $true)]
        [string]$Username
    )

    $profile = Get-CimInstance Win32_UserProfile -Filter "SID='$Sid'" -ErrorAction SilentlyContinue
    if ($profile -and -not [string]::IsNullOrWhiteSpace($profile.LocalPath)) {
        return [string]$profile.LocalPath
    }
    return "C:\Users\$Username"
}

function Open-UserRegistryHive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Sid,

        [Parameter(Mandatory = $true)]
        [string]$ProfilePath
    )

    $livePath = "Registry::HKEY_USERS\$Sid"
    if (Test-Path -LiteralPath $livePath) {
        return [ordered]@{
            hive_name = $Sid
            loaded_by_script = $false
        }
    }

    $ntUserPath = Join-Path $ProfilePath 'NTUSER.DAT'
    if (-not (Test-Path -LiteralPath $ntUserPath -PathType Leaf)) {
        throw "找不到用户注册表文件：$ntUserPath"
    }

    $hiveName = 'PortalFileSpaceMigration_' + ($Sid -replace '[^A-Za-z0-9_]', '_')
    $output = & reg.exe load "HKU\$hiveName" $ntUserPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "加载用户注册表失败：$output"
    }
    return [ordered]@{
        hive_name = $hiveName
        loaded_by_script = $true
    }
}

function Close-UserRegistryHive {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Hive
    )

    if (-not $Hive.loaded_by_script) {
        return
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    $output = & reg.exe unload "HKU\$($Hive.hive_name)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "卸载用户注册表失败：$output"
    }
}

function Update-UserShellFolders {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HiveName
    )

    $updated = New-Object Collections.Generic.List[string]
    $userShellFolders = "Registry::HKEY_USERS\$HiveName\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    if (-not (Test-Path -LiteralPath $userShellFolders)) {
        return @()
    }

    foreach ($name in $userShellFolderNames) {
        $current = Get-ItemPropertyValue -LiteralPath $userShellFolders -Name $name -ErrorAction SilentlyContinue
        if (Test-LegacyPath -Value $current) {
            New-ItemProperty `
                -LiteralPath $userShellFolders `
                -Name $name `
                -Value $TargetPath `
                -PropertyType ExpandString `
                -Force | Out-Null
            $updated.Add($name)
        }
    }
    return @($updated)
}

function Remove-LegacyMountPoints {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HiveName
    )

    $removed = New-Object Collections.Generic.List[string]
    $mountPoints = "Registry::HKEY_USERS\$HiveName\Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2"
    if (-not (Test-Path -LiteralPath $mountPoints)) {
        return @()
    }

    foreach ($key in Get-ChildItem -LiteralPath $mountPoints -ErrorAction SilentlyContinue) {
        if ($legacyMountPointNames -contains $key.PSChildName) {
            Remove-Item -LiteralPath $key.PSPath -Recurse -Force
            $removed.Add($key.PSChildName)
        }
    }
    return @($removed)
}

function Set-CurrentMountPointLabel {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HiveName
    )

    $mountPoints = "Registry::HKEY_USERS\$HiveName\Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2"
    $currentMountPoint = Join-Path $mountPoints $currentMountPointName
    if (-not (Test-Path -LiteralPath $mountPoints)) {
        New-Item -Path $mountPoints -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $currentMountPoint)) {
        New-Item -Path $currentMountPoint -Force | Out-Null
    }

    $mountPointProperties = Get-ItemProperty -LiteralPath $currentMountPoint
    $labelProperty = $mountPointProperties.PSObject.Properties |
        Where-Object { $_.Name -eq '_LabelFromReg' } |
        Select-Object -First 1
    $currentLabel = if ($labelProperty) { [string]$labelProperty.Value } else { '' }
    $normalizedCurrentLabel = $currentLabel.Normalize([System.Text.NormalizationForm]::FormC)
    $normalizedExpectedLabel = $userVisibleName.Normalize([System.Text.NormalizationForm]::FormC)
    $changed = $normalizedCurrentLabel -cne $normalizedExpectedLabel

    if ($changed) {
        New-ItemProperty `
            -LiteralPath $currentMountPoint `
            -Name '_LabelFromReg' `
            -Value $userVisibleName `
            -PropertyType String `
            -Force | Out-Null
    }
    return [ordered]@{
        registry_path = "$currentMountPointName\_LabelFromReg"
        previous_label = $currentLabel
        current_label = $userVisibleName
        changed = $changed
    }
}

function Remove-LegacyRecentState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProfilePath
    )

    $removed = New-Object Collections.Generic.List[string]
    $recentRoot = Join-Path $ProfilePath 'AppData\Roaming\Microsoft\Windows\Recent'
    if (-not (Test-Path -LiteralPath $recentRoot)) {
        return @()
    }

    foreach ($relativePath in @(
        "AutomaticDestinations\$quickAccessAppId.automaticDestinations-ms",
        "CustomDestinations\$quickAccessAppId.customDestinations-ms"
    )) {
        $path = Join-Path $recentRoot $relativePath
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Remove-Item -LiteralPath $path -Force
            $removed.Add($relativePath)
        }
    }

    $shell = New-Object -ComObject WScript.Shell
    foreach ($link in Get-ChildItem -LiteralPath $recentRoot -Filter '*.lnk' -File -ErrorAction SilentlyContinue) {
        try {
            $shortcut = $shell.CreateShortcut($link.FullName)
            if (Test-LegacyPath -Value $shortcut.TargetPath) {
                Remove-Item -LiteralPath $link.FullName -Force
                $removed.Add($link.Name)
            }
        }
        catch {
            continue
        }
    }
    return @($removed)
}

try {
    if (-not [string]::Equals(
        $TargetPath,
        $expectedTargetPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "TargetPath 只能是 $expectedTargetPath。"
    }
    foreach ($legacyPath in $LegacyPaths) {
        $isAllowedLegacyPath = $false
        foreach ($allowedLegacyPath in $allowedLegacyPaths) {
            if ([string]::Equals(
                $legacyPath,
                $allowedLegacyPath,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                $isAllowedLegacyPath = $true
                break
            }
        }
        if (-not $isAllowedLegacyPath) {
            throw "LegacyPaths 只能包含已知历史自动路径：$($allowedLegacyPaths -join ', ')。"
        }
    }
    $legacyMountPointNames = @(
        $LegacyPaths |
            ForEach-Object { $_ -replace '\\', '#' }
    )

    $plan = [ordered]@{
        action = if ($PlanOnly) { 'planned' } else { 'migrated' }
        target_path = $expectedTargetPath
        user_visible_name = $userVisibleName
        current_mount_point_name = $currentMountPointName
        legacy_paths = @($LegacyPaths)
        users = @($Users)
        quick_access_app_id = $quickAccessAppId
        results = @()
    }
    if ($PlanOnly) {
        Write-Output ($plan | ConvertTo-Json -Depth 6 -Compress)
        exit 0
    }
    if (-not (Test-Administrator)) {
        throw '必须使用 Windows 管理员权限运行。'
    }

    $results = @()
    foreach ($username in $Users) {
        $user = Get-LocalUser -Name $username -ErrorAction SilentlyContinue
        if (-not $user) {
            $results += [ordered]@{
                username = $username
                status = 'missing_user'
                requires_logoff = $false
            }
            continue
        }

        $sid = $user.Sid.Value
        $profilePath = Get-UserProfilePath -Sid $sid -Username $username
        $hive = $null
        try {
            $hive = Open-UserRegistryHive -Sid $sid -ProfilePath $profilePath
            $shellFolderChanges = @(Update-UserShellFolders -HiveName $hive.hive_name)
            $mountPointChanges = @(Remove-LegacyMountPoints -HiveName $hive.hive_name)
            $mountPointLabelResult = Set-CurrentMountPointLabel -HiveName $hive.hive_name
            $mountPointLabelChangeCount = if ($mountPointLabelResult.changed) { 1 } else { 0 }
            $recentStateChanges = @(Remove-LegacyRecentState -ProfilePath $profilePath)
            $changeCount = (
                $shellFolderChanges.Count +
                $mountPointChanges.Count +
                $mountPointLabelChangeCount +
                $recentStateChanges.Count
            )
            $hasActiveSession = Test-UserHasSession -Username $username
            $results += [ordered]@{
                username = $username
                status = if ($changeCount -gt 0) { 'updated' } else { 'unchanged' }
                sid = $sid
                profile_path = $profilePath
                requires_logoff = ($changeCount -gt 0 -and $hasActiveSession)
                user_shell_folders = $shellFolderChanges
                mount_points = $mountPointChanges
                mount_point_label = $mountPointLabelResult
                recent_state = $recentStateChanges
            }
        }
        finally {
            if ($hive) {
                Close-UserRegistryHive -Hive $hive
            }
        }
    }

    $plan.results = $results
    Write-Output ($plan | ConvertTo-Json -Depth 8 -Compress)
}
catch {
    $detail = "{0} | {1} | {2}" -f `
        $_.Exception.Message,
        $_.InvocationInfo.PositionMessage,
        $_.ScriptStackTrace
    Write-Error $detail -ErrorAction Continue
    exit 1
}
