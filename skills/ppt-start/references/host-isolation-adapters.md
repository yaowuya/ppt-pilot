# 页面生成宿主隔离适配器

## 抽象能力

页面 generator 的共同要求是 fresh conversation history（不继承父会话聊天记录）、完整 Prompt 按值传入、text-only result 与稳定 attribution。工具边界按已接受适配器验证：Claude Code／Codex 要求 `filesystem=none`、`data_tools=none`；DeepSeek Harness 使用下述 fresh-context、提示策略限制路径，**不具备硬工具隔离**。

`filesystem=none` 表示 worker 没有可主动读取或写入工作区的工具；`data_tools=none` 表示不存在可读取或写入业务数据的工具。宿主保留无数据控制工具不改变这两个声明，不得把继承数据工具的 DSH worker 填成无工具。

Prompt 是 coordinator 主动传入的唯一 PPT Pilot 内容载荷；DSH 允许的非内容执行 wrapper 不增加或改写冻结 Prompt，具体字节边界见[DSH 协议](deepseek-harness.md)。宿主自动加载的安全策略、项目指令或 VCS 摘要属于 ambient host context，必须明确枚举并由 worker 忽略，不能作为幻灯片事实、措辞或视觉方向；coordinator 不得额外传入父会话聊天记录、源稿、旧 SVG、工作区内容或 prompt 路径。

## Claude Code

Claude support is additive. Keep both installed adapters available, and select by the current host capability:

- **Agent SDK 1.9.0 host:** use registered `ppt-svg-generator-sdk` as an ordinary fresh-context foreground subagent. Set `run_in_background: false` and `allowed_tools: ["ListAgents"]`; the control-only `ListAgents` capability does not grant filesystem or business-data access. Always omit `isolation`; fresh conversation context must not be implemented with a Git worktree or remote isolation.
- **Legacy Claude host:** retain registered `ppt-svg-generator` as an ordinary fresh-context subagent, omit `isolation`, and allow only `TodoWrite`. Do not silently downgrade an SDK-capable host to this path or remove this path from a legacy host.

Both adapters receive only the complete Prompt by value and return text. Claude automatically loads `CLAUDE.md` and parent Git status; both adapters explicitly ignore this ambient host context and therefore do not claim byte-pure prompt-only execution. Neither adapter has filesystem, shell, network, Skill, MCP, browser, or business-data tools. If the caller requires absence of ambient host context, neither accepted Claude adapter satisfies that stricter capability and negotiation returns `generator_unavailable`.

For the SDK adapter, foreground completion must include completed text and a real task ID. The coordinator binds that task ID to the reserved dispatch before staging or ingesting the response. For either adapter, an accepted receipt binds the complete `host` + `adapter_id` + `version` + registered digest identity; a matching digest from another host, adapter, or version is insufficient. Runtime inspection, audit, `advance`, and resume validate the selected current identity but never invoke the standalone adapter-upgrade helper. Adapter upgrade is a separate, explicitly authorized maintenance action, not a page-recovery operation.

Git state does not authorize repository mutation. Do not run `git init`, `git add`, `git commit`, `git push`, switch repositories, or create an isolation worktree. Fresh conversation isolation is provided by the ordinary subagent route; if the host requires worktree or remote isolation, the Claude adapter is unavailable. This changes isolation mechanics, not Prompt contents, attribution, task-binding order, or the inherited three-dispatch page lifetime.

Agent unregistered, ordinary subagent unavailable, selected adapter receipt mismatch, unexpected data tools, Prompt not passable by value, missing attribution/task ID, forced worktree or remote isolation, or an unsatisfied byte-pure requirement yields structural `generator_unavailable`. The coordinator records the closed run-level blocker only through the [fixed runtime](runtime-canonical-owners.md) and [artifact contract](artifact-contract.md#可选-visual_generation_blocker); this is not capacity waiting and is reconsidered only after an actual host/install change plus explicit resume.

结构性不可用不得轮询，也不能通过修改 Git 状态、切换到未注册生成器或重置次数来解锁。

## Codex

Codex 只有在当前宿主公开的 native/remote task 原语能够逐项证明 prompt-by-value、fresh history、`filesystem=none`、`data_tools=none`、text-only result 与稳定 attribution 时才满足接口。缺 concurrency 或 durable lookup 但仍满足完整安全接口时只把实际 dispatch 降为 width 1；缺核心隔离能力时 fail closed。不得以 worktree 本身、普通协作者或当前 coordinator 上下文替代隔离证明。

## DeepSeek Harness

生成、补位或恢复页面前，必须读取[DeepSeek Harness 普通 subagent 协议](deepseek-harness.md)。插件 registry 接受 `host: deepseek-harness`、`adapter_id: native-subagent`、版本 `1.0.0`；使用普通 `functions.subagent`，固定 `run_in_background: true`。它返回 durable `subagent_id`（agent UUID），不是 `jobId`；coordinator 先将其绑定为 `host_task_id`，再消费同一 child 的完成文本。`subagent_fork`、专用 `ppt_svg_generator`、workflow agent 和嵌套 CLI 不属于此路径。

`native_fresh_isolation=true` **只表示 fresh context**：`fresh_history=true`、`current_context_only=false`，但 `filesystem_none=false`、`data_tools_none=false`。worker 继承工具；不调用工具、不再委派、只返回一个 `xml` 围栏是 prompt policy，不是 sandbox 保证。coordinator 传入同一份冻结完整 Prompt 与非内容执行 wrapper，独占文件写入、candidate/hash/transaction/final 与 QA 提交。DSH deployment system prompt、agent preset 与 workspace instructions 是 ambient host context，不作为页面事实／措辞／视觉方向；安全策略仍生效。

先 reserve，再用含真实 `dispatch_id` 的无页面内容 `description` 启动并立即 `bind-task`；完成通知必须与已绑定 child ID 匹配。`list_agents` 只作发现，不轮询或充当结果查询；必要时 `send_message` 只向同一 child 取回已完成的原答案，不重新生成。丢失 launch 且无法唯一关联时保留 reservation 并停止，不能重复 spawn。归因、去重和恢复细节以[DSH 协议](deepseek-harness.md)为准。

并发使用真实容量；未知写 `null` 并使用 width 1，不保证五个活动 child。当前固定运行时新批次上限为 5；规划器目标可达 10 不证明运行时会扩大批次。此适配不要求读取／修改 DSH 配置、安装 profile patch、重启或部署 DSH。实际宿主能力不符合接受的协议时，完整 preflight 后只由固定运行时记录规范 `visual_generation_blocker` 并停止；不以原生 PPTX、WPS/PowerPoint、当前上下文 SVG 或平行控制状态绕过。显式 resume 重新核验实际能力与原有 owner，不通过配置探测解锁。

任何宿主都不得调用嵌套 CLI 或使用 coordinator 当前上下文生成。
