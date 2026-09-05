# Generation Prompt 创意化重构实施计划

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

> **面向 Agent 执行者：** 必需子技能：使用 superpower-subagent-driven-development（推荐）或 superpower-executing-plans 按任务逐项执行本计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 把页面生成 prompt 从"执行锁定视觉规格"重构为"创意产出"：叙事要点 + 内容素材 + 软风格基线 + 输出硬契约，取消逐页 visual brief 阶段。

**架构：** 模板化字节语法保持不变（`generation-prompt-template.md` 为唯一编译源），但模板重写为三步骤（叙事组织/软基线设计/硬契约编码），替换域从两域改三域（叙事素材域 + 风格基线域，删有效页面规格域）。visual brief 阶段取消，storyboard + theme.json 直接编译。哈希 payload 与 QA 检查项同步改造，旧运行惰性兼容。

**技术栈：** Markdown 契约文档（无运行时代码）、Python unittest 契约测试、git。

**规格：** `docs/superpowers/specs/2026-08-26-generation-prompt-creative-reform-design.md`——计划论证以规格为准，规格随计划一同流转，执行者需同时阅读两者。

## 全局约束

- 模板唯一编译源路径不变：`skills/ppt-start/references/generation-prompt-template.md`
- 字节语法权威源不变：`skills/ppt-start/references/generation-prompt-byte-grammar.md`；其他引用文件只链接本文件，不复制编译规则
- 替换域从两个变三个：`[[CANONICAL_NARRATIVE_BULLETS]]`（叙事+素材，来自故事板）、`[[STYLE_BASELINE]]`（软风格基线，来自 theme.json）；删除 `[[EFFECTIVE_PAGE_SPECIFICATION]]`
- 事实底线（来自规格 3.2）：允许提纯/改写/重排/补充，但不得改变数字、单位、期间、限定词（待确认/待验收等）、因果、来源映射；补充内容必须来自已批准研究/来源，仅无事实内容的过渡句（如"因此""综上"）可自由撰写
- 软风格基线：不是逐项锁定令牌；生成器可在保持整套 deck 一致性前提下自选布局/层级/卡片/密度/配色用法/装饰
- 输出硬契约固定不变（viewBox 1280x720、64px 安全区、24px 节奏、path+A 圆角、显式 text+tspan、Office-safe 子集、最小字号 正文≥20px 次级/来源≥14px、全页至多一个主强调焦点、data-source-id 来源行、根含 title/desc）
- 旧运行兼容：已存在的 `.ppt-pilot/visual-briefs/` 惰性保留（只读历史，不迁移不重写）；已存在 `generation-prompts/` 只读保留；新运行不再创建 visual-briefs 目录
- 锚点流程保留：两页锚点（封面 + 密度最高/最困难页）直接由 storyboard + theme.json 编译，guided 预渲染证据后提出锚点批准问题
- 提交信息使用仓库既有风格（`fix(contracts):` / `feat(tools):` / `docs(spec):` 前缀），逐任务原子提交
- 演示用运行目录（`ppt-output/demo-gate-check/`、旧 `D:\05-AI\...` 运行）不是契约测试目标，不修改

---

### 任务 1：重写 generation-prompt-template.md（模板三步骤化）

**文件：**
- 修改：`skills/ppt-start/references/generation-prompt-template.md`（整文件替换）

**接口：**
- 依赖输入：规格第 4.1 节模板结构；现有模板（两域）为基线
- 对外产出：新的三域模板——包含 `[[CANONICAL_NARRATIVE_BULLETS]]`、`[[STYLE_BASELINE]]` 两个 whole-line marker；包含 `# Role`、`## Workflow`、`### 步骤 1`、`### 步骤 2`、`### 步骤 3`、`### 兼容约束` 六个固定标题；不含 `[[EFFECTIVE_PAGE_SPECIFICATION]]`

- [ ] **步骤 1：写测试断言新模板结构**

修改 `tests/test_redesign_prompt_contract.py`（新增测试类 `TemplateCreativeReformTest`，放在 `DEFAULT_CANONICAL_NARRATIVE_BULLETS` 常量定义之后）：

```python
class TemplateCreativeReformTest(unittest.TestCase):
    def test_template_has_two_replacement_domains(self):
        template = read_text(skill_root / "references" / "generation-prompt-template.md")
        self.assertEqual(template.count("[[CANONICAL_NARRATIVE_BULLETS]]"), 1)
        self.assertEqual(template.count("[[STYLE_BASELINE]]"), 1)
        self.assertNotIn("[[EFFECTIVE_PAGE_SPECIFICATION]]", template)

    def test_template_retains_six_fixed_headings(self):
        template = read_text(skill_root / "references" / "generation-prompt-template.md")
        for heading in (
            "# Role:",
            "## Workflow",
            "### 步骤 1",
            "### 步骤 2",
            "### 步骤 3",
            "### 兼容约束",
        ):
            self.assertIn(heading, template)

    def test_template_does_not_order_locked_layout_or_tokens(self):
        template = read_text(skill_root / "references" / "generation-prompt-template.md")
        for banned in (
            "不得重新选择布局",
            "不得重新选择配色",
            "逐项应用有效页面规格",
            "layout_family",
            "有效页面规格（唯一动态内容）",
        ):
            self.assertNotIn(banned, template)

    def test_template_permits_content_reformulation(self):
        template = read_text(skill_root / "references" / "generation-prompt-template.md")
        self.assertIn("不得重新选择叙事逻辑", template)
        self.assertIn("提纯", template)
        self.assertIn("改写", template)
        self.assertIn("补充", template)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：FAIL——旧模板含 `[[EFFECTIVE_PAGE_SPECIFICATION]]`、缺 `[[STYLE_BASELINE]]`、步骤 2/3 仍是锁定布局/令牌措辞

- [ ] **步骤 3：重写模板文件**

用以下完整内容替换 `skills/ppt-start/references/generation-prompt-template.md`：

```markdown
# Role: 高级信息架构师 & SVG 可视化编码专家

你的任务是基于叙事要点与内容素材，自主设计一页布局合理、逻辑清晰、视觉美观、可直接用于演示文稿的 Office-safe SVG。

## Workflow: 执行步骤

### 步骤 1: 组织叙事与内容 (Narrative and Content)

不得重新选择叙事逻辑。严格按照下列叙事要点组织信息：
[[CANONICAL_NARRATIVE_BULLETS]]

内容处理边界：
- 允许对素材进行提纯、改写、重排与补充；补充内容必须来自已批准的研究/来源，仅无事实内容的过渡句可自由撰写。
- 不得改变数字、单位、期间、限定词（待确认、待验收等）、因果、来源映射。
- 不得把推断或新增内容冒充为已批准事实。

### 步骤 2: 应用风格基线并设计视觉表达 (Style Baseline and Visual Design)

风格基线是软参考方向，不是逐项锁定令牌。在保持整套演示文稿风格一致性的前提下，布局、层级、卡片组织、信息密度、配色用法与装饰由你自主决定。
[[STYLE_BASELINE]]

### 步骤 3: 编码 SVG（输出硬契约）

- **画布**: 根元素必须使用 `<svg viewBox="0 0 1280 720">`。
- **安全区与节奏**: 所有可见内容位于 64px 安全区内；间距使用 24px 节奏。
- **圆角卡片**: 仅使用 `<path>` 与 SVG 弧线命令 `A` 绘制圆角卡片；禁止为 `<rect>` 添加 `rx` 或 `ry`。
- **文本**: 每个文本对象使用显式 `<text>`；每一行使用简单、非嵌套的 `<tspan>`，并保证文本不越界；文字保持为文字，不转轮廓。
- **字号**: 正文 ≥20px，次级/来源 ≥14px；关键数字可用大字号或强调色突出，全页至多一个主强调焦点。
- **来源**: 带 `SRC` 的主张所在分组携带 `data-source-id`；页脚来源行必须存在。
- **Office-safe 子集**: 仅使用 `svg`、`g`、`path`、`rect`（仅直角）、`circle`、`line`、`polyline`、`polygon`、`text`、`tspan`、`title`、`desc`；禁止 `foreignObject`、脚本、远程资源、滤镜、渐变、动画、`defs`、`use`、`clipPath`、`mask`、`image`。
- **根节点**: 包含 `<title>`（本页结论）与 `<desc>`（视觉关系）。

### 兼容约束

SVG 必须在 PowerPoint、Word 等 Office 软件中保持几何、文本和颜色稳定。所有图形、字体栈、颜色与文字内容必须自包含，不依赖外部文件、URL 或工具调用。

---

只返回一个 ```xml 代码围栏，围栏内必须是完整 SVG；围栏外不得输出解释、Markdown 标题或其它文本。
```

- [ ] **步骤 4：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：PASS（4 个测试全过）

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/references/generation-prompt-template.md tests/test_redesign_prompt_contract.py
git commit -m "feat(contracts): rewrite generation prompt template to creative three-step form"
```

---

### 任务 2：更新字节语法契约（三域 + 新 payload + 事实预检）

**文件：**
- 修改：`skills/ppt-start/references/generation-prompt-byte-grammar.md`（规则 3、4、5、7、8、10、12、14）

**接口：**
- 依赖输入：任务 1 的新模板
- 对外产出：更新后的编译规则——三域替换、新 payload 键、事实预检、锁定期望改为"保留叙事/事实、自由布局令牌"

- [ ] **步骤 1：写测试断言新字节语法**

在 `tests/test_redesign_prompt_contract.py` 的 `TemplateCreativeReformTest` 类中追加：

```python
    def test_byte_grammar_specifies_three_domains(self):
        grammar = read_text(skill_root / "references" / "generation-prompt-byte-grammar.md")
        self.assertIn("[[CANONICAL_NARRATIVE_BULLETS]]", grammar)
        self.assertIn("[[STYLE_BASELINE]]", grammar)
        self.assertNotIn("[[EFFECTIVE_PAGE_SPECIFICATION]]", grammar)
        self.assertNotIn("Exactly two replacement domains", grammar)

    def test_byte_grammar_new_payload_keys(self):
        grammar = read_text(skill_root / "references" / "generation-prompt-byte-grammar.md")
        self.assertIn("style_baseline_snapshot_id", grammar)
        self.assertNotIn("visual_brief_snapshot_id", grammar)
        self.assertNotIn("effective_revision_projection_sha256", grammar)

    def test_byte_grammar_fact_preflight(self):
        grammar = read_text(skill_root / "references" / "generation-prompt-byte-grammar.md")
        self.assertIn("事实", grammar)
        self.assertIn("preflight", grammar)

    def test_byte_grammar_locked_expectation_reformulated(self):
        grammar = read_text(skill_root / "references" / "generation-prompt-byte-grammar.md")
        self.assertIn("不得改变数字、单位、期间、限定词", grammar)
        self.assertNotIn("lay out the supplied regions", grammar)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：FAIL（新增 4 个断言全部失败——规则 3 仍是"Exactly two"，payload 含 visual_brief_snapshot_id）

- [ ] **步骤 3：更新字节语法规则**

对 `skills/ppt-start/references/generation-prompt-byte-grammar.md` 做以下精确替换：

规则 3 标题与正文：`Exactly two replacement domains` → `Exactly two replacement domains plus one style-baseline domain`；正文改为：

```
3. **Replacement domains.** The normalized canonical template contains exactly one whole-line `[[CANONICAL_NARRATIVE_BULLETS]]` token, exactly one whole-line `[[STYLE_BASELINE]]` token, in that order, and no other `[[...]]` marker of any casing. The legacy `[[EFFECTIVE_PAGE_SPECIFICATION]]` token is invalid for new canonical compilation and must not appear anywhere in the compiled body. Prefixing or suffixing either token makes the template invalid. Replace the first with persisted canonical narrative bullets plus content material from the approved storyboard (role, assertion, audience takeaway, visual intent, content blocks with source ids). The explicit default value is the three bullets headed `金字塔原理`, `精确表达`, and `层级执行`; default prose is never inferred at compile time. Replace the second with the persisted soft style baseline derived from `theme.json` (palette roles, font stack, spacing rhythm, prohibited motifs). There is no arbitrary body parameter and no third dynamic replacement marker.
```

规则 4 结尾句：`The resulting body must retain canonical `# Role`, `## Workflow`, `### 步骤 1`, `### 步骤 2`, `### 步骤 3`, and `### 兼容约束` headings.` 保持不变（任务 1 模板已含这些标题）。

规则 5 标题 `Locked decisions` 正文改为：

```
5. **Locked decisions and creative freedom.** Narrative logic is durable and locked: step 1 preserves the approved narrative (role, assertion, audience takeaway, visual intent, SCQA sequence) and the fact floor — exact numbers, units, periods, qualifiers (待确认, 待验收, etc.), causal claims, and source mapping must stay true. Within that floor the generator may purify, rephrase, reorder, and supplement content (supplements limited to already-approved research/sources; non-factual transition phrases are free). Step 2 treats the supplied style baseline as soft direction: the generator freely chooses layout, hierarchy, card organization, density, palette usage, and decoration while keeping the whole deck consistent. Step 3 applies the fixed output contract verbatim. The generator does not re-choose narrative logic; it may optimize, rewrite, infer presentation emphasis, choose, and re-choose visual design within the baseline.
```

规则 7 Envelope：metadata 删除 `visual_brief_snapshot_id`，新增 `format` 字段（值 `creative-brief-v1`），保持九字段。精确文本：

```
7. **Envelope.** Persisted layout is: `# <slide-id> 页面生成 Prompt`, a blank line, `## Snapshot metadata`, exactly nine metadata fields, a blank line, `## Compiled Prompt`, then the compiled body. Metadata fields, in order, are `slide_id`, `storyboard_snapshot_id`, `theme_snapshot_id`, `applied_visual_revision_ids`, `prompt_snapshot_id`, `user_page_request`, `expected_output`, `workspace_output_path`, and `format`. The `format` field value is exactly `creative-brief-v1` for new canonical prompts and distinguishes them from legacy brief-compiled forms. The restriction to those envelope headings applies only to bytes before the compiled body; canonical headings inside the body are required, not forbidden.
```

规则 8 preflight：新增事实预检条目，在 "Also reject any body that cannot be decomposed..." 之前插入：

```
Before creating a durable transaction or dispatching a generator, verify the narrative/material replacement: every number, unit, qualifier, and source id in the material must match the approved storyboard; a mismatch returns the slide to the storyboard owner as `storyboard_fact_mismatch`. Verify the style-baseline replacement is non-empty and derived from a readable `theme.json`; failure returns `style_baseline_unavailable`.
```

同时把规则 8 中禁止列表更新：`the old lean S01 form beginning `Role:` and containing `页面 ID:` plus custom `步骤 1/2/3``（保留，防旧格式注入）。

规则 10 payload：整条替换为：

```
10. **Prompt snapshot payload.** `prompt_snapshot_id` is SHA-256 over canonical JSON bytes with no trailing LF. The payload contains: `applied_visual_revision_ids`, `compiled_prompt_sha256`, `format`, `generation_intent`, `generation_prompt_template_snapshot_id`, `generation_trigger_id`, `outline_snapshot_id`, `resolved_generation_prompt_template_path`, `selected_style_id`, `storyboard_snapshot_id`, `style_baseline_snapshot_id`, `style_kind`, `style_manifest_version`, and `theme_snapshot_id`. `style_baseline_snapshot_id` is SHA-256 over the normalized soft-baseline bytes extracted from `theme.json` (palette roles, font stack, spacing, prohibited motifs). The resolved template path is exactly `skills/ppt-start/references/generation-prompt-template.md`. Legacy `visual_brief_snapshot_id`, `effective_revision_projection_sha256`, `style_prompt_snapshot_id`, and `resolved_redesign_prompt_path` names are invalid for new canonical provenance.
```

规则 12 Transaction identity：`Any change in either replacement` → `Any change in either dynamic replacement, the style-baseline bytes, template bytes, canonical template path/hash, outline snapshot, operation owner, active revision IDs, or storyboard/theme provenance changes the prompt snapshot.` 删除 `or brief/storyboard/theme provenance` 中的 brief。

规则 14 stale/conflict：`non-unique authoritative snapshots` 保留；新增 `style_baseline_unavailable` 属阻断 reason（与 `prompt_preflight_invalid` 并列）。

- [ ] **步骤 4：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：PASS（8 个测试全过）

运行全量：`python -m unittest discover -s tests -v`
预期：除任务 3/4 未动的旧断言（如 locked_content_fidelity 引用）外应通过——若旧测试引用了 `visual_brief_snapshot_id`/`effective_revision_projection_sha256` 而失败，**不要改代码绕过**，记录失败清单供任务 4 统一修。

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/references/generation-prompt-byte-grammar.md tests/test_redesign_prompt_contract.py
git commit -m "feat(contracts): three-domain compilation, new payload keys, fact preflight in byte grammar"
```

---

### 任务 3：取消 visual brief 阶段——改写 visual-brief-and-generation.md 与 artifact-contract.md

**文件：**
- 修改：`skills/ppt-start/references/visual-brief-and-generation.md`（整章重写为"故事板+主题直接编译路径"）
- 修改：`skills/ppt-start/references/artifact-contract.md`（目录产出、快照域、恢复语义）

**接口：**
- 依赖输入：任务 1、2 的模板与语法
- 对外产出：新编译路径文档——不再有逐页 brief 组装；恢复链直接引用 storyboard+theme；旧 brief 惰性兼容声明

- [ ] **步骤 1：写测试断言取消 brief**

在 `tests/test_redesign_prompt_contract.py` 的 `TemplateCreativeReformTest` 类追加：

```python
    def test_generation_path_direct_from_storyboard_and_theme(self):
        path_doc = read_text(skill_root / "references" / "visual-brief-and-generation.md")
        self.assertIn("storyboard", path_doc)
        self.assertIn("theme.json", path_doc)
        self.assertNotIn("必须先持久化", path_doc)
        self.assertNotIn("有效页面规格", path_doc)

    def test_artifact_contract_no_new_brief_requirement(self):
        contract = read_text(skill_root / "references" / "artifact-contract.md")
        self.assertNotIn("visual-briefs/", contract.split("新运行")[0])
        self.assertIn("惰性", contract)
        self.assertIn("只读", contract)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：FAIL（visual-brief-and-generation.md 仍要求"必须先持久化 brief"）

- [ ] **步骤 3：重写 visual-brief-and-generation.md**

用以下内容整文件替换 `skills/ppt-start/references/visual-brief-and-generation.md`：

```markdown
# 页面编译路径（故事板 + 主题直接编译）

本文件是页面生成 prompt 编译路径的权威说明。它取代旧版"逐页 visual brief 组装"阶段：新运行不再创建 `visual-briefs/` 目录，prompt 直接由已批准故事板与 `theme.json` 编译。

## 进入条件

只有 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，且已批准大纲、故事板、`theme.json` 与权威视觉修订历史均有效时，才能编译任何页面 prompt。任一内容授权、来源边界或主题状态失效时，停止视觉工作并返回对应上游 owner。

## 编译输入

每次首次生成或 `recompose` 页面的编译输入为：

1. 已批准故事板（`故事板.md`）中该页的记录：`role`、`assertion_title`、`audience_takeaway`、`visual_intent`、`content_blocks`、`source_ids`、`previous_link`／`next_link`；
2. 当前有效 `theme.json`：所选风格标识、软风格基线（色板角色、字体栈、间距节奏、禁止母题）、已应用与有效的整套视觉修订；
3. `run.json.interaction_history` 中该页适用的 `visual_revision-<N>` 记录（按 scope／supersedes 契约投影），只影响叙事/素材/风格基线表述，不投影布局令牌。

## 编译步骤

1. 在内存组装 canonical narrative bullets（叙事要点 + 内容素材 + 事实底线清单）；
2. 在内存组装 style baseline（来自 theme.json 的软风格基线）；
3. 读取唯一规范模板 [generation-prompt-template.md](generation-prompt-template.md)，在内存恰好替换 `[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]` 两个 whole-line marker；不得有第三动态替换域；
4. 字节规范化、预检与哈希遵循 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)；
5. 持久化 `generation-prompts/<slide-id>.md`（envelope 九字段，`format: creative-brief-v1`）并记录 `prompt_snapshot_id`；
6. 启动 fresh、独立的生成上下文，只授予编译后的 Prompt；首次生成不提供其他页面，重新排版不得提供旧 SVG、创作对话或未持久化上下文；
7. 生成上下文只返回一个 `xml` 代码围栏中的 SVG；调用是严格单轮的（一次请求、一次响应，请求预算与派发播报见 [QA、恢复与修订](qa-and-revision.md)）。

## 事实底线与生成自由

生成器可在不改变数字、单位、期间、限定词、因果与来源映射的前提下，对素材提纯、改写、重排、补充（补充仅限已批准研究/来源，无事实内容的过渡句自由）；可自主选择布局、层级、卡片组织、密度、配色用法与装饰，保持整套 deck 风格一致。

## 旧运行兼容

已存在 `visual-briefs/` 的旧运行惰性保留：目录只读历史，不迁移、不重写、不参与新编译。恢复旧运行时若仍在视觉阶段，按本文件路径从故事板与 theme.json 重编译；旧 brief 的锁定内容不再作为逐字 QA 基准（QA 基准为冻结故事板 + 事实底线）。
```

- [ ] **步骤 4：更新 artifact-contract.md 的对应章节**

对 `skills/ppt-start/references/artifact-contract.md` 做精确编辑（保持其它章节不动）：

1. 运行目录产出一览中删除 `visual-briefs/` 行为说明，改为：`visual-briefs/` 只在旧运行惰性保留；新运行不创建。
2. 把 `brief_snapshot_id` 相关字段说明改为：prompt snapshot 不再引用 brief；`visual_brief_snapshot_id` 从 payload 删除，`format: creative-brief-v1` 标识新格式。
3. 恢复顺序段落（若引用 brief）改为直接引用 storyboard + theme 快照。

- [ ] **步骤 5：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：PASS（10 个测试全过）

运行全量：`python -m unittest discover -s tests -v`
预期：记录仍然失败项（旧 fixtures 引用 `effective-visual-brief-contract.json` 等），供任务 4 修。

- [ ] **步骤 6：提交**

```bash
git add skills/ppt-start/references/visual-brief-and-generation.md skills/ppt-start/references/artifact-contract.md tests/test_redesign_prompt_contract.py
git commit -m "feat(contracts): cancel per-page visual brief; direct storyboard+theme compile path"
```

---

### 任务 4：QA 检查项改造（qa-and-revision.md）

**文件：**
- 修改：`skills/ppt-start/references/qa-and-revision.md`

**接口：**
- 依赖输入：任务 3 的编译路径
- 对外产出：`locked_content_fidelity` → `fact_source_consistency` + `narrative_integrity`；`reading_order` 改为视觉层级 QA

- [ ] **步骤 1：写测试断言新 QA 项**

在 `tests/test_redesign_prompt_contract.py` 的 `TemplateCreativeReformTest` 类追加：

```python
    def test_qa_uses_fact_source_consistency(self):
        qa = read_text(skill_root / "references" / "qa-and-revision.md")
        self.assertIn("fact_source_consistency", qa)
        self.assertIn("narrative_integrity", qa)
        self.assertNotIn("locked_content_fidelity", qa)

    def test_qa_reading_order_replaced_by_hierarchy(self):
        qa = read_text(skill_root / "references" / "qa-and-revision.md")
        self.assertNotIn("reading_order", qa)
        self.assertIn("视觉层级", qa)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：FAIL（qa-and-revision.md 仍含 locked_content_fidelity）

- [ ] **步骤 3：更新 QA 契约**

对 `skills/ppt-start/references/qa-and-revision.md` 编辑：

1. 找到 `## 硬检查`（或等效章节）中的 `locked_content_fidelity` 行，替换为：

```
| `fact_source_consistency` | 数字/单位/期间/限定词/因果/来源映射与冻结故事板一致；措辞自由 |
| `narrative_integrity` | assertion_title / role / audience_takeaway / visual_intent 保留；SCQA 顺序完好 |
```

2. 找到 `reading_order` 检查行，替换为：

```
| `visual_hierarchy` | 主次可辨：主信息面积/字号/明暗显著强于次信息；等权卡片墙视为失败 |
```

3. 补充内容溯源 QA 项（规格第 8 节推荐值）：

```
| `supplement_traceability` | 素材外新增的实质内容必须能在研究.md/来源.md 中溯源；无事实内容的过渡句豁免 |
```

- [ ] **步骤 4：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：PASS（12 个测试全过）

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/references/qa-and-revision.md tests/test_redesign_prompt_contract.py
git commit -m "fix(contracts): QA moves to fact-source consistency and narrative integrity"
```

---

### 任务 5：设计系统与工作流联动更新（design-system.md、workflow.md、SKILL.md、interaction-protocol.md、layout-catalog.md）

**文件：**
- 修改：`skills/ppt-start/references/design-system.md`
- 修改：`skills/ppt-start/references/workflow.md`
- 修改：`skills/ppt-start/SKILL.md`
- 修改：`skills/ppt-start/references/interaction-protocol.md`
- 修改：`skills/ppt-start/references/layout-catalog.md`

**接口：**
- 依赖输入：任务 3 的编译路径
- 对外产出：所有引用 brief 的文档一致指向"直接编译路径"；布局目录降级为软参考

- [ ] **步骤 1：写测试断言引用一致性**

在 `tests/test_redesign_prompt_contract.py` 的 `TemplateCreativeReformTest` 类追加：

```python
    def test_design_system_refers_to_soft_baseline(self):
        ds = read_text(skill_root / "references" / "design-system.md")
        self.assertIn("软参考", ds)
        self.assertNotIn("组装锚点页面 brief", ds)

    def test_workflow_uses_direct_compile_steps(self):
        wf = read_text(skill_root / "references" / "workflow.md")
        self.assertIn("直接编译", wf) or self.assertIn("storyboard", wf)

    def test_skill_workflow_step5_direct_compile(self):
        skill = read_text(skill_root / "SKILL.md")
        self.assertNotIn("组装并验证对应 `visual-briefs/`, skill)
        self.assertIn("生成任何视觉页面前", skill)

    def test_layout_catalog_is_soft_reference(self):
        lc = read_text(skill_root / "references" / "layout-catalog.md")
        self.assertIn("软参考", lc) or self.assertIn("自主", lc)
```

注意 `test_skill_workflow_step5_direct_compile` 中的反引号在 Python 字符串里需转义——用三引号字符串或 `\`` 转义，见步骤 3 实现示例。

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：FAIL

- [ ] **步骤 3：更新四个引用文档**

**design-system.md**：
- 将"主题阶段……先把当前有效主题、布局选择和权威视觉修订历史归并到逐页 `visual-briefs/<slide-id>.md`"段落改为："主题阶段解析当前有效主题后，直接把软风格基线（色板角色、字体栈、间距节奏、禁止母题）纳入编译输入，用于编译锚点与生产页面的 generation prompt；不再组装逐页 visual brief。"在"色彩层级"或"字体"处加一句"风格基线是软参考方向，生成器可在保持整套 deck 一致性的前提下自选布局与视觉表达；关键数字与关键比较的强调规则仍是输出硬契约的一部分。"（保留此前的关键数字强调规则）

**workflow.md**：
- 把"主题阶段解析当前有效主题后组装锚点页面 brief；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页组装其余 brief。任何页面在对应 `visual-briefs/<slide-id>.md` 有效前都不能生成"改为："主题阶段解析当前有效主题后直接编译锚点页 prompt；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页从故事板与 theme.json 直接编译其余页面 prompt。任何页面在对应 `generation-prompts/<slide-id>.md` 有效前都不能生成。"

**SKILL.md**：
- 工作流步骤 5 改为："5. 在生成任何视觉页面前，先按[页面编译路径](references/visual-brief-and-generation.md)从已批准故事板与 `theme.json` 编译并验证对应 `generation-prompts/<slide-id>.md`；没有有效 prompt 不得生成 SVG。"

**interaction-protocol.md**：
- 将"页面决定镜像到 `visual-briefs/<slide-id>.md`"改为"页面决定镜像到该页编译输入（叙事/素材/风格基线表述），并从 `interaction_history` 视为权威"。

**layout-catalog.md**：
- 开头加一段："本目录作为软风格参考：生成器可参考这些布局家族理解语义关系，但页面 prompt 不再锁定 `layout_family`；具体构图由生成器在软风格基线内自主决定。"

- [ ] **步骤 4：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.TemplateCreativeReformTest -v`
预期：PASS（16 个测试全过）

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/references/design-system.md skills/ppt-start/references/workflow.md skills/ppt-start/SKILL.md skills/ppt-start/references/interaction-protocol.md skills/ppt-start/references/layout-catalog.md tests/test_redesign_prompt_contract.py
git commit -m "fix(contracts): align design-system, workflow, skill, protocol, layout-catalog with direct compile path"
```

---

### 任务 6：更新测试夹具与旧断言（全量回归）

**文件：**
- 修改：`tests/test_redesign_prompt_contract.py`（旧断言清理）
- 修改：`tests/fixtures/generation-prompt-snapshot.json`（payload 键更新）
- 修改：`tests/test_visual_generation_contract.py`（如引用 brief 快照）
- 修改：`tests/test_canonical_golden_integration.py`（模板 marker 断言）

**接口：**
- 依赖输入：任务 1–5 的全部契约变更
- 对外产出：全量测试通过（160 项 + 新增 16 项）

- [ ] **步骤 1：运行全量测试并收集失败清单**

运行：`python -m unittest discover -s tests -v`
预期：存在失败——收集每个失败断言及其引用文件（fixture JSON 的 `effective_revision_projection_sha256`、`visual_brief_snapshot_id`、模板 marker 常量、`locked_content_fidelity` 等）

- [ ] **步骤 2：逐项修复失败断言**（每修一个跑一次）

```bash
# 模式：把 fixture 中旧 payload 键替换为新键
# generation-prompt-snapshot.json: 删除 "visual_brief_snapshot_id" 与 "effective_revision_projection_sha256"，
# 新增 "format": "creative-brief-v1" 与 "style_baseline_snapshot_id": "<test-fixture-hash>"
# test_redesign_prompt_contract.py: 更新 EFFECTIVE_PAGE_SPECIFICATION_TOKEN 常量引用与 default bullets 断言
# test_visual_generation_contract.py: brief 快照引用改 storyboard 快照引用
# test_canonical_golden_integration.py: 模板 marker 断言改为两域+新 token
```

每个具体替换文本以失败信息为准（测试输出包含确切断言与期望值）。

- [ ] **步骤 3：确认全量通过**

运行：`python -m unittest discover -s tests -v`
预期：Ran 176 tests, OK

- [ ] **步骤 4：提交**

```bash
git add tests/
git commit -m "test(contracts): update fixtures and assertions for creative-brief-v1 format"
```

---

### 任务 7：验收模拟——用新模板编译一页真实 prompt

**文件：**
- 验证（不提交到仓库）：`ppt-output/demo-gate-check/generation-prompts/S02-new.md`

**接口：**
- 依赖输入：任务 1–6 完成
- 对外产出：展示性验证——新格式 prompt 符合模板、三域替换、事实底线清单、软基线、硬契约

- [ ] **步骤 1：写验证脚本（模拟编译）**

临时脚本 `/tmp/compile_demo.py`（或用 python -c）：

```python
import hashlib, json
from pathlib import Path
skill = Path("skills/ppt-start")
template = (skill / "references/generation-prompt-template.md").read_bytes()
t = template.decode("utf-8")
assert "[[CANONICAL_NARRATIVE_BULLETS]]" in t and "[[STYLE_BASELINE]]" in t
assert "[[EFFECTIVE_PAGE_SPECIFICATION]]" not in t
# 组装叙事/素材域（来自测试 storyboard fixture 的 S05 记录）
narrative = """- **role**: evidence（SCQA 的 A 支撑）
- **assertion_title**: 覆盖率提升直接降低线上故障响应成本
- **audience_takeaway**: 质量门禁与覆盖率是 H2 主线之一
- **visual_intent**: 本页必须揭示覆盖率提升与故障成本下降的因果链
- **素材（可提纯/改写/补充）**:
  - (fact, SRC-001): 底座覆盖率 88%，目标 80%+ 单测覆盖
  - (fact+qualifier, SRC-001): 日均单据下降（待确认）
  - (fact, SRC-001): 质量门禁 + 4.x 单测覆盖
- **事实底线**: 不得改变 88%、80%、待确认；补充仅限已批准研究/来源
"""
style = """- 软风格基线（来自 theme.json）: 色板 主蓝 #156BFF / 证据浅蓝 #EFF6FF / 强调紫 #8866FD；字体 Microsoft YaHei, PingFang SC, Arial, sans-serif；间距 24px 节奏、64px 安全区；禁止母题 左侧长蓝条、等权卡片墙、全页阴影
- 保留整套 deck 风格一致性；布局/层级/密度由你自主决定"""
body = t.replace("[[CANONICAL_NARRATIVE_BULLETS]]", narrative).replace("[[STYLE_BASELINE]]", style)
compiled = hashlib.sha256(body.encode("utf-8")).hexdigest()
print(f"compiled_prompt_sha256={compiled}")
print(body[:2000])
```

- [ ] **步骤 2：写输出文件并检查事实底线**

运行：`python /tmp/compile_demo.py > ppt-output/demo-gate-check/generation-prompts/S02-new.md.tmp`
再读该文件人工核对：含三步骤标题、叙事/素材域、软基线域、硬契约、无 `有效页面规格`、无 `EFFECTIVE_PAGE_SPECIFICATION`。

- [ ] **步骤 3：确认此模拟 prompt 可作为下一轮真实验收基准**（测试 `tests/prompts/` 或人工运行 ppt-start 验证一次真实生成，visual_qa 记录 not_rendered 或真实渲染，验收目标：一次请求产出合规 SVG，无 patch 阶梯）

- [ ] **步骤 4：提交**（只提交测试与文档，不提交 ppt-output 下的临时文件）

```bash
git status --short  # 确认 ppt-output/demo-gate-check/ 未被跟踪或已 gitignore
git add skills/ppt-start tests
git commit -m "chore: demo compile verification for creative-brief-v1 prompt"
```

---

## 自检记录

**规格覆盖度**（对照 spec 第 4–7 节）：
- 4.1 新模板 → 任务 1 ✓
- 4.2/4.3 三域替换 → 任务 2 ✓
- 5.1 payload 键 → 任务 2 ✓
- 5.2 编译门禁（保留自包含/删除布局一致性/新增事实预检）→ 任务 2 规则 8 ✓
- 5.3 QA 改造 → 任务 4 ✓
- 5.4 恢复机制 → 任务 3 artifact-contract ✓
- 5.5 锚点流程 → 任务 5 workflow ✓
- 5.6 文档改动清单 → 任务 1/2/3/4/5 ✓（11 文件 + tests）
- 6 风险缓解 → 分散在各契约文档 ✓
- 7 兼容性 → 任务 3 旧运行惰性 ✓
- 8 未决问题（补充可溯源→严格，过渡句豁免）→ 任务 1 模板 + 任务 4 supplement_traceability ✓

**占位符扫描**：无 TBD/TODO；测试代码均为完整可执行片段；"具体替换文本以失败信息为准"仅用于测试失败修复（属常规 TDD 循环，非占位符缺陷）。

**类型一致性**：
- 模板 marker：`CANONICAL_NARRATIVE_BULLETS` / `STYLE_BASELINE` 全计划一致
- 新 payload 键：`style_baseline_snapshot_id` / `format` 全计划一致
- QA 名：`fact_source_consistency` / `narrative_integrity` / `visual_hierarchy` / `supplement_traceability` 全计划一致
- envelope 九字段顺序：任务 2 规则 7 与任务 3 步骤 3 文案一致
