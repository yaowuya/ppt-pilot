"""Hard-constraint verification for a composed style pack."""

from __future__ import annotations

import json
import math
import os
import re
import stat
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
_STYLE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_NARRATIVE_TOKEN = "{{NARRATIVE}}"
_MUSTACHE_MARKER_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_BRACKET_MARKER_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
_SOURCE_ANNOTATION_RE = re.compile(
    r"(?:\bsource\s*=|\[claim\s*=|data-source-id|\bSRC-[0-9]+\b)",
    re.IGNORECASE,
)
_NON_LF_LINE_SEPARATOR_RE = re.compile(r"[\x0b\x0c\x1c-\x1e\x85\u2028\u2029]")
_LEGACY_STYLE_MARKER_RE = re.compile(
    r"\[\[\s*(?:CANONICAL_NARRATIVE_BULLETS|STYLE_BASELINE)\s*\]\]",
    re.IGNORECASE,
)
_TOKEN_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
_FONT_NAME_PUNCTUATION = frozenset(" -_")
_REPARSE_POINT_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_KNOWN_CJK_FONT_NAMES = {
    "宋体",
    "微软雅黑",
    "思源黑体",
    "等线",
    "苹方",
    "黑体",
}


def _is_safe_font_name(value: object) -> bool:
    """Accept brand fonts without allowing a font value to become prompt syntax."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= 64
        and value == value.strip()
        and (
            value in _KNOWN_CJK_FONT_NAMES
            or (
                value.isascii()
                and any(character.isalnum() for character in value)
                and all(
                    character.isalnum() or character in _FONT_NAME_PUNCTUATION
                    for character in value
                )
            )
        )
    )


def canonicalize_font_stack(value: object) -> tuple[list[str], bool]:
    """Return a non-executable font stack; unknown families use a safe fallback."""
    if (
        isinstance(value, list)
        and bool(value)
        and len(value) <= 8
        and all(_is_safe_font_name(font) for font in value)
    ):
        return list(value), False
    return ["Arial", "sans-serif"], True

_PALETTE_ROLE_LABELS = {
    "primary_emphasis": "主强调",
    "secondary_relationship": "次级关系",
    "secondary_surface": "次级表面",
    "risk_or_pilot": "风险或试点",
    "single_focus": "唯一焦点",
    "headline": "标题",
    "action_or_metric": "行动或指标",
    "page_canvas": "页面画布",
    "body_text": "正文文字",
    "hierarchy_boundary": "层级边界",
    "selected_state": "选中状态",
}

_PALETTE_USE_LABELS = {
    "highest_value_only": "仅用于最高价值结论、行动或选中状态",
    "secondary_relationship": "用于次级关系或过渡",
    "secondary_surface": "用于次级表面或分隔",
    "risk_or_pilot": "用于有界试点、风险或失败分支",
    "single_dark_card": "每页至多一张深色主卡",
    "title_or_key_emphasis": "用于标题或关键强调",
    "metric_or_action": "用于关键数据或行动强调",
    "page_canvas": "用于页面背景画布",
    "body_text": "用于页面标题或正文",
    "hierarchy_boundary": "用于层级边界或深色强调",
    "selected_state": "用于少量关键点或选中状态",
    "weak_emphasis": "用于卡片底或弱强调区",
}

_PROHIBITED_MOTIF_LABELS = {
    "background_image_or_texture": "背景图片或纹理",
    "bright_white_background": "亮白底",
    "cold_dashboard": "冷色数据大屏感",
    "color_only_semantics": "用颜色替代必要文字",
    "connector_through_text": "穿过文字的连接线",
    "decorative_lines": "无语义装饰线",
    "english_title_translation": "标题英文翻译",
    "equal_weight_card_wall": "等权卡片墙",
    "excessive_rounding": "过度圆角",
    "forced_metric_cards": "强行拆分成数据卡片",
    "frosted_glass": "毛玻璃",
    "gradient_background": "渐变背景",
    "high_saturation_blue_blocks": "大量高饱和蓝色块状元素",
    "high_saturation_multicolor": "高饱和多色块",
    "left_blue_bar": "左侧长蓝条",
    "light_saturated_blocks": "浅色高饱和多色块",
    "literal_page_conclusion": "页面结论四字",
    "no_data_labels": "无数据标注的图表",
    "plain_white_editorial_loss": "纯白无编辑感",
    "premature_acceptance_claim": "把阶段交付写成最终验收",
    "redundant_decoration": "多余装饰",
    "top_right_logo": "右上角 logo 或图标",
}

def _valid_percentage_range(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = re.fullmatch(
        r"(0|[1-9][0-9]?|100)%-(0|[1-9][0-9]?|100)%", value
    )
    return match is not None and int(match.group(1)) < int(match.group(2))


_COMPOSITION_VALUE_RULES = {
    "card_coverage": _valid_percentage_range,
    "layout_family": lambda value: value
    in {"asymmetric_modular", "content_driven", "balanced_editorial"},
    "max_shadowed_objects": lambda value: isinstance(value, int)
    and not isinstance(value, bool)
    and 0 <= value <= 1,
    "min_card_gap": lambda value: isinstance(value, (int, float))
    and not isinstance(value, bool)
    and 8 <= value <= 96,
    "no_english_title": lambda value: isinstance(value, bool),
    "no_top_right_logo": lambda value: isinstance(value, bool),
    "phrase_emphasis_allowed": lambda value: isinstance(value, bool),
    "primary_secondary_ratio": lambda value: isinstance(value, (int, float))
    and not isinstance(value, bool)
    and 1 <= value <= 4,
    "title_position": lambda value: value in {"top_left", "top_center"},
    "title_single_line_preferred": lambda value: isinstance(value, bool),
}

_TYPOGRAPHY_KEYS = {
    "body",
    "body_weight",
    "caption",
    "emphasis_weight",
    "font_stack",
    "label_weight",
    "micro_label",
    "module_label",
    "page_title",
    "primary_proposition",
    "section_title",
    "section_weight",
    "slide_title",
    "support",
    "title_weight",
}

_SPACING_KEYS = {
    "card_gap",
    "card_padding",
    "line_height",
    "outer_margin",
    "page_padding",
    "standard_gap",
}

_TOP_LEVEL_SPACING_KEYS = _SPACING_KEYS | {"compact_gap", "micro_gap"}

_SHAPE_KEYS = {
    "button_radius",
    "card_radius",
    "connector_width",
    "corner_radius",
    "module_radius",
    "primary_radius",
    "secondary_radius",
    "stroke_width",
}

_TOP_LEVEL_SHAPE_KEYS = _SHAPE_KEYS | {"shadow_offset"}

_TOKEN_ROOT_KEYS = {
    "schema_version",
    "id",
    "display_name",
    "font_resolution",
    "colors",
    "typography",
    "spacing",
    "shape",
    "composition",
    "prompt_baseline",
}

_PROMPT_HARD_PREFIX = """# Role: 高级信息架构师 & SVG 可视化编码专家

你的任务是基于已批准的叙事要点与内容素材，自主设计一页逻辑清晰、视觉美观、可直接用于演示文稿的 Office-safe SVG。

## Workflow: 执行步骤

### 步骤 1: 组织叙事与内容 (Narrative and Content)

不得重新选择叙事逻辑。严格按照下列已批准叙事组织信息：
{{NARRATIVE}}

内容处理边界：
- 允许对已注入素材进行提纯、改写、重排与展开，但不得增加注入文本中没有的新事实性主张；仅无事实内容的过渡句可自由撰写。
- 不得改变数字、单位、期间、限定词（待确认、待验收等）或因果关系。
- 不得把推断或新增内容冒充为已批准事实；来源映射由 coordinator 单独处理。

### 步骤 2: 应用风格基线并设计视觉表达 (Style Baseline and Visual Design)

以下风格约定已在创建风格包时从提取证据静态物化。它们是软参考方向，不是逐项锁定令牌；在保持整套演示文稿风格一致性的前提下，布局、层级、卡片组织、信息密度、配色用法与装饰由你自主决定。

"""

_PROMPT_HARD_SUFFIX = """

### 步骤 3: 编码 SVG（输出硬契约）

- **画布**: 根元素必须使用 `<svg viewBox="0 0 1280 720">`。
- **安全区与节奏**: 所有可见内容位于 64px 安全区内；间距使用 24px 节奏。
- **圆角卡片**: 仅使用 `<path>` 与 SVG 弧线命令 `A` 绘制圆角卡片；禁止为 `<rect>` 添加 `rx` 或 `ry`。
- **文本**: 每个文本对象使用显式 `<text>`；每一行使用简单、非嵌套的 `<tspan>`，并保证文本不越界；文字保持为文字，不转轮廓。
- **字号**: 正文 ≥20px，次级说明 ≥14px；关键数字可用大字号或强调色突出，全页至多一个主强调焦点。
- **Office-safe 子集**: 仅使用 `svg`、`g`、`path`、`rect`（仅直角）、`circle`、`line`、`polyline`、`polygon`、`text`、`tspan`、`title`、`desc`；禁止 `foreignObject`、脚本、远程资源、滤镜、渐变、动画、`defs`、`use`、`clipPath`、`mask`、`image`。
- **根节点**: 包含 `<title>`（本页结论）与 `<desc>`（视觉关系）。
- **内容块追踪**: 注入叙事中的每个 `block_id` 必须在承载对应语义内容的唯一 `<g data-block-id="...">` 上原样回显；`block_id` 只可临时作为该精确属性值，不得出现在 `<text>`／`<tspan>`、任何节点的 text／tail 或其他属性中；不得自行添加来源属性。该临时属性由 coordinator 在候选写入前完成来源关联后移除。
- **可见来源禁令**: 不得在可见 `<text>`／`<tspan>` 中输出来源、引用、URL 或内部来源标识；仅 coordinator 可在候选写入前添加机器 trace。

### 兼容约束

SVG 必须在 PowerPoint、Word 等 Office 软件中保持几何、文本和颜色稳定。所有图形、字体栈、颜色与文字内容必须自包含，不依赖外部文件、URL 或工具调用。

---

只返回一个 ```xml 代码围栏，围栏内必须是完整 SVG；围栏外不得输出解释、Markdown 标题或其它文本。
"""

_STYLE_DIRECTIVE_PREFIXES = (
    "- 色彩角色：",
    "- 字体栈：",
    "- 字号层级：",
    "- 间距节奏：",
    "- 形状语言：",
    "- 构图规则：",
    "- 禁止母题：",
)

def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise VerificationError(reason)


def _is_semver(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(
        re.fullmatch(
            r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)",
            value,
        )
    )


def verify_manifest_schema(manifest: dict) -> None:
    """Schema-only manifest verification (no file-existence check)."""
    _require(manifest.get("schema_version") == 1, "manifest_schema_unsupported")
    style_id = manifest.get("id")
    _require(
        isinstance(style_id, str) and _STYLE_ID_RE.fullmatch(style_id) is not None,
        "manifest_identity_mismatch",
    )
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


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT_FLAG
    )


def _absolute_without_following(path: Path) -> Path:
    """Make a path absolute without resolving links or reparse points."""
    return Path(os.path.abspath(os.fspath(path)))


def _validate_pack_root_no_follow(pack_root: Path) -> Path:
    """Reject link/reparse traversal in every existing pack-root component."""
    absolute = _absolute_without_following(pack_root)
    anchor = Path(absolute.anchor)
    current = anchor
    relative_parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    final_metadata = None
    for part in relative_parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            raise VerificationError("manifest_missing") from None
        except OSError:
            raise VerificationError("style_pack_path_unsafe") from None
        _require(not _is_link_or_reparse(metadata), "style_pack_path_unsafe")
        _require(stat.S_ISDIR(metadata.st_mode), "style_pack_path_unsafe")
        final_metadata = metadata
    _require(final_metadata is not None, "style_pack_path_unsafe")
    return absolute


def _read_text_no_follow(path: Path, missing_reason: str) -> str:
    """Read one regular file after lstat, never intentionally following a link."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise VerificationError(missing_reason) from None
    except OSError:
        raise VerificationError("style_pack_path_unsafe") from None
    _require(not _is_link_or_reparse(before), "style_pack_path_unsafe")
    _require(stat.S_ISREG(before.st_mode), missing_reason)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        raise VerificationError(missing_reason) from None
    except OSError:
        raise VerificationError("style_pack_path_unsafe") from None
    try:
        after = os.fstat(descriptor)
        _require(stat.S_ISREG(after.st_mode), missing_reason)
        _require(
            (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino),
            "style_pack_path_unsafe",
        )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read()
    finally:
        os.close(descriptor)
    return payload.decode("utf-8")


def verify_manifest(manifest: dict, pack_root: Path) -> None:
    verify_manifest_schema(manifest)
    safe_root = _validate_pack_root_no_follow(pack_root)
    # File existence is only meaningful against a real on-disk pack root. Use
    # lstat rather than resolve()/is_file(), which would follow a link first.
    for name in _REQUIRED_MANIFEST_FILES.values():
        _read_text_no_follow(safe_root / name, f"manifest_missing_asset:{name}")


def verify_tokens(tokens: dict) -> None:
    _require(isinstance(tokens, dict), "tokens_schema_invalid")
    _require(
        set(tokens).issubset(_TOKEN_ROOT_KEYS)
        and (_TOKEN_ROOT_KEYS - {"font_resolution"}).issubset(tokens),
        "tokens_schema_invalid",
    )
    _require(tokens.get("schema_version") == 2, "tokens_schema_invalid")
    _require(
        isinstance(tokens.get("id"), str)
        and _STYLE_ID_RE.fullmatch(tokens["id"]) is not None
        and isinstance(tokens.get("display_name"), str)
        and 0 < len(tokens["display_name"]) <= 128,
        "tokens_schema_invalid",
    )
    for key in ("colors", "typography", "spacing", "shape", "composition"):
        _require(isinstance(tokens.get(key), dict), f"tokens_missing_section:{key}")
    if "font_resolution" in tokens:
        _require(
            isinstance(tokens["font_resolution"], dict)
            and tokens["font_resolution"].keys() == {"fallback_applied"}
            and isinstance(tokens["font_resolution"]["fallback_applied"], bool),
            "tokens_font_resolution_invalid",
        )
    baseline = tokens.get("prompt_baseline")
    _require(isinstance(baseline, dict), "tokens_prompt_baseline_invalid")
    _require(
        list(baseline) == _BASELINE_KEYS,
        "tokens_prompt_baseline_columns_invalid",
    )
    colors = tokens["colors"]
    _require(isinstance(colors, dict) and bool(colors), "tokens_colors_invalid")
    for token, value in colors.items():
        _require(
            isinstance(token, str)
            and _TOKEN_KEY_RE.fullmatch(token) is not None
            and isinstance(value, str)
            and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is not None,
            "tokens_colors_invalid",
        )
    roles = baseline.get("palette_roles", [])
    _require(
        isinstance(roles, list) and 0 < len(roles) <= 12,
        "tokens_palette_roles_invalid",
    )
    role_tokens = []
    for role in roles:
        _require(
            isinstance(role, dict)
            and set(role) == {"token", "role", "use"},
            "tokens_palette_roles_invalid",
        )
        token = role.get("token")
        role_tokens.append(token)
        _require(token in colors, "tokens_palette_role_not_in_colors")
        _require(
            role.get("role") in _PALETTE_ROLE_LABELS
            and role.get("use") in _PALETTE_USE_LABELS,
            "tokens_palette_roles_invalid",
        )
    _require(len(role_tokens) == len(set(role_tokens)), "tokens_palette_roles_invalid")

    font_stack = baseline.get("font_stack")
    _require(
        isinstance(font_stack, list)
        and bool(font_stack)
        and len(font_stack) <= 8
        and all(
            _is_safe_font_name(font) for font in font_stack
        )
        and tokens["typography"].get("font_stack") == font_stack
        and isinstance(baseline.get("prohibited_motifs"), list),
        "tokens_prompt_baseline_invalid",
    )
    _verify_numeric_mapping(
        tokens["typography"],
        _TYPOGRAPHY_KEYS,
        allow_font_stack=True,
        typography=True,
    )
    typography = tokens["typography"]
    _require(
        "body" in typography
        and any(key in typography for key in ("slide_title", "page_title"))
        and any(
            key in typography
            for key in ("support", "caption", "micro_label", "module_label")
        ),
        "tokens_typography_invalid",
    )

    spacing = baseline["spacing_rhythm"]
    shape = baseline["shape_language"]
    _verify_numeric_mapping(spacing, _SPACING_KEYS)
    _verify_numeric_mapping(shape, _SHAPE_KEYS)
    _verify_numeric_mapping(tokens["spacing"], _TOP_LEVEL_SPACING_KEYS)
    _verify_numeric_mapping(tokens["shape"], _TOP_LEVEL_SHAPE_KEYS)
    _require(
        spacing.get("outer_margin") == 64
        and spacing.get("standard_gap") == 24
        and all(value > 0 for value in spacing.values()),
        "tokens_spacing_invalid",
    )
    radius_keys = {
        "button_radius",
        "card_radius",
        "corner_radius",
        "module_radius",
        "primary_radius",
        "secondary_radius",
    }
    _require(
        "stroke_width" in shape
        and shape["stroke_width"] > 0
        and any(key in shape and shape[key] > 0 for key in radius_keys)
        and all(value > 0 for value in shape.values()),
        "tokens_shape_invalid",
    )
    _require(
        all(tokens["spacing"].get(key) == value for key, value in spacing.items())
        and all(tokens["shape"].get(key) == value for key, value in shape.items()),
        "tokens_prompt_baseline_invalid",
    )

    composition = baseline["composition_rules"]
    _require(
        isinstance(composition, dict) and bool(composition),
        "tokens_composition_rules_invalid",
    )
    for key, value in composition.items():
        rule = _COMPOSITION_VALUE_RULES.get(key)
        _require(rule is not None and bool(rule(value)), "tokens_composition_rules_invalid")
    _require(tokens["composition"] == composition, "tokens_composition_rules_invalid")

    prohibited = baseline["prohibited_motifs"]
    _require(
        bool(prohibited)
        and len(prohibited) == len(set(prohibited))
        and all(item in _PROHIBITED_MOTIF_LABELS for item in prohibited),
        "tokens_prohibited_motifs_invalid",
    )


def _verify_numeric_mapping(
    values: object,
    allowed_keys: set[str],
    allow_font_stack: bool = False,
    typography: bool = False,
) -> None:
    _require(
        isinstance(values, dict) and len(values) <= 20,
        "tokens_prompt_data_invalid",
    )
    for key, value in values.items():
        _require(
            isinstance(key, str)
            and _TOKEN_KEY_RE.fullmatch(key) is not None
            and key in allowed_keys,
            "tokens_prompt_data_invalid",
        )
        if allow_font_stack and key == "font_stack":
            continue
        _require(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 4096,
            "tokens_prompt_data_invalid",
        )
        if typography:
            if key.endswith("weight"):
                _require(100 <= value <= 900, "tokens_typography_invalid")
            elif key == "body":
                _require(value >= 20, "tokens_typography_invalid")
            elif key in {"caption", "micro_label", "module_label", "support"}:
                _require(value >= 14, "tokens_typography_invalid")
            elif "title" in key or key == "primary_proposition":
                _require(value >= 20, "tokens_typography_invalid")


def _render_mapping(values: dict) -> str:
    return "；".join(
        f"{key}={json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
        for key, value in sorted(values.items())
    )


def render_prompt_style_directives(tokens: dict) -> str:
    """Render the canonical authoring-time style block embedded in prompt.md."""
    baseline = tokens["prompt_baseline"]
    colors = tokens["colors"]
    palette = []
    for role in baseline["palette_roles"]:
        token = role["token"]
        palette.append(
            f"{token}={colors[token]}（{_PALETTE_ROLE_LABELS[role['role']]}；"
            f"{_PALETTE_USE_LABELS[role['use']]}）"
        )
    lines = [
            f"- 色彩角色：{'；'.join(palette)}",
            f"- 字体栈：{' / '.join(baseline['font_stack'])}",
            f"- 字号层级：{_render_mapping(tokens['typography'])}",
            f"- 间距节奏：{_render_mapping(baseline['spacing_rhythm'])}",
            f"- 形状语言：{_render_mapping(baseline['shape_language'])}",
            f"- 构图规则：{_render_mapping(baseline['composition_rules'])}",
            f"- 禁止母题：{'；'.join(_PROHIBITED_MOTIF_LABELS[item] for item in baseline['prohibited_motifs'])}",
    ]
    return "\n".join(lines)


def compose_prompt(tokens: dict) -> str:
    return (
        _PROMPT_HARD_PREFIX
        + render_prompt_style_directives(tokens)
        + _PROMPT_HARD_SUFFIX
    )


def verify_prompt_style_binding(tokens: dict, prompt: str) -> None:
    if prompt.startswith("\ufeff"):
        prompt = prompt[1:]
    prompt = prompt.replace("\r\n", "\n").replace("\r", "\n")
    _require(
        prompt == compose_prompt(tokens),
        "prompt_style_binding_mismatch",
    )


def verify_prompt(prompt: str) -> None:
    if prompt.startswith("\ufeff"):
        prompt = prompt[1:]
    _require("\ufeff" not in prompt, "prompt_template_invalid")
    _require(_NON_LF_LINE_SEPARATOR_RE.search(prompt) is None, "prompt_template_invalid")
    normalized = prompt.replace("\r\n", "\n").replace("\r", "\n")
    mustache_markers = _MUSTACHE_MARKER_RE.findall(normalized)
    _require(mustache_markers == [_NARRATIVE_TOKEN], "prompt_template_invalid")
    _require(
        normalized.count(_NARRATIVE_TOKEN) == 1
        and normalized.split("\n").count(_NARRATIVE_TOKEN) == 1,
        "prompt_template_invalid",
    )
    prompt_without_narrative = normalized.replace(_NARRATIVE_TOKEN, "", 1)
    _require(
        "{{" not in prompt_without_narrative and "}}" not in prompt_without_narrative,
        "prompt_template_invalid",
    )
    _require(_SOURCE_ANNOTATION_RE.search(normalized) is None, "prompt_forbidden_token")
    _require(
        _BRACKET_MARKER_RE.search(normalized) is None
        and "[[" not in normalized
        and "]]" not in normalized,
        "prompt_legacy_marker",
    )
    lines = normalized.split("\n")
    heading_positions = []
    for heading in _REQUIRED_PROMPT_HEADINGS:
        matches = [
            index
            for index, line in enumerate(lines)
            if line == heading
            or (
                line.startswith(heading)
                and line[len(heading) : len(heading) + 1] in (":", "：", " ", "\t", "(", "（")
            )
        ]
        _require(len(matches) == 1, f"prompt_missing_heading:{heading}")
        heading_positions.append(matches[0])
    _require(
        heading_positions == sorted(heading_positions) and heading_positions[0] == 0,
        "prompt_template_invalid",
    )
    _require("data-block-id" in normalized, "prompt_template_invalid")
    _require(
        normalized.startswith(_PROMPT_HARD_PREFIX)
        and normalized.endswith(_PROMPT_HARD_SUFFIX),
        "prompt_template_invalid",
    )
    style_section = normalized[
        len(_PROMPT_HARD_PREFIX) : len(normalized) - len(_PROMPT_HARD_SUFFIX)
    ]
    style_lines = style_section.split("\n")
    _require(
        all(sum(line.startswith(prefix) for line in style_lines) == 1 for prefix in _STYLE_DIRECTIVE_PREFIXES)
        and all(line.startswith(_STYLE_DIRECTIVE_PREFIXES) for line in style_lines),
        "prompt_template_invalid",
    )


def verify_rules(rules: str) -> None:
    for forbidden in (
        "REDESIGN.md",
        ".redesign.md",
        "完整生成 prompt",
        "完整 prompt",
        "可执行 prompt",
        "reference.svg",
        "参考 svg",
        "generation-prompt-template.md",
    ):
        _require(forbidden not in rules, "rules_forbidden_token")
    _require(_LEGACY_STYLE_MARKER_RE.search(rules) is None, "rules_forbidden_token")
    for line in rules.splitlines():
        folded = line.casefold()
        has_runtime = "runtime" in folded or "运行时" in line
        has_fallback = (
            "fallback" in folded or "回退" in line or "兜底" in line
        )
        has_repository_template = (
            ("repository" in folded or "仓库" in line)
            and ("template" in folded or "模板" in line)
        )
        _require(
            not (has_runtime and has_fallback and has_repository_template),
            "rules_forbidden_token",
        )
    _require(len(_CJK_RE.findall(rules)) >= 80, "rules_insufficient_chinese")


def verify_composed(manifest: dict, tokens: dict, prompt: str, rules: str) -> None:
    """Verify in-memory payloads against every hard constraint before any
    durable write. This is the authoritative pre-write gate."""
    verify_manifest_schema(manifest)
    verify_tokens(tokens)
    _require(manifest.get("id") == tokens.get("id"), "style_identity_mismatch")
    verify_prompt(prompt)
    verify_prompt_style_binding(tokens, prompt)
    verify_rules(rules)


def verify_style_pack(pack_root: Path) -> None:
    """Verify an on-disk style pack against every hard constraint (post-write
    integrity check; the pre-write authority is verify_composed)."""
    safe_root = _validate_pack_root_no_follow(pack_root)

    # Traversal order is part of the contract. Do not stat/read a later asset
    # until the current stage has passed completely.
    manifest = json.loads(
        _read_text_no_follow(safe_root / "manifest.json", "manifest_missing")
    )
    verify_manifest_schema(manifest)

    tokens = json.loads(
        _read_text_no_follow(
            safe_root / _REQUIRED_MANIFEST_FILES["tokens"],
            "manifest_missing_asset:tokens.json",
        )
    )
    verify_tokens(tokens)
    _require(manifest.get("id") == tokens.get("id"), "style_identity_mismatch")

    rules = _read_text_no_follow(
        safe_root / _REQUIRED_MANIFEST_FILES["guidance"],
        "manifest_missing_asset:STYLE.md",
    )
    verify_rules(rules)

    prompt = _read_text_no_follow(
        safe_root / _REQUIRED_MANIFEST_FILES["prompt_template"],
        "manifest_missing_asset:prompt.md",
    )
    verify_prompt(prompt)
    verify_prompt_style_binding(tokens, prompt)
