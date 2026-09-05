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
    "[[EFFECTIVE_PAGE_SPECIFICATION]]",
)
LEGACY_MARKER_RE = re.compile(
    "|".join(re.escape(marker) for marker in LEGACY_MARKERS),
    re.IGNORECASE,
)

HISTORICAL_CUE = re.compile(r"(?:legacy|历史|早期|旧协议|旧\s*marker)", re.IGNORECASE)
RETIRED_CUE = re.compile(
    r"(?:"
    r"(?:已|整体已)废弃|(?:已|应视为|必须视为)无效|(?:必须|应|一律)?拒绝|"
    r"(?:不得|禁止|严禁)(?:使用|注入|替换|出现|读取|采用|写入|生成)|不含|"
    r"不再(?:使用|注入|替换|读取|采用)|已被.{0,32}取代|只读|惰性|只作迁移历史|"
    r"(?:is|are)\s+(?:invalid|rejected|retired|deprecated|inert)|"
    r"must\s+be\s+rejected|(?:must\s+not|never)\s+(?:use|inject|replace|read|appear|write|generate)|"
    r"no\s+longer\s+(?:used|injected|replaced|read)|read-only|migration\s+(?:history|evidence)|inert"
    r")",
    re.IGNORECASE,
)
ACTIVE_LEGACY_CUE = re.compile(
    r"(?:"
    r"(?:禁止|严禁|不得|不能|不要|不可|不应)\s*(?:移除|删除|废弃|拒绝|禁用)"
    r"|不要将.{0,32}视为(?:废弃|无效)|(?:并非|不是).{0,32}(?:废弃|无效)"
    r"|(?:do\s+not|must\s+not|never)\s+(?:remove|reject|retire|deprecate|disable)"
    r"|(?:新运行|运行时|编译器).{0,16}(?:替换|注入|使用|采用|保留)"
    r"|(?:new\s+runs?|runtime|compiler).{0,24}(?:replace|inject|use|keep|retain|preserve)"
    r")",
    re.IGNORECASE,
)

RUNTIME_REPOSITORY_TEMPLATE_TARGET = re.compile(
    r"(?:generation-prompt-template\.md|(?:repository|仓库)[^。；;\n]{0,48}(?:prompt|template|模板))",
    re.IGNORECASE,
)
RUNTIME_FALLBACK_ACTION = re.compile(
    r"(?:fallback|fall\s+back|assemble|load|read|use|substitut|回退|兜底|组装|加载|读取|使用|采用|替代)",
    re.IGNORECASE,
)
RUNTIME_FALLBACK_RETIRED = re.compile(
    r"(?:no\s+runtime|do\s+not|must\s+not|never|only\s+(?:an?\s+)?authoring\s+seed|"
    r"不得|禁止|严禁|不可|绝不|不参与运行时|不允许运行时|从不|仅(?:是|作|作为).{0,20}authoring\s+seed)",
    re.IGNORECASE,
)


def _active_legacy_marker_violations(documents: tuple[tuple[str, str], ...]) -> list[str]:
    violations: list[str] = []
    for label, text in documents:
        for line_number, line in enumerate(text.splitlines(), start=1):
            for sentence in re.split(r"[。；.;]", line):
                for clause in re.split(r"[，,:：]", sentence):
                    marker_matches = tuple(LEGACY_MARKER_RE.finditer(clause))
                    if not marker_matches:
                        continue
                    # Every marker-bearing micro-clause must retire the marker
                    # itself. Cues never propagate across commas or colons.
                    if ACTIVE_LEGACY_CUE.search(clause):
                        pass
                    elif RETIRED_CUE.search(clause):
                        continue
                    for match in marker_matches:
                        violations.append(
                            f"{label}:{line_number}: {match.group(0)} in {clause.strip()}"
                        )
    return violations


def _active_runtime_fallback_violations(
    documents: tuple[tuple[str, str], ...]
) -> list[str]:
    violations: list[str] = []
    for label, text in documents:
        for line_number, line in enumerate(text.splitlines(), start=1):
            for clause in re.split(r"[。；;]", line):
                if (
                    RUNTIME_REPOSITORY_TEMPLATE_TARGET.search(clause)
                    and RUNTIME_FALLBACK_ACTION.search(clause)
                    and not RUNTIME_FALLBACK_RETIRED.search(clause)
                ):
                    violations.append(f"{label}:{line_number}: {clause.strip()}")
    return violations


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
            *sorted((self.skill_root / "references").glob("*.md")),
        )
        self.active_architecture_documents = (
            *self.active_runtime_authorities,
            *sorted(self.style_root.glob("*/STYLE.md")),
            repo_root() / "skills" / "ppt-style-extract" / "SKILL.md",
            repo_root()
            / "skills"
            / "ppt-style-extract"
            / "references"
            / "style-pack-verification.md",
            repo_root() / "README.md",
            repo_root() / "docs" / "ARCHITECTURE.md",
            repo_root() / "docs" / "USER-GUIDE.md",
            repo_root() / "docs" / "design.md",
            repo_root() / "docs" / "style-extract-design.md",
            repo_root() / "docs" / "acceptance.md",
            *sorted((repo_root() / "tests" / "prompts").glob("*.md")),
        )

    def test_active_styles_resolve_a_single_whole_line_narrative_template(self):
        style_extract_scripts = (
            repo_root() / "skills" / "ppt-style-extract" / "scripts"
        )
        if str(style_extract_scripts) not in sys.path:
            sys.path.insert(0, str(style_extract_scripts))
        from _style_extract.verify import (
            verify_prompt,
            verify_prompt_style_binding,
            verify_style_pack,
        )
        from tests.test_redesign_prompt_contract import (
            compile_style_prompt,
            style_template_path,
        )

        registry = json.loads(read_text(self.style_root / "registry.json"))
        self.assertTrue(registry["styles"])

        for style in registry["styles"]:
            with self.subTest(style_id=style["id"]):
                entrypoint = self.style_root / style["entrypoint"]
                manifest = json.loads(read_text(entrypoint))
                self.assertEqual(
                    manifest.get("files"),
                    {
                        "tokens": "tokens.json",
                        "guidance": "STYLE.md",
                        "prompt_template": "prompt.md",
                    },
                )
                template_relative = manifest["files"]["prompt_template"]
                template_path = entrypoint.parent / template_relative
                self.assertTrue(template_path.is_file())
                expected_relative = f"assets/styles/{style['id']}/prompt.md"
                self.assertEqual(style_template_path(style["id"]), expected_relative)
                self.assertEqual(
                    template_path.resolve(),
                    (self.skill_root / expected_relative).resolve(),
                )

                template = read_text(template_path)
                tokens = json.loads(read_text(entrypoint.parent / "tokens.json"))
                verify_style_pack(entrypoint.parent)
                verify_prompt(template)
                verify_prompt_style_binding(tokens, template)
                self.assertEqual(template.count(NARRATIVE_MARKER), 1)
                self.assertEqual(
                    [line for line in template.splitlines() if line == NARRATIVE_MARKER],
                    [NARRATIVE_MARKER],
                    "{{NARRATIVE}} must be the only content on its line",
                )
                for marker in LEGACY_MARKERS:
                    self.assertNotIn(marker, template)
                compiled = compile_style_prompt(
                    b"- block_id: S01-B1\n- clean narrative\n",
                    template_path.read_bytes(),
                )
                self.assertNotIn(NARRATIVE_MARKER.encode("utf-8"), compiled)

    def test_canonical_authority_requires_style_owned_template_without_runtime_fallback(self):
        text = read_text(self.canonical_compilation_authority)
        self.assertIn("files.prompt_template", text)
        self.assertIn(NARRATIVE_MARKER, text)
        self.assertRegex(text, r"whole-line[^\n。]{0,80}\{\{NARRATIVE\}\}")
        self.assertIn("there is no runtime repository-template fallback", text)
        self.assertIn("only an authoring seed", text)

    def test_legacy_markers_appear_only_in_explicit_retirement_or_rejection_clauses(self):
        documents = tuple(
            (str(path.relative_to(repo_root())), read_text(path))
            for path in self.active_architecture_documents
        )
        violations = _active_legacy_marker_violations(documents)

        self.assertEqual(
            violations,
            [],
            "legacy markers are active replacement instructions:\n" + "\n".join(violations),
        )

    def test_active_documents_never_authorize_repository_template_runtime_fallback(self):
        documents = tuple(
            (str(path.relative_to(repo_root())), read_text(path))
            for path in self.active_architecture_documents
        )
        self.assertEqual(
            _active_runtime_fallback_violations(documents),
            [],
            "repository authoring seed is active at runtime:\n"
            + "\n".join(_active_runtime_fallback_violations(documents)),
        )

    def test_runtime_fallback_scan_catches_paraphrased_active_instructions(self):
        for text in (
            "运行时缺少风格模板时，回退到仓库 generation-prompt-template.md。",
            "If the style prompt is missing, use the repository template as fallback.",
            "从仓库模板组装 page prompt。",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    len(_active_runtime_fallback_violations((("synthetic.md", text),))),
                    1,
                )

        for text in (
            "仓库 generation-prompt-template.md 仅作为 authoring seed，不参与运行时解析。",
            "Do not assemble a runtime prompt from repository templates.",
            "There is no runtime repository-template fallback.",
        ):
            with self.subTest(retired=text):
                self.assertEqual(
                    _active_runtime_fallback_violations((("synthetic.md", text),)),
                    [],
                )
    def test_retired_clause_cannot_mask_adjacent_active_instruction(self):
        for delimiter in ("。", "；", ".", ";", "，", ",", "：", ":"):
            text = (
                "Legacy [[EFFECTIVE_PAGE_SPECIFICATION]] is rejected"
                f"{delimiter}new runs replace [[STYLE_BASELINE]]"
            )
            with self.subTest(delimiter=delimiter):
                violations = _active_legacy_marker_violations((("synthetic.md", text),))
                self.assertEqual(len(violations), 1)
                self.assertIn("[[STYLE_BASELINE]]", violations[0].upper())

    def test_legacy_marker_scan_is_case_insensitive(self):
        violations = _active_legacy_marker_violations(
            (("synthetic.md", "new runs replace [[style_baseline]]"),)
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("[[style_baseline]]", violations[0])

    def test_retirement_words_cannot_mask_active_double_negation(self):
        for text in (
            "新运行禁止移除 [[STYLE_BASELINE]]",
            "不得废弃 [[STYLE_BASELINE]]",
            "严禁废弃 [[STYLE_BASELINE]]",
            "不要将 [[STYLE_BASELINE]] 视为废弃",
            "do not reject [[STYLE_BASELINE]]",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    len(_active_legacy_marker_violations((("synthetic.md", text),))),
                    1,
                )

    def test_retirement_cue_cannot_cross_comma_to_mask_unlisted_active_verb(self):
        for text in (
            "Legacy [[EFFECTIVE_PAGE_SPECIFICATION]] is rejected, continue populating [[STYLE_BASELINE]]",
            "旧协议 [[EFFECTIVE_PAGE_SPECIFICATION]] 已废弃，仍需填充 [[STYLE_BASELINE]]",
        ):
            with self.subTest(text=text):
                violations = _active_legacy_marker_violations((("synthetic.md", text),))
                self.assertEqual(len(violations), 1)
                self.assertIn("STYLE_BASELINE", violations[0].upper())

    def test_ambiguous_modal_or_migration_word_is_not_retirement(self):
        for text in (
            "不得遗漏 [[STYLE_BASELINE]]",
            "禁止跳过 [[STYLE_BASELINE]]",
            "迁移时填充 [[STYLE_BASELINE]]",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    len(_active_legacy_marker_violations((("synthetic.md", text),))),
                    1,
                )


if __name__ == "__main__":
    unittest.main()
