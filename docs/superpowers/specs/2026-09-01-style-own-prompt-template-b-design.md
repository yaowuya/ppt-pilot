# 方案B：Style 自带完整 Prompt 模板（核心重构）

> 用户方向（已确认）：PPT Pilot 改为"每个 style 自带完整 prompt 模板"。嘉为产品（jiawei-product）用用户原文（Safety/语法合规化）；现有 4 个 style（minimal-business/tech-dark/bold-editorial/canway-midyear-review）也全部改为自带完整模板，由我按各风格设计生成指令。输入用"规范化叙事（去 source）"。原有 canonical `generation-prompt-template.md` 与两 marker 机制被移除/降级。

## 0. 目标范式变化

现在：`canonical 模板（固定 Role/Workflow/三步）+ 恰两 marker 替换域`。
改为：`style 自带完整生成指令模板 + 一个统一叙事注入点`。

- **模板所有权**：每个 style 的 `manifest.json` 声明可选 `files.prompt_template`；编译用该模板。
- **统一注入点**：模板内用 `{{NARRATIVE}}`（唯一且必填一次）作为规范化叙事注入点。原 `[[CANONICAL_NARRATIVE_BULLETS]]`/`[[STYLE_BASELINE]]` 两 marker 废弃。style 模板无需 `[[STYLE_BASELINE]]`（视觉规范已内嵌在模板正文）。
- **叙事去 source**：注入的规范化叙事**不含** `source=`/`[claim=...source=[...]]` 字段；来源映射仅保留在审查层（`source_ids` 留在故事板/`qa-and-revision`），不入 prompt。
- **无 style 模板时**：默认回落 canonical 模板（兼容/兜底；本方案所有内置 style 都声明模板，故 canonical 仅作迁出与兜底）。

## 1. 新增/修改的资产

### 1.1 `manifest.json` 新增 `files.prompt_template`

```jsonc
{ "files": { "tokens": "tokens.json", "guidance": "STYLE.md", "prompt_template": "prompt.md" } }
```

### 1.2 每个 style 新增 `prompt.md`（完整生成指令）

- `jiawei-product/prompt.md`：用户原文 + Safety 合规化（圆角统一 `path+A`、`<rect rx>` 改写为 `path+A`、保留产品经理角色/提纯重构/Bento布局库/完整视觉规范/标题规范/右上角无logo 等）。
- `minimal-business/prompt.md`、`tech-dark/prompt.md`、`bold-editorial/prompt.md`、`canway-midyear-review/prompt.md`：按各风格命名与视觉设计的完整生成指令模板（信息架构师/编辑者角色 + 三步 + 各自视觉规范 + `{{NARRATIVE}}` 注入点）。

### 1.3 `tokens.json` 的 `prompt_baseline`

`[[STYLE_BASELINE]]` 不再注入，`prompt_baseline` 降为**不再是编译必需**；但保留 tokens（颜色字体等）供 QA / 语义参考，`prompt_baseline` 字段可保留作为风格数据（不再被两个 marker 使用）。嘉为产品视觉规范直接在模板正文，不必依赖 `prompt_baseline`。

## 2. 编译核心（仓库测试 oracle）改动

- `compile_prompt_body(narrative_bullets, style_baseline)` → 改为 `compile_prompt_body(narrative_bullets, template_path)` 或 `compile_style_prompt(narrative_bullets, style_id)`：读取所选 style 的 `prompt.md`，注入 `{{NARRATIVE}}` 一次。
- `_canonical_template_segments()` 需支持"style 模板"（从 manifest 解析 `files.prompt_template`）。
- `validate_compiled_prompt_body` 的"三静态段 + 两替换域 + 两 marker 恰好一次"校验改为"按所选 style 模板 + `{{NARRATIVE}}` 恰好一次"。
- byte-grammar 规则 1/3/4/8/10：把"唯一 canonical 模板 + 两 marker + three static segments"重构为"按 style 模板 + 单注入点 + 来源标记不入 prompt"。

## 3. resolver 改动

`resolve_style_case`：
- 校验 manifest `files` 含 `tokens` + `guidance`（+ 可选 `prompt_template`），并校验其路径安全/一致。
- 解析结果附带所选 style 的模板路径（若声明）。

## 4. 来源（source）移除

- 叙事要点注入文本不再含 `source=`/`[claim=...source=[...]]`。
- `generation-prompt-snapshot.json`、`style-prompt-resolution-cases.json` 的叙事金样去掉 source 字段。
- 保留 `svg-contract.md` / `qa-and-revision.md` / `narrative-and-storyboard.md` 的 `source_ids`/`fact_source_consistency`（证据层）。

## 5. 受影响面（全部重建）

- `skills/ppt-start/references/generation-prompt-byte-grammar.md`（规则1/3/4/8/10）
- `skills/ppt-start/references/generation-prompt-template.md`（迁出，或改为例示）
- `skills/ppt-start/references/visual-brief-and-generation.md`、`design-system.md`
- `skills/ppt-start/SKILL.md`（步骤6/37）
- `skills/ppt-start/assets/styles/*/prompt.md` ×5（新增）
- `skills/ppt-start/assets/styles/*/manifest.json` ×4（加 `files.prompt_template`）+ registry
- `tests/test_redesign_prompt_contract.py`（编译/解析/校验/来源断言改写）
- `tests/fixtures/generation-prompt-snapshot.json`、`style-prompt-resolution-cases.json`
- `tests/test_style_packs.py`、`test_skill_package.py`、`test_visual_generation_contract.py`

## 6. 里程碑

- **M1 契约**：byte-grammar 规则改为"style 自带模板 + 单 `{{NARRATIVE}}` 注入点 + 无来源标记"；visual-brief/design-system/SKILL.md 同步。
- **M2 编译核心**：`compile_prompt_body` 改按 style 模板；`_canonical_segments`/`validate`/`render` 重构。
- **M3 resolver**：manifest 加 `files.prompt_template`；`resolve_style_case` 校验并返回模板路径。
- **M4 资产**：写 5 个 style 的 `prompt.md`（嘉为=用户原文+合规化；现有4风格=我设计）。
- **M5 测试与金样**：更新 oracle 测试、金样（去 source）、新 style 解析断言、编译断言。
- **M6 回归**：全量测试（4 个既有 Get-FileHash 失败除外）。

## 7. 关键约定（需你确认）

1. 统一注入点用 **`{{NARRATIVE}}`**（单次、必填）替代原两 marker。是否接受该语法？
2. 现有 4 个 style 的 `prompt.md` 由我**设计**（给出各自 Role/Workflow/视觉规范的完整生成指令），完成后你评审。是否接受？
3. `prompt_baseline` 保留在 tokens.json（不再被编译使用，仅作为风格数据）。可接受？
