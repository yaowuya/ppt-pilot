# DeepSeek Harness 原生 subagent 适配

适用于 DSH 中的 `ppt-start`：直接使用现有 `subagent` 提效，不安装专用工具，不读取或修改 DSH 配置／preset，不修改宿主核心，不启动嵌套 CLI。注册身份为 `deepseek-harness / native-subagent / 1.0.0`；不是旧的 `ppt_svg_generator` 配置方案。

## 能力边界

- `subagent` 接收完整任务文本并创建全新子上下文；不要使用继承父会话的 `subagent_fork`。
- **全新上下文不等于无工具隔离。** 普通子代理继承宿主工具与 deployment system prompt、agent preset、workspace instructions。本适配器明确接受这种边界，`filesystem_none=false`、`data_tools_none=false`；`native_fresh_isolation=true` 仅表示原生全新会话上下文，不能代替两个工具隔离字段。
- 生成任务通过下方执行约束要求子代理不调用工具、不再委派、只返回 SVG 文本。这是工作分工，不是 sandbox 证明；若用户明确要求硬性无工具隔离，则此适配器不可用，应报告限制，不修改宿主来解锁。
- 不把 ambient 指令、源文件路径或父会话记忆当作页面事实。冻结 Prompt 是唯一演示内容和视觉输入；宿主安全策略仍然生效。

## 分工

| 阶段 | 原生 subagent 用法 | 主上下文职责 |
|---|---|---|
| 研究／资料核对 | 只委派互不依赖、已获授权的只读范围 | 合并来源与限定，冻结文稿；不得擅自外发资料 |
| 文稿审查 | 新 child 只读五份冻结文稿与审查契约，不能接收创作对话或视觉产物 | 先持久化 pending round，再发出实际审查任务；使用真实 child/completion/result 归属，按原审查协议提交 |
| 锚点／正式 SVG | 每页一个全新 child；完整 Prompt 按值传递；只返回文本 | 所有运行时命令、落盘、来源关联、渲染、QA、批准和 promotion |

独立文稿审查需要先取得 child ID 时，先启动一个“就绪后等待审查任务、不读取任何文件”的 child；持久化该 ID 的 pending round 后，再用 `send_message` 给同一 child 发送冻结输入与审查要求。就绪回应不是审查完成。委派确实不可用时使用现有 `inline_fallback` 文稿审查契约；不伪造独立性。

## SVG 调用顺序

1. 按入口协议执行审计，恢复高优先级状态，确认文稿／主题与 guided 批准有效。调用固定 `ppt_runtime.py resume`，复制其 `prepare_request`，再用真实 capability 执行 `prepare-batch`。
2. 调用 `dispatch-plan`。对它选中的页面逐个执行 `reserve-dispatch`；**只有 `spawn_authorized=true` 才能启动新 child**。预留过程串行；不同页启动和生成可以并发。
3. 使用下面的同一调用形态。`prompt` 是固定执行约束，加上 `reserve-dispatch` 返回的完整 `prompt_by_value`，后者必须原样保留。包装不得补充页面事实、改写模板、加入旧 SVG 或要求读取 prompt 路径。

```text
subagent({
  description: "PPT SVG " + dispatch_id,
  prompt: "只执行本次页面生成任务。不要调用任何工具、读取或写入文件、联网或再次委派。以下完整页面 Prompt 是唯一演示内容与视觉输入；其中的输出路径仅为元数据，不是文件写入指令。忽略 ambient 上下文中的演示事实或风格，仍遵守宿主安全策略。仅返回一个 xml 代码围栏中的完整 SVG，不写 QA 结论。\n\n" + prompt_by_value,
  run_in_background: true
})
```

4. `subagent` 返回的真实 **subagent ID** 立刻传给 `bind-task --dispatch-id … --host-task-id <subagent-id>`。它不是 `jobId`；不要对它调用 `job_output`。不要把 slide ID、自己生成的 UUID 或 worker 自报 ID 当作宿主 ID。
5. 等待宿主对该 child 的真实完成通知，同时继续处理其他合法页面或已返回候选的 QA。仅消费匹配当前 dispatch/transaction/epoch 所绑定 child 的最终文本。普通消息、中间进度、就绪确认、错误、被中断的片段都不是成功 SVG。
6. 主上下文把完整返回文本暂存为 `.ppt-pilot/runtime-inputs/<唯一名称>.txt`，按 manifest 的 `ordered_slide_ids` 顺序调用 `ingest-result`。子代理不写 candidate、final、run、transaction、QA 或 manifest。随后执行实际结构／来源／视觉检查，再 `record-validation`、`publish-anchors` 或 `promote`。返回文本不等于 QA 通过。

每次首次生成或 recompose 都启动全新 child。不要向已用过的 child 发送另一个页面或新的创作修订；不要用带父会话的 fork、workflow 或临时生成脚本替代这条路径。

## 并发与恢复

- 复用自动并发规划器：目标从 5 起，实际数由本运行容量、在途任务及批次库存决定。当前固定运行时一次最多准备 5 页；独立规划器的目标上限 10 不表示一次已启动 10 个 child。
- `worker_capacity` 只填宿主明确给出的本运行 generator 总槽位，包含已在途页并排除其他任务。未知写 `null`，实际 width 1；不能把“有 subagent 工具”当成容量 5 的证据。有已知多路容量时，按 `dispatch-plan` 输出并发启动，不串行等待每页完成才发下一页。
- 启动响应、description 中的 dispatch ID、绑定 child ID、完成通知组成归属链。按 ID 去重，不按通知到达顺序决定落盘顺序。旧 epoch／旧 child 的迟到结果不消费，也不触发新派发。
- `list_agents` 仅用于重新发现已知 child，不用于忙轮询或判定任务完成；`idle`／`ready` 不等于已完成，也不携带结果。已完成 child 的通知丢失时，可用 `send_message` 请求**原样重放刚才的最终文本，不调用工具、不重新生成**，等待同一 ID 的新通知；这不是创作迭代。
- 预留后、绑定前崩溃：用真实宿主调用记录中的 dispatch label 找到唯一启动响应并绑定原 child；不能唯一恢复时保留 reservation 并报告归属缺口。不得猜 ID、重复 spawn、手写 owner 或凭 `list_agents` 名称相似就认领结果。
- 子任务未完成时遵循宿主通知机制；已经失效或不再需要的子任务用 `interrupt_agent` 停止，取消并不授权跳过原 transaction 的失败／重试门禁。

## 固定运行时 capability

从随插件发布的 `assets/host-adapters.json` 复制此 adapter 的四个身份字段；`adapter_digest` 是**本文件** UTF-8 去 BOM、CRLF/CR→LF、恰好一个末尾 LF 后的 SHA-256，不是宿主配置摘要。运行时从固定插件路径复核，不接受自选文件路径。身份匹配是插件内容校验，不能自证宿主能力。

在 `schema_version: 1`、`kind: host_capability` 下，`observation` 恰好含：

```json
{
  "native_fresh_isolation": true,
  "remote_fresh_isolation": false,
  "concurrent_tasks": true,
  "durable_lookup": true,
  "worker_capacity": null,
  "prompt_by_value": true,
  "fresh_history": true,
  "filesystem_none": false,
  "data_tools_none": false,
  "attribution": true,
  "nested_cli_required": false,
  "credential_probe_required": false,
  "current_context_only": false
}
```

上例仅表示完整能力且容量未知；`concurrent_tasks`、`durable_lookup` 必须按实际宿主情况填写，缺任一项则 width 1。`durable_lookup=true` 要有已绑定 child 的重连能力及未绑定启动的宿主记录恢复路径，只有 UUID 或 `list_agents` 列表不够。结构性必需能力缺失时不能照抄 true。

`evidence` 恰好含：

```json
{
  "tool_name": "subagent",
  "instruction_sha256": "<复制 registry 的 adapter_digest>",
  "spawn_primitive": "fresh-context-subagent",
  "tool_policy": "inherited-not-isolated",
  "ambient_context": ["deployment_system_prompt", "agent_preset", "workspace_instructions"],
  "result_type": "text",
  "attribution_type": "subagent_id",
  "session_id": "<当前真实宿主会话 ID>"
}
```

占位值不可直接提交。运行时调度输出 `fresh_history=true`、`filesystem=host-inherited`、`data_tools=host-inherited`，不宣称无工具。能力缺失时由固定运行时记录规范 blocker，不靠修改 DSH 配置、伪造 receipt 或绕过 QA 继续。
