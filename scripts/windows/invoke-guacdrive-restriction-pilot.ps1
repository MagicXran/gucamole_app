param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [Parameter(Mandatory = $true)]
    [pscredential]$AdministratorCredential,
    [Parameter(Mandatory = $true)]
    [pscredential]$RemoteAppCredential,
    [Parameter(Mandatory = $true)]
    [pscredential]$VscodeCredential,
    [string]$ManagementSubnet = "192.168.56.0/24",
    [string[]]$AllowedExtensions = @("github.copilot-chat"),
    [ValidateSet("AuditOnly", "Enabled")]
    [string]$AppLockerMode = "AuditOnly",
    [int]$WinRmHttpsPort = 5986
)

$ErrorActionPreference = "Stop"
$sessionOption = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
$session = New-PSSession `
    -ComputerName $Target `
    -Port $WinRmHttpsPort `
    -UseSSL `
    -Credential $AdministratorCredential `
    -Authentication Negotiate `
    -SessionOption $sessionOption

try {
    $remoteDirectory = "C:\ProgramData\GuacDriveRestriction\deployment"
    Invoke-Command -Session $session -ScriptBlock {
        param($Path)
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    } -ArgumentList $remoteDirectory

    $files = @(
        "GuacDriveRestriction.Common.psm1",
        "GuacDriveRestriction.AppLocker.psm1",
        "cleanup-guacdrive-restricted-profiles.ps1",
        "install-guacdrive-restriction-pilot.ps1",
        "rollback-guacdrive-restriction-pilot.ps1",
        "set-guacdrive-applocker-mode.ps1",
        "test-guacdrive-restriction-pilot.ps1"
    )
    foreach ($fileName in $files) {
        Copy-Item `
            -LiteralPath (Join-Path $PSScriptRoot $fileName) `
            -Destination (Join-Path $remoteDirectory $fileName) `
            -ToSession $session `
            -Force
    }

    $deploymentConfig = [ordered]@{
        management_subnet = $ManagementSubnet
        allowed_extensions = @($AllowedExtensions)
        applocker_mode = $AppLockerMode
    }
    Invoke-Command -Session $session -ScriptBlock {
        param(
            $DeploymentDirectory,
            $RemoteAppCredential,
            $VscodeCredential,
            $DeploymentConfig
        )
        & (Join-Path $DeploymentDirectory "install-guacdrive-restriction-pilot.ps1") `
            -RemoteAppCredential $RemoteAppCredential `
            -VscodeCredential $VscodeCredential `
            -ManagementSubnet $DeploymentConfig.management_subnet `
            -AllowedExtensions @($DeploymentConfig.allowed_extensions) `
            -AppLockerMode $DeploymentConfig.applocker_mode
    } -ArgumentList @(
        $remoteDirectory,
        $RemoteAppCredential,
        $VscodeCredential,
        $deploymentConfig
    )
}
finally {
    Remove-PSSession $session
}
