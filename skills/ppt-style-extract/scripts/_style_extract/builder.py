"""Compose a compliant style pack from extractor output and write it."""

from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from uuid import uuid4

from .errors import PptStyleExtractError
from .verify import (
    canonicalize_font_stack,
    compose_prompt,
    verify_composed,
    verify_style_pack,
)
from .registry import prepare_registry_update, update_registry_idempotent


def _slug(style_id: str) -> None:
    if not isinstance(style_id, str) or not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", style_id
    ):
        raise PptStyleExtractError("style_id_invalid")


def _compose_manifest(style_id: str, display_name: str, version: str) -> dict:
    return {
        "schema_version": 1,
        "id": style_id,
        "display_name": display_name,
        "version": version,
        "kind": "style_pack",
        "default": False,
        "summary": f"用户从输入提取并固化的风格包：{display_name}。",
        "recommended_for": ["自定义风格复用", "品牌一致性演示"],
        "not_for": ["营销海报"],
        "selection_aliases": [style_id, display_name],
        "files": {
            "tokens": "tokens.json",
            "guidance": "STYLE.md",
            "prompt_template": "prompt.md",
        },
        "compatibility": {"office_safe_svg": True, "canvas": "1280x720", "languages": ["zh-CN", "en"]},
    }


def _bounded_number(value: object, default: float, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and minimum <= value <= maximum
    ):
        return value
    return default


def _compose_tokens(style_id: str, display_name: str, extract: dict, semantic: dict | None) -> dict:
    colors = extract.get("colors", {})
    palette = colors.get("accent_palette", []) or []
    primary = colors.get("brand_primary") or (palette[0] if palette else "#156BFF")
    secondary = palette[1] if len(palette) > 1 else _shade(primary)

    typography = extract.get("typography", {})
    if not isinstance(typography, dict):
        typography = {}
    font_stack, font_fallback_applied = canonicalize_font_stack(
        typography.get("font_stack", ["Arial", "sans-serif"])
    )
    shape = extract.get("shape", {})
    if not isinstance(shape, dict):
        shape = {}
    primary_radius = _bounded_number(shape.get("primary_radius"), 20.0, 1, 128)
    stroke_width = _bounded_number(shape.get("stroke_width"), 1.2, 0.1, 16)

    composition_rules = dict(semantic.get("composition_rules", {})) if semantic else {}
    composition_rules.setdefault("card_coverage", "40%-60%")
    composition_rules.setdefault("primary_secondary_ratio", 1.5)
    composition_rules.setdefault("max_shadowed_objects", 1)

    prohibited = list(semantic.get("prohibited_motifs", [])) if semantic else []
    prohibited = prohibited or ["decorative_lines", "color_only_semantics"]

    baseline = {
        "palette_roles": [
            {
                "token": "brand_primary",
                "role": "primary_emphasis",
                "use": "highest_value_only",
            },
            {
                "token": "brand_secondary",
                "role": "secondary_relationship",
                "use": "secondary_relationship",
            },
            {
                "token": "canvas",
                "role": "page_canvas",
                "use": "page_canvas",
            },
        ],
        "font_stack": font_stack,
        "spacing_rhythm": {
            "outer_margin": 64,
            "standard_gap": 24,
            "card_gap": 20,
            "card_padding": 24,
        },
        "shape_language": {
            "primary_radius": primary_radius,
            "secondary_radius": max(round(primary_radius * 0.7, 0), 8),
            "stroke_width": stroke_width,
            "connector_width": 2,
        },
        "composition_rules": composition_rules,
        "prohibited_motifs": prohibited,
    }
    # palette role tokens must live in colors
    colors = dict(colors)
    colors["brand_primary"] = primary
    colors["brand_secondary"] = secondary
    colors.setdefault("canvas", "#FFFFFF")
    colors.setdefault("ink", "#0B1930")
    colors.setdefault("text_secondary", "#52637B")
    colors.setdefault("border", "#DCE9F8")
    for key in ("accent_palette", "hero_dark", "sky", "ai_pilot", "fact_surface", "evidence_surface", "pilot_surface", "title_accent"):
        colors.pop(key, None)

    return {
        "schema_version": 2,
        "id": style_id,
        "display_name": display_name,
        "font_resolution": {"fallback_applied": font_fallback_applied},
        "colors": colors,
        "typography": {
            "font_stack": font_stack,
            "slide_title": max(typography.get("slide_title", 40), 20),
            "primary_proposition": max(
                typography.get("primary_proposition", 30), 20
            ),
            "section_title": max(typography.get("section_title", 24), 20),
            "body": max(typography.get("body", 20), 20),
            "support": max(typography.get("support", 16), 14),
            "micro_label": max(typography.get("micro_label", 14), 14),
            "title_weight": 700,
            "emphasis_weight": 700,
            "body_weight": 400,
        },
        "spacing": {
            "outer_margin": 64,
            "standard_gap": 24,
            "card_gap": 20,
            "compact_gap": 16,
            "micro_gap": 8,
            "card_padding": 24,
        },
        "shape": {
            "primary_radius": primary_radius,
            "secondary_radius": baseline["shape_language"]["secondary_radius"],
            "stroke_width": stroke_width,
            "connector_width": 2,
            "shadow_offset": 6,
        },
        "composition": composition_rules,
        "prompt_baseline": baseline,
    }


def _shade(hex_color: str) -> str:
    try:
        r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#65B7F9"
    # lighten toward white by 35%
    r, g, b = (c + int((255 - c) * 0.35) for c in (r, g, b))
    return "#%02X%02X%02X" % (r, g, b)


def _compose_style_md(style_id: str, display_name: str, extract: dict, semantic: dict | None) -> str:
    palette = extract.get("colors", {}).get("accent_palette", []) or []
    primary = extract.get("colors", {}).get("brand_primary") or (palette[0] if palette else "#156BFF")
    rules = (
        f"# {display_name}\n\n"
        f"## 使用场景\n\n"
        f"这是一套由用户输入提取并固化的风格包。它用于复用一致的品牌视觉表达，默认画布为纯白 "
        f"`#FFFFFF`，品牌主色 `{primary}` 用于最高价值结论、行动或选中状态。\n\n"
        f"## 核心识别\n\n"
        f"结论标题单行、可判断。主要命题用品牌色短语级强调，不能把整行标题染成强调色。背景不使用图片、纹理或渐变。\n\n"
        f"## 语义表面\n\n"
        f"- 白色事实卡承载已观察事实、已验证状态与来源可追溯内容。\n"
        f"- 强调表面承载证据边界、核心结论或需集中阅读的限定信息。\n"
        f"- 颜色与文字标签同时表达语义，不能仅靠颜色区分事实、假设或风险。\n\n"
        f"## 内容驱动构图\n\n"
        f"必须根据内容选择构图，而不是机械重复一个模板；卡片数量由内容语义决定，不追求填满画布。"
        f"同一套演示共享颜色、字体、间距与形状令牌，但每页构图必须响应其论证、流程、时间、比较或决策语义。\n\n"
        f"## 禁止项\n\n"
        f"禁止：\n\n"
        f"- 背景图片、纹理、渐变和远程资源；\n"
        f"- 等权卡片墙、全页阴影或每张卡片相同视觉权重；\n"
        f"- 无语义装饰线、穿过文字的连接线或暗示错误关系的箭头；\n"
        f"- 把观察、相关性、假设或提案渲染成已证实因果；\n"
        f"- 用颜色替代必要文字。\n\n"
        f"## 身份、令牌与指导\n\n"
        f"本文件与 `tokens.json` 共同定义本风格的身份、令牌与指导；二者不是 rendered exemplar、固定布局"
        f"或可直接复制的页面范本，也不拥有页面生成正文。本风格包不得包含单页成品示例、参考构图或固定区域图；"
        f"每页结构由 isolated generator 从当前故事板的内容语义与 `theme.json` 软风格基线重新推导。"
        f"不得从成品示例或既有 SVG 反推构图。\n"
    )
    return rules


def compose_style_pack(style_id: str, display_name: str, version: str, extract: dict, semantic: dict | None) -> dict:
    """Return the four text payloads keyed by filename."""
    _slug(style_id)
    manifest = _compose_manifest(style_id, display_name, version)
    tokens = _compose_tokens(style_id, display_name, extract, semantic)
    prompt = compose_prompt(tokens)
    rules = _compose_style_md(style_id, display_name, extract, semantic)
    return {
        "manifest": manifest,
        "tokens": tokens,
        "prompt": prompt,
        "STYLE.md": rules,
    }


def write_style_pack(
    pack: dict,
    out_root: Path,
    registry_path: Path,
) -> dict:
    """Stage and verify a pack, then commit pack and registry as one transaction."""
    style_id = pack["manifest"]["id"]
    # Defense in depth: callers can mutate a composed dict before write, so the
    # write boundary must revalidate identity and containment before any I/O.
    _slug(style_id)
    resolved_out_root = out_root.resolve()
    pack_dir = (out_root / style_id).resolve()
    if not pack_dir.is_relative_to(resolved_out_root):
        raise PptStyleExtractError("style_id_invalid")

    # Pre-write hard gate: verify composed payloads BEFORE any durable write.
    verify_composed(pack["manifest"], pack["tokens"], pack["prompt"], pack["STYLE.md"])

    # Registry uniqueness/schema errors are preflight failures: they must not
    # create or alter a pack directory.
    prepare_registry_update(registry_path, pack["manifest"])

    expected_files = {
        "manifest.json": json.dumps(
            pack["manifest"], ensure_ascii=False, indent=2
        ).encode("utf-8")
        + b"\n",
        "tokens.json": json.dumps(
            pack["tokens"], ensure_ascii=False, indent=2
        ).encode("utf-8")
        + b"\n",
        "prompt.md": pack["prompt"].encode("utf-8"),
        "STYLE.md": pack["STYLE.md"].encode("utf-8"),
    }

    # Published pack IDs are immutable. A byte-identical orphan left by a
    # crash can be adopted by the pointer-last registry commit; any differing
    # payload must use a new style ID.
    if pack_dir.exists():
        verify_style_pack(pack_dir)
        actual_names = {path.name for path in pack_dir.iterdir() if path.is_file()}
        if actual_names != set(expected_files) or any(
            (pack_dir / name).read_bytes() != expected
            for name, expected in expected_files.items()
        ):
            raise PptStyleExtractError("style_pack_immutable_conflict")
        count = update_registry_idempotent(registry_path, pack["manifest"])
        return {
            "result": "PASS",
            "style_id": style_id,
            "output_dir": str(pack_dir),
            "registry_entries": count,
            "note": "风格包已固化并注册；在 ppt-start 中可用 style id 或显示名选择。",
        }

    out_root.mkdir(parents=True, exist_ok=True)
    transaction_id = uuid4().hex
    staging_dir = out_root / f".{style_id}.staging-{transaction_id}"
    staging_dir.mkdir()
    committed_pack = False
    try:
        for name, content in expected_files.items():
            (staging_dir / name).write_bytes(content)
        verify_style_pack(staging_dir)

        try:
            staging_dir.replace(pack_dir)
            committed_pack = True
            count = update_registry_idempotent(registry_path, pack["manifest"])
        except Exception:
            if committed_pack and pack_dir.exists():
                shutil.rmtree(pack_dir)
            raise
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "result": "PASS",
        "style_id": style_id,
        "output_dir": str(pack_dir),
        "registry_entries": count,
        "note": "风格包已固化并注册；在 ppt-start 中可用 style id 或显示名选择。",
    }
