"""Error types for PPT Style Extract."""


class PptStyleExtractError(Exception):
    """Base error for this package."""


class ExtractError(PptStyleExtractError):
    """An extractor could not read usable evidence from the input."""


class Unavailable(PptStyleExtractError):
    """A required capability is missing and cannot be honestly satisfied."""


class VerificationError(PptStyleExtractError):
    """A composed style pack violated a hard constraint; write nothing."""
