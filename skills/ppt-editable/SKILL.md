---
name: ppt-editable
description: Use when a finalized complete or partial PPT Pilot SVG run must be converted to an editable PowerPoint with native shapes, editable text, and honest Office verification.
---

# PPT Editable

Convert one finalized PPT Pilot run into a recursively grouped, natively editable PowerPoint deck. This is optional post-processing: it never repairs, advances, or reopens `ppt-start` state.

## Read first

- [Input/output and state contract](references/input-output-contract.md)
- [Editable SVG subset](references/editable-svg-subset.md)
- [Verification gates](references/verification.md)

## Run

Resolve paths from this installed Skill:

```bash
python scripts/svg_to_editable_pptx.py --run-dir <final-run> --json
```

Use `--skip-office` only when Office is unavailable/disallowed or the user explicitly accepts degraded verification. It can produce `GENERATED_UNVERIFIED`, never `PASS`.

The converter selects exactly one input adapter:

- new AI-state complete/partial from storyboard + `slides` records;
- legacy explicit evidence-bound delivery;
- legacy implicit complete.

It converts only the selected promoted/delivered production pages in storyboard order. A malformed route fails closed; adapters never fall through into a looser route.

## Fixed conversion order

`locate → select adapter → validate → snapshot → recover editable output → idempotency → dependencies → SVG preflight → build → structural verify → Office capability → Office normalize/render → visual compare → promote → result`

Every selected SVG completes preflight before candidate publication. The converter writes only below `delivery/editable/` and never changes `run.json`, attempts, omissions, or source SVGs.

## Outcomes

- `PASS`: structural, Office and visual gates passed;
- `GENERATED_UNVERIFIED`: native candidate passed pre-Office checks, but Office/Pillow did not run;
- `BLOCKED`: input/dependency/path/SVG/lock/recovery contract prevented a build;
- `FAILED_VERIFICATION`: a candidate was built but failed structural, Office or visual verification.

Report `delivery_status` separately. Partial output uses the `-editable-partial` namespace and never overwrites complete output. An unverified refresh never replaces a previously verified deck.

## Non-negotiable

- Preserve SVG group hierarchy as PowerPoint groups and visible text as editable text boxes.
- No image fallback or mixed editable/image deck.
- Internal `SRC-<digits>` stays only in machine trace metadata; visible occurrences are `BLOCKED`.
- Never auto-install dependencies or terminate a pre-existing PowerPoint process.
- Missing Office/Pillow never produces PASS and never downgrades valid SVG completeness.
- File existence alone is not authority; snapshot, journal and commit record must agree.
