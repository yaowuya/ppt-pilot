import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "ppt-start" / "scripts" / "svg_tool.py"
sys.path.insert(0, str(SCRIPT.parent))
import svg_tool  # noqa: E402


CANDIDATE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<title>Tool contract</title><desc>One sourced claim</desc>
<rect id="s01-background" x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
<g id="s01-claim" data-block-id="S01-B1"><text id="s01-title" x="64" y="112" font-family="Arial" font-size="40" data-role="title"><tspan x="64" y="112">Validated claim</tspan></text></g>
</svg>"""


def command(*args):
    return [sys.executable, "-B", str(SCRIPT), *args]


class SvgToolCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.candidate = self.root / "candidate.svg"
        self.candidate.write_text(CANDIDATE_SVG, encoding="utf-8")
        self.generator = self.root / "generator.txt"
        self.generator.write_text("```xml\n" + CANDIDATE_SVG + "\n```\n", encoding="utf-8")
        self.source_map = self.root / "source-map.json"
        self.source_map.write_text('{"S01-B1":["SRC-001"]}\n', encoding="utf-8")

    def invoke(self, *args):
        return subprocess.run(
            command(*args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def payload(self, result):
        self.assertEqual(result.stderr, "", result.stderr)
        lines = [line for line in result.stdout.splitlines() if line]
        self.assertEqual(len(lines), 1, result.stdout)
        return json.loads(lines[0])

    def test_extract_returns_structured_pass_and_writes_utf8_svg(self):
        output = self.root / "extracted.svg"
        result = self.invoke("extract", "--input", str(self.generator), "--output", str(output))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.payload(result), {"operation": "extract", "status": "PASS", "warnings": []})
        self.assertEqual(output.read_text(encoding="utf-8"), CANDIDATE_SVG + "\n")

    def test_finalize_joins_source_metadata_and_removes_transient_block_id(self):
        output = self.root / "final.svg"
        result = self.invoke(
            "finalize", "--input", str(self.candidate), "--output", str(output),
            "--source-map", str(self.source_map),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = self.payload(result)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["operation"], "finalize")
        self.assertEqual(payload["warnings"], [])
        final_svg = output.read_text(encoding="utf-8")
        self.assertNotIn("data-block-id", final_svg)
        self.assertIn('data-source-id="SRC-001"', final_svg)

    def test_source_less_content_blocks_use_empty_source_lists(self):
        source_map = self.root / "source-less-map.json"
        source_map.write_text('{"S01-B1":[]}\n', encoding="utf-8")
        output = self.root / "source-less-final.svg"

        result = self.invoke(
            "finalize", "--input", str(self.candidate), "--output", str(output),
            "--source-map", str(source_map),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.payload(result)["status"], "PASS")
        final_svg = output.read_text(encoding="utf-8")
        self.assertNotIn("data-block-id", final_svg)
        self.assertNotIn("data-source-id", final_svg)

    def test_duplicate_source_map_keys_are_invalid(self):
        self.source_map.write_text(
            '{"S01-B1":["SRC-001"],"S01-B1":["SRC-999"]}\n',
            encoding="utf-8",
        )

        result = self.invoke(
            "validate", "--kind", "candidate", "--input", str(self.candidate),
            "--source-map", str(self.source_map),
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = self.payload(result)
        self.assertEqual(payload["status"], "INVALID")
        self.assertEqual(payload["reason"], "source_map_invalid")

    def test_validate_distinguishes_generator_candidate_and_final_lifecycles(self):
        generator = self.invoke("validate", "--kind", "generator", "--input", str(self.generator))
        candidate = self.invoke(
            "validate", "--kind", "candidate", "--input", str(self.candidate),
            "--source-map", str(self.source_map),
        )
        final = self.root / "final.svg"
        finalize = self.invoke(
            "finalize", "--input", str(self.candidate), "--output", str(final),
            "--source-map", str(self.source_map),
        )
        final_result = self.invoke("validate", "--kind", "final", "--input", str(final))

        for result, operation in (
            (generator, "validate"), (candidate, "validate"), (finalize, "finalize"), (final_result, "validate"),
        ):
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.payload(result)["status"], "PASS")
            self.assertEqual(self.payload(result)["operation"], operation)

    def test_invalid_input_is_structured_invalid_and_preserves_existing_destination(self):
        output = self.root / "final.svg"
        output.write_bytes(b"prior final bytes")
        malformed = self.root / "malformed.svg"
        malformed.write_text("<svg>", encoding="utf-8")

        result = self.invoke(
            "finalize", "--input", str(malformed), "--output", str(output),
            "--source-map", str(self.source_map),
        )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = self.payload(result)
        self.assertEqual(payload["status"], "INVALID")
        self.assertEqual(payload["operation"], "finalize")
        self.assertTrue(payload["reason"])
        self.assertEqual(output.read_bytes(), b"prior final bytes")

    def test_unreadable_input_is_unavailable_and_never_uses_blocked_status(self):
        missing = self.root / "missing.svg"
        result = self.invoke("validate", "--kind", "candidate", "--input", str(missing),
                             "--source-map", str(self.source_map))

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        payload = self.payload(result)
        self.assertEqual(payload["status"], "UNAVAILABLE")
        self.assertEqual(payload["operation"], "validate")
        self.assertTrue(payload["reason"])
        self.assertNotIn("BLOCKED", result.stdout)

    def test_rejects_nonfinite_or_underfloor_title_threshold_as_invalid(self):
        for value in ("0", "33", "nan", "inf", "4097"):
            with self.subTest(value=value):
                result = self.invoke(
                    "validate", "--kind", "candidate", "--input", str(self.candidate),
                    "--source-map", str(self.source_map), "--title-min-size", value,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                payload = self.payload(result)
                self.assertEqual(payload["status"], "INVALID")
                self.assertEqual(payload["reason"], "title_min_size_invalid")

    def test_successful_operation_never_overwrites_an_existing_destination(self):
        output = self.root / "extracted.svg"
        output.write_bytes(b"prior final bytes")

        result = self.invoke("extract", "--input", str(self.generator), "--output", str(output))

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        payload = self.payload(result)
        self.assertEqual(payload["status"], "UNAVAILABLE")
        self.assertEqual(payload["reason"], "output_exists")
        self.assertEqual(output.read_bytes(), b"prior final bytes")

    def test_publication_never_replaces_a_destination_created_during_publish(self):
        output = self.root / "raced.svg"

        def concurrent_create(temporary, target):
            Path(target).write_bytes(b"concurrent evidence")
            raise FileExistsError(target)

        with mock.patch.object(svg_tool.os, "link", side_effect=concurrent_create):
            with self.assertRaises(svg_tool._ToolUnavailable) as raised:
                svg_tool._publish_bytes(output, b"new final bytes")
        self.assertEqual(raised.exception.reason, "output_exists")
        self.assertEqual(output.read_bytes(), b"concurrent evidence")

    def test_help_and_malformed_invocations_are_single_structured_results(self):
        for args, operation in (("--help", "help"), ("validate", "validate")):
            with self.subTest(args=args):
                result = self.invoke(*args.split())
                payload = self.payload(result)
                self.assertEqual(payload["operation"], operation)
                self.assertIn(payload["status"], {"PASS", "UNAVAILABLE"})
                self.assertIn(result.returncode, {0, 3})

    def test_kind_specific_invocation_errors_are_unavailable(self):
        invalid_invocations = (
            ("validate", "--kind", "candidate", "--input", str(self.candidate)),
            ("validate", "--kind", "generator", "--input", str(self.generator),
             "--source-map", str(self.source_map)),
            ("validate", "--kind", "final", "--input", str(self.candidate),
             "--source-map", str(self.source_map)),
        )
        for args in invalid_invocations:
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                payload = self.payload(result)
                self.assertEqual(payload["status"], "UNAVAILABLE")
                self.assertEqual(payload["reason"], "tool_invocation_invalid")

    def test_final_rejects_transient_blocks_and_visible_source_ids(self):
        with_block = self.root / "with-block.svg"
        with_block.write_text(CANDIDATE_SVG, encoding="utf-8")
        visible_source = self.root / "visible-source.svg"
        visible_source.write_text(
            CANDIDATE_SVG.replace("Validated claim", "SRC-001"),
            encoding="utf-8",
        )
        for path in (with_block, visible_source):
            with self.subTest(path=path.name):
                result = self.invoke("validate", "--kind", "final", "--input", str(path))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.payload(result)["status"], "INVALID")
    def test_final_rejects_source_ids_embedded_in_visible_words(self):
        final = self.root / "final.svg"
        finalized = self.invoke(
            "finalize", "--input", str(self.candidate), "--output", str(final),
            "--source-map", str(self.source_map),
        )
        self.assertEqual(finalized.returncode, 0, finalized.stdout + finalized.stderr)
        final_svg = final.read_text(encoding="utf-8")

        for index, visible_text in enumerate(
            ("xSRC-001y", "来源SRC-001编号", "S01-B1", "S01- B1")
        ):
            path = self.root / ("visible-source-{}.svg".format(index))
            path.write_text(
                final_svg.replace("Validated claim", visible_text),
                encoding="utf-8",
            )
            with self.subTest(visible_text=visible_text):
                result = self.invoke("validate", "--kind", "final", "--input", str(path))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.payload(result)["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
