# Style Baseline Projection 设计（风格 → 基线 → prompt）

> 本文件是“把风格包编译成稳定 `style_baseline` 并填入 `[[STYLE_BASELINE]]`”的设计规格。它定义目标文件结构、确定性投影规则、`style_baseline_snapshot_id` 的输入域，以及如何让既有测试与金样保持一致。它是演进式改动：不改运行时生成逻辑、不新增第三个替换域、不把可执行 prompt 正文还给风格包。

## 1. 目标

消除风格基线的两个结构性缺陷：

1. **数值漂移**：`tokens.json` 与 `STYLE.md` 双写同样的数字（如 `card_coverage: "40%-60%"`、`max_shadowed_objects: 1`），目前靠字符串匹配测试（`tests/test_style_packs.py:107-127`）人工兜底。
2. **投影无标准**：`style_baseline_snapshot_id` 对“软风格基线字节”求哈希（`generation-prompt-byte-grammar.md:16`），但没有任何文件定义这些字节如何**确定性**从风格资产生成。`tests/fixtures/generation-prompt-snapshot.json:151` 显示实际合成出一条无角色、无禁止项的手写 token 串。

## 2. 非目标（明确不做）

- **不新增第三个替换域**：模板保持恰好 `[[CANONICAL_NARRATIVE_BULLETS]]` + `[[STYLE_BASELINE]]` 两个 whole-line marker（`generation-prompt-byte-grammar.md:9`）。
- **不把可执行 prompt 正文还给风格包**：风格资产仍是纯“身份 + tokens + 语义指导”，不拥有页面生成正文（`generation-prompt-byte-grammar.md:7`、`test_style_packs.py:68`）。
- **不改生成器运行时**：不新增 TypeScript/Python 编译步骤，只改契约文档、风格资产、测试断言与金样。

## 3. 目标文件结构

```
skills/ppt-start/assets/styles/
├── registry.json                    # 发现入口（不变）
├── minimal-business.json            # legacy seed（不变，仅文档化）
├── tech-dark.json
├── bold-editorial.json
└── canway-midyear-review/
    ├── manifest.json                # 身份（不变，仍 v1.3.0）
    ├── tokens.json                  # 重构：schema_version 2，新增 prompt_baseline
    ├── STYLE.md                     # 降级为纯语义判断指导（去数字）
    └── REDESIGN.md                  # 历史遗留（inert）
```

## 4. `tokens.json`（schema_version 2）

保留原有字段（`colors`、`typography`、`spacing`、`shape`、`composition`），**新增** `prompt_baseline`，并 `schema_version: 2`。`prompt_baseline` 是把风格软基线**一字一句**投影进 prompt 的机器数据，键顺序固定，语义分类固定。

```jsonc
{
  "schema_version": 2,
  "id": "canway-midyear-review",
  "display_name": "嘉为年中总结风格",
  "colors": { /* 保留，原有语义角色不变 */ },
  "typography": { /* 保留 */ },
  "spacing": { /* 保留 */ },
  "shape": { /* 保留 */ },
  "composition": { /* 保留 */ },
  "prompt_baseline": {
    "palette_roles": [
      { "token": "brand_primary", "role": "结论强调", "use": "仅用于最高价值结论、行动或选中状态" },
      { "token": "sky",           "role": "次级关系", "use": "用于次级关系或过渡" },
      { "token": "ai_pilot",      "role": "AI/试点/风险", "use": "用于 AI、有界试点、高风险或失败分支" },
      { "token": "hero_dark",     "role": "唯一焦点", "use": "每页至多一张深色主卡" }
    ],
    "font_stack": ["Microsoft YaHei", "PingFang SC", "Arial", "sans-serif"],
    "spacing_rhythm": { "outer_margin": 64, "standard_gap": 24, "card_gap": 20, "card_padding": 24 },
    "shape_language": { "primary_radius": 20, "secondary_radius": 14, "stroke_width": 1.2, "connector_width": 2 },
    "composition_rules": { "card_coverage": "40%-60%", "primary_secondary_ratio": 1.5, "max_shadowed_objects": 1 },
    "prohibited_motifs": [
      "左侧长蓝条",
      "等权卡片墙",
      "背景图片或纹理",
      "渐变",
      "穿过文字的连接线",
      "无语义装饰线"
    ]
  }
}
```

约束：

- `prompt_baseline` 只含**软方向**与**禁止母题**；不含画布/安全区/圆角 path+A/Office-safe 等硬契约（那些在模板步骤 3，`generation-prompt-template.md:24-31`）。
- `palette_roles` 每项 `token` 必须引用 `colors` 里的键名，且不能重复。
- `prohibited_motifs` 是字符串数组，去重。
- `schema_version` 从 1 升到 2；旧的 `schema_version: 1` tokens（无 `prompt_baseline`）视为 **legacy-invalid**，解析器返回 `style_asset_schema_unsupported`（现有 `test_style_packs.py`／`style-prompt-resolution-cases.json` 的 `schema_version: 1` 黄金示例需改到 2）。

## 5. `STYLE.md`（语义判断 + 禁止项人类可读说明）

仍承载机器渲染不出的“判断知识”，并保留禁止项的人类可读说明（供人阅读、供理解），但**删除所有与 `prompt_baseline` 重复的硬数值**（如 `40%–60%`、`1.5`、`最多一处轻阴影`），以免与 `tokens.json` 漂移；与模板硬契约重复的 Office 机械禁令（渐变/滤镜/远程资源等）不再逐条重复列出，改为一句话引用模板硬契约。

保留三段：使用场景、语义表面规则（哪类内容放哪种语义卡的判断）、内容驱动构图配方（论证/流程/时间/对比/决策页如何组织）。禁止母题在 `STYLE.md` 中的说明仅是给人看的人类可读版本，机器可读结构化版本唯一来自 `tokens.json.prompt_baseline.prohibited_motifs`，两者不得以同一事实重复承担“机器读它”的职责。

## 6. `StyleBaselineCompiler`（确定性投影）

`StyleBaselineCompiler` 是一个**无状态、纯函数、无运行时副作用**的规范，定义如何从风格资产得到 `style_baseline` 字节；它是文档化的契约，不是可安装的可执行代码。唯一职责：把 `tokens.json`（`schema_version: 2`）的 `prompt_baseline` 渲染成进入 `[[STYLE_BASELINE]]` 的规范文本。

具体投影规则（**全部固定，输入不变则输出逐字节不变**）：

1. **输入**：`tokens.json.prompt_baseline`（键顺序固定）。
2. **小节顺序固定**：`色板角色` → `字体栈` → `间距节奏` → `形状语言` → `构图规则` → `禁止母题`。
3. **每节格式固定**，标题为中文，值为一行（数组/对象用固定分隔符，对象键有序但只渲染 `value`，`role`/`use` 一并入行）。
4. **标题行用 `- `（bullet）**；节之间空一行；结尾正好一个 `\n`（满足“replacement 必须以一个 LF 结尾”，`generation-prompt-byte-grammar.md:10`）。
5. `palette_roles` 渲染为 `颜色 <token>：<role>（<use>）`；`font_stack` 渲染为 `字体栈：<join(", ")>`；`spacing_rhythm`/`shape_language`/`composition_rules` 渲染为 `键: 值` 列表；`prohibited_motifs` 渲染为 `禁止：<join("；")>`。
6. **转义与文本安全**：所有来自风格资产或用户文件、tool output、用户请求的文本先转纯文本并转义 `&`、`<`、`>`、`"`、`'`，禁止注入 `[[...]]` marker、Markdown 标题、JSON 围栏、绝对路径或外部指令（沿用 `_reject_unsafe_replacement` 的既有约束，`tests/test_redesign_prompt_contract.py:592`）。
7. **规范化**：输出先 UTF-8，去一个 BOM，CRLF/CR 归一为 LF，保证恰好一个结尾 LF（`generation-prompt-byte-grammar.md:8`）。

`style_baseline_snapshot_id` = SHA-256(规范化后的 `style_baseline` 字节)（沿用 `generation-prompt-byte-grammar.md:16` 既有定义）。

## 7. 与现有 test fixture 的衔接

- `tests/fixtures/generation-prompt-snapshot.json:151` 的 `style_baseline`（目前是手写 token 串）改为由 `StyleBaselineCompiler` 产出的规范字节，并更新相应 `compiled_prompt_sha256` 等哈希字段。
- `tests/fixtures/style-prompt-resolution-cases.json` 中 `tokens.schema_version: 1` 黄金示例改为 `2`，并对 `prompt_baseline` 结构做最小校验。
- `tests/test_style_packs.py` 的断言从“字符串匹配 STYLE.md 散文数字”改为“校验 `tokens.json.prompt_baseline` 与 `manifest` 一致性”，并新增对 `StyleBaselineCompiler` 输出形状的断言。

## 8. 里程碑与拆分

- **M1（契约）**：重写 `generation-prompt-byte-grammar.md` 规则 3／10，明确 `style_baseline` 的确定性输入源（`tokens.json.prompt_baseline`），删除手写 token 串的许可。更新 `design-system.md` 与 `visual-brief-and-generation.md` 的措辞。
- **M2（资产）**：`tokens.json` 升到 `schema_version: 2` 并新增 `prompt_baseline`；`STYLE.md` 去重去硬数值。
- **M3（金样与测试）**：更新 `generation-prompt-snapshot.json`、`style-prompt-resolution-cases.json`、`theme-canway-S05.json` 与 `test_style_packs.py`、`test_redesign_prompt_contract.py`、`test_visual_generation_contract.py`、`test_skill_package.py`。

## 9. 风险与兼容

- **兼容**：本次只改 `canway-midyear-review` 资产与对应金样；三个 `legacy_seed`（`minimal-business` 等）保持 `schema_version: 1`，其 `style_baseline_snapshot_id` 的基准与 fallback identity table 不变（`design-system.md:31-39`）。
- **失败态**：`tokens.json.schema_version` 非 2 时返回 `style_asset_schema_unsupported`（既有 reason，不改枚举）。
- **不破坏**：`style_baseline` 仍是软方向；`fact_source_consistency`/`narrative_integrity`/SVG 硬契约不变（`qa-and-revision.md:98-104`）。
