import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-start" / "scripts"
sys.path.insert(0, str(SCRIPTS))


P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


def _rels(items):
    body = "".join(
        f'<Relationship Id="{rid}" Type="{kind}" Target="{target}"{extra}/>'
        for rid, kind, target, extra in items
    )
    return f'<Relationships xmlns="{PR}">{body}</Relationships>'.encode()


def _slide(text, hidden=False, extra=""):
    show = ' show="0"' if hidden else ""
    runs = (f'<a:r><a:t>{text}</a:t></a:r><a:r><a:t> tail</a:t></a:r>'
            if text else "")
    return (f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"{show}>'
            f'<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/>'
            f'</p:nvSpPr><p:txBody><a:p>{runs}</a:p></p:txBody></p:sp>{extra}'
            f'</p:spTree></p:cSld></p:sld>').encode()


def _deck(path, *, unsafe_name=None, duplicate=False, doctype=False, first_text="first"):
    presentation = (f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
                    '<p:sldId id="300" r:id="rIdB"/><p:sldId id="200" r:id="rIdA"/>'
                    '</p:sldIdLst></p:presentation>').encode()
    pres_rels = _rels([
        ("rIdA", f"{R}/slide", "slides/slide1.xml", ""),
        ("rIdB", f"{R}/slide", "slides/slide2.xml", ""),
    ])
    table = (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="7" name="Data"/>'
             f'</p:nvGraphicFramePr><a:graphic><a:graphicData><a:tbl><a:tr>'
             f'<a:tc><a:txBody><a:p><a:r><a:t>A</a:t></a:r></a:p></a:txBody></a:tc>'
             f'<a:tc><a:txBody><a:p><a:r><a:t>B</a:t></a:r></a:p></a:txBody></a:tc>'
             f'</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
    picture = (f'<p:pic><p:nvPicPr><p:cNvPr id="9" name="Hero"/></p:nvPicPr>'
               f'<p:blipFill><a:blip r:embed="rIdImg"/></p:blipFill></p:pic>')
    note = (f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp>'
            '<p:txBody><a:p><a:r><a:t>speaker note</a:t></a:r></a:p></p:txBody>'
            '</p:sp></p:spTree></p:cSld></p:notes>').encode()
    entries = {
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": pres_rels,
        "ppt/slides/slide1.xml": _slide(first_text),
        "ppt/slides/slide2.xml": _slide("second", hidden=True, extra=table + picture),
        "ppt/slides/_rels/slide2.xml.rels": _rels([
            ("rIdImg", f"{R}/image", "../media/image1.png", ""),
            ("rIdNote", f"{R}/notesSlide", "../notesSlides/notesSlide1.xml", ""),
            ("rIdExt", f"{R}/hyperlink", "https://example.invalid/", ' TargetMode="External"'),
        ]),
        "ppt/notesSlides/notesSlide1.xml": note,
        "ppt/media/image1.png": b"not-a-real-png",
    }
    if doctype:
        entries["ppt/slides/slide1.xml"] = b'<!DOCTYPE x [<!ENTITY y "z">]><x>&y;</x>'
    if unsafe_name:
        entries[unsafe_name] = b"bad"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("ppt/presentation.xml", presentation)


class SourceIntakeTests(unittest.TestCase):
    def test_package_root_relationship_targets_are_package_uris(self):
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            with zipfile.ZipFile(source) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            entries["ppt/_rels/presentation.xml.rels"] = entries["ppt/_rels/presentation.xml.rels"].replace(b'Target="slides/', b'Target="/ppt/slides/')
            entries["ppt/slides/_rels/slide2.xml.rels"] = entries["ppt/slides/_rels/slide2.xml.rels"].replace(b'Target="../media/', b'Target="/ppt/media/')
            with zipfile.ZipFile(source, "w") as archive:
                for name, data in entries.items():
                    archive.writestr(name, data)
            result = extract_pptx(source)
            self.assertEqual(["ppt/slides/slide2.xml", "ppt/slides/slide1.xml"], [slide["part"] for slide in result["slides"]])
            self.assertEqual("rIdImg", result["slides"][0]["objects"][0]["relationship_id"])

    def test_relationship_targets_reject_unsafe_root_uris(self):
        from _source_intake import _resolve_target

        for target in ("//server/ppt/slide.xml", "/../escape.xml", "C:/ppt/slide.xml", "https://example.invalid/slide.xml", "/ppt/../../escape.xml", "/ppt\\slide.xml"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "unsafe"):
                _resolve_target("ppt/presentation.xml", target)

    def test_rejects_encoded_entities_dangling_references_and_corrupt_roots(self):
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            with zipfile.ZipFile(source) as archive:
                original = {name: archive.read(name) for name in archive.namelist()}
            encoded = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY e "expanded">]><x>&e;</x>'
            cases = [
                ({"ppt/slides/slide1.xml": encoded.encode("utf-16-le")}, "DOCTYPE"),
                ({"ppt/slides/slide1.xml": encoded.encode("utf-16-be")}, "DOCTYPE"),
                ({"ppt/unused.xml": encoded.encode("utf-16-le")}, "DOCTYPE"),
                ({"ppt/slides/_rels/slide2.xml.rels": None}, "missing.*relationship"),
                ({"ppt/media/image1.png": None}, "missing.*part"),
                ({"ppt/slides/slide1.xml": b"<notASlide/>"}, "root"),
                ({"ppt/notesSlides/notesSlide1.xml": b"<notNotes/>"}, "root"),
                ({"ppt/_rels/presentation.xml.rels": b"<notRelationships/>"}, "root"),
                ({"ppt/presentation.xml": original["ppt/presentation.xml"].replace(b"p:presentation", b"p:wrong")}, "root"),
                ({"ppt/presentation.xml": original["ppt/presentation.xml"].replace(b'<p:sldId id="300" r:id="rIdB"/>', b'').replace(b'<p:sldId id="200" r:id="rIdA"/>', b'')}, "empty"),
                ({"ppt/presentation.xml": original["ppt/presentation.xml"].replace(b'id="200"', b'id="300"')}, "duplicate"),
                ({"ppt/presentation.xml": original["ppt/presentation.xml"].replace(b'r:id="rIdA"', b'r:id="rIdB"')}, "duplicate"),
            ]
            for changes, message in cases:
                with self.subTest(changes=list(changes), message=message):
                    with zipfile.ZipFile(source, "w") as archive:
                        for name, data in dict(original, **changes).items():
                            if data is not None:
                                archive.writestr(name, data)
                    before = source.read_bytes()
                    with self.assertRaisesRegex(ValueError, message):
                        extract_pptx(source)
                    self.assertEqual(before, source.read_bytes())

    def test_accepts_utf16_xml_without_declarations(self):
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            with zipfile.ZipFile(source) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            for encoding in ("utf-16-le", "utf-16-be"):
                with self.subTest(encoding=encoding):
                    with zipfile.ZipFile(source, "w") as archive:
                        for name, data in entries.items():
                            if name == "ppt/slides/slide1.xml":
                                data = ('<?xml version="1.0" encoding="UTF-16"?>' + data.decode("utf-8")).encode(encoding)
                            archive.writestr(name, data)
                    self.assertEqual(["first tail"], extract_pptx(source)["slides"][1]["texts"])

    def test_source_snapshot_is_bounded_before_read(self):
        import _source_intake

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            with patch.object(_source_intake, "MAX_SOURCE_BYTES", 1, create=True):
                with patch.object(Path, "open", side_effect=AssertionError("source opened before size check")):
                    with self.assertRaisesRegex(ValueError, "source.*budget"):
                        _source_intake.extract_pptx(source)

    def test_whitespace_breaks_and_chart_smartart_ole_group_metadata(self):
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            with zipfile.ZipFile(source) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            chart = '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="11" name="Chart"/></p:nvGraphicFramePr><a:graphic><a:graphicData uri="chart"><c:chart xmlns:c="urn:chart" r:id="chart1"/></a:graphicData></a:graphic></p:graphicFrame>'
            smartart = '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="12" name="Diagram"/></p:nvGraphicFramePr><a:graphic><a:graphicData uri="diagram"><d:relIds xmlns:d="urn:diagram" r:dm="dm1" r:lo="lo1" r:qs="qs1" r:cs="cs1"/></a:graphicData></a:graphic></p:graphicFrame>'
            ole = '<p:oleObj r:id="ole1"/>'
            group = '<p:grpSp><p:nvGrpSpPr><p:cNvPr id="13" name="Group"/></p:nvGrpSpPr></p:grpSp>'
            line = '<p:sp><p:txBody><a:p><a:r><a:t xml:space="preserve">  leading </a:t></a:r><a:br/><a:r><a:t>trailing  </a:t></a:r></a:p></p:txBody></p:sp>'
            entries["ppt/slides/slide1.xml"] = _slide("", extra=line + chart + smartart + ole + group)
            entries["ppt/slides/_rels/slide1.xml.rels"] = _rels([
                (rid, f"{R}/{kind}", f"../objects/{rid}.bin", "")
                for rid, kind in [("chart1", "chart"), ("dm1", "diagramData"), ("lo1", "diagramLayout"), ("qs1", "diagramQuickStyle"), ("cs1", "diagramColors"), ("ole1", "oleObject")]
            ])
            for rid in ["chart1", "dm1", "lo1", "qs1", "cs1", "ole1"]:
                entries[f"ppt/objects/{rid}.bin"] = b"opaque inventory-only object"
            with zipfile.ZipFile(source, "w") as archive:
                for name, data in entries.items():
                    archive.writestr(name, data)
            slide = extract_pptx(source)["slides"][1]
            self.assertEqual(["  leading \ntrailing  "], slide["texts"])
            self.assertEqual({"chart", "smartart", "ole", "group"}, {obj["type"] for obj in slide["objects"]})
            self.assertEqual({"dm1", "lo1", "qs1", "cs1"}, {obj["relationship_id"] for obj in slide["objects"] if obj["type"] == "smartart"})
            self.assertTrue(slide["warnings"])

    def test_relationship_order_digest_content_notes_hidden_objects_and_warnings(self):
        """Catches sorting by slide filename or dropping content/object metadata."""
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source)
            original = source.read_bytes()
            result = extract_pptx(source)

            self.assertEqual(1, result["schema_version"])
            self.assertEqual("pptx_source_inventory", result["kind"])
            self.assertEqual({"name": "source.pptx", "sha256": hashlib.sha256(original).hexdigest(),
                              "size_bytes": len(original)}, result["source"])
            self.assertEqual(2, result["slide_count"])
            self.assertEqual(["ppt/slides/slide2.xml", "ppt/slides/slide1.xml"],
                             [slide["part"] for slide in result["slides"]])
            self.assertEqual(["SRC-S001", "SRC-S002"],
                             [slide["source_slide_id"] for slide in result["slides"]])
            first = result["slides"][0]
            self.assertEqual(1, first["position"])
            self.assertTrue(first["hidden"])
            self.assertIn("second tail", first["texts"])
            self.assertEqual([["A", "B"]], first["tables"][0]["rows"])
            self.assertEqual(["speaker note"], first["notes"])
            self.assertTrue(any(obj["type"] == "image" and obj["relationship_id"] == "rIdImg"
                                for obj in first["objects"]))
            self.assertTrue(any(w["code"] == "VISUAL_REVIEW_REQUIRED" for w in first["warnings"]))
            self.assertEqual(original, source.read_bytes())

    def test_textless_slide_has_visual_review_warning(self):
        """Catches inventories that silently treat no extracted text as understood."""
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pptx"
            _deck(source, first_text="")
            result = extract_pptx(source)
            textless = result["slides"][1]
            self.assertEqual([], textless["texts"])
            self.assertTrue(any(w["code"] == "NO_EXTRACTABLE_TEXT"
                                for w in textless["warnings"]))

    def test_rejects_missing_slide_relationship_and_oversized_member(self):
        """Catches guessed slide paths and reads beyond the per-member budget."""
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            missing = folder / "missing.pptx"
            _deck(missing)
            with zipfile.ZipFile(missing, "w", zipfile.ZIP_STORED) as archive:
                archive.writestr("ppt/presentation.xml",
                                 f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
                                 '<p:sldId id="1" r:id="noSuchRel"/></p:sldIdLst></p:presentation>')
                archive.writestr("ppt/_rels/presentation.xml.rels", _rels([]))
            with self.assertRaisesRegex(ValueError, "missing slide relationship"):
                extract_pptx(missing)

            oversized = folder / "oversized.pptx"
            with zipfile.ZipFile(oversized, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("oversized.bin", b"x" * (32 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "32 MiB"):
                extract_pptx(oversized)

    def test_rejects_unsafe_member_duplicate_doctype_and_wrong_extension(self):
        """Catches traversal, ambiguous ZIP members, active XML declarations, and .ppt input."""
        from _source_intake import extract_pptx

        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            cases = [("unsafe.pptx", {"unsafe_name": "../escape"}, "unsafe package path"),
                     ("noncanonical.pptx", {"unsafe_name": "ppt//odd.xml"}, "unsafe package path"),
                     ("duplicate.pptx", {"duplicate": True}, "duplicate"),
                     ("doctype.pptx", {"doctype": True}, "DOCTYPE"),
                     ("old.ppt", {}, "PPTX")]
            for name, kwargs, message in cases:
                source = folder / name
                _deck(source, **kwargs)
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                    extract_pptx(source)

    def test_cli_validates_before_exclusive_output_and_never_overwrites(self):
        """Catches partial output on failure and accidental replacement of an existing file."""
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "source.pptx"
            output = folder / "inventory.json"
            _deck(source)
            original = source.read_bytes()
            command = [sys.executable, str(SCRIPTS / "ppt_source_intake.py"),
                       "--source", str(source), "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("pptx_source_inventory", json.loads(output.read_text("utf-8"))["kind"])
            prior = output.read_bytes()
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(0, repeated.returncode)
            self.assertEqual(prior, output.read_bytes())
            self.assertEqual(original, source.read_bytes())

            bad = folder / "bad.pptx"
            bad.write_bytes(b"not a zip")
            absent = folder / "absent.json"
            failed = subprocess.run([*command[:2], "--source", str(bad), "--output", str(absent)],
                                    capture_output=True, text=True)
            self.assertNotEqual(0, failed.returncode)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
