# PPT Pilot MVP 设计文档

## 目标

PPT Pilot 是面向 Claude Code、OpenAI Codex 与 DeepSeek Harness 的可移植 Agent Skill。它把主题、简报、资料集合或既有运行转换为 6–15 页、16:9 的演示文稿，最终每页交付为独立 SVG 文件。

MVP 刻意保持纯指令架构。它只使用宿主常规的工作区能力，以及可选研究／视觉能力；不强制依赖 MCP 服务、API SDK、后台服务、Hook、嵌套 Skill、Shell 脚本或软件包运行时。

可执行 Skill 标识为 `ppt-start`。产品名称仍为 PPT Pilot；宿主调用方式见 [README](../README.md)。

## 产品原则

1. 内容先于外观。
2. 每页只表达一个结论，并以证据或明确限定支持。
3. 中间文件是产品状态，不是附带日志。
4. 文稿审查必须执行；每轮优先全新独立审稿人，委派失败时只有明确记录的 inline fallback 才能在当前上下文正式放行。
5. 文稿获批前禁止视觉设计。
6. SVG 兼容性与可读性优先于装饰效果。
7. 任何不可用能力都必须披露，不能悄然模拟。

## 共享 Skill 架构

标准包位于 `skills/ppt-start/`：

- `SKILL.md`：精简的编排入口和发现入口；
- `references/`：各阶段流程与契约；
- `assets/styles/registry.json`：风格发现注册表（五个内置风格包）；
- `assets/styles/<style-id>/`：自包含 style pack——`manifest.json`、`tokens.json`（schema 2，含结构化 `prompt_baseline`）、中文 `STYLE.md`，以及风格自带完整生成模板 `files.prompt_template`（默认 `prompt.md`）；
- `references/generation-prompt-template.md`：风格未声明自带模板时的 repository 兜底模板（已单注点化）；
- `assets/examples/`：一份 Office-safe SVG 示例。

运行目录不再创建逐页 visual brief。每页由已批准故事板与 `theme.json` 直接编译：读取所选中风格包自带的完整 prompt 模板，把叙事要点注入其**单一** whole-line `{{NARRATIVE}}` 注点（模板未声明时兜底 repository template），编译 `.ppt-pilot/generation-prompts/<slide-id>.md`；持久 envelope 的 `format` 精确为 `creative-brief-v1`。早期 `[[CANONICAL_NARRATIVE_BULLETS]]`／`[[STYLE_BASELINE]]` 双 marker 双域协议已被该单注点范式整体取代，旧协议产物只作迁移历史。

共享 `references/redesign-prompt.md` 规定 style identity/path containment、单注点编译、无副作用 preflight、宿主能力协商、schema-v2 batch/per-slide state、`prompt_by_value` isolated dispatch、coordinator ownership 和失败恢复。生成正文完全由风格自带模板承载，编译层拒绝 `source=`／`[claim=` 来源注解进入叙事，也不得把某个风格的布局语言作为默认。

共享 frontmatter 只包含 `name` 与 `description`，其中 `name` 为 `ppt-start`。运行时指令使用“读取、写入、委派、检查”等语义动作，不依赖宿主专属工具名、变量、权限语法或调用语法。

宿主专属安装位置和启动命令只写在 `README.md` 与验收文档中，不进入共享运行时指令。

本地契约测试只能证明文件结构、规则引用和静态资产一致，不能证明 Claude Code／Codex 的实际模型行为、跨宿主视觉一致性、浏览器渲染或 PowerPoint 导入；这些能力继续以独立人工验收台账为准。

## 工作流

```text
brief
  -> optional research
  -> assertion-led outline
  -> page storyboard
  -> mandatory manuscript review (subagent preferred; inline fallback on attributable failure)
  -> deck-scoped theme
  -> storyboard + theme.json direct compile (single {{NARRATIVE}} injection into style-owned template)
  -> byte-exact creative-brief-v1 prompt + in-memory preflight/capability negotiation
  -> pointer-last schema-v2 per-slide transactions + batch manifest
  -> prompt_by_value isolated generation + overlapping per-slide validation
  -> ordered coordinator promotion/blocker publication
  -> per-slide and deck-level QA
  -> complete
```

对应的稳定阶段值为：

```text
brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete
```

`guided` 与 `auto` 是写入 `run.json.mode` 的持久执行策略。`guided` 在简报、大纲和锚点 SVG 后提出一个直接问题并等待明确批准；新运行未显式指定策略时默认 `guided`。只有显式 `auto` 才跳过可选问题和批准，但用户权限或没有安全默认值的决策仍然阻塞，且全部中间产物仍需创建和验证。`new`、`resume` 与 `revise` 是入口动作：恢复和修订先读取 `run.json`、保留既有执行策略，再分别继续未完成工作或使受影响依赖项失效。

`theme` 阶段建立 deck-scoped style identity 与软风格基线。活动路径是**故事板 + `theme.json` 直接编译**：故事板拥有逐页叙事／素材／事实／来源，theme 拥有 deck 风格；已应用修订先投影回对应 owner，再把叙事要点注入所选风格自带模板的单一 `{{NARRATIVE}}` 注点。新 batch 在完整内存 preflight 与能力协商后 pointer-last 激活；SVG 不是设计状态，上述工作均属于既有阶段内部步骤。

## 用户交互与确认

交互由独立的共享参考协议定义，不依赖宿主专属工具。编排上下文先检查请求、工作区和已有产物，把决策分为已知、可安全默认和必须询问三类，形成按工作流顺序排列的决策队列。一次只提出一个实质性问题；有限选择提供 2–4 个互斥选项、逐项效果和推荐理由。推荐不是确认，提问后必须停止，明确回答持久化前不得推进下游阶段。

简报、大纲和锚点是 guided 强制批准点。研究授权、故事板冲突、审稿业务决策、缺少品牌方向和生产阻断只在没有安全默认值时触发。`auto` 可以记录保守假设，但不能自行授权网络传输、机密披露或改变核心业务立场。

为了支持跨宿主恢复，`schema_version: 1` 允许可选顶层 `pending_interaction` 与 `interaction_history`。`pending` 保存当前问题、逐项效果和推荐理由；回答先以 `answered`、原始 `answer` 和有限选择的规范化 `decision` 持久化。阶段产物按交互 ID 幂等更新后，`run.json` 以单次原子替换同时写入权威交互历史、目标阶段和对象删除／替换，不会留下阶段与旧问题错位的文件。阶段产物记录只是可重建镜像，失效不能删除权威历史。同一批准检查点通过单调 `approval_attempt` 生成独立交互 ID，后续批准不会覆盖此前修订事件。等待期间原有 `stage` 不变，不增加暂停状态。首次阻塞问题也必须在一个新建且不冲突的运行目录中先持久化；缺少这些可选字段的旧运行继续有效，格式错误则停止并报告。

当恢复／修订目标无法唯一确定时，工作区级 `ppt-output/run-selection.json` 先保存候选、`entry_action`、原始 `operation_payload` 与目标选择问题，不修改任何候选运行；选定运行按保存的完整操作到达下一个持久状态后才删除该路由文件。

## 文件化运行协议

每套演示文稿位于 `ppt-output/<deck-id>/`。新运行只在根目录暴露用户可读大纲和最终页面，其余过程状态都收进内部目录：

```text
ppt-output/<deck-id>/
├── 大纲.md          # 根目录中的用户可读大纲
├── slides/*.svg     # 最终页面
└── .ppt-pilot/      # 内部过程状态
    ├── run.json
    ├── 简报.md / 研究.md / 来源.md
    ├── 故事板.md / 文稿审查.md
    ├── theme.json / 质量检查报告.md
    ├── generation-prompts/<slide-id>.md
    ├── visual-generation-transactions/<slide-id>-<tx64>.json
    ├── visual-generation-batches/<batch-id>.json
    └── samples/*.svg
```

`run.json` 使用 `schema_version: 1` 记录工作流／交互状态，并只用 `active_visual_generation_batch: {schema_version,batch_id,manifest_path}` 指向当前 schema-v2 视觉批次；schema-v1 `visual_generation_transaction` 仅作零模型调用迁移输入。每页 transaction 文件拥有 operation、prompt/candidate/final paths、hash、state、validation、host 与 timing；manifest 只拥有 ordered refs/snapshots 和可重建 cursor 提示。`.ppt-pilot/generation-prompts/<slide-id>.md` 只记录九个 metadata 字段与单注点注入派生的 canonical body，不含 raw answer/history JSON。pointer-last 与这些文件足以支持跨宿主恢复，无需此前对话。

中文 Markdown 名称是新运行的标准。为了让既有运行仍能恢复，`resume`／`revise` 可以继续原位读取旧英文名称 `brief.md`、`research.md`、`sources.md`、`outline.md`、`storyboard.md`、`manuscript-review.md` 和 `qa-report.md`，但不得自动重命名、复制或迁移。实际名称由 `run.json` 的引用字段和目录中的完整文件集合共同决定；无法唯一判定时停止并报告冲突。

上游变化按最早受影响阶段重入并使依赖项失效：

- 简报变化：返回 `brief`，全部下游产物失效；
- 主张或来源变化：返回 `research`；大纲变化返回 `outline`；故事板变化返回 `storyboard`；这些变化都把嵌套审查授权重置为 pending，并使全部视觉产物失效；
- 主题变化：返回 `theme`，全部 generation prompts、未完成 transactions/batches、样例、正式页面和视觉 QA 失效；文案未变时可以保留文稿批准；
- 锚点内纯视觉修改：把修订投影回故事板或 `theme.json`，使受影响 prompt、transaction、锚点和依赖项失效并保留有效文稿批准；
- 单页 `recompose`：使该页 prompt、transaction、SVG 和 QA 失效；单页 `patch`：只使该页 SVG 和 QA 失效，并在 QA owner 中更新精确 defect 与候选版本。

## 强制文稿审查（独立优先、inline 降级）

只有 `简报.md`、`研究.md`、`来源.md`、`大纲.md` 和 `故事板.md` 全部完成并冻结，才到达文稿边界。

每轮先把五个冻结输入委派给全新独立子 Agent，并只授予只读访问。成功时保存真实 `delegation_evidence`；启动失败、接收者为空、完成事件缺失或结果上下文不匹配时，不空等、不询问用户，而是在当前步骤进入 `inline_fallback`，仅依据同一冻结快照和审查规范直接产生结构化 findings。

inline round 使用互斥 `fallback_evidence` 并明确声明“当前上下文降级审查，不具备独立上下文隔离”。它不能伪造独立性，但 inline PASS 与 subagent PASS 使用同一严格质量门，均可进入 `manuscript_approved`。`run.json.manuscript_review.pending_round` 在执行前持久化 cycle／round／mode／snapshot／evidence，crash 后复用同一轮，completed round 与删除 pending 在一次原子替换中完成。

subagent 审稿人只返回结构化 findings 载荷，不修改工作区；创作上下文负责把载荷保存到 `文稿审查.md`／旧 `manuscript-review.md` 并持久化 review history。inline 模式由创作上下文产生同构载荷并按同一职责持久化，但必须保留 fallback mode 和限制声明。

状态文件只是可移植记录，不是加密证明：subagent 独立性仍需宿主 transcript／协作日志核验；inline 记录只能证明降级契约已执行。

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

只有所有 `BLOCKER` 或 `HIGH` 问题都为 `RESOLVED` 时，质量门才通过；`OPEN` 与阻断级 `ACCEPTED_RISK` 都继续阻断。修订后下一轮仍先尝试独立子 Agent，失败时由 inline fallback 使用新冻结快照核验相同问题 ID。subagent 与 inline round 共同计入每 cycle 最多三轮；模式切换不能重置计数或开启第 4 轮。只有已经批准的版本后来发生实质变化时才能递增 cycle。

只有冻结输入不可读、当前上下文也无法执行审查或 pending 状态冲突时才使用 legacy-compatible `review_unavailable`。既有 unavailable 历史可读，resume 可以保留旧原因并创建下一合法 inline pending round。

## 视觉系统

设计系统使用 1280×720 画布、64 px 安全边距、24 px 标准间距、系统字体回退和显式 `<tspan>` 换行。标题至少 40 px，正文至少 20 px，脚注至少 14 px。

新安装通过 `assets/styles/registry.json` 发现风格。注册表当前提供五个内置 style pack：

- `canway-midyear-review`（中文显示名"嘉为年中总结风格"，manifest 内容版本必须精确为 `1.3.0`）
- `jiawei-product`（嘉为产品风格）
- `minimal-business`
- `tech-dark`
- `bold-editorial`

每个风格都是自包含 style pack：manifest 声明 `files.tokens`、`files.guidance` 与 `files.prompt_template`；tokens（schema 2）承载颜色、字体、间距、形状与结构化 `prompt_baseline`；`prompt.md` 是风格自带完整生成模板。运行时按 manifest 解析模板路径，编译层只注入叙事要点并拒绝来源注解；页面区域、卡片数量、连接关系和阅读路径由 isolated generator 在故事板语义边界内自主决定，并由 QA 验证。

布局根据内容语义选择，不机械轮换。支持封面／章节、单一结论、比较、时间线／流程、层级／架构、数据／图表、Bento 汇总和收束／行动。除非内容要求，相邻页面不得重复同一家族。

全面生产前生成两个锚点：封面，以及最困难或信息密度最高的内容页。`guided` 策略等待批准，`auto` 策略执行同等内部检查。

### 风格身份、规范编译与恢复边界

每个风格经 `files.prompt_template` 自带完整生成模板；style resolver 验证 identity、registry／manifest、tokens 与 guidance，并解析模板相对路径。compiler 把叙事要点注入模板的单一 whole-line `{{NARRATIVE}}` 注点，持久 envelope 是 `creative-brief-v1`；风格未声明模板时兜底 repository `references/generation-prompt-template.md`。

`theme.json` 权威拥有 deck style identity；故事板拥有逐页叙事、素材、事实与来源；per-slide schema-v2 transaction 拥有 operation/trigger/prompt/candidate/final/state/validation/host/timing。首次 trigger 使用 `initial:<slide-id>:<storyboard_snapshot_id>`，用户重构使用 `interaction:<history-id>`，fallback 与 patch 使用各自稳定 trigger。修订按 `visual-revision-N`／`supersedes` 投影回故事板或 theme，只应用一次。

新批次先完成两个 replacement、canonical hash preflight 与 fresh-isolation 能力协商；无能力保持零 prompt/transaction/candidate 写入。能力通过后按 pointer-last 写 per-slide transactions、batch manifest 与 `active_visual_generation_batch`。isolated task 只接收完整 `prompt_by_value`，fresh history、filesystem none、tools none、text-only；coordinator 独占所有工作区写入。

默认 `batch_width: 4`（可配置 3）；并发或 durable lookup 缺失时 width 1，非 Git 不降级。generation 与 per-slide validation 可重叠；promotion、最低 visible blocker 与 pointer 由 coordinator 按 `ordered_slide_ids` 串行提交。内部 `SRC-<digits>` 可保留在 `data-source-id`／trace，但可见文字以 `fact_source_mismatch` 阻断。

telemetry 以 compile/model/render/qa/promotion spans、DAG critical path 与 batch wall time解释并发；它是非权威诊断，`telemetry_diagnostic_failed` 不能改变 transaction correctness 或授权 promotion。schema-v1 singular transaction 和旧 prompt 目录只作为迁移历史，永不成为新运行 owner。

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

视觉修订先分类：局部碰撞、溢出、令牌、微小对齐、连接线或非事实错字使用 `patch`，输入为完整 direct-compile inputs、当前 SVG 和一个精确 defect；焦点、层级、布局、字体或品牌方向变化使用 `recompose`，先投影回故事板／theme，再重新编译 prompt 且不以旧 SVG 为几何底稿。事实或来源变化返回文稿流程。

每次全新生成或 recompose 都创建修复次数为 0 的新候选。候选最多自动 patch 两次；问题持续存在时，确定性降级为简单单栏或双栏布局；回退后仍有 SVG 硬失败就阻断交付。

整套 QA 检查叙事推进、结论／证据映射、密度节奏、布局变化、令牌一致性和未解决文稿问题。

## 安装模型

仓库发布两个职责独立的标准 Skill：

- `ppt-start`：保持本章工作流范围，生成独立 SVG；
- `ppt-editable`：只消费一个完成的 PPT Pilot 运行，生成原生可编辑并验证的 PPTX。

两个目录按同一 descriptor 安装到 Claude Code、Codex 和 DeepSeek 的发现根。DeepSeek 保持一个 `ppt-pilot` plugin/marketplace 条目，plugin 的 `skills/` 下同时包含两个 Skill。每个 Skill 的备份、保留和树摘要独立，备份目录必须位于任何 `skills/` 扫描根之外。

- Claude Code：`~/.claude/skills/<skill-id>/` 或 `.claude/skills/<skill-id>/`；
- Codex：`$HOME/.agents/skills/<skill-id>/` 或 `.agents/skills/<skill-id>/`；
- DeepSeek：`$HOME/.agents/plugins/plugins/ppt-pilot/skills/<skill-id>/`。

## ppt-start MVP 范围

包含：

- 由主题、简报、资料或既有运行驱动的演示文稿创建；
- `guided`／`auto` 持久执行策略与 `new`／`resume`／`revise` 入口动作；
- 可选研究与离线披露；
- 强制文稿审查（独立 subagent 优先，委派失败时 inline fallback）；
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

`ppt-editable` 是独立 Skill，不改变上述 `ppt-start` MVP 边界；它以完成运行中的 SVG、故事板和 QA 证据为输入，并承担 PPTX、递归分组、备注、Office/视觉验证及 previous-final 安全语义。

兼容性承诺仅限可以在浏览器打开并插入受支持 PowerPoint 版本的独立静态 SVG。逐元素编辑能力取决于 Office 版本、平台和 SVG 转换行为；`ppt-editable` 的更强承诺以其独立验证报告和验收台账为准。

## 验收标准

MVP 只有在以下条件满足时才算通过相应验收：

1. `ppt-start` 与 `ppt-editable` 在三个宿主的目标发现路径中独立可发现；
2. `ppt-start` 在两个生成宿主中产生相同的运行产物协议；
3. 人为植入且未解决的 `HIGH` 问题阻止主题和页面生成；
4. 委派不可用时进入 `inline_fallback`，在当前步骤完成同一严格审查；只有 inline 也无法执行时才使用 `review_unavailable`；
5. 后续正式 subagent／inline round 能够核验修订并推进运行，同时保留实际 review mode；
6. 两个跨宿主交接方向都能仅凭工作区文件完成；
7. 内置 SVG 与测试页面都满足 Office-safe 契约；
8. 代表性页面在浏览器中可打开，并能插入受支持 PowerPoint 版本且不丢失关键内容。

可重复流程与证据台账见 [`docs/acceptance.md`](acceptance.md)。自动一致性测试只覆盖包结构与书面契约，不能证明 Claude Code 行为、Codex 行为、fresh generator 行为、审稿来源、跨宿主交接、浏览器渲染或 PowerPoint 导入。证据类别必须区分 `static package`、`EVIDENCE_CLASS: DIAGNOSTIC`、`deployment hash` 和 `real host`：测试 oracle 不是运行时代码，诊断压力场景不是人工验收，部署 hash 只证明文件同步，只有真实宿主版本、transcript 和运行目录才能更新当前宿主行为结果。相关结论必须以台账中带日期的 `PASS`、`FAIL`、`NOT RUN` 或 `PENDING` 为准，不能把绿色测试套件描述成人工宿主／应用验收通过。
