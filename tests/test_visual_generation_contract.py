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
            "selected_style_id",
            "selected_style_display_name",
            "style_manifest_version",
            "style_reference_path",
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
            "`affected_scope`：允许 `deck`、`anchor`",
            "supersedes",
            "patch",
            "recompose",
            "几何底稿",
            "schema-v1",
        ):
            self.assertIn(token, combined)


if __name__ == "__main__":
    unittest.main()
