# 页面编译路径（故事板 + 主题直接编译）

本文件是页面生成 prompt 编译路径的权威说明。它取代旧版"逐页 visual brief 组装"阶段：新运行不再创建 `visual-briefs/` 目录，prompt 直接由已批准故事板与 `theme.json` 编译。

## 进入条件

只有 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，且已批准大纲、故事板、`theme.json` 与权威视觉修订历史均有效时，才能编译任何页面 prompt。任一内容授权、来源边界或主题状态失效时，停止视觉工作并返回对应上游 owner。

## 编译输入

每次首次生成或 `recompose` 页面的编译输入为：

1. 已批准故事板（`故事板.md`，快照 `storyboard_snapshot_id`）中该页的记录：`role`、`assertion_title`、`audience_takeaway`、`visual_intent`、`content_blocks`、`source_ids`、`previous_link`／`next_link`；
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