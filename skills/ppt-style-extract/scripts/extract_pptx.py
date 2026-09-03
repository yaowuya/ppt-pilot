#!/usr/bin/env python3
"""CLI entrypoint: deterministic style extraction from a .pptx."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _style_extract.errors import ExtractError


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract style evidence from a template PPTX.")
    parser.add_argument("--in", dest="path", required=True, help="Path to a .pptx file.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    try:
        from _style_extract.extract_pptx import extract_pptx

        result = extract_pptx(Path(args.path))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"extractor={result['extractor']}")
            print(f"brand_primary={result['colors']['brand_primary']}")
            print(f"canvas={result['colors']['canvas']}")
            print(f"font_stack={result['typography']['font_stack']}")
            print(f"primary_radius={result['shape']['primary_radius']}")
        return 0
    except (ExtractError, Exception) as exc:  # noqa: BLE001 - surface any failure as JSON
        print(json.dumps({"result": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
