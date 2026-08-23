# 逐页视觉 brief 与生成契约

## 进入条件

只有顶层 `manuscript_approved` 检查点已通过，`run.json.manuscript_review.state` 精确保持为 `manuscript_approved`，且已批准故事板和 `theme.json` 都有效时，才能组装视觉 brief。任一内容授权、来源边界或主题状态无效时，停止视觉工作并返回相应上游阶段。

## 唯一视觉生成入口

每个待首次生成或 `recompose` 的页面必须先有 `visual-briefs/<slide-id>.md`，再编译 `generation-prompts/<slide-id>.md`。visual brief 是内容与视觉契约的权威来源；generation prompt 是 fresh 独立生成上下文的唯一执行输入。不得由 visual brief 直接生成 SVG，也不得依赖对话记忆、探索性预览或未持久化决定。SVG 是派生结果，不是主题、构图或修订历史的权威来源。

生成前必须验证 brief 的快照引用仍指向当前有效故事板和主题，`applied_visual_revision_ids` 与权威历史一致，并且该页没有未解决冲突；随后验证 generation prompt 的 `prompt_snapshot_id`、brief 快照和修订 ID。缺少任一有效文件时不得创建、覆盖或 `recompose` SVG。`patch` 继续使用完整 brief、当前 SVG 与唯一精确 defect，不重新编译 generation prompt。

## 必需章节

每份逐页 brief 必须包含下面七个章节和全部字段；没有适用值时写明 `none` 及理由，不得省略字段。缺少任一章节、快照引用、来源边界或质量要求时停止生成。

- **来源与版本**：`slide_id`、`storyboard_snapshot_id`、`theme_snapshot_id`、`applied_visual_revision_ids`、`brief_snapshot_id`、`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`、`style_token_path`、`style_guidance_path`。
- **锁定内容**：`assertion_title`、`audience_takeaway`、`required_content_blocks`、`qualifiers`、`numbers_and_units`、`source_ids`、`forbidden_claims`、`render_copy_policy`。
- **信息层级**：`primary_message`、2–5 条 `supporting_arguments`、`de_emphasized_details`、`reading_order`、`management_judgment`。
- **构图**：`layout_family`、`rationale`、`focal_object`、`region_map`、`primary_secondary_ratio`、`card_count`、`nesting`、`connector_semantics`、`density_strategy`。
- **视觉系统**：`active_palette_roles`、`typography_ladder`、`phrase_emphasis`、`spacing_and_shape`、`prohibited_motifs`、`exceptions`。
- **修订模式**：`mode`、`generation_intent`、`generation_trigger_id`、`reason`、`patch_defect`、`fix_attempts_for_candidate`。
- **输出与质量要求**：`canvas`、`safe_area`、`office_safe_svg`、`text`、`source_metadata`、`qa`。

章节顺序固定为：来源与版本、锁定内容、信息层级、构图、视觉系统、修订模式、输出与质量要求。`primary_message` 只能有一个；`reading_order` 必须明确第一至第三阅读位置；连接线只在表达真实语义关系时出现。brief 的 `layout_family` 必须原样进入对应 generation prompt 的 `建议语义:` 槽位，按[语义布局目录](layout-catalog.md)的编译层映射规则表达为固定网格；映射偏离记录在 `exceptions`。

## schema-v1 identity 与 operation owner

theme.json 与每份 visual-briefs/<slide-id>.md 必须包含完全相同的四个 schema-v1 identity 字段：`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`。`legacy_seed` 的 `style_manifest_version` 必须是字符串 `none`；`style_pack` 必须写当前 manifest version。missing fields 只能从已验证 registry／manifest／fallback identity table 派生并重建；不得从 SVG、目录、请求文案或用户措辞推断。

每份 brief 还必须持久记录 `generation_intent` 与 `generation_trigger_id`，由当前操作的持久 owner 唯一决定：

| generation_intent | mode | generation_trigger_id | reason / USER_WORDING / candidate |
|---|---|---|---|
| `initial_generation` | `recompose` | `initial:<slide-id>:<visual_brief_snapshot_id>` | `reason: initial generation from approved visual brief`；`USER_WORDING: none (initial generation)`；prior candidate `none` |
| `user_recompose` | `recompose` | `interaction:<applied-history-id>` | `USER_WORDING: raw answer from applied history record only`，只来自该 `status: applied` history 记录的原始 answer |
| `deterministic_fallback` | `recompose` | `fallback:<slide-id>:<failed-transaction-64hex>:2` | `reason: deterministic single-column or two-column fallback after two failed patches`；`USER_WORDING: none (deterministic fallback after two failed patches)` |
| `local_patch` | `patch` | `patch:<slide-id>:<qa-defect-id>` | `requires_current_svg: true`；`compile_full_prompt: false` |

Deck-scope user_recompose fan-out uses same `interaction:<id>` copied to every affected brief; each slide keeps distinct slide-specific transaction identities and prompt snapshots.

trigger owner 缺失、无效、或多个 owner 同时声明不同 intent 时返回 `prompt_snapshot_conflict`。旧 brief 缺 `generation_intent` 或 `generation_trigger_id` 时，只能在下一次视觉操作开始前按当前持久 owner 重建；不能因为 SVG 存在、目录存在或请求 wording 看起来像首次生成而猜测。

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

先从已批准故事板复制锁定内容和来源边界，再解析 `theme.json` 的当前令牌与布局约束，然后按 `run.json.interaction_history` 归并适用于整套和该页的有效视觉修订，最后附上 SVG 与 QA 契约。组装结果必须明确记录所有输入快照、已应用视觉修订 ID，以及 `selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`、`generation_intent`、`generation_trigger_id`、`style_token_path`、`style_guidance_path`；保存 brief 后再计算 `brief_snapshot_id`。输入快照或所选风格版本变化后旧 brief 立即失效。

风格包说明服从已批准内容、证据边界和逐页语义。tokens 与 guidance 只提供颜色、字体、间距、形状、语义角色和抽象构图原则；不得从成品示例或既有 SVG 反推构图，也不得把单页区域、卡片数量、连接关系或阅读路径当成可复用模板。每页必须从当前内容语义独立选择构图；风格包与页面语义冲突时保留页面语义，并把偏离记录在 `exceptions`。

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


### Active visual revision 投影

visual-brief assembler 只负责按既有 scope／supersedes 契约决定本页适用的 `applied_visual_revision_ids`；compiler 不重新猜测 deck／anchor／page applicability。编译 `[ACTIVE_VISUAL_REVISIONS]` 时必须执行唯一的 answer-free projection：

1. brief 中的 `applied_visual_revision_ids` 必须已经是无重复且按 `visual-revision-N` 的 N 数值升序排列的列表；compiler 只验证该顺序，不重新排序。任一 unsorted source IDs、重复 ID 或非 `visual-revision-N` ID 都返回 `prompt_snapshot_conflict`；完整源列表写入 generation prompt provenance 与 composite snapshot，inactive record 的 ID 也必须保留。
2. 每个 ID 必须存在于 keyed `run.json.interaction_history`，且 history record 满足 `kind: visual_revision`、`status: applied`；brief mirror 与权威 history 任一投影字段不一致时返回 `prompt_snapshot_conflict`。
3. 每条 `supersedes` 必须是 `<earlier-id>:<normalized_changes-field>`；目标 ID 必须在同一排序列表中更早出现，字段必须存在。目标缺失、自身／未来目标、重复 edge、字段不存在或跨页 mirror 冲突都返回 `prompt_snapshot_conflict`。
4. 按 N 升序应用 edge；字段被任何后续 applied record supersede 后永久 inactive，即使 superseding record 的同字段以后又被更新，旧字段也不得复活。
5. prompt body 只投影 `id`、`stage`、`affected_scope`、`status`、`artifact_owner`、规范排序的 `supersedes` 和仍 active 的 `normalized_changes`；raw `answer`、recommendation、clarification、理由文字和其他未列字段一律排除。
6. `normalized_changes` 递归使用 canonical JSON key 顺序；没有 active fields 的 record 从 `[ACTIVE_VISUAL_REVISIONS]` body 中省略，但其 ID 仍保留在 `applied_visual_revision_ids` provenance。替换 bytes 是 projection array 的 canonical JSON 加恰好一个 LF；无有效投影时写 `[]
`。


### Generation prompt golden layout, byte grammar, hash domains, and stale semantics

This block is intentionally identical in redesign-prompt.md, visual-brief-and-generation.md, and artifact-contract.md. Every generation-prompts/<slide-id>.md compile uses this generation prompt byte grammar and byte contract, and the persisted file format is exactly the golden format of the approved run ppt-output/fy26-h1-midyear-review/generation-prompts/:

1. General byte normalization for style prompt templates and other non-theme bytes reads UTF-8, rejects undecodable bytes, removes any UTF-8 BOM, normalizes CRLF/CR to LF, preserves leading blank lines and all non-newline content, and enforces exactly one terminal LF. It does not trim leading blank lines from style templates, so adding a template leading blank line changes style_prompt_snapshot_id, compiled_prompt_sha256, prompt_snapshot_id, and transaction_id.
2. Visual brief extraction requires these headings exactly once and in order: ## 来源与版本, ## 锁定内容, ## 信息层级, ## 构图, ## 视觉系统, ## 修订模式, ## 输出与质量要求. Replacement bytes exclude the heading line, trim leading/trailing blank lines, preserve internal line order, and append one LF. SOURCE_AND_VERSION additionally removes the whole line whose prefix is - brief_snapshot_id: before trimming.
3. Persisted file layout is fixed: line 1 is exactly `# <slide-id> 页面生成 Prompt`; the only other headings are exactly `## Snapshot metadata` and `## Compiled Prompt`. Snapshot metadata lists exactly nine bold-name fields in this order: slide_id, visual_brief_snapshot_id, storyboard_snapshot_id, theme_snapshot_id, applied_visual_revision_ids, prompt_snapshot_id, user_page_request, expected_output, workspace_output_path. The compiled body starts on the line after the `## Compiled Prompt` heading. No additional headings, field aliases, or machine-only fields are allowed in the file.
4. Every path in the file is workspace-relative: `workspace_output_path` is exactly `slides/<slide-id>.svg`, and no absolute path, Windows drive letter, UNC path, or URL may appear anywhere in the file. The compiled body must never instruct the generator to call tools or read external files. Theme colors, typography, and style composition semantics are inlined into the single-line `主题:` slot and the `步骤 2` `建议语义:` slot; raw JSON dumps, PROMPT_SCHEMA_VERSION headers, HARD_CONSTRAINT_IDS lists, and BEGIN_UNTRUSTED_USER_WORDING_JSON-style fences must not appear in the persisted file.
5. The compiled body follows the fixed lean skeleton of the golden run: the Role line (`Role: 高级信息架构师 & SVG 可视化编码专家`), the isolation sentence (`你已获得全部输入；不要调用工具、读取文件、访问其他页面或既有 SVG。先对锁定内容进行 PPT 化提纯，再选择最合适 Bento Grid，只返回最终 SVG。`), then `页面 ID:`, `核心结论:`, `受众要点:`, the `锁定内容:` bullet list, the fixed `限定条件:` line (`保留所有待确认、待审议、期后、未核验、假设和计划边界。不得改变主张、数字、单位、期间、来源、因果、建议或受众行动。`), `来源策略:`, the single-line `主题:`, the fixed `步骤 1 内容提纯:` line, `步骤 2 Bento:` ending with the page-specific `建议语义:`, the fixed `步骤 3 SVG:` line, and the closing line (`只输出一个 xml 代码围栏，围栏内从 <svg 开始到 </svg> 结束；不要围栏外文字。`). Variable slots are filled only from the current visual brief, locked storyboard, active theme, active revision projection, and resolved style semantics; template placeholders and brief-section extraction continue to govern how those slot bytes are produced before they are projected into this skeleton.
6. style_prompt_snapshot_id is SHA-256 over the normalized pre-replacement template bytes. compiled_prompt_sha256 is SHA-256 over only the compiled prompt body bytes beginning after the ## Compiled Prompt heading; it excludes the title line, the whole Snapshot metadata section, both headings, and everything before the body.
7. prompt_snapshot_id is SHA-256 over canonical JSON bytes with no trailing LF and exactly these payload keys: applied_visual_revision_ids, compiled_prompt_sha256, generation_intent, generation_trigger_id, resolved_redesign_prompt_path, selected_style_id, storyboard_snapshot_id, style_kind, style_manifest_version, style_prompt_snapshot_id, theme_snapshot_id, visual_brief_snapshot_id. applied_visual_revision_ids is always a JSON array value/text, including zero or one item, ordered by the active-revision projection rules. These payload keys persist in run.json.visual_generation_transaction and visual-brief provenance; the prompt file itself displays only the nine metadata fields.
8. user_page_request mirrors the durable operation owner: initial_generation writes `首次生成 <slide-id>`; deterministic_fallback writes `确定性回退（两次 patch 失败后）`; user_recompose summarizes the applied raw answer without adding facts; expected_output is always exactly `恰好一个 xml 代码围栏中的完整 SVG`.
9. transaction_id == prompt_snapshot_id. `transaction_id` is exactly the full `prompt_snapshot_id`, including the `sha256:` prefix; the same canonical prompt payload repeats byte-identically, while any change to template bytes, resolved prompt path, manifest version, brief/storyboard/theme snapshots, projected revisions, revision ID array, generation intent, or trigger produces a different prompt snapshot and transaction. The candidate path uses only the 64 hex suffix of that same ID.
10. Template path/content/manifest-version drift with otherwise coherent provenance is ordinary stale and triggers recompilation. prompt_snapshot_conflict is reserved for internally inconsistent persisted provenance, stored body/hash mismatch, non-unique authoritative snapshots, invalid active-revision projection, or conflicting operation owners.
11. Hash-capability fallback: when the host provides no deterministic SHA-256 capability, the orchestrator must not fabricate digests. Persist `style_prompt_snapshot_id` and `compiled_prompt_sha256` as the literal `unhashed`, and persist `prompt_snapshot_id` / `transaction_id` as `unhashed:<token>`, where `<token>` is a run-scoped monotonic identifier (one plus the largest numeric suffix among existing `unhashed:` tokens recorded in this run's `run.json.interaction_history`, for example `gp-s03-3`) matching `[0-9a-z][0-9a-z-]*`; the candidate path then uses `slides/.candidates/<slide-id>-<token>.svg`. Resume verification degrades from digest comparison to re-deriving and comparing the nine metadata fields and payload keys; every other rule above, including byte normalization and stale semantics, is unchanged. Inventing a 64 hex digest without computing it is always a hard integrity violation.

## 生成模式

`mode` 只能是 `patch` 或 `recompose`：

- `patch` 读取完整 brief、当前 SVG 和唯一、可测量的 `patch_defect`（即 `complete brief + current SVG + one exact defect`）。它只修复碰撞、越界、令牌不一致、小范围对齐、连接线错误或不改变事实的错字，并保持既有焦点、阅读顺序、布局家族、卡片密度、字体系统和语义色。
- `recompose` 读取完整 brief、锁定故事板和当前主题（即 `complete brief + locked storyboard + active theme`）。焦点、层级、阅读路径、布局家族、卡片密度、字体系统、语义色、品牌方向、视觉参考或“更高级／重新优化”等广泛要求都必须使用此模式。旧 SVG 不得作为几何底稿，只能在新候选完成后核对锁定内容与来源是否保持一致。新候选的 `fix_attempts_for_candidate` 从 0 开始；随后最多允许两次局部硬失败 patch，再按 QA 契约执行确定性回退。

主张、来源、事实文案、大纲或故事板变化不属于这两种模式，必须返回文稿工作流。模式无法唯一判定时停止并提出一个直接澄清问题。

## 页面首次生成与重新排版的统一 Prompt 路径

每个页面的首次生成和任何 `recompose` 都必须读取[页面首次生成与重新排版专用 Prompt 契约](redesign-prompt.md)。用户明确说“重新排版”“重做版式”“重新设计页面”或“换个排版”时仍按本文件分类为 `recompose`，但与首次生成使用同一 Prompt 模板和独立执行路径：

1. 先按本文件组装并验证完整 `visual-briefs/<slide-id>.md`；
2. 从当前 brief、锁定故事板、active theme、权威视觉修订与兼容约束编译 `generation-prompts/<slide-id>.md`；编译必须先通过[专用 Prompt 契约](redesign-prompt.md)的编译门禁（自包含性、布局语义一致、枚举顺序一致、字号下限与容纳预算），门禁失败回上游修 brief／故事板，零请求消耗，通过后记录 `prompt_snapshot_id`；
3. 启动 fresh、独立的生成上下文，只授予编译后的 Prompt；首次生成不提供其他页面，重新排版还不得提供旧 SVG、创作对话或未持久化上下文；
4. 生成上下文只返回一个 `xml` 代码围栏中的 SVG；调用是严格单轮的——一次请求、一次响应，请求预算与派发播报规则见 [QA、恢复与修订](qa-and-revision.md)；
5. 创作上下文提取围栏内内容，确认从 `<svg` 开始并以 `</svg>` 结束，再保存裸 SVG；不得把代码围栏写入 `samples/` 或 `slides/`；
6. 对提取结果执行本文件、SVG 契约和 QA 契约的全部检查。

专用 Prompt 是从 visual brief 派生的执行产物，不改变权威层级。Prompt 过期、快照不匹配、输出含额外文字、多个围栏、缺失围栏或 SVG 无法解析时均为硬失败。圆角卡片遵循专用契约的 `path + A` 规则；普通直角背景仍可使用 `rect`。早期 `redesign-prompts/<slide-id>.md` 只读兼容，新生成统一写入 `generation-prompts/`。

## 可恢复生成 transaction

每个首次生成或 `recompose` 都在 `run.json.visual_generation_transaction` 中记录一个可恢复事务；默认同一运行一次只允许一个 active transaction，仅当并发事务同属当前生产批次且目标 slide 互不相同时，才允许多个 active transaction，而候选写入与提交仍逐页串行。事务 schema 与失败 consumer 以 [artifact-contract.md](artifact-contract.md) 为准，视觉 brief 层必须保证 `generation_intent`、`generation_trigger_id`、`applied_visual_revision_ids` 与 prompt snapshot 的 authoritative inputs 稳定，从而让 `transaction_id == prompt_snapshot_id`。正常图为 `compiling -> compiled -> generating -> candidate_written -> validated -> promoted`；失败图为 `generating | candidate_written | validated -> failed`；恢复只允许 `failed -> generating` 与 `failed -> validated`；权威输入变化或 deterministic fallback 使用 `failed transaction -> new compiling transaction`。

brief 修订、QA defect 与 dirty 状态不得绕过 transaction：previous final SVG 在候选生成、验证失败、QA 失败和 promotion conflict 期间保留；orphan candidate never adopted；`dirty_slides` 只在 promoted transaction 的页面和整套 QA 均通过后清除。`visual_qa_failed`、`svg_contract_failed`、`locked_content_mismatch` 必须先把 defect 持久化到 brief／QA owner，再决定 patch 或 deterministic fallback。No arbitrary delete/cancel。

## 旧运行

缺少 `visual-briefs/` 的 `schema-v1` 运行仍可读取，不得仅因此迁移或重写已批准上游产物。下一次锚点、正式页面生成或视觉修订前，必须从批准故事板、当前主题和权威 `interaction_history` 补建对应 brief，再继续视觉工作。

补建时沿用该运行实际使用的中英文文件名和已有快照证据。信息不足、批准证据无效、主题互相冲突或无法判断哪些视觉修订仍有效时停止；不得从旧对话、探索性 HTML、现存 SVG 几何或记忆中猜测缺失规则。
