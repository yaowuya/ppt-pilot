"""Full-resolution visual comparison for source and editable PowerPoint renders."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import io
import os
from pathlib import Path
import stat
from typing import Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError

from .atomic_io import atomic_write_bytes, atomic_write_json
from .contract import validate_safe_regular_file, validate_slide_id
from .errors import EditableError
from .model import Failure, VerificationConfig


@dataclass(frozen=True)
class TileMetric:
    x: int
    y: int
    width: int
    height: int
    mad: float
    passed: bool


@dataclass(frozen=True)
class SlideVisualReport:
    slide_id: str
    passed: bool
    full_page_mad: Optional[float]
    geometry_mad: Optional[float]
    tiles: Tuple[TileMetric, ...]
    failures: Tuple[Failure, ...]
    full_diff_path: Optional[str] = None
    geometry_diff_path: Optional[str] = None
    tile_report_path: Optional[str] = None

    def to_dict(self):
        return {
            "slide_id": self.slide_id,
            "passed": self.passed,
            "full_page_mad": self.full_page_mad,
            "geometry_mad": self.geometry_mad,
            "tiles": [asdict(tile) for tile in self.tiles],
            "failures": [asdict(failure) for failure in self.failures],
            "full_diff_path": self.full_diff_path,
            "geometry_diff_path": self.geometry_diff_path,
            "tile_report_path": self.tile_report_path,
        }


@dataclass(frozen=True)
class VisualReport:
    passed: bool
    slides: Tuple[SlideVisualReport, ...]
    failures: Tuple[Failure, ...]

    def to_dict(self):
        return {
            "schema_version": 1,
            "kind": "ppt_editable_visual_verification",
            "status": "passed" if self.passed else "failed",
            "slides": [slide.to_dict() for slide in self.slides],
            "failures": [asdict(failure) for failure in self.failures],
        }


@dataclass(frozen=True)
class RenderPaths:
    source_full_dir: Path
    editable_full_dir: Path
    source_geometry_dir: Path
    editable_geometry_dir: Path
    comparison_dir: Path


def _failure(
    slide_id: Optional[str],
    message: str,
    *,
    evidence_available: bool = True,
) -> Failure:
    remediation = (
        "inspect the saved full, geometry, and tile difference evidence"
        if evidence_available
        else "repair or regenerate the missing/invalid render evidence"
    )
    return Failure(
        code="visual_mismatch",
        slide_id=slide_id,
        svg_tree_path=None,
        element_type=None,
        message=message,
        remediation=remediation,
    )


def _safe_read_bytes(path: Path) -> bytes:
    path = Path(path)
    safe_path = validate_safe_regular_file(path, (path.parent,))
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(str(safe_path), flags)
    try:
        metadata = os.fstat(descriptor)
        limit = 100 * 1024 * 1024
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise ValueError("render file is not a bounded regular file")
        chunks = []
        total = 0
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            while True:
                chunk = handle.read(min(1024 * 1024, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise ValueError("render file exceeded the read limit")
        final_metadata = os.fstat(descriptor)
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    post_path = validate_safe_regular_file(path, (path.parent,))
    post_metadata = os.stat(str(post_path))
    if (
        not os.path.samestat(metadata, post_metadata)
        or final_metadata.st_size != metadata.st_size
        or post_metadata.st_size != metadata.st_size
        or len(data) != metadata.st_size
        or getattr(final_metadata, "st_mtime_ns", None)
        != getattr(metadata, "st_mtime_ns", None)
        or getattr(post_metadata, "st_mtime_ns", None)
        != getattr(metadata, "st_mtime_ns", None)
    ):
        raise ValueError("render file changed during validated read")
    return data


def _load_grayscale(path: Path, config: VerificationConfig) -> Image.Image:
    data = _safe_read_bytes(Path(path))
    with Image.open(io.BytesIO(data)) as image:
        if image.size != (config.render_width, config.render_height):
            raise ValueError(
                "render dimensions {} do not equal {}x{}".format(
                    image.size,
                    config.render_width,
                    config.render_height,
                )
            )
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", image.size, color=(255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("L")


def _difference_mad(difference: Image.Image) -> float:
    if difference.mode != "L":
        raise ValueError("difference image must be grayscale")
    return float(ImageStat.Stat(difference).mean[0])


def grayscale_mad(reference: Image.Image, actual: Image.Image) -> float:
    if reference.mode != "L" or actual.mode != "L" or reference.size != actual.size:
        raise ValueError("MAD inputs must be equal-sized grayscale images")
    return _difference_mad(ImageChops.difference(reference, actual))


def _tile_mads_from_difference(
    difference: Image.Image,
    tile_size: int,
    threshold: float,
) -> Tuple[TileMetric, ...]:
    if tile_size <= 0 or difference.mode != "L":
        raise ValueError("tile difference input is invalid")
    width, height = difference.size
    result = []
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            right = min(width, x + tile_size)
            bottom = min(height, y + tile_size)
            mad = _difference_mad(difference.crop((x, y, right, bottom)))
            result.append(
                TileMetric(
                    x=x,
                    y=y,
                    width=right - x,
                    height=bottom - y,
                    mad=mad,
                    passed=mad <= threshold,
                )
            )
    return tuple(result)


def tile_mads(
    reference: Image.Image,
    actual: Image.Image,
    tile_size: int,
    threshold: float,
) -> Tuple[TileMetric, ...]:
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")
    if reference.mode != "L" or actual.mode != "L" or reference.size != actual.size:
        raise ValueError("tile inputs must be equal-sized grayscale images")
    return _tile_mads_from_difference(
        ImageChops.difference(reference, actual),
        tile_size,
        threshold,
    )


def _png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def compare_slide_renders(
    slide_id: str,
    source_full: Path,
    editable_full: Path,
    source_geometry: Path,
    editable_geometry: Path,
    config: VerificationConfig,
    evidence_dir: Optional[Path] = None,
) -> SlideVisualReport:
    try:
        validate_slide_id(slide_id)
    except EditableError as exc:
        return SlideVisualReport(
            slide_id=slide_id,
            passed=False,
            full_page_mad=None,
            geometry_mad=None,
            tiles=(),
            failures=(
                _failure(
                    slide_id,
                    str(exc),
                    evidence_available=False,
                ),
            ),
        )
    failures = []
    try:
        full_reference = _load_grayscale(Path(source_full), config)
        full_actual = _load_grayscale(Path(editable_full), config)
        geometry_reference = _load_grayscale(Path(source_geometry), config)
        geometry_actual = _load_grayscale(Path(editable_geometry), config)
    except (
        EditableError,
        OSError,
        ValueError,
        SyntaxError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        return SlideVisualReport(
            slide_id=slide_id,
            passed=False,
            full_page_mad=None,
            geometry_mad=None,
            tiles=(),
            failures=(
                _failure(
                    slide_id,
                    str(exc),
                    evidence_available=False,
                ),
            ),
        )
    full_difference = ImageChops.difference(full_reference, full_actual)
    geometry_difference = ImageChops.difference(geometry_reference, geometry_actual)
    full_mad = _difference_mad(full_difference)
    geometry_mad = _difference_mad(geometry_difference)
    tiles = _tile_mads_from_difference(
        geometry_difference,
        config.geometry_tile_size,
        config.geometry_tile_mad_max,
    )
    evidence_requested = evidence_dir is not None
    if full_mad > config.full_page_grayscale_mad_max:
        failures.append(
            _failure(
                slide_id,
                "full-page MAD exceeds threshold",
                evidence_available=evidence_requested,
            )
        )
    if geometry_mad > config.geometry_only_grayscale_mad_max:
        failures.append(
            _failure(
                slide_id,
                "geometry-only MAD exceeds threshold",
                evidence_available=evidence_requested,
            )
        )
    if any(not tile.passed for tile in tiles):
        failures.append(
            _failure(
                slide_id,
                "one or more geometry tiles exceed threshold",
                evidence_available=evidence_requested,
            )
        )

    full_diff_path = geometry_diff_path = tile_report_path = None
    if evidence_dir is not None:
        evidence_dir = Path(evidence_dir)
        full_diff = evidence_dir / (slide_id + "-full-diff.png")
        geometry_diff = evidence_dir / (slide_id + "-geometry-diff.png")
        tile_report = evidence_dir / (slide_id + "-tiles.json")
        evidence_paths = (full_diff, geometry_diff, tile_report)
        previous_evidence = {}
        backup_complete = False
        try:
            for evidence_path in evidence_paths:
                if os.path.lexists(str(evidence_path)):
                    previous_evidence[evidence_path] = _safe_read_bytes(evidence_path)
            backup_complete = True
            atomic_write_bytes(full_diff, _png_bytes(full_difference))
            atomic_write_bytes(geometry_diff, _png_bytes(geometry_difference))
            atomic_write_json(
                tile_report,
                {
                    "schema_version": 1,
                    "slide_id": slide_id,
                    "tiles": [asdict(tile) for tile in tiles],
                },
            )
        except (EditableError, OSError, ValueError) as exc:
            rollback_errors = []
            if backup_complete:
                for evidence_path in evidence_paths:
                    try:
                        if evidence_path in previous_evidence:
                            atomic_write_bytes(
                                evidence_path,
                                previous_evidence[evidence_path],
                            )
                        elif os.path.lexists(str(evidence_path)):
                            evidence_path.unlink()
                    except (EditableError, OSError) as rollback_error:
                        rollback_errors.append(str(rollback_error))
            details = "visual evidence write failed: {}".format(exc)
            if rollback_errors:
                details += "; rollback failed: " + "; ".join(rollback_errors)
            failures[:] = [
                replace(
                    failure,
                    remediation="repair visual evidence persistence and rerun comparison",
                )
                for failure in failures
            ]
            failures.append(
                _failure(
                    slide_id,
                    details,
                    evidence_available=False,
                )
            )
        else:
            full_diff_path = full_diff.relative_to(evidence_dir).as_posix()
            geometry_diff_path = geometry_diff.relative_to(evidence_dir).as_posix()
            tile_report_path = tile_report.relative_to(evidence_dir).as_posix()
    return SlideVisualReport(
        slide_id=slide_id,
        passed=not failures,
        full_page_mad=full_mad,
        geometry_mad=geometry_mad,
        tiles=tiles,
        failures=tuple(failures),
        full_diff_path=full_diff_path,
        geometry_diff_path=geometry_diff_path,
        tile_report_path=tile_report_path,
    )


def compare_render_sets(
    paths: RenderPaths,
    slide_ids: Sequence[str],
    config: VerificationConfig,
) -> VisualReport:
    slide_ids = tuple(slide_ids)
    try:
        for slide_id in slide_ids:
            validate_slide_id(slide_id)
    except EditableError:
        failure = _failure(None, "slide IDs must use canonical S<digits> form", evidence_available=False)
        result = VisualReport(False, (), (failure,))
        atomic_write_json(paths.comparison_dir / "visual-summary.json", result.to_dict())
        return result
    if not slide_ids or len(slide_ids) != len(set(slide_ids)):
        failure = _failure(
            None,
            "slide IDs must be nonempty and unique",
            evidence_available=False,
        )
        result = VisualReport(False, (), (failure,))
        atomic_write_json(paths.comparison_dir / "visual-summary.json", result.to_dict())
        return result
    slides = []
    failures = []
    for slide_id in slide_ids:
        report = compare_slide_renders(
            slide_id,
            paths.source_full_dir / (slide_id + ".png"),
            paths.editable_full_dir / (slide_id + ".png"),
            paths.source_geometry_dir / (slide_id + ".png"),
            paths.editable_geometry_dir / (slide_id + ".png"),
            config,
            evidence_dir=paths.comparison_dir,
        )
        slides.append(report)
        failures.extend(report.failures)
    result = VisualReport(
        passed=not failures and len(slides) == len(slide_ids),
        slides=tuple(slides),
        failures=tuple(failures),
    )
    atomic_write_json(paths.comparison_dir / "visual-summary.json", result.to_dict())
    return result
