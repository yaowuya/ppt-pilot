"""Strict loading for the single authoritative verification configuration."""

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple, Union

from .model import VerificationConfig


_CONFIG_KEYS = frozenset(
    {
        "schema_version",
        "render_width",
        "render_height",
        "full_page_grayscale_mad_max",
        "geometry_only_grayscale_mad_max",
        "geometry_tile_size",
        "geometry_tile_mad_max",
        "bounds_tolerance_px",
    }
)


def _reject_duplicate_keys(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}  # type: Dict[str, Any]
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration key: {}".format(key))
        result[key] = value
    return result


def load_verification_config(path: Union[str, Path]) -> VerificationConfig:
    """Load schema-v1 config without accepting unknown or coerced values."""

    config_path = Path(path)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("unable to read verification configuration: {}".format(exc)) from exc

    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid verification configuration JSON: {}".format(exc)) from exc

    if not isinstance(payload, dict):
        raise ValueError("verification configuration must be a JSON object")

    actual_keys = frozenset(payload)
    if actual_keys != _CONFIG_KEYS:
        missing = sorted(_CONFIG_KEYS - actual_keys)
        extra = sorted(actual_keys - _CONFIG_KEYS)
        raise ValueError(
            "configuration keys must match schema-v1 exactly; missing={}, extra={}".format(
                missing, extra
            )
        )

    return VerificationConfig(**payload)
