#!/usr/bin/env python3
"""CLI entrypoint: deterministic style extraction from reference image(s)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _style_extract.errors import ExtractError, Unavailable


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract style evidence from reference images.")
    parser.add_argument("--in", dest="path", required=True, help="Image path or a folder of images.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    try:
        from _style_extract.extract_image import extract_image

        result = extract_image(Path(args.path))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"extractor={result['extractor']}")
            print(f"brand_primary={result['colors']['brand_primary']}")
            print(f"accent_palette={result['colors']['accent_palette']}")
        return 0
    except Unavailable as exc:
        print(json.dumps({"result": "UNAVAILABLE", "reason": str(exc)}, ensure_ascii=False))
        return 2
    except (ExtractError, Exception) as exc:  # noqa: BLE001
        print(json.dumps({"result": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
