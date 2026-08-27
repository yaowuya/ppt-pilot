import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills" / "ppt-start" / "references"
LEGACY_FIXTURE = ROOT / "tests" / "fixtures" / "resume-approved"


def read_reference(name: str) -> str:
    return (REFERENCES / name).read_text(encoding="utf-8")


class PathCompatibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = read_reference("workflow.md")
        cls.artifacts = read_reference("artifact-contract.md")
        cls.qa = read_reference("qa-and-revision.md")
        cls.review = read_reference("manuscript-review.md")
        cls.combined = "\n".join(
            (cls.workflow, cls.artifacts, cls.qa, cls.review)
        )

    def test_active_path_map_keeps_outline_at_root(self):
        required_paths = {
            "大纲.md",
            ".ppt-pilot/简报.md",
            ".ppt-pilot/研究.md",
            ".ppt-pilot/来源.md",
            ".ppt-pilot/故事板.md",
            ".ppt-pilot/文稿审查.md",
            ".ppt-pilot/质量检查报告.md",
        }
        for path in required_paths:
            self.assertIn(path, self.combined)

        for text, label in (
            (self.workflow, "workflow.md"),
            (self.artifacts, "artifact-contract.md"),
            (self.qa, "qa-and-revision.md"),
        ):
            self.assertRegex(
                text,
                r"(?:运行)?根目录[^\n]*`大纲\.md`|`大纲\.md`[^\n]*(?:运行)?根目录",
                f"{label} must identify root 大纲.md as the active outline",
            )

        self.assertRegex(
            self.combined,
            r"`\.ppt-pilot/大纲\.md`[^\n]*(?:不得|禁止)[^\n]*(?:活动|有效|读取|写入|路径)",
        )

    def test_resume_snapshot_reads_root_outline(self):
        self.assertRegex(
            self.qa,
            r"resume[^\n]*(?:运行)?根目录[^\n]*`大纲\.md`[^\n]*outline_snapshot_id",
        )
        self.assertRegex(
            self.qa,
            r"outline_snapshot_id[^\n]*(?:读取|来源|计算)[^\n]*(?:运行)?根目录[^\n]*`大纲\.md`",
        )

    def test_new_runs_write_only_chinese_canonical_names(self):
        self.assertRegex(
            self.combined,
            r"新(?:建)?运行[^\n]*(?:只|仅)[^\n]*(?:写入|创建)[^\n]*中文",
        )
        self.assertRegex(
            self.combined,
            r"(?:brief\.md|research\.md|sources\.md|outline\.md|storyboard\.md)[^\n]*(?:不得|禁止)[^\n]*(?:新运行|写入目标)|新运行[^\n]*(?:不得|禁止)[^\n]*(?:brief\.md|research\.md|sources\.md|outline\.md|storyboard\.md)",
        )

    def test_legacy_resume_and_revise_read_english_files_in_place(self):
        expected = {
            "brief.md",
            "research.md",
            "sources.md",
            "outline.md",
            "storyboard.md",
            "manuscript-review.md",
        }
        self.assertEqual(
            {path.name for path in LEGACY_FIXTURE.iterdir()},
            expected,
        )

        for name in expected - {"manuscript-review.md"}:
            self.assertIn(name, self.qa)
            self.assertIn(name, self.review)

        for text, label in (
            (self.qa, "qa-and-revision.md"),
            (self.review, "manuscript-review.md"),
        ):
            self.assertRegex(text, r"(?:resume|revise)[^\n]*(?:原位|就地)[^\n]*(?:读取|使用)")
            self.assertRegex(
                text,
                r"不得仅因[^\n]*(?:英文|English)[^\n]*(?:拒绝|重命名)[^\n]*(?:复制|迁移)[^\n]*(?:重算|重建|重新计算)",
                f"{label} must forbid English-name-only compatibility churn",
            )

    def test_legacy_compatibility_does_not_bypass_state_validation(self):
        for text, label in (
            (self.qa, "qa-and-revision.md"),
            (self.review, "manuscript-review.md"),
        ):
            self.assertRegex(
                text,
                r"(?:缺失|无效|invalid|stale|过期|dirty|脏)[^\n]*(?:阻断|拒绝|停止)",
                f"{label} must still block invalid or dirty legacy state",
            )


if __name__ == "__main__":
    unittest.main()
