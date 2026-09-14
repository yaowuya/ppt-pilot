# Input/output and state contract

## Input

Input is one runtime-finalized PPT Pilot run, never an arbitrary SVG directory. The run selection precedence is:

1. explicit run directory;
2. a valid final current run;
3. exactly one valid final run under `ppt-output/`.

Legacy `stage: complete` without delivery metadata retains the exact ordered storyboard page set and approved-anchor fallback. New explicit delivery requires `run.stage` and `run.delivery.status` to agree as `complete` or `partial`, no active generation owner, and an approved content-gate state. `prepared` and `failed` are not exportable.

For explicit delivery, the sibling installed `ppt-start/scripts/_delivery_contract.py` is the shared schema/evidence authority. The converter validates:

- persisted production policy matches the delivery policy; partial requires `best_effort`;
- original target IDs match the complete storyboard in order;
- delivered and missing IDs form a disjoint, exhaustive ordered partition;
- current storyboard, theme, QA report and delivered SVG hashes match the record;
- each omission binds an unchanged failed transaction and its sealed slot in a terminal batch;
- delivered pages are not dirty; omitted dirty pages remain recorded.

Only declared delivered pages are selected, in original storyboard order. Storyboard input accepts the runtime's single `ppt-pilot-json` owner with ordered `slides`, or the legacy Markdown slide sections; mixed conflicting inventories and malformed machine owners are rejected without rewriting the source. Explicit delivery uses formal `slides/<slide-id>.svg` files, never samples or incidental extra SVGs. The converter does not silently drop another failing page or modify `run.json`; a selected-page failure returns to the fixed runtime workflow.

## Snapshot

The canonical snapshot hashes actual selected SVG bytes, IDs, run-relative paths, owners, storyboard note fields, converter/subset versions, and exact verification config bytes. Explicit delivery additionally binds the entire delivery record, including original targets and omissions.

Canonical JSON uses sorted keys, compact separators, UTF-8, and no path aliases. Same snapshot plus coherent committed output is idempotent; changed input creates a new identity.

## Output paths

All writes stay under `delivery/editable/`:

| Namespace | Verified output | Unverified output | Commit record |
|---|---|---|---|
| Full | `<deck-id>-editable.pptx` | `<deck-id>-editable-unverified.pptx` | `editable-result.json` |
| Partial | `<deck-id>-editable-partial.pptx` | `<deck-id>-editable-partial-unverified.pptx` | `editable-result-partial.json` |

`.tmp/` holds transaction/work evidence and `quarantine/` holds failed or ambiguous evidence; partial work has its own namespace. Partial artifacts cannot overwrite full artifacts. `PASS` targets only its namespace's verified filename; `GENERATED_UNVERIFIED` targets only its unverified filename. Failed or blocked runs publish no new deck.

## Lock, journal, and recovery

Each full/partial namespace has an OS-backed lock (`.editable.lock` or `.editable-partial.lock`) covering recovery, generation and promotion. Lock-file existence alone is not ownership.

Each promotion writes a `PREPARED` journal binding snapshot, namespace, target kind/path, new hash, previous target hash, previous manifest hash and backups. It atomically writes and rereads the journal, replaces and hash-checks the public target, writes the selected commit record last, then removes transaction evidence only after committed hashes match.

Coherent previous verified authority wins over an unverified refresh or untrusted backup. Invalid journals cannot manufacture authority; ambiguous bytes are quarantined. File existence alone never authorizes adoption.

## Commit record and states

Verification and completeness are independent:

- `PASS`: selected pages passed structural, Office and visual checks.
- `GENERATED_UNVERIFIED`: selected pages passed pre-Office checks; the unverified output is separate and prior PASS remains authoritative.
- `BLOCKED`: no candidate is published.
- `FAILED_VERIFICATION`: no candidate is published; evidence is retained.

Explicit outcomes also report `delivery_status`, `delivery_policy`, `target_slide_ids`, `delivered_slide_ids` and `missing_slides`. A verified partial deck is still partial; a structurally valid deck without Office verification is not PASS. Legacy result schemas remain unchanged when no explicit delivery record exists.

Never mutate `.ppt-pilot/run.json`, reset attempts, rewrite failed evidence or infer a new omission inside the converter.
