# PPT Start 风格自有 Redesign Prompt 实施计划

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把完整 redesign prompt 下沉到四个内置风格，由共享 `redesign-prompt.md` 确定性解析、编译和恢复，并把验证后的标准 Skill 精确同步到 Claude Code 用户级安装目录。

**Architecture:** `registry.json` 为 legacy seed 声明 companion prompt，目录式 style pack 在 manifest 中声明自己的 `REDESIGN.md`。共享 reference 不再包含具体视觉 prompt，只定义 style identity、路径、编译、snapshot、blocker、transaction 和恢复协议；所有 Python helper 都只存在于测试中，作为规范 oracle，不是运行时实现。

**Tech Stack:** Markdown／JSON instruction assets、Python 3 `unittest` 静态契约测试、SHA-256 fixtures、Claude Code 文件式 Skill 安装。

## Global Constraints

- 规范源是 [`2026-08-21-ppt-start-style-owned-redesign-prompts-design.md`](../specs/2026-08-21-ppt-start-style-owned-redesign-prompts-design.md)；计划与规范冲突时以规范为准。
- 当前工作区已有大量用户修改和 acceptance-evidence staged removals。只修改本计划列出的文件；不得 reset、restore、clean、stage、commit、push 或改写历史。
- 用户没有授权 commit；每个任务以测试和 review checkpoint 结束，不包含 commit 步骤。
- 开始前把 `git status --short -- acceptance-evidence ppt-output` 保存到仓库外的 `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.before.txt`。不得修改 `acceptance-evidence/` 或 `ppt-output/`。
- 所有临时副本、诊断、manifest 和 hash 输出写入 `C:/Users/Lenovo/AppData/Local/Temp/`，不得进入仓库。
- 每个实现任务严格执行 RED → 观察正确失败 → 最小 GREEN → 聚焦回归；RED 不能来自语法、导入或无关既有失败。
- registry 与 manifest `schema_version` 保持整数 `1`。Canway 内容版本精确升级为 `1.2.0`；legacy `style_manifest_version` 使用字符串 `none`。
- 四个完整 prompt 使用规范定义的十个 hard-constraint IDs 和十一个独占行占位符。
- 不新增运行时脚本、SDK、服务、MCP 或宿主专属 API。测试 helper 是规范 oracle，不得描述成 Skill 运行时实现。
- 静态包测试、通用 Agent 压力诊断、Claude Code 安装 hash 和真实 Claude Code／Codex／浏览器／PowerPoint 验收是四类不同证据。
- 只有全部静态 gate 通过后才能同步 `C:/Users/Lenovo/.claude/skills/ppt-start`。

---

### Task 1: 建立保护基线与诊断场景

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py`
- Create: `tests/prompts/style-prompt-isolation-pressure.md`
- Create: `tests/prompts/style-prompt-fallback-pressure.md`
- Create: `tests/prompts/style-prompt-blocker-pressure.md`
- External: `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.before.txt`
- External: `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-style-owned-redesign-baseline/`

**Interfaces:**
- Consumes: 当前未修改的 `skills/ppt-start/`。
- Produces: 运行产物状态基线、旧 Skill 冻结副本和三个只用于诊断的压力输入。

- [ ] **Step 1: 保存 runtime-artifact 状态与旧 Skill**

```bash
git -C D:/01-code/ppt-pilot status --short -- acceptance-evidence ppt-output > C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.before.txt
```

```bash
python -c "from pathlib import Path; import shutil; s=Path(r'D:\01-code\ppt-pilot\skills\ppt-start'); d=Path(r'C:\Users\Lenovo\AppData\Local\Temp\ppt-start-style-owned-redesign-baseline'); shutil.rmtree(d,ignore_errors=True); shutil.copytree(s,d)"
```

Expected: 两个命令成功，仓库状态未改变。

- [ ] **Step 2: 先写压力 prompt 文件契约测试**

在 `RedesignPromptContractTests` 增加：

```python
def test_pressure_prompts_define_diagnostic_boundaries(self):
    cases = {
        "style-prompt-isolation-pressure.md": ("tech-dark", "style isolation"),
        "style-prompt-fallback-pressure.md": ("minimal-business", "registry fallback"),
        "style-prompt-blocker-pressure.md": ("canway-midyear-review", "style_prompt_unavailable"),
    }
    for filename, (style_id, scenario) in cases.items():
        with self.subTest(filename=filename):
            path = repo_root() / "tests" / "prompts" / filename
            self.assertTrue(path.is_file(), filename)
            text = read_text(path)
            for token in (
                style_id,
                scenario,
                "expected_artifacts",
                "expected_state",
                "forbidden_behavior",
                "EVIDENCE_CLASS: DIAGNOSTIC",
                "不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收",
            ):
                self.assertIn(token, text)
```

- [ ] **Step 3: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_pressure_prompts_define_diagnostic_boundaries -v
```

Expected: FAIL，按顺序指出三个 Markdown 文件不存在；不能是 import 或语法错误。

- [ ] **Step 4: 创建三个合成诊断输入**

每个文件必须显式列出：

```text
selected_style_id: <exact id>
scenario: <exact scenario>
operation: initial_generation | user_recompose
expected_artifacts:
expected_state:
forbidden_behavior:
EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
```

- isolation：选择 `tech-dark`，禁止 Canway/Bento 专属词进入最终 prompt。
- fallback：分别描述完整六文件 fallback 与缺一个 companion 的 partial install。
- blocker：Canway manifest 指向缺失／不安全 prompt，要求写 blocker、generator calls 为 0、SVG writes 为 0。

- [ ] **Step 5: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_pressure_prompts_define_diagnostic_boundaries -v
```

Expected: PASS。

**Checkpoint:** 只新增测试输入和仓库外基线；不修改 Skill production files。

---

### Task 2: 明确取代旧规范与旧计划

**Files:**
- Modify: `tests/test_skill_package.py`
- Modify: `docs/superpowers/specs/2026-08-20-ppt-pilot-visual-prompt-assembly-design.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-style-registry.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-reference-svg.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-canway-style-guidance.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-brief-contract.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-prompt-assembly.md`
- Modify: `docs/superpowers/plans/2026-08-20-ppt-pilot-visual-integration.md`

**Interfaces:**
- Consumes: 已批准的 2026-08-21 规范。
- Produces: 仓库中唯一当前有效的 prompt 所有权结论。

- [ ] **Step 1: 写 supersession RED 测试**

```python
def test_style_prompt_supersession_is_unambiguous(self):
    current = "2026-08-21-ppt-start-style-owned-redesign-prompts-design.md"
    plans = (
        "2026-08-20-ppt-pilot-style-registry.md",
        "2026-08-20-ppt-pilot-canway-reference-svg.md",
        "2026-08-20-ppt-pilot-canway-style-guidance.md",
        "2026-08-20-ppt-pilot-visual-brief-contract.md",
        "2026-08-20-ppt-pilot-visual-prompt-assembly.md",
        "2026-08-20-ppt-pilot-visual-integration.md",
    )
    for filename in plans:
        text = read_text(repo_root() / "docs" / "superpowers" / "plans" / filename)
        lines = text.splitlines()
        self.assertIn("SUPERSEDED", lines[2])
        self.assertIn(current, lines[2])
    old_design = read_text(
        repo_root() / "docs" / "superpowers" / "specs"
        / "2026-08-20-ppt-pilot-visual-prompt-assembly-design.md"
    )
    self.assertIn("部分已被 2026-08-21", old_design)
    self.assertIn("REDESIGN.md", old_design)
    self.assertNotIn("manifest 只引用机器可读 tokens 与中文 `STYLE.md`", old_design)
```

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_skill_package.SkillPackageTests.test_style_prompt_supersession_is_unambiguous -v
```

Expected: FAIL，首先指出旧计划标题下没有 `SUPERSEDED` banner。

- [ ] **Step 3: 最小修订旧文档**

每份旧计划标题后的第一段固定为：

```markdown
> **SUPERSEDED:** redesign prompt 所有权、编译、恢复与相关测试步骤已由 [`2026-08-21-ppt-start-style-owned-redesign-prompts-design.md`](../specs/2026-08-21-ppt-start-style-owned-redesign-prompts-design.md) 取代；本文不再作为当前执行说明。
```

旧设计标题下增加 partial supersession banner，并同步目标 2.8、provenance、generation flow、无 registry 兼容、错误、测试、资产树和验收段落，不再要求 exact two-key manifest／1.1.0／direct brief-to-SVG。

- [ ] **Step 4: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_skill_package.SkillPackageTests.test_style_prompt_supersession_is_unambiguous -v
```

Expected: PASS。

**Checkpoint:** 旧文档保留历史，但不再能被误作当前实施说明。

---

### Task 3: 先建立 registry／manifest 所有权契约

**Files:**
- Modify: `tests/test_style_packs.py`
- Modify: `skills/ppt-start/assets/styles/registry.json`
- Modify: `skills/ppt-start/assets/styles/canway-midyear-review/manifest.json`
- Modify: `tests/fixtures/visual-briefs/S05.md`

**Interfaces:**
- Produces: legacy companion path 与 Canway pack-owned prompt path；Task 4 创建对应文件。

- [ ] **Step 1: 写两个 metadata RED 测试**

```python
def test_legacy_registry_declares_redesign_prompts(self):
    styles = json.loads(read_text(self.registry_path))["styles"]
    actual = {
        item["id"]: item.get("redesign_prompt")
        for item in styles
        if item["kind"] == "legacy_seed"
    }
    self.assertEqual(actual, {
        "minimal-business": "minimal-business.redesign.md",
        "tech-dark": "tech-dark.redesign.md",
        "bold-editorial": "bold-editorial.redesign.md",
    })


def test_canway_manifest_owns_redesign_prompt(self):
    manifest = json.loads(read_text(self.manifest_path))
    self.assertEqual(manifest["version"], "1.2.0")
    self.assertEqual(manifest["files"], {
        "tokens": "tokens.json",
        "guidance": "STYLE.md",
        "redesign_prompt": "REDESIGN.md",
    })
```

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_style_packs.StylePackTests.test_legacy_registry_declares_redesign_prompts tests.test_style_packs.StylePackTests.test_canway_manifest_owns_redesign_prompt -v
```

Expected: legacy 三个值都是 `None`；Canway 第一处失败为 `'1.1.0' != '1.2.0'`。

- [ ] **Step 3: 更新 metadata**

- registry schema 保持 1，只给三个 legacy entry 添加 `redesign_prompt`。
- Canway registry entry 不复制 prompt path。
- Canway manifest `version` 改为 `1.2.0`，`files` 精确三键。
- 把旧 `test_manifest_references_complete_abstract_pack` 改名为 `test_manifest_references_complete_style_owned_pack` 并更新期望。
- S05 暂时只把 manifest version 改为 1.2.0；其他 identity 字段在 Task 6 完成。

- [ ] **Step 4: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_style_packs.StylePackTests.test_legacy_registry_declares_redesign_prompts tests.test_style_packs.StylePackTests.test_canway_manifest_owns_redesign_prompt tests.test_visual_generation_contract.VisualGenerationContractTests.test_fixture_has_every_required_brief_section -v
```

Expected: PASS。此时 prompt 文件尚未创建，不执行 package release gate。

---

### Task 4: 创建四份完整风格 prompt 并收敛共享 resolver

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `tests/test_style_packs.py`
- Create: `skills/ppt-start/assets/styles/minimal-business.redesign.md`
- Create: `skills/ppt-start/assets/styles/tech-dark.redesign.md`
- Create: `skills/ppt-start/assets/styles/bold-editorial.redesign.md`
- Create: `skills/ppt-start/assets/styles/canway-midyear-review/REDESIGN.md`
- Modify: `skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`

**Interfaces:**
- Produces: 四份 full prompt；共享文件只保留 resolver／compiler 协议。

- [ ] **Step 1: 定义测试常量并写 RED**

```python
STYLE_PROMPTS = {
    "minimal-business": "minimal-business.redesign.md",
    "tech-dark": "tech-dark.redesign.md",
    "bold-editorial": "bold-editorial.redesign.md",
    "canway-midyear-review": "canway-midyear-review/REDESIGN.md",
}
HARD_CONSTRAINT_IDS = (
    "CONTENT_LOCK_V1", "SOURCE_BOUNDARY_V1", "NO_OLD_SVG_GEOMETRY_V1",
    "SINGLE_XML_FENCE_V1", "OFFICE_SAFE_SVG_V1", "EXPLICIT_TSPAN_TEXT_V1",
    "NO_REMOTE_OR_ACTIVE_CONTENT_V1", "SOURCE_METADATA_V1",
    "CREATOR_OWNS_WRITE_AND_QA_V1", "DYNAMIC_INPUT_AUTHORITY_V1",
)
PROMPT_PLACEHOLDERS = (
    "[SLIDE_ID]", "[SOURCE_AND_VERSION]", "[LOCKED_CONTENT]",
    "[INFORMATION_HIERARCHY]", "[COMPOSITION]", "[VISUAL_SYSTEM]",
    "[REVISION_MODE]", "[OUTPUT_AND_QA]", "[ACTIVE_THEME]",
    "[ACTIVE_VISUAL_REVISIONS]", "[USER_WORDING]",
)
```

新增 `test_each_style_owns_a_complete_prompt_template`：先断言四个路径存在，再精确解析 schema／STYLE_ID／marker 顺序和每个独占行 placeholder；拒绝 `[VISUAL_BRIEF]`、`[OUTPUT_PATH]`、`[USER_PAGE_REQUEST]`、`[LOCKED_ORIGINAL_CONTENT]`。

在新增测试前先删除／改写三个反向契约：

- `test_prompt_template_has_required_role_and_workflow` 改为 `test_each_style_owns_a_complete_prompt_template`；
- `test_rounded_cards_use_path_arc_not_rect_rx` 改为 `test_canway_prompt_owns_card_geometry_compatibility`，读取 Canway `REDESIGN.md` 而不是 shared reference；
- `test_powerpoint_safe_text_model_is_explicit` 改为 table-driven `test_each_style_prompt_contains_text_and_powerpoint_contract`。

新增 `test_shared_reference_is_resolver_only`：

```python
text = read_text(self.reference)
self.assertNotIn("## 专用 Prompt 模板", text)
for forbidden in ("层级 Bento", "深色主卡", "40%–60%", "Microsoft YaHei"):
    self.assertNotIn(forbidden, text)
```

新增两个覆盖生产 edits 的 RED：

```python
def test_canway_literals_are_isolated_to_canway_prompt(self):
    required = (
        "层级 Bento", "深色主卡", "白色事实卡", "浅蓝证据边界",
        "40%–60%", "1.5", "最多一处轻阴影",
    )
    canway = read_text(self.style_root / "canway-midyear-review" / "REDESIGN.md")
    other = "\n".join([
        read_text(self.reference),
        *(read_text(self.style_root / STYLE_PROMPTS[style_id])
          for style_id in ("minimal-business", "tech-dark", "bold-editorial")),
    ])
    for token in required:
        self.assertIn(token, canway)
        self.assertNotIn(token, other)


def test_canway_style_links_complete_prompt_and_page_exceptions(self):
    text = read_text(self.style_root / "canway-midyear-review" / "STYLE.md")
    self.assertIn("REDESIGN.md", text)
    self.assertIn("完整生成 prompt", text)
    self.assertIn("exceptions", text)
    self.assertIn("页面语义", text)
```

- [ ] **Step 2: 运行分阶段 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_each_style_owns_a_complete_prompt_template tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_shared_reference_is_resolver_only tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_canway_literals_are_isolated_to_canway_prompt tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_canway_style_links_complete_prompt_and_page_exceptions -v
```

Expected: 四个文件不存在；共享文件仍有完整模板。

- [ ] **Step 3: 先创建空文件，观察结构 RED**

Expected next RED: `PROMPT_SCHEMA_VERSION: 1` 缺失，而不是 existence failure。

- [ ] **Step 4: 写四份完整 prompt**

每份文件按这个精确骨架组织，十一个 token 各独占一行且只出现一次：

```markdown
PROMPT_SCHEMA_VERSION: 1
STYLE_ID: <exact-style-id>
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

# <style display name> Complete Redesign Prompt

## Authority
锁定内容／来源／hard constraints > active theme／有效 normalized revisions > USER_WORDING。

## Inputs
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
BEGIN_UNTRUSTED_USER_WORDING_JSON
[USER_WORDING]
END_UNTRUSTED_USER_WORDING_JSON

## Style Direction
<本风格完整视觉规则>

## Output Contract
<内容保护、单 fenced SVG、Office-safe、tspan、安全区、来源、fresh text-only、creator QA>
```

这里 `<...>` 在实施文件中必须替换为真实文本：

- minimal：留白、克制边界、稀疏层级、简洁比较、结论先行；禁止默认 Bento／深色中央主卡／大量卡片。
- tech-dark：深色画布、高对比技术关系、系统／架构／流程、有限高亮；明确禁止 glow filter 和远程字体。
- bold-editorial：大标题、观点节奏、不对称、少量强色块、编辑式留白；禁止管理卡片墙。
- Canway：把当前共享模板中的内容提纯、层级 Bento、卡片层级、圆角兼容、字体／文本、Office-safe 和 PowerPoint 规则迁入；必须包含 `层级 Bento`、`深色主卡`、`白色事实卡`、`浅蓝证据边界`、`40%–60%`、`1.5`、`最多一处轻阴影`，并声明这些是抽象语法而非固定版式。

每份 prompt 都写齐规范 §6.4 的九项语义责任；不能以“同 Canway”或其他交叉引用代替完整正文。

- [ ] **Step 5: 把共享文件改为 resolver-only**

保留触发、patch exclusion、持久派生产物、style resolution、template validation、编译、fresh isolation、fence extraction、candidate／QA；删除 `## 专用 Prompt 模板` 及任何具体布局、字体、调色板和圆角示例。STYLE.md 增加 `REDESIGN.md` 所有权与 page exceptions 交叉引用。

- [ ] **Step 6: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs -v
```

Expected: PASS。

---

### Task 5: 建立确定性 resolver、路径和 fallback oracle

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `tests/test_style_packs.py`
- Create: `tests/fixtures/style-prompt-resolution-cases.json`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/design-system.md`

**Interfaces:**
- Produces: 规范 §9–11 的 test-only resolver oracle 和同构书面协议。

- [ ] **Step 1: 写 RED 测试**

新增：

```python
def test_resolution_fixture_covers_all_branches(self): ...
def test_resolution_failure_precedence(self): ...
def test_shared_reference_is_style_neutral(self): ...
```

fixture 必须包含：四个正常 style、旧 v1 companion、完整六文件 no-registry fallback、Canway／unknown no-registry、absolute／drive／UNC／URL／dot／traversal、root-level manifest、nested／overlapping packs、tokens／guidance／prompt escape、legacy-to-pack、link／directory／special target、identity／display／version mismatch。

下列 case IDs 是强制精确值，RED 测试先断言全部存在：

```text
precedence-unselected-pack-root-before-selected-prompt
precedence-selected-tokens-before-prompt
fallback-missing-minimal-business-seed
fallback-missing-tech-dark-seed
fallback-missing-bold-editorial-seed
fallback-missing-minimal-business-companion
fallback-missing-tech-dark-companion
fallback-missing-bold-editorial-companion
```

前两个分别同时植入两个缺陷并断言 expected reason 是 `entrypoint_path_unsafe` 与 `style_asset_target_invalid`；六个 fallback cases 全部 expected `registry_missing`。

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_resolution_fixture_covers_all_branches tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_resolution_failure_precedence tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_shared_reference_is_style_neutral -v
```

Expected: fixture missing；不能是 malformed JSON。

- [ ] **Step 3: 创建 fixture 与 test-only oracle**

helper 签名固定为：

```python
def resolve_style_prompt_case(case: dict) -> dict:
    """Return {'ok': bool, 'reason': str | None, 'resolved_path': str | None}."""
```

按规范 traversal 顺序返回稳定 reason；enum／condition 不能在测试与 reference 中各自发明。no-registry fallback 必须验证三 seed identity 和三 prompt contract 后才允许 legacy。Windows 无法创建 link／junction fixture 时只 skip 具体对象创建用例，lexical cases 仍必测。

- [ ] **Step 4: 同步书面 resolver**

`redesign-prompt.md` 与 `design-system.md` 明确：registry target 状态、pack root 精确形状、legacy identity、manifest handshake、tokens／guidance／prompt ownership、SemVer、fallback table、完整 reason precedence 和 package oracle 非运行时实现。

- [ ] **Step 5: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs -v
```

Expected: PASS。

---

### Task 6: 持久 identity、operation trigger 与旧运行迁移

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/fixtures/visual-briefs/S05.md`
- Create: `tests/fixtures/theme-canway-S05.json`
- Create: `tests/fixtures/style-identity-migration-cases.json`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `skills/ppt-start/references/design-system.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`

**Interfaces:**
- Produces: theme／brief 四字段 identity、`generation_intent`、`generation_trigger_id` 和旧目录迁移矩阵。

- [ ] **Step 1: 写 RED**

新增测试：

```python
def test_fixture_has_complete_style_identity_and_generation_owner(self): ...
def test_s05_and_theme_fixture_share_style_identity(self): ...
def test_identity_migration_cases(self): ...
def test_identity_handshake_distinguishes_stale_from_conflict(self): ...
def test_operation_matrix_covers_all_intents_and_triggers(self): ...
def test_old_run_prompt_migration_is_read_only_and_deterministic(self): ...
```

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_fixture_has_complete_style_identity_and_generation_owner tests.test_visual_generation_contract.VisualGenerationContractTests.test_s05_and_theme_fixture_share_style_identity tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_identity_migration_cases tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_identity_handshake_distinguishes_stale_from_conflict tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_operation_matrix_covers_all_intents_and_triggers tests.test_visual_generation_contract.VisualGenerationContractTests.test_old_run_prompt_migration_is_read_only_and_deterministic -v
```

Expected: S05 缺 `style_kind`／`generation_intent`／`generation_trigger_id`，theme 与 migration fixtures 不存在。

- [ ] **Step 3: 更新 S05 与 fixture**

S05 必须包含：

```text
selected_style_id: canway-midyear-review
selected_style_display_name: 嘉为年中总结风格
style_kind: style_pack
style_manifest_version: 1.2.0
generation_intent: user_recompose
generation_trigger_id: interaction:visual-revision-3
```

对应 `theme-canway-S05.json` 至少包含同值四字段：

```json
{
  "schema_version": 1,
  "selected_style_id": "canway-midyear-review",
  "selected_style_display_name": "嘉为年中总结风格",
  "style_kind": "style_pack",
  "style_manifest_version": "1.2.0"
}
```

fixture 覆盖：完整 identity、单侧缺 ID、双方缺 ID、可派生非 ID 字段、stale name／version、直接冲突、legacy version 非 none、fallback identity table、trigger 缺失／冲突、old-only／new-stale／双目录／不同 slide／prompt hash changed／stored body mismatch。

同一 fixture 必须有 exact 四行 operation matrix：

- `initial_generation`: mode `recompose`，trigger `initial:<slide-id>:<visual_brief_snapshot_id>`，reason `initial generation from approved visual brief`，USER_WORDING `"none (initial generation)"`，prior candidate `none`；
- `user_recompose`: mode `recompose`，trigger `interaction:<applied-history-id>`，USER_WORDING 只来自该记录 raw answer；
- `deterministic_fallback`: mode `recompose`，trigger `fallback:<slide-id>:<failed-transaction-64hex>:2`，reason `deterministic single-column or two-column fallback after two failed patches`，USER_WORDING `"none (deterministic fallback after two failed patches)"`；
- `local_patch`: mode `patch`，trigger `patch:<slide-id>:<qa-defect-id>`，要求 current SVG，`compile_full_prompt: false`。

另加 invalid／missing／multiple trigger owner cases，expected `prompt_snapshot_conflict`。

- [ ] **Step 4: 写 test-only migration oracle 与 reference**

helper：

```python
def evaluate_style_identity_case(case: dict) -> str:
    """Return 'valid', 'rebuild', 'ordinary_stale', or 'prompt_snapshot_conflict'."""
```

只从 registry／manifest／fallback table／persisted operation owner 派生；不从目录、文案或 SVG 存在推断。旧 `redesign-prompts/` 永远 inert、不写／不移／不删。

- [ ] **Step 5: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_visual_generation_contract -v
```

Expected: PASS。

---

### Task 7: 规范 active revisions、编译 bytes 与 golden snapshot

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `tests/test_visual_generation_contract.py`
- Create: `tests/fixtures/style-prompt-active-revision-projection.json`
- Create: `tests/fixtures/generation-prompt-snapshot.json`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`

**Interfaces:**
- Produces: answer-free revision projection、exact byte grammar、generation-prompt envelope 与 golden SHA-256。

- [ ] **Step 1: 写 projection RED**

新增：

```python
def test_active_revision_projection_matches_golden_bytes(self): ...
def test_active_revision_projection_rejects_conflicts(self): ...
def test_raw_answers_never_enter_projection(self): ...
```

fixture 中 raw answer 固定包含 `DEPRECATED_RAW_ANSWER_MUST_NOT_APPEAR`，并有 partial／chained supersede。

运行 projection RED：

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_active_revision_projection_matches_golden_bytes tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_active_revision_projection_rejects_conflicts tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_raw_answers_never_enter_projection -v
```

Expected: fixture 缺失。

- [ ] **Step 2: 实现 test-only projection oracle**

```python
def project_active_visual_revisions(payload: dict) -> tuple[list[str], bytes]:
    """Return sorted provenance IDs and canonical projected JSON ending in one LF."""
```

只投影规范允许字段；永久停用 superseded field；raw `answer` 永不输出；invalid edge 返回 `prompt_snapshot_conflict`。

- [ ] **Step 3: 写 compiler／snapshot RED**

新增：

```python
def test_brief_sections_follow_exact_byte_grammar(self): ...
def test_compile_replaces_token_lines_without_recursive_expansion(self): ...
def test_generation_prompt_snapshot_matches_golden_fixture(self): ...
def test_repeat_compile_is_byte_identical(self): ...
def test_each_snapshot_input_invalidates_transaction(self): ...
```

初始 RED 是 fixture 缺失；随后故意放一个错误 digest 观察明确 hash mismatch。

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_brief_sections_follow_exact_byte_grammar tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_compile_replaces_token_lines_without_recursive_expansion tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_generation_prompt_snapshot_matches_golden_fixture tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_repeat_compile_is_byte_identical tests.test_redesign_prompt_contract.RedesignPromptContractTests.test_each_snapshot_input_invalidates_transaction -v
```

Expected: generation snapshot fixture 缺失；创建错误 digest 后变为精确 hash mismatch。

- [ ] **Step 4: 实现 test-only compiler helpers**

```python
def normalize_lf(raw: bytes) -> bytes: ...
def extract_brief_sections(text: str) -> dict[str, bytes]: ...
def compile_prompt_body(template: bytes, replacements: dict[str, bytes]) -> bytes: ...
def canonical_json_bytes(value: object) -> bytes: ...
def sha256_id(data: bytes) -> str: ...
def render_generation_prompt(provenance: dict, body: bytes) -> bytes: ...
```

严格使用规范的 heading／blank-line／terminal-LF／one-pass token／canonical JSON／hash domain。`applied_visual_revision_ids` 在 envelope 永远是 JSON array text。candidate path 不进入 body/hash。

- [ ] **Step 5: 创建 literal golden fixture**

必须保存 literal template、brief sections、theme、projection、USER_WORDING、expected body、完整 envelope、canonical payload 和 hashes。测试独立重算所有 digest。

- [ ] **Step 6: 同步 reference 并运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_visual_generation_contract -v
```

Expected: PASS，repeat compile bytes 完全相同。

---

### Task 8: 持久 blocker 与全局恢复顺序

**Files:**
- Create: `tests/fixtures/style-prompt-blocker-cases.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/test_interaction_protocol.py`
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/qa-and-revision.md`

**Interfaces:**
- Produces: `visual_generation_blocker` schema、reason precedence、`pending > blocker > transaction > stage` 恢复顺序。

- [ ] **Step 1: 写 blocker RED**

```python
def test_style_prompt_blocker_fixture_models_atomic_lifecycle_and_precedence(self): ...
```

fixture exact reason set 必须与规范 §10 一致，覆盖 create／sanitize／same-slide refresh／other-slide serialization／still failing／durable prompt before run transition，并精确包含：

```text
precedence-unselected-pack-root-before-selected-prompt
precedence-selected-tokens-before-prompt
```

两者的 before state 必须同时携带 Task 5 指定的双缺陷，expected blocker reason 分别为 `entrypoint_path_unsafe` 与 `style_asset_target_invalid`。

- [ ] **Step 2: 写 resume-order RED**

```python
def test_resume_orders_pending_then_blocker_then_transaction_then_stage_scan(self): ...
```

解析 workflow 规范表，要求恰好四行：`pending_interaction`、`visual_generation_blocker`、`visual_generation_transaction`、stage scan。

- [ ] **Step 3: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_style_prompt_blocker_fixture_models_atomic_lifecycle_and_precedence tests.test_interaction_protocol.InteractionProtocolTests.test_resume_orders_pending_then_blocker_then_transaction_then_stage_scan -v
```

Expected: fixture／schema／table 缺失。

- [ ] **Step 4: 写 fixture 与契约**

- blocker 只保存安全相对 resource 或 `none`；保持 stage/mode/history，slide dirty。
- prompt durable 时仍可见 `compiling + active blocker`；一次 `run.json` 替换同时变为 compiled 并移除 blocker。
- pending interaction 存在时不创建／处理 blocker，不解析 style。
- still failing 时 generator／SVG writes 都为 0。

- [ ] **Step 5: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_interaction_protocol tests.test_visual_generation_contract -v
```

Expected: PASS。

---

### Task 9: 可恢复 transaction 与全部失败 consumer

**Files:**
- Create: `tests/fixtures/visual-generation-transaction-cases.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/test_interaction_protocol.py`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`

**Interfaces:**
- Produces: transaction 七状态、失败 reason、crash recovery 与失败 consumer。

- [ ] **Step 1: 写 transaction RED**

```python
def test_visual_generation_transaction_fixture_models_legal_transitions_and_crashes(self): ...
def test_failed_transaction_reasons_have_one_complete_consumer(self): ...
```

fixture 必须声明七状态、规范 failure reasons、normal／failure／recovery legal transitions、transaction／candidate paths、intent／trigger／attempt／hash 字段。恢复 transition 必须精确包含 `failed -> generating` 与条件式 `failed -> validated`；权威输入变化时用新的 `compiling` transaction 原子替换，不作为同 transaction edge。

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_visual_generation_transaction_fixture_models_legal_transitions_and_crashes tests.test_visual_generation_contract.VisualGenerationContractTests.test_failed_transaction_reasons_have_one_complete_consumer -v
```

Expected: fixture 缺失；不能接受额外 state/reason 或 pre-candidate hash。

- [ ] **Step 3: 创建正常与 crash cases**

覆盖：compiling prompt match/mismatch、generating orphan（必须删除并重调 generator）、candidate hash match/mismatch、validated final match/conflict、illegal transition、promoted QA cleanup。

- [ ] **Step 4: 添加失败 consumer cases**

- generator／candidate transport failures：同 transaction explicit-resume，attempt +1，每次调用最多 generator 1 次。
- SVG／content／visual QA failures：先持久 defect，再 patch 或新的 deterministic-fallback transaction。
- promotion／state conflict：保留 failed transaction，创建 production pending blocker，不覆盖 final；fixture 必须继续覆盖用户解决后的两个分支：(a) candidate／provenance 未变时原子 `failed -> validated` 并重试 promotion；(b) authoritative inputs 已变时以新的 `compiling` transaction 替换。两个分支 durable 前 failed transaction 都不能删除。

`covered reasons` 集合必须与声明 reason 集合精确相等。

- [ ] **Step 5: 同步状态契约并运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_interaction_protocol tests.test_visual_generation_contract -v
```

Expected: PASS。

---

### Task 10: 更新当前 README／设计／验收边界

**Files:**
- Modify: `tests/test_skill_package.py`
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `README.md`
- Modify: `docs/design.md`
- Modify: `docs/acceptance.md`

**Interfaces:**
- Produces: 与当前 Skill 一致的用户文档与不夸大的验收矩阵。

- [ ] **Step 1: 写 docs RED**

```python
def test_style_owned_prompt_architecture_and_evidence_boundaries(self):
    combined = "\n".join(read_text(path) for path in (self.readme, self.design, self.acceptance))
    for token in (
        "minimal-business.redesign.md", "tech-dark.redesign.md",
        "bold-editorial.redesign.md", "canway-midyear-review/REDESIGN.md",
        "1.2.0", "generation_trigger_id", "visual_generation_blocker",
        "visual_generation_transaction", "EVIDENCE_CLASS: DIAGNOSTIC",
    ):
        self.assertIn(token, combined)
    self.assertIn("PENDING", read_text(self.acceptance))
```

- [ ] **Step 2: 运行 RED**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_skill_package.SkillPackageTests.test_style_owned_prompt_architecture_and_evidence_boundaries -v
```

Expected: 缺四 prompt 和新状态字段。

- [ ] **Step 3: 更新文档**

README／design 描述四份完整 prompt、resolver-only、identity／provenance／blocker／transaction／old prompt inert。acceptance 区分：static package、DIAGNOSTIC、deployment hash、real host；真实 Claude Code、Codex、fresh context、browser、PowerPoint 仍 PENDING。

- [ ] **Step 4: 运行 GREEN**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v
```

Expected: PASS。

---

### Task 11: 完整静态 gate、代码审查与诊断复测

**Files:**
- Verify: `tests/`
- Verify: `skills/ppt-start/`
- Verify: `README.md`, `docs/`
- External: `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.*.txt`
- External: `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-style-owned-redesign-updated/`

**Interfaces:**
- Produces: 静态 release verdict、独立 code review、强制 before／after 诊断；不产生仓库 acceptance evidence。

- [ ] **Step 1: 运行设计规定的聚焦套件**

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs tests.test_visual_generation_contract -v
```

Expected: 0 failures/errors。

- [ ] **Step 2: 运行完整套件**

```bash
cd /d/01-code/ppt-pilot && python -m unittest discover -s tests -v
```

Expected: 0 failures/errors。

- [ ] **Step 3: 检查 diff 与运行产物漂移**

```bash
git -C D:/01-code/ppt-pilot diff --check
```

```bash
git -C D:/01-code/ppt-pilot status --short -- acceptance-evidence ppt-output > C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.after-static.txt && cmp C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.before.txt C:/Users/Lenovo/AppData/Local/Temp/ppt-start-runtime-artifacts.after-static.txt
```

Expected: diff check clean；artifact status 与基线逐字节相同。

- [ ] **Step 4: 独立 review**

Review scope：四 prompt 是否独立完整；共享 resolver 是否无 style leakage；fixtures／oracle 是否与规范一致；状态恢复是否无不可达分支；文档证据边界是否准确。任何 HIGH／MEDIUM finding 先补 RED test，再修复并重跑本任务全部 gate。

- [ ] **Step 5: 强制执行 before／after pressure diagnostics**

对三个场景各启动两个 fresh context：一个显式只读 `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-style-owned-redesign-baseline/`，另一个只读更新后的临时副本。先保存 old 输出，再运行同一输入的 new 输出；每份记录都写 host/model、package path／hash、`EVIDENCE_CLASS: DIAGNOSTIC`。

必须观察并保存旧版跨风格 Bento／unsafe fallback／缺 blocker 中至少一个实际缺陷，再核对新版是否遵循 style isolation、完整六文件 fallback 和 no-generator/no-SVG blocker。若 fresh delegation 不可用，记录 `DIAGNOSTIC NOT RUN` 并把本任务标为未完成；不得跳过后仍宣称规范的 pressure step 完成，也不得进入 Task 12。

所有输出只写 `C:/Users/Lenovo/AppData/Local/Temp/ppt-start-style-owned-redesign-diagnostics/`；不得改 acceptance rows 或仓库文件。

**Checkpoint:** 只有静态 gate 和 mandatory pressure pass 都完成才能进入 Task 12。

---

### Task 12: 精确同步到 Claude Code 用户级 Skill

**Files:**
- Source: `D:/01-code/ppt-pilot/skills/ppt-start/`
- Destination: `C:/Users/Lenovo/.claude/skills/ppt-start/`
- Temporary: `C:/Users/Lenovo/.claude/skills/ppt-start.sync-tmp/`
- Backup: `C:/Users/Lenovo/.claude/skills/ppt-start.sync-backup/`
- Preserved invalid copy: `C:/Users/Lenovo/.claude/skills/ppt-start.sync-broken/`

**Interfaces:**
- Consumes: Task 11 全绿的标准 Skill。
- Produces: 与源逐文件 SHA-256 相同的 Claude Code 用户级安装副本。

- [ ] **Step 1: 先比较 manifest，观察 deployment RED**

```bash
python -c "from pathlib import Path; import hashlib; s=Path(r'D:\01-code\ppt-pilot\skills\ppt-start'); d=Path(r'C:\Users\Lenovo\.claude\skills\ppt-start'); m=lambda r:{p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file()}; sm=m(s); dm=m(d) if d.exists() else {}; print('missing',sorted(sm.keys()-dm.keys())); print('stale',sorted(dm.keys()-sm.keys())); print('mismatched',sorted(k for k in sm.keys()&dm.keys() if sm[k]!=dm[k])); raise SystemExit(0 if sm==dm else 1)"
```

Expected: 实现后至少有新增／变更文件，因此非零；若已经完全相等，记录 already synchronized，不强制 swap。

- [ ] **Step 2: 创建并验证 staging**

```bash
python -c "from pathlib import Path; import hashlib,shutil; s=Path(r'D:\01-code\ppt-pilot\skills\ppt-start'); t=Path(r'C:\Users\Lenovo\.claude\skills\ppt-start.sync-tmp'); shutil.rmtree(t,ignore_errors=True); shutil.copytree(s,t); m=lambda r:{p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file()}; assert m(s)==m(t)"
```

- [ ] **Step 3: rollback-safe swap**

运行下面的单一 preflight／recovery／swap 脚本。它绝不在验证前删除已有 backup；ambiguous 双副本状态直接停止：

```bash
python - <<'PY'
from hashlib import sha256
from pathlib import Path
import shutil

source = Path(r"D:\01-code\ppt-pilot\skills\ppt-start")
destination = Path(r"C:\Users\Lenovo\.claude\skills\ppt-start")
staging = Path(r"C:\Users\Lenovo\.claude\skills\ppt-start.sync-tmp")
backup = Path(r"C:\Users\Lenovo\.claude\skills\ppt-start.sync-backup")
broken = Path(r"C:\Users\Lenovo\.claude\skills\ppt-start.sync-broken")

def manifest(root: Path) -> dict[str, str]:
    if not root.is_dir() or not (root / "SKILL.md").is_file():
        raise ValueError(f"invalid skill tree: {root}")
    return {
        p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }

source_manifest = manifest(source)
staging_manifest = manifest(staging)
if staging_manifest != source_manifest:
    raise RuntimeError("staging does not match source")

# Recover only unambiguous interrupted states before a new swap.
if backup.exists():
    if not destination.exists():
        backup.rename(destination)
    else:
        try:
            destination_manifest = manifest(destination)
        except ValueError:
            if broken.exists():
                raise RuntimeError("ambiguous recovery: broken path already exists")
            destination.rename(broken)
            backup.rename(destination)
            raise RuntimeError(f"restored backup; preserved invalid destination at {broken}")
        if destination_manifest == source_manifest:
            # New destination is independently verified; old backup is no longer needed.
            shutil.rmtree(backup)
        else:
            raise RuntimeError("ambiguous recovery: destination and backup both exist; neither may be deleted")

if destination.exists() and manifest(destination) == source_manifest:
    shutil.rmtree(staging)
else:
    had_destination = destination.exists()
    if had_destination:
        destination.rename(backup)
    try:
        staging.rename(destination)
        if manifest(destination) != source_manifest:
            raise RuntimeError("installed destination hash mismatch")
    except BaseException:
        if destination.exists():
            shutil.rmtree(destination)
        if backup.exists():
            backup.rename(destination)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)

installed = manifest(destination)
if installed != source_manifest:
    raise RuntimeError("final destination mismatch")
records = "".join(f"{path}\0{digest}\n" for path, digest in sorted(installed.items())).encode()
print(f"files={len(installed)} aggregate_sha256={sha256(records).hexdigest()}")
PY
```

脚本只操作 `ppt-start`、`sync-tmp`、`sync-backup` 和用于保留异常副本的 `sync-broken`；不得触碰同级其他 Skills。若报 ambiguous recovery，停止部署并保留所有副本，不重复删除。

- [ ] **Step 4: 最终验证**

打印相同 file count 和对排序 `path\0hash\n` records 的 aggregate SHA-256；再次运行聚焦套件和 artifact baseline compare。

```bash
cd /d/01-code/ppt-pilot && python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs tests.test_visual_generation_contract -v
```

Expected: PASS；source／destination 完全相同；Canway 1.2.0；四 prompt 均存在；无 stale destination files。

- [ ] **Step 5: 报告证据边界**

只报告“用户级 Skill 文件同步与 hash 验证通过”。不得把它描述为 Claude Code 行为、fresh generation、browser 或 PowerPoint 验收通过。未创建 commit，runtime artifact status 与基线相同。

---

## Plan Self-Review

- **Spec coverage:** Tasks 3–4 覆盖 prompt ownership／assets；Task 5 覆盖 resolver／path／fallback；Tasks 6–7 覆盖 identity／trigger／projection／bytes／snapshot；Tasks 8–9 覆盖 blocker／resume／transaction；Task 10 覆盖 current docs；Task 2 覆盖 supersession；Tasks 11–12 覆盖 verification／diagnostics／deployment。
- **Placeholder scan:** 本计划中的 `<...>` 只出现在解释文件格式的语法示例；实施要求已逐项列出实际 style rules、fields、states、reasons 和 commands，不存在未决占位表达。
- **Type consistency:** `visual_brief_snapshot_id`、`applied_visual_revision_ids`、`generation_intent`、`generation_trigger_id`、`visual_generation_blocker`、`visual_generation_transaction` 全文一致；Canway version 统一为 1.2.0。
- **Evidence boundary:** 静态 oracle、diagnostic、deployment 与 real host acceptance 全程分离。
- **Git constraint:** 无 commit／stage 步骤。
