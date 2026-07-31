Set-StrictMode -Version Latest

$script:ExpectedTargetPath = '\\tsclient\用户空间'
$script:UserVisibleName = '用户空间'
$script:InvalidFileNameCharsPattern = '[<>:"/\\|?*\x00-\x1F]'
$script:MaximumIdentityLength = 64

function ConvertTo-PortalFileSpaceDisplayName {
    [CmdletBinding()]
    param()

    return $script:UserVisibleName
}

function ConvertTo-PortalFileSpaceOwnerName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Username,

        [string]$DisplayName = ''
    )

    $candidate = if ([string]::IsNullOrWhiteSpace($DisplayName)) {
        $Username
    }
    else {
        $DisplayName
    }

    $candidate = ($candidate -replace $script:InvalidFileNameCharsPattern, '_').Trim().TrimEnd('.', ' ')
    if ($candidate.Length -gt $script:MaximumIdentityLength) {
        $candidate = $candidate.Substring(0, $script:MaximumIdentityLength).TrimEnd('.', ' ')
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        throw 'Username 或 DisplayName 清理后为空。'
    }
    return $candidate
}

function Resolve-PortalSessionEntryRoot {
    [CmdletBinding()]
    param(
        [string]$Root = ''
    )

    $candidate = $Root
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw 'LOCALAPPDATA 为空，必须显式提供 Root。'
        }
        $candidate = Join-Path $env:LOCALAPPDATA 'PortalSessionEntries'
    }

    if ($candidate -notmatch '^[A-Za-z]:[\\/]' -or $candidate.StartsWith('\\')) {
        throw 'Root 必须是 Windows 本地绝对路径。'
    }
    $resolvedPath = [System.IO.Path]::GetFullPath($candidate)
    if ($resolvedPath.Length -eq 3 -and $resolvedPath[1] -eq ':') {
        return $resolvedPath
    }
    return $resolvedPath.TrimEnd('\')
}

function Get-PortalSessionFileSpacePlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Username,

        [string]$DisplayName = '',

        [Parameter(Mandatory = $true)]
        [Guid]$PortalSessionId,

        [int]$WindowsSessionId = [System.Diagnostics.Process]::GetCurrentProcess().SessionId,

        [string]$TargetPath = '\\tsclient\用户空间',

        [string]$Root = ''
    )

    if ($WindowsSessionId -lt 0) {
        throw 'WindowsSessionId 必须大于或等于 0。'
    }
    if (-not [string]::Equals(
        $TargetPath,
        $script:ExpectedTargetPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "TargetPath 只能是 $($script:ExpectedTargetPath)。"
    }

    $resolvedRoot = Resolve-PortalSessionEntryRoot -Root $Root
    $normalizedPortalSessionId = $PortalSessionId.ToString('D').ToLowerInvariant()
    $displayLabel = ConvertTo-PortalFileSpaceDisplayName
    $ownerName = ConvertTo-PortalFileSpaceOwnerName -Username $Username -DisplayName $DisplayName
    $entryDirectoryName = "session_{0}_{1}" -f $WindowsSessionId, $normalizedPortalSessionId
    $entryDirectory = Join-Path $resolvedRoot $entryDirectoryName
    $entryPath = Join-Path $entryDirectory ($displayLabel + '.lnk')
    $metadataPath = Join-Path $entryDirectory 'entry.json'

    return [ordered]@{
        action = 'planned'
        display_name = $displayLabel
        owner_name = $ownerName
        target_path = $script:ExpectedTargetPath
        root = $resolvedRoot
        entry_directory = $entryDirectory
        entry_path = $entryPath
        metadata_path = $metadataPath
        windows_session_id = $WindowsSessionId
        portal_session_id = $normalizedPortalSessionId
    }
}

function Write-PortalSessionEntryMetadata {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Plan
    )

    $metadata = [ordered]@{
        display_name = $Plan.display_name
        owner_name = $Plan.owner_name
        target_path = $Plan.target_path
        entry_path = $Plan.entry_path
        windows_session_id = $Plan.windows_session_id
        portal_session_id = $Plan.portal_session_id
        updated_at = [DateTimeOffset]::UtcNow.ToString('o')
    }
    $json = $metadata | ConvertTo-Json -Depth 4
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Plan.metadata_path, $json, $utf8WithoutBom)
}

function Assert-PortalSessionFileSpacePlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Plan
    )

    $requiredKeys = @(
        'display_name',
        'owner_name',
        'target_path',
        'root',
        'entry_directory',
        'entry_path',
        'metadata_path',
        'windows_session_id',
        'portal_session_id'
    )
    foreach ($requiredKey in $requiredKeys) {
        if (-not $Plan.Contains($requiredKey)) {
            throw "Plan 缺少字段：$requiredKey。"
        }
    }

    if (-not [string]::Equals(
        [string]$Plan.target_path,
        $script:ExpectedTargetPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Plan TargetPath 只能是 $($script:ExpectedTargetPath)。"
    }

    $windowsSessionId = 0
    if (-not [int]::TryParse(
        [string]$Plan.windows_session_id,
        [ref]$windowsSessionId
    ) -or $windowsSessionId -lt 0) {
        throw 'Plan WindowsSessionId 无效。'
    }

    $portalSessionId = [Guid]::Empty
    if (-not [Guid]::TryParseExact(
        [string]$Plan.portal_session_id,
        'D',
        [ref]$portalSessionId
    )) {
        throw 'Plan PortalSessionId 无效。'
    }

    $displayName = [string]$Plan.display_name
    $normalizedDisplayName = ConvertTo-PortalFileSpaceDisplayName
    if (-not [string]::Equals(
        $displayName,
        $normalizedDisplayName,
        [System.StringComparison]::Ordinal
    )) {
        throw 'Plan display_name 不是合法的文件空间名称。'
    }
    $ownerName = [string]$Plan.owner_name
    $normalizedOwnerName = ConvertTo-PortalFileSpaceOwnerName -Username $ownerName -DisplayName $ownerName
    if (-not [string]::Equals(
        $ownerName,
        $normalizedOwnerName,
        [System.StringComparison]::Ordinal
    )) {
        throw 'Plan owner_name 不是合法的用户名称。'
    }

    $resolvedRoot = Resolve-PortalSessionEntryRoot -Root ([string]$Plan.root)
    $normalizedPortalSessionId = $portalSessionId.ToString('D').ToLowerInvariant()
    $expectedDirectory = Join-Path $resolvedRoot ("session_{0}_{1}" -f $windowsSessionId, $normalizedPortalSessionId)
    $expectedEntryPath = Join-Path $expectedDirectory ($displayName + '.lnk')
    $expectedMetadataPath = Join-Path $expectedDirectory 'entry.json'

    $pathChecks = @(
        @([string]$Plan.entry_directory, $expectedDirectory, 'entry_directory'),
        @([string]$Plan.entry_path, $expectedEntryPath, 'entry_path'),
        @([string]$Plan.metadata_path, $expectedMetadataPath, 'metadata_path')
    )
    foreach ($pathCheck in $pathChecks) {
        $actualPath = [System.IO.Path]::GetFullPath($pathCheck[0])
        $expectedPath = [System.IO.Path]::GetFullPath($pathCheck[1])
        if (-not [string]::Equals(
            $actualPath,
            $expectedPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Plan $($pathCheck[2]) 超出计算出的会话入口范围。"
        }
    }

    if (Test-Path -LiteralPath $expectedDirectory) {
        $entryDirectoryItem = Get-Item -LiteralPath $expectedDirectory -Force
        if ($entryDirectoryItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw '拒绝操作重解析点形式的会话入口目录。'
        }
    }

    return [ordered]@{
        action = [string]$Plan.action
        display_name = $displayName
        owner_name = $ownerName
        target_path = $script:ExpectedTargetPath
        root = $resolvedRoot
        entry_directory = $expectedDirectory
        entry_path = $expectedEntryPath
        metadata_path = $expectedMetadataPath
        windows_session_id = $windowsSessionId
        portal_session_id = $normalizedPortalSessionId
    }
}

function Get-PortalLegacyEntryPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Plan
    )

    return Join-Path $Plan.entry_directory ($Plan.owner_name + '的文件空间.lnk')
}

function Test-PortalShortcutTarget {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($Path)
        return [string]::Equals(
            [string]$shortcut.TargetPath,
            $script:ExpectedTargetPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    }
    catch {
        return $false
    }
}

function Set-PortalSessionFileSpaceEntry {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Plan
    )

    $validatedPlan = Assert-PortalSessionFileSpacePlan -Plan $Plan
    $entryExisted = Test-Path -LiteralPath $validatedPlan.entry_path -PathType Leaf
    New-Item -ItemType Directory -Path $validatedPlan.entry_directory -Force | Out-Null
    $legacyEntryPath = Get-PortalLegacyEntryPath -Plan $validatedPlan
    if (-not [string]::Equals(
        $legacyEntryPath,
        $validatedPlan.entry_path,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and (Test-Path -LiteralPath $legacyEntryPath -PathType Leaf)) {
        if (-not (Test-PortalShortcutTarget -Path $legacyEntryPath)) {
            throw '旧会话入口目标不受信任，已拒绝覆盖。'
        }
        Remove-Item -LiteralPath $legacyEntryPath -Force
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($validatedPlan.entry_path)
    $shortcut.TargetPath = $validatedPlan.target_path
    $shortcut.WorkingDirectory = $validatedPlan.target_path
    $shortcut.Description = $validatedPlan.display_name
    $shortcut.Save()

    Write-PortalSessionEntryMetadata -Plan $validatedPlan
    $validatedPlan.action = if ($entryExisted) { 'updated' } else { 'created' }
    return $validatedPlan
}

function Remove-PortalSessionFileSpaceEntry {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Plan
    )

    $validatedPlan = Assert-PortalSessionFileSpacePlan -Plan $Plan
    if (Test-Path -LiteralPath $validatedPlan.entry_directory) {
        $managedPaths = @(
            [System.IO.Path]::GetFullPath($validatedPlan.entry_path),
            [System.IO.Path]::GetFullPath($validatedPlan.metadata_path)
        )
        $legacyEntryPath = Get-PortalLegacyEntryPath -Plan $validatedPlan
        if (Test-PortalShortcutTarget -Path $legacyEntryPath) {
            $managedPaths += [System.IO.Path]::GetFullPath($legacyEntryPath)
        }
        $unexpectedItems = @(
            Get-ChildItem -LiteralPath $validatedPlan.entry_directory -Force |
                Where-Object {
                    $candidatePath = [System.IO.Path]::GetFullPath($_.FullName)
                    -not ($managedPaths -contains $candidatePath)
                }
        )
        if ($unexpectedItems.Count -gt 0) {
            throw '会话入口目录包含非入口文件，已拒绝递归删除。'
        }

        foreach ($managedPath in $managedPaths) {
            if (Test-Path -LiteralPath $managedPath) {
                Remove-Item -LiteralPath $managedPath -Force
            }
        }
        Remove-Item -LiteralPath $validatedPlan.entry_directory -Force
    }
    $validatedPlan.action = 'removed'
    return $validatedPlan
}

Export-ModuleMember -Function @(
    'ConvertTo-PortalFileSpaceDisplayName',
    'Get-PortalSessionFileSpacePlan',
    'Set-PortalSessionFileSpaceEntry',
    'Remove-PortalSessionFileSpaceEntry'
)
