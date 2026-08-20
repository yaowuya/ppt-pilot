import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import parse_frontmatter, read_text, repo_root, skill_root


class SkillPackageTests(unittest.TestCase):
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
            "强制独立",
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
            "visual-briefs/",
            "逐页视觉 brief",
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
        self.assertIn("旧英文运行", text)
        self.assertIn("原位读取", text)
        self.assertIn("不自动重命名", text)
        self.assertIn("不保证", text)
        self.assertIn("完全可编辑", text)
        self.assertIn("powerpoint", lower)

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
