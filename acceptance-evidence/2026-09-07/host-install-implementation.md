# Task 4 implementation report

## Implemented

- Routed `ppt-start` visual generation and recovery through the installed fixed `ppt_runtime.py` CLI, documented every implemented command signature, read-only `resume.result.prepare_request`, explicit capability reservation, sample-only anchor publication, shared `sha256:` anchor evidence, explicit v1 migration, and the closed recovery journal.
- Aligned the artifact prose with the unchanged closed schema-v2 transaction field set and the runtime-canonical-owner guidance. `ppt-editable` now audits before consuming prior-run artifacts and forbids evaluating run files or creating run-local scripts/dependencies.
- Added `tools/packaging.ps1` as the single filtered inventory/copy/digest/staged-replacement implementation. `__pycache__`, `.pyc`, `.pyo`, and named test caches are excluded consistently.
- Reworked `update-hosts.ps1` to aggregate selected destinations, report path/version/file count/digest, refresh existing source-repository and explicit-project discovery scopes by default, pair project Claude Skills with the Agent, update an explicit physical `CodexPluginRoot` without replacing unrelated plugin content, and return nonzero `PARTIAL_FAILURE` for mixed results.
- Result lists name actual destination paths. A successful Skill remains in `updated` if a later sibling fails; only a destination whose prior bytes were restored is placed in `rolled_back`, and the failing destination appears in `failed`. A failed Claude Agent update stops its paired Claude Skill refresh, leaving those Skill destinations unchanged.
- Updated the DeepSeek installer to use the shared filtered packaging implementation while retaining its plugin/marketplace transaction rollback.
- Preserved the old project flags for compatibility. `RepoRoot` is always the immutable source Skill tree; its already-existing `.agents/.claude` discovery trees are separate default project destinations. Extra projects with no existing discovery scope are skipped.

## TDD evidence

### RED

Command:

```text
py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_update_hosts_filters_cache_and_refreshes_existing_project_scopes tests.test_tools_package.MultiSkillInstallerTests.test_explicit_codex_plugin_root_updates_only_skills_and_preserves_unrelated_data tests.test_tools_package.MultiSkillInstallerTests.test_mixed_destination_failure_is_nonzero_partial_failure_and_rolls_back_failed_scope
```

Relevant pre-implementation output:

```text
ERROR ... copytree ... (fixture setup corrected to copy only the source package)
FAIL ... A parameter cannot be found that matches parameter name 'CodexPluginRoot'.
FAIL ... A parameter cannot be found that matches parameter name 'ProjectRoot'.
FAILED (failures=2, errors=1)
```

After correcting the hermetic source fixture, the expected behavioral failures were the missing `CodexPluginRoot`/`ProjectRoot` contracts and absence of `PARTIAL_FAILURE` aggregation. Additional existing rollback tests exposed and covered backup-preparation and post-copy restore flag ordering.

### GREEN

Commands and output:

```text
py -3 -m unittest tests.test_tools_package
Ran 26 tests in 30.982s
OK

py -3 -m unittest tests.test_workflow_contract tests.test_skill_package tests.test_path_compat_contract
Ran 41 tests
OK

py -3 -m compileall -q skills/ppt-start/scripts skills/ppt-editable/scripts
(no output; exit 0)

py -3 skills/ppt-start/scripts/ppt_runtime.py reserve-dispatch --help
py -3 skills/ppt-start/scripts/ppt_runtime.py publish-anchors --help
py -3 skills/ppt-start/scripts/ppt_runtime.py resume --help
py -3 skills/ppt-start/scripts/ppt_runtime.py migrate-v1 --help
(all printed the documented signatures; exit 0)
```

The final packaging tests use temporary user/project/plugin destinations. However, during the earlier Task 4 iteration, after default `RepoRoot` project refresh was introduced and before legacy tests were given hidden `-SkipRepoProject`, at least one updater regression ran with the real checkout as `RepoRoot`. That run refreshed the real repository discovery copies under `<REPO_ROOT>/.agents/skills` and `<REPO_ROOT>/.claude/skills`, created/refreshed `.claude/agents/ppt-svg-generator.md`, and created repository `skill-backups` entries timestamped `20260907225432`. The observed file times around 22:54 match that test sequence. It did not intentionally target the real user-level roots, Codex plugin cache, DeepSeek marketplace, or `<EXAMPLE_PROJECT>`; their state was not established by this task report. No cleanup or rollback of the repository copies was performed. Subsequent legacy tests pass hidden `-SkipRepoProject`, and the default source-repository refresh test uses a complete temporary source fixture.

## Installer CLI contract and recommended deployment

Run from an existing PowerShell session so `ProjectRoot` binds as a real string array:

```powershell
& '<REPO_ROOT>/tools/update-hosts.ps1' `
  -RepoRoot '<REPO_ROOT>' `
  -CodexPluginRoot '<USER_HOME>/.codex/plugins/cache/personal/ppt-pilot/local' `
  -ProjectRoot @('<REPO_ROOT>', '<EXAMPLE_PROJECT>')
```

This updates default user hosts, the explicit Codex plugin Skill tree, existing source-repository discovery scopes, and only existing discovery scopes in the extra project. A fresh host session is required afterward. Static digest equality is installation evidence, not fresh-session host acceptance.

## Files changed

- `skills/ppt-start/SKILL.md`
- `skills/ppt-start/references/workflow.md`
- `skills/ppt-start/references/artifact-contract.md`
- `skills/ppt-start/references/runtime-canonical-owners.md`
- `skills/ppt-editable/SKILL.md`
- `tools/packaging.ps1`
- `tools/update-hosts.ps1`
- `tools/install-deepseek-plugin.ps1`
- `tests/test_tools_package.py`
- `README.md`
- `docs/INSTALL.md`

## Self-review and limitations

- Reviewed the scoped diff and ran `git diff --check`; no whitespace errors.
- Pressure round 1 identified two instruction gaps. The final docs now make existing-run audit precede dashboard writes, stop response staging/ingest/manual owner edits on contamination, stop when the fixed runtime is absent, and route `generator_unavailable` persistence through the fixed runtime after safe preflight. The controller owns the requested re-run.
- The skill validator script could not run because its external environment lacks `yaml` (`ModuleNotFoundError`). Existing repository skill/package contract tests passed instead.
- Fresh-session host acceptance, instruction pressure tests, and deployment to actual roots remain controller-owned and were intentionally not performed here.

## Fix round 1 — review d2e508d

All six Important findings in `task-4-review.md` were addressed:

- corrected the closed style blocker tuple so `style_asset_malformed` permits verified `tokens.json` or `STYLE.md`, while `style_asset_schema_unsupported` remains tokens-only;
- added explicit backup-moved/restored exception state, so a pre-move backup-preparation failure is never mislabeled `rolled_back`;
- made Claude Agent plus all selected Claude Skills a paired scope: any later Skill failure restores the old Agent and every Skill target, including a deliberately different old Agent byte sequence;
- rejects and names direct-child shadowing Skill paths before any selected discovery-root update;
- changed DeepSeek Skill replacement to the filtered, verified staged `Install-PptPilotTree` path; the outer plugin/marketplace transaction still restores the complete live plugin on failure;
- refreshed editable GREEN provenance from the supplied fresh no-history exercise, preserving historical RED cases and recording the actual current Skill hash and `gpt-5.6-sol` model.

### Fix-round RED

```text
py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_backup_preparation_failure_is_failed_but_not_rolled_back tests.test_tools_package.MultiSkillInstallerTests.test_project_claude_scope_restores_agent_when_later_skill_copy_fails tests.test_tools_package.MultiSkillInstallerTests.test_direct_child_shadowing_skill_fails_and_names_path_before_update tests.test_tools_package.MultiSkillInstallerTests.test_deepseek_staged_copy_failure_preserves_live_skill_tree
FFFF
FAILED (failures=4)
```

Observed failures matched the review: premature rollback labeling, new Agent left beside stale Skills, shadow accepted with exit 0, and injected staged-copy failure not reached because DeepSeek still copied directly.

The editable provenance contract was also red before its fixture update because the stored Skill hash/model described the prior run; the initially mistyped unittest class name produced a loader error, after which the exact reviewed test was run with the correct `PptEditablePressureFixtureTests` class.

### Fix-round GREEN

```text
py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_backup_preparation_failure_is_failed_but_not_rolled_back tests.test_tools_package.MultiSkillInstallerTests.test_project_claude_scope_restores_agent_when_later_skill_copy_fails tests.test_tools_package.MultiSkillInstallerTests.test_direct_child_shadowing_skill_fails_and_names_path_before_update tests.test_tools_package.MultiSkillInstallerTests.test_deepseek_staged_copy_failure_preserves_live_skill_tree
Ran 4 tests in 8.465s
OK

py -3 -m unittest tests.test_ppt_editable_package.PptEditablePressureFixtureTests.test_pressure_green_outputs_are_hash_locked_and_compliant tests.test_workflow_contract.WorkflowContractTests.test_style_blocker_tuple_allows_malformed_guidance_but_not_schema_guidance
Ran 2 tests in 0.009s
OK

py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests
Ran 15 tests in 42.364s
OK

py -3 -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_project_claude_scope_restores_agent_when_later_skill_copy_fails
Ran 1 test in 1.691s
OK
```

The last focused fix-round run strengthens the paired-scope assertion: the preexisting Agent bytes are intentionally different from source and all three stale Skill entrypoints are checked byte-for-byte after rollback. That fix-round run touched only temporary discovery roots. This statement does not erase the earlier real repository-project refresh disclosed above. Per controller direction, no full-suite rerun was performed.
