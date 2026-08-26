import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


VISUAL_STAGES = {"theme", "anchor", "production", "qa", "complete"}


def visual_stage_allowed(run: dict) -> bool:
    return (
        run.get("stage") in VISUAL_STAGES
        and run.get("manuscript_review", {}).get("state") == "manuscript_approved"
    )


class WorkflowContractTests(unittest.TestCase):
    WORKFLOW_STAGES = [
        "brief",
        "research",
        "outline",
        "storyboard",
        "manuscript_review",
        "theme",
        "anchor",
        "production",
        "qa",
        "complete",
    ]

    REQUIRED_MODE_TOKENS = {"guided", "auto", "new", "resume", "revise"}
    REVIEW_STATES = {"review_unavailable", "manuscript_blocked"}

    REQUIRED_ARTIFACTS = [
        "大纲.md",
        "slides/",
        ".ppt-pilot/",
    ]

    REQUIRED_RUN_FIELDS = {
        "schema_version",
        "deck_id",
        "mode",
        "stage",
        "manuscript_review",
        "dirty_slides",
    }
    REQUIRED_REVIEW_FIELDS = {
        "required",
        "round",
        "mode",
        "state",
        "status",
        "latest_report",
        "open_blocking_findings",
        "review_history",
    }

    def setUp(self):
        self.reference_root = skill_root() / "references"
        self.workflow_path = self.reference_root / "workflow.md"
        self.contract_path = self.reference_root / "artifact-contract.md"
        self.brief_research_path = self.reference_root / "brief-and-research.md"
        self.narrative_path = self.reference_root / "narrative-and-storyboard.md"
        self.qa_path = self.reference_root / "qa-and-revision.md"
        self.prompt_root = Path(__file__).resolve().parent / "prompts"

    def test_workflow_reference_exists(self):
        self.assertTrue(self.workflow_path.exists(), f"Missing workflow reference file: {self.workflow_path}")

    def _extract_stage_order(self, text: str) -> list[str]:
        flow_lines = [
            line
            for line in text.splitlines()
            if "->" in line and "brief" in line.lower() and "complete" in line.lower()
        ]
        self.assertTrue(flow_lines, "No stage flow line containing -> found in workflow.md")

        text_line = " -> ".join(flow_lines)
        stages = [
            match.group(0)
            for match in re.finditer(
                r"\b(?:brief|research|outline|storyboard|manuscript_review|theme|anchor|production|qa|complete)\b",
                text_line.lower(),
            )
        ]
        return stages

    def test_workflow_stage_order_is_explicit_and_exact(self):
        text = read_text(self.workflow_path).lower()
        stages = self._extract_stage_order(text)
        self.assertGreaterEqual(len(stages), len(self.WORKFLOW_STAGES), "Expected at least one occurrence of every workflow stage")
        self.assertEqual(stages[: len(self.WORKFLOW_STAGES)], self.WORKFLOW_STAGES)

    def test_workflow_modes_and_review_hard_gate(self):
        text = read_text(self.workflow_path)
        lower = text.lower()

        for mode in self.REQUIRED_MODE_TOKENS:
            self.assertIn(mode, lower, f"workflow.md should declare mode: {mode}")

        self.assertIn("硬质量门", lower)
        self.assertRegex(
            lower,
            r"最多(?:执行)?三轮|三轮文稿审查",
            "workflow.md 应明确文稿审查最多三轮",
        )
        self.assertTrue(
            all(state in lower for state in self.REVIEW_STATES),
            f"workflow.md should include explicit states: {sorted(self.REVIEW_STATES)}",
        )

    def test_artifact_contract_reference_exists(self):
        self.assertTrue(self.contract_path.exists(), f"Missing artifact contract file: {self.contract_path}")

    def _extract_section_list(self, text: str, section_name: str) -> list[str]:
        pattern = rf"##\s+{re.escape(section_name)}\n(?P<body>(?:.|\n)*?)(?:\n##\s|\Z)"
        match = re.search(pattern, text, re.IGNORECASE)
        self.assertIsNotNone(match, f"Missing section {section_name!r} in artifact contract")

        body = match.group("body")
        items = re.findall(r"^\s*[-*]\s+`?([^`\n]+)`?\s*$", body, flags=re.MULTILINE)
        return [item.strip() for item in items if item.strip()]

    def test_artifact_contract_required_artifacts(self):
        text = read_text(self.contract_path)
        items = self._extract_section_list(text, "必需产物")
        for artifact in self.REQUIRED_ARTIFACTS:
            self.assertIn(artifact, items, f"artifact-contract.md missing required artifact {artifact}")

    def test_artifact_contract_run_json_fields(self):
        text = read_text(self.contract_path).lower()
        field_lines = re.findall(
            r"^\s*[-*]\s+`?([a-z_]+)`?\s*$",
            text,
            flags=re.MULTILINE,
        )
        fields = {name for name in field_lines if name in self.REQUIRED_RUN_FIELDS}
        self.assertEqual(fields, self.REQUIRED_RUN_FIELDS)

        self.assertRegex(
            text,
            r"run\.json.*schema_version",
            "artifact-contract.md should describe schema_version as a required run.json field",
        )
        for field in self.REQUIRED_REVIEW_FIELDS:
            self.assertIn(
                f"`{field}`",
                text,
                f"artifact-contract.md missing manuscript_review field {field}",
            )

    def test_artifact_contract_invalidation_rules_are_explicit(self):
        text = read_text(self.contract_path).lower()

        self.assertRegex(
            text,
            r"`brief`.*全部下游",
            "简报变化应使全部下游产物失效",
        )
        self.assertRegex(
            text,
            r"`outline`.*`storyboard`.*全部下游",
            "大纲变化应使故事板及全部下游产物失效",
        )
        self.assertRegex(
            text,
            r"`source`.*`storyboard`.*文稿审查.*视觉",
            "来源或故事板变化应使文稿审查与视觉产物失效",
        )
        self.assertRegex(
            text,
            r"`theme`.*`samples`.*`slides`.*qa",
            "主题变化应使样例、页面与 QA 失效",
        )
        self.assertRegex(
            text,
            r"单页.*标记为脏",
            "单页视觉修改只能标脏该页",
        )

        self.assertIn("运行目录", text)
        self.assertIn("不得覆盖", text)
        self.assertIn("更新", text)
        self.assertIn("每完成一个阶段", text)

    def test_brief_and_research_contract_covers_decisions_and_evidence(self):
        self.assertTrue(self.brief_research_path.exists())
        text = read_text(self.brief_research_path).lower()
        required = {
            "audience",
            "purpose",
            "desired audience action",
            "slide count",
            "presentation time",
            "required content",
            "forbidden content",
            "evidence policy",
            "confidentiality",
            "language",
            "brand/style",
            "source_id",
            "publication_date",
            "accessed_at",
            "confidence",
            "unverified",
        }
        for token in required:
            self.assertIn(token, text, f"brief-and-research.md missing {token}")
        for route in ("topic-only", "complete brief", "source-driven", "resume"):
            self.assertIn(route, text, f"brief-and-research.md missing {route} route")
        self.assertIn("用户提供的资料", text)
        self.assertIn("不得把机密内容", text)
        self.assertIn("网络", text)
        self.assertIn("限定", text)
        self.assertIn("绝不能虚构", text)

    def test_narrative_and_storyboard_contract_is_assertion_led(self):
        self.assertTrue(self.narrative_path.exists())
        text = read_text(self.narrative_path).lower()
        for token in (
            "结论先行",
            "金字塔",
            "一页一个结论",
            "去重",
            "拆分",
            "缩小字号",
        ):
            self.assertIn(token, text, f"narrative-and-storyboard.md 缺少 {token}")
        storyboard_fields = {
            "slide_id",
            "role",
            "assertion_title",
            "audience_takeaway",
            "content_blocks",
            "source_ids",
            "visual_intent",
            "layout_family",
            "density_budget",
            "previous_link",
            "next_link",
        }
        for field in storyboard_fields:
            self.assertRegex(text, rf"`{field}`", f"storyboard field missing: {field}")
        self.assertIn("manuscript_review", text)

    def test_content_behavior_prompts_define_expected_artifacts_and_states(self):
        expected = {
            "guided-topic-only.md",
            "source-driven.md",
            "review-blocker.md",
        }
        self.assertTrue(self.prompt_root.is_dir())
        self.assertTrue(expected.issubset({path.name for path in self.prompt_root.iterdir()}))

        guided = read_text(self.prompt_root / "guided-topic-only.md").lower()
        for artifact in ("简报.md", "大纲.md", "故事板.md", "run.json"):
            self.assertIn(artifact, guided)
        self.assertIn("guided", guided)

        source_driven = read_text(self.prompt_root / "source-driven.md").lower()
        for artifact in ("来源.md", "研究.md", "大纲.md", "故事板.md"):
            self.assertIn(artifact, source_driven)
        self.assertIn("user sources", source_driven)

        blocker = read_text(self.prompt_root / "review-blocker.md").lower()
        self.assertRegex(blocker, r"\b(?:47|73|91)%")
        self.assertIn("unsupported", blocker)
        self.assertIn("manuscript_blocked", blocker)
        self.assertIn("stop after the first independent review", blocker)
        self.assertIn("do not revise", blocker)
        self.assertIn("no svg", blocker)
        self.assertIn("no theme.json", blocker)

    def test_source_driven_prompt_has_runnable_synthetic_inputs(self):
        prompt = read_text(self.prompt_root / "source-driven.md")
        acceptance = read_text(repo_root() / "docs" / "acceptance.md").lower()
        input_root = repo_root() / "tests" / "inputs"
        expected = {
            "retention-study.pdf",
            "customer-interviews.md",
            "q2-cohort.csv",
        }

        for name in expected:
            with self.subTest(name=name):
                self.assertIn(f"inputs/{name}", prompt)

        missing = sorted(name for name in expected if not (input_root / name).is_file())
        self.assertEqual(missing, [], f"Missing acceptance inputs: {missing}")
        self.assertIn("tests/inputs/", acceptance)
        self.assertIn("复制", acceptance)

        pdf = (input_root / "retention-study.pdf").read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-"), "retention-study.pdf must be an actual PDF")
        self.assertIn(b"Synthetic acceptance fixture", pdf)

        for name in ("customer-interviews.md", "q2-cohort.csv"):
            text = read_text(input_root / name).lower()
            self.assertIn("synthetic acceptance fixture", text)

    def test_qa_contract_covers_slide_and_deck_quality(self):
        self.assertTrue(self.qa_path.exists())
        text = read_text(self.qa_path).lower()
        for token in (
            "xml",
            "禁止特性",
            "来源覆盖",
            "溢出",
            "重叠",
            "对比度",
            "对齐",
            "整套演示 qa",
            "叙事",
            "节奏",
            "visual_qa: rendered",
            "visual_qa: not_rendered",
            "两次修复",
            "single-column",
            "two-column",
            "硬检查",
            "每个非背景元素",
            "页脚",
            "页码",
            "渲染证据",
        ):
            self.assertIn(token, text, f"qa-and-revision.md 缺少 {token}")

    def test_production_resume_and_revision_semantics_are_explicit(self):
        qa = read_text(self.qa_path).lower()
        skill = read_text(skill_root() / "SKILL.md").lower()
        artifact = read_text(self.contract_path).lower()
        visual_brief = read_text(self.reference_root / "visual-brief-and-generation.md").lower()
        combined = "\n".join((qa, skill, artifact, visual_brief))
        self.assertRegex(combined, r"每批 3[–-]4 页")
        self.assertIn("每次只写入并验证一个 svg", combined)
        self.assertIn("更新 `run.json`", combined)
        self.assertIn("每完成一个持久阶段", combined)
        self.assertIn("停止", combined)
        self.assertIn("硬检查失败", combined)

        for token in (
            "visual-briefs/<slide-id>.md",
            "patch",
            "recompose",
            "当前 svg",
            "几何底稿",
            "supersedes",
        ):
            self.assertIn(token, combined)

        self.assertIn("先读取 `run.json`", combined)
        self.assertIn("已批准的上游", combined)
        self.assertIn("重新计算", combined)
        self.assertIn("visual-only", combined)
        self.assertIn("non-factual copy", combined)
        self.assertIn("不重新运行文稿审查", combined)
        self.assertIn("主张", combined)
        self.assertIn("来源", combined)
        self.assertIn("新的文稿审查", combined)

    def test_visual_stage_guard_uses_persistent_review_state(self):
        approved = {
            "stage": "production",
            "manuscript_review": {"state": "manuscript_approved"},
        }
        blocked = {
            "stage": "production",
            "manuscript_review": {"state": "manuscript_blocked"},
        }
        unavailable = {
            "stage": "production",
            "manuscript_review": {"state": "review_unavailable"},
        }
        self.assertTrue(visual_stage_allowed(approved))
        self.assertFalse(visual_stage_allowed(blocked))
        self.assertFalse(visual_stage_allowed(unavailable))

        qa = read_text(self.qa_path).lower()
        workflow = read_text(self.workflow_path).lower()
        artifact = read_text(self.contract_path).lower()
        design = read_text(self.reference_root / "design-system.md").lower()
        for text, label in (
            (qa, "qa-and-revision.md"),
            (artifact, "artifact-contract.md"),
            (design, "design-system.md"),
        ):
            self.assertIn(
                "run.json.manuscript_review.state",
                text,
                f"{label} must guard visual stages with persistent review state",
            )
        self.assertNotIn("production starts only from `run.json.stage: manuscript_approved`", qa)
        self.assertIn("`manuscript_approved` 检查点", workflow)
        self.assertIn("设置 `stage: theme`", workflow)
        self.assertIn("设置 `stage: anchor`", workflow)
        self.assertIn("设置 `stage: production`", workflow)

    def test_resume_and_revision_prompts_define_expected_branching(self):
        expected = {"resume-after-review.md", "revise-single-slide.md"}
        self.assertTrue(expected.issubset({path.name for path in self.prompt_root.iterdir()}))

        resume = read_text(self.prompt_root / "resume-after-review.md").lower()
        for token in (
            "run-review-approved.json",
            "manuscript_approved",
            "read run.json first",
            "do not repeat research",
            "theme.json",
            "anchor",
        ):
            self.assertIn(token, resume)

        approved_run_path = repo_root() / "tests" / "fixtures" / "run-review-approved.json"
        approved_run = json.loads(read_text(approved_run_path))
        self.assertEqual(approved_run["deck_id"], "resume-approved")
        self.assertEqual(approved_run["mode"], "auto")

        companion_root = repo_root() / "tests" / "fixtures" / "resume-approved"
        legacy_companions = {
            "brief.md",
            "research.md",
            "sources.md",
            "outline.md",
            "storyboard.md",
            "manuscript-review.md",
        }
        present = {path.name for path in companion_root.iterdir()} if companion_root.is_dir() else set()
        self.assertEqual(legacy_companions - present, set())
        self.assertEqual(
            approved_run["manuscript_review"]["latest_report"],
            "manuscript-review.md",
        )

        acceptance = read_text(repo_root() / "docs" / "acceptance.md").lower()
        self.assertIn("tests/fixtures/resume-approved/", acceptance)
        self.assertIn("run-review-approved.json", acceptance)
        self.assertIn("旧英文运行兼容夹具", acceptance)
        self.assertRegex(acceptance, r"resume-after-review\.md.*tests/inputs")
        self.assertRegex(acceptance, r"revise-single-slide\.md.*三个相互独立.*完整")

        companion_sources = read_text(companion_root / "sources.md")
        self.assertNotIn("tests/inputs/", companion_sources)
        for name in ("retention-study.pdf", "customer-interviews.md", "q2-cohort.csv"):
            self.assertIn(f"inputs/{name}", companion_sources)

        revise = read_text(self.prompt_root / "revise-single-slide.md").lower()
        for token in (
            "branch a — patch",
            "branch b — recompose",
            "branch c — factual change",
            "24 px",
            "full brief + current svg + exact defect",
            "do not use old svg as a geometric base",
            "fresh independent subagent first",
            "inline fallback",
        ):
            self.assertIn(token, revise)


if __name__ == "__main__":
    unittest.main()
