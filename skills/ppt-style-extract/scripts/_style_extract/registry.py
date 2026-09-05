"""Idempotent style registry update."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from uuid import uuid4

from .errors import PptStyleExtractError


_registry_locks_guard = threading.Lock()
_registry_thread_locks: dict[str, threading.Lock] = {}


@contextmanager
def _registry_lock(path: Path):
    """Serialize registry read/modify/replace across threads and processes."""
    canonical_path = str(path.resolve())
    with _registry_locks_guard:
        thread_lock = _registry_thread_locks.setdefault(
            canonical_path, threading.Lock()
        )
    with thread_lock:
        lock_path = path.with_name(path.name + ".lock")
        handle = lock_path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                handle.close()
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()


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


def prepare_registry_update(path: Path, manifest: dict) -> dict:
    """Validate and materialize the next registry payload without writing it."""
    payload = read_registry(path)
    entry = {
        "id": manifest["id"],
        "display_name": manifest["display_name"],
        "kind": "style_pack",
        "entrypoint": f"{manifest['id']}/manifest.json",
    }
    return register_style(payload, entry)


def commit_registry_payload(path: Path, payload: dict) -> int:
    """Atomically replace the registry with a previously validated payload."""
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return len(payload["styles"])


def update_registry_idempotent(path: Path, manifest: dict) -> int:
    """Register `manifest` into `path` and write it back atomically.

    Returns the number of entries after the write. Manifest-last semantics:
    this is the final durable action; the caller should have already written
    the pack files and verified them.
    """
    with _registry_lock(path):
        # Reload while holding the lock so a stale preflight cannot overwrite a
        # registration committed by another writer.
        updated = prepare_registry_update(path, manifest)
        return commit_registry_payload(path, updated)
