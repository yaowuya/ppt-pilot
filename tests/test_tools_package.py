"""Static contract tests for the optional companion tooling and the
batch-concurrency / hash-fallback / CJK-width / preference-profile contracts
introduced by the group-A speedup changes.

These tests only prove package structure and written contracts; they do not
prove real host behaviour, PowerPoint import, or rendering (see
docs/acceptance.md evidence classes).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


GOLDEN_ITEM_11_PREFIX = "11. Hash-capability fallback:"
GOLDEN_AUTHORITY = "generation-prompt-byte-grammar.md"
GOLDEN_FILES = (
    "redesign-prompt.md",
    "visual-brief-and-generation.md",
    "artifact-contract.md",
)


class DeckDeliverToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tool_path = repo_root() / "tools" / "deck-deliver.ps1"

    def test_tool_exists_and_is_documented(self) -> None:
        self.assertTrue(self.tool_path.exists(), "tools/deck-deliver.ps1 must exist")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("deck-deliver.ps1", readme, "README must document the delivery tool")

    def test_tool_declares_parameters_and_outputs(self) -> None:
        tool = read_text(self.tool_path)
        for token in (
            "$RunDir",
            "$SkipPptx",
            "$ExportPng",
            "preview.html",
            "AddPicture",
            "audience_takeaway",
            "assertion_title",
            "delivery-result.json",
        ):
            self.assertIn(token, tool, f"deck-deliver.ps1 missing {token}")

    def test_deepseek_installer_exists_and_matches_marketplace_convention(self) -> None:
        installer_path = repo_root() / "tools" / "install-deepseek-plugin.ps1"
        self.assertTrue(installer_path.exists(), "tools/install-deepseek-plugin.ps1 must exist")
        installer = read_text(installer_path)
        for token in (
            "$MarketplaceRoot",
            "plugins\\ppt-pilot",
            ".codex-plugin\\plugin.json",
            "marketplace.json",
            "skills\\ppt-start",
            "ppt-start.bak-*",
        ):
            self.assertIn(token, installer, f"installer missing {token}")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("install-deepseek-plugin.ps1", readme, "README must document the installer")

    def test_tool_never_writes_into_skill_or_slides(self) -> None:
        tool = read_text(self.tool_path)
        # The tool's only persistent writes are preview.html and the delivery
        # manifest. Reading slides/ is expected; writing there is not.
        write_calls = [line for line in tool.splitlines() if "Write-Utf8File -Path" in line]
        self.assertEqual(len(write_calls), 2)
        self.assertTrue(any("$previewPath" in line for line in write_calls))
        self.assertTrue(any("$resultPath" in line for line in write_calls))
        for line in tool.splitlines():
            if "slides" in line.lower():
                self.assertNotRegex(line, r"Set-Content|Out-File|WriteAllText")


class GoldenHashFallbackContractTest(unittest.TestCase):
    """The golden byte-grammar block lives once in the authority file; the three
    stage contracts reference it by link and must not inline it anymore."""

    def setUp(self) -> None:
        self.authority_path = skill_root() / "references" / GOLDEN_AUTHORITY
        self.authority = read_text(self.authority_path)

    def test_authority_holds_item_11_exactly_once(self) -> None:
        matches = [
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        ]
        self.assertEqual(
            len(matches), 1, f"{GOLDEN_AUTHORITY} must contain item 11 exactly once"
        )

    def test_stage_contracts_reference_the_authority_without_inlining(self) -> None:
        for name in GOLDEN_FILES:
            text = read_text(skill_root() / "references" / name)
            self.assertIn(
                "generation-prompt-byte-grammar.md",
                text,
                f"{name} must link the byte-grammar authority",
            )
            self.assertNotIn(
                GOLDEN_ITEM_11_PREFIX,
                text,
                f"{name} must not inline item 11 anymore",
            )

    def test_item_11_defines_unhashed_fallback_rules(self) -> None:
        item = next(
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        )
        for token in (
            "`unhashed`",
            "`unhashed:<token>`",
            "`slides/.candidates/<slide-id>-<token>.svg`",
            "must not fabricate digests",
            "hard integrity violation",
        ):
            self.assertIn(token, item, f"item 11 missing {token}")

    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )
    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )


class BatchConcurrencyContractTest(unittest.TestCase):
    """Production batches may dispatch several compiled prompts to fresh
    generators concurrently, but write/validate/promotion stays serial."""

class CjkLineWidthContractTest(unittest.TestCase):
    def test_svg_contract_defines_width_formula(self) -> None:
        svg = read_text(skill_root() / "references" / "svg-contract.md")
        self.assertIn("行宽估算", svg)
        self.assertIn("1.0 × font-size", svg)
        self.assertIn("0.88", svg)
        self.assertIn("12% 余量", svg)

    def test_qa_geometry_check_references_the_formula(self) -> None:
        qa = read_text(skill_root() / "references" / "qa-and-revision.md")
        self.assertIn("行宽估算公式", qa)
        self.assertRegex(qa, r"svg-contract\.md\) 的行宽估算公式")


class PreferenceProfileContractTest(unittest.TestCase):
    def test_interaction_protocol_defines_profile_semantics(self) -> None:
        protocol = read_text(skill_root() / "references" / "interaction-protocol.md")
        for token in (
            "pilot-preferences.json",
            "当前请求明确答案 > 本运行已批准产物 > 偏好档案 > 安全默认值",
            "standing 授权",
            "咨询性输入",
        ):
            self.assertIn(token, protocol, f"interaction-protocol.md missing {token}")

    def test_artifact_contract_defines_profile_schema(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn("## 可选工作区偏好档案", artifact)
        self.assertIn("standing_authorizations", artifact)
        self.assertIn("不进入任何 `run.json` 恢复链", artifact)

    def test_brief_and_design_system_consume_the_profile(self) -> None:
        brief = read_text(skill_root() / "references" / "brief-and-research.md")
        design = read_text(skill_root() / "references" / "design-system.md")
        self.assertIn("pilot-preferences.json", brief)
        self.assertIn("偏好档案已记录品牌方向", design)


if __name__ == "__main__":
    unittest.main()
