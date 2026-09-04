# PPT Pilot Visual Assembly Integration and Fast Regression Implementation Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

**Goal:** Integrate the visual-brief and style-pack mechanisms into public documentation and run one short local regression suite proving the Skill package remains coherent.

**Architecture:** Documentation will describe the file-backed prompt boundary and style registry without claiming live host behavior. Existing tests will be extended only where necessary to verify package links, required artifact names, style discoverability, and the three revision branches.

**Tech Stack:** Markdown docs, Python `unittest` contract tests.

## Global Constraints

- This is Plan 7 of 7; Plans 1–6 must be complete and passing before it starts.
- Do not modify FY26 runs or SVGs.
- Do not create live Claude Code/Codex acceptance evidence, PowerPoint evidence, or browser screenshots.
- Do not add model calls or slow end-to-end behavior tests.
- Keep the pure-instruction and cross-host portability claims accurate: file contracts are supported; live behavior remains unverified until separately tested.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

## File structure

- Modify `README.md`: visual briefs, style discovery, named Canway style, and quick test command.
- Modify `docs/design.md`: architecture and artifact protocol.
- Modify `docs/acceptance.md`: static acceptance scope and explicit exclusions.
- Modify `tests/test_skill_package.py`: public docs expose the new artifact and style.
- Modify `tests/test_workflow_contract.py`: `visual-briefs/` belongs to the visual artifact protocol.
- Run existing plus new unit tests; do not create runtime code.

### Task 1: Update user-facing README and architecture documentation

**Files:**
- Modify: `README.md:1-117`
- Modify: `docs/design.md:21-95,124-163`
- Test: `tests/test_skill_package.py`

**Interfaces:**
- Consumes: completed visual-brief reference and style registry.
- Produces: accurate user-facing discovery and recovery documentation.

- [ ] **Step 1: Add failing public-doc assertions**

Extend `tests/test_skill_package.py::test_readme_documents_both_hosts_without_runtime_coupling` with:

```python
for token in (
    "visual-briefs/",
    "逐页视觉 brief",
    "patch",
    "recompose",
    "嘉为年中总结风格",
    "canway-midyear-review",
    "assets/styles/registry.json",
):
    self.assertIn(token.lower(), lower, f"README.md 缺少 {token}")
```

Extend `test_current_readme_and_process_docs_are_chinese` unchanged; the new reference and style guide must satisfy its existing Chinese-content threshold automatically.

Run:

```bash
python -m unittest tests.test_skill_package.SkillPackageTests.test_readme_documents_both_hosts_without_runtime_coupling -v
```

Expected: FAIL because README does not yet mention the new mechanisms.

- [ ] **Step 2: Update README workflow and artifacts**

Add these concise user-facing statements:

```markdown
主题确认后，PPT Pilot 为每个待生成或待修订页面创建 `visual-briefs/<slide-id>.md`。该文件组装已批准内容、当前主题、有效视觉修订、信息层级、构图和 SVG/QA 契约，是跨对话和跨宿主恢复视觉意图的唯一页面输入。

局部碰撞、越界、令牌或对齐错误使用 `patch`；焦点、层级、布局、卡片密度、字体、语义色、品牌方向或视觉参考变化使用 `recompose`。事实和来源变化仍必须重新进行独立文稿审查。
```

Update the run directory list to include:

```text
visual-briefs/*.md
```

Add style discovery:

```markdown
新安装从 `assets/styles/registry.json` 发现可选风格。内置 rich style pack `canway-midyear-review` 的中文显示名为“嘉为年中总结风格”；只有用户明确选择或主题阶段安全选中时使用，不是新的默认主题。
```

Keep the existing quick test command:

```bash
python -m unittest discover -s tests -v
```

- [ ] **Step 3: Update `docs/design.md` architecture**

In the shared Skill architecture, add:

```text
assets/styles/registry.json: style discovery
assets/styles/<style-id>/: rich style packs
visual-briefs/<slide-id>.md: self-contained per-page visual generation state
```

Update the workflow prose without adding a new stage:

```markdown
`theme` 阶段把已批准故事板、当前主题、权威视觉修订历史和 SVG/QA 契约归并为逐页 visual brief。`anchor` 与 `production` 只能消费有效 brief；SVG 本身不是设计状态。
```

Add this exact limitation after the architecture description:

```markdown
本地契约测试只能证明文件结构、规则引用和静态资产一致，不能证明 Claude Code／Codex 的实际模型行为、跨宿主视觉一致性、浏览器渲染或 PowerPoint 导入；这些能力继续以独立人工验收台账为准。
```

- [ ] **Step 4: Run package tests**

Run:

```bash
python -m unittest tests.test_skill_package -v
```

Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Record the new public artifact name, style ID, and exact package-test result.

### Task 2: Align workflow contract tests and acceptance documentation

**Files:**
- Modify: `tests/test_workflow_contract.py:39-51,284-310,424-481`
- Modify: `docs/acceptance.md:1-53,108-136`
- Test: `tests/test_workflow_contract.py`

**Interfaces:**
- Consumes: final visual contract and style-pack files.
- Produces: static acceptance expectations that do not imply live model or Office verification.

- [ ] **Step 1: Add the visual brief directory to the required artifact set**

Update `WorkflowContractTests.REQUIRED_ARTIFACTS`:

```python
REQUIRED_ARTIFACTS = [
    "run.json",
    "简报.md",
    "研究.md",
    "来源.md",
    "大纲.md",
    "故事板.md",
    "文稿审查.md",
    "theme.json",
    "visual-briefs/",
    "samples/",
    "slides/",
    "质量检查报告.md",
]
```

- [ ] **Step 2: Add static visual-contract expectations**

In `test_production_resume_and_revision_semantics_are_explicit`, assert:

```python
for token in (
    "visual-briefs/<slide-id>.md",
    "patch",
    "recompose",
    "当前 svg",
    "几何底稿",
    "supersedes",
):
    self.assertIn(token, combined)
```

Keep the existing manuscript hard-gate assertions.

- [ ] **Step 3: Update the acceptance matrix without adding live runs**

In `docs/acceptance.md`, update the `revise-single-slide.md` row to describe three independent static branches:

- patch: local visual defect;
- recompose: hierarchy/style/reference change;
- factual: manuscript re-entry.

Add a “快速视觉机制验证” section:

```markdown
本次机制改造只要求本地契约测试与 SVG 静态检查：visual brief 完整性、视觉修订优先级、patch/recompose 分支、风格注册表、嘉为年中总结风格的抽象资产边界，以及生成 SVG 的 Office-safe 结构。

本次不新增 Claude Code/Codex 现场运行、PowerPoint 导入、整套浏览器视觉检查或 FY26 页面重生成证据。历史验收台账保持原状态，不能把本地绿色测试描述为这些人工验收已经通过。
```

- [ ] **Step 4: Run workflow tests**

Run:

```bash
python -m unittest tests.test_workflow_contract -v
```

Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Record that acceptance language distinguishes fast static validation from historical/live evidence.

### Task 3: Run the short regression suite and review scope

**Files:**
- Verify only; do not modify unless a failing test identifies a contract inconsistency.

**Interfaces:**
- Consumes: all changes from Plans 1–3.
- Produces: one concise local validation result and changed-file summary.

- [ ] **Step 1: Run focused new-feature tests**

Run:

```bash
python -m unittest tests.test_visual_generation_contract tests.test_style_packs tests.test_assets tests.test_svg_contract -v
```

Expected: all tests PASS with no network, model, browser, or Office calls.

- [ ] **Step 2: Run interaction/workflow/package tests**

Run:

```bash
python -m unittest tests.test_interaction_protocol tests.test_workflow_contract tests.test_skill_package -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run the full local suite once**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: PASS. If an unrelated pre-existing failure appears, report the exact test and do not broaden scope into live-host or deck changes.

- [ ] **Step 4: Perform a fast static scope scan**

Confirm:

- no changed file is under `ppt-output/fy26-h1-auto-ops-review/`;
- no shared Skill/test file contains FY26 customer or project names;
- no new file contains `http://` or `https://` except the SVG namespace;
- no host-specific tool name or runtime dependency was added;
- no TODO/TBD placeholder remains in new plan-delivery files.

Use dedicated search tools rather than a live model or browser run.

- [ ] **Step 5: Record final implementation checkpoint**

Report:

- files created and modified;
- focused and full unit-test counts/results;
- “嘉为年中总结风格” stable ID and asset paths;
- explicit exclusions: no FY26 edits, live host acceptance, PowerPoint import, or full browser review;
- Git commit omitted because the workspace is not a Git repository.
