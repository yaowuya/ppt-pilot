$ErrorActionPreference = 'Stop'

$evidenceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $evidenceRoot '..\..')).Path
$svgPath = Join-Path $projectRoot 'skills\ppt-pilot\assets\examples\office-safe-slide.svg'
$pptxPath = Join-Path $evidenceRoot 'office-safe-slide-powerpoint.pptx'
$pngPath = Join-Path $evidenceRoot 'office-safe-slide-powerpoint.png'
$resultPath = Join-Path $evidenceRoot 'powerpoint-import-result.json'

$powerPointExe = 'C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE'
$launchedProcess = $null
$powerPoint = $null
$presentation = $null
$reopened = $null
$result = [ordered]@{
    runDate = '2026-08-19'
    sourceSvg = $svgPath
    outputPptx = $pptxPath
    outputPng = $pngPath
    result = 'FAIL'
}

try {
    $launchedProcess = Start-Process -FilePath $powerPointExe -ArgumentList '/automation' -PassThru
    for ($attempt = 0; $attempt -lt 20 -and -not $powerPoint; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $powerPoint = [Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application')
        }
        catch {
        }
    }
    if (-not $powerPoint) {
        throw 'No active Microsoft PowerPoint COM object after launching POWERPNT.EXE.'
    }

    $applicationExe = Join-Path $powerPoint.Path 'POWERPNT.EXE'
    if ((Resolve-Path $applicationExe).Path -ne (Resolve-Path $powerPointExe).Path) {
        throw "Automation resolved to a different application: $applicationExe"
    }
    $result.applicationName = $powerPoint.Name
    $result.applicationPath = $applicationExe
    $result.powerPointVersion = $powerPoint.Version
    $result.powerPointBuild = $powerPoint.Build
    $result.productVersion = (Get-Item $applicationExe).VersionInfo.ProductVersion

    $presentation = $powerPoint.Presentations.Add()
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540
    $slide = $presentation.Slides.Add(1, 12)
    $shape = $slide.Shapes.AddPicture($svgPath, 0, -1, 0, 0, 960, 540)
    $result.insertedShapeType = $shape.Type
    $result.insertedShapeCount = $slide.Shapes.Count
    $result.insertedWidth = $shape.Width
    $result.insertedHeight = $shape.Height
    $presentation.SaveAs($pptxPath, 24)
    $presentation.Close()
    $presentation = $null

    $reopened = $powerPoint.Presentations.Open($pptxPath, -1, 0, 0)
    $reopenedSlide = $reopened.Slides.Item(1)
    $reopenedShape = $reopenedSlide.Shapes.Item(1)
    $result.reopenedSlideCount = $reopened.Slides.Count
    $result.reopenedShapeCount = $reopenedSlide.Shapes.Count
    $result.reopenedShapeType = $reopenedShape.Type
    $result.reopenedWidth = $reopenedShape.Width
    $result.reopenedHeight = $reopenedShape.Height
    $reopenedSlide.Export($pngPath, 'PNG', 1280, 720)
    $result.exportExists = Test-Path $pngPath

    if ($result.reopenedSlideCount -eq 1 -and
        $result.reopenedShapeCount -eq 1 -and
        [Math]::Abs($result.reopenedWidth - 960) -lt 0.1 -and
        [Math]::Abs($result.reopenedHeight - 540) -lt 0.1 -and
        $result.exportExists) {
        $result.result = 'PASS_PENDING_VISUAL_INSPECTION'
    }
}
catch {
    $result.error = $_.Exception.Message
}
finally {
    if ($reopened) { $reopened.Close() }
    if ($presentation) { $presentation.Close() }
    if ($powerPoint) { $powerPoint.Quit() }
    if ($launchedProcess -and -not $launchedProcess.HasExited) {
        Stop-Process -Id $launchedProcess.Id -Force
    }
    $result | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $resultPath
}

$result | ConvertTo-Json -Depth 4
if ($result.result -eq 'FAIL') { exit 1 }
