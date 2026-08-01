[CmdletBinding()]
param(
    [string]$StateRoot = 'C:\ProgramData\NercarPortal',

    [string]$Alias = 'portal-freecad',

    [string]$FreeCADPath = 'C:\Program Files\FreeCAD 1.1\bin\freecad.exe',

    [string]$TargetPath = '\\tsclient\用户空间',

    [ValidatePattern('^[A-Z]$')]
    [string]$DriveLetter = 'U',

    [switch]$PlanOnly,

    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
try {
    [Console]::OutputEncoding = $utf8WithoutBom
}
catch {
    # 计划任务可能没有可用控制台句柄。
}
$OutputEncoding = $utf8WithoutBom

$expectedStateRoot = 'C:\ProgramData\NercarPortal'
$expectedAlias = 'portal-freecad'
$expectedName = 'FreeCAD 用户空间'
$expectedFreeCADPath = 'C:\Program Files\FreeCAD 1.1\bin\freecad.exe'
$expectedTargetPath = '\\tsclient\用户空间'
$expectedDriveLetter = 'U'
$launcherSource = Join-Path $PSScriptRoot 'PortalFreeCADLauncher.cs'
$launcherSourcePath = Join-Path $StateRoot 'PortalFreeCADLauncher.cs'
$launcherPath = Join-Path $StateRoot 'PortalFreeCADLauncher.exe'
$legacyLauncherPath = Join-Path $StateRoot 'PortalFreeCADLauncher.ps1'
$manifestPath = Join-Path $StateRoot 'portal-freecad-installation.json'
$compilerPath = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$legacyPowershellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$legacyRequiredCommandLine = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $legacyLauncherPath
$remoteAppRoot = 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications'
$remoteAppKey = Join-Path $remoteAppRoot $Alias
$rollbackRequired = $false
$rollbackBackupDirectory = $null
$rollbackRegistryPath = $null
$rollbackHadAlias = $false
$rollbackHadLauncherSource = $false
$rollbackHadLauncher = $false
$rollbackHadLegacyLauncher = $false
$rollbackHadManifest = $false

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ObjectPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [object]$DefaultValue = $null
    )

    $property = $InputObject.PSObject.Properties |
        Where-Object { $_.Name -eq $Name } |
        Select-Object -First 1
    if ($property) {
        return $property.Value
    }
    return $DefaultValue
}

function Get-ExistingRemoteAppState {
    if (-not (Test-Path -LiteralPath $remoteAppKey)) {
        return [ordered]@{
            exists = $false
            managed_alias = $false
            mode = 'missing'
        }
    }

    $item = Get-ItemProperty -LiteralPath $remoteAppKey
    $path = [string](Get-ObjectPropertyValue -InputObject $item -Name 'Path' -DefaultValue '')
    $vpath = [string](Get-ObjectPropertyValue -InputObject $item -Name 'VPath' -DefaultValue '')
    $name = [string](Get-ObjectPropertyValue -InputObject $item -Name 'Name' -DefaultValue '')
    $required = [string](Get-ObjectPropertyValue -InputObject $item -Name 'RequiredCommandLine' -DefaultValue '')
    $commandLineSetting = [int](Get-ObjectPropertyValue -InputObject $item -Name 'CommandLineSetting' -DefaultValue -1)
    $iconPath = [string](Get-ObjectPropertyValue -InputObject $item -Name 'IconPath' -DefaultValue '')
    $iconIndex = [int](Get-ObjectPropertyValue -InputObject $item -Name 'IconIndex' -DefaultValue -1)
    $showInTSWA = [int](Get-ObjectPropertyValue -InputObject $item -Name 'ShowInTSWA' -DefaultValue -1)
    $nativeAlias = `
        [string]::Equals($path, $launcherPath, [StringComparison]::OrdinalIgnoreCase) -and `
        [string]::Equals($vpath, $launcherPath, [StringComparison]::OrdinalIgnoreCase) -and `
        [string]::Equals($name, $expectedName, [StringComparison]::Ordinal) -and `
        [string]::IsNullOrEmpty($required) -and `
        $commandLineSetting -eq 0 -and `
        [string]::Equals($iconPath, $FreeCADPath, [StringComparison]::OrdinalIgnoreCase) -and `
        $iconIndex -eq 0 -and `
        $showInTSWA -eq 0
    $legacyAlias = `
        [string]::Equals($path, $legacyPowershellPath, [StringComparison]::OrdinalIgnoreCase) -and `
        [string]::Equals($vpath, $legacyPowershellPath, [StringComparison]::OrdinalIgnoreCase) -and `
        [string]::Equals($name, $expectedName, [StringComparison]::Ordinal) -and `
        [string]::Equals($required, $legacyRequiredCommandLine, [StringComparison]::Ordinal) -and `
        $commandLineSetting -eq 2 -and `
        [string]::Equals($iconPath, $FreeCADPath, [StringComparison]::OrdinalIgnoreCase) -and `
        $iconIndex -eq 0 -and `
        $showInTSWA -eq 0
    return [ordered]@{
        exists = $true
        managed_alias = ($nativeAlias -or $legacyAlias)
        mode = if ($nativeAlias) { 'native' } elseif ($legacyAlias) { 'legacy_powershell' } else { 'unknown' }
        name = $name
        path = $path
        vpath = $vpath
        required_command_line = $required
        command_line_setting = $commandLineSetting
        icon_path = $iconPath
        icon_index = $iconIndex
        show_in_tswa = $showInTSWA
    }
}

function Get-InstallationManifest {
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Test-DeployedLauncherIntegrity {
    if (-not (Test-Path -LiteralPath $launcherSourcePath -PathType Leaf)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        return $false
    }
    $manifest = Get-InstallationManifest
    if ($null -eq $manifest) {
        return $false
    }

    $manifestSourceHash = [string](Get-ObjectPropertyValue -InputObject $manifest -Name 'launcher_source_sha256' -DefaultValue '')
    $manifestLauncherHash = [string](Get-ObjectPropertyValue -InputObject $manifest -Name 'launcher_sha256' -DefaultValue '')
    $deployedSourceHash = (Get-FileHash -LiteralPath $launcherSourcePath -Algorithm SHA256).Hash
    $deployedLauncherHash = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash
    return `
        -not [string]::IsNullOrWhiteSpace($manifestSourceHash) -and `
        -not [string]::IsNullOrWhiteSpace($manifestLauncherHash) -and `
        [string]::Equals($manifestSourceHash, $deployedSourceHash, [StringComparison]::OrdinalIgnoreCase) -and `
        [string]::Equals($manifestLauncherHash, $deployedLauncherHash, [StringComparison]::OrdinalIgnoreCase)
}

function Test-LauncherContentMatches {
    if (-not (Test-DeployedLauncherIntegrity)) {
        return $false
    }
    $launcherSourceHash = (Get-FileHash -LiteralPath $launcherSource -Algorithm SHA256).Hash
    $deployedSourceHash = (Get-FileHash -LiteralPath $launcherSourcePath -Algorithm SHA256).Hash
    return [string]::Equals($launcherSourceHash, $deployedSourceHash, [StringComparison]::OrdinalIgnoreCase)
}

try {
    if (-not [string]::Equals($StateRoot, $expectedStateRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "StateRoot 只能是 $expectedStateRoot。"
    }
    if (-not [string]::Equals($Alias, $expectedAlias, [StringComparison]::Ordinal)) {
        throw "Alias 只能是 $expectedAlias。"
    }
    if (-not [string]::Equals($FreeCADPath, $expectedFreeCADPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw "FreeCADPath 只能是 $expectedFreeCADPath。"
    }
    if (-not [string]::Equals($TargetPath, $expectedTargetPath, [StringComparison]::Ordinal)) {
        throw "TargetPath 只能是 $expectedTargetPath。"
    }
    if (-not [string]::Equals($DriveLetter, $expectedDriveLetter, [StringComparison]::Ordinal)) {
        throw "DriveLetter 只能是 $expectedDriveLetter。"
    }

    $existingState = Get-ExistingRemoteAppState
    $plan = [ordered]@{
        action = if ($Remove) { 'remove_planned' } else { 'planned' }
        alias = $Alias
        launcher_source = $launcherSource
        launcher_source_path = $launcherSourcePath
        launcher_path = $launcherPath
        compiler_path = $compilerPath
        freecad_path = $FreeCADPath
        target_path = $TargetPath
        drive_letter = $DriveLetter
        alias_exists = $existingState.exists
        managed_alias = $existingState.managed_alias
        alias_mode = $existingState.mode
    }
    if ($PlanOnly) {
        Write-Output ($plan | ConvertTo-Json -Depth 5 -Compress)
        exit 0
    }
    if (-not (Test-Administrator)) {
        throw '必须使用 Windows 管理员权限运行。'
    }
    if (-not (Test-Path -LiteralPath $launcherSource -PathType Leaf)) {
        throw "找不到 Launcher 源文件：$launcherSource"
    }
    if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) {
        throw "找不到 C# 编译器：$compilerPath"
    }
    if ($existingState.exists -and -not $existingState.managed_alias) {
        throw "Refusing to overwrite unknown RemoteApp alias: $Alias"
    }
    $hasLegacyArtifact = Test-Path -LiteralPath $legacyLauncherPath -PathType Leaf
    if ($hasLegacyArtifact -and $existingState.mode -ne 'legacy_powershell') {
        if ($Remove) {
            throw "Refusing to remove unknown legacy Launcher artifact: $legacyLauncherPath"
        }
        throw "Refusing to overwrite unknown legacy Launcher artifact: $legacyLauncherPath"
    }

    if ($Remove) {
        $changed = $false
        $hasLauncherArtifacts = `
            (Test-Path -LiteralPath $launcherSourcePath -PathType Leaf) -or `
            (Test-Path -LiteralPath $launcherPath -PathType Leaf) -or `
            (Test-Path -LiteralPath $manifestPath -PathType Leaf)
        if ($hasLauncherArtifacts -and -not (Test-DeployedLauncherIntegrity)) {
            throw "Refusing to remove incomplete or modified Launcher deployment: $StateRoot"
        }
        if ($existingState.exists) {
            Remove-Item -LiteralPath $remoteAppKey -Recurse -Force
            $changed = $true
        }
        if (Test-Path -LiteralPath $launcherSourcePath -PathType Leaf) {
            Remove-Item -LiteralPath $launcherSourcePath -Force
            $changed = $true
        }
        if (Test-Path -LiteralPath $launcherPath -PathType Leaf) {
            Remove-Item -LiteralPath $launcherPath -Force
            $changed = $true
        }
        if (Test-Path -LiteralPath $legacyLauncherPath -PathType Leaf) {
            Remove-Item -LiteralPath $legacyLauncherPath -Force
            $changed = $true
        }
        if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
            Remove-Item -LiteralPath $manifestPath -Force
            $changed = $true
        }
        $result = [ordered]@{
            action = 'removed'
            alias = $Alias
            launcher_path = $launcherPath
            managed_alias = $true
            changed = $changed
        }
        Write-Output ($result | ConvertTo-Json -Depth 5 -Compress)
        exit 0
    }

    if (-not (Test-Path -LiteralPath $FreeCADPath -PathType Leaf)) {
        throw "找不到 FreeCAD：$FreeCADPath"
    }

    $launcherMatches = Test-LauncherContentMatches
    $aliasMatches = $existingState.exists -and $existingState.mode -eq 'native'
    $changed = -not ($launcherMatches -and $aliasMatches)
    $backupDirectory = $null

    if ($changed) {
        New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
        $temporaryExecutable = "$launcherPath.new"
        Remove-Item -LiteralPath $temporaryExecutable -Force -ErrorAction SilentlyContinue
        $compileOutput = @(
            & $compilerPath `
                /nologo `
                /target:winexe `
                /optimize+ `
                /codepage:65001 `
                "/out:$temporaryExecutable" `
                $launcherSource 2>&1
        )
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $temporaryExecutable -PathType Leaf)) {
            Remove-Item -LiteralPath $temporaryExecutable -Force -ErrorAction SilentlyContinue
            throw "编译 Launcher 失败：$($compileOutput -join ' ')"
        }

        $backupDirectory = Join-Path `
            (Join-Path $StateRoot 'backups') `
            (Get-Date -Format 'yyyyMMdd-HHmmss')
        New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
        $rollbackHadAlias = $existingState.exists
        $rollbackHadLauncherSource = Test-Path -LiteralPath $launcherSourcePath -PathType Leaf
        $rollbackHadLauncher = Test-Path -LiteralPath $launcherPath -PathType Leaf
        $rollbackHadLegacyLauncher = Test-Path -LiteralPath $legacyLauncherPath -PathType Leaf
        $rollbackHadManifest = Test-Path -LiteralPath $manifestPath -PathType Leaf
        foreach ($path in @($launcherSourcePath, $launcherPath, $legacyLauncherPath, $manifestPath)) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                Copy-Item -LiteralPath $path -Destination $backupDirectory -Force
            }
        }
        if ($existingState.exists) {
            $backupRegistryPath = Join-Path $backupDirectory 'portal-freecad.reg'
            & reg.exe export "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications\$Alias" $backupRegistryPath /y | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw '导出 RemoteApp alias 备份失败。'
            }
            $rollbackRegistryPath = $backupRegistryPath
        }

        $rollbackBackupDirectory = $backupDirectory
        $rollbackRequired = $true
        Copy-Item -LiteralPath $launcherSource -Destination $launcherSourcePath -Force
        Move-Item -LiteralPath $temporaryExecutable -Destination $launcherPath -Force
        Remove-Item -LiteralPath $legacyLauncherPath -Force -ErrorAction SilentlyContinue

        New-Item -Path $remoteAppKey -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'Name' -Value $expectedName -PropertyType String -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'Path' -Value $launcherPath -PropertyType String -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'VPath' -Value $launcherPath -PropertyType String -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'RequiredCommandLine' -Value '' -PropertyType String -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'CommandLineSetting' -Value 0 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'IconPath' -Value $FreeCADPath -PropertyType String -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'IconIndex' -Value 0 -PropertyType DWord -Force | Out-Null
        New-ItemProperty -LiteralPath $remoteAppKey -Name 'ShowInTSWA' -Value 0 -PropertyType DWord -Force | Out-Null
    }

    $manifest = [ordered]@{
        installed_at = (Get-Date).ToString('o')
        alias = $Alias
        launcher_source_path = $launcherSourcePath
        launcher_path = $launcherPath
        launcher_source_sha256 = (Get-FileHash -LiteralPath $launcherSourcePath -Algorithm SHA256).Hash
        launcher_sha256 = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash
        freecad_path = $FreeCADPath
        target_path = $TargetPath
        drive_letter = $DriveLetter
        backup_directory = $backupDirectory
    }
    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
    [IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 5),
        $utf8WithoutBom
    )
    $rollbackRequired = $false

    $result = [ordered]@{
        action = if ($changed) { 'installed' } else { 'unchanged' }
        alias = $Alias
        launcher_path = $launcherPath
        backup_directory = $backupDirectory
        managed_alias = $true
        changed = $changed
    }
    Write-Output ($result | ConvertTo-Json -Depth 5 -Compress)
}
catch {
    $failureMessage = $_.Exception.Message
    if ($rollbackRequired) {
        try {
            foreach ($path in @($launcherSourcePath, $launcherPath, $legacyLauncherPath, $manifestPath)) {
                Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            }
            if ($rollbackHadLauncherSource) {
                Copy-Item -LiteralPath (Join-Path $rollbackBackupDirectory 'PortalFreeCADLauncher.cs') -Destination $launcherSourcePath -Force
            }
            if ($rollbackHadLauncher) {
                Copy-Item -LiteralPath (Join-Path $rollbackBackupDirectory 'PortalFreeCADLauncher.exe') -Destination $launcherPath -Force
            }
            if ($rollbackHadLegacyLauncher) {
                Copy-Item -LiteralPath (Join-Path $rollbackBackupDirectory 'PortalFreeCADLauncher.ps1') -Destination $legacyLauncherPath -Force
            }
            if ($rollbackHadManifest) {
                Copy-Item -LiteralPath (Join-Path $rollbackBackupDirectory 'portal-freecad-installation.json') -Destination $manifestPath -Force
            }
            Remove-Item -LiteralPath $remoteAppKey -Recurse -Force -ErrorAction SilentlyContinue
            if ($rollbackHadAlias -and $rollbackRegistryPath) {
                & reg.exe import $rollbackRegistryPath | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    throw '恢复 RemoteApp alias 备份失败。'
                }
            }
        }
        catch {
            Write-Error "Deployment rollback failed: $($_.Exception.Message)" -ErrorAction Continue
        }
    }
    Write-Error $failureMessage -ErrorAction Continue
    exit 1
}
