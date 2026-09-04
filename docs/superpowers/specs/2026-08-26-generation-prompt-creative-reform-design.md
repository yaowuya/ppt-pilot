# Generation Prompt 创意化重构设计

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

日期：2026-08-26
状态：待复核
范围：ppt-pilot 插件 `skills/ppt-start/` 的页面生成 prompt 契约重构

## 1. 背景与问题

当前架构（模板化字节语法）：

- `generation-prompt-template.md` 是唯一编译源，含两个替换域：
  - `[[CANONICAL_NARRATIVE_BULLETS]]`：大纲持久化的叙事要点
  - `[[EFFECTIVE_PAGE_SPECIFICATION]]`：由逐页 visual brief 提供的完整页面规格（锁定内容、层级、构图、视觉令牌、输出质量、修订 owner）
- 模板固定三步：步骤 1 锁定内容（不得改写）、步骤 2 锁定布局（不得改选）、步骤 3 锁定令牌（不得自选）
- fresh generator 被定位为"忠实执行者"

实际产出（实测 `S02.md`）包含 `有效页面规格（唯一动态内容）` 整段：页面结论、锁定内容块（逐字）、信息层级、构图（严格实现）、视觉令牌（逐项套用）、输出与质量、修订与生成 owner。

**问题**：用户在真实使用中发现，这种 prompt 预先设定了 SVG 的全部视觉形态，生成器只是把预先确定的布局/颜色/文字搬进 SVG。既浪费上游人力（brief 组装构图令牌），又限制生成器的设计能力。用户要求反转定位：**prompt 只承载叙事逻辑与内容素材，生成器负责设计好看的 SVG**。

## 2. 目标与非目标

### 目标

1. generation prompt 定位改为"创意产出"，内容为：叙事要点 + 内容素材 + 软风格基线 + 输出硬契约。
2. 取消逐页 visual brief 阶段；storyboard + theme 直接编译 prompt。
3. 允许生成器提纯、改写、补充内容（仅限已批准素材），但事实底线不可破。
4. 保留主题基线作为"软参考"（非逐项锁定），保障跨页风格一致性。
5. 保留锚点页与用户批准节点（审批点是"生成器在软基线下的产出风格"）。

### 非目标

- 不改变简报/研究/来源/大纲/故事板/文稿审查等上游阶段。
- 不改变 guided/auto 执行策略框架。
- 不改变 Office-safe SVG 技术子集（画布/安全区/tspan/path+A 等硬规则）。
- 不改变 deck-deliver 等伴随工具。
- 不迁移旧运行（旧 brief 目录惰性保留，只读）。

## 3. 已确认决策（问答记录）

| 决策点 | 结论 |
|---|---|
| 风格来源 | 保留主题基线作为软参考（不逐项锁定令牌） |
| 内容边界 | 可改写/重排/补充（仅限已批准素材），事实/数字/单位/限定词/因果/来源映射必须真实 |
| visual brief | 取消该阶段 |
| 叙事字段 | 保留 role / assertion_title / audience_takeaway / visual_intent；删除构图字段 |
| 锚点流程 | 保留两页锚点+审批，但不生成 brief |

## 4. 新 Prompt 结构设计

### 4.1 新模板（generation-prompt-template.md 重写）

```
# Role: 高级信息架构师 & SVG 可视化编码专家

你的任务是基于叙事要点与内容素材，自主设计一页布局合理、逻辑清晰、视觉美观、
可直接用于演示文稿的 Office-safe SVG。

## Workflow: 执行步骤

### 步骤 1: 组织叙事与内容 (Narrative and Content)
不得重新选择叙事逻辑。严格执行以下叙事要点：
[[CANONICAL_NARRATIVE_BULLETS]]

内容处理边界：
- 允许对素材进行提纯、改写、重排与补充（补充仅限来自已批准研究/来源的内容）。
- 不得改变数字、单位、期间、限定词（待确认/待验收等）、因果、来源映射。
- 不得把推断/新增内容冒充为已批准事实。

### 步骤 2: 应用风格基线并设计视觉表达 (Style Baseline and Visual Design)
风格基线是软参考方向，不是逐项锁定令牌。在保持整套 deck 风格一致性的前提下，
布局、层级、卡片组织、信息密度、配色用法与装饰由你自主决定。
[[STYLE_BASELINE]]

### 步骤 3: 编码 SVG（输出硬契约,固定不变）
- **画布**: 根元素必须使用 `<svg viewBox="0 0 1280 720">`。
- **安全区与节奏**: 所有可见内容位于 64px 安全区内；间距使用 24px 节奏。
- **圆角卡片**: 仅使用 `<path>` 与 SVG 弧线命令 `A`；禁止为 `<rect>` 添加 `rx` 或 `ry`。
- **文本**: 每个文本对象使用显式 `<text>`；每一行使用简单、非嵌套的 `<tspan>`；文字保持为文字，不转轮廓。
- **字号**: 正文 ≥20px，次级/来源 ≥14px；关键数字可用大字号或强调色突出，全页至多一个主强调焦点。
- **来源**: 带 SRC 的主张所在分组携带 `data-source-id`；页脚来源行必须存在。
- **Office-safe 子集**: 仅使用 `svg`、`g`、`path`、`rect`（仅直角）、`circle`、`line`、`polyline`、
  `polygon`、`text`、`tspan`、`title`、`desc`；禁止 `foreignObject`、脚本、远程资源、滤镜、渐变、
  动画、`defs`、`use`、`clipPath`、`mask`、`image`。
- 根节点包含 `<title>`（本页结论）与 `<desc>`（视觉关系）。

## 兼容约束
SVG 必须在 PowerPoint、Word 等 Office 软件中保持几何、文本和颜色稳定。
所有图形、字体栈、颜色与文字内容必须自包含，不依赖外部文件、URL 或工具调用。

---

只返回一个 ```xml 代码围栏，围栏内必须是完整 SVG；围栏外不得输出解释、Markdown 标题或其它文本。
```

### 4.2 替换域变化

| 旧 | 新 |
|---|---|
| `[[CANONICAL_NARRATIVE_BULLETS]]` | 保留：叙事要点 + 内容素材（role/assertion/audience/visual_intent + content_blocks+source_ids） |
| `[[EFFECTIVE_PAGE_SPECIFICATION]]` | 删除 |
| （无） | 新增 `[[STYLE_BASELINE]]`：来自 theme.json 的软风格基线 |

字节语法规则相应改为"恰好三个 replacement domains"（或把风格基线并入叙事域，见 4.3 备选）。

### 4.3 替换域结构（已定：方案 A - 三域）

- **叙事/素材域** `[[CANONICAL_NARRATIVE_BULLETS]]`：来自故事板（role/assertion/audience/visual_intent + content_blocks + source_ids）
- **风格基线域** `[[STYLE_BASELINE]]`：来自 theme.json 软风格基线（独立快照域）
- （无第三动态域；输出硬契约是模板静态部分）

两个编译输入源分离：叙事/素材来自故事板，风格来自 theme.json，快照/哈希职责清晰。备选的方案 B（风格并入叙事域）已否决：会使模板职责混合、快照域不清晰。

## 5. 技术联动设计

### 5.1 哈希域（generation-prompt-byte-grammar.md 规则 10 重写）

**旧 payload（13 键）**：applied_visual_revision_ids, compiled_prompt_sha256, effective_revision_projection_sha256, generation_intent, generation_prompt_template_snapshot_id, generation_trigger_id, outline_snapshot_id, resolved_generation_prompt_template_path, selected_style_id, storyboard_snapshot_id, style_kind, style_manifest_version, theme_snapshot_id, visual_brief_snapshot_id

**新 payload**：
- 删除：`visual_brief_snapshot_id`、`effective_revision_projection_sha256`（无 brief 与 revision projection 概念）
- 保留：`applied_visual_revision_ids`（修订仍从 interaction_history 权威投影，但只影响叙事/素材域，不投影布局令牌）
- 保留：其余键（template snapshot、outline/storyboard/theme snapshot、style identity、intent、trigger）
- 新增：`style_baseline_snapshot_id`（theme.json 软风格基线规范化字节哈希）

### 5.2 编译门禁（redesign-prompt.md / byte-grammar 规则 8 改造）

保留：
- 自包含性（无悬空引用、无外部路径、无未解析 marker）
- 禁止注入标题/JSON/围栏等注入面
- 禁止工具调用指令

删除：
- 布局语义一致性（生成器自选布局）
- 枚举与顺序一致性（内容可重排）
- 字号下限/容纳预算（改为输出硬契约，生成后 QA 校验）

新增（事实底线预检）：
- 素材事实一致性：叙事/素材域中的数字、单位、限定词与故事板一致，冲突返回上游 storyboard defect

### 5.3 QA 改造（qa-and-revision.md）

| 旧 | 新 |
|---|---|
| `locked_content_fidelity`（逐字内容） | `fact_source_consistency`（数字/单位/限定词/因果/来源映射核对，措辞自由） |
| （无） | `narrative_integrity`（assertion/role/audience/visual_intent 保留；SCQA 顺序完好） |
| `reading_order`（预设阅读顺序） | 删除预设，改为视觉层级 QA（主次可辨） |
| 其余（xml_well_formed/office_safe_subset/source_coverage/safe_area/overflow/contrast） | 保留 |

### 5.4 恢复机制

- `visual_generation_transaction` 不再引用 visual_brief_snapshot_id；直接引用 storyboard+theme。
- 全局恢复顺序不变：`pending_interaction > manuscript_review.pending_round > visual_generation_blocker > visual_generation_transaction > stage scan`。
- 旧运行（已有 `.ppt-pilot/visual-briefs/`）惰性保留：只读历史，不参与新编译；恢复旧运行时若仍在视觉阶段，按新路径从 storyboard+theme 重编译（intro 不迁移 brief）。

### 5.5 锚点流程

- 主题选型后直接由 storyboard（封面页 + 密度最高/最困难页）+ theme.json 编译锚点 prompt，不再组装锚点 brief。
- `guided`：两页锚点完成并通过硬检查后，提供真实渲染证据并提出锚点批准问题；批准对象为"生成器在当前软基线下的产出风格"。
- `auto`：执行同等检查，跳过可选批准。

### 5.6 文档改动清单

| 文件 | 改动 |
|---|---|
| `generation-prompt-template.md` | 按 4.1 重写：步骤 1 放权、步骤 2 软基线、步骤 3 固定硬契约；删 `EFFECTIVE_PAGE_SPECIFICATION` |
| `generation-prompt-byte-grammar.md` | 规则 3/4/5/8/10/12/14 更新：三域、软基线、新 payload、事实预检、锁定期望改写 |
| `visual-brief-and-generation.md` | 整章改为"故事板+主题直接编译路径"；取消 brief 组装；旧 brief 惰性兼容 |
| `artifact-contract.md` | 目录产出（删 visual-briefs 新运行要求）、快照 payload、恢复语义 |
| `qa-and-revision.md` | QA 检查项改造（5.3） |
| `design-system.md` | 主题归并段改为软基线表述；删"组装锚点 brief" |
| `workflow.md` | 阶段说明更新（theme/anchor 不再消费 brief） |
| `SKILL.md` | 工作流步骤 5 改"从故事板+主题直接编译 prompt" |
| `interaction-protocol.md` | 页面视觉修订镜像目标从 brief 改为编译输入（叙事/素材域） |
| `layout-catalog.md` | 降级为"软风格参考"，不再作为锁定规格 |
| `tests/` | 更新模板/语法契约测试夹具与断言 |

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 跨页风格漂移（生成器自由发挥） | 软基线 + 锚点批准 + 整套演示 QA 视觉一致性检查 |
| 生成器改写内容时扭曲事实 | 事实底线预检（编译期）+ fact_source_consistency（QA 期）+ 来源行强制 |
| 补充内容混入虚构 | 仅限已批准素材；`narrative_integrity` 之外增加"新内容必须可溯源到研究/来源"QA 项 |
| 旧运行恢复语义变化 | 惰性保留旧 brief；恢复按新路径重编译，intro 记录迁移说明 |
| prompt 哈希与旧产物不可比 | 新旧 prompt 快照天然不同；旧 generation-prompts 目录只读保留 |

## 7. 兼容性

- 旧运行 `.ppt-pilot/visual-briefs/`、`generation-prompts/` 保持只读历史，不迁移、不重写。
- 新运行不再创建 visual-briefs 目录。
- 模板路径 `skills/ppt-start/references/generation-prompt-template.md` 不变（保持唯一编译源）。

## 8. 未决问题（实现前确认）

1. 补充内容的"可溯源"要求：严格要求全部补充内容必须来自研究/来源，还是允许生成器用常识性连接词（如"因此""综上"）而无需溯源？→ 推荐前者严格，后者仅限无事实内容的过渡句。
