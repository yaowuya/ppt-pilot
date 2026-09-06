# Legacy PPT Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Prevent external old decks from taking an unreviewed visual-only shortcut.

**Architecture:** Read-only PPTX intake creates a deterministic inventory. An import-specific, read-only workflow gate validates cumulative stage evidence; conditional skill routing invokes it without replacing existing generation contracts.

**Tech Stack:** Python 3.9+ standard library, unittest, Markdown skills.

**Spec:** `docs/superpowers/specs/2026-09-06-legacy-ppt-redesign-design.md`

## Global Constraints

- Keep the ten stages, guided/auto modes and five-control recovery order unchanged.
- Source/reference directories are read-only; no host installation, push or credential access.
- Tests use synthetic local files; no customer deck contents in the repository.
- Fail closed with explicit exceptions and nonzero CLI exit; no assert-based production gates.
- Helpers supplement existing style/generator/review contracts; they are not host hooks or semantic visual proof.

### Task 1: Safe source intake

**Files:** Create `skills/ppt-start/scripts/ppt_source_intake.py`, `skills/ppt-start/scripts/_source_intake.py`, `tests/test_source_intake.py`.

**Interfaces:** Produce `extract_pptx(path) -> dict` and the exact source inventory schema in the spec; CLI `--source --output`. No dependency on Task 2.

- [x] Write tests constructing ZIP/XML with reordered presentation relationships; assert `result['slides'][0]['part']` follows relationship order and `result['source']['sha256']` equals the source bytes digest.
- [x] Run `py -3 -m unittest discover -s tests -p test_source_intake.py -v`; observe missing implementation failure.
- [x] Implement parsing with `zipfile.ZipFile`, `xml.etree.ElementTree`, relationship normalization and bounded reads; use `open(output, 'xb')` only after extraction succeeds, cleaning only this created output if its write fails.
- [x] Add behavioral tests for text, tables, notes, warnings, hidden pages, unsafe package inputs, existing output and source preservation; run focused suite until green.
- [x] Self-review and report RED/GREEN evidence; leave changes uncommitted for the controller's combined review.

### Task 2: Import-specific stage gate

**Files:** Create `skills/ppt-start/scripts/ppt_workflow_gate.py`, `skills/ppt-start/scripts/_workflow_gate.py`, `tests/test_source_workflow_gate.py`.

**Interfaces:** Consume Task 1 inventory schema (synthetic fixtures can be built independently). Produce `check_run(run_dir, before) -> dict`, CLI `--run-dir --before` / `--snapshot`, and exact checkpoint schema in spec.

- [x] Write tests that create temporary run files with an external source binding; assert `check_run(root, 'theme')['status'] == 'BLOCKED'` when manuscript evidence is absent, despite `stage='production'`.
- [x] Run `py -3 -m unittest discover -s tests -p test_source_workflow_gate.py -v`; verify RED before implementation.
- [x] Implement read-only staged checks, strict types, safe evidence path resolution, hash binding, source-map coverage, recovery priority, review/anchor/QA checks and structured errors. Use explicit `raise ValueError`/error results, never assertions.
- [x] Add a valid fixture then mutate one field/file at a time: source, inventory, map, review input/report, style, anchor, SVG and render; verify expected BLOCKED code and reentry. Cover all nine before stages, malformed inputs, non-import NOT_APPLICABLE, python -O and no writes.
- [x] Self-review and report RED/GREEN evidence; no commits.

### Task 3: Conditional skill integration and forward verification

**Files:** Create `skills/ppt-start/references/source-deck-redesign.md`, `tests/prompts/legacy-ppt-redesign.md`, `tests/test_source_redesign_integration.py`; modify `skills/ppt-start/SKILL.md` and relevant pointers in workflow, brief-and-research, qa-and-revision, artifact-contract, manuscript-review, design-system.

**Interfaces:** Consume both CLI contracts exactly. Preserve all existing non-import routes and generation contracts.

- [x] Capture current fresh-Agent routing baseline before changing instructions.
- [x] Write a real CLI integration test: synthesize old deck, run intake, create import binding, request `--before theme`, assert exit 2 / manuscript-or-upstream blocker and no visual files; extend with a complete synthetic evidence chain and stale evidence failure.
- [x] Add narrow conditional entry routing plus one authoritative reference with commands, schemas, checkpoint notices, source/target style distinction, limitation disclosure and remediation recipes.
- [x] Run focused and full `py -3 -m unittest discover -s tests -q`, skill creator `quick_validate.py`, and fresh-Agent raw-PPT / pending-review / source-changed / missing-style / auto / protected-page scenarios.
- [x] Independent review of code correctness and spec compliance; fix findings with focused tests and re-review. Record exact test results and behavioral-test limitations in acceptance evidence.

## Execution notes

Work in the approved separate branch `codex/legacy-ppt-redesign` in the current checkout; no extra worktree is needed. Source intake and gate use separate owned files and can run in parallel. Documentation remains controller-owned. Baseline test rerun uses normal temporary-directory permissions because restricted Windows execution denied temporary paths.

## Completion record and validation limitations

- Task 1 implemented and independently reviewed; all reported intake defects fixed with RED/GREEN evidence. Includes source-size cap and OPC package-root targets.
- Task 2 implemented; final review additionally required active-batch resume input checks, exact affirmative source-operation authorization and shared safe XML parsing. Added `_xml_safety.py` and `tests/test_source_workflow_recovery.py`; scoped re-review approved all three fixes with no important new regressions.
- Task 3 integrated into the entrypoint and seven relevant references, with actual CLI integration tests and six routing-plan cases. Baseline was fresh; forward cases reused an independent dashboard-only task because new agent creation hit a thread limit. These are planning checks, not six fresh full-host executions.
- Final full suite: 663 tests, 8 skips, 0 failures, 79.210s. Python 3.9 final source suite: 63 tests, 1 Windows symlink skip, 0 failures, 14.087s. Optimized Python source suite also passed with the same count.
- Skill creator quick_validate was attempted but could not run because available Python runtimes lack PyYAML; no dependency was installed. Existing skill-package and workflow contract tests passed. Checkmarks above record completed implementation/verification attempts with these explicit limitations, not unperformed validator or host executions.
- Changes remain uncommitted in the approved local branch; no hosts installed, no push, no PR mutation.
