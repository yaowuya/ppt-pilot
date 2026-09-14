---
name: ppt-editable
description: Use when a finalized PPT Pilot SVG run, complete or explicitly partial, must be delivered as a PowerPoint deck with editable native shapes, editable text, preserved SVG groups, or verified Office rendering.
---

# PPT Editable

Convert one runtime-finalized PPT Pilot run into a recursively grouped, natively editable PowerPoint deck. Accept full completion or an explicitly authorized, evidence-bound partial delivery. Preserve the previous verified final until a new verified promotion commits; partial output never overwrites full output.

Before consuming prior run artifacts, run the installed `ppt-start/scripts/ppt_workflow_gate.py --run-dir <run> --audit-run` common read-only audit and stop on `BLOCKED`. Consume only contract-validated data files: never execute, import, dynamically load, or pass a run file to an interpreter; never install dependencies or create helper scripts below the run. Owner recovery belongs to the fixed `ppt-start` runtime CLI, not manual repair.

## Required references

Read these before running the converter:

- [Input/output and state contract](references/input-output-contract.md)
- [Editable SVG subset](references/editable-svg-subset.md)
- [Verification gates](references/verification.md)

## Fixed phase order

`locate → validate → snapshot → recover → idempotency → dependencies → preflight → build → structural verify → capability → Office → visual compare → promotion → result`

Do not reorder these implementation phases. Every selected delivery page finishes SVG preflight before any candidate bytes are written. The model uses the packaged command, not a manual phase-by-phase state update.

## Run

Resolve paths relative to this installed Skill, not the repository or current directory.

```bash
python scripts/svg_to_editable_pptx.py --run-dir <final-run> --json
```

Use `--skip-office` when the user disallows Office execution or explicitly requests degraded verification; it never grants verification PASS. The packaged verifier is:

```bash
python scripts/verify_editable_pptx.py --candidate <pptx> --run-dir <final-run> --input-snapshot-id <sha256:id> --config assets/verification-config.json --report <report.json>
```

The Office adapter is `scripts/normalize_and_export.ps1`; call it only through the packaged Python protocol.

## Result states

- `PASS`: every structural, Office, and visual gate passed for the selected pages. Full delivery uses `<deck-id>-editable.pptx`; partial delivery uses `<deck-id>-editable-partial.pptx`.
- `GENERATED_UNVERIFIED`: native candidate passed pre-Office checks, but Office or Pillow capability is unavailable or Office was explicitly skipped. Full delivery uses `<deck-id>-editable-unverified.pptx`; partial delivery uses `<deck-id>-editable-partial-unverified.pptx`.
- `BLOCKED`: input, dependency, SVG subset, candidate-write, lock, or recovery contract failed. Publish no new deck.
- `FAILED_VERIFICATION`: a built candidate failed structural, Office, normalized, or visual verification. Publish no new deck and retain evidence.

`editable-result.json` is the full-delivery commit record. Partial delivery uses `editable-result-partial.json`, `.editable-partial.lock`, and `<deck-id>-editable-partial.pptx` or `<deck-id>-editable-partial-unverified.pptx`. File existence never authorizes adoption.

Report completeness independently from verification: `delivery_status: partial` is never complete, even when verification is `PASS`. Preserve original `target_slide_ids`, ordered `delivered_slide_ids`, and every `missing_slides` reason/evidence record in the result. `prepared` and `failed` runs are not exportable; zero delivered pages never produce a PPTX.

## Non-negotiable behavior

- Accept one runtime-finalized run. Legacy `complete` without delivery metadata still requires the exact storyboard page set. Explicit `complete|partial` must match the final `run.delivery`, approved content-node state, production policy, current hashes, and sealed omission evidence.
- Partial delivery selects only declared delivered pages in original storyboard order; never silently shrink the targets or drop another failing page during conversion.
- Production `slides/<slide-id>.svg` is mandatory for explicit delivery metadata. Approved `samples/` fallback remains only for legacy full runs.
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

When a request conflicts with this contract, return the matching decision without repeating or endorsing the forbidden action. The filename examples below describe full delivery; a partial run must use the converter-returned partial namespace instead:

- PowerPoint unavailable after pre-Office checks: `GENERATED_UNVERIFIED — publish <deck-id>-editable-unverified.pptx.`
- Unsupported SVG transform or feature: `BLOCKED — svg_attribute_unsupported — Publish no new deck.`
- New unverified build when a verified output exists: `Publish <deck-id>-editable-unverified.pptx; preserve verified final unchanged.`

## Capability behavior

Missing PowerPoint or Pillow can never produce `PASS`. A later run with capability may resume a coherent same-snapshot unverified result and promote it only after all gates pass.

## Safety

Reject unsafe paths, symlinks, junctions, reparse points, special files, external SVG references, unsupported CSS/features, malformed paths, and nonzero arc rotation. Recovery is journaled and manifest-last; ambiguous evidence is quarantined.
