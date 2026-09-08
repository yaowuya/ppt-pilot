# Final fix wave — BASE 6fff469

Status: DONE. Implemented all three Important findings from `final-review.md`; scoped verification recorded below. Commit: `219c13d` — `fix: preserve owned anchor revisions and report installer failures` (six owned source/test files only). No Skill/instruction text changes or new control-state fields.

## Implementation

1. Anchor re-entry now reads the existing canonical `run.anchor.files` map for ordinary runs, or the bound source evidence's `anchor.files` map for source runs. Replacement is permitted only when the current sample bytes match that owner's exact lowercase SHA-256. Absent samples and exact publication replays retain their existing behavior. All samples are preflighted before writes; the existing store write barrier and CAS recheck both owner and sample bytes. The existing publication digest and guided approval rules are unchanged. Publication preserves prior production finals and does not record approval. A newly published digest needs a new applied approval decision before promotion.
2. Claude paired-scope snapshot directory creation and all copies now execute inside the existing `try/finally`, before any live destination mutation. The user-scope boundary catches preparation errors and adds the concrete Skills root and error to `failed`, allowing final `PARTIAL_FAILURE`, `updated`, `rolled_back`, and `failed` reporting after an earlier successful DeepSeek destination. Failed preparation does not claim rollback of untouched live bytes; partially prepared snapshots are removed.
3. The direct-child shadowing-Skill inventory moved from `update-hosts.ps1` into shared `packaging.ps1`. Both existing updater paths and DeepSeek invoke it. DeepSeek runs inventory before creating transaction/snapshot/install directories, prints the unwrapped offending path, and fails nonzero without modifying the marketplace or installed trees.

## TDD RED

Exact commands, before production edits:

```text
py -3 -m unittest discover -s tests -p test_ppt_runtime.py -k final_anchor
Ran 5 tests in 17.437s
FAILED (failures=3)
```

The ordinary and source owned-sample replacement tests both returned `BLOCKED / anchor_sample_conflict` with zero writes. The CAS race case failed before reaching the write because the same ownership check rejected the old sample. The two third-party/unknown-owner preservation tests already passed and establish the behavior that must remain preserved.

```text
py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_final_claude_snapshot_failure_after_deepseek_success_reports_and_cleans tests.test_tools_package.MultiSkillInstallerTests.test_final_deepseek_shadow_fails_before_any_mutation
Ran 2 tests in 5.089s
FAILED (failures=2)
```

The snapshot-copy injection ran after DeepSeek successfully installed its temporary destination, but output lacked `PARTIAL_FAILURE` and terminated at `injected snapshot copy failure`. DeepSeek accepted the duplicate `legacy-ppt/SKILL.md` declaring `name: ppt-start`, returned 0, and updated its temporary live destination.

## Iteration notes

- First anchor GREEN attempt: 5 tests in 19.544s, one fixture failure after successful source publication and stale-approval rejection. The new synthetic approval incorrectly reused approval_attempt 1; corrected it to the required unique next attempt 2. No approval validation was weakened.
- First packaging GREEN attempt: 2 tests in 3.562s, one failure because PowerShell wrapped the unhandled shadow-path error across lines. Added a full-line `failed:` message before rethrowing, so the exact path is directly readable. The Claude snapshot regression already passed.

## Final covering GREEN

All test commands use approved escalation solely for Windows temporary fixtures. No real user/project/plugin installation is performed; existing `-SkipRepoProject` isolation is retained, and tests needing source-project refresh copy a complete temporary source tree.

```text
py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests
Ran 17 tests in 46.551s
OK

py -3 -m unittest discover -s tests -p test_ppt_runtime.py -k anchor
Ran 10 tests in 36.476s
OK

py -3 -m unittest discover -s tests -p test_source_workflow_gate.py -k guided_anchor
Ran 2 tests in 0.243s
OK
```

```text
py -3.9 -m unittest discover -s tests -p test_ppt_runtime.py -k anchor
Ran 10 tests in 58.923s
OK
```

All final covering tests passed with no skips or warnings. Staged diff check also exited 0 before commit.

`git diff --check -- skills/ppt-start/scripts/_runtime_commands.py tests/test_ppt_runtime.py tests/test_tools_package.py tools/update-hosts.ps1 tools/install-deepseek-plugin.ps1 tools/packaging.ps1` exited 0; only repository LF/CRLF conversion notices.

## New focused tests

- `test_final_anchor_replaces_owned_ordinary_sample_requires_new_approval`
- `test_final_anchor_replaces_owned_source_sample_requires_new_approval`
- `test_final_anchor_preserves_ordinary_third_party_samples`
- `test_final_anchor_preserves_source_third_party_samples`
- `test_final_anchor_owned_sample_cas_rejects_change_before_write`
- `test_final_claude_snapshot_failure_after_deepseek_success_reports_and_cleans`
- `test_final_deepseek_shadow_fails_before_any_mutation`

The replacement tests retain actual prior sample bytes, prior final bytes, and prior approval; exercise read-only resume, reserve/bind/ingest/validation, replacement, idempotent replay, stale approval rejection, and successful promotion after a new approval of the publisher-returned digest. Source ownership is read exclusively from its evidence owner. Conflict tests compare the entire run file inventory byte-for-byte, and the CAS test changes the sample immediately before the real store writer.

## Scope and self-review

Six owned source/test files changed: `_runtime_commands.py`, `test_ppt_runtime.py`, `test_tools_package.py`, `update-hosts.ps1`, `install-deepseek-plugin.ps1`, `packaging.ps1`. Reviewed the complete scoped diff. No full-suite run, real-host acceptance, deployment, source tree cache creation, adapters, run-local executable code, dependencies, Office, or nested AI CLI execution. Parent-owned plan, Task 4 disclosure report, acceptance evidence, and process ledger remain untouched and uncommitted by this wave. The existing runtime class size remains the deferred maintainability concern already recorded in final review; no additional concern identified.
