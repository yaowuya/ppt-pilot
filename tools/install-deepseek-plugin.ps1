<#
.SYNOPSIS
把当前仓库的 ppt-start Skill 安装为 DeepSeek harness 的本地插件。

.DESCRIPTION
可选伴随工具（不属于安装后的 Skill）。它按本机 harness 的插件约定执行：

1. 目标：$HOME\.agents\plugins\plugins\ppt-pilot\
2. 复制 skills\ppt-start -> <target>\skills\ppt-start（SKILL.md + references/ + assets/ 完整拷贝）
3. 写入 .codex-plugin\plugin.json（版本 1.0.0+codex.<时间戳>，或用 -Version 覆盖）
4. 校正 marketplace.json：缺少 ppt-pilot 条目时自动追加（已有则不动），原文件先备份

幂等：可重复运行升级；每次覆盖前把上一版备份为 *.bak-<时间戳>（仅保留最近一份）。

.PARAMETER MarketplaceRoot
harness 插件市场根目录，默认 $HOME\.agents\plugins。

.PARAMETER RepoRoot
仓库根目录，默认脚本上一级。

.PARAMETER Version
插件版本号，默认自动生成 1.0.0+codex.<yyyyMMddHHmmss>。

.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\install-deepseek-plugin.ps1
powershell -ExecutionPolicy Bypass -File tools\install-deepseek-plugin.ps1 -Version 1.0.0
#>
[CmdletBinding()]
param(
    [string]$MarketplaceRoot = '',
    [string]$RepoRoot = '',
    [string]$Version = ''
)

$ErrorActionPreference = 'Stop'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$timestamp = (Get-Date).ToString('yyyyMMddHHmmss')

if (-not $RepoRoot) {
    if ($PSScriptRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot } else { $RepoRoot = (Get-Location).Path }
}
if (-not $MarketplaceRoot) { $MarketplaceRoot = Join-Path $env:USERPROFILE '.agents\plugins' }
if (-not $Version) { $Version = "1.0.0+codex.$timestamp" }

$packSrc = Join-Path $RepoRoot 'skills\ppt-start'
if (-not (Test-Path (Join-Path $packSrc 'SKILL.md'))) { throw "源 Skill 不完整，缺 SKILL.md：$packSrc" }

$pluginDir = Join-Path $MarketplaceRoot 'plugins\ppt-pilot'
$skillDst = Join-Path $pluginDir 'skills\ppt-start'

# --- 1. 目录 ---
New-Item -ItemType Directory -Force -Path (Join-Path $pluginDir '.codex-plugin') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $pluginDir 'skills') | Out-Null

# --- 2. 复制 Skill（旧版备份）---
if (Test-Path $skillDst) {
    $bak = "$skillDst.bak-$timestamp"
    Move-Item -LiteralPath $skillDst -Destination $bak
    Get-ChildItem -Path (Join-Path $pluginDir 'skills') -Directory -Filter 'ppt-start.bak-*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -Skip 1 |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
    Write-Host "已备份旧版 -> $(Split-Path -Leaf $bak)"
}
Copy-Item -Recurse -Force $packSrc $skillDst

# --- 3. plugin.json ---
$manifest = [ordered]@{
    name        = 'ppt-pilot'
    version     = $Version
    description = '可移植纯指令演示文稿 Skill：证据支撑的 16:9 多页 PPT，交付独立 SVG'
    author      = [ordered]@{ name = 'ppt-pilot' }
    skills      = './skills/'
    interface   = [ordered]@{
        displayName       = 'PPT Pilot'
        shortDescription  = '证据支撑的多页演示文稿生成'
        longDescription   = '通过工作区持久产物开发结论先行的演示文稿：简报、研究、大纲、故事板、独立文稿审查硬质量门、主题与逐页 visual brief、Office-safe SVG 生产与整套 QA；支持新建、恢复与修订入口，跨宿主可交接。'
        developerName     = 'ppt-pilot'
        category          = 'Productivity'
        capabilities      = @('Interactive', 'Write')
        defaultPrompt     = @(
            'ppt-start：根据 inputs/ 中的资料制作一份 10 页中文策略演示文稿',
            'ppt-start：从 ppt-output/ 中的既有运行恢复并继续生成 SVG',
            'ppt-start：对当前运行的指定页面做单页修订'
        )
        brandColor        = '#156BFF'
    }
}
$pluginJsonPath = Join-Path $pluginDir '.codex-plugin\plugin.json'
[System.IO.File]::WriteAllText($pluginJsonPath, ($manifest | ConvertTo-Json -Depth 6), $utf8NoBom)

# --- 4. marketplace.json 校正 ---
$marketplacePath = Join-Path $MarketplaceRoot 'marketplace.json'
if (Test-Path $marketplacePath) {
    $backup = "$marketplacePath.bak-$timestamp"
    Copy-Item -LiteralPath $marketplacePath -Destination $backup
    $market = Get-Content -LiteralPath $marketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $market.plugins) { throw "marketplace.json 缺少 plugins 数组：$marketplacePath" }
    $existing = @($market.plugins | Where-Object { $_.name -eq 'ppt-pilot' })
    if ($existing.Count -eq 0) {
        $entry = [pscustomobject]@{
            name   = 'ppt-pilot'
            source = [ordered]@{ source = 'local'; path = './plugins/ppt-pilot' }
            policy = [ordered]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
            category = 'Productivity'
        }
        $list = @($market.plugins) + @($entry)
        $market.plugins = $list
        [System.IO.File]::WriteAllText($marketplacePath, ($market | ConvertTo-Json -Depth 6), $utf8NoBom)
        Write-Host "已在 marketplace.json 追加 ppt-pilot 条目（备份：$(Split-Path -Leaf $backup)）"
    } else {
        Remove-Item -LiteralPath $backup -Force
        Write-Host 'marketplace.json 已含 ppt-pilot 条目，无需修改。'
    }
} else {
    $market = [ordered]@{
        name = 'personal'
        interface = [ordered]@{ displayName = 'Personal' }
        plugins = @([pscustomobject]@{
            name   = 'ppt-pilot'
            source = [ordered]@{ source = 'local'; path = './plugins/ppt-pilot' }
            policy = [ordered]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
            category = 'Productivity'
        })
    }
    [System.IO.File]::WriteAllText($marketplacePath, ($market | ConvertTo-Json -Depth 6), $utf8NoBom)
    Write-Host 'marketplace.json 不存在，已创建并写入 ppt-pilot 条目。'
}

# --- 5. 校验 ---
$checks = @(
    (Join-Path $skillDst 'SKILL.md'),
    (Join-Path $skillDst 'references\workflow.md'),
    (Join-Path $skillDst 'assets\styles\registry.json'),
    $pluginJsonPath,
    $marketplacePath
)
foreach ($c in $checks) {
    if (-not (Test-Path $c)) { throw "安装校验失败，缺文件：$c" }
}
Write-Host ''
Write-Host "安装完成：$pluginDir"
Write-Host "版本：$Version"
Write-Host '在 DeepSeek harness 中使用启动词 ppt-start 发起请求即可。'
exit 0
