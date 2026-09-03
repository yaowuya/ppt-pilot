#!/usr/bin/env python3
"""CLI orchestrator: turn a template PPT / image / prompt into a style pack.

Phases (fixed order):
  locate -> classify -> extract -> compose -> verify -> write -> register -> report
Verification happens before any durable pack write; a verify failure returns
BLOCKED and writes nothing.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _style_extract.errors import ExtractError, PptStyleExtractError, Unavailable, VerificationError
from _style_extract import analyze_prompt as _analyze
from _style_extract import extract_image as _image
from _style_extract import extract_pptx as _pptx
from _style_extract.builder import compose_style_pack, write_style_pack
from _style_extract.verify import verify_style_pack


def _classify(argument: str) -> str:
    path = Path(argument)
    if path.exists():
        if path.is_file() and path.suffix.lower() == ".pptx":
            return "pptx"
        if path.is_file() and path.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
            return "image"
        if path.is_dir():
            return "image"
        return "prompt"
    return "prompt"


def _resolve_input(kind: str, argument: str):
    if kind == "pptx":
        return _pptx.extract_pptx(Path(argument))
    if kind == "image":
        return _image.extract_image(Path(argument))
    return _analyze.analyze_prompt(argument)


def _safe_path(path: Path) -> Path:
    if not path.is_absolute():
        raise PptStyleExtractError("path_must_be_absolute")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Author a PPT Pilot style pack from input.")
    parser.add_argument("--input", required=True, help="A .pptx path, image path/folder, or style prompt.")
    parser.add_argument("--style-id", required=True, help="Unique lowercase kebab-style id, e.g. my-brand.")
    parser.add_argument("--display-name", default=None, help="Human display name for the pack.")
    parser.add_argument("--version", default="1.0.0", help="semver pack version.")
    parser.add_argument("--out", required=True, help="Absolute user-style-packs root directory.")
    parser.add_argument("--registry", required=True, help="Absolute path to the registry.json to update.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON on stdout.")
    args = parser.parse_args()

    try:
        out_root = _safe_path(Path(args.out))
        registry = _safe_path(Path(args.registry))
        kind = _classify(args.input)
        extract = _resolve_input(kind, args.input)
        semantic = extract.get("semantic") if kind == "prompt" else None

        display_name = args.display_name or args.style_id
        pack = compose_style_pack(
            args.style_id, display_name, args.version, extract, semantic
        )
        result = write_style_pack(pack, out_root, registry)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"PASS {result['style_id']} -> {result['output_dir']}")
        return 0
    except VerificationError as exc:
        print(json.dumps({"result": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1
    except Unavailable as exc:
        print(json.dumps({"result": "UNAVAILABLE", "reason": str(exc)}, ensure_ascii=False))
        return 2
    except (ExtractError, PptStyleExtractError, Exception) as exc:  # noqa: BLE001
        print(json.dumps({"result": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
