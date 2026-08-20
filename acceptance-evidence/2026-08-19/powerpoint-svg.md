# Bundled SVG Microsoft PowerPoint Evidence

- **Run date:** 2026-08-19
- **Application in the completed historical run:** Microsoft PowerPoint 16.0, build 20228
- **Executable product version:** 16.0.20228.20190
- **Platform:** Windows 11
- **Current source:** `skills/ppt-pilot/assets/examples/office-safe-slide.svg`
- **Automation script:** `acceptance-evidence/2026-08-19/powerpoint-import.ps1`
- **Current machine result:** `acceptance-evidence/2026-08-19/powerpoint-import-result.json`
- **Revalidation diagnostic:** `acceptance-evidence/2026-08-19/powerpoint-revalidation-diagnostic.json`
- **Historical saved presentation:** `acceptance-evidence/2026-08-19/office-safe-slide-powerpoint.pptx`
- **Historical reopened-slide export:** `acceptance-evidence/2026-08-19/office-safe-slide-powerpoint.png`
- **Historical PPTX package check:** `acceptance-evidence/2026-08-19/powerpoint-pptx-package.txt`

## Historical completed run

Before the final safe-margin corrections, the script launched the specific Microsoft executable at `C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE`, verified that the active COM object's path matched that executable, inserted the then-current SVG at 960×540 points, saved and reopened the PPTX, and exported the reopened slide at 1280×720. One slide and one shape of type 28 remained at the original dimensions, and `ppt/media/image1.svg` was preserved. Visual inspection found no clipping, overlap, missing content, or material color loss.

That historical SVG has SHA-256 `b5b2abe4a1ed93f41938e4bf3473b39c10b645203748c5a004e74e3b1944b58a` inside the saved PPTX.

## Current-asset revalidation

The canonical SVG was then corrected so title glyphs and the source line remain inside the full 64 px safe rectangle. Its current SHA-256 is `33f711f6fe026255c784a49b6a27e7bf2f2bfdbd44aa24e974a9fbe2815cd95a`, so the historical PPTX does not contain the current asset.

Two automation reruns could not obtain a Microsoft PowerPoint COM object. A 30-second diagnostic showed the exact Microsoft process remained running but never appeared in the Running Object Table. A versioned `PowerPoint.Application.16` activation resolved to the installed WPS Office path instead, so it was rejected rather than misrepresented as Microsoft PowerPoint. No current-asset import/save/reopen result was produced.

## Current result and scope

**PENDING — host automation blocked.** The prior run remains evidence that the earlier SVG revision imported successfully in Microsoft PowerPoint 16.0.20228.20190, but it is not a PASS for the current canonical SVG. Browser and structural checks for the current SVG pass separately.

This evidence never establishes universal compatibility, per-element editability, generated-deck quality, another Office version, or another platform. Generated-deck SVG import also remains pending.
