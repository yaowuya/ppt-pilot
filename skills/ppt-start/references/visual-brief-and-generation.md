# 逐页视觉 brief 与生成契约

## 进入条件

只有顶层 `manuscript_approved` 检查点已通过，`run.json.manuscript_review.state` 精确保持为 `manuscript_approved`，且已批准故事板和 `theme.json` 都有效时，才能组装视觉 brief。任一内容授权、来源边界或主题状态无效时，停止视觉工作并返回相应上游阶段。

## 唯一视觉生成入口

每个待生成或待修订页面必须先有 `visual-briefs/<slide-id>.md`。该文件是正式页面唯一的视觉生成输入：宿主必须能只依靠它及其明确引用的当前运行产物生成页面，不得依赖对话记忆、探索性预览或未持久化决定。SVG 是派生结果，不是主题、构图或修订历史的权威来源。

生成前必须验证 brief 的快照引用仍指向当前有效故事板和主题，`applied_visual_revision_ids` 与权威历史一致，并且该页没有未解决冲突。无有效 brief 时不得创建、覆盖或修订 SVG。

## 必需章节

每份逐页 brief 必须包含下面七个章节和全部字段；没有适用值时写明 `none` 及理由，不得省略字段。缺少任一章节、快照引用、来源边界或质量要求时停止生成。

- **来源与版本**：`slide_id`、`storyboard_snapshot_id`、`theme_snapshot_id`、`applied_visual_revision_ids`、`brief_snapshot_id`、`selected_style_id`、`selected_style_display_name`、`style_manifest_version`、`style_reference_path`。
- **锁定内容**：`assertion_title`、`audience_takeaway`、`required_content_blocks`、`qualifiers`、`numbers_and_units`、`source_ids`、`forbidden_claims`、`render_copy_policy`。
- **信息层级**：`primary_message`、2–5 条 `supporting_arguments`、`de_emphasized_details`、`reading_order`、`management_judgment`。
- **构图**：`layout_family`、`rationale`、`focal_object`、`region_map`、`primary_secondary_ratio`、`card_count`、`nesting`、`connector_semantics`、`density_strategy`。
- **视觉系统**：`active_palette_roles`、`typography_ladder`、`phrase_emphasis`、`spacing_and_shape`、`prohibited_motifs`、`exceptions`。
- **修订模式**：`mode`、`reason`、`patch_defect`、`fix_attempts_for_candidate`。
- **输出与质量要求**：`canvas`、`safe_area`、`office_safe_svg`、`text`、`source_metadata`、`qa`。

章节顺序固定为：来源与版本、锁定内容、信息层级、构图、视觉系统、修订模式、输出与质量要求。`primary_message` 只能有一个；`reading_order` 必须明确第一至第三阅读位置；连接线只在表达真实语义关系时出现。

## 组装顺序

逐页按以下顺序组装，不得跳层或使用较旧副本：

```text
approved storyboard
-> active theme
-> authoritative visual revision history
-> SVG/QA contracts
-> active visual contract
-> visual-briefs/<slide-id>.md
```

先从已批准故事板复制锁定内容和来源边界，再解析 `theme.json` 的当前令牌与布局约束，然后按 `run.json.interaction_history` 归并适用于整套和该页的有效视觉修订，最后附上 SVG 与 QA 契约。组装结果必须明确记录所有输入快照、已应用视觉修订 ID，以及 `selected_style_id`、`selected_style_display_name`、`style_manifest_version`、`style_reference_path`；保存 brief 后再计算 `brief_snapshot_id`。输入快照或所选风格版本变化后旧 brief 立即失效。

风格包说明服从已批准内容、证据边界和逐页语义。`reference.svg` 只提供视觉语言，不是内容模板；其区域、文案和卡片数量不得覆盖 visual brief 的布局选择。风格包与页面语义冲突时保留页面语义，并把偏离记录在 `exceptions`，不得为了匹配参考图改变锁定内容。

## 内容保护

允许为了展示压缩标签或拆分行，但不得改变主张、置信度、范围、因果、比较、建议、数字、单位、限定条件、来源映射或受众行动。不得把“阶段完成”改成“最终验收”，不得把假设、观察或提案改成已证明结论。

若所需视觉结构无法容纳锁定内容，应拆页、减少非关键装饰或返回故事板阶段；不得通过删掉限定语、来源或关键数字解决空间问题。任何事实性改写都不属于视觉生成，必须使文稿批准失效并重新审查。

## 当前有效契约

按以下优先级归并视觉规则：

1. 不可覆盖层：已批准内容、证据、保密要求、Office-safe SVG 和硬 QA 约束；
2. 种子层：所选风格种子或风格包默认值；
3. 品牌／主题层：当前整套品牌、颜色、字体和视觉方向；
4. 页面层：适用于指定页面的布局、层级和艺术指导；
5. 修复层：不改变构图的局部 defect 修复。

后一条明确规则可以覆盖前一条同字段规则，但必须在权威历史中记录 `supersedes`。被废弃规则只能保留在历史中，不得进入当前有效生成指令或作为备选约束继续影响页面。页面规则只能覆盖其 `affected_scope` 内的页面；局部修复不得覆盖品牌或内容层。

如果两条仍有效规则对同一字段给出互斥值、作用域无法判断、`supersedes` 指向不存在的记录，或历史与阶段产物镜像不一致，必须停止并报告冲突，不得把两条规则同时写入 brief，也不得根据对话猜测优先级。

## 生成模式

`mode` 只能是 `patch` 或 `recompose`：

- `patch` 读取完整 brief、当前 SVG 和唯一、可测量的 `patch_defect`（即 `complete brief + current SVG + one exact defect`）。它只修复碰撞、越界、令牌不一致、小范围对齐、连接线错误或不改变事实的错字，并保持既有焦点、阅读顺序、布局家族、卡片密度、字体系统和语义色。
- `recompose` 读取完整 brief、锁定故事板和当前主题（即 `complete brief + locked storyboard + active theme`）。焦点、层级、阅读路径、布局家族、卡片密度、字体系统、语义色、品牌方向、视觉参考或“更高级／重新优化”等广泛要求都必须使用此模式。旧 SVG 不得作为几何底稿，只能在新候选完成后核对锁定内容与来源是否保持一致。新候选的 `fix_attempts_for_candidate` 从 0 开始；随后最多允许两次局部硬失败 patch，再按 QA 契约执行确定性回退。

主张、来源、事实文案、大纲或故事板变化不属于这两种模式，必须返回文稿工作流。模式无法唯一判定时停止并提出一个直接澄清问题。

## 旧运行

缺少 `visual-briefs/` 的 `schema-v1` 运行仍可读取，不得仅因此迁移或重写已批准上游产物。下一次锚点、正式页面生成或视觉修订前，必须从批准故事板、当前主题和权威 `interaction_history` 补建对应 brief，再继续视觉工作。

补建时沿用该运行实际使用的中英文文件名和已有快照证据。信息不足、批准证据无效、主题互相冲突或无法判断哪些视觉修订仍有效时停止；不得从旧对话、探索性 HTML、现存 SVG 几何或记忆中猜测缺失规则。
