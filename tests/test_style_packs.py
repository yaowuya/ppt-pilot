import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root


class StylePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.style_root = skill_root() / "assets" / "styles"
        self.registry_path = self.style_root / "registry.json"
        self.pack_root = self.style_root / "canway-midyear-review"
        self.manifest_path = self.pack_root / "manifest.json"
        self.tokens_path = self.pack_root / "tokens.json"
        self.rules_path = self.pack_root / "STYLE.md"
        self.runtime_references = (
            skill_root() / "references" / "design-system.md",
            skill_root() / "references" / "visual-brief-and-generation.md",
        )

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
        self.assertNotIn("redesign_prompt", canway)

    def test_legacy_registry_declares_redesign_prompts(self):
        styles = json.loads(read_text(self.registry_path))["styles"]
        actual = {
            item["id"]: item.get("redesign_prompt")
            for item in styles
            if item["kind"] == "legacy_seed"
        }
        self.assertEqual(
            actual,
            {
                "minimal-business": "minimal-business.redesign.md",
                "tech-dark": "tech-dark.redesign.md",
                "bold-editorial": "bold-editorial.redesign.md",
            },
        )

    def test_canway_manifest_owns_redesign_prompt(self):
        manifest = json.loads(read_text(self.manifest_path))
        self.assertEqual(manifest["version"], "1.3.0")
        self.assertEqual(
            manifest["files"],
            {
                "tokens": "tokens.json",
                "guidance": "STYLE.md",
                "redesign_prompt": "REDESIGN.md",
            },
        )

    def test_manifest_references_complete_style_owned_pack(self):
        manifest = json.loads(read_text(self.manifest_path))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "canway-midyear-review")
        self.assertEqual(manifest["display_name"], "嘉为年中总结风格")
        self.assertEqual(manifest["kind"], "style_pack")
        self.assertEqual(manifest["version"], "1.3.0")
        self.assertIn("嘉为年中总结风格", manifest["selection_aliases"])
        self.assertEqual(
            manifest["files"],
            {
                "tokens": "tokens.json",
                "guidance": "STYLE.md",
                "redesign_prompt": "REDESIGN.md",
            },
        )
        for path in manifest["files"].values():
            self.assertTrue((self.pack_root / path).is_file())
        self.assertTrue(manifest["compatibility"]["office_safe_svg"])
        self.assertFalse(manifest["default"])

    def test_registered_redesign_prompt_files_exist(self):
        registry = json.loads(read_text(self.registry_path))
        for style in registry["styles"]:
            with self.subTest(style=style["id"]):
                if style["kind"] == "legacy_seed":
                    relative = style["redesign_prompt"]
                    root = self.style_root
                else:
                    manifest_path = self.style_root / style["entrypoint"]
                    manifest = json.loads(read_text(manifest_path))
                    relative = manifest["files"]["redesign_prompt"]
                    root = manifest_path.parent
                self.assertTrue((root / relative).is_file())

    def test_tokens_encode_approved_canway_style(self):
        tokens = json.loads(read_text(self.tokens_path))
        self.assertEqual(tokens["schema_version"], 1)
        self.assertEqual(tokens["id"], "canway-midyear-review")
        expected_colors = {
            "canvas": "#FFFFFF",
            "hero_dark": "#10233F",
            "brand_primary": "#156BFF",
            "title_accent": "#156BFF",
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

    def test_style_pack_has_no_rendered_slide_exemplar(self):
        self.assertEqual(list(self.pack_root.rglob("*.svg")), [])
        manifest = read_text(self.manifest_path).lower()
        active_contract = "\n".join(
            [read_text(self.rules_path), *(read_text(path) for path in self.runtime_references)]
        )
        for forbidden in ("reference.svg", "reference_svg", "参考 svg"):
            self.assertNotIn(forbidden, manifest)
            self.assertNotIn(forbidden, active_contract.lower())
        self.assertIn("不得包含单页成品示例、参考构图或固定区域图", active_contract)
        self.assertIn("不得从成品示例或既有 SVG 反推构图", active_contract)


if __name__ == "__main__":
    unittest.main()
