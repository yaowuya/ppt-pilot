"""Stable failure reasons for the ppt-editable schema-v1 contract."""

from typing import Optional


FAILURE_REASONS = frozenset(
    {
        "run_not_found",
        "run_ambiguous",
        "run_not_complete",
        "deck_id_invalid",
        "quality_report_missing",
        "storyboard_missing",
        "storyboard_ambiguous",
        "slide_set_invalid",
        "source_path_unsafe",
        "source_unreadable",
        "python_version_unsupported",
        "core_dependency_missing",
        "svg_xml_invalid",
        "svg_canvas_invalid",
        "svg_element_unsupported",
        "svg_attribute_unsupported",
        "svg_external_reference",
        "svg_path_invalid",
        "svg_arc_rotation_unsupported",
        "svg_group_empty",
        "svg_coordinate_invalid",
        "svg_text_invalid",
        "candidate_write_failed",
        "candidate_hash_mismatch",
        "pptx_zip_invalid",
        "pptx_reopen_failed",
        "structure_mismatch",
        "content_mismatch",
        "group_mismatch",
        "notes_mismatch",
        "bounds_violation",
        "image_fallback_detected",
        "powerpoint_normalize_failed",
        "powerpoint_reopen_failed",
        "powerpoint_render_failed",
        "visual_mismatch",
        "promotion_conflict",
    }
)


def validate_failure_reason(code: str) -> str:
    """Return a schema-v1 reason code, rejecting extensions to the closed set."""

    if not isinstance(code, str) or code not in FAILURE_REASONS:
        raise ValueError("unknown failure reason: {!r}".format(code))
    return code


class EditableError(Exception):
    """Expected conversion failure carrying one closed schema-v1 reason."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        slide_id: Optional[str] = None,
        svg_tree_path: Optional[str] = None,
        element_type: Optional[str] = None,
        remediation: str = "",
    ) -> None:
        self.code = validate_failure_reason(code)
        self.slide_id = slide_id
        self.svg_tree_path = svg_tree_path
        self.element_type = element_type
        self.message = message
        self.remediation = remediation
        super().__init__(message)
