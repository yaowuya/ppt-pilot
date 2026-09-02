"""Private implementation foundation for the ppt-editable Skill."""

from .config import load_verification_config
from .errors import EditableError, FAILURE_REASONS
from .model import (
    Bounds,
    DeckPlan,
    EditableResult,
    Failure,
    ResolvedStyle,
    SlidePlan,
    SpeakerNotes,
    SvgNode,
    TextLine,
    TextRun,
    VerificationConfig,
)

from .office_protocol import OfficeResult, invoke_office_verification
from .orchestrator import GenerationCapability, generate_editable

__all__ = [
    "Bounds",
    "DeckPlan",
    "EditableError",
    "EditableResult",
    "FAILURE_REASONS",
    "Failure",
    "GenerationCapability",
    "OfficeResult",
    "ResolvedStyle",
    "SlidePlan",
    "SpeakerNotes",
    "SvgNode",
    "TextLine",
    "TextRun",
    "VerificationConfig",
    "generate_editable",
    "invoke_office_verification",
    "load_verification_config",
]
