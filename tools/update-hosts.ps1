<#
.SYNOPSIS
更新 ppt-start 与 ppt-editable 到 DeepSeek、Claude Code、Codex 及可选项目级技能目录。
.DESCRIPTION
两个 Skill 使用同一 descriptor 流程；备份位于 skills 扫描根之外的 skill-backups，按 Skill ID 各保留最近一份。
#>
[CmdletBinding()]
param(
    [string]$MarketplaceRoot = '',
    [string]$ClaudeSkillsRoot = '',
    [string]$CodexSkillsRoot = '',
    [string]$RepoRoot = '',
    [string]$Version = '',
    [switch]$SkipDeepSeek,
    [switch]$SkipClaudeCode,
    [switch]$SkipCodex,
    [switch]$ProjectClaude,
    [switch]$ProjectCodex
)

$ErrorActionPreference = 'Stop'
$ts = (Get-Date).ToString('yyyyMMddHHmmss')
if (-not $RepoRoot) {
    if ($PSScriptRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
    else { $RepoRoot = (Get-Location).Path }
}

$skills = @(
    [ordered]@{ Id = 'ppt-start'; Source = Join-Path $RepoRoot 'skills\ppt-start' },
    [ordered]@{ Id = 'ppt-editable'; Source = Join-Path $RepoRoot 'skills\ppt-editable' },
    [ordered]@{ Id = 'ppt-style-extract'; Source = Join-Path $RepoRoot 'skills\ppt-style-extract' }
)
foreach ($skill in $skills) {
    if (-not (Test-Path -LiteralPath (Join-Path $skill.Source 'SKILL.md'))) {
        throw "源 Skill 缺 SKILL.md：$($skill.Source)"
    }
}

function Get-FileSha256 {
    param([string]$Path)
    $fileStream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($fileStream))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
        $fileStream.Dispose()
    }
}

function Get-SkillTreeInfo {
    param([string]$Root)
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $files = @(
        Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force |
            Sort-Object FullName
    )
    $stream = New-Object IO.MemoryStream
    $encoding = New-Object Text.UTF8Encoding($false)
    try {
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($rootPath.Length).TrimStart('\', '/').Replace('\', '/')
            $contentHash = Get-FileSha256 -Path $file.FullName
            $frame = "$relative`0$($file.Length)`0$contentHash`n"
            $bytes = $encoding.GetBytes($frame)
            $stream.Write($bytes, 0, $bytes.Length)
        }
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = ([BitConverter]::ToString($sha.ComputeHash($stream.ToArray()))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    }
    finally { $stream.Dispose() }
    return [pscustomobject]@{ Count = $files.Count; Digest = $digest }
}

function Copy-SkillWithBackup {
    param([System.Collections.IDictionary]$Descriptor, [string]$Destination)
    $id = [string]$Descriptor.Id
    $source = [string]$Descriptor.Source
    $skillsRoot = Split-Path -Parent $Destination
    $harnessRoot = Split-Path -Parent $skillsRoot
    $backupRoot = Join-Path $harnessRoot 'skill-backups'
    $filter = "$id.bak-*"
    $createdBackup = $null
    $destinationExisted = Test-Path -LiteralPath $Destination
    $backupMoved = $false

    New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
    $legacyBackups = @(Get-ChildItem -LiteralPath $skillsRoot -Directory -Filter $filter -ErrorAction SilentlyContinue)
    if ($legacyBackups.Count -gt 0) {
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        $index = 0
        foreach ($legacy in $legacyBackups) {
            $target = Join-Path $backupRoot $legacy.Name
            while (Test-Path -LiteralPath $target) {
                $index += 1
                $target = Join-Path $backupRoot ($legacy.Name + ".migrated-$ts-$index")
            }
            Move-Item -LiteralPath $legacy.FullName -Destination $target
        }
    }

    try {
        if ($destinationExisted) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $backupCandidate = Join-Path $backupRoot "$id.bak-$ts"
            if (Test-Path -LiteralPath $backupCandidate) {
                $backupCandidate += "." + [guid]::NewGuid().ToString('N')
            }
            Move-Item -LiteralPath $Destination -Destination $backupCandidate
            $createdBackup = $backupCandidate
            $backupMoved = $true
            Write-Host "  备份 $id -> $createdBackup"
        }
        Copy-Item -LiteralPath $source -Destination $Destination -Recurse -Force
        $sourceInfo = Get-SkillTreeInfo $source
        $destinationInfo = Get-SkillTreeInfo $Destination
        if ($sourceInfo.Count -ne $destinationInfo.Count -or $sourceInfo.Digest -ne $destinationInfo.Digest) {
            throw "$id 安装树摘要不一致"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $Destination 'SKILL.md'))) {
            throw "$id 安装缺 SKILL.md"
        }
    }
    catch {
        if ($backupMoved) {
            if (Test-Path -LiteralPath $Destination) {
                Remove-Item -LiteralPath $Destination -Recurse -Force
            }
            if (Test-Path -LiteralPath $createdBackup) {
                Move-Item -LiteralPath $createdBackup -Destination $Destination
            }
        }
        elseif (-not $destinationExisted -and (Test-Path -LiteralPath $Destination)) {
            Remove-Item -LiteralPath $Destination -Recurse -Force
        }
        throw
    }

    if (Test-Path -LiteralPath $backupRoot) {
        $backups = @(
            Get-ChildItem -LiteralPath $backupRoot -Directory -Filter $filter -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTimeUtc, Name -Descending
        )
        $preserve = $createdBackup
        if (-not $preserve -and $backups.Count -gt 0) {
            $preserve = $backups[0].FullName
        }
        foreach ($backup in $backups) {
            if (-not $preserve -or $backup.FullName -ne $preserve) {
                Remove-Item -LiteralPath $backup.FullName -Recurse -Force
            }
        }
    }
}

function Install-SkillsToRoot {
    param([string]$SkillsRoot, [string]$Label)
    foreach ($skill in $skills) {
        $destination = Join-Path $SkillsRoot $skill.Id
        Copy-SkillWithBackup $skill $destination
        Write-Host "  $Label 已更新 -> $destination"
    }
}

if (-not $SkipDeepSeek) {
    Write-Host '[1/3] DeepSeek harness（插件市场）...'
    $args2 = @{ }
    $args2.RepoRoot = $RepoRoot
    if ($MarketplaceRoot) { $args2.MarketplaceRoot = $MarketplaceRoot }
    if ($Version) { $args2.Version = $Version }
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install-deepseek-plugin.ps1') @args2
    if ($LASTEXITCODE -ne 0) { throw "DeepSeek 安装器退出码 $LASTEXITCODE" }
}
else { Write-Host '[1/3] 跳过 DeepSeek。' }

if (-not $SkipClaudeCode) {
    Write-Host '[2/3] Claude Code（用户级技能）...'
    if (-not $ClaudeSkillsRoot) { $ClaudeSkillsRoot = Join-Path $env:USERPROFILE '.claude\skills' }
    Install-SkillsToRoot $ClaudeSkillsRoot 'Claude Code'
}
else { Write-Host '[2/3] 跳过 Claude Code。' }

if (-not $SkipCodex) {
    Write-Host '[3/3] Codex（用户级技能）...'
    if (-not $CodexSkillsRoot) { $CodexSkillsRoot = Join-Path $env:USERPROFILE '.agents\skills' }
    Install-SkillsToRoot $CodexSkillsRoot 'Codex'
}
else { Write-Host '[3/3] 跳过 Codex。' }

if ($ProjectClaude) { Install-SkillsToRoot (Join-Path $RepoRoot '.claude\skills') '项目级 Claude' }
if ($ProjectCodex) { Install-SkillsToRoot (Join-Path $RepoRoot '.agents\skills') '项目级 Codex' }

Write-Host ''
Write-Host '全部完成。Claude Code：/ppt-start、/ppt-editable；Codex：$ppt-start、$ppt-editable；DeepSeek：ppt-start、ppt-editable。'
