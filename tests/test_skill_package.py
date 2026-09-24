import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import parse_frontmatter, read_text, repo_root, skill_root  # noqa: E402


class SkillPackageTests(unittest.TestCase):
    def setUp(self):
        self.repo = repo_root()
        self.skill = skill_root()

    def test_ppt_start_frontmatter_is_portable_and_describes_the_actual_trigger(self):
        fields = parse_frontmatter(self.skill / "SKILL.md")
        self.assertEqual(fields["name"], "ppt-start")
        self.assertTrue(fields["description"].startswith("Use when "))
        self.assertLessEqual(len(fields["description"]), 500)
        self.assertEqual(set(fields), {"name", "description"})

    def test_ppt_start_is_a_short_ai_owned_orchestrator(self):
        text = read_text(self.skill / "SKILL.md")
        self.assertLessEqual(len(text.splitlines()), 90)
        for token in (
            "AI is the only workflow coordinator",
            "AI state",
            "interaction",
            "PASS",
            "INVALID",
            "UNAVAILABLE",
            "ppt-editable",
        ):
            self.assertIn(token, text)
        for token in (
            "ppt_runtime.py",
            "ppt_entry.py",
            "ppt_workflow_gate.py",
            "ppt_dashboard.py",
            "ListAgents",
            "ppt-svg-generator-sdk",
        ):
            self.assertNotIn(token, text)

    def test_ppt_start_package_contains_only_stateless_runtime_files(self):
        scripts = {path.name for path in (self.skill / "scripts").glob("*.py")}
        self.assertEqual(
            scripts,
            {
                "_source_intake.py",
                "_svg_geometry.py",
                "_svg_runtime.py",
                "_xml_safety.py",
                "ppt_source_intake.py",
                "svg_tool.py",
            },
        )
        for name in scripts:
            self.assertFalse(name.startswith(("_runtime", "_generation", "_workflow")))
            self.assertFalse(name.startswith(("ppt_runtime", "ppt_entry", "ppt_dashboard", "ppt_concurrency")))

    def test_claude_generator_agent_has_a_prompt_only_contract(self):
        path = self.repo / "hosts" / "claude-code" / "agents" / "ppt-svg-generator.md"
        fields = parse_frontmatter(path)
        text = read_text(path)
        self.assertEqual(fields["name"], "ppt-svg-generator")
        self.assertIn("complete prompt supplied by value", fields["description"])
        self.assertIn("Do not call tools.", text)
        self.assertIn("Do not inspect or read the working directory.", text)
        self.assertIn("exactly one fenced `xml` code block", text)
        self.assertNotIn("worktree", text)
        self.assertNotIn("ListAgents", text)

    def test_style_registry_has_only_current_pack_entries(self):
        registry_path = self.skill / "assets" / "styles" / "registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], 1)
        ids = [entry["id"] for entry in registry["styles"]]
        self.assertEqual(ids, ["jiawei-product", "canway-midyear-review"])
        for entry in registry["styles"]:
            pack = registry_path.parent / entry["id"]
            manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], entry["id"])
            for name in ("tokens.json", "STYLE.md", "prompt.md"):
                self.assertTrue((pack / name).is_file())

    def test_public_readme_links_to_current_user_documents(self):
        readme = read_text(self.repo / "README.md")
        for token in (
            "ppt-start",
            "ppt-editable",
            "ppt-style-extract",
            "PASS",
            "INVALID",
            "UNAVAILABLE",
            "docs/INSTALL.md",
            "docs/USER-GUIDE.md",
            "docs/ARCHITECTURE.md",
        ):
            self.assertIn(token, readme)
        self.assertNotIn("固定运行时", readme)
        self.assertNotIn("ppt_runtime.py", readme)


if __name__ == "__main__":
    unittest.main()
