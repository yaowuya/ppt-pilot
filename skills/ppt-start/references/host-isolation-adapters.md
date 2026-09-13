# 页面生成宿主隔离适配器

## 抽象能力

页面 generator 的共同要求是 fresh conversation history（不继承父会话聊天记录）、完整 Prompt 按值传入、text-only result 与稳定 attribution。工具边界按已接受适配器验证：Claude Code／Codex 要求 `filesystem=none`、`data_tools=none`；DeepSeek Harness 使用下述 fresh-context、提示策略限制路径，**不具备硬工具隔离**。

`filesystem=none` 表示 worker 没有可主动读取或写入工作区的工具；`data_tools=none` 表示不存在可读取或写入业务数据的工具。宿主保留无数据控制工具不改变这两个声明，不得把继承数据工具的 DSH worker 填成无工具。

Prompt 是 coordinator 主动传入的唯一 PPT Pilot 内容载荷；DSH 允许的非内容执行 wrapper 不增加或改写冻结 Prompt，具体字节边界见[DSH 协议](deepseek-harness.md)。宿主自动加载的安全策略、项目指令或 VCS 摘要属于 ambient host context，必须明确枚举并由 worker 忽略，不能作为幻灯片事实、措辞或视觉方向；coordinator 不得额外传入父会话聊天记录、源稿、旧 SVG、工作区内容或 prompt 路径。

## Claude Code

Claude Code 必须选择已安装的 `ppt-svg-generator`，以普通 fresh-context subagent 启动，并省略 `isolation`。不得把 fresh conversation context 映射为 worktree checkout。

Claude Code 会自动加载 `CLAUDE.md` 与父会话的 Git status；本适配器明确接受并忽略这两类 ambient host context，**不提供 byte-pure prompt-only** 保证。该 agent 的允许工具只能是 `TodoWrite`；它没有 filesystem、shell、network、Skill、MCP 或 browser 数据能力，不能主动读取源稿或工作区。coordinator 只传完整 Prompt 文本，并只消费返回文本。若调用方要求连 ambient host context 都不存在的严格模式，则当前 Claude Code 普通 subagent 不满足能力，必须返回 `generator_unavailable`。

Git 状态不参与路由：普通目录、unborn `HEAD` 和已有提交的仓库都选择同一 agent。禁止运行 `git init`；禁止运行 `git add`；禁止运行 `git commit` 或创建空提交；禁止运行 `git push`；不得请求 `isolation: worktree`；不得请求 `isolation: remote`；不得切换到另一仓库作为基线。

agent 未注册、普通 subagent 不可用、宿主强制 worktree/remote、agent 暴露数据工具、Prompt 不能按值传入、attribution 不可用，或调用方要求 byte-pure prompt-only 时，按结构性不可用返回 `generator_unavailable`。coordinator 只通过[固定运行时](runtime-canonical-owners.md)记录[产物契约](artifact-contract.md#可选-visual_generation_blocker)的闭合 run-level blocker，不手写 owner；该结果不是容量等待，不得轮询，只有安装/宿主配置实际变化后的显式 resume 才重新协商。

## Codex

Codex 只有在当前宿主公开的 native/remote task 原语能够逐项证明 prompt-by-value、fresh history、`filesystem=none`、`data_tools=none`、text-only result 与稳定 attribution 时才满足接口。缺 concurrency 或 durable lookup 但仍满足完整安全接口时只把实际 dispatch 降为 width 1；缺核心隔离能力时 fail closed。不得以 worktree 本身、普通协作者或当前 coordinator 上下文替代隔离证明。

## DeepSeek Harness

生成、补位或恢复页面前，必须读取[DeepSeek Harness 普通 subagent 协议](deepseek-harness.md)。插件 registry 接受 `host: deepseek-harness`、`adapter_id: native-subagent`、版本 `1.0.0`；使用普通 `functions.subagent`，固定 `run_in_background: true`。它返回 durable `subagent_id`（agent UUID），不是 `jobId`；coordinator 先将其绑定为 `host_task_id`，再消费同一 child 的完成文本。`subagent_fork`、专用 `ppt_svg_generator`、workflow agent 和嵌套 CLI 不属于此路径。

`native_fresh_isolation=true` **只表示 fresh context**：`fresh_history=true`、`current_context_only=false`，但 `filesystem_none=false`、`data_tools_none=false`。worker 继承工具；不调用工具、不再委派、只返回一个 `xml` 围栏是 prompt policy，不是 sandbox 保证。coordinator 传入同一份冻结完整 Prompt 与非内容执行 wrapper，独占文件写入、candidate/hash/transaction/final 与 QA 提交。DSH deployment system prompt、agent preset 与 workspace instructions 是 ambient host context，不作为页面事实／措辞／视觉方向；安全策略仍生效。

先 reserve，再用含真实 `dispatch_id` 的无页面内容 `description` 启动并立即 `bind-task`；完成通知必须与已绑定 child ID 匹配。`list_agents` 只作发现，不轮询或充当结果查询；必要时 `send_message` 只向同一 child 取回已完成的原答案，不重新生成。丢失 launch 且无法唯一关联时保留 reservation 并停止，不能重复 spawn。归因、去重和恢复细节以[DSH 协议](deepseek-harness.md)为准。

并发使用真实容量；未知写 `null` 并使用 width 1，不保证五个活动 child。当前固定运行时新批次上限为 5；规划器目标可达 10 不证明运行时会扩大批次。此适配不要求读取／修改 DSH 配置、安装 profile patch、重启或部署 DSH。实际宿主能力不符合接受的协议时，完整 preflight 后只由固定运行时记录规范 `visual_generation_blocker` 并停止；不以原生 PPTX、WPS/PowerPoint、当前上下文 SVG 或平行控制状态绕过。显式 resume 重新核验实际能力与原有 owner，不通过配置探测解锁。

任何宿主都不得调用嵌套 CLI 或使用 coordinator 当前上下文生成。
