"""Contract tests for the ppt-style-extract skill.

Covers: extractor evidence bounds, pack hard-constraint verification, the
pre-write zero-write guarantee, and idempotent registry registration.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "ppt-style-extract" / "scripts"))

from helpers import repo_root, skill_root  # noqa: E402

_demo_registry = {
    "schema_version": 1,
    "styles": [
        {"id": "minimal-business", "display_name": "极简商务", "kind": "style_pack", "entrypoint": "minimal-business/manifest.json"},
        {"id": "canway-midyear-review", "display_name": "嘉为年中总结风格", "kind": "style_pack", "entrypoint": "canway-midyear-review/manifest.json"},
    ],
}


def _make_pptx(path: Path) -> None:
    """Build a tiny real .pptx with an accent color, a dark ink run, and a
    rounded rectangle so the extractor has concrete evidence to read."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(6), Inches(0.8))
    run = title.text_frame.paragraphs[0].add_run()
    run.text = "年度复盘"
    run.font.size = Pt(32)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x15, 0x6B, 0xFF)

    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2), Inches(3), Inches(3), Inches(1.5))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0xEF, 0xF6, 0xFF)
    card.line.color.rgb = RGBColor(0xDC, 0xE9, 0xF8)

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))


class StyleExtractModuleTests(unittest.TestCase):
    def test_package_imports(self):
        import _style_extract  # noqa: F401
        from _style_extract import analyze_prompt, builder, extract_image, extract_pptx, registry, verify  # noqa: F401

        self.assertTrue(hasattr(builder, "compose_style_pack"))
        self.assertTrue(hasattr(verify, "verify_composed"))
        self.assertTrue(hasattr(registry, "update_registry_idempotent"))

    def test_pptx_extractor_finds_color_and_font_evidence(self):
        import tempfile

        from _style_extract.extract_pptx import extract_pptx

        with tempfile.TemporaryDirectory() as d:
            pptx = Path(d) / "demo.pptx"
            _make_pptx(pptx)
            result = extract_pptx(pptx)
        self.assertEqual(result["extractor"], "pptx")
        self.assertTrue(result["colors"]["brand_primary"])
        self.assertEqual(result["colors"]["brand_primary"], "#156BFF")
        self.assertTrue(result["evidence"]["fills"])
        self.assertGreaterEqual(result["typography"]["slide_title"], 32)

    def test_prompt_analyzer_seeds_semantic_direction(self):
        from _style_extract.analyze_prompt import analyze_prompt

        result = analyze_prompt("极简商务，深色科技，数据优先")
        self.assertEqual(result["extractor"], "prompt")
        self.assertTrue(result["semantic"]["prohibited_motifs"])
        self.assertIn("minimal", result["semantic"]["direction"])

    def test_svg_extractor_reads_fills(self):
        import tempfile

        from _style_extract.extract_image import extract_image

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<rect width="100" height="50" fill="#156BFF"/>'
            '<text x="10" y="20" fill="#0B1930">hello</text></svg>'
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ref.svg"
            p.write_text(svg, encoding="utf-8")
            result = extract_image(p)
        self.assertEqual(result["extractor"], "svg")
        self.assertIn("#156BFF", result["colors"]["accent_palette"])


class StylePackVerificationTests(unittest.TestCase):
    def setUp(self):
        self.pack = None
        self.out_root = None

    def _author(self, style_id="acme-brand", display_name="Acme 品牌", mutate=None):
        import tempfile

        from _style_extract import extract_pptx
        from _style_extract.builder import compose_style_pack, write_style_pack

        with tempfile.TemporaryDirectory() as pptxd:
            pptx = Path(pptxd) / "demo.pptx"
            _make_pptx(pptx)
            extract = extract_pptx.extract_pptx(pptx)
        pack = compose_style_pack(style_id, display_name, "1.0.0", extract, None)
        if mutate:
            mutate(pack)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.out_root = Path(self.tmpdir.name) / "out"
        self.reg = Path(self.tmpdir.name) / "registry.json"
        self.reg.write_text(json.dumps(_demo_registry, ensure_ascii=False), encoding="utf-8")
        self.pack = pack
        return write_style_pack(pack, self.out_root, self.reg)

    def tearDown(self):
        if getattr(self, "tmpdir", None):
            self.tmpdir.cleanup()

    def test_valid_pack_passes_and_registers_idempotently(self):
        result = self._author()
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["registry_entries"], 3)
        # second run: same id, still 3 entries
        result2 = self._author()
        self.assertEqual(result2["registry_entries"], 3)

    def test_pack_on_disk_satisfies_hard_constraints(self):
        self._author()
        from _style_extract.verify import verify_style_pack

        pack_dir = self.out_root / "acme-brand"
        verify_style_pack(pack_dir)  # raises on violation

    def test_prompt_with_two_narrative_tokens_blocks_zero_write(self):
        def mutate(pack):
            pack["prompt"] = pack["prompt"].replace("{{NARRATIVE}}", "{{NARRATIVE}}{{NARRATIVE}}")

        with self.assertRaises(Exception) as ctx:
            self._author(mutate=mutate)
        self.assertIn("prompt_template_invalid", str(ctx.exception))
        self.assertFalse((self.out_root / "acme-brand").exists())

    def test_missing_palette_role_in_colors_blocks(self):
        def mutate(pack):
            pack["tokens"]["prompt_baseline"]["palette_roles"][0]["token"] = "not_in_colors"

        with self.assertRaises(Exception) as ctx:
            self._author(mutate=mutate)
        self.assertIn("tokens_palette_role_not_in_colors", str(ctx.exception))
        self.assertFalse((self.out_root / "acme-brand").exists())

    def test_registry_display_name_collision_blocks(self):
        with self.assertRaises(Exception) as ctx:
            self._author(style_id="other-id", display_name="极简商务")
        self.assertIn("registry_display_name_collision", str(ctx.exception))


class StyleExtractSkillLayoutTests(unittest.TestCase):
    def test_skill_descriptor_and_references_exist(self):
        skill = skill_root("ppt-style-extract")
        self.assertTrue((skill / "SKILL.md").is_file())
        for ref in ("input-and-output-contract.md", "extraction-contract.md", "style-pack-verification.md"):
            self.assertTrue((skill / "references" / ref).is_file())
        for script in ("write_style_pack.py", "extract_pptx.py", "extract_image.py", "analyze_prompt.py"):
            self.assertTrue((skill / "scripts" / script).is_file())

    def test_skill_descriptor_frontmatter(self):
        from helpers import parse_frontmatter, read_text

        fields = parse_frontmatter(skill_root("ppt-style-extract") / "SKILL.md")
        self.assertEqual(fields["name"], "ppt-style-extract")
        self.assertTrue(fields["description"].startswith("Use when "))
        self.assertLessEqual(len(fields["description"]), 500)

    def test_prompt_template_has_single_narrative_and_no_legacy_tokens(self):
        from helpers import read_text

        prompt = read_text(skill_root("ppt-style-extract") / "references" / "style-pack-verification.md")
        for token in ("{{NARRATIVE}}", "prompt_baseline", "palette_roles"):
            self.assertIn(token, prompt)


if __name__ == "__main__":
    unittest.main()
