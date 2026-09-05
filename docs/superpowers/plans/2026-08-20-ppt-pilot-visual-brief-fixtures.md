# PPT Pilot Visual Brief Fixtures and Contract Tests Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define synthetic visual-brief and revision-precedence fixtures plus the first failing static contract tests.

**Architecture:** Tests establish the exact portable data shape before Skill documentation changes. All content is synthetic and file-backed.

**Tech Stack:** Markdown fixture, JSON fixture, Python `unittest`.

## Global Constraints

- This is Plan 1 of 7.
- Create tests and synthetic fixtures only; do not change the Skill yet.
- Do not use FY26 content, model calls, browser runs, or runtime dependencies.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Add failing visual-generation contract fixtures and tests

**Files:**
- Create: `tests/fixtures/visual-briefs/S05.md`
- Create: `tests/fixtures/visual-revision-precedence.json`
- Create: `tests/test_visual_generation_contract.py`

**Interfaces:**
- Consumes: `tests/helpers.py::read_text`, `tests/helpers.py::repo_root`, `tests/helpers.py::skill_root`.
- Produces: a normative synthetic brief shape and precedence fixture used by later tasks.

- [ ] **Step 1: Create the precedence fixture**

Write `tests/fixtures/visual-revision-precedence.json` exactly as a synthetic, content-free sequence:

```json
{
  "schema_version": 1,
  "history": [
    {
      "id": "visual-revision-1",
      "stage": "anchor",
      "kind": "visual_revision",
      "answer": "Use the brand blue and a long blue title rail.",
      "normalized_changes": {
        "brand_primary": "#156BFF",
        "title_rail": "long-blue"
      },
      "affected_scope": "deck",
      "supersedes": [],
      "status": "applied",
      "artifact_owner": "theme.json"
    },
    {
      "id": "visual-revision-2",
      "stage": "anchor",
      "kind": "visual_revision",
      "answer": "Remove the long blue title rail.",
      "normalized_changes": {
        "title_rail": "none"
      },
      "affected_scope": "deck",
      "supersedes": ["visual-revision-1:title_rail"],
      "status": "applied",
      "artifact_owner": "theme.json"
    },
    {
      "id": "visual-revision-3",
      "stage": "anchor",
      "kind": "visual_revision",
      "answer": "Use hierarchical Bento for S05.",
      "normalized_changes": {
        "layout_family": "hierarchical-bento"
      },
      "affected_scope": ["S05"],
      "supersedes": [],
      "status": "applied",
      "artifact_owner": "visual-briefs/S05.md"
    }
  ],
  "expected_active_contract": {
    "brand_primary": "#156BFF",
    "title_rail": "none",
    "layout_family": "hierarchical-bento"
  },
  "expected_superseded_rules": ["visual-revision-1:title_rail"]
}
```

- [ ] **Step 2: Create the complete synthetic visual brief fixture**

Write `tests/fixtures/visual-briefs/S05.md` with every required section and no real customer data:

```markdown
# S05 视觉 brief

## 来源与版本

- slide_id: S05
- storyboard_snapshot_id: sha256:synthetic-storyboard
- theme_snapshot_id: sha256:synthetic-theme
- applied_visual_revision_ids: visual-revision-1, visual-revision-2, visual-revision-3
- brief_snapshot_id: sha256:synthetic-brief

## 锁定内容

- assertion_title: 工作假设必须通过有界试点验证
- audience_takeaway: 当前信号可以提出假设，但不足以证明因果。
- required_content_blocks: 已观察信号；替代解释；验证问题；有界试点
- qualifiers: 不得把相关性写成因果；不得把阶段结果写成最终验收
- source_ids: SYN-001, SYN-002
- forbidden_claims: 已证明机制有效；已实现最终验收
- render_copy_policy: 可以压缩标签，不得改变置信度、范围、数字、来源或行动

## 信息层级

- primary_message: 核心假设必须可证伪
- supporting_arguments: 已观察信号；证据边界；控制变量；试点设计
- de_emphasized_details: 非关键元数据只放在微标签
- reading_order: 标题；核心假设；支持信号；控制变量；试点
- management_judgment: 是否批准有边界的验证，而不是直接扩围

## 构图

- layout_family: hierarchical-bento
- rationale: 不同证据共同支持一个可证伪命题
- focal_object: 中央主假设卡
- region_map: 左侧事实；中央命题；右侧控制与试点
- primary_secondary_ratio: 主卡至少为单张次卡的 1.5 倍
- card_count: 4
- nesting: 主卡内允许三个指标子卡
- connector_semantics: 只连接真实推理关系
- density_strategy: 40%–60% 卡片覆盖，其余留白

## 视觉系统

- active_palette_roles: 深色主卡；白色事实卡；浅蓝证据边界；紫色有界试点
- typography_ladder: 标题；主命题；区块标题；正文；辅助；微标签
- phrase_emphasis: 可证伪
- spacing_and_shape: 24px 网格；主卡大圆角；次卡小圆角；最多一处轻阴影
- prohibited_motifs: 左侧长蓝条；背景图片；渐变；等权卡片墙
- exceptions: 无

## 修订模式

- mode: recompose
- reason: 重新建立焦点、阅读顺序和卡片层级
- patch_defect: none
- fix_attempts_for_candidate: 0

## 输出与质量要求

- canvas: 1280×720
- safe_area: x=64..1216, y=64..656
- office_safe_svg: 只使用允许元素；无外部资源、脚本、CSS、滤镜或渐变
- text: 系统字体；显式 tspan；关键内容不得低于可读性下限
- source_metadata: 相关组保留 data-source-id
- qa: 结构、锁定内容、来源、几何、真实渲染焦点、扫描顺序、层级、语义色、卡片密度
```

- [ ] **Step 3: Create the first failing contract test**

Create `tests/test_visual_generation_contract.py`:

```python
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


class VisualGenerationContractTests(unittest.TestCase):
    REQUIRED_BRIEF_HEADINGS = {
        "来源与版本",
        "锁定内容",
        "信息层级",
        "构图",
        "视觉系统",
        "修订模式",
        "输出与质量要求",
    }

    def setUp(self) -> None:
        self.reference = skill_root() / "references" / "visual-brief-and-generation.md"
        self.skill = skill_root() / "SKILL.md"
        self.workflow = skill_root() / "references" / "workflow.md"
        self.artifact = skill_root() / "references" / "artifact-contract.md"
        self.qa = skill_root() / "references" / "qa-and-revision.md"
        self.brief = repo_root() / "tests" / "fixtures" / "visual-briefs" / "S05.md"
        self.precedence = repo_root() / "tests" / "fixtures" / "visual-revision-precedence.json"

    def test_skill_requires_visual_brief_contract_before_svg(self):
        self.assertTrue(self.reference.exists())
        skill = read_text(self.skill)
        self.assertIn("visual-brief-and-generation.md", skill)
        self.assertLess(skill.index("visual-brief-and-generation.md"), skill.index("SVG 契约"))

    def test_fixture_has_every_required_brief_section(self):
        text = read_text(self.brief)
        headings = {
            line.removeprefix("## ").strip()
            for line in text.splitlines()
            if line.startswith("## ")
        }
        self.assertEqual(headings, self.REQUIRED_BRIEF_HEADINGS)
        for token in (
            "storyboard_snapshot_id",
            "theme_snapshot_id",
            "applied_visual_revision_ids",
            "primary_message",
            "reading_order",
            "layout_family",
            "focal_object",
            "typography_ladder",
            "prohibited_motifs",
            "mode: recompose",
            "office_safe_svg",
        ):
            self.assertIn(token, text)

    def test_precedence_fixture_keeps_history_and_one_active_value(self):
        payload = json.loads(read_text(self.precedence))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["history"]), 3)
        self.assertEqual(payload["expected_active_contract"]["title_rail"], "none")
        self.assertEqual(payload["expected_active_contract"]["layout_family"], "hierarchical-bento")
        self.assertIn("visual-revision-1:title_rail", payload["expected_superseded_rules"])

    def test_contract_names_patch_recompose_and_legacy_synthesis(self):
        combined = "\n".join(
            read_text(path).lower()
            for path in (self.reference, self.workflow, self.artifact, self.qa)
            if path.exists()
        )
        for token in (
            "visual-briefs/<slide-id>.md",
            "visual-revision-<n>",
            "supersedes",
            "patch",
            "recompose",
            "几何底稿",
            "schema-v1",
        ):
            self.assertIn(token, combined)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the focused test and confirm the intended failure**

Run:

```bash
python -m unittest tests.test_visual_generation_contract -v
```

Expected: fixture tests pass; contract tests fail because `visual-brief-and-generation.md` does not exist and current references do not yet contain the new tokens.

- [ ] **Step 5: Record checkpoint**

Record that Task 1 created only synthetic fixtures/tests and that no Skill or FY26 artifact has changed. Do not commit because the workspace is not a Git repository.
