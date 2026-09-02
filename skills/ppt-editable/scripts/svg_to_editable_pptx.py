#!/usr/bin/env python
"""Public CLI for ppt-editable generation."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from _ppt_editable.atomic_io import atomic_write_json
from _ppt_editable.office_protocol import powerpoint_available
from _ppt_editable.orchestrator import (
    GenerationCapability,
    editable_result_dict,
    generate_editable,
)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _parser():
    parser = _ArgumentParser(prog="svg_to_editable_pptx.py")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--result-path")
    parser.add_argument("--skip-office", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    except ValueError:
        return 3
    try:
        capability = GenerationCapability(
            office_available=(
                not arguments.skip_office and powerpoint_available()
            ),
            pillow_available=importlib.util.find_spec("PIL") is not None,
        )
        result = generate_editable(Path(arguments.run_dir), capability)
        payload = editable_result_dict(result)
        if arguments.result_path:
            atomic_write_json(Path(arguments.result_path), payload)
        if arguments.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if result.status in ("PASS", "GENERATED_UNVERIFIED") else 2
    except Exception:
        return 4


if __name__ == "__main__":
    sys.exit(main())
