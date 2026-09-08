# SVG 自动并发策略

首次生成和 `recompose` 的 coordinator 在宿主能力协商后、每次 dispatch／补位前读取本参考。并发量由插件自动决定，**不询问用户选择**；`guided` 和 `auto` 使用同一策略，不改变简报、大纲、文稿审查、锚点或 QA 门禁。

## 目标与实际容量

新运行的目标并发从 **5** 开始，最多 **10**。在当前已批准的故事板、主题、源审计快照范围内，每累计 5 个连续稳定通过全部单页检查的生成结果，目标增加 2：`5 → 7 → 9 → 10`。任何 `rate_limited`、`timeout`、`capacity_limited` 或 `failed` 事件都重置连续成功计数，目标回到 5。上游快照失效后重新计数，不沿用旧稿或旧主题的成功记录。

目标最低为 5 不代表任何宿主都能实际运行 5 个任务。实际并发还受宿主可用容量、剩余页数、活动批次 inventory 和安全能力约束；不足 5 时明确报告实际数量及受限原因，不能虚报并发，也不能擅自修改宿主配置。非 Git 工作区不降级。

- 有安全 fresh isolation、concurrent tasks 与 durable lookup，且容量已知时，按实际容量自动执行目标并发。
- 缺并发或 durable lookup，但仍有完整安全 fresh isolation 时降为 **width 1**；容量未知也保守使用 1，并报告限制。
- 已知可分配容量为 0 时返回 `WAIT`，等待已有任务／宿主容量变化，不记作 `generator_unavailable`，不忙轮询，不取消已有任务腾位。
- 缺少或不安全的[宿主隔离适配器](host-isolation-adapters.md)时按原契约 `generator_unavailable` 阻断，禁止当前上下文生成、嵌套 CLI 或凭据探测。这是结构性不可用，不是 `WAIT` 容量状态，不得轮询；安全接口判定仍须包含 prompt-by-value、fresh history、`filesystem=none`、`data_tools=none`、text-only result 与 attribution，不能只相信一个未验证布尔值。

本参考及入口文档中的“width 1”仅指实际调度上限为 1，不把 manifest 的 `batch_width` 改成 1。

## 只读调度规划器

使用已有 Python 3.9+：

```text
python <skill-dir>/scripts/ppt_concurrency.py --input <观测快照.json的绝对路径>
```

该脚本只读输入并向 stdout 返回 JSON，不启动模型、不写 run／transaction、不检查或替代工作流批准。实际任务仍由宿主 coordinator 调度。观测快照是 coordinator 从当前 durable 状态、已归因结果和宿主能力重建的派生输入；可放在运行的 `.ppt-pilot/concurrency-observation.json`，不是新增恢复 owner，不得覆盖原全局恢复顺序。不得把上一次快照当作实时事实。

输入示例（有 6 个 ready 页面、宿主可分配 10 路时，首次只派出前 5 页）：

```json
{
  "schema_version": 1,
  "capabilities": {
    "fresh_isolation": true,
    "concurrent_tasks": true,
    "durable_lookup": true,
    "worker_capacity": 10
  },
  "ready_slide_ids": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "in_flight_slide_ids": [],
  "history": [],
  "blocked": false
}
```

`worker_capacity` 是**本运行可占用的 generator 总槽位**：宿主实际上限扣除 coordinator 和其他运行／无关任务后所得，**包含本运行已经在途的 generator**，不是剩余空闲槽数，避免重复扣减。只能使用宿主明确报告的整数容量；未知写 `null`，不得把宿主总上限直接当作 generator 容量。

`ready_slide_ids` 是按 manifest 顺序排列、已通过 preflight 且可合法 dispatch 的 `compiled` 页；`in_flight_slide_ids` 包括所有 `generating` 页，以及已有 `host_task_id` 或 `host_attribution_id` 的 reserved `compiled` 页，包括未终结的旧 epoch 任务。两列表必须唯一且互斥。transaction 仍须先通过原 schema 校验：仅填一个 ID 等不完整记录会在规划前阻断，不能视为可重派页。只有 durable lookup／结果归因确认终结后才可释放槽位；不能靠回调到达顺序或超时猜测释放。

`history` 按已提交的结果顺序提供 `{"event_id":"唯一结果事件标识","outcome":"validated"}`。outcome 仅限 `validated`、`rate_limited`、`timeout`、`capacity_limited`、`failed`；从跨批次的 transaction／归因结果重建，同一个结果使用同一个 event ID。`validated` 必须有对应 attempt 的持久验证证据，不能把“模型返回 SVG”当成通过；重复同值事件只计一次，重复 ID 不同结果会 `BLOCKED`。恢复重放同一历史不继续升档；历史缺失保守从 5 重新开始，不能捏造成功补足计数。

可选 `batch_width` 是当前已激活批次不可变的 inventory 上限（整数 `1..10`；实际 manifest 仍按产物契约为 `3..10`），不是用户配置参数。可选 `blocked` 默认 false，但 coordinator 必须先检查实际高优先级控制状态、工作流质量门和导入 gate；存在禁止 dispatch 的条件时不得传 false 绕过它们。

输出始终含 `schema_version`、`status`（`READY`／`WAIT`／`BLOCKED`）、`target_concurrency`、`effective_concurrency`、`available_slots`、`dispatch_slide_ids`、`limitations` 和 `reason`。`READY`／`WAIT` 退出码为 0，`BLOCKED` 为 2；无效输入返回结构化 `BLOCKED` 与 `invalid_observation`，不能忽略错误继续生成。其他 limitations 区分 `worker_capacity_unknown`、`worker_capacity_limited`、`capability_limited`、`legacy_batch_cap`（也用于尚未完成的较小自动批次）、`remaining_work_limited`、`in_flight_exceeds_limit`、`fresh_isolation_unavailable`、`upstream_blocked`。

## 批次、补位与恢复

1. 先按[工作流](workflow.md)恢复全部高优先级控制状态，校验既有 manifest／transactions 与前置质量门。旧稿 active batch 仍在原 owner 内执行 `--resume-active-batch`。规划器的 `READY` 不能授权跳过这些检查。
2. 新批次按自动计算的目标选定 `batch_width`（5..10），选取最多该数量的有序页面；尾批可以只有 1 页，width 不因此写成 1。批内完整 preflight 和宿主安全能力协商通过后，仍按 pointer-last 持久化。活动批次绝不因升档扩大 inventory 或改写 width；下一批采用新目标。旧 3／4 页批次原位恢复，v1→v2 迁移仍保留原 width 4 的确定性字节。
3. 每次初始 dispatch 或完成后的补位都重新读取 transactions 和实际宿主容量，传入当前 `batch_width`。`effective_concurrency = min(目标, 宿主安全容量, 活动批次上限, ready + in_flight 页数)`；新增任务最多 `max(0, effective_concurrency - in_flight 数)`，只派出返回的有序 `dispatch_slide_ids`。容量缩小到在途数以下时等待，不追加、不取消、不重复派发。
4. coordinator 按既有一次派发协议串行预留／持久化 task attribution，并及时更新在途 inventory；再次补位前必须重新观测。禁止多次对同一旧快照调用规划器后重复 spawn，也禁止把旧 epoch 的归因任务当作空闲页。任务归因失败时保留原阻断／恢复路径，不擅自新建 epoch 重试。
5. generator 按页隔离，coordinator 只传完整 prompt by value，`fresh_history=true`、`filesystem=none`、`data_tools=none`、只返回文本；Claude ambient host context 边界按[宿主隔离适配器](host-isolation-adapters.md)处理。每页 validation 可与 sibling 生成重叠，但 candidate／transaction 写入、final promotion、最低 visible blocker 和 run pointer 仍只有 coordinator 按 `ordered_slide_ids` 串行提交。
6. 限流、超时和失败只会降低后续目标，**不授权立即重试**；先执行原有失败归因、退避、修复上限与恢复门禁，再观测是否可调度。某页耗尽修复策略后仍阻断时不能继续新派后续页。

开始生产时提示“自动并发：目标 5，实际 X，上限 10”；目标或限制发生变化时简短更新，例如“目标 7，宿主仅可分配 3 路，实际 3”。不向用户提出并发选择，不把规划输出称作已经运行的任务数；实际在途数量以宿主任务及持久归因为准。
