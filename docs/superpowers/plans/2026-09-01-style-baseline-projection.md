# Style Baseline Projection Implementation Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

> **面向 Agent 执行者：** 必需子技能：使用 superpower-subagent-driven-development（推荐）或 superpower-executing-plans 按任务逐项执行本计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 把风格软基线从“手写 token 串 + 散文双写数字”改为“`tokens.json.prompt_baseline` 结构数据 + 确定性 `StyleBaselineCompiler` 投影”，保证跨宿主字节级一致的 `style_baseline` 与 `style_baseline_snapshot_id`。

**架构：** 引入 `tokens.json`（`schema_version: 2`，新增 `prompt_baseline`），由 Skill 拥有的无状态 `StyleBaselineCompiler` 把风格资产渲染成规范 `style_baseline`；`STYLE.md` 只保留语义判断与禁止项的人类可读说明，移除与 `prompt_baseline` 重复的硬数值；相关契约文档、测试解析 oracle 与金样同步调整。只在 `canway-midyear-review` 资产上启用，不改运行时生成逻辑、不新增第三个替换域、不把可执行 prompt 还给风格包。

**技术栈：** Markdown 契约文档（无运行时代码）、Python unittest 契约测试、git。

**规格：** `docs/superpowers/specs/2026-09-01-style-baseline-projection-design.md`——计划论证以规格为准，规格随计划一同流转，执行者需同时阅读两者。

## 全局约束

- 模板唯一编译源与字节语法权威不变：`skills/ppt-start/references/generation-prompt-template.md`、`skills/ppt-start/references/generation-prompt-byte-grammar.md`
- 模板保持恰好两个 whole-line marker：`[[CANONICAL_NARRATIVE_BULLETS]]` + `[[STYLE_BASELINE]]`；禁止新增第三个动态替换域（`generation-prompt-byte-grammar.md:9`）
- `style_baseline` 仍是软方向、不是逐项锁定令牌；画布/安全区/圆角 path+A/Office-safe 等硬契约仍在模板步骤 3（`generation-prompt-template.md:24-31`）
- `schema_version`：`tokens.json`（`canway-midyear-review`）升到 2；三个 `legacy_seed`（`minimal-business` 等）保持 1，不得改动其 `style_baseline_snapshot_id` 基准与 fallback identity table（`design-system.md:31-39`）
- `style_baseline_snapshot_id` = SHA-256(规范化 `style_baseline` 字节)，定义沿用 `generation-prompt-byte-grammar.md:16`
- `StyleBaselineCompiler` 是纯函数、无状态、无运行时副作用；风格资产不拥有可执行 prompt 正文（`generation-prompt-byte-grammar.md:7`）
- 全部文本先转纯文本并转义 `&`、`<`、`>`、`"`、`'`；禁止注入 `[[...]]` marker、Markdown 标题、JSON 围栏、绝对路径、外部指令（沿用 `_reject_unsafe_replacement` 约束，`tests/test_redesign_prompt_contract.py:592`）
- 风格解析 oracle（`tests/test_redesign_prompt_contract.py::resolve_style_case`）是“宿主解析该契约”的模拟；让 style pack tokens 接受 `schema_version: 2` 需要同步扩展它，失败态仍为 `style_asset_schema_unsupported`（reason 枚举不变）
- 提交信息使用仓库既有风格（`feat(contracts):` / `docs(spec):` / `test(contracts):` 前缀），逐任务原子提交
- 演示用运行目录（`ppt-output/demo-gate-check/`、旧 `D:\05-AI\...` 运行）不是契约测试目标，不修改

---

### 任务 1：重写 Style Baseline 投影契约（byte-grammar / design-system / visual-brief）

**文件：**
- 修改：`skills/ppt-start/references/generation-prompt-byte-grammar.md:9,16`
- 修改：`skills/ppt-start/references/design-system.md:55`
- 修改：`skills/ppt-start/references/visual-brief-and-generation.md:14,20,27`
- 测试：`tests/test_redesign_prompt_contract.py`（新增类内断言）

**接口：**
- 依赖输入：现有两域模板（金样 `generation-prompt-snapshot.json`）；`tokens.json`（目标 `schema_version: 2`，下一任务迁移）
- 对外产出：`style_baseline` 的确定性输入源明确为 `tokens.json.prompt_baseline`；后续任务据此改写金样与测试

- [ ] **步骤 1：写失败测试断言新契约措辞**

在 `tests/test_redesign_prompt_contract.py` 的 `RedesignPromptContractTests` 类后新增：

```python
class StyleBaselineProjectionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.grammar = skill_root() / "references" / "generation-prompt-byte-grammar.md"
        self.design = skill_root() / "references" / "design-system.md"
        self.visual = skill_root() / "references" / "visual-brief-and-generation.md"

    def test_grammar_names_prompt_baseline_as_deterministic_source(self):
        text = read_text(self.grammar)
        self.assertIn("tokens.json", text)
        self.assertIn("prompt_baseline", text)
        self.assertIn("StyleBaselineCompiler", text)

    def test_design_system_soft_baseline_is_prompt_baseline(self):
        text = read_text(self.design)
        self.assertIn("prompt_baseline", text)

    def test_visual_compile_domain_is_prompt_baseline(self):
        text = read_text(self.visual)
        self.assertIn("prompt_baseline", text)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.StyleBaselineProjectionContractTest -v`
预期：FAIL——三个断言均因当前契约无 `prompt_baseline` / `StyleBaselineCompiler` 而失败

- [ ] **步骤 3：按规格改写三条契约**

`generation-prompt-byte-grammar.md` 规则 3（`Replace the second with ...`）改为明确：`style_baseline` 是 `StyleBaselineCompiler` 从当前 `tokens.json`（`schema_version: 2`）的 `prompt_baseline` 确定性投影；删除手写 token 串许可。规则 10 的 `style_baseline_snapshot_id` 输入域同理改为 `tokens.json.prompt_baseline` 规范化字节。三个文档中均写入 `StyleBaselineCompiler` 与 `prompt_baseline` 字样。

`design-system.md:55` 改为：把软风格基线（色板角色、字体栈、间距节奏、形状语言、构图规则、禁止母题——来源均为 `tokens.json.prompt_baseline`）纳入编译输入。

`visual-brief-and-generation.md:14,20,27` 相应改为引用 `prompt_baseline`。

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.StyleBaselineProjectionContractTest -v`
预期：PASS（3 个测试全过）

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/references/generation-prompt-byte-grammar.md skills/ppt-start/references/design-system.md skills/ppt-start/references/visual-brief-and-generation.md tests/test_redesign_prompt_contract.py
git commit -m "docs(contracts): define style baseline projection from tokens.json.prompt_baseline"
```

---

### 任务 2：迁移 canway tokens.json 到 schema v2 并添加 prompt_baseline

**文件：**
- 修改：`skills/ppt-start/assets/styles/canway-midyear-review/tokens.json`
- 修改：`skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`
- 测试：`tests/test_style_packs.py`

**接口：**
- 依赖输入：风格身份（`manifest.json` 仍 v1.3.0）；`prompt_baseline` 结构
- 对外产出：`schema_version: 2` 的 `tokens.json`；`test_rules_capture_identity_and_prohibitions` 中“数值必须出现在 STYLE.md”改为“数值来自 `tokens.json.prompt_baseline`”

- [ ] **步骤 1：写测试校验 prompt_baseline 结构**

在 `tests/test_style_packs.py` 的 `StylePackTests` 中新增：

```python
    def test_tokens_use_schema_v2_and_have_structured_baseline(self):
        tokens = json.loads(read_text(self.tokens_path))
        self.assertEqual(tokens["schema_version"], 2)
        baseline = tokens["prompt_baseline"]
        self.assertEqual(
            list(baseline),
            ["palette_roles", "font_stack", "spacing_rhythm", "shape_language", "composition_rules", "prohibited_motifs"],
        )
        palette_tokens = [role["token"] for role in baseline["palette_roles"]]
        self.assertEqual(len(palette_tokens), len(set(palette_tokens)))
        self.assertTrue(all(role["token"] in tokens["colors"] for role in baseline["palette_roles"]))
        self.assertEqual(baseline["spacing_rhythm"]["outer_margin"], 64)
        self.assertEqual(baseline["composition_rules"]["max_shadowed_objects"], 1)
        self.assertTrue(baseline["prohibited_motifs"])
        self.assertIn("40%-60%", baseline["composition_rules"]["card_coverage"])
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m unittest tests.test_style_packs.StylePackTests.test_tokens_use_schema_v2_and_have_structured_baseline -v`
预期：FAIL——当前 `tokens.json` 仍 `schema_version: 1` 且无 `prompt_baseline`

- [ ] **步骤 3：迁移 tokens.json 并更新 STYLE.md 相关断言**

把 `tokens.json` 的 `schema_version` 改为 `2`，追加 `prompt_baseline`（按规格第 4 节结构，`palette_roles` 的 `token` 引用 `colors` 键）。把 `STYLE.md` 中与 `prompt_baseline` 重复的硬数值（`40%–60%`、`1.5`、`最多一处轻阴影`）删除或改为一句“见 `tokens.json.prompt_baseline`”；`STYLE.md` 保留语义表面、构图配方与禁止项的人类可读说明。

同步修改 `tests/test_style_packs.py` 的 `test_rules_capture_identity_and_prohibitions`：把 `"40%–60%"`、`"最多一处轻阴影"` 两个 token 从 STYLE.md 字符串断言中移除（之后校验 `prompt_baseline`），其余语义 token 保留。

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m unittest tests.test_style_packs.StylePackTests.test_tokens_use_schema_v2_and_have_structured_baseline tests.test_style_packs.StylePackTests.test_rules_capture_identity_and_prohibitions -v`
预期：PASS

- [ ] **步骤 5：提交**

```bash
git add skills/ppt-start/assets/styles/canway-midyear-review/tokens.json skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md tests/test_style_packs.py
git commit -m "feat(styles): add structured prompt_baseline to canway tokens schema v2"
```

---

### 任务 3：更新生成 prompt 金样（generation-prompt-snapshot.json）

**文件：**
- 修改：`tests/fixtures/generation-prompt-snapshot.json`
- 测试：`tests/test_redesign_prompt_contract.py`

**接口：**
- 依赖输入：`tokens.json` v2 的 `prompt_baseline`
- 对外产出：由 `StyleBaselineCompiler` 产出的规范 `style_baseline` 字节；`compiled_prompt_sha256`、`prompt_snapshot_id`、`style_baseline_snapshot_id`、`template_snapshot_id` 等哈希同步

- [ ] **步骤 1：写测试断言金样 style_baseline 是结构化产物**

在 `tests/test_redesign_prompt_contract.py` 中新增：

```python
    def test_golden_style_baseline_is_structured_compiler_output(self):
        payload = json.loads(read_text(self.generation_prompt_snapshot_fixture))
        baseline = payload["style_baseline"]
        self.assertIn("色板角色", baseline)
        self.assertIn("字体栈", baseline)
        self.assertIn("禁止", baseline)
        self.assertNotIn("（来自 theme.json）", baseline)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_golden_style_baseline_is_structured_compiler_output -v`
预期：FAIL——当前金样 `style_baseline` 是无“色板角色/字体栈/禁止”标题的手写 token 串（且含“（来自 theme.json）”）

- [ ] **步骤 3：用 StyleBaselineCompiler 输出替换金样**

把 `tests/fixtures/generation-prompt-snapshot.json` 的 `style_baseline` 替换为规范投影（含 `色板角色`、`字体栈`、`间距节奏`、`形状语言`、`构图规则`、`禁止` 六个小节，行格式按规格第 6 节，开头不再有“（来自 theme.json）”）。逐字更新与之关联的哈希字段（`compiled_prompt_sha256`、`style_baseline_snapshot_id`、`canonical_payload_json` 与 `envelope` 内的 `prompt_snapshot_id`）。

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_golden_style_baseline_is_structured_compiler_output tests.test_redesign_prompt_contract.StyleBaselineProjectionContractTest -v`
预期：PASS

- [ ] **步骤 5：提交**

```bash
git add tests/fixtures/generation-prompt-snapshot.json tests/test_redesign_prompt_contract.py
git commit -m "test(contracts): pin structured style baseline golden bytes"
```

---

### 任务 4：更新风格解析 oracle 与金样（accept schema v2）

**文件：**
- 修改：`tests/test_redesign_prompt_contract.py`（`resolve_style_case`，约 `:1134`）
- 修改：`tests/fixtures/style-prompt-resolution-cases.json`
- 修改：`tests/fixtures/theme-canway-S05.json`
- 测试：`tests/test_redesign_prompt_contract.py`、`tests/test_visual_generation_contract.py`

**接口：**
- 依赖输入：`tokens.json`（`schema_version: 2`）；manifest 身份
- 对外产出：解析 oracle 接受 style pack tokens 的 `schema_version: 2`，同时仍然对非 1/2 值返回 `style_asset_schema_unsupported`

- [ ] **步骤 1：写失败测试断言 schema_v2 为合法解析示例**

在 `tests/test_redesign_prompt_contract.py` 新增（或扩展在既有 `test_style_resolution_ignores_legacy_prompt_fields_and_resources` 附近）：

```python
    def test_resolution_case_uses_schema_v2_tokens(self):
        case = self._resolution_case_by_id("valid-style-pack")
        assets = case["resources"]["assets"]["canway-midyear-review"]
        self.assertEqual(assets["tokens"]["schema_version"], 2)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_resolution_case_uses_schema_v2_tokens -v`
预期：FAIL——解析金样里 `tokens.schema_version` 仍为 1

- [ ] **步骤 3：扩展 resolve_style_case 接受 schema_version 2**

把 `tests/test_redesign_prompt_contract.py:1134` 的：

```python
            if asset.get("schema_version", 1) != 1:
                return _failure("style_asset_schema_unsupported")
```

改为：

```python
            if asset.get("schema_version", 1) not in (1, 2):
                return _failure("style_asset_schema_unsupported")
```

并把 `tests/fixtures/style-prompt-resolution-cases.json` 中 `resources.assets.canway-midyear-review.tokens.schema_version` 改为 `2`。`tests/fixtures/theme-canway-S05.json` 的四个风格身份字段保持 `1.3.0` / `style_pack` 不变，缺其它字段不改。

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_resolution_case_uses_schema_v2_tokens tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_resolver_failure_reason_closure_is_contractually_complete tests.test_visual_generation_contract.VisualGenerationContractTests.test_s05_and_theme_fixture_share_style_identity -v`
预期：PASS

- [ ] **步骤 5：提交**

```bash
git add tests/test_redesign_prompt_contract.py tests/fixtures/style-prompt-resolution-cases.json tests/fixtures/theme-canway-S05.json tests/test_visual_generation_contract.py
git commit -m "test(contracts): accept schema v2 style pack tokens in resolution oracle"
```

---

### 任务 5：更新 skill 包完整性断言（test_skill_package.py）

**文件：**
- 修改：`tests/test_skill_package.py`
- 测试：`tests/test_skill_package.py`

**接口：**
- 依赖输入：`manifest.json`、`registry.json`、tokens/STYLE/REDESIGN 资产
- 对外产出：包结构完整性断言针对 `tokens.json` 的 `prompt_baseline`

- [ ] **步骤 1：写测试断言不受影响**

在 `tests/test_skill_package.py` 新增（或扩展既有结构断言）：

```python
    def test_style_pack_assets_exist_with_structured_baseline(self):
        style_root = skill_root() / "assets" / "styles"
        for f in ("canway-midyear-review/tokens.json", "canway-midyear-review/STYLE.md", "canway-midyear-review/manifest.json"):
            self.assertTrue((style_root / f).is_file())
        tokens = json.loads(read_text(style_root / "canway-midyear-review/tokens.json"))
        self.assertEqual(tokens["schema_version"], 2)
        self.assertIn("prompt_baseline", tokens)
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m unittest tests.test_skill_package.SkillPackageTests.test_style_pack_assets_exist_with_structured_baseline -v`
预期：FAIL——当前解引用 `tokens["schema_version"]` 报错，或仍为 1

- [ ] **步骤 3：修正既有结构断言（若锁定 STYLE.md 散文数字则迁移）**

若 `tests/test_skill_package.py` 或 `tests/test_style_packs.py` 中仍有断言要求 STYLE.md 含 `40%–60%`／`最多一处轻阴影` 等数值，改为断言其来自 `tokens.json.prompt_baseline`。不得新引入对 STYLE.md 散文数值的字符串匹配。

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m unittest tests.test_skill_package tests.test_style_packs -v`
预期：PASS

- [ ] **步骤 5：提交**

```bash
git add tests/test_skill_package.py tests/test_style_packs.py
git commit -m "test(package): assert structured prompt_baseline in canway pack"
```

---

### 任务 6：全量契约测试回归

**文件：**
- 修改：无（仅运行）
- 测试：`tests/` 全量

**接口：**
- 依赖输入：任务 1–5 全部资产与金样
- 对外产出：全量测试通过，无残留手写 token 串 / 散文双写数值断言

- [ ] **步骤 1：全量测试**

运行：`python -m unittest discover -s tests -v`

- [ ] **步骤 2：修复任何未考虑到的字符串匹配断言**

逐条解决因 `STYLE.md` 去数字、`tokens.json` 升 v2、解析 oracle 接受 v2 而失败的断言；替换为对 `prompt_baseline` 或 `StyleBaselineCompiler` 输出的校验。禁止新引入对 STYLE.md 散文数字的字符串匹配。

- [ ] **步骤 3：复跑全量并确认通过**

运行：`python -m unittest discover -s tests -v`
预期：全 PASS

- [ ] **步骤 4：提交**

```bash
git add .
git commit -m "test(contracts): pass full suite after structured style baseline"
```

---

## 自检结果

- **规格覆盖度**：M1（byte-grammar/design-system/visual-brief）→ 任务 1；M2（tokens.json/STYLE.md）→ 任务 2；M3（金样与测试）→ 任务 3/4/5；全量回归 → 任务 6。`legacy_seed` 不动、`schema_version` 失败态、`style_baseline` 仍是软方向均已在规格/约束中覆盖。
- **占位符扫描**：无 TBD/占位符；每个代码/断言步骤均含具体内容。
- **类型一致性**：`prompt_baseline` 键序、`schema_version: 2`、`StyleBaselineCompiler` 名称、`resolve_style_case` 接受 `(1, 2)` 在任务间保持一致；`legacy_seed` 不升级、`canway` 升 2 已明确。
