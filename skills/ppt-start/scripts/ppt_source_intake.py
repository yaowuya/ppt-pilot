#!/usr/bin/env python3
"""CLI for safely inventorying an external PPTX source deck."""

import argparse
import json
import sys
from pathlib import Path

from _source_intake import extract_pptx


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    created = False
    try:
        inventory = extract_pptx(args.source)
        if not output.parent.is_dir():
            raise ValueError("output parent directory must already exist")
        payload = (json.dumps(inventory, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with output.open("xb") as stream:
            created = True
            stream.write(payload)
        return 0
    except Exception as error:
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        print("source intake failed: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
