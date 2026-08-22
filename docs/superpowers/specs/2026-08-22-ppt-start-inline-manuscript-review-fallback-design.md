# PPT Start 当前步骤文稿审查降级设计

- **日期**：2026-08-22
- **状态**：核心行为已确认，待书面规范复核
- **范围**：独立子 Agent 不可用时，在当前创作步骤执行完整文稿审查，并允许按严格质量门批准或阻断

## 1. 背景

当前 `ppt-start` 把文稿质量门限定为全新独立子 Agent。真实启动失败或没有可归因结果时，运行进入 `review_unavailable`，禁止当前上下文产生审查 findings，也禁止进入视觉阶段。

新决策是：仍优先独立审稿；如果宿主不能创建或完成子 Agent，则当前步骤立即使用同一组冻结文稿和同一审查规范执行降级审查。降级结果不是独立审查，但具有正式质量门效力：没有未解决 `BLOCKER/HIGH` 时可以进入 `manuscript_approved`。

## 2. 目标

1. 保留独立子 Agent 为首选路径。
2. 子 Agent 启动或结果归因失败时，不再仅因此阻断整个演示文稿。
3. 当前上下文执行与独立审稿相同的输入边界、审查维度、findings schema、阻断规则和三轮上限。
4. 持久状态明确区分 `subagent` 与 `inline_fallback`，不得把自审伪称为独立。
5. inline 审查通过后可以设置 `manuscript_approved`；未解决阻断问题仍然进入修订／下一轮或最终 `manuscript_blocked`。
6. crash、resume、跨宿主和混合审查轮次都能仅凭运行目录恢复。

## 3. 非目标

- 不在子 Agent 可用时默认跳过独立审查。
- 不降低 `BLOCKER/HIGH` 必须 `RESOLVED` 的质量门。
- 不允许用户用 `ACCEPTED_RISK` 放行阻断级问题。
- 不跳过文稿审查。
- 不把 inline fallback 描述成独立审稿或伪造 delegation IDs。
- 不增加运行时脚本、SDK、服务或宿主专属 API。

## 4. 审查模式

`run.json.manuscript_review.mode` 允许：

- `pending`：尚未选择／完成当前轮执行方式；
- `subagent`：已成功启动并接收可归因的独立子 Agent 结果；
- `inline_fallback`：本轮子 Agent 启动或结果归因失败，当前上下文直接审查；
- `unavailable`：只用于真正无法完成任何审查的异常，例如冻结输入不可读、当前上下文也不能执行审查，或读取到无法安全恢复的状态冲突。委派不可用本身不再产生该模式。

缺少新字段的旧 schema-v1 运行继续按原记录读取；既有 `review_unavailable` 运行不自动改写。收到新的 `resume` 请求后，可以在保留旧历史的前提下创建一个新的 inline fallback 轮次。

## 5. 固定执行顺序

每轮文稿审查严格执行：

1. 验证五个冻结文件和 `reviewed_file_snapshot`。
2. 请求真实启动独立子 Agent，并检查宿主响应。
3. 启动成功时，只等待该子上下文；结果具有完整 delegation evidence 时使用 `subagent`。
4. 启动失败、接收者为空、没有完成事件、结果上下文不匹配或委派能力明确不可用时：
   - 保存委派失败原因；
   - 不重复空等待；
   - 不询问用户；
   - 在当前步骤建立 `inline_fallback` pending round；
   - 立即按同一规范审查冻结文件。
5. 完成报告后，原子提交 review history、质量门结果和 pending round 删除。

如果子 Agent 已成功返回有效结果，不再追加 inline 自审作为第二个正式 round；当前上下文只能保存载荷和作者修订说明。

## 6. Inline 审查输入边界

inline reviewer 虽位于创作上下文，但正式审查时必须建立显式输入边界：

- 只把五个冻结文稿和 `manuscript-review.md` 作为 findings 的事实来源；
- 不使用主题、样例、SVG 或视觉产物评价文稿；
- 不把创作意图、先前辩解或用户偏好当作事实支持；
- 先从冻结文件重新列出主张／来源映射，再执行审查；
- 报告必须注明上下文隔离有限，不能声称独立。

这是一条行为契约，不是加密隔离。

## 7. 持久状态

### 7.1 `pending_round`

`manuscript_review.pending_round` 是 schema-v1 可选对象：

```json
{
  "cycle": 1,
  "round": 1,
  "mode": "inline_fallback",
  "reviewed_file_snapshot": {
    "snapshot_id": "sha256:...",
    "files": ["简报.md", "研究.md", "来源.md", "大纲.md", "故事板.md"]
  },
  "fallback_evidence": {
    "delegation_attempted": true,
    "reason": "child_context_unavailable",
    "host_detail": "no child context returned"
  },
  "status": "in_progress"
}
```

规则：

- 提交 completed round 前先持久化 pending round；
- subagent pending 只记录 `delegation_attempt_evidence.child_context_id`，因为 completion/result 尚未发生；inline pending 记录完整 `fallback_evidence`；
- completed subagent round 才记录三字段 `delegation_evidence`，且 child/result 必须等于 pending child；completed inline evidence 必须与 pending fallback evidence 一致；
- crash 后复用相同 current cycle、下一合法 round、mode 和 snapshot，不递增轮次；round 必须等于已完成 round + 1 且不超过 3；
- completed report 必须保留并处理前一轮每个未解决 `BLOCKER/HIGH` ID；
- snapshot 变化时 pending round 失效，按当前 cycle 规则重新冻结；
- 同一运行一次只允许一个 pending round；
- completed round 与删除 pending round 在一次原子 `run.json` 替换中完成，重复 resume 不追加第二次。

### 7.2 Inline review history record

```json
{
  "cycle": 1,
  "round": 1,
  "reviewer_id": "current-context-inline-review-cycle-1-round-1",
  "reviewer_context": "current-authoring-context",
  "review_mode": "inline_fallback",
  "fallback_evidence": {
    "delegation_attempted": true,
    "reason": "child_context_unavailable",
    "host_detail": "no child context returned"
  },
  "reviewed_file_snapshot": {
    "snapshot_id": "sha256:...",
    "files": ["简报.md", "研究.md", "来源.md", "大纲.md", "故事板.md"]
  },
  "verdict": "PASS",
  "findings": []
}
```

- inline record 不包含 `delegation_evidence`；
- subagent record 必须包含现有三字段 delegation evidence；
- 两种 evidence 对象互斥；
- `fallback_evidence.reason` 使用稳定值：
  - `child_context_unavailable`
  - `child_start_failed`
  - `completion_event_missing`
  - `result_context_mismatch`
  - `delegation_capability_unavailable`
- `host_detail` 只保存非机密、可归因的宿主失败摘要；不能编造 IDs。

## 8. Findings 与质量门

两种模式完全复用：

- findings 必填字段；
- severity/status 枚举；
- 来源覆盖、事实准确性、时效性、逻辑、重复、遗漏、风险七维；
- 每个 `BLOCKER/HIGH` 必须为 `RESOLVED`；
- `OPEN` 和阻断级 `ACCEPTED_RISK` 都阻断；
- 没有 findings 时写明确 PASS 报告。

inline round 的 PASS 可以把：

```text
manuscript_review.mode = inline_fallback
manuscript_review.state = manuscript_approved
manuscript_review.status = PASSED
stage = manuscript_approved
```

inline round 有未解决阻断问题时使用现有作者修订／下一轮流程；cycle 第三轮后仍失败进入 `manuscript_blocked`。

## 9. 轮次与混合模式

- subagent 与 inline fallback 共同使用同一个 `cycle`／`round` 计数；fallback 不重置三轮上限。
- 后续轮次仍先尝试子 Agent；能力恢复后可以从 inline round 切回 subagent round。
- 后续 round 必须追踪此前阻断 finding IDs，无论前一轮模式是什么。
- inline round 可以在有冻结证据时把前一轮问题标记 `RESOLVED`，但报告必须明确是 inline 核验。
- `manuscript_blocked` 不能通过切换模式开启第 4 轮。
- 只有此前 `manuscript_approved` 的版本发生实质修订时才能开始新 cycle。

## 10. 报告格式

`文稿审查.md`／旧 `manuscript-review.md` 必须记录：

- `review_mode: subagent | inline_fallback`
- 本轮 cycle／round／snapshot；
- subagent delegation evidence 或 inline fallback evidence；
- verdict 和完整 findings；
- inline 模式限制声明：`当前上下文降级审查，不具备独立上下文隔离`。

不得把 inline 报告标题写为“独立审查通过”。

## 11. 恢复与错误

- `resume` 先处理已有 `pending_round`，再按普通 stage 发现；不能重新创建同一轮。
- pending round 已有完整报告但尚未提交时，按 cycle／round／mode／snapshot／execution evidence 幂等完成原子提交；不得丢失此前未解决 IDs；重复 resume 为 no-op。
- pending round 格式错误、snapshot 冲突或存在两个 pending round 时停止并报告状态冲突。
- 如果当前上下文也无法读取／审查冻结文件，才进入 `review_unavailable`，记录 `mode: unavailable`，不生成伪报告。
- 旧 `review_unavailable` 运行 resume 时，新的 inline round 使用下一合法 round；不删除旧不可用原因。

## 12. 测试策略

先替换旧反向契约并观察 RED：

1. execution evidence 使用 discriminated validation：
   - subagent 必须有完整 delegation evidence，不能有 fallback evidence；
   - inline 必须有完整 fallback evidence，不能有 delegation evidence。
2. 新增 `run-review-inline-approved.json` 与 `run-review-inline-blocked.json`。
3. truth table 覆盖：
   - 子 Agent 成功；
   - 启动失败 → inline PASS；
   - 启动失败 → inline BLOCK；
   - inline 修订后下一轮 subagent PASS；
   - subagent 阻断后 inline RESOLVED；
   - 三轮混合模式仍阻断；
   - crash/resume pending round；
   - 双 evidence／缺 evidence 拒绝。
4. 删除“委派不可用必然 review_unavailable／禁止自审放行”的静态断言，替换为“委派失败必须 inline fallback”。
5. README、design、acceptance 同步；真实 Claude Code／Codex inline fallback 行保持 PENDING，直到保存 host transcript。
6. 完整测试通过后同步 Claude Code 用户级 Skill，并更新当前 PR。

静态测试只证明包契约和状态 fixture，不证明模型在同一上下文中真正消除了自我偏见。

## 13. 影响文件

- `skills/ppt-start/SKILL.md`
- `skills/ppt-start/references/manuscript-review.md`
- `skills/ppt-start/references/artifact-contract.md`
- `skills/ppt-start/references/workflow.md`
- `skills/ppt-start/references/qa-and-revision.md`
- `tests/test_manuscript_review_gate.py`
- `tests/test_workflow_contract.py`
- `tests/fixtures/run-review-inline-approved.json`（新增）
- `tests/fixtures/run-review-inline-blocked.json`（新增）
- 现有 unavailable fixtures／prompts（保留 legacy 兼容并修订当前期望）
- `README.md`
- `docs/design.md`
- `docs/acceptance.md`
- 新设计与实施计划文档

## 14. 验收标准

1. 子 Agent 可用时仍使用独立审查并要求真实 delegation evidence。
2. 子 Agent 不可用时不等待、不询问，持久化 inline pending round 并在当前步骤审查。
3. inline PASS 可以产生 `manuscript_approved`；inline BLOCK 继续严格阻断。
4. 两种模式 evidence 互斥、可审计，不伪造独立性。
5. 三轮上限、finding ID 追踪、cycle 规则和视觉生产护栏不变。
6. crash/resume 不重复轮次或报告。
7. 旧 schema-v1 和 `review_unavailable` 历史可读取。
8. 静态测试与真实宿主验收边界准确。
9. 更新后的用户级 Claude Code Skill 与仓库源逐文件 hash 一致。
10. 当前 PR 包含新 commit，并保留此前完整测试证据。
