# Codex Resume Acceptance — Attempt 2

- **Run date:** 2026-08-19
- **Host:** Codex CLI 0.146.1
- **Scenario:** resume from the synthetic approved fixture through theme and two anchors only
- **Transcript:** `codex-transcript.jsonl`
- **Run state:** `ppt-output/resume-approved/run.json`
- **Independent browser captures:** `S01-chrome.png`, `S05-chrome.png`

## Result

**FAIL — the resume branch is correct, but hard geometry validation passed invalid safe-margin placement.**

Correct behavior observed:

- the run reads and preserves the approved manuscript artifacts without rerunning manuscript stages;
- it uses the exact portable state fields;
- it creates one `theme.json` and exactly two anchor SVGs, `samples/S01.svg` and `samples/S05.svg`;
- it stops at `stage: anchor` before production;
- both SVGs parse as XML, use only whitelisted elements, contain no remote/unsafe content, and render without clipping or obvious content overlap in Chrome.

Hard-check violations:

- both anchors place footer/source and page-number text at baseline `y=680`, outside the 64 px safe rectangle whose lower boundary is `y=656`;
- the rendered S05 title bounding box starts at `y=42`, outside the top safe boundary;
- despite those defects, `run.json` marks both anchors `structural_qa: passed` and `visual_qa: rendered_passed`.

The transcript does show real Chrome headless screenshot calls and visual repair attempts, so this is not classified as an unrendered run. It is a geometry-validation failure. The screenshots were also written to a temporary machine path rather than recorded as durable run evidence.

## Corrective action

The Skill now defines the safe rectangle explicitly as `x=64..1216`, `y=64..656` for every non-background element, including titles, source/footer text, and page numbers, with glyph ascent/descent reserved. A rendered status also requires a concrete rendering method and durable evidence reference.
