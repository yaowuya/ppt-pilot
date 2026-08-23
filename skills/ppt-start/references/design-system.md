# 设计系统契约

## 进入条件

只有顶层 `manuscript_approved` 检查点已通过，并且 `run.json.manuscript_review.state` 精确保持为 `manuscript_approved` 时，视觉工作才能开始。工作推进时，顶层 `stage` 依次变为 `theme`、`anchor` 和 `production`；嵌套审查状态是持续授权护栏。选择风格前必须读取已批准的故事板和文稿审查历史；视觉样式不得改变或掩盖已批准主张。主题与锚点交互遵循[用户交互与确认协议](interaction-protocol.md)。

## 主题选择与风格解析

新安装先读取 `assets/styles/registry.json` 发现可选风格；缺 registry 时只允许下方完整 fallback 表中的三个 legacy seed。用户给出稳定 ID 或唯一显示名时可直接选择；未明确选择时仍按 guided／auto 规则决定，不得因新增风格包改变默认行为。根据主题、受众、品牌／风格约束和内容密度选择，不得只按主题关键词机械轮换。用户提供的品牌颜色可以覆盖 seed 或 style pack，但必须先检查对比度并记录最终值。

风格解析是 package oracle 契约，不是运行时安全实现。主题阶段和生成阶段必须使用同一 traversal、同一 reason 词表与同一 no-follow ownership 规则；不得在两个文档中各自发明条件。宿主仍必须对真实文件系统执行 no-follow／`lstat`、普通文件、UTF-8 和 JSON 检查。

### registry 与 pack root

- `assets/styles/registry.json` 只有在 no-follow／`lstat` 明确不存在时才进入 fallback；link、symlink、junction、reparse point、目录、特殊文件、不可读、非 UTF-8、JSON 无效或 schema 非 1 都是 blocker，不当作 missing。
- registry 的 style ID 与 display name 必须唯一；否则返回 `registry_duplicate_style`。
- 任何 `style_pack` 的 entrypoint 必须精确等于 `<entry-id>/manifest.json`；exact pack root 必须是 `assets/styles/<entry-id>/` 的直接子目录，所有 pack roots 互不相同且互不嵌套。这个 registry-wide 检查按 registry 数组顺序执行，也覆盖未选 pack，失败返回 `entrypoint_path_unsafe`。
- 路径拒绝范围固定：空值、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越、no-follow target 集合 link/symlink/junction/reparse。no-follow target 在 registry/entrypoint/asset/prompt 中统一映射到对应 *_path_unsafe；目录和特殊文件仍是 target invalid。

### legacy seed 与 style pack ownership

- `legacy_seed` 的 `entrypoint` 和 `redesign_prompt` 都相对 `assets/styles/` 根解析，规范化后仍必须在该根内，且不能位于任一注册 style-pack 子目录。seed JSON 必须是既有 seed 结构且 `name == selected_style_id`；否则分别返回 `legacy_entrypoint_malformed` 或 `legacy_identity_mismatch`。
- registry-backed legacy 只有三个内置 legacy ID 的旧 v1 条目缺 `redesign_prompt` 时，始终从 entrypoint 派生 `<entrypoint-stem>.redesign.md`；派生 prompt 缺失返回 `prompt_file_missing`。其他 legacy 缺 prompt 字段返回 `prompt_field_missing`。
- `style_pack` manifest 必须位于 exact pack root 内，`schema_version == 1`，`id`、`kind`、`display_name` 与 registry／selected 一致，`version` 必须 fullmatch `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`；失败映射到 `manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch` 或 `manifest_version_invalid`。
- `files.tokens`、`files.guidance`、`files.redesign_prompt` 都相对 exact pack root 解析，不得指向 legacy 文件、styles 根文件或兄弟 pack。tokens／guidance 的路径 ownership 与 containment 使用生成解析同一规则：字段缺失返回 `style_asset_field_missing`，路径越界或 no-follow target 返回 `style_asset_path_unsafe`，目标缺失、目录或特殊文件返回 `style_asset_target_invalid`，不可读返回 `style_asset_unreadable`。theme.json 必须记录已验证 tokens／guidance 规范路径，后续身份握手要求这些记录与当前 manifest 一致。

### 身份握手、ordinary stale 与 blocker

`theme.json` 与 visual brief 必须记录并核对 selected style ID、display name、kind、manifest version。theme.json 与每份 visual-briefs/<slide-id>.md 必须包含完全相同的四个 schema-v1 identity 字段：`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`。style-pack 的持久值还必须与当前 registry／manifest 精确一致；registry-backed legacy 的 version 必须是字符串 `none`；fallback 使用下方 fallback identity table 并同时匹配 seed `name`。missing fields 只能从 registry／manifest／fallback identity table 派生后重建；不得从 SVG、目录、请求文案或用户措辞推断。brief 与 theme 彼此冲突、legacy version 非 `none`、或多个 owner 声明不同 style 时，返回 `prompt_snapshot_conflict` 并写 `style_prompt_unavailable` blocker。brief 与 theme 一致但安装升级导致当前 registry display name 或 manifest version 改变时，属于 ordinary stale：按现有 theme 失效规则返回 `theme`，重建 theme 和受影响 visual briefs，不写 blocker。

### 缺 registry fallback identity table

fallback 只在 registry path no-follow 缺失时探测，并且必须验证三 seed identity 与三 companion prompt contract 后才允许 legacy。任一 seed 或 companion 缺失、不可读、格式错误或身份不符，都统一返回 `registry_missing`；selected ID 不在表内也返回 `registry_missing`，不得扫描未知目录或发现 style pack。

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | entrypoint | companion prompt |
|---|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` | `minimal-business.redesign.md` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` | `tech-dark.redesign.md` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` | `bold-editorial.redesign.md` |

### 稳定 reason traversal

所有 prompt 解析／编译失败使用 `state: style_prompt_unavailable`，按 traversal 的第一个失败项返回唯一 reason：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`prompt_field_missing`、`prompt_path_unsafe`、`prompt_file_missing`、`prompt_target_invalid`、`prompt_unreadable`、`prompt_template_invalid`、`prompt_snapshot_conflict`。

Traversal 顺序固定为：registry target 状态；registry duplicate；registry-wide pack-root shape；selected style lookup/kind；selected entrypoint 字段、路径、target；legacy seed JSON/identity 或 style-pack manifest JSON/schema/identity/version；style-pack tokens/guidance field/path/target/readability；prompt field/path/target/readability/template（含 `STYLE_ID == selected_style_id`）；persisted provenance/snapshot。多缺陷时严格按此顺序与 registry 数组顺序选择：未选 pack root 错误先于 selected prompt 错误，selected tokens/guidance 错误先于 prompt 错误。

风格包不得包含单页成品示例、参考构图或固定区域图；Office-safe SVG 兼容性由生成与 QA 契约验证，不得从成品示例或既有 SVG 反推构图。

### 条件式主题问题

已有明确品牌规范、已确认风格或工作区偏好档案已记录品牌方向时直接复用，不重复询问。`guided` 只有在缺少品牌／风格信息且多个视觉方向会实质改变使用场景、语气或可读性时，才提出一个条件式主题问题，并推荐最适合内容密度与受众的种子。`auto` 使用安全的内置种子并记录选择理由；品牌权限不清或没有安全默认值时仍须询问。

`theme.json` 记录所选种子、最终颜色、字体、间距、形状令牌、语言和已批准覆盖项。不得包含远程 URL 或机器绝对路径。生成或重建该文件时，必须从 `run.json.interaction_history` 恢复 `artifact_owner: theme.json` 的阶段产物镜像到 `user_revision_notes`；不得把 `theme.json` 当作锚点修订记录的唯一权威，也不得因主题失效覆盖或丢失权威交互历史。

主题阶段不能直接从故事板生成 SVG。先把当前有效主题、布局选择和权威视觉修订历史归并到逐页 `visual-briefs/<slide-id>.md`，再由锚点或生产阶段消费。每页必须明确唯一焦点、第一至第三阅读位置、主次面积或替代层级编码、完整字体阶梯、语义色和禁止母题；具体字段与冲突处理遵循[逐页视觉 brief 与生成契约](visual-brief-and-generation.md)。

主题归并使用固定优先级：

```text
不可覆盖内容／证据／兼容性规则 > seed defaults > latest deck theme/brand decision > latest scoped slide decision > local patch defect
```

每条品牌／主题或页面决定来自 `run.json.interaction_history` 的已应用记录。后续规则替换同字段时必须记录 `supersedes`；废弃规则留在历史中，但不得进入当前主题、active contract 或 visual brief。`affected_scope: deck` 的最新决定写入 `theme.json.user_revision_notes`，页面决定写入对应 `visual-briefs/<slide-id>.md`。同字段冲突而替换关系或作用域不明确时停止，不得混用相互矛盾的令牌或从 SVG 反推主题。

## 色彩层级

主导色约占 60%–70% 的视觉权重，另配一到两个辅助色和一个鲜明强调色。背景与表面色承担功能；强调色只用于最高价值的比较、行动或例外，不用于一般装饰。

正文／脚注文本的对比度至少为 4.5:1；大号文本和关键图形边界至少为 3:1。用户覆盖色与种子冲突时，应修改令牌，而不是给文字添加描边或阴影。

禁止把通用强调色条、装饰边条、标题下划线或渐变作为视觉母题。禁止远程字体及字体下载依赖。优先使用留白、层级、分组、图标和数据关系。

## 字体

使用所选种子记录的系统字体栈，至少满足：

- 标题：40 px；
- 正文：20 px；
- 脚注／来源：14 px。

密度允许时使用更大字号。标题必须是结论，可有意换成两行。正文默认左对齐；只有短标签具有明确语义理由时才居中。

SVG 没有可靠且 Office-safe 的自动段落换行。每行必须使用 `<tspan>` 显式拆分，并为各行设置 `x` 与 `dy`。文字保持为文字，不转换为轮廓路径。内容过多时应拆页，不能把字号降到下限以下。

## 网格与间距

画布为 1280×720，外部安全边距为 64 px。所有非背景元素都必须位于 `x=64..1216`、`y=64..656` 内，包括标题、来源／页脚和页码；放置文字时必须预留字形上升部与下降部。标准间距为 24 px，内边距和章节节奏使用一致倍数。标题、内容、来源和重复卡片必须对齐到共同网格。

下方安全区域为来源说明预留，但来源不得与正文碰撞。相似元素默认使用相同尺寸和间距，除非差异本身编码了数据。

## 形状与视觉语言

统一使用所选种子的圆角和描边宽度。优先使用平面填充、实线描边、清晰轮廓和简单内联路径。图标辅助含义，但不能替代关键信息文字。避免依赖浏览器 filter、mask、图像填充或在 Office 中可能表现不一致的透明度技巧。

每页必须表达一个有目的的视觉关系：证据、比较、顺序、层级、分组或强调。只有装饰形状不算满足视觉意图。

## 锚点批准

写完 `theme.json` 后，根据已批准文稿生成两页锚点：

1. 封面，用于确立语气和字体；
2. 密度最高或技术上最困难的内容页，用于证明设计系统能处理真实约束。

`guided` 模式在两页锚点完成并通过硬检查后，必须提供真实渲染证据并提出一个锚点批准问题；收到明确回答前保持 `stage: anchor`，不得进入正式生产。渲染不可用时记录 `visual_qa: not_rendered` 并披露限制，不得把 XML 或源文件检查描述成视觉批准。`auto` 模式执行相同的结构、可读性和 SVG 检查，但不进行可选批准。改变文案或主张的锚点修改会使文稿批准失效；纯视觉修改只使依赖主题的视觉产物失效。
