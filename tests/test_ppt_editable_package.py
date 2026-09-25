import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import parse_frontmatter, relative_markdown_links, repo_root, skill_root  # noqa: E402


class SkillRootHelperTests(unittest.TestCase):
    def test_skill_root_uses_portable_skill_names(self):
        self.assertEqual(skill_root(), repo_root() / "skills" / "ppt-start")
        self.assertEqual(skill_root("ppt-editable"), repo_root() / "skills" / "ppt-editable")
        for name in ("", "Ppt-Editable", "ppt_editable", "../ppt"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    skill_root(name)


class PptEditablePackageTests(unittest.TestCase):
    def setUp(self):
        self.root = skill_root("ppt-editable")
        self.skill = self.root / "SKILL.md"
        self.input_output = self.root / "references" / "input-output-contract.md"

    def test_frontmatter_and_internal_links_are_portable(self):
        fields = parse_frontmatter(self.skill)
        self.assertEqual(fields["name"], "ppt-editable")
        self.assertTrue(fields["description"].startswith("Use when "))
        self.assertLessEqual(len(fields["description"]), 500)
        self.assertEqual(set(fields), {"name", "description"})
        for source in (self.skill, *sorted((self.root / "references").glob("*.md"))):
            for target in relative_markdown_links(source):
                with self.subTest(source=source.name, target=target):
                    self.assertTrue(target.is_file())
                    self.assertTrue(target.is_relative_to(self.root.resolve()))

    def test_skill_exposes_only_converter_and_verifier_entrypoints(self):
        text = self.skill.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 120)
        for relative in (
            "scripts/svg_to_editable_pptx.py",
            "references/input-output-contract.md",
            "references/editable-svg-subset.md",
            "references/verification.md",
        ):
            self.assertIn(relative, text)
            self.assertTrue((self.root / relative).is_file())
        self.assertNotIn("ppt_runtime.py", text)
        self.assertNotIn("ppt_workflow_gate.py", text)

    def test_input_contract_separates_ai_state_from_legacy_adapters(self):
        text = self.input_output.read_text(encoding="utf-8")
        for token in (
            "AI 状态",
            "legacy explicit",
            "legacy implicit",
            "slides",
            "complete",
            "partial",
            "transaction",
            "batch",
            "evidence_type: ai_state",
            "不需要",
        ):
            self.assertIn(token, text)
        self.assertIn("cannot fall through", text)
        self.assertIn("never modifies `.ppt-pilot/run.json`", text)

    def test_skill_preserves_editability_and_truthful_result_boundaries(self):
        text = self.skill.read_text(encoding="utf-8")
        for token in (
            "PASS",
            "GENERATED_UNVERIFIED",
            "BLOCKED",
            "FAILED_VERIFICATION",
            "group hierarchy",
            "editable text",
            "No image fallback",
            "SRC-<digits>",
            "never changes `run.json`",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
