# Input/output and state contract

## Input routes

`ppt-editable` accepts one finalized PPT Pilot run selected by explicit path, current directory, or the only valid run under `ppt-output/`. It never accepts an arbitrary SVG directory and never modifies `.ppt-pilot/run.json`.

There are three disjoint adapters:

1. **AI 状态**：new runs with a storyboard-keyed `slides` map and `delivery: {status: complete|partial}`;
2. **legacy explicit**：historical delivery object with policy, hashes, omission transactions and terminal batch evidence;
3. **legacy implicit**：historical `stage: complete` run without delivery metadata.

A malformed legacy-shaped object cannot fall through to AI state. A run with `slides` but missing/malformed delivery cannot fall through to legacy complete.

## AI 状态 adapter

- `slides` keys equal the complete storyboard target IDs exactly;
- target and output order always comes from the storyboard;
- `promoted` requires `slides/<id>.svg` and enters delivered pages;
- `failed` requires nonempty failure code/message;
- `skipped` requires the saved explicit user decision and original answer;
- `complete` requires every page promoted;
- `partial` requires at least one promoted page and at least one failed/skipped page;
- stage, delivery status, approved manuscript state, theme, QA report, and actual production SVGs must agree; the QA report contains exactly one `ppt-pilot-qa-json` fenced object whose exact `status`, target, promoted and missing arrays equal the derived partition.

AI 状态 complete/partial **不需要** transaction 或 batch owner，也不得制造它们。Missing-page evidence is projected into the editable snapshot/result as `{slide_id, reason, evidence_type: ai_state, evidence}`.

## Legacy adapters

Legacy explicit delivery keeps its existing strict validator: policy, ordered target partition, storyboard/theme/QA/SVG hashes, failed transaction and terminal batch omission slot must all match. Legacy implicit complete retains its exact storyboard inventory and approved-anchor fallback.

Legacy omission JSON remains byte-compatible and has no `evidence_type` field.

## Snapshot and source selection

The input snapshot binds actual selected SVG bytes, IDs, canonical relative paths, storyboard notes, converter/subset versions, verification config, and the selected adapter's complete normalized delivery record. A committed result with the same snapshot ID is reused only when its delivered/missing partition and evidence also equal the current selection.

AI state always uses formal production SVGs. Partial conversion selects only promoted pages in storyboard order; it never silently drops another selected page or adopts an old sample.

## Output namespaces

All writes stay under `delivery/editable/`:

| Completeness | Verified | Unverified | Commit record |
|---|---|---|---|
| complete | `<deck-id>-editable.pptx` | `<deck-id>-editable-unverified.pptx` | `editable-result.json` |
| partial | `<deck-id>-editable-partial.pptx` | `<deck-id>-editable-partial-unverified.pptx` | `editable-result-partial.json` |

Partial and complete outputs never overwrite each other. Existing verified authority is preserved when a new build is blocked, fails verification, or remains unverified.

## Result states

- `PASS`: selected pages passed structural, Office and visual verification;
- `GENERATED_UNVERIFIED`: native candidate passed pre-Office checks but Office/Pillow was unavailable or Office was explicitly skipped;
- `BLOCKED`: input, path, dependency, lock, SVG or recovery contract failed; no new deck is published;
- `FAILED_VERIFICATION`: a built candidate failed structural, Office, normalized or visual verification; no new deck is published.

Completeness and verification are independent. A verified partial deck remains partial; an unverified complete deck is not PASS. Converter failure is local to editable delivery and never downgrades or reopens the SVG run.
