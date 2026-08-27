# 页面首次生成与重新排版专用 Prompt 契约

## Active request and path names

Active generation uses `user_page_request`, never the old active slot name. Initial generation derives it from the approved storyboard and theme; deterministic fallback uses its fixed fallback request. For `user_recompose`, the orchestrator selects the single applied `interaction:<id>` owner, sorts its `normalized_changes` keys canonically, and renders a deterministic concise natural-language summary of those normalized values without adding facts; the raw `answer` remains only in `interaction_history` and neither it nor history JSON enters the prompt. New prompts are written to `.ppt-pilot/generation-prompts/<slide-id>.md`. The transaction stores `generation-prompts/<slide-id>.md`; `prompt_path is relative to `.ppt-pilot/``. Old marker names are accepted only by explicit stale-reader classification and are inert.

## 强制适用范围

本契约是 **所有页面** 视觉生成的统一执行入口：

- 每个页面首次生成必须使用；
- 每个 `recompose` 必须使用，包括用户明确要求重新排版与系统主动重构；
- `patch` 不使用本契约；本契约不得用于 patch，仍读取完整编译输入（故事板+theme）、当前 SVG 和一个精确 defect。

完成编译输入组装后，**不得由故事板或 theme 直接生成** SVG。必须先在内存完成规范编译与全部确定性 preflight，随后创建 transaction 并持久化 `.ppt-pilot/generation-prompts/<slide-id>.md`，再由 fresh 独立上下文只使用该 Prompt 生成。

## 明确重新排版的触发与路由

当用户明确表达以下任一意图时，必须使用本路径并归类为 `recompose`：

- “重新排版”；
- “重做版式”；
- “重新设计页面”；
- “换个排版”；
- “这页效果不好，重新做”。

局部碰撞、越界、对齐误差和错字仍按 `patch` 处理。用户要求改变事实、数字、限定条件、来源或受众行动时，不得进入本路径，必须返回文稿工作流。

## 持久产物与权威关系

每个首次生成或 `recompose` 都直接从已批准故事板与 `theme.json` 编译 `.ppt-pilot/generation-prompts/<slide-id>.md`（编译路径见 [visual-brief-and-generation.md](visual-brief-and-generation.md)）。不再组装逐页 visual brief；旧运行已有 `.ppt-pilot/visual-briefs/` 惰性保留为只读历史，不迁移、不重写、不参与新编译。

该文件的持久布局以黄金范本为唯一标准（完整规则见下方字节契约）：第 1 行是 `# <slide-id> 页面生成 Prompt`；随后是恰好九个加粗字段组成的 `## Snapshot metadata`（`slide_id`、`storyboard_snapshot_id`、`theme_snapshot_id`、`applied_visual_revision_ids`、`prompt_snapshot_id`、`user_page_request`、`expected_output`、`workspace_output_path`、`format`，其中 `format` 精确为 `creative-brief-v1`）；最后一个标题是 `## Compiled Prompt`，其后是规范模板的完整编译正文。全文件所有路径必须是工作区相对路径，禁止绝对路径、盘符、UNC 与 URL；所有动态内容都由恰好两个 whole-line marker 序列化：`[[CANONICAL_NARRATIVE_BULLETS]]`（叙事+素材）与 `[[STYLE_BASELINE]]`（软风格基线）。正文不得包含 raw answer、history JSON、未解析 marker、风格模板 schema 头、硬约束 ID 列表或 UNTRUSTED 围栏，也不得指示 generator 调用工具或读取外部文件。

风格身份四字段属于 deck-level `theme.json`；逐页 `generation_intent`／`generation_trigger_id`、revision projection 与 transaction 由 `run.json` owner 持有。generation prompt 本身只显示九个元数据字段，且 provenance 只保留 revision IDs，不保留原始回答或历史对象。

输入快照、主题、锁定内容或有效视觉修订变化后，旧 Prompt 立即失效。`.ppt-pilot/generation-prompts/` 是派生产物，不能覆盖故事板或权威修订历史。

新生成统一写入 `.ppt-pilot/generation-prompts/<slide-id>.md`；旧 `.ppt-pilot/redesign-prompts/` 永远只读且 inert。

### schema-v1 identity、operation owner 与旧目录迁移

四个 schema-v1 identity 字段（`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`）由 `theme.json` 持有；权威定义见[产物契约 Task 6](artifact-contract.md)。四字段不提升 schema 版本；`style_manifest_version` 对 `legacy_seed` 固定为 `none`，对 `style_pack` 固定为当前 manifest version。missing fields 只能从已验证 registry／manifest／fallback identity table 或已持久 operation owner 派生后重建；不得从 SVG、目录、请求文案或用户措辞推断。

`generation_intent` 与 `generation_trigger_id` 是 generation prompt 的 operation owner。四个合法 operation rows 固定如下：

| generation_intent | mode | generation_trigger_id | fixed reason / sentinel |
|---|---|---|---|
| `initial_generation` | `recompose` | `initial:<slide-id>:<storyboard_snapshot_id>` | `initial generation from approved storyboard and theme`；`user_page_request` 为 `none (initial generation)`；prior candidate 为 `none` |
| `user_recompose` | `recompose` | `interaction:<applied-history-id>` | `user_page_request` 只能是从权威 history 规范化并推导后的简短意图摘要；raw answer 与 history JSON 不进入 prompt |
| `deterministic_fallback` | `recompose` | `fallback:<slide-id>:<failed-transaction-64hex>:2` | `deterministic single-column or two-column fallback after two failed patches`；`user_page_request` 为 `none (deterministic fallback after two failed patches)` |
| `local_patch` | `patch` | `patch:<slide-id>:<qa-defect-id>` | `requires_current_svg: true`；`compile_full_prompt: false`，不得编译完整 generation prompt |

theme 四字段缺失/冲突、legacy version 不是 `none`、trigger owner 缺失/无效/多个、stored compiled body 与 hash 不一致、或同一 transaction/provenance 无法唯一解释时返回 `prompt_snapshot_conflict`。当前 registry display name 或 manifest version 已变化时属于 ordinary stale，重建 theme/generation prompt，不写 style blocker。历史完整模板文件的存在、路径或字节变化不参与 stale、provenance 或 snapshot identity。

same `interaction:<id>` copied to every affected page compile input; each slide keeps distinct slide-specific transaction identities and prompt snapshots。Deck-scope user_recompose fan-out copies the same `interaction:<id>` to every affected page compile input; each slide keeps distinct slide-specific transaction identities and prompt snapshots.

不再支持旧 `redesign-prompts/` 目录；若发现该目录，下次首次生成或 recompose 按当前故事板/theme 编译 `generation-prompts/<slide-id>.md`；新目录 stale 时只替换新目录文件；双目录同页时以新目录 provenance 为准；不同 slide 独立处理；旧目录存在与否从不构成 style identity 或 operation owner 证据。

## 风格身份与资产解析

解析器只是一份身份、令牌与指导的 package oracle／书面协议：测试中的 `resolve_style_case(case)` 用它验证包内路径、身份和 fallback 契约，但它不是运行时安全实现，也不能替代宿主对真实文件系统的 no-follow／`lstat` 检查。运行时必须从受信任的 Skill 根解析，不能从请求文本、目录猜测或旧 SVG 反推风格。风格资产不拥有生成正文；每次编译只读取规范的 `generation-prompt-template.md`。

### 固定解析顺序

1. 先验证 `run.json.manuscript_review.state == manuscript_approved`，并确认当前 storyboard、theme 快照有效。
2. 从 `theme.json` 读取唯一 `selected_style_id`。
3. 定位 `assets/styles/registry.json`：
   - 只有 no-follow／`lstat` 明确返回不存在时才进入完整 fallback；
   - 任一路径组件或叶节点是 symlink、junction 或 reparse point 时返回 `registry_path_unsafe`；
   - 目标不是普通文件时返回 `registry_target_invalid`；不可读或非 UTF-8 返回 `registry_unreadable`；JSON 无效返回 `registry_malformed`；schema 非 1 返回 `registry_schema_unsupported`；
   - registry 中 style ID 和 display name 必须唯一，否则返回 `registry_duplicate_style`；
   - 在处理所选条目前，按 registry 数组顺序验证每个 `style_pack` 的 entrypoint 精确等于 `<entry-id>/manifest.json`，其 exact pack root 必须是 `assets/styles/<entry-id>/` 的直接子目录，所有 pack roots 必须互不相同且互不嵌套；失败统一返回 `entrypoint_path_unsafe`。这一步也覆盖未选中的 pack。
4. registry 存在时按 `selected_style_id` 精确查找唯一条目；不存在返回 `style_not_registered`，`kind` 不是 `legacy_seed` 或 `style_pack` 返回 `style_kind_invalid`。
5. selected `entrypoint` 缺失返回 `entrypoint_missing`；路径为空、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越或 no-follow target link/symlink/junction/reparse 返回 `entrypoint_path_unsafe`；目标缺失、目录或特殊文件返回 `entrypoint_target_invalid`；不可读或非 UTF-8 返回 `entrypoint_unreadable`。
6. `legacy_seed`：`entrypoint` 相对 `assets/styles/` 解析，规范化后仍必须位于 styles 根内，且不得位于任一已注册 style-pack 子目录；seed JSON 格式或结构错误返回 `legacy_entrypoint_malformed`，seed `name` 与 selected ID 不同返回 `legacy_identity_mismatch`。
7. `style_pack`：entrypoint 打开前再次确认所有组件和叶节点非 no-follow target link/symlink/junction/reparse，且 manifest 位于 exact pack root 内。manifest JSON 无效返回 `manifest_malformed`，schema 非 1 返回 `manifest_schema_unsupported`，`id`、`kind`、`display_name` 与 registry／selected 不一致返回 `manifest_identity_mismatch`，`version` 未 fullmatch `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$` 返回 `manifest_version_invalid`。
8. style-pack 只要求 `files.tokens` 与 `files.guidance`；字段缺失返回 `style_asset_field_missing`。二者都相对 exact pack root 解析，路径越界或 no-follow target link/symlink/junction/reparse 返回 `style_asset_path_unsafe`，目标缺失、目录或特殊文件返回 `style_asset_target_invalid`，不可读或非 UTF-8 返回 `style_asset_unreadable`。tokens JSON 无效返回 `style_asset_malformed`，tokens schema 非 1 返回 `style_asset_schema_unsupported`；guidance 不解析为 JSON。二者规范路径记录在 `theme.json`，身份握手时必须与当前 manifest 一致。
9. schema-v1 registry／manifest 的其他字段按向前兼容规则忽略。历史完整模板文件可留在磁盘，但 resolver 不得查找、派生、读取、验证或哈希，也不得把其路径或字节加入 provenance 或 snapshot identity。
10. 在编译规范正文前完成身份握手：`theme.json` 的 selected style ID、display name、kind、manifest version 必须与当前 registry／manifest 一致；registry-backed legacy 的 manifest version 必须是字符串 `none`；fallback 使用下方权威表并同时匹配 seed `name`。theme 内部矛盾或多个持久 owner 声明不同 style 时返回 `prompt_snapshot_conflict`。theme 一致但安装升级导致当前 display name 或 manifest version 改变时，这是 ordinary stale，按现有 theme 失效规则返回 `theme` 并重建，不写 style blocker。
11. 仅从 `generation-prompt-template.md` 在内存编译正文并完成本文件全部确定性 preflight；成功后才创建 `compiling` transaction，再持久化并复读 `.ppt-pilot/generation-prompts/<slide-id>.md`，提交 `compiled` 后才能启动 fresh independent generator。

### 稳定 reason traversal

所有风格身份或资产解析 blocker 使用 `state: style_assets_unavailable`，并按下面 traversal 的第一个失败项返回唯一 reason。枚举文本包括：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`entrypoint_unreadable`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`style_asset_malformed`、`style_asset_schema_unsupported`、`prompt_snapshot_conflict`。

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
| 5 | selected entrypoint 不可读或非 UTF-8 | `entrypoint_unreadable` |
| 6 | legacy JSON 无效／结构不完整 | `legacy_entrypoint_malformed` |
| 6 | legacy `name` 与 selected ID 不同 | `legacy_identity_mismatch` |
| 7 | manifest JSON／schema／identity／version 无效 | 对应 `manifest_*` reason |
| 8 | selected pack 的 `files.tokens` 或 `files.guidance` 字段缺失 | `style_asset_field_missing` |
| 8 | 上述资产路径越界／no-follow target | `style_asset_path_unsafe` |
| 8 | 上述资产目标缺失、目录或特殊文件 | `style_asset_target_invalid` |
| 8 | 上述资产不可读或非 UTF-8 | `style_asset_unreadable` |
| 8 | tokens JSON 无效 | `style_asset_malformed` |
| 8 | tokens schema 非 1 | `style_asset_schema_unsupported` |
| 10 | persisted provenance／snapshot 无法唯一解释 | `prompt_snapshot_conflict` |

同一状态有多个缺陷时严格按顺序与 registry 数组顺序选择一个 reason：未选 pack root 错误先于 selected assets；selected tokens 错误先于 guidance 错误。

### 缺 registry fallback

fallback 只在 no-follow／`lstat` 确认 `assets/styles/registry.json` 不存在时探测。必须先验证下列三份 seed JSON 的结构与 `name` 身份；三份 seed 全部有效后，才允许三个 legacy ID 解析到对应 entrypoint。任一 seed 缺失、不可读、格式错误或身份不符，都统一返回 `registry_missing`；selected ID 是未知值或只存在于 registry-backed style-pack 时，也返回 `registry_missing`，不得扫描目录发现 style pack。磁盘上的其他历史文件不参与 fallback。

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | entrypoint |
|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` |


### 修订投影验证，不重复物化

编译输入按 [页面编译路径契约](visual-brief-and-generation.md) 从权威 history 完成 applicability、scope、ID、history mirror 与 `supersedes` 验证，确定 canonical active projection。compiler 不重新选择修订、不重排 ID，也不再次覆盖字段；它只执行以下一致性验证：

1. `applied_visual_revision_ids` 必须是无重复、按 `visual-revision-N` 数值升序的完整源列表，每个 ID 对应权威 history 中 `kind: visual_revision`、`status: applied` 的同一记录。
2. 重新验证每条 `<earlier-id>:<normalized_changes-field>` edge，按同一规范算法推导 deterministic active projection；缺失、自身／未来目标、重复 edge、字段不存在或 mirror 冲突均返回 `prompt_snapshot_conflict`。
3. generation prompt provenance 只保留 revision IDs；`[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]` 只包含最终有效字段。raw `answer`、recommendation、clarification、未归一化 history 对象和 raw JSON 一律排除。
4. compiler 的替换域固定为 `[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]`，不得增加修订专用的第三片段。无修订时 `applied_visual_revision_ids` 为 `[]`。

### 编译上下文与精确 preflight 顺序

首次生成和 `recompose` 的编译器必须先完成全部内存工作，随后才能产生任何 durable side effect：

1. 读取当前批准 outline、storyboard、theme 与权威 revisions；不写文件或状态。
2. 在内存组装 canonical narrative bullets（叙事要点+素材+事实底线）与 style baseline（软风格基线）。后者已包含 palette 角色、字体栈、间距节奏与禁止母题。
3. 在内存验证 outline/storyboard/theme snapshots 相等；素材事实底线（数字/单位/限定词/因果/来源映射）与故事板一致；narrative bullets 与 outline 一致；theme identity、64 px safe area、字号下限、`path+A` 与 Office-safe allowlist 完整。
4. 从 repository `references/generation-prompt-template.md` 读取规范 bytes，在内存恰好进行两个 whole-line marker 替换：`[[CANONICAL_NARRATIVE_BULLETS]]` 与 `[[STYLE_BASELINE]]`。
5. 验证模板与 compiled body 的 canonical byte derivation、自包含性、无外部文件指令、无未解析 marker、无 raw revision material，并计算 template/body/compiled prompt/composite snapshot hashes。
6. 只有步骤 1–5 全部成功后，才原子创建 `visual_generation_transaction.state: compiling`；随后写 `.ppt-pilot/generation-prompts/<slide-id>.md`，关闭、复读、核对 hash，再原子提交 `compiled`。
7. 从 `compiled` 原子进入 `generating` 后，才向恰好一个 fresh generator 派发 durable prompt；之后依次处理 candidate 写入／hash、fact-source 与 SVG/visual QA、validated 和 promotion。

确定性 preflight 失败必须产生零 transaction 写入、零 prompt 写入、零 generator 调用和零 SVG 写入。缺陷分类为 outline／storyboard／theme defect 并返回对应权威 owner；只有规范模板、规范字节或无法唯一解释的 snapshot/provenance 自身失败才写 canonical `visual_generation_blocker`。preflight 包括但不限于以下关系门禁：

- **事实底线与叙事相等**：素材中的数字、单位、期间、限定词、因果、来源映射与故事板一致；canonical narrative bullets 与 outline 的叙事要点一致；不得靠改写规避差异。
- **风格基线闭合**：palette 是最终颜色值；type/spacing/shape/output 无 token 名或待选项；标题 ≥40 px、正文 ≥20 px、脚注 ≥14 px；所有 region 位于 64 px safe area 并遵循 24 px rhythm。
- **规范编译**：模板源路径唯一；两个 replacement bytes 经过注入／Setext／路径／外部输入防护；compiled bytes 由 repository template 加这两个 replacement 唯一派生。

### `visual_generation_blocker` 生命周期

风格身份／资产解析失败时写入 `state: style_assets_unavailable`；规范模板读取、编译或 pre-dispatch gate 失败时写入 `state: generation_prompt_unavailable`。两类情况都必须以单次原子 `run.json` 替换写入 `visual_generation_blocker`，字段和 reason 集合遵循 [artifact-contract.md](artifact-contract.md)。写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，受影响 `slide_id` 必须继续留在 `dirty_slides`。阻断期间不得启动 fresh generator、不得创建／覆盖 SVG、不得降级为 patch、不得改用其他风格或 stale cached generation prompt。

`resource` 只允许保存已经通过 containment 和 no-follow 检查的 Skill 相对路径：风格资产状态使用 `assets/styles/...`，规范模板状态使用 `references/generation-prompt-template.md`。路径安全前失败、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 越界、link／junction／reparse 或任何工作区／机密路径，都写 `none`。

恢复时的全局顺序固定为 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > visual_generation_transaction > stage scan`。前四类 durable control state 均不存在或已完成前不得扫描普通阶段。只要前序 owner 存在，就不得解析新页面、编译 generation prompt 或启动 generator。已有 blocker 与当前目标为同一 slide 时，重新验证同一资源与快照并幂等刷新；另一 slide 已有 active blocker 时必须先处理原 blocker。仍失败时 transaction writes、prompt writes、generator calls 与 SVG writes 都保持 0。

canonical blocker 必须在 preflight 已失败、且没有为本次尝试创建 transaction 或 prompt 后独立写入；blocker 与同一尝试的 `compiling` transaction 不得共存。历史 crash 若留下旧协议的 prompt／`compiling`／blocker 组合，只能把 prompt 当作不可信派生产物：保留 previous final，清理或隔离 orphan candidate，重新从步骤 1 执行无副作用 preflight；不得用旧 prompt 直接补提交 `compiled`。

### `visual_generation_transaction` 生成边界

首次生成与 `recompose` 先在内存完成编译输入验证、恰好两个规范替换、compiled bytes 验证和全部 hash 计算；只有 preflight 成功后才原子创建 `visual_generation_transaction.state: compiling`。`transaction_id == prompt_snapshot_id`，transaction 内部 `prompt_path` 为 `generation-prompts/<slide-id>.md`，明确相对于 `.ppt-pilot/`；其拥有的外部文件是 `.ppt-pilot/generation-prompts/<slide-id>.md`。候选为 deterministic `slides/.candidates/<slide-id>-<64hex>.svg`，final 为 `slides/<slide-id>.svg`。创建 transaction 后以同目录 temp file + rename 原子写 prompt，关闭、复读、hash 匹配才原子提交 `compiled`。fresh generator 只在 transaction 已从 `compiled` 原子进入 `generating` 后启动；generator output 先作为 untrusted text 提取单个 fenced XML，再写 deterministic candidate path。`candidate_sha256` 只在候选写入、关闭并复读后提交；`generating` crash 留下的 orphan candidate 必须 delete/isolate，never adopted。

prompt 持久化、复读或 hash 验证失败必须原子记录 `failure_reason: prompt_write_failed` 并走 `compiling -> failed`；此时 generator calls、candidate writes 与 SVG writes 均为 0。显式 resume 时，若 authoritative inputs、template/body bytes 与 snapshots unchanged，则保留同一 transaction identity，原子 `failed -> compiling`，隔离／删除 orphan temp 后重新执行 temp+rename、复读与 hash 验证，再提交 `compiled`；若任一 authoritative input changed，则保留 failed audit，以新的 `compiling` transaction 替换，绝不在旧 transaction 内继续。

transport 和候选写入失败 reason（`generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch`）只能由显式 resume 消费为同一 transaction 的 `failed -> generating`，并使用 `generation_attempt + 1`；每次宿主调用最多 generator 1 次。SVG／内容／视觉 QA 失败（`svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed`）先持久化 defect，再 patch 或 new deterministic fallback compiling transaction。promotion／state conflict（`final_promotion_conflict`、`transaction_state_conflict`）持久化 production `blocker`，保留 previous final SVG 和 failed transaction；用户解决后 unchanged valid candidate 走 `failed -> validated` promotion retry，authoritative inputs changed 走 failed transaction -> new compiling transaction。No arbitrary delete/cancel。


### Generation prompt golden layout, byte grammar, hash domains, and stale semantics

本节收敛为单一权威文件：完整定义见 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)（generation prompt byte grammar 与 byte contract 的全部 11 条规则）。该文件对本文件同等具有约束力；编译、校验或恢复前必须完整阅读。
## 最终 Prompt 正文模板

新运行的 `.ppt-pilot/generation-prompts/<slide-id>.md` 中 `## Compiled Prompt` 必须由 [generation-prompt-template.md](generation-prompt-template.md) 的 repository bytes 唯一派生。compiler 只能进行恰好两个 whole-line replacement：用 canonical narrative bullets（叙事+素材）替换 `[[CANONICAL_NARRATIVE_BULLETS]]`，用软风格基线 bytes 替换 `[[STYLE_BASELINE]]`；其余模板字节不得改动，不得加入第三 fragment。完整 byte grammar 与 hash domain 见 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)。

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
