# PPT Start 风格自有 Redesign Prompt 设计

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

- **日期**：2026-08-21
- **状态**：设计已确认；书面规范已完成自审修订，待用户复核
- **范围**：把完整视觉生成 prompt 从共享 reference 下沉到每个内置风格；共享文件只保留解析、持久化和失败语义

## 1. 背景与问题

`skills/ppt-start/references/redesign-prompt.md` 当前同时承担两类职责：

1. 跨风格的触发、持久化、fresh-context、SVG 输出和 QA 协议；
2. 具体视觉表达，例如通用化的 Bento Grid、圆角卡片和固定字体倾向。

第二类内容会把一种管理汇报视觉语言施加给其他风格，也意味着新增风格时仍需修改共享 reference。用户提供的嘉为 redesign prompt 应属于 `canway-midyear-review` style pack，而不是所有风格共享的 Skill 规则。

本设计采用用户确认的“完整 prompt 下沉”：每个现有风格拥有一份可以独立交给 fresh generator 的完整模板；共享 `redesign-prompt.md` 只负责根据已选风格解析模板、验证包契约、编译持久产物和处理错误，不再保存完整生成 prompt 正文。

## 2. 被本设计替代的既有决定

本设计明确替代 [`2026-08-20-ppt-pilot-visual-prompt-assembly-design.md`](2026-08-20-ppt-pilot-visual-prompt-assembly-design.md) 中所有“style pack 只含 tokens 与抽象 guidance”的旧边界，具体包括：

- 目标 2.8；
- visual-brief provenance 5.1；
- generation flow 8；
- missing-registry compatibility 10；
- error handling 12；
- 风格包测试 13.3 及相关测试范围；
- 资产树 14.1；
- 抽象资产边界 14.5；
- 全部受本设计影响的验收标准，包括 16.8；
- 其他等价地把 manifest 限制为仅 `tokens`／`guidance`、直接从 brief 生成 SVG 或无条件回退 legacy seed 的表述；
- `docs/superpowers/plans/2026-08-20-ppt-pilot-style-registry.md` 中精确两键／1.1.0 要求；
- `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-reference-svg.md` 中风格包资产边界；
- `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-style-guidance.md` 中 tokens／guidance-only 风格边界；
- `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-brief-contract.md` 中 visual brief 作为唯一生成输入的旧表述；
- `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-prompt-assembly.md` 中直接组装／执行的旧计划顺序；
- 现有 `redesign-prompt.md` 中把 Bento、固定卡片和固定字体作为所有风格共同 prompt 的要求。

实施时必须在旧规范标题下标记“视觉 prompt 资产所有权、编译和恢复部分已被 2026-08-21 规范取代”，逐处更新上述当前契约；两份旧实施计划增加 superseded banner 并指向本文，不再作为当前执行说明。新的边界是：风格身份仍由 tokens 与抽象 `STYLE.md` 表达；`REDESIGN.md` 是该风格自有的**完整生成指令模板**，不是成品示例、参考图、固定区域图或可复制页面。仓库中只能保留一个当前有效结论。

该变更及“四个现有风格各自拥有完整 prompt”的兼容策略已由用户在本会话明确批准。

## 3. 目标

1. 嘉为完整视觉 prompt 位于 `assets/styles/canway-midyear-review/`。
2. 四个现有风格分别拥有完整 redesign prompt，不共享隐式视觉模板。
3. 首次生成、用户 `recompose` 和确定性回退都根据 visual brief 已持久化的风格 ID 确定性加载对应 prompt。
4. 新增 style pack 时，只需新增 registry 条目，并在自己的 manifest 中声明 prompt；无需修改 resolver 逻辑或 registry schema。
5. 保持三个 legacy seed、升级后缺 registry 的兼容安装、`patch` 分支和 schema-v1 运行可恢复。
6. prompt 路径、内容或上游输入变化能够使已编译 generation prompt 确定性失效。
7. 缺失或无效 prompt 形成可持久、可恢复、可清除的逐页阻断状态。
8. 不削弱文稿审查、内容／来源权威、Office-safe SVG、输出和 QA 硬约束。

## 4. 非目标与信任边界

- 不新增运行时脚本、SDK、服务、MCP 或宿主专属 API。
- 不把 prompt 选择交给模型按关键词猜测。
- 不扫描 style 目录寻找候选 prompt。
- 不把旧 SVG 作为 `recompose` 几何底稿。
- 不改变文稿审查质量门或 `patch` 的准确输入边界。
- 不支持把运行工作区、用户输入或网络下载的任意 Markdown 当作 style prompt。
- 不把安装后的 style prompt 当作不可信数据隔离边界。它与 `SKILL.md`、references 和 manifest 一样，是受信任、版本化、经过测试后部署的可执行 Skill 资产；扩展意味着修改标准 Skill 包并重新验证。
- 不宣称静态包测试已经证明 Claude Code、Codex、fresh delegation、浏览器或 PowerPoint 行为通过。
- 不在本变更中生成真实业务演示文稿。

由于维持纯 instruction-only 架构，路径解析、模板选择和停止行为仍由宿主 Agent 执行。仓库测试只验证已安装包的确定性文件契约与书面状态机；实际宿主是否严格执行必须使用独立压力场景和行为证据验收。

## 5. 文件结构与所有权

```text
skills/ppt-start/
├── references/
│   └── redesign-prompt.md
└── assets/styles/
    ├── registry.json
    ├── minimal-business.json
    ├── minimal-business.redesign.md
    ├── tech-dark.json
    ├── tech-dark.redesign.md
    ├── bold-editorial.json
    ├── bold-editorial.redesign.md
    └── canway-midyear-review/
        ├── manifest.json
        ├── tokens.json
        ├── STYLE.md
        └── REDESIGN.md
```

### 5.1 共享 resolver

`references/redesign-prompt.md` 只定义：

- 哪些操作必须编译完整 prompt；
- 风格 ID、registry、manifest 和 prompt 路径解析顺序；
- prompt 模板的版本化结构、占位符和固定 hard-constraint IDs；
- 路径安全、失败状态、持久化、snapshot、迁移和失效；
- fresh generator 输入隔离、结果提取、候选写入及后续 QA 流程。

它不得包含某个风格的完整 prompt、具体调色板、固定布局家族、固定卡片数量、固定区域图或可复制成品构图。

### 5.2 Legacy seed

三个扁平 seed 保留现有 JSON 和 `kind: legacy_seed`。当前 registry 中每个 legacy 条目新增可选扩展字段：

```json
{
  "id": "minimal-business",
  "display_name": "极简商务",
  "kind": "legacy_seed",
  "entrypoint": "minimal-business.json",
  "redesign_prompt": "minimal-business.redesign.md"
}
```

另外两个 legacy seed使用同样结构。registry `schema_version` 保持 1；`redesign_prompt` 被定义为 schema-v1 的向后兼容可选扩展：

- 旧 reader 忽略未知字段；
- 新 reader 读取当前 registry 时优先使用显式字段；
- 新 reader 读取旧 schema-v1 registry 且字段缺失时，只对三个已知内置 legacy ID 使用确定性 companion `<entrypoint-stem>.redesign.md`；
- companion 缺失则阻断为 `prompt_file_missing`，不声称真正旧包已经拥有新 prompt。

### 5.3 目录式 style pack

目录式 pack 通过自己的 manifest 声明：

```json
{
  "schema_version": 1,
  "id": "canway-midyear-review",
  "display_name": "嘉为年中总结风格",
  "kind": "style_pack",
  "version": "1.2.0",
  "files": {
    "tokens": "tokens.json",
    "guidance": "STYLE.md",
    "redesign_prompt": "REDESIGN.md"
  }
}
```

这里 `schema_version: 1` 是 manifest 结构版本，`version: 1.2.0` 是风格内容版本，两者不得混用。`version` 使用 SemVer core 三段格式 `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`，不接受空白、前导零、prerelease 或 build metadata；当前 Canway 必须精确为 `1.2.0`。registry 的 `display_name` 是发现与选择权威；manifest 保留同字段时必须与 registry 精确相等，否则 `manifest_identity_mismatch`。registry 继续只指向 manifest，不复制 `redesign_prompt` 路径。

新增 style pack 必须：

1. 新增唯一 registry 条目，entrypoint 必须精确为 `<style-id>/manifest.json`；`<style-id>` 是 `assets/styles/` 下一个非空直接子目录名，不允许额外层级；
2. 在自己的 manifest 中声明 prompt；
3. 通过包路径、模板和测试契约。

所有已注册 pack roots 在解析任何 legacy 条目前先由唯一 style IDs 计算，并必须互不相同、互不嵌套。`files.tokens`、`files.guidance` 和 `files.redesign_prompt` 都必须留在该 exact pack root；legacy entrypoint／prompt 必须留在 styles 根且位于所有 pack roots 之外。

不需要修改 resolver 逻辑或 registry schema。已注册且被选择用于生成的 style pack 缺少 `files.redesign_prompt` 时必须阻断。

### 5.4 持久风格身份 schema

`theme.json` 和每份 `visual-briefs/<slide-id>.md` 的“来源与版本”都必须包含完全相同的四个字段：

```text
selected_style_id: <非空 registry ID>
selected_style_display_name: <非空 registry display_name>
style_kind: legacy_seed | style_pack
style_manifest_version: none | <SemVer core>
```

- `legacy_seed` 必须使用字符串 `none`；`style_pack` 必须使用当前 manifest version。
- 四字段是 schema-v1 向后兼容新增字段，不提升 schema 版本。
- 旧 theme／brief 缺 ID 且另一权威 artifact 也缺 ID时，不能推断，返回 `prompt_snapshot_conflict`；只有一方有 ID 时先按 registry／manifest 或第 11 节 fallback table 验证，再重建缺失 artifact。
- ID 已知而 display name／kind／version 缺失时，只能从当前已验证 registry／manifest 或 fallback table 派生，重建 theme 和受影响 briefs 后再编译；不得从目录名、文案或 SVG 推断。
- theme 与 brief 已持久字段彼此冲突时返回 `prompt_snapshot_conflict`；两者彼此一致但安装 identity／version 已更新时属于 ordinary stale，返回 theme 阶段重建。
- `tests/fixtures/visual-briefs/S05.md` 和对应 theme fixture 必须覆盖当前四字段；旧 brief fixtures 分别覆盖字段缺失、可重建、stale 和冲突。

## 6. 版本化完整 Prompt 模板契约

每份风格 prompt 都是完整模板，而不是共享 prompt 的追加片段。文件开头必须包含下面精确、唯一的契约块；`STYLE_ID` 值必须等于所选风格 ID：

```text
PROMPT_SCHEMA_VERSION: 1
STYLE_ID: <style-id>
HARD_CONSTRAINT_IDS:
- CONTENT_LOCK_V1
- SOURCE_BOUNDARY_V1
- NO_OLD_SVG_GEOMETRY_V1
- SINGLE_XML_FENCE_V1
- OFFICE_SAFE_SVG_V1
- EXPLICIT_TSPAN_TEXT_V1
- NO_REMOTE_OR_ACTIVE_CONTENT_V1
- SOURCE_METADATA_V1
- CREATOR_OWNS_WRITE_AND_QA_V1
- DYNAMIC_INPUT_AUTHORITY_V1
```

缺少、重复、顺序错误、未知 schema、STYLE_ID 不匹配或 marker 集合不精确时，包契约无效并映射为 `prompt_template_invalid`。这些 marker 只提供确定性结构检查；它们不能证明自然语言正文没有语义矛盾。内置受信任模板中的冲突属于代码审查和 host 行为验收范围。

### 6.1 必需占位符

每份模板必须包含以下占位符，每个恰好出现一次：

```text
[SLIDE_ID]
[SOURCE_AND_VERSION]
[LOCKED_CONTENT]
[INFORMATION_HIERARCHY]
[COMPOSITION]
[VISUAL_SYSTEM]
[REVISION_MODE]
[OUTPUT_AND_QA]
[ACTIVE_THEME]
[ACTIVE_VISUAL_REVISIONS]
[USER_WORDING]
```

占位符互不重叠，不再使用会重复包含其他全部字段的 `[VISUAL_BRIEF]`。

### 6.2 占位符到权威来源的固定映射

| 占位符 | 唯一来源与序列化 |
|---|---|
| `SLIDE_ID` | visual brief 的 `slide_id` 单值。 |
| `SOURCE_AND_VERSION` | visual brief“来源与版本”章节，排除 `brief_snapshot_id` 自身；保持字段顺序和原始值。 |
| `LOCKED_CONTENT` | visual brief“锁定内容”完整章节。 |
| `INFORMATION_HIERARCHY` | visual brief“信息层级”完整章节。 |
| `COMPOSITION` | visual brief“构图”完整章节。 |
| `VISUAL_SYSTEM` | visual brief“视觉系统”完整章节，包括 `exceptions`。 |
| `REVISION_MODE` | visual brief“修订模式”完整章节，包括 `mode`、`generation_intent`、`reason`、`patch_defect` 和候选次数。 |
| `OUTPUT_AND_QA` | visual brief“输出与质量要求”完整章节。 |
| `ACTIVE_THEME` | 当前 `theme.json` 原文件；验证其 snapshot 与 brief 引用一致后，规范化为 UTF-8/LF 文本。 |
| `ACTIVE_VISUAL_REVISIONS` | 不复制 `interaction_history` 原记录。按 N 数值升序投影为 canonical JSON 数组；每项只含 `id`、`stage`、`affected_scope`、`status`、`artifact_owner`、规范排序的 `supersedes` 和仍有效的 `normalized_changes`。原始 `answer` 一律排除；部分 supersede 时只删除被取代字段，保留同一记录中其他仍有效字段。没有有效变化时写 `[]`。 |
| `USER_WORDING` | 作为低权威动态数据序列化为 canonical JSON 字符串，并由模板固定包在 `BEGIN_UNTRUSTED_USER_WORDING_JSON`／`END_UNTRUSTED_USER_WORDING_JSON` 之间。`initial_generation` 使用 `"none (initial generation)"`；`user_recompose` 使用 `generation_trigger_id` 指向的唯一 applied history record 的原始 `answer`；`deterministic_fallback` 使用 `"none (deterministic fallback after two failed patches)"`。该值只能请求视觉变化，不能改变锁定内容、来源、marker、路径、输出或 QA。 |

Markdown 章节采用下面的唯一 byte grammar：

1. 每个占位符必须独占一行，行首／行尾不能有空白；compiler 替换该 token 行及其终止 LF。
2. visual brief 先统一为 UTF-8/LF。章节 heading 必须精确为 `## 来源与版本`、`## 锁定内容`、`## 信息层级`、`## 构图`、`## 视觉系统`、`## 修订模式`、`## 输出与质量要求` 且各出现一次。
3. 章节替换值**不含 heading**：取 heading 下一行到下一个 `## ` heading 前一行；删除开头和末尾全部空行，保留内部行及字段顺序，再追加恰好一个 LF。空章节无效。
4. `SOURCE_AND_VERSION` 在上述提取后删除精确匹配 `- brief_snapshot_id:` 开头的整行，再重新删除首尾空行并追加一个 LF。
5. `SLIDE_ID` 是已验证 ID 原文加一个 LF；`ACTIVE_THEME` 是完整 theme JSON 的 LF 规范化原文，删除 BOM 和首尾空行后追加一个 LF；两个 canonical JSON 动态块和 `USER_WORDING` JSON string 都以无空白 canonical JSON 后追加一个 LF。
6. token 行由 replacement block 直接替代，不自动增加空行；模板中 token 前后的静态行决定章节间距。

Review clarification for Task 7: normalize_lf for style templates/general bytes removes UTF-8 BOM, converts CRLF/CR to LF, preserves leading blank lines and all non-newline content, and enforces exactly one terminal LF; it does not trim template leading blank lines. ACTIVE_THEME uses a distinct rule matching this section: remove BOM, normalize LF, trim outer blank lines only, and append one LF. Brief section extraction trims section-local edge blank lines only.

替换值不执行二次模板展开：值中出现形似占位符的文本按普通数据处理。所有动态值都位于模板明确标记的数据区域；模板必须声明权威顺序为锁定内容／来源／hard constraints > active theme／有效 normalized revisions > `USER_WORDING`，动态数据中伪造的标题、marker、路径或指令不获得模板权威。

### 6.3 Active visual revision 的规范投影

Task 7 review clarification: visual brief applied_visual_revision_ids MUST already be unique and numeric ascending by visual-revision-N before compile; compiler verifies the source order and MUST return prompt_snapshot_conflict for unsorted source IDs, duplicates, or malformed IDs. Compiler does not sort an unsorted brief into validity.

visual-brief assembler 继续按既有 scope／supersedes 契约决定适用于本页的 `applied_visual_revision_ids`；compiler 不重新猜测 deck／anchor／page applicability。编译时执行下面唯一投影：

1. 把 brief 中 IDs 解析为无重复列表，并按 `visual-revision-N` 的 N 数值升序；该完整排序列表写入 provenance 和 composite snapshot。
2. 每个 ID 必须在 keyed `run.json.interaction_history` 中存在，且记录满足 `kind: visual_revision`、`status: applied`；brief mirror 与权威 history 不一致时返回 `prompt_snapshot_conflict`。
3. 每条 `supersedes` 必须是 `<earlier-id>:<normalized_changes-field>`，目标 ID 必须在同一排序列表中更早出现，字段必须存在；不存在、跨页 mirror 冲突、目标为自身／未来或重复 edge 都返回 `prompt_snapshot_conflict`。
4. 按 N 升序应用所有有效 edge。一个字段被任何后续 applied record 取代后永久 inactive；即使该 superseding record 的字段以后也被更新，旧字段不复活。
5. 对每条记录只投影 `id`、`stage`、`affected_scope`、`status`、`artifact_owner`、规范排序的 `supersedes` 和仍 active 的 `normalized_changes`。`answer`、推荐理由、clarification 文字和其他未列字段一律排除。
6. `normalized_changes` 递归使用 canonical JSON key 顺序；没有 active fields 的记录从 prompt body 投影中省略，但其 ID 仍保留在 `applied_visual_revision_ids` provenance。
7. `[ACTIVE_VISUAL_REVISIONS]` 的替换 bytes 是投影数组的 canonical JSON 加一个 LF；无有效投影时是 `[]\n`。

`tests/fixtures/style-prompt-active-revision-projection.json` 必须给出 keyed history、目标 brief IDs、部分 supersede、后续再次 supersede，以及精确 expected canonical JSON bytes；其中 raw `answer` 包含已废弃指令，以证明它不会进入输出。

### 6.4 每份完整 prompt 的语义责任

每份模板正文必须明确要求：

1. 不改变锁定主张、置信度、范围、因果、比较、数字、单位、限定、来源或受众行动；
2. 不使用旧 SVG 作为 `recompose` 的几何底稿；
3. 先优化信息优先级、焦点和阅读顺序，再生成几何；
4. 只输出一个 fenced `xml` 代码块，代码块内只有一个完整 `<svg>`；
5. 使用 1280×720 画布、64 px 安全边距和允许的 Office-safe 元素；
6. 文字保持为文字并使用显式 `<tspan>`；
7. 不使用远程资源、脚本、事件、HTML、滤镜、渐变、自动换行或关键 emoji；
8. 保留来源元数据并满足结构、内容、视觉和 PowerPoint QA；
9. fresh generator 只返回文本，不能直接改工作区；创建上下文提取、验证并原子提升候选文件。

包测试通过固定 marker、占位符、允许／禁止字面契约和人工审查验证内置模板。运行时 Agent 不尝试对任意自由文本做完整语义证明。

## 7. 四个风格的完整 Prompt

### 7.1 `minimal-business`

强调留白、克制边界、少量层级、简洁比较和结论先行。不得默认使用层级 Bento、深色中央主卡或大量卡片。

### 7.2 `tech-dark`

使用深色画布、高对比技术关系、系统／架构／流程表达和有限高亮。不能用发光滤镜、远程字体或降低正文可读性。

### 7.3 `bold-editorial`

强调大标题、观点节奏、不对称排版、少量强色块和编辑式留白。不得机械套用管理卡片墙。

### 7.4 `canway-midyear-review`

承载用户提供的嘉为视觉指令，包括层级 Bento、深色主卡、白色事实卡、浅蓝证据边界、紫色试点／风险语义、短语级强调、40%–60% 卡片覆盖、主次至少 1.5 倍和最多一处轻阴影。

它必须继续遵守 `STYLE.md` 的防同质化边界：这些是抽象视觉语法，不是固定区域、固定卡片数量或单页成品模板。逐页构图与风格语法不匹配时，visual brief 的页面语义胜出，并在 `exceptions` 记录偏离；这不是模板无效。

Canway 专属词汇和强制构图不得存在于共享 resolver 或另外三个 prompt。

## 8. 规范操作类型

visual brief 的 `mode` 仍只允许 `patch` 或 `recompose`，不新增第三值。“修订模式”章节新增两个 schema-v1 必需字段：`generation_intent` 与 `generation_trigger_id`。

| 场景 | mode | generation_intent | generation_trigger_id | prior candidate |
|---|---|---|---|---|
| 首次生成 | `recompose` | `initial_generation` | `initial:<slide-id>:<visual_brief_snapshot_id>` | `none` |
| 用户要求重新构图 | `recompose` | `user_recompose` | `interaction:<interaction_history-id>` | 只用于锁定内容核对，不作为几何底稿 |
| 两次 patch 后确定性回退 | `recompose` | `deterministic_fallback` | `fallback:<slide-id>:<failed-transaction-64hex>:2` | 只用于问题核对，不作为几何底稿 |
| 局部修补 | `patch` | `local_patch` | `patch:<slide-id>:<qa-defect-id>` | 当前 SVG 是必需输入 |

首次生成使用固定 `reason: initial generation from approved visual brief`。确定性回退使用固定 `reason: deterministic single-column or two-column fallback after two failed patches`。

`user_recompose` 的 trigger 必须指向 `run.json.interaction_history` 中恰好一条 `status: applied` 的记录；该记录的原始 `answer` 是 `[USER_WORDING]` 的唯一来源。若请求为 deck scope，同一个 `interaction:<id>` 确定性 fan out 到全部受影响 briefs；每页保留同一 trigger ID，但 transaction 因 slide／brief snapshot 不同而不同。trigger 在 brief 和 transaction 中持久保留，resume 不重新选择“最新”记录；下一次明确视觉操作原子替换 brief 中的 trigger。initial 和 fallback 只使用表中的 sentinel，不引用历史 answer。trigger 目标缺失、状态不为 applied 或存在多个 owner 时返回 `prompt_snapshot_conflict`。

两次 patch 失败后的单栏／双栏回退必须重新组装 brief、重新解析 style prompt、编译新的 generation prompt、启动 fresh generator，并把新候选修复次数重置为 0。它不能继续标作 patch，也不能绕过风格 prompt provenance。

`generation_intent` 是 schema-v1 visual brief 的向后兼容新增必需字段，不提升 schema 版本。旧 brief 缺该字段时，只有在下一次视觉操作开始前才重建该章节：当前操作来自普通 anchor／production 首次生成队列时写 `initial_generation`；来自已持久化用户 recompose 请求时写 `user_recompose`；来自两次 patch 失败的确定性回退记录时写 `deterministic_fallback`；局部 patch 写 `local_patch`。判定依据是当前操作的持久 owner／触发记录，不从 SVG 是否存在猜测。若多个 owner 同时声明不同 intent，返回 `prompt_snapshot_conflict`。

## 9. 解析算法与身份握手

首次生成、用户 `recompose` 或确定性回退的解析顺序固定如下：

1. 验证 `run.json.manuscript_review.state == manuscript_approved`，并验证当前 visual brief、storyboard 和 theme 快照有效。
2. 从 visual brief 读取唯一 `selected_style_id`；不得从请求文本、主题关键词、目录内容或旧 SVG 猜测。
3. 从受信任固定 Skill 根定位 `assets/styles/registry.json`：
   - 只有 no-follow／`lstat` 明确返回不存在时才进入第 11 节 fallback；
   - 已存在但任一路径组件或叶节点是 symlink／junction／reparse point 时返回 `registry_path_unsafe`；目录、特殊文件或其他非普通文件返回 `registry_target_invalid`；普通文件不可读或不是 UTF-8 时返回 `registry_unreadable`；JSON 无效返回 `registry_malformed`；这些情况绝不当作 missing；
   - 解析后验证 `schema_version == 1`、style IDs 和 display names 唯一；
   - 在处理任一具体条目前，先要求每个 `style_pack` entrypoint 精确等于 `<entry-id>/manifest.json`，计算 `assets/styles/<entry-id>/` exact pack root，并验证全部 roots 是 styles 根的直接子目录、互不相同且互不嵌套。
4. registry 存在时按精确 ID 查找唯一条目，并验证 `kind` 只能是 `legacy_seed` 或 `style_pack`。
5. 对 `legacy_seed`：
   - `entrypoint` 和 `redesign_prompt` 都相对 `assets/styles/` 根解析；
   - 规范化后必须仍位于该根内，且不能位于任何已注册 style-pack 子目录；
   - entrypoint 与 prompt 的每一级路径组件及叶节点都不能是 symlink、junction 或 reparse point，叶节点必须是普通文件；
   - 解析 entrypoint JSON，要求为既有 seed 对象结构且 `name == selected_style_id`；格式错误映射 `legacy_entrypoint_malformed`，身份不符映射 `legacy_identity_mismatch`；
   - 旧 v1 条目缺 `redesign_prompt` 时只对三个已知内置 ID 采用 `<entrypoint-stem>.redesign.md` companion。
6. 对 `style_pack`：
   - entrypoint 已由步骤 3 证明精确为 `<selected_style_id>/manifest.json`；在打开前再次验证每一级路径组件和叶节点均非 symlink／junction／reparse point，目标是 exact pack root 内普通 manifest 文件；
   - 验证 manifest JSON、`schema_version == 1`、`manifest.id == selected_style_id`、`manifest.kind == registry.kind == style_pack`、`manifest.display_name == registry.display_name` 和符合第 5.3 节语法的 `version`；
   - `files.tokens`、`files.guidance`、`files.redesign_prompt` 都相对 exact pack root 解析，每一级路径组件和叶节点均不得是 symlink／junction／reparse point，规范化目标必须仍位于该 exact root 且为普通文件；不得引用 legacy 文件、styles 根文件或兄弟 pack；
   - tokens／guidance 的内容验证仍由 theme／design-system 阶段负责，但其路径 ownership 与 containment 使用本节同一规则，并在 `theme.json` 记录已经验证的规范路径；resolver 在身份握手时要求这些记录与当前 manifest 一致。
7. 所有路径拒绝：空值、绝对路径、Windows 盘符、UNC、URL、`.`／`..` 穿越、符号链接、junction/reparse point、目录和特殊文件。
8. 在读取模板正文前完成持久身份链握手：
   - visual brief 与 `theme.json` 的 selected style ID、display name、kind 和 manifest version 必须互相一致；
   - style-pack 的两份持久值还必须与当前 registry／manifest 精确一致；registry-backed legacy 的 ID／display name／kind 必须与 registry／seed 一致且 `style_manifest_version` 必须为字符串 `none`；registry-missing fallback 使用第 11 节权威身份表并同时匹配 seed `name`；
   - brief 与 theme 彼此矛盾，或多个持久 owner 声明不同 style 时返回 `prompt_snapshot_conflict`；
   - brief 与 theme 彼此一致，但安装升级导致当前 registry display name 或 manifest version 改变时，属于 ordinary stale：按现有 theme 失效规则返回 `theme`，从当前 registry／manifest 重建 theme 和全部受影响 visual briefs 后再编译，不写 blocker；
   - fixtures 覆盖 stale display name、stale version、brief/theme ID 混用和 legacy 非 `none` version。
9. 读取模板，验证模板 schema、STYLE_ID、marker 集合和占位符，然后按第 6.2 节编译。
10. 先建立第 13 节 transaction，再持久化 generation prompt；prompt durable 后才能启动 fresh independent generator。

路径 containment 是 instruction contract；静态测试验证内置包中的真实路径和恶意 fixture，host 行为验收验证 Agent 是否执行了先检查后读取。不得把测试内 resolver 称为运行时安全实现。

## 10. 稳定失败原因

所有 prompt 解析／编译错误使用 `state: style_prompt_unavailable`，并从下面的唯一 reason 中选择最早失败项：

```text
registry_missing
registry_path_unsafe
registry_target_invalid
registry_unreadable
registry_malformed
registry_schema_unsupported
registry_duplicate_style
style_not_registered
style_kind_invalid
entrypoint_missing
entrypoint_path_unsafe
entrypoint_target_invalid
legacy_entrypoint_malformed
legacy_identity_mismatch
manifest_malformed
manifest_schema_unsupported
manifest_identity_mismatch
manifest_version_invalid
style_asset_field_missing
style_asset_path_unsafe
style_asset_target_invalid
style_asset_unreadable
prompt_field_missing
prompt_path_unsafe
prompt_file_missing
prompt_target_invalid
prompt_unreadable
prompt_template_invalid
prompt_snapshot_conflict
```

reason 的唯一判定顺序不是上面枚举顺序，而是下面的 traversal；遇到首个失败立即停止。registry-wide pack-root shape 检查按 registry 数组顺序，只有该检查覆盖未选条目；manifest／asset／prompt 内容只检查 selected 条目。

| 顺序 | predicate | reason |
|---|---|---|
| 1 | 固定 registry path 不存在且不能通过完整 fallback | `registry_missing` |
| 1 | registry 路径含 link／junction／reparse | `registry_path_unsafe` |
| 1 | registry 目标不是普通文件 | `registry_target_invalid` |
| 1 | registry 不可读或非 UTF-8 | `registry_unreadable` |
| 1 | registry JSON 无效 | `registry_malformed` |
| 1 | registry schema 非 1 | `registry_schema_unsupported` |
| 2 | ID 或 display name 重复 | `registry_duplicate_style` |
| 3 | 任一 pack entrypoint 不是精确 `<entry-id>/manifest.json`，pack root 非直接子目录，或 roots 重叠／嵌套 | `entrypoint_path_unsafe` |
| 4 | selected ID 不存在 | `style_not_registered` |
| 4 | selected kind 不支持 | `style_kind_invalid` |
| 5 | selected entrypoint 字段缺失 | `entrypoint_missing` |
| 5 | selected entrypoint 路径越界／link | `entrypoint_path_unsafe` |
| 5 | selected entrypoint 目标无效／缺失 | `entrypoint_target_invalid` |
| 6 | legacy JSON 无效／结构不完整 | `legacy_entrypoint_malformed` |
| 6 | legacy `name` 与 selected ID 不同 | `legacy_identity_mismatch` |
| 7 | manifest JSON／schema／identity／version 无效 | 对应 `manifest_*` reason |
| 8 | selected pack 的 `files.tokens` 或 `files.guidance` 字段缺失 | `style_asset_field_missing` |
| 8 | 上述资产路径越界／link | `style_asset_path_unsafe` |
| 8 | 上述资产目标缺失、目录或特殊文件 | `style_asset_target_invalid` |
| 8 | 上述资产不可读 | `style_asset_unreadable` |
| 9 | prompt 字段、路径、目标、读取或模板结构失败 | 对应 `prompt_*` reason |
| 10 | persisted provenance／snapshot 无法唯一解释 | `prompt_snapshot_conflict` |

同一状态有多个缺陷时严格按顺序与 registry 数组顺序选择一个 reason；fixtures 必须包含未选 pack root 错误加 selected prompt 错误、以及 selected tokens 错误加 prompt 错误，证明 precedence。

`registry_missing` 只有在不能进入第 11 节完整兼容 fallback 时才阻断。

### 10.1 `run.json.visual_generation_blocker`

schema-version 1 增加可选顶层对象；没有它的旧运行继续有效：

```json
{
  "visual_generation_blocker": {
    "state": "style_prompt_unavailable",
    "slide_id": "S07",
    "reason": "prompt_file_missing",
    "selected_style_id": "canway-midyear-review",
    "resource": "assets/styles/canway-midyear-review/REDESIGN.md",
    "visual_brief_snapshot_id": "sha256:...",
    "theme_snapshot_id": "sha256:...",
    "status": "active"
  }
}
```

- `resource` 只保存规范化 Skill 相对路径；解析在路径安全前失败时写 `none`，不得持久化未验证绝对路径、URL 或机密内容。
- 阻断写入使用单次原子 `run.json` 替换；`stage`、`mode`、`interaction_history` 和 `dirty_slides` 保持不变，受影响 slide 保持 dirty。
- 它不是用户问题，不使用 `pending_interaction`。恢复总顺序固定为：先验证／消费 `pending_interaction`；只有该对象不存在时才处理 `visual_generation_blocker`；交互对象存在时不得创建新的 style blocker，也不得开始 prompt 解析。
- blocker 恢复时重新验证同一 slide 的当前资源和快照：仍失败则幂等更新同一对象，不启动 generator。验证通过后先把 prompt 持久化；此时 transaction 仍为 `compiling` 且 blocker 仍 active。随后以**一次**原子 `run.json` 替换同时把 transaction 改为 `compiled` 并移除匹配 blocker。若 crash 留下“prompt 已 durable、transaction 仍 compiling、blocker 仍 active”，resume 核对 transaction ID 与 prompt hash 后补做这一次提交；绝不描述不存在的跨文件原子事务。
- 新 blocker 替换同一 slide 的旧 blocker；若另一个 slide 已有 active blocker，先处理原 blocker，不创建并行 blocker。
- 阻断期间不得创建／覆盖 SVG、不得把问题降级为 patch、不得改用其他风格。

## 11. 缺 Registry 与旧包兼容

缺 registry fallback 只使用下面的内置权威身份表：

| selected_style_id | selected_style_display_name | style_kind | style_manifest_version | entrypoint | companion prompt |
|---|---|---|---|---|---|
| `minimal-business` | `极简商务` | `legacy_seed` | `none` | `minimal-business.json` | `minimal-business.redesign.md` |
| `tech-dark` | `深色科技` | `legacy_seed` | `none` | `tech-dark.json` | `tech-dark.redesign.md` |
| `bold-editorial` | `强调编辑` | `legacy_seed` | `none` | `bold-editorial.json` | `bold-editorial.redesign.md` |

step 9 identity handshake 在 registry fallback active 时以此表替代 registry，并同时要求 seed `name`、prompt `STYLE_ID`、theme 与 brief 四字段全部匹配。持久 display name／kind／version 缺失按第 5.4 节重建；显式冲突返回 `prompt_snapshot_conflict`。

区分三个场景：

1. **升级后的完整兼容安装**：只有 no-follow／`lstat` 已确认 registry 路径不存在时才探测 fallback。固定检查 `minimal-business.json`／`.redesign.md`、`tech-dark.json`／`.redesign.md`、`bold-editorial.json`／`.redesign.md` 六个文件：三份 seed 都必须通过 JSON 结构和 `name` 身份校验，三份 prompt 都必须通过 schema／STYLE_ID／marker／占位符契约，所有路径都必须满足 legacy containment。六者全部通过后才允许三个内置 ID 按 `<entrypoint-stem>.redesign.md` 解析；任一未选中 seed／prompt 格式错误也使完整 fallback 不成立并统一返回 `registry_missing`。六者全部有效但 selected ID 是 Canway 或未知值时同样返回 `registry_missing`。
2. **部分升级或真正旧包**：registry 缺失，且上述六文件集合不完整。统一返回 `registry_missing`，要求先升级标准 Skill 包；不得因为所选风格的一对文件恰好存在而进入部分 fallback。现有已验证 SVG 在没有视觉修改请求时可以只读保留。
3. **registry 存在但 prompt 声明缺失**：
   - 三个已知内置 legacy ID 的条目缺 `redesign_prompt` 时，按第 5.2 节使用 `<entrypoint-stem>.redesign.md`；companion 不存在时返回 `prompt_file_missing`；
   - 其他 legacy 条目缺字段时返回 `prompt_field_missing`；
   - style-pack manifest 缺 `files.redesign_prompt` 时返回 `prompt_field_missing`；
   - 任一显式字段存在但目标文件缺失时返回 `prompt_file_missing`。

缺 registry 时不得发现 style pack。用户选择 Canway 或未知 style ID 时阻断为 `registry_missing`。测试分别覆盖完整 fallback、缺任一 seed、缺任一 companion 和 registry-backed prompt 缺失，reason 不允许二选一。

## 12. 编译产物与 Snapshot

`generation-prompts/<slide-id>.md` 使用固定两段格式：

```markdown
# Generation Prompt <slide-id>

## Provenance
- artifact_schema_version: 1
- transaction_id: sha256:...
- selected_style_id: canway-midyear-review
- style_kind: style_pack
- style_manifest_version: 1.2.0
- resolved_redesign_prompt_path: canway-midyear-review/REDESIGN.md
- style_prompt_snapshot_id: sha256:...
- visual_brief_snapshot_id: sha256:...
- storyboard_snapshot_id: sha256:...
- theme_snapshot_id: sha256:...
- applied_visual_revision_ids: ["visual-revision-1"]
- generation_intent: user_recompose
- generation_trigger_id: interaction:visual-revision-4
- compiled_prompt_sha256: sha256:...
- prompt_snapshot_id: sha256:...
- status: compiled

## Compiled Prompt Body
<替换占位符后的完整风格 prompt 正文>
```

legacy seed 的 `style_manifest_version` 写字符串 `none`。`applied_visual_revision_ids` 在 envelope 中始终写 canonical JSON array text，零项为 `[]`、一项也保留数组，顺序与第 6.3 节一致。路径统一保存为以 `assets/styles/` 为根的区分大小写 POSIX 相对路径。字段名沿用现有 generation-prompt 契约的 `visual_brief_snapshot_id` 与 `applied_visual_revision_ids`，不得另造 `brief_snapshot_id`／`active_visual_revision_ids` 别名。

### 12.1 文本规范化与 hash domain

- 所有 prompt 与 Markdown 输入必须是 UTF-8；拒绝解码错误。
- 编译前把 CRLF 和 CR 统一为 LF，输出 UTF-8、无 BOM、文件末尾恰好一个 LF。
- `style_prompt_snapshot_id` 对**替换前、已完成 LF 规范化的模板正文 UTF-8 bytes**计算 SHA-256，格式为 `sha256:<64 位小写 hex>`。
- `compiled_prompt_sha256` 只对 `## Compiled Prompt Body` 标题下一行开始的规范化正文 bytes 计算，不包含标题、Provenance、hash 字段或其他 envelope；因此不存在自引用。
- `[OUTPUT_PATH]` 不属于模板契约。fresh generator 不写文件，候选路径由第 13 节 transaction 在创建上下文计算，不进入 compiled body 或 snapshot hash domain。

### 12.2 Composite snapshot

`prompt_snapshot_id` 对下面的 canonical JSON UTF-8 bytes 计算 SHA-256：

```json
{
  "applied_visual_revision_ids": ["visual-revision-1"],
  "compiled_prompt_sha256": "sha256:...",
  "generation_intent": "user_recompose",
  "generation_trigger_id": "interaction:visual-revision-4",
  "resolved_redesign_prompt_path": "canway-midyear-review/REDESIGN.md",
  "selected_style_id": "canway-midyear-review",
  "storyboard_snapshot_id": "sha256:...",
  "style_kind": "style_pack",
  "style_manifest_version": "1.2.0",
  "style_prompt_snapshot_id": "sha256:...",
  "theme_snapshot_id": "sha256:...",
  "visual_brief_snapshot_id": "sha256:..."
}
```

Canonical JSON 规则：UTF-8、无 BOM、对象键按 Unicode code point 升序、数组保持规范顺序、分隔符使用 `,` 和 `:` 且无额外空白、末尾无换行。最终格式同样是 `sha256:<64 位小写 hex>`。`transaction_id` 精确等于 `prompt_snapshot_id`，所以相同权威输入重复编译产生相同 transaction、正文 bytes 和 hashes。

模板 path、模板内容、manifest version 或任一上游 snapshot/hash 变化都属于普通 stale，重新编译；即使 style author 忘记升级 manifest version，模板 hash 变化也不产生 blocker。`prompt_snapshot_conflict` 只用于持久 provenance 内部不一致或权威输入无法唯一重建，例如 stored compiled-body hash 与 stored body 不一致、同一 transaction 声称两个不同 canonical prompt payload、或 brief/theme/storyboard 权威 snapshots 互相矛盾。

测试提供一个固定 body/envelope fixture 与 golden hashes，并验证相同输入重复编译字节完全一致；再分别变更路径、模板内容、manifest 版本、brief、theme、storyboard、revision IDs 和 intent，确认 hash 改变。

## 13. 可恢复 Generation Transaction

schema-version 1 增加可选顶层 `run.json.visual_generation_transaction`，一次只允许一个 active transaction：

```json
{
  "visual_generation_transaction": {
    "transaction_id": "sha256:...",
    "slide_id": "S07",
    "generation_intent": "user_recompose",
    "generation_trigger_id": "interaction:visual-revision-4",
    "prompt_path": "generation-prompts/S07.md",
    "prompt_snapshot_id": "sha256:...",
    "compiled_prompt_sha256": "sha256:...",
    "candidate_path": "slides/.candidates/S07-<64hex>.svg",
    "final_path": "slides/S07.svg",
    "state": "compiled",
    "generation_attempt": 0,
    "candidate_sha256": null,
    "failure_reason": null
  }
}
```

`transaction_id` 精确等于完整 `prompt_snapshot_id`（含 `sha256:` 前缀）；候选文件名只使用其 64 位 hex 部分，因此相同逻辑 transaction 的路径稳定。允许状态：

```text
正常：compiling -> compiled -> generating -> candidate_written -> validated -> promoted
失败：generating | candidate_written | validated -> failed
恢复：failed -> generating（transport／generator retry）
      failed -> validated（用户解决 conflict 且 candidate／provenance 未变）
替换：failed transaction -> new compiling transaction（权威输入已变或 deterministic fallback）；这是原子对象替换，不是同 transaction edge
```

`failure_reason` 为 null 或下面一个稳定值：

```text
generator_unavailable
generator_refused
generator_timeout
generator_output_malformed
candidate_write_failed
candidate_hash_mismatch
svg_contract_failed
locked_content_mismatch
visual_qa_failed
final_promotion_conflict
transaction_state_conflict
```

每次状态变化都使用单次原子 `run.json` 替换；跨文件步骤不声称原子。固定顺序和 crash 恢复如下：

1. **开始编译**：原子写入 `state: compiling`，记录 transaction 的全部可预计算字段；保留现有 final SVG。
2. **持久化 prompt**：写同目录临时文件，关闭并复读校验后原子替换 `generation-prompts/<slide-id>.md`。
3. **提交 compiled**：核对 durable prompt 后，以一次原子 `run.json` 替换把 transaction 改为 `compiled`，并在同一份 `run.json` 新值中移除匹配的 `visual_generation_blocker`。如果 crash 发生在步骤 2 后，resume 在 `compiling` 状态复核 prompt path／hash；匹配则只补做步骤 3，不匹配则重编。
4. **启动 generator**：先原子改为 `generating`，再把 compiled body 交给 fresh generator。generator 不接收旧 SVG、对话或工作区写权限。委派不可用、拒绝、超时分别原子转为 `failed` 并记录 `generator_unavailable`、`generator_refused`、`generator_timeout`。
5. **持久化候选**：generator 输出视为不可信文本；创建上下文只提取恰好一个 fenced XML 中的单个 SVG。格式无效转为 `failed: generator_output_malformed`；候选写入失败转为 `failed: candidate_write_failed`。成功时写入 deterministic candidate path，关闭后计算 SHA-256，再原子把状态改为 `candidate_written` 并保存 `candidate_sha256`。如果 crash 留在 `generating`，此时没有 committed expected candidate hash；任何 deterministic path 上的文件都视为 orphan，必须删除或隔离且绝不采用，然后重新调用 generator。只有 transaction 已 durable 为 `candidate_written` 且记录非空 `candidate_sha256` 时，resume 才可复读候选并比较；不匹配转为 `failed: candidate_hash_mismatch`，匹配才继续验证。
6. **验证候选**：按现有 `svg-contract.md` 检查禁止 DTD／ENTITY、脚本、事件、远程资源、命名空间、元素／属性和几何；结构失败用 `svg_contract_failed`，锁定内容失败用 `locked_content_mismatch`，必需视觉 QA 失败用 `visual_qa_failed`。全部通过后原子改为 `validated`；任一失败原子改为 `failed`，保留上一有效 SVG 和 dirty 状态。
7. **提升候选**：只有 `validated` 状态才能把候选原子替换为 final path，然后原子把 transaction 改为 `promoted`。如果 crash 发生在 final 替换后、状态提交前，resume 比较 final bytes 与已记录 `candidate_sha256`；相同则补写 `promoted`，不同则原子转为 `failed: final_promotion_conflict`。不符合当前状态允许 transition 的任何恢复请求使用 `transaction_state_conflict`。
8. **完成**：页面和整套 QA 使用 promoted transaction 的 prompt／candidate hashes；通过后在清除该页 dirty 状态的同一 `run.json` 原子替换中移除 transaction。transaction 未 promoted 时不得清除 dirty。

新操作到来时若已有非终态 transaction，必须先按上述状态恢复，不得覆盖。`failed` 不能静默删除，并按 reason 使用唯一 consumer：

| failed reasons | 唯一下一步 |
|---|---|
| `generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch` | 下一次显式 `resume` 删除／隔离本 transaction orphan candidate，`generation_attempt` 加一，以原子 `run.json` transition 把同一 transaction 从 `failed` 改回 `generating`，使用同一 trigger 和 authoritative inputs 重新调用 generator；每次宿主调用最多重试一次，不自动循环。 |
| `svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed` | 先把 failure reason 和一个精确 defect 幂等镜像到 visual brief／QA owner。defect 可局部修复时，在 patch owner durable 后原子移除 failed transaction并进入既有 patch；需要改变布局时，在已更新 brief 的同一次 `run.json` 替换中用新的 `deterministic_fallback`／`compiling` transaction 替换 failed transaction。初始生成没有 final SVG 时仍可把失败 candidate 作为 patch 输入，但不能提升为 final。 |
| `final_promotion_conflict`、`transaction_state_conflict` | 按 interaction protocol 持久化一个 production `blocker` 问题并停止；不得覆盖未知 final 或删除 transaction。用户明确解决 workspace 冲突后，若 candidate/hash/provenance 仍有效则原子 `failed -> validated` 并重试提升；权威输入已变则以新的 `compiling` transaction 替换。 |

除这些 consumer 和 promoted 后最终 QA 清理外，不存在取消、任意终止或直接删除 transaction。每个 reason 到下一状态都在 `visual-generation-transaction-cases.json` 中有 before／after fixture。

本设计不重新定义 XML parser 实现；现有纯指令 SVG 契约仍是规范来源，真实 hostile-output 防护属于 host／工具行为验收。

## 14. 风格冲突的两个分支

### 14.1 模板本身无效

如果受信任模板缺少固定结构、marker、占位符，或 STYLE_ID 不匹配，则确定性标记 `prompt_template_invalid` 并阻断。正文是否明确要求削弱内容／来源／Office-safe／输出／QA 硬约束，由模板代码审查和 host 压力场景判定；静态包测试不发明自然语言禁句 oracle，也不把 marker 出现误称为完整语义证明。

### 14.2 页面语义覆盖风格艺术方向

如果模板本身有效，但某页内容不适合该风格的常用构图、卡片数量、表面或阅读路径，则不把模板判无效。visual brief 的页面语义胜出，并在 `视觉系统.exceptions` 记录具体偏离；编译时该 exceptions 字段通过 `[VISUAL_SYSTEM]` 进入完整 prompt。

## 15. 旧 Prompt 目录迁移矩阵

新标准目录为 `generation-prompts/`，旧 `redesign-prompts/` 始终只读。当前有效性只由新 provenance 和 snapshots 决定，不由目录存在决定。

| 初始状态 | 无视觉请求 | 下一次首次生成／recompose | 旧文件处理 |
|---|---|---|---|
| 只有旧目录，已有有效 SVG | 保留 SVG，不重写上游 | 按当前 brief/style 编译新目录；成功后新文件 active | 旧目录保留为只读历史，不参与选择 |
| 只有新目录但缺新 provenance | 保留现有有效 SVG | 把新文件视为 stale，并只原子替换 `generation-prompts/<slide-id>.md` | `redesign-prompts/` 下任何文件都不写、不移动、不删除 |
| 同一 slide 两目录都有文件 | 只要现有 SVG 无视觉请求就不猜 prompt | 新文件 provenance 全部匹配则使用新文件；否则只重编新文件 | 旧文件永远 inert，不构成冲突 |
| 两目录包含不同 slides | 每页独立处理 | 目标页按同一规则解析 | 不迁移无关页 |
| brief 缺 `selected_style_id` | 现有 SVG 可只读保留 | 返回 `prompt_snapshot_conflict`，先重建 brief 或询问无法推断的风格 | 不猜风格 |
| brief 缺 `generation_intent` | 现有 SVG 可只读保留 | 按第 8 节当前持久 operation owner 重建字段；owner 冲突才报 `prompt_snapshot_conflict` | 不从 SVG 存在推断 intent |
| brief manifest 1.1.0、安装资源 1.2.0 | 现有 SVG可只读保留 | style provenance 已变化：使旧 brief／prompt stale，从当前 theme 和 style 重新组装 brief 后编译 | 保留历史文件但不激活 |
| style prompt 内容已变化 | 现有 SVG可只读保留 | snapshot 不匹配，重新编译 | 原子替换新目录文件 |

`prompt_snapshot_conflict` 只用于持久 provenance 内部不一致或无法从权威状态唯一重建：缺 selected style、多个 operation owner 声明不同 intent、brief/theme/storyboard snapshots 互相矛盾、stored compiled-body hash 与 stored body 不一致，或同一 transaction ID 对应两个不同 canonical payload。安装模板 path／hash 变化，无论 manifest version 是否同步变化，都只是 ordinary stale 并重新编译，不报冲突。

## 16. 测试与证据边界

### 16.1 TDD 顺序

1. 先改写当前反向契约测试：共享文件不再要求 Bento／固定字体／固定圆角，Canway manifest 不再要求精确两键或版本 1.1.0。
2. 在新增 prompt 资产前运行，确认因四个 prompt 缺失、manifest／registry 未声明、共享文件仍含风格规则而 RED。
3. 逐个增加 legacy prompt、Canway prompt、resolver 文案、artifact schema 和 fixtures，每个最小变更后转 GREEN。
4. 对 instruction 行为使用 fresh-agent 压力场景：先用旧 Skill 记录错误的跨风格 Bento／错误 fallback 行为，再用新 Skill 复测。压力场景是诊断，不替代真实 Claude Code／Codex 验收。

### 16.2 确定性 package-contract 测试

仓库测试可以确定性证明：

- 四个 registry 风格都声明存在且包内安全的 prompt 资产，并满足精确 schema／marker／placeholder 表面契约；自然语言完整性由模板代码审查与 host 证据负责；
- style pack prompt 只由 manifest 声明，legacy prompt 由 registry 或已知 companion 规则声明；
- registry/manifest identity、kind、schema 和路径握手 fixtures；
- 四个 prompt 的 schema block、STYLE_ID、marker 集合和十一个唯一占位符；
- 可执行 prompt 表面隔离：下面区分大小写的 Canway 专属字面量必须存在于 `canway-midyear-review/REDESIGN.md`，并且不得出现在共享 `references/redesign-prompt.md` 或三个 legacy `*.redesign.md`：`层级 Bento`、`深色主卡`、`白色事实卡`、`浅蓝证据边界`、`40%–60%`、`1.5`、`最多一处轻阴影`；`STYLE.md`、tokens、manifest、测试和设计文档不属于此排除范围；
- 通用硬约束的确定性测试只检查精确 marker IDs、占位符、STYLE_ID 和结构；第 6.4 节自然语言是否完整、是否存在隐含矛盾属于模板代码审查与 host 压力场景，不发明额外“禁句”oracle；
- 绝对路径、盘符、UNC、URL、`.`／`..`、root-level manifest、nested／overlapping pack roots、parent-to-child pack reference、tokens／guidance／prompt escape、legacy-to-pack、symlink（平台允许时）、缺失文件、目录和特殊目标 fixture 被书面 resolver oracle 判无效；
- blocker schema、reason 枚举、迁移矩阵和 generation-prompt provenance 格式；
- canonical snapshot fixture、repeat-compile byte equality 与 golden SHA-256；
- `ACTIVE_VISUAL_REVISIONS` fixture 证明原始 `answer` 永不进入编译 prompt，且部分 supersede 只保留仍有效的 `normalized_changes`；
- generation transaction 的每个状态、单文件原子 transition 和 crash 边界 fixture；
- manifest 版本、prompt 内容或上游 snapshot 变化会改变测试 oracle 的 hash；
- shared references、README、设计和验收文档使用同一契约。

测试中的 resolver/hash oracle只证明规范算法和内置包一致，不是 Skill 的运行时实现。

聚焦命令固定为：

```bash
python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs tests.test_visual_generation_contract -v
```

完整命令固定为：

```bash
python -m unittest discover -s tests -v
```

### 16.3 Host／Skill 行为验收

以下项目保持 `PENDING`，直到保存真实宿主版本、transcript 和运行目录证据：

- 只按 selected style 加载一个 prompt；
- 路径或模板错误时先写 blocker，且不启动 generator、不覆盖 SVG；
- `patch` 不加载完整 prompt；
- 首次生成、用户 recompose 和确定性 fallback 都走 fresh generator；
- fresh generator 只收到编译 prompt；
- crash／resume 按 blocker 和 provenance 幂等恢复；
- 浏览器渲染与 PowerPoint 导入。

静态测试绿色不得描述为这些行为已经通过。

## 17. 影响文件

必须修改：

- `skills/ppt-start/SKILL.md`（同步恢复顺序摘要）
- `skills/ppt-start/references/workflow.md`（`pending_interaction` > blocker > transaction 的总顺序）
- `skills/ppt-start/references/redesign-prompt.md`
- `skills/ppt-start/references/design-system.md`
- `skills/ppt-start/references/visual-brief-and-generation.md`
- `skills/ppt-start/references/artifact-contract.md`
- `skills/ppt-start/references/qa-and-revision.md`
- `skills/ppt-start/assets/styles/registry.json`
- `skills/ppt-start/assets/styles/canway-midyear-review/manifest.json`
- `skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`（增加完整 prompt 所有权与 exceptions 交叉引用）
- `skills/ppt-start/assets/styles/minimal-business.redesign.md`（新增）
- `skills/ppt-start/assets/styles/tech-dark.redesign.md`（新增）
- `skills/ppt-start/assets/styles/bold-editorial.redesign.md`（新增）
- `skills/ppt-start/assets/styles/canway-midyear-review/REDESIGN.md`（新增）
- `tests/test_redesign_prompt_contract.py`
- `tests/test_style_packs.py`
- `tests/test_visual_generation_contract.py`
- `tests/fixtures/visual-briefs/S05.md`（Canway 1.2.0、四个持久 identity 字段、`generation_intent` 与 `generation_trigger_id`）
- `tests/fixtures/style-identity-migration-cases.json`（新增：theme／brief 字段缺失、stale、fallback 和冲突）
- `tests/fixtures/style-prompt-active-revision-projection.json`（新增：排除 raw `answer` 与部分 supersede）
- `tests/fixtures/style-prompt-resolution-cases.json`（新增：四个正常分支、旧 registry、非法路径和身份握手）
- `tests/fixtures/generation-prompt-snapshot.json`（新增：literal 输入章节、compiled body、完整 envelope、canonical payload 与 golden hashes）
- `tests/fixtures/style-prompt-blocker-cases.json`（新增：blocker 前后状态和恢复）
- `tests/fixtures/visual-generation-transaction-cases.json`（新增：各状态、crash 边界和候选提升）
- `README.md`
- `docs/design.md`
- `docs/acceptance.md`
- `docs/superpowers/specs/2026-08-20-ppt-pilot-visual-prompt-assembly-design.md`（同步所有被替代的所有权、编译、恢复、测试与验收边界）
- `docs/superpowers/plans/2026-08-20-ppt-pilot-style-registry.md`（增加 superseded banner）
- `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-reference-svg.md`（增加 superseded banner）
- `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-style-guidance.md`（增加 superseded banner）
- `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-brief-contract.md`（增加 superseded banner）
- `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-prompt-assembly.md`（增加 superseded banner）

不修改运行时 acceptance evidence，不创建真实 deck 产物。

## 18. 验收标准

### 18.1 书面与包契约

1. `references/redesign-prompt.md` 不含完整生成 prompt 或任何内置风格专属构图规则。
2. 四个现有风格各自拥有完整、版本化、可验证的 redesign prompt。
3. Canway prompt 位于 `canway-midyear-review` pack，并由 manifest 声明；manifest 内容版本为 `1.2.0`、schema 仍为 1。
4. 当前 registry 与全部 manifest／prompt 引用通过 identity、kind 和 kind-specific containment 检查。
5. 新 style pack 通过新增 registry 条目及自己的 manifest／prompt 接入，无需修改 resolver 逻辑或 schema。
6. schema-v1 legacy 条目缺新字段时有确定性 companion fallback；真正缺少 companion 的旧包明确阻断并要求升级。
7. generation prompt 记录完整 style provenance，使用规范 SHA-256；资源变化使测试 fixture 的旧 snapshot 失效。
8. `visual_generation_blocker`、reason 枚举、`visual_generation_transaction` 状态机、原子单文件 transitions 和旧目录迁移都有确定性 schema／fixture。
9. `patch`、文稿质量门、页面 exceptions、Office-safe SVG 和 QA 书面硬约束不被削弱。
10. 聚焦 package-contract 测试和完整本地测试全部通过。
11. 更新后的标准 Skill 包同步到 Claude Code 用户级安装目录，并以文件集和 SHA-256 验证与仓库源包一致；这是部署验证，不是 host 行为验收。

### 18.2 行为验收

第 16.3 节全部行为在没有真实证据前保持 `PENDING`。实施完成不得把静态测试、测试 oracle、通用子 Agent 或安装 hash 描述为 Claude Code／Codex 行为通过。
