"""Secure SVG-tree preflight for the editable DrawingML subset."""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import re
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from defusedxml import ElementTree as DET

from .contract import (
    RunContext,
    SlideSource,
    StoryboardSlide,
    validate_safe_regular_file,
)
from .errors import EditableError
from .model import (
    Bounds,
    DeckPlan,
    Failure,
    ResolvedStyle,
    SlidePlan,
    SpeakerNotes,
    SvgNode,
)


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_SUPPORTED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "title",
        "desc",
    }
)
_COMMON_ATTRIBUTES = frozenset({"id", "data-source-id"})
_STYLE_ATTRIBUTES = frozenset(
    {
        "fill",
        "stroke",
        "stroke-width",
        "fill-opacity",
        "stroke-opacity",
        "font-family",
        "font-size",
        "font-weight",
        "letter-spacing",
        "text-anchor",
    }
)
_LEAF_STYLE_ATTRIBUTES = _STYLE_ATTRIBUTES | {"opacity"}
_ALLOWED_ATTRIBUTES = {
    "svg": frozenset({"viewBox", "width", "height", "font-family"}),
    "g": _COMMON_ATTRIBUTES | _STYLE_ATTRIBUTES,
    "path": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"d"},
    "rect": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"x", "y", "width", "height"},
    "circle": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"cx", "cy", "r"},
    "ellipse": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"cx", "cy", "rx", "ry"},
    "line": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"x1", "y1", "x2", "y2"},
    "polyline": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"points"},
    "polygon": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"points"},
    "text": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"x", "y", "xml:space"},
    "tspan": _COMMON_ATTRIBUTES | _LEAF_STYLE_ATTRIBUTES | {"x", "dy", "xml:space"},
    "title": frozenset(),
    "desc": frozenset(),
}
_VISIBLE_ELEMENTS = frozenset(
    {"g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"}
)
_NUMBER_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?:px)?$"
)
_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class DeckPreflightError(Exception):
    def __init__(self, failures: Sequence[Failure]) -> None:
        self.failures = tuple(failures)
        super().__init__("{} SVG preflight failures".format(len(self.failures)))


def _default_path_bounds_parser(data: str) -> Bounds:
    from .path_parser import parse_path, path_bounds

    return path_bounds(parse_path(data))


def _default_text_flattener(element, style: ResolvedStyle, tree_path: str):
    from .text_layout import flatten_text_lines

    return flatten_text_lines(element, style, tree_path)


def local_name(tag: str) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _error(
    code: str,
    message: str,
    *,
    slide_id: Optional[str] = None,
    tree_path: Optional[str] = None,
    element_type: Optional[str] = None,
) -> EditableError:
    return EditableError(
        code,
        message,
        slide_id=slide_id,
        svg_tree_path=tree_path,
        element_type=element_type,
        remediation="make the SVG conform to the ppt-editable schema-v1 subset",
    )


def _require_svg_element(element, slide_id: str, tree_path: str) -> str:
    tag = element.tag
    if not isinstance(tag, str) or not tag.startswith("{") or "}" not in tag:
        namespace = None
        name = local_name(tag)
    else:
        namespace, name = tag[1:].split("}", 1)
    if namespace != SVG_NAMESPACE or not name or "}" in name:
        raise _error(
            "svg_element_unsupported",
            "every SVG element must use the exact SVG namespace",
            slide_id=slide_id,
            tree_path=tree_path,
            element_type=name,
        )
    return name


def _attribute_map(element) -> Mapping[str, str]:
    result = {}
    for raw_name, value in element.attrib.items():
        if raw_name.startswith("{"):
            namespace, name = raw_name[1:].split("}", 1)
            if namespace == XML_NAMESPACE and name == "space":
                name = "xml:space"
            else:
                raise _error(
                    "svg_attribute_unsupported",
                    "foreign namespaced SVG attributes are forbidden",
                )
        else:
            name = raw_name
        if name in result:
            raise _error("svg_attribute_unsupported", "duplicate normalized SVG attribute")
        result[name] = value
    return result


def _validate_attributes(
    kind: str,
    attributes: Mapping[str, str],
    *,
    slide_id: str,
    tree_path: str,
) -> None:
    allowed = _ALLOWED_ATTRIBUTES[kind]
    for name, value in attributes.items():
        if name not in allowed:
            raise _error(
                "svg_attribute_unsupported",
                "unsupported {} attribute: {}".format(kind, name),
                slide_id=slide_id,
                tree_path=tree_path,
                element_type=kind,
            )
        lowered = value.lower()
        if name in ("href", "xlink:href") or "url(" in lowered or "://" in lowered or lowered.startswith("file:"):
            raise _error(
                "svg_external_reference",
                "external SVG references are forbidden",
                slide_id=slide_id,
                tree_path=tree_path,
                element_type=kind,
            )

def _number(
    value: Optional[str],
    *,
    default: Optional[float] = None,
    code: str = "svg_coordinate_invalid",
) -> float:
    if value is None:
        if default is None:
            raise _error(code, "required numeric SVG attribute is missing")
        return default
    if not isinstance(value, str) or _NUMBER_RE.fullmatch(value.strip()) is None:
        raise _error(code, "invalid SVG numeric value: {!r}".format(value))
    normalized = value.strip()
    if normalized.endswith("px"):
        normalized = normalized[:-2]
    parsed = float(normalized)
    if not math.isfinite(parsed):
        raise _error(code, "SVG numeric value must be finite")
    try:
        decimal = Decimal(normalized)
    except InvalidOperation as exc:
        raise _error(code, "SVG numeric value is invalid") from exc
    if decimal != 0 and parsed == 0.0:
        raise _error(code, "SVG numeric value is outside supported float precision")
    return parsed


def _opacity(value: Optional[str], default: float) -> float:
    parsed = _number(value, default=default, code="svg_attribute_unsupported")
    if parsed < 0 or parsed > 1:
        raise _error("svg_attribute_unsupported", "opacity must be between zero and one")
    return parsed


def _paint(value: Optional[str], default: Optional[str]) -> Optional[str]:
    if value is None:
        return default
    if value == "none":
        return None
    if _COLOR_RE.fullmatch(value) is None:
        if "url(" in value.lower():
            raise _error("svg_external_reference", "paint servers are forbidden")
        raise _error("svg_attribute_unsupported", "paint must be #RRGGBB or none")
    return "#" + value[1:].upper()


def _validate_font_family(value: Optional[str]) -> None:
    if value is None:
        return
    if "\\" in value or ";" in value:
        raise _error("svg_attribute_unsupported", "font-family escapes and declarations are unsupported")
    tokens = []
    buffer = []
    quote = None
    for character in value:
        if quote is not None:
            buffer.append(character)
            if character == quote:
                quote = None
        elif character in ("'", '"'):
            buffer.append(character)
            quote = character
        elif character == ",":
            tokens.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(character)
    if quote is not None:
        raise _error("svg_attribute_unsupported", "font-family quoting is invalid")
    tokens.append("".join(buffer).strip())
    for token in tokens:
        if not token:
            raise _error("svg_attribute_unsupported", "font-family contains an empty name")
        if token[0] in ("'", '"'):
            if len(token) < 3 or token[-1] != token[0] or token[0] in token[1:-1]:
                raise _error("svg_attribute_unsupported", "quoted font-family token is invalid")
        elif "'" in token or '"' in token:
            raise _error("svg_attribute_unsupported", "font-family token mixes quoted and unquoted syntax")


def resolve_style(
    parent: ResolvedStyle,
    element_name: str,
    attributes: Mapping[str, str],
) -> ResolvedStyle:
    fill = _paint(attributes.get("fill"), parent.fill)
    stroke = _paint(attributes.get("stroke"), parent.stroke)
    stroke_width = _number(
        attributes.get("stroke-width"),
        default=parent.stroke_width,
        code="svg_attribute_unsupported",
    )
    if stroke_width < 0:
        raise _error("svg_attribute_unsupported", "stroke width cannot be negative")
    inherited_fill_opacity = _opacity(
        attributes.get("fill-opacity"), parent.fill_opacity
    )
    inherited_stroke_opacity = _opacity(
        attributes.get("stroke-opacity"), parent.stroke_opacity
    )
    leaf_opacity = _opacity(attributes.get("opacity"), 1.0)
    font_size = _number(
        attributes.get("font-size"),
        default=parent.font_size if parent.font_size is not None else 16.0,
        code="svg_attribute_unsupported",
    )
    if font_size <= 0:
        raise _error("svg_attribute_unsupported", "font size must be positive")
    letter_spacing = _number(
        attributes.get("letter-spacing"),
        default=parent.letter_spacing,
        code="svg_attribute_unsupported",
    )
    anchor = attributes.get("text-anchor", parent.text_anchor)
    if anchor not in ("start", "middle", "end"):
        raise _error("svg_attribute_unsupported", "unsupported text-anchor")
    weight = attributes.get("font-weight", parent.font_weight or "400")
    if weight not in ("normal", "bold"):
        try:
            numeric_weight = int(weight)
        except (TypeError, ValueError) as exc:
            raise _error("svg_attribute_unsupported", "invalid font weight") from exc
        if numeric_weight < 100 or numeric_weight > 900 or numeric_weight % 100:
            raise _error("svg_attribute_unsupported", "invalid font weight")
        weight = str(numeric_weight)
    family = attributes.get("font-family", parent.font_family)
    _validate_font_family(family)
    source_id = attributes.get("data-source-id", parent.data_source_id)
    for value in (family, source_id):
        if value is not None and any(ord(character) < 32 for character in value):
            raise _error("svg_attribute_unsupported", "control character in SVG metadata")
    is_leaf = element_name not in ("svg", "g")
    return ResolvedStyle(
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        fill_opacity=inherited_fill_opacity * leaf_opacity if is_leaf else inherited_fill_opacity,
        stroke_opacity=inherited_stroke_opacity * leaf_opacity if is_leaf else inherited_stroke_opacity,
        opacity=leaf_opacity,
        font_family=family,
        font_size=font_size,
        font_weight=weight,
        letter_spacing=letter_spacing,
        text_anchor=anchor,
        data_source_id=source_id,
    )


def _points(value: Optional[str], minimum: int) -> Tuple[Tuple[float, float], ...]:
    if not value:
        raise _error("svg_coordinate_invalid", "points are missing")
    tokens = [token for token in re.split(r"[\s,]+", value.strip()) if token]
    if len(tokens) % 2 or len(tokens) < minimum * 2:
        raise _error("svg_coordinate_invalid", "invalid point list")
    numbers = tuple(_number(token) for token in tokens)
    return tuple((numbers[index], numbers[index + 1]) for index in range(0, len(numbers), 2))


def _validated_bounds(value: Bounds) -> Bounds:
    coordinates = (value.left, value.top, value.right, value.bottom)
    if (
        not all(math.isfinite(coordinate) for coordinate in coordinates)
        or value.left > value.right
        or value.top > value.bottom
    ):
        raise _error("svg_coordinate_invalid", "derived SVG bounds are not finite")
    return value


def _bounds(
    kind: str,
    attributes: Mapping[str, str],
    style: ResolvedStyle,
    path_bounds_parser: Callable[[str], Bounds],
) -> Bounds:
    if kind == "rect":
        x = _number(attributes.get("x"), default=0.0)
        y = _number(attributes.get("y"), default=0.0)
        width = _number(attributes.get("width"))
        height = _number(attributes.get("height"))
        if width <= 0 or height <= 0:
            raise _error("svg_coordinate_invalid", "rect dimensions must be positive")
        result = Bounds(x, y, x + width, y + height)
    elif kind == "circle":
        cx = _number(attributes.get("cx"))
        cy = _number(attributes.get("cy"))
        radius = _number(attributes.get("r"))
        if radius <= 0:
            raise _error("svg_coordinate_invalid", "circle radius must be positive")
        result = Bounds(cx - radius, cy - radius, cx + radius, cy + radius)
    elif kind == "ellipse":
        cx = _number(attributes.get("cx"))
        cy = _number(attributes.get("cy"))
        rx = _number(attributes.get("rx"))
        ry = _number(attributes.get("ry"))
        if rx <= 0 or ry <= 0:
            raise _error("svg_coordinate_invalid", "ellipse radii must be positive")
        result = Bounds(cx - rx, cy - ry, cx + rx, cy + ry)
    elif kind == "line":
        x1 = _number(attributes.get("x1"))
        y1 = _number(attributes.get("y1"))
        x2 = _number(attributes.get("x2"))
        y2 = _number(attributes.get("y2"))
        result = Bounds(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    elif kind in ("polygon", "polyline"):
        points = _points(attributes.get("points"), 3 if kind == "polygon" else 2)
        result = Bounds(
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )
    elif kind == "text":
        x = _number(attributes.get("x"), default=0.0)
        y = _number(attributes.get("y"), default=0.0)
        size = style.font_size or 16.0
        result = Bounds(x, y - size, x + size, y + size * 0.5)
    elif kind == "path":
        data = attributes.get("d")
        if not data:
            raise _error("svg_path_invalid", "path d is missing")
        result = path_bounds_parser(data)
    else:
        raise _error("svg_element_unsupported", "unsupported visible SVG element")
    expansion = style.stroke_width / 2.0 if style.stroke is not None else 0.0
    return _validated_bounds(result.expanded(expansion))


def _parse_children(
    parent,
    parent_style: ResolvedStyle,
    parent_path: str,
    slide_id: str,
    path_bounds_parser: Callable[[str], Bounds],
    text_flattener: Callable,
) -> Tuple[SvgNode, ...]:
    counters: Dict[str, int] = {}
    nodes = []
    for child in parent:
        kind = _require_svg_element(child, slide_id, parent_path)
        if kind in ("title", "desc"):
            if parent_path != "/svg[1]":
                raise _error(
                    "svg_element_unsupported",
                    "title and desc are allowed only at the SVG root",
                    slide_id=slide_id,
                    tree_path=parent_path,
                    element_type=kind,
                )
            continue
        if kind not in _SUPPORTED_ELEMENTS or kind not in _VISIBLE_ELEMENTS:
            raise _error(
                "svg_element_unsupported",
                "unsupported SVG element: {}".format(kind),
                slide_id=slide_id,
                tree_path=parent_path,
                element_type=kind,
            )
        counters[kind] = counters.get(kind, 0) + 1
        tree_path = "{}/{}[{}]".format(parent_path, kind, counters[kind])
        attributes = _attribute_map(child)
        _validate_attributes(
            kind,
            attributes,
            slide_id=slide_id,
            tree_path=tree_path,
        )
        style = resolve_style(parent_style, kind, attributes)
        if kind == "g":
            children = _parse_children(
                child,
                style,
                tree_path,
                slide_id,
                path_bounds_parser,
                text_flattener,
            )
            if not children:
                raise _error(
                    "svg_group_empty",
                    "empty SVG group",
                    slide_id=slide_id,
                    tree_path=tree_path,
                    element_type=kind,
                )
            bounds = children[0].bounds
            for nested in children[1:]:
                bounds = bounds.union(nested.bounds)
            bounds = _validated_bounds(bounds)
            node = SvgNode(
                kind=kind,
                tree_path=tree_path,
                style=style,
                bounds=bounds,
                attributes=tuple(sorted(attributes.items())),
                children=children,
            )
        else:
            if kind == "text":
                text_lines = text_flattener(child, style, tree_path)
                bounds = text_lines[0].bounds
                for text_line in text_lines[1:]:
                    bounds = bounds.union(text_line.bounds)
                bounds = _validated_bounds(bounds)
                node = SvgNode(
                    kind=kind,
                    tree_path=tree_path,
                    style=style,
                    bounds=bounds,
                    attributes=tuple(sorted(attributes.items())),
                    text_lines=text_lines,
                )
            else:
                node = SvgNode(
                    kind=kind,
                    tree_path=tree_path,
                    style=style,
                    bounds=_bounds(kind, attributes, style, path_bounds_parser),
                    attributes=tuple(sorted(attributes.items())),
                )
        nodes.append(node)
    return tuple(nodes)


def _canvas(root, attributes: Mapping[str, str], slide_id: str) -> None:
    if attributes.get("viewBox") != "0 0 1280 720":
        raise _error(
            "svg_canvas_invalid",
            'SVG viewBox must be exactly "0 0 1280 720"',
            slide_id=slide_id,
        )
    if "width" in attributes and attributes["width"] != "1280":
        raise _error(
            "svg_canvas_invalid",
            'SVG width must be exactly "1280" when present',
            slide_id=slide_id,
        )
    if "height" in attributes and attributes["height"] != "720":
        raise _error(
            "svg_canvas_invalid",
            'SVG height must be exactly "720" when present',
            slide_id=slide_id,
        )


def _source_xml_bytes(source: SlideSource, source_bytes: Optional[bytes]) -> bytes:
    if source_bytes is not None:
        if not isinstance(source_bytes, bytes):
            raise TypeError("source_bytes must be bytes")
        return source_bytes
    try:
        return Path(source.path).read_bytes()
    except OSError as exc:
        raise _error(
            "source_unreadable",
            "SVG source cannot be read",
            slide_id=source.slide_id,
        ) from exc


def _decode_and_validate_xml_source(data: bytes, slide_id: str) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _error(
            "svg_xml_invalid",
            "SVG source must use UTF-8 encoding",
            slide_id=slide_id,
        ) from exc
    if "\x00" in text:
        raise _error(
            "svg_xml_invalid",
            "SVG source must not contain NUL characters",
            slide_id=slide_id,
        )
    for metadata_tag in ("title", "desc"):
        pattern = (
            r"<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?{}\b[^>]*>"
            r"(?:(?!</(?:[A-Za-z_][A-Za-z0-9_.-]*:)?{}\s*>).)*<!--"
        ).format(metadata_tag, metadata_tag)
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            raise _error(
                "svg_xml_invalid",
                "SVG title and desc must contain plain text without comments",
                slide_id=slide_id,
            )
    scan_text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for match in re.finditer(r"<\?([A-Za-z_:][A-Za-z0-9_.:-]*)", scan_text):
        target = match.group(1).lower()
        if target != "xml" or scan_text[: match.start()].strip():
            raise _error(
                "svg_external_reference",
                "XML processing instructions are forbidden",
                slide_id=slide_id,
            )
    if re.search(r"<!", scan_text, flags=re.IGNORECASE):
        raise _error(
            "svg_xml_invalid",
            "SVG declarations, DTDs, comments, and CDATA are forbidden",
            slide_id=slide_id,
        )
    declaration = re.match(r"<\?xml\s+([^?]+)\?>", text)
    if declaration:
        encoding = re.search(
            r"\bencoding\s*=\s*['\"]([^'\"]+)['\"]",
            declaration.group(1),
            flags=re.IGNORECASE,
        )
        if encoding and encoding.group(1).lower().replace("-", "") != "utf8":
            raise _error(
                "svg_xml_invalid",
                "SVG XML declaration must use UTF-8",
                slide_id=slide_id,
            )
    return text


def parse_svg_slide(
    source: SlideSource,
    notes: SpeakerNotes,
    source_bytes: Optional[bytes] = None,
    *,
    path_bounds_parser: Optional[Callable[[str], Bounds]] = None,
    text_flattener: Optional[Callable] = None,
) -> SlidePlan:
    if path_bounds_parser is None:
        path_bounds_parser = _default_path_bounds_parser
    if text_flattener is None:
        text_flattener = _default_text_flattener
    if not callable(path_bounds_parser) or not callable(text_flattener):
        raise TypeError("path_bounds_parser and text_flattener must be callable")
    data = _source_xml_bytes(source, source_bytes)
    text = _decode_and_validate_xml_source(data, source.slide_id)
    try:
        root = DET.fromstring(text)
    except Exception as exc:
        raise _error("svg_xml_invalid", "SVG XML cannot be parsed", slide_id=source.slide_id) from exc
    if root.tag != "{{{}}}svg".format(SVG_NAMESPACE):
        raise _error("svg_element_unsupported", "root must be a namespaced SVG", slide_id=source.slide_id)
    attributes = _attribute_map(root)
    _validate_attributes("svg", attributes, slide_id=source.slide_id, tree_path="/svg[1]")
    _canvas(root, attributes, source.slide_id)
    base_style = ResolvedStyle(
        fill="#000000",
        stroke=None,
        stroke_width=0.0,
        fill_opacity=1.0,
        stroke_opacity=1.0,
        opacity=1.0,
        font_family=None,
        font_size=16.0,
        font_weight="400",
        letter_spacing=0.0,
        text_anchor="start",
        data_source_id=None,
    )
    root_style = resolve_style(base_style, "svg", attributes)
    metadata_values = {"title": None, "desc": None}
    for child in root:
        kind = _require_svg_element(child, source.slide_id, "/svg[1]")
        if kind not in metadata_values:
            continue
        child_attributes = _attribute_map(child)
        _validate_attributes(
            kind,
            child_attributes,
            slide_id=source.slide_id,
            tree_path="/svg[1]/{}[1]".format(kind),
        )
        if len(child):
            raise _error(
                "svg_element_unsupported",
                "SVG metadata must contain plain text only",
                slide_id=source.slide_id,
                tree_path="/svg[1]/{}[1]".format(kind),
                element_type=kind,
            )
        if metadata_values[kind] is not None:
            raise _error(
                "svg_attribute_unsupported",
                "duplicate SVG {} metadata".format(kind),
                slide_id=source.slide_id,
                tree_path="/svg[1]",
                element_type=kind,
            )
        metadata_values[kind] = "".join(child.itertext()).strip() or None
    if metadata_values["title"] is None or metadata_values["desc"] is None:
        raise _error(
            "svg_attribute_unsupported",
            "SVG root requires one nonempty title and desc",
            slide_id=source.slide_id,
            tree_path="/svg[1]",
        )
    nodes = _parse_children(
        root,
        root_style,
        "/svg[1]",
        source.slide_id,
        path_bounds_parser,
        text_flattener,
    )
    if not nodes:
        raise _error(
            "svg_group_empty",
            "SVG page has no visible nodes",
            slide_id=source.slide_id,
            tree_path="/svg[1]",
        )
    title = metadata_values["title"]
    description = metadata_values["desc"]
    return SlidePlan(
        slide_id=source.slide_id,
        source_path=source.path,
        title=title,
        description=description,
        nodes=nodes,
        notes=notes,
    )


def preflight_deck(
    context: RunContext,
    sources: Sequence[SlideSource],
    storyboard: Sequence[StoryboardSlide],
    input_snapshot_id: str,
    *,
    path_bounds_parser: Optional[Callable[[str], Bounds]] = None,
    text_flattener: Optional[Callable] = None,
) -> DeckPlan:
    expected_ids = tuple(slide.slide_id for slide in storyboard)
    selected_ids = tuple(source.slide_id for source in sources)
    if (
        not expected_ids
        or len(expected_ids) != len(set(expected_ids))
        or selected_ids != expected_ids
    ):
        raise DeckPreflightError(
            (
                Failure(
                    code="slide_set_invalid",
                    slide_id=None,
                    svg_tree_path=None,
                    element_type=None,
                    message="preflight source set must exactly match storyboard order",
                    remediation="resolve the complete authoritative source set before preflight",
                ),
            )
        )
    storyboard_by_id = {slide.slide_id: slide for slide in storyboard}
    failures = []
    warnings = []
    plans = []
    for source in sources:
        record = storyboard_by_id.get(source.slide_id)
        if record is None:
            failures.append(
                Failure(
                    code="slide_set_invalid",
                    slide_id=source.slide_id,
                    svg_tree_path=None,
                    element_type=None,
                    message="source has no storyboard owner",
                    remediation="align the storyboard and selected source set",
                )
            )
            continue
        for field_name in (
            "assertion_title",
            "audience_takeaway",
            "next_link",
        ):
            value = getattr(record, field_name)
            if not isinstance(value, str) or not value.strip():
                warnings.append(
                    "{}: missing optional note field {}".format(
                        source.slide_id,
                        field_name,
                    )
                )
        notes = SpeakerNotes(
            assertion_title=record.assertion_title,
            audience_takeaway=record.audience_takeaway,
            next_link=record.next_link,
        )
        try:
            if source.owner == "production":
                allowed_root = context.slides_dir
            elif source.owner == "approved_anchor":
                allowed_root = context.samples_dir
            else:
                raise _error(
                    "slide_set_invalid",
                    "unknown source owner",
                    slide_id=source.slide_id,
                )
            expected_path = (context.run_dir / source.relative_path).absolute()
            validated_path = validate_safe_regular_file(
                expected_path,
                (allowed_root,),
            )
            try:
                resolved_source = Path(source.path).resolve(strict=True)
                source_bytes = validated_path.read_bytes()
            except OSError as exc:
                raise _error(
                    "source_unreadable",
                    "source changed while preparing SVG preflight",
                    slide_id=source.slide_id,
                ) from exc
            if validated_path != resolved_source:
                raise _error(
                    "source_path_unsafe",
                    "source identity changed before SVG parsing",
                    slide_id=source.slide_id,
                )
            observed_sha256 = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
            if source.svg_sha256 != observed_sha256:
                raise _error(
                    "source_path_unsafe",
                    "source bytes changed after snapshot resolution",
                    slide_id=source.slide_id,
                )
            safe_source = SlideSource(
                slide_id=source.slide_id,
                path=validated_path,
                relative_path=source.relative_path,
                owner=source.owner,
                svg_sha256=observed_sha256,
            )
            plans.append(
                parse_svg_slide(
                    safe_source,
                    notes,
                    source_bytes,
                    path_bounds_parser=path_bounds_parser,
                    text_flattener=text_flattener,
                )
            )
        except EditableError as exc:
            failures.append(
                Failure(
                    code=exc.code,
                    slide_id=exc.slide_id or source.slide_id,
                    svg_tree_path=exc.svg_tree_path,
                    element_type=exc.element_type,
                    message=exc.message,
                    remediation=exc.remediation,
                )
            )
    if failures:
        raise DeckPreflightError(failures)
    return DeckPlan(
        deck_id=context.deck_id,
        input_snapshot_id=input_snapshot_id,
        slides=tuple(plans),
        warnings=tuple(warnings),
    )
