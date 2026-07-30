param(
    [ValidateSet("AuditOnly", "Enabled")]
    [string]$Mode,
    [string]$RemoteAppGroup = "GuacRestrictedRemoteApp",
    [string]$VscodeGroup = "GuacRestrictedVscode"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.Common.psm1") -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.AppLocker.psm1") -Force -DisableNameChecking

Assert-GuacDriveAdministrator
$remoteAppGroupSid = Get-GuacDrivePrincipalSid -Name $RemoteAppGroup
$vscodeGroupSid = Get-GuacDrivePrincipalSid -Name $VscodeGroup
$vscodeContentDirectory = Get-GuacDriveVscodeContentDirectory
$policyPath = Install-GuacDriveAppLockerPolicy `
    -StrictGroupSid $remoteAppGroupSid `
    -VscodeGroupSid $vscodeGroupSid `
    -VscodeContentDirectory $vscodeContentDirectory `
    -EnforcementMode $Mode

[ordered]@{
    changed_at = (Get-Date).ToString("o")
    mode = $Mode
    policy_path = $policyPath
    vscode_content_directory = $vscodeContentDirectory
}
