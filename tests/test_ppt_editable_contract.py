import dataclasses
import hashlib
import importlib
import json
import math
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "ppt-editable"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
CONFIG_PATH = SKILL_ROOT / "assets" / "verification-config.json"
sys.path.insert(0, str(SCRIPTS_ROOT))

from _ppt_editable import (  # noqa: E402
    Bounds,
    DeckPlan,
    EditableError,
    EditableResult,
    Failure,
    ResolvedStyle,
    SlidePlan,
    SpeakerNotes,
    SvgNode,
    TextLine,
    TextRun,
    VerificationConfig,
    load_verification_config,
)
from _ppt_editable.errors import FAILURE_REASONS  # noqa: E402


EXPECTED_CONFIG = {
    "schema_version": 1,
    "render_width": 1280,
    "render_height": 720,
    "full_page_grayscale_mad_max": 4.0,
    "geometry_only_grayscale_mad_max": 1.5,
    "geometry_tile_size": 64,
    "geometry_tile_mad_max": 8.0,
    "bounds_tolerance_px": 1.0,
}

EXPECTED_CONFIG_BYTES = (
    b'{\n'
    b'  "bounds_tolerance_px": 1.0,\n'
    b'  "full_page_grayscale_mad_max": 4.0,\n'
    b'  "geometry_only_grayscale_mad_max": 1.5,\n'
    b'  "geometry_tile_mad_max": 8.0,\n'
    b'  "geometry_tile_size": 64,\n'
    b'  "render_height": 720,\n'
    b'  "render_width": 1280,\n'
    b'  "schema_version": 1\n'
    b'}\n'
)

EXPECTED_FAILURE_REASONS = frozenset(
    {
        "run_not_found",
        "run_ambiguous",
        "run_not_complete",
        "deck_id_invalid",
        "quality_report_missing",
        "storyboard_missing",
        "storyboard_ambiguous",
        "slide_set_invalid",
        "source_path_unsafe",
        "source_unreadable",
        "python_version_unsupported",
        "core_dependency_missing",
        "svg_xml_invalid",
        "svg_canvas_invalid",
        "svg_element_unsupported",
        "svg_attribute_unsupported",
        "svg_external_reference",
        "svg_path_invalid",
        "svg_arc_rotation_unsupported",
        "svg_group_empty",
        "svg_coordinate_invalid",
        "svg_text_invalid",
        "candidate_write_failed",
        "candidate_hash_mismatch",
        "pptx_zip_invalid",
        "pptx_reopen_failed",
        "structure_mismatch",
        "content_mismatch",
        "group_mismatch",
        "notes_mismatch",
        "bounds_violation",
        "image_fallback_detected",
        "powerpoint_normalize_failed",
        "powerpoint_reopen_failed",
        "powerpoint_render_failed",
        "visual_mismatch",
        "promotion_conflict",
    }
)


class FoundationTests(unittest.TestCase):
    def _write_config(self, payload):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "verification.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_config_has_exact_schema(self):
        self.assertEqual(load_verification_config(CONFIG_PATH).__dict__, EXPECTED_CONFIG)

    def test_config_file_has_canonical_exact_bytes(self):
        self.assertEqual(CONFIG_PATH.read_bytes(), EXPECTED_CONFIG_BYTES)

    def test_repository_pins_verification_config_to_lf(self):
        attributes_path = REPO_ROOT / ".gitattributes"
        self.assertIn(
            "/skills/ppt-editable/assets/verification-config.json text eol=lf",
            attributes_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_failure_reason_set_is_exactly_closed(self):
        self.assertEqual(FAILURE_REASONS, EXPECTED_FAILURE_REASONS)

    def test_unknown_reason_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown failure reason"):
            Failure(
                code="invented",
                slide_id=None,
                svg_tree_path=None,
                element_type=None,
                message="x",
                remediation="y",
            )

    def test_editable_error_cannot_bypass_reason_validation(self):
        with self.assertRaisesRegex(ValueError, "unknown failure reason"):
            EditableError("invented", "x")

    def test_failure_is_immutable(self):
        failure = Failure(
            code="svg_path_invalid",
            slide_id="S01",
            svg_tree_path="/svg[1]/path[1]",
            element_type="path",
            message="bad path",
            remediation="fix the path",
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            failure.code = "content_mismatch"

    def test_all_foundation_models_are_frozen_dataclasses(self):
        model_types = (
            Failure,
            Bounds,
            ResolvedStyle,
            TextRun,
            TextLine,
            SvgNode,
            SpeakerNotes,
            SlidePlan,
            DeckPlan,
            EditableResult,
            VerificationConfig,
        )
        for model_type in model_types:
            with self.subTest(model=model_type.__name__):
                self.assertTrue(dataclasses.is_dataclass(model_type))
                self.assertTrue(model_type.__dataclass_params__.frozen)

    def test_bounds_union_and_expansion_return_new_values(self):
        first = Bounds(10.0, 20.0, 30.0, 40.0)
        second = Bounds(5.0, 25.0, 35.0, 38.0)
        self.assertEqual(first.union(second), Bounds(5.0, 20.0, 35.0, 40.0))
        self.assertEqual(first.expanded(2.5), Bounds(7.5, 17.5, 32.5, 42.5))
        self.assertEqual(first, Bounds(10.0, 20.0, 30.0, 40.0))

    def test_config_rejects_missing_and_extra_keys(self):
        missing = dict(EXPECTED_CONFIG)
        del missing["render_width"]
        extra = dict(EXPECTED_CONFIG, surprise=1)
        for payload in (missing, extra):
            with self.subTest(keys=sorted(payload)):
                with self.assertRaisesRegex(ValueError, "configuration keys"):
                    load_verification_config(self._write_config(payload))

    def test_config_rejects_boolean_numeric_values(self):
        for key in EXPECTED_CONFIG:
            payload = dict(EXPECTED_CONFIG)
            payload[key] = True
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, key):
                    load_verification_config(self._write_config(payload))

    def test_config_accepts_positive_dimensions_from_selected_asset(self):
        payload = dict(EXPECTED_CONFIG, render_width=640, render_height=360)
        try:
            config = load_verification_config(self._write_config(payload))
        except ValueError as exc:
            self.fail(f"positive asset dimensions must be accepted: {exc}")
        self.assertEqual((config.render_width, config.render_height), (640, 360))

    def test_config_rejects_invalid_integer_fields(self):
        invalid_values = {
            "render_width": (0, -1, 1280.0, "1280"),
            "render_height": (0, -1, 720.0, "720"),
            "geometry_tile_size": (0, -1, 64.0, "64"),
        }
        for key, values in invalid_values.items():
            for value in values:
                payload = dict(EXPECTED_CONFIG)
                payload[key] = value
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, key):
                        load_verification_config(self._write_config(payload))

    def test_config_rejects_negative_nonfinite_and_nonnumeric_thresholds(self):
        threshold_keys = (
            "full_page_grayscale_mad_max",
            "geometry_only_grayscale_mad_max",
            "geometry_tile_mad_max",
            "bounds_tolerance_px",
        )
        for key in threshold_keys:
            for value in (-0.01, math.inf, math.nan, "1.0"):
                payload = dict(EXPECTED_CONFIG)
                payload[key] = value
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, key):
                        load_verification_config(self._write_config(payload))

    def test_config_rejects_schema_other_than_integer_one(self):
        for value in (0, 2, 1.0, "1"):
            payload = dict(EXPECTED_CONFIG)
            payload["schema_version"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "schema_version"):
                    load_verification_config(self._write_config(payload))

    def test_config_rejects_duplicate_keys_and_nonfinite_json_constants(self):
        cases = (
            '{"schema_version":1,"schema_version":1}',
            '{"schema_version":NaN}',
            '{"schema_version":Infinity}',
        )
        for content in cases:
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            path = Path(directory.name) / "verification.json"
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content):
                with self.assertRaises(ValueError):
                    load_verification_config(path)


class RunContractTests(unittest.TestCase):
    def _contract(self):
        return importlib.import_module("_ppt_editable.contract")

    def _write_run(self, root, *, stage="complete", deck_id="example-deck"):
        root = Path(root)
        control = root / ".ppt-pilot"
        (root / "slides").mkdir(parents=True, exist_ok=True)
        (root / "samples").mkdir(parents=True, exist_ok=True)
        control.mkdir(parents=True, exist_ok=True)
        run = {
            "schema_version": 1,
            "deck_id": deck_id,
            "stage": stage,
            "anchor_generation": {
                "anchors": ["S01"],
                "records": [
                    {"slide_id": "S01", "output": "samples/S01.svg"}
                ],
            },
        }
        (control / "run.json").write_text(
            json.dumps(run, ensure_ascii=False), encoding="utf-8"
        )
        (control / "故事板.md").write_text(
            "# 故事板\n\n"
            "## S01（cover）\n"
            "- **assertion_title**: 封面结论\n"
            "- **audience_takeaway**: 理解主题\n"
            "- **next_link**: S02\n\n"
            "## S02 section/context\n"
            "- **assertion_title**: 第二页结论\n"
            "- **audience_takeaway**: 理解证据\n"
            "- **next_link**: END\n",
            encoding="utf-8",
        )
        (control / "质量检查报告.md").write_text("# PASS\n", encoding="utf-8")
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"></svg>\n'
        (root / "samples" / "S01.svg").write_text(svg, encoding="utf-8")
        (root / "slides" / "S02.svg").write_text(svg, encoding="utf-8")
        return root

    def _temp_root(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def _assert_reason(self, expected, callback):
        with self.assertRaises(EditableError) as raised:
            callback()
        self.assertEqual(raised.exception.code, expected)

    def test_locate_run_prefers_explicit_then_current_then_unique_completed(self):
        contract = self._contract()
        temp = self._temp_root()
        explicit = self._write_run(temp / "explicit")
        current = self._write_run(temp / "current")
        output_root = temp / "ppt-output"
        unique = self._write_run(output_root / "unique")
        self.assertEqual(
            contract.locate_run(explicit, temp, output_root), explicit.resolve()
        )
        self.assertEqual(
            contract.locate_run(None, current, output_root), current.resolve()
        )
        self.assertEqual(
            contract.locate_run(None, temp, output_root), unique.resolve()
        )

    def test_locate_run_rejects_explicit_reparse_before_resolving(self):
        contract = self._contract()
        temp = self._temp_root()
        explicit = self._write_run(temp / "explicit-reparse")
        real_lstat = contract.os.lstat

        def explicit_reparse(path):
            value = real_lstat(path)
            if Path(path) == explicit:
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(contract.os, "lstat", side_effect=explicit_reparse):
            self._assert_reason(
                "source_path_unsafe",
                lambda: contract.locate_run(explicit, temp, None),
            )

    def test_locate_run_skips_invalid_current_and_uses_unique_completed_run(self):
        contract = self._contract()
        temp = self._temp_root()
        current = self._write_run(temp / "current", stage="production")
        output_root = temp / "ppt-output"
        unique = self._write_run(output_root / "unique")
        self.assertEqual(
            contract.locate_run(None, current, output_root), unique.resolve()
        )
        data = json.loads(
            (current / ".ppt-pilot" / "run.json").read_text(encoding="utf-8")
        )
        data["stage"] = "complete"
        (current / ".ppt-pilot" / "run.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        (current / ".ppt-pilot" / "质量检查报告.md").unlink()
        self.assertEqual(
            contract.locate_run(None, current, output_root), unique.resolve()
        )

    def test_locate_run_rejects_missing_and_ambiguous_candidates(self):
        contract = self._contract()
        temp = self._temp_root()
        output_root = temp / "ppt-output"
        output_root.mkdir()
        self._assert_reason(
            "run_not_found",
            lambda: contract.locate_run(None, temp, output_root),
        )
        self._write_run(output_root / "one")
        self._write_run(output_root / "two")
        self._assert_reason(
            "run_ambiguous",
            lambda: contract.locate_run(None, temp, output_root),
        )

    def test_validate_completed_run_enforces_stage_deck_id_and_owners(self):
        contract = self._contract()
        temp = self._temp_root()
        valid = self._write_run(temp / "valid")
        context = contract.validate_completed_run(valid)
        self.assertEqual(context.deck_id, "example-deck")
        self.assertEqual(context.storyboard_path.name, "故事板.md")
        self.assertEqual(context.quality_report_path.name, "质量检查报告.md")

        draft = self._write_run(temp / "draft", stage="production")
        self._assert_reason(
            "run_not_complete", lambda: contract.validate_completed_run(draft)
        )
        unicode_run = self._write_run(temp / "unicode", deck_id="季度总结-2026")
        self.assertEqual(
            contract.validate_completed_run(unicode_run).deck_id,
            "季度总结-2026",
        )
        unsafe_ids = (
            "",
            ".",
            "..",
            "../x",
            "x/y",
            "x\\y",
            "C:x",
            "CON",
            "con.txt",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "LPT9",
            "trailing.",
            "trailing ",
            "bad<name",
            "bad|name",
        )
        for index, deck_id in enumerate(unsafe_ids):
            unsafe = self._write_run(temp / ("unsafe-{}".format(index)), deck_id=deck_id)
            self._assert_reason(
                "deck_id_invalid", lambda path=unsafe: contract.validate_completed_run(path)
            )

        missing_quality = self._write_run(temp / "missing-quality")
        (missing_quality / ".ppt-pilot" / "质量检查报告.md").unlink()
        self._assert_reason(
            "quality_report_missing",
            lambda: contract.validate_completed_run(missing_quality),
        )
        ambiguous_story = self._write_run(temp / "ambiguous-story")
        (ambiguous_story / ".ppt-pilot" / "storyboard.md").write_text(
            "# legacy\n", encoding="utf-8"
        )
        self._assert_reason(
            "storyboard_ambiguous",
            lambda: contract.validate_completed_run(ambiguous_story),
        )

    def test_parse_storyboard_returns_ordered_notes_and_rejects_bad_ids(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        slides = contract.parse_storyboard(run / ".ppt-pilot" / "故事板.md")
        self.assertEqual([slide.slide_id for slide in slides], ["S01", "S02"])
        self.assertEqual(slides[0].assertion_title, "封面结论")
        self.assertEqual(slides[0].audience_takeaway, "理解主题")
        self.assertEqual(slides[1].next_link, "END")

        for name, body in (
            ("duplicate.md", "## S01\n## S01\n"),
            ("unordered.md", "## S02\n## S01\n"),
            ("malformed.md", "## page-one\n"),
        ):
            path = temp / name
            path.write_text(body, encoding="utf-8")
            self._assert_reason(
                "slide_set_invalid", lambda target=path: contract.parse_storyboard(target)
            )

    def test_parse_storyboard_rejects_malformed_h2_between_valid_slides(self):
        contract = self._contract()
        temp = self._temp_root()
        path = temp / "mixed.md"
        path.write_text(
            "## S01 封面\n"
            "assertion_title: 第一页\n\n"
            "## Sx malformed slide\n"
            "assertion_title: 不得吸收到 S01\n\n"
            "## S02 section\n"
            "assertion_title: 第二页\n",
            encoding="utf-8",
        )
        self._assert_reason(
            "slide_set_invalid", lambda: contract.parse_storyboard(path)
        )

    def test_parse_storyboard_accepts_plain_bold_and_backtick_field_keys(self):
        contract = self._contract()
        temp = self._temp_root()
        path = temp / "storyboard.md"
        path.write_text(
            "## S01 封面\n"
            "assertion_title: 普通键\n"
            "- `audience_takeaway`: 代码键\n"
            "- **next_link**: S02\n\n"
            "## S02 section/context\n"
            "- **assertion_title**：粗体键\n"
            "next_link: END\n",
            encoding="utf-8",
        )
        slides = contract.parse_storyboard(path)
        self.assertEqual(slides[0].assertion_title, "普通键")
        self.assertEqual(slides[0].audience_takeaway, "代码键")
        self.assertEqual(slides[0].next_link, "S02")
        self.assertEqual(slides[1].assertion_title, "粗体键")
        self.assertEqual(slides[1].next_link, "END")

    def test_resolve_sources_prefers_production_and_requires_approved_sample(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        sources = contract.resolve_slide_sources(context, storyboard)
        self.assertEqual(
            [(item.slide_id, item.relative_path, item.owner) for item in sources],
            [
                ("S01", "samples/S01.svg", "approved_anchor"),
                ("S02", "slides/S02.svg", "production"),
            ],
        )

        shutil.copy2(run / "samples" / "S01.svg", run / "slides" / "S01.svg")
        sources = contract.resolve_slide_sources(context, storyboard)
        self.assertEqual(sources[0].relative_path, "slides/S01.svg")
        self.assertEqual(sources[0].owner, "production")

    def test_resolve_sources_rejects_unapproved_missing_and_extra_pages(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)

        data = json.loads((run / ".ppt-pilot" / "run.json").read_text(encoding="utf-8"))
        data["anchor_generation"] = {"anchors": [], "records": []}
        (run / ".ppt-pilot" / "run.json").write_text(json.dumps(data), encoding="utf-8")
        unapproved = contract.validate_completed_run(run)
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(unapproved, storyboard),
        )

        data["anchor_generation"] = {
            "anchors": ["S01"],
            "records": [{"slide_id": "S01", "output": "samples/S01.svg"}],
        }
        (run / ".ppt-pilot" / "run.json").write_text(json.dumps(data), encoding="utf-8")
        restored = contract.validate_completed_run(run)
        (run / "slides" / "S02.svg").unlink()
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(restored, storyboard),
        )
        self._write_run(temp / "extra")
        extra = temp / "extra"
        (extra / "slides" / "S03.svg").write_text(
            (extra / "slides" / "S02.svg").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        extra_context = contract.validate_completed_run(extra)
        extra_storyboard = contract.parse_storyboard(extra_context.storyboard_path)
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(extra_context, extra_storyboard),
        )

    def test_resolve_sources_ignores_internal_candidate_directory_without_descent(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "candidate-cache")
        candidates = run / "slides" / ".candidates"
        candidates.mkdir()
        shutil.copy2(run / "slides" / "S02.svg", candidates / "S99.svg")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        sources = contract.resolve_slide_sources(context, storyboard)
        self.assertEqual([source.slide_id for source in sources], ["S01", "S02"])

    def test_sample_candidate_directory_is_not_an_allowed_cache(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "sample-candidate")
        candidates = run / "samples" / ".candidates"
        candidates.mkdir()
        shutil.copy2(run / "samples" / "S01.svg", candidates / "S99.svg")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(context, storyboard),
        )

    def test_resolve_sources_rejects_nested_and_malformed_svg_files(self):
        contract = self._contract()
        temp = self._temp_root()
        nested_run = self._write_run(temp / "nested")
        nested = nested_run / "slides" / "nested"
        nested.mkdir()
        shutil.copy2(nested_run / "slides" / "S02.svg", nested / "S03.svg")
        context = contract.validate_completed_run(nested_run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(context, storyboard),
        )

        malformed_run = self._write_run(temp / "malformed")
        shutil.copy2(
            malformed_run / "slides" / "S02.svg",
            malformed_run / "slides" / "Sbad.svg",
        )
        malformed_context = contract.validate_completed_run(malformed_run)
        malformed_storyboard = contract.parse_storyboard(
            malformed_context.storyboard_path
        )
        self._assert_reason(
            "slide_set_invalid",
            lambda: contract.resolve_slide_sources(
                malformed_context, malformed_storyboard
            ),
        )

    def test_anchor_ownership_rejects_unhashable_slide_id_as_typed_failure(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "unhashable-anchor")
        run_path = run / ".ppt-pilot" / "run.json"
        data = json.loads(run_path.read_text(encoding="utf-8"))
        data["anchor_generation"]["records"][0]["slide_id"] = {"nested": "S01"}
        run_path.write_text(json.dumps(data), encoding="utf-8")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        try:
            self._assert_reason(
                "slide_set_invalid",
                lambda: contract.resolve_slide_sources(context, storyboard),
            )
        except TypeError as exc:
            self.fail(f"malformed anchor leaked raw TypeError: {exc}")

    def test_anchor_ownership_requires_both_id_and_exact_output(self):
        contract = self._contract()
        temp = self._temp_root()
        for index, anchor_generation in enumerate(
            (
                {
                    "anchors": ["S01"],
                    "records": [{"slide_id": "S01", "output": "samples/wrong.svg"}],
                },
                {
                    "anchors": [],
                    "records": [{"slide_id": "S01", "output": "samples/S01.svg"}],
                },
                {"anchors": ["S01"], "records": []},
            )
        ):
            run = self._write_run(temp / "anchor-{}".format(index))
            path = run / ".ppt-pilot" / "run.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["anchor_generation"] = anchor_generation
            path.write_text(json.dumps(data), encoding="utf-8")
            context = contract.validate_completed_run(run)
            storyboard = contract.parse_storyboard(context.storyboard_path)
            self._assert_reason(
                "slide_set_invalid",
                lambda c=context, s=storyboard: contract.resolve_slide_sources(c, s),
            )

    def test_storyboard_missing_and_empty_are_stable_failures(self):
        contract = self._contract()
        temp = self._temp_root()
        missing = self._write_run(temp / "missing")
        (missing / ".ppt-pilot" / "故事板.md").unlink()
        self._assert_reason(
            "storyboard_missing", lambda: contract.validate_completed_run(missing)
        )
        empty = temp / "empty.md"
        empty.write_text("# no slides\n", encoding="utf-8")
        self._assert_reason(
            "slide_set_invalid", lambda: contract.parse_storyboard(empty)
        )

    def test_safe_file_rejects_escape_mocked_reparse_and_special_leaf(self):
        contract = self._contract()
        temp = self._temp_root()
        allowed = temp / "allowed"
        allowed.mkdir()
        inside = allowed / "inside.svg"
        inside.write_text("x", encoding="utf-8")
        outside = temp / "outside.svg"
        outside.write_text("x", encoding="utf-8")
        self._assert_reason(
            "source_path_unsafe",
            lambda: contract.validate_safe_regular_file(outside, (allowed,)),
        )

        real_lstat = contract.os.lstat

        def reparse_lstat(path):
            value = real_lstat(path)
            if Path(path) == inside:
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(contract.os, "lstat", side_effect=reparse_lstat):
            self._assert_reason(
                "source_path_unsafe",
                lambda: contract.validate_safe_regular_file(inside, (allowed,)),
            )

        def special_stat(path):
            value = real_lstat(path)
            if Path(path) == inside:
                return SimpleNamespace(st_mode=stat.S_IFIFO, st_file_attributes=0)
            return value

        with mock.patch.object(contract.os, "stat", side_effect=special_stat):
            self._assert_reason(
                "source_path_unsafe",
                lambda: contract.validate_safe_regular_file(inside, (allowed,)),
            )

    def test_run_json_rejects_duplicate_keys_nonfinite_and_unsupported_schema(self):
        contract = self._contract()
        temp = self._temp_root()
        cases = (
            '{"schema_version":1,"schema_version":2,"deck_id":"x","stage":"complete"}',
            '{"deck_id":"x","stage":"complete"}',
            '{"schema_version":2,"deck_id":"x","stage":"complete"}',
            '{"schema_version":NaN,"deck_id":"x","stage":"complete"}',
        )
        for index, content in enumerate(cases):
            run = self._write_run(temp / "run-json-{}".format(index))
            (run / ".ppt-pilot" / "run.json").write_text(content, encoding="utf-8")
            self._assert_reason(
                "source_unreadable",
                lambda path=run: contract.validate_completed_run(path),
            )

    def test_validated_run_data_is_deeply_immutable(self):
        contract = self._contract()
        temp = self._temp_root()
        context = contract.validate_completed_run(self._write_run(temp / "valid"))
        with self.assertRaises(TypeError):
            context.run_data["stage"] = "production"
        with self.assertRaises(TypeError):
            context.run_data["anchor_generation"]["records"] = ()
        with self.assertRaises(TypeError):
            context.run_data["anchor_generation"]["anchors"][0] = "S99"

    def test_source_root_reparse_is_rejected_before_enumeration(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        real_lstat = contract.os.lstat

        def root_reparse(path):
            value = real_lstat(path)
            if Path(path) == context.slides_dir:
                return SimpleNamespace(
                    st_mode=value.st_mode,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(contract.os, "lstat", side_effect=root_reparse):
            with mock.patch.object(
                contract.Path,
                "rglob",
                side_effect=AssertionError("source root traversed before lstat"),
            ):
                self._assert_reason(
                    "source_path_unsafe",
                    lambda: contract.resolve_slide_sources(context, storyboard),
                )

    def test_nested_reparse_entry_is_rejected_without_descent(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)

        class ReparseEntry:
            name = "junction"
            path = str(context.slides_dir / "junction")

            def is_symlink(self):
                return False

            def stat(self, follow_symlinks=True):
                self.follow_symlinks = follow_symlinks
                return SimpleNamespace(
                    st_mode=stat.S_IFDIR,
                    st_file_attributes=0x400,
                )

        class Scan:
            def __enter__(self):
                return iter((ReparseEntry(),))

            def __exit__(self, exc_type, exc, traceback):
                return False

        real_scandir = contract.os.scandir
        calls = []

        def controlled_scandir(path):
            calls.append(Path(path))
            if Path(path) == context.slides_dir:
                return Scan()
            return real_scandir(path)

        with mock.patch.object(contract.os, "scandir", side_effect=controlled_scandir):
            self._assert_reason(
                "source_path_unsafe",
                lambda: contract.resolve_slide_sources(context, storyboard),
            )
        self.assertEqual(calls, [context.slides_dir])

    def test_safe_file_rejects_directory_symlink_and_reparse(self):
        contract = self._contract()
        temp = self._temp_root()
        run = self._write_run(temp / "valid")
        target = run / "slides" / "S02.svg"
        target.unlink()
        target.mkdir()
        self._assert_reason(
            "source_path_unsafe",
            lambda: contract.validate_safe_regular_file(target, (run / "slides",)),
        )

        outside = temp / "outside.svg"
        outside.write_text("x", encoding="utf-8")
        link = run / "slides" / "link.svg"
        try:
            link.symlink_to(outside)
        except OSError:
            pass
        else:
            self._assert_reason(
                "source_path_unsafe",
                lambda: contract.validate_safe_regular_file(link, (run / "slides",)),
            )
        self.assertTrue(
            contract._is_reparse_stat(SimpleNamespace(st_file_attributes=0x400))
        )
        self.assertFalse(contract._is_reparse_stat(SimpleNamespace()))

    def test_contract_fixture_case_ids_are_stable(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "contract-cases.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            [case["id"] for case in payload["cases"]],
            [
                "production-wins",
                "approved-anchor-fallback",
                "unapproved-sample",
                "missing-page",
                "extra-page",
                "ambiguous-run",
                "unsafe-source",
            ],
        )


class SnapshotTests(unittest.TestCase):
    def _modules(self):
        return (
            importlib.import_module("_ppt_editable.contract"),
            importlib.import_module("_ppt_editable.snapshot"),
        )

    def _prepared(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        run = Path(directory.name) / "run"
        shutil.copytree(
            REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "run-complete",
            run,
        )
        contract, snapshot = self._modules()
        context = contract.validate_completed_run(run)
        storyboard = contract.parse_storyboard(context.storyboard_path)
        sources = contract.resolve_slide_sources(context, storyboard)
        return run, context, storyboard, sources, snapshot

    def _payload(self, context, storyboard, sources, snapshot, **overrides):
        arguments = {
            "context": context,
            "sources": sources,
            "storyboard": storyboard,
            "converter_version": "1.0.0",
            "subset_contract_version": "1",
            "verification_config_bytes": CONFIG_PATH.read_bytes(),
        }
        arguments.update(overrides)
        return snapshot.canonical_snapshot_payload(**arguments)

    def test_sha256_file_hashes_actual_svg_bytes(self):
        run, _, _, sources, snapshot = self._prepared()
        expected = "sha256:" + hashlib.sha256(
            (run / "samples" / "S01.svg").read_bytes()
        ).hexdigest()
        self.assertEqual(snapshot.sha256_file(sources[0].path), expected)

    def test_snapshot_payload_is_exact_canonical_utf8_json(self):
        _, context, storyboard, sources, snapshot = self._prepared()
        payload = self._payload(context, storyboard, sources, snapshot)
        value = json.loads(payload)
        self.assertEqual(
            set(value),
            {
                "schema_version",
                "kind",
                "deck_id",
                "run_schema_version",
                "run_stage",
                "storyboard_path",
                "converter_version",
                "subset_contract_version",
                "verification_config_sha256",
                "slides",
            },
        )
        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(value["kind"], "ppt_editable_input_snapshot")
        self.assertEqual(value["storyboard_path"], ".ppt-pilot/故事板.md")
        self.assertEqual(
            [(item["slide_id"], item["path"], item["owner"]) for item in value["slides"]],
            [
                ("S01", "samples/S01.svg", "approved_anchor"),
                ("S02", "slides/S02.svg", "production"),
            ],
        )
        self.assertEqual(
            value["slides"][0]["notes"],
            {
                "assertion_title": "封面结论",
                "audience_takeaway": "理解主题",
                "next_link": "S02",
            },
        )
        self.assertEqual(
            payload,
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        self.assertFalse(payload.endswith(b"\n"))

    def test_snapshot_id_is_sha256_of_payload_and_repeatable(self):
        _, context, storyboard, sources, snapshot = self._prepared()
        first = self._payload(context, storyboard, sources, snapshot)
        second = self._payload(context, storyboard, sources, snapshot)
        expected = "sha256:" + hashlib.sha256(first).hexdigest()
        self.assertEqual(first, second)
        self.assertEqual(snapshot.compute_snapshot_id(first), expected)

    def test_every_authoritative_snapshot_input_invalidates_identity(self):
        run, context, storyboard, sources, snapshot = self._prepared()
        baseline = self._payload(context, storyboard, sources, snapshot)
        baseline_id = snapshot.compute_snapshot_id(baseline)

        changed_svg = run / "samples" / "S01.svg"
        original_svg = changed_svg.read_bytes()
        changed_svg.write_bytes(original_svg + b"<!-- changed -->\n")
        contract = importlib.import_module("_ppt_editable.contract")
        changed_sources = contract.resolve_slide_sources(context, storyboard)
        svg_payload = self._payload(
            context,
            storyboard,
            changed_sources,
            snapshot,
        )
        changed_svg.write_bytes(original_svg)

        changed_storyboard = (
            dataclasses.replace(storyboard[0], assertion_title="新结论"),
            storyboard[1],
        )
        mutations = (
            svg_payload,
            self._payload(context, changed_storyboard, sources, snapshot),
            self._payload(
                context,
                storyboard,
                sources,
                snapshot,
                converter_version="1.0.1",
            ),
            self._payload(
                context,
                storyboard,
                sources,
                snapshot,
                subset_contract_version="2",
            ),
            self._payload(
                context,
                storyboard,
                sources,
                snapshot,
                verification_config_bytes=CONFIG_PATH.read_bytes() + b" ",
            ),
        )
        shutil.copy2(run / "samples" / "S01.svg", run / "slides" / "S01.svg")
        contract = importlib.import_module("_ppt_editable.contract")
        production_sources = contract.resolve_slide_sources(context, storyboard)
        mutations += (
            self._payload(context, storyboard, production_sources, snapshot),
        )
        for index, payload in enumerate(mutations):
            with self.subTest(index=index):
                self.assertNotEqual(snapshot.compute_snapshot_id(payload), baseline_id)

    def test_snapshot_rejects_noncanonical_relative_path_aliases(self):
        _, context, storyboard, sources, snapshot = self._prepared()
        aliases = (
            dataclasses.replace(
                sources[1],
                relative_path=str(sources[1].path),
            ),
            dataclasses.replace(
                sources[1],
                relative_path="slides/sub/../S02.svg",
            ),
        )
        for alias in aliases:
            mutated = (sources[0], alias)
            with self.subTest(relative_path=alias.relative_path):
                with self.assertRaises(EditableError) as raised:
                    self._payload(context, storyboard, mutated, snapshot)
                self.assertEqual(raised.exception.code, "source_path_unsafe")

    def test_snapshot_revalidates_every_source_immediately_before_hashing(self):
        _, context, storyboard, sources, snapshot = self._prepared()
        contract = importlib.import_module("_ppt_editable.contract")
        with mock.patch.object(
            snapshot,
            "validate_safe_regular_file",
            wraps=contract.validate_safe_regular_file,
        ) as validator:
            self._payload(context, storyboard, sources, snapshot)
        self.assertEqual(validator.call_count, len(sources))

    def test_snapshot_rejects_source_swapped_to_symlink_after_resolution(self):
        run, context, storyboard, sources, snapshot = self._prepared()
        target = run / "slides" / "S02.svg"
        outside = run.parent / "outside.svg"
        outside.write_text("outside", encoding="utf-8")
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(EditableError) as raised:
            self._payload(context, storyboard, sources, snapshot)
        self.assertEqual(raised.exception.code, "source_path_unsafe")

    def test_unrelated_files_do_not_change_snapshot(self):
        run, context, storyboard, sources, snapshot = self._prepared()
        baseline = self._payload(context, storyboard, sources, snapshot)
        (run / "unrelated.txt").write_text("noise", encoding="utf-8")
        self.assertEqual(
            self._payload(context, storyboard, sources, snapshot), baseline
        )


if __name__ == "__main__":
    unittest.main()
