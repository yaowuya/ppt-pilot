"""Packaged deterministic svg_runtime operations."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from _xml_safety import parse_xml
from _svg_geometry import NUMBER, number, validate_geometry

SVG_NS = "http://www.w3.org/2000/svg"
_ELEMENTS = {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "title", "desc"}
_ATTRIBUTES = {
    "id", "width", "height", "viewBox", "version", "x", "y", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "points", "d", "fill", "fill-rule", "fill-opacity",
    "stroke", "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin",
    "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "opacity",
    "font-family", "font-size", "font-weight", "font-style", "text-anchor",
    "data-role", "data-block-id", "data-source-id", "href",
}
_NUMERIC_ATTRIBUTES = {"width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "font-size", "stroke-width", "stroke-miterlimit", "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity"}


def extract_svg(generator_text: str) -> str:
    """Accept exactly one XML fence and no prose or additional code blocks."""
    if not isinstance(generator_text, str):
        raise ValueError("generator_output_malformed")
    match = re.fullmatch(r"\s*```xml\r?\n(.*?)\r?\n```\s*", generator_text, re.DOTALL)
    if match is None or "```" in match.group(1):
        raise ValueError("generator_output_malformed")
    return match.group(1)


def _validate_svg(svg_text, *, enriched=False):
    if not isinstance(svg_text, str) or re.search(r"<\?(?!xml\s)", svg_text, re.IGNORECASE):
        raise ValueError("svg_contract_failed")
    root = parse_xml(svg_text.encode("utf-8"), "candidate SVG", "{" + SVG_NS + "}svg")
    if any(root.get(key) != value for key, value in (("width", "1280"), ("height", "720"), ("viewBox", "0 0 1280 720"))):
        raise ValueError("svg_contract_failed")
    for name in ("title", "desc"):
        nodes = root.findall("{" + SVG_NS + "}" + name)
        if len(nodes) != 1 or not (nodes[0].text or "").strip() or len(nodes[0]):
            raise ValueError("svg_contract_failed")
    seen_ids = set()
    def visit(element, inherited, parent=None):
        local = element.tag.rsplit("}", 1)[-1]
        if element.tag != "{" + SVG_NS + "}" + local or local not in _ELEMENTS or (local == "svg" and parent is not None):
            raise ValueError("svg_contract_failed")
        if local == "tspan" and parent != "text":
            raise ValueError("svg_contract_failed")
        for key, value in element.attrib.items():
            if key not in _ATTRIBUTES or re.search(r"url\s*\(|(?:https?|file|data|javascript):|[A-Za-z]:[/\\]|(?:^|\s)/(?:home|tmp|Users)/|base64", value, re.IGNORECASE):
                raise ValueError("svg_contract_failed")
            if key == "href" and re.fullmatch(r"#[A-Za-z_][\w.-]*", value) is None:
                raise ValueError("svg_contract_failed")
            if key in _NUMERIC_ATTRIBUTES:
                numeric = number(value)
                if key.endswith("opacity") and not 0 <= numeric <= 1:
                    raise ValueError("svg_contract_failed")
            if key == "stroke-dasharray" and value.strip() != "none":
                # SVG comma-wsp separators must separate complete numbers;
                # empty entries, units and adjacent signed tokens are invalid.
                separator = r"(?:[ \t\r\n]*,[ \t\r\n]*|[ \t\r\n]+)"
                if re.fullmatch(NUMBER + r"(?:" + separator + NUMBER + r")*", value.strip()) is None:
                    raise ValueError("svg_contract_failed")
                if any(number(token) < 0 for token in re.findall(NUMBER, value)):
                    raise ValueError("svg_contract_failed")
            if key == "data-source-id" and (not enriched or local != "g" or _SOURCE_ID.fullmatch(value) is None):
                raise ValueError("fact_source_mismatch")
            if key == "data-block-id" and enriched:
                raise ValueError("fact_source_mismatch")
            if key == "id":
                if value in seen_ids or re.fullmatch(r"s[0-9]+-[A-Za-z0-9_-]+", value) is None:
                    raise ValueError("svg_contract_failed")
                seen_ids.add(value)
        if local not in ("text", "tspan", "title", "desc") and (element.text or "").strip():
            raise ValueError("svg_contract_failed")
        if (element.tail or "").strip():
            raise ValueError("svg_contract_failed")
        validate_geometry(element, inherited)
        attrs = dict(inherited)
        attrs.update(element.attrib)
        for child in element:
            visit(child, attrs, local)
    visit(root, {})
    if fact_source_visible_text_result(svg_text):
        raise ValueError("fact_source_mismatch")
    return root


def validate_candidate(svg_text, expected_block_ids, source_map) -> bytes:
    """Validate, enrich, revalidate and serialize in memory; never write files."""
    if (not isinstance(expected_block_ids, (list, tuple)) or not expected_block_ids
        or any(not isinstance(block, str) or _BLOCK_ID.fullmatch(block) is None for block in expected_block_ids)
        or len(expected_block_ids) != len(set(expected_block_ids))
        or len({block.split("-B")[0] for block in expected_block_ids}) != 1
        or not isinstance(source_map, dict) or set(expected_block_ids) != set(source_map)):
        raise ValueError("fact_source_mismatch")
    root = _validate_svg(svg_text)
    prefix = expected_block_ids[0].split("-B")[0].lower() + "-"
    if any(node.get("id") and not node.get("id").startswith(prefix) for node in root.iter()):
        raise ValueError("svg_contract_failed")
    result = enrich_candidate_source_metadata(svg_text, source_map)
    _validate_svg(result.decode("utf-8"), enriched=True)
    return result

_VISIBLE_INTERNAL_SOURCE_ID = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)


_BLOCK_ID = re.compile(r"S[0-9]+-B[1-9][0-9]*")


_BLOCK_ID_LEAK = re.compile(r"S[0-9]+-B[1-9][0-9]*", re.IGNORECASE)


_SOURCE_ID = re.compile(r"SRC-[0-9]+")


_SOURCE_ID_LEAK = re.compile(r"SRC-[0-9]+", re.IGNORECASE)


def _is_source_attribute(name: str) -> bool:
    local_name = name.rsplit("}", 1)[-1]
    normalized = re.sub(r"[^a-z0-9]", "", local_name.casefold())
    return "source" in normalized


def enrich_candidate_source_metadata(
    svg_text: str,
    ordered_source_ids_by_block: dict[str, list[str]],
) -> bytes:
    """Join transient block IDs to frozen source mappings before candidate I/O."""
    if not isinstance(ordered_source_ids_by_block, dict):
        raise ValueError("fact_source_mismatch")
    for block, sources in ordered_source_ids_by_block.items():
        if (not isinstance(block, str) or _BLOCK_ID.fullmatch(block) is None
            or not isinstance(sources, list)
            or any(not isinstance(source, str) or _SOURCE_ID.fullmatch(source) is None for source in sources)
            or len(sources) != len(set(sources))):
            raise ValueError("fact_source_mismatch")
    try:
        root = parse_xml(svg_text.encode("utf-8"), "candidate SVG")
    except (ET.ParseError, ValueError) as exc:
        raise ValueError("svg_contract_failed") from exc

    block_nodes: dict[str, ET.Element] = {}
    for element in root.iter():
        for name, value in element.attrib.items():
            if (
                _is_source_attribute(name)
                or _BLOCK_ID_LEAK.search(name) is not None
                or _SOURCE_ID_LEAK.search(name) is not None
                or _SOURCE_ID_LEAK.search(value or "") is not None
                or (
                    name != "data-block-id"
                    and _BLOCK_ID_LEAK.search(value or "") is not None
                )
            ):
                raise ValueError("fact_source_mismatch")
        if (
            _SOURCE_ID_LEAK.search(element.text or "") is not None
            or _SOURCE_ID_LEAK.search(element.tail or "") is not None
            or _BLOCK_ID_LEAK.search(element.text or "") is not None
            or _BLOCK_ID_LEAK.search(element.tail or "") is not None
        ):
            raise ValueError("fact_source_mismatch")
        if any(
            name.casefold() == "data-block-id" and name != "data-block-id"
            for name in element.attrib
        ):
            raise ValueError("fact_source_mismatch")
        block_id = element.attrib.get("data-block-id")
        if block_id is None:
            continue
        if element.tag.rsplit("}", 1)[-1] != "g" or _BLOCK_ID.fullmatch(block_id) is None:
            raise ValueError("fact_source_mismatch")
        if block_id in block_nodes:
            raise ValueError("fact_source_mismatch")
        block_nodes[block_id] = element

    if set(block_nodes) != set(ordered_source_ids_by_block):
        raise ValueError("fact_source_mismatch")

    namespace = "http://www.w3.org/2000/svg"
    if root.tag.startswith("{"):
        namespace = root.tag[1:].split("}", 1)[0]
    ET.register_namespace("", namespace)
    group_tag = f"{{{namespace}}}g" if namespace else "g"

    for block_id, node in block_nodes.items():
        source_ids = ordered_source_ids_by_block[block_id]
        if (
            not isinstance(source_ids, list)
            or len(source_ids) != len(set(source_ids))
            or any(
                not isinstance(source_id, str)
                or _SOURCE_ID.fullmatch(source_id) is None
                for source_id in source_ids
            )
        ):
            raise ValueError("fact_source_mismatch")
        del node.attrib["data-block-id"]
        if not source_ids:
            continue
        node.set("data-source-id", source_ids[0])
        current = node
        for source_id in source_ids[1:]:
            children = list(current)
            wrapper = ET.Element(group_tag, {"data-source-id": source_id})
            for child in children:
                current.remove(child)
                wrapper.append(child)
            current.append(wrapper)
            current = wrapper

    return ET.tostring(root, encoding="utf-8", xml_declaration=False) + b"\n"


def fact_source_visible_text_result(svg_text: str):
    try:
        root = parse_xml(svg_text.encode("utf-8"), "candidate SVG")
    except (ET.ParseError, ValueError):
        return "svg_contract_failed"
    visible = " ".join(
        "".join(element.itertext())
        for element in root.iter()
        if isinstance(element.tag, str)
        and element.tag.rsplit("}", 1)[-1] == "text"
    )
    if _VISIBLE_INTERNAL_SOURCE_ID.search(visible):
        return "fact_source_mismatch"
    human_citation_visible = re.search(
        r"(?i)(?:来源\s*[:：]|source\s*:)",
        visible,
    ) is not None
    if human_citation_visible:
        return "fact_source_mismatch"
    if re.search(r"(?:https?://|www\.)", visible, re.IGNORECASE):
        return "fact_source_mismatch"
    return None
