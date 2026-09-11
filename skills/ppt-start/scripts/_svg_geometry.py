"""Conservative, renderer-independent bounds for the Office-safe SVG subset.

Curve control hulls and arc radius boxes deliberately overestimate bounds.
Rendering and fact/narrative review remain separate QA obligations.
"""
import math
import re
import unicodedata

NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"


def number(value):
    if not isinstance(value, str) or re.fullmatch(NUMBER, value.strip()) is None:
        raise ValueError("svg_contract_failed")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("svg_contract_failed")
    return result


def numbers(value):
    if re.sub(NUMBER, "", value).strip(" ,\t\r\n"):
        raise ValueError("svg_contract_failed")
    return [number(token) for token in re.findall(NUMBER, value)]


def _path_points(value):
    tokens = re.findall(NUMBER + r"|[MmLlHhVvCcSsQqTtAaZz]", value)
    if re.sub(NUMBER + r"|[MmLlHhVvCcSsQqTtAaZz]", "", value).strip(" ,\t\r\n"):
        raise ValueError("svg_contract_failed")
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    x = y = sx = sy = 0.0
    command = None
    previous_control = None
    previous_kind = None
    points = []
    index = 0
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command.upper() == "Z":
                x, y = sx, sy
                points.append((x, y))
                command = None
                previous_control = None
                previous_kind = "Z"
                continue
        if command is None or (not points and command.upper() != "M"):
            raise ValueError("svg_contract_failed")
        kind = command.upper()
        count = counts[kind]
        args = tokens[index:index + count]
        if len(args) != count:
            raise ValueError("svg_contract_failed")
        args = [number(arg) for arg in args]
        index += count
        relative = command.islower()
        ox, oy = (x, y) if relative else (0, 0)
        if kind == "H":
            x = ox + args[0]
        elif kind == "V":
            y = oy + args[0]
        elif kind == "A":
            rx, ry, angle, large, sweep, ex, ey = args
            if rx < 0 or ry < 0 or large not in (0, 1) or sweep not in (0, 1):
                raise ValueError("svg_contract_failed")
            # A conservative circle enclosing any rotated elliptical arc.
            ex, ey = ox + ex, oy + ey
            if rx and ry:
                rotation = math.radians(angle % 360)
                dx, dy = (x - ex) / 2, (y - ey) / 2
                rotated_x = math.cos(rotation) * dx + math.sin(rotation) * dy
                rotated_y = -math.sin(rotation) * dx + math.cos(rotation) * dy
                correction = max(1, math.hypot(rotated_x / rx, rotated_y / ry))
                radius = max(rx, ry) * correction * 2
            else:
                radius = 0
            points.extend([(min(x, ex) - radius, min(y, ey) - radius),
                           (max(x, ex) + radius, max(y, ey) + radius)])
            x, y = ex, ey
        else:
            pairs = [(ox + args[i], oy + args[i + 1]) for i in range(0, count, 2)]
            if kind in ("S", "T"):
                compatible = previous_kind in (("C", "S") if kind == "S" else ("Q", "T"))
                control = previous_control if compatible and previous_control else (x, y)
                reflected = (2 * x - control[0], 2 * y - control[1])
                points.append(reflected)
                previous_control = reflected if kind == "T" else pairs[-2]
            elif kind in ("C", "Q"):
                previous_control = pairs[-2]
            points.extend(pairs)
            x, y = pairs[-1]
            if kind == "M":
                sx, sy = x, y
                command = "l" if relative else "L"
        if kind not in ("C", "S", "Q", "T"):
            previous_control = None
        previous_kind = kind
        points.append((x, y))
    if not points:
        raise ValueError("svg_contract_failed")
    return points


def _safe_box(left, top, right, bottom):
    if not all(math.isfinite(v) for v in (left, top, right, bottom)) or not (
        64 <= left <= right <= 1216 and 64 <= top <= bottom <= 656
    ):
        raise ValueError("svg_contract_failed")


def validate_geometry(element, inherited, *, title_min_size=40):
    """Check static coordinates, stroke bounds and explicit text layout."""
    tag = element.tag.rsplit("}", 1)[-1]
    attrs = dict(inherited)
    attrs.update(element.attrib)
    # Bounds are evaluated in canvas coordinates. Transforms must be flattened
    # into coordinates by the generator so a browser cannot change these bounds.
    if "transform" in element.attrib:
        raise ValueError("svg_contract_failed")
    get = lambda key, default="0": number(element.get(key, default))
    points = []
    if tag == "rect":
        x, y, width, height = get("x"), get("y"), get("width"), get("height")
        if width < 0 or height < 0 or get("rx") < 0 or get("ry") < 0:
            raise ValueError("svg_contract_failed")
        if (x, y, width, height) == (0, 0, 1280, 720) and attrs.get("stroke", "none") == "none":
            return
        points = [(x, y), (x + width, y + height)]
    elif tag in ("circle", "ellipse"):
        x, y = get("cx"), get("cy")
        rx = ry = get("r") if tag == "circle" else 0
        if tag == "ellipse":
            rx, ry = get("rx"), get("ry")
        if rx < 0 or ry < 0:
            raise ValueError("svg_contract_failed")
        points = [(x - rx, y - ry), (x + rx, y + ry)]
    elif tag == "line":
        points = [(get("x1"), get("y1")), (get("x2"), get("y2"))]
    elif tag in ("polyline", "polygon"):
        values = numbers(element.get("points", ""))
        if len(values) < (6 if tag == "polygon" else 4) or len(values) % 2:
            raise ValueError("svg_contract_failed")
        points = list(zip(values[::2], values[1::2]))
    elif tag == "path":
        points = _path_points(element.get("d", ""))
    elif tag == "text":
        role = element.get("data-role")
        size = get("font-size")
        if role not in ("title", "body", "footnote") or size < {"title": title_min_size, "body": 20, "footnote": 14}.get(role, 0):
            raise ValueError("svg_contract_failed")
        if not attrs.get("font-family") or (element.text or "").strip() or len(element) != 1:
            raise ValueError("svg_contract_failed")
        line = element[0]
        if line.tag.rsplit("}", 1)[-1] != "tspan" or len(line) or (line.tail or "").strip():
            raise ValueError("svg_contract_failed")
        if any(line.get(key) != element.get(key) or element.get(key) is None for key in ("x", "y")):
            raise ValueError("svg_contract_failed")
        if line.get("font-size", element.get("font-size")) != element.get("font-size"):
            raise ValueError("svg_contract_failed")
        text = line.text or ""
        if not text.strip() or "\n" in text or "\r" in text:
            raise ValueError("svg_contract_failed")
        width = sum(1 if unicodedata.east_asian_width(c) in ("W", "F") else
                    .6 if c.isupper() or c.isdigit() else .52 if c.islower() else .35
                    for c in text) * size
        x, y = get("x"), get("y")
        anchor = line.get("text-anchor", attrs.get("text-anchor", "start"))
        if anchor not in ("start", "middle", "end"):
            raise ValueError("svg_contract_failed")
        left = x - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
        available = 2 * min(x - 64, 1216 - x) if anchor == "middle" else x - 64 if anchor == "end" else 1216 - x
        if width > available * .88:
            raise ValueError("svg_contract_failed")
        line_attrs = dict(attrs)
        line_attrs.update(line.attrib)
        text_stroke = number(line_attrs.get("stroke-width", "1")) if line_attrs.get("stroke", "none") != "none" else 0
        if text_stroke < 0:
            raise ValueError("svg_contract_failed")
        _safe_box(left - text_stroke / 2, y - size - text_stroke / 2,
                  left + width + text_stroke / 2, y + size * .25 + text_stroke / 2)
    if points:
        stroke = number(attrs.get("stroke-width", "1")) if attrs.get("stroke", "none") != "none" else 0
        if stroke < 0:
            raise ValueError("svg_contract_failed")
        # Round/bevel joins remain within half the stroke; miter joins may grow.
        allowance = stroke / 2
        if tag in ("path", "polyline", "polygon") and attrs.get("stroke-linejoin", "miter") == "miter":
            allowance *= max(1, number(attrs.get("stroke-miterlimit", "4")))
        # A rotated square cap extends by half-width * (|sin| + |cos|)
        # along either axis, whose maximum is half-width * sqrt(2).
        # This also covers open path/polyline ends and individual dash caps.
        if attrs.get("stroke-linecap", "butt") == "square":
            allowance = max(allowance, stroke / 2 * math.sqrt(2))
        _safe_box(min(p[0] for p in points) - allowance, min(p[1] for p in points) - allowance,
                  max(p[0] for p in points) + allowance, max(p[1] for p in points) + allowance)
