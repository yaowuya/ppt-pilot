"""Behavioral checks of the installed production runtime boundary."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/ppt-start/scripts"))

VALID_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>Growth</title><desc>Revenue rose</desc><g data-block-id="S01-B1"><text x="100" y="120" font-size="40" font-family="Arial" data-role="title"><tspan x="100" y="120">Growth</tspan></text></g></svg>'''


class CandidateValidationTests(unittest.TestCase):
    def test_square_caps_stay_inside_safe_area(self):
        from _svg_runtime import validate_candidate
        shapes = ('<line x1="{x}" y1="200" x2="170" y2="300"',
                  '<polyline points="{x},200 170,300"',
                  '<path d="M{x} 200 L170 300"')
        for shape in shapes:
            for x, accepted in ((70, False), (72, True)):
                svg = VALID_SVG.replace('</svg>', shape.format(x=x) +
                    ' stroke="black" stroke-width="10" stroke-linecap="square" stroke-linejoin="round"/></svg>')
                with self.subTest(shape=shape, x=x):
                    if accepted:
                        validate_candidate(svg, ("S01-B1",), {"S01-B1": []})
                    else:
                        with self.assertRaises(ValueError):
                            validate_candidate(svg, ("S01-B1",), {"S01-B1": []})

    def test_dash_array_requires_finite_nonnegative_numeric_list(self):
        from _svg_runtime import validate_candidate
        valid = ('none', '0', '5 10', '5,10', ' 5 , 10 ', '1e1 .5 +2')
        invalid = ('NaN 5', 'Inf', '-Inf 1', '1e999 5', '-1 5', '',
                   '1,,2', ',1', '1,', '1-2', '1.2.3', '1px 2', 'none 1')
        for value in valid + invalid:
            svg = VALID_SVG.replace('</svg>', '<line x1="100" y1="200" x2="300" y2="200" stroke="black" stroke-dasharray="' + value + '"/></svg>')
            with self.subTest(value=value):
                if value in valid:
                    validate_candidate(svg, ("S01-B1",), {"S01-B1": []})
                else:
                    with self.assertRaises(ValueError):
                        validate_candidate(svg, ("S01-B1",), {"S01-B1": []})

    def test_shape_bounds_and_numeric_geometry(self):
        from _svg_runtime import validate_candidate
        valid_shapes = ['<rect x="0" y="0" width="1280" height="720" fill="white"/>',
                        '<rect x="70" y="200" width="100" height="100"/>',
                        '<circle cx="200" cy="200" r="30"/>',
                        '<ellipse cx="200" cy="200" rx="40" ry="20"/>',
                        '<line x1="100" y1="200" x2="300" y2="200" stroke="black"/>',
                        '<polygon points="100,200 150,200 150,250"/>',
                        '<path d="M100 200 C120 200 150 250 200 250 L200 300 Z"/>']
        for shape in valid_shapes:
            validate_candidate(VALID_SVG.replace('</svg>', shape + '</svg>'),
                               ("S01-B1",), {"S01-B1": []})
        invalid_shapes = ['<rect x="63" y="200" width="100" height="100"/>',
                          '<circle cx="100" cy="100" r="-1"/>',
                          '<ellipse cx="1200" cy="200" rx="40" ry="20"/>',
                          '<line x1="64" y1="200" x2="300" y2="200" stroke="black"/>',
                          '<polygon points="100,200 150,200 150"/>',
                          '<path d="M100 200 C0 200 150 250 200 250"/>',
                          '<path d="M100 200 L1e999 300"/>',
                          '<path d="M600 300 A1 100 0 0 0 700 300"/>',
                          '<path d="M100 200 bananas"/>',
                          '<g transform="translate(-100,0)"/>']
        for shape in invalid_shapes:
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                validate_candidate(VALID_SVG.replace('</svg>', shape + '</svg>'),
                                   ("S01-B1",), {"S01-B1": []})

    def test_invalid_sources_raise_closed_errors(self):
        from _svg_runtime import enrich_candidate_source_metadata
        for mapping in ({"S01-B1": [["SRC-1"]]}, {"S01-B1": ["SRC-1", "SRC-1"]},
                        {"S01-B1": ["src-1"]}, {"S01-B1": ["SRC-１"]}, []):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                enrich_candidate_source_metadata(VALID_SVG, mapping)

    def test_valid_candidate_is_enriched_after_validation(self):
        from _svg_runtime import validate_candidate
        result = validate_candidate(VALID_SVG, ("S01-B1",), {"S01-B1": ["SRC-1"]})
        self.assertIn(b'data-source-id="SRC-1"', result)
        self.assertNotIn(b"data-block-id", result)

    def test_candidate_rejects_contract_violations(self):
        from _svg_runtime import validate_candidate
        invalid = [
            VALID_SVG.replace('width="1280"', 'width="640"'),
            VALID_SVG.replace('<title>Growth</title>', ''),
            VALID_SVG.replace('<desc>Revenue rose</desc>', ''),
            VALID_SVG.replace('<g ', '<g onclick="alert(1)" '),
            VALID_SVG.replace('</svg>', '<script>alert(1)</script></svg>'),
            VALID_SVG.replace('</svg>', '<image href="https://example.com/a"/></svg>'),
            VALID_SVG.replace('font-size="40"', 'font-size="NaN"'),
            VALID_SVG.replace('font-size="40"', 'font-size="10"'),
            VALID_SVG.replace('x="100"', 'x="20"'),
            VALID_SVG.replace('y="120"', 'y="64"'),
            VALID_SVG.replace('x="100" y="120">Growth', 'x="101" y="120">Growth'),
            VALID_SVG.replace('<tspan ', '<tspan dy="1" '),
            VALID_SVG.replace('>Growth</tspan>', '>' + 'W' * 100 + '</tspan>'),
            VALID_SVG.replace('<g ', '<g fill="url(#x)" '),
            VALID_SVG.replace('<g ', '<g style="fill:red" '),
            '<?xml-stylesheet href="file:///x"?>' + VALID_SVG,
            '<!DOCTYPE svg [<!ENTITY a "x">]>' + VALID_SVG,
        ]
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    validate_candidate(candidate, ("S01-B1",), {"S01-B1": ["SRC-1"]})

    def test_exact_fence_extraction(self):
        from _svg_runtime import extract_svg
        self.assertEqual(extract_svg('```xml\n' + VALID_SVG + '\n```'), VALID_SVG)
        for text in (VALID_SVG, 'intro\n```xml\n' + VALID_SVG + '\n```',
                     '```svg\n' + VALID_SVG + '\n```', '```xml\n' + VALID_SVG + '\n```\n```xml\n<svg/>\n```'):
            with self.assertRaises(ValueError):
                extract_svg(text)


class InstalledRuntimeTests(unittest.TestCase):
    def test_installed_modules_compile_and_reject_invalid_source_blocks(self):
        skills = Path(__file__).resolve().parents[1] / "skills"
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "skills"
            for name in ("ppt-start", "ppt-style-extract"):
                shutil.copytree(skills / name, installed / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            code = '''
import sys
sys.path.insert(0, sys.argv[1])
import types
poison = types.ModuleType("_style_extract.verify")
def forbidden(*args, **kwargs):
    raise AssertionError("ambient verifier was imported")
poison.verify_prompt = forbidden
sys.modules["_style_extract.verify"] = poison
from _prompt_runtime import compile_style_prompt, _style_template_bytes
from _generation_runtime import validate_v2_transaction
from _svg_runtime import enrich_candidate_source_metadata
body = compile_style_prompt(b"- block_id: S01-B1\\n- Revenue grew\\n", _style_template_bytes("canway-midyear-review"))
assert b"Revenue grew" in body and b"{{NARRATIVE}}" not in body
for svg in ('<svg><g data-block-id="S01-B1"/><g data-block-id="S01-B1"/></svg>', '<svg><g data-block-id="S01-B2"/></svg>'):
    try:
        enrich_candidate_source_metadata(svg, {"S01-B1": ["SRC-1"]})
    except ValueError:
        pass
    else:
        raise AssertionError("invalid semantic block accepted")
assert not any(name == "helpers" or name.startswith("tests.") for name in sys.modules)
'''
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", code,
                 str(installed / "ppt-start" / "scripts")],
                cwd=directory, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
