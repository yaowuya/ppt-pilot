"""Packaged deterministic prompt_runtime operations."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import types
from pathlib import Path


def skill_root() -> Path:
    return Path(__file__).parent.parent


def _style_verifier():
    """Load only the installed sibling verifier, independent of sys.path."""
    package_root = Path(__file__).parent.parent.parent / "ppt-style-extract" / "scripts" / "_style_extract"
    package_name = "_ppt_runtime_style_verifier"
    if package_name + ".verify" not in sys.modules:
        _validate_directory_chain_no_follow(package_root, path_reason="style_asset_path_unsafe", missing_reason="style_asset_target_invalid")
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_root)]
        sys.modules[package_name] = package
        for name in ("errors", "verify"):
            path = package_root / (name + ".py")
            _validate_leaf_no_follow(path, path_reason="style_asset_path_unsafe", missing_reason="style_asset_target_invalid")
            spec = importlib.util.spec_from_file_location(package_name + "." + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
    return sys.modules[package_name + ".verify"]

CANONICAL_REPLACEMENT_MARKER_RE = re.compile(rb"\[\[.*?\]\]", re.DOTALL)


DYNAMIC_TEMPLATE_MARKER_RE = re.compile(rb"\{\{.*?\}\}", re.DOTALL)


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


def _path_has_reparse(path: Path) -> bool:
    target_stat = os.lstat(path)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(target_stat.st_mode) or bool(
        getattr(target_stat, "st_file_attributes", 0) & reparse_flag
    )


def _absolute_without_following(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _validate_directory_chain_no_follow(
    path: Path, *, path_reason: str, missing_reason: str
) -> Path:
    """Validate every directory component without resolving a link target."""
    absolute = _absolute_without_following(path)
    current = Path(absolute.anchor)
    relative_parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in relative_parts:
        current = current / part
        try:
            target_stat = os.lstat(current)
        except FileNotFoundError as exc:
            raise ValueError(missing_reason) from exc
        except OSError as exc:
            raise ValueError(path_reason) from exc
        try:
            if _path_has_reparse(current):
                raise ValueError(path_reason)
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError(path_reason) from exc
        if not stat.S_ISDIR(target_stat.st_mode):
            raise ValueError(path_reason)
    return absolute


def _validate_leaf_no_follow(
    path: Path, *, path_reason: str, missing_reason: str
) -> None:
    try:
        os.lstat(path)
    except FileNotFoundError as exc:
        raise ValueError(missing_reason) from exc
    except OSError as exc:
        raise ValueError(path_reason) from exc
    try:
        if _path_has_reparse(path):
            raise ValueError(path_reason)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(path_reason) from exc


class AssetFailure(ValueError):
    """Resolver failure retaining the exact trusted resource for blocker owners."""
    def __init__(self, reason, resource):
        super().__init__(reason)
        self.reason = reason
        self.resource = resource


def _read_regular_asset(path, **reasons):
    try:
        return _read_regular_asset_impl(path, **reasons)
    except ValueError as error:
        reason = str(error)
        try:
            resource = Path(path).relative_to(skill_root()).as_posix()
        except ValueError:
            resource = 'none'
        if reason.endswith('_path_unsafe') or reason in ('registry_missing', 'style_asset_field_missing'):
            resource = 'none'
        raise AssetFailure(reason, resource) from error


def _read_regular_asset_impl(
    path: Path,
    *,
    path_reason: str,
    missing_reason: str,
    target_reason: str,
    unreadable_reason: str,
) -> bytes:
    """Read one trusted asset without following a symlink/reparse target."""
    absolute = _absolute_without_following(path)
    _validate_directory_chain_no_follow(
        absolute.parent,
        path_reason=path_reason,
        missing_reason=missing_reason,
    )
    try:
        target_stat = os.lstat(absolute)
    except FileNotFoundError as exc:
        raise ValueError(missing_reason) from exc
    except OSError as exc:
        raise ValueError(unreadable_reason) from exc
    try:
        if _path_has_reparse(absolute):
            raise ValueError(path_reason)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(path_reason) from exc
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError(target_reason)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(absolute, flags)
    except FileNotFoundError as exc:
        raise ValueError(missing_reason) from exc
    except PermissionError as exc:
        raise ValueError(unreadable_reason) from exc
    except OSError as exc:
        raise ValueError(path_reason) from exc
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise ValueError(target_reason)
        if (target_stat.st_dev, target_stat.st_ino) != (
            opened_stat.st_dev,
            opened_stat.st_ino,
        ):
            raise ValueError(path_reason)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(unreadable_reason) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _decode_asset(raw: bytes, unreadable_reason: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(unreadable_reason) from exc


def _load_json_asset(raw: bytes, malformed_reason: str, unreadable_reason: str) -> dict:
    text = _decode_asset(raw, unreadable_reason)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(malformed_reason) from exc
    if not isinstance(value, dict):
        raise ValueError(malformed_reason)
    return value


def style_template_path(style_id: str) -> str:
    """Resolve a required style-owned template through registry -> manifest."""
    if not isinstance(style_id, str) or re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", style_id
    ) is None:
        raise ValueError("style_not_registered")
    style_root = skill_root() / "assets" / "styles"
    registry_path = style_root / "registry.json"
    registry_raw = _read_regular_asset(
        registry_path,
        path_reason="registry_path_unsafe",
        missing_reason="registry_missing",
        target_reason="registry_target_invalid",
        unreadable_reason="registry_unreadable",
    )
    registry = _load_json_asset(
        registry_raw, "registry_malformed", "registry_unreadable"
    )
    if registry.get("schema_version") != 1:
        raise ValueError("registry_schema_unsupported")
    styles = registry.get("styles")
    if not isinstance(styles, list):
        raise ValueError("registry_malformed")
    if not all(isinstance(item, dict) for item in styles):
        raise ValueError("registry_malformed")
    if len({item.get("id") for item in styles}) != len(styles):
        raise ValueError("registry_duplicate_style")
    display_names = [item.get("display_name") for item in styles]
    if len(set(display_names)) != len(styles):
        raise ValueError("registry_duplicate_style")
    style_root_absolute = _absolute_without_following(style_root)
    for item in styles:
        item_id = item.get("id")
        if (
            not isinstance(item_id, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item_id) is None
            or not isinstance(item.get("display_name"), str)
            or not item["display_name"]
        ):
            raise ValueError("registry_malformed")
        if item.get("kind") != "style_pack":
            continue
        expected_item_entrypoint = f"{item_id}/manifest.json"
        if item.get("entrypoint") != expected_item_entrypoint:
            raise ValueError("entrypoint_path_unsafe")
        item_pack_root = style_root_absolute / item_id
        item_manifest_path = item_pack_root / "manifest.json"
        if item_pack_root.parent != style_root_absolute:
            raise ValueError("entrypoint_path_unsafe")
        _validate_directory_chain_no_follow(
            item_pack_root,
            path_reason="entrypoint_path_unsafe",
            missing_reason="entrypoint_missing",
        )
        _validate_leaf_no_follow(
            item_manifest_path,
            path_reason="entrypoint_path_unsafe",
            missing_reason="entrypoint_missing",
        )
    matches = [item for item in styles if item.get("id") == style_id]
    if len(matches) != 1:
        raise ValueError("style_not_registered")
    entry = matches[0]
    if entry.get("kind") != "style_pack":
        raise ValueError("style_kind_invalid")
    expected_entrypoint = f"{style_id}/manifest.json"
    if entry.get("entrypoint") != expected_entrypoint:
        raise ValueError("entrypoint_path_unsafe")
    pack_root = style_root_absolute / style_id
    manifest_path = pack_root / "manifest.json"
    manifest_raw = _read_regular_asset(
        manifest_path,
        path_reason="entrypoint_path_unsafe",
        missing_reason="entrypoint_missing",
        target_reason="entrypoint_target_invalid",
        unreadable_reason="entrypoint_unreadable",
    )
    manifest = _load_json_asset(
        manifest_raw, "manifest_malformed", "entrypoint_unreadable"
    )
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest_schema_unsupported")
    if (
        manifest.get("id") != style_id
        or manifest.get("kind") != "style_pack"
        or manifest.get("display_name") != entry.get("display_name")
        or not isinstance(manifest.get("selection_aliases"), list)
        or style_id not in manifest["selection_aliases"]
    ):
        raise ValueError("manifest_identity_mismatch")
    if not _is_semver(manifest.get("version")):
        raise ValueError("manifest_version_invalid")
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, dict) or compatibility.get("office_safe_svg") is not True:
        raise ValueError("manifest_schema_unsupported")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise AssetFailure("manifest_malformed", manifest_path.relative_to(skill_root()).as_posix())
    required_files = {
        "tokens": "tokens.json",
        "guidance": "STYLE.md",
        "prompt_template": "prompt.md",
    }
    if any(field not in files for field in required_files):
        raise ValueError("style_asset_field_missing")
    if files != required_files:
        if files.get("prompt_template") != "prompt.md":
            raise ValueError("prompt_path_unsafe")
        raise ValueError("style_asset_path_unsafe")
    template_rel = files["prompt_template"]
    if (
        template_rel != "prompt.md"
        or _is_path_unsafe(template_rel)
        or "\\" in template_rel
    ):
        raise ValueError("prompt_path_unsafe")
    return f"assets/styles/{style_id}/{template_rel}"


def _style_template_bytes(style_id: str) -> bytes:
    path = style_template_path(style_id)
    template_path = skill_root() / path
    verifier = _style_verifier()
    verify_prompt = verifier.verify_prompt
    verify_prompt_style_binding = verifier.verify_prompt_style_binding
    verify_rules = verifier.verify_rules
    verify_tokens = verifier.verify_tokens

    pack_root = template_path.parent
    tokens_path = pack_root / "tokens.json"
    guidance_path = pack_root / "STYLE.md"
    tokens_raw = _read_regular_asset(
        tokens_path,
        path_reason="style_asset_path_unsafe",
        missing_reason="style_asset_target_invalid",
        target_reason="style_asset_target_invalid",
        unreadable_reason="style_asset_unreadable",
    )
    tokens = _load_json_asset(
        tokens_raw, "style_asset_malformed", "style_asset_unreadable"
    )
    if tokens.get("schema_version") != 2:
        raise ValueError("style_asset_schema_unsupported")
    try:
        verify_tokens(tokens)
    except Exception as exc:
        raise AssetFailure("style_asset_malformed", tokens_path.relative_to(skill_root()).as_posix()) from exc
    if tokens.get("id") != style_id:
        raise AssetFailure("style_asset_malformed", tokens_path.relative_to(skill_root()).as_posix())

    guidance_raw = _read_regular_asset(
        guidance_path,
        path_reason="style_asset_path_unsafe",
        missing_reason="style_asset_target_invalid",
        target_reason="style_asset_target_invalid",
        unreadable_reason="style_asset_unreadable",
    )
    try:
        guidance = _decode_asset(guidance_raw, "style_asset_unreadable")
    except ValueError as error:
        raise AssetFailure(str(error), guidance_path.relative_to(skill_root()).as_posix()) from error
    try:
        verify_rules(guidance)
    except Exception as exc:
        raise AssetFailure("style_asset_malformed", guidance_path.relative_to(skill_root()).as_posix()) from exc

    raw = _read_regular_asset(
        template_path,
        path_reason="prompt_path_unsafe",
        missing_reason="prompt_file_missing",
        target_reason="prompt_target_invalid",
        unreadable_reason="prompt_unreadable",
    )
    try:
        normalized = normalize_lf(raw)
    except ValueError as exc:
        raise ValueError("prompt_unreadable") from exc
    prompt_text = _decode_asset(normalized, "prompt_unreadable")
    try:
        verify_prompt(prompt_text)
        verify_prompt_style_binding(tokens, prompt_text)
    except Exception as exc:
        raise AssetFailure("prompt_template_invalid", path) from exc
    return normalized


def runtime_style_assets(style_id):
    """Resolve with a closed, structured failure resource (never exception prose)."""
    try:
        template_path = style_template_path(style_id)
        return template_path, _style_template_bytes(style_id)
    except AssetFailure:
        raise
    except ValueError as error:
        reason = str(error)
        if reason.endswith('_path_unsafe') or reason in ('registry_missing', 'style_asset_field_missing', 'prompt_snapshot_conflict'):
            resource = 'none'
        elif reason.startswith('registry_') or reason in ('style_not_registered', 'style_kind_invalid'):
            resource = 'assets/styles/registry.json'
        elif isinstance(style_id, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', style_id):
            if reason.startswith(('manifest_', 'entrypoint_')):
                resource = 'assets/styles/' + style_id + '/manifest.json'
            elif reason in ('style_asset_malformed', 'style_asset_schema_unsupported'):
                resource = 'assets/styles/' + style_id + '/tokens.json'
            elif reason.startswith('prompt_'):
                resource = 'assets/styles/' + style_id + '/prompt.md'
            else:
                raise
        else:
            raise
        raise AssetFailure(reason, resource) from error


def _validate_canonical_template_path(snapshot_inputs: dict) -> None:
    style_id = snapshot_inputs.get("selected_style_id")
    if not style_id:
        raise ValueError("prompt_snapshot_conflict")
    expected = style_template_path(style_id)
    if snapshot_inputs.get("resolved_generation_prompt_template_path") != expected:
        raise ValueError("prompt_snapshot_conflict")


def _contains_raw_json_block(text: str) -> bool:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^\s*(?=[\[{])", text):
        candidate = text[match.start():].lstrip()
        try:
            value, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return True
    return False


def _reject_unsafe_replacement(raw: bytes) -> bytes:
    normalized = normalize_lf(raw)
    text = normalized.decode("utf-8")
    stripped = text.lstrip("﻿\n")
    legacy_steps = (
        ("页面 ID:" in text and "步骤 1" in text and "步骤 2" in text and "步骤 3" in text)
        or ("Page ID:" in text and "Step 1" in text and "Step 2" in text and "Step 3" in text)
    )
    forbidden_markers = (
        "PROMPT_SCHEMA_VERSION:",
        "STYLE_ID:",
        "HARD_CONSTRAINT_IDS:",
        "BEGIN_UNTRUSTED_USER_WORDING_JSON",
        "END_UNTRUSTED_USER_WORDING_JSON",
    )
    external_instruction = re.search(
        r"(?is)(?:\b(?:read|load|open|fetch|consult)\b.{0,32}\b(?:external\s+)?files?\b)"
        r"|(?:\b(?:call|invoke|use)\b.{0,24}\b(?:the\s+)?(?:read\s+)?tools?\b)"
        r"|(?:(?:读取|打开|载入|获取|参考|查阅).{0,12}(?:外部)?(?:文件|资料))"
        r"|(?:(?:使用|调用|执行|运行).{0,12}(?:Read\s*)?工具)",
        text,
    )
    unix_absolute_path = re.search(
        r"(?m)(?<!\w)/(?!/|\s)[^\s/]+(?:/[^\s]*)?",
        text,
    )
    absolute_path_or_uri = (
        re.search(r"(?i)(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*:[^\s]", text)
        or re.search(r"(?<!:)//[^\s]", text)
        or unix_absolute_path
        or re.search(r"[A-Za-z]:[\\/]", text)
        or re.search(r"\\\\[^\s\\]+[\\/]", text)
    )
    json_fence = re.search(r"(?im)^\s*(?:```|~~~)\s*json\b", text)
    setext_heading = re.search(
        r"(?m)^[^\r\n]*\S[^\r\n]*\n[\t ]*(?:={3,}|-{3,})[\t ]*$",
        text,
    )
    if (
        not text.strip()
        or (stripped.startswith("Role:") and legacy_steps)
        or any(marker.lower() in text.lower() for marker in forbidden_markers)
        or re.search(r"(?m)^#{1,6}\s", text)
        or CANONICAL_REPLACEMENT_MARKER_RE.search(normalized)
        or json_fence
        or setext_heading
        or _contains_raw_json_block(text)
        or absolute_path_or_uri
        or external_instruction
        or any(separator in normalized for separator in NON_LF_LINE_SEPARATORS)
    ):
        raise ValueError("prompt_preflight_invalid")
    return normalized


STYLE_NARRATIVE_TOKEN = b"{{NARRATIVE}}"


SOURCE_ANNOTATION_RE = re.compile(
    rb"(?:\bsource\s*=|\[claim\s*=|data-source-id|\bSRC-[0-9]+\b)",
    re.IGNORECASE,
)


STYLE_REQUIRED_HEADINGS = (
    b"# Role",
    b"## Workflow",
    "### 步骤 1".encode("utf-8"),
    "### 步骤 2".encode("utf-8"),
    "### 步骤 3".encode("utf-8"),
    "### 兼容约束".encode("utf-8"),
)


NON_LF_LINE_SEPARATORS = (
    b"\x0b",
    b"\x0c",
    b"\x1c",
    b"\x1d",
    b"\x1e",
    b"\xc2\x85",
    b"\xe2\x80\xa8",
    b"\xe2\x80\xa9",
)


BLOCK_ID_LINE_RE = re.compile(rb"(?m)^- block_id: (S[0-9]+-B[1-9][0-9]*)$")


DEFAULT_EXPECTED_BLOCK_IDS = (b"S01-B1",)


def _validate_narrative_block_ids(
    narrative: bytes, expected_block_ids: tuple[bytes, ...]
) -> None:
    block_ids = tuple(BLOCK_ID_LINE_RE.findall(narrative))
    if (
        not block_ids
        or len(block_ids) != len(set(block_ids))
        or narrative.count(b"block_id") != len(block_ids)
        or len({block_id.rsplit(b"-B", 1)[0] for block_id in block_ids}) != 1
    ):
        raise ValueError("prompt_preflight_invalid")
    if (
        not expected_block_ids
        or len(expected_block_ids) != len(set(expected_block_ids))
        or any(
            re.fullmatch(rb"S[0-9]+-B[1-9][0-9]*", block_id) is None
            for block_id in expected_block_ids
        )
        or block_ids != expected_block_ids
    ):
        raise ValueError("storyboard_fact_mismatch")


def _validate_required_prompt_structure(body: bytes) -> None:
    if any(separator in body for separator in NON_LF_LINE_SEPARATORS):
        raise ValueError("prompt_template_invalid")
    lines = body.split(b"\n")
    positions = []
    for heading in STYLE_REQUIRED_HEADINGS:
        matches = []
        for index, line in enumerate(lines):
            if line == heading:
                matches.append(index)
                continue
            if line.startswith(heading):
                tail = line[len(heading) :]
                if tail.startswith(
                    (b":", "：".encode("utf-8"), b" ", b"\t", b"(", "（".encode("utf-8"))
                ):
                    matches.append(index)
        if len(matches) != 1:
            raise ValueError("prompt_template_invalid")
        positions.append(matches[0])
    if (
        positions != sorted(positions)
        or positions[0] != 0
        or b"data-block-id" not in body
    ):
        raise ValueError("prompt_template_invalid")


def compile_style_prompt(
    narrative_bullets: bytes,
    template_bytes: bytes,
    expected_block_ids: tuple[bytes, ...] = DEFAULT_EXPECTED_BLOCK_IDS,
) -> bytes:
    """Compile a style-owned complete prompt template by injecting the canonical
    narrative bullets at its single whole-line {{NARRATIVE}} token. The narrative
    carries no source-/source-annotation fields; those stay in the review layer.
    The style template is a trusted repository asset and may contain its own
    headings/steps; only the narrative replacement is run through the preflight
    safety check, and the template's injection-token structure is validated."""
    narrative = _reject_unsafe_replacement(narrative_bullets)
    _validate_narrative_block_ids(narrative, expected_block_ids)
    template = normalize_lf(template_bytes)
    verify_prompt = _style_verifier().verify_prompt

    try:
        verify_prompt(template.decode("utf-8"))
    except Exception as exc:
        raise ValueError("prompt_template_invalid") from exc
    _validate_required_prompt_structure(template)
    if (
        template.count(STYLE_NARRATIVE_TOKEN) != 1
        or template.split(b"\n").count(STYLE_NARRATIVE_TOKEN) != 1
        or DYNAMIC_TEMPLATE_MARKER_RE.findall(template) != [STYLE_NARRATIVE_TOKEN]
        or CANONICAL_REPLACEMENT_MARKER_RE.search(template)
    ):
        raise ValueError("prompt_template_invalid")
    template_without_narrative = template.replace(STYLE_NARRATIVE_TOKEN, b"", 1)
    if (
        b"{{" in template_without_narrative
        or b"}}" in template_without_narrative
        or b"[[" in template
        or b"]]" in template
    ):
        raise ValueError("prompt_template_invalid")
    # source-annotation fields must not leak into a style-owned prompt: statement
    # provenance stays in the review layer only, never in the generated prompt.
    if SOURCE_ANNOTATION_RE.search(narrative):
        raise ValueError("prompt_preflight_invalid")
    body = normalize_lf(template.replace(STYLE_NARRATIVE_TOKEN, narrative))
    if not body.endswith(b"\n"):
        body += b"\n"
    if (
        DYNAMIC_TEMPLATE_MARKER_RE.search(body)
        or CANONICAL_REPLACEMENT_MARKER_RE.search(body)
        or b"{{" in body
        or b"}}" in body
        or b"[[" in body
        or b"]]" in body
        or SOURCE_ANNOTATION_RE.search(body)
    ):
        raise ValueError("prompt_preflight_invalid")
    return body


def validate_style_compiled_body(body: bytes) -> None:
    """Validate a style-owned prompt body (the style template with its single
    {{NARRATIVE}} already replaced by the narrative). It must not carry legacy
    two-marker text, a residual {{NARRATIVE}} token, or source-annotation fields."""
    normalized = normalize_lf(body)
    if normalized != body:
        raise ValueError("prompt_preflight_invalid")
    try:
        _validate_required_prompt_structure(body)
    except ValueError as exc:
        raise ValueError("prompt_preflight_invalid") from exc
    if not body.startswith(b"# Role") or not body.endswith(b"\n"):
        raise ValueError("prompt_preflight_invalid")
    if (
        DYNAMIC_TEMPLATE_MARKER_RE.search(body)
        or CANONICAL_REPLACEMENT_MARKER_RE.search(body)
        or b"{{" in body
        or b"}}" in body
        or b"[[" in body
        or b"]]" in body
        or SOURCE_ANNOTATION_RE.search(body)
    ):
        raise ValueError("prompt_preflight_invalid")


def sha256_id(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


METADATA_FIELD_ORDER = (
    "slide_id",
    "storyboard_snapshot_id",
    "theme_snapshot_id",
    "applied_visual_revision_ids",
    "prompt_snapshot_id",
    "user_page_request",
    "expected_output",
    "workspace_output_path",
    "format",
)


COMPILED_PROMPT_SEPARATOR = b"## Compiled Prompt\n\n"


def split_generation_prompt_envelope(envelope: bytes) -> tuple[bytes, bytes]:
    if envelope.count(COMPILED_PROMPT_SEPARATOR) != 1:
        raise ValueError("prompt_preflight_invalid")
    prefix, body = envelope.split(COMPILED_PROMPT_SEPARATOR, 1)
    if not body.startswith(b"# Role") or not body.endswith(b"\n") or body.endswith(b"\n\n"):
        raise ValueError("prompt_preflight_invalid")
    return prefix, body


def _provenance_value_text(value):
    if isinstance(value, list):
        return canonical_json_bytes(value).decode("utf-8")
    return str(value)


def render_generation_prompt(metadata: dict, body: bytes, slide_id=None) -> bytes:
    if not isinstance(slide_id, str) or not slide_id or "\n" in slide_id or "\r" in slide_id:
        raise ValueError("prompt_snapshot_conflict")
    missing = [field for field in METADATA_FIELD_ORDER if field not in metadata]
    if missing:
        raise ValueError("prompt_snapshot_conflict")
    for value in metadata.values():
        serialized = _provenance_value_text(value)
        if "\n" in serialized or "\r" in serialized:
            raise ValueError("prompt_snapshot_conflict")
    validate_style_compiled_body(body)
    metadata_lines = ["# " + slide_id + " 页面生成 Prompt", "", "## Snapshot metadata"]
    metadata_lines.extend(
        f"- **{field}**：{_provenance_value_text(metadata[field])}"
        for field in METADATA_FIELD_ORDER
    )
    prefix = ("\n".join(metadata_lines) + "\n\n").encode("utf-8")
    envelope = prefix + COMPILED_PROMPT_SEPARATOR + body
    _, persisted_body = split_generation_prompt_envelope(envelope)
    if sha256_id(persisted_body) != sha256_id(body):
        raise ValueError("prompt_snapshot_conflict")
    return envelope


def _revision_edge_sort_key(edge: str) -> tuple[int, str]:
    earlier_id, field = edge.split(":", 1)
    return (_visual_revision_sort_key(earlier_id), field)


def project_active_visual_revisions(payload: dict) -> tuple[list[str], bytes]:
    """Return sorted provenance IDs and canonical projected JSON ending in one LF."""
    storyboard = payload.get("storyboard") or {}
    applied_ids = storyboard.get("applied_visual_revision_ids")
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

    mirrors = storyboard.get("applied_visual_revision_mirrors", {})
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


def _path_parts(value):
    return value.replace(chr(92), "/").split("/")


def _is_path_unsafe(value):
    if not isinstance(value, str) or not value:
        return True
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return True
    if value.startswith(("/", chr(92))):
        return True
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return True
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return True
    return any(
        part in ("", ".", "..") or ":" in part
        for part in _path_parts(value)
    )


def _is_semver(value):
    return isinstance(value, str) and re.fullmatch(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", value) is not None
