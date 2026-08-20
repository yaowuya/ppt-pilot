import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root
from test_svg_contract import ALLOWED, local_name, numeric_font_size


class StylePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.style_root = skill_root() / "assets" / "styles"
        self.registry_path = self.style_root / "registry.json"
        self.pack_root = self.style_root / "canway-midyear-review"
        self.manifest_path = self.pack_root / "manifest.json"
        self.tokens_path = self.pack_root / "tokens.json"
        self.rules_path = self.pack_root / "STYLE.md"
        self.reference_path = self.pack_root / "reference.svg"

    def test_registry_has_unique_ids_names_and_existing_entrypoints(self):
        payload = json.loads(read_text(self.registry_path))
        self.assertEqual(payload["schema_version"], 1)
        styles = payload["styles"]
        ids = [style["id"] for style in styles]
        names = [style["display_name"] for style in styles]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))
        for style in styles:
            self.assertTrue((self.style_root / style["entrypoint"]).is_file())
        canway = next(style for style in styles if style["id"] == "canway-midyear-review")
        self.assertEqual(canway["display_name"], "嘉为年中总结风格")
        self.assertEqual(canway["kind"], "style_pack")

    def test_manifest_references_complete_pack(self):
        manifest = json.loads(read_text(self.manifest_path))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "canway-midyear-review")
        self.assertEqual(manifest["display_name"], "嘉为年中总结风格")
        self.assertIn("嘉为年中总结风格", manifest["selection_aliases"])
        for path in manifest["files"].values():
            self.assertTrue((self.pack_root / path).is_file())
        self.assertTrue(manifest["compatibility"]["office_safe_svg"])
        self.assertFalse(manifest["default"])

    def test_tokens_encode_approved_canway_style(self):
        tokens = json.loads(read_text(self.tokens_path))
        self.assertEqual(tokens["schema_version"], 1)
        self.assertEqual(tokens["id"], "canway-midyear-review")
        expected_colors = {
            "canvas": "#F5F8FC",
            "hero_dark": "#10233F",
            "brand_primary": "#156BFF",
            "title_accent": "#1E63FF",
            "sky": "#65B7F9",
            "ai_pilot": "#8866FD",
            "ink": "#0B1930",
            "fact_surface": "#FFFFFF",
            "border": "#DCE9F8",
        }
        for name, value in expected_colors.items():
            self.assertEqual(tokens["colors"][name], value)
        self.assertGreaterEqual(tokens["typography"]["slide_title"], 40)
        self.assertGreaterEqual(tokens["typography"]["body"], 20)
        self.assertGreaterEqual(tokens["typography"]["micro_label"], 14)
        self.assertEqual(tokens["spacing"]["outer_margin"], 64)
        self.assertEqual(tokens["composition"]["max_shadowed_objects"], 1)
        self.assertEqual(tokens["composition"]["primary_secondary_ratio"], 1.5)

    def test_rules_capture_identity_and_prohibitions(self):
        rules = read_text(self.rules_path)
        for token in (
            "单行结论标题",
            "短语级",
            "深色主卡",
            "白色事实卡",
            "证据边界",
            "AI",
            "有界试点",
            "40%–60%",
            "最多一处轻阴影",
            "左侧长蓝条",
            "背景图片",
            "渐变",
            "等权卡片墙",
            "根据内容选择",
        ):
            self.assertIn(token, rules)

    def test_reference_is_standalone_office_safe_svg(self):
        raw = read_text(self.reference_path)
        lowered = raw.lower()
        for forbidden in ("<style", "<defs", "<filter", "<lineargradient", "<image", "url(", "javascript:"):
            self.assertNotIn(forbidden, lowered)
        root = ET.fromstring(raw)
        self.assertEqual(root.attrib.get("width"), "1280")
        self.assertEqual(root.attrib.get("height"), "720")
        self.assertEqual(root.attrib.get("viewBox"), "0 0 1280 720")
        ids = set()
        for element in root.iter():
            self.assertIn(local_name(element.tag), ALLOWED)
            element_id = element.attrib.get("id")
            if element_id:
                self.assertNotIn(element_id, ids)
                ids.add(element_id)
            if local_name(element.tag) == "text":
                self.assertTrue(any(local_name(child.tag) == "tspan" for child in element))
                role = element.attrib.get("data-role", "body")
                size = numeric_font_size(element.attrib["font-size"])
                minimum = 40 if role == "title" else 14 if role == "footnote" else 20
                self.assertGreaterEqual(size, minimum)
        self.assertEqual(root.find("{http://www.w3.org/2000/svg}path").attrib["fill"], "#F5F8FC")


if __name__ == "__main__":
    unittest.main()
