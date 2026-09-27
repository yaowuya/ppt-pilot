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
  "active_generation_wave": null,
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
3. 每轮执行一个非生成动作，或一个独立页面的有界生成 wave；默认并发 5，显式串行 1，显式并发 2–10。没有隐藏队列、忙等或自动循环。
4. 先写入并读回真实证据，再原子更新状态。
5. 报告本轮动作、工具降级、页面失败、下一动作和待决定事项。

只有真实 fresh-context 生成调用才增加该页 `attempts`；只有宿主接受完整 Prompt 并返回可恢复的任务归因，才算该调用发生。读取、校验、格式转换、容量拒绝、工具启动失败、用户 skip 和恢复检查都不得增加或重置它。

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

### 有界 generation wave

`active_generation_wave` 是 AI 暂存的协调证据，不是队列或第二份页面 inventory；`slides` 始终是页面 authority。只有同一运行、同一阶段、同一已批准故事板／文稿／主题快照下，且 Prompt 与 page-specific source map 已完整写入并读回、互不依赖的页面才能进入同一 wave。锚点 wave 与 production wave 不能跨越批准门。

默认并发 5；显式串行宽度为 1，显式并发宽度为 2–10。实际宽度取 target、剩余 eligible 页面和已知 host capacity 的最小值。准备阶段按故事板顺序选择页面，并在任何 Agent 调用前原子写入：

```json
{
  "active_generation_wave": {
    "schema_version": 1,
    "wave_id": "wave-S02-S06-01",
    "stage": "production",
    "status": "prepared",
    "target_width": 5,
    "ordered_slide_ids": ["S02", "S03", "S04", "S05", "S06"],
    "prompt_sha256": {
      "S02": "sha256:d4df06e9137784f7529d8a018c4801f664c512389c2656bbf3b12b8ff1df9f12",
      "S03": "sha256:c41ec4b66d5bf8b7b1723e827ad29aa953dd055c8eff00334c0735407cffa141",
      "S04": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "S05": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "S06": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    },
    "accepted_tasks": {}
  }
}
```

示例 digest 只展示字段语法；真实运行必须从每份实际读回的 Prompt 字节计算。宿主接受调用后，`accepted_tasks` 只记录真实返回的 durable task attribution：

```json
{
  "S02": {
    "task_id": "task-S02-01",
    "attempt": 1,
    "prompt_sha256": "sha256:d4df06e9137784f7529d8a018c4801f664c512389c2656bbf3b12b8ff1df9f12",
    "state": "in_flight"
  }
}
```

不变量：

- `status` 只能是 `prepared|collecting`；`ordered_slide_ids` 无重复且保持故事板顺序；
- `prompt_sha256` 的 key 必须与 `ordered_slide_ids` 完全相同，且摘要来自实际读回字节；
- `accepted_tasks` 的 key 是 `ordered_slide_ids` 的子集，task ID 非空且 Prompt digest 一致；
- 只有 task attribution 被宿主接受并写入后，相应 `slides[id].attempts` 才增加一次并进入 `generating`；prepared 但未接受的页面不消耗 attempt；
- 同一 `task_id` 与 Prompt digest 的重复归因幂等：保持原 attempt 和 task state，不再次增加 attempts；
- 归因冲突（同页 task/digest 被替换、同一 task ID 绑定多页或 attempt 不一致）必须 fail closed，只使该页成为 `generator_attribution_unknown`，不覆盖证据、不猜测或重复计数；
- 已接受 task ID 在恢复时只 resume／consume，绝不因新回合重新 dispatch；
- 所有 accepted task 终止并按顺序处理，且未接受页面恢复 eligible 后，清除 wave；最终 `complete|partial|failed` 必须让 `active_generation_wave` 为 `null` 或不存在。

### Generator setup 证据

[生成器恢复协议](visual-brief-and-generation.md) 是原生路由和本地 HEAD 修复的唯一规则；这里仅定义已有页面 record 中的审计证据，不创建新的流程 owner。

旧的 `claude_code_local_git_initialized` **不代表 HEAD 就绪**，只证明曾初始化目录。旧版初始化不消耗本次 HEAD 修复机会；保留旧证据，在确认同一安全根目录和授权后恢复。只有从宿主实际启动目录验证通过，才保存新的 `generator_setup`：

```json
{
  "generator_setup": {
    "protocol_version": 2,
    "kind": "claude_code_local_git_head_ready",
    "scope": "presentation_workspace_root",
    "trigger": "host_git_head_required",
    "head": "<实际验证返回的 Git 对象 ID>"
  }
}
```

`scope` 按实际选择记录为 `presentation_workspace_root` 或 `ppt_output_parent`；`trigger` 为真实的 `host_git_required` 或 `host_git_head_required`。复用已有有效 HEAD 也必须实际验证，不能用旧 init 成功记录代替，也不能伪造对象 ID。head-ready 只证明宿主基准，不证明 generator／SVG PASS。

失败时，在既有页面证据中记录 `generator_setup.protocol_version: 2`、`kind: claude_code_local_git_head_unavailable`、实际失败步骤和 `failure.code: generator_unavailable`，保持 stage 和 attempts。恢复时读取该证据；对同一宿主／根目录／错误且环境未变的情况不重复追加失败、不重复消耗 setup 机会。只有原生路由、权限、宿主能力、Git 状态或修复协议实际改变，才重新评估；“继续”本身不是环境修复。

### 生成预算

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
