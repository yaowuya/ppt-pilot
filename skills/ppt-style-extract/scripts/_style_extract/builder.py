"""Compose a compliant style pack from extractor output and write it."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import PptStyleExtractError
from .verify import verify_composed, verify_style_pack
from .registry import update_registry_idempotent


def _slug(style_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", style_id):
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


def _compose_tokens(style_id: str, display_name: str, extract: dict, semantic: dict | None) -> dict:
    colors = extract.get("colors", {})
    palette = colors.get("accent_palette", []) or []
    primary = colors.get("brand_primary") or (palette[0] if palette else "#156BFF")
    secondary = palette[1] if len(palette) > 1 else _shade(primary)

    typography = extract.get("typography", {})
    font_stack = typography.get("font_stack", ["Arial", "sans-serif"])
    spacing = extract.get("spacing", {"outer_margin": 64, "standard_gap": 24})
    shape = extract.get("shape", {"primary_radius": 20.0, "stroke_width": 1.2})

    composition_rules = dict(semantic.get("composition_rules", {})) if semantic else {}
    composition_rules.setdefault("card_coverage", "40%-60%")
    composition_rules.setdefault("primary_secondary_ratio", 1.5)
    composition_rules.setdefault("max_shadowed_objects", 1)

    prohibited = list(semantic.get("prohibited_motifs", [])) if semantic else []
    prohibited = prohibited or ["无语义装饰线", "用颜色替代必要文字"]

    baseline = {
        "palette_roles": [
            {"token": "brand_primary", "role": "结论强调", "use": "仅用于最高价值结论、行动或选中状态"},
            {"token": "brand_secondary", "role": "次级关系", "use": "用于次级关系或过渡"},
            {"token": "canvas", "role": "背景画布", "use": "每页默认为画布色"},
        ],
        "font_stack": font_stack,
        "spacing_rhythm": {
            "outer_margin": spacing.get("outer_margin", 64),
            "standard_gap": spacing.get("standard_gap", 24),
            "card_gap": 20,
            "card_padding": 24,
        },
        "shape_language": {
            "primary_radius": shape.get("primary_radius", 20.0),
            "secondary_radius": max(round(shape.get("primary_radius", 20.0) * 0.7, 0), 8),
            "stroke_width": shape.get("stroke_width", 1.2),
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
        "colors": colors,
        "typography": {
            "font_stack": font_stack,
            "slide_title": typography.get("slide_title", 40),
            "primary_proposition": typography.get("primary_proposition", 30),
            "section_title": typography.get("section_title", 24),
            "body": typography.get("body", 20),
            "support": typography.get("support", 16),
            "micro_label": typography.get("micro_label", 14),
            "title_weight": 700,
            "emphasis_weight": 700,
            "body_weight": 400,
        },
        "spacing": {
            "outer_margin": spacing.get("outer_margin", 64),
            "standard_gap": spacing.get("standard_gap", 24),
            "card_gap": 20,
            "compact_gap": 16,
            "micro_gap": 8,
            "card_padding": 24,
        },
        "shape": {
            "primary_radius": shape.get("primary_radius", 20.0),
            "secondary_radius": baseline["shape_language"]["secondary_radius"],
            "stroke_width": shape.get("stroke_width", 1.2),
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


_PROMPT_TEMPLATE = """# Role: 高级信息架构师 & SVG 可视化编码专家

你的任务是基于叙事要点与内容素材，自主设计一页布局合理、逻辑清晰、视觉美观、可直接用于演示文稿的 Office-safe SVG。

## Workflow: 执行步骤

### 步骤 1: 组织叙事与内容 (Narrative and Content)

不得重新选择叙事逻辑。严格按照下列叙事要点组织信息：
{{NARRATIVE}}

内容处理边界：
- 允许对素材进行提纯、改写、重排与补充；补充内容必须来自已批准的研究/来源，仅无事实内容的过渡句可自由撰写。
- 不得改变数字、单位、期间、限定词（待确认、待验收等）、因果、来源映射。
- 不得把推断或新增内容冒充为已批准事实。

### 步骤 2: 应用风格基线并设计视觉表达 (Style Baseline and Visual Design)

风格基线是软参考方向，不是逐项锁定令牌。在保持整套演示文稿风格一致性的前提下，布局、层级、卡片组织、信息密度、配色用法与装饰由你自主决定。

### 步骤 3: 编码 SVG（输出硬契约）

- **画布**: 根元素必须使用 `<svg viewBox="0 0 1280 720">`。
- **安全区与节奏**: 所有可见内容位于 64px 安全区内；间距使用 24px 节奏。
- **圆角卡片**: 仅使用 `<path>` 与 SVG 弧线命令 `A` 绘制圆角卡片；禁止为 `<rect>` 添加 `rx` 或 `ry`。
- **文本**: 每个文本对象使用显式 `<text>`；每一行使用简单、非嵌套的 `<tspan>`，并保证文本不越界；文字保持为文字，不转轮廓。
- **字号**: 正文 ≥20px，次级/来源 ≥14px；关键数字可用大字号或强调色突出，全页至多一个主强调焦点。
- **Office-safe 子集**: 仅使用 `svg`、`g`、`path`、`rect`（仅直角）、`circle`、`line`、`polyline`、`polygon`、`text`、`tspan`、`title`、`desc`；禁止 `foreignObject`、脚本、远程资源、滤镜、渐变、动画、`defs`、`use`、`clipPath`、`mask`、`image`。
- **根节点**: 包含 `<title>`（本页结论）与 `<desc>`（视觉关系）。

### 兼容约束

SVG 必须在 PowerPoint、Word 等 Office 软件中保持几何、文本和颜色稳定。所有图形、字体栈、颜色与文字内容必须自包含，不依赖外部文件、URL 或工具调用。

---

只返回一个 ```xml 代码围栏，围栏内必须是完整 SVG；围栏外不得输出解释、Markdown 标题或其它文本。
"""


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
    prompt = _PROMPT_TEMPLATE
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
    """Write the four files atomically under out_root/<style-id>/, verify, then
    register. Returns a result dict. Raises on verification failure."""
    style_id = pack["manifest"]["id"]
    pack_dir = (out_root / style_id)

    # Pre-write hard gate: verify composed payloads BEFORE any durable write.
    verify_composed(pack["manifest"], pack["tokens"], pack["prompt"], pack["STYLE.md"])

    pack_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    manifest_path = pack_dir / "manifest.json"
    tokens_path = pack_dir / "tokens.json"
    prompt_path = pack_dir / "prompt.md"
    rules_path = pack_dir / "STYLE.md"

    _atomic_write(manifest_path, json.dumps(pack["manifest"], ensure_ascii=False, indent=2) + "\n")
    _atomic_write(tokens_path, json.dumps(pack["tokens"], ensure_ascii=False, indent=2) + "\n")
    _atomic_write(prompt_path, pack["prompt"])
    _atomic_write(rules_path, pack["STYLE.md"])

    # Post-write integrity: on-disk verification must also pass.
    verify_style_pack(pack_dir)

    count = update_registry_idempotent(registry_path, pack["manifest"])
    return {
        "result": "PASS",
        "style_id": style_id,
        "output_dir": str(pack_dir),
        "registry_entries": count,
        "note": "风格包已固化并注册；在 ppt-start 中可用 style id 或显示名选择。",
    }
