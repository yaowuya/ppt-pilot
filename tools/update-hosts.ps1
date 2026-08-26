<#
.SYNOPSIS
一条命令把当前仓库的 ppt-start Skill 更新到本机三个宿主：
DeepSeek harness（.agents 插件市场）、Claude Code（用户级技能目录）与 Codex（用户级技能目录）。

.DESCRIPTION
可选伴随工具。DeepSeek 侧复用 install-deepseek-plugin.ps1 的插件约定；
Claude Code 侧复制到 $HOME\.claude\skills\ppt-start\（旧版备份为 *.bak-<时间戳>，
仅保留最近一份）。Codex 侧复制到 $HOME\.agents\skills\ppt-start\。-ProjectClaude 额外写入 <RepoRoot>\.claude\skills\。

.PARAMETER SkipDeepSeek
跳过 DeepSeek 插件更新。
.PARAMETER SkipClaudeCode
跳过 Claude Code 用户级更新。
.PARAMETER SkipCodex
跳过 Codex 用户级更新。
.PARAMETER ProjectClaude
额外更新仓库内 .claude\skills\ppt-start（项目级）。
.PARAMETER ProjectCodex
额外更新仓库内 .agents\skills\ppt-start（项目级）。
.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\update-hosts.ps1 -ProjectClaude
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
if (-not $RepoRoot) { if ($PSScriptRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot } else { $RepoRoot = (Get-Location).Path } }
$packSrc = Join-Path $RepoRoot 'skills\ppt-start'
if (-not (Test-Path (Join-Path $packSrc 'SKILL.md'))) { throw "源 Skill 缺 SKILL.md：$packSrc" }

function Copy-SkillWithBackup([string]$dst) {
    if (Test-Path $dst) {
        $bak = "$dst.bak-$ts"
        Move-Item -LiteralPath $dst -Destination $bak
        Get-ChildItem -Path (Split-Path -Parent $dst) -Directory -Filter '*.bak-*' -ErrorAction SilentlyContinue |
            Where-Object Name -like 'ppt-start.bak-*' | Sort-Object Name -Descending | Select-Object -Skip 1 |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
        Write-Host "  备份旧版 -> $(Split-Path -Leaf $bak)"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -Recurse -Force $packSrc $dst
}

if (-not $SkipDeepSeek) {
    Write-Host '[1/3] DeepSeek harness（插件市场）...'
    $args2 = @{ }
    if ($MarketplaceRoot) { $args2.MarketplaceRoot = $MarketplaceRoot }
    if ($Version) { $args2.Version = $Version }
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install-deepseek-plugin.ps1') @args2
    if ($LASTEXITCODE -ne 0) { throw "DeepSeek 安装器退出码 $LASTEXITCODE" }
} else { Write-Host '[1/3] 跳过 DeepSeek。' }

if (-not $SkipClaudeCode) {
    Write-Host '[3/3] Claude Code（用户级技能）...'
    if (-not $ClaudeSkillsRoot) { $ClaudeSkillsRoot = Join-Path $env:USERPROFILE '.claude\skills' }
    Copy-SkillWithBackup (Join-Path $ClaudeSkillsRoot 'ppt-start')
    $check = Get-Content (Join-Path $ClaudeSkillsRoot 'ppt-start\SKILL.md') -Raw -Encoding UTF8
    if (-not $check) { throw 'Claude Code 安装校验失败' }
    Write-Host "  已更新 -> $ClaudeSkillsRoot\ppt-start"
} else { Write-Host '[3/3] 跳过 Claude Code。' }

if (-not $SkipCodex) {
    Write-Host '[3/3] Codex（用户级技能）...'
    if (-not $CodexSkillsRoot) { $CodexSkillsRoot = Join-Path $env:USERPROFILE '.agents\skills' }
    Copy-SkillWithBackup (Join-Path $CodexSkillsRoot 'ppt-start')
    $check = Get-Content (Join-Path $CodexSkillsRoot 'ppt-start\SKILL.md') -Raw -Encoding UTF8
    if (-not $check) { throw 'Codex 安装校验失败' }
    Write-Host "  已更新 -> $CodexSkillsRoot\ppt-start"
} else { Write-Host '[3/3] 跳过 Codex。' }

if ($ProjectClaude) {
    $pd = Join-Path $RepoRoot '.claude\skills\ppt-start'
    Copy-SkillWithBackup $pd
    Write-Host "  项目级已更新 -> $pd"
}

if ($ProjectCodex) {
    $px = Join-Path $RepoRoot '.agents\skills\ppt-start'
    Copy-SkillWithBackup $px
    Write-Host "  项目级已更新 -> $px"
}

Write-Host ''
Write-Host '全部完成。Claude Code 使用 /ppt-start；Codex 使用 $ppt-start；DeepSeek harness 使用启动词 ppt-start。'
