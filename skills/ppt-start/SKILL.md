---
name: ppt-start
description: Use when creating or resuming SVG presentations, redesigning an existing PPT/PPTX in a product style, or revising a PPT Pilot run for evidence-backed, PowerPoint-compatible vector delivery.
---

# PPT Pilot

## 概述

通过工作区中的持久产物开发演示文稿，而不是只在对话中一次性输出。内容决策与视觉设计必须分离；正式文稿审查通过之前禁止开始视觉设计，审查优先独立 subagent，委派失败时使用明确记录的 inline fallback。

## 输入、入口与执行策略

可接收主题、完整简报、资料集合、外部旧 PPT／PPTX、既有运行目录或定向修订请求。开始任何阶段前先读取[用户交互与确认协议](references/interaction-protocol.md)，使用固定 `scripts/ppt_entry.py` 选择或创建运行；默认 `resume`，不得自行 mkdir、追加 `recovery-N` 或复制运行。`READY` 只确定目标，之后仍须审计；`CHOICE_REQUIRED` 持久化选择后提问并停止。

**外部旧稿按产品风格重设计**：先读[旧 PPT 导入与重设计](references/source-deck-redesign.md)。已有运行即使尚未批准、被阻断或候选失败，也原位恢复；缺少批准不是新建理由。仅明确新建且入口允许创建时走 `new + source-driven`：用 `ppt_source_intake.py` 盘点原稿，建立 source_deck 绑定与源页映射，再执行全部阶段。旧 PPT、用户说“内容不变”或“只换风格”都不构成已批准文稿，不能套用纯视觉 revise 免审；二进制 `.ppt` 需真实转换为 `.pptx`。

持久执行策略只有两种：

- **guided**：新运行未显式指定策略时的默认值；在简报、大纲和锚点页批准节点提出一个直接问题，并等待明确回答。
- **auto**：只有显式指定时才使用；采用合理默认值并跳过可选问题，但需要用户权限或没有安全默认值时仍须询问。

`resume` 和 `revise` 是入口动作，不写入 `run.json.mode`：

- **resume**：先读取 `run.json`，按[工作流](references/workflow.md)的全局恢复顺序表处理 durable control state；保留既有 `run.json.mode`，只有前五者都不存在或已完成时才从第一个未完成或脏阶段继续。
- **revise**：先读取并保留既有 `run.json.mode`，同样先按[工作流](references/workflow.md)的全局恢复顺序表处理 durable control state，再按照产物契约只使受影响的产物失效；修改类别无法唯一判断时先询问。

推荐不是确认。提出阻塞问题后必须停止，不得在收到并持久化明确答案前推进下游工作。每次运行写入 `ppt-output/<deck-id>/`。禁止把产物写入本 Skill 或宿主配置目录。新运行的过程 Markdown 使用中文文件名；`resume`／`revise` 对旧英文运行只做原位读取并沿用既有名称，不自动重命名、复制或迁移，具体规则见产物契约。

## 必须执行的工作流

### 先启动实时进度面板

已有运行先审计：`resume`／`revise` 或任何已含 `run.json` 的目录，必须先执行 `ppt_workflow_gate.py --audit-run`，再考虑 dashboard。审计 `BLOCKED` 时立即停止所有写入：不启动或重启 dashboard，不暂存 generator 响应，不调用 `ingest-result`，不得手写 owner／blocker，也不继续读取低优先级运行产物。固定入口新建的最小运行也先审计，再按下段启动 dashboard。固定 `ppt_runtime.py` 不存在、摘要不符或不可执行时停止并要求维护安装；单独插件维护不得在 PPT 运行中自制 helper、复制运行时代码或安装依赖。

DSH 入口在任何阶段／dashboard 写入前先做[安装与能力只读诊断](references/deepseek-harness.md#入口诊断与升级后恢复)：新运行创建目录前执行，已有运行先通过上述审计。使用宿主本次加载 Skill 返回的真实根路径执行 `scripts/ppt_runtime.py inspect-host --host deepseek-harness`，不要猜用户级／插件级路径或沿用旧会话说明。诊断只证明安装／声明符合契约；恢复时由 coordinator 重新观测并构建 capability，不能把旧 `unregistered` 输入继续重试，也不能手写 blocker。

新运行创建目标目录后、开始资料处理前，或 `resume`／`revise` 唯一确定运行目录后，先读取[实时进度面板](references/live-dashboard.md)。DeepSeek Harness 必须先以前台命令调用 `status --run-dir <绝对路径>`：已返回 `running` 时直接复用该实际 `instance_id`／`url`，若本 coordinator 仍持有对应 job ID 则继续跟踪，**不得再次 spawn**。只有 `stopped` 时，主 coordinator 才通过宿主管理的后台命令作业（`run_in_background: true`）运行本 Skill 的 `ppt_dashboard.py serve --run-dir <绝对路径> --port 0`；不得调用会自行 detach 的 `start`，也不得让 subagent 启动服务。取得作业 ID 和 serve 的首行 JSON 后，再以另一条前台 `status` 核对相同 `instance_id`／`url`，双重验证通过才可发布 URL；保留该作业，不得在正常回合结束时 `job_kill`。Claude Code／Codex 或独立终端仍可使用 `start --open`。用户明确不需要浏览器／服务时跳过；宿主没有持久后台能力或新启动任一步失败时，先重新执行 status，只有仍为 stopped 才说明未启动并给出用户独立终端的 `serve` 命令，不得把健康旧实例误报为失败，也不得伪造链接或改变工作流质量门。

运行目录拥有最小 `run.json` 后，或任何 `resume`／`revise` 开始时，必须先运行本 Skill 的 `scripts/ppt_workflow_gate.py --run-dir <运行目录绝对路径> --audit-run`。`BLOCKED`／非零退出时报告首个错误并停止；不得先解释、重命名或继续消费低优先级状态。外部旧稿后续每个 `--before`／`--resume-active-batch` 检查都内置同一审计。审计禁止宿主自创 `native_*`、`run_level_generator_blocker`、`anchor_plan`、`execution_hold` 等平行控制状态，禁止 `complete` 前在运行目录写入非源稿 PPTX，并要求完成后的 PPTX 只由 `ppt-editable` 写入 `delivery/editable/`。

进入阶段时先持久化真实 `run.json.stage`，再执行该阶段；待确认、审查和逐页 transaction 在原契约规定的时点落盘，面板每秒读取更新。观察服务仅作展示，不向隔离 generator 添加工具，也不替代宿主对话中的批准。完成后保留面板供查看，提示对应 `stop --run-dir` 命令。

执行某阶段前，先读取该阶段链接的参考文档。

1. 简报与可选研究——[简报与研究](references/brief-and-research.md)
2. 把叙事规范化为可组合字段：金字塔原理只定 `argument_framework` 论证层级，SCQA 只定 `opening_framework` 开场过渡，三段式／Why-What-How／总-分-总只定 `sequence_template` 页面推进；冻结 `narrative_id`、`narrative_step1_bullets`、选择理由与 `outline_snapshot_id`，再产出结论先行的大纲和带稳定块／主张／来源映射的逐页故事板——[叙事与故事板](references/narrative-and-storyboard.md)
3. 文稿审查（subagent 优先，失败时 inline fallback）——[文稿审查](references/manuscript-review.md)
4. 主题、风格包与语义布局选择——先读[设计系统](references/design-system.md)和[布局目录](references/layout-catalog.md)。未指定风格且无已批准选择／工作区偏好时默认 `jiawei-product`（嘉为产品）；保留 `guided`／`auto` 确认规则。显式请求未注册或已移除的 ID 时以 `style_not_registered` 停止并要求选择已注册风格，不静默替换。
5. 在生成任何视觉页面前，先按[页面编译路径](references/visual-brief-and-generation.md)从已批准故事板与 `theme.json` 编译并验证对应 `generation-prompts/<slide-id>.md`；没有有效 prompt 不得生成 SVG。
6. 每个页面的首次生成和任何 `recompose` 都必须按[页面生成与重新排版专用 Prompt](references/redesign-prompt.md)：每个可选择 `style_pack` 必须通过 `files.prompt_template` 自带已静态物化具体视觉约定的完整模板；模板仅允许同包已验证 tokens 确定性选择闭合 `prompt_role`、独立布尔 `composition.strict_brand_rules` 引言变体与 Step 2 七条 closed typed 风格指令；其余 hard shell 字节不变，完整模板必须与 tokens 精确绑定，详见[字节契约](references/generation-prompt-byte-grammar.md)。只把故事板拥有的叙事、素材与事实值以及非来源 `block_id` 注入该模板的**单一** `{{NARRATIVE}}` whole-line 注点。缺少模板字段必须 fail closed，仓库 [generation-prompt-template.md](references/generation-prompt-template.md) 只作建包 authoring seed，不允许运行时静默 fallback。来源映射单独校验；来源注解不得进入模板正文。isolated generator 只能把每个 `block_id` 精确回显一次于规范 `<g data-block-id>` 属性值，禁止写入 text／tail／其他属性；coordinator 在任何 candidate 写入／hash／`candidate_written` 前从冻结故事板确定性关联机器来源元数据并移除临时 block 属性，泄漏以 `fact_source_mismatch` 零 candidate write 失败。完整内存 preflight 后先按[宿主隔离适配器](references/host-isolation-adapters.md)协商能力，无能力则零 prompt／transaction／candidate 写入；能力通过才按 pointer-last 写 schema-v2 per-slide transactions、batch manifest 与 `active_visual_generation_batch`。Claude Code 使用已注册的普通 `ppt-svg-generator`，且不传 `isolation` 参数。coordinator 只授予编译后的 Prompt 作为页面内容，按值传入完整冻结 `prompt_by_value`；任务使用 fresh history 并只返回文本；Claude／Codex 保持 `filesystem=none`、`data_tools=none`。DeepSeek Harness 在生成／恢复前必须读取[普通 subagent 协议](references/deepseek-harness.md)：使用 `functions.subagent` 的 fresh-context 路径，继承工具但以非内容 wrapper 禁止工具调用和再委派，不宣称硬工具隔离。工具与 ambient host context 边界以已接受适配器为准；旧 `.ppt-pilot/redesign-prompts/` 永远只读且 inert。
7. 两页锚点 SVG——[SVG 契约](references/svg-contract.md)
8. 生成任何正式页面前，先读取 [QA、恢复与修订](references/qa-and-revision.md)、[自动并发策略](references/adaptive-concurrency.md)及[宿主隔离适配器](references/host-isolation-adapters.md)。无需用户选择，规划器目标从 5 自动提高到最多 10；当前固定运行时新批次上限为 5，目标不代表五个在途任务或运行时会扩容。每次 dispatch／补位使用 `scripts/ppt_concurrency.py`，按真实宿主容量、活动批次上限和在途任务计算可派发页数；未知容量填 `null`，实际 width 1。容量／页数不足时报告实际限制；缺并发或 durable lookup 时 width 1。非 Git 不降级；Claude Code 在非 Git 目录、unborn `HEAD` 与已有提交的仓库都使用已注册 `ppt-svg-generator` 普通 subagent 并省略 `isolation`，不得执行 Git mutation 或以 worktree／remote 解锁。结构性 adapter 不可用即 `generator_unavailable` 并停止，不得轮询。每页生成与 validation 可重叠，但 candidate/transaction 写入、final promotion、visible blocker 和 `run.json` pointer 只由 coordinator 按 `ordered_slide_ids` 确定性提交。

阶段转换遵循[工作流](references/workflow.md)，视觉生命周期必须调用当前安装 Skill 的固定 `scripts/ppt_runtime.py`，其命令、声明式 staging 和恢复边界以[固定运行时 owner](references/runtime-canonical-owners.md)为权威；文件和状态字段遵循[产物契约](references/artifact-contract.md)。宿主只负责写入契约允许的 `.json`／`.txt` 输入并按值传递 prompt／结果，不在运行目录创建或执行脚本、依赖、解释器输入或 owner 修复程序。

SVG 的锚点、生产、修订与预览使用结构检查和浏览器／非 Office 渲染，不启动 PowerPoint／WPS。源稿核对与完成后的 Office 交付各走自己的分支；具体触发条件见 [SVG 渲染与 Office 边界](references/qa-and-revision.md#svg-渲染与-office-边界)。

外部旧稿运行还须从进入 research 起、在每次后续阶段进入、锚点／生产新批次生成前以及交付前执行[导入阶段检查](references/source-deck-redesign.md#3-可执行阶段检查)的 `scripts/ppt_workflow_gate.py --run-dir <run> --before <目标阶段>`。活跃批次恢复在原 owner 校验后、dispatch／候选采用／提升前执行同脚本 `--resume-active-batch`，不能先提升再检查源稿变化。BLOCKED／非零退出时提示缺失项、返回阶段和下一步并停止下游工作；不得忽略失败而补写 PASS。检查器不替代原有文稿、风格、隔离生成与 QA 门禁。

## 文稿审查是硬质量门

`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md` 全部完成即冻结并进入审查：优先委派**全新且独立的子 Agent**（只读五文件）；启动或结果归因失败时，当前步骤执行正式 `inline_fallback`，报告必须声明"当前上下文降级审查，不具备独立上下文隔离"。任一 `BLOCKER`／`HIGH` 问题状态不是 `RESOLVED` 就阻断——`OPEN` 与 `ACCEPTED_RISK` 仍然阻断；零问题也必须保存显式 `PASS` 报告；subagent 与 inline 共同计入每 cycle 三轮上限。设计师视角的材料充分性缺口以 `category: material_gap` 记录（必填 `missing_evidence` 与 `proposed_question`），由创作上下文按交互协议逐一向用户提问。findings 字段 schema、八项检查维度、重大影响判定、业务决策与批准后生产限制，一律以[文稿审查](references/manuscript-review.md)为单一权威。

## 生产、恢复与修订

- 顶层 `stage` 表示当前工作流位置。批准检查点之后，每个视觉阶段都要求 `run.json.manuscript_review.state` 持续为 `manuscript_approved`。
- 每完成一个持久阶段或一个生产批次，都更新 `run.json`。
- 候选失败先调用固定 `resume`，按其 `recoveries`／`in_flight` 在同一运行恢复或等待；WAIT、审查归因缺失和候选失败均不授权新建运行。重试上限、已证明的两次 patch 后回退与停止条件见[QA](references/qa-and-revision.md)；固定运行时没有通用 patch 命令。
- `resume` 入口必须先读取 `run.json` 并保留既有 `run.json.mode`；除非产物缺失、格式错误或被标记为脏，否则不得重新计算已批准的上游工作。
- 文稿批准和冻结证据有效时，失败页的 `layout_family`／`visual_intent` 修改使用[固定 `revise-visual`](references/runtime-canonical-owners.md#failed-page-visual-revision)：运行时只覆盖该页视觉投影，保持五份审查输入与 review hash 不变，不重审或重置 sibling。其他事实／文稿修改仍按失效协议重审；外部旧稿首次导入不能继承批准。
- 所有首次页面生成和 `recompose` 必须按 manifest → tokens → guidance → prompt 固定 traversal 读取所选中风格包必需的完整 `files.prompt_template`，再编译 `.ppt-pilot/generation-prompts/<slide-id>.md`；完成 canonical bytes 与关系门禁后按 pointer-last 激活 schema-v2 batch。coordinator 向 fresh-context 任务按值传入完整冻结 prompt bytes；DSH 的非内容执行 wrapper、继承工具边界与各宿主 ambient host context 按[宿主适配器](references/host-isolation-adapters.md)处理；`block_id` 仅可临时出现一次于规范 `data-block-id` 精确属性值，禁止进入 text／tail／其他属性。coordinator 完成来源关联并移除该属性后才原子写 candidate、复读 hash 并提交 per-slide transaction；泄漏以 `fact_source_mismatch` 零 candidate write 失败。
- 确定性 preflight 失败必须产生零 transaction 写入、零 prompt 写入、零 generator 调用和零 SVG 写入。authoritative outline／storyboard／theme 缺陷返回对应 owner；只有规范模板／规范字节／无法唯一解释的 provenance 自身失败，或完整 preflight 后宿主 adapter 不可用，才在没有本次 transaction/prompt/manifest 的情况下独立写闭合的 `run.json.visual_generation_blocker`。历史 crash 留下旧协议的 prompt／`compiling`／blocker 组合时，不采用旧 Prompt，必须从完整无副作用 preflight 重启；成功后先以一次原子 `run.json` 替换仅移除 blocker，并原样保留可能存在的 schema-v1 owner，再重新进入全局顺序完成零模型调用迁移，不能跨过 v1 创建新 transaction。
- `generator_unavailable` 是终止本次入口的结构性阻断：完整安全 preflight 后只由固定 `ppt_runtime.py prepare-batch`（或当前状态对应的固定 runtime 命令）记录规范 `visual_generation_blocker`；不得手写 `generator_unavailable` 或 owner。随后立即停止，不得改用原生 PPTX、WPS／PowerPoint 重排、当前上下文 SVG、未被适配器接受的 subagent、临时脚本或新的批准点继续生产；用户要求最终 PPTX 也不改变此规则。DSH 普通 subagent 是[已接受的独立宿主路径](references/deepseek-harness.md)，不是越过 blocker 的 fallback，仍须先通过相同 preflight 与恢复门禁。
- 主张、来源、事实性文案、大纲或故事板变化会使批准失效；重新生成视觉页面前必须进行新的文稿审查。

## 输出规则

- 最终页面是独立 UTF-8 SVG 文件，并包含 `viewBox="0 0 1280 720"`。
- 过程文件与页面保存在同一运行目录，使另一个受支持宿主可以恢复运行。
- 只使用 Office-safe SVG 子集，不使用远程资源。
- 事实无法验证时，必须限定或删除，不得把证据缺失改写成确定结论。
- 无法视觉渲染时，记录 `visual_qa: not_rendered`，不得声称视觉检查通过。

## 完成条件

只有文稿质量门通过、全部 SVG 硬检查通过、整套 QA 已写入 `.ppt-pilot/质量检查报告.md`，并且 `run.json` 的阶段为 `complete`，本次运行才算完成。

## 完成后的下一步：转可编辑 PowerPoint

每次运行达到 `complete` 后，向用户明确提示下一步可把本次运行的 SVG 交付为**可编辑 PowerPoint**：调用 `ppt-editable` 技能，把 `slides/<slide-id>.svg` 转成带原生可编辑形状/文本的 `delivery/editable/<deck-id>-editable.pptx`。

只在用户明确需要 PowerPoint（或原生可编辑形状、可编辑文本、保留 SVG 分组、Office 渲染验证）时调用 `ppt-editable`；若用户只要 SVG，不要强行转。

`ppt-editable` 负责其自身的门禁与结果状态（`PASS` / `GENERATED_UNVERIFIED` / `BLOCKED` / `FAILED_VERIFICATION`），本技能不越过 `ppt-editable` 的契约，只在完成时引导用户。
