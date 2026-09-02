"""Immutable data exchanged by ppt-editable conversion stages."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Optional, Tuple

from .errors import validate_failure_reason


@dataclass(frozen=True)
class Failure:
    code: str
    slide_id: Optional[str]
    svg_tree_path: Optional[str]
    element_type: Optional[str]
    message: str
    remediation: str

    def __post_init__(self) -> None:
        validate_failure_reason(self.code)


@dataclass(frozen=True)
class Bounds:
    left: float
    top: float
    right: float
    bottom: float

    def union(self, other: "Bounds") -> "Bounds":
        return Bounds(
            min(self.left, other.left),
            min(self.top, other.top),
            max(self.right, other.right),
            max(self.bottom, other.bottom),
        )

    def expanded(self, amount: float) -> "Bounds":
        return Bounds(
            self.left - amount,
            self.top - amount,
            self.right + amount,
            self.bottom + amount,
        )


@dataclass(frozen=True)
class ResolvedStyle:
    fill: Optional[str] = None
    stroke: Optional[str] = None
    stroke_width: float = 0.0
    fill_opacity: float = 1.0
    stroke_opacity: float = 1.0
    opacity: float = 1.0
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    letter_spacing: float = 0.0
    text_anchor: str = "start"
    data_source_id: Optional[str] = None


@dataclass(frozen=True)
class TextRun:
    text: str
    style: ResolvedStyle
    preserve_space: bool = False


@dataclass(frozen=True)
class TextLine:
    line_index: int
    x: float
    y: float
    anchor: str
    runs: Tuple[TextRun, ...]
    bounds: Bounds


@dataclass(frozen=True)
class SvgNode:
    kind: str
    tree_path: str
    style: ResolvedStyle
    bounds: Bounds
    attributes: Tuple[Tuple[str, str], ...] = ()
    children: Tuple["SvgNode", ...] = ()
    text_lines: Tuple[TextLine, ...] = ()


@dataclass(frozen=True)
class SpeakerNotes:
    assertion_title: Optional[str] = None
    audience_takeaway: Optional[str] = None
    next_link: Optional[str] = None


@dataclass(frozen=True)
class SlidePlan:
    slide_id: str
    source_path: Path
    title: Optional[str]
    description: Optional[str]
    nodes: Tuple[SvgNode, ...]
    notes: SpeakerNotes


@dataclass(frozen=True)
class DeckPlan:
    deck_id: str
    input_snapshot_id: str
    slides: Tuple[SlidePlan, ...]
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EditableResult:
    status: str
    deck_id: str
    input_snapshot_id: str
    slide_count: int
    output_path: Optional[str] = None
    output_sha256: Optional[str] = None
    failures: Tuple[Failure, ...] = ()
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationConfig:
    schema_version: int
    render_width: int
    render_height: int
    full_page_grayscale_mad_max: float
    geometry_only_grayscale_mad_max: float
    geometry_tile_size: int
    geometry_tile_mad_max: float
    bounds_tolerance_px: float

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("schema_version must be the integer 1")

        for field_name in ("render_width", "render_height", "geometry_tile_size"):
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0:
                raise ValueError("{} must be a positive integer".format(field_name))

        for field_name in (
            "full_page_grayscale_mad_max",
            "geometry_only_grayscale_mad_max",
            "geometry_tile_mad_max",
            "bounds_tolerance_px",
        ):
            value = getattr(self, field_name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("{} must be a finite nonnegative number".format(field_name))
            object.__setattr__(self, field_name, float(value))
