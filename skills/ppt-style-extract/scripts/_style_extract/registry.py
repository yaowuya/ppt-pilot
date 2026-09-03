"""Idempotent style registry update."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import PptStyleExtractError


def read_registry(path: Path) -> dict:
    if not path.is_file():
        raise PptStyleExtractError(f"registry not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("styles"), list):
        raise PptStyleExtractError("registry_schema_invalid")
    return payload


def register_style(payload: dict, style: dict) -> dict:
    """Return a new payload with `style` idempotently upserted.

    Guards uniqueness: display_name must not collide with a different id.
    """
    styles = payload["styles"]
    idx = next((i for i, s in enumerate(styles) if s.get("id") == style["id"]), None)
    for existing in styles:
        if existing.get("display_name") == style["display_name"] and existing.get("id") != style["id"]:
            raise PptStyleExtractError("registry_display_name_collision")

    updated = [dict(s) for s in styles]
    if idx is None:
        updated.append(dict(style))
    else:
        updated[idx] = dict(style)
    return {"schema_version": 1, "styles": updated}


def update_registry_idempotent(path: Path, manifest: dict) -> int:
    """Register `manifest` into `path` and write it back atomically.

    Returns the number of entries after the write. Manifest-last semantics:
    this is the final durable action; the caller should have already written
    the pack files and verified them.
    """
    payload = read_registry(path)
    entry = {
        "id": manifest["id"],
        "display_name": manifest["display_name"],
        "kind": "style_pack",
        "entrypoint": f"{manifest['id']}/manifest.json",
    }
    updated = register_style(payload, entry)

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return len(updated["styles"])
