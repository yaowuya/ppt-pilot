# 设计系统契约

## 进入条件

只有顶层 `manuscript_approved` 检查点已通过，并且 `run.json.manuscript_review.state` 精确保持为 `manuscript_approved` 时，视觉工作才能开始。工作推进时，顶层 `stage` 依次变为 `theme`、`anchor` 和 `production`；嵌套审查状态是持续授权护栏。选择风格前必须读取已批准的故事板和文稿审查历史；视觉样式不得改变或掩盖已批准主张。主题与锚点交互遵循[用户交互与确认协议](interaction-protocol.md)。

## 主题选择与风格解析

新安装先读取 `assets/styles/registry.json` 发现可选风格；缺 registry 时，下方 identity-recovery 表只能为旧运行恢复只读身份，不能用于主题选择或页面生成，任何首次生成／`recompose` 仍以 `registry_missing` fail closed。用户给出稳定 ID 或唯一显示名时可直接选择；未明确选择时仍按 guided／auto 规则决定，不得因新增风格包改变默认行为。根据主题、受众、品牌／风格约束和内容密度选择，不得只按主题关键词机械轮换。用户提供的品牌颜色、字体、间距或形状值若与所选包不同，不能作为 `theme.json` 的运行时覆盖层；必须先完成下方派生风格包闭环。

### 品牌覆盖的派生风格包闭环

`brand_override_requires_derived_style_pack` 是硬门禁。任何品牌／主题覆盖只要改变已选 pack 的颜色、字体、间距、形状语言、构图规则或禁止母题，就必须在最终确定 theme 和首次生成前完成以下步骤：

1. 以当前已验证 pack 与规范化覆盖值为 authoring 输入，调用 `ppt-style-extract` 生成新的 immutable style ID；ID 必须与原 ID 不同并绑定输入摘要，已发布 ID 不得原地改写。
2. 派生包必须把最终值同时静态物化到 `tokens.json`、`STYLE.md` 和 style-owned `prompt.md`，再通过完整 pack verifier；失败时不得写 `theme.json`、generation prompt 或 transaction。
3. writer 先发布不可变 pack 目录，再在 registry 锁内重新读取并以 registry pointer-last 注册；并发冲突必须重读合并，不能 blind replace。崩溃后未注册的完整 pack 只是安全 orphan，同一输入可幂等恢复注册。
4. 注册后从 `assets/styles/registry.json` 重新执行完整 resolver traversal，并把 `theme.json.selected_style_id`、display name、kind、manifest version 以及最终颜色／字体等值全部设置为该派生包的已验证身份和值。
5. 只有上述身份握手成功后才可进入 anchor／production。首次生成的 `user_page_request` 仍为 `none (initial generation)`；覆盖值已经存在于派生 style-owned prompt 的固定字节中，不创建第二个运行时替换域。

若宿主不能调用 `ppt-style-extract`、无法安全注册新包或覆盖值无法通过对比度／字体安全校验，必须在首次生成前停止并持久化一个 `pending_interaction`，让用户选择保留原包或终止；不得静默使用旧 pack 生成后再依赖 QA 猜测修正。

风格解析是身份、令牌、指导与模板的 package oracle 契约，不是运行时安全实现。主题阶段和生成阶段必须使用同一 traversal、同一 reason 词表与同一 no-follow ownership 规则；不得在两个文档中各自发明条件。宿主仍必须对真实文件系统执行 no-follow／`lstat`、普通文件、UTF-8 和 JSON 检查。每个可选择 style pack 必须通过 manifest 的 `files.prompt_template` 拥有完整可执行生成正文；该字段未声明即以 `style_asset_field_missing` fail closed。仓库 `references/generation-prompt-template.md` 只作建包 authoring seed，运行时不得读取或回退；风格自有模板必须满足单 whole-line `{{NARRATIVE}}` 契约。

### registry 与 pack root

- `assets/styles/registry.json` 只有在 no-follow／`lstat` 明确不存在时才进入只读 identity recovery；link、symlink、junction、reparse point、目录、特殊文件、不可读、非 UTF-8、JSON 无效或 schema 非 1 都是 blocker，不当作 missing。
- registry 的 style ID 与 display name 必须唯一；否则返回 `registry_duplicate_style`。
- 任何 `style_pack` 的 entrypoint 必须精确等于 `<entry-id>/manifest.json`；exact pack root 必须是 `assets/styles/<entry-id>/` 的直接子目录，所有 pack roots 互不相同且互不嵌套。这个 registry-wide 检查按 registry 数组顺序执行，也覆盖未选 pack，失败返回 `entrypoint_path_unsafe`。
- 路径拒绝范围固定：空值、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越、no-follow target 集合 link/symlink/junction/reparse。no-follow target 在 registry、entrypoint 或 style asset 中统一映射到对应 `*_path_unsafe`；目录和特殊文件仍是 target invalid，entrypoint 不可读或非 UTF-8 返回 `entrypoint_unreadable`。

### legacy seed 与 style pack ownership

- `legacy_seed` 的 `entrypoint` 相对 `assets/styles/` 根解析，规范化后仍必须在该根内，且不能位于任一注册 style-pack 子目录。entrypoint 不可读或非 UTF-8 返回 `entrypoint_unreadable`；seed JSON 必须是既有 seed 结构且 `name == selected_style_id`，否则分别返回 `legacy_entrypoint_malformed` 或 `legacy_identity_mismatch`。
- `style_pack` manifest 必须位于 exact pack root 内，`schema_version == 1`，`id`、`kind`、`display_name` 与 registry／selected 一致，`version` 必须 fullmatch `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`；失败映射到 `manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch` 或 `manifest_version_invalid`。
- schema-v1 manifest 的 `files` 必须恰好声明 `tokens.json`、`STYLE.md` 与 `prompt.md` 三个固定目标，`files.prompt_template` 不是可选字段。三个资产都相对 exact pack root 解析，不得指向 legacy 文件、styles 根文件或兄弟 pack；字段缺失返回 `style_asset_field_missing`，其路径、target、可读性与 tokens schema 失败沿用 `style_asset_*` reason。traversal 必须先验证 tokens、再验证 guidance、最后验证 prompt；多缺陷时不能因 prompt 先被触碰而掩盖 tokens blocker。generation preflight 对 prompt 执行 containment／no-follow、普通文件、UTF-8、canonical hard shell、单 whole-line `{{NARRATIVE}}` 与 tokens 精确绑定校验；失败映射到 `prompt_path_unsafe`、`prompt_file_missing`／`prompt_target_invalid`、`prompt_unreadable` 或 `prompt_template_invalid`。`theme.json` 必须记录已验证 tokens／guidance 规范路径；generation provenance 记录 resolved template 路径与 normalized bytes hash，后续身份握手要求这些记录与当前 manifest 一致。
- registry 或 manifest 中的其他 schema-v1 字段按向前兼容规则忽略。未被 `files.prompt_template` 声明的历史 `REDESIGN.md`／`*.redesign.md` 可以保留在磁盘，但解析器不得查找、派生、读取、验证或哈希这些文件，也不得把其路径或字节写入生成 provenance。

### 身份握手、ordinary stale 与 blocker

`theme.json` 必须记录并核对 selected style ID、display name、kind、manifest version。四个 schema-v1 identity 字段（`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`）由 `theme.json` 权威拥有，并原样投影到 canonical prompt snapshot payload 与每页 generation owner；权威定义见[产物契约 Task 6](artifact-contract.md)。style-pack 的持久值还必须与当前 registry／manifest 精确一致；registry-backed legacy 的 version 必须是字符串 `none`；registry 缺失时只能使用下方 identity-recovery table 恢复旧运行身份并同时匹配 seed `name`，不能据此编译或生成。missing fields 只能从 registry／manifest／identity-recovery table 派生后重建；不得从 SVG、目录、请求文案或用户措辞推断。prompt provenance 与 theme 冲突、legacy version 非 `none`、或多个 owner 声明不同 style 时，返回 `prompt_snapshot_conflict` 并写 `generation_prompt_unavailable` blocker。持久身份与 theme 一致但安装升级导致当前 registry display name、manifest version、声明的 prompt template 路径或模板 bytes 改变时，属于 ordinary stale：按现有 theme 失效规则返回 `theme`，重建 theme 和受影响 generation prompts，不写 blocker。只有未声明的历史 `REDESIGN.md`／`*.redesign.md` 的存在、路径或字节变化永远不是 identity、ordinary stale 或 snapshot 输入。

### 缺 registry 的只读 identity-recovery table

该表只在 registry path 经 no-follow 确认缺失时，为旧运行的只读身份恢复探测三份 seed JSON，并验证其结构与 `name`。它不解析 manifest、tokens、guidance 或 prompt，不授权首次生成／`recompose`；一旦旧运行需要生成页面，仍以 `registry_missing` fail closed，等待完整 registry/style pack 修复。任一 seed 缺失、不可读、格式错误、身份不符或 selected ID 不在表内，也统一返回 `registry_missing`；不得扫描未知目录或发现 style pack。

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | entrypoint |
|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` |

### 稳定 reason traversal

所有风格身份或资产解析失败使用 `state: style_assets_unavailable`，按 traversal 的第一个失败项返回唯一 reason：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`entrypoint_unreadable`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`style_asset_malformed`、`style_asset_schema_unsupported`。persisted identity／provenance 冲突虽在同一 resolver traversal 中被发现，但唯一返回 `prompt_snapshot_conflict` 并发布 `generation_prompt_unavailable`，不得混入 style-assets blocker reason 集合。只有该 traversal 全部通过后才验证 resolved prompt template；其余 `prompt_*` 失败同样属于 `generation_prompt_unavailable`，reason 集合以 [artifact-contract.md](artifact-contract.md) 为准。

Style-assets traversal 顺序固定为：registry target 状态；registry duplicate；registry-wide pack-root shape；selected style lookup/kind；selected entrypoint 字段、路径、target；legacy seed JSON/identity 或 style-pack manifest JSON/schema/identity/version；style-pack tokens/guidance field/path/target/readability；persisted identity conflict。多缺陷时严格按此顺序与 registry 数组顺序选择：未选 pack root 错误先于 selected assets，selected tokens 先于 guidance。只有该序列无错误后，generation preflight 才验证 resolved prompt template 的 path/target/readability/shape，并按 `generation_prompt_unavailable` 发布最低模板 blocker。

风格包不得包含活跃的单页成品示例、参考构图或固定区域图；Office-safe SVG 兼容性由生成与 QA 契约验证，不得从成品示例或既有 SVG 反推构图。

### 条件式主题问题

已有明确品牌规范、已确认风格或工作区偏好档案已记录品牌方向时直接复用，不重复询问。`guided` 只有在缺少品牌／风格信息且多个视觉方向会实质改变使用场景、语气或可读性时，才提出一个条件式主题问题，并推荐最适合内容密度与受众的种子。`auto` 使用安全的内置种子并记录选择理由；品牌权限不清或没有安全默认值时仍须询问。

`theme.json` 记录所选种子、最终颜色、字体、间距、形状令牌、语言和已批准覆盖项；这些视觉值必须与当前所选且已验证 pack 的 tokens 精确一致。不得包含远程 URL 或机器绝对路径。生成或重建该文件时，必须从 `run.json.interaction_history` 恢复 `artifact_owner: theme.json` 的阶段产物镜像到 `user_revision_notes`；不得把 `theme.json` 当作锚点修订记录的唯一权威，也不得因主题失效覆盖或丢失权威交互历史。

主题阶段解析当前有效主题后，读取软风格基线（色板角色、字体栈、间距节奏、形状语言、构图规则、禁止母题——来源均为所选中风格包 `tokens.json` 的闭合类型 `prompt_baseline`，由 `StyleBaselineCompiler` 确定性投影）。该基线只作为风格数据、QA 输入与 snapshot provenance，不是 generation prompt 的正文替换域；具体视觉生成指令只由已验证、与 tokens 精确绑定的 resolved style-owned template 承载。不再创建逐页中间规格产物。

主题归并使用固定优先级：

```text
不可覆盖内容／证据／兼容性规则 > seed defaults > latest deck theme/brand decision > latest scoped slide decision > local patch defect
```

每条品牌／主题或页面决定来自 `run.json.interaction_history` 的已应用记录。后续规则替换同字段时必须记录 `supersedes`；废弃规则留在历史中，但不得进入当前主题、active contract 或编译输入。`affected_scope: deck` 的最新决定写入 `theme.json.user_revision_notes`，页面决定只投影到对应故事板／theme owner 与 revision provenance；不得直接改写已选 style pack 的 prompt/tokens 或生成运行时第八条 Step-2 行。需要改变风格时必须按 `brand_override_requires_derived_style_pack` 闭环选择或生成并注册一个新 ID 的完整风格包。同字段冲突而替换关系或作用域不明确时停止，不得混用相互矛盾的令牌或从 SVG 反推主题。

## 色彩层级

主导色、辅助色与强调色的具体视觉权重由所选 style 的闭合 tokens 决定。背景与表面色承担功能；强调色只用于最高价值的比较、行动或例外，不用于一般装饰。

关键数字与关键比较必须用强调色或明确标注（对比色、圈注、箭头差值）突出，且每页只保留一个主强调焦点——这是故事板"每页黄金规则"在视觉层的执行细则。强调服务于该页 `visual_intent`，优先把关键比较绘制为带指标、期间、单位和限定词的图表，而不是文字罗列；来源关联只存在于 coordinator 注入的机器元数据，不得成为可见文字。同一页出现多个并列强调时按重要性只保留一个，其余降级为辅助色或普通标注。

风格基线是软参考方向，生成器可在保持整套 deck 一致性的前提下自选布局与视觉表达；关键数字与关键比较的强调规则仍是输出硬契约的一部分。

正文／脚注文本的对比度至少为 4.5:1；大号文本和关键图形边界至少为 3:1。用户覆盖色与种子冲突时，应修改令牌，而不是给文字添加描边或阴影。

禁止把通用强调色条、装饰边条、标题下划线或渐变作为视觉母题。禁止远程字体及字体下载依赖。优先使用留白、层级、分组、图标和数据关系。

## 字体

使用所选种子记录的系统字体栈，至少满足：

- 标题：40 px；
- 正文：20 px；
- 脚注／来源：14 px。

密度允许时使用更大字号。标题必须是结论，可有意换成两行。正文默认左对齐；只有短标签具有明确语义理由时才居中。

SVG 没有可靠且 Office-safe 的自动段落换行。每行必须使用 `<tspan>` 显式拆分，并统一使用绝对 `x`／`y` 定位；禁止 `dy` 相对位移。文字保持为文字，不转换为轮廓路径。内容过多时应拆页，不能把字号降到下限以下。

## 网格与间距

画布为 1280×720，外部安全边距为 64 px。所有非背景元素都必须位于 `x=64..1216`、`y=64..656` 内，包括标题、来源／页脚和页码；放置文字时必须预留字形上升部与下降部。标准间距为 24 px，内边距和章节节奏使用一致倍数。标题、内容、来源和重复卡片必须对齐到共同网格。

来源说明不占用可见区域；当前视觉运行时不支持在页面中自动渲染人类可读 citation、来源名称或 URL。用户明确请求可见引用时，必须在视觉生成前写入 `pending_interaction`，让用户选择继续使用机器 trace 或停止并单独交付来源报告；不得由 generator 或 coordinator 临时拼接可见引用。相似元素默认使用相同尺寸和间距，除非差异本身编码了数据。

## 形状与视觉语言

统一使用所选种子的圆角和描边宽度。优先使用平面填充、实线描边、清晰轮廓和简单内联路径。图标辅助含义，但不能替代关键信息文字。避免依赖浏览器 filter、mask、图像填充或在 Office 中可能表现不一致的透明度技巧。

每页必须表达一个有目的的视觉关系：证据、比较、顺序、层级、分组或强调。只有装饰形状不算满足视觉意图。

## 锚点批准

写完 `theme.json` 后，根据已批准文稿生成两页锚点并写入运行目录 `samples/`：

1. 封面，用于确立语气和字体；
2. 密度最高或技术上最困难的内容页，用于证明设计系统能处理真实约束。

`guided` 模式在两页锚点完成并通过硬检查后，必须提供真实渲染证据并提出一个锚点批准问题；收到明确回答前保持 `stage: anchor`，不得进入正式生产。渲染不可用时记录 `visual_qa: not_rendered` 并披露限制，不得把 XML 或源文件检查描述成视觉批准。`auto` 模式执行相同的结构、可读性和 SVG 检查，但不进行可选批准。改变文案或主张的锚点修改会使文稿批准失效；纯视觉修改只使依赖主题的视觉产物失效。
