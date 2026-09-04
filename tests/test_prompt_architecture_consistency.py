import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


NARRATIVE_MARKER = "{{NARRATIVE}}"
LEGACY_MARKERS = (
    "[[CANONICAL_NARRATIVE_BULLETS]]",
    "[[STYLE_BASELINE]]",
)


class PromptArchitectureConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_root = skill_root()
        self.style_root = self.skill_root / "assets" / "styles"
        self.fallback_template = (
            self.skill_root / "references" / "generation-prompt-template.md"
        )
        self.canonical_compilation_authority = (
            self.skill_root / "references" / "generation-prompt-byte-grammar.md"
        )
        self.active_runtime_authorities = (
            self.skill_root / "SKILL.md",
            self.skill_root / "references" / "artifact-contract.md",
            self.skill_root / "references" / "redesign-prompt.md",
            self.canonical_compilation_authority,
            self.skill_root / "references" / "visual-brief-and-generation.md",
            self.skill_root / "references" / "design-system.md",
            self.skill_root / "references" / "qa-and-revision.md",
            self.skill_root / "references" / "workflow.md",
        )
        self.active_architecture_documents = (
            *self.active_runtime_authorities,
            repo_root() / "README.md",
            repo_root() / "docs" / "ARCHITECTURE.md",
            repo_root() / "docs" / "design.md",
            repo_root() / "docs" / "acceptance.md",
        )

    def test_active_styles_resolve_a_single_whole_line_narrative_template(self):
        registry = json.loads(read_text(self.style_root / "registry.json"))
        self.assertTrue(registry["styles"])

        for style in registry["styles"]:
            with self.subTest(style_id=style["id"]):
                entrypoint = self.style_root / style["entrypoint"]
                manifest = json.loads(read_text(entrypoint))
                template_relative = manifest.get("files", {}).get("prompt_template")
                template_path = (
                    entrypoint.parent / template_relative
                    if template_relative
                    else self.fallback_template
                )
                self.assertTrue(template_path.is_file())

                template = read_text(template_path)
                self.assertEqual(template.count(NARRATIVE_MARKER), 1)
                self.assertEqual(
                    [line for line in template.splitlines() if line == NARRATIVE_MARKER],
                    [NARRATIVE_MARKER],
                    "{{NARRATIVE}} must be the only content on its line",
                )
                for marker in LEGACY_MARKERS:
                    self.assertNotIn(marker, template)

    def test_canonical_authority_selects_style_owned_template_with_repo_fallback(self):
        text = read_text(self.canonical_compilation_authority)
        self.assertIn("files.prompt_template", text)
        self.assertIn(NARRATIVE_MARKER, text)
        self.assertRegex(text, r"whole-line[^\n。]{0,80}\{\{NARRATIVE\}\}")
        self.assertRegex(
            text,
            re.compile(
                r"(?:兜底|fallback)[^\n。]{0,160}generation-prompt-template\.md"
                r"|generation-prompt-template\.md[^\n。]{0,160}(?:兜底|fallback)",
                re.IGNORECASE,
            ),
        )

    def test_legacy_markers_appear_only_in_explicit_retirement_or_rejection_clauses(self):
        historical_cue = re.compile(r"(?:legacy|历史|早期|旧协议|旧\s*marker)", re.IGNORECASE)
        retired_cue = re.compile(
            r"(?:废弃|拒绝|invalid|无效|不得|禁止|不再|取代|只读|迁移|inert|reject)",
            re.IGNORECASE,
        )

        violations: list[str] = []
        for path in self.active_architecture_documents:
            relative = path.relative_to(repo_root())
            for line_number, line in enumerate(read_text(path).splitlines(), start=1):
                for clause in re.split(r"[。；]", line):
                    if not any(marker in clause for marker in LEGACY_MARKERS):
                        continue
                    if historical_cue.search(clause) and retired_cue.search(clause):
                        continue
                    violations.append(f"{relative}:{line_number}: {clause.strip()}")

        self.assertEqual(
            violations,
            [],
            "legacy markers are active replacement instructions:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
