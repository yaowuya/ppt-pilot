# 推翻范式：Style 自带完整 Prompt 模板 实施计划

> **SUPERSEDED（历史实施稿）：** 本计划已由当前活动契约取代，仅保留审计轨迹。新运行必须使用 style-owned 必需模板、单 whole-line `{{NARRATIVE}}`、闭合 tokens 精确绑定、冻结故事板 `block_id` 集合校验与稳定 blocker reason；不得执行本文未完成复选框或 fallback 备选项。

> **面向 Agent 执行者：** 必需子技能：使用 superpower-subagent-driven-development（推荐）或 superpower-executing-plans 按任务逐项执行本计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 以"每个 style 自带完整 `prompt.md` 模板 + 单个 `{{NARRATIVE}}` 注入点 + 叙事去 source"取代现有"canonical `generation-prompt-template.md` + 两 marker（`[[CANONICAL_NARRATIVE_BULLETS]]`/`[[STYLE_BASELINE]]`）"的编译范式。所有 5 个内置 style（minimal-business/tech-dark/bold-editorial/canway-midyear-review/jiawei-product）各自声明 `files.prompt_template` 并提供完整生成指令；原 3 个 legacy_seed 迁移为 style_pack；canonical 两 marker 机制移除。

**架构：** 编译读取所选 style 的 `prompt.md`（来自其 manifest 声明的 `files.prompt_template`），把规范化叙事注入模板内唯一一次出现的 `{{NARRATIVE}}`；叙事不含 `source=`/`[claim=...source=[...]]`。`prompt_baseline` 保留在 tokens.json 作为风格数据，不再作为第二个注入域。

**技术栈：** Python 3 + unittest（仓库测试）；JSON（manifest/tokens/golden fixtures）；Markdown 契约文档（byte-grammar/visual-brief/design-system/SKILL.md）。

**规格：** `docs/superpowers/specs/2026-09-01-style-own-prompt-template-b-design.md`（用户已确认方向：方案B、全部自带、legacy_seed 迁移为 style_pack、去 source、只改仓库不改项目脚本）。

## 全局约束

- 只改仓库（`skills/ppt-start`、`tests`、`docs`），不改用户项目 `D:\05-AI\FY26H1-test\ppt-output\...\compile_prompt.py`。
- 任何 style 编译出的 prompt 不得含 `source=`、`SRC-<digits>`、`data-source-id`、`[[STYLE_BASELINE]]`、`[[CANONICAL_NARRATIVE_BULLETS]]`、`{{NARRATIVE}}`（注入后不得残留）。
- 源文件统一 UTF-8；JSON 文件缩进 2 空格；蛇形文件名。
- 保留证据层来源语义：`svg-contract.md`/`qa-and-revision.md`/`narrative-and-storyboard.md` 中的 `source_ids`/`fact_source_consistency` 不动。
- SVG 模板正文的 Office-safe 硬契约（`<svg viewBox="0 0 1280 720">`、`<path>`+`A` 圆角、禁 `<rect rx>`、文本用 `<text>`/`<tspan>`、禁 `foreignObject`）必须保留。
- 全量测试目标：通过（4 个既有 `Get-FileHash` 沙箱边界失败除外）。
- 每个任务结束时运行其对应测试用例确认通过，并提交。

---

### 任务 1：编写失败测试——`compile_style_prompt` 支持按 style 模板注入

**文件：**
- 测试：`tests/test_redesign_prompt_contract.py`（新增方法，靠近现有 `test_style_owned_prompt_template_compiles_and_carries_no_source`）
- 实现（本任务尚不存在的函数）：`compile_style_prompt(narrative_bullets: bytes, template_bytes: bytes) -> bytes`

**接口：**
- 依赖输入：无（本任务是 TDD 红盘，先写测试）。
- 对外产出：`compile_style_prompt(narrative_bullets, template_bytes)` —— 注入唯一的 `{{NARRATIVE}}`，模板含该 token 恰好一次，否则抛 `ValueError("prompt_template_invalid")`；叙事含 `source=`/`[claim=` 抛 `ValueError("prompt_preflight_invalid")`。

- [ ] **步骤 1：编写失败的测试**（追加到 test_redesign_prompt_contract.py 的 `RedesignPromptContractTests` 类，替换或扩展现有同名测试，使断言明确覆盖"按 style 模板 + 单注入点 + 无来源"）：

```python
def test_style_owned_template_compiles_and_rejects_source(self):
    template_path = skill_root() / "assets" / "styles" / "jiawei-product" / "prompt.md"
    template_bytes = normalize_lf(template_path.read_bytes())
    narrative = (
        "- **金字塔原理**: 核心主标题：嘉为自动化运维平台 · 产品能力全景；分论点：底座能力、AI 提效、专项交付、决策诉求。\n"
        "- **精确表达**: 保留显示文案、事实、数字、单位、限定词。\n"
        "- **层级执行**: 核心信息放大展示。\n"
    ).encode("utf-8")
    body = compile_style_prompt(narrative, template_bytes)
    self.assertIn("# Role:产品经理& SVG 可视化编码专家".encode("utf-8"), body)
    self.assertIn("### 步骤 2: 匹配 Bento Grid".encode("utf-8"), body)
    self.assertNotIn(b"{{NARRATIVE}}", body)
    self.assertNotIn(b"[[STYLE_BASELINE]]", body)
    self.assertNotIn(b"[[CANONICAL_NARRATIVE_BULLETS]]", body)
    self.assertNotIn(b"source=", body)
    self.assertNotIn(b"SRC-", body)
    with_source = '- 块 P1（core） [claim=B1 source=["SRC-002"]]\n'.encode("utf-8")
    with self.assertRaisesRegex(ValueError, "^prompt_preflight_invalid$"):
        compile_style_prompt(with_source, template_bytes)
    from_zero = template_bytes.replace(b"{{NARRATIVE}}", b"")
    with self.assertRaisesRegex(ValueError, "^prompt_template_invalid$"):
        compile_style_prompt(b"- sample\n", from_zero)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_style_owned_template_compiles_and_rejects_source -v`（从 `D:\01-code\ppt-pilot`）
预期：失败，提示 `compile_style_prompt` 未定义（若函数已存在并曾通过，先删除旧实现再进入本任务）。

- [ ] **步骤 3：编写最小实现**（确保 `compile_style_prompt` 已存在并满足：模板 `{{NARRATIVE}}` 恰好一次；叙事 `_reject_unsafe_replacement` + 拒 source；body 无遗留 marker）：

```python
STYLE_NARRATIVE_TOKEN = b"{{NARRATIVE}}"

def compile_style_prompt(narrative_bullets: bytes, template_bytes: bytes) -> bytes:
    narrative = _reject_unsafe_replacement(narrative_bullets)
    template = normalize_lf(template_bytes)
    if template.count(STYLE_NARRATIVE_TOKEN) != 1:
        raise ValueError("prompt_template_invalid")
    if b"source=" in narrative or b"[claim=" in narrative:
        raise ValueError("prompt_preflight_invalid")
    body = normalize_lf(template.replace(STYLE_NARRATIVE_TOKEN, narrative))
    if not body.endswith(b"\n"):
        body += b"\n"
    if b"[[STYLE_BASELINE]]" in body or b"[[CANONICAL_NARRATIVE_BULLETS]]" in body or b"{{NARRATIVE}}" in body:
        raise ValueError("prompt_preflight_invalid")
    return body
```

注意：`narrative` 含 `source=`/`[claim=` 时 `_reject_unsafe_replacement` 本身不会拒绝（它只拒 `[[...]]`/多级标题/绝对路径等），但上一步 `_reject_unsafe_replacement` 仍应先行调用以保证安全，再叠加 source 门禁。

- [ ] **步骤 4：运行测试并确认其通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_style_owned_template_compiles_and_rejects_source -v`
预期：PASS。

- [ ] **步骤 5：提交**

```bash
git add tests/test_redesign_prompt_contract.py
git commit -m "test(contracts): style-owned prompt template compiles and rejects source"
```

---

### 任务 2：迁移 3 个 legacy_seed 为 style_pack（minimal-business/tech-dark/bold-editorial）

**文件：**
- 新建：`skills/ppt-start/assets/styles/minimal-business/{manifest.json,tokens.json,STYLE.md,prompt.md}`（同理 tech-dark、bold-editorial）
- 修改：`skills/ppt-start/assets/styles/registry.json`（把 min/tech/bold 的 `"kind": "legacy_seed"` 改为 `"style_pack"`，entrypoint 改为 style_pack 目录结构）
- 修改：`skills/ppt-start/assets/styles/minimal-business.json`、`tech-dark.json`、`bold-editorial.json`（若 registry 不再引用则删除或作为迁移来源保留）

**接口：**
- 依赖输入：任务 1 的 `compile_style_prompt`（模板格式）。
- 对外产出：3 个版式的 style_pack 资产：`files = {tokens, guidancy, prompt_template}`，`kind="style_pack"`，每个 `prompt.md` 含唯一 `{{NARRATIVE}}`。

- [ ] **步骤 1：为每个版式创建子目录结构**（以 minimal-business 为例；tech/bold 同构，仅视觉值/文案不同）：

`minimal-business/manifest.json`：
```json
{
  "schema_version": 1,
  "id": "minimal-business",
  "display_name": "极简商务",
  "version": "1.0.0",
  "kind": "style_pack",
  "default": false,
  "summary": "极简商务风格：白底、大留白、克制配色、清晰层级。",
  "recommended_for": ["专业商务汇报", "简洁方案说明", "管理周报/月报"],
  "not_for": ["营销海报", "重数据大屏"],
  "selection_aliases": ["minimal-business", "极简商务"],
  "files": { "tokens": "tokens.json", "guidance": "STYLE.md", "prompt_template": "prompt.md" },
  "compatibility": { "office_safe_svg": true, "canvas": "1280x720", "languages": ["zh-CN"] }
}
```

`minimal-business/tokens.json`：把 `minimal-business.json` 的 `colors/typography/spacing/shape` 迁入，并补 `schema_version: 2`、`id`、`display_name`、`prompt_baseline`（palette_roles/font_stack/spacing_rhythm/shape_language/composition_rules/prohibited_motifs）。

`minimal-business/STYLE.md`：一行说明 + 视觉摘要（白底 #FFFFFF、表面 #F2F6F8、主导 #163B52、强调 #E06B45、Title 4/body20/footnote14、66 margin/24 gap/24 pad、圆角12/描边1.5）。

`minimal-business/prompt.md`：完整生成指令（信息架构师/编辑者角色 + 三步 Workflow + 极简商务视觉规范 + `{{NARRATIVE}}` 注入点 + Office-safe 硬契约段 + `---` 分隔 + "只返回一个 ```xml 围栏"结尾）。参照 `skills/ppt-start/assets/styles/canway-midyear-review/prompt.md` 结构与视觉值的占位对应关系。

- [ ] **步骤 2：更新 registry.json**：把 minimal-business/tech-dark/bold-editorial 的 kind 改为 `"style_pack"`，并把 entrypoint 从单文件改为对应子目录（确认 registry 对 style_pack 的 manifest 字段读取逻辑）；保留选择别名。

- [ ] **步骤 3：删除（或归档）旧的根目录单文件** `minimal-business.json`/`tech-dark.json`/`bold-editorial.json`（若 registry/测试仍引用则先改引用）。

- [ ] **步骤 4：运行相关测试并确认通过**

运行：`python -m unittest tests.test_style_packs tests.test_skill_package -v`
预期：通过；若有测试断言 legacy_seed kind 或根目录 entrypoint，需在后期任务一并迁移（此处先确认 failure 可归因于预期差异）。

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/assets/styles/minimal-business skills/ppt-start/assets/styles/tech-dark skills/ppt-start/assets/styles/bold-editorial skills/ppt-start/assets/styles/registry.json
git commit -m "feat(styles): migrate minimal/tech/bold legacy_seed to style_pack with owned prompt template"
```

---

### 任务 3：改写 resolver `resolve_style_case` 支持 `files.prompt_template` 并附模板路径

**文件：**
- 修改：`tests/test_redesign_prompt_contract.py`（`resolve_style_case` 函数，约 1027-1134；`_resolved_style` 约 957；`RESOLVED_STYLE_KEYS`/失败原因常量）
- 测试：`tests/test_redesign_prompt_contract.py`（新增解析断言）`tests/fixtures/style-prompt-resolution-cases.json`（可加用例）

**接口：**
- 依赖输入：任务 2 的 style_pack 资产（manifest `files.prompt_template`）。
- 对外产出：`resolve_style_case(case)` 返回 dict 含模板路径（如 `template_path` 或 `resolved_generation_prompt_template_path` 指向该 style 的 `prompt.md`）。

- [ ] **步骤 1：编写/更新解析测试**（验证 manifest 含 `tokens`+`guidance`+可选 `prompt_template`；`prompt_template` 文件存在；缺失 `tokens`/`guidance` 抛 `prompt_template_invalid`）：

```python
def test_style_pack_resolves_prompt_template_path_and_completeness(self):
    for dirname in ("minimal-business", "tech-dark", "bold-editorial", "canway-midyear-review", "jiawei-product"):
        manifest_path = skill_root() / "assets" / "styles" / dirname / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "style_pack")
        self.assertIn("tokens", manifest["files"])
        self.assertIn("guidance", manifest["files"])
        self.assertIn("prompt_template", manifest["files"])
        prompt_path = skill_root() / "assets" / "styles" / dirname / manifest["files"]["prompt_template"]
        self.assertTrue(prompt_path.is_file())
        prompt = prompt_path.read_text(encoding="utf-8")
        self.assertEqual(prompt.count("{{NARRATIVE}}"), 1)
```

- [ ] **步骤 2：运行测试并确认其失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_style_pack_resolves_prompt_template_path_and_completeness -v`
预期：失败（manifest kind/字段不符或 prompt.md 缺失），据此修补。

- [ ] **步骤 3：实现 resolver 改动**。在 `resolve_style_case` 内：当 `kind == "style_pack"` 时读取 `manifest["files"]`，校验含 `tokens`+`guidance`（可选 `prompt_template`），校验引用的文件路径均在 style 目录内（防路径逃逸，参照现有 `_resource`/路径安全校验），在返回结果附模板路径。

- [ ] **步骤 4：运行测试并确认通过**（含既有解析/安全测试回退）。

运行：`python -m unittest tests.test_redesign_prompt_contract -v`
预期：PASS（含本任务新增 + 既有契约测试）。

- [ ] **步骤 5：提交**

```bash
git add tests/test_redesign_prompt_contract.py tests/fixtures/style-prompt-resolution-cases.json
git commit -m "feat(resolver): resolve_style_case validates files.prompt_template and returns template path"
```

---

### 任务 4：改写 byte-grammar 规则 1/3/4/8/10 + 契约文档 + SKILL.md 同步

**文件：**
- 修改：`skills/ppt-start/references/generation-prompt-byte-grammar.md`（规则1/3/4/8/10）
- 修改：`skills/ppt-start/references/visual-brief-and-generation.md`
- 修改：`skills/ppt-start/references/design-system.md`
- 修改：`skills/ppt-start/SKILL.md`（步骤 6/37）

**接口：**
- 依赖输入：任务 1/3 的 `{{NARRATIVE}}` 注入点与 resolver 模板路径语义。
- 对外产出：契约文档描述新范式（按 style 模板 + 单注点 + 去来源），删除两 marker 描述。

- [ ] **步骤 1：改写规则** `generation-prompt-byte-grammar.md`：

规则 3 改为：编译读取所选 style 的 `manifest["files"]["prompt_template"]`（无则报 `prompt_template_invalid`）；模板含唯一 `{{NARRATIVE}}`；禁 `[[CANONICAL_NARRATIVE_BULLETS]]`/`[[STYLE_BASELINE]]`/`EFFECTIVE_PAGE_SPECIFICATION`；注入的叙事去 source。规则 1/4/8/10：把"唯一 canonical 模板 + 两 marker + three static segments"改为"按 style 模板 + 单注点 + 来源标记不入 prompt"；删除/改写任何"prompt_snapshot_conflict（非 canonical 路径）"语义为"按所选 style 模板路径"。

- [ ] **步骤 2：同步** `visual-brief-and-generation.md`、`design-system.md`、`SKILL.md`（把"通过 `[[STYLE_BASELINE]]` 投影注入"改为"style 自带模板 + `{{NARRATIVE}}` 注入叙事"；提及可选视觉/结构小节由 style 模板正文承载）。

- [ ] **步骤 3：运行相关测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract -v`
预期：PASS。

- [ ] **步骤 4：提交**

```bash
git add skills/ppt-start/references/generation-prompt-byte-grammar.md skills/ppt-start/references/visual-brief-and-generation.md skills/ppt-start/references/design-system.md skills/ppt-start/SKILL.md
git commit -m "docs(contracts): style-owned template + single {{NARRATIVE}} injection + no source in prompt"
```

---

### 任务 5：改写编译核心 `_canonical_segments`/`_canonical_template_bytes`/`validate`/`render` 为按 style 模板 + 单注点

**文件：**
- 修改：`tests/test_redesign_prompt_contract.py`（`_canonical_template_segments` 610-628、`_canonical_template_bytes` 531、`compile_prompt_body`、`validate_compiled_prompt_body` 640-660、`_render_generation_prompt_fixture` 1488、`_validate_canonical_template_path` 535）
- 金样：`tests/fixtures/generation-prompt-snapshot.json`、`style-prompt-resolution-cases.json`
- 实现文件：`skills/ppt-start/references/generation-prompt-template.md`（移除/改示例）

**接口：**
- 依赖输入：任务 1 的 `compile_style_prompt`（主路径）、任务 3 的 resolver 模板路径。
- 对外产出：`compile_prompt_body(narrative_bullets, style_id_or_template)` 走新范式；`render_generation_prompt` 用 style 模板路径快照 id；`validate_compiled_prompt_body` 校验"按 style 模板 + `{{NARRATIVE}}` 恰好一次 + 无来源"。

- [ ] **步骤 1：重构** `_canonical_template_segments` 为 `_style_template_segments(style_dir, template_filename)` 或 `resolve_style_template_bytes(style_id)`：从 manifest 读 `files.prompt_template`，校验恰含一个 `{{NARRATIVE}}`，返回模板字节与其分片。

- [ ] **步骤 2：改 `validate_compiled_prompt_body`**：从"三静态段 + 两替换域 + 两 marker 恰好一次"改为"body 由 style 模板以 `{{NARRATIVE}}` 替换叙事得到、无遗留 marker、无 source"。

- [ ] **步骤 3：改 `_render_generation_prompt_fixture`**：`_validate_canonical_template_path`→校验 `snapshot_inputs["resolved_generation_prompt_template_path"]` 等于所选 style 的 `prompt.md` 相对路径；`template_bytes`→`resolve_style_template_bytes(style_id)`；`canonical_payload["generation_prompt_template_snapshot_id"]` 用该 style 模板字节的 sha256。

- [ ] **步骤 4：更新 `generation-prompt-snapshot.json`**：`resolved_generation_prompt_template_path`、`generation_prompt_template_snapshot_id`、`compiled_prompt_sha256`、`style_baseline`（去 `[[STYLE_BASELINE]]` 投影概念）、`expected` 的 body/base64/sha256/envelope/canonical_payload_json 等全部重算（先用临时脚本按新 `_render_generation_prompt_fixture` 生成再写回，脚本用完删除）。

- [ ] **步骤 5：运行测试并确认通过**（金样 oracle + 契约全量）

运行：`python -m unittest tests.test_redesign_prompt_contract -v`
预期：PASS（若 `test_generation_prompt_snapshot_matches_golden_fixture`/`test_generation_prompt_fixture_is_a_full_byte_oracle`/`test_provenance_assertion_slices_only_provenance_section` 仍失败，重新生成 golden 并核对 diff）。

- [ ] **步骤 6：提交**

```bash
git add tests/test_redesign_prompt_contract.py tests/fixtures/generation-prompt-snapshot.json tests/fixtures/style-prompt-resolution-cases.json skills/ppt-start/references/generation-prompt-template.md
git commit -m "feat(compile): compile core uses style-owned template with single {{NARRATIVE}} injection"
```

---

### 任务 6：改写来源（source）相关测试与叙事注入金样

**文件：**
- 修改：`tests/test_redesign_prompt_contract.py`（`test_internal_source_ids_are_machine_only_across_generation_contract`，约 184；输出层断言，确保 style 模板编译产物无 `data-source-id`/`SRC-`/`source`）
- 修改：证据层保留（`svg-contract.md`/`qa-and-revision.md`/`narrative-and-storyboard.md` 不动）。

**接口：**
- 依赖输入：任务 1/5 的编译产物。
- 对外产出：确认输出层（style 模板编译）无任何来源标记，证据层仍保留 `data-source-id`/`source_ids`/`fact_source_consistency`。

- [ ] **步骤 1：检查/更新 `test_internal_source_ids_are_machine_only_across_generation_contract`**：输出层断言（canonical/byte-grammar/编译产物不含 `data-source-id`/`SRC-`/`source=`）应继续 pass；若断言依赖 `generation-prompt-template.md` 或两 marker，改为依赖任一 style 模板编译产物。

- [ ] **步骤 2：运行测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_internal_source_ids_are_machine_only_across_generation_contract -v`
预期：PASS。

- [ ] **步骤 3：提交**

```bash
git add tests/test_redesign_prompt_contract.py
git commit -m "test(contracts): source ids remain machine-only, absent from style-owned prompt output"
```

---

### 任务 7：迁移 visual/风格测试与金样（去 source / 新解析 / 新编译）

**文件：**
- 修改：`tests/test_style_packs.py`（`test_manifest_references_complete_style_identity_pack` 79 行 `set(manifest["files"])=={"tokens","guidance"}` 改为含 `prompt_template`；`test_tokens_use_schema_v2_and_have_structured_baseline` 保留）
- 修改：`tests/test_visual_generation_contract.py`（若引用两 marker/canonical）
- 金样：`tests/fixtures/style-prompt-resolution-cases.json`、`visual-generation-batch-v2-cases.json`（涉及 `generation_prompt_template_snapshot_id` 等）

**接口：**
- 依赖输入：前面的样式资产与编译核心。
- 对外产出：全部风格/视觉测试通过。

- [ ] **步骤 1：改 `test_style_packs.py`**：将 `set(manifest["files"])` 断言扩展为 `{"tokens","guidance","prompt_template"}`（canway 等已声明）；`test_jiawei_product_tokens_expose_extended_visual_structure` 保留。

- [ ] **步骤 2：迁移 `test_visual_generation_contract.py`**：若其依赖两 marker 或 `style_baseline` 投影，改为依赖 style 模板 + 单注点；更新 `visual-generation-batch-v2-cases.json` 中 `generation_prompt_template_snapshot_id`/`compiled_prompt_sha256` 等派生字段（用临时脚本重算后写回并删除脚本）。

- [ ] **步骤 3：运行相关测试并确认通过**

运行：`python -m unittest tests.test_style_packs tests.test_visual_generation_contract tests.test_skill_package -v`
预期：PASS。

- [ ] **步骤 4：提交**

```bash
git add tests/test_style_packs.py tests/test_visual_generation_contract.py tests/fixtures/style-prompt-resolution-cases.json tests/fixtures/visual-generation-batch-v2-cases.json
git commit -m "test(styles/visual): migrate to style-owned template and no-source golden fields"
```

---

### 任务 8：移除 canonical 两 marker 机制与 `generation-prompt-template.md`

**文件：**
- 删除/改写：`skills/ppt-start/references/generation-prompt-template.md`（若不再作为任何 style 的模板，则删除；若保留作"无 style 模板 Fallback"则改为例示式、去掉两 marker）
- 修改：`tests/test_redesign_prompt_contract.py`（凡引用 `CANONICAL_GENERATION_TEMPLATE_PATH`/`_canonical_template_bytes`/两 marker 的测试改为引用 style 模板）
- 修改：`skills/ppt-start/references/visual-brief-and-generation.md`、`design-system.md`、`SKILL.md`（清除两 marker 描述）

**接口：**
- 依赖输入：前面任务全部完成。
- 对外产出：仓库不再依赖 canonical 模板 + 两 marker；`generation-prompt-template.md` 视决策删除或改示例。

- [ ] **步骤 1：清除所有两 marker 引用**：在 `tests/test_redesign_prompt_contract.py` 与契约文档中，把 `CANONICAL_NARRATIVE_BULLETS_TOKEN`/`STYLE_BASELINE_TOKEN`/`EFFECTIVE_PAGE_SPECIFICATION_TOKEN`/`_canonical_template_bytes`/`_canonical_template_segments`/`CANONICAL_GENERATION_TEMPLATE_PATH` 的依赖改为 style 模板 + `{{NARRATIVE}}`。

- [ ] **步骤 2：处理 `generation-prompt-template.md`**：确认无任何 style 引用后删除；若保留则改为不含两 marker 的模板示例。

- [ ] **步骤 3：运行全量契约测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract -v`
预期：PASS。

- [ ] **步骤 4：提交**

```bash
git add skills/ppt-start/references/generation-prompt-template.md tests/test_redesign_prompt_contract.py skills/ppt-start/references/visual-brief-and-generation.md skills/ppt-start/references/design-system.md skills/ppt-start/SKILL.md
git commit -m "refactor(contracts): remove canonical two-marker template mechanism"
```

---

### 任务 9：全量回归与最终评审

**文件：** 无新增（仅验证）。

**接口：**
- 依赖输入：全部任务完成。

- [ ] **步骤 1：全量测试**

运行：`python -m unittest discover -s tests 2>&1 | Select-String -Pattern 'Ran |FAILED|^OK'`
预期：`OK`（至多 4 个既有 `Get-FileHash` 沙箱边界失败）。

- [ ] **步骤 2：验证任一 style 编译无来源**：用 `compile_style_prompt` 对每个 style 的 prompt.md 编译一份叙事，断言无 `source=`/`SRC-`/`data-source-id`/两 marker；用临时脚本执行后删除。

- [ ] **步骤 3：提交收尾**（工作区干净，确认 HEAD 与远程 ahead/behind 合理）

```bash
git status --porcelain
git log --oneline -8
```

- [ ] **步骤 4：用 superpower-requesting-code-review 评审本分支，处理 HIGH 级意见后进入 final review 收尾。**

---

## 自检（已由计划作者执行）

- **规格覆盖度：** 已对照 `2026-09-01-style-own-prompt-template-b-design.md` 各节：§1 资产（任务2/4）✓；§2 编译核心（任务1/5）✓；§3 resolver（任务3）✓；§4 去 source（任务6/7）✓；§5 受影响面（任务4/5/7/8）✓；§6 里程碑（映射到任务1-9）✓。`prompt_baseline` 保留为风格数据（规格§1.3）✓。
- **占位符扫描：** 无 TBD/TODO；每个含代码的任务均给出实际代码/路径/命令。
- **类型一致性：** `compile_style_prompt(narrative_bullets: bytes, template_bytes: bytes) -> bytes` 在任务1定义并被任务5复用；`files.prompt_template` 命名在任务2/3/7 一致；`{{NARRATIVE}}` 注入点命名一致；`resolve_style_case` 返回的模板路径字段名在任务3/5 一致（据现有 `resolved_generation_prompt_template_path` 键沿用）。
