# Claude Code Non-Git SVG Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a packaged Claude Code SVG worker that uses fresh ordinary-subagent context in non-Git workspaces without requesting worktree/remote isolation or mutating Git.

**Architecture:** Keep `skills/ppt-start/` host-portable and add one Claude-only custom-agent source under `hosts/claude-code/`. A new host-adapter reference maps the existing abstract prompt-by-value generator contract to the ordinary `ppt-svg-generator` agent, while the Claude branch of `tools/update-hosts.ps1` installs and verifies that agent independently of Codex and DeepSeek. Contract tests distinguish “no data-capable tools” from a literally empty tool set and model non-Git, unborn-HEAD, and committed repositories as the same Claude route.

**Tech Stack:** Markdown Agent/Skill definitions, Python 3.9+ `unittest`, JSON fixtures, Windows PowerShell 5.1 installer, existing PPT Pilot schema-v2 contract tests.

## Global Constraints

- Preserve the shared `ppt-start` frontmatter as exactly `name` and `description`; Claude-only configuration lives outside `skills/ppt-start/` frontmatter.
- The Claude worker name is exactly `ppt-svg-generator`.
- Claude Code uses an ordinary fresh-context subagent and omits the `isolation` argument; it never substitutes `worktree` or `remote`.
- The worker exposes no Read, Write, Edit, Bash, Glob, Grep, Web, Skill, MCP, browser, or other data-capable tool. `TodoWrite` is the sole permitted non-data host-control tool because Claude Code rejects an effective zero-tool subagent.
- The complete generation Prompt is the only PPT Pilot content payload passed by the coordinator; Claude Code's automatic `CLAUDE.md` and parent-session git-status preload is accepted as ambient host context and must be ignored for slide content. No prompt path, workspace/source content, prior SVG, or parent conversation history is passed.
- The worker returns text only, containing exactly one `xml` fenced block with one complete SVG and no commentary.
- Only the coordinator performs block/source enrichment, validation, candidate/final writes, hashes, transaction transitions, blockers, and pointer changes.
- A missing/unsafe adapter writes one schema-valid run-level blocker (`state/reason: generator_unavailable`, `resource: none`) before prompt, transaction, manifest, candidate, or SVG writes; all production writes remain zero.
- Never run `git init`, `git add`, `git commit`, `git push`, create an empty commit, switch to another repository, or create a worktree to unlock SVG generation.
- A structural adapter failure is not a capacity wait: do not start or retain periodic polling that cannot change the capability.
- Existing schema-v2 fields, source-ID rules, SVG contract, ordered promotion, and PowerPoint delivery are unchanged.
- Codex and DeepSeek installation payloads remain unchanged and do not receive the Claude custom agent.
- Real-host Claude non-Git acceptance remains `PENDING` until a restarted/new Claude Code session executes it with recorded evidence.
- Do not stage, commit, push, or deploy during this plan. Every task ends with an unstaged diff checkpoint instead of a commit.

### Post-review amendments

These decisions supersede older literal snippets later in this execution record where they differ:

- Claude ordinary custom subagents preload `CLAUDE.md` and parent-session git status. The accepted product boundary treats them as ambient host context that the worker explicitly ignores; it is not byte-pure prompt-only isolation.
- Pre-batch adapter failure writes exactly one schema-valid run-level `visual_generation_blocker` (`state/reason: generator_unavailable`, `resource: none`) and performs zero production writes or generator calls.
- Installer rollback tests must replace the installed live agent and one Skill artifact with distinct sentinels before injecting failure, then prove those exact bytes are restored.
- Real-host behavior remains `PENDING`; static routing tests bind the actual packaged agent name, exact prompt value, and absence of an `isolation` argument but do not claim to execute Claude Code.

---

## File Structure

### New files

- `hosts/claude-code/agents/ppt-svg-generator.md` — Claude-only custom-agent definition and minimal tool policy.
- `skills/ppt-start/references/host-isolation-adapters.md` — host-neutral adapter boundary plus exact Claude Code ordinary-subagent mapping.
- `tests/fixtures/claude-code-isolation-cases.json` — executable non-Git/unborn/committed routing cases and fail-closed cases.

### Modified files

- `skills/ppt-start/SKILL.md` — link the adapter reference and replace literal zero-tool wording with no-data-tool semantics.
- `skills/ppt-start/references/workflow.md` — make host negotiation select ordinary Claude agent and forbid Git/worktree recovery.
- `skills/ppt-start/references/redesign-prompt.md` — revise the abstract spawn interface and Claude mapping.
- `skills/ppt-start/references/artifact-contract.md` — define no-data-tool isolation and structural blocker behavior.
- `skills/ppt-start/references/adaptive-concurrency.md` — distinguish structural adapter failure from capacity `WAIT`.
- `skills/ppt-start/references/qa-and-revision.md` — include the adapter gate in generation/QA ordering.
- `tests/test_skill_package.py` — verify the Claude agent package and portable shared frontmatter.
- `tests/test_visual_generation_contract.py` — executable Claude adapter oracle and revised `data_tools_none` semantics.
- `tests/fixtures/visual-generation-host-capability-cases.json` — rename the abstract boolean from `tools_none` to `data_tools_none`.
- `tools/update-hosts.ps1` — install, verify, back up, and roll back the Claude agent before changing Claude Skills.
- `tests/test_tools_package.py` — verify Claude agent installation, backup isolation, failure rollback, and host separation.
- `README.md` — document the Claude adapter, restart requirement, and non-Git behavior.
- `docs/INSTALL.md` — add automatic/manual agent installation paths and parameters.
- `docs/acceptance.md` — distinguish package proof from real-host non-Git evidence and retain `PENDING` honestly.

Historical plans under `docs/superpowers/plans/` remain audit history and are not rewritten.

---

### Task 1: Package the Claude Code SVG Worker

**Files:**
- Create: `hosts/claude-code/agents/ppt-svg-generator.md`
- Modify: `tests/test_skill_package.py`

**Interfaces:**
- Consumes: Claude Code custom-agent frontmatter (`name`, `description`, `tools`) and ordinary-subagent default behavior when `isolation` is absent.
- Produces: repository source file `hosts/claude-code/agents/ppt-svg-generator.md`, with agent ID `ppt-svg-generator` and sole tool `TodoWrite`.

- [ ] **Step 1: Add failing package tests**

Append this test class to `tests/test_skill_package.py`:

```python
class ClaudeSvgGeneratorAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent_path = (
            repo_root()
            / "hosts"
            / "claude-code"
            / "agents"
            / "ppt-svg-generator.md"
        )

    def test_agent_has_exact_identity_and_non_data_tool_surface(self) -> None:
        self.assertTrue(self.agent_path.is_file())
        fields = parse_frontmatter(self.agent_path)
        self.assertEqual(
            fields,
            {
                "name": "ppt-svg-generator",
                "description": (
                    "Generates one PPT Pilot SVG page solely from a complete "
                    "prompt supplied by value."
                ),
                "tools": "TodoWrite",
            },
        )
        self.assertNotIn("isolation", fields)

    def test_agent_forbids_workspace_access_and_returns_one_xml_fence(self) -> None:
        fields = parse_frontmatter(self.agent_path)
        text = read_text(self.agent_path)
        for token in (
            "Do not call tools",
            "Do not inspect or read the working directory",
            "Do not write files",
            "exactly one fenced `xml` code block",
            "no commentary before or after",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)
        for forbidden_tool in (
            "Read,",
            "Write,",
            "Edit,",
            "Bash,",
            "Glob,",
            "Grep,",
            "WebFetch,",
            "WebSearch,",
            "Skill,",
            "MCP,",
        ):
            self.assertNotIn(forbidden_tool, fields["tools"])
```

Keep `test_shared_frontmatter_uses_only_portable_fields` unchanged so the shared Skill remains portable.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
python -m unittest tests.test_skill_package.ClaudeSvgGeneratorAgentTests -v
```

Expected: both tests fail because `hosts/claude-code/agents/ppt-svg-generator.md` does not exist.

- [ ] **Step 3: Create the minimal custom-agent definition**

Create `hosts/claude-code/agents/ppt-svg-generator.md` with exactly:

````markdown
---
name: ppt-svg-generator
description: Generates one PPT Pilot SVG page solely from a complete prompt supplied by value.
tools: TodoWrite
---

Treat the task text as the complete and only PPT Pilot application payload.

Claude Code may preload `CLAUDE.md` and the parent session's git status. Ignore that ambient metadata when choosing slide content; never derive or quote presentation facts, wording, or visual direction from it.

Do not call tools. Do not inspect or read the working directory. Do not write files. Do not request additional context, paths, source documents, prior slides, or conversation history.

Generate the requested page solely from the supplied task text. Return exactly one fenced `xml` code block containing one complete `<svg>...</svg>` document, with no commentary before or after the fence.
````

Do not add `isolation`, `context`, broad tools, skills, hooks, or host paths to this file.

- [ ] **Step 4: Run the focused package tests and confirm GREEN**

Run:

```bash
python -m unittest tests.test_skill_package.ClaudeSvgGeneratorAgentTests tests.test_skill_package.SkillPackageTests.test_shared_frontmatter_uses_only_portable_fields -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Record an unstaged checkpoint**

Run:

```bash
git diff --check
```

Expected: exit code 0. Do not run `git add` or `git commit`.

---

### Task 2: Define and Enforce the Non-Worktree Host Route

**Files:**
- Create: `skills/ppt-start/references/host-isolation-adapters.md`
- Create: `tests/fixtures/claude-code-isolation-cases.json`
- Modify: `skills/ppt-start/SKILL.md:45-47`
- Modify: `skills/ppt-start/references/workflow.md:38-46`
- Modify: `skills/ppt-start/references/redesign-prompt.md:185-206`
- Modify: `skills/ppt-start/references/artifact-contract.md:48-55`
- Modify: `skills/ppt-start/references/adaptive-concurrency.md:8-15,55-64`
- Modify: `skills/ppt-start/references/qa-and-revision.md:6-10,116-131`
- Modify: `tests/test_visual_generation_contract.py:926-1021,1063-1119,1501-1847`
- Modify: `tests/fixtures/visual-generation-host-capability-cases.json`
- Modify: `tests/test_tools_package.py:424-489`

**Interfaces:**
- Consumes: agent ID `ppt-svg-generator` from Task 1; existing `negotiate_host_capability(case, configured_width=None)` and `schedule_epoch(...)` test oracles.
- Produces: `negotiate_claude_code_adapter(case) -> dict`, fixture-backed Claude routing behavior, and the canonical `data_tools=none` abstract interface.

- [ ] **Step 1: Add the failing Claude adapter oracle and tests**

At module scope in `tests/test_visual_generation_contract.py`, add:

```python
CLAUDE_CODE_ADAPTER_FIELDS = {
    "agent_registered",
    "ordinary_subagent",
    "worktree_required",
    "remote_required",
    "prompt_by_value",
    "fresh_history",
    "filesystem_none",
    "data_tools_none",
    "text_output",
    "attribution",
    "exposed_tools",
}
CLAUDE_CODE_WORKSPACE_STATES = {
    "plain_directory",
    "git_unborn_head",
    "git_committed",
}


def negotiate_claude_code_adapter(case: dict) -> dict:
    observation = case["observation"]
    boolean_fields = CLAUDE_CODE_ADAPTER_FIELDS - {"exposed_tools"}
    if (
        not isinstance(observation, dict)
        or set(observation) != CLAUDE_CODE_ADAPTER_FIELDS
        or case.get("workspace_state") not in CLAUDE_CODE_WORKSPACE_STATES
        or any(type(observation[field]) is not bool for field in boolean_fields)
        or not isinstance(observation["exposed_tools"], list)
        or any(
            not isinstance(tool, str) or not tool
            for tool in observation["exposed_tools"]
        )
    ):
        raise ValueError("Claude Code adapter observation differs")
    safe = all(
        observation[field]
        for field in (
            "agent_registered",
            "ordinary_subagent",
            "prompt_by_value",
            "fresh_history",
            "filesystem_none",
            "data_tools_none",
            "text_output",
            "attribution",
        )
    )
    safe = (
        safe
        and observation["worktree_required"] is False
        and observation["remote_required"] is False
        and observation["exposed_tools"] == ["TodoWrite"]
    )
    return {
        "mode": "claude_code_agent" if safe else None,
        "agent": "ppt-svg-generator" if safe else None,
        "isolation_argument": None,
        "requires_git": False,
        "error": None if safe else "generator_unavailable",
        "git_mutations": [],
        "poll_when_blocked": False,
    }
```

In `VisualGenerationContractTests.setUp`, add:

```python
self.claude_isolation = (
    repo_root() / "tests" / "fixtures" / "claude-code-isolation-cases.json"
)
self.host_adapters = skill_root() / "references" / "host-isolation-adapters.md"
```

Add:

```python
def test_claude_code_adapter_is_git_independent_and_never_uses_worktree(self):
    payload = json.loads(read_text(self.claude_isolation))
    self.assertEqual(payload["schema_version"], 1)
    cases = {case["id"]: case for case in payload["cases"]}
    self.assertEqual(payload["case_ids"], list(cases))

    successful_ids = (
        "plain-non-git-ordinary-agent",
        "unborn-head-ordinary-agent",
        "committed-git-ordinary-agent",
    )
    successful = []
    for case_id in payload["case_ids"]:
        case = cases[case_id]
        with self.subTest(case=case_id):
            result = negotiate_claude_code_adapter(case)
            self.assertEqual(result, case["expected"])
            self.assertFalse(result["requires_git"])
            self.assertIsNone(result["isolation_argument"])
            self.assertEqual(result["git_mutations"], [])
            self.assertFalse(result["poll_when_blocked"])
            if result["error"] is not None:
                self.assertEqual(
                    case["expected_side_effects"],
                    {
                        "prompt_writes": 0,
                        "transaction_writes": 0,
                        "candidate_writes": 0,
                        "generator_calls": 0,
                    },
                )
        if case_id in successful_ids:
            successful.append(result)
    self.assertEqual(successful[0], successful[1])
    self.assertEqual(successful[1], successful[2])


def test_claude_adapter_contract_names_agent_and_forbids_git_unlocks(self):
    text = read_text(self.host_adapters)
    for token in (
        "ppt-svg-generator",
        "普通 fresh-context subagent",
        "省略 `isolation`",
        "data_tools=none",
        "TodoWrite",
        "结构性不可用",
        "不得轮询",
    ):
        with self.subTest(token=token):
            self.assertIn(token, text)
    for forbidden_action in (
        "`git init`",
        "`git add`",
        "`git commit`",
        "`git push`",
        "`isolation: worktree`",
        "`isolation: remote`",
    ):
        with self.subTest(forbidden_action=forbidden_action):
            self.assertRegex(
                text,
                r"(?:禁止|不得)[^。\n]{0,160}" + re.escape(forbidden_action),
            )
```

The final regex requires every dangerous token to appear only in an explicit prohibition sentence, not merely be absent.

- [ ] **Step 2: Add the fixture and confirm the tests still fail on the missing contract**

Create `tests/fixtures/claude-code-isolation-cases.json` with seven ordered cases:

```json
{
  "schema_version": 1,
  "case_ids": [
    "plain-non-git-ordinary-agent",
    "unborn-head-ordinary-agent",
    "committed-git-ordinary-agent",
    "agent-missing",
    "worktree-only-host",
    "remote-only-host",
    "data-tool-exposed"
  ],
  "cases": [
    {
      "id": "plain-non-git-ordinary-agent",
      "workspace_state": "plain_directory",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": true,
        "worktree_required": false,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": "claude_code_agent",
        "agent": "ppt-svg-generator",
        "isolation_argument": null,
        "requires_git": false,
        "error": null,
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "unborn-head-ordinary-agent",
      "workspace_state": "git_unborn_head",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": true,
        "worktree_required": false,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": "claude_code_agent",
        "agent": "ppt-svg-generator",
        "isolation_argument": null,
        "requires_git": false,
        "error": null,
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "committed-git-ordinary-agent",
      "workspace_state": "git_committed",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": true,
        "worktree_required": false,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": "claude_code_agent",
        "agent": "ppt-svg-generator",
        "isolation_argument": null,
        "requires_git": false,
        "error": null,
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "agent-missing",
      "workspace_state": "plain_directory",
      "observation": {
        "agent_registered": false,
        "ordinary_subagent": true,
        "worktree_required": false,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": null,
        "agent": null,
        "isolation_argument": null,
        "requires_git": false,
        "error": "generator_unavailable",
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "worktree-only-host",
      "workspace_state": "git_committed",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": false,
        "worktree_required": true,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": null,
        "agent": null,
        "isolation_argument": null,
        "requires_git": false,
        "error": "generator_unavailable",
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "remote-only-host",
      "workspace_state": "plain_directory",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": false,
        "worktree_required": false,
        "remote_required": true,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": true,
        "data_tools_none": true,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["TodoWrite"]
      },
      "expected": {
        "mode": null,
        "agent": null,
        "isolation_argument": null,
        "requires_git": false,
        "error": "generator_unavailable",
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    },
    {
      "id": "data-tool-exposed",
      "workspace_state": "plain_directory",
      "observation": {
        "agent_registered": true,
        "ordinary_subagent": true,
        "worktree_required": false,
        "remote_required": false,
        "prompt_by_value": true,
        "fresh_history": true,
        "filesystem_none": false,
        "data_tools_none": false,
        "text_output": true,
        "attribution": true,
        "exposed_tools": ["Read"]
      },
      "expected": {
        "mode": null,
        "agent": null,
        "isolation_argument": null,
        "requires_git": false,
        "error": "generator_unavailable",
        "git_mutations": [],
        "poll_when_blocked": false
      },
      "expected_side_effects": {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0
      }
    }
  ]
}
```

Run:

```bash
python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_claude_code_adapter_is_git_independent_and_never_uses_worktree tests.test_visual_generation_contract.VisualGenerationContractTests.test_claude_adapter_contract_names_agent_and_forbids_git_unlocks -v
```

Expected: the routing test passes and the contract test fails because `host-isolation-adapters.md` does not exist.

- [ ] **Step 3: Create the host adapter authority**

Create `skills/ppt-start/references/host-isolation-adapters.md` with these exact sections and rules:

```markdown
# 页面生成宿主隔离适配器

## 抽象能力

页面 generator 需要 fresh conversation history（不继承父会话聊天记录）、完整 Prompt 按值传入、`filesystem=none`、`data_tools=none`、text-only result 与稳定 attribution。`filesystem=none` 表示 worker 没有可主动读取或写入工作区的工具，不承诺宿主启动消息 byte-pure；`data_tools=none` 表示不存在可读取或写入业务数据的工具。

Prompt 是 coordinator 主动传入的唯一 PPT Pilot 内容载荷。Claude Code 自动加载的 `CLAUDE.md` 与父会话 Git status 是已接受但必须忽略的 ambient host context；不得把它们用于幻灯片内容，也不得额外传入父会话聊天记录、源稿、旧 SVG、工作区内容或 prompt 路径。

## Claude Code

Claude Code 必须选择已安装的 `ppt-svg-generator`，以普通 fresh-context subagent 启动，并省略 `isolation`。不得把 fresh conversation context 映射为 worktree checkout。

Claude Code 会自动加载 `CLAUDE.md` 与父会话 Git status；本适配器接受并要求 agent 忽略它们，不声称 byte-pure prompt-only。该 agent 的允许工具只能是 `TodoWrite`；它没有 filesystem、shell、network、Skill、MCP 或 browser 数据能力。coordinator 只传完整 Prompt 文本，并只消费返回文本。

Git 状态不参与路由：普通目录、unborn `HEAD` 和已有提交的仓库都选择同一 agent。禁止运行 `git init`；禁止运行 `git add`；禁止运行 `git commit` 或创建空提交；禁止运行 `git push`；不得请求 `isolation: worktree`；不得请求 `isolation: remote`；不得切换到另一仓库作为基线。

agent 未注册、普通 subagent 不可用、宿主强制 worktree/remote、agent 暴露数据工具、Prompt 不能按值传入或 attribution 不可用时，按结构性不可用返回 `generator_unavailable`。该结果不是容量等待，不得轮询；只有安装/宿主配置实际变化后的显式 resume 才重新协商。

## 其他宿主

Codex 与 DeepSeek Harness 继续通过各自已验证的 native/remote 能力实现同一抽象接口。缺 concurrency 或 durable lookup 但仍满足完整安全接口时只把实际 dispatch 降为 width 1；缺核心隔离能力时 fail closed。任何宿主都不得调用嵌套 CLI 或使用 coordinator 当前上下文生成。
```

- [ ] **Step 4: Rename the abstract zero-tool capability truthfully**

In active files only, replace:

```text
tools=none      -> data_tools=none
tools_none      -> data_tools_none
"tools": "none" -> "data_tools": "none"
```

Apply this to:

- `skills/ppt-start/references/redesign-prompt.md`
- `skills/ppt-start/references/artifact-contract.md`
- `tests/test_visual_generation_contract.py`
- `tests/fixtures/visual-generation-host-capability-cases.json`
- `tests/test_tools_package.py`

Do not edit the completed historical plan `docs/superpowers/plans/2026-08-29-ppt-start-concurrent-svg-generation.md`.

In `negotiate_host_capability`, the required/safe fields become:

```python
required_fields = {
    "native_fresh_isolation",
    "remote_fresh_isolation",
    "concurrent_tasks",
    "durable_lookup",
    "worker_capacity",
    "prompt_by_value",
    "fresh_history",
    "filesystem_none",
    "data_tools_none",
    "attribution",
    "nested_cli_required",
    "credential_probe_required",
    "current_context_only",
}
```

In `schedule_epoch`, emit:

```python
"fresh_history": True,
"filesystem": "none",
"data_tools": "none",
"output": "text",
```

Update the exact expected task-field set and assertions from `tools` to `data_tools`.

- [ ] **Step 5: Link and apply the adapter in every active workflow owner**

Use `skills/ppt-start/references/host-isolation-adapters.md` as the single host-mapping authority. Make these exact semantic changes:

1. `SKILL.md` step 6 links `[宿主隔离适配器](references/host-isolation-adapters.md)` and says Claude Code uses the registered ordinary `ppt-svg-generator` without an isolation argument.
2. `SKILL.md` step 8 says non-Git does not degrade and structural adapter failure stops without Git mutation or polling.
3. `workflow.md` says capability negotiation follows the adapter authority; Claude ordinary agents do not require Git/HEAD; worktree/remote are forbidden fallbacks.
4. `redesign-prompt.md` changes the abstract signature to:

```text
spawn_isolated_text_task(
  prompt_by_value,
  fresh_history=true,
  filesystem=none,
  data_tools=none,
  timeout,
  cancellation
) -> attribution_id, task_id, text, status, error_code
```

5. `artifact-contract.md` defines `data_tools=none` as no data-capable tools and preserves coordinator-only writes.
6. `adaptive-concurrency.md` distinguishes `worker_capacity == 0` (`WAIT`) from a missing/unsafe adapter (`generator_unavailable`, no polling).
7. `qa-and-revision.md` places adapter negotiation between deterministic preflight and durable writes and links the authority.

Do not duplicate the full Claude mapping into every file; each active owner states the relevant invariant and links the authority.

- [ ] **Step 6: Update the host-contract tests to require the new authority**

In `test_host_contract_documents_safe_degradation_and_forbidden_fallbacks`, require:

```python
for token in (
    "spawn_isolated_text_task",
    "get_isolated_text_task_result",
    "prompt_by_value",
    "fresh_history=true",
    "filesystem=none",
    "data_tools=none",
    "batch_width",
    "width 1",
    "generator_unavailable",
    "host_attribution_id",
    "host_task_id",
    "非 Git",
    "host-isolation-adapters.md",
):
    ...
```

In `BatchConcurrencyContractTest`, replace the old `tools=none` token with `data_tools=none` and add:

```python
self.assertIn("host-isolation-adapters.md", self.combined)
self.assertIn("不得轮询", read_text(skill_root() / "references" / "host-isolation-adapters.md"))
```

- [ ] **Step 7: Run focused routing and concurrency tests**

Run:

```bash
python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_host_capability_matrix_is_portable_and_fail_closed tests.test_visual_generation_contract.VisualGenerationContractTests.test_schedule_epoch_dispatches_each_transaction_once_with_prompt_by_value tests.test_visual_generation_contract.VisualGenerationContractTests.test_host_contract_documents_safe_degradation_and_forbidden_fallbacks tests.test_visual_generation_contract.VisualGenerationContractTests.test_claude_code_adapter_is_git_independent_and_never_uses_worktree tests.test_visual_generation_contract.VisualGenerationContractTests.test_claude_adapter_contract_names_agent_and_forbids_git_unlocks tests.test_tools_package.BatchConcurrencyContractTest -v
```

Expected: all focused tests pass.

- [ ] **Step 8: Record an unstaged checkpoint**

Run:

```bash
git diff --check
```

Expected: exit code 0. Do not stage or commit.

---

### Task 3: Install and Roll Back the Claude Agent Safely

**Files:**
- Modify: `tools/update-hosts.ps1:8-19,21-36,77-165,178-196`
- Modify: `tests/test_tools_package.py:101-224`

**Interfaces:**
- Consumes: source agent `hosts/claude-code/agents/ppt-svg-generator.md` from Task 1 and existing `Get-FileSha256`.
- Produces: optional parameter `-ClaudeAgentsRoot`, `Copy-ClaudeAgentWithBackup`, and installed `<ClaudeAgentsRoot>/ppt-svg-generator.md` with one backup under sibling `agent-backups/`.

- [ ] **Step 1: Extend installer tests first**

In `test_update_hosts_copies_and_verifies_both_skill_trees_with_per_id_backups`, define:

```python
claude_agents = root / "claude" / "agents"
```

Pass:

```python
"-ClaudeAgentsRoot",
str(claude_agents),
```

After two installer runs, assert:

```python
source_agent = (
    repo_root()
    / "hosts"
    / "claude-code"
    / "agents"
    / "ppt-svg-generator.md"
)
installed_agent = claude_agents / "ppt-svg-generator.md"
self.assertEqual(installed_agent.read_bytes(), source_agent.read_bytes())
self.assertEqual(
    len(list((claude_agents.parent / "agent-backups").glob(
        "ppt-svg-generator.bak-*.md"
    ))),
    1,
)
self.assertFalse(any(claude_agents.glob("*.bak-*")))
self.assertFalse((codex_skills.parent / "agents" / "ppt-svg-generator.md").exists())
```

Add a separate failure test:

```python
@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
def test_claude_agent_backup_failure_leaves_agent_and_skills_unchanged(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        claude_root = root / "claude"
        claude_skills = claude_root / "skills"
        claude_agents = claude_root / "agents"
        command = [
            shutil.which("powershell"),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.update_path),
            "-RepoRoot",
            str(repo_root()),
            "-SkipDeepSeek",
            "-SkipCodex",
            "-ClaudeSkillsRoot",
            str(claude_skills),
            "-ClaudeAgentsRoot",
            str(claude_agents),
        ]
        first = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        before_agent = (claude_agents / "ppt-svg-generator.md").read_bytes()
        before_skills = {
            skill_id: _tree_digest(claude_skills / skill_id)
            for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract")
        }
        backup_root = claude_root / "agent-backups"
        backup_root.write_text("not a directory", encoding="utf-8")

        second = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(
            (claude_agents / "ppt-svg-generator.md").read_bytes(),
            before_agent,
        )
        for skill_id, digest in before_skills.items():
            self.assertEqual(_tree_digest(claude_skills / skill_id), digest)
```

Add a post-copy rollback test without adding a production test hook. The test writes a temporary copy of the installer and injects one failure immediately after the agent `Copy-Item` line:

```python
@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
def test_claude_agent_post_copy_failure_restores_live_agent_and_skills(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        claude_root = root / "claude"
        claude_skills = claude_root / "skills"
        claude_agents = claude_root / "agents"
        base_command = [
            shutil.which("powershell"),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.update_path),
            "-RepoRoot",
            str(repo_root()),
            "-SkipDeepSeek",
            "-SkipCodex",
            "-ClaudeSkillsRoot",
            str(claude_skills),
            "-ClaudeAgentsRoot",
            str(claude_agents),
        ]
        first = subprocess.run(
            base_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        before_agent = (claude_agents / "ppt-svg-generator.md").read_bytes()
        before_skills = {
            skill_id: _tree_digest(claude_skills / skill_id)
            for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract")
        }

        installer_text = read_text(self.update_path)
        copy_line = (
            "        Copy-Item -LiteralPath $source "
            "-Destination $destination -Force\n"
        )
        self.assertEqual(installer_text.count(copy_line), 1)
        injected_installer = root / "update-hosts-agent-failure.ps1"
        injected_installer.write_text(
            installer_text.replace(
                copy_line,
                copy_line + "        throw 'injected agent verification failure'\n",
                1,
            ),
            encoding="utf-8",
        )
        failed_command = list(base_command)
        failed_command[failed_command.index(str(self.update_path))] = str(
            injected_installer
        )
        failed = subprocess.run(
            failed_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(
            (claude_agents / "ppt-svg-generator.md").read_bytes(),
            before_agent,
        )
        for skill_id, digest in before_skills.items():
            self.assertEqual(_tree_digest(claude_skills / skill_id), digest)
```

Update static installer assertions to require `$ClaudeAgentsRoot`, `ppt-svg-generator.md`, and `agent-backups` only in `update-hosts.ps1`.

- [ ] **Step 2: Run installer tests and confirm RED**

Run:

```bash
python -m unittest tests.test_tools_package.MultiSkillInstallerTests.test_update_hosts_copies_and_verifies_both_skill_trees_with_per_id_backups tests.test_tools_package.MultiSkillInstallerTests.test_claude_agent_backup_failure_leaves_agent_and_skills_unchanged tests.test_tools_package.MultiSkillInstallerTests.test_claude_agent_post_copy_failure_restores_live_agent_and_skills -v
```

Expected: failures because `update-hosts.ps1` does not accept `-ClaudeAgentsRoot` and does not install the agent.

- [ ] **Step 3: Add the Claude agent source descriptor and parameter**

Extend the parameter block:

```powershell
[string]$ClaudeSkillsRoot = '',
[string]$ClaudeAgentsRoot = '',
[string]$CodexSkillsRoot = '',
```

After validating `$skills`, define and validate:

```powershell
$claudeAgent = [ordered]@{
    Id = 'ppt-svg-generator'
    Source = Join-Path $RepoRoot 'hosts\claude-code\agents\ppt-svg-generator.md'
}
if (-not (Test-Path -LiteralPath $claudeAgent.Source -PathType Leaf)) {
    throw "Claude Code Agent 缺失：$($claudeAgent.Source)"
}
```

- [ ] **Step 4: Implement single-file backup, verification, and rollback**

Add this function after `Copy-SkillWithBackup`:

```powershell
function Copy-ClaudeAgentWithBackup {
    param(
        [System.Collections.IDictionary]$Descriptor,
        [string]$AgentsRoot,
        [string]$Label
    )
    $id = [string]$Descriptor.Id
    $source = [string]$Descriptor.Source
    $destination = Join-Path $AgentsRoot "$id.md"
    $harnessRoot = Split-Path -Parent $AgentsRoot
    $backupRoot = Join-Path $harnessRoot 'agent-backups'
    $filter = "$id.bak-*.md"
    $createdBackup = $null
    $destinationExisted = Test-Path -LiteralPath $destination
    $backupMoved = $false

    New-Item -ItemType Directory -Force -Path $AgentsRoot | Out-Null
    try {
        if ($destinationExisted) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $backupCandidate = Join-Path $backupRoot "$id.bak-$ts.md"
            if (Test-Path -LiteralPath $backupCandidate) {
                $backupCandidate = Join-Path $backupRoot (
                    "$id.bak-$ts." + [guid]::NewGuid().ToString('N') + '.md'
                )
            }
            Move-Item -LiteralPath $destination -Destination $backupCandidate
            $createdBackup = $backupCandidate
            $backupMoved = $true
        }

        Copy-Item -LiteralPath $source -Destination $destination -Force
        if ((Get-FileSha256 -Path $source) -ne (Get-FileSha256 -Path $destination)) {
            throw "$id Agent 安装摘要不一致"
        }
    }
    catch {
        if (Test-Path -LiteralPath $destination) {
            Remove-Item -LiteralPath $destination -Force
        }
        if ($backupMoved -and (Test-Path -LiteralPath $createdBackup)) {
            Move-Item -LiteralPath $createdBackup -Destination $destination
        }
        throw
    }

    if (Test-Path -LiteralPath $backupRoot -PathType Container) {
        $backups = @(
            Get-ChildItem -LiteralPath $backupRoot -File -Filter $filter -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTimeUtc, Name -Descending
        )
        $preserve = $createdBackup
        if (-not $preserve -and $backups.Count -gt 0) {
            $preserve = $backups[0].FullName
        }
        foreach ($backup in $backups) {
            if (-not $preserve -or $backup.FullName -ne $preserve) {
                Remove-Item -LiteralPath $backup.FullName -Force
            }
        }
    }

    Write-Host "  $Label Agent 已更新 -> $destination"
}
```

This function prepares the backup before moving the live agent, restores on copy/hash failure, and retains one backup outside `agents/`.

- [ ] **Step 5: Install the agent before Claude Skills**

Replace the Claude user branch with:

```powershell
if (-not $SkipClaudeCode) {
    Write-Host '[2/3] Claude Code（用户级技能与 SVG Agent）...'
    if (-not $ClaudeSkillsRoot) {
        $ClaudeSkillsRoot = Join-Path $env:USERPROFILE '.claude\skills'
    }
    if (-not $ClaudeAgentsRoot) {
        $ClaudeAgentsRoot = Join-Path (Split-Path -Parent $ClaudeSkillsRoot) 'agents'
    }
    Copy-ClaudeAgentWithBackup $claudeAgent $ClaudeAgentsRoot 'Claude Code'
    Install-SkillsToRoot $ClaudeSkillsRoot 'Claude Code'
}
else { Write-Host '[2/3] 跳过 Claude Code。' }
```

Replace the project-Claude branch with:

```powershell
if ($ProjectClaude) {
    $projectClaudeRoot = Join-Path $RepoRoot '.claude'
    Copy-ClaudeAgentWithBackup $claudeAgent (Join-Path $projectClaudeRoot 'agents') '项目级 Claude'
    Install-SkillsToRoot (Join-Path $projectClaudeRoot 'skills') '项目级 Claude'
}
```

Update the final installer message to say that Claude Code must reopen the session to discover a newly installed agent.

Do not pass the agent to `install-deepseek-plugin.ps1` or the Codex branch.

- [ ] **Step 6: Run focused installer and rollback tests**

Run:

```bash
python -m unittest tests.test_tools_package.MultiSkillInstallerTests -v
```

Expected: all `MultiSkillInstallerTests` pass; Windows-only tests skip only when PowerShell is genuinely unavailable.

- [ ] **Step 7: Record an unstaged checkpoint**

Run:

```bash
git diff --check
```

Expected: exit code 0. Do not stage, commit, or run the installer against the real user profile.

---

### Task 4: Document Installation, Evidence Boundaries, and Verify the Whole Change

**Files:**
- Modify: `README.md:63-95,150-220`
- Modify: `docs/INSTALL.md:1-59,138-143`
- Modify: `docs/acceptance.md:3-100,135-143,219-275`
- Modify: `tests/test_skill_package.py:68-100`
- Modify: `tests/test_tools_package.py:101-132`

**Interfaces:**
- Consumes: packaged agent and installer behavior from Tasks 1–3.
- Produces: user-visible install/restart instructions, honest `PENDING` real-host row, and complete repository verification evidence.

- [ ] **Step 1: Add failing documentation assertions**

In `SkillPackageTests.test_readme_documents_both_hosts_without_runtime_coupling`, add these required README tokens:

```python
for token in (
    "hosts/claude-code/agents/ppt-svg-generator.md",
    "~/.claude/agents/ppt-svg-generator.md",
    "普通 fresh-context subagent",
    "不需要 Git",
    "重新开启 Claude Code 会话",
):
    self.assertIn(token, readme)
```

Add a test for the installation and evidence documents:

```python
def test_claude_agent_install_and_real_host_evidence_are_explicit(self):
    install = read_text(repo_root() / "docs" / "INSTALL.md")
    acceptance = read_text(repo_root() / "docs" / "acceptance.md")
    for token in (
        "-ClaudeAgentsRoot",
        "~/.claude/agents/ppt-svg-generator.md",
        "hosts/claude-code/agents/ppt-svg-generator.md",
        "非 Git",
        "重新开启",
    ):
        with self.subTest(document="install", token=token):
            self.assertIn(token, install)
    for token in (
        "Claude Code 非 Git SVG isolation",
        "ppt-svg-generator",
        "无 `.git` 目录",
        "PENDING",
        "static package",
        "real host",
    ):
        with self.subTest(document="acceptance", token=token):
            self.assertIn(token, acceptance)
```

- [ ] **Step 2: Run documentation tests and confirm RED**

Run:

```bash
python -m unittest tests.test_skill_package.SkillPackageTests.test_readme_documents_both_hosts_without_runtime_coupling tests.test_skill_package.SkillPackageTests.test_claude_agent_install_and_real_host_evidence_are_explicit -v
```

Expected: failures for the new Claude agent/install/evidence tokens.

- [ ] **Step 3: Update README installation and behavior**

Document all of the following without claiming a real-host PASS:

```markdown
Claude Code 的 SVG fresh-context 生成还需要仓库随附的
`hosts/claude-code/agents/ppt-svg-generator.md`，由 `tools/update-hosts.ps1`
安装到 `~/.claude/agents/ppt-svg-generator.md`。它使用普通 fresh-context
subagent，不请求 worktree，因此普通非 Git PPT 工作目录不需要 Git、首个提交或
可解析 `HEAD`。新增或更新 Agent 后需重新开启 Claude Code 会话完成发现。
```

State that manually copying only `skills/ppt-start/` is insufficient for Claude SVG generation unless the agent is copied separately. Do not describe the custom agent as part of Codex or DeepSeek installation.

- [ ] **Step 4: Update the installation guide**

In the one-click section, add `-ClaudeAgentsRoot` to the parameter list and state that the Claude branch installs both Skills and the custom agent.

Add user-level manual installation:

```bash
mkdir -p ~/.claude/agents
```

```bash
cp hosts/claude-code/agents/ppt-svg-generator.md ~/.claude/agents/ppt-svg-generator.md
```

Add project-level manual installation:

```bash
mkdir -p .claude/agents
```

```bash
cp hosts/claude-code/agents/ppt-svg-generator.md .claude/agents/ppt-svg-generator.md
```

State that a running Claude Code session must be reopened after agent installation and that no Git repository is required in the PPT workspace.

- [ ] **Step 5: Update acceptance without overstating evidence**

In the Claude Code setup section, require installation/discovery of `ppt-svg-generator` in addition to the Skills.

Add a real-host procedure that records:

1. a newly opened Claude Code session rooted in a temporary plain directory;
2. absence of `.git` before and after;
3. `ppt-svg-generator` selected as an ordinary agent;
4. no worktree or remote isolation request;
5. Prompt passed by value;
6. returned SVG text consumed and written only by coordinator;
7. transcript, Claude Code version, run directory, and attribution.

Add this ledger row and leave it exactly pending:

```markdown
| Claude Code 非 Git SVG isolation | Claude Code | — | — | PENDING — packaged adapter added; real restarted-host transcript required | — |
```

Keep the existing `schema-v2 isolated generation` row `PENDING`. Static/package tests may prove configuration and routing oracles, but they must not be described as real host evidence.

- [ ] **Step 6: Run focused documentation and package tests**

Run:

```bash
python -m unittest tests.test_skill_package tests.test_tools_package -v
```

Expected: exit code 0; all applicable tests pass, with only environment-dependent PowerShell skips if PowerShell is unavailable.

- [ ] **Step 7: Run all visual-generation contract tests**

Run:

```bash
python -m unittest tests.test_visual_generation_contract tests.test_generation_concurrency tests.test_adaptive_generation_contract -v
```

Expected: exit code 0 and `OK`.

- [ ] **Step 8: Run the complete frozen repository suite**

Run:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: exit code 0 and `OK`; only explicitly documented environment/reference-dependent skips are acceptable.

- [ ] **Step 9: Verify formatting and inspect the final unstaged scope**

Run:

```bash
git diff --check
```

Expected: exit code 0.

Run:

```bash
git status --short
```

Expected: only the files listed in this plan are modified/untracked. Do not stage, commit, push, or install to the real Claude profile.

- [ ] **Step 10: Record the external verification boundary**

Report these outcomes separately:

- repository tests: PASS or exact failures;
- temporary-root installer verification: PASS or exact failures;
- real user-profile deployment: NOT PERFORMED;
- restarted Claude Code non-Git smoke: PENDING;
- `.git` cleanup in the affected PPT directory: NOT PERFORMED.

Do not claim that the original blocked run has resumed until a new Claude Code session actually discovers the agent and produces transcript evidence.
