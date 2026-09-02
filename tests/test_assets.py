import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root


HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")
STYLE_PACK_IDS = {
    "minimal-business",
    "tech-dark",
    "bold-editorial",
    "canway-midyear-review",
    "jiawei-product",
}
TOKEN_FILE = "tokens.json"
MANIFEST_FILE = "manifest.json"
PROMPT_FILE = "prompt.md"
STYLE_FILE = "STYLE.md"


class StyleAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.style_root = skill_root() / "assets" / "styles"
        self.reference_root = skill_root() / "references"

    def test_exact_style_pack_set_and_schema(self):
        self.assertTrue(self.style_root.is_dir())
        pack_dirs = {
            style_id: self.style_root / style_id
            for style_id in STYLE_PACK_IDS
        }
        self.assertTrue(all(path.is_dir() for path in pack_dirs.values()))

        seen_palettes: set[tuple[str, ...]] = set()
        seen_ids: set[str] = set()
        for style_id, pack_dir in pack_dirs.items():
            with self.subTest(style_id=style_id):
                manifest_path = pack_dir / MANIFEST_FILE
                self.assertTrue(manifest_path.is_file())
                manifest = json.loads(read_text(manifest_path))
                self.assertEqual(manifest["id"], style_id)
                self.assertEqual(manifest["kind"], "style_pack")
                self.assertEqual(set(manifest["files"]), {"tokens", "guidance", "prompt_template"})
                self.assertIn(style_id, manifest["selection_aliases"])

                tokens_path = pack_dir / TOKEN_FILE
                self.assertTrue(tokens_path.is_file())
                tokens = json.loads(read_text(tokens_path))
                self.assertEqual(tokens["schema_version"], 2)
                self.assertEqual(tokens["id"], style_id)
                self.assertIn("colors", tokens)
                self.assertIn("typography", tokens)
                self.assertIn("spacing", tokens)
                self.assertIn("shape", tokens)
                self.assertIn("prompt_baseline", tokens)

                colors = tokens["colors"]
                self.assertGreaterEqual(len(colors), 6)
                for token, value in colors.items():
                    self.assertIsInstance(value, str, f"{style_id}:{token}")
                    self.assertRegex(value, HEX_COLOR, f"{style_id}:{token}")
                palette = tuple(colors.values())
                self.assertNotIn(palette, seen_palettes)
                seen_palettes.add(palette)

                typography = tokens["typography"]
                self.assertIsInstance(typography, dict)
                self.assertIsInstance(typography["font_stack"], list)
                self.assertGreaterEqual(len(typography["font_stack"]), 2)
                self.assertFalse(any("http" in font.lower() for font in typography["font_stack"]))
                # style packs vary in key naming (slide_title/page_title/body) and may keep
                # small caption sizes; require a title-level size >= 34 once weights excluded.
                font_sizes = [
                    value for key, value in typography.items()
                    if "weight" not in key and key != "font_stack" and isinstance(value, int)
                ]
                self.assertTrue(font_sizes)
                self.assertGreaterEqual(max(font_sizes), 34)

                spacing = tokens["spacing"]
                self.assertEqual(spacing["outer_margin"], 64)
                # key naming varies (standard_gap/card_gap/compact_gap); require at least one
                # positive gap key and one positive padding key.
                self.assertTrue(any("gap" in key for key in spacing))
                gap_values = [v for k, v in spacing.items() if "gap" in k and isinstance(v, int)]
                self.assertGreaterEqual(min(gap_values), 1)
                padding_values = [
                    v for k, v in spacing.items()
                    if ("pad" in k or "margin" in k or "line" in k) and isinstance(v, int)
                ]
                self.assertTrue(padding_values)
                self.assertGreaterEqual(min(padding_values), 1)

                shape = tokens["shape"]
                self.assertGreater(shape["stroke_width"], 0)
                # at least one radius key present and positive
                self.assertTrue(any("radius" in key for key in shape))

                # each style pack owns a complete prompt template with a single injection point
                prompt_path = pack_dir / PROMPT_FILE
                self.assertTrue(prompt_path.is_file())
                prompt = read_text(prompt_path)
                self.assertEqual(prompt.count("{{NARRATIVE}}"), 1)
                self.assertNotIn("[[STYLE_BASELINE]]", prompt)
                self.assertNotIn("[[CANONICAL_NARRATIVE_BULLETS]]", prompt)
                self.assertNotIn("source=", prompt)

                self.assertTrue((pack_dir / STYLE_FILE).is_file())

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
            "visual_intent",
            "theme.json",
            "唯一焦点",
            "第一至第三阅读位置",
            "等权卡片墙",
            "1.5 倍",
            "recompose",
        ):
            self.assertIn(hierarchy_rule, layouts)
        self.assertNotIn("visual-briefs/<slide-id>.md", layouts)


if __name__ == "__main__":
    unittest.main()
