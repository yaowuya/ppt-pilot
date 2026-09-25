# AI 状态协议

AI 是 `.ppt-pilot/run.json` 的唯一流程 owner。文件是跨回合证据，不是脚本输入队列；工具不得读取、修改或推进它。

## 最小状态

新运行至少记录：

```json
{
  "schema_version": 1,
  "deck_id": "example",
  "mode": "guided",
  "stage": "production",
  "pending_interaction": null,
  "dirty_slides": ["S02"],
  "slides": {
    "S01": {
      "state": "promoted",
      "attempts": 1,
      "prompt": ".ppt-pilot/generation-prompts/S01.md",
      "svg": "slides/S01.svg",
      "failure": null,
      "qa": {"structure": "pass", "visual": "not_rendered", "tool": "pass"}
    }
  },
  "delivery": {"status": "in_progress"}
}
```

`stage` 使用 `brief|research|outline|storyboard|manuscript_review|theme|anchor|production|qa|complete|partial|failed`。页面 `state` 使用 `planned|generating|validated|promoted|failed|skipped`。

最终运行的 `slides` key 必须与故事板 target ID 完全相同。旧运行的未知字段原样保留；`visual_generation_transaction`、batch、dispatch、recovery 等历史 owner 只作证据，不再驱动流程，也不为新运行创建。

## 每轮完成条件

1. 读取当前状态和真实产物。
2. 处理 `pending_interaction` 或选择最早可执行动作。
3. 每轮最多执行一个真实页面生成调用；没有隐藏队列、忙等或自动循环。
4. 先写入并读回真实证据，再原子更新状态。
5. 报告本轮动作、工具降级、页面失败、下一动作和待决定事项。

只有真实 fresh-context 生成调用才增加该页 `attempts`。读取、校验、格式转换、工具启动失败、用户 skip 和恢复检查都不得增加或重置它。

## 工具证据

所有保留工具只有三类结果：

| 状态 | 含义 | AI 如何处理 |
|---|---|---|
| `PASS` | 指定操作完成并通过其确定性检查 | 可记录为额外证据并继续 |
| `INVALID` | 工具成功证明输入产物不符合契约 | 仅把对应产物／页面标记 `failed`，保留旧 final，继续 siblings |
| `UNAVAILABLE` | 工具无法启动、缺依赖、环境不支持或内部失败 | 记录 `tool_unavailable`；保持当前 stage 与 attempts，由 AI 直接检查后继续，不声称工具 PASS |

只有结构化 `INVALID` 能证明产物错误。非零退出、异常文本或工具消失本身都属于 `UNAVAILABLE`，不能消耗生成预算、创建问题或变成全局 blocker。

## 页面证据

每个页面记录实际 Prompt、final 路径、attempts、failure 和 QA。每个 content block 都有稳定 block ID；没有可关联来源的 block 在冻结 source map 中保留 `[]`，不因为 source-less 而省略结构 join key。失败示例：

```json
{
  "state": "failed",
  "attempts": 2,
  "prompt": ".ppt-pilot/generation-prompts/S02.md",
  "svg": null,
  "failure": {"code": "generator_unavailable", "message": "fresh-context generator could not start"},
  "qa": {"structure": "not_run", "visual": "not_rendered", "tool": "unavailable"}
}
```

Claude Code 仅在 Agent 尚未接受 Prompt 且明确产生 `host_git_required` 后，才可在页面既有 record 中附加成功 bootstrap 的审计事实：

```json
"generator_setup": {
  "kind": "claude_code_local_git_initialized",
  "scope": "presentation_workspace_root",
  "trigger": "host_git_required"
}
```

它不是新的 control state 或 retry owner。bootstrap 失败或 Agent 第二次仍无法启动时，记录 `generator_unavailable`，保持 stage 和 attempts；只有 Agent 接受 Prompt 后的真实 fresh-context call 才增加 attempts。

- 首次真实生成失败后，只有用户或当前修订动作明确选择 retry/recompose 才能再生成一次。
- 第二次失败后等待用户选择修复、skip 或停止；不得重建运行、改名页面或删除证据归零。
- `skipped` 页保存 `skip.decision: user_skipped` 和用户原始回答，attempts 保持不变。
- 新 candidate 失败不得覆盖旧 `promoted` final；旧 final 也不得冒充新结果。

## 失败边界

页面生成、SVG、事实来源或视觉 QA 缺陷是页面局部失败。独立页面继续。

只有无法安全确定下一动作的共享状态才全局停止：例如 `run.json` 无法解析、故事板 target 集冲突、已批准文稿不可读，或同一 owner 有互相矛盾的版本。停止时保留现场，不创建替代运行。

可编辑 PPT 转换失败只影响 editable delivery，不降级有效 SVG 状态。

## 完整度

`delivery.status` 是从 `slides` 推导的结论，不是第二份页面清单：

- `complete`：每个 target 都是 `promoted`，且 final SVG 可读；
- `partial`：至少一个 target 是 `promoted`，其余均为有失败证据的 `failed` 或有明确授权的 `skipped`；
- `failed`：没有可交付页面；
- `in_progress`：仍有可执行动作或待用户决定。

结构、视觉渲染和 Office 验证分别记录。没有真实渲染写 `not_rendered`；没有 Office 实测写 `not_verified`。
