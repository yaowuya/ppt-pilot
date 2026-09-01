param(
    [Parameter(Mandatory = $true)][string]$RequestPath,
    [Parameter(Mandatory = $true)][string]$ResultPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OwnershipPath = "$ResultPath.owner.json"

$NativeTypeDefinition = @'
using System;
using System.Runtime.InteropServices;
public static class PowerPointNativeMethods {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@

function Write-AtomicJson {
    param([string]$Path, [object]$Value)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        [void][IO.Directory]::CreateDirectory($parent)
    }
    $temporary = Join-Path $parent ('.' + [IO.Path]::GetFileName($Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $json = $Value | ConvertTo-Json -Depth 16 -Compress
    [IO.File]::WriteAllText($temporary, $json + "`n", (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Release-ComObject {
    param([object]$Value)
    if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
    }
}

function Get-PowerPointProcesses {
    $result = @()
    foreach ($process in @(Get-Process -Name POWERPNT,wpp -ErrorAction SilentlyContinue)) {
        try {
            $result += [pscustomobject]@{
                pid = [int]$process.Id
                started_at = $process.StartTime.ToUniversalTime().ToString('o')
            }
        }
        catch {
            throw "cannot capture complete PowerPoint process snapshot for PID $($process.Id): $($_.Exception.Message)"
        }
    }
    return @($result)
}

function Get-ExactOwnedProcess {
    param([int]$ProcessId, [string]$StartedAt)
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (
            $process.ProcessName -eq 'POWERPNT' -and
            $process.StartTime.ToUniversalTime().ToString('o') -eq $StartedAt
        ) {
            return $process
        }
    }
    catch { }
    return $null
}

function New-Result {
    param([string]$RequestId)
    return [ordered]@{
        schema_version = 1
        request_id = $RequestId
        capability = $false
        powerpoint = [ordered]@{ version = $null; build = $null }
        process = [ordered]@{ pid = $null; started_at = $null; owned = $false }
        stages = @()
        counts = [ordered]@{}
        renders = [ordered]@{
            source_full = @()
            editable_full = @()
            source_geometry = @()
            editable_geometry = @()
        }
        normalized_path = $null
        error = $null
        exit_code = 4
    }
}

function Add-Stage {
    param([System.Collections.IDictionary]$Result, [string]$Name, [string]$Status)
    $Result.stages += [ordered]@{ name = $Name; status = $Status }
}

function Set-ResultError {
    param([System.Collections.IDictionary]$Result, [string]$Code, [string]$Message, [string]$Stage, [int]$ExitCode)
    $Result.error = [ordered]@{ code = $Code; message = $Message; stage = $Stage }
    $Result.exit_code = $ExitCode
}

function Assert-ExactProperties {
    param([object]$Value, [string[]]$Names, [string]$Label)
    if ($null -eq $Value) {
        throw "$Label is missing"
    }
    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    if (@(Compare-Object ($Names | Sort-Object) $actual).Count -ne 0) {
        throw "$Label fields differ from schema"
    }
}

function Assert-Request {
    param([object]$Request)
    $required = @(
        'schema_version', 'request_id', 'capability_only', 'protocol_dir',
        'candidate_path', 'normalized_path', 'geometry_candidate_path',
        'source_full_deck_path', 'source_geometry_deck_path', 'selected_svgs',
        'geometry_svgs', 'render_directories', 'ordered_slide_ids',
        'expected_counts', 'config'
    )
    Assert-ExactProperties $Request $required 'request'
    Assert-ExactProperties $Request.config @('render_width', 'render_height') 'config'
    Assert-ExactProperties $Request.expected_counts @('slides', 'top_level_shapes', 'recursive_leaves', 'recursive_groups') 'expected_counts'
    Assert-ExactProperties $Request.render_directories @('source_full', 'editable_full', 'source_geometry', 'editable_geometry') 'render_directories'
    if ($Request.schema_version -ne 1 -or $Request.request_id -notmatch '^[0-9a-f]{32}$') {
        throw 'request identity is invalid'
    }
    if ($Request.config.render_width -ne 1280 -or $Request.config.render_height -ne 720) {
        throw 'render dimensions must equal the configured 1280x720 contract'
    }
    # Keep the exact export dimensions visible in the adapter contract: 1280, 720.
    $slideIds = @($Request.ordered_slide_ids)
    if ($slideIds.Count -eq 0 -or $slideIds.Count -ne [int]$Request.expected_counts.slides) {
        throw 'ordered slide count differs'
    }
    if (@($slideIds | Select-Object -Unique).Count -ne $slideIds.Count) {
        throw 'ordered slide IDs are duplicated'
    }
    foreach ($entriesName in @('selected_svgs', 'geometry_svgs')) {
        $entries = @($Request.$entriesName)
        if ($entries.Count -ne $slideIds.Count) {
            throw "$entriesName count differs"
        }
        for ($index = 0; $index -lt $entries.Count; $index += 1) {
            Assert-ExactProperties $entries[$index] @('slide_id', 'path') "$entriesName entry"
            if ([string]$entries[$index].slide_id -ne [string]$slideIds[$index] -or -not [string]$entries[$index].path) {
                throw "$entriesName order or path differs"
            }
        }
    }
}

function Open-PresentationReadOnly {
    param([object]$Application, [string]$Path)
    $presentations = $null
    try {
        $presentations = $Application.Presentations
        return $presentations.Open($Path, -1, 0, 0)
    }
    finally {
        Release-ComObject $presentations
    }
}

function Get-RecursiveShapeCounts {
    param([object]$Presentation)
    $top = 0
    $leaves = 0
    $groups = 0
    $slides = $null
    try {
        $slides = $Presentation.Slides
        for ($slideIndex = 1; $slideIndex -le [int]$slides.Count; $slideIndex += 1) {
            $slide = $null
            $shapes = $null
            try {
                $slide = $slides.Item($slideIndex)
                $shapes = $slide.Shapes
                $top += [int]$shapes.Count
                for ($shapeIndex = 1; $shapeIndex -le [int]$shapes.Count; $shapeIndex += 1) {
                    $stack = New-Object Collections.Stack
                    $stack.Push($shapes.Item($shapeIndex))
                    while ($stack.Count -gt 0) {
                        $current = $stack.Pop()
                        try {
                            if ([int]$current.Type -eq 6) {
                                $groups += 1
                                $groupItems = $null
                                try {
                                    $groupItems = $current.GroupItems
                                    for ($index = 1; $index -le [int]$groupItems.Count; $index += 1) {
                                        $stack.Push($groupItems.Item($index))
                                    }
                                }
                                finally {
                                    Release-ComObject $groupItems
                                }
                            }
                            else {
                                $leaves += 1
                            }
                        }
                        finally {
                            Release-ComObject $current
                        }
                    }
                }
            }
            finally {
                Release-ComObject $shapes
                Release-ComObject $slide
            }
        }
        return [ordered]@{
            slides = [int]$slides.Count
            top_level_shapes = $top
            recursive_leaves = $leaves
            recursive_groups = $groups
        }
    }
    finally {
        Release-ComObject $slides
    }
}

function Get-OoxmlRecursiveShapeCounts {
    param([string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $slideEntries = @(
            $archive.Entries |
                Where-Object { $_.FullName -match '^ppt/slides/slide[0-9]+\.xml$' } |
                Sort-Object { [int]([regex]::Match($_.FullName, '[0-9]+').Value) }
        )
        $top = 0
        $leaves = 0
        $groups = 0
        foreach ($entry in $slideEntries) {
            $stream = $null
            try {
                $stream = $entry.Open()
                $document = New-Object Xml.XmlDocument
                $document.PreserveWhitespace = $true
                $document.Load($stream)
                $namespaces = New-Object Xml.XmlNamespaceManager($document.NameTable)
                $namespaces.AddNamespace('p', 'http://schemas.openxmlformats.org/presentationml/2006/main')
                $tree = $document.SelectSingleNode('/p:sld/p:cSld/p:spTree', $namespaces)
                if ($null -eq $tree) { throw "slide lacks spTree: $($entry.FullName)" }
                $top += $tree.SelectNodes('./p:sp | ./p:grpSp', $namespaces).Count
                $leaves += $tree.SelectNodes('.//p:sp', $namespaces).Count
                $groups += $tree.SelectNodes('.//p:grpSp', $namespaces).Count
            }
            finally {
                if ($null -ne $stream) { $stream.Dispose() }
            }
        }
        return [ordered]@{
            slides = $slideEntries.Count
            top_level_shapes = $top
            recursive_leaves = $leaves
            recursive_groups = $groups
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Export-Presentation {
    param(
        [object]$Presentation,
        [object[]]$SlideIds,
        [string]$Directory,
        [string]$StreamName,
        [System.Collections.IDictionary]$Result
    )
    if (-not (Test-Path -LiteralPath $Directory)) {
        [void][IO.Directory]::CreateDirectory($Directory)
    }
    $entries = @()
    $slides = $null
    try {
        $slides = $Presentation.Slides
        if ([int]$slides.Count -ne $SlideIds.Count) {
            throw 'render slide count differs from ordered IDs'
        }
        for ($index = 1; $index -le [int]$slides.Count; $index += 1) {
            $slide = $null
            try {
                $slideId = [string]$SlideIds[$index - 1]
                $outputPath = Join-Path $Directory ($slideId + '.png')
                $slide = $slides.Item($index)
                $slide.Export($outputPath, 'PNG', 1280, 720)
                $entries += [ordered]@{ slide_id = $slideId; path = $outputPath }
            }
            finally {
                Release-ComObject $slide
            }
        }
    }
    finally {
        Release-ComObject $slides
    }
    $Result.renders[$StreamName] = @($entries)
}

function New-SourceDeck {
    param(
        [object]$Application,
        [object[]]$Entries,
        [string]$Path
    )
    $presentations = $null
    $presentation = $null
    $slides = $null
    $pageSetup = $null
    try {
        $presentations = $Application.Presentations
        $presentation = $presentations.Add()
        $pageSetup = $presentation.PageSetup
        $pageSetup.SlideWidth = 960
        $pageSetup.SlideHeight = 540
        $slides = $presentation.Slides
        for ($index = 0; $index -lt $Entries.Count; $index += 1) {
            $slide = $null
            $shapes = $null
            $picture = $null
            try {
                $slide = $slides.Add($index + 1, 12)
                $shapes = $slide.Shapes
                $picture = $shapes.AddPicture([string]$Entries[$index].path, 0, -1, 0, 0, 960, 540)
            }
            finally {
                Release-ComObject $picture
                Release-ComObject $shapes
                Release-ComObject $slide
            }
        }
        $presentation.SaveAs($Path, 24)
        return $presentation
    }
    catch {
        if ($null -ne $presentation) {
            try { $presentation.Close() } catch { }
            Release-ComObject $presentation
            $presentation = $null
        }
        throw
    }
    finally {
        Release-ComObject $slides
        Release-ComObject $pageSetup
        Release-ComObject $presentations
    }
}

$result = New-Result ''
$exitCode = 4
$request = $null
$application = $null
$ownedProcess = $null
$openedCandidate = $null
$normalizedPresentation = $null
$geometryPresentation = $null
$sourceFullPresentation = $null
$sourceGeometryPresentation = $null
$activeStage = $null

try {
    try {
        $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-Request $request
        $result = New-Result ([string]$request.request_id)
    }
    catch {
        Set-ResultError $result 'invalid_request' $_.Exception.Message 'request' 3
        $exitCode = 3
        throw
    }

    if (-not ("PowerPointNativeMethods" -as [type])) {
        Add-Type -TypeDefinition $NativeTypeDefinition
    }

    $before = @{}
    foreach ($identity in @(Get-PowerPointProcesses)) {
        $before[([string]$identity.pid + '|' + [string]$identity.started_at)] = $true
    }

    try {
        $application = New-Object -ComObject PowerPoint.Application
        $firstHwnd = [IntPtr][int64]$application.HWND
        if ($firstHwnd -eq [IntPtr]::Zero) {
            throw 'PowerPoint application HWND is unavailable'
        }
        $pidValue = [uint32]0
        $threadId = [PowerPointNativeMethods]::GetWindowThreadProcessId($firstHwnd, [ref]$pidValue)
        if ($threadId -eq 0 -or $pidValue -eq 0) {
            throw 'PowerPoint application process identity is unavailable'
        }
        $process = Get-Process -Id ([int]$pidValue) -ErrorAction Stop
        if ($process.ProcessName -ne 'POWERPNT') {
            throw 'registered PowerPoint.Application server is not Microsoft POWERPNT.EXE'
        }
        $startedAt = $process.StartTime.ToUniversalTime().ToString('o')

        $secondHwnd = [IntPtr][int64]$application.HWND
        $confirmedPidValue = [uint32]0
        $confirmedThreadId = [PowerPointNativeMethods]::GetWindowThreadProcessId($secondHwnd, [ref]$confirmedPidValue)
        if (
            $secondHwnd -eq [IntPtr]::Zero -or
            $secondHwnd -ne $firstHwnd -or
            $confirmedThreadId -eq 0 -or
            $confirmedPidValue -ne $pidValue
        ) {
            throw 'PowerPoint application process identity changed during ownership claim'
        }
        $confirmedProcess = Get-Process -Id ([int]$confirmedPidValue) -ErrorAction Stop
        $confirmedStartedAt = $confirmedProcess.StartTime.ToUniversalTime().ToString('o')
        if (
            $confirmedProcess.ProcessName -ne 'POWERPNT' -or
            $confirmedStartedAt -ne $startedAt
        ) {
            throw 'PowerPoint application process identity changed during ownership claim'
        }

        $identityKey = [string]$confirmedProcess.Id + '|' + $confirmedStartedAt
        if (-not $before.ContainsKey($identityKey)) {
            $ownedProcess = $confirmedProcess
        }
        $result.process.pid = [int]$confirmedProcess.Id
        $result.process.started_at = $confirmedStartedAt
        $result.process.owned = ($null -ne $ownedProcess)
        Write-AtomicJson $OwnershipPath $result.process
        $result.powerpoint.version = [string]$application.Version
        $result.powerpoint.build = [string]$application.Build
        $result.capability = $true
        Add-Stage $result 'capability' 'passed'
    }
    catch {
        $result.capability = $false
        Add-Stage $result 'capability' 'failed'
        Set-ResultError $result 'powerpoint_unavailable' $_.Exception.Message 'capability' 0
        $exitCode = 0
    }

    if ($result.capability -and [bool]$request.capability_only) {
        $result.exit_code = 0
        $exitCode = 0
    }
    elseif ($result.capability) {
        $activeStage = 'normalize'
        Add-Stage $result 'normalize' 'running'
        $openedCandidate = Open-PresentationReadOnly $application ([string]$request.candidate_path)
        $openedCandidate.SaveAs([string]$request.normalized_path, 24)
        $openedCandidate.Close()
        Release-ComObject $openedCandidate
        $openedCandidate = $null
        $normalizedPresentation = Open-PresentationReadOnly $application ([string]$request.normalized_path)
        $result.normalized_path = [string]$request.normalized_path
        Add-Stage $result 'normalize' 'passed'
        $activeStage = $null

        $activeStage = 'counts'
        Add-Stage $result 'counts' 'running'
        $counts = Get-OoxmlRecursiveShapeCounts ([string]$request.normalized_path)
        $result.counts = $counts
        foreach ($key in @('slides', 'top_level_shapes', 'recursive_leaves', 'recursive_groups')) {
            if ([int]$counts[$key] -ne [int]$request.expected_counts.$key) {
                Add-Stage $result 'counts' 'failed'
                Set-ResultError $result 'powerpoint_reopen_failed' "count differs: $key" 'counts' 2
                $exitCode = 2
                throw 'PowerPoint recursive count verification failed'
            }
        }
        Add-Stage $result 'counts' 'passed'
        $activeStage = $null

        $activeStage = 'source_decks'
        Add-Stage $result 'source_decks' 'running'
        $sourceFullPresentation = New-SourceDeck $application @($request.selected_svgs) ([string]$request.source_full_deck_path)
        $sourceGeometryPresentation = New-SourceDeck $application @($request.geometry_svgs) ([string]$request.source_geometry_deck_path)
        $geometryPresentation = Open-PresentationReadOnly $application ([string]$request.geometry_candidate_path)
        $geometrySlides = $null
        try {
            $geometrySlides = $geometryPresentation.Slides
            if ([int]$geometrySlides.Count -ne [int]$request.expected_counts.slides) {
                throw 'geometry candidate slide count differs'
            }
        }
        finally {
            Release-ComObject $geometrySlides
        }
        Add-Stage $result 'source_decks' 'passed'
        $activeStage = $null

        $activeStage = 'render'
        Add-Stage $result 'render' 'running'
        Export-Presentation $sourceFullPresentation @($request.ordered_slide_ids) ([string]$request.render_directories.source_full) 'source_full' $result
        Export-Presentation $normalizedPresentation @($request.ordered_slide_ids) ([string]$request.render_directories.editable_full) 'editable_full' $result
        Export-Presentation $sourceGeometryPresentation @($request.ordered_slide_ids) ([string]$request.render_directories.source_geometry) 'source_geometry' $result
        Export-Presentation $geometryPresentation @($request.ordered_slide_ids) ([string]$request.render_directories.editable_geometry) 'editable_geometry' $result
        Add-Stage $result 'render' 'passed'
        $activeStage = $null
        $result.exit_code = 0
        $exitCode = 0
    }
}
catch {
    if ($null -eq $result.error) {
        $stageName = 'adapter'
        $errorCode = 'powerpoint_render_failed'
        if ($null -ne $activeStage) {
            $stageName = [string]$activeStage
            Add-Stage $result $stageName 'failed'
            switch ($stageName) {
                'normalize' { $errorCode = 'powerpoint_normalize_failed' }
                'counts' { $errorCode = 'powerpoint_reopen_failed' }
                default { $errorCode = 'powerpoint_render_failed' }
            }
        }
        $location = $_.InvocationInfo.PositionMessage
        Set-ResultError $result $errorCode ($_.Exception.Message + " `n" + $location) $stageName 4
        $exitCode = 4
    }
}
finally {
    foreach ($presentation in @(
        $geometryPresentation,
        $sourceGeometryPresentation,
        $sourceFullPresentation,
        $normalizedPresentation,
        $openedCandidate
    )) {
        if ($null -ne $presentation) {
            try { $presentation.Close() } catch { }
            Release-ComObject $presentation
        }
    }

    if ($ownedProcess) {
        $confirmedOwnedProcess = Get-ExactOwnedProcess ([int]$result.process.pid) ([string]$result.process.started_at)
        if ($null -ne $confirmedOwnedProcess) {
            try { $application.Quit() } catch { }
        }
        Release-ComObject $confirmedOwnedProcess
    }
    Release-ComObject $application
    $application = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()

    if ($ownedProcess) {
        try {
            $remaining = Get-ExactOwnedProcess ([int]$result.process.pid) ([string]$result.process.started_at)
            if ($null -ne $remaining) {
                $remaining.Kill()
                [void]$remaining.WaitForExit(5000)
            }
        }
        catch { }
    }

    $result.exit_code = $exitCode
    try {
        Write-AtomicJson $ResultPath $result
    }
    catch {
        $exitCode = 4
    }
}

exit $exitCode
