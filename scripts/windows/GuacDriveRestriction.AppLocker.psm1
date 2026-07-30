Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Add-GuacDriveFilePathRule {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$Document,
        [Parameter(Mandatory = $true)]
        [System.Xml.XmlElement]$Collection,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$UserOrGroupSid,
        [Parameter(Mandatory = $true)]
        [ValidateSet("Allow", "Deny")]
        [string]$Action,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $rule = $Document.CreateElement("FilePathRule")
    $rule.SetAttribute("Id", [Guid]::NewGuid().ToString("D"))
    $rule.SetAttribute("Name", $Name)
    $rule.SetAttribute("Description", "GuacDrive restriction pilot")
    $rule.SetAttribute("UserOrGroupSid", $UserOrGroupSid)
    $rule.SetAttribute("Action", $Action)

    $conditions = $Document.CreateElement("Conditions")
    $condition = $Document.CreateElement("FilePathCondition")
    $condition.SetAttribute("Path", $Path)
    [void]$conditions.AppendChild($condition)
    [void]$rule.AppendChild($conditions)
    [void]$Collection.AppendChild($rule)
}

function New-GuacDriveRuleCollection {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$Document,
        [Parameter(Mandatory = $true)]
        [ValidateSet("Exe", "Script", "Msi", "Dll")]
        [string]$Type,
        [Parameter(Mandatory = $true)]
        [ValidateSet("AuditOnly", "Enabled")]
        [string]$EnforcementMode
    )

    $collection = $Document.CreateElement("RuleCollection")
    $collection.SetAttribute("Type", $Type)
    $collection.SetAttribute("EnforcementMode", $EnforcementMode)
    [void]$Document.DocumentElement.AppendChild($collection)
    return $collection
}

function New-GuacDriveAppLockerPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StrictGroupSid,
        [Parameter(Mandatory = $true)]
        [string]$VscodeGroupSid,
        [Parameter(Mandatory = $true)]
        [string]$VscodeContentDirectory,
        [ValidateSet("AuditOnly", "Enabled")]
        [string]$EnforcementMode = "AuditOnly"
    )

    $document = New-Object Xml.XmlDocument
    $root = $document.CreateElement("AppLockerPolicy")
    $root.SetAttribute("Version", "1")
    [void]$document.AppendChild($root)

    $administratorsSid = "S-1-5-32-544"
    $everyoneSid = "S-1-1-0"

    $exeCollection = New-GuacDriveRuleCollection `
        -Document $document `
        -Type "Exe" `
        -EnforcementMode $EnforcementMode
    Add-GuacDriveFilePathRule -Document $document -Collection $exeCollection -Name "Administrators may run all executables" -UserOrGroupSid $administratorsSid -Action Allow -Path "*"
    Add-GuacDriveFilePathRule -Document $document -Collection $exeCollection -Name "Allow Windows executables" -UserOrGroupSid $everyoneSid -Action Allow -Path "%WINDIR%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $exeCollection -Name "Allow Program Files executables" -UserOrGroupSid $everyoneSid -Action Allow -Path "%PROGRAMFILES%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $exeCollection -Name "Allow VSCode executable" -UserOrGroupSid $VscodeGroupSid -Action Allow -Path "C:\Apps\Microsoft VS Code\Code.exe"
    Add-GuacDriveFilePathRule -Document $document -Collection $exeCollection -Name "Allow current VSCode content" -UserOrGroupSid $VscodeGroupSid -Action Allow -Path "$VscodeContentDirectory\*"

    $strictDeniedExecutables = @(
        "%WINDIR%\explorer.exe",
        "%WINDIR%\System32\cmd.exe",
        "%WINDIR%\SysWOW64\cmd.exe",
        "%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe",
        "%WINDIR%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
        "%WINDIR%\System32\WindowsPowerShell\v1.0\powershell_ise.exe",
        "%WINDIR%\System32\wscript.exe",
        "%WINDIR%\System32\cscript.exe",
        "%WINDIR%\System32\mshta.exe",
        "%WINDIR%\System32\mmc.exe",
        "%WINDIR%\System32\taskmgr.exe",
        "%WINDIR%\System32\control.exe",
        "%WINDIR%\System32\reg.exe",
        "%WINDIR%\regedit.exe",
        "%WINDIR%\System32\rundll32.exe",
        "%WINDIR%\System32\msiexec.exe",
        "%WINDIR%\System32\schtasks.exe",
        "%WINDIR%\System32\sc.exe",
        "%WINDIR%\System32\net.exe",
        "%WINDIR%\System32\net1.exe",
        "%WINDIR%\System32\certutil.exe",
        "%WINDIR%\System32\bitsadmin.exe",
        "%WINDIR%\System32\curl.exe",
        "%WINDIR%\System32\ftp.exe",
        "%WINDIR%\System32\tftp.exe",
        "%WINDIR%\System32\wbem\wmic.exe",
        "%WINDIR%\System32\forfiles.exe",
        "C:\Apps\Microsoft VS Code\Code.exe",
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files\nodejs\*",
        "C:\Program Files\Python310\*",
        "C:\Program Files\Git\*",
        "C:\Program Files (x86)\RemoteApp Tool\RemoteApp Tool.exe",
        "C:\Program Files\Sandboxie-Plus\*",
        "C:\Program Files\TightVNC\*"
    )
    foreach ($path in $strictDeniedExecutables) {
        Add-GuacDriveFilePathRule `
            -Document $document `
            -Collection $exeCollection `
            -Name "Strict deny $path" `
            -UserOrGroupSid $StrictGroupSid `
            -Action Deny `
            -Path $path
    }

    $vscodeDeniedExecutables = @(
        "%WINDIR%\explorer.exe",
        "%WINDIR%\System32\wscript.exe",
        "%WINDIR%\System32\cscript.exe",
        "%WINDIR%\System32\mshta.exe",
        "%WINDIR%\System32\mmc.exe",
        "%WINDIR%\System32\taskmgr.exe",
        "%WINDIR%\System32\control.exe",
        "%WINDIR%\System32\reg.exe",
        "%WINDIR%\regedit.exe",
        "%WINDIR%\System32\rundll32.exe",
        "%WINDIR%\System32\msiexec.exe",
        "%WINDIR%\System32\schtasks.exe",
        "%WINDIR%\System32\sc.exe",
        "%WINDIR%\System32\net.exe",
        "%WINDIR%\System32\net1.exe",
        "%WINDIR%\System32\certutil.exe",
        "%WINDIR%\System32\bitsadmin.exe",
        "%WINDIR%\System32\ftp.exe",
        "%WINDIR%\System32\tftp.exe",
        "%WINDIR%\System32\wbem\wmic.exe",
        "C:\Apps\Microsoft VS Code\new_Code.exe",
        "C:\Apps\Microsoft VS Code\unins000.exe",
        "C:\Apps\Microsoft VS Code\bin\code-tunnel.exe",
        "C:\Apps\Microsoft VS Code\bin\new_code-tunnel.exe",
        "C:\Program Files\Google\Chrome\Application\chrome.exe",
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files (x86)\RemoteApp Tool\RemoteApp Tool.exe",
        "C:\Program Files\Sandboxie-Plus\*",
        "C:\Program Files\TightVNC\*"
    )
    foreach ($path in $vscodeDeniedExecutables) {
        Add-GuacDriveFilePathRule `
            -Document $document `
            -Collection $exeCollection `
            -Name "VSCode deny $path" `
            -UserOrGroupSid $VscodeGroupSid `
            -Action Deny `
            -Path $path
    }

    $scriptCollection = New-GuacDriveRuleCollection `
        -Document $document `
        -Type "Script" `
        -EnforcementMode $EnforcementMode
    Add-GuacDriveFilePathRule -Document $document -Collection $scriptCollection -Name "Administrators may run all scripts" -UserOrGroupSid $administratorsSid -Action Allow -Path "*"
    Add-GuacDriveFilePathRule -Document $document -Collection $scriptCollection -Name "Allow Windows scripts" -UserOrGroupSid $everyoneSid -Action Allow -Path "%WINDIR%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $scriptCollection -Name "Allow Program Files scripts" -UserOrGroupSid $everyoneSid -Action Allow -Path "%PROGRAMFILES%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $scriptCollection -Name "Strict users may not run scripts" -UserOrGroupSid $StrictGroupSid -Action Deny -Path "*"

    $msiCollection = New-GuacDriveRuleCollection `
        -Document $document `
        -Type "Msi" `
        -EnforcementMode $EnforcementMode
    Add-GuacDriveFilePathRule -Document $document -Collection $msiCollection -Name "Administrators may run all installers" -UserOrGroupSid $administratorsSid -Action Allow -Path "*"
    Add-GuacDriveFilePathRule -Document $document -Collection $msiCollection -Name "Allow Windows installer cache" -UserOrGroupSid $everyoneSid -Action Allow -Path "%WINDIR%\Installer\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $msiCollection -Name "Strict users may not run installers" -UserOrGroupSid $StrictGroupSid -Action Deny -Path "*"
    Add-GuacDriveFilePathRule -Document $document -Collection $msiCollection -Name "VSCode users may not run installers" -UserOrGroupSid $VscodeGroupSid -Action Deny -Path "*"

    $dllCollection = New-GuacDriveRuleCollection `
        -Document $document `
        -Type "Dll" `
        -EnforcementMode "AuditOnly"
    Add-GuacDriveFilePathRule -Document $document -Collection $dllCollection -Name "Administrators may load all DLLs" -UserOrGroupSid $administratorsSid -Action Allow -Path "*"
    Add-GuacDriveFilePathRule -Document $document -Collection $dllCollection -Name "Audit Windows DLLs" -UserOrGroupSid $everyoneSid -Action Allow -Path "%WINDIR%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $dllCollection -Name "Audit Program Files DLLs" -UserOrGroupSid $everyoneSid -Action Allow -Path "%PROGRAMFILES%\*"
    Add-GuacDriveFilePathRule -Document $document -Collection $dllCollection -Name "Audit current VSCode DLLs" -UserOrGroupSid $VscodeGroupSid -Action Allow -Path "$VscodeContentDirectory\*"

    return $document
}

function Install-GuacDriveAppLockerPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StrictGroupSid,
        [Parameter(Mandatory = $true)]
        [string]$VscodeGroupSid,
        [Parameter(Mandatory = $true)]
        [string]$VscodeContentDirectory,
        [ValidateSet("AuditOnly", "Enabled")]
        [string]$EnforcementMode = "AuditOnly",
        [string]$OutputDirectory = "C:\ProgramData\GuacDriveRestriction\policy"
    )

    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $policy = New-GuacDriveAppLockerPolicy `
        -StrictGroupSid $StrictGroupSid `
        -VscodeGroupSid $VscodeGroupSid `
        -VscodeContentDirectory $VscodeContentDirectory `
        -EnforcementMode $EnforcementMode
    $policyPath = Join-Path $OutputDirectory ("applocker-{0}.xml" -f $EnforcementMode.ToLowerInvariant())
    $policy.Save($policyPath)

    Set-AppLockerPolicy -XmlPolicy $policyPath
    & sc.exe config AppIDSvc start= auto | Out-Null
    Start-Service AppIDSvc

    return $policyPath
}

Export-ModuleMember -Function @(
    "New-GuacDriveAppLockerPolicy",
    "Install-GuacDriveAppLockerPolicy"
)
