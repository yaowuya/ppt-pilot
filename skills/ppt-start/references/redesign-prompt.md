# 页面首次生成与重新排版专用 Prompt 契约

## 强制适用范围

本契约是 **所有页面** 视觉生成的统一执行入口：

- 每个页面首次生成必须使用；
- 每个 `recompose` 必须使用，包括用户明确要求重新排版与系统主动重构；
- `patch` 不使用本契约；本契约不得用于 patch，仍读取完整 brief、当前 SVG 和一个精确 defect。

完成 visual brief 后，**不得由 visual brief 直接生成** SVG。必须先编译 `generation-prompts/<slide-id>.md`，再由 fresh 独立上下文只使用该 Prompt 生成。

## 明确重新排版的触发与路由

当用户明确表达以下任一意图时，必须使用本路径并归类为 `recompose`：

- “重新排版”；
- “重做版式”；
- “重新设计页面”；
- “换个排版”；
- “这页效果不好，重新做”。

局部碰撞、越界、对齐误差和错字仍按 `patch` 处理。用户要求改变事实、数字、限定条件、来源或受众行动时，不得进入本路径，必须返回文稿工作流。

## 持久产物与权威关系

`visual-briefs/<slide-id>.md` 继续是内容、证据和视觉约束的权威来源。每个首次生成或 `recompose` 都必须额外生成：

```text
generation-prompts/<slide-id>.md
```

该文件的持久布局以黄金范本为唯一标准（完整规则见下方字节契约）：第 1 行是 `# <slide-id> 页面生成 Prompt`；随后是恰好九个加粗字段组成的 `## Snapshot metadata`（`slide_id`、`visual_brief_snapshot_id`、`storyboard_snapshot_id`、`theme_snapshot_id`、`applied_visual_revision_ids`、`prompt_snapshot_id`、`user_page_request`、`expected_output`、`workspace_output_path`）；最后一个标题是 `## Compiled Prompt`，其后是精简编译体。全文件所有路径必须是工作区相对路径，禁止绝对路径、盘符、UNC 与 URL；主题色板与风格构图语义内联进单行 `主题:` 与 `建议语义:` 槽位；编译体不得包含 JSON 数据块、PROMPT_SCHEMA_VERSION 头、HARD_CONSTRAINT_IDS 列表或 UNTRUSTED 围栏，也不得指示 generator 调用工具或读取外部文件。

风格身份四字段、`generation_intent`／`generation_trigger_id`、`compiled_prompt_sha256` 等机器字段持久在 visual brief、`theme.json` 与 `run.json.visual_generation_transaction` 中；该文件本身只显示九个元数据字段。schema-v1 identity 与 operation owner 的完整规则见下节。

输入快照、主题或有效视觉修订变化后，旧 Prompt 立即失效。`generation-prompts/` 是派生产物，不能覆盖 visual brief 或权威修订历史。

早期版本产生的 `redesign-prompts/<slide-id>.md` 只作只读兼容；新运行统一写入 `generation-prompts/`，不得同时激活两种路径。

### schema-v1 identity、operation owner 与旧目录迁移

theme.json 与每份 visual-briefs/<slide-id>.md 必须包含完全相同的四个 schema-v1 identity 字段：`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`。四字段不提升 schema 版本；`style_manifest_version` 对 `legacy_seed` 固定为 `none`，对 `style_pack` 固定为当前 manifest version。missing fields 只能从已验证 registry／manifest／fallback identity table 或已持久 operation owner 派生后重建；不得从 SVG、目录、请求文案或用户措辞推断。

`generation_intent` 与 `generation_trigger_id` 是 visual brief 和 generation prompt 的 operation owner。四个合法 operation rows 固定如下：

| generation_intent | mode | generation_trigger_id | fixed reason / sentinel |
|---|---|---|---|
| `initial_generation` | `recompose` | `initial:<slide-id>:<visual_brief_snapshot_id>` | `initial generation from approved visual brief`；`USER_WORDING` 为 `none (initial generation)`；prior candidate 为 `none` |
| `user_recompose` | `recompose` | `interaction:<applied-history-id>` | `USER_WORDING` 为 `raw answer from applied history record only`，只能来自该 applied history 记录的原始 answer |
| `deterministic_fallback` | `recompose` | `fallback:<slide-id>:<failed-transaction-64hex>:2` | `deterministic single-column or two-column fallback after two failed patches`；`USER_WORDING` 为 `none (deterministic fallback after two failed patches)` |
| `local_patch` | `patch` | `patch:<slide-id>:<qa-defect-id>` | `requires_current_svg: true`；`compile_full_prompt: false`，不得编译完整 generation prompt |

brief 与 theme 的四字段彼此冲突、legacy version 不是 `none`、trigger owner 缺失/无效/多个、stored compiled body 与 hash 不一致、或同一 transaction/provenance 无法唯一解释时返回 `prompt_snapshot_conflict`。brief/theme 彼此一致但当前 registry display name、manifest version、prompt path 或 prompt hash 已变化时属于 ordinary stale，重建 theme/brief/generation prompt，不写 style blocker。

same `interaction:<id>` copied to every affected brief; each slide keeps distinct slide-specific transaction identities and prompt snapshots。Deck-scope user_recompose fan-out copies the same `interaction:<id>` to every affected brief; each slide keeps distinct slide-specific transaction identities and prompt snapshots.

`redesign-prompts/` 始终 inert：旧目录只读保留为历史，不参与 prompt 选择，不写、不移动、不删除。只有旧目录时，下一次首次生成或 recompose 按当前 brief/style 编译 `generation-prompts/<slide-id>.md`；新目录 stale 时只替换新目录文件；双目录同页时以新目录 provenance 为准；不同 slide 独立处理；旧目录存在与否从不构成 style identity 或 operation owner 证据。

## Style Prompt 解析与编译

解析器只是一份 package oracle／书面协议：测试中的 `resolve_style_prompt_case(case)` 用它验证包内路径、身份和 fallback 契约，但它不是运行时安全实现，也不能替代宿主对真实文件系统的 no-follow／`lstat` 检查。运行时必须从受信任的 Skill 根解析，不能从请求文本、目录猜测或旧 SVG 反推风格。

### 固定解析顺序

1. 先验证 `run.json.manuscript_review.state == manuscript_approved`，并确认当前 visual brief、storyboard、theme 快照有效。
2. 只从 visual brief 读取唯一 `selected_style_id`。
3. 定位 `assets/styles/registry.json`：
   - 只有 no-follow／`lstat` 明确返回不存在时才进入完整 fallback；
   - 任一路径组件或叶节点是 symlink、junction 或 reparse point 时返回 `registry_path_unsafe`；
   - 目标不是普通文件时返回 `registry_target_invalid`；不可读或非 UTF-8 返回 `registry_unreadable`；JSON 无效返回 `registry_malformed`；schema 非 1 返回 `registry_schema_unsupported`；
   - registry 中 style ID 和 display name 必须唯一，否则返回 `registry_duplicate_style`；
   - 在处理所选条目前，按 registry 数组顺序验证每个 `style_pack` 的 entrypoint 精确等于 `<entry-id>/manifest.json`，其 exact pack root 必须是 `assets/styles/<entry-id>/` 的直接子目录，所有 pack roots 必须互不相同且互不嵌套；失败统一返回 `entrypoint_path_unsafe`。这一步也覆盖未选中的 pack。
4. registry 存在时按 `selected_style_id` 精确查找唯一条目；不存在返回 `style_not_registered`，`kind` 不是 `legacy_seed` 或 `style_pack` 返回 `style_kind_invalid`。
5. selected `entrypoint` 缺失返回 `entrypoint_missing`；路径为空、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越或 no-follow target link/symlink/junction/reparse 返回 `entrypoint_path_unsafe`；目标缺失、目录或特殊文件返回 `entrypoint_target_invalid`。
6. `legacy_seed`：`entrypoint` 和 `redesign_prompt` 都相对 `assets/styles/` 解析，规范化后仍必须位于 styles 根内，且不得位于任一已注册 style-pack 子目录；seed JSON 格式或结构错误返回 `legacy_entrypoint_malformed`，seed `name` 与 selected ID 不同返回 `legacy_identity_mismatch`。旧 v1 registry 条目只有在三个内置 legacy ID 上缺 `redesign_prompt` 时，始终从 entrypoint 派生 `<entrypoint-stem>.redesign.md`；该派生 prompt 缺失返回 `prompt_file_missing`，其他 legacy 缺字段返回 `prompt_field_missing`。
7. `style_pack`：entrypoint 打开前再次确认所有组件和叶节点非 no-follow target link/symlink/junction/reparse，且 manifest 位于 exact pack root 内。manifest JSON 无效返回 `manifest_malformed`，schema 非 1 返回 `manifest_schema_unsupported`，`id`、`kind`、`display_name` 与 registry／selected 不一致返回 `manifest_identity_mismatch`，`version` 未 fullmatch `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$` 返回 `manifest_version_invalid`。
8. style-pack `files.tokens` 与 `files.guidance` 字段缺失返回 `style_asset_field_missing`；二者都相对 exact pack root 解析，路径越界或 no-follow target link/symlink/junction/reparse 返回 `style_asset_path_unsafe`，目标缺失、目录或特殊文件返回 `style_asset_target_invalid`，不可读返回 `style_asset_unreadable`。tokens／guidance 内容由 theme／design-system 阶段验证，但路径 ownership 与 containment 使用本节同一规则，并在 `theme.json` 记录规范路径；resolver 在身份握手时要求这些记录与当前 manifest 一致。
9. prompt 字段、路径、目标、读取和模板结构失败分别返回 `prompt_field_missing`、`prompt_path_unsafe`、`prompt_file_missing`、`prompt_target_invalid`、`prompt_unreadable`、`prompt_template_invalid`。legacy prompt 不得指向 style-pack 子目录；style-pack prompt 不得指向 legacy 文件、styles 根文件或兄弟 pack；prompt no-follow target link/symlink/junction/reparse 返回 `prompt_path_unsafe`。
10. 在读取模板正文前完成身份握手：visual brief 与 `theme.json` 的 selected style ID、display name、kind、manifest version 必须彼此一致；style-pack 还必须与当前 registry／manifest 一致；registry-backed legacy 的 manifest version 必须是字符串 `none`；fallback 使用下方权威表并同时匹配 seed `name`。brief/theme 互相矛盾或多个持久 owner 声明不同 style 时返回 `prompt_snapshot_conflict`。brief/theme 一致但安装升级导致当前 display name 或 manifest version 改变时，这是 ordinary stale，按现有 theme 失效规则返回 `theme` 并重建，不写 style blocker。
11. 读取模板，验证 `PROMPT_SCHEMA_VERSION: 1`、`STYLE_ID == selected_style_id`、完整 `HARD_CONSTRAINT_IDS`、marker 集合和占位符，然后按模板编译。
12. 先建立 transaction，再持久化 `generation-prompts/<slide-id>.md`；prompt durable 后才能启动 fresh independent generator。

### 稳定 reason traversal

所有 prompt 解析／编译 blocker 使用 `state: style_prompt_unavailable`，并按下面 traversal 的第一个失败项返回唯一 reason。枚举文本包括：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`prompt_field_missing`、`prompt_path_unsafe`、`prompt_file_missing`、`prompt_target_invalid`、`prompt_unreadable`、`prompt_template_invalid`、`prompt_snapshot_conflict`。

| 顺序 | predicate | reason |
|---|---|---|
| 1 | registry 缺失且完整 fallback 不成立 | `registry_missing` |
| 1 | registry 路径含 no-follow target link/symlink/junction/reparse | `registry_path_unsafe` |
| 1 | registry 目标不是普通文件 | `registry_target_invalid` |
| 1 | registry 不可读或非 UTF-8 | `registry_unreadable` |
| 1 | registry JSON 无效 | `registry_malformed` |
| 1 | registry schema 非 1 | `registry_schema_unsupported` |
| 2 | ID 或 display name 重复 | `registry_duplicate_style` |
| 3 | 任一 pack entrypoint 不是精确 `<entry-id>/manifest.json`，pack root 非直接子目录，或 roots 重叠／嵌套 | `entrypoint_path_unsafe` |
| 4 | selected ID 不存在 | `style_not_registered` |
| 4 | selected kind 不支持 | `style_kind_invalid` |
| 5 | selected entrypoint 字段缺失 | `entrypoint_missing` |
| 5 | selected entrypoint 路径越界／no-follow target | `entrypoint_path_unsafe` |
| 5 | selected entrypoint 目标无效／缺失 | `entrypoint_target_invalid` |
| 6 | legacy JSON 无效／结构不完整 | `legacy_entrypoint_malformed` |
| 6 | legacy `name` 与 selected ID 不同 | `legacy_identity_mismatch` |
| 7 | manifest JSON／schema／identity／version 无效 | 对应 `manifest_*` reason |
| 8 | selected pack 的 `files.tokens` 或 `files.guidance` 字段缺失 | `style_asset_field_missing` |
| 8 | 上述资产路径越界／no-follow target | `style_asset_path_unsafe` |
| 8 | 上述资产目标缺失、目录或特殊文件 | `style_asset_target_invalid` |
| 8 | 上述资产不可读 | `style_asset_unreadable` |
| 9 | prompt 字段、路径、目标、读取或模板结构失败 | 对应 `prompt_*` reason |
| 10 | persisted provenance／snapshot 无法唯一解释 | `prompt_snapshot_conflict` |

同一状态有多个缺陷时严格按顺序与 registry 数组顺序选择一个 reason：未选 pack root 错误先于 selected prompt 错误；selected tokens/guidance 错误先于 prompt 错误。

### 缺 registry fallback

fallback 只在 no-follow／`lstat` 确认 `assets/styles/registry.json` 不存在时探测。必须先验证下列三份 seed JSON 的结构与 `name` 身份，以及三份 companion prompt 的 schema、`STYLE_ID`、marker 和占位符契约；六个文件全部有效后，才允许三个 legacy ID 解析到 companion prompt。任一 seed 或 companion 缺失、不可读、格式错误或身份不符，都统一返回 `registry_missing`；selected ID 是未知值或只存在于 registry-backed style-pack 时，也返回 `registry_missing`，不得扫描目录发现 style pack。

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | entrypoint | companion prompt |
|---|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` | `minimal-business.redesign.md` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` | `tech-dark.redesign.md` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` | `bold-editorial.redesign.md` |


### Active visual revision 投影

visual-brief assembler 只负责按既有 scope／supersedes 契约决定本页适用的 `applied_visual_revision_ids`；compiler 不重新猜测 deck／anchor／page applicability。编译 `[ACTIVE_VISUAL_REVISIONS]` 时必须执行唯一的 answer-free projection：

1. brief 中的 `applied_visual_revision_ids` 必须已经是无重复且按 `visual-revision-N` 的 N 数值升序排列的列表；compiler 只验证该顺序，不重新排序。任一 unsorted source IDs、重复 ID 或非 `visual-revision-N` ID 都返回 `prompt_snapshot_conflict`；完整源列表写入 generation prompt provenance 与 composite snapshot，inactive record 的 ID 也必须保留。
2. 每个 ID 必须存在于 keyed `run.json.interaction_history`，且 history record 满足 `kind: visual_revision`、`status: applied`；brief mirror 与权威 history 任一投影字段不一致时返回 `prompt_snapshot_conflict`。
3. 每条 `supersedes` 必须是 `<earlier-id>:<normalized_changes-field>`；目标 ID 必须在同一排序列表中更早出现，字段必须存在。目标缺失、自身／未来目标、重复 edge、字段不存在或跨页 mirror 冲突都返回 `prompt_snapshot_conflict`。
4. 按 N 升序应用 edge；字段被任何后续 applied record supersede 后永久 inactive，即使 superseding record 的同字段以后又被更新，旧字段也不得复活。
5. prompt body 只投影 `id`、`stage`、`affected_scope`、`status`、`artifact_owner`、规范排序的 `supersedes` 和仍 active 的 `normalized_changes`；raw `answer`、recommendation、clarification、理由文字和其他未列字段一律排除。
6. `normalized_changes` 递归使用 canonical JSON key 顺序；没有 active fields 的 record 从 `[ACTIVE_VISUAL_REVISIONS]` body 中省略，但其 ID 仍保留在 `applied_visual_revision_ids` provenance。替换 bytes 是 projection array 的 canonical JSON 加恰好一个 LF；无有效投影时写 `[]
`。

### 编译上下文

- 从 `generation-prompts/<slide-id>.md` 组装模板输入，加入当前 visual brief（locked content）、active theme、source/version、normalized revisions、审核和 QA 边界。
- 写入 `generation-prompts/<slide-id>.md` 并持久化 `prompt_snapshot_id`。
- `visual_generation_blocker.resource` 只保存规范化 Skill 相对路径；路径安全前失败写 `none`，不得持久化未验证绝对路径、URL 或机密内容。

### `visual_generation_blocker` 生命周期

风格 prompt 解析／编译失败时，必须以单次原子 `run.json` 替换写入 `visual_generation_blocker`，字段和 reason 集合遵循 [artifact-contract.md](artifact-contract.md)。写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，受影响 `slide_id` 必须继续留在 `dirty_slides`。阻断期间不得启动 fresh generator、不得创建／覆盖 SVG、不得降级为 patch、不得改用其他风格或 stale cached prompt。

`resource` 只允许保存已经通过 containment 和 no-follow 检查的 `assets/styles/...` Skill 相对路径；路径安全前失败、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 越界、link／junction／reparse 或任何工作区／机密路径，都写 `none`。

恢复时的全局顺序固定为 `pending_interaction` > `visual_generation_blocker` > `visual_generation_transaction` > stage scan。只要 `pending_interaction` 存在，就不得创建或处理 style blocker，不得解析 style prompt，也不得启动 generator。已有 blocker 与当前目标为同一 slide 时，重新验证同一资源与快照并幂等刷新同一对象；若另一个 slide 已有 active blocker，必须先处理原 blocker，不创建并行 blocker。仍失败时 generator calls 与 SVG writes 都保持 0。

如果 resolver 已恢复且 prompt 文件已经 durable，允许临时看到 `visual_generation_transaction.state: compiling` 与 active blocker 同时存在；这表示跨文件步骤已完成但 `run.json` 尚未提交。随后只能通过一次 `run.json` 原子替换同时把匹配 transaction 改为 `compiled` 并移除 blocker。crash 留下该中间态时，resume 必须复核 transaction ID、prompt path、`prompt_snapshot_id` 与 `compiled_prompt_sha256`，匹配则补做这一次替换，不匹配则重编或重新阻断。

### `visual_generation_transaction` 生成边界

首次生成与 `recompose` 在编译 prompt 前先创建 `visual_generation_transaction`；`transaction_id == prompt_snapshot_id`，`prompt_path` 为 `generation-prompts/<slide-id>.md`，候选为 deterministic `slides/.candidates/<slide-id>-<64hex>.svg`，final 为 `slides/<slide-id>.svg`。fresh generator 只在 transaction 已从 `compiled` 原子进入 `generating` 后启动；generator output 先作为 untrusted text 提取单个 fenced XML，再写 deterministic candidate path。`candidate_sha256` 只在候选写入、关闭并复读后提交；`generating` crash 留下的 orphan candidate 必须 delete/isolate，never adopted。

transport 和候选写入失败 reason（`generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch`）只能由显式 resume 消费为同一 transaction 的 `failed -> generating`，并使用 `generation_attempt + 1`；每次宿主调用最多 generator 1 次。SVG／内容／视觉 QA 失败（`svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed`）先持久化 defect，再 patch 或 new deterministic fallback compiling transaction。promotion／state conflict（`final_promotion_conflict`、`transaction_state_conflict`）持久化 production `blocker`，保留 previous final SVG 和 failed transaction；用户解决后 unchanged valid candidate 走 `failed -> validated` promotion retry，authoritative inputs changed 走 failed transaction -> new compiling transaction。No arbitrary delete/cancel。


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

## 独立执行

1. 启动一个 **fresh、独立** 的生成上下文；
2. 只授予 `generation-prompts/<slide-id>.md` 中的完整 Prompt，不提供旧 SVG、创作对话、主题文件或其他页面；
3. 生成上下文只返回一个 `xml` 代码围栏；
4. 从围栏中提取裸 SVG，提取结果必须从 `<svg` 开始并以 `</svg>` 结束；
5. 工作区保存的是裸 SVG，不写入 fenced 文本。

## 候选与 QA

- 候选文件进入输出验收前先运行 SVG、视觉和 PowerPoint 检查。
- 额外文字、多个代码围栏、缺失围栏、提取失败、解析失败都属于硬失败。
- 额外失败（shape 不一致、快照过期、权限不足）返回阻断，不得悄悄降级。
- 仅当 `generation-prompts/<slide-id>.md` 验收通过后，才进入正式候选与后续回归。
