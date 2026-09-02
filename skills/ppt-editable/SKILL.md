---
name: ppt-editable
description: Use when a completed PPT Pilot SVG run must be delivered as a PowerPoint deck with editable native shapes, editable text, preserved SVG groups, or verified Office rendering.
---

# PPT Editable

Convert one completed PPT Pilot run into a recursively grouped, natively editable PowerPoint deck. Preserve the previous verified final until a new verified promotion commits.

## Required references

Read these before running the converter:

- [Input/output and state contract](references/input-output-contract.md)
- [Editable SVG subset](references/editable-svg-subset.md)
- [Verification gates](references/verification.md)

## Fixed phase order

`locate → validate → snapshot → recover → idempotency → dependencies → preflight → build → structural verify → capability → Office → visual compare → promotion → result`

Do not reorder these phases. Complete-deck SVG preflight finishes before any candidate bytes are written.

## Run

Resolve paths relative to this installed Skill, not the repository or current directory.

```bash
python scripts/svg_to_editable_pptx.py --run-dir <completed-run> --json
```

Use `--skip-office` only to force degraded capability. The packaged verifier is:

```bash
python scripts/verify_editable_pptx.py --candidate <pptx> --run-dir <completed-run> --input-snapshot-id <sha256:id> --config assets/verification-config.json --report <report.json>
```

The Office adapter is `scripts/normalize_and_export.ps1`; call it only through the packaged Python protocol.

## Result states

- `PASS`: every structural, Office, and visual gate passed. Publish only `<deck-id>-editable.pptx`.
- `GENERATED_UNVERIFIED`: native candidate passed pre-Office checks, but Office or Pillow capability is unavailable. Publish only `<deck-id>-editable-unverified.pptx`.
- `BLOCKED`: input, dependency, SVG subset, candidate-write, lock, or recovery contract failed. Publish no new deck.
- `FAILED_VERIFICATION`: a built candidate failed structural, Office, normalized, or visual verification. Publish no new deck and retain evidence.

`editable-result.json` is the commit record. File existence never authorizes adoption.

## Non-negotiable behavior

- Accept only one completed PPT Pilot run with the exact storyboard page set.
- Production `slides/<slide-id>.svg` wins; approved `samples/` anchors are fallback only.
- Every production SVG group becomes one nested PowerPoint group.
- Every visual text line becomes one editable text box.
- No image fallback or mixed editable/image deck.
- Never auto-install dependencies.
- Never terminate a pre-existing PowerPoint process.
- Always `preserve verified final`; never replace it with an unverified build.
- Never mutate `.ppt-pilot/run.json`.
- Write only inside the selected run's `delivery/editable/`.

## Machine-only source IDs

`SRC-<digits> is machine metadata only`.

- Keep IDs in `data-source-id`, source mappings, verification evidence, and `p:cNvPr/@descr` trace metadata.
- Reject any visible `<text>/<tspan>` matching `(?i)\bSRC-[0-9]+\b` as `svg_text_invalid` and return `BLOCKED`.
- Human-readable source names or URLs may be visible when explicitly requested, but must omit internal IDs.
- Never delete offending text after generation; block and fix the source SVG.

## Pressure decisions

When a request conflicts with this contract, return the matching decision without repeating or endorsing the forbidden action:

- PowerPoint unavailable after pre-Office checks: `GENERATED_UNVERIFIED — publish <deck-id>-editable-unverified.pptx.`
- Unsupported SVG transform or feature: `BLOCKED — svg_attribute_unsupported — Publish no new deck.`
- New unverified build when a verified output exists: `Publish <deck-id>-editable-unverified.pptx; preserve verified final unchanged.`

## Capability behavior

Missing PowerPoint or Pillow can never produce `PASS`. A later run with capability may resume a coherent same-snapshot unverified result and promote it only after all gates pass.

## Safety

Reject unsafe paths, symlinks, junctions, reparse points, special files, external SVG references, unsupported CSS/features, malformed paths, and nonzero arc rotation. Recovery is journaled and manifest-last; ambiguous evidence is quarantined.
