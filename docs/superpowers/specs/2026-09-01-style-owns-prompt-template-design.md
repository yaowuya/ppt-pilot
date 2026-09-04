# 规模1：Style 自定义视觉结构（扩展基线）+ 移除输出层 SRC

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。
> 方向（用户已拍板）：保留唯一 canonical 固定模板 + 两个 marker；扩展 `prompt_baseline` 让 style 能自定义更完整的视觉/布局/规范指令；移除生成 prompt 正文的 SRC/来源标记（输出层）。**不**推翻 byte-grammar 规则 1/8/10 的"仅 canonical 模板可执行"安全边界。

## 1. 核心原则

- **模板不变**：`generation-prompt-template.md` 仍是唯一 canonical 模板，角色（信息架构师）、Workflow 三步、SVG 硬契约、兼容约束全部锁定。
- **两个 marker 不变**：`[[CANONICAL_NARRATIVE_BULLETS]]` + `[[STYLE_BASELINE]]`。
- **style 的发挥空间**：全部集中在 `[[STYLE_BASELINE]]`。通过扩展 `prompt_baseline`，让 style 能投影出"这套 style 想要传达给生成器的完整视觉/布局/结构指令"。

## 2. `tokens.json.prompt_baseline` 扩展

在既有 6 小节（palette_roles / font_stack / spacing_rhythm / shape_language / composition_rules / prohibited_motifs）基础上，新增**结构化指令小节**，让 style 能自定义更完整的产品/布局/视觉规范：

```jsonc
{
  "prompt_baseline": {
    // 既有 6 小节不变 ...
    "layout_preferences": [
      { "when": "产品能力概览页", "structure": "顶部标题栏+中部模块区+右侧卖点栏（左 2/3 + 右 1/3）" },
      { "when": "对比页", "structure": "不对称双栏，主卡显著" }
    ],
    "structure_rules": [
      "先提纯为金字塔结构，再选布局",
      "卡片间至少 20px 间距",
      "指标完成度优先用简洁表格，不拆成数据卡片"
    ],
    "title_spec": {
      "position": "top-left",
      "font_weight": 700,
      "size": "34-38px",
      "color": "#000000",
      "decoration": "黑蓝错位方块",
      "no_english": true,
      "no_top_right_logo": true
    },
    "tone_skew": "产品经理视角，商务+科技+简约，蓝色科技风，弱阴影，圆角卡片"
  }
}
```

`StyleBaselineCompiler` 按固定小节顺序（既有 6 + 新增 4：`layout_preferences` → `structure_rules` → `title_spec` → `tone_skew`）投影成 `[[STYLE_BASELINE]]` 文本。生成器在模板"步骤 2 应用风格基线"里读到这些，按其自定义视觉/结构指令设计。

## 3. 输出层移除 SRC/来源标记（不变，但明确边界）

- **删（生成 prompt 输出层）**：
  - `generation-prompt-template.md` 第 29 行整句；
  - `generation-prompt-byte-grammar.md` 规则 6 的来源句。
- **保留（证据/审查层）**：`narrative-and-storyboard.md` / `brief-and-research.md` 的 `source_ids` 映射；`qa-and-revision.md` 的 `fact_source_consistency`；`svg-contract.md` 的 `data-source-id` 机器 trace 元数据。

## 4. 受影响文件

- `skills/ppt-start/assets/styles/<new-style>/tokens.json`（`prompt_baseline` 扩展 + schema v2）
- `skills/ppt-start/assets/styles/<new-style>/STYLE.md`
- `skills/ppt-start/assets/styles/<new-style>/manifest.json`
- `skills/ppt-start/assets/styles/registry.json`
- `skills/ppt-start/references/generation-prompt-template.md`（删第 29 行）
- `skills/ppt-start/references/generation-prompt-byte-grammar.md`（规则 6 删来源句）
- `skills/ppt-start/references/design-system.md`（扩展 prompt_baseline 描述）
- `tests/test_redesign_prompt_contract.py`（_canonical_template_segments 保留；改第 202-203 行的"全部文档须含 SRC"断言为"输出层不得含、证据层须含"；改 SRC 相关测试）
- `tests/fixtures/generation-prompt-snapshot.json`、`style-prompt-resolution-cases.json`
- `tests/test_style_packs.py`、`test_skill_package.py`（扩展 prompt_baseline 结构断言）

## 5. 质量门

- 新"嘉为产品"style 编译出的 prompt：含自定义视觉/结构指令且正文无 `SRC-<digits>`/`data-source-id`/来源标记。
- 现有 canway 等 style：仍用默认模板 + 既有 prompt_baseline，向后兼容。
- 全量契约测试通过（4 个既有 Get-FileHash 沙箱边界失败除外）。
