"""Complete consuming parser and geometry math for the SVG M/L/H/V/A/Z subset."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import re
from typing import Optional, Sequence, Tuple, Union

from .errors import EditableError
from .model import Bounds


_NUMBER_RE = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
_COMMANDS = frozenset("MmLlHhVvAaZz")
_TWO_PI = math.pi * 2.0


@dataclass(frozen=True)
class PathToken:
    kind: str
    value: str
    offset: int


@dataclass(frozen=True)
class MoveTo:
    x: float
    y: float


@dataclass(frozen=True)
class LineTo:
    x: float
    y: float


@dataclass(frozen=True)
class ArcTo:
    rx: float
    ry: float
    rotation_degrees: float
    large_arc: int
    sweep: int
    end_x: float
    end_y: float


@dataclass(frozen=True)
class ClosePath:
    pass


@dataclass(frozen=True)
class CenterArc:
    cx: float
    cy: float
    corrected_rx: float
    corrected_ry: float
    start_radians: float
    sweep_radians: float


PathSegment = Union[MoveTo, LineTo, ArcTo, ClosePath]


def _error(message: str, code: str = "svg_path_invalid") -> EditableError:
    return EditableError(code, message, element_type="path")


def _finite_number(token: PathToken) -> float:
    try:
        value = float(token.value)
    except ValueError as exc:
        raise _error("invalid number at offset {}".format(token.offset)) from exc
    if not math.isfinite(value):
        raise _error("non-finite number at offset {}".format(token.offset))
    return value


def _decimal_number(token: PathToken) -> Decimal:
    try:
        value = Decimal(token.value)
    except InvalidOperation as exc:
        raise _error("invalid number at offset {}".format(token.offset)) from exc
    if not value.is_finite():
        raise _error("non-finite number at offset {}".format(token.offset))
    return value


def tokenize_path(data: str) -> Tuple[PathToken, ...]:
    if not isinstance(data, str) or not data.strip():
        raise _error("path data is empty")
    tokens = []
    cursor = 0
    length = len(data)
    while cursor < length:
        character = data[cursor]
        if character in " \t\r\n\f":
            cursor += 1
            continue
        if character == ",":
            tokens.append(PathToken("comma", character, cursor))
            cursor += 1
            continue
        if character.isalpha():
            if character not in _COMMANDS:
                raise _error(
                    "unsupported path command at offset {}".format(cursor)
                )
            tokens.append(PathToken("command", character, cursor))
            cursor += 1
            continue
        match = _NUMBER_RE.match(data, cursor)
        if match is None:
            raise _error("unrecognized path character at offset {}".format(cursor))
        tokens.append(PathToken("number", match.group(0), cursor))
        cursor = match.end()
    for index, token in enumerate(tokens):
        if token.kind != "comma":
            continue
        if (
            index == 0
            or index + 1 == len(tokens)
            or tokens[index - 1].kind != "number"
            or tokens[index + 1].kind != "number"
        ):
            raise _error("comma is not between numbers at offset {}".format(token.offset))
    return tuple(token for token in tokens if token.kind != "comma")


def _groups(tokens: Sequence[PathToken], arity: int, command: str) -> Tuple[Tuple[PathToken, ...], ...]:
    if not tokens or len(tokens) % arity:
        raise _error("{} command has invalid arity".format(command))
    return tuple(
        tuple(tokens[index : index + arity])
        for index in range(0, len(tokens), arity)
    )


def _coordinate_token(token: PathToken) -> float:
    decimal = _decimal_number(token)
    value = _finite_number(token)
    if decimal != 0 and value == 0.0:
        raise _error("nonzero coordinate is outside supported float precision")
    return value


def _coordinate(value: float) -> float:
    if not math.isfinite(value):
        raise _error("coordinate arithmetic produced a non-finite value")
    return value


def parse_path(data: str) -> Tuple[PathSegment, ...]:
    tokens = tokenize_path(data)
    segments = []
    index = 0
    current_x = current_y = 0.0
    subpath_x = subpath_y = None
    seen_move = False
    while index < len(tokens):
        command_token = tokens[index]
        if command_token.kind != "command":
            raise _error("path numbers must follow a command")
        command = command_token.value
        if command not in _COMMANDS:
            raise _error("unsupported path command: {}".format(command))
        index += 1
        if not seen_move and command not in ("M", "m"):
            raise _error("first path command must be M or m")
        if command in ("Z", "z"):
            if subpath_x is None:
                raise _error("close command has no subpath")
            if index < len(tokens) and tokens[index].kind != "command":
                raise _error("close command cannot have coordinates")
            segments.append(ClosePath())
            current_x, current_y = subpath_x, subpath_y
            continue
        value_start = index
        while index < len(tokens) and tokens[index].kind != "command":
            index += 1
        values = tokens[value_start:index]
        relative = command.islower()
        upper = command.upper()
        arity = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7}[upper]
        groups = _groups(values, arity, command)
        for group_index, group in enumerate(groups):
            numbers = tuple(_finite_number(token) for token in group)
            if upper in ("M", "L"):
                x, y = _coordinate_token(group[0]), _coordinate_token(group[1])
                if relative:
                    x = _coordinate(x + current_x)
                    y = _coordinate(y + current_y)
                else:
                    x = _coordinate(x)
                    y = _coordinate(y)
                if upper == "M" and group_index == 0:
                    segments.append(MoveTo(x, y))
                    subpath_x, subpath_y = x, y
                    seen_move = True
                else:
                    segments.append(LineTo(x, y))
                current_x, current_y = x, y
            elif upper == "H":
                raw_x = _coordinate_token(group[0])
                x = _coordinate(raw_x + current_x if relative else raw_x)
                segments.append(LineTo(x, current_y))
                current_x = x
            elif upper == "V":
                raw_y = _coordinate_token(group[0])
                y = _coordinate(raw_y + current_y if relative else raw_y)
                segments.append(LineTo(current_x, y))
                current_y = y
            else:
                rx, ry, rotation = numbers[0], numbers[1], numbers[2]
                end_x = _coordinate_token(group[5])
                end_y = _coordinate_token(group[6])
                rx_decimal = _decimal_number(group[0])
                ry_decimal = _decimal_number(group[1])
                rotation_decimal = _decimal_number(group[2])
                large_token = group[3].value
                sweep_token = group[4].value
                if large_token not in ("0", "1") or sweep_token not in ("0", "1"):
                    raise _error("arc flags must be exact 0 or 1")
                if rx_decimal < 0 or ry_decimal < 0:
                    raise _error("arc radii cannot be negative")
                if rotation_decimal != 0:
                    raise _error(
                        "rotated elliptical arcs are unsupported",
                        "svg_arc_rotation_unsupported",
                    )
                if relative:
                    end_x = _coordinate(end_x + current_x)
                    end_y = _coordinate(end_y + current_y)
                else:
                    end_x = _coordinate(end_x)
                    end_y = _coordinate(end_y)
                if end_x == current_x and end_y == current_y:
                    continue
                radii_are_zero = rx_decimal == 0 or ry_decimal == 0
                if not radii_are_zero and (rx == 0.0 or ry == 0.0):
                    raise _error("positive arc radius is outside supported float precision")
                if radii_are_zero:
                    segments.append(LineTo(end_x, end_y))
                else:
                    segments.append(
                        ArcTo(
                            rx=rx,
                            ry=ry,
                            rotation_degrees=rotation,
                            large_arc=int(large_token),
                            sweep=int(sweep_token),
                            end_x=end_x,
                            end_y=end_y,
                        )
                    )
                current_x, current_y = end_x, end_y
    if not seen_move:
        raise _error("path has no move command")
    return tuple(segments)


def endpoint_arc_to_center(
    start_x: float,
    start_y: float,
    arc: ArcTo,
) -> Optional[CenterArc]:
    if arc.rotation_degrees != 0.0:
        raise _error("rotated elliptical arcs are unsupported", "svg_arc_rotation_unsupported")
    if arc.rx == 0.0 or arc.ry == 0.0:
        return None
    if start_x == arc.end_x and start_y == arc.end_y:
        return None
    rx = abs(arc.rx)
    ry = abs(arc.ry)
    x1p = start_x / 2.0 - arc.end_x / 2.0
    y1p = start_y / 2.0 - arc.end_y / 2.0
    midpoint_x = start_x / 2.0 + arc.end_x / 2.0
    midpoint_y = start_y / 2.0 + arc.end_y / 2.0
    geometry_scale = max(abs(x1p), abs(y1p), rx, ry)
    if geometry_scale == 0.0 or not math.isfinite(geometry_scale):
        raise _error("arc geometry cannot be normalized")
    normalized_rx = rx / geometry_scale
    normalized_ry = ry / geometry_scale
    if normalized_rx == 0.0 or normalized_ry == 0.0:
        raise _error("arc radii exceed supported float precision")
    radius_scale = math.hypot(
        (x1p / geometry_scale) / normalized_rx,
        (y1p / geometry_scale) / normalized_ry,
    )
    if not math.isfinite(radius_scale):
        raise _error("arc radius correction is non-finite")
    if radius_scale > 1.0:
        rx = (normalized_rx * radius_scale) * geometry_scale
        ry = (normalized_ry * radius_scale) * geometry_scale
    ratio_x = x1p / rx
    ratio_y = y1p / ry
    normalized_distance = math.hypot(ratio_x, ratio_y)
    if normalized_distance == 0.0 or not math.isfinite(normalized_distance):
        raise _error("arc center calculation exceeds supported precision")
    offset_magnitude = math.sqrt(
        max(0.0, 1.0 - normalized_distance * normalized_distance)
    )
    sign = -1.0 if arc.large_arc == arc.sweep else 1.0
    unit_x = ratio_x / normalized_distance
    unit_y = ratio_y / normalized_distance
    cxp = (sign * unit_y * offset_magnitude) * rx
    cyp = (-sign * unit_x * offset_magnitude) * ry
    cx = cxp + midpoint_x
    cy = cyp + midpoint_y
    start_unit_x = (x1p - cxp) / rx
    start_unit_y = (y1p - cyp) / ry
    start_angle = math.atan2(start_unit_y, start_unit_x)
    half_rx = rx / 2.0
    half_ry = ry / 2.0
    if half_rx == 0.0 or half_ry == 0.0:
        raise _error("arc sweep exceeds supported precision")
    normalized_chord = math.hypot(
        (arc.end_x / 2.0 - start_x / 2.0) / half_rx,
        (arc.end_y / 2.0 - start_y / 2.0) / half_ry,
    )
    small_sweep = 2.0 * math.asin(min(1.0, normalized_chord / 2.0))
    sweep_magnitude = _TWO_PI - small_sweep if arc.large_arc else small_sweep
    if sweep_magnitude == 0.0:
        raise _error("arc sweep is below supported float precision")
    sweep_angle = sweep_magnitude if arc.sweep else -sweep_magnitude
    values = (cx, cy, rx, ry, start_angle, sweep_angle)
    if not all(math.isfinite(value) for value in values):
        raise _error("arc conversion produced non-finite geometry")
    return CenterArc(cx, cy, rx, ry, start_angle, sweep_angle)


def angle_is_on_sweep(
    angle: float,
    start: float,
    sweep: float,
    epsilon: float = 0.0,
) -> bool:
    if sweep >= 0:
        return (angle - start) % _TWO_PI <= sweep + epsilon
    return (start - angle) % _TWO_PI <= -sweep + epsilon


def path_bounds(
    segments: Sequence[PathSegment],
    stroke_width: float = 0.0,
) -> Bounds:
    if (
        type(stroke_width) not in (int, float)
        or not math.isfinite(stroke_width)
        or stroke_width < 0.0
    ):
        raise _error("stroke width must be a finite nonnegative number")
    current_x = current_y = None
    subpath_x = subpath_y = None
    points = []
    drew = False
    for segment in segments:
        if isinstance(segment, MoveTo):
            current_x, current_y = segment.x, segment.y
            subpath_x, subpath_y = current_x, current_y
        elif isinstance(segment, LineTo):
            if current_x is None:
                raise _error("line has no current point")
            points.extend(((current_x, current_y), (segment.x, segment.y)))
            current_x, current_y = segment.x, segment.y
            drew = True
        elif isinstance(segment, ArcTo):
            if current_x is None:
                raise _error("arc has no current point")
            center = endpoint_arc_to_center(current_x, current_y, segment)
            if center is None:
                current_x, current_y = segment.end_x, segment.end_y
                continue
            points.extend(((current_x, current_y), (segment.end_x, segment.end_y)))
            for cardinal, unit_x, unit_y in (
                (0.0, 1.0, 0.0),
                (math.pi / 2.0, 0.0, 1.0),
                (math.pi, -1.0, 0.0),
                (math.pi * 1.5, 0.0, -1.0),
            ):
                if angle_is_on_sweep(cardinal, center.start_radians, center.sweep_radians):
                    points.append(
                        (
                            center.cx + center.corrected_rx * unit_x,
                            center.cy + center.corrected_ry * unit_y,
                        )
                    )
            current_x, current_y = segment.end_x, segment.end_y
            drew = True
        else:
            if current_x is None or subpath_x is None:
                raise _error("close has no current subpath")
            if current_x != subpath_x or current_y != subpath_y:
                points.extend(((current_x, current_y), (subpath_x, subpath_y)))
                drew = True
            current_x, current_y = subpath_x, subpath_y
    if not drew or not points:
        raise _error("path has no visible segments")
    coordinates = [coordinate for point in points for coordinate in point]
    if not all(math.isfinite(value) for value in coordinates):
        raise _error("path bounds are non-finite")
    bounds = Bounds(
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )
    return bounds.expanded(float(stroke_width) / 2.0)


def round_int(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("cannot round non-finite value")
    return int(Decimal(str(value)).to_integral_value(rounding=ROUND_HALF_UP))
