"""Conservative, renderer-independent bounds for the Office-safe SVG subset.

Bezier control hulls deliberately overestimate bounds; elliptical arcs use exact
axis extrema on their SVG sweep. Rendering and fact/narrative review stay separate.
"""
import math
import re
import unicodedata

NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"


class GeometryError(ValueError):
    """Stable contract error with fixed reasons and optional numeric diagnostics."""
    def __init__(self, reason, *, bbox=None):
        super().__init__("svg_contract_failed")
        self.details = {"reason": reason}
        if bbox is not None:
            self.details.update(bbox=list(bbox), bounds=[64, 64, 1216, 656])


def number(value):
    if not isinstance(value, str) or re.fullmatch(NUMBER, value.strip()) is None:
        raise GeometryError("invalid_number")
    result = float(value)
    if not math.isfinite(result):
        raise GeometryError("non_finite_number")
    if result == 0 and re.search(r"[1-9]", re.split("[eE]", value, maxsplit=1)[0]):
        raise GeometryError("numeric_underflow")
    return result


def numbers(value):
    if re.sub(NUMBER, "", value).strip(" ,\t\r\n"):
        raise GeometryError("invalid_geometry")
    return [number(token) for token in re.findall(NUMBER, value)]


def _arc_points(x, y, rx, ry, angle, large, sweep, ex, ey):
    """SVG endpoint-to-center conversion, then extrema on the selected sweep."""
    if not rx or not ry or (x, y) == (ex, ey):
        return []  # Zero radii draw a line; coincident endpoints omit the arc.
    rotation = math.radians(angle % 360)
    cosine, sine = math.cos(rotation), math.sin(rotation)
    dx, dy = (x - ex) / 2, (y - ey) / 2
    px, py = cosine * dx + sine * dy, -sine * dx + cosine * dy
    ux, uy = px / rx, py / ry
    scale = math.hypot(ux, uy)
    # ponytail: float endpoint conversion loses tiny chords relative to radii;
    # fail closed below 1e-12 rather than invent bounds. Use higher precision
    # if such ill-conditioned arcs ever become a real slide requirement.
    if not math.isfinite(scale) or scale < 1e-12:
        raise GeometryError("unstable_arc")
    if scale > 1:
        rx, ry = rx * scale, ry * scale
        if not all(math.isfinite(v) for v in (rx, ry)):
            raise GeometryError("unstable_arc")
        ux, uy = px / rx, py / ry
        scale = 1.0
    # ponytail: huge eccentric axes lose extrema to center/radius cancellation.
    # Cap even corrected radii at 1e6 canvas units; supporting larger arcs needs
    # higher-precision or endpoint-relative extrema, not wider safety bounds.
    if max(rx, ry) > 1e6:
        raise GeometryError("unstable_arc")
    factor = math.sqrt(max(0, (1 - scale) * (1 + scale)))
    if large == sweep:
        factor = -factor
    cx, cy = factor * rx * (uy / scale), -factor * ry * (ux / scale)
    center_x = cosine * cx - sine * cy + (x + ex) / 2
    center_y = sine * cx + cosine * cy + (y + ey) / 2
    start = math.atan2((py - cy) / ry, (px - cx) / rx)
    end = math.atan2((-py - cy) / ry, (-px - cx) / rx)
    direction = 1 if sweep else -1
    span = (direction * (end - start)) % math.tau
    if not all(math.isfinite(v) for v in (center_x, center_y, span)) or not span:
        raise GeometryError("unstable_arc")
    # dx/dt = 0 and dy/dt = 0, each with its antipodal extremum.
    extrema = (math.atan2(-ry * sine, rx * cosine),
               math.atan2(ry * cosine, rx * sine))
    points = []
    for base in extrema:
        for theta in (base, base + math.pi):
            if (direction * (theta - start)) % math.tau <= span + 1e-12:
                points.append((center_x + rx * cosine * math.cos(theta) - ry * sine * math.sin(theta),
                               center_y + rx * sine * math.cos(theta) + ry * cosine * math.sin(theta)))
    return points


def _path_points(value):
    tokens = re.findall(NUMBER + r"|[MmLlHhVvCcSsQqTtAaZz]", value)
    if re.sub(NUMBER + r"|[MmLlHhVvCcSsQqTtAaZz]", "", value).strip(" ,\t\r\n"):
        raise GeometryError("invalid_path")
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
            raise GeometryError("invalid_path")
        kind = command.upper()
        count = counts[kind]
        args = tokens[index:index + count]
        if len(args) != count:
            raise GeometryError("invalid_path")
        if kind == "A" and any(arg not in ("0", "1") for arg in args[3:5]):
            raise GeometryError("invalid_arc_flags")
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
            if rx < 0 or ry < 0:
                raise GeometryError("invalid_arc")
            ex, ey = ox + ex, oy + ey
            points.extend(_arc_points(x, y, rx, ry, angle, large, sweep, ex, ey))
            x, y = ex, ey
        else:
            # ponytail: Bezier bounds retain their conservative control hull;
            # solve derivative roots only if tighter Bezier bounds are needed.
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
        raise GeometryError("invalid_path")
    return points


def _safe_box(left, top, right, bottom):
    if not all(math.isfinite(v) for v in (left, top, right, bottom)):
        raise GeometryError("non_finite_geometry")
    if not (64 <= left <= right <= 1216 and 64 <= top <= bottom <= 656):
        raise GeometryError("geometry_out_of_bounds", bbox=(left, top, right, bottom))


def validate_geometry(element, inherited, *, title_min_size=40):
    """Check static coordinates, stroke bounds and explicit text layout."""
    tag = element.tag.rsplit("}", 1)[-1]
    attrs = dict(inherited)
    attrs.update(element.attrib)
    # Bounds are evaluated in canvas coordinates. Transforms must be flattened
    # into coordinates by the generator so a browser cannot change these bounds.
    if "transform" in element.attrib:
        raise GeometryError("invalid_geometry")
    get = lambda key, default="0": number(element.get(key, default))
    points = []
    if tag == "rect":
        x, y, width, height = get("x"), get("y"), get("width"), get("height")
        if width < 0 or height < 0 or get("rx") < 0 or get("ry") < 0:
            raise GeometryError("invalid_geometry")
        if (x, y, width, height) == (0, 0, 1280, 720) and attrs.get("stroke", "none") == "none":
            return
        points = [(x, y), (x + width, y + height)]
    elif tag in ("circle", "ellipse"):
        x, y = get("cx"), get("cy")
        rx = ry = get("r") if tag == "circle" else 0
        if tag == "ellipse":
            rx, ry = get("rx"), get("ry")
        if rx < 0 or ry < 0:
            raise GeometryError("invalid_geometry")
        points = [(x - rx, y - ry), (x + rx, y + ry)]
    elif tag == "line":
        points = [(get("x1"), get("y1")), (get("x2"), get("y2"))]
    elif tag in ("polyline", "polygon"):
        values = numbers(element.get("points", ""))
        if len(values) < (6 if tag == "polygon" else 4) or len(values) % 2:
            raise GeometryError("invalid_geometry")
        points = list(zip(values[::2], values[1::2]))
    elif tag == "path":
        points = _path_points(element.get("d", ""))
    elif tag == "text":
        role = element.get("data-role")
        size = get("font-size")
        if role not in ("title", "body", "footnote") or size < {"title": title_min_size, "body": 20, "footnote": 14}.get(role, 0):
            raise GeometryError("invalid_text")
        if not attrs.get("font-family") or (element.text or "").strip() or len(element) != 1:
            raise GeometryError("invalid_text")
        line = element[0]
        if line.tag.rsplit("}", 1)[-1] != "tspan" or len(line) or (line.tail or "").strip():
            raise GeometryError("invalid_text")
        if any(line.get(key) != element.get(key) or element.get(key) is None for key in ("x", "y")):
            raise GeometryError("invalid_text")
        if line.get("font-size", element.get("font-size")) != element.get("font-size"):
            raise GeometryError("invalid_text")
        text = line.text or ""
        if not text.strip() or "\n" in text or "\r" in text:
            raise GeometryError("invalid_text")
        width = sum(1 if unicodedata.east_asian_width(c) in ("W", "F") else
                    .6 if c.isupper() or c.isdigit() else .52 if c.islower() else .35
                    for c in text) * size
        x, y = get("x"), get("y")
        anchor = line.get("text-anchor", attrs.get("text-anchor", "start"))
        if anchor not in ("start", "middle", "end"):
            raise GeometryError("invalid_text")
        left = x - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
        available = 2 * min(x - 64, 1216 - x) if anchor == "middle" else x - 64 if anchor == "end" else 1216 - x
        if width > available * .88:
            raise GeometryError("text_overflow")
        line_attrs = dict(attrs)
        line_attrs.update(line.attrib)
        text_stroke = number(line_attrs.get("stroke-width", "1")) if line_attrs.get("stroke", "none") != "none" else 0
        if text_stroke < 0:
            raise GeometryError("invalid_geometry")
        _safe_box(left - text_stroke / 2, y - size - text_stroke / 2,
                  left + width + text_stroke / 2, y + size * .25 + text_stroke / 2)
    if points:
        stroke = number(attrs.get("stroke-width", "1")) if attrs.get("stroke", "none") != "none" else 0
        if stroke < 0:
            raise GeometryError("invalid_geometry")
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
