import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ppt-start"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _svg_runtime import validate_candidate


class InstalledSvgTextRoleNormalizationRegressionTests(unittest.TestCase):
    def test_normalizes_invalid_body_role_to_footnote_before_candidate_write(self):
        svg = """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1280\" height=\"720\" viewBox=\"0 0 1280 720\">
<title>Probe</title><desc>Probe</desc>
<rect x=\"0\" y=\"0\" width=\"1280\" height=\"720\" fill=\"#FFFFFF\"/>
<g data-block-id=\"S01-B1\"><text x=\"64\" y=\"100\" data-role=\"body\" font-size=\"14\" font-family=\"Arial\"><tspan x=\"64\" y=\"100\">label</tspan></text></g>
</svg>"""

        result = validate_candidate(
            svg,
            ["S01-B1"],
            {"S01-B1": ["SRC-001"]},
        ).decode("utf-8")

        self.assertIn('data-role="footnote"', result)
        self.assertNotIn('data-role="body" font-size="14"', result)
        self.assertIn('data-source-id="SRC-001"', result)

    def test_shifts_text_minimally_inside_vertical_safe_area(self):
        svg = """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1280\" height=\"720\" viewBox=\"0 0 1280 720\">
<title>Probe</title><desc>Probe</desc>
<rect x=\"0\" y=\"0\" width=\"1280\" height=\"720\" fill=\"#FFFFFF\"/>
<g data-block-id=\"S01-B1\"><text x=\"64\" y=\"102\" data-role=\"title\" font-size=\"40\" font-family=\"Arial\"><tspan x=\"64\" y=\"102\">Title</tspan></text></g>
</svg>"""

        result = validate_candidate(
            svg,
            ["S01-B1"],
            {"S01-B1": ["SRC-001"]},
        ).decode("utf-8")

        self.assertIn('y="104" data-role="title"', result)
        self.assertIn('<tspan x="64" y="104">Title</tspan>', result)

    def test_keeps_visible_stroke_inside_canonical_safe_area(self):
        svg = """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1280\" height=\"720\" viewBox=\"0 0 1280 720\">
<title>Probe</title><desc>Probe</desc>
<rect x=\"0\" y=\"0\" width=\"1280\" height=\"720\" fill=\"#FFFFFF\"/>
<g data-block-id=\"S01-B1\"><path d=\"M84 182 H278 A20 20 0 0 1 298 202 V394 A20 20 0 0 1 278 414 H84 A20 20 0 0 1 64 394 V202 A20 20 0 0 1 84 182 Z\" fill=\"#FFFFFF\" stroke=\"#DCE7F5\" stroke-width=\"1.2\"/><text x=\"88\" y=\"240\" data-role=\"body\" font-size=\"20\" font-family=\"Arial\"><tspan x=\"88\" y=\"240\">Body</tspan></text></g>
</svg>"""

        with self.assertRaises(ValueError):
            validate_candidate(
                svg,
                ["S01-B1"],
                {"S01-B1": ["SRC-001"]},
            )


if __name__ == "__main__":
    unittest.main()
