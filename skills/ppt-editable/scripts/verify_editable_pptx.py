#!/usr/bin/env python
"""Gating CLI for ppt-editable structural/content verification."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Optional, Sequence

from _ppt_editable.atomic_io import atomic_write_json
from _ppt_editable.config import load_verification_config
from _ppt_editable.contract import (
    parse_storyboard,
    resolve_slide_sources,
    validate_completed_run,
)
from _ppt_editable.errors import EditableError
from _ppt_editable.svg_parser import DeckPreflightError, preflight_deck
from _ppt_editable.structural_verify import VerificationReport, verify_candidate


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="verify_editable_pptx.py")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input-snapshot-id", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--report", required=True)
    return parser


def _report_path_from_argv(argv: Optional[Sequence[str]]) -> Optional[Path]:
    values = list(sys.argv[1:] if argv is None else argv)
    for index, value in enumerate(values):
        if value.startswith("--report="):
            candidate = value.split("=", 1)[1]
            return Path(candidate) if candidate else None
        if value == "--report" and index + 1 < len(values):
            return Path(values[index + 1])
    return None


def _write_report(path: Path, value) -> bool:
    try:
        atomic_write_json(path, value)
        return True
    except Exception:
        return False


def _failure_payload(code: str, message: str):
    return {
        "code": code,
        "slide_id": None,
        "svg_tree_path": None,
        "element_type": None,
        "message": message,
        "remediation": "correct the invocation or rebuild the verification input",
    }


def _report_payload(status: str, *, failures=(), slides=()):
    return {
        "schema_version": 1,
        "kind": "ppt_editable_verification",
        "status": status,
        "slide_count": 0,
        "top_level_shape_count": 0,
        "recursive_leaf_count": 0,
        "recursive_group_count": 0,
        "slides": list(slides),
        "failures": list(failures),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        report_path = _report_path_from_argv(argv)
        if report_path is not None:
            invalid = _report_payload(
                "invalid",
                failures=[_failure_payload("source_unreadable", str(exc))],
            )
            if not _write_report(report_path, invalid):
                return 4
        return 3
    except ValueError as exc:
        report_path = _report_path_from_argv(argv)
        if report_path is not None:
            invalid = _report_payload(
                "invalid",
                failures=[_failure_payload("source_unreadable", str(exc))],
            )
            if not _write_report(report_path, invalid):
                return 4
        return 3
    report_path = Path(arguments.report)
    running = _report_payload("running")
    if not _write_report(report_path, running):
        return 4
    if _SHA256_RE.fullmatch(arguments.input_snapshot_id) is None:
        invalid = _report_payload(
            "invalid",
            failures=[
                _failure_payload(
                    "source_unreadable",
                    "input snapshot ID is invalid",
                )
            ],
        )
        return 3 if _write_report(report_path, invalid) else 4
    try:
        config = load_verification_config(Path(arguments.config))
        context = validate_completed_run(Path(arguments.run_dir))
        storyboard = parse_storyboard(context.storyboard_path)
        sources = resolve_slide_sources(context, storyboard)
        plan = preflight_deck(
            context,
            sources,
            storyboard,
            arguments.input_snapshot_id,
        )
    except (EditableError, DeckPreflightError, ValueError, OSError) as exc:
        invalid = _report_payload(
            "invalid",
            failures=[_failure_payload("source_unreadable", str(exc))],
        )
        return 3 if _write_report(report_path, invalid) else 4
    try:
        report = verify_candidate(Path(arguments.candidate), plan, config)
    except Exception as exc:
        error = _report_payload(
            "error",
            failures=[_failure_payload("pptx_reopen_failed", str(exc))],
        )
        _write_report(report_path, error)
        return 4
    if not _write_report(report_path, report.to_dict()):
        return 4
    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
