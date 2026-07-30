param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [string]$RemoteAppUser = "GuacRemoteApp",
    [string]$VscodeUser = "GuacVscode",
    [string]$RemoteAppGroup = "GuacRestrictedRemoteApp",
    [string]$VscodeGroup = "GuacRestrictedVscode",
    [switch]$RemoveCreatedAccounts
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.Common.psm1") -Force -DisableNameChecking
Assert-GuacDriveAdministrator

$statePath = Join-Path $BackupDirectory "state.json"
$firewallPath = Join-Path $BackupDirectory "firewall.wfw"
$appLockerPath = Join-Path $BackupDirectory "applocker-effective.xml"
foreach ($requiredPath in @($statePath, $firewallPath, $appLockerPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Rollback artifact is missing: $requiredPath"
    }
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json

Set-AppLockerPolicy -XmlPolicy $appLockerPath
$appIdStartType = [string]$state.appidsvc.StartType
switch ($appIdStartType) {
    "Automatic" { & sc.exe config AppIDSvc start= auto | Out-Null }
    "Manual" { & sc.exe config AppIDSvc start= demand | Out-Null }
    "Disabled" { & sc.exe config AppIDSvc start= disabled | Out-Null }
}
if ([string]$state.appidsvc.Status -eq "Running") {
    Start-Service AppIDSvc -ErrorAction SilentlyContinue
}
else {
    Stop-Service AppIDSvc -Force -ErrorAction SilentlyContinue
}

& netsh.exe advfirewall import $firewallPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to restore Windows Firewall policy."
}

$remoteDesktopUsers = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-555"
Get-LocalGroupMember -Group $remoteDesktopUsers -ErrorAction SilentlyContinue |
    ForEach-Object {
        Remove-LocalGroupMember -Group $remoteDesktopUsers -Member $_ -ErrorAction SilentlyContinue
    }
foreach ($member in @($state.remote_desktop_users)) {
    Add-LocalGroupMember -Group $remoteDesktopUsers -Member $member.Name -ErrorAction SilentlyContinue
}

Set-ItemProperty `
    -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" `
    -Name "fSingleSessionPerUser" `
    -Value ([int]$state.rdp.single_session_per_user)
if ($null -ne $state.rdp.disable_drive_redirection) {
    Set-ItemProperty `
        -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" `
        -Name "fDisableCdm" `
        -Value ([int]$state.rdp.disable_drive_redirection)
}

$remoteAppRoot = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications"
foreach ($app in @($state.remoteapps)) {
    $path = Join-Path $remoteAppRoot $app.alias
    if (Test-Path -LiteralPath $path) {
        Set-ItemProperty -LiteralPath $path -Name "CommandLineSetting" -Value ([int]$app.command_line_setting)
        Set-ItemProperty -LiteralPath $path -Name "RequiredCommandLine" -Value ([string]$app.required_command_line)
    }
}

$vscodePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\VSCode"
Remove-Item -LiteralPath $vscodePolicyPath -Recurse -Force -ErrorAction SilentlyContinue
if ([bool]$state.vscode_policy_exists) {
    New-Item -Force -Path $vscodePolicyPath | Out-Null
    foreach ($property in $state.vscode_policy.PSObject.Properties) {
        $value = $property.Value
        if ($value -is [array]) {
            New-ItemProperty -LiteralPath $vscodePolicyPath -Name $property.Name -Value $value -PropertyType MultiString -Force | Out-Null
        }
        elseif ($value -is [int] -or $value -is [long]) {
            New-ItemProperty -LiteralPath $vscodePolicyPath -Name $property.Name -Value $value -PropertyType DWord -Force | Out-Null
        }
        else {
            New-ItemProperty -LiteralPath $vscodePolicyPath -Name $property.Name -Value ([string]$value) -PropertyType String -Force | Out-Null
        }
    }
}

foreach ($aclState in @($state.acls)) {
    if (-not (Test-Path -LiteralPath $aclState.path)) {
        continue
    }
    $acl = Get-Acl -LiteralPath $aclState.path
    $acl.SetSecurityDescriptorSddlForm([string]$aclState.sddl)
    Set-Acl -LiteralPath $aclState.path -AclObject $acl
}

Unregister-ScheduledTask -TaskName "GuacDrive Restricted Profile Cleanup" -Confirm:$false -ErrorAction SilentlyContinue

if ($RemoveCreatedAccounts) {
    foreach ($userName in @($RemoteAppUser, $VscodeUser)) {
        if (Get-LocalUser -Name $userName -ErrorAction SilentlyContinue) {
            Remove-LocalUser -Name $userName
        }
    }
    foreach ($groupName in @($RemoteAppGroup, $VscodeGroup)) {
        if (Get-LocalGroup -Name $groupName -ErrorAction SilentlyContinue) {
            Remove-LocalGroup -Name $groupName
        }
    }
}

[ordered]@{
    rolled_back_at = (Get-Date).ToString("o")
    backup_directory = $BackupDirectory
    removed_created_accounts = [bool]$RemoveCreatedAccounts
}
