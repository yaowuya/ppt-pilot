"""PPT Style Extract - deterministic style-pack authoring package."""

from .errors import (
    ExtractError,
    PptStyleExtractError,
    Unavailable,
    VerificationError,
)
from .registry import register_style, update_registry_idempotent

__all__ = [
    "ExtractError",
    "PptStyleExtractError",
    "Unavailable",
    "VerificationError",
    "register_style",
    "update_registry_idempotent",
]
