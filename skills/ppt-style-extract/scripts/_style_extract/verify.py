"""Hard-constraint verification for a composed style pack."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import VerificationError

_BASELINE_KEYS = [
    "palette_roles",
    "font_stack",
    "spacing_rhythm",
    "shape_language",
    "composition_rules",
    "prohibited_motifs",
]

_REQUIRED_PROMPT_HEADINGS = [
    "# Role",
    "## Workflow",
    "### 步骤 1",
    "### 步骤 2",
    "### 步骤 3",
    "### 兼容约束",
]

_REQUIRED_MANIFEST_FILES = {
    "tokens": "tokens.json",
    "guidance": "STYLE.md",
    "prompt_template": "prompt.md",
}

_CJK_RE = re.compile(r"[㐀-鿿]")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise VerificationError(reason)


def _is_semver(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", value))


def verify_manifest_schema(manifest: dict) -> None:
    """Schema-only manifest verification (no file-existence check)."""
    _require(manifest.get("schema_version") == 1, "manifest_schema_unsupported")
    style_id = manifest.get("id")
    _require(isinstance(style_id, str) and style_id, "manifest_identity_mismatch")
    aliases = manifest.get("selection_aliases", [])
    _require(
        isinstance(aliases, list) and style_id in aliases,
        "manifest_identity_mismatch",
    )
    _require(manifest.get("kind") == "style_pack", "manifest_kind_invalid")
    _require(manifest.get("files") == _REQUIRED_MANIFEST_FILES, "manifest_files_invalid")
    _require(_is_semver(manifest.get("version")), "manifest_version_invalid")
    compat = manifest.get("compatibility", {})
    _require(compat.get("office_safe_svg") is True, "manifest_office_safe_invalid")


def verify_manifest(manifest: dict, pack_root: Path) -> None:
    verify_manifest_schema(manifest)
    # File existence is only meaningful against a real on-disk pack root.
    for name in _REQUIRED_MANIFEST_FILES.values():
        target = (pack_root / name).resolve()
        _require(target.is_relative_to(pack_root.resolve()), "manifest_path_escape")
        _require(target.is_file(), f"manifest_missing_asset:{name}")


def verify_tokens(tokens: dict) -> None:
    _require(tokens.get("schema_version") == 2, "tokens_schema_invalid")
    for key in ("colors", "typography", "spacing", "shape", "composition"):
        _require(key in tokens, f"tokens_missing_section:{key}")
    baseline = tokens.get("prompt_baseline")
    _require(isinstance(baseline, dict), "tokens_prompt_baseline_invalid")
    _require(
        list(baseline) == _BASELINE_KEYS,
        "tokens_prompt_baseline_columns_invalid",
    )
    colors = tokens["colors"]
    roles = baseline.get("palette_roles", [])
    _require(isinstance(roles, list) and roles, "tokens_palette_roles_invalid")
    for role in roles:
        token = role.get("token")
        _require(token in colors, "tokens_palette_role_not_in_colors")


def verify_prompt(prompt: str) -> None:
    _require(prompt.count("{{NARRATIVE}}") == 1, "prompt_template_invalid")
    for forbidden in (
        "[[CANONICAL_NARRATIVE_BULLETS]]",
        "[[STYLE_BASELINE]]",
        "source=",
    ):
        _require(forbidden not in prompt, "prompt_forbidden_token")
    for heading in _REQUIRED_PROMPT_HEADINGS:
        _require(heading in prompt, f"prompt_missing_heading:{heading}")
    _require("[[EFFECTIVE_PAGE_SPECIFICATION]]" not in prompt, "prompt_legacy_marker")


def verify_rules(rules: str) -> None:
    for forbidden in (
        "REDESIGN.md",
        ".redesign.md",
        "完整生成 prompt",
        "完整 prompt",
        "可执行 prompt",
        "reference.svg",
        "参考 svg",
    ):
        _require(forbidden not in rules, "rules_forbidden_token")
    _require(len(_CJK_RE.findall(rules)) >= 80, "rules_insufficient_chinese")


def verify_composed(manifest: dict, tokens: dict, prompt: str, rules: str) -> None:
    """Verify in-memory payloads against every hard constraint before any
    durable write. This is the authoritative pre-write gate."""
    verify_manifest_schema(manifest)
    verify_tokens(tokens)
    verify_prompt(prompt)
    verify_rules(rules)


def verify_style_pack(pack_root: Path) -> None:
    """Verify an on-disk style pack against every hard constraint (post-write
    integrity check; the pre-write authority is verify_composed)."""
    manifest_path = pack_root / "manifest.json"
    _require(manifest_path.is_file(), "manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_manifest(manifest, pack_root)
    tokens_path = pack_root / "tokens.json"
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    verify_tokens(tokens)
    prompt_path = pack_root / "prompt.md"
    verify_prompt(prompt_path.read_text(encoding="utf-8"))
    rules_path = pack_root / "STYLE.md"
    verify_rules(rules_path.read_text(encoding="utf-8"))
