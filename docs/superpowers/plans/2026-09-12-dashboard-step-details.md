# Dashboard Step Details Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the checklist inline. Do not commit or deploy without a user request.

**Goal:** Every HTML workflow step shows its purpose and concrete observed information, including completed and pending steps on narrow screens.

**Architecture:** Enrich the existing `tasks[].detail` projection using already allowlisted document metadata, storyboard parsing, sanitized review counters and public slide state. Keep schema version 1, workflow ownership, recovery priority and preview authorization unchanged. Render every detail using `textContent`; retain the existing light palette and desktop sidebar/mobile horizontal rail.

**Tech Stack:** Python 3.9+ standard library, plain JavaScript/CSS, unittest, browser preview.

## Constraints

- Preserve all pre-existing working-tree changes.
- Do not expose raw document text, arbitrary run fields, absolute paths or control tokens.
- File presence is not approval; formal-page counts are not elapsed-time progress.
- Pending steps describe their work and missing output, not fabricated execution.
- No new dependency, remote service, runtime write, host installation or commit.

## Implementation

- [x] Add snapshot tests for ten distinct step descriptions, canonical/legacy document presence, storyboard-only counts, review round/blocker summaries, formal/sample/dirty page facts, current notices and malformed data without private-content leakage.
- [x] Run focused tests and confirm that detail assertions fail against the old generic payload.
- [x] Enrich `_tasks` in `skills/ppt-start/scripts/_dashboard/snapshot.py`; pass sanitized review and parsed storyboard count from `build_snapshot` through `_finish`.
- [x] Update `skills/ppt-start/assets/dashboard/app.js` to show a visible status and detail for every stage. Update `styles.css` for readable text and wrapping on desktop/mobile, without mobile hiding or clamping.
- [x] Add an HTTP assertion in `tests/test_dashboard_server.py` for per-stage information and its live update.
- [x] Document the display semantics in `docs/LIVE-DASHBOARD.md` and the existing live-dashboard reference, preserving their current lifecycle requirements.
- [x] Run dashboard tests and the repository suite. Preview an isolated synthetic fixture using the real dashboard server, inspect all ten details on desktop and mobile, exercise updates and existing slide navigation, and capture visual proof.

## Verification commands

```bash
python -m unittest tests.test_dashboard_snapshot tests.test_dashboard_server tests.test_dashboard_lifecycle -v
```

```bash
python -m unittest discover -s tests -q
```

Browser fixture must contain only synthetic data, outside existing presentation runs. Use the preview server tools and restore desktop viewport after mobile verification.

## Verification results

- Baseline: 913 tests, 11 skipped, exit 0. After changes: 921 tests, 11 skipped, exit 0. Both runs report the same pre-existing temporary-directory ResourceWarning.
- Focused snapshot/HTTP suite: 42 tests, 2 skipped, exit 0. New assertions first failed against the generic detail payload.
- Browser before frontend changes: only 1 of 10 steps had a detail node. After: 10 of 10 at desktop width 1024 and mobile width 375, all displayed and unclipped; no document-width overflow.
- Same-stage artifact updates changed report metadata and formal-page counts without reload, while preserving slide selection and stage-rail scroll position. Raw report text remained absent.
- Existing dirty-page preview, modal and next-page navigation worked. Console and failed-request checks were empty; screenshots captured desktop and mobile. Viewport reset to desktop.
- Browser reload exposed an unrelated existing Windows disconnected-client traceback in `server.py`; the service recovered and continued polling. Logged as a separate task suggestion, not folded into this change.
- JavaScript syntax and `git diff --check` passed. No host installation or commit performed.
