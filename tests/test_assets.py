import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root


HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")
LEGACY_STYLE_FILES = {
    "minimal-business.json",
    "tech-dark.json",
    "bold-editorial.json",
}
TOP_LEVEL_KEYS = {"name", "colors", "typography", "spacing", "shape"}


class StyleAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.style_root = skill_root() / "assets" / "styles"
        self.reference_root = skill_root() / "references"

    def test_exact_style_seed_set_and_schema(self):
        self.assertTrue(self.style_root.is_dir())
        paths = {
            filename: self.style_root / filename
            for filename in LEGACY_STYLE_FILES
        }
        self.assertTrue(all(path.is_file() for path in paths.values()))

        names: set[str] = set()
        palettes: set[tuple[str, ...]] = set()
        for filename, path in paths.items():
            with self.subTest(filename=filename):
                data = json.loads(read_text(path))
                self.assertEqual(set(data), TOP_LEVEL_KEYS)
                self.assertEqual(data["name"], path.stem)
                self.assertNotIn(data["name"], names)
                names.add(data["name"])

                colors = data["colors"]
                self.assertGreaterEqual(len(colors), 6)
                for token, value in colors.items():
                    self.assertIsInstance(value, str, f"{filename}:{token}")
                    self.assertRegex(value, HEX_COLOR, f"{filename}:{token}")
                palette = tuple(colors.values())
                self.assertNotIn(palette, palettes)
                palettes.add(palette)

                typography = data["typography"]
                self.assertGreaterEqual(typography["title_min"], 40)
                self.assertGreaterEqual(typography["body_min"], 20)
                self.assertGreaterEqual(typography["footnote_min"], 14)
                self.assertIsInstance(typography["font_stack"], list)
                self.assertGreaterEqual(len(typography["font_stack"]), 2)
                self.assertFalse(any("http" in font.lower() for font in typography["font_stack"]))

                spacing = data["spacing"]
                self.assertEqual(spacing["outer_margin"], 64)
                self.assertEqual(spacing["standard_gap"], 24)
                self.assertGreater(spacing["card_padding"], 0)

                shape = data["shape"]
                self.assertGreater(shape["corner_radius"], 0)
                self.assertGreater(shape["stroke_width"], 0)

    def test_visual_references_define_tokens_and_safe_defaults(self):
        design_path = self.reference_root / "design-system.md"
        layout_path = self.reference_root / "layout-catalog.md"
        self.assertTrue(design_path.exists())
        self.assertTrue(layout_path.exists())

        design = read_text(design_path).lower()
        for token in (
            "manuscript_approved",
            "theme.json",
            "64 px",
            "24 px",
            "40 px",
            "20 px",
            "14 px",
            "系统字体",
            "<tspan>",
            "对比度",
            "主导色",
            "minimal-business",
            "tech-dark",
            "bold-editorial",
        ):
            self.assertIn(token, design, f"design-system.md 缺少 {token}")
        for prohibition in ("强调色条", "标题下划线", "渐变", "远程字体"):
            self.assertIn(prohibition, design, f"design-system.md 必须说明禁止项 {prohibition}")

        layouts = read_text(layout_path).lower()
        for family in (
            "cover/section",
            "single assertion",
            "comparison",
            "timeline/process",
            "hierarchy/architecture",
            "data/chart",
            "bento summary",
            "close/action",
        ):
            self.assertIn(family, layouts, f"layout-catalog.md 缺少布局家族 {family}")
        self.assertIn("内容语义", layouts)
        self.assertIn("相邻页面", layouts)
        self.assertIn("密度", layouts)
        for hierarchy_rule in (
            "visual-briefs/<slide-id>.md",
            "唯一焦点",
            "第一至第三阅读位置",
            "等权卡片墙",
            "1.5 倍",
            "recompose",
        ):
            self.assertIn(hierarchy_rule, layouts)


if __name__ == "__main__":
    unittest.main()
