import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root


ALLOWED = {
    "svg",
    "g",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "path",
    "text",
    "tspan",
    "title",
    "desc",
}


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def numeric_font_size(value: str) -> float:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(?:px)?", value.strip())
    if not match:
        raise ValueError(f"invalid font size: {value}")
    return float(match.group(1))


class SvgContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example_path = skill_root() / "assets" / "examples" / "office-safe-slide.svg"
        self.contract_path = skill_root() / "references" / "svg-contract.md"

    def test_svg_contract_reference_is_complete(self):
        self.assertTrue(self.contract_path.exists())
        text = read_text(self.contract_path).lower()
        for tag in sorted(ALLOWED):
            self.assertRegex(text, rf"`{re.escape(tag)}`", f"svg-contract.md missing allowed tag {tag}")
        for token in (
            "viewbox=\"0 0 1280 720\"",
            "utf-8",
            "unique id",
            "xml escaping",
            "<tspan>",
            "text remains text",
            "source id",
            "<title>",
            "<desc>",
            "foreignobject",
            "script",
            "event handler",
            "external dtd",
            "remote resource",
            "css import",
            "animation",
            "absolute path",
            "browser filter",
        ):
            self.assertIn(token, text, f"svg-contract.md missing {token}")

    def test_example_uses_only_office_safe_standalone_svg(self):
        self.assertTrue(self.example_path.exists())
        raw = read_text(self.example_path)
        lowered = raw.lower()
        self.assertNotIn("<!doctype", lowered)
        self.assertNotIn("<!entity", lowered)
        self.assertNotIn("javascript:", lowered)
        self.assertNotIn("url(", lowered)
        external_url_scan = lowered.replace('xmlns="http://www.w3.org/2000/svg"', "")
        self.assertNotRegex(external_url_scan, r"https?://")
        self.assertNotRegex(raw, r"(?:[A-Za-z]:\\|/(?:Users|home|tmp)/)")

        root = ET.fromstring(raw)
        self.assertEqual(local_name(root.tag), "svg")
        self.assertEqual(root.attrib.get("width"), "1280")
        self.assertEqual(root.attrib.get("height"), "720")
        self.assertEqual(root.attrib.get("viewBox"), "0 0 1280 720")

        ids: set[str] = set()
        tags: list[str] = []
        for element in root.iter():
            tag = local_name(element.tag)
            tags.append(tag)
            self.assertIn(tag, ALLOWED, f"forbidden SVG element: {tag}")
            element_id = element.attrib.get("id")
            if element_id:
                self.assertNotIn(element_id, ids, f"duplicate SVG id: {element_id}")
                ids.add(element_id)
            for raw_name, value in element.attrib.items():
                name = local_name(raw_name).lower()
                lowered_value = value.lower()
                self.assertFalse(name.startswith("on"), f"event handler attribute: {name}")
                if name == "href":
                    self.assertTrue(value.startswith("#"), f"external href: {value}")
                for forbidden in ("javascript:", "http://", "https://", "file:"):
                    self.assertNotIn(forbidden, lowered_value)

        self.assertIn("title", tags)
        self.assertIn("desc", tags)
        self.assertIn("rect", tags)
        self.assertIn("path", tags)
        self.assertIn("tspan", tags)

    def test_example_text_anchors_stay_inside_the_safe_margin(self):
        root = ET.parse(self.example_path).getroot()
        for element in root.iter():
            if local_name(element.tag) not in {"text", "tspan"}:
                continue
            x = element.attrib.get("x")
            y = element.attrib.get("y")
            if x is not None:
                self.assertGreaterEqual(float(x), 64, f"{element.tag} x is outside safe margin")
                self.assertLessEqual(float(x), 1216, f"{element.tag} x is outside safe margin")
            if y is not None:
                self.assertGreaterEqual(float(y), 64, f"{element.tag} y is outside safe margin")
                self.assertLessEqual(float(y), 656, f"{element.tag} y is outside safe margin")

    def test_example_text_reserves_vertical_glyph_extents(self):
        root = ET.parse(self.example_path).getroot()
        for element in root.iter():
            if local_name(element.tag) != "text":
                continue
            size = numeric_font_size(element.attrib["font-size"])
            baseline = float(element.attrib["y"])
            tspans = [child for child in element if local_name(child.tag) == "tspan"]
            for index, tspan in enumerate(tspans):
                if index:
                    baseline += float(tspan.attrib.get("dy", "0"))
                self.assertGreaterEqual(
                    baseline - size,
                    64,
                    f"{element.attrib.get('id')} does not reserve title/text ascent",
                )
                self.assertLessEqual(
                    baseline + size * 0.25,
                    656,
                    f"{element.attrib.get('id')} does not reserve text descent",
                )

    def test_example_text_is_explicit_wrapped_and_readable(self):
        root = ET.parse(self.example_path).getroot()
        text_nodes = [element for element in root.iter() if local_name(element.tag) == "text"]
        self.assertTrue(text_nodes)
        roles: set[str] = set()
        for element in text_nodes:
            role = element.attrib.get("data-role", "body")
            roles.add(role)
            self.assertIn("font-size", element.attrib, "each text element needs explicit font-size")
            size = numeric_font_size(element.attrib["font-size"])
            if role == "title":
                self.assertGreaterEqual(size, 40)
            elif role == "footnote":
                self.assertGreaterEqual(size, 14)
            else:
                self.assertGreaterEqual(size, 20)
            self.assertTrue(
                any(local_name(child.tag) == "tspan" for child in element),
                "text must use explicit tspan wrapping",
            )
        self.assertTrue({"title", "body", "footnote"}.issubset(roles))

        source_nodes = [
            element
            for element in root.iter()
            if element.attrib.get("data-source-id")
        ]
        self.assertTrue(source_nodes)
        self.assertTrue(
            all(
                re.fullmatch(r"SRC-[0-9]+", element.attrib["data-source-id"], re.IGNORECASE)
                for element in source_nodes
            )
        )
        visible_text = " ".join("".join(element.itertext()) for element in text_nodes)
        self.assertNotRegex(
            visible_text,
            re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE),
        )


if __name__ == "__main__":
    unittest.main()
