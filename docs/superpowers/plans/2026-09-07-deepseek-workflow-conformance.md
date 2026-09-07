# DeepSeek Workflow Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an external-PPT redesign fail closed when a host invents a native-PPT route or writes PPTX before the canonical SVG run reaches `complete`, and remove the built-in Jiawei style conflict that triggered an ad-hoc derived pack.

**Architecture:** Extend the existing read-only workflow gate with a host-neutral conformance audit and run it before every cumulative source-deck gate. Keep the repair policy in the Skill contract: violations are quarantined outside the run, then the run resumes from the canonical stage with a canonical `visual_generation_blocker`. Fix the source style pack so it already satisfies the SVG title-size contract.

**Tech Stack:** Python 3.9+, `unittest`, PowerShell deployment scripts, JSON/Markdown Skill assets.

**Spec:** `skills/ppt-start/references/source-deck-redesign.md`

## Global Constraints

- The workflow remains `brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`.
- PPTX delivery is allowed only after `stage: complete`, through `ppt-editable`, under `delivery/editable/`.
- The workflow gate remains read-only and returns exit code 2 for `BLOCKED`.
- An unavailable isolated generator writes only canonical `visual_generation_blocker` and performs zero prompt, transaction, manifest, candidate, SVG, or PPTX writes.
- Existing experiment artifacts are preserved; repair uses backup/quarantine rather than deletion.

---

### Task 1: Add run-level conformance audit

**Files:**
- Modify: `tests/test_source_workflow_gate.py`
- Modify: `skills/ppt-start/scripts/_workflow_gate.py`
- Modify: `skills/ppt-start/scripts/ppt_workflow_gate.py`

**Interfaces:**
- Produces: `audit_run(run_dir) -> {status, before, errors}`.
- Changes: every `check_run(run_dir, before)` invokes the same audit before recovery and stage evidence checks.

- [ ] **Step 1: Write failing behavioral tests**

Add tests that create real fixture files and assert literal results:

```python
def test_precomplete_pptx_blocks_every_gate(self):
    self.fixture.write('unexpected.pptx', 'native detour')
    self.blocked('anchor', 'precomplete_pptx', 'theme')

def test_noncanonical_native_control_state_blocks(self):
    self.fixture.run['native_delivery'] = {'status': 'active'}
    self.blocked('anchor', 'workflow_escape_state', 'theme')

def test_audit_cli_is_read_only(self):
    # Invoke --audit-run, assert PASS on a canonical fixture and byte-identical tree.
```

- [ ] **Step 2: Run the focused tests and observe RED**

Run: `py -3 -m unittest tests.test_source_workflow_gate.SourceGateTests.test_precomplete_pptx_blocks_every_gate tests.test_source_workflow_gate.SourceGateTests.test_noncanonical_native_control_state_blocks tests.test_source_workflow_gate.SourceGateTests.test_audit_cli_is_read_only -v`

Expected: FAIL because the existing gate ignores PPTX and escape-state fields and the CLI has no `--audit-run` action.

- [ ] **Step 3: Implement the minimal read-only audit**

Add `Gate.conformance()`, `audit_run()`, and CLI `--audit-run`. Validate the canonical stage set; reject `native_delivery`, `run_level_generator_blocker`, or any top-level `native_*` control; reject run-owned `.pptx` before `complete`; and after `complete` allow `.pptx` only below `delivery/editable/`. Exclude only the exact bound source PPTX path.

- [ ] **Step 4: Run the focused tests and observe GREEN**

Run the same command and require three passing tests with exit code 0.

### Task 2: Make the Jiawei source style valid without runtime derivation

**Files:**
- Modify: `tests/test_assets.py`
- Modify: `skills/ppt-start/assets/styles/jiawei-product/tokens.json`
- Modify: `skills/ppt-start/assets/styles/jiawei-product/prompt.md`

**Interfaces:**
- Produces: every selectable style pack exposes an explicit title token of at least 40px, matching its materialized prompt.

- [ ] **Step 1: Tighten the style behavior test**

Resolve `slide_title` or `page_title` explicitly and assert `>= 40`; also assert the materialized prompt contains the same `key=value` pair.

- [ ] **Step 2: Run the focused test and observe RED**

Run: `py -3 -m unittest tests.test_assets.StyleAssetTests.test_exact_style_pack_set_and_schema -v`

Expected: FAIL for `jiawei-product` with `page_title=36`.

- [ ] **Step 3: Update the source pack to 40px**

Change `tokens.json` and the closed typed prompt line from `page_title=36` to `page_title=40`; do not create a second runtime-derived style.

- [ ] **Step 4: Run the focused test and observe GREEN**

Run the same command and require exit code 0.

### Task 3: Bind DeepSeek failure behavior to the executable audit

**Files:**
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/source-deck-redesign.md`
- Modify: `skills/ppt-start/references/host-isolation-adapters.md`
- Modify: `docs/acceptance.md`

**Interfaces:**
- Consumes: `ppt_workflow_gate.py --audit-run`.
- Produces: an explicit DeepSeek adapter branch whose only safe no-adapter outcome is canonical `generator_unavailable` and stop.

- [ ] **Step 1: Document the executable checkpoints**

Require `--audit-run` immediately after selecting/creating the run, before every stage gate, and immediately before `ppt-editable`. State that cumulative `--before` calls include the audit automatically.

- [ ] **Step 2: Close the DeepSeek adapter ambiguity**

Replace the unsupported “already verified native/remote” claim with an evidence-based rule: use only a host primitive proven to supply prompt-by-value, fresh history, no filesystem/data tools, text-only output, and attribution; otherwise write the canonical blocker and stop. Generic tool-bearing subagents and native PPT/WPS fallbacks are forbidden.

- [ ] **Step 3: Add the incident as a pending real-host acceptance row**

Record the 2026-09-07 DeepSeek run as FAIL with its local evidence path and require the repaired host rerun to turn it into PASS; do not claim current DeepSeek generator support.

### Task 4: Verify, deploy, and repair the experiment without loss

**Files:**
- Operational update: DeepSeek plugin and user-level shared Skill installations.
- Operational repair: `D:/05-AI/ppt-部署与升级/ppt-output/jiwei-deployment-upgrade-restyle/`.

**Interfaces:**
- Consumes: passing repository tests and `--audit-run`.
- Produces: identical core Skill files in both discovery roots, a quarantined native detour, and a canonical stopped run at `anchor`.

- [ ] **Step 1: Run focused and full verification**

Run: `py -3 -m unittest tests.test_source_workflow_gate tests.test_source_redesign_integration tests.test_assets -v`, then `py -3 -m unittest discover -s tests -q` using a workspace-owned temporary directory if the sandbox blocks the system temporary directory.

- [ ] **Step 2: Reinstall the DeepSeek plugin and update the shared Skill core**

Use the repository installers/backups. Preserve the generated Jiawei pack until the canonical base pack has been deployed and the run theme is migrated; never silently delete the custom pack.

- [ ] **Step 3: Quarantine the invalid native branch**

Copy the original `run.json` and move the two root PPTX files plus native-only scripts/reports to a timestamped sibling quarantine directory. Preserve hashes in a repair manifest.

- [ ] **Step 4: Canonicalize the run state**

Remove only `native_delivery`, `run_level_generator_blocker`, and native-only hold/plan fields after archiving them. Restore `stage: anchor`, keep `dirty_slides`, and create the exact canonical `visual_generation_blocker` tuple if DeepSeek still lacks the isolation adapter.

- [ ] **Step 5: Re-run the original symptom check**

Run both `--audit-run` and `--before anchor`. Expected: audit PASS; stage gate BLOCKED only by canonical `visual_generation_blocker`, with zero PPTX/SVG generation side effects.

