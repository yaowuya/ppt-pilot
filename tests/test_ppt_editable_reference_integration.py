import json
import os
from pathlib import Path
import re
import sys
import unittest
import zipfile

from defusedxml import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "ppt-editable" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from _ppt_editable.config import load_verification_config  # noqa: E402
from _ppt_editable.contract import (  # noqa: E402
    parse_storyboard,
    resolve_slide_sources,
    validate_completed_run,
)
from _ppt_editable.office_protocol import powerpoint_available  # noqa: E402
from _ppt_editable.orchestrator import (  # noqa: E402
    GenerationCapability,
    generate_editable,
)
from _ppt_editable.structural_verify import verify_candidate  # noqa: E402
from _ppt_editable.svg_parser import preflight_deck  # noqa: E402


REFERENCE_RUN = os.environ.get("PPT_EDITABLE_REFERENCE_RUN")
CONFIG_PATH = REPO_ROOT / "skills" / "ppt-editable" / "assets" / "verification-config.json"
VISIBLE_SOURCE_ID = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _visible_svg_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    return " ".join(
        "".join(node.itertext())
        for node in root.iter()
        if isinstance(node.tag, str) and node.tag.rsplit("}", 1)[-1] == "text"
    )


def _plan_counts(nodes):
    leaves = groups = 0
    for node in nodes:
        if node.kind == "g":
            groups += 1
            child_leaves, child_groups = _plan_counts(node.children)
            leaves += child_leaves
            groups += child_groups
        elif node.kind == "text":
            leaves += len(node.text_lines)
        else:
            leaves += 1
    return leaves, groups


def _source_ids(nodes):
    result = set()
    for node in nodes:
        if node.style.data_source_id:
            result.add(node.style.data_source_id)
        if node.kind == "g":
            result.update(_source_ids(node.children))
        for line in node.text_lines:
            for run in line.runs:
                if run.style.data_source_id:
                    result.add(run.style.data_source_id)
    return result


@unittest.skipUnless(REFERENCE_RUN, "PPT_EDITABLE_REFERENCE_RUN not configured")
class ReferenceIntegrationTests(unittest.TestCase):
    def test_fy26h1_reference_run_is_editable_grouped_verified_and_machine_source_only(self):
        run = Path(REFERENCE_RUN)
        context = validate_completed_run(run)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        self.assertEqual(len(sources), 14)
        self.assertEqual(
            {source.slide_id for source in sources if source.owner == "approved_anchor"},
            {"S01", "S06"},
        )
        self.assertEqual(
            {source.slide_id for source in sources if source.owner == "production"},
            {"S{:02d}".format(index) for index in range(1, 15)} - {"S01", "S06"},
        )

        visible_violations = {
            source.slide_id: VISIBLE_SOURCE_ID.findall(_visible_svg_text(source.path))
            for source in sources
            if VISIBLE_SOURCE_ID.search(_visible_svg_text(source.path))
        }
        self.assertEqual(
            visible_violations,
            {},
            "internal source IDs must be removed from visible text and retained only as metadata",
        )

        deck = preflight_deck(
            context,
            sources,
            storyboard,
            "sha256:" + "a" * 64,
        )
        leaves = groups = 0
        for slide in deck.slides:
            slide_leaves, slide_groups = _plan_counts(slide.nodes)
            leaves += slide_leaves
            groups += slide_groups
        self.assertEqual((len(deck.slides), leaves, groups, leaves + groups), (14, 570, 63, 633))
        expected_source_ids = set()
        for slide in deck.slides:
            expected_source_ids.update(_source_ids(slide.nodes))
        self.assertTrue(expected_source_ids)

        office_capable = powerpoint_available()
        capability = GenerationCapability(
            office_available=office_capable,
            pillow_available=True,
        )
        result = generate_editable(run, capability)
        expected_status = "PASS" if office_capable else "GENERATED_UNVERIFIED"
        self.assertEqual(result.status, expected_status)
        output = run / result.output_path
        self.assertTrue(output.is_file())
        self.assertEqual(
            "sha256:" + __import__("hashlib").sha256(output.read_bytes()).hexdigest(),
            result.output_sha256,
        )
        structural = verify_candidate(
            output,
            deck,
            load_verification_config(CONFIG_PATH),
            office_normalized=office_capable,
        )
        self.assertTrue(structural.passed, structural.failures)
        self.assertEqual(
            (
                structural.slide_count,
                structural.recursive_leaf_count,
                structural.recursive_group_count,
            ),
            (14, 570, 63),
        )
        with zipfile.ZipFile(output, "r") as archive:
            names = archive.namelist()
            self.assertFalse(any(name.startswith("ppt/media/") for name in names))
            slide_names = [
                name
                for name in names
                if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", name)
            ]
            visible_text = []
            group_count = 0
            trace_source_ids = set()
            for name in slide_names:
                slide_root = ET.fromstring(archive.read(name))
                for node in slide_root.iter():
                    local = node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""
                    if local == "t" and node.text:
                        visible_text.append(node.text)
                    elif local == "grpSp":
                        group_count += 1
                    elif local == "cNvPr" and node.get("descr"):
                        trace = json.loads(node.get("descr"))
                        if trace.get("source_id"):
                            trace_source_ids.add(trace["source_id"])
            self.assertNotRegex(" ".join(visible_text), VISIBLE_SOURCE_ID)
            self.assertEqual(group_count, 63)
            self.assertFalse(expected_source_ids - trace_source_ids)
            self.assertEqual(
                len([name for name in names if re.fullmatch(r"ppt/notesSlides/notesSlide[0-9]+\.xml", name)]),
                14,
            )

        manifest = json.loads(
            (run / "delivery" / "editable" / "editable-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], expected_status)
        self.assertEqual(manifest["output_sha256"], result.output_sha256)


if __name__ == "__main__":
    unittest.main()
