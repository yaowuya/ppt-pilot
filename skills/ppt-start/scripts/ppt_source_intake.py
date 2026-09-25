#!/usr/bin/env python3
"""Safely inventory an external PPTX source deck without workflow side effects."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


_RUNTIME_ERROR = None
try:
    from _source_intake import extract_pptx
except Exception as exc:  # pragma: no cover - exercised by the CLI boundary test.
    _RUNTIME_ERROR = exc


class _ToolUnavailable(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ToolUnavailable("tool_invocation_invalid")


def _emit(status, *, reason=None):
    payload = {"operation": "source-intake", "status": status, "warnings": []}
    if reason is not None:
        payload["reason"] = reason
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return {"PASS": 0, "INVALID": 2, "UNAVAILABLE": 3}[status]


def _source_is_available(path):
    try:
        return path.is_file()
    except OSError as exc:
        raise _ToolUnavailable("input_unreadable") from exc


def _publish_new(path, data):
    if not path.parent.is_dir():
        raise _ToolUnavailable("output_parent_missing")
    try:
        if path.exists():
            raise _ToolUnavailable("output_exists")
        handle, temporary = tempfile.mkstemp(
            prefix="." + path.name + ".",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary_path.read_bytes() != data:
                raise OSError("temporary output verification failed")
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError as exc:
                raise _ToolUnavailable("output_exists") from exc
            if path.read_bytes() != data:
                raise OSError("published output verification failed")
        finally:
            try:
                temporary_path.unlink()
            except OSError:
                pass
    except _ToolUnavailable:
        raise
    except OSError as exc:
        raise _ToolUnavailable("output_unavailable") from exc


def _parse_args(argv):
    parser = _Parser(description=__doc__, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--source")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if not args.help and (not args.source or not args.output):
        raise _ToolUnavailable("tool_invocation_invalid")
    return args


def main(argv=None):
    try:
        args = _parse_args(argv)
        if args.help:
            return _emit("PASS")
        if _RUNTIME_ERROR is not None:
            raise _ToolUnavailable("tool_runtime_unavailable")
        source = Path(args.source)
        output = Path(args.output)
        if not _source_is_available(source):
            raise _ToolUnavailable("input_unreadable")
        inventory = extract_pptx(source)
        payload = (json.dumps(inventory, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        _publish_new(output, payload)
        return _emit("PASS")
    except _ToolUnavailable as error:
        return _emit("UNAVAILABLE", reason=error.reason)
    except ValueError as error:
        if str(error).startswith("cannot read PPTX source:"):
            return _emit("UNAVAILABLE", reason="input_unreadable")
        return _emit("INVALID", reason="source_invalid")
    except Exception:
        return _emit("UNAVAILABLE", reason="tool_internal_error")


if __name__ == "__main__":
    raise SystemExit(main())
