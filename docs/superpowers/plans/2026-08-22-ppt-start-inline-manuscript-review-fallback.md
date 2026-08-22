# PPT Start Inline Manuscript Review Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 子 Agent 文稿审查不可用时，由当前步骤执行同一严格审查，并允许 inline PASS 正式进入 `manuscript_approved`。

**Architecture:** 保留 subagent 优先路径；用 discriminated evidence 区分 `subagent` 与 `inline_fallback`。新增 schema-v1 `pending_round` 保证 crash/resume 幂等；两种模式共享 findings、轮次、cycle 和质量门。

**Tech Stack:** Markdown instruction Skill、JSON fixtures、Python `unittest`、Claude Code 用户级文件同步、Git/GitHub PR。

## Global Constraints

- 规范源：`docs/superpowers/specs/2026-08-22-ppt-start-inline-manuscript-review-fallback-design.md`。
- 当前分支：`feat/style-owned-redesign-prompts`；PR #1 已存在。
- 不修改或提交运行时 acceptance 产物；现有 `.gitignore` 策略保持。
- 独立子 Agent 仍是第一选择；只在启动／结果归因失败时 inline fallback。
- inline 不得伪装独立；subagent 与 inline evidence 互斥。
- `BLOCKER/HIGH` 非 `RESOLVED` 继续阻断；三轮/cycle 规则不变。
- 先测试 RED，再修改 Skill；静态测试不能冒充真实宿主验收。

---

### Task 1: Discriminated Review Evidence and Inline Fixtures

**Files:**
- Modify: `tests/test_manuscript_review_gate.py`
- Create: `tests/fixtures/run-review-inline-approved.json`
- Create: `tests/fixtures/run-review-inline-blocked.json`
- Modify: `tests/fixtures/run-review-unavailable.json`

**Interfaces:**
- Produces: `validate_review_execution(round_record)`；subagent 与 inline evidence 的唯一判定；inline approved/blocked fixture。

- [ ] **Step 1: 写 RED tests**

新增：

```python
INLINE_FALLBACK_REASONS = {
    "child_context_unavailable",
    "child_start_failed",
    "completion_event_missing",
    "result_context_mismatch",
    "delegation_capability_unavailable",
}


def validate_review_execution(round_record):
    mode = round_record.get("review_mode")
    if mode == "subagent":
        validate_delegation_evidence(round_record)
        if "fallback_evidence" in round_record:
            raise ValueError("subagent round cannot contain fallback_evidence")
        return
    if mode == "inline_fallback":
        if "delegation_evidence" in round_record:
            raise ValueError("inline round cannot contain delegation_evidence")
        evidence = round_record.get("fallback_evidence")
        if not isinstance(evidence, dict):
            raise TypeError("inline round requires fallback_evidence")
        if evidence.get("delegation_attempted") is not True:
            raise ValueError("inline fallback must follow a delegation attempt")
        if evidence.get("reason") not in INLINE_FALLBACK_REASONS:
            raise ValueError("invalid fallback reason")
        if not isinstance(evidence.get("host_detail"), str) or not evidence["host_detail"].strip():
            raise ValueError("fallback host_detail must be non-empty")
        return
    raise ValueError("invalid review_mode")
```

测试覆盖：

- subagent valid；subagent 缺 delegation／双 evidence 拒绝；
- inline valid；inline 缺 fallback／含 delegation／未尝试／非法 reason 拒绝；
- inline PASS fixture 进入 manuscript_approved；
- inline BLOCK fixture 保持 blocking finding；
- mixed rounds 追踪相同 finding ID；
- 三轮混合仍 blocked；
- pending_round crash/resume 不增加 round。

- [ ] **Step 2: 运行 RED**

```bash
python -m unittest tests.test_manuscript_review_gate -v
```

Expected: 缺 inline fixtures／当前 unavailable-only 断言导致失败。

- [ ] **Step 3: 创建 fixtures**

`run-review-inline-approved.json`：

- `manuscript_review.mode: inline_fallback`
- `state: manuscript_approved`
- `status: PASSED`
- completed history round 使用 `review_mode: inline_fallback`、`reviewer_context: current-authoring-context`、fallback evidence、无 delegation evidence、findings 空或全部 resolved。

`run-review-inline-blocked.json`：

- inline round 含一个 `HIGH/OPEN` finding；
- state 继续 pending/blocked（按当前 round）；
- 不创建视觉授权。

`run-review-unavailable.json` 保留 legacy 可读含义，但当前测试不再把“委派失败”直接映射 unavailable。

- [ ] **Step 4: GREEN**

```bash
python -m unittest tests.test_manuscript_review_gate -v
```

---

### Task 2: Skill State Machine and Documentation

**Files:**
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/manuscript-review.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `tests/test_workflow_contract.py`
- Modify: `tests/test_skill_package.py`
- Modify: `README.md`
- Modify: `docs/design.md`
- Modify: `docs/acceptance.md`

**Interfaces:**
- Consumes: Task 1 evidence/fixtures。
- Produces: subagent-first → inline fallback 状态机、`pending_round`、文档与验收边界。

- [ ] **Step 1: 写文档契约 RED**

新增断言：

```python
for token in (
    "inline_fallback",
    "pending_round",
    "fallback_evidence",
    "当前上下文降级审查",
    "不具备独立上下文隔离",
):
    self.assertIn(token, combined)

self.assertRegex(combined, r"子 agent.*失败.*inline_fallback|inline_fallback.*委派.*失败")
self.assertIn("inline PASS", combined)
self.assertIn("manuscript_approved", combined)
```

负向断言：

- 不再存在“委派不可用必然在设计前停止”的当前规则；
- 不再把同上下文审查固定为只能建议性 QA；
- inline 不能包含 delegation evidence。

- [ ] **Step 2: 运行 RED**

```bash
python -m unittest tests.test_workflow_contract tests.test_skill_package -v
```

- [ ] **Step 3: 修改 Skill 状态机**

固定顺序：

```text
freeze five files
-> attempt subagent once
-> valid child result: subagent mode
-> startup/result evidence failure: persist inline pending_round
-> current step executes same review
-> atomically append completed round and clear pending_round
-> strict gate decides approved / revise / blocked
```

`artifact-contract.md` 定义 pending round 与互斥 evidence；`manuscript-review.md` 定义输入边界、失败 reasons、报告限制、混合轮次；workflow/SKILL/QA 同步。

- [ ] **Step 4: 更新公开文档**

README/design 说明“优先独立，失败当前步骤审查并可严格放行”。acceptance：

- 旧 `review_unavailable` 历史行保留；
- 当前委派不可用场景改为 inline fallback 预期；
- Claude Code／Codex inline fallback 当前行为行新增 PENDING；
- 不能把 inline 称作独立。

- [ ] **Step 5: GREEN**

```bash
python -m unittest tests.test_manuscript_review_gate tests.test_workflow_contract tests.test_skill_package -v
```

---

### Task 3: Full Verification, Deployment, Commit, and PR Update

**Files:**
- Verify: all repository tests
- Sync: `skills/ppt-start/` → `C:/Users/Lenovo/.claude/skills/ppt-start/`
- Update: branch and PR #1

- [ ] **Step 1: 完整验证**

```bash
python -m unittest discover -s tests -v
git diff --check
```

- [ ] **Step 2: runtime-artifact 审计**

确认 `acceptance-evidence/`／`ppt-output/` 没有新增 runtime 文件；只保留既有索引策略。

- [ ] **Step 3: Claude Code 精确同步**

建立 staging，比较文件集和每文件 SHA-256，backup-aware swap，最终源／目标 manifest 完全相等；Canway 无 SVG exemplar。

- [ ] **Step 4: 独立 review**

审查：inline evidence 互斥、正式放行条件、三轮上限、pending round crash、旧运行兼容和文档 evidence boundary。修复任何 CRITICAL/IMPORTANT 后重跑完整测试。

- [ ] **Step 5: commit/push 更新 PR**

```bash
git add -A
git commit -m "feat: add inline manuscript review fallback"
git push
```

确认 PR #1 head 更新，base 仍为 `main`，工作树干净。

---

## Plan Self-Review

- Task 1 覆盖 evidence schema、fixtures、gate truth table。
- Task 2 覆盖 Skill、状态、恢复、公开文档和验收。
- Task 3 覆盖完整验证、Claude Code 安装、review、commit/push。
- 不新增 runtime 架构；不弱化 findings／三轮／cycle 规则。
