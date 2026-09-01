"""Canonical identity for one completed editable-deck input set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from .contract import (
    RunContext,
    SlideSource,
    StoryboardSlide,
    validate_safe_regular_file,
)
from .errors import EditableError


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise EditableError("source_unreadable", "cannot hash source file") from exc
    return "sha256:" + digest.hexdigest()


def canonical_snapshot_payload(
    context: RunContext,
    sources: Sequence[SlideSource],
    storyboard: Sequence[StoryboardSlide],
    converter_version: str,
    subset_contract_version: str,
    verification_config_bytes: bytes,
) -> bytes:
    if not isinstance(converter_version, str) or not converter_version:
        raise ValueError("converter_version must be nonempty")
    if not isinstance(subset_contract_version, str) or not subset_contract_version:
        raise ValueError("subset_contract_version must be nonempty")
    if not isinstance(verification_config_bytes, bytes):
        raise TypeError("verification_config_bytes must be bytes")
    notes_by_id = {slide.slide_id: slide for slide in storyboard}
    if len(notes_by_id) != len(storyboard):
        raise EditableError("slide_set_invalid", "duplicate storyboard identity")
    if tuple(source.slide_id for source in sources) != tuple(
        slide.slide_id for slide in storyboard
    ):
        raise EditableError("slide_set_invalid", "source order differs from storyboard")

    slide_payload = []
    for source in sources:
        if source.owner == "production":
            allowed_root = context.slides_dir
        elif source.owner == "approved_anchor":
            allowed_root = context.samples_dir
        else:
            raise EditableError("slide_set_invalid", "unknown slide source owner")
        relative_path = source.relative_path
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or "\\" in relative_path
            or Path(relative_path).is_absolute()
            or any(part in ("", ".", "..") for part in relative_path.split("/"))
        ):
            raise EditableError("source_path_unsafe", "slide source path is not canonical")
        expected_path = (context.run_dir / relative_path).absolute()
        validated_path = validate_safe_regular_file(expected_path, (allowed_root,))
        try:
            canonical_relative = validated_path.relative_to(
                context.run_dir.resolve(strict=True)
            ).as_posix()
            if canonical_relative != relative_path:
                raise EditableError("source_path_unsafe", "slide source path is not canonical")
            if validated_path != Path(source.path).resolve(strict=True):
                raise EditableError("source_path_unsafe", "slide source identity drifted")
        except OSError as exc:
            raise EditableError("source_path_unsafe", "slide source identity is unreadable") from exc
        observed_sha256 = sha256_file(validated_path)
        if source.svg_sha256 != observed_sha256:
            raise EditableError("source_path_unsafe", "slide source bytes changed after resolution")
        note = notes_by_id[source.slide_id]
        slide_payload.append(
            {
                "slide_id": source.slide_id,
                "path": relative_path,
                "owner": source.owner,
                "svg_sha256": observed_sha256,
                "notes": {
                    "assertion_title": note.assertion_title,
                    "audience_takeaway": note.audience_takeaway,
                    "next_link": note.next_link,
                },
            }
        )
    try:
        storyboard_path = context.storyboard_path.relative_to(context.run_dir).as_posix()
    except ValueError as exc:
        raise EditableError("source_path_unsafe", "storyboard escapes run directory") from exc
    payload = {
        "schema_version": 1,
        "kind": "ppt_editable_input_snapshot",
        "deck_id": context.deck_id,
        "run_schema_version": context.run_data.get("schema_version"),
        "run_stage": context.run_data.get("stage"),
        "storyboard_path": storyboard_path,
        "converter_version": converter_version,
        "subset_contract_version": subset_contract_version,
        "verification_config_sha256": sha256_bytes(verification_config_bytes),
        "slides": slide_payload,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_snapshot_id(payload: bytes) -> str:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    return sha256_bytes(payload)
