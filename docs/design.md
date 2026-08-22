# PPT Pilot MVP 设计文档

## 目标

PPT Pilot 是面向 Claude Code 与 OpenAI Codex 的可移植 Agent Skill。它把主题、简报、资料集合或既有运行转换为 6–15 页、16:9 的演示文稿，最终每页交付为独立 SVG 文件。

MVP 刻意保持纯指令架构。它只使用宿主常规的工作区能力，以及可选研究／视觉能力；不强制依赖 MCP 服务、API SDK、后台服务、Hook、嵌套 Skill、Shell 脚本或软件包运行时。

可执行 Skill 标识为 `ppt-start`。产品名称仍为 PPT Pilot；宿主调用方式见 [README](../README.md)。

## 产品原则

1. 内容先于外观。
2. 每页只表达一个结论，并以证据或明确限定支持。
3. 中间文件是产品状态，不是附带日志。
4. 文稿批准必须由全新审稿人负责，不能由创作上下文自批。
5. 文稿获批前禁止视觉设计。
6. SVG 兼容性与可读性优先于装饰效果。
7. 任何不可用能力都必须披露，不能悄然模拟。

## 共享 Skill 架构

标准包位于 `skills/ppt-start/`：

- `SKILL.md`：精简的编排入口和发现入口；
- `references/`：各阶段流程与契约；
- `assets/styles/registry.json`：风格发现注册表；
- `assets/styles/*.json`：三个兼容的扁平风格种子；
- `assets/styles/minimal-business.redesign.md`、`assets/styles/tech-dark.redesign.md`、`assets/styles/bold-editorial.redesign.md`：三个 legacy seed 自有完整 redesign prompt；
- `assets/styles/<style-id>/`：包含 manifest、tokens、中文抽象设计指导与自有完整 prompt 的 rich style packs；当前 `canway-midyear-review/REDESIGN.md` 由 Canway manifest 声明；
- `assets/examples/`：一份 Office-safe SVG 示例。

运行目录中的 `visual-briefs/<slide-id>.md` 是自包含的逐页视觉生成状态，不属于共享 Skill 安装资产；首次生成、用户 `recompose` 与确定性回退还会编译并持久化 `generation-prompts/<slide-id>.md`，其中包含所选风格完整 prompt 的替换后正文和 provenance。

共享 `references/redesign-prompt.md` 是 resolver-only contract：它只规定 selected style identity、registry／manifest／legacy companion 解析、路径 containment、模板 marker、snapshot、blocker、transaction、fresh generator 输入隔离和失败恢复。它不得保存四个风格的完整视觉生成正文，也不得把某个风格的布局语言作为共享默认。

共享 frontmatter 只包含 `name` 与 `description`，其中 `name` 为 `ppt-start`。运行时指令使用“读取、写入、委派、检查”等语义动作，不依赖宿主专属工具名、变量、权限语法或调用语法。

宿主专属安装位置和启动命令只写在 `README.md` 与验收文档中，不进入共享运行时指令。

本地契约测试只能证明文件结构、规则引用和静态资产一致，不能证明 Claude Code／Codex 的实际模型行为、跨宿主视觉一致性、浏览器渲染或 PowerPoint 导入；这些能力继续以独立人工验收台账为准。

## 工作流

```text
brief
  -> optional research
  -> assertion-led outline
  -> page storyboard
  -> mandatory independent manuscript review
  -> theme and layout planning
  -> two anchor SVGs
  -> batched SVG production
  -> per-slide and deck-level QA
  -> complete
```

对应的稳定阶段值为：

```text
brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete
```

`guided` 与 `auto` 是写入 `run.json.mode` 的持久执行策略。`guided` 在简报、大纲和锚点 SVG 后提出一个直接问题并等待明确批准；新运行未显式指定策略时默认 `guided`。只有显式 `auto` 才跳过可选问题和批准，但用户权限或没有安全默认值的决策仍然阻塞，且全部中间产物仍需创建和验证。`new`、`resume` 与 `revise` 是入口动作：恢复和修订先读取 `run.json`、保留既有执行策略，再分别继续未完成工作或使受影响依赖项失效。

`theme` 阶段把已批准故事板、当前主题、权威视觉修订历史和 SVG／QA 契约归并为逐页 visual brief。`anchor` 与 `production` 只能消费有效 brief；SVG 本身不是设计状态。visual brief 组装属于既有阶段内部工作，不增加新的顶层阶段值。

## 用户交互与确认

交互由独立的共享参考协议定义，不依赖宿主专属工具。编排上下文先检查请求、工作区和已有产物，把决策分为已知、可安全默认和必须询问三类，形成按工作流顺序排列的决策队列。一次只提出一个实质性问题；有限选择提供 2–4 个互斥选项、逐项效果和推荐理由。推荐不是确认，提问后必须停止，明确回答持久化前不得推进下游阶段。

简报、大纲和锚点是 guided 强制批准点。研究授权、故事板冲突、审稿业务决策、缺少品牌方向和生产阻断只在没有安全默认值时触发。`auto` 可以记录保守假设，但不能自行授权网络传输、机密披露或改变核心业务立场。

为了支持跨宿主恢复，`schema_version: 1` 允许可选顶层 `pending_interaction` 与 `interaction_history`。`pending` 保存当前问题、逐项效果和推荐理由；回答先以 `answered`、原始 `answer` 和有限选择的规范化 `decision` 持久化。阶段产物按交互 ID 幂等更新后，`run.json` 以单次原子替换同时写入权威交互历史、目标阶段和对象删除／替换，不会留下阶段与旧问题错位的文件。阶段产物记录只是可重建镜像，失效不能删除权威历史。同一批准检查点通过单调 `approval_attempt` 生成独立交互 ID，后续批准不会覆盖此前修订事件。等待期间原有 `stage` 不变，不增加暂停状态。首次阻塞问题也必须在一个新建且不冲突的运行目录中先持久化；缺少这些可选字段的旧运行继续有效，格式错误则停止并报告。

当恢复／修订目标无法唯一确定时，工作区级 `ppt-output/run-selection.json` 先保存候选、`entry_action`、原始 `operation_payload` 与目标选择问题，不修改任何候选运行；选定运行按保存的完整操作到达下一个持久状态后才删除该路由文件。

## 文件化运行协议

每套演示文稿位于 `ppt-output/<deck-id>/`：

```text
run.json
简报.md
研究.md
来源.md
大纲.md
故事板.md
文稿审查.md
theme.json
visual-briefs/<slide-id>.md
generation-prompts/<slide-id>.md
samples/*.svg
slides/*.svg
质量检查报告.md
```

`run.json` 使用 `schema_version: 1`，记录 `guided`／`auto` 执行策略、当前阶段、文稿审查状态、可选的 `pending_interaction`／`interaction_history`、`visual_generation_blocker`、`visual_generation_transaction` 和脏页面；入口动作不写入 `mode`。`manuscript_review.cycle` 也是可选 schema-v1 字段，旧运行缺少时按 1。直接视觉修订以 `visual-revision-<N>` 保存在权威 `interaction_history`，并通过 `supersedes` 排除废弃规则。每个 `visual-briefs/<slide-id>.md` 记录锁定内容、主题与风格 provenance、有效修订、层级、构图、模式和 QA 要求；其中 `generation_intent` 与 `generation_trigger_id` 说明当前视觉操作的持久来源，不能从 SVG 是否存在或用户措辞猜测。`generation-prompts/<slide-id>.md` 记录 resolved prompt path、style／brief／theme／storyboard snapshots、`compiled_prompt_sha256`、`prompt_snapshot_id` 和 transaction provenance。这些文件足以让一个受支持宿主把运行交给另一个宿主，而不依赖此前对话。

中文 Markdown 名称是新运行的标准。为了让既有运行仍能恢复，`resume`／`revise` 可以继续原位读取旧英文名称 `brief.md`、`research.md`、`sources.md`、`outline.md`、`storyboard.md`、`manuscript-review.md` 和 `qa-report.md`，但不得自动重命名、复制或迁移。实际名称由 `run.json` 的引用字段和目录中的完整文件集合共同决定；无法唯一判定时停止并报告冲突。

上游变化按最早受影响阶段重入并使依赖项失效：

- 简报变化：返回 `brief`，全部下游产物失效；
- 主张或来源变化：返回 `research`；大纲变化返回 `outline`；故事板变化返回 `storyboard`；这些变化都把嵌套审查授权重置为 pending，并使全部视觉产物失效；
- 主题变化：返回 `theme`，全部 visual brief、样例、正式页面和视觉 QA 失效；文案未变时可以保留文稿批准；
- 锚点内纯视觉修改：返回 `anchor`，使受影响锚点 brief、锚点和依赖项失效并保留有效文稿批准；
- 单页 `recompose`：使该页 brief、SVG 和 QA 失效；单页 `patch`：只使该页 SVG 和 QA 失效，并在 brief 中更新精确 defect 与候选版本。

## 强制独立文稿审查

只有 `简报.md`、`研究.md`、`来源.md`、`大纲.md` 和 `故事板.md` 全部完成并冻结，才到达文稿边界。

编排上下文把这五个输入委派给全新独立子 Agent，并只授予只读访问。审稿人能看到五个文稿文件和审查规范，但不能看到创作对话、设计主题、样例或正式页面。审稿人只返回结构化问题与来源载荷，绝不修改工作区文件。创作上下文把载荷原样保存到当前运行的审查报告（新运行为 `文稿审查.md`，旧英文运行沿用 `manuscript-review.md`），后续作者修订说明另行记录；文稿修订只能由创作上下文完成。

独立性需要机器可关联的委派证据，不能只靠文字标签。每轮都把宿主返回的 `child_context_id`、`completion_event_id` 和 `result_context_id` 写入 `delegation_evidence`；子上下文 ID 与结果上下文 ID 必须相等。虚构名称、叙述、休眠或空等待都不能证明委派。如果宿主无法返回可归因的子上下文结果，运行进入 `review_unavailable`，创作上下文不得伪造问题。

状态文件只是可移植记录，不是加密证明：`run.json` 单独存在不能证明 ID 来自宿主事件。带日期的行为验收必须与保存的宿主 transcript 或协作日志交叉核对。该证据核验位于安装后的 Skill 之外，因此不改变纯指令 MVP。

审查至少覆盖：

- 来源覆盖及来源与主张是否对齐；
- 事实准确性和内部一致性；
- 时效性主张是否仍然有效；
- 缺少支持的数字、比较和最高级表述；
- 核心论点与叙事逻辑；
- 重复或矛盾页面；
- 缺失的反方观点、风险和限定；
- 对目标受众与决策的价值。

每条问题都包含 `id`、`severity`、`category`、`slide_ids`、`claim`、`evidence`、`recommendation` 和 `status`。严重级别为 `BLOCKER`、`HIGH`、`MEDIUM`、`LOW`；状态为 `OPEN`、`RESOLVED`、`ACCEPTED_RISK`。

只有所有 `BLOCKER` 或 `HIGH` 问题都为 `RESOLVED` 时，质量门才通过；这两个级别的 `OPEN` 与 `ACCEPTED_RISK` 都继续阻断。修订后必须由新的独立审稿人使用相同问题 ID 核验并给出解决证据。审稿身份、文稿快照、修订说明、cycle 和问题历史保存在 `run.json.manuscript_review.review_history`。每个审查周期最多三轮；被阻断周期不得重置。只有已经批准的版本后来发生实质变化时才能递增 cycle 并从 `round: 0` 开启新周期。

宿主无法启动独立子 Agent 时，运行进入 `review_unavailable` 并停止。同上下文自审可作为补充 QA，但不能满足文稿质量门。

## 视觉系统

设计系统使用 1280×720 画布、64 px 安全边距、24 px 标准间距、系统字体回退和显式 `<tspan>` 换行。标题至少 40 px，正文至少 20 px，脚注至少 14 px。

新安装通过 `assets/styles/registry.json` 发现风格。注册表保留三个 `legacy_seed`：

- `minimal-business`
- `tech-dark`
- `bold-editorial`

并提供非默认 rich style pack `canway-midyear-review`，中文显示名为“嘉为年中总结风格”，manifest 内容版本必须精确为 `1.2.0`，并在 `files.redesign_prompt` 中声明 `canway-midyear-review/REDESIGN.md`。它的 manifest 引用机器可读 tokens、中文 `STYLE.md` 抽象规则和风格自有完整 prompt；这些都不是单页成品 SVG 或固定构图参考。颜色、字体、间距、形状和语义角色可以复用；每页区域、卡片数量、连接关系和阅读路径必须由当前 visual brief 重新推导，避免把风格身份固化为同一张版式。

布局根据内容语义选择，不机械轮换。支持封面／章节、单一结论、比较、时间线／流程、层级／架构、数据／图表、Bento 汇总和收束／行动。除非内容要求，相邻页面不得重复同一家族。

全面生产前生成两个锚点：封面，以及最困难或信息密度最高的内容页。`guided` 策略等待批准，`auto` 策略执行同等内部检查。

### 风格 prompt、身份与恢复边界

四个内置风格的完整 prompt 是风格自有的独立可编译的完整模板：`minimal-business.redesign.md`、`tech-dark.redesign.md`、`bold-editorial.redesign.md` 与 `canway-midyear-review/REDESIGN.md`。legacy seed 可以通过 registry 的 `redesign_prompt` 字段或已知 companion 规则定位；style pack 只能通过自己的 manifest 定位。新增 style pack 只新增 registry 条目和 manifest／prompt 资产，不修改共享 resolver schema 或逻辑。visual brief 是页面视觉权威状态与 compiler 输入；编译后的 generation prompt 是 fresh generator 的唯一执行输入，fresh generator 不得直接接收 visual brief 或原始风格 prompt。

`theme.json` 与 visual brief 持久保存同一组 identity 字段：`selected_style_id`、`selected_style_display_name`、`style_kind` 与 `style_manifest_version`。编译 prompt 时只信任这些持久字段、registry／manifest 和快照；display name 或 manifest version 升级属于 ordinary stale 并触发重建，互相矛盾或无法唯一重建才是 `prompt_snapshot_conflict`。

操作触发也必须持久化：首次生成使用 `generation_trigger_id: initial:<slide-id>:<visual_brief_snapshot_id>`，用户重构使用 `interaction:<interaction_history-id>`，两次 patch 后确定性回退使用 `fallback:<slide-id>:<failed-transaction-64hex>:2`，局部修补使用 `patch:<slide-id>:<qa-defect-id>`。deck-scope 用户重构可以共享同一个 trigger，但每页仍有独立 prompt snapshot 和 transaction identity。

当 style prompt、路径、身份或 snapshot 无法解析时，运行写入 `run.json.visual_generation_blocker` 并保持 slide dirty，不启动 generator、不覆盖 SVG、不改用其他风格。成功编译后，`run.json.visual_generation_transaction` 以 `compiling -> compiled -> generating -> candidate_written -> validated -> promoted` 描述可恢复状态；每一步只声称单个 `run.json` 原子替换，跨文件 prompt／候选写入只通过复读 hash 恢复。全局恢复顺序精确为 `pending_interaction > visual_generation_blocker > visual_generation_transaction > stage scan`；前三类 durable control state 均不存在或已完成后才能扫描普通阶段。

旧 `redesign-prompts/` 目录永远 inert：可作为只读历史保留，但不能写入、移动、删除、激活或用来推断当前风格。当前 prompt 有效性只由新 `generation-prompts/` provenance、visual brief、theme、storyboard 和安装包 prompt snapshot 决定。

## Office-safe SVG 契约

每个最终页面都是 UTF-8 XML，且包含 `width="1280"`、`height="720"` 与 `viewBox="0 0 1280 720"`。

允许元素：`svg`、`g`、`rect`、`circle`、`ellipse`、`line`、`polyline`、`polygon`、`path`、`text`、`tspan`、`title`、`desc`。

MVP 禁止：

- `foreignObject`、脚本、嵌入 HTML、事件处理器和动画；
- 外部 DTD／实体、CSS import 和远程资源；
- 外部字体、图库 URL 和机器绝对路径；
- 依赖浏览器滤镜的效果；
- 自动 HTML 文字换行；
- 用 emoji 承载关键信息。

文字保持为文字，使用系统字体回退，并通过显式 `<tspan>` 换行。基本图表由允许的矢量元素构造，重要主张携带来源 ID。

## QA 与能力降级

单页 QA 检查 XML 有效性、禁止特性、唯一 ID、画布尺寸、转义、来源覆盖、文字溢出、重叠、安全边距、对比度、对齐和主题令牌一致性。

宿主能够渲染时执行视觉检查，包括 3 秒焦点识别、第一至第三阅读顺序、主次支配、六级字体阶梯、语义色、卡片分组、假设页证据边界和视觉债务；不能渲染时，报告必须写 `visual_qa: not_rendered`。源文件检查不能冒充视觉批准。

视觉修订先分类：局部碰撞、溢出、令牌、微小对齐、连接线或非事实错字使用 `patch`，输入为完整 brief、当前 SVG 和一个精确 defect；焦点、层级、阅读路径、布局、卡片密度、字体、语义色、品牌方向或参考变化使用 `recompose`，输入为完整 brief、锁定故事板和当前主题，且旧 SVG 不能作为几何底稿。事实或来源变化返回文稿流程。

每次全新生成或 recompose 都创建修复次数为 0 的新候选。候选最多自动 patch 两次；问题持续存在时，确定性降级为简单单栏或双栏布局；回退后仍有 SVG 硬失败就阻断交付。

整套 QA 检查叙事推进、结论／证据映射、密度节奏、布局变化、令牌一致性和未解决文稿问题。

## 安装模型

同一标准目录复制或链接到各宿主发现路径：

- Claude Code 用户／项目级：`~/.claude/skills/ppt-start/` 或 `.claude/skills/ppt-start/`；
- Codex 用户／项目级：`$HOME/.agents/skills/ppt-start/` 或 `.agents/skills/ppt-start/`。

MVP 不包含宿主插件 manifest。未来包装器可以引用同一标准包，但不得复制工作流规则。

## MVP 范围

包含：

- 由主题、简报、资料或既有运行驱动的演示文稿创建；
- `guided`／`auto` 持久执行策略与 `new`／`resume`／`revise` 入口动作；
- 可选研究与离线披露；
- 强制独立文稿审查；
- 中文和英文内容；
- 基础图表、流程、比较、架构和 Bento 汇总；
- 独立 SVG 输出和定向修订；
- Claude Code／Codex 工作区交接。

不包含：

- PPTX 生成或模板导入；
- 图库搜索或生成式图像；
- 动画、视频和演讲者备注；
- 自定义画布比例；
- MCP、外部审稿模型、服务、数据库和强制脚本；
- 保证所有 Office 版本都能拆分并编辑每个 SVG 元素。

兼容性承诺仅限可以在浏览器打开并插入受支持 PowerPoint 版本的独立静态 SVG。逐元素编辑能力取决于 Office 版本、平台和 SVG 转换行为。

## 验收标准

MVP 只有在以下条件满足时才算通过相应验收：

1. 同一 Skill 包在两个宿主中可发现；
2. 两个宿主生成相同的运行产物协议；
3. 人为植入且未解决的 `HIGH` 问题阻止主题和页面生成；
4. 委派不可用时产生 `review_unavailable`，不能同上下文静默自批；
5. 第二个全新审稿人能够核验修订并推进运行；
6. 两个跨宿主交接方向都能仅凭工作区文件完成；
7. 内置 SVG 与测试页面都满足 Office-safe 契约；
8. 代表性页面在浏览器中可打开，并能插入受支持 PowerPoint 版本且不丢失关键内容。

可重复流程与证据台账见 [`docs/acceptance.md`](acceptance.md)。自动一致性测试只覆盖包结构与书面契约，不能证明 Claude Code 行为、Codex 行为、fresh generator 行为、审稿来源、跨宿主交接、浏览器渲染或 PowerPoint 导入。证据类别必须区分 `static package`、`EVIDENCE_CLASS: DIAGNOSTIC`、`deployment hash` 和 `real host`：测试 oracle 不是运行时代码，诊断压力场景不是人工验收，部署 hash 只证明文件同步，只有真实宿主版本、transcript 和运行目录才能更新当前宿主行为结果。相关结论必须以台账中带日期的 `PASS`、`FAIL`、`NOT RUN` 或 `PENDING` 为准，不能把绿色测试套件描述成人工宿主／应用验收通过。
