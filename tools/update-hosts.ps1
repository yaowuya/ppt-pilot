[CmdletBinding()]
param(
    [string]$MarketplaceRoot = '', [string]$ClaudeSkillsRoot = '', [string]$ClaudeAgentsRoot = '',
    [string]$CodexSkillsRoot = '', [string]$CodexPluginRoot = '', [string[]]$ProjectRoot = @(),
    [string]$RepoRoot = '', [string]$Version = '', [switch]$SkipDeepSeek,
    [switch]$SkipClaudeCode, [switch]$SkipCodex, [switch]$ProjectClaude, [switch]$ProjectCodex,
    [Parameter(DontShow)][switch]$SkipRepoProject
)
$ErrorActionPreference = 'Stop'
$timestamp = (Get-Date).ToString('yyyyMMddHHmmss')
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$reportedVersion = if ($Version) { $Version } else { 'source' }
. (Join-Path $PSScriptRoot 'packaging.ps1')
$skills = @(
    [ordered]@{ Id = 'ppt-start'; Source = Join-Path $RepoRoot 'skills\ppt-start' },
    [ordered]@{ Id = 'ppt-editable'; Source = Join-Path $RepoRoot 'skills\ppt-editable' },
    [ordered]@{ Id = 'ppt-style-extract'; Source = Join-Path $RepoRoot 'skills\ppt-style-extract' }
)
$agentSource = Join-Path $RepoRoot 'hosts\claude-code\agents\ppt-svg-generator.md'
foreach ($skill in $skills) {
    if (-not (Test-Path -LiteralPath (Join-Path $skill.Source 'SKILL.md') -PathType Leaf)) { throw "Incomplete source Skill: $($skill.Source)" }
}
if (-not (Test-Path -LiteralPath $agentSource -PathType Leaf)) { throw "Missing Claude Agent: $agentSource" }
$updated = New-Object Collections.Generic.List[string]
$rolledBack = New-Object Collections.Generic.List[string]
$failed = New-Object Collections.Generic.List[string]

function Invoke-Scope {
    param([string]$Label, [scriptblock]$Action)
    try { & $Action; $updated.Add($Label) }
    catch { $failed.Add("$Label :: $($_.Exception.Message)") }
}
function Install-SkillsRoot {
    param([string]$SkillsRoot, [string]$Label)
    try { Assert-NoShadowingSkills $SkillsRoot }
    catch { [void]$failed.Add("$([IO.Path]::GetFullPath($SkillsRoot)) :: $($_.Exception.Message)"); return $false }
    $backupRoot = Join-Path (Split-Path -Parent $SkillsRoot) 'skill-backups'
    $allSucceeded = $true
    foreach ($skill in $skills) {
        $destination = Join-Path $SkillsRoot $skill.Id
        if ($updated -contains ([IO.Path]::GetFullPath($destination))) { continue }
        try {
            $result = Install-PptPilotTree $skill.Source $destination $backupRoot $skill.Id $timestamp
            [void]$updated.Add($result.Path)
            Write-Host ("installed scope={0} version={1} path={2} files={3} digest={4}" -f $Label, $reportedVersion, $result.Path, $result.Count, $result.Digest)
        }
        catch {
            $allSucceeded = $false
            [void]$failed.Add("$([IO.Path]::GetFullPath($destination)) :: $($_.Exception.Message)")
            if ($_.Exception.Data['PptPilotBackupRestored']) { [void]$rolledBack.Add([IO.Path]::GetFullPath($destination)) }
        }
    }
    return $allSucceeded
}
function Install-ClaudeAgent {
    param([string]$AgentsRoot, [string]$Label)
    $destination = Join-Path $AgentsRoot 'ppt-svg-generator.md'
    $backupRoot = Join-Path (Split-Path -Parent $AgentsRoot) 'agent-backups'
    $backup = $null
    $destinationExisted = Test-Path -LiteralPath $destination
    $backupMoved = $false
    $newCopied = $false
    try {
        New-Item -ItemType Directory -Force -Path $AgentsRoot | Out-Null
        if (Test-Path -LiteralPath $destination) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $backup = Join-Path $backupRoot ("ppt-svg-generator.bak-$timestamp-" + [guid]::NewGuid().ToString('N') + '.md')
            Move-Item -LiteralPath $destination -Destination $backup
            $backupMoved = $true
        }
        $newCopied = $true
        Copy-Item -LiteralPath $agentSource -Destination $destination -Force
        $digest = Get-PptPilotFileSha256 $destination
        if ($digest -ne (Get-PptPilotFileSha256 $agentSource)) { throw 'Agent installed digest mismatch' }
        [void]$updated.Add([IO.Path]::GetFullPath($destination))
        Write-Host ("installed scope={0} version={1} path={2} files=1 digest={3}" -f $Label, $reportedVersion, [IO.Path]::GetFullPath($destination), $digest)
        return $true
    }
    catch {
        if ($newCopied -and (Test-Path -LiteralPath $destination)) { Remove-Item -LiteralPath $destination -Force }
        if ($backupMoved -and (Test-Path -LiteralPath $backup)) { Move-Item -LiteralPath $backup -Destination $destination }
        [void]$failed.Add("$([IO.Path]::GetFullPath($destination)) :: $($_.Exception.Message)")
        if ($destinationExisted -and (Test-Path -LiteralPath $destination)) { [void]$rolledBack.Add([IO.Path]::GetFullPath($destination)) }
        return $false
    }
}

function Install-ClaudePairedScope {
    param([string]$SkillsRoot, [string]$AgentsRoot, [string]$Label)
    try { Assert-NoShadowingSkills $SkillsRoot }
    catch { [void]$failed.Add("$([IO.Path]::GetFullPath($SkillsRoot)) :: $($_.Exception.Message)"); return }
    $snapshot = Join-Path ([IO.Path]::GetTempPath()) ('ppt-claude-scope-' + [guid]::NewGuid().ToString('N'))
    $agentDestination = Join-Path $AgentsRoot 'ppt-svg-generator.md'
    $targets = @([pscustomobject]@{ Path = $agentDestination; Snapshot = Join-Path $snapshot 'agent.md'; IsDirectory = $false })
    foreach ($skill in $skills) {
        $targets += [pscustomobject]@{ Path = Join-Path $SkillsRoot $skill.Id; Snapshot = Join-Path $snapshot $skill.Id; IsDirectory = $true }
    }
    $failedBefore = $failed.Count
    try {
        New-Item -ItemType Directory -Force -Path $snapshot | Out-Null
        foreach ($target in $targets) {
            if (Test-Path -LiteralPath $target.Path) {
                if ($target.IsDirectory) { Copy-Item -LiteralPath $target.Path -Destination $target.Snapshot -Recurse -Force }
                else { Copy-Item -LiteralPath $target.Path -Destination $target.Snapshot -Force }
            }
        }
        if (-not (Install-ClaudeAgent $AgentsRoot "$Label-agent")) { return }
        [void](Install-SkillsRoot $SkillsRoot $Label)
        if ($failed.Count -eq $failedBefore) { return }
        foreach ($target in $targets) {
            $full = [IO.Path]::GetFullPath($target.Path)
            if (Test-Path -LiteralPath $target.Path) { Remove-Item -LiteralPath $target.Path -Recurse -Force }
            if (Test-Path -LiteralPath $target.Snapshot) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target.Path) | Out-Null
                Copy-Item -LiteralPath $target.Snapshot -Destination $target.Path -Recurse:$target.IsDirectory -Force
                if (-not $rolledBack.Contains($full)) { [void]$rolledBack.Add($full) }
            }
            [void]$updated.Remove($full)
        }
    }
    finally { if (Test-Path -LiteralPath $snapshot) { Remove-Item -LiteralPath $snapshot -Recurse -Force } }
}

if (-not $SkipDeepSeek) {
    Invoke-Scope 'deepseek-plugin' {
        $arguments = @{ RepoRoot = $RepoRoot }
        # This updater owns shared roots, including SkipCodex and explicit-root selection.
        $arguments.SkipSharedSkills = $true
        if ($MarketplaceRoot) { $arguments.MarketplaceRoot = $MarketplaceRoot }
        if ($Version) { $arguments.Version = $Version }
        & (Join-Path $PSScriptRoot 'install-deepseek-plugin.ps1') @arguments
        if ($LASTEXITCODE -ne 0) { throw "DeepSeek installer exit $LASTEXITCODE" }
    }
}
if (-not $SkipClaudeCode) {
    if (-not $ClaudeSkillsRoot) { $ClaudeSkillsRoot = Join-Path $env:USERPROFILE '.claude\skills' }
    if (-not $ClaudeAgentsRoot) { $ClaudeAgentsRoot = Join-Path (Split-Path -Parent $ClaudeSkillsRoot) 'agents' }
    try { Install-ClaudePairedScope $ClaudeSkillsRoot $ClaudeAgentsRoot 'claude-user' }
    catch { [void]$failed.Add("$([IO.Path]::GetFullPath($ClaudeSkillsRoot)) :: $($_.Exception.Message)") }
}
if (-not $SkipCodex) {
    if (-not $CodexSkillsRoot) { $CodexSkillsRoot = Join-Path $env:USERPROFILE '.agents\skills' }
    [void](Install-SkillsRoot $CodexSkillsRoot 'codex-user')
}
if ($CodexPluginRoot) { [void](Install-SkillsRoot (Join-Path $CodexPluginRoot 'skills') 'codex-plugin') }

$projects = New-Object Collections.Generic.List[string]
$repoFull = [IO.Path]::GetFullPath($RepoRoot)
if (-not $SkipRepoProject) { $projects.Add($repoFull) }
foreach ($projectValue in $ProjectRoot) {
    $full = [IO.Path]::GetFullPath($projectValue)
    if (-not $projects.Contains($full)) { $projects.Add($full) }
}
foreach ($project in $projects) {
    try {
        if (-not (Test-Path -LiteralPath $project -PathType Container)) { throw "selected project root is not a directory: $project" }
        $claudeSkills = Join-Path $project '.claude\skills'; $codexSkills = Join-Path $project '.agents\skills'
        $refreshClaude = (Test-Path -LiteralPath $claudeSkills -PathType Container) -or ($project -eq $repoFull -and $ProjectClaude)
        $refreshCodex = (Test-Path -LiteralPath $codexSkills -PathType Container) -or ($project -eq $repoFull -and $ProjectCodex)
        if ($refreshClaude) { Install-ClaudePairedScope $claudeSkills (Join-Path $project '.claude\agents') 'claude-project' }
        if ($refreshCodex) { [void](Install-SkillsRoot $codexSkills 'codex-project') }
        if (-not $refreshClaude -and -not $refreshCodex) { Write-Host "skipped project=$project reason=no-existing-discovery-scope" }
    }
    catch { $failed.Add("project:$project :: $($_.Exception.Message)") }
}
if ($failed.Count -gt 0) {
    Write-Host 'PARTIAL_FAILURE'; Write-Host ('updated: ' + ($updated -join '; '))
    Write-Host ('rolled_back: ' + ($rolledBack -join '; ')); Write-Host ('failed: ' + ($failed -join '; ')); exit 2
}
Write-Host ('SUCCESS updated: ' + ($updated -join '; ')); Write-Host 'New session required after Skill or Agent replacement.'; exit 0
