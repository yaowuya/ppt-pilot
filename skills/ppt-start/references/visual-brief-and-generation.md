# 页面编译路径（故事板 + 主题直接编译）

本文件是已批准故事板、`theme.json` 与已应用视觉修订投影到页面生成 Prompt 两个替换域的唯一投影权威。它不定义 envelope、字节、哈希、事务、派发或候选晋升规则；这些职责分别由 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)、[redesign-prompt.md](redesign-prompt.md) 与 [qa-and-revision.md](qa-and-revision.md) 持有。

## 进入条件

只有 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，且已批准大纲、故事板、`theme.json` 与权威视觉修订历史均有效时，才能投影并编译任何页面 Prompt。任一内容授权、来源边界或主题状态失效时，停止视觉工作并返回对应上游权威 owner。

## 权威输入与所有权

每次首次生成或 `recompose` 页面的完整直接编译输入为：

1. 已批准故事板（`故事板.md`，快照 `storyboard_snapshot_id`）中该页的记录。故事板拥有叙事、显示素材、事实、主张、限定词与来源映射，包括 `role`、`assertion_title`、`audience_takeaway`、`visual_intent`、`content_blocks`、`source_ids`、`previous_link`／`next_link`；
2. 当前有效 `theme.json`。主题拥有风格标识与软风格基线，包括色板角色、字体栈、间距节奏与禁止母题；
3. `run.json.interaction_history` 中该页适用的 `visual_revision-<N>` 记录。按 scope／supersedes 契约得到的已应用修订只回写或投影到前述故事板内容所有权或主题风格所有权，不形成第三个页面规格域，也不投影布局令牌。

## 编译步骤：两域投影

1. 从已批准故事板及其已应用内容修订投影 canonical narrative bullets：叙事要点、显示素材以及数字、单位、期间、限定词、因果与来源映射组成的事实底线；
2. 从 `theme.json` 及其已应用风格修订投影 style baseline：用于整套 deck 一致性的软风格方向；
3. 读取唯一规范模板 [generation-prompt-template.md](generation-prompt-template.md)，在内存中恰好替换 `[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]` 两个 whole-line marker；不得增加第三个动态替换域或持久化逐页中间规格；
4. 按 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md) 完成规范化、预检、envelope 与哈希后，持久化 `generation-prompts/<slide-id>.md`（`format: creative-brief-v1`）；
5. 首次生成与 `recompose` 都只通过该已持久化编译 Prompt 进入生成：启动 fresh、独立上下文，只授予编译后的 Prompt；生成上下文只返回一个 `xml` 代码围栏中的完整 SVG。

## 事实底线与生成自由

生成器不得重新选择故事板叙事逻辑，也不得改变数字、单位、期间、限定词、因果与来源映射。它可以对显示素材提纯、改写、重排与补充；补充仅限已批准研究或来源，无事实内容的过渡句可自由撰写。在主题软风格基线内，生成器可以自主选择或重选布局、层级、卡片组织、信息密度、配色用法与装饰，但必须保持整套 deck 的风格一致性。

## 旧运行兼容

旧运行遗留的 `.ppt-pilot/visual-briefs/` 仅作为惰性、只读历史保留，不参与新运行的编译、QA、provenance、recovery 或 invalidation。
