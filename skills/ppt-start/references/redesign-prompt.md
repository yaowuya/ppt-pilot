# 页面首次生成与重新排版专用 Prompt 契约

## Active request and path names

Active generation uses `user_page_request`, never the old active slot name. Initial generation derives it from the approved storyboard and theme; deterministic fallback uses its fixed fallback request. For `user_recompose`, the orchestrator selects the single applied `interaction:<id>` owner, sorts its `normalized_changes` keys canonically, and renders a deterministic concise natural-language summary of those normalized values without adding facts; the raw `answer` remains only in `interaction_history` and neither it nor history JSON enters the prompt. New prompts are written to `.ppt-pilot/generation-prompts/<slide-id>.md`. The transaction stores `generation-prompts/<slide-id>.md`; `prompt_path is relative to `.ppt-pilot/``. Old marker names are accepted only by explicit stale-reader classification and are inert.

## 强制适用范围

本契约是 **所有页面** 视觉生成的统一执行入口：

- 每个页面首次生成必须使用；
- 每个 `recompose` 必须使用，包括用户明确要求重新排版与系统主动重构；
- `patch` 不使用本契约；本契约不得用于 patch，仍读取完整编译输入（故事板+theme）、当前 SVG 和一个精确 defect。

完成编译输入组装后，**不得由故事板或 theme 直接生成** SVG。必须先在内存完成规范编译与全部确定性 preflight，再在任何 prompt／transaction／candidate 写入前协商安全 fresh isolation；无能力时只写 run-level blocker。能力通过后才按 pointer-last 协议准备 schema-v2 per-slide transactions、batch manifest 与 `run.json.active_visual_generation_batch`，并持久化 `.ppt-pilot/generation-prompts/<slide-id>.md`；批次激活后 fresh 独立上下文才能使用该 Prompt 生成。

## 明确重新排版的触发与路由

当用户明确表达以下任一意图时，必须使用本路径并归类为 `recompose`：

- “重新排版”；
- “重做版式”；
- “重新设计页面”；
- “换个排版”；
- “这页效果不好，重新做”。

局部碰撞、越界、对齐误差和错字仍按 `patch` 处理。用户要求改变事实、数字、限定条件、来源或受众行动时，不得进入本路径，必须返回文稿工作流。

## 持久产物与权威关系

每个首次生成或 `recompose` 都直接从已批准故事板与 `theme.json` 编译 `.ppt-pilot/generation-prompts/<slide-id>.md`（编译路径见 [visual-brief-and-generation.md](visual-brief-and-generation.md)）。不再组装逐页 visual brief；旧运行已有的逐页 brief 产物只作为惰性、只读历史保留，不迁移、不重写、不参与新编译。

该文件的持久布局以黄金范本为唯一标准（完整规则见下方字节契约）：第 1 行是 `# <slide-id> 页面生成 Prompt`；随后是恰好九个加粗字段组成的 `## Snapshot metadata`（`slide_id`、`storyboard_snapshot_id`、`theme_snapshot_id`、`applied_visual_revision_ids`、`prompt_snapshot_id`、`user_page_request`、`expected_output`、`workspace_output_path`、`format`，其中 `format` 精确为 `creative-brief-v1`）；最后一个标题是 `## Compiled Prompt`，其后是解析后模板的完整编译正文。全文件所有路径必须是工作区相对路径，禁止绝对路径、盘符、UNC 与 URL。compiler 先按 `theme.selected_style_id` 解析 registry，再严格执行 manifest → tokens → guidance → prompt traversal；每个可选择 `style_pack` 必须声明风格自有完整 `files.prompt_template`，字段缺失 fail closed，不使用 repository runtime fallback。模板唯一动态注点必须是 whole-line `{{NARRATIVE}}`，只注入一次不含来源注解的已批准故事板叙事／素材与非来源 `block_id`。`prompt_baseline` 不进入正文替换域。历史旧 marker `[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]` 对新编译均无效并必须拒绝。正文不得包含 raw answer、history JSON、未解析 marker、历史风格模板 schema 头、硬约束 ID 列表或 UNTRUSTED 围栏，也不得指示 generator 调用工具或读取外部文件。

风格身份四字段属于 deck-level `theme.json`；逐页 `generation_intent`／`generation_trigger_id`、revision projection 与执行状态由 schema-v2 per-slide transaction 文件持有，`run.json` 只持有 `active_visual_generation_batch`。generation prompt 本身只显示九个元数据字段，且 provenance 只保留 revision IDs，不保留原始回答或历史对象。

输入快照、主题、锁定内容或有效视觉修订变化后，旧 Prompt 立即失效。`.ppt-pilot/generation-prompts/` 是派生产物，不能覆盖故事板或权威修订历史。

新生成统一写入 `.ppt-pilot/generation-prompts/<slide-id>.md`；旧 `.ppt-pilot/redesign-prompts/` 永远只读且 inert。

### schema-v1 identity、operation owner 与旧目录迁移

schema-v1 `visual_generation_transaction` 只能按 [artifact-contract.md](artifact-contract.md) 的 v1→v2 顺序迁移：先 transaction、再 manifest、最后一次原子 `run.json` 替换删除 v1 owner 并发布 v2 pointer。迁移和 crash 恢复的 generator calls 必须为 0，不读取模型、不从 SVG 内容推断缺失值；v1+v2 split brain 或 prepared bytes 不一致都以 `visual_generation_state_conflict` fail closed。

四个 schema-v1 identity 字段（`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`）由 `theme.json` 持有；权威定义见[产物契约 Task 6](artifact-contract.md)。四字段不提升 schema 版本；`style_manifest_version` 对 `legacy_seed` 固定为 `none`，对 `style_pack` 固定为当前 manifest version。missing fields 只能从已验证 registry／manifest 或已持久 operation owner 派生后重建；registry 缺失时 identity-recovery table 只恢复旧运行身份，不授权编译或生成，任何生成请求仍返回 `registry_missing`。不得从 SVG、目录、请求文案或用户措辞推断。

`generation_intent` 与 `generation_trigger_id` 是 generation prompt 的 operation owner。四个合法 operation rows 固定如下：

| generation_intent | mode | generation_trigger_id | fixed reason / sentinel |
|---|---|---|---|
| `initial_generation` | `recompose` | `initial:<slide-id>:<storyboard_snapshot_id>` | `initial generation from approved storyboard and theme`；`user_page_request` 为 `none (initial generation)`；prior candidate 为 `none` |
| `user_recompose` | `recompose` | `interaction:<applied-history-id>` | `user_page_request` 只能是从权威 history 规范化并推导后的简短意图摘要；raw answer 与 history JSON 不进入 prompt |
| `deterministic_fallback` | `recompose` | `fallback:<slide-id>:<failed-transaction-64hex>:2` | `deterministic single-column or two-column fallback after two failed patches`；`user_page_request` 为 `none (deterministic fallback after two failed patches)` |
| `local_patch` | `patch` | `patch:<slide-id>:<qa-defect-id>` | `requires_current_svg: true`；`compile_full_prompt: false`，不得编译完整 generation prompt |

theme 四字段缺失/冲突、legacy version 不是 `none`、trigger owner 缺失/无效/多个、stored compiled body 与 hash 不一致、或同一 transaction/provenance 无法唯一解释时返回 `prompt_snapshot_conflict` 并发布 `generation_prompt_unavailable` blocker。当前 registry display name、manifest version、已声明 `files.prompt_template` 的规范路径或模板 bytes 已变化时属于 ordinary stale，重建 theme/generation prompt，不写 style blocker。只有未被 manifest 声明的历史 `REDESIGN.md`／`*.redesign.md` 的存在、路径或字节变化不参与 stale、provenance 或 snapshot identity。

same `interaction:<id>` copied to every affected page compile input; each slide keeps distinct slide-specific transaction identities and prompt snapshots。Deck-scope user_recompose fan-out copies the same `interaction:<id>` to every affected page compile input; each slide keeps distinct slide-specific transaction identities and prompt snapshots.

不再支持旧 `redesign-prompts/` 目录；若发现该目录，下次首次生成或 recompose 按当前故事板/theme 编译 `generation-prompts/<slide-id>.md`；新目录 stale 时只替换新目录文件；双目录同页时以新目录 provenance 为准；不同 slide 独立处理；旧目录存在与否从不构成 style identity 或 operation owner 证据。

## 风格身份与资产解析

解析器只是一份身份、令牌、指导与模板的 package oracle／书面协议：测试中的 `resolve_style_case(case)` 用它验证包内路径、身份与完整性契约，但它不是运行时安全实现，也不能替代宿主对真实文件系统的 no-follow／`lstat` 检查。运行时必须从受信任的 Skill 根解析，不能从请求文本、目录猜测或旧 SVG 反推风格。每个可选择 style pack 必须通过 manifest 的 `files.prompt_template` 拥有完整可执行生成正文；字段缺失返回 `style_asset_field_missing`，不读取 repository authoring seed。

### 固定解析顺序

1. 先验证 `run.json.manuscript_review.state == manuscript_approved`，并确认当前 storyboard、theme 快照有效。
2. 从 `theme.json` 读取唯一 `selected_style_id`。
3. 定位 `assets/styles/registry.json`：
   - 只有 no-follow／`lstat` 明确返回不存在时才进入只读 identity recovery；该恢复只补全旧运行身份，不授权主题选择、Prompt 编译或页面生成，生成请求仍以 `registry_missing` fail closed；
   - 任一路径组件或叶节点是 symlink、junction 或 reparse point 时返回 `registry_path_unsafe`；
   - 目标不是普通文件时返回 `registry_target_invalid`；不可读或非 UTF-8 返回 `registry_unreadable`；JSON 无效返回 `registry_malformed`；schema 非 1 返回 `registry_schema_unsupported`；
   - registry 中 style ID 和 display name 必须唯一，否则返回 `registry_duplicate_style`；
   - 在处理所选条目前，按 registry 数组顺序验证每个 `style_pack` 的 entrypoint 精确等于 `<entry-id>/manifest.json`，其 exact pack root 必须是 `assets/styles/<entry-id>/` 的直接子目录，所有 pack roots 必须互不相同且互不嵌套；失败统一返回 `entrypoint_path_unsafe`。这一步也覆盖未选中的 pack。
4. registry 存在时按 `selected_style_id` 精确查找唯一条目；不存在返回 `style_not_registered`，`kind` 不是 `legacy_seed` 或 `style_pack` 返回 `style_kind_invalid`。
5. selected `entrypoint` 缺失返回 `entrypoint_missing`；路径为空、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越或 no-follow target link/symlink/junction/reparse 返回 `entrypoint_path_unsafe`；目标缺失、目录或特殊文件返回 `entrypoint_target_invalid`；不可读或非 UTF-8 返回 `entrypoint_unreadable`。
6. `legacy_seed`：`entrypoint` 相对 `assets/styles/` 解析，规范化后仍必须位于 styles 根内，且不得位于任一已注册 style-pack 子目录；seed JSON 格式或结构错误返回 `legacy_entrypoint_malformed`，seed `name` 与 selected ID 不同返回 `legacy_identity_mismatch`。
7. `style_pack`：entrypoint 打开前再次确认所有组件和叶节点非 no-follow target link/symlink/junction/reparse，且 manifest 位于 exact pack root 内。manifest JSON 无效返回 `manifest_malformed`，schema 非 1 返回 `manifest_schema_unsupported`，`id`、`kind`、`display_name` 与 registry／selected 不一致返回 `manifest_identity_mismatch`，`version` 未 fullmatch `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$` 返回 `manifest_version_invalid`。
8. style-pack 的 `files` 必须恰好声明 `tokens.json`、`STYLE.md` 与 `prompt.md` 三个固定目标，`files.tokens`、`files.guidance`、`files.prompt_template` 都是必需字段；任一字段缺失返回 `style_asset_field_missing`。按 tokens → guidance → prompt 的固定顺序相对 exact pack root 解析，前一资产未完整通过前不得触碰后一资产。tokens／guidance 的路径、target、可读性与 tokens schema 失败沿用 `style_asset_*` reason；prompt 的路径、target、可读性和 canonical shell／单 whole-line `{{NARRATIVE}}`／tokens 精确 binding 失败映射到对应 `prompt_*` reason。tokens／guidance 规范路径记录在 `theme.json`，prompt 规范路径与 normalized bytes hash 进入 generation provenance。
9. schema-v1 registry／manifest 的其他字段按向前兼容规则忽略。未被 `files.prompt_template` 声明的历史 `REDESIGN.md`／`*.redesign.md` 可留在磁盘，但 resolver 不得查找、派生、读取、验证或哈希，也不得把其路径或字节加入 provenance 或 snapshot identity。
10. 在编译规范正文前完成身份握手：`theme.json` 的 selected style ID、display name、kind、manifest version 必须与当前 registry／manifest 一致；registry-backed legacy 的 manifest version 必须是字符串 `none`。registry 缺失时，下方表仅可同时匹配 seed `name` 以恢复旧运行身份，随后仍以 `registry_missing` 停止生成。theme 内部矛盾或多个持久 owner 声明不同 style 时返回 `prompt_snapshot_conflict` 并发布 `generation_prompt_unavailable` blocker。theme 一致但安装升级导致当前 display name 或 manifest version 改变时，这是 ordinary stale，按现有 theme 失效规则返回 `theme` 并重建，不写 style blocker。
11. 身份握手与第 8 步完整 traversal 通过后，在内存编译 style-owned 模板正文并完成本文件全部确定性 preflight，再协商安全 fresh-isolation 能力。无能力时保持零 prompt／transaction／candidate 写入；能力通过后才按页写入 `compiling` schema-v2 transaction，持久化并复读 prompt，提交 `compiled`，再写 batch manifest 并最后发布 active pointer。

### 稳定 reason traversal

所有风格身份或资产解析 blocker 使用 `state: style_assets_unavailable`，并按下面 traversal 的第一个失败项返回唯一 reason。枚举文本包括：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`entrypoint_unreadable`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`style_asset_malformed`、`style_asset_schema_unsupported`。persisted identity／provenance 冲突是例外：返回 `prompt_snapshot_conflict` 并发布 `generation_prompt_unavailable`，不属于 style-assets blocker reason 集合。

| 顺序 | predicate | reason |
|---|---|---|
| 1 | registry 缺失；可选只读 identity recovery 不改变生成阻断 | `registry_missing` |
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
| 5 | selected entrypoint 不可读或非 UTF-8 | `entrypoint_unreadable` |
| 6 | legacy JSON 无效／结构不完整 | `legacy_entrypoint_malformed` |
| 6 | legacy `name` 与 selected ID 不同 | `legacy_identity_mismatch` |
| 7 | manifest JSON／schema／identity／version 无效 | 对应 `manifest_*` reason |
| 8 | selected pack 的 `files.tokens`、`files.guidance` 或 `files.prompt_template` 字段缺失 | `style_asset_field_missing` |
| 8 | 上述资产路径越界／no-follow target | `style_asset_path_unsafe` |
| 8 | 上述资产目标缺失、目录或特殊文件 | `style_asset_target_invalid` |
| 8 | tokens／guidance 不可读或非 UTF-8 | `style_asset_unreadable` |
| 8 | tokens JSON 无效 | `style_asset_malformed` |
| 8 | tokens schema 非 2 | `style_asset_schema_unsupported` |
| 8 | prompt 路径、目标、可读性或 canonical binding 无效 | 对应 `prompt_path_unsafe`、`prompt_file_missing`／`prompt_target_invalid`、`prompt_unreadable` 或 `prompt_template_invalid`，发布 `generation_prompt_unavailable` |
| 10 | persisted provenance／snapshot 无法唯一解释；发布 `generation_prompt_unavailable` | `prompt_snapshot_conflict` |

同一状态有多个缺陷时严格按顺序与 registry 数组顺序选择一个 reason：未选 pack root 错误先于 selected assets；selected tokens 错误先于 guidance 错误。

### 缺 registry 的只读 identity recovery

identity recovery 只在 no-follow／`lstat` 确认 `assets/styles/registry.json` 不存在时探测。必须验证下列三份 seed JSON 的结构与 `name` 身份；三份 seed 全部有效时，只允许为既有运行恢复三个 legacy ID 的只读身份。该结果不解析 manifest、tokens、guidance 或 prompt，也不授权首次生成／`recompose`；任何生成请求仍返回 `registry_missing`。任一 seed 缺失、不可读、格式错误或身份不符，selected ID 未知或只存在于 registry-backed style-pack 时，同样返回 `registry_missing`；不得扫描目录发现 style pack。磁盘上的其他历史文件不参与 identity recovery。

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | identity evidence path |
|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` |


### 修订投影验证，不重复物化

编译输入按 [页面编译路径契约](visual-brief-and-generation.md) 从权威 history 完成 applicability、scope、ID、history mirror 与 `supersedes` 验证，确定 canonical active projection。compiler 不重新选择修订、不重排 ID，也不再次覆盖字段；它只执行以下一致性验证：

1. `applied_visual_revision_ids` 必须是无重复、按 `visual-revision-N` 数值升序的完整源列表，每个 ID 对应权威 history 中 `kind: visual_revision`、`status: applied` 的同一记录。
2. 重新验证每条 `<earlier-id>:<normalized_changes-field>` edge，按同一规范算法推导 deterministic active projection；缺失、自身／未来目标、重复 edge、字段不存在或 mirror 冲突均返回 `prompt_snapshot_conflict`。
3. generation prompt provenance 只保留 revision IDs；最终有效内容修订先投影回故事板 owner，最终有效视觉修订只投影回故事板／theme owner 与 revision provenance。不得直接改写已选 style pack 的 prompt/tokens 或把修订变成第八条 Step-2 行；需要改变风格时必须选择或重建一个通过完整验证的 style pack。raw `answer`、recommendation、clarification、未归一化 history 对象和 raw JSON 一律排除。
4. compiler 的唯一动态替换域是 resolved template 中的 whole-line `{{NARRATIVE}}`；它只接收不含来源注解的已批准故事板叙事／素材。`prompt_baseline` 只参与风格数据、QA 与 snapshot provenance，不作为修订片段或正文注入。无修订时 `applied_visual_revision_ids` 为 `[]`。

### 编译上下文与精确 preflight 顺序

首次生成和 `recompose` 的编译器必须先完成全部内存工作，随后才能产生任何 durable side effect：

1. 读取当前批准 outline、storyboard、theme 与权威 revisions；不写文件或状态。
2. 在内存组装 canonical narrative bullets（叙事要点+素材+事实底线）与 style baseline（软风格基线）。后者已包含 palette 角色、字体栈、间距节奏与禁止母题。
3. 在内存验证 outline/storyboard/theme snapshots 相等；素材事实底线（数字/单位/限定词/因果/来源映射）与故事板一致；narrative bullets 与 outline 一致；theme identity、64 px safe area、字号下限、`path+A` 与 Office-safe allowlist 完整。
4. 复用第 8 步已按 manifest → tokens → guidance → prompt 固定 traversal 解析并验证的 `files.prompt_template`；不得重新跳读 prompt 或绕过前序资产。在内存只替换一次 whole-line `{{NARRATIVE}}`，注入不含来源注解的已批准叙事／素材与非来源 `block_id`。
5. 验证模板与 compiled body 的 canonical byte derivation、自包含性、无外部文件指令、无未解析 marker、无 raw revision material，并计算 template/body/compiled prompt/composite snapshot hashes。
6. 只有批内所有页面的步骤 1–5 全部成功后，才执行宿主能力协商；无安全 fresh isolation 时保持零 prompt／transaction／candidate 写入，只写 run-level `generator_unavailable` blocker。
7. 能力通过后，按 `ordered_slide_ids` 为每页原子写入 schema-v2 transaction `state: compiling`；随后写 `.ppt-pilot/generation-prompts/<slide-id>.md`，关闭、复读、核对 hash，再提交该页 `compiled`。全部 transaction 完整后写入并复读 batch manifest，最后原子发布 `run.json.active_visual_generation_batch`。
8. active pointer、manifest 与完整 transaction inventory 一致后才按协商宽度 dispatch；generator 返回后由 coordinator 处理 candidate 写入／hash、fact-source 与 SVG/visual QA、validated 和 ordered serial promotion。

确定性 preflight 失败必须产生零 transaction 写入、零 prompt 写入、零 generator 调用和零 SVG 写入。缺陷分类为 outline／storyboard／theme defect 并返回对应权威 owner；只有规范模板、规范字节或无法唯一解释的 snapshot/provenance 自身失败才写 canonical `visual_generation_blocker`。preflight 包括但不限于以下关系门禁：

- **事实底线与叙事相等**：素材中的数字、单位、期间、限定词、因果、来源映射与故事板一致；canonical narrative bullets 与 outline 的叙事要点一致；不得靠改写规避差异。
- **风格基线闭合**：palette 是最终颜色值；type/spacing/shape/output 无 token 名或待选项；标题 ≥40 px、正文 ≥20 px、脚注 ≥14 px；所有 region 位于 64 px safe area 并遵循 24 px rhythm。
- **规范编译**：resolved template 源路径唯一；单一 narrative replacement bytes 经过来源注解／Setext／路径／外部输入防护；compiled bytes 只由该模板与唯一 whole-line `{{NARRATIVE}}` 注入派生，`prompt_baseline` 不进入正文。

### `visual_generation_blocker` 生命周期

风格身份／资产解析失败时写入 `state: style_assets_unavailable`；规范模板读取、编译或 pre-dispatch gate 失败时写入 `state: generation_prompt_unavailable`。两类情况都必须以单次原子 `run.json` 替换写入 `visual_generation_blocker`，字段和 reason 集合遵循 [artifact-contract.md](artifact-contract.md)。写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，受影响 `slide_id` 必须继续留在 `dirty_slides`。阻断期间不得启动 fresh generator、不得创建／覆盖 SVG、不得降级为 patch、不得改用其他风格或 stale cached generation prompt。

`resource` 只允许保存已经通过 containment 和 no-follow 检查的 Skill 相对路径：风格资产与已声明模板状态使用 `assets/styles/...`。路径安全前失败、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 越界、link／junction／reparse 或任何工作区／机密路径，都写 `none`；repository authoring seed 不属于运行时 resource。

恢复时的全局顺序固定为 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > schema-v1 visual_generation_transaction migration > active_visual_generation_batch > stage scan`。前五类 durable control state 均不存在或已完成前不得扫描普通阶段。schema-v1 `visual_generation_transaction` 必须先进入 Task 3 的零模型调用迁移，不得直接 dispatch；blocker 存续期间保持该 v1 owner 原样不变，blocker 修复后先原子移除 blocker，再重新进入全局顺序完成 pointer-last 迁移，不能跨过 v1 直接创建新 transaction。只要前序 owner 存在，就不得解析新页面、编译 generation prompt 或启动 generator。已有 blocker 与当前目标为同一 slide 时，重新验证同一资源与快照并幂等刷新；另一 slide 已有 active blocker 时必须先处理原 blocker。仍失败时 transaction writes、prompt writes、generator calls 与 SVG writes 都保持 0。

canonical blocker 必须在 preflight 已失败、且没有为本次尝试创建 transaction 或 prompt 后独立写入；blocker 与同一尝试的 `compiling` transaction 不得共存。历史 crash 若留下旧协议的 prompt／`compiling`／blocker 组合，只能把 prompt 当作不可信派生产物：保留 previous final，清理或隔离 orphan candidate，重新从步骤 1 执行无副作用 preflight；不得用旧 prompt 直接补提交 `compiled`。

### schema-v2 batch／per-slide transaction 生成边界

首次生成与 `recompose` 先在内存完成 resolved template／编译输入验证、单一 `{{NARRATIVE}}` 注入、compiled bytes 验证和全部 hash 计算。每页 transaction 使用规范路径 `.ppt-pilot/visual-generation-transactions/<slide-id>-<tx64>.json`，`transaction_id == prompt_snapshot_id`，内部 `prompt_path` 为 `generation-prompts/<slide-id>.md`；候选为 `slides/.candidates/<slide-id>-<tx64>.svg`，final 为 `slides/<slide-id>.svg`，`prior_final_sha256` 必须是完整 hash 或 `none`。transaction 创建后以同目录 temp+rename 原子写 prompt，关闭、复读、hash 匹配才提交 `compiled`。

所有 per-slide transactions 都关闭、复读并通过 schema/path/batch 校验后，写入 `.ppt-pilot/visual-generation-batches/<batch-id>.json`。manifest 的 `transaction_refs` 与 `ordered_slide_ids` 一一对齐，不复制 transaction state；`promotion_cursor`／`blocker_cursor` 只作提示。manifest 复读成功后才原子写 `run.json.active_visual_generation_batch`，完成 pointer-last 激活。pointer 早于 files 以 `visual_generation_state_conflict` fail closed；files 早于 pointer 则字节复用并只补 pointer。

`candidate_sha256` 只在候选写入、关闭并复读后随 `candidate_written` 提交；`generating` crash 留下的 orphan candidate 必须 delete/isolate，never adopted。`validated` final CAS 只接受 candidate 已是 final、prior final 仍在或第三 hash conflict；任何失败保留 previous final。transport retry、并发 dispatch、validation 与 serial promotion 的后续状态变化分别由 Tasks 4–5 扩展，但 durable owner 始终是该页 transaction 文件，不是 manifest 或 callback。

schema-v1 顶层 `visual_generation_transaction` 只按 [artifact-contract.md](artifact-contract.md) 的 v1 迁移章节解释；新批次绝不创建它。No arbitrary delete/cancel。


### Generation prompt golden layout, byte grammar, hash domains, and stale semantics

本节收敛为单一权威文件：完整定义见 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)（generation prompt byte grammar 与 byte contract 的全部规则）。该文件对本文件同等具有约束力；编译、校验或恢复前必须完整阅读。
## 最终 Prompt 正文模板

新运行的 `.ppt-pilot/generation-prompts/<slide-id>.md` 中 `## Compiled Prompt` 必须由 manifest 必需的 style-owned `files.prompt_template` bytes 唯一派生；仓库 [generation-prompt-template.md](generation-prompt-template.md) 只作建包 authoring seed。compiler 只在唯一 whole-line `{{NARRATIVE}}` 注点注入一次不含来源注解的 approved narrative/material 与非来源 `block_id`，其余模板字节不得改动；`prompt_baseline` 不注入正文。完整 byte grammar 与 hash domain 只由 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md) 定义。

## 独立执行与宿主能力接口

coordinator 先关闭、复读并验证 durable generation prompt，再把完整 Prompt bytes **按值**传给隔离任务；隔离任务永远不接收 prompt 路径，也不能读取工作区。

```text
spawn_isolated_text_task(
  prompt_by_value,
  fresh_history=true,
  filesystem=none,
  tools=none,
  timeout,
  cancellation
) -> attribution_id, task_id, text, status, error_code

get_isolated_text_task_result(attribution_id | task_id)
```

宿主能力协商优先使用 native fresh isolation，其次是受支持的 remote fresh isolation。支持并发且有 durable lookup 时使用配置的 `batch_width` 3 或 4；缺少并发或 durable lookup 但仍有 fresh isolation 时安全降级为 width 1。工作区是否为 Git 不参与能力判断，非 Git 工作区仍可 width 4。没有 fresh isolation、prompt-by-value、fresh history、`filesystem=none`、`tools=none` 或 attribution 时，在任何 prompt／transaction／candidate 写入前以 `generator_unavailable` fail closed。

每个 `(transaction_id, dispatch_epoch)` 最多调用一次 spawn；同 epoch 已有 `host_attribution_id`／`host_task_id` 时只能 durable lookup，不得重复派发。`refused`、`timeout` 与 unknown durable result 分别映射为稳定失败，且 coordinator 保留 transaction 与 previous final。禁止嵌套调用 Claude、Codex 或 DeepSeek CLI；不得探测凭据或 profile；不得使用 coordinator 当前上下文作为 generator fallback；不得要求 Git 或 worktree。

隔离任务只返回 text；coordinator 单独提取恰好一个 `xml` 围栏并解析裸 SVG，先验证每个 `block_id` 仅临时出现一次于规范 `<g data-block-id>` 精确属性值，且不出现在 text／tail／其他属性名值，再与冻结故事板块一一对应；随后按 `block_id -> ordered source_ids` 确定性关联机器来源、移除临时 block 属性并规范化序列化。未知／遗漏／重复／泄漏 block 或非法来源以 `fact_source_mismatch` 在 candidate write 前失败。只有 enrichment 成功后才以 temp+rename 写 candidate，关闭、复读、hash 后提交 `candidate_written`。generator、隔离任务或 completion callback 都不能写 prompt、transaction、candidate、final 或 `run.json`。per-slide validation 可与 sibling generation 重叠，但只有 coordinator 能按 `ordered_slide_ids` 串行提交 final promotion、visible blocker 与 pointer 变化。

每次 compile、model、render、qa、promotion 可写非权威 telemetry span。model span 记录 host/capability/provider/model/isolation、`host_attribution_id`、`host_task_id`、queue/timeout/token/finish reason；其它 phase 对不可用字段写 null。`critical_path_parent_ids` 只表达真实依赖，parallel sibling 取 max；同 `span_id` 的恢复重放只计一次。任何 telemetry 错误只记 `telemetry_diagnostic_failed`，不能改变 generator result、transaction state 或 promotion 决策。

## 候选与 QA

- 候选文件进入输出验收前先运行 SVG、视觉和 PowerPoint 检查。
- 额外文字、多个代码围栏、缺失围栏、提取失败、解析失败都属于硬失败。
- 额外失败（shape 不一致、快照过期、权限不足）返回阻断，不得悄悄降级。
- 仅当 `generation-prompts/<slide-id>.md` 验收通过后，才进入正式候选与后续回归。
