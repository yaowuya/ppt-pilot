import copy
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root

STYLE_PROMPTS = {
    "minimal-business": "minimal-business.redesign.md",
    "tech-dark": "tech-dark.redesign.md",
    "bold-editorial": "bold-editorial.redesign.md",
    "canway-midyear-review": "canway-midyear-review/REDESIGN.md",
}

HARD_CONSTRAINT_IDS = (
    "CONTENT_LOCK_V1",
    "SOURCE_BOUNDARY_V1",
    "NO_OLD_SVG_GEOMETRY_V1",
    "SINGLE_XML_FENCE_V1",
    "OFFICE_SAFE_SVG_V1",
    "EXPLICIT_TSPAN_TEXT_V1",
    "NO_REMOTE_OR_ACTIVE_CONTENT_V1",
    "SOURCE_METADATA_V1",
    "CREATOR_OWNS_WRITE_AND_QA_V1",
    "DYNAMIC_INPUT_AUTHORITY_V1",
)

PROMPT_PLACEHOLDERS = (
    "[SLIDE_ID]",
    "[SOURCE_AND_VERSION]",
    "[LOCKED_CONTENT]",
    "[INFORMATION_HIERARCHY]",
    "[COMPOSITION]",
    "[VISUAL_SYSTEM]",
    "[REVISION_MODE]",
    "[OUTPUT_AND_QA]",
    "[ACTIVE_THEME]",
    "[ACTIVE_VISUAL_REVISIONS]",
    "[USER_WORDING]",
)

NO_FOLLOW_TARGETS = {"link", "symlink", "junction", "reparse"}

REQUIRED_RESOLUTION_CASE_IDS = (
    "precedence-unselected-pack-root-before-selected-prompt",
    "precedence-selected-tokens-before-prompt",
    "fallback-missing-minimal-business-seed",
    "fallback-missing-tech-dark-seed",
    "fallback-missing-bold-editorial-seed",
    "fallback-missing-minimal-business-companion",
    "fallback-missing-tech-dark-companion",
    "fallback-missing-bold-editorial-companion",
)

RESOLUTION_BRANCHES = (
    "valid-style-pack",
    "valid-legacy-seed",
    "registry-backed-legacy-v1-companion",
    "registry-missing-complete-fallback",
    "registry-missing-unknown",
    "registry-missing-canway",
    "path-lexical-entrypoint",
    "path-lexical-prompt",
    "path-lexical-style-asset",
    "pack-root-shape",
    "pack-root-nested-overlap",
    "style-asset-ownership",
    "prompt-ownership",
    "legacy-to-pack-boundary",
    "target-kind",
    "identity-display-version",
    "failure-precedence",
    "fallback-incomplete",
)

FALLBACK_IDENTITIES = {
    "minimal-business": {"display_name": "极简商务", "kind": "legacy_seed", "version": "none", "entrypoint": "minimal-business.json", "prompt": "minimal-business.redesign.md"},
    "tech-dark": {"display_name": "深色科技", "kind": "legacy_seed", "version": "none", "entrypoint": "tech-dark.json", "prompt": "tech-dark.redesign.md"},
    "bold-editorial": {"display_name": "强调编辑", "kind": "legacy_seed", "version": "none", "entrypoint": "bold-editorial.json", "prompt": "bold-editorial.redesign.md"},
}


REQUIRED_IDENTITY_CASE_IDS = (
    "valid-complete-style-pack-identity",
    "missing-brief-id-rebuilds",
    "missing-theme-id-rebuilds",
    "missing-both-ids-conflicts-without-owner",
    "missing-both-ids-rebuilds-from-persisted-owner",
    "derives-non-id-fields-from-manifest",
    "missing-non-id-fields-rebuilds-with-backfill",
    "stale-display-name-is-ordinary-stale",
    "stale-version-is-ordinary-stale",
    "brief-theme-display-name-conflict",
    "brief-theme-manifest-version-conflict",
    "direct-style-id-conflict",
    "legacy-version-non-none-conflicts",
    "fallback-minimal-business-valid",
    "fallback-minimal-business-default-table-valid",
    "fallback-tech-dark-default-table-valid",
    "fallback-bold-editorial-default-table-valid",
    "missing-operation-owner-conflicts",
    "missing-trigger-owner-conflicts",
    "invalid-trigger-owner-conflicts",
    "multiple-trigger-owners-conflict",
    "user-recompose-valid-owner",
    "user-recompose-missing-history-conflicts",
    "user-recompose-non-applied-history-conflicts",
    "user-recompose-multiple-history-conflicts",
    "deck-scope-fanout-shares-trigger-not-transaction",
    "old-directory-only-is-inert",
    "new-stale-with-old-directory-rebuilds-from-new-owner",
    "dual-directory-prefers-new-owner",
    "old-directory-different-slide-is-inert",
    "conflicting-legacy-provenance-is-inert",
    "prompt-hash-changed-is-ordinary-stale",
    "stored-body-mismatch-conflicts",
    "initial-generation-valid-owner",
    "initial-generation-malformed-trigger-conflicts",
    "initial-generation-wrong-sentinel-conflicts",
    "deterministic-fallback-valid-owner",
    "deterministic-fallback-malformed-trigger-conflicts",
    "local-patch-valid-owner",
    "local-patch-malformed-trigger-conflicts",
    "local-patch-missing-current-svg-conflicts",
    "local-patch-compiles-full-prompt-conflicts",
    "missing-both-ids-owner-unregistered-identity-conflicts",
    "missing-both-ids-owner-stale-identity-conflicts",
    "missing-both-ids-owner-inconsistent-identity-conflicts",
)

OPERATION_MATRIX = {
    "initial_generation": {
        "mode": "recompose",
        "trigger": "initial:<slide-id>:<visual_brief_snapshot_id>",
        "reason": "initial generation from approved visual brief",
        "USER_WORDING": "none (initial generation)",
        "prior_candidate": "none",
    },
    "user_recompose": {
        "mode": "recompose",
        "trigger": "interaction:<applied-history-id>",
        "USER_WORDING_source": "applied history raw answer",
    },
    "deterministic_fallback": {
        "mode": "recompose",
        "trigger": "fallback:<slide-id>:<failed-transaction-64hex>:2",
        "reason": "deterministic single-column or two-column fallback after two failed patches",
        "USER_WORDING": "none (deterministic fallback after two failed patches)",
    },
    "local_patch": {
        "mode": "patch",
        "trigger": "patch:<slide-id>:<qa-defect-id>",
        "requires_current_svg": True,
        "compile_full_prompt": False,
    },
}


def _merged_case_section(case: dict, section: str):
    defaults = case.get("defaults", {})
    default_value = defaults.get(section, {})
    if section not in case:
        return copy.deepcopy(default_value)
    override = case.get(section)
    if override is None:
        return None
    if isinstance(default_value, dict) and isinstance(override, dict):
        merged = copy.deepcopy(default_value)
        merged.update(override)
        return merged
    return copy.deepcopy(override)


def _fallback_identity_payload(identity: dict, style_id: str) -> dict:
    if "selected_style_id" in identity:
        return copy.deepcopy(identity)
    return {
        "selected_style_id": style_id,
        "selected_style_display_name": identity.get("display_name"),
        "style_kind": identity.get("kind"),
        "style_manifest_version": identity.get("version"),
    }


def _canonical_identity_for_style(case: dict, style_id: str):
    registry = _merged_case_section(case, "registry") or {}
    fallback_table = case.get("fallback_identity_table", FALLBACK_IDENTITIES)
    if registry.get("state") == "missing":
        fallback = fallback_table.get(style_id)
        return _fallback_identity_payload(fallback, style_id) if fallback else None
    registered = next((style for style in registry.get("styles", []) if style.get("id") == style_id), None)
    if registered is None:
        return None
    manifest = _merged_case_section(case, "manifest") or {}
    return {
        "selected_style_id": style_id,
        "selected_style_display_name": manifest.get("display_name", registered.get("display_name")),
        "style_kind": manifest.get("kind", registered.get("kind")),
        "style_manifest_version": manifest.get("version"),
    }


def _projection_conflict():
    raise ValueError("prompt_snapshot_conflict")


def _visual_revision_sort_key(revision_id: str) -> int:
    match = re.fullmatch(r"visual-revision-([0-9]+)", revision_id or "")
    if match is None:
        _projection_conflict()
    return int(match.group(1))


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_json_bytes(value: object) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def normalize_lf(raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("prompt_snapshot_conflict") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def active_theme_json_bytes(raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("prompt_snapshot_conflict") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    theme_lines = text.split("\n")
    while theme_lines and theme_lines[0].strip() == "":
        theme_lines.pop(0)
    while theme_lines and theme_lines[-1].strip() == "":
        theme_lines.pop()
    if not theme_lines:
        _projection_conflict()
    return ("\n".join(theme_lines) + "\n").encode("utf-8")

BRIEF_SECTION_TO_TOKEN = {
    "来源与版本": "SOURCE_AND_VERSION",
    "锁定内容": "LOCKED_CONTENT",
    "信息层级": "INFORMATION_HIERARCHY",
    "构图": "COMPOSITION",
    "视觉系统": "VISUAL_SYSTEM",
    "修订模式": "REVISION_MODE",
    "输出与质量要求": "OUTPUT_AND_QA",
}

def _section_body_bytes(lines: list[str], *, drop_brief_snapshot: bool = False) -> bytes:
    body_lines = list(lines)
    if drop_brief_snapshot:
        body_lines = [line for line in body_lines if not line.startswith("- brief_snapshot_id:")]
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()
    if not body_lines:
        _projection_conflict()
    return ("\n".join(body_lines) + "\n").encode("utf-8")


def extract_brief_sections(text: str) -> dict[str, bytes]:
    normalized = normalize_lf(text.encode("utf-8"))
    lines = normalized.decode("utf-8").split("\n")[:-1]
    heading_positions = [(index, line.removeprefix("## ")) for index, line in enumerate(lines) if line.startswith("## ")]
    headings = [heading for _, heading in heading_positions]
    if headings != list(BRIEF_SECTION_TO_TOKEN):
        _projection_conflict()
    sections = {}
    for position, (start, heading) in enumerate(heading_positions):
        end = heading_positions[position + 1][0] if position + 1 < len(heading_positions) else len(lines)
        token = BRIEF_SECTION_TO_TOKEN[heading]
        sections[token] = _section_body_bytes(
            lines[start + 1:end],
            drop_brief_snapshot=(token == "SOURCE_AND_VERSION"),
        )
    return sections


def compile_prompt_body(template: bytes, replacements: dict[str, bytes]) -> bytes:
    lines = normalize_lf(template).decode("utf-8").splitlines(keepends=True)
    remaining = set(replacements)
    output = bytearray()
    for line in lines:
        token = line[:-1] if line.endswith("\n") else line
        if token in replacements:
            output.extend(replacements[token])
            remaining.discard(token)
        else:
            output.extend(line.encode("utf-8"))
    if remaining:
        raise ValueError("prompt_template_invalid")
    return bytes(output)


def sha256_id(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


PROVENANCE_FIELD_ORDER = (
    "artifact_schema_version",
    "transaction_id",
    "selected_style_id",
    "style_kind",
    "style_manifest_version",
    "resolved_redesign_prompt_path",
    "style_prompt_snapshot_id",
    "visual_brief_snapshot_id",
    "storyboard_snapshot_id",
    "theme_snapshot_id",
    "applied_visual_revision_ids",
    "generation_intent",
    "generation_trigger_id",
    "compiled_prompt_sha256",
    "prompt_snapshot_id",
    "status",
)


def _provenance_value_text(value):
    if isinstance(value, list):
        return canonical_json_bytes(value).decode("utf-8")
    return str(value)


def render_generation_prompt(provenance: dict, body: bytes, slide_id=None) -> bytes:
    if not isinstance(slide_id, str) or not slide_id:
        raise ValueError("prompt_snapshot_conflict")
    missing = [field for field in PROVENANCE_FIELD_ORDER if field not in provenance]
    if missing:
        raise ValueError("prompt_snapshot_conflict")
    body_bytes = body if body.endswith(b"\n") else body + b"\n"
    lines = ["# Generation Prompt " + slide_id, "", "## Provenance"]
    lines.extend(f"- {field}: {_provenance_value_text(provenance[field])}" for field in PROVENANCE_FIELD_ORDER)
    lines.extend(["", "## Compiled Prompt Body", ""])
    return ("\n".join(lines).encode("utf-8") + body_bytes)

def _revision_edge_sort_key(edge: str) -> tuple[int, str]:
    earlier_id, field = edge.split(":", 1)
    return (_visual_revision_sort_key(earlier_id), field)


def project_active_visual_revisions(payload: dict) -> tuple[list[str], bytes]:
    """Return sorted provenance IDs and canonical projected JSON ending in one LF."""
    brief = payload.get("brief") or {}
    applied_ids = brief.get("applied_visual_revision_ids")
    if not isinstance(applied_ids, list) or any(not isinstance(revision_id, str) for revision_id in applied_ids):
        _projection_conflict()
    if len(applied_ids) != len(set(applied_ids)):
        _projection_conflict()

    sorted_ids = sorted(applied_ids, key=_visual_revision_sort_key)
    if applied_ids != sorted_ids:
        _projection_conflict()
    id_index = {revision_id: index for index, revision_id in enumerate(sorted_ids)}
    history = (payload.get("run") or {}).get("interaction_history")
    if not isinstance(history, dict):
        _projection_conflict()

    mirrors = brief.get("applied_visual_revision_mirrors", {})
    if mirrors and (not isinstance(mirrors, dict) or set(mirrors) != set(sorted_ids)):
        _projection_conflict()

    records = {}
    mirror_keys = ("id", "kind", "stage", "affected_scope", "status", "artifact_owner", "supersedes", "normalized_changes")
    for revision_id in sorted_ids:
        record = history.get(revision_id)
        if not isinstance(record, dict) or record.get("id") != revision_id:
            _projection_conflict()
        if record.get("kind") != "visual_revision" or record.get("status") != "applied":
            _projection_conflict()
        if not isinstance(record.get("normalized_changes"), dict):
            _projection_conflict()
        if not isinstance(record.get("supersedes", []), list):
            _projection_conflict()
        mirror = mirrors.get(revision_id) if mirrors else None
        if mirror is not None:
            if not isinstance(mirror, dict):
                _projection_conflict()
            for key in mirror_keys:
                if mirror.get(key) != record.get(key):
                    _projection_conflict()
        records[revision_id] = record

    active_fields = {revision_id: set(records[revision_id]["normalized_changes"]) for revision_id in sorted_ids}
    seen_edges = set()
    sorted_edges_by_record = {}
    for revision_id in sorted_ids:
        edges = records[revision_id].get("supersedes", [])
        validated_edges = []
        for edge in edges:
            if not isinstance(edge, str) or edge.count(":") != 1:
                _projection_conflict()
            earlier_id, field = edge.split(":", 1)
            if edge in seen_edges or earlier_id == revision_id:
                _projection_conflict()
            seen_edges.add(edge)
            if earlier_id not in id_index or id_index[earlier_id] >= id_index[revision_id]:
                _projection_conflict()
            if field not in records[earlier_id]["normalized_changes"]:
                _projection_conflict()
            validated_edges.append(edge)
        sorted_edges_by_record[revision_id] = sorted(validated_edges, key=_revision_edge_sort_key)
        for edge in sorted_edges_by_record[revision_id]:
            earlier_id, field = edge.split(":", 1)
            active_fields[earlier_id].discard(field)

    projection = []
    for revision_id in sorted_ids:
        active_changes = {
            field: records[revision_id]["normalized_changes"][field]
            for field in sorted(active_fields[revision_id])
        }
        if not active_changes:
            continue
        projection.append(
            {
                "id": revision_id,
                "stage": records[revision_id].get("stage"),
                "affected_scope": records[revision_id].get("affected_scope"),
                "status": records[revision_id]["status"],
                "artifact_owner": records[revision_id].get("artifact_owner"),
                "supersedes": sorted_edges_by_record[revision_id],
                "normalized_changes": active_changes,
            }
        )
    return sorted_ids, _canonical_json_bytes(projection)


def derive_style_identity_backfill(case: dict):
    owner = _merged_case_section(case, "persisted_operation_owner")
    default_identity = _merged_case_section(case, "identity") or {}
    brief = copy.deepcopy(case.get("brief_identity", default_identity))
    theme = copy.deepcopy(case.get("theme_identity", default_identity))
    ids = [value for value in (brief.get("selected_style_id"), theme.get("selected_style_id")) if value]
    if len(set(ids)) > 1:
        return None
    if ids:
        return _canonical_identity_for_style(case, ids[0])
    if isinstance(owner, dict) and isinstance(owner.get("style_identity"), dict):
        owner_identity = copy.deepcopy(owner["style_identity"])
        style_id = owner_identity.get("selected_style_id")
        if not style_id:
            return None
        canonical = _canonical_identity_for_style(case, style_id)
        return canonical if owner_identity == canonical else None
    return None


def _operation_owner_is_valid(case: dict, owner) -> bool:
    if not isinstance(owner, dict):
        return False
    if owner.get("trigger_owner_state") != "valid" or owner.get("trigger_owner_count") != 1:
        return False
    intent = owner.get("generation_intent")
    trigger = owner.get("generation_trigger_id")
    if not isinstance(trigger, str):
        return False

    if intent == "initial_generation":
        return (
            re.fullmatch(r"initial:[^:]+:sha256:[^:]+", trigger) is not None
            and owner.get("reason") == "initial generation from approved visual brief"
            and owner.get("USER_WORDING") == "none (initial generation)"
            and owner.get("prior_candidate") == "none"
        )

    if intent == "user_recompose":
        match = re.fullmatch(r"interaction:([^:]+)", trigger)
        if match is None:
            return False
        history = _merged_case_section(case, "interaction_history") or []
        target_id = match.group(1)
        matches = [record for record in history if record.get("id") == target_id]
        return len(matches) == 1 and matches[0].get("status") == "applied" and isinstance(matches[0].get("answer"), str) and matches[0].get("answer") != ""

    if intent == "deterministic_fallback":
        return (
            re.fullmatch(r"fallback:[^:]+:[0-9a-f]{64}:2", trigger) is not None
            and owner.get("reason") == "deterministic single-column or two-column fallback after two failed patches"
            and owner.get("USER_WORDING") == "none (deterministic fallback after two failed patches)"
        )

    if intent == "local_patch":
        return (
            re.fullmatch(r"patch:[^:]+:[^:]+", trigger) is not None
            and owner.get("requires_current_svg") is True
            and owner.get("compile_full_prompt") is False
        )

    return False


def evaluate_style_identity_case(case: dict) -> str:
    """Return 'valid', 'rebuild', 'ordinary_stale', or 'prompt_snapshot_conflict'."""
    owner = _merged_case_section(case, "persisted_operation_owner")
    if not _operation_owner_is_valid(case, owner):
        return "prompt_snapshot_conflict"

    if owner.get("stored_body_hash_64hex") and owner.get("current_body_hash_64hex") and owner["stored_body_hash_64hex"] != owner["current_body_hash_64hex"]:
        return "prompt_snapshot_conflict"
    prompt_stale = owner.get("prompt_hash_64hex") and owner.get("current_prompt_hash_64hex") and owner["prompt_hash_64hex"] != owner["current_prompt_hash_64hex"]

    default_identity = _merged_case_section(case, "identity") or {}
    brief = copy.deepcopy(case.get("brief_identity", default_identity))
    theme = copy.deepcopy(case.get("theme_identity", default_identity))
    for field in (
        "selected_style_id",
        "selected_style_display_name",
        "style_kind",
        "style_manifest_version",
    ):
        brief_value = brief.get(field)
        theme_value = theme.get(field)
        if brief_value is not None and theme_value is not None and brief_value != theme_value:
            return "prompt_snapshot_conflict"
    brief_id = brief.get("selected_style_id")
    theme_id = theme.get("selected_style_id")
    if not brief_id and not theme_id:
        return "rebuild" if derive_style_identity_backfill(case) else "prompt_snapshot_conflict"
    if brief_id and theme_id and brief_id != theme_id:
        return "prompt_snapshot_conflict"
    style_id = brief_id or theme_id
    canonical = _canonical_identity_for_style(case, style_id)
    if canonical is None:
        return "rebuild"

    rebuild = not brief_id or not theme_id
    stale = bool(prompt_stale)
    for side in (brief, theme):
        for key, value in canonical.items():
            existing = side.get(key)
            if existing is None:
                rebuild = True
                continue
            if existing == value:
                continue
            if key in ("selected_style_id", "style_kind"):
                return "prompt_snapshot_conflict"
            if side.get("style_kind") == "legacy_seed" and key == "style_manifest_version" and existing != "none":
                return "prompt_snapshot_conflict"
            stale = True
    if rebuild:
        return "rebuild"
    return "ordinary_stale" if stale else "valid"


def _failure(reason):
    return {"ok": False, "reason": reason, "resolved_path": None}


def _success(path):
    return {"ok": True, "reason": None, "resolved_path": path}


def _path_parts(value):
    return value.replace(chr(92), "/").split("/")


def _is_path_unsafe(value):
    if not isinstance(value, str) or not value:
        return True
    if value.startswith(("/", chr(92))):
        return True
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return True
    if "://" in value:
        return True
    return any(part in ("", ".", "..") for part in _path_parts(value))


def _is_semver(value):
    return isinstance(value, str) and re.fullmatch(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", value) is not None


def _resource(resources, group, style_id, field=None):
    data = resources.get(group, {}).get(style_id, {})
    if field is not None:
        data = data.get(field, {})
    return data


def _target_failure(target, unsafe_reason, invalid_reason, missing_reason=None):
    if target in NO_FOLLOW_TARGETS:
        return unsafe_reason
    if target == "missing" and missing_reason is not None:
        return missing_reason
    if target != "file":
        return invalid_reason
    return None


def _duplicate_registry_style(styles):
    ids = [style.get("id") for style in styles]
    names = [style.get("display_name") for style in styles]
    return len(ids) != len(set(ids)) or len(names) != len(set(names))


def _pack_roots_or_failure(registry, styles):
    roots = []
    for style in styles:
        if style.get("kind") != "style_pack":
            continue
        entrypoint = style.get("entrypoint")
        expected = f"{style.get('id')}/manifest.json"
        if _is_path_unsafe(entrypoint) or entrypoint != expected:
            return None, "entrypoint_path_unsafe"
        root = entrypoint.rsplit("/", 1)[0]
        if "/" in root or root in roots:
            return None, "entrypoint_path_unsafe"
        roots.append(root)
    if registry.get("pack_root_shape", "valid") != "valid":
        return None, "entrypoint_path_unsafe"
    return roots, None


def _prompt_failure(prompt_path, prompt, reason_prefix, selected_style_id=None, pack_roots=()):
    if _is_path_unsafe(prompt_path) or prompt.get("target") in NO_FOLLOW_TARGETS:
        return f"{reason_prefix}_path_unsafe"
    if reason_prefix == "prompt" and any(prompt_path.startswith(root + "/") for root in pack_roots):
        return "prompt_path_unsafe"
    target_reason = _target_failure(prompt.get("target", "file"), f"{reason_prefix}_path_unsafe", f"{reason_prefix}_target_invalid", "prompt_file_missing" if reason_prefix == "prompt" else None)
    if target_reason:
        return target_reason
    if not prompt.get("readable", True):
        return f"{reason_prefix}_unreadable"
    if prompt.get("template", "valid") != "valid":
        return "prompt_template_invalid"
    if selected_style_id is not None and prompt.get("style_id") != selected_style_id:
        return "prompt_template_invalid"
    return None


def _resolve_registry_missing(case):
    fallback_files = case.get("fallback_files", {})
    for style_id in FALLBACK_IDENTITIES:
        bundle = fallback_files.get(style_id, {})
        seed = bundle.get("seed", {})
        prompt = bundle.get("prompt", {})
        if seed.get("target", "missing") != "file" or prompt.get("target", "missing") != "file":
            return _failure("registry_missing")
        if not seed.get("readable", True) or not prompt.get("readable", True):
            return _failure("registry_missing")
        if seed.get("json", "valid") != "valid" or seed.get("name") != style_id:
            return _failure("registry_missing")
        if prompt.get("template", "valid") != "valid" or prompt.get("style_id") != style_id:
            return _failure("registry_missing")
    selected = case.get("selected_style_id")
    if selected not in FALLBACK_IDENTITIES:
        return _failure("registry_missing")
    if case.get("snapshot", "valid") != "valid":
        return _failure("prompt_snapshot_conflict")
    return _success(f"assets/styles/{FALLBACK_IDENTITIES[selected]['prompt']}")


def resolve_style_prompt_case(case: dict) -> dict:
    """Return {'ok': bool, 'reason': str | None, 'resolved_path': str | None}."""
    registry = case.get("registry", {})
    registry_state = registry.get("state", "present")
    if registry_state in NO_FOLLOW_TARGETS:
        return _failure("registry_path_unsafe")
    if registry_state == "missing":
        return _resolve_registry_missing(case)
    registry_reason = {
        "path_unsafe": "registry_path_unsafe",
        "target_invalid": "registry_target_invalid",
        "unreadable": "registry_unreadable",
        "malformed": "registry_malformed",
        "schema_unsupported": "registry_schema_unsupported",
    }.get(registry_state)
    if registry_reason:
        return _failure(registry_reason)

    styles = registry.get("styles", [])
    if registry.get("schema_version", 1) != 1:
        return _failure("registry_schema_unsupported")
    if _duplicate_registry_style(styles):
        return _failure("registry_duplicate_style")

    pack_roots, pack_root_failure = _pack_roots_or_failure(registry, styles)
    if pack_root_failure:
        return _failure(pack_root_failure)

    selected_id = case.get("selected_style_id")
    selected = next((style for style in styles if style.get("id") == selected_id), None)
    if selected is None:
        return _failure("style_not_registered")
    kind = selected.get("kind")
    if kind not in ("legacy_seed", "style_pack"):
        return _failure("style_kind_invalid")

    entrypoint = selected.get("entrypoint")
    if entrypoint is None:
        return _failure("entrypoint_missing")
    if _is_path_unsafe(entrypoint):
        return _failure("entrypoint_path_unsafe")
    resources = case.get("resources", {})
    entry_resource = _resource(resources, "entrypoints", selected_id)
    entry_target_reason = _target_failure(entry_resource.get("target", "file"), "entrypoint_path_unsafe", "entrypoint_target_invalid")
    if entry_target_reason:
        return _failure(entry_target_reason)

    if kind == "legacy_seed":
        if any(entrypoint.startswith(root + "/") for root in pack_roots):
            return _failure("entrypoint_path_unsafe")
        if entry_resource.get("json", "valid") != "valid":
            return _failure("legacy_entrypoint_malformed")
        if entry_resource.get("name", selected_id) != selected_id:
            return _failure("legacy_identity_mismatch")
        prompt_path = selected.get("redesign_prompt")
        if prompt_path is None:
            if selected_id not in FALLBACK_IDENTITIES:
                return _failure("prompt_field_missing")
            prompt_path = entrypoint.rsplit(".", 1)[0] + ".redesign.md"
        prompt = _resource(resources, "prompts", selected_id)
        prompt_reason = _prompt_failure(prompt_path, prompt, "prompt", selected_id, pack_roots)
        if prompt_reason:
            return _failure(prompt_reason)
        if case.get("snapshot", "valid") != "valid":
            return _failure("prompt_snapshot_conflict")
        return _success(f"assets/styles/{prompt_path}")

    manifest = _resource(resources, "manifests", selected_id)
    manifest_target_reason = _target_failure(manifest.get("target", "file"), "entrypoint_path_unsafe", "entrypoint_target_invalid")
    if manifest_target_reason:
        return _failure(manifest_target_reason)
    if manifest.get("json", "valid") != "valid":
        return _failure("manifest_malformed")
    if manifest.get("schema_version", 1) != 1:
        return _failure("manifest_schema_unsupported")
    if (manifest.get("id", selected_id) != selected_id or manifest.get("kind", "style_pack") != "style_pack" or manifest.get("display_name", selected.get("display_name")) != selected.get("display_name")):
        return _failure("manifest_identity_mismatch")
    if not _is_semver(manifest.get("version")):
        return _failure("manifest_version_invalid")

    files = manifest.get("files", {})
    pack_root = entrypoint.rsplit("/", 1)[0]
    for field in ("tokens", "guidance"):
        asset_path = files.get(field)
        if asset_path is None:
            return _failure("style_asset_field_missing")
        asset = _resource(resources, "assets", selected_id, field)
        if _is_path_unsafe(asset_path) or asset.get("target") in NO_FOLLOW_TARGETS:
            return _failure("style_asset_path_unsafe")
        asset_target_reason = _target_failure(asset.get("target", "file"), "style_asset_path_unsafe", "style_asset_target_invalid")
        if asset_target_reason:
            return _failure(asset_target_reason)
        if not asset.get("readable", True):
            return _failure("style_asset_unreadable")

    prompt_path = files.get("redesign_prompt")
    if prompt_path is None:
        return _failure("prompt_field_missing")
    prompt = _resource(resources, "prompts", selected_id)
    prompt_reason = _prompt_failure(prompt_path, prompt, "prompt", selected_id)
    if prompt_reason:
        return _failure(prompt_reason)
    if case.get("snapshot", "valid") != "valid":
        return _failure("prompt_snapshot_conflict")
    return _success(f"assets/styles/{pack_root}/{prompt_path}")


class RedesignPromptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = skill_root() / "SKILL.md"
        self.reference = skill_root() / "references" / "redesign-prompt.md"
        self.visual = skill_root() / "references" / "visual-brief-and-generation.md"
        self.qa = skill_root() / "references" / "qa-and-revision.md"
        self.artifact = skill_root() / "references" / "artifact-contract.md"
        self.prompt_fixture = repo_root() / "tests" / "prompts" / "redesign-dedicated.md"
        self.style_root = skill_root() / "assets" / "styles"
        self.resolution_fixture = repo_root() / "tests" / "fixtures" / "style-prompt-resolution-cases.json"
        self.identity_migration_fixture = repo_root() / "tests" / "fixtures" / "style-identity-migration-cases.json"
        self.active_revision_projection_fixture = repo_root() / "tests" / "fixtures" / "style-prompt-active-revision-projection.json"
        self.generation_prompt_snapshot_fixture = repo_root() / "tests" / "fixtures" / "generation-prompt-snapshot.json"

    def _load_active_revision_projection_payload(self):
        self.assertTrue(
            self.active_revision_projection_fixture.is_file(),
            f"missing fixture: {self.active_revision_projection_fixture}",
        )
        payload = json.loads(read_text(self.active_revision_projection_fixture))
        self.assertEqual(payload["schema_version"], 1)
        return payload

    def test_active_revision_projection_matches_golden_bytes(self):
        payload = self._load_active_revision_projection_payload()
        provenance_ids, projection_bytes = project_active_visual_revisions(payload["valid_projection"])
        self.assertEqual(provenance_ids, payload["expected_provenance_ids"])
        self.assertEqual(projection_bytes, payload["expected_canonical_json"].encode("utf-8"))
        self.assertTrue(projection_bytes.endswith(b"\n"))
        self.assertEqual(json.loads(projection_bytes), payload["expected_projection"])

    def test_active_revision_projection_rejects_conflicts(self):
        payload = self._load_active_revision_projection_payload()
        for case in payload["conflict_cases"]:
            with self.subTest(case_id=case["id"]):
                with self.assertRaisesRegex(ValueError, "^prompt_snapshot_conflict$"):
                    project_active_visual_revisions(case["payload"])

    def test_raw_answers_never_enter_projection(self):
        payload = self._load_active_revision_projection_payload()
        _, projection_bytes = project_active_visual_revisions(payload["valid_projection"])
        projection_text = projection_bytes.decode("utf-8")
        self.assertNotIn(payload["raw_answer_sentinel"], projection_text)
        for forbidden in ("answer", "recommendation", "clarification", "unrelated"):
            self.assertNotIn(forbidden, projection_text)

    def _load_generation_prompt_snapshot_payload(self):
        self.assertTrue(
            self.generation_prompt_snapshot_fixture.is_file(),
            f"missing fixture: {self.generation_prompt_snapshot_fixture}",
        )
        payload = json.loads(read_text(self.generation_prompt_snapshot_fixture))
        self.assertEqual(payload["schema_version"], 1)
        return payload

    def _render_generation_prompt_fixture(self, payload: dict):
        section_bytes = extract_brief_sections(payload["brief_markdown"])
        template_bytes = normalize_lf(payload["template"].encode("utf-8"))
        active_theme_bytes = active_theme_json_bytes(payload["theme_json"].encode("utf-8"))
        active_revision_bytes = canonical_json_bytes(payload["active_visual_revisions"]) + b"\n"
        user_wording_bytes = canonical_json_bytes(payload["user_wording"]) + b"\n"
        replacements = {
            "[SLIDE_ID]": (payload["slide_id"] + "\n").encode("utf-8"),
            "[SOURCE_AND_VERSION]": section_bytes["SOURCE_AND_VERSION"],
            "[LOCKED_CONTENT]": section_bytes["LOCKED_CONTENT"],
            "[INFORMATION_HIERARCHY]": section_bytes["INFORMATION_HIERARCHY"],
            "[COMPOSITION]": section_bytes["COMPOSITION"],
            "[VISUAL_SYSTEM]": section_bytes["VISUAL_SYSTEM"],
            "[REVISION_MODE]": section_bytes["REVISION_MODE"],
            "[OUTPUT_AND_QA]": section_bytes["OUTPUT_AND_QA"],
            "[ACTIVE_THEME]": active_theme_bytes,
            "[ACTIVE_VISUAL_REVISIONS]": active_revision_bytes,
            "[USER_WORDING]": user_wording_bytes,
        }
        body = compile_prompt_body(template_bytes, replacements)
        style_prompt_snapshot_id = sha256_id(template_bytes)
        compiled_prompt_sha256 = sha256_id(body)
        canonical_payload = copy.deepcopy(payload["snapshot_inputs"])
        canonical_payload["style_prompt_snapshot_id"] = style_prompt_snapshot_id
        canonical_payload["compiled_prompt_sha256"] = compiled_prompt_sha256
        prompt_snapshot_id = sha256_id(canonical_json_bytes(canonical_payload))
        transaction_id = prompt_snapshot_id
        provenance = {
            "artifact_schema_version": 1,
            "transaction_id": transaction_id,
            **canonical_payload,
            "prompt_snapshot_id": prompt_snapshot_id,
            "status": "compiled",
        }
        return {
            "sections": section_bytes,
            "template_bytes": template_bytes,
            "body": body,
            "style_prompt_snapshot_id": style_prompt_snapshot_id,
            "compiled_prompt_sha256": compiled_prompt_sha256,
            "canonical_payload": canonical_payload,
            "canonical_payload_bytes": canonical_json_bytes(canonical_payload),
            "prompt_snapshot_id": prompt_snapshot_id,
            "transaction_id": transaction_id,
            "envelope": render_generation_prompt(provenance, body, payload["slide_id"]),
        }

    def test_brief_sections_follow_exact_byte_grammar(self):
        payload = self._load_generation_prompt_snapshot_payload()
        rendered = self._render_generation_prompt_fixture(payload)
        expected = payload["expected"]
        self.assertEqual(
            {key: value.decode("utf-8") for key, value in rendered["sections"].items()},
            expected["sections"],
        )
        self.assertNotIn("brief_snapshot_id", rendered["sections"]["SOURCE_AND_VERSION"].decode("utf-8"))
        for section_name, section_text in expected["sections"].items():
            with self.subTest(section=section_name):
                self.assertTrue(section_text.endswith("\n"))
                self.assertFalse(section_text.startswith("\n"))
                self.assertFalse(section_text.endswith("\n\n"))
        for case in payload["invalid_briefs"]:
            with self.subTest(case_id=case["id"]):
                with self.assertRaisesRegex(ValueError, "^prompt_snapshot_conflict\Z"):
                    extract_brief_sections(case["brief_markdown"])

    def test_compile_replaces_token_lines_without_recursive_expansion(self):
        payload = self._load_generation_prompt_snapshot_payload()
        rendered = self._render_generation_prompt_fixture(payload)
        body_text = rendered["body"].decode("utf-8")
        self.assertEqual(body_text, payload["expected"]["body"])
        self.assertIn(payload["user_wording"], body_text)
        self.assertIn("[SLIDE_ID]", body_text)
        self.assertIn("## forged heading remains data", body_text)
        for token in PROMPT_PLACEHOLDERS:
            if token == "[SLIDE_ID]":
                continue
            self.assertNotIn(f"\n{token}\n", body_text)
        self.assertNotIn(payload["candidate_path"], body_text)
        self.assertNotIn(payload["output_path"], body_text)

    def test_generation_prompt_snapshot_matches_golden_fixture(self):
        payload = self._load_generation_prompt_snapshot_payload()
        rendered = self._render_generation_prompt_fixture(payload)
        expected = payload["expected"]
        self.assertEqual(rendered["style_prompt_snapshot_id"], expected["style_prompt_snapshot_id"])
        self.assertEqual(rendered["compiled_prompt_sha256"], expected["compiled_prompt_sha256"])
        self.assertEqual(rendered["canonical_payload_bytes"].decode("utf-8"), expected["canonical_payload_json"])
        self.assertEqual(rendered["prompt_snapshot_id"], expected["prompt_snapshot_id"])
        self.assertEqual(rendered["transaction_id"], rendered["prompt_snapshot_id"])
        self.assertEqual(rendered["transaction_id"], expected["transaction_id"])
        self.assertEqual(rendered["envelope"].decode("utf-8"), expected["envelope"])
        provenance_section = expected["envelope"].split("## Provenance\n", 1)[1].split("\n## Compiled Prompt Body", 1)[0]
        provenance_lines = [line for line in provenance_section.splitlines() if line.startswith("- ")]
        self.assertEqual(provenance_lines, expected["provenance_lines"])
        self.assertIn("- applied_visual_revision_ids: [\"visual-revision-2\",\"visual-revision-3\",\"visual-revision-7\",\"visual-revision-10\"]", provenance_lines)
        self.assertNotIn("- brief_snapshot_id:", expected["envelope"])
        self.assertNotIn("candidate_path", expected["canonical_payload_json"])
        self.assertNotIn("output_path", expected["canonical_payload_json"])

    def test_repeat_compile_is_byte_identical(self):
        payload = self._load_generation_prompt_snapshot_payload()
        first = self._render_generation_prompt_fixture(payload)
        second = self._render_generation_prompt_fixture(copy.deepcopy(payload))
        self.assertEqual(first["body"], second["body"])
        self.assertEqual(first["canonical_payload_bytes"], second["canonical_payload_bytes"])
        self.assertEqual(first["envelope"], second["envelope"])
        mutated_non_hash = copy.deepcopy(payload)
        mutated_non_hash["candidate_path"] = "slides/.candidates/S07-different.svg"
        mutated_non_hash["output_path"] = "slides/S07-different.svg"
        non_hash = self._render_generation_prompt_fixture(mutated_non_hash)
        self.assertEqual(first["body"], non_hash["body"])
        self.assertEqual(first["canonical_payload_bytes"], non_hash["canonical_payload_bytes"])

    def test_each_snapshot_input_invalidates_transaction(self):
        payload = self._load_generation_prompt_snapshot_payload()
        baseline = self._render_generation_prompt_fixture(payload)
        for mutation in payload["snapshot_mutations"]:
            mutated = copy.deepcopy(payload)
            target = mutated
            for part in mutation["path"][:-1]:
                target = target[part]
            target[mutation["path"][-1]] = mutation["value"]
            changed = self._render_generation_prompt_fixture(mutated)
            with self.subTest(case_id=mutation["id"]):
                self.assertNotEqual(changed["prompt_snapshot_id"], baseline["prompt_snapshot_id"])
                self.assertNotEqual(changed["transaction_id"], baseline["transaction_id"])
                if mutation.get("body_hash_changes"):
                    self.assertNotEqual(changed["compiled_prompt_sha256"], baseline["compiled_prompt_sha256"])
                else:
                    self.assertEqual(changed["compiled_prompt_sha256"], baseline["compiled_prompt_sha256"])


    def test_active_revision_projection_rejects_unsorted_source_ids(self):
        payload = self._load_active_revision_projection_payload()
        unsorted = next(case for case in payload["conflict_cases"] if case["id"] == "unsorted-brief-ids")
        with self.assertRaisesRegex(ValueError, "^prompt_snapshot_conflict$"):
            project_active_visual_revisions(unsorted["payload"])

    def test_template_leading_blank_lines_are_hash_significant(self):
        payload = self._load_generation_prompt_snapshot_payload()
        baseline = self._render_generation_prompt_fixture(payload)
        mutated = copy.deepcopy(payload)
        mutated["template"] = "\n" + mutated["template"]
        changed = self._render_generation_prompt_fixture(mutated)
        self.assertNotEqual(changed["style_prompt_snapshot_id"], baseline["style_prompt_snapshot_id"])
        self.assertNotEqual(changed["compiled_prompt_sha256"], baseline["compiled_prompt_sha256"])
        self.assertNotEqual(changed["prompt_snapshot_id"], baseline["prompt_snapshot_id"])

    def test_active_theme_outer_blank_lines_are_normalized_without_hash_churn(self):
        payload = self._load_generation_prompt_snapshot_payload()
        baseline = self._render_generation_prompt_fixture(payload)
        mutated = copy.deepcopy(payload)
        mutated["theme_json"] = "\ufeff\n\n\n" + mutated["theme_json"].lstrip("\ufeff\n") + "\n\n"
        changed = self._render_generation_prompt_fixture(mutated)
        self.assertEqual(changed["body"], baseline["body"])
        self.assertEqual(changed["compiled_prompt_sha256"], baseline["compiled_prompt_sha256"])
        self.assertEqual(active_theme_json_bytes(mutated["theme_json"].encode("utf-8")), active_theme_json_bytes(payload["theme_json"].encode("utf-8")))

    def test_render_generation_prompt_requires_explicit_slide_id(self):
        payload = self._load_generation_prompt_snapshot_payload()
        rendered = self._render_generation_prompt_fixture(payload)
        provenance = copy.deepcopy(rendered["canonical_payload"])
        provenance.update({
            "artifact_schema_version": 1,
            "transaction_id": rendered["transaction_id"],
            "prompt_snapshot_id": rendered["prompt_snapshot_id"],
            "status": "compiled",
        })
        with self.assertRaisesRegex(ValueError, "^prompt_snapshot_conflict$"):
            render_generation_prompt(provenance, rendered["body"])

    def test_provenance_assertion_slices_only_provenance_section(self):
        payload = self._load_generation_prompt_snapshot_payload()
        rendered = self._render_generation_prompt_fixture(payload)
        envelope = rendered["envelope"].decode("utf-8")
        provenance_text = envelope.split("## Provenance\n", 1)[1].split("\n## Compiled Prompt Body", 1)[0]
        provenance_lines = [line for line in provenance_text.splitlines() if line.startswith("- ")]
        self.assertEqual(provenance_lines, payload["expected"]["provenance_lines"])
        self.assertNotIn("- source_ids:", provenance_text)

    def _load_identity_migration_payload(self):
        self.assertTrue(
            self.identity_migration_fixture.is_file(),
            f"missing fixture: {self.identity_migration_fixture}",
        )
        payload = json.loads(read_text(self.identity_migration_fixture))
        self.assertEqual(payload["schema_version"], 1)
        for case in payload["cases"]:
            case.setdefault("defaults", payload.get("defaults", {}))
            case.setdefault("fallback_identity_table", payload.get("fallback_identity_table", FALLBACK_IDENTITIES))
        return payload

    def test_identity_migration_cases(self):
        payload = self._load_identity_migration_payload()
        cases = payload["cases"]
        case_ids = [case["id"] for case in cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for required_id in REQUIRED_IDENTITY_CASE_IDS:
            self.assertIn(required_id, case_ids)
        for case in cases:
            with self.subTest(case_id=case["id"]):
                self.assertIn(case["expected"], {"valid", "rebuild", "ordinary_stale", "prompt_snapshot_conflict"})
                self.assertEqual(evaluate_style_identity_case(case), case["expected"])
                if "expected_backfill" in case:
                    self.assertEqual(derive_style_identity_backfill(case), case["expected_backfill"])

    def test_identity_handshake_distinguishes_stale_from_conflict(self):
        cases = {case["id"]: case for case in self._load_identity_migration_payload()["cases"]}
        expected = {
            "missing-both-ids-conflicts-without-owner": "prompt_snapshot_conflict",
            "missing-both-ids-rebuilds-from-persisted-owner": "rebuild",
            "derives-non-id-fields-from-manifest": "rebuild",
            "missing-non-id-fields-rebuilds-with-backfill": "rebuild",
            "stale-display-name-is-ordinary-stale": "ordinary_stale",
            "stale-version-is-ordinary-stale": "ordinary_stale",
            "brief-theme-display-name-conflict": "prompt_snapshot_conflict",
            "brief-theme-manifest-version-conflict": "prompt_snapshot_conflict",
            "direct-style-id-conflict": "prompt_snapshot_conflict",
            "legacy-version-non-none-conflicts": "prompt_snapshot_conflict",
            "prompt-hash-changed-is-ordinary-stale": "ordinary_stale",
            "stored-body-mismatch-conflicts": "prompt_snapshot_conflict",
        }
        for case_id, result in expected.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_style_identity_case(cases[case_id]), result)

    def test_operation_matrix_covers_all_intents_and_triggers(self):
        payload = self._load_identity_migration_payload()
        matrix = payload["operation_matrix"]
        self.assertEqual(set(matrix), set(OPERATION_MATRIX))
        for intent, expected in OPERATION_MATRIX.items():
            with self.subTest(intent=intent):
                row = matrix[intent]
                for key, value in expected.items():
                    self.assertEqual(row.get(key), value)
        self.assertEqual(len(matrix), 4)
        self.assertEqual(matrix["user_recompose"].get("USER_WORDING"), "raw answer from applied history record only")
        self.assertTrue(matrix["local_patch"].get("requires_current_svg"))
        self.assertFalse(matrix["local_patch"].get("compile_full_prompt"))

    def test_task6_reference_language_documents_identity_operation_and_migration(self):
        combined = "\n".join(
            read_text(path)
            for path in (
                self.reference,
                self.visual,
                skill_root() / "references" / "design-system.md",
                self.artifact,
            )
        )
        for token in (
            "四个 schema-v1 identity 字段",
            "`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`",
            "theme.json 与每份 visual-briefs/<slide-id>.md 必须包含完全相同",
            "`generation_intent`",
            "`generation_trigger_id`",
            "initial:<slide-id>:<visual_brief_snapshot_id>",
            "interaction:<applied-history-id>",
            "fallback:<slide-id>:<failed-transaction-64hex>:2",
            "patch:<slide-id>:<qa-defect-id>",
            "initial generation from approved visual brief",
            "deterministic single-column or two-column fallback after two failed patches",
            "none (initial generation)",
            "none (deterministic fallback after two failed patches)",
            "raw answer from applied history record only",
            "requires_current_svg",
            "compile_full_prompt: false",
            "ordinary stale",
            "prompt_snapshot_conflict",
            "fallback identity table",
            "legacy_seed",
            "missing fields",
            "`redesign-prompts/` 始终 inert",
            "不写、不移动、不删除",
            "不得从 SVG、目录、请求文案或用户措辞推断",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_operation_owner_requires_valid_single_durable_source(self):
        cases = {case["id"]: case for case in self._load_identity_migration_payload()["cases"]}
        for case_id in (
            "missing-operation-owner-conflicts",
            "missing-trigger-owner-conflicts",
            "invalid-trigger-owner-conflicts",
            "multiple-trigger-owners-conflict",
            "user-recompose-missing-history-conflicts",
            "user-recompose-non-applied-history-conflicts",
            "user-recompose-multiple-history-conflicts",
        ):
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_style_identity_case(cases[case_id]), "prompt_snapshot_conflict")

        valid = cases["user-recompose-valid-owner"]
        owner = valid["persisted_operation_owner"]
        history_matches = [
            record for record in valid["interaction_history"]
            if record["id"] == owner["generation_trigger_id"].removeprefix("interaction:")
        ]
        self.assertEqual(len(history_matches), 1)
        self.assertEqual(history_matches[0]["status"], "applied")
        self.assertEqual(valid["expected_user_wording"], history_matches[0]["answer"])
        self.assertEqual(evaluate_style_identity_case(valid), "valid")

    def test_deck_scope_fanout_reuses_trigger_but_not_transaction_identity(self):
        cases = {case["id"]: case for case in self._load_identity_migration_payload()["cases"]}
        case = cases["deck-scope-fanout-shares-trigger-not-transaction"]
        briefs = case["affected_briefs"]
        self.assertGreaterEqual(len(briefs), 2)
        self.assertEqual({brief["generation_trigger_id"] for brief in briefs}, {"interaction:visual-revision-9"})
        self.assertEqual(len({brief["slide_id"] for brief in briefs}), len(briefs))
        self.assertEqual(len({brief["transaction_id"] for brief in briefs}), len(briefs))
        self.assertEqual(len({brief["prompt_snapshot_id"] for brief in briefs}), len(briefs))
        for brief in briefs:
            self.assertEqual(brief["transaction_id"], brief["prompt_snapshot_id"])
        self.assertEqual(evaluate_style_identity_case(case), "valid")

    def test_fallback_identity_table_uses_persisted_keys_and_all_legacy_defaults(self):
        payload = self._load_identity_migration_payload()
        table = payload["fallback_identity_table"]
        expected_keys = set(("selected_style_id", "selected_style_display_name", "style_kind", "style_manifest_version"))
        self.assertEqual(set(table), {"minimal-business", "tech-dark", "bold-editorial"})
        for style_id, identity in table.items():
            with self.subTest(style_id=style_id):
                self.assertEqual(set(identity), expected_keys)
                self.assertEqual(identity["selected_style_id"], style_id)
                self.assertEqual(identity["style_kind"], "legacy_seed")
                self.assertEqual(identity["style_manifest_version"], "none")
        cases = {case["id"]: case for case in payload["cases"]}
        for case_id in (
            "fallback-minimal-business-default-table-valid",
            "fallback-tech-dark-default-table-valid",
            "fallback-bold-editorial-default-table-valid",
        ):
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_style_identity_case(cases[case_id]), "valid")

    def test_operation_owner_validates_exact_intent_trigger_contracts(self):
        cases = {case["id"]: case for case in self._load_identity_migration_payload()["cases"]}
        expected = {
            "initial-generation-valid-owner": "valid",
            "initial-generation-malformed-trigger-conflicts": "prompt_snapshot_conflict",
            "initial-generation-wrong-sentinel-conflicts": "prompt_snapshot_conflict",
            "deterministic-fallback-valid-owner": "valid",
            "deterministic-fallback-malformed-trigger-conflicts": "prompt_snapshot_conflict",
            "local-patch-valid-owner": "valid",
            "local-patch-malformed-trigger-conflicts": "prompt_snapshot_conflict",
            "local-patch-missing-current-svg-conflicts": "prompt_snapshot_conflict",
            "local-patch-compiles-full-prompt-conflicts": "prompt_snapshot_conflict",
        }
        for case_id, result in expected.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_style_identity_case(cases[case_id]), result)

    def test_owner_supplied_identity_is_canonicalized_before_backfill(self):
        cases = {case["id"]: case for case in self._load_identity_migration_payload()["cases"]}
        self.assertEqual(evaluate_style_identity_case(cases["missing-both-ids-rebuilds-from-persisted-owner"]), "rebuild")
        self.assertEqual(
            derive_style_identity_backfill(cases["missing-both-ids-rebuilds-from-persisted-owner"]),
            cases["missing-both-ids-rebuilds-from-persisted-owner"]["expected_backfill"],
        )
        for case_id in (
            "missing-both-ids-owner-unregistered-identity-conflicts",
            "missing-both-ids-owner-stale-identity-conflicts",
            "missing-both-ids-owner-inconsistent-identity-conflicts",
        ):
            with self.subTest(case_id=case_id):
                self.assertEqual(evaluate_style_identity_case(cases[case_id]), "prompt_snapshot_conflict")
                self.assertIsNone(derive_style_identity_backfill(cases[case_id]))

    def test_task6_reference_language_is_coherent_per_reference(self):
        redesign = read_text(self.reference)
        visual = read_text(self.visual)
        design = read_text(skill_root() / "references" / "design-system.md")
        artifact = read_text(self.artifact)

        for token in (
            "四个 schema-v1 identity 字段",
            "generation_intent",
            "generation_trigger_id",
            "initial:<slide-id>:<visual_brief_snapshot_id>",
            "interaction:<applied-history-id>",
            "fallback:<slide-id>:<failed-transaction-64hex>:2",
            "patch:<slide-id>:<qa-defect-id>",
            "ordinary stale",
            "prompt_snapshot_conflict",
            "`redesign-prompts/` 始终 inert",
            "不写、不移动、不删除",
            "不得从 SVG、目录、请求文案或用户措辞推断",
            "same `interaction:<id>` copied to every affected brief",
            "distinct slide-specific transaction identities and prompt snapshots",
        ):
            with self.subTest(reference="redesign", token=token):
                self.assertIn(token, redesign)

        for token in (
            "来源与版本",
            "修订模式",
            "generation_intent",
            "generation_trigger_id",
            "requires_current_svg: true",
            "compile_full_prompt: false",
            "不得从 SVG、目录、请求文案或用户措辞推断",
            "same `interaction:<id>` copied to every affected brief",
            "distinct slide-specific transaction identities and prompt snapshots",
        ):
            with self.subTest(reference="visual", token=token):
                self.assertIn(token, visual)

        for token in (
            "fallback identity table",
            "selected_style_id",
            "selected_style_display_name",
            "style_kind",
            "style_manifest_version",
            "missing fields",
            "ordinary stale",
            "prompt_snapshot_conflict",
        ):
            with self.subTest(reference="design", token=token):
                self.assertIn(token, design)

        for token in (
            "history/read-only only",
            "never active prompt source",
            "`redesign-prompts/` 始终 inert",
            "不写、不移动、不删除",
            "prompt_snapshot_conflict",
            "same `interaction:<id>` copied to every affected brief",
            "distinct slide-specific transaction identities and prompt snapshots",
        ):
            with self.subTest(reference="artifact", token=token):
                self.assertIn(token, artifact)

        forbidden_active_legacy = (
            "旧运行可以沿用实际文件名",
            "旧运行可以沿用 actual filename",
            "激活旧目录",
            "激活 redesign-prompts",
        )
        for reference_name, body in (("redesign", redesign), ("visual", visual), ("artifact", artifact)):
            for token in forbidden_active_legacy:
                with self.subTest(reference=reference_name, forbidden=token):
                    self.assertNotIn(token, body)

    def test_dedicated_redesign_reference_exists_and_is_linked(self):
        self.assertTrue(self.reference.exists())
        skill = read_text(self.skill)
        self.assertIn("redesign-prompt.md", skill)
        self.assertLess(skill.index("redesign-prompt.md"), skill.index("SVG 契约"))

    def test_explicit_redesign_triggers_are_observable(self):
        text = read_text(self.reference)
        for trigger in ("重新排版", "重做版式", "重新设计页面", "换个排版"):
            self.assertIn(trigger, text)
        self.assertIn("recompose", text)
        self.assertIn("不得用于 patch", text)

    def test_each_style_owns_a_complete_prompt_template(self):
        for style_id, prompt_path in STYLE_PROMPTS.items():
            path = self.style_root / prompt_path
            with self.subTest(style_id=style_id, path=path):
                self.assertTrue(path.is_file(), f"missing prompt: {path}")
                text = read_text(path)
                raw_lines = text.splitlines()
                lines = [line.strip() for line in raw_lines if line.strip()]

                self.assertEqual(text.count("PROMPT_SCHEMA_VERSION: 1"), 1)
                self.assertEqual(text.count(f"STYLE_ID: {style_id}"), 1)
                self.assertEqual(lines[0], "PROMPT_SCHEMA_VERSION: 1")
                self.assertEqual(lines[1], f"STYLE_ID: {style_id}")
                self.assertEqual(lines[2], "HARD_CONSTRAINT_IDS:")

                hard_constraint_start = next(
                    index for index, line in enumerate(raw_lines)
                    if line.strip() == "HARD_CONSTRAINT_IDS:"
                )
                hard_constraints = []
                for line in raw_lines[hard_constraint_start + 1:]:
                    if not line.startswith("- "):
                        break
                    hard_constraints.append(line.removeprefix("- "))
                self.assertEqual(tuple(hard_constraints), HARD_CONSTRAINT_IDS)

                ordered_markers = (
                    "[SLIDE_ID]",
                    "[SOURCE_AND_VERSION]",
                    "[LOCKED_CONTENT]",
                    "[INFORMATION_HIERARCHY]",
                    "[COMPOSITION]",
                    "[VISUAL_SYSTEM]",
                    "[REVISION_MODE]",
                    "[OUTPUT_AND_QA]",
                    "[ACTIVE_THEME]",
                    "[ACTIVE_VISUAL_REVISIONS]",
                    "BEGIN_UNTRUSTED_USER_WORDING_JSON",
                    "[USER_WORDING]",
                    "END_UNTRUSTED_USER_WORDING_JSON",
                )

                ordered_indices = []
                for marker in ordered_markers:
                    matches = [index for index, line in enumerate(raw_lines) if line == marker]
                    self.assertEqual(text.count(marker), 1, marker)
                    self.assertEqual(len(matches), 1, marker)
                    ordered_indices.append(matches[0])
                self.assertEqual(ordered_indices, sorted(ordered_indices))

                for marker in ("[VISUAL_BRIEF]", "[OUTPUT_PATH]", "[USER_PAGE_REQUEST]", "[LOCKED_ORIGINAL_CONTENT]"):
                    self.assertNotIn(marker, text)

    def test_prompt_is_persisted_and_runs_in_fresh_context(self):
        combined = "\n".join(read_text(path) for path in (self.reference, self.visual, self.qa, self.artifact))
        for token in (
            "redesign-prompts/<slide-id>.md",
            "fresh",
            "独立",
            "只授予",
            "旧 SVG",
            "创作对话",
            "prompt_snapshot_id",
        ):
            self.assertIn(token, combined)

    def test_canway_prompt_owns_card_geometry_compatibility(self):
        text = read_text(self.style_root / "canway-midyear-review" / "REDESIGN.md")
        self.assertIn("<path", text)
        self.assertIn("A 16 16", text)
        self.assertIn("禁止使用 `<rect rx", text)
        self.assertIn("普通直角 `<rect>`", text)

    def test_each_style_prompt_contains_text_and_powerpoint_contract(self):
        for style_id, prompt_path in STYLE_PROMPTS.items():
            text = read_text(self.style_root / prompt_path)
            with self.subTest(style_id=style_id):
                for token in (
                    "一个独立 `<text>`",
                    "一个简单 `<tspan>`",
                    "nested tspan",
                    "Microsoft YaHei, Arial, sans-serif",
                    "12%",
                    "PowerPoint",
                ):
                    self.assertIn(token, text)

    def test_each_style_prompt_states_shared_semantic_responsibilities(self):
        content_lock_terms = (
            "置信度",
            "范围",
            "因果",
            "比较",
            "数字",
            "单位",
            "限定",
            "来源",
            "受众行动",
        )
        hierarchy_terms = ("信息层级", "焦点", "阅读顺序", "几何")
        execution_terms = (
            "fresh generator",
            "不能写入工作区",
            "只返回文本",
            "创建上下文",
            "提取",
            "验证",
            "原子提升",
        )

        for style_id, prompt_path in STYLE_PROMPTS.items():
            text = read_text(self.style_root / prompt_path)
            contract = text.split("## Output Contract", 1)[1]
            with self.subTest(style_id=style_id, responsibility="content-lock"):
                for token in content_lock_terms:
                    self.assertIn(token, contract)
            with self.subTest(style_id=style_id, responsibility="hierarchy-before-geometry"):
                for token in hierarchy_terms:
                    self.assertIn(token, contract)
                positions = [contract.index(token) for token in hierarchy_terms]
                self.assertEqual(positions, sorted(positions))
            with self.subTest(style_id=style_id, responsibility="execution-boundary"):
                for token in execution_terms:
                    self.assertIn(token, contract)

    def test_canway_prompt_states_purple_semantics_and_phrase_emphasis(self):
        text = read_text(self.style_root / "canway-midyear-review" / "REDESIGN.md")
        for token in ("紫色", "AI", "有界试点", "高风险", "失败", "回退"):
            self.assertIn(token, text)
        for token in ("短语级", "标题强调", "句义", "页面语义", "exceptions"):
            self.assertIn(token, text)

    def test_initial_generation_uses_the_same_dedicated_prompt(self):
        combined = "\n".join(
            read_text(path)
            for path in (self.skill, self.reference, self.visual, self.qa, self.artifact)
        )
        for token in (
            "首次生成",
            "所有页面",
            "generation-prompts/<slide-id>.md",
            "不得由 visual brief 直接生成",
            "fresh",
            "独立",
        ):
            self.assertIn(token, combined)

    def test_generation_prompt_is_required_visual_artifact(self):
        text = read_text(self.artifact)
        self.assertIn("- `generation-prompts/`", text)
        self.assertIn("每个首次生成", text)
        self.assertIn("redesign-prompts/", text)
        self.assertIn("只读兼容", text)

    def test_synthetic_prompt_fixture_declares_expected_artifacts(self):
        self.assertTrue(self.prompt_fixture.exists())
        text = read_text(self.prompt_fixture)
        for token in (
            "generation-prompts/S07.md",
            "visual-briefs/S07.md",
            "recompose",
            "path + A",
            "only fenced SVG",
            "slides/S07.svg",
        ):
            self.assertIn(token, text)

    def test_pressure_prompts_define_diagnostic_boundaries(self):
        cases = {
            "style-prompt-isolation-pressure.md": ("tech-dark", "style isolation"),
            "style-prompt-fallback-pressure.md": ("minimal-business", "registry fallback"),
            "style-prompt-blocker-pressure.md": ("canway-midyear-review", "style_prompt_unavailable"),
        }
        for filename, (style_id, scenario) in cases.items():
            with self.subTest(filename=filename):
                path = repo_root() / "tests" / "prompts" / filename
                self.assertTrue(path.is_file(), filename)
                text = read_text(path)
                self.assertIn(f"selected_style_id: {style_id}", text)
                self.assertIn(f"scenario: {scenario}", text)
                operation_lines = [
                    line.removeprefix("operation: ").strip()
                    for line in text.splitlines()
                    if line.startswith("operation: ")
                ]
                self.assertEqual(len(operation_lines), 1)
                self.assertIn(operation_lines[0], {"initial_generation", "user_recompose"})
                for heading in ("expected_artifacts:", "expected_state:", "forbidden_behavior:"):
                    self.assertEqual(text.splitlines().count(heading), 1)
                for token in (
                    "EVIDENCE_CLASS: DIAGNOSTIC",
                    "不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收",
                ):
                    self.assertIn(token, text)

    def test_shared_reference_is_resolver_only(self):
        text = read_text(self.reference)
        self.assertNotIn("## 专用 Prompt 模板", text)
        for forbidden in ("层级 Bento", "深色主卡", "40%–60%", "Microsoft YaHei"):
            self.assertNotIn(forbidden, text)

    def _load_resolution_cases(self):
        self.assertTrue(self.resolution_fixture.is_file(), f"missing fixture: {self.resolution_fixture}")
        with self.resolution_fixture.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["schema_version"], 1)
        cases = payload["cases"]
        self.assertIsInstance(cases, list)
        case_ids = [case["id"] for case in cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for required_id in REQUIRED_RESOLUTION_CASE_IDS:
            self.assertIn(required_id, case_ids)
        return cases

    def _resolution_case_by_id(self, case_id):
        return next(case for case in self._load_resolution_cases() if case["id"] == case_id)

    def test_no_follow_targets_map_to_path_unsafe_reasons(self):
        for target in sorted(NO_FOLLOW_TARGETS):
            scenarios = []

            registry_case = copy.deepcopy(self._resolution_case_by_id("valid-minimal-business"))
            registry_case["registry"]["state"] = target
            scenarios.append((target, "registry", registry_case, "registry_path_unsafe"))

            entrypoint_case = copy.deepcopy(self._resolution_case_by_id("valid-minimal-business"))
            entrypoint_case["resources"]["entrypoints"]["minimal-business"]["target"] = target
            scenarios.append((target, "entrypoint", entrypoint_case, "entrypoint_path_unsafe"))

            asset_case = copy.deepcopy(self._resolution_case_by_id("valid-canway-midyear-review"))
            asset_case["resources"]["assets"]["canway-midyear-review"]["tokens"]["target"] = target
            scenarios.append((target, "asset", asset_case, "style_asset_path_unsafe"))

            prompt_case = copy.deepcopy(self._resolution_case_by_id("valid-minimal-business"))
            prompt_case["resources"]["prompts"]["minimal-business"]["target"] = target
            scenarios.append((target, "prompt", prompt_case, "prompt_path_unsafe"))

            for target_name, route, case, reason in scenarios:
                with self.subTest(target=target_name, route=route):
                    self.assertEqual(resolve_style_prompt_case(case), _failure(reason))

    def test_registry_missing_fallback_rejects_unreadable_regular_files(self):
        valid_case = self._resolution_case_by_id("fallback-complete-six-file-minimal-business")
        for style_id in FALLBACK_IDENTITIES:
            for field in ("seed", "prompt"):
                case = copy.deepcopy(valid_case)
                case["fallback_files"][style_id][field]["readable"] = False
                with self.subTest(style_id=style_id, field=field):
                    self.assertEqual(resolve_style_prompt_case(case), _failure("registry_missing"))

    def test_resolution_fixture_covers_all_branches(self):
        cases = self._load_resolution_cases()
        covered = {branch for case in cases for branch in case.get("covers", [])}
        for branch in RESOLUTION_BRANCHES:
            self.assertIn(branch, covered)

        expected_by_id = {case["id"]: case["expected"] for case in cases}
        self.assertEqual(
            expected_by_id["precedence-unselected-pack-root-before-selected-prompt"],
            {
                "ok": False,
                "reason": "entrypoint_path_unsafe",
                "resolved_path": None,
            },
        )
        self.assertEqual(
            expected_by_id["precedence-selected-tokens-before-prompt"],
            {
                "ok": False,
                "reason": "style_asset_target_invalid",
                "resolved_path": None,
            },
        )
        for case_id in REQUIRED_RESOLUTION_CASE_IDS[2:]:
            self.assertEqual(
                expected_by_id[case_id],
                {
                    "ok": False,
                    "reason": "registry_missing",
                    "resolved_path": None,
                },
            )
        for case in cases:
            with self.subTest(case_id=case["id"]):
                self.assertEqual(resolve_style_prompt_case(case), case["expected"])

    def test_resolution_failure_precedence(self):
        cases = {case["id"]: case for case in self._load_resolution_cases()}
        for case_id in (
            "precedence-unselected-pack-root-before-selected-prompt",
            "precedence-selected-tokens-before-prompt",
        ):
            with self.subTest(case_id=case_id):
                self.assertGreaterEqual(len(cases[case_id].get("defects", [])), 2)
                self.assertEqual(resolve_style_prompt_case(cases[case_id]), cases[case_id]["expected"])

    def test_shared_reference_is_style_neutral(self):
        combined = "\n".join(
            read_text(path)
            for path in (
                self.reference,
                skill_root() / "references" / "design-system.md",
            )
        )
        for required in (
            "registry_missing",
            "entrypoint_path_unsafe",
            "style_asset_target_invalid",
            "prompt_snapshot_conflict",
            "package oracle",
        ):
            self.assertIn(required, combined)
        for style_literal in (
            "层级 Bento",
            "深色主卡",
            "白色事实卡",
            "40%–60%",
            "最多一处轻阴影",
        ):
            self.assertNotIn(style_literal, combined)

    def test_canway_literals_are_isolated_to_canway_prompt(self):
        required = (
            "层级 Bento",
            "深色主卡",
            "白色事实卡",
            "浅蓝证据边界",
            "40%–60%",
            "1.5",
            "最多一处轻阴影",
        )
        canway = read_text(self.style_root / "canway-midyear-review" / "REDESIGN.md")
        other = "\n".join(
            [
                read_text(self.reference),
                *(read_text(self.style_root / STYLE_PROMPTS[style_id]) for style_id in ("minimal-business", "tech-dark", "bold-editorial")),
            ]
        )
        for token in required:
            self.assertIn(token, canway)
            self.assertNotIn(token, other)

    def test_canway_style_links_complete_prompt_and_page_exceptions(self):
        text = read_text(self.style_root / "canway-midyear-review" / "STYLE.md")
        self.assertIn("REDESIGN.md", text)
        self.assertIn("完整生成 prompt", text)
        self.assertIn("exceptions", text)
        self.assertIn("页面语义", text)


if __name__ == "__main__":
    unittest.main()
