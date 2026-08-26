<#
.SYNOPSIS
PPT Pilot 可选伴随工具：把一次运行的 slides/*.svg 组装为可交付成果。

.DESCRIPTION
属于仓库工具，不属于安装后的 Skill（skills/ppt-start/ 保持纯指令）。功能：

1. 始终生成 preview.html 联系表（缩略图网格 + 单页查看器，纯静态、无外部资源）；
2. 从 故事板.md（旧运行 storyboard.md）解析每页 assertion_title / audience_takeaway /
   next_link，自动写入 PPTX 演讲者备注；
3. 调用本机 Microsoft PowerPoint（COM 自动化）把每页 SVG 插入 16:9 PPTX；
4. -ExportPng 时用 PowerPoint 导出每页 PNG，作为渲染证据。

不修改任何 Skill 运行产物；只新增 preview.html 与 delivery/ 目录。

.PARAMETER RunDir
运行目录（含 run.json 与 slides/）。缺省时自动探测 ppt-output/ 下唯一含 run.json 的运行。

.PARAMETER SkipPptx
跳过 PPTX 组装，只生成 preview.html。

.PARAMETER ExportPng
额外导出每页 1280x720 PNG 到 delivery/png/。

.EXAMPLE
powershell -File tools\deck-deliver.ps1
powershell -File tools\deck-deliver.ps1 -RunDir ppt-output\fy26-h1-midyear-review -ExportPng

.NOTES
退出码：0 = PPTX+preview 成功；3 = 仅 preview 成功（PowerPoint 不可用或 -SkipPptx）；
致命失败（如运行目录无效、没有 SVG）以异常终止（非零退出码）。
#>
[CmdletBinding()]
param(
    [string]$RunDir = '',
    [string]$WorkspaceRoot = '',
    [switch]$SkipPptx,
    [switch]$ExportPng,
    [string]$PowerPointExe = ''
)

$ErrorActionPreference = 'Stop'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8File {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
}

function ConvertTo-HtmlText {
    param([string]$Value)
    if (-not $Value) { return '' }
    return $Value.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;')
}

function Get-StoryboardNotes {
    param([string]$RunPath, [string]$SlideId)
    foreach ($name in @('.ppt-pilot\故事板.md')) {
        $path = Join-Path $RunPath $name
        if (Test-Path $path) { return @{ raw = (Get-Content -LiteralPath $path -Raw -Encoding UTF8); file = $name } }
    }
    return $null
}

function Split-StoryboardSections {
    param([string]$Raw)
    $result = @{}
    $regex = '(?ms)^##\s*(?<id>S\d+)\s*\r?\n(?<body>.*?)(?=^##\s*S\d+\s*\r?\n|\z)'
    foreach ($match in [regex]::Matches($Raw, $regex)) {
        $body = $match.Groups['body'].Value
        $title = ''
        $takeaway = ''
        $nextLink = ''
        $t = [regex]::Match($body, '(?m)^\s*-\s*\*\*assertion_title\*\*\s*[：:]\s*(?<v>.+?)\s*$')
        if ($t.Success) { $title = $t.Groups['v'].Value }
        $a = [regex]::Match($body, '(?m)^\s*-\s*\*\*audience_takeaway\*\*\s*[：:]\s*(?<v>.+?)\s*$')
        if ($a.Success) { $takeaway = $a.Groups['v'].Value }
        $n = [regex]::Match($body, '(?m)^\s*-\s*\*\*next_link\*\*\s*[：:]\s*(?<v>.+?)\s*$')
        if ($n.Success) { $nextLink = $n.Groups['v'].Value }
        $result[$match.Groups['id'].Value] = @{
            title    = $title
            takeaway = $takeaway
            nextLink = $nextLink
        }
    }
    return $result
}

function Find-PowerPointExe {
    param([string]$Explicit)
    if ($Explicit) { if (Test-Path $Explicit) { return (Resolve-Path $Explicit).Path } return $null }
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Microsoft Office\root\Office16\POWERPNT.EXE'),
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Office\root\Office16\POWERPNT.EXE')
    )
    $glob = Get-ChildItem -Path (Join-Path $env:ProgramFiles 'Microsoft Office\root\Office*\POWERPNT.EXE') -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($glob) { $candidates += $glob.FullName }
    $command = Get-Command POWERPNT.EXE -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return (Resolve-Path $candidate).Path }
    }
    return $null
}

# ---------------------------------------------------------------------------
# 1. 解析运行目录
# ---------------------------------------------------------------------------
if (-not $WorkspaceRoot) {
    if ($PSScriptRoot) { $WorkspaceRoot = Split-Path -Parent $PSScriptRoot } else { $WorkspaceRoot = (Get-Location).Path }
}
$pptOutput = Join-Path $WorkspaceRoot 'ppt-output'

if ($RunDir) {
    if (-not (Test-Path $RunDir)) { throw "RunDir 不存在：$RunDir" }
    $runPath = (Resolve-Path $RunDir).Path
} else {
    if (-not (Test-Path $pptOutput)) { throw "未找到 ppt-output 目录：$pptOutput" }
    $candidates = @(Get-ChildItem -LiteralPath $pptOutput -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'run.json') })
    if ($candidates.Count -eq 1) {
        $runPath = $candidates[0].FullName
    } elseif ($candidates.Count -eq 0) {
        throw "ppt-output 下没有含 run.json 的运行目录，请用 -RunDir 指定。"
    } else {
        $names = ($candidates | ForEach-Object { $_.Name }) -join ', '
        throw "存在多个候选运行（$names），请用 -RunDir 指定其一。"
    }
}

$runJsonPath = Join-Path $runPath '.ppt-pilot\run.json'
$run = Get-Content -LiteralPath $runJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$deckId = if ($run.deck_id) { [string]$run.deck_id } else { Split-Path -Leaf $runPath }
$stage = if ($run.stage) { [string]$run.stage } else { 'unknown' }

$slidesDir = Join-Path $runPath 'slides'
$slideFiles = @(Get-ChildItem -LiteralPath $slidesDir -Filter '*.svg' -File -ErrorAction SilentlyContinue |
    Sort-Object { if ($_.BaseName -match '(\d+)') { [int]$Matches[1] } else { [int]::MaxValue } }, Name)
if ($slideFiles.Count -eq 0) { throw "运行目录没有 SVG 页面：$slidesDir" }

$warnings = @()
if ($stage -ne 'complete') { $warnings += "run.json.stage 为 $stage（非 complete），交付前请确认质量门已通过。" }

# ---------------------------------------------------------------------------
# 2. 解析故事板备注
# ---------------------------------------------------------------------------
$storyboard = Get-StoryboardNotes -RunPath $runPath
$sections = @{}
if ($storyboard) { $sections = Split-StoryboardSections -Raw $storyboard.raw } else { $warnings += '未找到 .ppt-pilot/故事板.md，演讲者备注将为空。' }

$slideInfos = @()
foreach ($file in $slideFiles) {
    $id = $file.BaseName
    $sec = $sections[$id]
    $title = ''; $takeaway = ''; $nextLink = ''
    if ($sec) {
        $title = $sec.title; $takeaway = $sec.takeaway; $nextLink = $sec.nextLink
    } else {
        $warnings += "$id 在故事板中无对应小节，该页备注为空。"
    }
    $slideInfos += @{
        id       = $id
        path     = $file.FullName
        relPath  = "slides/$($file.Name)"
        title    = $title
        takeaway = $takeaway
        nextLink = $nextLink
    }
}

# ---------------------------------------------------------------------------
# 3. preview.html 联系表
# ---------------------------------------------------------------------------
$deliveryDir = Join-Path $runPath 'delivery'
New-Item -ItemType Directory -Force -Path $deliveryDir | Out-Null
$previewPath = Join-Path $runPath 'preview.html'

$cardParts = New-Object System.Collections.Generic.List[string]
$index = 0
foreach ($info in $slideInfos) {
    $caption = $info.title
    if (-not $caption) { $caption = $info.id }
    $safeCaption = ConvertTo-HtmlText $caption
    $cardParts.Add(('      <figure class="card" data-index="{0}" data-src="{1}" title="点击放大">' -f $index, (ConvertTo-HtmlText $info.relPath)) + "`n" +
        ('        <img loading="lazy" src="{0}" alt="{1} 缩略图">' -f (ConvertTo-HtmlText $info.relPath), (ConvertTo-HtmlText $info.id)) + "`n" +
        ('        <figcaption><span class="sid">{0}</span> {1}</figcaption>' -f (ConvertTo-HtmlText $info.id), $safeCaption) + "`n" +
        '      </figure>')
    $index++
}

$slidesJson = @($slideInfos | ForEach-Object { @{ id = $_.id; src = $_.relPath; title = $_.title } }) | ConvertTo-Json -Compress
$warningsHtml = ''
if ($warnings.Count -gt 0) {
    $items = ($warnings | ForEach-Object { '        <li>' + (ConvertTo-HtmlText $_) + '</li>' }) -join "`n"
    $warningsHtml = "    <div class=`"warnings`"><strong>提示</strong><ul>`n$items`n    </ul></div>"
}
$generatedAt = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

$htmlTemplate = @'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__DECK_ID__｜PPT Pilot 预览</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif; background: #f2f4f8; color: #0f172a; }
  header { padding: 20px 28px; background: #ffffff; border-bottom: 1px solid #d7dee8; position: sticky; top: 0; z-index: 5; }
  header h1 { margin: 0 0 4px; font-size: 20px; }
  header .meta { font-size: 13px; color: #475467; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; background: #e7f0ff; color: #156bff; margin-left: 8px; }
  .badge.warn { background: #fff2d9; color: #9a6a00; }
  .warnings { margin: 16px 28px 0; padding: 12px 16px; background: #fff8e6; border: 1px solid #f0d48a; border-radius: 8px; font-size: 13px; }
  .warnings ul { margin: 6px 0 0; padding-left: 18px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; padding: 22px 28px 48px; }
  .card { margin: 0; background: #ffffff; border: 1px solid #d7dee8; border-radius: 10px; overflow: hidden; cursor: zoom-in; transition: box-shadow .15s ease, transform .15s ease; }
  .card:hover { box-shadow: 0 6px 18px rgba(15,23,42,.12); transform: translateY(-2px); }
  .card img { width: 100%; display: block; background: #ffffff; }
  .card figcaption { padding: 8px 12px; font-size: 13px; color: #344054; border-top: 1px solid #e7ecf3; }
  .card .sid { font-weight: 700; color: #156bff; margin-right: 6px; }
  #viewer { position: fixed; inset: 0; background: rgba(15,23,42,.82); display: none; align-items: center; justify-content: center; flex-direction: column; z-index: 50; }
  #viewer.open { display: flex; }
  #viewer img { max-width: 94vw; max-height: 84vh; background: #ffffff; box-shadow: 0 12px 40px rgba(0,0,0,.45); border-radius: 4px; }
  #viewer .bar { margin-top: 14px; color: #e7ecf3; font-size: 14px; display: flex; gap: 14px; align-items: center; }
  #viewer button { background: #156bff; border: 0; color: #fff; padding: 8px 18px; border-radius: 8px; font-size: 14px; cursor: pointer; }
  #viewer button.secondary { background: rgba(255,255,255,.18); }
  #viewer button:hover { filter: brightness(1.08); }
</style>
</head>
<body>
<header>
  <h1>__DECK_ID__<span class="badge">stage: __STAGE__</span></h1>
  <div class="meta">__COUNT__ 页 · 生成于 __GENERATED_AT__ · 由 tools/deck-deliver.ps1 生成 · 方向键翻页，Esc 关闭</div>
</header>
__WARNINGS__
<main class="grid" id="grid">
__CARDS__
</main>
<div id="viewer">
  <img id="viewer-img" src="" alt="页面预览">
  <div class="bar">
    <button id="prev">← 上一页</button>
    <span id="viewer-caption"></span>
    <button id="next">下一页 →</button>
    <button id="close" class="secondary">关闭 (Esc)</button>
  </div>
</div>
<script>
var SLIDES = __SLIDES_JSON__;
var current = -1;
var viewer = document.getElementById('viewer');
var viewerImg = document.getElementById('viewer-img');
var caption = document.getElementById('viewer-caption');
function show(i) {
  if (!SLIDES.length) { return; }
  current = (i + SLIDES.length) % SLIDES.length;
  viewerImg.src = SLIDES[current].src;
  var title = SLIDES[current].title ? ' · ' + SLIDES[current].title : '';
  caption.textContent = SLIDES[current].id + title + '（' + (current + 1) + '/' + SLIDES.length + '）';
  viewer.classList.add('open');
}
function hide() { viewer.classList.remove('open'); current = -1; }
document.getElementById('grid').addEventListener('click', function (event) {
  var card = event.target.closest('.card');
  if (card) { show(parseInt(card.getAttribute('data-index'), 10)); }
});
document.getElementById('prev').addEventListener('click', function () { show(current - 1); });
document.getElementById('next').addEventListener('click', function () { show(current + 1); });
document.getElementById('close').addEventListener('click', hide);
document.addEventListener('keydown', function (event) {
  if (!viewer.classList.contains('open')) { return; }
  if (event.key === 'Escape') { hide(); }
  if (event.key === 'ArrowLeft') { show(current - 1); }
  if (event.key === 'ArrowRight') { show(current + 1); }
});
</script>
</body>
</html>
'@

$html = $htmlTemplate
$html = $html.Replace('__DECK_ID__', (ConvertTo-HtmlText $deckId))
$html = $html.Replace('__STAGE__', (ConvertTo-HtmlText $stage))
$html = $html.Replace('__COUNT__', [string]$slideInfos.Count)
$html = $html.Replace('__GENERATED_AT__', $generatedAt)
$html = $html.Replace('__WARNINGS__', $warningsHtml)
$html = $html.Replace('__CARDS__', ($cardParts -join "`n"))
$html = $html.Replace('__SLIDES_JSON__', $slidesJson)
Write-Utf8File -Path $previewPath -Text $html
Write-Host "[1/3] preview.html 已生成：$previewPath"

# ---------------------------------------------------------------------------
# 4. PPTX 组装（可选）
# ---------------------------------------------------------------------------
$result = [ordered]@{
    deckId      = $deckId
    stage       = $stage
    slideCount  = $slideInfos.Count
    previewPath = $previewPath
    pptxPath    = $null
    pngDir      = $null
    notesMapped = 0
    powerPoint  = $null
    warnings    = $warnings
    result      = 'PASS_WITHOUT_PPTX'
}
$exitCode = 3

if ($SkipPptx) {
    Write-Host '[2/3] 已按 -SkipPptx 跳过 PPTX 组装。'
} else {
    $pptExe = Find-PowerPointExe -Explicit $PowerPointExe
    if (-not $pptExe) {
        $warnings += '未找到本机 PowerPoint，跳过 PPTX 组装（preview.html 仍可用）。'
        $result.warnings = $warnings
        Write-Host '[2/3] 未找到 PowerPoint，跳过 PPTX 组装。'
    } else {
        Write-Host "[2/3] 使用 PowerPoint：$pptExe"
        $launchedProcess = $null
        $powerPoint = $null
        $presentation = $null
        $reopened = $null
        $attached = $false
        $step = 'connect'
        try {
            try {
                $powerPoint = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application')
                $attached = $true
            } catch {
                $launchedProcess = Start-Process -FilePath $pptExe -ArgumentList '/automation' -PassThru
                for ($attempt = 0; $attempt -lt 30 -and -not $powerPoint; $attempt++) {
                    Start-Sleep -Milliseconds 500
                    try { $powerPoint = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application') } catch { }
                }
            }
            if (-not $powerPoint) { throw 'PowerPoint COM 对象在 15 秒内不可用。' }

            $result.powerPoint = [ordered]@{
                version  = $powerPoint.Version
                build    = $powerPoint.Build
                attached = $attached
            }
            $step = 'init'
            try { $powerPoint.DisplayAlerts = 1 } catch { }

            $step = 'add-presentation'
            $presentation = $powerPoint.Presentations.Add()   # 与验收脚本一致：带窗口自动化更可靠
            try { $presentation.Windows.Item(1).WindowState = 2 } catch { }  # ppWindowMinimized
            $presentation.PageSetup.SlideWidth = 960
            $presentation.PageSetup.SlideHeight = 540

            $slideIndex = 1
            foreach ($info in $slideInfos) {
                $step = "slide-$slideIndex"
                $slide = $presentation.Slides.Add($slideIndex, 12)  # ppLayoutBlank
                $step = "picture-$($info.id)"
                $picture = $null
                foreach ($pictureAttempt in 1..2) {
                    try {
                        $picture = $slide.Shapes.AddPicture($info.path, 0, -1, 0, 0, 960, 540)
                        break
                    } catch {
                        if ($pictureAttempt -eq 2) { throw }
                        Start-Sleep -Milliseconds 800
                    }
                }

                if ($info.takeaway -or $info.title) {
                    $noteLines = New-Object System.Collections.Generic.List[string]
                    if ($info.title) { $noteLines.Add(('本页结论：' + $info.title)) }
                    if ($info.takeaway) { $noteLines.Add(('听众要点：' + $info.takeaway)) }
                    if ($info.nextLink) { $noteLines.Add(('衔接下一页：' + $info.nextLink)) }
                    $notesText = ($noteLines -join "`r")
                    $step = "notes-$($info.id)"
                    $notesShape = $null
                    foreach ($shape in $slide.NotesPage.Shapes) {
                        try {
                            if ($shape.HasTextFrame -eq -1 -and $shape.PlaceholderFormat.Type -eq 2) { $notesShape = $shape; break }
                        } catch { }
                    }
                    if (-not $notesShape) {
                        foreach ($shape in $slide.NotesPage.Shapes) {
                            if ($shape.HasTextFrame -eq -1) { $notesShape = $shape; break }
                        }
                    }
                    if ($notesShape) {
                        $notesShape.TextFrame.TextRange.Text = $notesText
                        $result.notesMapped++
                    } else {
                        $warnings += "$($info.id) 未能定位备注占位符，备注未写入。"
                    }
                }
                $slideIndex++
            }

            $step = 'saveas'
            $pptxPath = Join-Path $deliveryDir ("$deckId.pptx")
            $presentation.SaveAs($pptxPath, 24)  # ppSaveAsOpenXMLPresentation
            $presentation.Close()
            $presentation = $null
            $result.pptxPath = $pptxPath

            # 复开校验：页数与每页至少一个形状
            $step = 'reopen'
            $reopened = $powerPoint.Presentations.Open($pptxPath, -1, 0, 0)  # ReadOnly, Untitled, WithWindow=false
            $verifyOk = $reopened.Slides.Count -eq $slideInfos.Count
            if ($verifyOk) {
                foreach ($s in $reopened.Slides) { if ($s.Shapes.Count -lt 1) { $verifyOk = $false; break } }
            }
            if (-not $verifyOk) { throw 'PPTX 复开校验失败：页数或形状数量不符。' }

            if ($ExportPng) {
                $pngDir = Join-Path $deliveryDir 'png'
                New-Item -ItemType Directory -Force -Path $pngDir | Out-Null
                foreach ($s in $reopened.Slides) {
                    $pngPath = Join-Path $pngDir ("$($slideInfos[$s.SlideIndex - 1].id).png")
                    $s.Export($pngPath, 'PNG', 1280, 720)
                }
                $result.pngDir = $pngDir
            }
            $reopened.Close()
            $reopened = $null

            $result.result = 'PASS'
            $exitCode = 0
            Write-Host "[3/3] PPTX 已生成并通过复开校验：$pptxPath（备注 $($result.notesMapped)/$($slideInfos.Count) 页）"
        } catch {
            $warnings += ("PPTX 组装失败（step=$step）：" + $_.Exception.Message)
            $result.warnings = $warnings
            Write-Warning "[2/3] PPTX 组装失败（step=$step）：$($_.Exception.Message)"
        } finally {
            if ($reopened) { try { $reopened.Close() } catch { } }
            if ($presentation) { try { $presentation.Close() } catch { } }
            if ($powerPoint -and -not $attached) { try { $powerPoint.Quit() } catch { } }
            if ($launchedProcess -and -not $launchedProcess.HasExited) {
                Stop-Process -Id $launchedProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

$resultPath = Join-Path $deliveryDir 'delivery-result.json'
Write-Utf8File -Path $resultPath -Text (($result | ConvertTo-Json -Depth 4))
Write-Host "交付清单：$resultPath"

if ($exitCode -eq 0) { exit 0 }
exit 3
