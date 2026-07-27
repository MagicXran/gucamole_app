[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Username,

    [string]$DisplayName = '',

    [Parameter(Mandatory = $true)]
    [Guid]$PortalSessionId,

    [int]$WindowsSessionId = [System.Diagnostics.Process]::GetCurrentProcess().SessionId,

    [string]$TargetPath = '\\tsclient\UserFiles',

    [string]$Root = '',

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
    # 非交互会话可能没有可用控制台句柄。
}
$OutputEncoding = $utf8WithoutBom

try {
    $modulePath = Join-Path $PSScriptRoot 'PortalSessionFileSpace.psm1'
    Import-Module $modulePath -Force

    $plan = Get-PortalSessionFileSpacePlan `
        -Username $Username `
        -DisplayName $DisplayName `
        -PortalSessionId $PortalSessionId `
        -WindowsSessionId $WindowsSessionId `
        -TargetPath $TargetPath `
        -Root $Root

    if ($Remove) {
        $result = Remove-PortalSessionFileSpaceEntry -Plan $plan
    }
    elseif ($PlanOnly) {
        $result = $plan
    }
    else {
        $result = Set-PortalSessionFileSpaceEntry -Plan $plan
    }

    Write-Output ($result | ConvertTo-Json -Depth 5 -Compress)
}
catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 1
}
