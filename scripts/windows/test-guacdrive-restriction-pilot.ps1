param(
    [string]$RemoteAppUser = "GuacRemoteApp",
    [string]$VscodeUser = "GuacVscode",
    [string]$RemoteAppGroup = "GuacRestrictedRemoteApp",
    [string]$VscodeGroup = "GuacRestrictedVscode",
    [string[]]$ExpectedExtensions = @("github.copilot-chat"),
    [ValidateSet("AuditOnly", "Enabled")]
    [string]$ExpectedAppLockerMode = "AuditOnly"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "GuacDriveRestriction.Common.psm1") -Force -DisableNameChecking
Assert-GuacDriveAdministrator

$checks = New-Object Collections.Generic.List[object]
$warnings = New-Object Collections.Generic.List[string]

function Add-Check {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [bool]$Passed,
        [Parameter(Mandatory = $true)]
        [string]$Detail
    )

    [void]$checks.Add([ordered]@{
        name = $Name
        passed = $Passed
        detail = $Detail
    })
}

function Get-OfflineUserPolicyValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName,
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [string]$ValueName
    )

    $sid = Get-GuacDrivePrincipalSid -Name $UserName
    $profilePath = Ensure-GuacDriveUserProfile -UserName $UserName
    $alreadyLoaded = Test-Path -LiteralPath "Registry::HKEY_USERS\$sid"
    $loadedName = "GuacDriveTest_" + ($sid -replace "-", "_")
    if (-not $alreadyLoaded) {
        $output = & reg.exe load "HKU\$loadedName" (Join-Path $profilePath "NTUSER.DAT") 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to load $UserName hive: $output"
        }
    }
    $root = if ($alreadyLoaded) { "Registry::HKEY_USERS\$sid" } else { "Registry::HKEY_USERS\$loadedName" }
    try {
        $path = Join-Path $root $RelativePath
        return (Get-ItemProperty -LiteralPath $path -Name $ValueName -ErrorAction Stop).$ValueName
    }
    finally {
        if (-not $alreadyLoaded) {
            [GC]::Collect()
            [GC]::WaitForPendingFinalizers()
            & reg.exe unload "HKU\$loadedName" | Out-Null
        }
    }
}

$remoteAppUserObject = Get-LocalUser -Name $RemoteAppUser -ErrorAction SilentlyContinue
$vscodeUserObject = Get-LocalUser -Name $VscodeUser -ErrorAction SilentlyContinue
Add-Check -Name "remote_app_user_exists" -Passed ($null -ne $remoteAppUserObject) -Detail "User=$RemoteAppUser"
Add-Check -Name "vscode_user_exists" -Passed ($null -ne $vscodeUserObject) -Detail "User=$VscodeUser"

$administrators = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-544"
$administratorMembers = @(Get-LocalGroupMember -Group $administrators -ErrorAction SilentlyContinue | ForEach-Object { $_.SID.Value })
if ($remoteAppUserObject) {
    Add-Check `
        -Name "remote_app_user_is_standard" `
        -Passed ($administratorMembers -notcontains $remoteAppUserObject.SID.Value) `
        -Detail "SID=$($remoteAppUserObject.SID.Value)"
}
if ($vscodeUserObject) {
    Add-Check `
        -Name "vscode_user_is_standard" `
        -Passed ($administratorMembers -notcontains $vscodeUserObject.SID.Value) `
        -Detail "SID=$($vscodeUserObject.SID.Value)"
}

$remoteDesktopUsers = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-555"
$rdpMembers = @(Get-LocalGroupMember -Group $remoteDesktopUsers -ErrorAction SilentlyContinue)
$rdpMemberSids = @($rdpMembers | ForEach-Object { $_.SID.Value })
Add-Check `
    -Name "rdp_everyone_removed" `
    -Passed ($rdpMemberSids -notcontains "S-1-1-0") `
    -Detail (($rdpMembers | ForEach-Object Name) -join ", ")
if ($remoteAppUserObject) {
    Add-Check -Name "remote_app_user_can_rdp" -Passed ($rdpMemberSids -contains $remoteAppUserObject.SID.Value) -Detail "Remote Desktop Users membership"
}
if ($vscodeUserObject) {
    Add-Check -Name "vscode_user_can_rdp" -Passed ($rdpMemberSids -contains $vscodeUserObject.SID.Value) -Detail "Remote Desktop Users membership"
}

$terminalServer = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
$rdpTcp = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
Add-Check -Name "multiple_sessions_allowed" -Passed ([int]$terminalServer.fSingleSessionPerUser -eq 0) -Detail "fSingleSessionPerUser=$($terminalServer.fSingleSessionPerUser)"
Add-Check -Name "drive_redirection_enabled" -Passed ([int]$rdpTcp.fDisableCdm -eq 0) -Detail "fDisableCdm=$($rdpTcp.fDisableCdm)"

$remoteAppRoot = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications"
$publishedApps = @(Get-ChildItem -LiteralPath $remoteAppRoot | ForEach-Object {
    [ordered]@{
        alias = $_.PSChildName
        properties = Get-ItemProperty -LiteralPath $_.PSPath
    }
})
foreach ($target in @(
    [ordered]@{ label = "vscode"; executable = "C:\Apps\Microsoft VS Code\Code.exe" },
    [ordered]@{ label = "calculator"; executable = "C:\Windows\System32\calc.exe" },
    [ordered]@{ label = "notepad"; executable = "C:\Windows\System32\notepad.exe" }
)) {
    $publishedApp = $publishedApps |
        Where-Object { [string]::Equals($_.properties.Path, $target.executable, [StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -First 1
    $app = if ($publishedApp) { $publishedApp.properties } else { $null }
    Add-Check `
        -Name ("remoteapp_arguments_" + $target.label) `
        -Passed ($app -and [int]$app.CommandLineSetting -eq 1) `
        -Detail $(if ($app) { "CommandLineSetting=$($app.CommandLineSetting)" } else { "missing" })
}

$strictNoDrives = Get-OfflineUserPolicyValue `
    -UserName $RemoteAppUser `
    -RelativePath "Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" `
    -ValueName "NoDrives"
$strictDisableCmd = Get-OfflineUserPolicyValue `
    -UserName $RemoteAppUser `
    -RelativePath "Software\Policies\Microsoft\Windows\System" `
    -ValueName "DisableCMD"
$vscodeNoDrives = Get-OfflineUserPolicyValue `
    -UserName $VscodeUser `
    -RelativePath "Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" `
    -ValueName "NoDrives"
$vscodeDisableCmd = Get-OfflineUserPolicyValue `
    -UserName $VscodeUser `
    -RelativePath "Software\Policies\Microsoft\Windows\System" `
    -ValueName "DisableCMD"
Add-Check -Name "strict_drive_policy" -Passed ([int]$strictNoDrives -eq 12) -Detail "NoDrives=$strictNoDrives"
Add-Check -Name "strict_command_shell_disabled" -Passed ([int]$strictDisableCmd -eq 1) -Detail "DisableCMD=$strictDisableCmd"
Add-Check -Name "vscode_drive_policy" -Passed ([int]$vscodeNoDrives -eq 12) -Detail "NoDrives=$vscodeNoDrives"
Add-Check -Name "vscode_command_shell_allowed" -Passed ([int]$vscodeDisableCmd -eq 0) -Detail "DisableCMD=$vscodeDisableCmd"

$vscodePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\VSCode"
$vscodePolicy = Get-ItemProperty -LiteralPath $vscodePolicyPath -ErrorAction SilentlyContinue
$allowedExtensionsValid = $false
$allowedExtensionsDetail = "missing"
if ($vscodePolicy -and $vscodePolicy.AllowedExtensions) {
    try {
        $policyObject = (@($vscodePolicy.AllowedExtensions) -join "`n") | ConvertFrom-Json
        $allowedExtensionsValid = $policyObject."*" -eq $false
        foreach ($extensionId in $ExpectedExtensions) {
            $extensionProperty = $policyObject.PSObject.Properties[$extensionId]
            $allowedExtensionsValid = $allowedExtensionsValid -and $extensionProperty -and ($extensionProperty.Value -eq $true)
        }
        $allowedExtensionsDetail = (@($vscodePolicy.AllowedExtensions) -join " ")
    }
    catch {
        $allowedExtensionsDetail = $_.Exception.Message
    }
}
Add-Check -Name "vscode_allowed_extensions_policy" -Passed $allowedExtensionsValid -Detail $allowedExtensionsDetail

$profiles = @(Get-NetFirewallProfile)
Add-Check `
    -Name "firewall_enabled" `
    -Passed (-not ($profiles | Where-Object { -not $_.Enabled })) `
    -Detail (($profiles | ForEach-Object { "$($_.Name)=$($_.Enabled)" }) -join ", ")
foreach ($ruleName in @(
    "GuacDrive-RDP-In",
    "GuacDrive-WinRM-HTTPS-In",
    "GuacDrive-WinRM-HTTP-In",
    "GuacDrive-Block-SMB-TCP-Out",
    "GuacDrive-Block-SMB-UDP-Out"
)) {
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    Add-Check -Name ("firewall_rule_" + $ruleName) -Passed ($rule -and $rule.Enabled -eq "True") -Detail $(if ($rule) { "$($rule.Direction)/$($rule.Action)" } else { "missing" })
}

$appIdService = Get-Service AppIDSvc
Add-Check -Name "application_identity_running" -Passed ($appIdService.Status -eq "Running") -Detail "Status=$($appIdService.Status); StartType=$($appIdService.StartType)"
$appLockerPolicy = Get-AppLockerPolicy -Effective
$collectionModes = @{}
foreach ($collection in $appLockerPolicy.RuleCollections) {
    $collectionModes[$collection.RuleCollectionType.ToString()] = $collection.EnforcementMode.ToString()
}
foreach ($collectionName in @("Exe", "Script", "Msi")) {
    Add-Check `
        -Name ("applocker_" + $collectionName.ToLowerInvariant()) `
        -Passed ($collectionModes[$collectionName] -eq $ExpectedAppLockerMode) `
        -Detail "Mode=$($collectionModes[$collectionName])"
}
Add-Check -Name "applocker_dll_audit" -Passed ($collectionModes["Dll"] -eq "AuditOnly") -Detail "Mode=$($collectionModes['Dll'])"

$cleanupTask = Get-ScheduledTask -TaskName "GuacDrive Restricted Profile Cleanup" -ErrorAction SilentlyContinue
Add-Check -Name "cleanup_task_registered" -Passed ($null -ne $cleanupTask) -Detail $(if ($cleanupTask) { $cleanupTask.State.ToString() } else { "missing" })

$rdsInstalled = [bool](Get-WindowsFeature RDS-RD-Server).Installed
if (-not $rdsInstalled) {
    [void]$warnings.Add("Remote Desktop Session Host role is not installed; the pilot relies on the existing RemoteApp Tool configuration and Windows administrative-session limits.")
}

$eventStart = (Get-Date).AddHours(-4)
$appLockerEvents = [ordered]@{}
foreach ($logName in @(
    "Microsoft-Windows-AppLocker/EXE and DLL",
    "Microsoft-Windows-AppLocker/MSI and Script"
)) {
    try {
        $events = @(Get-WinEvent -FilterHashtable @{ LogName = $logName; StartTime = $eventStart } -ErrorAction Stop)
        $appLockerEvents[$logName] = [ordered]@{
            count = $events.Count
            event_ids = @($events | Group-Object Id | ForEach-Object { [ordered]@{ id = $_.Name; count = $_.Count } })
        }
    }
    catch {
        $appLockerEvents[$logName] = [ordered]@{ error = $_.Exception.Message }
    }
}

$failedChecks = @($checks | Where-Object { -not $_.passed })
[ordered]@{
    generated_at = (Get-Date).ToString("o")
    passed = $failedChecks.Count -eq 0
    checks = $checks
    warnings = $warnings
    applocker_events = $appLockerEvents
}
