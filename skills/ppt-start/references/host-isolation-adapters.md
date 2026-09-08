# 页面生成宿主隔离适配器

## 抽象能力

页面 generator 需要 fresh conversation history（不继承父会话聊天记录）、完整 Prompt 按值传入、`filesystem=none`、`data_tools=none`、text-only result 与稳定 attribution。`filesystem=none` 表示 worker 没有可主动读取或写入工作区的工具，不承诺宿主启动消息是 byte-pure；`data_tools=none` 表示不存在可读取或写入业务数据的工具。宿主为允许 subagent 启动而保留的无数据控制工具不改变该结论，也不得成为生成输入、输出或正确性依赖。

Prompt 是 coordinator 主动传入的唯一 PPT Pilot 内容载荷。宿主自动加载的安全策略、项目指令或 VCS 摘要属于 ambient host context，必须明确枚举并由 worker 忽略，不能作为幻灯片事实、措辞或视觉方向；coordinator 不得额外传入父会话聊天记录、源稿、旧 SVG、工作区内容或 prompt 路径。

## Claude Code

Claude Code 必须选择已安装的 `ppt-svg-generator`，以普通 fresh-context subagent 启动，并省略 `isolation`。不得把 fresh conversation context 映射为 worktree checkout。

Claude Code 会自动加载 `CLAUDE.md` 与父会话的 Git status；本适配器明确接受并忽略这两类 ambient host context，**不提供 byte-pure prompt-only** 保证。该 agent 的允许工具只能是 `TodoWrite`；它没有 filesystem、shell、network、Skill、MCP 或 browser 数据能力，不能主动读取源稿或工作区。coordinator 只传完整 Prompt 文本，并只消费返回文本。若调用方要求连 ambient host context 都不存在的严格模式，则当前 Claude Code 普通 subagent 不满足能力，必须返回 `generator_unavailable`。

Git 状态不参与路由：普通目录、unborn `HEAD` 和已有提交的仓库都选择同一 agent。禁止运行 `git init`；禁止运行 `git add`；禁止运行 `git commit` 或创建空提交；禁止运行 `git push`；不得请求 `isolation: worktree`；不得请求 `isolation: remote`；不得切换到另一仓库作为基线。

agent 未注册、普通 subagent 不可用、宿主强制 worktree/remote、agent 暴露数据工具、Prompt 不能按值传入、attribution 不可用，或调用方要求 byte-pure prompt-only 时，按结构性不可用返回 `generator_unavailable`。coordinator 只按[产物契约](artifact-contract.md#可选-visual_generation_blocker)写入闭合的 run-level blocker；该结果不是容量等待，不得轮询，只有安装/宿主配置实际变化后的显式 resume 才重新协商。

## Codex

Codex 只有在当前宿主公开的 native/remote task 原语能够逐项证明 prompt-by-value、fresh history、`filesystem=none`、`data_tools=none`、text-only result 与稳定 attribution 时才满足接口。缺 concurrency 或 durable lookup 但仍满足完整安全接口时只把实际 dispatch 降为 width 1；缺核心隔离能力时 fail closed。不得以 worktree 本身、普通协作者或当前 coordinator 上下文替代隔离证明。

## DeepSeek Harness

DeepSeek Harness 当前没有可由本 Skill 静态假定为已验证的 generator adapter。每次视觉批次必须从实际宿主调用面重新取得六项能力证据；“可以创建普通 subagent”、提示词要求其不要读文件、或事后声称未使用工具，都不能证明 `filesystem=none`／`data_tools=none`。

六项能力任一缺失时，coordinator 只能以一次原子 `run.json` 替换写入规范 `visual_generation_blocker`：`state: generator_unavailable`、`reason: generator_unavailable`、`resource: none`、当前 style/snapshot 与最低受影响 `slide_id`，然后立即结束本次入口。禁止创建 `run_level_generator_blocker`、`native_delivery`、`native_anchor`、`anchor_plan` 或 `execution_hold` 等平行状态；禁止调用 WPS/PowerPoint、生成原生 PPTX、用当前上下文画 SVG、启动带数据工具的通用 subagent，或通过嵌套 CLI 规避。只有宿主配置或能力实际改变后的显式 resume 才重新协商。

任何宿主都不得调用嵌套 CLI 或使用 coordinator 当前上下文生成。
