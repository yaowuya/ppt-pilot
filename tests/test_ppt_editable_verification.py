import inspect
import io
import json
import shutil
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

from lxml import etree
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "ppt-editable"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
RUN_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "run-complete"
SVG_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "svg"
CONFIG_PATH = SKILL_ROOT / "assets" / "verification-config.json"
sys.path.insert(0, str(SCRIPTS_ROOT))

from _ppt_editable import DeckPlan, EditableError, SpeakerNotes  # noqa: E402
from _ppt_editable.config import load_verification_config  # noqa: E402
from _ppt_editable.contract import (  # noqa: E402
    SlideSource,
    parse_storyboard,
    resolve_slide_sources,
    validate_completed_run,
)
from _ppt_editable.drawingml import presentation_bytes  # noqa: E402
from _ppt_editable.svg_parser import parse_svg_slide, preflight_deck  # noqa: E402
import _ppt_editable.structural_verify as structural_verify  # noqa: E402
from _ppt_editable.structural_verify import verify_candidate  # noqa: E402
import verify_editable_pptx  # noqa: E402


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": P_NS, "a": A_NS}


def qn(namespace, local):
    return "{{{}}}{}".format(namespace, local)


class StructuralVerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = load_verification_config(CONFIG_PATH)

    def _deck_plan(self):
        run = self.root / "run"
        if not run.exists():
            shutil.copytree(RUN_FIXTURE_ROOT, run)
        context = validate_completed_run(run)
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        return run, preflight_deck(
            context,
            sources,
            storyboard,
            "sha256:" + "a" * 64,
        )

    def _candidate(self):
        run, plan = self._deck_plan()
        path = self.root / "candidate.pptx"
        path.write_bytes(presentation_bytes(plan))
        return run, plan, path

    def _rewrite_member(self, data, member, transform):
        source = zipfile.ZipFile(io.BytesIO(data), "r")
        output_stream = io.BytesIO()
        with source, zipfile.ZipFile(output_stream, "w") as output:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == member:
                    payload = transform(payload)
                output.writestr(info, payload)
        return output_stream.getvalue()

    def _add_member(self, data, member, payload):
        source = zipfile.ZipFile(io.BytesIO(data), "r")
        output_stream = io.BytesIO()
        with source, zipfile.ZipFile(output_stream, "w") as output:
            for info in source.infolist():
                output.writestr(info, source.read(info.filename))
            output.writestr(member, payload)
        return output_stream.getvalue()

    def _remove_member(self, data, member):
        source = zipfile.ZipFile(io.BytesIO(data), "r")
        output_stream = io.BytesIO()
        with source, zipfile.ZipFile(output_stream, "w") as output:
            for info in source.infolist():
                if info.filename != member:
                    output.writestr(info, source.read(info.filename))
        return output_stream.getvalue()

    def _set_unsupported_compression(self, data, member):
        payload = bytearray(data)
        target = member.encode("utf-8")
        cursor = 0
        while True:
            index = payload.find(b"PK\x03\x04", cursor)
            if index < 0:
                break
            name_length = int.from_bytes(payload[index + 26 : index + 28], "little")
            extra_length = int.from_bytes(payload[index + 28 : index + 30], "little")
            name = bytes(payload[index + 30 : index + 30 + name_length])
            if name == target:
                payload[index + 8 : index + 10] = (99).to_bytes(2, "little")
            cursor = index + 30 + name_length + extra_length
        cursor = 0
        while True:
            index = payload.find(b"PK\x01\x02", cursor)
            if index < 0:
                break
            name_length = int.from_bytes(payload[index + 28 : index + 30], "little")
            extra_length = int.from_bytes(payload[index + 30 : index + 32], "little")
            comment_length = int.from_bytes(payload[index + 32 : index + 34], "little")
            name = bytes(payload[index + 46 : index + 46 + name_length])
            if name == target:
                payload[index + 10 : index + 12] = (99).to_bytes(2, "little")
            cursor = index + 46 + name_length + extra_length + comment_length
        return bytes(payload)

    def _mutate_xml(self, data, member, transform):
        def apply(payload):
            root = etree.fromstring(payload)
            transform(root)
            return etree.tostring(
                root,
                xml_declaration=True,
                encoding="UTF-8",
                standalone=True,
            )

        return self._rewrite_member(data, member, apply)

    def test_valid_candidate_passes_all_pre_office_gates_and_counts(self):
        _, plan, path = self._candidate()
        report = verify_candidate(path, plan, self.config)
        self.assertTrue(report.passed)
        self.assertEqual(report.failures, ())
        self.assertEqual(report.slide_count, 2)
        self.assertEqual(report.recursive_leaf_count, 2)
        self.assertEqual(report.recursive_group_count, 0)
        self.assertEqual(report.top_level_shape_count, 2)
        self.assertTrue(
            hasattr(report, "slide_metadata"),
            "validation report must retain source title/description metadata",
        )
        self.assertEqual(
            report.slide_metadata,
            tuple(
                (slide.slide_id, slide.title, slide.description)
                for slide in plan.slides
            ),
        )
        self.assertEqual(
            report.to_dict()["slides"],
            [
                {
                    "slide_id": slide.slide_id,
                    "title": slide.title,
                    "description": slide.description,
                }
                for slide in plan.slides
            ],
        )

    def test_office_normalized_root_and_space_canonicalization_is_scoped(self):
        slide = parse_svg_slide(
            SlideSource(
                "S01",
                SVG_FIXTURE_ROOT / "namespace-text.svg",
                "slides/S01.svg",
                "production",
            ),
            SpeakerNotes(),
        )
        plan = DeckPlan("office-normalized", "sha256:" + "a" * 64, (slide,))
        path = self.root / "office-normalized.pptx"
        original = presentation_bytes(plan)

        def normalize_like_office(root):
            properties = root.find(".//p:spTree/p:grpSpPr", NS)
            xfrm = etree.SubElement(properties, qn(A_NS, "xfrm"))
            etree.SubElement(xfrm, qn(A_NS, "off"), x="0", y="0")
            etree.SubElement(xfrm, qn(A_NS, "ext"), cx="0", cy="0")
            etree.SubElement(xfrm, qn(A_NS, "chOff"), x="0", y="0")
            etree.SubElement(xfrm, qn(A_NS, "chExt"), cx="0", cy="0")
            xml_space = qn("http://www.w3.org/XML/1998/namespace", "space")
            for text in root.findall(".//a:t", NS):
                text.attrib.pop(xml_space, None)

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                normalize_like_office,
            )
        )
        self.assertFalse(verify_candidate(path, plan, self.config).passed)
        try:
            normalized_report = verify_candidate(
                path,
                plan,
                self.config,
                office_normalized=True,
            )
        except TypeError as exc:
            self.fail(f"office-normalized verifier mode is missing: {exc}")
        self.assertTrue(normalized_report.passed, normalized_report.failures)

    def test_office_normalized_may_remove_printer_settings_only(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()
        printer_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
            "printerSettings"
        )

        def remove_printer_relationship(root):
            relationship = next(
                child
                for child in root
                if child.get("Type") == printer_type
            )
            root.remove(relationship)

        normalized = self._mutate_xml(
            original,
            "ppt/_rels/presentation.xml.rels",
            remove_printer_relationship,
        )
        normalized = self._remove_member(
            normalized,
            "ppt/printerSettings/printerSettings1.bin",
        )
        path.write_bytes(normalized)

        self.assertFalse(verify_candidate(path, plan, self.config).passed)
        report = verify_candidate(
            path,
            plan,
            self.config,
            office_normalized=True,
        )
        self.assertTrue(report.passed, report.failures)

    def test_text_boxes_require_exact_no_fill_and_no_border(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def visible_fill(root):
            properties = root.find(".//p:sp[p:txBody]/p:spPr", NS)
            no_fill = properties.find("./a:noFill", NS)
            index = properties.index(no_fill)
            properties.remove(no_fill)
            solid = etree.Element(qn(A_NS, "solidFill"))
            etree.SubElement(solid, qn(A_NS, "srgbClr"), val="FF0000")
            properties.insert(index, solid)

        def visible_border(root):
            line = root.find(".//p:sp[p:txBody]/p:spPr/a:ln", NS)
            no_fill = line.find("./a:noFill", NS)
            line.remove(no_fill)
            solid = etree.SubElement(line, qn(A_NS, "solidFill"))
            etree.SubElement(solid, qn(A_NS, "srgbClr"), val="FF0000")

        for transform in (visible_fill, visible_border):
            path.write_bytes(
                self._mutate_xml(
                    original,
                    "ppt/slides/slide1.xml",
                    transform,
                )
            )
            with self.subTest(transform=transform.__name__):
                report = verify_candidate(path, plan, self.config)
                self.assertFalse(report.passed)
                self.assertIn(
                    "content_mismatch",
                    {failure.code for failure in report.failures},
                )

    def test_corrupt_and_duplicate_zip_entries_fail_zip_gate(self):
        _, plan, path = self._candidate()
        valid = path.read_bytes()
        path.write_bytes(b"not a zip")
        report = verify_candidate(path, plan, self.config)
        self.assertFalse(report.passed)
        self.assertIn("pptx_zip_invalid", {failure.code for failure in report.failures})

        path.write_bytes(valid)
        data = io.BytesIO(path.read_bytes())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(data, "a") as archive:
                archive.writestr("ppt/slides/slide1.xml", b"duplicate")
        path.write_bytes(data.getvalue())
        report = verify_candidate(path, plan, self.config)
        self.assertIn("pptx_zip_invalid", {failure.code for failure in report.failures})

        path.write_bytes(
            self._set_unsupported_compression(
                valid,
                "ppt/slides/slide1.xml",
            )
        )
        report = verify_candidate(path, plan, self.config)
        self.assertFalse(report.passed)
        self.assertIn("pptx_zip_invalid", {failure.code for failure in report.failures})

    def test_slide_root_requires_one_content_tree_and_global_image_scan(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_extra_content_tree_with_picture(root):
            extra = etree.SubElement(root, qn(P_NS, "cSld"), name="hidden-extra")
            tree = etree.SubElement(extra, qn(P_NS, "spTree"))
            etree.SubElement(tree, qn(P_NS, "pic"))

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                add_extra_content_tree_with_picture,
            )
        )
        codes = {
            failure.code
            for failure in verify_candidate(path, plan, self.config).failures
        }
        self.assertIn("structure_mismatch", codes)
        self.assertIn("image_fallback_detected", codes)

    def test_unsupported_slide_children_and_geometry_text_bodies_are_rejected(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_graphic_frame(root):
            tree = root.find(".//p:spTree", NS)
            frame = etree.Element(qn(P_NS, "graphicFrame"))
            nv = etree.SubElement(frame, qn(P_NS, "nvGraphicFramePr"))
            etree.SubElement(nv, qn(P_NS, "cNvPr"), id="999", name="extra")
            etree.SubElement(nv, qn(P_NS, "cNvGraphicFramePr"))
            etree.SubElement(nv, qn(P_NS, "nvPr"))
            tree.append(frame)

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_graphic_frame))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_text_body_to_geometry(root):
            geometry = root.xpath(
                ".//p:sp[p:nvSpPr/p:cNvPr[@descr and not(contains(@descr, '&quot;kind&quot;:&quot;text&quot;'))]]",
                namespaces=NS,
            )
            if not geometry:
                return
            body = etree.SubElement(geometry[0], qn(P_NS, "txBody"))
            etree.SubElement(body, qn(A_NS, "bodyPr"))
            etree.SubElement(body, qn(A_NS, "lstStyle"))
            etree.SubElement(body, qn(A_NS, "p"))

        arc_slide = parse_svg_slide(
            SlideSource("S01", SVG_FIXTURE_ROOT / "arcs.svg", "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        arc_plan = DeckPlan("arc-deck", "sha256:" + "a" * 64, (arc_slide,))
        arc_original = presentation_bytes(arc_plan)
        path.write_bytes(
            self._mutate_xml(
                arc_original,
                "ppt/slides/slide1.xml",
                add_text_body_to_geometry,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, arc_plan, self.config).failures},
        )

    def test_text_shape_rejects_duplicate_body_and_extra_paragraph_formatting(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def duplicate_body(root):
            shape = root.find(".//p:sp[p:txBody]", NS)
            shape.append(etree.fromstring(etree.tostring(shape.find("./p:txBody", NS))))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", duplicate_body))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def extra_paragraph_format(root):
            root.find(".//a:pPr", NS).set("marL", "100")

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", extra_paragraph_format)
        )
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_nonvisual_and_sptree_root_metadata_are_exact(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def hide_shape(root):
            root.find(".//p:cNvPr[@descr]", NS).set("hidden", "1")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", hide_shape))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def corrupt_root_properties(root):
            tree = root.find(".//p:spTree", NS)
            tree[1].tag = "{urn:evil}grpSpPr"

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", corrupt_root_properties)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_presentation_relationship_order_is_the_authoritative_slide_order(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def swap_slide_relationship_ids(root):
            slide_ids = root.findall(".//p:sldId", NS)
            relationship_attribute = next(
                name for name in slide_ids[0].attrib if name.endswith("}id")
            )
            first = slide_ids[0].get(relationship_attribute)
            second = slide_ids[1].get(relationship_attribute)
            slide_ids[0].set(relationship_attribute, second)
            slide_ids[1].set(relationship_attribute, first)

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/presentation.xml",
                swap_slide_relationship_ids,
            )
        )
        codes = {failure.code for failure in verify_candidate(path, plan, self.config).failures}
        self.assertIn("structure_mismatch", codes)

    def test_shape_ids_names_and_trace_sequence_must_match_exactly(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def unique_but_wrong_id(root):
            nodes = root.findall(".//p:cNvPr[@descr]", NS)
            nodes[0].set("id", "999")

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                unique_but_wrong_id,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def wrong_name(root):
            nodes = root.findall(".//p:cNvPr[@descr]", NS)
            nodes[0].set("name", "wrong-but-unique")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", wrong_name))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_image_duplicate_id_trace_and_hierarchy_mutations_fail_structure(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_picture(root):
            root.find(".//p:spTree", NS).append(etree.Element(qn(P_NS, "pic")))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_picture))
        report = verify_candidate(path, plan, self.config)
        self.assertIn("image_fallback_detected", {failure.code for failure in report.failures})

        def duplicate_id(root):
            nodes = root.findall(".//p:cNvPr", NS)
            nodes[1].set("id", nodes[0].get("id"))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", duplicate_id))
        report = verify_candidate(path, plan, self.config)
        self.assertIn("structure_mismatch", {failure.code for failure in report.failures})

        def forge_trace(root):
            nodes = root.findall(".//p:cNvPr[@descr]", NS)
            nodes[0].set("descr", "{}")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", forge_trace))
        report = verify_candidate(path, plan, self.config)
        self.assertIn("group_mismatch", {failure.code for failure in report.failures})

    def test_title_text_run_and_empty_text_mutations_fail_content(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def wrong_title(root):
            root.find(".//p:cSld", NS).set("name", "wrong")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", wrong_title))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def wrong_text(root):
            root.find(".//a:t", NS).text = "wrong"

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", wrong_text))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def empty_text(root):
            root.find(".//a:t", NS).text = ""

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", empty_text))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_text_fill_rejects_color_transforms_and_redundant_alpha(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_tint(root):
            color = root.find(".//a:rPr/a:solidFill/a:srgbClr", NS)
            etree.SubElement(color, qn(A_NS, "tint"), val="50000")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_tint))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_redundant_alpha(root):
            color = root.find(".//a:rPr/a:solidFill/a:srgbClr", NS)
            etree.SubElement(color, qn(A_NS, "alpha"), val="100000")

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", add_redundant_alpha)
        )
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_custom_geometry_trace_requires_one_matching_custgeom(self):
        slide = parse_svg_slide(
            SlideSource("S01", SVG_FIXTURE_ROOT / "arcs.svg", "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        plan = DeckPlan("arc-deck", "sha256:" + "a" * 64, (slide,))
        path = self.root / "arc-geometry.pptx"
        original = presentation_bytes(plan)

        def remove_geometry(root):
            shape = root.xpath(
                ".//p:sp[p:nvSpPr/p:cNvPr[@descr]]",
                namespaces=NS,
            )[0]
            sp_pr = shape.find("./p:spPr", NS)
            sp_pr.remove(sp_pr.find("./a:custGeom", NS))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", remove_geometry))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_competing_geometry(root):
            shape = root.xpath(
                ".//p:sp[p:nvSpPr/p:cNvPr[@descr]]",
                namespaces=NS,
            )[0]
            sp_pr = shape.find("./p:spPr", NS)
            preset = etree.SubElement(sp_pr, qn(A_NS, "prstGeom"), prst="rect")
            etree.SubElement(preset, qn(A_NS, "avLst"))

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", add_competing_geometry)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_text_font_nodes_allow_only_typeface_and_no_children(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_charset(root):
            root.find(".//a:rPr/a:latin", NS).set("charset", "1")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_charset))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_font_child(root):
            etree.SubElement(root.find(".//a:rPr/a:ea", NS), qn(A_NS, "extLst"))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_font_child))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_extra_paragraph_and_unsupported_run_formatting_fail_content(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_paragraph(root):
            text_body = root.find(".//p:txBody", NS)
            paragraph = etree.SubElement(text_body, qn(A_NS, "p"))
            run = etree.SubElement(paragraph, qn(A_NS, "r"))
            etree.SubElement(run, qn(A_NS, "rPr"), lang="zh-CN", sz="1500", dirty="0")
            etree.SubElement(run, qn(A_NS, "t")).text = "injected"

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_paragraph))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_italic(root):
            root.find(".//a:rPr", NS).set("i", "1")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_italic))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_notes_and_bounds_mutations_have_distinct_failures(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def wrong_notes(root):
            text = root.find(".//a:t", NS)
            if text is not None:
                text.text = "wrong note"

        path.write_bytes(self._mutate_xml(original, "ppt/notesSlides/notesSlide1.xml", wrong_notes))
        self.assertIn(
            "notes_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def off_slide(root):
            shape = root.xpath(
                ".//p:sp[p:nvSpPr/p:cNvPr[@descr]]",
                namespaces=NS,
            )[0]
            shape.find("./p:spPr/a:xfrm/a:off", NS).set("x", str(2000 * 9525))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", off_slide))
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_notes_shape_inventory_rejects_non_placeholders_and_pictures(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_non_placeholder_text(root):
            tree = root.find("./p:cSld/p:spTree", NS)
            body = root.xpath(
                "./p:cSld/p:spTree/p:sp[p:nvSpPr/p:nvPr/p:ph[@type='body']]",
                namespaces=NS,
            )[0]
            injected = etree.fromstring(etree.tostring(body))
            nonvisual = injected.find("./p:nvSpPr", NS)
            identity = nonvisual.find("./p:cNvPr", NS)
            identity.set("id", "99")
            identity.set("name", "Injected notes text")
            placeholder = nonvisual.find("./p:nvPr/p:ph", NS)
            placeholder.getparent().remove(placeholder)
            tree.append(injected)

        def add_picture(root):
            tree = root.find("./p:cSld/p:spTree", NS)
            etree.SubElement(tree, qn(P_NS, "pic"))

        for transform in (add_non_placeholder_text, add_picture):
            path.write_bytes(
                self._mutate_xml(
                    original,
                    "ppt/notesSlides/notesSlide1.xml",
                    transform,
                )
            )
            with self.subTest(transform=transform.__name__):
                report = verify_candidate(path, plan, self.config)
                self.assertFalse(report.passed)
                self.assertIn(
                    "structure_mismatch",
                    {failure.code for failure in report.failures},
                )

        def add_standard_header(root):
            tree = root.find("./p:cSld/p:spTree", NS)
            standard = root.xpath(
                "./p:cSld/p:spTree/p:sp[p:nvSpPr/p:nvPr/p:ph[@type='sldNum']]",
                namespaces=NS,
            )[0]
            header = etree.fromstring(etree.tostring(standard))
            identity = header.find("./p:nvSpPr/p:cNvPr", NS)
            identity.set("id", "99")
            identity.set("name", "Header Placeholder 99")
            placeholder = header.find("./p:nvSpPr/p:nvPr/p:ph", NS)
            placeholder.set("type", "hdr")
            placeholder.set("idx", "99")
            tree.append(header)

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/notesSlides/notesSlide1.xml",
                add_standard_header,
            )
        )
        self.assertTrue(verify_candidate(path, plan, self.config).passed)

    def test_custom_geometry_oracle_is_independent_from_production_emitter(self):
        source = inspect.getsource(structural_verify._verify_custom_geometry)
        self.assertNotIn("build_leaf_shape", source)

    def test_source_oracle_rejects_valid_but_wrong_transform_flip(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def add_flip(root):
            root.find(".//p:sp/p:spPr/a:xfrm", NS).set("flipH", "1")

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                add_flip,
            )
        )
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_source_oracle_rejects_in_slide_shift_over_bounds_tolerance(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def shift_inside_slide(root):
            off = root.find(".//p:sp/p:spPr/a:xfrm/a:off", NS)
            off.set("x", str(int(off.get("x")) + 2 * 9525))

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                shift_inside_slide,
            )
        )
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_exact_slide_dimensions_are_structurally_gated(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def change_slide_width(root):
            size = root.find(".//p:sldSz", NS)
            size.set("cx", str(12192000 + 1))

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/presentation.xml",
                change_slide_width,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_xfrm_child_cardinality_attributes_and_ranges_are_strict(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def duplicate_off(root):
            xfrm = root.find(".//p:spPr/a:xfrm", NS)
            xfrm.insert(1, etree.fromstring(etree.tostring(xfrm.find("./a:off", NS))))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", duplicate_off))
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def unsupported_rotation(root):
            root.find(".//p:spPr/a:xfrm", NS).set("rot", "1")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", unsupported_rotation))
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def noninteger_extent(root):
            root.find(".//p:spPr/a:xfrm/a:ext", NS).set("cx", "1.0")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", noninteger_extent))
        self.assertIn(
            "bounds_violation",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_custom_geometry_requires_path_list_integer_values_and_nonzero_sweep(self):
        slide = parse_svg_slide(
            SlideSource("S01", SVG_FIXTURE_ROOT / "arcs.svg", "slides/S01.svg", "production"),
            SpeakerNotes(),
        )
        plan = DeckPlan("arc-deck", "sha256:" + "a" * 64, (slide,))
        path = self.root / "arcs.pptx"
        original = presentation_bytes(plan)
        path.write_bytes(original)
        self.assertTrue(verify_candidate(path, plan, self.config).passed)

        def valid_but_wrong_sweep(root):
            arc = root.find(".//a:arcTo", NS)
            arc.set("swAng", str(int(arc.get("swAng")) + 60000))

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                valid_but_wrong_sweep,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def mixed_geometry_text(root):
            root.find(".//a:path", NS).text = "inert"

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/slide1.xml",
                mixed_geometry_text,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def remove_path_list(root):
            custom = root.find(".//a:custGeom", NS)
            custom.remove(custom.find("./a:pathLst", NS))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", remove_path_list))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def decimal_coordinate(root):
            root.find(".//a:pt", NS).set("x", "1.5")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", decimal_coordinate))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def zero_sweep(root):
            root.find(".//a:arcTo", NS).set("swAng", "0")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", zero_sweep))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def empty_path(root):
            path_node = root.find(".//a:path", NS)
            for child in list(path_node):
                path_node.remove(child)

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", empty_path))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def missing_path_width(root):
            del root.find(".//a:path", NS).attrib["w"]

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", missing_path_width))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def missing_arc_sweep(root):
            del root.find(".//a:arcTo", NS).attrib["swAng"]

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", missing_arc_sweep))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def foreign_command(root):
            root.find(".//a:arcTo", NS).tag = "{urn:evil}arcTo"

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", foreign_command))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def nonempty_adjustment_list(root):
            etree.SubElement(root.find(".//a:avLst", NS), qn(A_NS, "gd"), name="x", fmla="val 1")

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", nonempty_adjustment_list)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def move_then_close_only(root):
            path_node = root.find(".//a:path", NS)
            first_move = path_node.find("./a:moveTo", NS)
            for child in list(path_node):
                path_node.remove(child)
            path_node.append(first_move)
            etree.SubElement(path_node, qn(A_NS, "close"))

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", move_then_close_only))
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_content_type_declarations_and_optional_part_mimes_are_strict(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def root_attribute(root):
            root.set("unexpected", "1")

        def nested_declaration(root):
            declaration = root.xpath(".//*[local-name()='Default']")[0]
            etree.SubElement(declaration, "{urn:evil}child")

        def wrong_jpeg_type(root):
            declaration = root.xpath(
                ".//*[local-name()='Default' and translate(@Extension, 'JPEG', 'jpeg')='jpeg']"
            )[0]
            declaration.set("ContentType", "application/octet-stream")

        def wrong_printer_settings_type(root):
            declaration = root.xpath(
                ".//*[local-name()='Default' and translate(@Extension, 'BIN', 'bin')='bin']"
            )[0]
            declaration.set("ContentType", "application/octet-stream")

        def wrong_relationship_override(root):
            etree.SubElement(
                root,
                qn("http://schemas.openxmlformats.org/package/2006/content-types", "Override"),
                PartName="/ppt/slides/_rels/slide1.xml.rels",
                ContentType="application/octet-stream",
            )

        def content_types_self_override(root):
            etree.SubElement(
                root,
                qn("http://schemas.openxmlformats.org/package/2006/content-types", "Override"),
                PartName="/[Content_Types].xml",
                ContentType="application/octet-stream",
            )

        for transform in (
            root_attribute,
            nested_declaration,
            wrong_jpeg_type,
            wrong_printer_settings_type,
            wrong_relationship_override,
            content_types_self_override,
        ):
            path.write_bytes(
                self._mutate_xml(
                    original,
                    "[Content_Types].xml",
                    transform,
                )
            )
            with self.subTest(transform=transform.__name__):
                self.assertIn(
                    "structure_mismatch",
                    {
                        failure.code
                        for failure in verify_candidate(path, plan, self.config).failures
                    },
                )

    def test_relationship_targets_and_slide_content_types_are_required(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def missing_target(root):
            relationship = root.xpath(".//*[local-name()='Relationship']")[0]
            relationship.set("Target", "../../missing.xml")

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/_rels/slide1.xml.rels",
                missing_target,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def wrong_content_type(root):
            override = root.xpath(
                ".//*[local-name()='Override' and @PartName='/ppt/slides/slide1.xml']"
            )[0]
            override.set("ContentType", "application/octet-stream")

        path.write_bytes(
            self._mutate_xml(original, "[Content_Types].xml", wrong_content_type)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def remove_rels_default(root):
            default = root.xpath(
                ".//*[local-name()='Default' and translate(@Extension, 'RELS', 'rels')='rels']"
            )[0]
            root.remove(default)

        path.write_bytes(
            self._mutate_xml(original, "[Content_Types].xml", remove_rels_default)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_relationship_target_mode_and_master_layout_cardinality_are_strict(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def bogus_target_mode(root):
            relationship = root.xpath(".//*[local-name()='Relationship']")[0]
            relationship.set("TargetMode", "Bogus")

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/_rels/slide1.xml.rels",
                bogus_target_mode,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        with zipfile.ZipFile(io.BytesIO(original), "r") as archive:
            slide_relationships = etree.fromstring(
                archive.read("ppt/slides/_rels/slide1.xml.rels")
            )
        layout_target = next(
            relationship.get("Target")
            for relationship in slide_relationships
            if relationship.get("Type", "").endswith("/slideLayout")
        )
        layout_name = posix_name = layout_target.rsplit("/", 1)[-1]
        self.assertTrue(posix_name.startswith("slideLayout"))

        def remove_master_layout_edge(root):
            relationship = next(
                child
                for child in root
                if child.get("Type", "").endswith("/slideLayout")
                and child.get("Target", "").endswith(layout_name)
            )
            root.remove(relationship)

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slideMasters/_rels/slideMaster1.xml.rels",
                remove_master_layout_edge,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def relationship_root_attribute(root):
            root.set("unexpected", "1")

        def nested_relationship_payload(root):
            relationship = root.xpath(".//*[local-name()='Relationship']")[0]
            etree.SubElement(relationship, "{urn:evil}child")

        for transform in (
            relationship_root_attribute,
            nested_relationship_payload,
        ):
            path.write_bytes(
                self._mutate_xml(
                    original,
                    "ppt/slides/_rels/slide1.xml.rels",
                    transform,
                )
            )
            with self.subTest(transform=transform.__name__):
                self.assertIn(
                    "structure_mismatch",
                    {
                        failure.code
                        for failure in verify_candidate(path, plan, self.config).failures
                    },
                )

    def test_relationship_graph_namespaces_types_ids_and_sources_are_strict(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def wrong_type(root):
            relationship = root.xpath(
                ".//*[local-name()='Relationship' and contains(@Target, 'notesSlides')]"
            )[0]
            relationship.set(
                "Type",
                "http://schemas.openxmlformats.org/fake/notesSlide",
            )

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/_rels/slide1.xml.rels",
                wrong_type,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def duplicate_id(root):
            relationships = root.xpath(".//*[local-name()='Relationship']")
            relationships[1].set("Id", relationships[0].get("Id"))

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/_rels/slide1.xml.rels",
                duplicate_id,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def wrong_namespace(root):
            root.tag = "{urn:evil}Relationships"

        path.write_bytes(
            self._mutate_xml(
                original,
                "ppt/slides/_rels/slide1.xml.rels",
                wrong_namespace,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        orphan = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="urn:test" Target="../../slides/slide1.xml"/>'
            '</Relationships>'
        ).encode("utf-8")
        path.write_bytes(
            self._add_member(
                original,
                "ppt/orphan/_rels/missing.xml.rels",
                orphan,
            )
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def duplicate_override(root):
            target = root.xpath(
                ".//*[local-name()='Override' and @PartName='/ppt/slides/slide1.xml']"
            )[0]
            root.append(etree.fromstring(etree.tostring(target)))

        path.write_bytes(
            self._mutate_xml(original, "[Content_Types].xml", duplicate_override)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_root_and_presentation_support_relationships_are_exactly_one(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()
        office = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        package = "http://schemas.openxmlformats.org/package/2006/relationships/"
        cases = (
            ("_rels/.rels", package + "metadata/core-properties", "docProps/core.xml", True),
            ("_rels/.rels", office + "extended-properties", "docProps/app.xml", True),
            ("_rels/.rels", package + "metadata/thumbnail", "docProps/thumbnail.jpeg", True),
            ("ppt/_rels/presentation.xml.rels", office + "printerSettings", "ppt/printerSettings/printerSettings1.bin", True),
            ("ppt/_rels/presentation.xml.rels", office + "presProps", "ppt/presProps.xml", True),
            ("ppt/_rels/presentation.xml.rels", office + "viewProps", "ppt/viewProps.xml", True),
            ("ppt/_rels/presentation.xml.rels", office + "theme", "ppt/theme/theme1.xml", False),
            ("ppt/_rels/presentation.xml.rels", office + "tableStyles", "ppt/tableStyles.xml", True),
        )

        for rels_member, relationship_type, target_part, remove_part in cases:
            def duplicate(root, relationship_type=relationship_type):
                relationship = next(
                    child
                    for child in root
                    if child.get("Type") == relationship_type
                )
                copied = etree.fromstring(etree.tostring(relationship))
                copied.set("Id", "rId999")
                root.append(copied)

            duplicated = self._mutate_xml(original, rels_member, duplicate)
            path.write_bytes(duplicated)
            with self.subTest(role=relationship_type, mutation="duplicate"):
                self.assertIn(
                    "structure_mismatch",
                    {failure.code for failure in verify_candidate(path, plan, self.config).failures},
                )

            def remove_relationship(root, relationship_type=relationship_type):
                relationship = next(
                    child
                    for child in root
                    if child.get("Type") == relationship_type
                )
                root.remove(relationship)

            missing = self._mutate_xml(original, rels_member, remove_relationship)
            if remove_part:
                missing = self._remove_member(missing, target_part)

                def remove_override(root, target_part=target_part):
                    for override in root.xpath(
                        ".//*[local-name()='Override' and @PartName=$part]",
                        part="/" + target_part,
                    ):
                        root.remove(override)

                missing = self._mutate_xml(
                    missing,
                    "[Content_Types].xml",
                    remove_override,
                )
            path.write_bytes(missing)
            with self.subTest(role=relationship_type, mutation="missing"):
                self.assertIn(
                    "structure_mismatch",
                    {failure.code for failure in verify_candidate(path, plan, self.config).failures},
                )

    def test_empty_relationship_parts_require_an_allowed_owner_class(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()
        empty_relationships = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        ).encode("utf-8")
        for member in (
            "docProps/_rels/core.xml.rels",
            "ppt/theme/_rels/theme1.xml.rels",
        ):
            path.write_bytes(self._add_member(original, member, empty_relationships))
            with self.subTest(member=member):
                self.assertIn(
                    "structure_mismatch",
                    {failure.code for failure in verify_candidate(path, plan, self.config).failures},
                )

    def test_extra_reachable_slide_and_wrong_layout_content_type_are_rejected(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(original), "r") as archive:
            slide1 = archive.read("ppt/slides/slide1.xml")
        data = self._add_member(original, "ppt/slides/slide3.xml", slide1)

        def add_slide_override(root):
            etree.SubElement(
                root,
                "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
                PartName="/ppt/slides/slide3.xml",
                ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            )

        data = self._mutate_xml(data, "[Content_Types].xml", add_slide_override)

        def add_reachable_extra(root):
            etree.SubElement(
                root,
                "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship",
                Id="rId999",
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml",
                Target="slides/slide3.xml",
            )

        data = self._mutate_xml(
            data,
            "ppt/_rels/presentation.xml.rels",
            add_reachable_extra,
        )
        path.write_bytes(data)
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def wrong_layout_type(root):
            override = root.xpath(
                ".//*[local-name()='Override' and contains(@PartName, '/ppt/slideLayouts/slideLayout1.xml')]"
            )[0]
            override.set("ContentType", "application/octet-stream")

        path.write_bytes(
            self._mutate_xml(original, "[Content_Types].xml", wrong_layout_type)
        )
        self.assertIn(
            "structure_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_true_text_box_requires_zero_insets_and_no_autofit(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def remove_no_autofit(root):
            body = root.find(".//a:bodyPr", NS)
            body.remove(body.find("./a:noAutofit", NS))

        path.write_bytes(
            self._mutate_xml(original, "ppt/slides/slide1.xml", remove_no_autofit)
        )
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

        def add_inset(root):
            root.find(".//a:bodyPr", NS).set("lIns", "1")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", add_inset))
        self.assertIn(
            "content_mismatch",
            {failure.code for failure in verify_candidate(path, plan, self.config).failures},
        )

    def test_extreme_numeric_and_trace_json_inputs_are_typed_failures(self):
        _, plan, path = self._candidate()
        original = path.read_bytes()

        def huge_id(root):
            root.find(".//p:cNvPr[@descr]", NS).set("id", "9" * 5000)

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", huge_id))
        report = verify_candidate(path, plan, self.config)
        self.assertFalse(report.passed)
        self.assertIn("structure_mismatch", {failure.code for failure in report.failures})

        def recursive_trace(root):
            root.find(".//p:cNvPr[@descr]", NS).set(
                "descr",
                "[" * 2000 + "0" + "]" * 2000,
            )

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", recursive_trace))
        report = verify_candidate(path, plan, self.config)
        self.assertFalse(report.passed)
        self.assertIn("structure_mismatch", {failure.code for failure in report.failures})

    def test_malformed_candidate_values_are_structured_failures_and_cli_exit_two(self):
        run, plan, path = self._candidate()
        original = path.read_bytes()

        def malformed_alpha(root):
            color = root.find(".//a:rPr/a:solidFill/a:srgbClr", NS)
            etree.SubElement(color, qn(A_NS, "alpha"), val="not-an-integer")

        path.write_bytes(self._mutate_xml(original, "ppt/slides/slide1.xml", malformed_alpha))
        report = verify_candidate(path, plan, self.config)
        self.assertFalse(report.passed)
        self.assertIn("content_mismatch", {failure.code for failure in report.failures})
        report_path = self.root / "malformed-report.json"
        code = verify_editable_pptx.main(
            [
                "--candidate",
                str(path),
                "--run-dir",
                str(run),
                "--input-snapshot-id",
                plan.input_snapshot_id,
                "--config",
                str(CONFIG_PATH),
                "--report",
                str(report_path),
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "failed")

    def test_cli_report_statuses_share_one_canonical_schema(self):
        self.assertTrue(
            hasattr(verify_editable_pptx, "_report_payload"),
            "CLI needs one canonical report constructor",
        )
        expected_keys = {
            "schema_version",
            "kind",
            "status",
            "slide_count",
            "top_level_shape_count",
            "recursive_leaf_count",
            "recursive_group_count",
            "slides",
            "failures",
        }
        failure_keys = {
            "code",
            "slide_id",
            "svg_tree_path",
            "element_type",
            "message",
            "remediation",
        }
        for status in ("running", "invalid", "error"):
            failures = (
                []
                if status == "running"
                else [verify_editable_pptx._failure_payload("source_unreadable", status)]
            )
            payload = verify_editable_pptx._report_payload(
                status,
                failures=failures,
            )
            with self.subTest(status=status):
                self.assertEqual(set(payload), expected_keys)
                self.assertIsInstance(payload["slides"], list)
                self.assertTrue(
                    all(set(failure) == failure_keys for failure in payload["failures"])
                )

    def test_cli_replaces_stale_report_on_invalid_snapshot_and_reports_write_failure(self):
        run, plan, path = self._candidate()
        report_path = self.root / "stale-report.json"
        report_path.write_text('{"status":"passed"}\n', encoding="utf-8")
        arguments = [
            "--candidate",
            str(path),
            "--run-dir",
            str(run),
            "--input-snapshot-id",
            "invalid",
            "--config",
            str(CONFIG_PATH),
            "--report",
            str(report_path),
        ]
        self.assertEqual(verify_editable_pptx.main(arguments), 3)
        self.assertEqual(
            json.loads(report_path.read_text(encoding="utf-8"))["status"],
            "invalid",
        )
        report_path.write_text('{"status":"passed"}\n', encoding="utf-8")
        self.assertEqual(
            verify_editable_pptx.main(["--report", str(report_path)]),
            3,
        )
        self.assertEqual(
            json.loads(report_path.read_text(encoding="utf-8"))["status"],
            "invalid",
        )
        with mock.patch.object(
            verify_editable_pptx,
            "atomic_write_json",
            side_effect=OSError("report unavailable"),
        ):
            self.assertEqual(verify_editable_pptx.main(arguments), 4)

    def test_cli_writes_structured_report_and_uses_fixed_exit_codes(self):
        run, plan, path = self._candidate()
        report_path = self.root / "verification.json"
        code = verify_editable_pptx.main(
            [
                "--candidate",
                str(path),
                "--run-dir",
                str(run),
                "--input-snapshot-id",
                plan.input_snapshot_id,
                "--config",
                str(CONFIG_PATH),
                "--report",
                str(report_path),
            ]
        )
        self.assertEqual(code, 0)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["failures"], [])

        path.write_bytes(b"broken")
        code = verify_editable_pptx.main(
            [
                "--candidate",
                str(path),
                "--run-dir",
                str(run),
                "--input-snapshot-id",
                plan.input_snapshot_id,
                "--config",
                str(CONFIG_PATH),
                "--report",
                str(report_path),
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "failed")
        self.assertEqual(verify_editable_pptx.main([]), 3)
        self.assertEqual(verify_editable_pptx.main(["--help"]), 0)

        path.write_bytes(presentation_bytes(plan))
        with mock.patch.object(
            verify_editable_pptx,
            "verify_candidate",
            side_effect=RuntimeError("unexpected verifier failure"),
        ):
            code = verify_editable_pptx.main(
                [
                    "--candidate",
                    str(path),
                    "--run-dir",
                    str(run),
                    "--input-snapshot-id",
                    plan.input_snapshot_id,
                    "--config",
                    str(CONFIG_PATH),
                    "--report",
                    str(report_path),
                ]
            )
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "error")


class VisualMetricTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = load_verification_config(CONFIG_PATH)

    def _visual(self):
        import _ppt_editable.visual_compare as module

        return module

    def _image(self, name, value=0, size=(1280, 720)):
        path = self.root / name
        Image.new("L", size, color=value).save(path)
        return path

    def _renders(self, full_value=0, geometry_value=0):
        return (
            self._image("source-full.png", 0),
            self._image("editable-full.png", full_value),
            self._image("source-geometry.png", 0),
            self._image("editable-geometry.png", geometry_value),
        )

    def test_visual_metric_fixture_cases_are_stable(self):
        payload = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "visual-metric-cases.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            payload,
            {
                "schema_version": 1,
                "cases": [
                    {"id": "identical", "full_mad": 0.0, "geometry_mad": 0.0, "passed": True},
                    {"id": "full-threshold-equality", "full_mad": 4.0, "passed": True},
                    {"id": "full-over-threshold", "full_mad": 5.0, "passed": False},
                    {"id": "geometry-threshold-equality", "geometry_mad": 1.5, "passed": True},
                    {"id": "localized-tile-failure", "tile_mad": 9.0, "passed": False},
                    {"id": "partial-bottom-tile", "tile_width": 64, "tile_height": 16, "tile_mad": 9.0, "passed": False},
                    {"id": "wrong-dimensions", "passed": False},
                    {"id": "missing-render", "passed": False},
                ],
            },
        )

    def test_identical_and_exact_full_threshold_pass_while_over_threshold_fails(self):
        module = self._visual()
        report = module.compare_slide_renders("S01", *self._renders(), self.config)
        self.assertTrue(report.passed)
        self.assertEqual((report.full_page_mad, report.geometry_mad), (0.0, 0.0))

        report = module.compare_slide_renders("S01", *self._renders(full_value=4), self.config)
        self.assertTrue(report.passed)
        self.assertEqual(report.full_page_mad, 4.0)

        report = module.compare_slide_renders("S01", *self._renders(full_value=5), self.config)
        self.assertFalse(report.passed)
        self.assertIn("visual_mismatch", {failure.code for failure in report.failures})

    def test_geometry_threshold_equality_passes(self):
        module = self._visual()
        source_full, editable_full, source_geometry, editable_geometry = self._renders()
        image = Image.new("L", (1280, 720), color=1)
        image.paste(2, (0, 360, 1280, 720))
        image.save(editable_geometry)
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.geometry_mad, 1.5)

    def test_tile_threshold_equality_passes(self):
        module = self._visual()
        reference = Image.new("L", (64, 64), color=0)
        actual = Image.new("L", (64, 64), color=8)
        tiles = module.tile_mads(reference, actual, 64, 8.0)
        self.assertEqual(len(tiles), 1)
        self.assertEqual(tiles[0].mad, 8.0)
        self.assertTrue(tiles[0].passed)

    def test_localized_tile_failure_is_not_hidden_by_full_page_average(self):
        module = self._visual()
        source_full, editable_full, source_geometry, editable_geometry = self._renders()
        image = Image.open(editable_geometry)
        image.paste(9, (0, 0, 64, 64))
        image.save(editable_geometry)
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        self.assertLess(report.geometry_mad, self.config.geometry_only_grayscale_mad_max)
        self.assertFalse(report.passed)
        failed = [tile for tile in report.tiles if not tile.passed]
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0].x, failed[0].y, failed[0].width, failed[0].height), (0, 0, 64, 64))
        self.assertEqual(failed[0].mad, 9.0)

    def test_partial_bottom_tile_uses_actual_64_by_16_area(self):
        module = self._visual()
        source_full, editable_full, source_geometry, editable_geometry = self._renders()
        image = Image.open(editable_geometry)
        image.paste(9, (1216, 704, 1280, 720))
        image.save(editable_geometry)
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        tile = next(tile for tile in report.tiles if tile.x == 1216 and tile.y == 704)
        self.assertEqual((tile.width, tile.height, tile.mad, tile.passed), (64, 16, 9.0, False))

    def test_wrong_dimensions_and_missing_files_fail_without_resize(self):
        module = self._visual()
        source_full, editable_full, source_geometry, editable_geometry = self._renders()
        self._image("source-full.png", 0, size=(160, 90))
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        self.assertFalse(report.passed)
        self.assertIn("visual_mismatch", {failure.code for failure in report.failures})
        source_full.unlink()
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        self.assertFalse(report.passed)

    def test_rgba_renders_are_composited_on_white_before_grayscale(self):
        module = self._visual()
        source_full, editable_full, source_geometry, editable_geometry = self._renders()
        Image.new("RGBA", (1280, 720), color=(0, 0, 0, 0)).save(source_full)
        Image.new("RGBA", (1280, 720), color=(0, 0, 0, 255)).save(editable_full)
        report = module.compare_slide_renders(
            "S01",
            source_full,
            editable_full,
            source_geometry,
            editable_geometry,
            self.config,
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.full_page_mad, 255.0)

    def test_slide_id_cannot_escape_render_or_comparison_directories(self):
        module = self._visual()
        directories = {}
        for name in (
            "source-full",
            "editable-full",
            "source-geometry",
            "editable-geometry",
            "comparison",
        ):
            directories[name] = self.root / name
            directories[name].mkdir()
        Image.new("L", (1280, 720), color=0).save(self.root / "outside.png")
        paths = module.RenderPaths(
            source_full_dir=directories["source-full"],
            editable_full_dir=directories["editable-full"],
            source_geometry_dir=directories["source-geometry"],
            editable_geometry_dir=directories["editable-geometry"],
            comparison_dir=directories["comparison"],
        )
        report = module.compare_render_sets(paths, ("../outside",), self.config)
        self.assertFalse(report.passed)
        self.assertFalse((self.root / "outside-full-diff.png").exists())
        self.assertIn("visual_mismatch", {failure.code for failure in report.failures})

    def test_evidence_write_failure_returns_typed_failure_without_partial_files(self):
        module = self._visual()
        renders = self._renders()
        evidence = self.root / "evidence"
        real_write = module.atomic_write_bytes
        calls = []

        def fail_second(path, data):
            calls.append(Path(path))
            if len(calls) == 2:
                raise EditableError("candidate_write_failed", "disk full")
            return real_write(path, data)

        with mock.patch.object(module, "atomic_write_bytes", side_effect=fail_second):
            report = module.compare_slide_renders(
                "S01",
                *renders,
                self.config,
                evidence_dir=evidence,
            )
        self.assertFalse(report.passed)
        self.assertIn("visual_mismatch", {failure.code for failure in report.failures})
        self.assertFalse((evidence / "S01-full-diff.png").exists())
        self.assertFalse((evidence / "S01-geometry-diff.png").exists())
        self.assertFalse((evidence / "S01-tiles.json").exists())

    def test_evidence_write_failure_restores_preexisting_evidence_bytes(self):
        module = self._visual()
        renders = self._renders()
        evidence = self.root / "evidence-existing"
        evidence.mkdir()
        previous = {
            evidence / "S01-full-diff.png": b"old-full",
            evidence / "S01-geometry-diff.png": b"old-geometry",
            evidence / "S01-tiles.json": b"old-tiles",
        }
        for path, data in previous.items():
            path.write_bytes(data)
        real_write = module.atomic_write_bytes
        calls = []

        def fail_second(path, data):
            calls.append(Path(path))
            if len(calls) == 2:
                raise EditableError("candidate_write_failed", "disk full")
            return real_write(path, data)

        with mock.patch.object(module, "atomic_write_bytes", side_effect=fail_second):
            report = module.compare_slide_renders(
                "S01",
                *renders,
                self.config,
                evidence_dir=evidence,
            )
        self.assertFalse(report.passed)
        self.assertIsNone(report.full_diff_path)
        self.assertIsNone(report.geometry_diff_path)
        self.assertIsNone(report.tile_report_path)
        for path, data in previous.items():
            self.assertEqual(path.read_bytes(), data)

    def test_render_set_rejects_empty_or_duplicate_slide_ids(self):
        module = self._visual()
        directories = {}
        for name in (
            "source-full",
            "editable-full",
            "source-geometry",
            "editable-geometry",
            "comparison",
        ):
            directories[name] = self.root / name
            directories[name].mkdir()
        for name in directories:
            if name != "comparison":
                Image.new("L", (1280, 720), color=0).save(
                    directories[name] / "S01.png"
                )
        paths = module.RenderPaths(
            source_full_dir=directories["source-full"],
            editable_full_dir=directories["editable-full"],
            source_geometry_dir=directories["source-geometry"],
            editable_geometry_dir=directories["editable-geometry"],
            comparison_dir=directories["comparison"],
        )
        for slide_ids in ((), ("S01", "S01")):
            with self.subTest(slide_ids=slide_ids):
                report = module.compare_render_sets(paths, slide_ids, self.config)
                self.assertFalse(report.passed)
                self.assertIn(
                    "visual_mismatch",
                    {failure.code for failure in report.failures},
                )

    def test_summary_write_failure_retains_complete_slide_evidence_without_success(self):
        module = self._visual()
        directories = {}
        for name in (
            "source-full",
            "editable-full",
            "source-geometry",
            "editable-geometry",
            "comparison",
        ):
            directories[name] = self.root / ("summary-failure-" + name)
            directories[name].mkdir()
        for name, directory in directories.items():
            if name != "comparison":
                Image.new("L", (1280, 720), color=0).save(directory / "S01.png")
        paths = module.RenderPaths(
            source_full_dir=directories["source-full"],
            editable_full_dir=directories["editable-full"],
            source_geometry_dir=directories["source-geometry"],
            editable_geometry_dir=directories["editable-geometry"],
            comparison_dir=directories["comparison"],
        )
        real_write_json = module.atomic_write_json

        def fail_summary(path, value):
            if Path(path).name == "visual-summary.json":
                raise EditableError("candidate_write_failed", "summary unavailable")
            return real_write_json(path, value)

        with mock.patch.object(module, "atomic_write_json", side_effect=fail_summary):
            with self.assertRaisesRegex(EditableError, "summary unavailable"):
                module.compare_render_sets(paths, ("S01",), self.config)
        self.assertFalse((directories["comparison"] / "visual-summary.json").exists())
        self.assertTrue((directories["comparison"] / "S01-full-diff.png").is_file())
        self.assertTrue((directories["comparison"] / "S01-geometry-diff.png").is_file())
        self.assertTrue((directories["comparison"] / "S01-tiles.json").is_file())

    def test_evidence_and_render_set_summary_are_written_in_slide_order(self):
        module = self._visual()
        directories = {}
        for name in (
            "source-full",
            "editable-full",
            "source-geometry",
            "editable-geometry",
            "comparison",
        ):
            directories[name] = self.root / name
            directories[name].mkdir()
        for slide_id in ("S01", "S02"):
            for name in directories:
                if name != "comparison":
                    Image.new("L", (1280, 720), color=0).save(
                        directories[name] / (slide_id + ".png")
                    )
        paths = module.RenderPaths(
            source_full_dir=directories["source-full"],
            editable_full_dir=directories["editable-full"],
            source_geometry_dir=directories["source-geometry"],
            editable_geometry_dir=directories["editable-geometry"],
            comparison_dir=directories["comparison"],
        )
        report = module.compare_render_sets(paths, ("S01", "S02"), self.config)
        self.assertTrue(report.passed)
        self.assertEqual([slide.slide_id for slide in report.slides], ["S01", "S02"])
        summary = json.loads((directories["comparison"] / "visual-summary.json").read_text(encoding="utf-8"))
        self.assertEqual([slide["slide_id"] for slide in summary["slides"]], ["S01", "S02"])
        for slide_id in ("S01", "S02"):
            self.assertTrue((directories["comparison"] / (slide_id + "-full-diff.png")).is_file())
            self.assertTrue((directories["comparison"] / (slide_id + "-geometry-diff.png")).is_file())
            self.assertTrue((directories["comparison"] / (slide_id + "-tiles.json")).is_file())


if __name__ == "__main__":
    unittest.main()
