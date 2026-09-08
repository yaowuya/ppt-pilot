Set-StrictMode -Version 2.0
$script:PptPilotExcludedDirectories = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.tox', '.nox')
$script:PptPilotExcludedExtensions = @('.pyc', '.pyo')

function Assert-NoShadowingSkills {
    param([string]$SkillsRoot)
    if (-not (Test-Path -LiteralPath $SkillsRoot -PathType Container)) { return }
    $known = @('ppt-start', 'ppt-editable', 'ppt-style-extract')
    foreach ($child in Get-ChildItem -LiteralPath $SkillsRoot -Directory -Force) {
        if ($known -contains $child.Name) { continue }
        $entrypoint = Join-Path $child.FullName 'SKILL.md'
        if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) { continue }
        $declaresKnownSkill = Select-String -LiteralPath $entrypoint -Pattern '^name:\s*(ppt-start|ppt-editable|ppt-style-extract)\s*$' -Quiet
        if ($declaresKnownSkill) { throw "shadowing Skill discovery path: $($child.FullName)" }
    }
}

function Test-PptPilotPackagePath {
    param([string]$RelativePath)
    foreach ($part in $RelativePath.Replace('\', '/').Split('/')) {
        if ($script:PptPilotExcludedDirectories -contains $part) { return $false }
    }
    return -not ($script:PptPilotExcludedExtensions -contains [IO.Path]::GetExtension($RelativePath).ToLowerInvariant())
}

function Get-PptPilotFileSha256 {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path); $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Get-PptPilotTreeInfo {
    param([string]$Root)
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $files = @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force | Where-Object {
        Test-PptPilotPackagePath $_.FullName.Substring($rootPath.Length).TrimStart('\', '/')
    } | Sort-Object FullName)
    $memory = New-Object IO.MemoryStream; $encoding = New-Object Text.UTF8Encoding($false)
    try {
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($rootPath.Length).TrimStart('\', '/').Replace('\', '/')
            $bytes = $encoding.GetBytes("$relative`0$($file.Length)`0$(Get-PptPilotFileSha256 $file.FullName)`n")
            $memory.Write($bytes, 0, $bytes.Length)
        }
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = ([BitConverter]::ToString($sha.ComputeHash($memory.ToArray()))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    }
    finally { $memory.Dispose() }
    [pscustomobject]@{ Count = $files.Count; Digest = $digest }
}

function Copy-PptPilotFilteredTree {
    param([string]$Source, [string]$Destination)
    $sourcePath = [IO.Path]::GetFullPath($Source).TrimEnd('\', '/')
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($file in Get-ChildItem -LiteralPath $sourcePath -File -Recurse -Force) {
        $relative = $file.FullName.Substring($sourcePath.Length).TrimStart('\', '/')
        if (-not (Test-PptPilotPackagePath $relative)) { continue }
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

function Install-PptPilotTree {
    param([string]$Source, [string]$Destination, [string]$BackupRoot, [string]$Id, [string]$Timestamp)
    $parent = Split-Path -Parent $Destination
    $stageParent = Join-Path (Split-Path -Parent $parent) '.ppt-pilot-install-staging'
    $stage = Join-Path $stageParent ($Id + '-' + [guid]::NewGuid().ToString('N'))
    $backup = $null
    $destinationExisted = Test-Path -LiteralPath $Destination
    $backupMoved = $false
    $stageMoved = $false
    try {
        Copy-PptPilotFilteredTree $Source $stage
        $sourceInfo = Get-PptPilotTreeInfo $Source; $stageInfo = Get-PptPilotTreeInfo $stage
        if ($sourceInfo.Count -ne $stageInfo.Count -or $sourceInfo.Digest -ne $stageInfo.Digest) { throw "$Id staged tree digest mismatch" }
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        if (Test-Path -LiteralPath $Destination) {
            New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
            $backup = Join-Path $BackupRoot ("$Id.bak-$Timestamp-" + [guid]::NewGuid().ToString('N'))
            Move-Item -LiteralPath $Destination -Destination $backup
            $backupMoved = $true
        }
        Move-Item -LiteralPath $stage -Destination $Destination
        $stageMoved = $true
        $installedInfo = Get-PptPilotTreeInfo $Destination
        if ($sourceInfo.Count -ne $installedInfo.Count -or $sourceInfo.Digest -ne $installedInfo.Digest) { throw "$Id installed tree digest mismatch" }
        if (Test-Path -LiteralPath $BackupRoot -PathType Container) {
            foreach ($old in @(Get-ChildItem -LiteralPath $BackupRoot -Directory -Filter "$Id.bak-*" | Sort-Object LastWriteTimeUtc, Name -Descending | Select-Object -Skip 1)) {
                Remove-Item -LiteralPath $old.FullName -Recurse -Force
            }
        }
        return [pscustomobject]@{ Path = [IO.Path]::GetFullPath($Destination); Count = $installedInfo.Count; Digest = $installedInfo.Digest; Backup = $backup }
    }
    catch {
        $failure = $_.Exception
        if ($stageMoved -and (Test-Path -LiteralPath $Destination)) { Remove-Item -LiteralPath $Destination -Recurse -Force }
        if ($backupMoved -and (Test-Path -LiteralPath $backup)) { Move-Item -LiteralPath $backup -Destination $Destination }
        $failure.Data['PptPilotBackupMoved'] = $backupMoved
        $failure.Data['PptPilotBackupRestored'] = ($backupMoved -and (Test-Path -LiteralPath $Destination))
        throw $failure
    }
    finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
        if ((Test-Path -LiteralPath $stageParent -PathType Container) -and @(Get-ChildItem -LiteralPath $stageParent -Force).Count -eq 0) { Remove-Item -LiteralPath $stageParent -Force }
    }
}
