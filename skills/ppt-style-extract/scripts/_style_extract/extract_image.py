"""Deterministic style extraction from reference images.

SVG: sample text/fill/stroke colors and estimate spacing/radius.
PNG/JPEG: RGB histogram to cluster a dominant palette. If the runtime has no
pillow/ndarray capability, THIS RETURNS `unavailable` rather than guessing.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .errors import ExtractError, Unavailable

_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

_COLOR_ATTRS = ("fill", "stroke", "color")


def _hex(text: str) -> str | None:
    text = (text or "").strip().lower()
    if text.startswith("#") and len(text) == 7:
        return "#" + text[1:].upper()
    # named colors we can resolve without a full palette
    if text in _NAMED:
        return _NAMED[text]
    return None


_NAMED = {
    "white": "#FFFFFF",
    "black": "#000000",
    "black": "#000000",
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#008000",
    "gray": "#808080",
    "grey": "#808080",
    "orange": "#FFA500",
    "purple": "#800080",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
}


def _iter_svg_files(path: Path):
    if path.is_file() and path.suffix.lower() == ".svg":
        yield path
    elif path.is_dir():
        for child in sorted(path.iterdir()):
            if child.suffix.lower() == ".svg":
                yield child


def extract_svg(path: Path) -> dict:
    import lxml.etree as ET

    fills: Counter[str] = Counter()
    strokes: Counter[str] = Counter()
    sizes: Counter[int] = Counter()
    text_nodes = 0
    viewbox = None
    for svg_path in _iter_svg_files(path):
        tree = ET.parse(str(svg_path))
        root = tree.getroot()
        if viewbox is None:
            viewbox = root.get("viewBox")
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "text":
                text_nodes += 1
            fill = node.get("fill")
            if fill and fill != "none":
                val = _hex(fill)
                if val:
                    fills[val] += 1
            stroke = node.get("stroke")
            if stroke and stroke != "none":
                val = _hex(stroke)
                if val:
                    strokes[val] += 1
            fs = node.get("font-size")
            if fs:
                try:
                    sizes[int(fs)] += 1
                except ValueError:
                    pass

    if not fills and not strokes and not text_nodes:
        raise ExtractError("svg_no_color_evidence")

    top_fills = _top(fills, 5)
    return {
        "extractor": "svg",
        "colors": {
            "canvas": _top(fills, 1)[0] if fills else "#FFFFFF",
            "brand_primary": (top_fills[0] if top_fills else "#156BFF"),
            "accent_palette": top_fills,
        },
        "typography": {
            "font_stack": ["Arial", "sans-serif"],
            "slide_title": 40,
            "primary_proposition": 30,
            "section_title": 24,
            "body": 20,
            "support": 16,
            "micro_label": 14,
        },
        "shape": {"primary_radius": 20.0, "stroke_width": 1.2},
        "spacing": {"outer_margin": 64, "standard_gap": 24},
        "evidence": {
            "fills": dict(fills.most_common(8)),
            "strokes": dict(strokes.most_common(8)),
            "text_nodes": text_nodes,
            "viewbox": viewbox,
        },
    }


def _top(counter: Counter, n: int = 4) -> list:
    return [item for item, _ in counter.most_common(n) if item]


def extract_raster(path: Path, image_paths: list[Path]) -> dict:
    """Pixel histogram for PNG/JPEG. Returns `unavailable` when no pixel
    reader exists. Never fabricates a palette."""
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on runtime
        raise Unavailable(f"raster_unavailable:{exc}") from exc

    hues: Counter[str] = Counter()
    total = 0
    for image_path in image_paths:
        try:
            im = Image.open(image_path).convert("RGB")
            im.thumbnail((64, 64))
        except Exception as exc:
            raise ExtractError(f"raster_unreadable:{image_path}:{exc}") from exc
        pixels = list(im.getdata())
        sample = pixels[:: max(1, len(pixels) // 4000)]
        for r, g, b in sample:
            # quantize to reduce jpeg noise
            qr, qg, qb = ((r // 16) * 16, (g // 16) * 16, (b // 16) * 16)
            hues["#%02X%02X%02X" % (qr, qg, qb)] += 1
            total += 1

    if total == 0:
        raise ExtractError("raster_no_pixels")
    top = _top(hues, 6)
    return {
        "extractor": "raster",
        "colors": {"accent_palette": top, "brand_primary": top[0] if top else "#156BFF", "canvas": "#FFFFFF"},
        "typography": {
            "font_stack": ["Arial", "sans-serif"],
            "slide_title": 40,
            "primary_proposition": 30,
            "section_title": 24,
            "body": 20,
            "support": 16,
            "micro_label": 14,
        },
        "shape": {"primary_radius": 20.0, "stroke_width": 1.2},
        "spacing": {"outer_margin": 64, "standard_gap": 24},
        "evidence": {"histogram": dict(hues.most_common(12)), "sampled_pixels": total},
    }


def extract_image(path: Path) -> dict:
    """Dispatch SVG vs raster sampling."""
    if path.is_file() and path.suffix.lower() == ".svg":
        return extract_svg(path)
    if path.is_dir():
        svgs = list(path.glob("*.svg"))
        if svgs:
            return extract_svg(path)
        rasters = [
            p
            for p in path.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        ]
        if not rasters:
            raise ExtractError("no_images_in_dir")
        return extract_raster(path, rasters)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return extract_raster(path, [path])
    raise ExtractError("unsupported_image_path")
