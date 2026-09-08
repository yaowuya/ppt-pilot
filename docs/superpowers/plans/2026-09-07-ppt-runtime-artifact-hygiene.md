# PPT Runtime Artifact Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Eliminate run-local programs by supplying fixed runtime operations and enforcing the presentation artifact contract in every executable entry point.

**Architecture:** A shared read-only artifact firewall protects existing workflow and delivery tools. Production prompt/transaction/SVG modules back one runtime facade with atomic state storage, registered host adapters, durable dispatch reservations, and recovery. Installers synchronize selected user and project discovery scopes.

**Tech Stack:** Python 3.9+ standard library, PowerShell, unittest/pytest, existing PPT Pilot assets.

**Spec:** docs/superpowers/specs/2026-09-07-ppt-runtime-artifact-hygiene-design.md

## Global Constraints

- Python 3.9+; no new third-party runtime dependency.
- Installed Skill tools run in place; presentation runs never create or execute scripts or install dependencies.
- Detection is read-only; historical unexpected artifacts are never silently deleted.
- Preserve existing schema-v2 transaction and manifest fields and existing golden prompt bytes.
- Do not import tests from production, invoke nested AI CLIs, or start Office before editable delivery.
- Unknown host adapters fail closed; no DeepSeek adapter is registered by this change.
- Continue in the existing codex/legacy-ppt-redesign branch; user requested removal of extra worktrees.
- Verify behavior using real temporary runs. Full host acceptance requires actual host evidence; never relabel static tests as real host success.

### Task 1: Shared artifact firewall and executable entry-point coverage

**Files:** Create skills/ppt-start/scripts/_artifact_firewall.py and tests/test_runtime_artifacts.py. Modify skills/ppt-start/scripts/_workflow_gate.py, ppt_workflow_gate.py, and the ppt-editable preflight module. Keep one policy implementation; editable resolves the sibling installed ppt-start module with a fail-closed dependency error.

**Interfaces:** Produce `audit_artifacts(root, stage='brief', source_path=None) -> list[dict]`, whose errors contain `code`, `reentry_stage`, `next_action`, `artifacts`. Raise no unexpected exceptions for filesystem errors; return an unsafe-path error. Use `stat.FILE_ATTRIBUTE_REPARSE_POINT` on Windows/Python 3.9. Recognized source PPTX and delivery paths retain current semantics.

- [x] Add behavioral regression tests first. The failing production behavior is that ordinary and source runs with executable artifacts pass the gate.

```python
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    fixture = Fixture(root)
    fixture.write('helper.PS1.tmp', 'Write-Output 1')
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = audit_run(root)
    assert result['status'] == 'BLOCKED'
    assert result['errors'][0]['code'] == 'runtime_code_artifact'
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
```

- [x] Run `py -3 -m unittest discover -s tests -p test_runtime_artifacts.py -q`; capture the expected regression failure before implementation.
- [x] Implement full suffix-chain and forbidden-directory detection from the spec, plus contract-owned path/type rules. Preserve legacy English layouts, evidence paths bound by canonical owners, dashboard data and editable delivery. Unknown code/archives/extensionless files block. Data temp names must remain valid. A source PPTX exemption must match its exact bound path.

```python
errors = audit_artifacts(self.root, self.run['stage'], source_path)
if errors:
    error = GateError(errors[0]['code'], errors[0]['reentry_stage'], errors[0]['next_action'])
    error.error.update(errors[0])
    raise error
```

- [x] Integrate before ordinary `NOT_APPLICABLE`, audit, snapshot, active-batch and editable preflight; a rejected run causes zero delivery writes.
- [x] Run focused gate/editable tests, inspect filesystem read-only assertions, and commit this task.

### Task 2: Move proven prompt, SVG and generation functions into production

**Files:** Create skills/ppt-start/scripts/_prompt_runtime.py, _svg_runtime.py, _generation_runtime.py (focused private support modules permitted). Modify tests/test_redesign_prompt_contract.py and tests/test_visual_generation_contract.py to import production functions. Add tests/test_runtime_modules.py.

**Interfaces:** Preserve callable signatures for `compile_style_prompt`, `render_generation_prompt`, `sha256_id`, `canonical_json_bytes`, `project_active_visual_revisions`, `validate_v2_transaction`, `validate_v2_manifest`, `rebuild_batch_cursors`, `migrate_v1_run_to_v2`, `enrich_candidate_source_metadata`, `schedule_epoch`, and `promote_in_order`. Expose `validate_candidate(svg_text, expected_block_ids, source_map) -> bytes` as strict parsing/enrichment entry. Installed paths derive from `__file__`, never repo/test helpers. Fixture simulators stay in tests.

- [x] Add a real installed-copy test that imports production modules without the repository/tests on sys.path, compiles a bundled style prompt and rejects a duplicate/unknown source block. Run to prove the missing production boundary.

```python
try:
    enrich_candidate_source_metadata('<svg><g data-block-id="S01-B1"/><g data-block-id="S01-B1"/></svg>', {'S01-B1': ['SRC-1']})
except ValueError:
    pass
else:
    raise AssertionError('duplicate semantic block accepted')
```

- [x] Move production-suitable functions and constants with their actual dependency closure. Replace test-local implementations with explicit production imports; keep test fixtures/case interpreters separate. The extraction is mechanical only where byte-for-byte behavior is retained.
- [x] Add XML active-content, Office-safe elements/attributes, canvas, finite numeric values, basic geometry/text and source-enrichment validation using existing repository rules. No candidate is written by this module.
- [x] Run migrated contract tests and installed-copy tests. Verify existing golden bytes remain unchanged; commit.

### Task 3: Fixed runtime facade, storage and host dispatch lifecycle

**Files:** Create skills/ppt-start/scripts/ppt_runtime.py, _run_store.py, _host_adapter_runtime.py and focused runtime command modules; create skills/ppt-start/assets/host-adapters.json. Add tests/test_ppt_runtime.py and tests/fixtures/runtime-* declarative cases. Extend generation/firewall modules only for the declared runtime paths.

**Interfaces:** CLI commands and exact request schemas are defined in the approved spec. `RunStore(root)` provides no-follow `read_json`, `read_bytes`, `write_json`, `write_bytes`, hash CAS and a process lock. Every writer audits before consuming input and again under lock before writing. Responses truthfully report actual writes, including canonical failure/blocker writes; zero-write conformance errors remain distinct from recorded workflow failures.

Implementation clarification: reserve-dispatch additionally requires --capability CAPABILITY.json using the same exact preflight-only receipt schema. Neither the v2 manifest/transaction nor a previous read-only dispatch-plan stores host identity; this input prevents guessing which host/adapter to bind. The spec command signature has been clarified accordingly. No other owner fields are added. Set sys.dont_write_bytecode before packaged imports so the facade does not modify the installed Skill tree.

The read-only resume result supplies prepare_request when canonical prerequisites are ready, with all request/snapshot hashes computed by the runtime. The host must not need a custom hashing script to call prepare-batch.

- [x] Start with subprocess tests for an unsafe runtime input and an unregistered DeepSeek receipt. Add a one-slide end-to-end fixture for prepare → dispatch-plan → reserve-dispatch → bind-task → ingest-result → validation → promote → resume.

```python
result = invoke('resume', '--run-dir', str(run))
assert result.returncode == 2
assert json.loads(result.stdout)['errors'][0]['code'] == 'runtime_code_artifact'
assert (run / 'helper.py').read_text() == 'print(1)'
```

- [x] Implement store locking, canonical JSON and write-then-reread/hash; maintain original bytes on CAS conflict. Handle crash state using durable owner graphs and pointer-last rules, never trust cursor hints.
- [x] Implement capability receipt validation with an empty DeepSeek/Codex registry until real adapters have acceptance evidence; Claude entry binds packaged agent bytes and exact observation. Do not claim registry digests cryptographically attest a live host; the registered adapter and current host evidence both must match.
- [x] Implement the ten lifecycle commands plus explicit migrate-v1 and publish-anchors from the clarified spec. Migration is a mutator and resume remains read-only. Anchor generation must not depend on prior anchor approval or publish finals early: publish validated sample bytes, then require the existing approval flow before formal promotion. Runtime reads approved narrative/theme/source owners rather than taking unchecked narrative in request. Persist only contract-owned inputs, prompts, transactions, manifests, dispatch reservations, candidates/samples/finals and QA. Preserve source hash bindings and prior SVG on every failure.
- [x] Add real crash/replay tests for reservation-before-spawn, bind after uncertain spawn, pointer-last interrupted prepare, candidate before hash commit, promotion before state commit, exact prepare replay after changed run hash, stale QA and changed final bytes. An unbound reservation never respawns automatically.
- [x] Add explicit retry/recompose/fallback transitions using existing failure/attempt rules, including canonical blocker writes on exhausted attempts. Ensure no command shells out or imports run-local files.
- [x] Run focused runtime plus migrated contract/gate suites; commit.

### Task 4: Workflow instructions and reliable multi-host installation

**Files:** Modify skills/ppt-start/SKILL.md and relevant references, skills/ppt-editable/SKILL.md, tools/update-hosts.ps1, tools/install-deepseek-plugin.ps1, tests/test_tools_package.py, README.md, docs/INSTALL.md. Add a shared packaging helper only if needed to avoid duplicating copy/filter/digest logic.

**Interfaces:** Installer accepts explicit extra project roots, preserves old flags for compatibility, and automatically refreshes existing .agents/.claude Skill roots in selected projects. Package inventory, copy and digest use the same cache exclusions. Report actual installed paths/counts/digests and PARTIAL_FAILURE on mixed results.

Known discovery target: <USER_HOME>/.codex/plugins/cache/personal/ppt-pilot/local/skills is a physical stale plugin copy. Support an explicit CodexPluginRoot and refresh this existing skill tree; preserve its .git and unrelated files. Do not recursively enumerate plugin caches. Extra project target is <EXAMPLE_PROJECT>, with only existing local Skill discovery scopes updated.

When refreshing an existing project Claude Skill scope, install its matching ppt-svg-generator Agent too, including creating that project's .claude/agents directory if absent. This keeps the selected Skill and its verified Agent paired. Do not create discovery scopes in an extra project with no relevant Skill root. The coordinator reruns skill-pressure-baseline.md scenarios against the updated instructions before deployment; this text-only test does not replace actual host acceptance.

Align existing artifact-contract prose with the tested runtime boundaries: the closed v2 transaction field set remains unchanged (outline identity is bound through canonical prompt provenance), and malformed guidance permits `style_assets_unavailable + style_asset_malformed` with the verified selected STYLE.md resource, while schema-unsupported stays tokens-only. Link the strict runtime-canonical-owners reference and document all implemented command signatures, including explicit capability reservation, sample-only anchor publication, read-only computed prepare requests, and explicit migration.

- [x] Add installer tests using temporary user/project destinations with stale skills and source cache files. Run red before changing copy behavior.

```python
assert not (installed / 'scripts' / '__pycache__').exists()
assert (project / '.agents/skills/ppt-start/scripts/ppt_runtime.py').is_file()
assert installed_digest == filtered_source_digest
```

- [x] Implement filtered staged installation, backup/restore and partial-failure output; preserve unrelated user skills and unrelated project files. Do not recursively search drives.
- [x] Route all generation lifecycle operations in Skill instructions through the fixed CLI, forbid all run-local scripts including inline interpreter evaluation of run files, and document data staging, failure recovery and adapter limitations.
- [x] Run packaging regression tests and compile/help smoke tests. Commit.

### Task 5: Final review, integration verification and deployment

**Files:** Update docs/superpowers/plans/2026-09-07-ppt-runtime-artifact-hygiene.md and acceptance-evidence runtime evaluation Markdown; source fixes only when required by final review.

**Interfaces:** All task reports/commits feed a whole-change review against baseline cc8b1cf. Deployment uses the verified installer and explicit known targets only. No code-generating presentation run is used as an acceptance shortcut.

- [x] Review the complete implementation against the approved spec, resolve functional findings and run `py -3 -m unittest discover -s tests -q` once after integrated fixes.
- [x] Run a packaged runtime lifecycle in a clean temporary run and a source-deck fixture; record inventory and CLI outputs. Mark unavailable real host cases PENDING and record reasons, not synthetic PASS.
- [x] Run the updated host installer for Claude Code, Codex, DeepSeek and existing repo project copies; inspect actual discovery locations and filtered digests. External writes use the approved escalation mechanism.
- [x] Inspect `git worktree list --porcelain` and branches; do not delete the current worktree or any branch with unmerged work. User requested extra worktree cleanup and current inventory has only the main checkout.
- [x] Record exact test results, installed paths and actual remaining host limitations. Commit the final verification record and report the delivered behavior without overstating real-host acceptance.

Completed 2026-09-08. Source `219c13d`; installed version `1.0.0+codex.20260908.219c13d`. Final suite: 781 tests, 10 skipped, zero failures. All Important findings closed; 18 Skill trees and 2 Claude Agent copies verified. Actual host generation is PENDING, not synthetic PASS. See acceptance-evidence/2026-09-07/runtime-artifact-hygiene.md for exact results, the unchanged BLOCKED experiment, and deployment/backup evidence. No merge or push; the current branch remains intact.
