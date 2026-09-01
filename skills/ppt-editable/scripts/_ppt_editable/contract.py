"""Completed-run discovery and deterministic slide-source ownership."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import EditableError


_SLIDE_ID_RE = re.compile(r"^S([0-9]+)$")
_STORYBOARD_SECTION_RE = re.compile(
    r"(?m)^##[ \t]+(S[0-9]+)(?:(?:[ \t]+[^\r\n]*)|(?:[（(][^\r\n]*[）)]))?[ \t]*$"
)
_ALL_H2_RE = re.compile(r"(?m)^##[ \t]+(?P<title>[^\r\n]+?)[ \t]*$")
_STORYBOARD_FIELD_RE = re.compile(
    r"(?m)^\s*(?:-\s*)?(?:"
    r"\*\*(?P<bold>assertion_title|audience_takeaway|next_link)\*\*|"
    r"`(?P<code>assertion_title|audience_takeaway|next_link)`|"
    r"(?P<plain>assertion_title|audience_takeaway|next_link)"
    r")\s*[：:]\s*(?P<value>.*?)\s*$"
)
_REPARSE_ATTRIBUTE = 0x400
_WINDOWS_FORBIDDEN = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM{}".format(index) for index in range(1, 10)}
    | {"LPT{}".format(index) for index in range(1, 10)}
)


@dataclass(frozen=True)
class StoryboardSlide:
    slide_id: str
    assertion_title: Optional[str]
    audience_takeaway: Optional[str]
    next_link: Optional[str]


@dataclass(frozen=True)
class RunContext:
    run_dir: Path
    deck_id: str
    run_data: Mapping[str, Any]
    storyboard_path: Path
    quality_report_path: Path
    slides_dir: Path
    samples_dir: Path


@dataclass(frozen=True)
class SlideSource:
    slide_id: str
    path: Path
    relative_path: str
    owner: str
    svg_sha256: str = ""


def _error(code: str, message: str, remediation: str = "") -> EditableError:
    return EditableError(code, message, remediation=remediation)


def _slide_number(slide_id: str) -> int:
    match = _SLIDE_ID_RE.fullmatch(slide_id)
    if match is None:
        raise _error("slide_set_invalid", "invalid slide id: {}".format(slide_id))
    return int(match.group(1))


def validate_slide_id(value: str) -> str:
    _slide_number(value)
    return value


def _is_reparse_stat(value: object) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE)


def _path_chain(path: Path) -> Tuple[Path, ...]:
    absolute = path.absolute()
    chain = []
    current = absolute
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    chain.reverse()
    return tuple(chain)


def _reject_link_components(path: Path) -> None:
    for component in _path_chain(path):
        try:
            metadata = os.lstat(str(component))
        except OSError as exc:
            raise _error("source_unreadable", "cannot inspect path: {}".format(component)) from exc
        if stat.S_ISLNK(metadata.st_mode) or _is_reparse_stat(metadata):
            raise _error("source_path_unsafe", "linked path component: {}".format(component))


def validate_safe_regular_file(candidate: Path, allowed_roots: Sequence[Path]) -> Path:
    candidate = Path(candidate).absolute()
    lexical_owner = None
    for allowed in allowed_roots:
        allowed_absolute = Path(allowed).absolute()
        try:
            candidate.relative_to(allowed_absolute)
        except ValueError:
            continue
        lexical_owner = allowed_absolute
        break
    if lexical_owner is None:
        raise _error("source_path_unsafe", "source escapes allowed roots")

    _reject_link_components(lexical_owner)
    _reject_link_components(candidate)
    try:
        owner_resolved = lexical_owner.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
        candidate_resolved.relative_to(owner_resolved)
        metadata = os.stat(str(candidate_resolved))
    except (OSError, ValueError) as exc:
        raise _error("source_path_unsafe", "source containment failed") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise _error("source_path_unsafe", "source is not a regular file")
    try:
        with candidate_resolved.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise _error("source_unreadable", "source cannot be read") from exc
    return candidate_resolved


def _has_run_control(path: Path) -> bool:
    return (path / ".ppt-pilot" / "run.json").is_file()


def _is_completed_candidate(path: Path) -> bool:
    try:
        return validate_completed_run(path).run_data.get("stage") == "complete"
    except EditableError:
        return False


def locate_run(
    explicit_run_dir: Optional[Path],
    cwd: Path,
    ppt_output_root: Optional[Path],
) -> Path:
    if explicit_run_dir is not None:
        selected = Path(explicit_run_dir).absolute()
        if not os.path.lexists(str(selected)):
            raise _error("run_not_found", "explicit run does not exist")
        _reject_link_components(selected)
        if not selected.is_dir() or not _has_run_control(selected):
            raise _error("run_not_found", "explicit run has no control file")
        return selected.resolve()

    current = Path(cwd).absolute()
    if _has_run_control(current) and _is_completed_candidate(current):
        return current.resolve()

    root = Path(ppt_output_root).absolute() if ppt_output_root is not None else current / "ppt-output"
    if not root.is_dir():
        raise _error("run_not_found", "ppt-output root does not exist")
    candidates = tuple(
        child.resolve()
        for child in sorted(root.iterdir(), key=lambda value: value.name)
        if child.is_dir() and _is_completed_candidate(child)
    )
    if not candidates:
        raise _error("run_not_found", "no completed PPT Pilot run found")
    if len(candidates) != 1:
        raise _error("run_ambiguous", "multiple completed PPT Pilot runs found")
    return candidates[0]


def _unique_json_object(pairs: Sequence[Tuple[str, Any]]) -> Mapping[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant: {}".format(value))


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _load_run_json(path: Path) -> Mapping[str, Any]:
    try:
        with path.open(encoding="utf-8-sig") as handle:
            value = json.load(
                handle,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise _error("source_unreadable", "run.json is unreadable") from exc
    if not isinstance(value, dict):
        raise _error("source_unreadable", "run.json must be an object")
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise _error("source_unreadable", "run.json schema_version must equal integer 1")
    return _deep_freeze(value)


def _select_storyboard(control_dir: Path) -> Path:
    current = control_dir / "故事板.md"
    legacy = control_dir / "storyboard.md"
    existing = tuple(path for path in (current, legacy) if os.path.lexists(str(path)))
    if not existing:
        raise _error("storyboard_missing", "storyboard owner is missing")
    if len(existing) != 1:
        raise _error("storyboard_ambiguous", "multiple storyboard owners exist")
    return validate_safe_regular_file(existing[0], (control_dir,))


def _deck_id_is_safe(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    if value in (".", "..") or value[-1] in (".", " "):
        return False
    if any(ord(character) < 32 or character in _WINDOWS_FORBIDDEN for character in value):
        return False
    device_stem = value.split(".", 1)[0].upper()
    return device_stem not in _WINDOWS_RESERVED


def validate_completed_run(run_dir: Path) -> RunContext:
    run_dir = Path(run_dir).absolute()
    if not run_dir.is_dir():
        raise _error("run_not_found", "run directory does not exist")
    _reject_link_components(run_dir)
    control_dir = run_dir / ".ppt-pilot"
    run_path = validate_safe_regular_file(control_dir / "run.json", (control_dir,))
    run_data = _load_run_json(run_path)
    if run_data.get("stage") != "complete":
        raise _error("run_not_complete", "run.json.stage must equal complete")
    deck_id = run_data.get("deck_id")
    if not _deck_id_is_safe(deck_id):
        raise _error("deck_id_invalid", "deck_id is not path-safe")
    storyboard_path = _select_storyboard(control_dir)
    quality_path = control_dir / "质量检查报告.md"
    if not quality_path.exists():
        raise _error("quality_report_missing", "quality report is missing")
    quality_path = validate_safe_regular_file(quality_path, (control_dir,))
    return RunContext(
        run_dir=run_dir.resolve(),
        deck_id=deck_id,
        run_data=run_data,
        storyboard_path=storyboard_path,
        quality_report_path=quality_path,
        slides_dir=run_dir / "slides",
        samples_dir=run_dir / "samples",
    )


def parse_storyboard(path: Path) -> Tuple[StoryboardSlide, ...]:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise _error("storyboard_missing", "storyboard cannot be read") from exc
    matches = tuple(_STORYBOARD_SECTION_RE.finditer(text))
    if not matches:
        raise _error("slide_set_invalid", "storyboard has no slide sections")
    valid_starts = {match.start() for match in matches}
    first_slide_start = matches[0].start()
    for heading in _ALL_H2_RE.finditer(text):
        title = heading.group("title").strip()
        if heading.start() not in valid_starts and (
            heading.start() >= first_slide_start or title.startswith("S")
        ):
            raise _error("slide_set_invalid", "malformed slide heading: {}".format(title))
    slides = []
    seen = set()
    for index, match in enumerate(matches):
        slide_id = match.group(1)
        if slide_id in seen:
            raise _error("slide_set_invalid", "duplicate storyboard slide id")
        seen.add(slide_id)
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():body_end]
        fields = {}
        for field_match in _STORYBOARD_FIELD_RE.finditer(body):
            key = (
                field_match.group("bold")
                or field_match.group("code")
                or field_match.group("plain")
            )
            value = field_match.group("value")
            if key in fields:
                raise _error("storyboard_ambiguous", "duplicate storyboard field")
            fields[key] = value
        slides.append(
            StoryboardSlide(
                slide_id=slide_id,
                assertion_title=fields.get("assertion_title"),
                audience_takeaway=fields.get("audience_takeaway"),
                next_link=fields.get("next_link"),
            )
        )
    numbers = [_slide_number(slide.slide_id) for slide in slides]
    if numbers != sorted(numbers) or len(numbers) != len(set(numbers)):
        raise _error("slide_set_invalid", "storyboard slides are not uniquely ordered")
    return tuple(slides)


def _svg_files(directory: Path, *, allow_candidates: bool = False) -> Mapping[str, Path]:
    if not os.path.lexists(str(directory)):
        return {}
    _reject_link_components(directory)
    try:
        metadata = os.stat(str(directory))
    except OSError as exc:
        raise _error("source_unreadable", "slide source root cannot be read") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise _error("source_path_unsafe", "slide source root is not a directory")
    result = {}
    try:
        with os.scandir(str(directory)) as entries:
            discovered = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise _error("source_unreadable", "slide source root cannot be enumerated") from exc
    for entry in discovered:
        try:
            entry_metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise _error("source_unreadable", "slide source entry cannot be inspected") from exc
        if entry.is_symlink() or _is_reparse_stat(entry_metadata):
            raise _error("source_path_unsafe", "linked source entry is not allowed")
        if stat.S_ISDIR(entry_metadata.st_mode):
            if allow_candidates and entry.name == ".candidates":
                continue
            raise _error("slide_set_invalid", "nested slide source directories are not allowed")
        if not stat.S_ISREG(entry_metadata.st_mode):
            raise _error("source_path_unsafe", "special source entry is not allowed")
        if not entry.name.startswith("S") or not entry.name.endswith(".svg"):
            continue
        path = directory / entry.name
        slide_id = path.stem
        _slide_number(slide_id)
        if slide_id in result:
            raise _error("slide_set_invalid", "duplicate slide source")
        result[slide_id] = path
    return result


def _source_sha256(path: Path) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise _error("source_unreadable", "slide source cannot be read") from exc
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _approved_anchor_paths(run_data: Mapping[str, Any]) -> Mapping[str, str]:
    generation = run_data.get("anchor_generation")
    if generation is None:
        return {}
    if not isinstance(generation, Mapping):
        raise _error("slide_set_invalid", "anchor_generation must be an object")
    anchors = generation.get("anchors", [])
    records = generation.get("records")
    legacy_results = generation.get("results")
    if records is not None and legacy_results is not None and records != legacy_results:
        raise _error("slide_set_invalid", "anchor ownership has competing record sets")
    ownership_rows = records if records is not None else legacy_results
    if ownership_rows is None:
        ownership_rows = []
    if not isinstance(anchors, (list, tuple)) or not isinstance(
        ownership_rows, (list, tuple)
    ):
        raise _error("slide_set_invalid", "anchor ownership is malformed")
    if any(not isinstance(value, str) for value in anchors) or len(anchors) != len(set(anchors)):
        raise _error("slide_set_invalid", "anchor IDs are invalid")
    resolved = {}
    for value in ownership_rows:
        if not isinstance(value, Mapping):
            raise _error("slide_set_invalid", "anchor result is malformed")
        slide_id = value.get("slide_id")
        output = value.get("output")
        if not isinstance(slide_id, str) or not isinstance(output, str) or slide_id in resolved:
            raise _error("slide_set_invalid", "anchor result is ambiguous")
        resolved[slide_id] = output
    return {
        slide_id: output
        for slide_id, output in resolved.items()
        if slide_id in anchors and output == "samples/{}.svg".format(slide_id)
    }


def resolve_slide_sources(
    context: RunContext,
    storyboard: Sequence[StoryboardSlide],
) -> Tuple[SlideSource, ...]:
    expected = tuple(slide.slide_id for slide in storyboard)
    if len(expected) != len(set(expected)) or not expected:
        raise _error("slide_set_invalid", "storyboard page set is invalid")
    production = _svg_files(context.slides_dir, allow_candidates=True)
    samples = _svg_files(context.samples_dir)
    if (set(production) | set(samples)) - set(expected):
        raise _error("slide_set_invalid", "source contains an unmatched page")
    approved = _approved_anchor_paths(context.run_data)
    if any(slide_id not in approved for slide_id in samples):
        raise _error("slide_set_invalid", "sample is not an approved anchor")

    selected = []
    for slide_id in expected:
        if slide_id in production:
            path = validate_safe_regular_file(production[slide_id], (context.slides_dir,))
            relative_path = "slides/{}.svg".format(slide_id)
            owner = "production"
        elif slide_id in samples and approved.get(slide_id) == "samples/{}.svg".format(slide_id):
            path = validate_safe_regular_file(samples[slide_id], (context.samples_dir,))
            relative_path = "samples/{}.svg".format(slide_id)
            owner = "approved_anchor"
        else:
            raise _error("slide_set_invalid", "expected slide source is missing")
        selected.append(
            SlideSource(
                slide_id=slide_id,
                path=path,
                relative_path=relative_path,
                owner=owner,
                svg_sha256=_source_sha256(path),
            )
        )
    return tuple(selected)
