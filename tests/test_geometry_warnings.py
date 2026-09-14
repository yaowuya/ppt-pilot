"""A conservative text margin is a warning, not proof of clipped glyphs."""
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))
from _svg_geometry import GeometryError, validate_geometry


class GeometryWarningTests(unittest.TestCase):
    def text(self, x=932, content='一' * 13):
        return ElementTree.fromstring(
            '<text x="%s" y="400" font-size="20" font-family="Microsoft YaHei" data-role="body">'
            '<tspan x="%s" y="400">%s</tspan></text>' % (x, x, content))

    def test_text_inside_safe_area_but_outside_margin_is_warning(self):
        try:
            warnings = validate_geometry(self.text(), {})
        except GeometryError as exc:
            self.fail('A conservative margin still aborts generation: ' + str(exc))
        self.assertEqual(warnings, [{'code': 'text_margin_unverified', 'estimated_width': 260.0,
                                     'available_width': 284.0, 'margin_limit': 249.92}])

    def test_estimated_bounds_outside_explicit_safe_area_still_fail(self):
        with self.assertRaises(GeometryError):
            validate_geometry(self.text(x=1000), {})

    def test_text_well_inside_margin_has_no_warning(self):
        self.assertIsNone(validate_geometry(self.text(x=800), {}))

    def test_warnings_never_include_visible_content(self):
        content = 'PRIVATE_VALUE'
        try:
            warnings = validate_geometry(self.text(x=1060, content=content), {})
        except GeometryError as exc:
            self.fail('Margin must be reported without aborting: ' + str(exc))
        self.assertNotIn(content, repr(warnings))
        self.assertTrue(warnings)


if __name__ == '__main__':
    unittest.main()
