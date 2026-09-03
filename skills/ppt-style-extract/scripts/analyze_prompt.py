#!/usr/bin/env python3
"""CLI entrypoint: map a natural-language style prompt to semantic direction."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _style_extract.errors import ExtractError


def main() -> int:
    parser = argparse.ArgumentParser(description="Map a style prompt to semantic direction.")
    parser.add_argument("--in", dest="text", required=True, help="A natural-language style description.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    try:
        from _style_extract.analyze_prompt import analyze_prompt

        result = analyze_prompt(args.text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"extractor={result['extractor']}")
            print(f"direction={result['semantic']['direction']}")
            print(f"prohibited={result['semantic']['prohibited_motifs']}")
        return 0
    except (ExtractError, Exception) as exc:  # noqa: BLE001
        print(json.dumps({"result": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
