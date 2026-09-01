import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import parse_frontmatter, read_text, repo_root, skill_root


class SkillPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = repo_root() / "README.md"
        self.design = repo_root() / "docs" / "design.md"
        self.acceptance = repo_root() / "docs" / "acceptance.md"

    def test_shared_frontmatter_uses_only_portable_fields(self):
        fields = parse_frontmatter(skill_root() / "SKILL.md")
        self.assertEqual(fields["name"], "ppt-start")
        self.assertTrue(fields["description"].strip())
        self.assertLessEqual(len(fields["description"]), 500)
        self.assertTrue(fields["description"].startswith("Use when "))
        self.assertEqual(set(fields), {"name", "description"})

    def test_skill_avoids_host_specific_runtime_contracts(self):
        text = read_text(skill_root() / "SKILL.md")
        forbidden = [
            "AskUserQuestion",
            "SendMessage",
            "CLAUDE_SKILL_DIR",
            "CLAUDE_PROJECT_DIR",
            "$ARGUMENTS",
            "agents/openai.yaml",
            "mcp__",
            "context: fork",
            "allowed-tools:",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_skill_is_a_short_orchestrator(self):
        lines = read_text(skill_root() / "SKILL.md").splitlines()
        self.assertLessEqual(len(lines), 500)

    def test_readme_documents_both_hosts_without_runtime_coupling(self):
        readme_path = repo_root() / "README.md"
        self.assertTrue(readme_path.exists())
        text = read_text(readme_path)
        lower = text.lower()

        for path in (
            "~/.claude/skills/ppt-start/",
            ".claude/skills/ppt-start/",
            "$HOME/.agents/skills/ppt-start/",
            ".agents/skills/ppt-start/",
        ):
            self.assertIn(path, text)
        self.assertIn("技能启动标识：`ppt-start`", text)
        self.assertIn("/ppt-start", text)
        self.assertIn("$ppt-start", text)

        shared_skill = read_text(skill_root() / "SKILL.md")
        self.assertNotIn("/ppt-start", shared_skill)
        self.assertNotIn("$ppt-start", shared_skill)

        for token in (
            "纯指令",
            "可选网络",
            "独立子 agent",
            "review_unavailable",
            "独立 svg",
            "guided",
            "auto",
            "resume",
            "revise",
            "复制",
            "符号链接",
        ):
            self.assertIn(token, lower, f"README.md 缺少 {token}")
        for token in (
            "active_visual_generation_batch",
            "visual-generation-transactions/",
            "prompt_by_value",
            "patch",
            "recompose",
            "嘉为年中总结风格",
            "canway-midyear-review",
            "assets/styles/registry.json",
        ):
            self.assertIn(token.lower(), lower, f"README.md 缺少 {token}")
        for artifact in (
            "简报.md",
            "研究.md",
            "来源.md",
            "大纲.md",
            "故事板.md",
            "文稿审查.md",
            "质量检查报告.md",
        ):
            self.assertIn(artifact, text)
        self.assertIn(".ppt-pilot/", text)
        self.assertIn("slides/", text)
        self.assertIn(".ppt-pilot/run.json", text)
        self.assertIn("不保证", text)
        self.assertIn("完全可编辑", text)
        self.assertIn("powerpoint", lower)

    def test_readme_and_design_show_root_outline_and_internal_run_layout(self):
        readme = read_text(self.readme)
        design = read_text(self.design)
        for text in (readme, design):
            self.assertRegex(text, r"ppt-output/<deck-id>/[\s\S]{0,240}大纲\.md")
            self.assertRegex(text, r"大纲\.md[^\n]*(?:用户|根目录)")
            self.assertIn("slides/", text)
            self.assertIn(".ppt-pilot/", text)
            for artifact in ("简报.md", "研究.md", "来源.md", "故事板.md", "文稿审查.md", "质量检查报告.md"):
                self.assertIn(artifact, text)
        self.assertNotRegex(design, r"(?m)^run\.json\n简报\.md\n研究\.md\n来源\.md\n大纲\.md")

    def test_acceptance_matrix_covers_hosts_handoffs_and_strict_gate(self):
        path = repo_root() / "docs" / "acceptance.md"
        self.assertTrue(path.exists())
        text = read_text(path)
        lower = text.lower()
        for host in ("claude code", "codex"):
            self.assertIn(host, lower)
        for prompt in (
            "guided-topic-only.md",
            "source-driven.md",
            "review-blocker.md",
            "resume-after-review.md",
            "revise-single-slide.md",
        ):
            self.assertIn(prompt, text)
        self.assertIn("Claude Code -> Codex", text)
        self.assertIn("Codex -> Claude Code", text)
        self.assertIn("未解决的 `HIGH`", text)
        self.assertIn("review_unavailable", text)
        self.assertIn("不得生成 `theme.json`", text)
        self.assertIn("不得生成 SVG", text)
        for column in ("运行日期", "宿主版本", "结果", "证据路径"):
            self.assertIn(column, text)
        self.assertIn("PENDING", text)
        self.assertIn("受支持的 PowerPoint", text)
        self.assertIn("浏览器", text)

    def test_direct_compile_schema_v2_architecture_and_evidence_boundaries(self):
        readme = read_text(self.readme)
        design = read_text(self.design)
        acceptance = read_text(self.acceptance)

        for text in (readme, design):
            for token in (
                "故事板 + `theme.json` 直接编译",
                "[[CANONICAL_NARRATIVE_BULLETS]]",
                "[[STYLE_BASELINE]]",
                "creative-brief-v1",
                "active_visual_generation_batch",
                "visual-generation-transactions/",
                "visual-generation-batches/",
                "prompt_by_value",
                "batch_width",
                "ordered_slide_ids",
                "1.3.0",
            ):
                self.assertIn(token, text)
            for stale in (
                "render-ready effective visual brief",
                "[[EFFECTIVE_PAGE_SPECIFICATION]]",
                "visual_brief_snapshot_id",
                "visual-brief assembler",
                "单个 `visual_generation_transaction`",
            ):
                self.assertNotIn(stale, text)

        for token in (
            "pointer-last",
            "并发",
            "width 1",
            "非 Git",
            "coordinator",
            "fact_source_mismatch",
            "telemetry_diagnostic_failed",
            "内部 `SRC-<digits>`",
        ):
            self.assertIn(token, readme + "\n" + design)

        focused = "python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v"
        full = "python -m unittest discover -s tests -v"
        for text in (readme, acceptance):
            self.assertIn(focused, text)
            self.assertIn(full, text)

        evidence_contracts = {
            "static package": "只证明包结构、书面契约和 fixture oracle",
            "EVIDENCE_CLASS: DIAGNOSTIC": "不得作为 Claude Code、Codex、fresh generator、浏览器或 PowerPoint 验收通过依据",
            "deployment hash": "只证明部署的 `skills/ppt-start/` 与仓库源一致",
            "real host": "只有记录真实宿主版本、启动命令、transcript",
        }
        for evidence_class, limitation in evidence_contracts.items():
            self.assertIn(evidence_class, acceptance)
            self.assertIn(limitation, acceptance)
        self.assertIn("测试中的 resolver／hash oracle 不是运行时代码", acceptance)

        for row in (
            "| schema-v2 isolated generation | Claude Code | — | — | PENDING | — |",
            "| schema-v2 isolated generation | Codex | — | — | PENDING | — |",
            "| 仅主题 guided | Claude Code | — | — | PENDING | — |",
            "| 仅主题 guided | Codex | — | — | PENDING | — |",
            "| 完整生成演示文稿 SVG 渲染 | 浏览器 | — | — | PENDING | — |",
            "| 生成演示文稿 SVG 导入 | 受支持的 PowerPoint | — | — | PENDING | — |",
        ):
            self.assertIn(row, acceptance)

        for historical in (
            "Claude Code 2.1.223",
            "Codex CLI 0.146.1",
            "codex-blocker-v3-evaluation.md",
            "内置示例 SVG 渲染（历史资产证据，仍适用于未改变资产）",
            "Chrome 151.0.0.0 / Windows 11",
            "browser-svg.md",
        ):
            self.assertIn(historical, acceptance)

    def test_inline_review_fallback_is_documented_without_independence_overclaim(self):
        readme = read_text(self.readme)
        design = read_text(self.design)
        acceptance = read_text(self.acceptance)
        for text in (readme, design, acceptance):
            for token in (
                "inline_fallback",
                "优先",
                "当前上下文降级审查",
                "不具备独立上下文隔离",
                "manuscript_approved",
            ):
                self.assertIn(token, text)
        self.assertIn("inline PASS", readme)
        self.assertIn("pending_round", design)
        self.assertIn(
            "| 文稿 inline fallback | Claude Code | — | — | PENDING | — |",
            acceptance,
        )
        self.assertIn(
            "| 文稿 inline fallback | Codex | — | — | PENDING | — |",
            acceptance,
        )
        self.assertIn("委派不可用（历史旧标识）", acceptance)
        self.assertNotIn("委派不可用时必须阻断视觉设计，不能降级为同上下文自审放行", readme)

    def test_current_readme_and_process_docs_are_chinese(self):
        documents = [
            repo_root() / "README.md",
            repo_root() / "docs" / "design.md",
            repo_root() / "docs" / "acceptance.md",
            skill_root() / "SKILL.md",
            *sorted((skill_root() / "references").glob("*.md")),
        ]
        self.assertGreaterEqual(len(documents), 13)
        for path in documents:
            with self.subTest(path=path.relative_to(repo_root())):
                self.assertTrue(path.exists())
                chinese_characters = re.findall(r"[㐀-鿿]", read_text(path))
                self.assertGreaterEqual(
                    len(chinese_characters),
                    80,
                    f"{path.relative_to(repo_root())} 缺少足量中文正文",
                )

    def test_active_acceptance_matches_direct_compile_schema_v2_and_current_canway_version(self):
        acceptance = read_text(self.acceptance)
        for token in (
            "故事板 + `theme.json` 直接编译",
            "唯一仓库 `generation-prompt-template.md`",
            "schema-v2 per-slide transaction/batch manifest",
            "`active_visual_generation_batch`",
            "Canway manifest 版本为 `1.3.0`",
            "内部 `SRC-<digits>` 不得成为可见文字",
        ):
            self.assertIn(token, acceptance)
        for stale in (
            "Canway `1.2.0`",
            "当前四个 style-owned full prompts",
            "四份完整 prompt",
            "render-ready effective visual brief",
            "单个 `visual_generation_transaction`",
            "[[EFFECTIVE_PAGE_SPECIFICATION]]",
        ):
            self.assertNotIn(stale, acceptance)

    def test_package_wide_active_authorities_are_direct_compile_schema_v2_only(self):
        active_paths = (
            skill_root() / "SKILL.md",
            *sorted((skill_root() / "references").glob("*.md")),
            skill_root() / "assets" / "styles" / "canway-midyear-review" / "STYLE.md",
            self.readme,
            self.design,
            self.acceptance,
        )
        texts = {path: read_text(path) for path in active_paths}
        combined = "\n".join(texts.values())
        for forbidden in (
            "[[EFFECTIVE_PAGE_SPECIFICATION]]",
            "有效页面规格（唯一动态内容）",
            "visual_brief_snapshot_id",
            "visual-brief assembler",
            "当前 visual brief",
            "current-context generator fallback",
        ):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, combined)
        for path, text in texts.items():
            for line in text.splitlines():
                if "visual_generation_transaction" not in line:
                    continue
                with self.subTest(path=path, line=line[:80]):
                    self.assertRegex(line, r"(?i)(?:schema-v1|\bv1\b|迁移|legacy)")
        for required in (
            "[[CANONICAL_NARRATIVE_BULLETS]]",
            "[[STYLE_BASELINE]]",
            "creative-brief-v1",
            "active_visual_generation_batch",
            "visual-generation-transactions/",
            "visual-generation-batches/",
            "prompt_by_value",
            "fact_source_mismatch",
            "telemetry_diagnostic_failed",
        ):
            self.assertIn(required, combined)

        visible_internal = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)
        examples = sorted((skill_root() / "assets" / "examples").glob("*.svg"))
        self.assertTrue(examples)
        for path in examples:
            root = ET.fromstring(path.read_bytes())
            visible = " ".join(
                "".join(element.itertext())
                for element in root.iter()
                if isinstance(element.tag, str)
                and element.tag.rsplit("}", 1)[-1] == "text"
            )
            with self.subTest(path=path):
                self.assertNotRegex(visible, visible_internal)

    def test_style_prompt_supersession_is_unambiguous(self):
        current = "2026-08-21-ppt-start-style-owned-redesign-prompts-design.md"
        plans = (
            "2026-08-20-ppt-pilot-style-registry.md",
            "2026-08-20-ppt-pilot-canway-reference-svg.md",
            "2026-08-20-ppt-pilot-canway-style-guidance.md",
            "2026-08-20-ppt-pilot-visual-brief-contract.md",
            "2026-08-20-ppt-pilot-visual-prompt-assembly.md",
            "2026-08-20-ppt-pilot-visual-integration.md",
        )
        for filename in plans:
            text = read_text(repo_root() / "docs" / "superpowers" / "plans" / filename)
            lines = text.splitlines()
            self.assertIn("SUPERSEDED", lines[2])
            self.assertIn(current, lines[2])
        old_design = read_text(
            repo_root() / "docs" / "superpowers" / "specs"
            / "2026-08-20-ppt-pilot-visual-prompt-assembly-design.md"
        )
        self.assertIn("部分已被 2026-08-21", old_design)
        self.assertIn("当前风格由 tokens 与 `STYLE.md` 表达身份，并由风格自有 `REDESIGN.md` 提供完整生成模板。", old_design)
        self.assertIn("`visual-briefs/<slide-id>.md` 是该页已消解冲突的权威视觉输入，但不是可直接交给生成器的完整 prompt。", old_design)
        self.assertIn("按照 2026-08-21 规范，首次生成、`recompose` 与确定性回退还必须解析所选风格自有模板，编译并持久化 `generation-prompts/<slide-id>.md`，再由 fresh generator 生成候选 SVG。", old_design)
        self.assertIn("风格身份仍由 tokens 与抽象 `STYLE.md` 表达；完整 `REDESIGN.md` 是风格自有生成模板而非单页成品", old_design)
        self.assertIn("每个风格另外拥有一份 `REDESIGN.md`（legacy 使用同级 `*.redesign.md`）作为可独立交给 fresh generator 的完整生成指令模板；", old_design)
        self.assertNotIn("manifest 只引用机器可读 tokens 与中文 `STYLE.md", old_design)

    def test_legacy_skill_identifier_is_absent_from_current_docs(self):
        documents = [
            repo_root() / "README.md",
            *(repo_root() / "docs").glob("*.md"),
            skill_root() / "SKILL.md",
            *(skill_root() / "references").glob("*.md"),
        ]
        for path in documents:
            with self.subTest(path=path.relative_to(repo_root())):
                self.assertNotIn("skills/ppt-pilot", read_text(path))
        self.assertFalse((repo_root() / "skills" / "ppt-pilot").exists())


if __name__ == "__main__":
    unittest.main()
