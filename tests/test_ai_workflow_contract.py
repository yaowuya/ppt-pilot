import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import read_text, relative_markdown_links, repo_root, skill_root  # noqa: E402


ROOT = repo_root()
PPT_START = skill_root()
PPT_EDITABLE = skill_root("ppt-editable")
ACTIVE_DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "INSTALL.md",
    ROOT / "docs" / "USER-GUIDE.md",
    ROOT / "docs" / "ARCHITECTURE.md",
    ROOT / "docs" / "design.md",
    ROOT / "docs" / "acceptance.md",
    ROOT / "docs" / "RESILIENT-WORKFLOW.md",
    PPT_START / "SKILL.md",
    *sorted((PPT_START / "references").glob("*.md")),
    PPT_EDITABLE / "SKILL.md",
    *sorted((PPT_EDITABLE / "references").glob("*.md")),
)


class AIWorkflowContractTests(unittest.TestCase):
    def active_docs(self):
        for path in ACTIVE_DOCS:
            if path.exists():
                yield path

    def combined(self):
        return "\n".join(read_text(path) for path in self.active_docs())

    def test_active_instructions_do_not_invoke_deleted_workflow_surfaces(self):
        forbidden = (
            "ppt_runtime.py",
            "ppt_entry.py",
            "ppt_workflow_gate.py",
            "ppt_review_snapshot.py",
            "ppt_dashboard.py",
            "advance --allow-partial",
            "--skip-slide",
            "revise-visual",
            "ppt-svg-generator-sdk",
            "ListAgents",
            "runtime-canonical-owners.md",
            "deepseek-harness.md",
            "host-isolation-adapters.md",
            "live-dashboard.md",
        )
        for path in self.active_docs():
            text = read_text(path)
            for token in forbidden:
                with self.subTest(path=path.relative_to(ROOT), token=token):
                    self.assertNotIn(token, text)

    def test_ai_state_is_the_single_workflow_owner_and_tools_have_three_outcomes(self):
        skill = read_text(PPT_START / "SKILL.md")
        state = read_text(PPT_START / "references" / "ai-state.md")
        self.assertLessEqual(len(skill.splitlines()), 90)
        self.assertIn("AI is the only workflow coordinator", skill)
        self.assertIn("ai-state.md", skill)
        for token in ("PASS", "INVALID", "UNAVAILABLE", "tool_unavailable", "slides", "delivery"):
            self.assertIn(token, state)
        self.assertRegex(state, r"只有[^\n]{0,40}真实[^\n]{0,30}生成[^\n]{0,30}(?:attempts|次数)")
        self.assertRegex(state, r"UNAVAILABLE[^\n]{0,100}(?:不改变|保持)[^\n]{0,30}(?:stage|阶段|attempts)")
        self.assertRegex(state, r"INVALID[^\n]{0,100}(?:页面|page)[^\n]{0,30}(?:失败|failed)")

    def test_ai_state_qa_partition_is_a_single_machine_owner(self):
        qa = read_text(PPT_START / "references" / "qa-and-revision.md")
        editable = read_text(PPT_EDITABLE / "references" / "input-output-contract.md")
        for token in (
            "ppt-pilot-qa-json",
            "target_slide_ids",
            "promoted_slide_ids",
            "missing_slide_ids",
            "delivery.status",
        ):
            self.assertIn(token, qa)
        self.assertIn("ppt-pilot-qa-json", editable)

    def test_pending_answer_is_applied_directly_without_an_answer_command(self):
        protocol = read_text(PPT_START / "references" / "interaction-protocol.md")
        for token in (
            "status: answered",
            "原始回答",
            "规范化决定",
            "interaction_history",
            "skipped",
            "attempts",
            "最早可执行",
        ):
            self.assertIn(token, protocol)
        self.assertRegex(
            protocol,
            r"(?:读取|读入).*pending_interaction[\s\S]{0,500}answered[\s\S]{0,500}(?:应用|写入)[\s\S]{0,500}(?:清除|替换)",
        )
        self.assertNotRegex(protocol, r"(?m)^\s*(?:python|py)\s+.*scripts/")

    def test_prompt_contract_distinguishes_source_ids_from_transient_block_ids(self):
        grammar = read_text(PPT_START / "references" / "generation-prompt-byte-grammar.md")
        visual = read_text(PPT_START / "references" / "visual-brief-and-generation.md")
        svg = read_text(PPT_START / "references" / "svg-contract.md")
        combined = grammar + "\n" + visual + "\n" + svg
        self.assertIn("source ID", combined)
        self.assertIn("block ID", combined)
        self.assertIn("data-block-id", combined)
        self.assertIn("data-source-id", combined)
        self.assertRegex(combined, r"source ID[^\n]{0,100}(?:不得|不能)[^\n]{0,50}(?:Prompt|generator)")
        self.assertRegex(combined, r"block ID[^\n]{0,100}(?:Prompt|generator|叙事)")
        self.assertRegex(combined, r"(?:移除|删除)[^\n]{0,60}data-block-id")
        self.assertIn('{"S01-B1": []}', combined)
        self.assertRegex(combined, r"(?:没有|无)[^\n]{0,80}content block[^\n]{0,80}\{\}")

    def test_machine_source_ids_remain_in_ledgers_and_never_visible_slide_text(self):
        brief = read_text(PPT_START / "references" / "brief-and-research.md")
        readme = read_text(ROOT / "README.md")
        architecture = read_text(ROOT / "docs" / "ARCHITECTURE.md")
        for text in (readme, architecture):
            self.assertIn("来源.md", text)
            self.assertIn("source map", text)
            self.assertIn("data-source-id", text)
            self.assertRegex(text, r"(?:绝不|不能).*可见")
        self.assertIn("稳定 ID", brief)
        self.assertIn("SRC-001", brief)

    def test_editable_docs_describe_ai_state_and_legacy_as_separate_adapters(self):
        text = read_text(PPT_EDITABLE / "references" / "input-output-contract.md")
        for token in ("AI 状态", "slides", "complete", "partial", "legacy", "transaction", "batch"):
            self.assertIn(token, text)
        self.assertRegex(text, r"AI 状态[\s\S]{0,700}(?:不需要|不要求)[^\n]{0,80}(?:transaction|batch)")
        self.assertRegex(text, r"Legacy explicit[\s\S]{0,700}(?:strict validator|byte-compatible)")

    def test_active_markdown_links_resolve(self):
        historical_roots = (ROOT / "docs" / "superpowers", ROOT / "acceptance-evidence")
        for path in self.active_docs():
            for target in relative_markdown_links(path):
                if any(target.is_relative_to(root) for root in historical_roots):
                    continue
                with self.subTest(source=path.relative_to(ROOT), target=target):
                    self.assertTrue(target.exists(), "{} links missing {}".format(path, target))

    def test_retired_dashboard_document_is_not_active(self):
        self.assertFalse((ROOT / "docs" / "LIVE-DASHBOARD.md").exists())


if __name__ == "__main__":
    unittest.main()
