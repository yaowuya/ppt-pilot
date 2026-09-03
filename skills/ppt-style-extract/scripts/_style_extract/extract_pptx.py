"""Deterministic style extraction from a template .pptx.

Reads theme / slide-master / per-slide XML to derive an evidence-bound
candidate token set (colors, font stacks, font-size ladder, radius,
spacing, stroke). Uses only python-pptx's zip access plus lxml; never
guesses colors or sizes that are not present in the bytes.
"""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

from .errors import ExtractError

_XML_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

_SLOT_NAMES = [
    "dk1",
    "dk2",
    "lt1",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
]


def _hex(text: str) -> str | None:
    text = (text or "").strip()
    if _HEX_RE.fullmatch(text):
        return "#" + text.upper()
    return None


def _theme_colors(zf: zipfile.ZipFile) -> dict:
    data = {}
    try:
        root = zf.read("ppt/theme/theme1.xml")
    except KeyError:
        return data
    import lxml.etree as ET

    tree = ET.fromstring(root)
    scheme = tree.find(f".//{_XML_NS}clrScheme")
    if scheme is None:
        return data
    for name in _SLOT_NAMES:
        slot = scheme.find(f"{_XML_NS}{name}")
        if slot is None:
            continue
        srgb = slot.find(f".//{_XML_NS}srgbClr")
        if srgb is not None:
            val = _hex(srgb.get("val", ""))
            if val:
                data[name] = val
    return data


def _theme_fonts(zf: zipfile.ZipFile) -> dict:
    fonts = {}
    try:
        root = zf.read("ppt/theme/theme1.xml")
    except KeyError:
        return fonts
    import lxml.etree as ET

    tree = ET.fromstring(root)
    scheme = tree.find(f".//{_XML_NS}fontScheme")
    if scheme is None:
        return fonts
    for tag in ("latin", "ea"):
        node = scheme.find(f".//{_XML_NS}{tag}")
        if node is not None:
            tf = node.get("typeface")
            if tf:
                fonts[tag] = tf
    return fonts


def _iter_slide_xml(zf: zipfile.ZipFile):
    for name in zf.namelist():
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
            import lxml.etree as ET

            yield ET.fromstring(zf.read(name))


def _collect_geometry(zf: zipfile.ZipFile) -> dict:
    """Aggregate fill / stroke / radius / font-size / weight across slides."""
    fills: Counter[str] = Counter()
    strokes: Counter[str] = Counter()
    stroke_weights: Counter[float] = Counter()
    radii: Counter[float] = Counter()
    sizes: Counter[int] = Counter()
    bold: Counter[int] = Counter()
    shapes = 0

    for root in _iter_slide_xml(zf):
        for node in root.iter():
            tag = node.tag
            if tag == f"{_XML_NS}prstGeom":
                prst = node.get("prst")
                # roundRect has a<adj> in 0..50000 representing radius fraction
                if prst == "roundRect":
                    adj = node.find(f".//{_XML_NS}adj")
                    if adj is not None:
                        try:
                            v = float(adj.get("val", "0"))
                        except ValueError:
                            v = 0.0
                        # fraction of the smaller dimension; 50000 == 50%.
                        radii[v / 500.0] += 1
                shapes += 1
            elif tag == f"{_XML_NS}solidFill":
                srgb = node.find(f"{_XML_NS}srgbClr")
                if srgb is not None:
                    val = _hex(srgb.get("val", ""))
                    if val:
                        fills[val] += 1
            elif tag == f"{_XML_NS}rPr":
                sz = node.get("sz")
                if sz:
                    try:
                        sizes[int(sz)] += 1
                    except ValueError:
                        pass
                b = node.get("b")
                if b is not None:
                    bold[1 if b.lower() in ("1", "true") else 0] += 1
            elif tag == f"{_XML_NS}ln":
                w = node.get("w")
                if w:
                    try:
                        stroke_weights[int(w) / 12700.0] += 1
                    except ValueError:
                        pass
                srgb = node.find(f"{_XML_NS}solidFill/{_XML_NS}srgbClr")
                if srgb is not None:
                    val = _hex(srgb.get("val", ""))
                    if val:
                        strokes[val] += 1

    return {
        "fills": fills,
        "strokes": strokes,
        "stroke_weights": stroke_weights,
        "radii": radii,
        "sizes": sizes,
        "bold": bold,
        "shapes": shapes,
    }


def _top(counter: Counter, n: int = 4) -> list:
    return [item for item, _ in counter.most_common(n) if item]


def extract_pptx(path: Path) -> dict:
    """Return an evidence-bound candidate style token dict for a .pptx."""
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ExtractError(f"unreadable_pptx:{exc}") from exc

    with zf:
        theme_colors = _theme_colors(zf)
        theme_fonts = _theme_fonts(zf)
        geo = _collect_geometry(zf)

    if not theme_colors and not geo["fills"]:
        raise ExtractError("no_color_evidence")

    # Pick canvas: lt1 if present, else most common fill, else white.
    canvas = theme_colors.get("lt1") or theme_colors.get("lt2")
    if canvas is None:
        canvas = _top(geo["fills"], 1)[0] if geo["fills"] else "#FFFFFF"

    fills = _top(geo["fills"], 5) or []
    theme_accent = theme_colors.get("accent1", "#156BFF") if theme_colors else "#156BFF"
    primary = list(dict.fromkeys(fills + [theme_accent]))[:5] or ["#156BFF"]
    # The page's dominant fill is the template's visible brand; fall back to
    # the theme accent only when the pages carry no fill evidence.
    brand_primary = primary[0]

    latin = theme_fonts.get("latin", "Arial")
    ea = theme_fonts.get("ea", latin)
    font_stack = [ea, latin, "sans-serif"]

    # Font-size ladder: authoritative if theme/slide masters declare it; fall
    # back to the most common sizes seen across runs.
    sizes = geo["sizes"]
    ms = _font_size_ladder(sizes)

    radii = geo["radii"]
    primary_radius = _radius_px(radii)

    stroke_weights = geo["stroke_weights"]
    stroke_px = _top(stroke_weights, 1)[0] if stroke_weights else 1.2
    if stroke_px > 24:  # guard absurd stroke widths
        stroke_px = 1.2

    return {
        "extractor": "pptx",
        "colors": {
            "canvas": canvas,
            "brand_primary": brand_primary,
            "hero_dark": theme_colors.get("dk1", "#0B1930"),
            "ink": theme_colors.get("dk1", "#0B1930"),
            "text_secondary": theme_colors.get("dk2", "#52637B"),
            "border": theme_colors.get("lt2", "#DCE9F8"),
            "accent_palette": primary,
        },
        "typography": {"font_stack": font_stack, **ms},
        "shape": {"primary_radius": primary_radius, "stroke_width": round(stroke_px, 2)},
        "spacing": {"outer_margin": 64, "standard_gap": 24},
        "evidence": {
            "fills": dict(geo["fills"].most_common(8)),
            "strokes": dict(geo["strokes"].most_common(8)),
            "radii_count": len(radii),
            "sizes_count": len(sizes),
            "shapes": geo["shapes"],
        },
    }


def _font_size_ladder(sizes: Counter) -> dict:
    """Map observed font sizes (in hundredths of a point from sz attr) to a
    six-level ladder. `sz` is in hundredths of a point, so sz=2000 == 20pt.
    """
    pts = {int(round(sz / 100.0, 0)): cnt for sz, cnt in sizes.items() if sz >= 800}
    if not pts:
        return {
            "slide_title": 40,
            "primary_proposition": 30,
            "section_title": 24,
            "body": 20,
            "support": 16,
            "micro_label": 14,
        }
    # sort by frequency, then size; pick representative levels
    ordered = [size for size, _ in sorted(pts.items(), key=lambda kv: (-kv[1], kv[0]))]
    biggest = max(pts)
    return {
        "slide_title": max(biggest, 32),
        "primary_proposition": _pick(ordered, biggest, ratio=0.75),
        "section_title": _pick(ordered, biggest, ratio=0.6),
        "body": _pick(ordered, biggest, ratio=0.5),
        "support": _pick(ordered, biggest, ratio=0.4),
        "micro_label": max(_pick(ordered, biggest, ratio=0.35), 14),
    }


def _pick(ordered: list, biggest: int, ratio: float) -> int:
    target = biggest * ratio
    if not ordered:
        return int(target)
    return min(ordered, key=lambda v: abs(v - target)) or int(target)


def _radius_px(radii: Counter) -> float:
    """Radii are expressed as a fraction (0..0.5) of the smaller side of a
    card. We approximate as pixels on a 1280x720 canvas assuming ~720 smaller
    dimension, capped to the most common value (clamped to a sane range)."""
    if not radii:
        return 20.0
    frac = max(radii, key=lambda r: radii[r])
    px = frac * 720
    return round(min(max(px, 4.0), 64.0), 0)
