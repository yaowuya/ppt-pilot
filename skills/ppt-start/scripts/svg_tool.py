#!/usr/bin/env python3
"""Stateless SVG extraction, finalization, and validation utility for PPT Pilot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


_RUNTIME_ERROR = None
try:
    from _svg_runtime import (
        extract_svg,
        finalize_candidate_svg,
        normalize_text_roles,
        validate_candidate_svg,
        validate_final_svg,
        validate_generator_svg,
        validate_title_min_size,
    )
except Exception as exc:  # pragma: no cover - exercised when packaged imports fail.
    _RUNTIME_ERROR = exc


class _ToolError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _ToolInvalid(_ToolError):
    pass


class _ToolUnavailable(_ToolError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ToolUnavailable("tool_invocation_invalid")


_KNOWN_INVALID_REASONS = frozenset(
    {
        "fact_source_mismatch",
        "generator_output_malformed",
        "source_map_invalid",
        "svg_contract_failed",
        "title_min_size_invalid",
    }
)


def _emit(status: str, operation: str, *, reason: str | None = None, warnings=()) -> int:
    payload: dict[str, Any] = {
        "operation": operation,
        "status": status,
        "warnings": list(warnings),
    }
    if reason is not None:
        payload["reason"] = reason
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return {"PASS": 0, "INVALID": 2, "UNAVAILABLE": 3}[status]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise _ToolInvalid("input_not_utf8") from exc
    except OSError as exc:
        raise _ToolUnavailable("input_unreadable") from exc


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _read_source_map(path: Path) -> Mapping[str, list[str]]:
    raw = _read_text(path)
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (TypeError, ValueError, RecursionError) as exc:
        raise _ToolInvalid("source_map_invalid") from exc
    if not isinstance(value, dict):
        raise _ToolInvalid("source_map_invalid")
    return value


def _title_floor(raw: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise _ToolInvalid("title_min_size_invalid") from exc
    try:
        return validate_title_min_size(value)
    except ValueError as exc:
        raise _ToolInvalid(str(exc)) from exc


def _temporary_file(path: Path, data: bytes) -> Path:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            prefix="." + path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path = Path(temporary)
        if temporary_path.read_bytes() != data:
            raise OSError("temporary output verification failed")
        return temporary_path
    except OSError as exc:
        raise _ToolUnavailable("output_unavailable") from exc


def _publish_bytes(path: Path, data: bytes) -> None:
    try:
        if os.path.lexists(str(path)):
            raise _ToolUnavailable("output_exists")
    except _ToolUnavailable:
        raise
    except OSError as exc:
        raise _ToolUnavailable("output_unavailable") from exc

    temporary = _temporary_file(path, data)
    try:
        try:
            os.link(str(temporary), str(path))
        except FileExistsError as exc:
            raise _ToolUnavailable("output_exists") from exc
        if path.read_bytes() != data:
            raise OSError("destination output verification failed")
    except _ToolUnavailable:
        raise
    except OSError as exc:
        try:
            if path.exists() and path.read_bytes() == data:
                path.unlink()
        except OSError:
            pass
        raise _ToolUnavailable("output_unavailable") from exc
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _publish_text(path: Path, text: str) -> None:
    _publish_bytes(path, text.encode("utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(description=__doc__, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    validate = sub.add_parser("validate", help="validate one SVG lifecycle form", add_help=False)
    validate.add_argument("-h", "--help", action="store_true")
    validate.add_argument("--kind", required=True, choices=("generator", "candidate", "final"))
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--source-map", type=Path)
    validate.add_argument("--title-min-size", default="40")

    extract = sub.add_parser("extract", help="extract one XML fence", add_help=False)
    extract.add_argument("-h", "--help", action="store_true")
    extract.add_argument("--input", required=True, type=Path)
    extract.add_argument("--output", required=True, type=Path)

    normalize = sub.add_parser("normalize-text", help="normalize text roles and safe vertical positions", add_help=False)
    normalize.add_argument("-h", "--help", action="store_true")
    normalize.add_argument("--input", required=True, type=Path)
    normalize.add_argument("--output", required=True, type=Path)
    normalize.add_argument("--title-min-size", default="40")

    finalize = sub.add_parser("finalize", help="normalize, source-join, and validate one raw candidate", add_help=False)
    finalize.add_argument("-h", "--help", action="store_true")
    finalize.add_argument("--input", required=True, type=Path)
    finalize.add_argument("--output", required=True, type=Path)
    finalize.add_argument("--source-map", required=True, type=Path)
    finalize.add_argument("--title-min-size", default="40")
    return parser


def _validate(args, warnings: list[dict[str, Any]]) -> None:
    floor = _title_floor(args.title_min_size)
    if args.kind == "generator":
        if args.source_map is not None:
            raise _ToolUnavailable("tool_invocation_invalid")
        validate_generator_svg(_read_text(args.input), title_min_size=floor, warnings=warnings)
        return
    if args.kind == "candidate":
        if args.source_map is None:
            raise _ToolUnavailable("tool_invocation_invalid")
        validate_candidate_svg(
            _read_text(args.input),
            _read_source_map(args.source_map),
            title_min_size=floor,
            warnings=warnings,
        )
        return
    if args.source_map is not None:
        raise _ToolUnavailable("tool_invocation_invalid")
    validate_final_svg(_read_text(args.input), title_min_size=floor, warnings=warnings)


def _run(args, warnings: list[dict[str, Any]]) -> None:
    if _RUNTIME_ERROR is not None:
        raise _ToolUnavailable("tool_runtime_unavailable")
    if args.command == "extract":
        _publish_text(args.output, extract_svg(_read_text(args.input)) + "\n")
        return
    if args.command == "normalize-text":
        floor = _title_floor(args.title_min_size)
        _publish_text(
            args.output,
            normalize_text_roles(_read_text(args.input), title_min_size=floor, warnings=warnings),
        )
        return
    if args.command == "validate":
        _validate(args, warnings)
        return
    floor = _title_floor(args.title_min_size)
    output = finalize_candidate_svg(
        _read_text(args.input),
        _read_source_map(args.source_map),
        title_min_size=floor,
        warnings=warnings,
    )
    _publish_bytes(args.output, output)


def _operation_from_argv(argv) -> str:
    values = list(sys.argv[1:] if argv is None else argv)
    for value in values:
        if value in ("validate", "extract", "normalize-text", "finalize"):
            return value
    return "help" if any(value in ("-h", "--help") for value in values) else "unknown"


def main(argv=None) -> int:
    operation = _operation_from_argv(argv)
    try:
        args = _parser().parse_args(argv)
        operation = "help" if args.help else args.command
        if args.help:
            return _emit("PASS", operation)
        if args.command is None:
            raise _ToolUnavailable("tool_invocation_invalid")
        warnings: list[dict[str, Any]] = []
        _run(args, warnings)
        return _emit("PASS", operation, warnings=warnings)
    except _ToolInvalid as exc:
        return _emit("INVALID", operation, reason=exc.reason)
    except _ToolUnavailable as exc:
        return _emit("UNAVAILABLE", operation, reason=exc.reason)
    except ValueError as exc:
        reason = str(exc)
        if reason in _KNOWN_INVALID_REASONS:
            return _emit("INVALID", operation, reason=reason)
        return _emit("UNAVAILABLE", operation, reason="tool_internal_error")
    except Exception:
        return _emit("UNAVAILABLE", operation, reason="tool_internal_error")


if __name__ == "__main__":
    raise SystemExit(main())
