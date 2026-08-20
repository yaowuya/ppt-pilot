# Codex Resume Acceptance — Attempt 3

- **Run date:** 2026-08-19
- **Host:** Codex CLI 0.146.1
- **Scenario:** resume the synthetic approved fixture through theme and two anchors only
- **Transcript:** `codex-transcript.jsonl`
- **Run state:** `ppt-output/resume-approved/run.json`
- **Anchor QA:** `ppt-output/resume-approved/anchor-qa.json`

## Result

**PASS — Codex resumed the staged fixture without redoing manuscript work and produced two validated, durable anchors.**

Verified behavior:

- `brief.md`, `research.md`, `sources.md`, `outline.md`, `storyboard.md`, and `manuscript-review.md` remained byte-identical to the staged fixture;
- exact portable state fields remain in `run.json`, with nested state `manuscript_approved` and top-level stage `anchor`;
- `theme.json` resolves the bundled `minimal-business` seed and preserves 64 px / 24 px spacing plus typography minimums;
- exactly `samples/S01.svg` and `samples/S05.svg` were generated; no `slides/` production directory or deck-level QA was started;
- both SVGs parse as UTF-8 XML, use only whitelisted elements, preserve unique IDs, contain no remote/unsafe values, meet type minimums, use explicit tspans, and pass conservative vertical glyph/safe-area checks;
- Chrome headless render evidence is durable under `qa/rendered/`, and the final two PNGs are 1280×720;
- independent inspection of the final renders found no clipping, overlap, missing geometry, or unreadable content;
- S05 records one visual repair and its final render as `qa/rendered/S05-r1.png`.

Chrome `getBBox()` found one 0.67 px Arial glyph overhang to the left of the S01 takeaway's source anchor at `x=64`; the source anchor and all structural geometry remain at or within the safe rectangle, and nothing is clipped. This is treated as subpixel font-metric rendering variance, not a layout failure.

## Scope

This is a resume-behavior test from a synthetic approved fixture. It proves neither that the fixture's historical reviewer IDs came from real host events nor that Codex can run a valid independent reviewer now. Real provenance still requires the originating host transcript; the separate Codex blocker acceptance remains failed.

Generated-anchor PowerPoint import is not covered by this PASS and remains pending.
