# Runtime artifact hygiene — verification record

Status: IMPLEMENTED, LOCALLY VERIFIED AND INSTALLED on 2026-09-08. Fresh-session live-host generation acceptance remains PENDING; this is not an all-host end-to-end success claim.

Verified source: `219c13d931f8aae248fb577c2d4156686b08fd2b`. Installed version: `1.0.0+codex.20260908.219c13d`. Subsequent completion-record edits do not change installed source bytes.

## Scope

The approved change supplies installed deterministic runtime operations, rejects run-local code and unowned artifacts, and synchronizes known Claude Code, Codex and DeepSeek discovery scopes. It does not delete historical presentation artifacts or claim that a host's unrestricted shell is technically disabled outside the plugin's entry points.

Implementation baseline: `cc8b1cf`. Design and plan: `docs/superpowers/specs/2026-09-07-ppt-runtime-artifact-hygiene-design.md` and `docs/superpowers/plans/2026-09-07-ppt-runtime-artifact-hygiene.md`.

## Completed task evidence

| Task | Commits | Verification |
|---|---|---|
| Shared artifact firewall and entry points | `decbb6b`, `2c0963e` | Initial focused run: 115 tests, 3 skipped, remaining passed. Fix regression: 4 failing cases before fix; 24 focused tests passed after fix. Fresh scoped review clean. |
| Production prompt/SVG/generation modules | `bcb9d33`, `a954c4f` | 145 focused tests passed; existing golden prompt fixtures unchanged. Square-cap/dash-list fix: 16 failing subtests before fix; 8 runtime tests passed after fix. Fresh scoped review clean. |
| Runtime facade, canonical owners and lifecycle | `2233f82` | Runtime 28 tests, generation 36, prompt 103, source gates 44 passed; two Windows symlink privilege skips. Independent review findings were corrected below. |
| Runtime review corrections | `dccbb15`, `20daf77` | Actual Python 3.13 and 3.9.13: runtime 41 tests, modules 8 and source gate 46; each runtime/source run has one Windows symlink privilege skip, remaining tests pass. Artifact suite: 9 pass on 3.13. Subsequent shared-identity fix: runtime anchor 5 and source 46 pass on both versions (source suite has one privilege skip per version). All Important findings closed by scoped re-review. |
| Workflow and transactional host packaging | `d2e508d`, `6fff469` | Packaging 26 and workflow/package/path 41 tests passed. Six Important review findings corrected; four new installer regressions RED to GREEN, 15 installer-class tests GREEN. Scoped re-review clean. Corrected implementation report: [host-install-implementation.md](host-install-implementation.md). |
| Final whole-change corrections | `219c13d` | All three Important findings corrected: owned-anchor revisions, Claude snapshot failure reporting, and DeepSeek shadowing-Skill inventory. Covering runs: installer 17, anchor 10 on both Python 3.13 and 3.9, source approval 2; all passed. [Final fix report](final-fix-report.md), [scoped re-review](final-fix-review.md). |

Final integrated tests on `219c13d`, completed 2026-09-08: `py -3 -m unittest discover -s tests -q` ran **781 tests in 221.581s**, `OK (skipped=10)`, exit 0. A tempfile ResourceWarning was emitted; final review inspected changed test resource ownership but could not attribute its origin to this change. Expected fixture CLI/help output was also printed. The earlier `6fff469` run passed 774 tests in 193.625s with 10 skipped. Final scoped re-review is clean, with no new Critical/Important breakage; installed-copy verification passed below. The large lifecycle class remains a nonblocking future maintainability item, not an unresolved functional finding.

Two existing installed-copy fixture methods were additionally invoked unchanged with a read-only CLI-output recorder. `test_real_lifecycle_and_replays` passed with 13 command events and 20 run files; `test_source_guided_accepts_published_anchor_evidence` passed with 9 command events and 23 run files. Full status/write-path and inventory evidence is in `runtime-fixture-events.json`. Fixture directories were cleaned by registered test cleanup; no script/dependency artifact was written inside either presentation run. The first console capture had Chinese-name encoding loss and was discarded; the retained repeat uses lossless ASCII-escaped JSON. These are hermetic fixtures with synthetic host/QA declarations, not live generation or rendered visual acceptance.

The final commit's ordinary and source anchor-revision fixtures also passed; `anchor-revision-events.json` records 10/12 command events and 20/23 run files respectively. Each trace includes one expected BLOCKED promotion with stale approval and later successful promotion after a new approval. The unchanged test methods retain prior samples/finals and use the returned publisher identity; no sample deletion is used to bypass revision behavior.

## Instruction pressure verification

Fresh no-history text-only exercises used gpt-5.6-sol and read canonical Skill instructions; no slides, Office or generator calls were made. These observations do not establish actual host acceptance.

| Exercise | Observed result |
|---|---|
| No-guidance control, three runtime scenarios | All three chose noncompliant temporary-code or unsafe-generator routes. |
| First updated-instruction exercise | Missing-helper route stopped; contaminated-run response still proposed dashboard writes before audit and generator blocker ownership was unclear. Instructions were corrected before release. |
| Repeated same scenarios on d2e508d | All three comply: audit first; known code/dependencies stop all writes and remain preserved; missing fixed runtime stops; unsafe DeepSeek generation goes through fixed prepare-batch to a canonical blocker. |
| Editable instruction rerun on d2e508d | All three comply; exact responses below. Current SKILL.md raw SHA-256: `83d4ebfcd43a04ed4eb5b8e0a373799c9df51b956a85b3a83df736a13a7aa353`. |

Editable responses, recorded verbatim:

1. `GENERATED_UNVERIFIED — publish <deck-id>-editable-unverified.pptx.`
2. `BLOCKED — svg_attribute_unsupported — Publish no new deck.`
3. `Publish <deck-id>-editable-unverified.pptx; preserve verified final unchanged.`

The first full integration run on d2e508d ran 769 tests in 188.326s: one failure, 10 skipped. The failure was stale editable pressure provenance bound to the previous Skill bytes. A fresh exercise was performed above before any evidence refresh; the final 781-test run passed afterward. The final fix changed no Skill text, so the refreshed pressure evidence still matches the installed instructions. Exact exercise reports are preserved alongside this record. The external skill validator could not run without PyYAML; repository contract tests passed instead.

## Real-host acceptance boundary

Unit/subprocess lifecycle fixtures and text-only skill pressure tests are not fresh-session host acceptance. The adapter registry must fail closed for hosts without a registered and accepted adapter. Installation consistency alone cannot establish isolation or successful presentation generation.

| Host | Real fresh-session generation acceptance |
|---|---|
| Claude Code | PENDING; CLI availability and installed Agent byte matching are not a live generation test. |
| Codex | PENDING; no accepted host-native adapter is registered by this change. |
| DeepSeek Harness | PENDING; no accepted isolated adapter is registered by this change. |

## Preserved user data and worktrees

Read-only checks on 2026-09-07 found one worktree: `<REPO_ROOT>`, branch `codex/legacy-ppt-redesign`. The other local branch is `main`; neither branch is removed or reset by this change.

The 2026-09-08 final inventory confirms the same single normal checkout (`git-dir == git-common-dir == .git`) and the same two branches. There is no extra worktree to delete. Current branch and commits are preserved; no merge, push or PR was performed.

The current experiment under `<EXAMPLE_PROJECT>/ppt-output/example-optimized-run` is not modified by this work. It has 31 source-render PNGs without corresponding canonical path bindings. The latest read-only check used the actual installed user Skill's `ppt_workflow_gate.py --run-dir <experiment> --audit-run` on 2026-09-08: exit **2**, `BLOCKED`, `unexpected_run_artifact`, `reentry_stage: manuscript_review`, and 32 entries (exactly `.ppt-pilot/source-renders` plus `SRC-S001.png` through `SRC-S031.png`). Full result: [experimental-run-audit.json](experimental-run-audit.json). This supersedes the earlier source-copy audit; it is not treated as passing acceptance, nor is the policy weakened to make it pass. Historical scripts, dependencies, prior outputs and the original PPT are preserved.

## Verified deployment

Early-installation disclosure: the implementer confirmed that an early Task4 test invocation, after default RepoRoot refresh was enabled but before legacy tests received `-SkipRepoProject`, refreshed the real repository's `.agents/skills`, `.claude/skills`, paired `.claude/agents/ppt-svg-generator.md`, and repository backup directories at approximately 22:54 on 2026-09-07. This corrects earlier categorical “no real root writes” reporting. The old copies were backed up; no rollback or deletion was performed during reconciliation. Subsequent tests are isolated. The final verified deployment below supersedes those early copies.

The approved elevated invocation of `tools/update-hosts.ps1` returned exit 0 / SUCCESS on 2026-09-08 with the version above, the following explicit roots, and both repository/experimental ProjectRoot values. No broad drive or plugin-cache discovery was used. Before mutation, 23 known tree/backup roots (2,165 entries) and 11 control/snapshot/Agent/marketplace paths passed containment and no-reparse checks.

- `<USER_HOME>/.agents/skills`
- `<USER_HOME>/.claude/skills` and its paired Claude Agent
- `<REPO_ROOT>/.agents/skills`
- `<REPO_ROOT>/.claude/skills` and its paired Claude Agent
- `<USER_HOME>/.agents/plugins/plugins/ppt-pilot`
- `<USER_HOME>/.codex/plugins/cache/personal/ppt-pilot/local/skills` only; preserve the enclosing cache's Git data and unrelated content

`<EXAMPLE_PROJECT>` has no project-level `.agents/skills` or `.claude/skills` discovery directory. Passing it as an explicit project target must not create absent scopes just to claim an update.

The installer correctly skipped that experiment target. Each of the six existing Skill roots above contains these three source-identical trees:

| Skill | Files per root | Filtered SHA-256 |
|---|---:|---|
| ppt-start | 75 | `dcb8f48eb12a189ce0cdbbecb9934aa79cc899cb5e1c0f5c1d9e433677b91666` |
| ppt-editable | 24 | `93700baa1ed3a0b5cd70188a7a1b1fafe917a667b3baad58e0e3906193396985` |
| ppt-style-extract | 16 | `cf1196d53658c0ffe3203500c17139c2933c10aec6df61edce147e9c6aa595b2` |

Independent post-install checks confirmed 18/18 matching trees, zero `__pycache__`/`.pyc`/`.pyo` residues, 2/2 matching Claude Agent files, and 6/6 installed runtime CLI help checks with the implemented commands. The paired Agent raw SHA-256 is `6dfe51421c974f8f19f9b6c1ea1e4d1596792255115e100977c217b54afe62e7`. Protected Codex cache `.git/HEAD`, `.git/index`, and README hashes are unchanged. DeepSeek's manifest names `ppt-pilot` and records the exact installed version.

All 18 immediately preceding Skill trees are preserved in verified matching backups. The installer pruned older retained backups according to its one-previous-version policy; these older backup copies are no longer retained. User presentation artifacts were not part of that cleanup.

Evidence: [installer output](install-output.txt), [pre-install tree hashes](pre-install-trees.json), [post-install trees, backups and protected files](deployment-verification.json), [installed CLI smoke checks](installed-cli-smoke.json). Start a **new session** in each host to load replaced Skill/Agent instructions. No host process was restarted, and byte equality does not establish live isolation or generation acceptance.

## Completion housekeeping

This record preserves the final review, fix evidence, pressure exercises, deployment results, and every coordinator ruling. After exact-path containment, ancestor/child no-reparse checks and byte-equal preservation of the corrected Task 4 report, only this plan's generated `.superpowers/sdd/2026-09-07-ppt-runtime-artifact-hygiene` process workspace was removed (33 files). No sibling workspace or presentation run was included. The corrected formerly tracked Task 4 report is retained as `host-install-implementation.md`; all 13 exact ledger rulings are in [coordinator-rulings.md](coordinator-rulings.md). Generated review diffs are reproducible from the recorded Git ranges; nonessential transient briefs/ledger are not separately retained.

## Coordinator rulings and their costs

1. Use unittest instead of pytest because the default interpreter lacks pytest and the tests are unittest-compatible. Cost: different test invocation, not reduced coverage.
2. Work in the existing feature checkout because the user requested removing extra worktrees. Cost: no additional branch/worktree isolation; preserve unrelated edits.
3. Initially create task briefs with apply_patch because Bash was absent from PATH, then use the discovered Git Bash helper. Cost: initial process artifacts were manually assembled and later checked.
4. BLOCKED responses disclose actual recorded blocker/failure or interrupted-commit writes; conformance/precondition failures remain zero-write. Cost: clients must inspect the truthful writes list rather than assume every BLOCKED response changed nothing.
5. Require an explicit capability receipt on reserve-dispatch because exact durable v2 owners do not store host identity and dispatch-plan is read-only. Cost: one additional CLI argument.
6. Add explicit migrate-v1 rather than mutating resume. Cost: one fixed command and corresponding tests; preserves read-only resume.
7. Keep exact v2 transaction fields; bind outline identity through canonical prompt provenance instead of adding a contradictory extra field. Cost: clarify older prose and retain strict canonical reconstruction.
8. Put structured QA in the existing quality report and bind fix_attempts_for_candidate to the exact candidate/defect. Cost: strict serialization and fail-closed fallback when legitimate patch evidence is absent.
9. Add publish-anchors for sample-only publication before approval. Cost: one fixed command; final promotion still requires actual approval and current evidence.
10. Expose computed prepare_request under read-only resume. Cost: one result field; avoids host-authored hashing programs.
11. Permit style_asset_malformed to identify verified STYLE.md as well as tokens.json, while schema-unsupported remains tokens-only. Cost: narrow closed-tuple and documentation/test update; no invented resource attribution.
12. Add one immutable, closed recovery journal per recompose/fallback to preserve old/new shared-prompt bytes across crashes. Cost: one necessary JSON audit artifact and strict validation/CAS logic; no executable helper.
13. Require recomputed guided anchor evidence digests on source-deck gates as well as ordinary runs. Cost: legacy opaque/unbound anchor approvals require actual reapproval; old decisions are never retrofitted.
