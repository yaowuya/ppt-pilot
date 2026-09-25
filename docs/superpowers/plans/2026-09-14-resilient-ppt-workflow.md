# Resilient PPT Workflow Implementation Plan

> Execute the user-approved design in this session using test-first changes and narrowly owned subagents. Do not commit, push, run Office, mutate the real presentation run, or overwrite installed enhancements.

**Goal:** A reliable runtime enforces facts, permissions, identity and delivered-page quality while the model chooses creative methods; ordinary page failures do not stop independent work and partial PPT delivery is explicit.

**Architecture:** Preserve existing transaction identities, CAS and source validation. Separate page-local failures from shared corruption; promote valid pages independently. Record authorized omissions against unchanged failed transaction bytes, settle batches without resetting attempts, and finish with a verified target/delivered/missing partition. A small high-level advance/finalize interface owns mechanical transitions. Both SVG workflow and editable export consume one installed delivery-contract validator.

**Tech stack:** Python 3.9+ standard library, existing SVG/OOXML conversion, plain dashboard JavaScript/CSS, unittest.

## Constraints

- Canonical starting commit: `0ba86aa`; retain installed SDK generator 1.9.0 enhancements, normalization and theme-batch retirement without downgrading existing style assets or the dashboard disconnect fix.
- Keep original failed transactions and response evidence; never reset counters, create a recovery deck, fabricate PASS or write invalid SVG as a candidate.
- Path, source/fact identity, snapshot/CAS and unsupported executable SVG checks remain hard gates. Shared integrity failures still block.
- Partial delivery includes only validated current formal SVGs, retains original target IDs/order, explicitly records missing pages and does not claim full completion or Office verification.
- Existing complete-only runs without new metadata keep their strict legacy validation. Existing runs are not mutated by installation or tests.
- All maintenance code, fixtures and evidence stay in this repository. Any install must preserve locally enhanced contracts and use normal backup/verification installers only after tests.

## Shared delivery contract

New optional `run.json.delivery`, schema version 1:

```json
{
  "schema_version": 1,
  "status": "prepared|complete|partial|failed",
  "policy": "strict|best_effort",
  "target_slide_ids": ["S01", "S02"],
  "delivered_slide_ids": ["S01"],
  "missing_slides": [{
    "slide_id": "S02",
    "reason": "attempts_exhausted|user_skipped",
    "failure_reason": "svg_contract_failed",
    "generation_attempt": 3,
    "transaction_id": "sha256:<64 lowercase hex>",
    "transaction_ref": ".ppt-pilot/visual-generation-transactions/S02-<same hex>.json",
    "transaction_sha256": "sha256:<failed transaction file digest>"
  }],
  "storyboard_sha256": "sha256:<current storyboard bytes>",
  "theme_sha256": "sha256:<current theme bytes>",
  "quality_report_sha256": null,
  "slide_sha256": {"S01": "sha256:<current formal SVG bytes>"}
}
```

`quality_report_sha256` is required for final complete/partial; prepared is never exportable. Delivered and missing sets are disjoint and exhaust the original ordered targets. Complete requires no omissions; partial requires best_effort and both delivered and missing; failed requires zero delivered. The shared `_delivery_contract.py` validates data; callers retain safe file readers and verify all bound bytes, including failed transaction evidence. Legacy absence never authorizes missing pages.

`run.production_policy` is `strict` or `best_effort`; legacy absence is strict, new entry defaults to best_effort, and explicit `advance --allow-partial` changes an existing run's policy. The delivery record must match the persisted policy. Manifest omission extensions are paired `omitted_transaction_refs` and `omitted_transaction_sha256` (ref to original failed-file digest); omission evidence requires a terminal `partial`/`failed` manifest and its original slot. Failed transaction bytes and attempt counters remain unchanged. Shared safety/identity failures are not omittable.

Implementation subagents must start at commit `0ba86aa`, not the Agent tool's older default `origin/main` (`99e9326`); preserve and rebase any work started at the wrong baseline before integration.

## Tasks

- [x] **Baseline reconciliation:** Port installed enhancements and their regression tests into canonical source, preserving public fixes and agent/style versions. Validate affected host/runtime tests before layering new semantics.
- [x] **Delivery contract:** Add pure shared partition/evidence schema validator and adversarial tests for omissions, status contradictions, duplicate IDs, missing hashes, unsafe refs and invalid failure classes.
- [x] **Page-local runtime:** Classify ordinary output/visual failures separately from global integrity errors; retain failed transaction bytes; add audited omission metadata to manifests; independently promote validated pages; close processed batches; expose genuinely executable actions and bounded retry outcomes. Add high-level `advance`/`finalize` operations with explicit best-effort authorization rather than model-written owner state.
- [x] **Workflow gates:** Add prepared/partial/failed outcome handling, delivered-only final QA, dirty-page exclusion, bound evidence and safe partial export paths. Keep complete legacy behavior strict.
- [x] **Editable delivery:** Validate final partial metadata and current hashes; select only the delivered storyboard subset in original order; bind original target/missing inventory to snapshots/results; distinguish completeness from structural/Office verification and name partial output explicitly. Keep no-image fallback and publish guarantees.
- [x] **Autonomy and validation:** Preserve explicit user constraints while reporting conservative text-width margin as a warning requiring visual evidence instead of claiming actual clipping; use existing safe SVG normalization for ordinary model formatting. Keep actual bounds/unsafe elements/fact mismatches blocking for the affected page.
- [x] **Approval locality:** Separate structured content/visual/operational fingerprints for newly recorded review snapshots; use raw-hash validation for old approvals. Only known visual/metadata fields may be excluded; arbitrary prose/facts stay bound. Move style updates out of content-owned brief rewrites.
- [x] **Dashboard and instructions:** Show page-local failures/omissions, processed vs delivered counts, partial delivery and actionable next work. Replace repeated low-level choreography in primary skill with four key nodes, runtime-owned mechanics, scoped QA and end-to-end PPT handoff when requested.
- [x] **Integration and review:** Test synthetic mixed batches (including zero-candidate exhausted S06), promotion/resume/replay, strict mode, global corruptions, partial PPT structure, missing/tampered omission records, and existing full delivery. Run full suite and browser checks. Compare install surfaces before any standard deployment; preserve actual run-state hash.

## Verified outcome — 2026-09-14

- Complete unittest discovery ran in four isolated module shards: 1073 tests, 1062 passed, 11 skipped, zero failures/errors after aligning the last obsolete README assertion. Historical pressure evidence was preserved against its original Skill snapshot; four fresh policy-only agent checks bind the revised editable Skill.
- Integrated runtime/export regression set: 386 tests, four skips, no failures. Additional end-to-end checks exposed and fixed structured-storyboard and canonical SVG text metadata compatibility rather than rewriting runtime artifacts.
- Synthetic end-to-end result: three planned pages, two native editable PPTX pages, one disclosed omission, no image fallback, unchanged failed transaction bytes. `GENERATED_UNVERIFIED` is deliberate because no real Office process was run; synthetic PNG files test evidence binding, not actual visual quality.
- Final ordinary-run QA now requires a `final_review` binding current formal SVGs to actual PNG render paths/hashes, renderer identity and visual PASS; boolean checks alone cannot finalize. Imported source/render drift is rechecked before committing the final run state.
- Browser checks covered page-local failure with a healthy sibling, prepared-not-delivered, explicit partial and zero-output failed outcomes, all ten details, mobile overflow, terminal skipped-page copy and clean browser/server error logs.
- Standard installer verified in isolated directories, then updated DeepSeek Harness, Claude Code and Codex plus the repository's existing project scopes. Fifteen installed Skill trees match source exactly after cache filtering. Original user Agent bytes and all existing style assets were preserved; SDK stays at 1.9.0.
- The installed runtime read-only audit of the original run passes and identifies S02–S05 as promotable and S06 as exhausted with zero remaining attempts. No run write, page generation, attempt reset, Office execution, commit, push or PR action was performed.
- Deliberate compatibility choices: installed counter-decrement retry was not propagated; visible 64px geometry bounds remain hard. The 0.88 width-margin heuristic is a render-required warning. Existing raw approval snapshots remain exact-byte strict; new semantic snapshots are not retrofitted onto old approvals.

## Verification

Use focused unittest modules during each red/green cycle, followed by `python -m unittest discover -s tests -q`. Run all presentation tests on synthetic/temp directories; run no presentation model generation or Office. Use browser preview tools for dashboard changes, including mobile and mixed partial status. Record outcomes and known limits before reporting completion.
