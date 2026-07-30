Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-GuacDriveAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator privileges are required."
    }
}

function Get-GuacDriveLocalGroupName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Sid
    )

    return (Get-LocalGroup -SID $Sid).Name
}

function Get-GuacDrivePrincipalSid {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $account = New-Object Security.Principal.NTAccount($env:COMPUTERNAME, $Name)
    return $account.Translate([Security.Principal.SecurityIdentifier]).Value
}

function Ensure-GuacDriveLocalGroup {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$Description = "GuacDrive restricted connection group"
    )

    $group = Get-LocalGroup -Name $Name -ErrorAction SilentlyContinue
    if (-not $group) {
        $group = New-LocalGroup -Name $Name -Description $Description
    }
    return $group
}

function Ensure-GuacDriveLocalUser {
    param(
        [Parameter(Mandatory = $true)]
        [pscredential]$Credential,
        [Parameter(Mandatory = $true)]
        [string]$GroupName,
        [string]$Description = "GuacDrive restricted RemoteApp account"
    )

    $userName = $Credential.UserName
    if ($userName.Contains("\")) {
        $userName = $userName.Split("\")[-1]
    }

    $user = Get-LocalUser -Name $userName -ErrorAction SilentlyContinue
    if (-not $user) {
        $user = New-LocalUser `
            -Name $userName `
            -Password $Credential.Password `
            -AccountNeverExpires `
            -PasswordNeverExpires `
            -UserMayNotChangePassword `
            -Description $Description
    }
    else {
        Set-LocalUser `
            -Name $userName `
            -Password $Credential.Password `
            -AccountNeverExpires `
            -PasswordNeverExpires $true `
            -UserMayChangePassword $false
        Enable-LocalUser -Name $userName
        $user = Get-LocalUser -Name $userName
    }

    $administrators = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-544"
    Remove-LocalGroupMember -Group $administrators -Member $userName -ErrorAction SilentlyContinue
    Add-LocalGroupMember -Group $GroupName -Member $userName -ErrorAction SilentlyContinue

    $remoteDesktopUsers = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-555"
    Add-LocalGroupMember -Group $remoteDesktopUsers -Member $userName -ErrorAction SilentlyContinue

    return Get-LocalUser -Name $userName
}

function Ensure-GuacDriveUserProfile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName
    )

    $sid = Get-GuacDrivePrincipalSid -Name $UserName
    $profileListPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$sid"
    if (Test-Path -LiteralPath $profileListPath) {
        return (Get-ItemProperty -LiteralPath $profileListPath).ProfileImagePath
    }

    if (-not ("GuacDrive.UserProfileNative" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace GuacDrive {
    public static class UserProfileNative {
        [DllImport("userenv.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern int CreateProfile(
            string pszUserSid,
            string pszUserName,
            StringBuilder pszProfilePath,
            uint cchProfilePath);
    }
}
"@
    }

    $profilePath = New-Object Text.StringBuilder 260
    $result = [GuacDrive.UserProfileNative]::CreateProfile($sid, $UserName, $profilePath, 260)
    if ($result -ne 0 -and $result -ne -2147024713) {
        throw "CreateProfile failed for $UserName with HRESULT $result."
    }

    if (Test-Path -LiteralPath $profileListPath) {
        return (Get-ItemProperty -LiteralPath $profileListPath).ProfileImagePath
    }
    if ($profilePath.Length -gt 0) {
        return $profilePath.ToString()
    }
    throw "Profile creation did not return a profile path for $UserName."
}

function Set-GuacDriveRegistryValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        $Value,
        [ValidateSet("String", "ExpandString", "DWord", "QWord", "MultiString")]
        [string]$PropertyType = "DWord"
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        $parentPath = Split-Path -Parent $Path
        if ($parentPath -and -not (Test-Path -LiteralPath $parentPath)) {
            Set-GuacDriveRegistryValue `
                -Path $parentPath `
                -Name "GuacDrivePlaceholder" `
                -Value 0
            Remove-ItemProperty `
                -LiteralPath $parentPath `
                -Name "GuacDrivePlaceholder" `
                -ErrorAction SilentlyContinue
        }
        New-Item -Force -Path $Path | Out-Null
    }
    New-ItemProperty `
        -LiteralPath $Path `
        -Name $Name `
        -Value $Value `
        -PropertyType $PropertyType `
        -Force | Out-Null
}

function Protect-GuacDriveRegistryPolicyKey {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RegistryPath,
        [Parameter(Mandatory = $true)]
        [string]$UserSid
    )

    $prefix = "Registry::HKEY_USERS\"
    if (-not $RegistryPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Only HKEY_USERS policy paths are supported: $RegistryPath"
    }
    $subKeyPath = $RegistryPath.Substring($prefix.Length)
    $key = [Microsoft.Win32.Registry]::Users.OpenSubKey(
        $subKeyPath,
        [Microsoft.Win32.RegistryKeyPermissionCheck]::ReadWriteSubTree,
        [Security.AccessControl.RegistryRights]::ChangePermissions)
    if (-not $key) {
        throw "Registry policy key does not exist: $RegistryPath"
    }

    try {
        $acl = $key.GetAccessControl()
        $acl.SetAccessRuleProtection($true, $false)
        $existingRules = $acl.GetAccessRules(
            $true,
            $true,
            [Security.Principal.SecurityIdentifier])
        foreach ($rule in @($existingRules)) {
            [void]$acl.RemoveAccessRuleAll($rule)
        }

        $inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit
        $propagation = [Security.AccessControl.PropagationFlags]::None
        $allow = [Security.AccessControl.AccessControlType]::Allow
        $fullControl = [Security.AccessControl.RegistryRights]::FullControl
        $readKey = [Security.AccessControl.RegistryRights]::ReadKey
        $systemSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-18")
        $administratorsSid = New-Object Security.Principal.SecurityIdentifier("S-1-5-32-544")
        $restrictedUserSid = New-Object Security.Principal.SecurityIdentifier($UserSid)

        $acl.AddAccessRule((New-Object Security.AccessControl.RegistryAccessRule(
            $systemSid, $fullControl, $inheritance, $propagation, $allow)))
        $acl.AddAccessRule((New-Object Security.AccessControl.RegistryAccessRule(
            $administratorsSid, $fullControl, $inheritance, $propagation, $allow)))
        $acl.AddAccessRule((New-Object Security.AccessControl.RegistryAccessRule(
            $restrictedUserSid, $readKey, $inheritance, $propagation, $allow)))
        $key.SetAccessControl($acl)
    }
    finally {
        $key.Dispose()
    }
}

function Set-GuacDriveUserPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName,
        [Parameter(Mandatory = $true)]
        [bool]$AllowCommandShell
    )

    $sid = Get-GuacDrivePrincipalSid -Name $UserName
    $profilePath = Ensure-GuacDriveUserProfile -UserName $UserName
    $hivePath = Join-Path $profilePath "NTUSER.DAT"
    if (-not (Test-Path -LiteralPath $hivePath)) {
        throw "User hive does not exist: $hivePath"
    }

    $loadedHiveName = "GuacDrive_" + ($sid -replace "-", "_")
    $loadedHiveRoot = "Registry::HKEY_USERS\$loadedHiveName"
    $alreadyLoaded = Test-Path -LiteralPath "Registry::HKEY_USERS\$sid"
    $root = if ($alreadyLoaded) { "Registry::HKEY_USERS\$sid" } else { $loadedHiveRoot }
    $hiveRegistryName = if ($alreadyLoaded) { $sid } else { $loadedHiveName }

    if (-not $alreadyLoaded) {
        $loadOutput = & reg.exe load "HKU\$loadedHiveName" $hivePath 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to load $UserName hive: $loadOutput"
        }
    }

    try {
        function Set-LoadedHiveValue {
            param(
                [Parameter(Mandatory = $true)]
                [string]$RelativePath,
                [Parameter(Mandatory = $true)]
                [string]$Name,
                [Parameter(Mandatory = $true)]
                [string]$Type,
                [Parameter(Mandatory = $true)]
                [string]$Data
            )

            $registryPath = "HKU\$hiveRegistryName\$RelativePath"
            $output = & reg.exe add $registryPath /v $Name /t $Type /d $Data /f 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to set $registryPath\${Name}: $output"
            }
        }

        $explorerPolicy = Join-Path $root "Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
        $systemPolicy = Join-Path $root "Software\Microsoft\Windows\CurrentVersion\Policies\System"
        $windowsSystemPolicy = Join-Path $root "Software\Policies\Microsoft\Windows\System"

        $explorerValues = [ordered]@{
            NoDrives = 12
            NoViewOnDrive = 12
            NoRun = 1
            NoControlPanel = 1
            NoNetConnectDisconnect = 1
            NoRecentDocsHistory = 1
            ClearRecentDocsOnExit = 1
            NoRecentDocsMenu = 1
            NoFolderOptions = 1
            NoViewContextMenu = 1
            NoWinKeys = 1
            NoSetTaskbar = 1
            NoSetFolders = 1
            NoDesktop = 1
        }
        foreach ($entry in $explorerValues.GetEnumerator()) {
            Set-LoadedHiveValue `
                -RelativePath "Software\Microsoft\Windows\CurrentVersion\Policies\Explorer" `
                -Name $entry.Key `
                -Type "REG_DWORD" `
                -Data ([string]$entry.Value)
        }

        Set-LoadedHiveValue `
            -RelativePath "Software\Microsoft\Windows\CurrentVersion\Policies\System" `
            -Name "DisableTaskMgr" `
            -Type "REG_DWORD" `
            -Data "1"
        Set-LoadedHiveValue `
            -RelativePath "Software\Microsoft\Windows\CurrentVersion\Policies\System" `
            -Name "DisableRegistryTools" `
            -Type "REG_DWORD" `
            -Data "1"
        Set-LoadedHiveValue `
            -RelativePath "Software\Policies\Microsoft\Windows\System" `
            -Name "DisableCMD" `
            -Type "REG_DWORD" `
            -Data $(if ($AllowCommandShell) { "0" } else { "1" })

        Set-LoadedHiveValue `
            -RelativePath "Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" `
            -Name "Desktop" `
            -Type "REG_EXPAND_SZ" `
            -Data "\\tsclient\GuacDrive"
        Set-LoadedHiveValue `
            -RelativePath "Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" `
            -Name "Personal" `
            -Type "REG_EXPAND_SZ" `
            -Data "\\tsclient\GuacDrive"
        Set-LoadedHiveValue `
            -RelativePath "Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" `
            -Name "{374DE290-123F-4565-9164-39C4925E467B}" `
            -Type "REG_EXPAND_SZ" `
            -Data "\\tsclient\GuacDrive"

        Protect-GuacDriveRegistryPolicyKey -RegistryPath $explorerPolicy -UserSid $sid
        Protect-GuacDriveRegistryPolicyKey -RegistryPath $systemPolicy -UserSid $sid
        Protect-GuacDriveRegistryPolicyKey -RegistryPath $windowsSystemPolicy -UserSid $sid
    }
    finally {
        if (-not $alreadyLoaded) {
            [GC]::Collect()
            [GC]::WaitForPendingFinalizers()
            $unloadOutput = & reg.exe unload "HKU\$loadedHiveName" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to unload $UserName hive: $unloadOutput"
            }
        }
    }
}

function Set-GuacDriveDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ModifyGroupSid
    )

    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    & icacls.exe $Path /inheritance:r | Out-Null
    & icacls.exe $Path /grant:r `
        "*S-1-5-18:(OI)(CI)(F)" `
        "*S-1-5-32-544:(OI)(CI)(F)" `
        "*${ModifyGroupSid}:(OI)(CI)(M)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set ACL on $Path."
    }
}

function Set-GuacDriveReadOnlyDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string[]]$ReadGroupSids
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Path does not exist: $Path"
    }

    & icacls.exe $Path /inheritance:r | Out-Null
    $grantArguments = @(
        $Path,
        "/grant:r",
        "*S-1-5-18:(OI)(CI)(F)",
        "*S-1-5-32-544:(OI)(CI)(F)"
    )
    foreach ($sid in $ReadGroupSids) {
        $grantArguments += "*${sid}:(OI)(CI)(RX)"
    }
    & icacls.exe @grantArguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to protect application directory $Path."
    }
}

function Add-GuacDriveRootWriteDeny {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string[]]$GroupSids
    )

    $acl = Get-Acl -LiteralPath $Path
    $rights = [Security.AccessControl.FileSystemRights]::CreateFiles -bor
        [Security.AccessControl.FileSystemRights]::CreateDirectories -bor
        [Security.AccessControl.FileSystemRights]::WriteData -bor
        [Security.AccessControl.FileSystemRights]::AppendData
    $deny = [Security.AccessControl.AccessControlType]::Deny
    foreach ($sid in $GroupSids) {
        $identity = New-Object Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $identity,
            $rights,
            [Security.AccessControl.InheritanceFlags]::None,
            [Security.AccessControl.PropagationFlags]::None,
            $deny)
        $acl.SetAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Set-GuacDriveLocalFolderReadOnly {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName
    )

    $profilePath = Ensure-GuacDriveUserProfile -UserName $UserName
    $userSid = Get-GuacDrivePrincipalSid -Name $UserName
    foreach ($folderName in @("Desktop", "Documents", "Downloads")) {
        $path = Join-Path $profilePath $folderName
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        & icacls.exe $path /inheritance:r | Out-Null
        & icacls.exe $path /grant:r `
            "*S-1-5-18:(OI)(CI)(F)" `
            "*S-1-5-32-544:(OI)(CI)(F)" `
            "*${userSid}:(OI)(CI)(RX)" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to protect $path."
        }
    }
}

function Set-GuacDriveVscodeEnterprisePolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$AllowedExtensions
    )

    if (-not $AllowedExtensions -or $AllowedExtensions.Count -eq 0) {
        throw "At least one VSCode extension ID must be allowed."
    }

    $policyPath = "HKLM:\SOFTWARE\Policies\Microsoft\VSCode"
    New-Item -Force -Path $policyPath | Out-Null

    $lines = New-Object Collections.Generic.List[string]
    [void]$lines.Add("{")
    [void]$lines.Add('  "*": false,')
    for ($index = 0; $index -lt $AllowedExtensions.Count; $index++) {
        $extensionId = $AllowedExtensions[$index]
        $suffix = if ($index -lt ($AllowedExtensions.Count - 1)) { "," } else { "" }
        [void]$lines.Add(('  "{0}": true{1}' -f $extensionId, $suffix))
    }
    [void]$lines.Add("}")

    Set-GuacDriveRegistryValue `
        -Path $policyPath `
        -Name "AllowedExtensions" `
        -Value $lines.ToArray() `
        -PropertyType MultiString
    Set-GuacDriveRegistryValue `
        -Path $policyPath `
        -Name "UpdateMode" `
        -Value "none" `
        -PropertyType String
}

function Set-GuacDriveRemoteAppRegistry {
    $root = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications"
    $targets = @(
        [ordered]@{ label = "vscode"; executable = "C:\Apps\Microsoft VS Code\Code.exe" },
        [ordered]@{ label = "calculator"; executable = "C:\Windows\System32\calc.exe" },
        [ordered]@{ label = "notepad"; executable = "C:\Windows\System32\notepad.exe" }
    )
    $publishedApps = @(Get-ChildItem -LiteralPath $root | ForEach-Object {
        [ordered]@{
            registry_path = $_.PSPath
            properties = Get-ItemProperty -LiteralPath $_.PSPath
        }
    })
    foreach ($target in $targets) {
        $publishedApp = $publishedApps |
            Where-Object { [string]::Equals($_.properties.Path, $target.executable, [StringComparison]::OrdinalIgnoreCase) } |
            Select-Object -First 1
        if (-not $publishedApp) {
            throw "Published RemoteApp is missing: $($target.label)"
        }
        Set-GuacDriveRegistryValue -Path $publishedApp.registry_path -Name "CommandLineSetting" -Value 1
        Set-GuacDriveRegistryValue -Path $publishedApp.registry_path -Name "RequiredCommandLine" -Value "" -PropertyType String
    }
}

function Set-GuacDriveRdpConfiguration {
    $terminalServerPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    $rdpTcpPath = Join-Path $terminalServerPath "WinStations\RDP-Tcp"
    $terminalServicesPolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"

    Set-GuacDriveRegistryValue -Path $terminalServerPath -Name "fSingleSessionPerUser" -Value 0
    Set-GuacDriveRegistryValue -Path $rdpTcpPath -Name "fDisableCdm" -Value 0
    Set-GuacDriveRegistryValue -Path $terminalServicesPolicyPath -Name "fDisableCdm" -Value 0
}

function Set-GuacDriveFirewallBaseline {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManagementSubnet
    )

    Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled True -DefaultInboundAction Block -DefaultOutboundAction Allow

    Get-NetFirewallRule -DisplayName "Remote Desktop" -ErrorAction SilentlyContinue |
        Disable-NetFirewallRule
    Get-NetFirewallRule -Name "WINRM-HTTP-In-TCP", "WINRM-HTTP-In-TCP-PUBLIC" -ErrorAction SilentlyContinue |
        Disable-NetFirewallRule

    $ruleDefinitions = @(
        [ordered]@{ Name = "GuacDrive-RDP-In"; DisplayName = "GuacDrive RDP inbound"; Direction = "Inbound"; Protocol = "TCP"; LocalPort = 3389; RemoteAddress = $ManagementSubnet; Action = "Allow" },
        [ordered]@{ Name = "GuacDrive-WinRM-HTTPS-In"; DisplayName = "GuacDrive WinRM HTTPS inbound"; Direction = "Inbound"; Protocol = "TCP"; LocalPort = 5986; RemoteAddress = $ManagementSubnet; Action = "Allow" },
        [ordered]@{ Name = "GuacDrive-WinRM-HTTP-In"; DisplayName = "GuacDrive WinRM HTTP fallback"; Direction = "Inbound"; Protocol = "TCP"; LocalPort = 5985; RemoteAddress = $ManagementSubnet; Action = "Allow" },
        [ordered]@{ Name = "GuacDrive-Block-SMB-TCP-Out"; DisplayName = "GuacDrive block SMB TCP outbound"; Direction = "Outbound"; Protocol = "TCP"; RemotePort = @("139", "445"); RemoteAddress = "Any"; Action = "Block" },
        [ordered]@{ Name = "GuacDrive-Block-SMB-UDP-Out"; DisplayName = "GuacDrive block NetBIOS UDP outbound"; Direction = "Outbound"; Protocol = "UDP"; RemotePort = @("137", "138"); RemoteAddress = "Any"; Action = "Block" }
    )

    foreach ($definition in $ruleDefinitions) {
        Remove-NetFirewallRule -Name $definition.Name -ErrorAction SilentlyContinue
        $parameters = @{
            Name = $definition.Name
            DisplayName = $definition.DisplayName
            Direction = $definition.Direction
            Protocol = $definition.Protocol
            Action = $definition.Action
            Profile = "Any"
            Enabled = "True"
            RemoteAddress = $definition.RemoteAddress
        }
        if ($definition.Contains("LocalPort")) {
            $parameters.LocalPort = $definition.LocalPort
        }
        if ($definition.Contains("RemotePort")) {
            $parameters.RemotePort = $definition.RemotePort
        }
        New-NetFirewallRule @parameters | Out-Null
    }

    $webClient = Get-Service -Name WebClient -ErrorAction SilentlyContinue
    if ($webClient) {
        Stop-Service -Name WebClient -Force -ErrorAction SilentlyContinue
        Set-Service -Name WebClient -StartupType Disabled
    }
}

function Get-GuacDriveVscodeContentDirectory {
    param(
        [string]$InstallRoot = "C:\Apps\Microsoft VS Code"
    )

    $codePath = Join-Path $InstallRoot "Code.exe"
    if (-not (Test-Path -LiteralPath $codePath)) {
        throw "VSCode executable does not exist: $codePath"
    }
    $version = (Get-Item -LiteralPath $codePath).VersionInfo.FileVersion
    foreach ($directory in Get-ChildItem -LiteralPath $InstallRoot -Directory) {
        $packagePath = Join-Path $directory.FullName "resources\app\package.json"
        if (-not (Test-Path -LiteralPath $packagePath)) {
            continue
        }
        $package = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
        if ([string]$package.version -eq $version) {
            return $directory.FullName
        }
    }
    throw "No VSCode content directory matches Code.exe version $version."
}

function Save-GuacDriveRestrictionBackup {
    param(
        [string]$BackupRoot = "C:\ProgramData\GuacDriveRestriction\backups",
        [string[]]$AclPaths = @("C:\", "C:\Apps", "C:\ProgramData", "C:\PortalProfiles", "C:\PortalExtensions")
    )

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDirectory = Join-Path $BackupRoot $timestamp
    New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null

    $appLockerPath = Join-Path $backupDirectory "applocker-effective.xml"
    Get-AppLockerPolicy -Effective -Xml | Set-Content -LiteralPath $appLockerPath -Encoding utf8

    $firewallPath = Join-Path $backupDirectory "firewall.wfw"
    & netsh.exe advfirewall export $firewallPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to export Windows Firewall policy."
    }

    $remoteDesktopUsers = Get-GuacDriveLocalGroupName -Sid "S-1-5-32-555"
    $remoteAppRoot = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList\Applications"
    $vscodePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\VSCode"
    $state = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        computer_name = $env:COMPUTERNAME
        appidsvc = Get-Service AppIDSvc | Select-Object Status, StartType
        firewall_profiles = @(Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction)
        remote_desktop_users = @(Get-LocalGroupMember -Group $remoteDesktopUsers -ErrorAction SilentlyContinue | Select-Object Name, ObjectClass, PrincipalSource)
        rdp = [ordered]@{
            single_session_per_user = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server").fSingleSessionPerUser
            disable_drive_redirection = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" -ErrorAction SilentlyContinue).fDisableCdm
        }
        remoteapps = if (Test-Path -LiteralPath $remoteAppRoot) {
            @(Get-ChildItem -LiteralPath $remoteAppRoot | ForEach-Object {
                $app = Get-ItemProperty -LiteralPath $_.PSPath
                [ordered]@{
                    alias = $_.PSChildName
                    command_line_setting = $app.CommandLineSetting
                    required_command_line = $app.RequiredCommandLine
                }
            })
        } else { @() }
        vscode_policy_exists = Test-Path -LiteralPath $vscodePolicyPath
        vscode_policy = if (Test-Path -LiteralPath $vscodePolicyPath) {
            $key = Get-Item -LiteralPath $vscodePolicyPath
            $values = [ordered]@{}
            foreach ($valueName in $key.GetValueNames()) {
                $values[$valueName] = $key.GetValue($valueName)
            }
            $values
        } else { $null }
        local_users = @(Get-LocalUser | Select-Object Name, Enabled)
        local_groups = @(Get-LocalGroup | Select-Object Name, SID)
        acls = @($AclPaths | ForEach-Object {
            if (Test-Path -LiteralPath $_) {
                $acl = Get-Acl -LiteralPath $_
                [ordered]@{ path = $_; sddl = $acl.Sddl }
            }
        })
    }
    $state |
        ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath (Join-Path $backupDirectory "state.json") -Encoding utf8

    return $backupDirectory
}

Export-ModuleMember -Function @(
    "Assert-GuacDriveAdministrator",
    "Get-GuacDriveLocalGroupName",
    "Get-GuacDrivePrincipalSid",
    "Ensure-GuacDriveLocalGroup",
    "Ensure-GuacDriveLocalUser",
    "Ensure-GuacDriveUserProfile",
    "Set-GuacDriveUserPolicy",
    "Set-GuacDriveDirectoryAcl",
    "Set-GuacDriveReadOnlyDirectoryAcl",
    "Add-GuacDriveRootWriteDeny",
    "Set-GuacDriveLocalFolderReadOnly",
    "Set-GuacDriveVscodeEnterprisePolicy",
    "Set-GuacDriveRemoteAppRegistry",
    "Set-GuacDriveRdpConfiguration",
    "Set-GuacDriveFirewallBaseline",
    "Get-GuacDriveVscodeContentDirectory",
    "Save-GuacDriveRestrictionBackup"
)
