# Claude Code Native Generator Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make PPT Pilot use only the active Claude Code session's prompt-only generator, with one safe local Git bootstrap only for an explicit Git-prerequisite launch failure and never a local Claude CLI login or fallback.

**Architecture:** The AI coordinator remains the sole owner of workflow state. The existing prompt-by-value `ppt-svg-generator` Agent remains deliberately tool-free; the coordinator's generation reference gains a narrowly scoped Claude Code launch-repair branch. This is documentation-and-contract work only: no new Python runtime, queue, adapter registry, Git helper, or state machine is introduced.

**Tech Stack:** Markdown Skill instructions, Claude Code custom-Agent frontmatter/body, Python `unittest`, PowerShell installer package-copy regression tests.

## Global Constraints

- Use only the host-native `ppt-svg-generator` route; no local `claude` CLI executable, authentication flow, browser login, API key prompt, or `claude -p` fallback.
- Only Claude Code may bootstrap Git, and only after an explicit named-Agent launch diagnosis that Git is missing before the Prompt is accepted.
- Bootstrap with exactly one `git init <safe-root>`; do not run `git add`, `commit`, `branch`, `remote`, `push`, `pull`, `fetch`, `clone`, `worktree`, or explicit `git config`.
- Never create `.git` inside `ppt-output/<deck-id>/`; the selected root must be an explicit presentation workspace or the `ppt-output/` ancestor permitted by the design.
- Retry the named Agent at most once, with the byte-identical frozen Prompt; generic launcher failures become page-local `generator_unavailable` without changing attempts.
- Preserve existing `PASS | INVALID | UNAVAILABLE`, AI-owned `run.json`, source metadata, SVG validation, partial-delivery, and editable-PPT contracts.
- Do not commit, push, or deploy to local Claude Code, Codex, or DeepSeek Harness during this work unless the user explicitly requests it later.

---

## File Structure

| File | Responsibility after this change |
|---|---|
| `skills/ppt-start/SKILL.md` | Short always-loaded rule: host-native generator only, no local CLI route; links generation-specific behavior to the existing reference. |
| `skills/ppt-start/references/visual-brief-and-generation.md` | Single detailed owner for Claude Code fresh-context launch, safe-root selection, one bootstrap/retry, and page-local downgrade. |
| `skills/ppt-start/references/workflow.md` | Explains that a pre-Prompt host launch/bootstrap is not a real generation attempt and cannot create hidden retries. |
| `skills/ppt-start/references/ai-state.md` | Defines optional AI evidence describing a successful Git bootstrap without creating a new state-machine owner. |
| `hosts/claude-code/agents/ppt-svg-generator.md` | Keeps the isolated generator prompt-only; explicitly excludes local CLI, Git, authentication, files, and workspace access. |
| `README.md`, `docs/ARCHITECTURE.md`, `docs/INSTALL.md`, `docs/RESILIENT-WORKFLOW.md`, `docs/USER-GUIDE.md` | Short public explanations of active-session generation and honest downgrade; no duplicate command recipe. |
| `tests/test_ai_workflow_contract.py` | Static contract for exactly one detailed host-bootstrap owner, no CLI fallback, no unsafe Git operations, fixed retry/attempt semantics. |
| `tests/test_skill_package.py` | Prompt-only generator Agent contract, including no setup capability inside the Agent. |
| `tests/test_tools_package.py` | Installer regression proving the source Agent containing the hardened contract is deployed byte-exactly. |

### Task 1: Encode the host-native generation boundary

**Files:**
- Modify: `skills/ppt-start/SKILL.md:8-12,39-44,52-54`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md:23-39`
- Modify: `skills/ppt-start/references/workflow.md:27-30`
- Modify: `skills/ppt-start/references/ai-state.md:35-44,57-75`
- Modify: `hosts/claude-code/agents/ppt-svg-generator.md:7-13`
- Modify: `tests/test_ai_workflow_contract.py:60-84`
- Modify: `tests/test_skill_package.py:62-73`

**Interfaces:**
- Consumes: Existing AI-owned page record (`slides[slide_id]`), frozen Prompt bytes, `generator_unavailable`, and the installed `ppt-svg-generator` Agent.
- Produces: A documented coordinator-only sequence: named-Agent launch → optional one-time `git init` → one same-Prompt relaunch → page-local unavailable result.
- Invariant: The Agent itself remains `Prompt bytes → exactly one XML fence`; no Git/CLI/auth/filesystem action is delegated to it.

- [x] **Step 1: Add failing static contract coverage**

In `tests/test_ai_workflow_contract.py`, add this test directly after `test_ai_state_is_the_single_workflow_owner_and_tools_have_three_outcomes`:

```python
def test_claude_native_generator_has_one_safe_git_bootstrap_route(self):
    skill = read_text(PPT_START / "SKILL.md")
    visual = read_text(PPT_START / "references" / "visual-brief-and-generation.md")
    workflow = read_text(PPT_START / "references" / "workflow.md")
    state = read_text(PPT_START / "references" / "ai-state.md")

    self.assertIn("ppt-svg-generator", skill)
    self.assertIn("local CLI", skill)
    self.assertEqual(visual.count("git init"), 1)
    for token in (
        "Claude Code",
        "host_git_required",
        "ppt-output",
        "same frozen Prompt",
        "generator_unavailable",
        "claude_code_local_git_initialized",
    ):
        self.assertIn(token, visual + "\n" + workflow + "\n" + state)
    self.assertRegex(workflow, r"(?:不增加|不消耗).*attempts")
    for forbidden in (
        "git add",
        "git commit",
        "git branch",
        "git remote",
        "git push",
        "git pull",
        "git fetch",
        "git clone",
        "git worktree",
        "git config",
    ):
        self.assertIn(forbidden, visual)
```

Use the repository's current Chinese narrative around these stable English command/field literals; do not introduce a parser or a runtime implementation merely to satisfy the test.

In `tests/test_skill_package.py`, extend `test_claude_generator_agent_has_a_prompt_only_contract` with:

```python
for token in (
    "local CLI executable",
    "Git command",
    "authentication flow",
    "coordinator, not this generator",
):
    self.assertIn(token, text)
```

- [x] **Step 2: Run the new tests and confirm the documented behavior is absent**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract.AIWorkflowContractTests.test_claude_native_generator_has_one_safe_git_bootstrap_route tests.test_skill_package.SkillPackageTests.test_claude_generator_agent_has_a_prompt_only_contract -v
```

Expected: the new assertions fail because the current reference has no bounded Git-bootstrap route and the Agent does not explicitly name local CLI/Git/authentication exclusion.

- [x] **Step 3: Add the minimal coordinator-owned instructions**

Update `skills/ppt-start/SKILL.md` so its ownership section says that the active host session—not a local CLI process—is the Claude generation route. Keep the top-level version short and direct readers doing generation to `visual-brief-and-generation.md`.

Replace the existing two-paragraph `## Generator 边界` section in `visual-brief-and-generation.md` with a detailed `## Host-native generator boundary` section containing the exact literals `host_git_required`, `same frozen Prompt`, `generator_unavailable`, and `claude_code_local_git_initialized`, plus this decision flow in Chinese prose and one command block:

```text
1. Give the complete frozen Prompt by value to the installed ppt-svg-generator Agent.
2. If Claude Code reports an explicit Git prerequisite before accepting the Prompt:
   - choose the known presentation workspace root only when it is an ancestor of run_dir;
   - when that root equals run_dir, require run_dir.parent.name == "ppt-output" and use the parent instead;
   - run exactly once: git init <safe-local-root>;
   - record claude_code_local_git_initialized, scope, and host_git_required in the page evidence;
   - relaunch the named Agent once with byte-identical Prompt bytes.
3. On any other launcher failure, absent Git executable, unsafe root, bootstrap failure, or second launch failure:
   record generator_unavailable, leave attempts unchanged, and continue siblings.
```

Immediately after the block, state all disallowed Git operations as literal commands: `git add`, `git commit`, `git branch`, `git remote`, `git push`, `git pull`, `git fetch`, `git clone`, `git worktree`, and `git config`. State that no local Claude CLI executable, authentication flow, or browser login is a route in this workflow.

Update `workflow.md` to distinguish a pre-Prompt host launch from a real generator call: the failed launch and one permitted bootstrap/relaunch remain one coordinator action, do not increment `attempts`, and cannot become polling or a generic retry loop.

Update `ai-state.md` after the current page-evidence example with the optional audit shape:

```json
"generator_setup": {
  "kind": "claude_code_local_git_initialized",
  "scope": "presentation_workspace_root",
  "trigger": "host_git_required"
}
```

State that it is only evidence on the existing page record, not a new control state; it appears only after a successful bootstrap, and a failed bootstrap leaves `attempts` unchanged with `generator_unavailable`.

Update the Agent body after its existing workspace-isolation paragraph with this exact sentence:

```text
Do not invoke a local CLI executable, any Git command, or an authentication flow. The coordinator, not this generator, handles all host setup.
```

Do not give the Agent a Git tool, CLI tool, filesystem tool, workspace path, or a retry instruction.

- [x] **Step 4: Run core contract tests and confirm green**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract tests.test_skill_package -v
```

Expected: all tests pass; existing short-skill, deleted-runtime, prompt-only Agent, and active-link checks remain green.

- [x] **Step 5: Inspect the diff for prohibited control surfaces**

Run:

```bash
git diff -- skills/ppt-start/SKILL.md skills/ppt-start/references/visual-brief-and-generation.md skills/ppt-start/references/workflow.md skills/ppt-start/references/ai-state.md hosts/claude-code/agents/ppt-svg-generator.md tests/test_ai_workflow_contract.py tests/test_skill_package.py
```

Expected: no Python runtime, no Git helper script, no host registry, no local CLI invocation, and no change to the generator's prompt-by-value boundary.

### Task 2: Keep public guidance and installed copies aligned

**Files:**
- Modify: `README.md:65-73`
- Modify: `docs/ARCHITECTURE.md:23-33,86-89`
- Modify: `docs/INSTALL.md:48-54`
- Modify: `docs/RESILIENT-WORKFLOW.md:18-24`
- Modify: `docs/USER-GUIDE.md:25-36`
- Modify: `tests/test_ai_workflow_contract.py:137-147`
- Modify: `tests/test_tools_package.py:85-122`

**Interfaces:**
- Consumes: The single detailed coordinator behavior from `visual-brief-and-generation.md` and the source Agent at `hosts/claude-code/agents/ppt-svg-generator.md`.
- Produces: Public docs that accurately say users need no local Claude CLI login, and an installer proof that the exact hardened Agent ships to Claude scopes.
- Invariant: Public documents summarize behavior and link to the Skill; they do not duplicate the `git init` command sequence or suggest Git is a normal content-workflow prerequisite.

- [x] **Step 1: Add failing public/install contract coverage**

Add this test to `tests/test_ai_workflow_contract.py` before `test_active_markdown_links_resolve`:

```python
def test_public_docs_keep_claude_generation_host_native(self):
    for path in (
        ROOT / "README.md",
        ROOT / "docs" / "ARCHITECTURE.md",
        ROOT / "docs" / "INSTALL.md",
        ROOT / "docs" / "RESILIENT-WORKFLOW.md",
        ROOT / "docs" / "USER-GUIDE.md",
    ):
        text = read_text(path)
        with self.subTest(path=path.relative_to(ROOT)):
            self.assertIn("local Claude CLI", text)
            self.assertIn("generator_unavailable", text)
```

In `tests/test_tools_package.py`, extend `test_update_installs_three_skills_retires_sdk_and_preserves_unrelated_agent` after the existing byte comparison:

```python
installed_agent = (claude_agents / "ppt-svg-generator.md").read_text(encoding="utf-8")
self.assertIn("local CLI executable", installed_agent)
self.assertIn("coordinator, not this generator", installed_agent)
```

- [x] **Step 2: Run the public/install tests and confirm they fail first**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract.AIWorkflowContractTests.test_public_docs_keep_claude_generation_host_native tests.test_tools_package.InstallerTests.test_update_installs_three_skills_retires_sdk_and_preserves_unrelated_agent -v
```

Expected: the public-doc test fails before documentation is updated; the installer test may fail until Task 1's Agent text exists.

- [x] **Step 3: Add concise public descriptions without duplicating the protocol**

Apply these content rules:

- `README.md`: after the fresh-context generator workflow bullet, state that Claude Code uses the active session's installed Agent; users do not need a local Claude CLI login. Refer to the Skill for its conditional host setup and page-level downgrade.
- `docs/ARCHITECTURE.md`: in “SVG generation and tools”, identify the native Agent as the only Claude route and say the coordinator may perform a bounded local Git bootstrap only for an explicit Claude Code launch prerequisite; generic failure remains `generator_unavailable`.
- `docs/INSTALL.md`: in “Claude generator”, state that installation provides the prompt-only Agent, uses the active Claude Code session authorization, neither needs nor installs a local Claude CLI login path, and exposes a page-local `generator_unavailable` rather than treating missing host capability as an install failure.
- `docs/RESILIENT-WORKFLOW.md`: extend the unavailable-tool paragraph so a missing host generator—including failed safe Git bootstrap—is page-local `generator_unavailable`, not a global blocker or attempt.
- `docs/USER-GUIDE.md`: near its page-generation guidance, say the user should not authenticate a local CLI; Claude Code handles its own active-session Agent route and reports a page-local downgrade if unavailable.

Each public document must contain the literals `local Claude CLI` and `generator_unavailable` so the contract test stays meaningful. Do not include a shell command for `git init` outside the single detailed Skill reference.

- [x] **Step 4: Run public/install tests and packaging regression**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract tests.test_tools_package -v
```

Expected: public guidance and package-copy tests pass; the installer still copies all three skills and the same hardened Agent byte-for-byte while retiring the SDK Agent.

- [x] **Step 5: Verify docs remain navigable and free of a local CLI execution route**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract.AIWorkflowContractTests.test_active_markdown_links_resolve -v
```

Expected: PASS.

Then inspect only executable-looking local Claude commands:

```bash
git grep -n -E '^[[:space:]]*claude([[:space:]]+-p|[[:space:]]+login|[[:space:]]+auth)' -- README.md docs skills hosts
```

Expected: no matches. Mentions that explain the prohibition are acceptable only as prose, not runnable commands.

### Task 3: Verify the whole migration without deploying it

**Files:**
- Modify: `docs/superpowers/specs/2026-09-25-claude-code-native-generator-bootstrap-design.md` only if testing uncovers a real contradiction; otherwise no source edits.
- Verify: all files from Tasks 1–2.

**Interfaces:**
- Consumes: New static host-generation contract and existing installer/tree-digest tests.
- Produces: Evidence that no code-level workflow owner or local-host deployment was introduced.

- [x] **Step 1: Run the focused host-generation regression set**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract tests.test_skill_package tests.test_tools_package tests.test_interaction_protocol -v
```

Expected: PASS. In particular, the one-real-generator-call rule, no deleted runtime surfaces, agent package behavior, and installer behavior remain intact.

- [x] **Step 2: Run the complete test suite**

Run:

```bash
python -B -m unittest discover -s tests -v
```

Expected: PASS with only documented environment-capability skips. Record the exact run/skipped counts from the command output; do not describe skipped Office/reference tests as passed runtime generation.

- [x] **Step 3: Run final static diff checks**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

Run:

```bash
git diff --name-only
```

Expected: only the documented Skill, Agent, public docs, tests, design spec, and implementation plan paths appear; no `scripts/*.py` runtime owner, new host registry, or local deployment artifact is created.

- [x] **Step 4: Report the result without deploying**

Report:

```text
- Claude Code now uses only its active-session prompt-only Agent.
- A Git-less explicit Claude Code Agent-launch prerequisite can bootstrap exactly one private local Git repository outside the run artifact tree and retry once.
- No new local host deployment was performed for this change.
- List exact test commands and their outcomes.
```

Do not run `tools/update-hosts.ps1`, `tools/install-deepseek-plugin.ps1`, `git commit`, or `git push` in this task.

## Plan Self-Review

- **Spec coverage:** Task 1 implements every host/Git/attempt/nonblocking/Agent boundary in the approved spec. Task 2 covers public guidance and installed-copy fidelity. Task 3 proves the complete repository remains compatible without executing deployment.
- **Placeholder scan:** No TBD/TODO/generalized validation steps are present; each test, expected outcome, and documentation insertion is named explicitly.
- **Type/contract consistency:** `claude_code_local_git_initialized`, `host_git_required`, and `generator_unavailable` use the exact literals defined in the design. The only generator Agent name is `ppt-svg-generator`; no retired SDK Agent, CLI fallback, or new runtime interface appears.
