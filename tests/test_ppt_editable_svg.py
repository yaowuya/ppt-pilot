import hashlib
import importlib
import inspect
import json
import math
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "ppt-editable"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "ppt-editable"
sys.path.insert(0, str(SCRIPTS_ROOT))

from _ppt_editable import (  # noqa: E402
    Bounds,
    EditableError,
    ResolvedStyle,
    SpeakerNotes,
    TextLine,
    TextRun,
)
from _ppt_editable.contract import (  # noqa: E402
    SlideSource,
    parse_storyboard,
    resolve_slide_sources,
    validate_completed_run,
)
from _ppt_editable.svg_parser import (  # noqa: E402
    DeckPreflightError,
    local_name,
    parse_svg_slide,
    preflight_deck,
)


class SvgPreflightTests(unittest.TestCase):
    def _temp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def _source(self, text, slide_id="S01"):
        root = self._temp()
        path = root / (slide_id + ".svg")
        path.write_text(text, encoding="utf-8")
        return SlideSource(
            slide_id=slide_id,
            path=path,
            relative_path="slides/{}.svg".format(slide_id),
            owner="production",
        )

    def _parse(self, text):
        return parse_svg_slide(self._source(text), SpeakerNotes())

    def _parse_bytes(self, data):
        root = self._temp()
        path = root / "S01.svg"
        path.write_bytes(data)
        source = SlideSource(
            slide_id="S01",
            path=path,
            relative_path="slides/S01.svg",
            owner="production",
        )
        return parse_svg_slide(source, SpeakerNotes())

    def _assert_reason(self, expected, callback):
        with self.assertRaises(EditableError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def _tree_snapshot(self, root):
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_parser_uses_defusedxml_not_standard_elementtree(self):
        import _ppt_editable.svg_parser as module

        source = inspect.getsource(module)
        self.assertIn("defusedxml", source)
        self.assertNotIn("import xml.etree", source)

    def test_path_and_text_helpers_are_consumed_through_narrow_injection(self):
        path_calls = []
        text_calls = []

        def injected_path_bounds(data):
            path_calls.append(data)
            return Bounds(10.0, 20.0, 30.0, 40.0)

        def injected_text_lines(element, style, tree_path):
            text_calls.append((element.tag, tree_path))
            return (
                TextLine(
                    line_index=0,
                    x=50.0,
                    y=60.0,
                    anchor="start",
                    runs=(TextRun("editable", style),),
                    bounds=Bounds(50.0, 40.0, 110.0, 70.0),
                ),
            )

        source = self._source(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<path d="M 0 0 L 1 1"/>'
            '<text x="50" y="60">editable</text>'
            '</svg>'
        )
        try:
            plan = parse_svg_slide(
                source,
                SpeakerNotes(),
                path_bounds_parser=injected_path_bounds,
                text_flattener=injected_text_lines,
            )
        except TypeError as exc:
            self.fail(f"path/text helper injection is missing: {exc}")

        self.assertEqual(path_calls, ["M 0 0 L 1 1"])
        self.assertEqual(text_calls, [("{http://www.w3.org/2000/svg}text", "/svg[1]/text[1]")])
        self.assertEqual(plan.nodes[0].bounds, Bounds(10.0, 20.0, 30.0, 40.0))
        self.assertIn("path_bounds_parser", inspect.signature(preflight_deck).parameters)
        self.assertIn("text_flattener", inspect.signature(preflight_deck).parameters)

    def test_falsey_noncallable_helper_injections_are_rejected(self):
        source = self._source(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<rect x="0" y="0" width="1" height="1"/>'
            '</svg>'
        )
        for kwargs in (
            {"path_bounds_parser": False},
            {"text_flattener": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(TypeError, "must be callable"):
                    parse_svg_slide(source, SpeakerNotes(), **kwargs)

    def test_local_name_handles_default_namespace_and_plain_names(self):
        self.assertEqual(local_name("{http://www.w3.org/2000/svg}tspan"), "tspan")
        self.assertEqual(local_name("rect"), "rect")

    def test_nested_groups_preserve_order_bounds_and_inherited_style(self):
        path = FIXTURE_ROOT / "svg" / "nested-groups.svg"
        plan = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(assertion_title="Nested groups"),
        )
        self.assertEqual(plan.title, "Nested groups")
        self.assertEqual(plan.description, "Inherited style and order")
        self.assertEqual([node.kind for node in plan.nodes], ["g"])
        outer = plan.nodes[0]
        self.assertEqual(outer.tree_path, "/svg[1]/g[1]")
        self.assertEqual(outer.style.data_source_id, "SRC-001")
        self.assertEqual([node.kind for node in outer.children], ["rect", "g"])
        rect, inner = outer.children
        self.assertEqual(rect.style.fill, "#112233")
        self.assertEqual(rect.style.font_family, "Arial, sans-serif")
        self.assertEqual(inner.children[0].style.stroke, "#445566")
        self.assertEqual(inner.children[0].style.stroke_width, 2.0)
        self.assertLessEqual(outer.bounds.left, rect.bounds.left)
        self.assertGreaterEqual(outer.bounds.right, inner.bounds.right)

    def test_leaf_opacity_multiplies_resolved_fill_and_stroke_opacity(self):
        plan = self._parse(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<g fill-opacity="0.4" stroke-opacity="0.6">'
            '<rect x="10" y="10" width="100" height="50" fill="#112233" '
            'stroke="#445566" stroke-width="2" opacity="0.5"/>'
            '</g></svg>'
        )
        leaf = plan.nodes[0].children[0]
        self.assertAlmostEqual(leaf.style.fill_opacity, 0.2)
        self.assertAlmostEqual(leaf.style.stroke_opacity, 0.3)
        self.assertAlmostEqual(leaf.style.opacity, 0.5)

    def test_every_element_and_namespaced_attribute_must_use_the_exact_svg_contract(self):
        cases = (
            (
                '<foo:rect xmlns:foo="urn:evil" x="0" y="0" width="1" height="1"/>',
                "svg_element_unsupported",
            ),
            (
                '<rect xmlns="" x="0" y="0" width="1" height="1"/>',
                "svg_element_unsupported",
            ),
            (
                '<foo:rect xmlns:foo="http://www.w3.org/2000/svg}evil" '
                'x="0" y="0" width="1" height="1"/>',
                "svg_xml_invalid",
            ),
            (
                '<rect xmlns:foo="urn:evil" foo:fill="#112233" x="0" y="0" width="1" height="1"/>',
                "svg_attribute_unsupported",
            ),
        )
        for body, reason in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>{}</svg>'
            ).format(body)
            with self.subTest(body=body):
                self._assert_reason(reason, lambda value=text: self._parse(value))
        import _ppt_editable.svg_parser as module

        forged = SimpleNamespace(
            tag="{http://www.w3.org/2000/svg}evil}rect"
        )
        self._assert_reason(
            "svg_element_unsupported",
            lambda: module._require_svg_element(forged, "S01", "/svg[1]"),
        )

    def test_processing_instructions_are_rejected_before_xml_parse(self):
        text = (
            '<?xml-stylesheet href="https://example.com/evil.css"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<rect x="0" y="0" width="1" height="1"/>'
            '</svg>'
        )
        self._assert_reason("svg_external_reference", lambda: self._parse(text))

    def test_non_utf8_pi_and_dtd_encodings_are_rejected_before_parse(self):
        bodies = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<?xml-stylesheet href="https://example.com/evil.css"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc><rect x="0" y="0" width="1" height="1"/>'
            '</svg>',
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE svg>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc><rect x="0" y="0" width="1" height="1"/>'
            '</svg>',
        )
        for text in bodies:
            with self.subTest(kind="PI" if "stylesheet" in text else "DTD"):
                self._assert_reason(
                    "svg_xml_invalid",
                    lambda value=text: self._parse_bytes(value.encode("utf-16")),
                )

    def test_xml_comments_are_not_plain_metadata(self):
        text = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>visible<!-- hidden -->title</title><desc>x</desc>'
            '<rect x="0" y="0" width="1" height="1"/>'
            '</svg>'
        )
        self._assert_reason("svg_xml_invalid", lambda: self._parse(text))

    def test_dtd_and_external_entity_are_rejected_behaviorally(self):
        text = (
            '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///secret">]>'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>&xxe;</title><desc>x</desc>'
            '<rect x="0" y="0" width="1" height="1"/>'
            '</svg>'
        )
        self._assert_reason("svg_xml_invalid", lambda: self._parse(text))

    def test_canvas_must_be_exact_and_finite(self):
        for view_box in (
            "0 0 1280 721",
            "0 0 1280",
            "0 0 NaN 720",
            "0,0,1280,720",
            "0 0 1.28e3 720",
            "-0 0 1280 720",
            "0.0 0 1280 720",
        ):
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="{}">'
                '<title>x</title><desc>x</desc></svg>'
            ).format(view_box)
            with self.subTest(view_box=view_box):
                self._assert_reason("svg_canvas_invalid", lambda value=text: self._parse(value))

    def test_canvas_dimensions_use_exact_lexical_values(self):
        cases = (
            ("1280px", "720"),
            ("1280.0", "720"),
            ("01280", "720"),
            ("1280", "720px"),
            ("1280", "0720"),
        )
        for width, height in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
                'width="{}" height="{}">'
                '<title>x</title><desc>x</desc>'
                '<rect x="0" y="0" width="1" height="1"/>'
                '</svg>'
            ).format(width, height)
            with self.subTest(width=width, height=height):
                self._assert_reason(
                    "svg_canvas_invalid", lambda value=text: self._parse(value)
                )

    def test_derived_bounds_must_remain_finite(self):
        text = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<rect x="1e308" y="0" width="1e308" height="1"/>'
            '</svg>'
        )
        self._assert_reason("svg_coordinate_invalid", lambda: self._parse(text))

    def test_unknown_elements_attributes_and_external_content_fail_closed(self):
        cases = (
            ("<image href=\"file:///secret\"/>", "svg_element_unsupported"),
            ("<foreignObject/>", "svg_element_unsupported"),
            ("<defs/><use href=\"#x\"/>", "svg_element_unsupported"),
            ("<rect x=\"0\" y=\"0\" width=\"1\" height=\"1\" transform=\"translate(1)\"/>", "svg_attribute_unsupported"),
            ("<rect x=\"0\" y=\"0\" width=\"1\" height=\"1\" style=\"fill:red\"/>", "svg_attribute_unsupported"),
            ("<rect x=\"0\" y=\"0\" width=\"1\" height=\"1\" fill=\"url(#x)\"/>", "svg_external_reference"),
            ("<g opacity=\"0.5\"><rect x=\"0\" y=\"0\" width=\"1\" height=\"1\"/></g>", "svg_attribute_unsupported"),
        )
        for body, reason in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>{}</svg>'
            ).format(body)
            with self.subTest(body=body):
                self._assert_reason(reason, lambda value=text: self._parse(value))

    def test_numeric_units_ranges_and_paints_are_strict(self):
        cases = (
            ('<rect x="10%" y="0" width="1" height="1"/>', "svg_coordinate_invalid"),
            ('<rect x="0" y="0" width="0" height="1"/>', "svg_coordinate_invalid"),
            ('<rect x="0" y="0" width="1" height="1" fill="red"/>', "svg_attribute_unsupported"),
            ('<rect x="0" y="0" width="1" height="1" opacity="1.1"/>', "svg_attribute_unsupported"),
            ('<text x="0" y="20" text-anchor="justify">x</text>', "svg_attribute_unsupported"),
        )
        for body, reason in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>{}</svg>'
            ).format(body)
            with self.subTest(body=body):
                self._assert_reason(reason, lambda value=text: self._parse(value))

    def test_numeric_font_weight_lexemes_are_canonicalized(self):
        slide = self._parse(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20" font-weight=" 700 ">x</text>'
            '</svg>'
        )
        self.assertEqual(slide.nodes[0].text_lines[0].runs[0].style.font_weight, "700")
        self._assert_reason(
            "svg_attribute_unsupported",
            lambda: self._parse(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>'
                '<text x="0" y="20" font-weight="650">x</text>'
                '</svg>'
            ),
        )

    def test_empty_group_is_rejected(self):
        self._assert_reason(
            "svg_group_empty",
            lambda: self._parse(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc><g id="empty"/></svg>'
            ),
        )

    def test_title_and_description_are_unique_attribute_free_metadata(self):
        cases = (
            '<title id="x">x</title><desc>x</desc>',
            '<title>x</title><title>y</title><desc>x</desc>',
            '<title>x</title><desc>x</desc><desc>y</desc>',
        )
        for metadata in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '{}<rect x="0" y="0" width="1" height="1"/></svg>'
            ).format(metadata)
            with self.subTest(metadata=metadata):
                self._assert_reason(
                    "svg_attribute_unsupported", lambda value=text: self._parse(value)
                )

    def test_metadata_must_be_root_level_plain_text_and_page_must_be_visible(self):
        cases = (
            (
                '<title><script>bad</script></title><desc>x</desc>'
                '<rect x="0" y="0" width="1" height="1"/>',
                "svg_element_unsupported",
            ),
            (
                '<title>x</title><desc>x</desc><g>'
                '<title>nested</title><rect x="0" y="0" width="1" height="1"/>'
                '</g>',
                "svg_element_unsupported",
            ),
            ('<desc>x</desc><rect x="0" y="0" width="1" height="1"/>', "svg_attribute_unsupported"),
            ('<title>x</title><desc>x</desc>', "svg_group_empty"),
        )
        for body, reason in cases:
            text = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '{}'
                '</svg>'
            ).format(body)
            with self.subTest(body=body):
                self._assert_reason(reason, lambda value=text: self._parse(value))

    def test_preflight_revalidates_each_source_before_parsing(self):
        import _ppt_editable.svg_parser as module
        from _ppt_editable.contract import validate_safe_regular_file

        root = self._temp() / "run"
        shutil.copytree(FIXTURE_ROOT / "run-complete", root)
        context = validate_completed_run(root)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        with mock.patch.object(
            module,
            "validate_safe_regular_file",
            wraps=validate_safe_regular_file,
        ) as validator:
            preflight_deck(
                context,
                sources,
                storyboard,
                "sha256:" + "a" * 64,
            )
        self.assertEqual(validator.call_count, len(sources))

    def test_preflight_module_has_no_candidate_writer_dependency(self):
        import _ppt_editable.svg_parser as module

        source = inspect.getsource(module)
        self.assertNotIn("atomic_io", source)
        self.assertNotIn("python-pptx", source)
        self.assertNotIn("Presentation(", source)
        self.assertNotIn("atomic_write", source)

    def test_deck_preflight_collects_independent_failures_without_output(self):
        root = self._temp() / "run"
        shutil.copytree(FIXTURE_ROOT / "run-complete", root)
        (root / "samples" / "S01.svg").write_text(
            (FIXTURE_ROOT / "svg" / "unsupported.svg").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "slides" / "S02.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>',
            encoding="utf-8",
        )
        context = validate_completed_run(root)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        before = self._tree_snapshot(root)
        with self.assertRaises(DeckPreflightError) as raised:
            preflight_deck(context, sources, storyboard, "sha256:" + "a" * 64)
        self.assertEqual(len(raised.exception.failures), 2)
        self.assertEqual(
            {failure.code for failure in raised.exception.failures},
            {"svg_attribute_unsupported", "svg_canvas_invalid"},
        )
        self.assertFalse((root / "delivery").exists())
        self.assertEqual(self._tree_snapshot(root), before)

    def test_preflight_rejects_source_bytes_changed_after_resolution(self):
        root = self._temp() / "run"
        shutil.copytree(FIXTURE_ROOT / "run-complete", root)
        context = validate_completed_run(root)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        changed = root / "slides" / "S02.svg"
        changed.write_bytes(changed.read_bytes() + b"<!-- changed -->\n")
        with self.assertRaises(DeckPreflightError) as raised:
            preflight_deck(
                context,
                sources,
                storyboard,
                "sha256:" + "a" * 64,
            )
        self.assertEqual(
            [failure.code for failure in raised.exception.failures],
            ["source_path_unsafe"],
        )

    def test_preflight_rejects_empty_subset_duplicate_and_order_mismatch(self):
        root = self._temp() / "run"
        shutil.copytree(FIXTURE_ROOT / "run-complete", root)
        context = validate_completed_run(root)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        invalid_sets = ((), sources[:1], (sources[1], sources[0]), (sources[0], sources[0]))
        for selected in invalid_sets:
            with self.subTest(ids=[source.slide_id for source in selected]):
                with self.assertRaises(DeckPreflightError) as raised:
                    preflight_deck(
                        context,
                        selected,
                        storyboard,
                        "sha256:" + "a" * 64,
                    )
                self.assertEqual(
                    [failure.code for failure in raised.exception.failures],
                    ["slide_set_invalid"],
                )

    def test_valid_fixture_run_preflights_to_ordered_deck_plan(self):
        root = self._temp() / "run"
        shutil.copytree(FIXTURE_ROOT / "run-complete", root)
        context = validate_completed_run(root)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        snapshot = "sha256:" + "b" * 64
        deck = preflight_deck(context, sources, storyboard, snapshot)
        self.assertEqual(deck.deck_id, "fixture-deck")
        self.assertEqual(deck.input_snapshot_id, snapshot)
        self.assertEqual([slide.slide_id for slide in deck.slides], ["S01", "S02"])
        self.assertEqual(deck.slides[0].notes.next_link, "S02")


class PathParserTests(unittest.TestCase):
    def _path(self):
        return importlib.import_module("_ppt_editable.path_parser")

    def _assert_path_reason(self, expected, data):
        with self.assertRaises(EditableError) as raised:
            self._path().parse_path(data)
        self.assertEqual(raised.exception.code, expected)

    def test_fixture_case_ids_and_results_are_stable(self):
        payload = json.loads((FIXTURE_ROOT / "path-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            [case["id"] for case in payload["valid"]],
            ["absolute-lines", "relative-lines", "repeated-move", "multiple-subpaths", "arc"],
        )
        for case in payload["valid"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(self._path().parse_path(case["d"]))
        for case in payload["invalid"]:
            with self.subTest(case=case["id"]):
                expected = (
                    "svg_arc_rotation_unsupported"
                    if case["id"] == "rotation"
                    else "svg_path_invalid"
                )
                self._assert_path_reason(expected, case["d"])

    def test_cursor_lexer_consumes_every_character_and_retains_offsets(self):
        module = self._path()
        tokens = module.tokenize_path("M +1. .5e1, -2E-1 L10-5")
        self.assertEqual([token.kind for token in tokens], [
            "command", "number", "number", "number", "command", "number", "number"
        ])
        self.assertEqual([token.value for token in tokens if token.kind == "number"], [
            "+1.", ".5e1", "-2E-1", "10", "-5"
        ])
        self.assertEqual(tokens[0].offset, 0)
        for data in ("M0 0 @ L1 1", "M0 0L1e 2", "M0,,0", "M,0 0", "M0 0,"):
            with self.subTest(data=data):
                self._assert_path_reason("svg_path_invalid", data)

    def test_lexer_rejects_unknown_letters_and_malformed_numbers_at_exact_offset(self):
        module = self._path()
        for data, offset in (
            ("M0 0X1 1", 4),
            ("M0 0L1e 2", 6),
            ("MNaN 0", 1),
            ("MInfinity 0", 1),
        ):
            with self.subTest(data=data):
                with self.assertRaisesRegex(
                    EditableError,
                    rf"offset {offset}$",
                ):
                    module.tokenize_path(data)

    def test_path_bounds_owns_optional_stroke_expansion_exactly_once(self):
        module = self._path()
        segments = module.parse_path("M0 0L10 0")
        try:
            expanded = module.path_bounds(segments, stroke_width=4.0)
        except TypeError as exc:
            self.fail(f"path_bounds stroke-width contract is missing: {exc}")
        self.assertEqual(expanded, Bounds(-2.0, -2.0, 12.0, 2.0))

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source_path = Path(directory.name) / "S01.svg"
        source_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<path d="M0 0L10 0" fill="none" stroke="#000000" stroke-width="4"/>'
            '</svg>',
            encoding="utf-8",
        )
        plan = parse_svg_slide(
            SlideSource("S01", source_path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        self.assertEqual(plan.nodes[0].bounds, Bounds(-2.0, -2.0, 12.0, 2.0))

    def test_absolute_relative_repeated_and_close_commands_normalize(self):
        module = self._path()
        segments = module.parse_path("M10 20 L30 40 H50 V60 Z")
        self.assertEqual(
            [(type(item).__name__, getattr(item, "x", None), getattr(item, "y", None)) for item in segments],
            [
                ("MoveTo", 10.0, 20.0),
                ("LineTo", 30.0, 40.0),
                ("LineTo", 50.0, 40.0),
                ("LineTo", 50.0, 60.0),
                ("ClosePath", None, None),
            ],
        )
        relative = module.parse_path("m10 20 l20 20 h20 v20 z m5 5 5 5")
        self.assertEqual(
            [(type(item).__name__, getattr(item, "x", None), getattr(item, "y", None)) for item in relative],
            [
                ("MoveTo", 10.0, 20.0),
                ("LineTo", 30.0, 40.0),
                ("LineTo", 50.0, 40.0),
                ("LineTo", 50.0, 60.0),
                ("ClosePath", None, None),
                ("MoveTo", 15.0, 25.0),
                ("LineTo", 20.0, 30.0),
            ],
        )
        repeated = module.parse_path("M0 0 10 10 20 0")
        self.assertEqual([type(item).__name__ for item in repeated], ["MoveTo", "LineTo", "LineTo"])

    def test_parser_rejects_first_command_arity_flags_radii_and_rotation(self):
        invalid = (
            "L0 0",
            "M0",
            "M0 0L1",
            "M0 0H",
            "M0 0A1 1 0 2 0 2 2",
            "M0 0A1 1 0 1.0 0 2 2",
            "M0 0A-1 1 0 0 0 2 2",
            "M0 0C1 1 2 2 3 3",
            "M0 0X1 1",
        )
        for data in invalid:
            with self.subTest(data=data):
                self._assert_path_reason("svg_path_invalid", data)
        self._assert_path_reason(
            "svg_arc_rotation_unsupported",
            "M0 0A1 2 45 0 1 2 2",
        )
        self._assert_path_reason(
            "svg_arc_rotation_unsupported",
            "M0 0A1 2 1e-400 0 1 2 2",
        )
        self._assert_path_reason(
            "svg_path_invalid",
            "M0 0A-1e-400 2 0 0 1 2 2",
        )
        self._assert_path_reason(
            "svg_path_invalid",
            "M0 0L1e-400 0",
        )
        self._assert_path_reason(
            "svg_path_invalid",
            "M1e308 0l1e308 0",
        )

    def test_zero_radius_becomes_line_and_same_endpoint_arc_is_noop(self):
        module = self._path()
        zero = module.parse_path("M0 0A0 10 0 0 1 20 0")
        self.assertEqual([type(item).__name__ for item in zero], ["MoveTo", "LineTo"])
        self.assertEqual((zero[1].x, zero[1].y), (20.0, 0.0))
        noop = module.parse_path("M5 5A10 10 0 0 1 5 5")
        self.assertEqual([type(item).__name__ for item in noop], ["MoveTo"])

    def test_endpoint_arc_returns_corrected_radii_and_direction(self):
        module = self._path()
        arc = module.ArcTo(10.0, 10.0, 0.0, 0, 1, 100.0, 0.0)
        center = module.endpoint_arc_to_center(0.0, 0.0, arc)
        self.assertAlmostEqual(center.cx, 50.0, places=9)
        self.assertAlmostEqual(center.cy, 0.0, places=9)
        self.assertAlmostEqual(center.corrected_rx, 50.0, places=9)
        self.assertAlmostEqual(center.corrected_ry, 50.0, places=9)
        self.assertGreater(center.sweep_radians, 0.0)
        reverse = module.endpoint_arc_to_center(
            0.0, 0.0, module.ArcTo(50.0, 50.0, 0.0, 0, 0, 100.0, 0.0)
        )
        self.assertLess(reverse.sweep_radians, 0.0)
        tiny = module.endpoint_arc_to_center(
            0.0,
            0.0,
            module.ArcTo(1e-200, 1e-200, 0.0, 0, 1, 1.0, 0.0),
        )
        self.assertAlmostEqual(tiny.corrected_rx, 0.5, places=12)
        self.assertAlmostEqual(tiny.corrected_ry, 0.5, places=12)
        huge_center = module.endpoint_arc_to_center(
            1e308,
            0.0,
            module.ArcTo(1.0, 1.0, 0.0, 0, 1, 1e308, 2.0),
        )
        self.assertTrue(math.isfinite(huge_center.cx))
        self.assertEqual(huge_center.cx, 1e308)

    def test_large_arc_with_tiny_chord_keeps_nearly_full_sweep(self):
        module = self._path()
        segments = module.parse_path("M0 0A1e17 1e17 0 1 1 1 0")
        arc = segments[1]
        center = module.endpoint_arc_to_center(0.0, 0.0, arc)
        self.assertGreater(center.sweep_radians, 6.0)
        bounds = module.path_bounds(segments)
        self.assertGreater(bounds.right - bounds.left, 1.9e17)
        self.assertGreater(bounds.bottom - bounds.top, 1.9e17)

    def test_arc_bounds_include_only_extrema_on_the_sweep(self):
        module = self._path()
        quarter = module.parse_path("M100 100A20 20 0 0 1 120 120")
        self.assertEqual(module.path_bounds(quarter), Bounds(100.0, 100.0, 120.0, 120.0))
        corrected = module.parse_path("M0 0A10 10 0 0 1 100 0")
        bounds = module.path_bounds(corrected)
        self.assertEqual((bounds.left, bounds.right), (0.0, 100.0))
        self.assertAlmostEqual(bounds.bottom - bounds.top, 50.0, places=9)
        near_integer = module.path_bounds(
            module.parse_path("M0 0L1.0000000000001 0")
        )
        self.assertGreaterEqual(near_integer.right, 1.0000000000001)
        cardinal = module.path_bounds(
            module.parse_path("M0 1A1 1 0 0 1-1 0")
        )
        self.assertEqual(cardinal.right, 0.0)

    def test_move_only_subpaths_do_not_expand_bounds_or_count_as_visible(self):
        module = self._path()
        segments = module.parse_path("M1000 1000 M0 0 L10 0")
        self.assertEqual(module.path_bounds(segments), Bounds(0.0, 0.0, 10.0, 0.0))
        for data in ("M0 0", "M0 0Z"):
            with self.subTest(data=data):
                with self.assertRaises(EditableError) as raised:
                    module.path_bounds(module.parse_path(data))
                self.assertEqual(raised.exception.code, "svg_path_invalid")

    def test_round_int_uses_halves_away_from_zero(self):
        module = self._path()
        self.assertEqual(
            [
                module.round_int(value)
                for value in (
                    1.5,
                    1.49,
                    -1.5,
                    -1.49,
                    0.49999999999999994,
                    -0.49999999999999994,
                )
            ],
            [2, 1, -2, -1, 0, 0],
        )

    def test_svg_parser_uses_exact_path_bounds_not_canvas_placeholder(self):
        fixture = FIXTURE_ROOT / "svg" / "arcs.svg"
        plan = parse_svg_slide(
            SlideSource("S01", fixture, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        first, second = plan.nodes
        self.assertEqual(first.kind, "path")
        self.assertEqual(first.bounds, Bounds(80.0, 100.0, 300.0, 240.0))
        self.assertLess(second.bounds.right - second.bounds.left, 1280.0)
        self.assertLess(second.bounds.bottom - second.bounds.top, 720.0)


class TextLayoutTests(unittest.TestCase):
    def _text(self):
        return importlib.import_module("_ppt_editable.text_layout")

    def _fixture_plan(self):
        path = FIXTURE_ROOT / "svg" / "namespace-text.svg"
        return parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )

    def test_visible_internal_source_ids_fail_but_machine_metadata_passes(self):
        module = self._text()
        self.assertTrue(module._VISIBLE_INTERNAL_SOURCE_ID_RE.flags & re.IGNORECASE)
        self.assertEqual(
            module._VISIBLE_INTERNAL_SOURCE_ID_RE.pattern,
            r"\bSRC-[0-9]+\b",
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "S01.svg"
        for visible_text in (
            "来源：SRC-001 · SRC-002",
            "Source: SRC-003",
            "SRC-005",
            "src-006",
            "SrC-007",
        ):
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>'
                '<text x="10" y="20">{}</text>'
                '</svg>'.format(visible_text),
                encoding="utf-8",
            )
            with self.subTest(visible_text=visible_text):
                with self.assertRaises(EditableError) as raised:
                    parse_svg_slide(
                        SlideSource("S01", path, "slides/S01.svg", "production"),
                        SpeakerNotes(),
                    )
                self.assertEqual(raised.exception.code, "svg_text_invalid")

        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="10" y="20"><tspan>SrC-</tspan><tspan>008</tspan></text>'
            '</svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<g data-source-id="SRC-001">'
            '<text x="10" y="20">88%</text>'
            '</g>'
            '<text x="10" y="40">来源：2026 年年度报告</text>'
            '</svg>',
            encoding="utf-8",
        )
        plan = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        self.assertEqual(plan.nodes[0].style.data_source_id, "SRC-001")
        visible = "".join(
            run.text
            for node in plan.nodes
            for text_node in ((node.children if node.kind == "g" else (node,)))
            for line in text_node.text_lines
            for run in line.runs
        )
        self.assertNotIn("SRC-", visible)

    def test_inline_runs_preserve_text_spaces_and_style(self):
        plan = self._fixture_plan()
        first = plan.nodes[0]
        self.assertEqual(first.kind, "text")
        self.assertEqual(len(first.text_lines), 1)
        runs = first.text_lines[0].runs
        self.assertEqual([run.text for run in runs], ["广东电网 ", "27 套", " 系统收敛"])
        self.assertEqual(runs[1].style.fill, "#156BFF")
        self.assertEqual(runs[1].style.font_weight, "700")
        self.assertTrue(runs[0].preserve_space)
        self.assertTrue(runs[2].preserve_space)

    def test_x_and_dy_create_three_absolute_visual_lines(self):
        plan = self._fixture_plan()
        lines = plan.nodes[1].text_lines
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            [(line.x, line.y, "".join(run.text for run in line.runs)) for line in lines],
            [
                (64.0, 160.0, "第一行"),
                (64.0, 184.0, "第二行"),
                (64.0, 208.0, "第三行"),
            ],
        )
        self.assertEqual([line.line_index for line in lines], [1, 2, 3])

    def test_nested_tspan_inherits_and_overrides_style_recursively(self):
        plan = self._fixture_plan()
        runs = plan.nodes[2].text_lines[0].runs
        self.assertEqual([run.text for run in runs], ["A", "B", "C", "D", "E"])
        self.assertEqual(runs[1].style.fill, "#445566")
        self.assertEqual(runs[2].style.fill, "#445566")
        self.assertEqual(runs[2].style.font_weight, "700")
        self.assertEqual(runs[3].style.fill, "#445566")
        self.assertEqual(runs[4].style.fill, "#000000")

    def test_explicit_xml_space_keeps_meaningful_all_space_run(self):
        plan = self._fixture_plan()
        runs = plan.nodes[3].text_lines[0].runs
        self.assertEqual([run.text for run in runs], ["左", "   ", "右"])
        self.assertTrue(runs[1].preserve_space)

    def test_line_start_tspan_owns_anchor_and_inline_anchor_change_is_rejected(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="100" y="100" font-size="20" text-anchor="start">'
            '<tspan x="300" dy="20" text-anchor="end">right</tspan>'
            '</text></svg>',
            encoding="utf-8",
        )
        plan = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        line = plan.nodes[0].text_lines[0]
        self.assertEqual(line.anchor, "end")
        self.assertEqual(line.bounds.right, 300.0)

        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="100" y="100">left<tspan text-anchor="end">right</tspan></text>'
            '</svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_xml_space_accepts_only_default_or_preserve(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20" xml:space="invalid">bad</text>'
            '</svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_default_whitespace_collapses_once_across_run_boundaries(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20">A <tspan> B </tspan> C</text>'
            '</svg>',
            encoding="utf-8",
        )
        plan = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        runs = plan.nodes[0].text_lines[0].runs
        self.assertEqual([run.text for run in runs], ["A ", "B ", "C"])
        self.assertEqual("".join(run.text for run in runs), "A B C")

    def test_preserved_whitespace_converts_controls_to_spaces_for_one_line_box(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20">A<tspan xml:space="preserve"> \t B\n </tspan>C</text>'
            '</svg>',
            encoding="utf-8",
        )
        plan = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        value = "".join(run.text for run in plan.nodes[0].text_lines[0].runs)
        self.assertNotIn("\t", value)
        self.assertNotIn("\n", value)
        self.assertEqual(value, "A   B  C")

    def test_dy_only_line_keeps_the_current_explicit_x(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="10" y="20"><tspan x="100">A</tspan><tspan dy="20">B</tspan></text>'
            '</svg>',
            encoding="utf-8",
        )
        lines = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        ).nodes[0].text_lines
        self.assertEqual([(line.x, line.y) for line in lines], [(100.0, 20.0), (100.0, 40.0)])

    def test_tail_with_conflicting_anchor_is_rejected(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="10" y="20" text-anchor="start">'
            '<tspan x="100" text-anchor="end">A</tspan>B'
            '</text></svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_font_selection_honors_commas_inside_quoted_family(self):
        module = self._text()
        self.assertEqual(
            module.choose_primary_font('"ACME, Sans", Arial'),
            "ACME, Sans",
        )
        self.assertEqual(
            module.choose_primary_font("'Microsoft, YaHei', sans-serif"),
            "Microsoft, YaHei",
        )

    def test_letter_spacing_nonzero_underflow_is_rejected(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20" letter-spacing="1e-400">bad</text>'
            '</svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_attribute_unsupported")

    def test_default_all_space_events_and_unicode_spaces_are_meaningful(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        cases = (
            ("<tspan>A</tspan> <tspan>B</tspan>", "A B"),
            ("A<tspan> </tspan>B", "A B"),
            ("A<tspan> </tspan>B", "A B"),
            ("A<tspan>　</tspan>B", "A　B"),
        )
        for index, (content, expected) in enumerate(cases):
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>'
                '<text x="0" y="20">{}</text>'
                '</svg>'.format(content),
                encoding="utf-8",
            )
            plan = parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
            value = "".join(run.text for run in plan.nodes[0].text_lines[0].runs)
            with self.subTest(index=index):
                self.assertEqual(value, expected)

    def test_precision_collapsed_text_coordinates_and_boxes_fail_closed(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        cases = (
            '<text x="1e308" y="1e308">A<tspan dy="1">B</tspan></text>',
            '<text x="1e308" y="20">A</text>',
        )
        for content in cases:
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>{}</svg>'.format(content),
                encoding="utf-8",
            )
            with self.subTest(content=content):
                with self.assertRaises(EditableError) as raised:
                    parse_svg_slide(
                        SlideSource("S01", path, "slides/S01.svg", "production"),
                        SpeakerNotes(),
                    )
                self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_font_family_escape_and_unbalanced_quotes_fail_in_preflight(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        for family in (r"ACME\, Sans, Arial", "'unterminated, Arial"):
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>'
                '<text x="0" y="20" font-family="{}">bad</text>'
                '</svg>'.format(family),
                encoding="utf-8",
            )
            with self.subTest(family=family):
                with self.assertRaises(EditableError) as raised:
                    parse_svg_slide(
                        SlideSource("S01", path, "slides/S01.svg", "production"),
                        SpeakerNotes(),
                    )
                self.assertEqual(raised.exception.code, "svg_attribute_unsupported")

    def test_default_space_run_preserves_its_own_style_and_anchor(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="120" font-size="10">A'
            '<tspan font-size="100" fill="#FF0000"> </tspan>B'
            '</text></svg>',
            encoding="utf-8",
        )
        line = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        ).nodes[0].text_lines[0]
        self.assertEqual([run.text for run in line.runs], ["A", " ", "B"])
        self.assertEqual(line.runs[1].style.font_size, 100.0)
        self.assertEqual(line.runs[1].style.fill, "#FF0000")
        self.assertAlmostEqual(line.bounds.bottom - line.bounds.top, 150.0)

        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="120" text-anchor="start">A'
            '<tspan text-anchor="end"> </tspan>B'
            '</text></svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_finite_negative_letter_spacing_uses_minimum_width_clamp(self):
        module = self._text()
        style = ResolvedStyle(
            font_family="Arial",
            font_size=20.0,
            letter_spacing=-100.0,
        )
        try:
            bounds = module.compute_text_box(
                0.0,
                100.0,
                "start",
                (TextRun("AB", style),),
            )
        except ValueError as exc:
            self.fail(f"finite negative tracking must use the width clamp: {exc}")
        self.assertEqual(bounds.right - bounds.left, 30.0)

    def test_zero_font_size_is_not_silently_replaced_by_default(self):
        module = self._text()
        style = ResolvedStyle(
            font_family="Arial",
            font_size=0.0,
            letter_spacing=0.0,
        )
        with self.assertRaisesRegex(ValueError, "positive"):
            module.compute_text_box(
                0.0,
                100.0,
                "start",
                (TextRun("A", style),),
            )

    def test_aggregate_negative_or_nonfinite_letter_spacing_fails_closed(self):
        module = self._text()
        style = ResolvedStyle(
            font_family="Arial",
            font_size=20.0,
            letter_spacing=-1e308,
        )
        with self.assertRaises(ValueError):
            module.compute_text_box(
                0.0,
                100.0,
                "start",
                (TextRun("A", style), TextRun("B", style), TextRun("C", style)),
            )

    def test_mixed_quote_font_family_tokens_fail_preflight(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        for family in ("Arial'Foo', sans-serif", "'Arial'junk, sans-serif"):
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>'
                '<text x="0" y="20" font-family="{}">bad</text>'
                '</svg>'.format(family),
                encoding="utf-8",
            )
            with self.subTest(family=family):
                with self.assertRaises(EditableError) as raised:
                    parse_svg_slide(
                        SlideSource("S01", path, "slides/S01.svg", "production"),
                        SpeakerNotes(),
                    )
                self.assertEqual(raised.exception.code, "svg_attribute_unsupported")

    def test_font_selection_advance_and_anchor_bounds_are_deterministic(self):
        module = self._text()
        self.assertEqual(
            module.choose_primary_font("Arial, 'Microsoft YaHei', sans-serif"),
            "Arial",
        )
        self.assertAlmostEqual(
            module.estimate_text_advance_px("中Aaz ·", 20.0, 1.0),
            71.8,
            places=9,
        )
        style = ResolvedStyle(font_family="Arial", font_size=20.0, letter_spacing=0.0)
        runs = (TextRun("中文", style),)
        start = module.compute_text_box(100.0, 100.0, "start", runs)
        middle = module.compute_text_box(100.0, 100.0, "middle", runs)
        end = module.compute_text_box(100.0, 100.0, "end", runs)
        self.assertEqual(module.POWERPOINT_TEXT_BASELINE_OFFSET_PX, 2.0)
        self.assertAlmostEqual(start.top, 80.8, places=9)
        self.assertAlmostEqual(start.bottom, 110.8, places=9)
        self.assertEqual(start.left, 100.0)
        self.assertAlmostEqual(middle.left, 100.0 - (start.right - start.left) / 2.0)
        self.assertAlmostEqual(end.right, 100.0)
        spaced_style = ResolvedStyle(
            font_family="Arial",
            font_size=20.0,
            letter_spacing=1.0,
        )
        spaced = module.compute_text_box(
            0.0,
            100.0,
            "start",
            (TextRun("A", spaced_style), TextRun("B", spaced_style)),
        )
        self.assertAlmostEqual(spaced.right - spaced.left, 34.0, places=9)

    def test_text_node_bounds_are_union_of_emitted_line_boxes(self):
        plan = self._fixture_plan()
        multiline = plan.nodes[1]
        lines = multiline.text_lines
        expected = lines[0].bounds
        for line in lines[1:]:
            expected = expected.union(line.bounds)
        self.assertEqual(multiline.bounds, expected)
        self.assertNotEqual(multiline.bounds.left, multiline.bounds.right)
        self.assertNotEqual(multiline.bounds.top, multiline.bounds.bottom)

    def test_nonzero_text_coordinate_underflow_is_rejected(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="1e-400" y="20">bad</text>'
            '</svg>',
            encoding="utf-8",
        )
        with self.assertRaises(EditableError) as raised:
            parse_svg_slide(
                SlideSource("S01", path, "slides/S01.svg", "production"),
                SpeakerNotes(),
            )
        self.assertEqual(raised.exception.code, "svg_text_invalid")

    def test_unsupported_text_coordinate_lists_and_ambiguous_axes_fail_closed(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        cases = (
            ('<text x="0 10" y="20">bad</text>', "svg_text_invalid"),
            ('<text x="0" y="20 30">bad</text>', "svg_text_invalid"),
            ('<text x="0" y="20"><tspan x="10 20">bad</tspan></text>', "svg_text_invalid"),
            ('<text x="0" y="20"><tspan dy="10 20">bad</tspan></text>', "svg_text_invalid"),
            ('<text x="0" y="20"><tspan dx="1">bad</tspan></text>', "svg_attribute_unsupported"),
            ('<text x="0" y="20"><tspan y="40">bad</tspan></text>', "svg_attribute_unsupported"),
        )
        for content, expected in cases:
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
                '<title>x</title><desc>x</desc>{}</svg>'.format(content),
                encoding="utf-8",
            )
            with self.subTest(content=content):
                with self.assertRaises(EditableError) as raised:
                    parse_svg_slide(
                        SlideSource("S01", path, "slides/S01.svg", "production"),
                        SpeakerNotes(),
                    )
                self.assertEqual(raised.exception.code, expected)

    def test_nested_xml_space_preserve_inheritance_and_default_reset(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "S01.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
            '<title>x</title><desc>x</desc>'
            '<text x="0" y="20" xml:space="preserve">'
            '<tspan>B  C<tspan xml:space="default">D   E</tspan>F  G</tspan>'
            '</text></svg>',
            encoding="utf-8",
        )
        runs = parse_svg_slide(
            SlideSource("S01", path, "slides/S01.svg", "production"),
            SpeakerNotes(),
        ).nodes[0].text_lines[0].runs
        self.assertEqual([run.text for run in runs], ["B  C", "D E", "F  G"])
        self.assertEqual([run.preserve_space for run in runs], [True, False, True])


if __name__ == "__main__":
    unittest.main()
