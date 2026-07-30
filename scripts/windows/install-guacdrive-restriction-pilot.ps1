param(
    [Parameter(Mandatory = $true)]
    [pscredential]$RemoteAppCredential,
    [Parameter(Mandatory = $true)]
    [pscredential]$VscodeCredential,
    [string]$RemoteAppGroup = "GuacRestrictedRemoteApp",
    [string]$VscodeGroup = "GuacRestrictedVscode",
    [string]$ManagementSubnet = "192.168.56.0/24",
    [string[]]$AllowedExtensions = @("github.copilot-chat"),
    [ValidateSet("AuditOnly", "Enabled")]
    [string]$AppLockerMode = "AuditOnly",
    [string]$StateRoot = "C:\ProgramData\GuacDriveRestriction"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.Common.psm1") -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.AppLocker.psm1") -Force -DisableNameChecking

Assert-GuacDriveAdministrator

function Get-LocalUserNameFromCredential {
    param([pscredential]$Credential)
    $name = $Credential.UserName
    if ($name.Contains("\")) {
        return $name.Split("\")[-1]
    }
    return $name
}

$remoteAppUser = Get-LocalUserNameFromCredential -Credential $RemoteAppCredential
$vscodeUser = Get-LocalUserNameFromCredential -Credential $VscodeCredential
$backupDirectory = Save-GuacDriveRestrictionBackup

$remoteAppGroupObject = Ensure-GuacDriveLocalGroup `
    -Name $RemoteAppGroup `
    -Description "Strict GuacDrive RemoteApp users"
$vscodeGroupObject = Ensure-GuacDriveLocalGroup `
    -Name $VscodeGroup `
    -Description "Controlled GuacDrive VSCode users"

Ensure-GuacDriveLocalUser `
    -Credential $RemoteAppCredential `
    -GroupName $RemoteAppGroup `
    -Description "Strict GuacDrive RemoteApp account" | Out-Null
Ensure-GuacDriveLocalUser `
    -Credential $VscodeCredential `
    -GroupName $VscodeGroup `
    -Description "Controlled GuacDrive VSCode account" | Out-Null

$remoteDesktopUsers = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-555"
Get-LocalGroupMember -Group $remoteDesktopUsers -ErrorAction SilentlyContinue |
    Where-Object { $_.SID.Value -eq "S-1-1-0" } |
    ForEach-Object {
        Remove-LocalGroupMember -Group $remoteDesktopUsers -Member $_ -ErrorAction SilentlyContinue
    }

$remoteAppProfile = Ensure-GuacDriveUserProfile -UserName $remoteAppUser
$vscodeProfile = Ensure-GuacDriveUserProfile -UserName $vscodeUser
Set-GuacDriveUserPolicy -UserName $remoteAppUser -AllowCommandShell $false
Set-GuacDriveUserPolicy -UserName $vscodeUser -AllowCommandShell $true
Set-GuacDriveLocalFolderReadOnly -UserName $remoteAppUser
Set-GuacDriveLocalFolderReadOnly -UserName $vscodeUser

$remoteAppGroupSid = Get-GuacDrivePrincipalSid -Name $RemoteAppGroup
$vscodeGroupSid = Get-GuacDrivePrincipalSid -Name $VscodeGroup
Set-GuacDriveDirectoryAcl -Path "C:\PortalProfiles" -ModifyGroupSid $vscodeGroupSid
Set-GuacDriveDirectoryAcl -Path "C:\PortalExtensions" -ModifyGroupSid $vscodeGroupSid
Set-GuacDriveReadOnlyDirectoryAcl `
    -Path "C:\Apps" `
    -ReadGroupSids @($remoteAppGroupSid, $vscodeGroupSid)
Add-GuacDriveRootWriteDeny `
    -Path "C:\" `
    -GroupSids @($remoteAppGroupSid, $vscodeGroupSid)
Add-GuacDriveRootWriteDeny `
    -Path "C:\ProgramData" `
    -GroupSids @($remoteAppGroupSid, $vscodeGroupSid)

Set-GuacDriveVscodeEnterprisePolicy -AllowedExtensions $AllowedExtensions
Set-GuacDriveRemoteAppRegistry
Set-GuacDriveRdpConfiguration

$toolsDirectory = Join-Path $StateRoot "tools"
New-Item -ItemType Directory -Force -Path $toolsDirectory | Out-Null
$cleanupScript = Join-Path $toolsDirectory "cleanup-guacdrive-restricted-profiles.ps1"
Copy-Item `
    -LiteralPath (Join-Path $PSScriptRoot "cleanup-guacdrive-restricted-profiles.ps1") `
    -Destination $cleanupScript `
    -Force

$cleanupAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$cleanupScript`""
$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$recurringTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$cleanupTriggers = @($startupTrigger, $recurringTrigger)
$cleanupPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$cleanupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask `
    -TaskName "GuacDrive Restricted Profile Cleanup" `
    -Action $cleanupAction `
    -Trigger $cleanupTriggers `
    -Principal $cleanupPrincipal `
    -Settings $cleanupSettings `
    -Force | Out-Null

Set-GuacDriveFirewallBaseline -ManagementSubnet $ManagementSubnet

$vscodeContentDirectory = Get-GuacDriveVscodeContentDirectory
$appLockerPolicyPath = Install-GuacDriveAppLockerPolicy `
    -StrictGroupSid $remoteAppGroupSid `
    -VscodeGroupSid $vscodeGroupSid `
    -VscodeContentDirectory $vscodeContentDirectory `
    -EnforcementMode $AppLockerMode

$manifest = [ordered]@{
    installed_at = (Get-Date).ToString("o")
    computer_name = $env:COMPUTERNAME
    backup_directory = $backupDirectory
    remote_app_user = $remoteAppUser
    vscode_user = $vscodeUser
    remote_app_group = $RemoteAppGroup
    vscode_group = $VscodeGroup
    remote_app_profile = $remoteAppProfile
    vscode_profile = $vscodeProfile
    vscode_content_directory = $vscodeContentDirectory
    allowed_extensions = $AllowedExtensions
    applocker_mode = $AppLockerMode
    applocker_policy_path = $appLockerPolicyPath
    management_subnet = $ManagementSubnet
    rds_session_host_installed = [bool](Get-WindowsFeature RDS-RD-Server).Installed
}

$manifestPath = Join-Path $StateRoot "installation.json"
New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
$manifest |
    ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $manifestPath -Encoding utf8

$manifest
