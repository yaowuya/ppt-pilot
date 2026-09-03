<#
.SYNOPSIS
把 ppt-start 与 ppt-editable 安装为一个 DeepSeek harness 本地插件。
.DESCRIPTION
保留单一 ppt-pilot 插件/市场条目；两个 Skill 安装到 plugin\skills，per-ID 备份位于扫描根外的 plugin\backups。
#>
[CmdletBinding()]
param(
    [string]$MarketplaceRoot = '',
    [string]$RepoRoot = '',
    [string]$Version = ''
)

$ErrorActionPreference = 'Stop'
$utf8NoBom = New-Object Text.UTF8Encoding($false)
$timestamp = (Get-Date).ToString('yyyyMMddHHmmss')
if (-not $RepoRoot) {
    if ($PSScriptRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
    else { $RepoRoot = (Get-Location).Path }
}
if (-not $MarketplaceRoot) { $MarketplaceRoot = Join-Path $env:USERPROFILE '.agents\plugins' }
if (-not $Version) { $Version = "1.0.0+codex.$timestamp" }

$skills = @(
    [ordered]@{ Id = 'ppt-start'; Source = Join-Path $RepoRoot 'skills\ppt-start' },
    [ordered]@{ Id = 'ppt-editable'; Source = Join-Path $RepoRoot 'skills\ppt-editable' },
    [ordered]@{ Id = 'ppt-style-extract'; Source = Join-Path $RepoRoot 'skills\ppt-style-extract' }
)
foreach ($skill in $skills) {
    if (-not (Test-Path -LiteralPath (Join-Path $skill.Source 'SKILL.md'))) {
        throw "源 Skill 不完整：$($skill.Source)"
    }
}

function Get-SkillTreeInfo {
    param([string]$Root)
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $files = @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force | Sort-Object FullName)
    $stream = New-Object IO.MemoryStream
    $encoding = New-Object Text.UTF8Encoding($false)
    try {
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($rootPath.Length).TrimStart('\', '/').Replace('\', '/')
            $contentHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
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

function Copy-PluginSkill {
    param([System.Collections.IDictionary]$Descriptor, [string]$SkillsRoot, [string]$BackupRoot)
    $id = [string]$Descriptor.Id
    $source = [string]$Descriptor.Source
    $destination = Join-Path $SkillsRoot $id
    $filter = "$id.bak-*"
    $createdBackup = $null
    $destinationExisted = Test-Path -LiteralPath $destination
    $backupMoved = $false

    New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null
    $legacy = @(Get-ChildItem -LiteralPath $SkillsRoot -Directory -Filter $filter -ErrorAction SilentlyContinue)
    if ($legacy.Count -gt 0) {
        New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
        $index = 0
        foreach ($item in $legacy) {
            $target = Join-Path $BackupRoot $item.Name
            while (Test-Path -LiteralPath $target) {
                $index += 1
                $target = Join-Path $BackupRoot ($item.Name + ".migrated-$timestamp-$index")
            }
            Move-Item -LiteralPath $item.FullName -Destination $target
        }
    }

    try {
        if ($destinationExisted) {
            New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
            $backupCandidate = Join-Path $BackupRoot "$id.bak-$timestamp"
            if (Test-Path -LiteralPath $backupCandidate) {
                $backupCandidate += "." + [guid]::NewGuid().ToString('N')
            }
            Move-Item -LiteralPath $destination -Destination $backupCandidate
            $createdBackup = $backupCandidate
            $backupMoved = $true
        }
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
        $sourceInfo = Get-SkillTreeInfo $source
        $destinationInfo = Get-SkillTreeInfo $destination
        if ($sourceInfo.Count -ne $destinationInfo.Count -or $sourceInfo.Digest -ne $destinationInfo.Digest) {
            throw "$id 插件安装树摘要不一致"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $destination 'SKILL.md'))) {
            throw "$id 插件安装缺 SKILL.md"
        }
    }
    catch {
        if ($backupMoved) {
            if (Test-Path -LiteralPath $destination) {
                Remove-Item -LiteralPath $destination -Recurse -Force
            }
            if (Test-Path -LiteralPath $createdBackup) {
                Move-Item -LiteralPath $createdBackup -Destination $destination
            }
        }
        elseif (-not $destinationExisted -and (Test-Path -LiteralPath $destination)) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        throw
    }

    if (Test-Path -LiteralPath $BackupRoot) {
        $backups = @(
            Get-ChildItem -LiteralPath $BackupRoot -Directory -Filter $filter -ErrorAction SilentlyContinue |
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

$pluginDir = Join-Path $MarketplaceRoot 'plugins\ppt-pilot'
$skillsRoot = Join-Path $pluginDir 'skills'
$backupRoot = Join-Path $pluginDir 'backups'
$marketplacePath = Join-Path $MarketplaceRoot 'marketplace.json'
$transactionRoot = Join-Path $MarketplaceRoot ('.install-transactions\ppt-pilot-' + $timestamp + '-' + [guid]::NewGuid().ToString('N'))
$pluginSnapshot = Join-Path $transactionRoot 'plugin'
$marketplaceSnapshot = Join-Path $transactionRoot 'marketplace.json'
$pluginExisted = Test-Path -LiteralPath $pluginDir
$marketplaceExisted = Test-Path -LiteralPath $marketplacePath
$marketplaceAttemptBackup = $null
New-Item -ItemType Directory -Force -Path $transactionRoot | Out-Null
if ($pluginExisted) { Copy-Item -LiteralPath $pluginDir -Destination $pluginSnapshot -Recurse -Force }
if ($marketplaceExisted) { Copy-Item -LiteralPath $marketplacePath -Destination $marketplaceSnapshot -Force }

try {
    New-Item -ItemType Directory -Force -Path (Join-Path $pluginDir '.codex-plugin') | Out-Null
    New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
    foreach ($skill in $skills) { Copy-PluginSkill $skill $skillsRoot $backupRoot }

$manifest = [ordered]@{
    name        = 'ppt-pilot'
    version     = $Version
    description = 'PPT Pilot：独立 SVG 演示生成与原生可编辑 PowerPoint 交付'
    author      = [ordered]@{ name = 'ppt-pilot' }
    skills      = './skills/'
    interface   = [ordered]@{
        displayName       = 'PPT Pilot'
        shortDescription  = '演示文稿生成与可编辑交付'
        longDescription   = 'ppt-start 生成证据支撑的独立 SVG 演示；ppt-editable 将完成运行转换为带递归分组、可编辑文本和验证证据的 PowerPoint。'
        developerName     = 'ppt-pilot'
        category          = 'Productivity'
        capabilities      = @('Interactive', 'Write')
        defaultPrompt     = @(
            'ppt-start：根据 inputs/ 制作中文策略演示文稿',
            'ppt-start：恢复既有运行并继续生成 SVG',
            'ppt-editable：把完成的 PPT Pilot 运行转换为原生可编辑 PowerPoint'
        )
        brandColor        = '#156BFF'
    }
}
$pluginJsonPath = Join-Path $pluginDir '.codex-plugin\plugin.json'
[IO.File]::WriteAllText($pluginJsonPath, ($manifest | ConvertTo-Json -Depth 8), $utf8NoBom)

$marketplaceEntry = [pscustomobject]@{
    name = 'ppt-pilot'
    source = [ordered]@{ source = 'local'; path = './plugins/ppt-pilot' }
    policy = [ordered]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
    category = 'Productivity'
}
if (Test-Path -LiteralPath $marketplacePath) {
    $backup = "$marketplacePath.bak-$timestamp"
    if (Test-Path -LiteralPath $backup) {
        $backup += "." + [guid]::NewGuid().ToString('N')
    }
    $marketplaceAttemptBackup = $backup
    Copy-Item -LiteralPath $marketplacePath -Destination $backup
    $originalMarketText = Get-Content -LiteralPath $marketplacePath -Raw -Encoding UTF8
    $market = $originalMarketText | ConvertFrom-Json
    if (-not $market.PSObject.Properties['plugins']) {
        throw "marketplace.json 缺 plugins：$marketplacePath"
    }
    $others = @($market.plugins | Where-Object { $_.name -ne 'ppt-pilot' })
    $market.plugins = @($others) + @($marketplaceEntry)
    $normalizedMarketText = $market | ConvertTo-Json -Depth 8
    if ($normalizedMarketText -eq $originalMarketText) {
        Remove-Item -LiteralPath $backup -Force
    }
    else {
        [IO.File]::WriteAllText($marketplacePath, $normalizedMarketText, $utf8NoBom)
    }
}
else {
    $market = [ordered]@{
        name = 'personal'
        interface = [ordered]@{ displayName = 'Personal' }
        plugins = @($marketplaceEntry)
    }
    New-Item -ItemType Directory -Force -Path $MarketplaceRoot | Out-Null
    [IO.File]::WriteAllText($marketplacePath, ($market | ConvertTo-Json -Depth 8), $utf8NoBom)
}

foreach ($skill in $skills) {
    if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $skillsRoot $skill.Id) 'SKILL.md'))) {
        throw "安装校验失败：$($skill.Id)"
    }
}
if (-not (Test-Path -LiteralPath $pluginJsonPath) -or -not (Test-Path -LiteralPath $marketplacePath)) {
    throw '插件清单校验失败'
}
}
catch {
    $failure = $_
    if (Test-Path -LiteralPath $pluginDir) {
        Remove-Item -LiteralPath $pluginDir -Recurse -Force
    }
    if ($pluginExisted) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pluginDir) | Out-Null
        Copy-Item -LiteralPath $pluginSnapshot -Destination $pluginDir -Recurse -Force
    }
    if ($marketplaceExisted) {
        Copy-Item -LiteralPath $marketplaceSnapshot -Destination $marketplacePath -Force
    }
    elseif (Test-Path -LiteralPath $marketplacePath) {
        Remove-Item -LiteralPath $marketplacePath -Force
    }
    if ($marketplaceAttemptBackup -and (Test-Path -LiteralPath $marketplaceAttemptBackup)) {
        Remove-Item -LiteralPath $marketplaceAttemptBackup -Force
    }
    throw $failure
}
finally {
    if (Test-Path -LiteralPath $transactionRoot) {
        Remove-Item -LiteralPath $transactionRoot -Recurse -Force
    }
}

Write-Host "安装完成：$pluginDir"
Write-Host "版本：$Version"
Write-Host 'DeepSeek 启动词：ppt-start；ppt-editable：转换完成运行为可编辑 PowerPoint。'
exit 0
