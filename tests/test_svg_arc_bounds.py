"""Exact arc bounds and fail-closed checks at the geometry/runtime seams."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/ppt-start/scripts"))

from _svg_geometry import GeometryError, _path_points, validate_geometry
from _svg_runtime import validate_candidate


ROUNDED_RECTS = (
    'M112 590 H416 A8 8 0 0 1 424 598 V634 A8 8 0 0 1 416 642 H112 A8 8 0 0 1 104 634 V598 A8 8 0 0 1 112 590 Z',
    'M106 188 H1174 A16 16 0 0 1 1190 204 V240 A16 16 0 0 1 1174 256 H106 A16 16 0 0 1 90 240 V204 A16 16 0 0 1 106 188 Z',
    'M737 113 H1143 A24 24 0 0 1 1167 137 V583 A24 24 0 0 1 1143 607 H737 A24 24 0 0 1 713 583 V137 A24 24 0 0 1 737 113 Z',
)


def candidate(shape):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
            'viewBox="0 0 1280 720"><title>Arc</title><desc>Geometry test</desc>'
            '<g data-block-id="S01-B1">' + shape + '</g></svg>')


class ArcBoundsTests(unittest.TestCase):
    def test_safe_rounded_rect_incidents_pass_real_candidate_validation(self):
        for index, path in enumerate(ROUNDED_RECTS):
            with self.subTest(incident=index):
                svg = candidate(f'<path d="{path}" stroke="black" stroke-width="1"/>')
                try:
                    result = validate_candidate(svg, ("S01-B1",), {"S01-B1": []})
                except ValueError as error:
                    self.fail(f"inbounds rounded rectangle rejected: {error}")
                self.assertIn(b'<path ', result)
                self.assertNotIn(b'data-block-id', result)

    def test_exact_extrema_for_rotated_swept_large_relative_and_scaled_arcs(self):
        # Literal boxes from circles and a (100,50) ellipse rotated with cos=.8,
        # sin=.6: its full axis radii are sqrt(7300), sqrt(5200). No sampling.
        cases = (
            (ROUNDED_RECTS[0], (104, 590, 424, 642)),
            (ROUNDED_RECTS[1], (90, 188, 1190, 256)),
            (ROUNDED_RECTS[2], (713, 113, 1167, 607)),
            ('M200 300 A100 100 0 0 1 400 300', (200, 200, 400, 300)),
            ('M200 300 A100 100 0 0 0 400 300', (200, 300, 400, 400)),
            ('M300 200 A100 100 0 1 1 200 300', (200, 200, 400, 400)),
            ('M300 200 A100 100 0 1 0 200 300', (100, 100, 300, 300)),
            ('M480 360 A100 50 36.86989764584402 0 1 320 240',
             (314.5599625468247, 240, 480, 372.1110255092798)),
            ('M480 360 A100 50 36.86989764584402 0 0 320 240',
             (320, 227.8889744907202, 485.4400374531753, 360)),
            ('M480 360 A100 50 396.86989764584402 0 1 370 340',
             (370, 340, 480, 372.1110255092798)),
            ('m200 300 a100 100 0 0 1 200 0 100 100 0 0 1 -200 0 z',
             (200, 200, 400, 400)),
            ('M200 300 A10 20 0 0 1 400 300', (200, 100, 400, 300)),
            ('M480 360 A10 5 36.86989764584402 0 1 320 240',
             (314.5599625468247, 240, 480, 372.1110255092798)),
            ('M600 300 A1 100 0 0 0 700 300', (600, 300, 700, 5300)),
            ('M200 200 A0 100 45 1 1 300 300', (200, 200, 300, 300)),
            ('M200 200 A100 0 45 1 0 300 300', (200, 200, 300, 300)),
            ('M200 200 A100 50 45 1 1 200 200', (200, 200, 200, 200)),
        )
        for index, (path, expected) in enumerate(cases):
            with self.subTest(case=index):
                points = _path_points(path)
                actual = (min(x for x, y in points), min(y for x, y in points),
                          max(x for x, y in points), max(y for x, y in points))
                for got, want in zip(actual, expected):
                    self.assertAlmostEqual(got, want, delta=1e-6)

    def test_outside_arc_reports_only_numeric_bounds_and_fixed_reason(self):
        svg = candidate('<path d="M64 200 H200 A20 20 0 0 1 220 220" '
                        'stroke="black" stroke-width="1" stroke-linejoin="round"/>')
        with self.assertRaises(ValueError) as raised:
            validate_candidate(svg, ("S01-B1",), {"S01-B1": []})
        self.assertEqual(str(raised.exception), 'svg_contract_failed')
        self.assertIsInstance(raised.exception, GeometryError)
        details = raised.exception.details
        self.assertEqual({key: details[key] for key in ('reason', 'bbox', 'bounds')}, {
            'reason': 'geometry_out_of_bounds',
            'bbox': [63.5, 199.5, 220.5, 220.5],
            'bounds': [64, 64, 1216, 656],
        })

    def test_malformed_flags_and_nonfinite_or_extreme_arcs_fail_closed(self):
        arcs = [f'M200 300 A100 50 0 {flag} 1 400 300'
                for flag in ('2', '-1', '0.5', '1.0', '1e0', '+1', '-0')]
        arcs += [f'M200 300 A100 50 0 0 {flag} 400 300'
                 for flag in ('2', '1.0', '1e0', '+1')]
        arcs += [
            'M200 300 A-100 50 0 0 1 400 300',
            'M200 300 A100 -50 0 0 1 400 300',
            'M200 300 A100 50 NaN 0 1 400 300',
            'M200 300 AInf 50 0 0 1 400 300',
            'M200 300 A1e999 50 0 0 1 400 300',
            'M200 300 A100 50 0 0 1 1e999 300',
            'M200 300 A1e308 1e308 45 0 1 400 300',
            'M200 300 A1e-320 1e-320 0 0 1 400 300',
            'M200 300 A1e-300 1e300 0 0 1 400 300',
            'M200 300 A1e300 1e-300 45 0 1 400 300',
            'M200 300 A1e300 1e300 37 1 1 400 300',
            'M200 300 A1e300 1e300 37 0 1 400 300',
            'M1e308 300 a100 50 0 0 1 1e308 0',
            'M200 300 A100 50 0 0 1 400',
        ]
        for index, path in enumerate(arcs):
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, '^svg_contract_failed$'):
                validate_candidate(candidate(f'<path d="{path}"/>'),
                                   ("S01-B1",), {"S01-B1": []})

    def test_cancellation_prone_eccentric_arcs_fail_closed(self):
        # Ellipse sagitta gives true maxima 1218.75 and 1232.9135802469;
        # adding a huge center to the radius previously rounded both inside.
        paths = (
            'M1200 200 A6e18 4e10 0 0 1 1200 400',
            'M986 200 A3.6e17 2.7e9 0 0 1 986 400',
            'M1200 200 a6e18 4e10 0 0 1 0 200',
            'M200 640 A4e10 6e18 0 0 0 400 640',
            # Small source radii can also become huge after SVG correction.
            'M200 200 A10 .000001 0 0 1 200 400',
        )
        for index, path in enumerate(paths):
            with self.subTest(case=index):
                with self.assertRaises(GeometryError) as raised:
                    validate_candidate(candidate(f'<path d="{path}"/>'),
                                       ("S01-B1",), {"S01-B1": []})
                self.assertEqual(raised.exception.details['reason'], 'unstable_arc')
                self.assertNotIn('bbox', raised.exception.details)
        # Large but usable radii still pass; this is not a slide-sized radius cap.
        svg = candidate('<path d="M1200 200 A6000 4000 0 0 1 1200 400"/>')
        self.assertIn(b'<path ', validate_candidate(svg, ("S01-B1",), {"S01-B1": []}))

    def test_geometry_failure_details_never_echo_input(self):
        cases = (
            ('<path d="M200 300 A100 50 0 1e0 1 400 300"/>', 'invalid_arc_flags'),
            ('<path d="M200 300 A-100 50 0 0 1 400 300"/>', 'invalid_arc'),
            ('<path d="M200 300 A100 50 0 0 1 400"/>', 'invalid_path'),
            ('<path d="M200 300 A1e999 50 0 0 1 400 300"/>', 'non_finite_number'),
            ('<path d="M200 300 A1e-999 50 0 0 1 400 300"/>', 'numeric_underflow'),
            ('<path d="M200 300 A1e300 1e300 0 1 1 400 300"/>', 'unstable_arc'),
            ('<rect x="1e308" y="100" width="1e308" height="100"/>', 'non_finite_geometry'),
            ('<text x="100" y="120" font-size="39" font-family="Arial" data-role="title">'
             '<tspan x="100" y="120">private text</tspan></text>', 'invalid_text'),
            ('<text x="100" y="120" font-size="40" font-family="Arial" data-role="title">'
             '<tspan x="100" y="120">' + 'private text ' * 100 + '</tspan></text>', 'text_overflow'),
        )
        for index, (shape, reason) in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ValueError) as raised:
                    validate_geometry(ET.fromstring(shape), {})
                self.assertIsInstance(raised.exception, GeometryError)
                self.assertEqual(str(raised.exception), 'svg_contract_failed')
                self.assertEqual(raised.exception.details, {'reason': reason})

    def test_real_outside_arcs_and_stroke_miter_text_guards_still_reject(self):
        shapes = [f'<path d="{path}"/>' for path in (
            'M100 100 A50 50 0 0 1 200 100',
            'M100 630 A50 50 0 0 0 200 630',
            'M100 100 A50 50 0 0 0 100 200',
            'M1180 100 A50 50 0 0 1 1180 200',
            'M600 300 A1 100 0 0 0 700 300',
            'M100 200 C0 200 150 250 200 250',  # Conservative Bezier hull remains.
        )]
        shapes += [
            f'<path d="{ROUNDED_RECTS[0]}" stroke="black" stroke-width="30" stroke-linejoin="round"/>',
            '<path d="M70 200 A20 20 0 0 1 110 200" stroke="black" stroke-width="4"/>',
            '<g stroke="black" stroke-width="16" stroke-linejoin="round">'
            '<path d="M70 200 A20 20 0 0 1 110 200"/></g>',
            '<text x="100" y="64" font-size="40" font-family="Arial" data-role="title">'
            '<tspan x="100" y="64">Title</tspan></text>',
        ]
        for index, shape in enumerate(shapes):
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, '^svg_contract_failed$'):
                validate_candidate(candidate(shape), ("S01-B1",), {"S01-B1": []})
        # Touching the boundary remains valid, both directly and after inheritance.
        path = ET.fromstring('<path d="M70 200 A20 20 0 0 1 110 200"/>')
        attrs = {'stroke': 'black', 'stroke-width': '12', 'stroke-linejoin': 'round'}
        self.assertIsNone(validate_geometry(path, attrs))
        shape = ('<g stroke="black" stroke-width="12" stroke-linejoin="round">'
                 '<path d="M70 200 A20 20 0 0 1 110 200"/></g>')
        self.assertIn(b'<path ', validate_candidate(candidate(shape), ("S01-B1",), {"S01-B1": []}))


if __name__ == "__main__":
    unittest.main()
