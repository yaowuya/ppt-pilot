"""Recursive SVG text/tspan events and deterministic editable text-box bounds."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata
from typing import List, Sequence, Tuple

from .errors import EditableError
from .model import Bounds, ResolvedStyle, TextLine, TextRun


_VISIBLE_INTERNAL_SOURCE_ID_RE = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)
POWERPOINT_TEXT_BASELINE_OFFSET_PX = 2.0


@dataclass
class _TextEvent:
    text: str
    style: ResolvedStyle
    preserve: bool


@dataclass
class _MutableLine:
    x: float
    y: float
    anchor: str
    events: List[_TextEvent]


def _text_error(message: str, tree_path: str) -> EditableError:
    return EditableError(
        "svg_text_invalid",
        message,
        svg_tree_path=tree_path,
        element_type="text",
        remediation="use scalar absolute x and line-changing dy text positioning",
    )


def _text_number(value: str, tree_path: str) -> float:
    from .svg_parser import _number

    try:
        parsed = _number(value, code="svg_text_invalid")
    except EditableError as exc:
        raise _text_error(exc.message, tree_path) from exc
    if not math.isfinite(parsed):
        raise _text_error("text coordinate must be finite", tree_path)
    lexical = value.strip()
    lexical = lexical[:-2] if lexical.endswith("px") else lexical
    try:
        decimal = Decimal(lexical)
    except InvalidOperation as exc:
        raise _text_error("text coordinate is invalid", tree_path) from exc
    if decimal != 0 and parsed == 0.0:
        raise _text_error("text coordinate is outside supported float precision", tree_path)
    return parsed


def normalize_svg_text_whitespace(
    events: Sequence[_TextEvent],
    line_anchor: str = "start",
    tree_path: str = "",
) -> Tuple[TextRun, ...]:
    result = []
    pending_default_event = None

    def attach_pending_space() -> None:
        nonlocal pending_default_event
        event = pending_default_event
        pending_default_event = None
        if event is None or not result:
            return
        if event.style.text_anchor != line_anchor:
            raise _text_error(
                "meaningful space cannot change text-anchor",
                tree_path,
            )
        if result[-1].style == event.style:
            if not result[-1].text.endswith(" "):
                result[-1] = replace(
                    result[-1],
                    text=result[-1].text + " ",
                    preserve_space=True,
                )
        else:
            result.append(TextRun(" ", event.style, preserve_space=True))

    for event in events:
        if not event.text:
            continue
        if event.preserve:
            attach_pending_space()
            normalized = re.sub(r"[\t\r\n]", " ", event.text)
            if normalized:
                result.append(TextRun(normalized, event.style, preserve_space=True))
            continue
        collapsed = re.sub(r"[\t\r\n ]+", " ", event.text)
        core = collapsed.strip(" ")
        if not core:
            if result and pending_default_event is None:
                pending_default_event = event
            continue
        had_pending = pending_default_event is not None
        attach_pending_space()
        leading = collapsed.startswith(" ") and bool(result) and not had_pending
        text = (" " if leading else "") + core
        result.append(TextRun(text, event.style, preserve_space=leading))
        pending_default_event = event if collapsed.endswith(" ") else None
    return tuple(result)


def choose_primary_font(font_families) -> str:
    if not isinstance(font_families, str):
        for value in tuple(font_families or ()):
            normalized = str(value).strip().strip("\"").strip("'")
            if normalized:
                return normalized
        return "Arial"
    values = []
    buffer = []
    quote = None
    for character in font_families:
        if quote is not None:
            if character == quote:
                quote = None
            else:
                buffer.append(character)
        elif character in ("'", '"'):
            quote = character
        elif character == ",":
            values.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(character)
    if quote is not None:
        raise ValueError("unterminated quoted font family")
    values.append("".join(buffer).strip())
    return next((value for value in values if value), "Arial")


def estimate_text_advance_px(
    text: str,
    font_size_px: float,
    letter_spacing_px: float,
) -> float:
    if not math.isfinite(font_size_px) or font_size_px <= 0:
        raise ValueError("font_size_px must be finite and positive")
    if not math.isfinite(letter_spacing_px):
        raise ValueError("letter_spacing_px must be finite")
    width_units = 0.0
    for character in text:
        if unicodedata.east_asian_width(character) in ("W", "F"):
            width_units += 1.0
        elif character == " " or character in "·•":
            width_units += 0.35
        elif character.isdigit() or character.isupper():
            width_units += 0.60
        elif character.islower():
            width_units += 0.52
        else:
            width_units += 0.40
    spacing = max(0, len(text) - 1) * letter_spacing_px
    result = width_units * font_size_px + spacing
    if not math.isfinite(result):
        raise ValueError("text advance is non-finite")
    return result


def compute_text_box(
    anchor_x_px: float,
    baseline_y_px: float,
    anchor: str,
    runs: Sequence[TextRun],
) -> Bounds:
    if anchor not in ("start", "middle", "end") or not runs:
        raise ValueError("text box requires runs and a supported anchor")
    max_size = max(
        run.style.font_size if run.style.font_size is not None else 16.0
        for run in runs
    )
    advance = sum(
        estimate_text_advance_px(
            run.text,
            run.style.font_size if run.style.font_size is not None else max_size,
            run.style.letter_spacing,
        )
        for run in runs
    )
    advance += sum(
        run.style.letter_spacing
        for run, following in zip(runs, runs[1:])
        if run.text and following.text
    )
    if not math.isfinite(advance):
        raise ValueError("aggregate text advance must be finite")
    width = max(advance * 1.12 + 6.0, 30.0)
    top = baseline_y_px - max_size * 1.06 + POWERPOINT_TEXT_BASELINE_OFFSET_PX
    height = max_size * 1.50
    if anchor == "start":
        left = anchor_x_px
    elif anchor == "middle":
        left = anchor_x_px - width / 2.0
    else:
        left = anchor_x_px - width
    bounds = Bounds(left, top, left + width, top + height)
    if (
        not all(
            math.isfinite(value)
            for value in (bounds.left, bounds.top, bounds.right, bounds.bottom)
        )
        or bounds.right <= bounds.left
        or bounds.bottom <= bounds.top
    ):
        raise ValueError("text bounds must be finite with positive extents")
    return bounds


def flatten_text_lines(
    text_element,
    inherited_style: ResolvedStyle,
    tree_path: str,
) -> Tuple[TextLine, ...]:
    from .svg_parser import (
        _attribute_map,
        _require_svg_element,
        _validate_attributes,
        resolve_style,
    )

    root_attributes = _attribute_map(text_element)
    root_x = _text_number(root_attributes.get("x", "0"), tree_path)
    root_y = _text_number(root_attributes.get("y", "0"), tree_path)
    root_space = root_attributes.get("xml:space")
    if root_space not in (None, "default", "preserve"):
        raise _text_error("xml:space must be default or preserve", tree_path)
    root_preserve = root_space == "preserve"
    lines = [
        _MutableLine(
            root_x,
            root_y,
            inherited_style.text_anchor,
            [],
        )
    ]
    current = [lines[0]]

    def append_text(value, style, preserve, event_path):
        if not value:
            return
        has_visible_content = bool(re.sub(r"[ \t\r\n]", "", value))
        if (has_visible_content or preserve) and style.text_anchor != current[0].anchor:
            raise _text_error(
                "one visual line cannot mix text-anchor values",
                event_path,
            )
        current[0].events.append(_TextEvent(value, style, preserve))

    append_text(text_element.text, inherited_style, root_preserve, tree_path)

    def visit(parent, parent_style, inherited_preserve, parent_path):
        counters = 0
        for child in parent:
            counters += 1
            child_path = "{}/tspan[{}]".format(parent_path, counters)
            kind = _require_svg_element(child, "", child_path)
            if kind != "tspan":
                raise _text_error("text may contain only tspan elements", child_path)
            attributes = _attribute_map(child)
            _validate_attributes(kind, attributes, slide_id="", tree_path=child_path)
            style = resolve_style(parent_style, kind, attributes)
            preserve_value = attributes.get("xml:space")
            if preserve_value not in (None, "default", "preserve"):
                raise _text_error("xml:space must be default or preserve", child_path)
            preserve = (
                inherited_preserve
                if preserve_value is None
                else preserve_value == "preserve"
            )
            dy = _text_number(attributes.get("dy", "0"), child_path)
            starts_line = "x" in attributes or dy != 0.0
            if (
                not starts_line
                and "text-anchor" in attributes
                and style.text_anchor != current[0].anchor
            ):
                raise _text_error(
                    "inline tspan cannot change text-anchor",
                    child_path,
                )
            if starts_line:
                x = (
                    _text_number(attributes["x"], child_path)
                    if "x" in attributes
                    else current[0].x
                )
                previous_y = current[0].y
                y = previous_y + dy
                if not math.isfinite(y) or (dy != 0.0 and y == previous_y):
                    raise _text_error(
                        "text line coordinate change is not representable",
                        child_path,
                    )
                current[0] = _MutableLine(x, y, style.text_anchor, [])
                lines.append(current[0])
            append_text(child.text, style, preserve, child_path)
            visit(child, style, preserve, child_path)
            append_text(child.tail, parent_style, inherited_preserve, parent_path)

    visit(text_element, inherited_style, root_preserve, tree_path)
    result = []
    for mutable in lines:
        runs = normalize_svg_text_whitespace(
            mutable.events,
            mutable.anchor,
            tree_path,
        )
        if not runs:
            continue
        visible_text = "".join(run.text for run in runs)
        if _VISIBLE_INTERNAL_SOURCE_ID_RE.search(visible_text):
            raise _text_error(
                "internal SRC identifiers are machine metadata only",
                tree_path,
            )
        try:
            bounds = compute_text_box(
                mutable.x,
                mutable.y,
                mutable.anchor,
                runs,
            )
        except ValueError as exc:
            raise _text_error(str(exc), tree_path) from exc
        result.append(
            TextLine(
                line_index=len(result) + 1,
                x=mutable.x,
                y=mutable.y,
                anchor=mutable.anchor,
                runs=runs,
                bounds=bounds,
            )
        )
    if not result:
        raise _text_error("text element has no visible lines", tree_path)
    return tuple(result)
