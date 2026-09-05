# 页面编译路径（故事板 + 主题直接编译）

本文件是已批准故事板、`theme.json` 与已应用视觉修订投影到页面生成 Prompt 的内容权威。正文只有一个动态域：不含来源注解的故事板叙事／素材注入 resolved template 的 whole-line `{{NARRATIVE}}`；`prompt_baseline` 只保留为风格数据、QA 输入与 snapshot provenance。它不定义 envelope、字节、哈希、事务、派发或候选晋升规则；这些职责分别由 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)、[redesign-prompt.md](redesign-prompt.md) 与 [qa-and-revision.md](qa-and-revision.md) 持有。

## 进入条件

只有 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，且已批准大纲、故事板、`theme.json` 与权威视觉修订历史均有效时，才能投影并编译任何页面 Prompt。任一内容授权、来源边界或主题状态失效时，停止视觉工作并返回对应上游权威 owner。

## 权威输入与所有权

每次首次生成或 `recompose` 页面的完整直接编译输入为：

1. 已批准故事板（`故事板.md`，快照 `storyboard_snapshot_id`）中该页的记录。故事板拥有叙事、显示素材、事实、主张、限定词与来源映射，包括 `role`、`assertion_title`、`audience_takeaway`、`visual_intent`、`content_blocks`、`source_ids`、`previous_link`／`next_link`；
2. 当前有效 `theme.json`。主题拥有风格标识与软风格基线（色板角色、字体栈、间距节奏、形状语言、构图规则与禁止母题，来源为所选中风格包 `tokens.json` 恰好六键的闭合类型 `prompt_baseline`，由 `StyleBaselineCompiler` 确定性投影供 QA 与 provenance 使用；不得附加自由文本扩展小节）；
3. `run.json.interaction_history` 中该页适用的 `visual_revision-<N>` 记录。按 scope／supersedes 契约得到的已应用修订只回写或投影到前述故事板内容所有权或主题风格所有权，不形成第三个页面规格域，也不投影布局令牌。

## 编译步骤：单注点注入

1. 从已批准故事板及其已应用内容修订投影 canonical narrative/material：按 `content_blocks[].reading_order` 保留叙事要点、显示素材、每个内容块唯一稳定的非来源 `block_id`，以及数字、单位、期间、限定词与因果组成的事实底线；编译前必须把 narrative 中的 ordered `block_id` 集合与冻结故事板逐项精确比较，缺失、重复、错页、未知或重排均以 `storyboard_fact_mismatch` 停止。来源映射仍在故事板／coordinator／审查层核验，但 `source=`、`[claim=...source=[...]]`、内部 source ID 等来源注解不得进入注入文本；
2. 按 manifest → tokens → guidance → prompt 的固定 no-follow traversal 读取所选中风格包必需的完整 `files.prompt_template`，先验证 schema-v2 闭合 tokens、canonical hard shell 以及 prompt/tokens 精确绑定，再在内存中把模板的**单一** `{{NARRATIVE}}` whole-line 注点替换为上述叙事／素材。字段缺失 fail closed，仓库 [generation-prompt-template.md](generation-prompt-template.md) 只作 authoring seed，且故意不能通过运行时 binding gate。运行时 `tokens.json.prompt_baseline` 供 QA、风格一致性判断与 snapshot provenance 使用，不注入正文；唯一动态替换域就是该叙事注点，也不持久化逐页中间规格；
3. 按 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md) 完成规范化、预检、envelope 与哈希后，持久化 `generation-prompts/<slide-id>.md`（`format: creative-brief-v1`）；
4. 首次生成与 `recompose` 都只通过该已持久化编译 Prompt 进入生成：启动 fresh、独立上下文，只授予编译后的 Prompt；生成上下文只返回一个 `xml` 代码围栏中的完整 SVG，每个 `block_id` 只可在对应唯一语义 `<g data-block-id>` 的精确属性值中临时出现一次，禁止进入 text／tail／其他属性名值。coordinator 在任何 candidate 持久化、hash 或事件提交前按冻结故事板的 `block_id → ordered source_ids` 确定性关联机器来源元数据、移除该临时属性并扫描全部属性名／值与 text／tail；任一映射、block 泄漏或来源泄漏失败均返回 `fact_source_mismatch`，candidate writes 为 0。

## 事实底线与生成自由

生成器不得重新选择故事板叙事逻辑，也不得改变数字、单位、期间、限定词与因果。它可以对显示素材提纯、改写、重排与展开，但不得添加注入叙事中没有的新事实；无事实内容的过渡句可自由撰写。生成器遵循 style-owned template 已静态物化的软风格方向，自主选择或重选布局、层级、卡片组织、信息密度、配色用法与装饰，并保持整套 deck 的风格一致性；来源映射由 coordinator 在隔离生成后确定性恢复。

## 旧运行兼容

旧运行遗留的 `.ppt-pilot/visual-briefs/` 仅作为惰性、只读历史保留，不参与新运行的编译、QA、provenance、recovery 或 invalidation。
