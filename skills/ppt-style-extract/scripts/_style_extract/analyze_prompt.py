"""Map a free-text style prompt to an initial, honest token vocabulary.

This does not invent evidence for colors/sizes; it seeds semantic direction
(composition, prohibited motifs, palette-role naming) that the compose step
turns into a full tokens.json + STYLE.md. Color values remain contractual
defaults that a user may calibrate later.
"""

from __future__ import annotations

from .errors import ExtractError

_DIRECTION_MARKERS = {
    # each entry: keywords (matched against the full prompt, case-insensitive),
    # composition_rules default, prohibited motifs.
    "minimal": {
        "keywords": ["minimal", "极简", "简洁", "留白"],
        "composition_rules": {"card_coverage": "20%-40%"},
        "prohibited": ["redundant_decoration", "high_saturation_multicolor"],
    },
    "bento": {
        "keywords": ["bento", "bento 布局", "模块化", "卡片墙"],
        "composition_rules": {"card_coverage": "40%-60%"},
        "prohibited": ["equal_weight_card_wall"],
    },
    "dark": {
        "keywords": ["dark", "深色", "暗色", "夜间"],
        "composition_rules": {},
        "prohibited": ["bright_white_background"],
    },
    "data": {
        "keywords": ["data", "数据", "指标", "大屏"],
        "composition_rules": {},
        "prohibited": ["no_data_labels", "premature_acceptance_claim"],
    },
    "tech": {
        "keywords": ["tech", "科技", "数字化", "智能"],
        "composition_rules": {},
        "prohibited": ["gradient_background"],
    },
    "business": {
        "keywords": ["business", "商务", "企业", "汇报"],
        "composition_rules": {},
        "prohibited": ["left_blue_bar"],
    },
}


def _merge(seed: dict, additions: dict) -> None:
    seed["prohibited_motifs"] = list(dict.fromkeys(
        seed.get("prohibited_motifs", []) + additions.get("prohibited", [])
    ))
    for key in ("composition_rules",):
        seed.setdefault(key, {}).update(additions.get(key, {}))


def analyze_prompt(text: str) -> dict:
    if not text or not text.strip():
        raise ExtractError("empty_prompt")
    seed = {
        "direction": [],
        "composition_rules": {},
        "prohibited_motifs": [],
        "guidance_notes": [],
    }
    lower = text.lower()
    for direction, spec in _DIRECTION_MARKERS.items():
        if any(kw in lower for kw in spec["keywords"]):
            seed["direction"].append(direction)
            _merge(seed, spec)
    # Defaults kept conservative; never invent color evidence from prompt text.
    seed["prohibited_motifs"] = list(dict.fromkeys(
        seed["prohibited_motifs"] or ["decorative_lines", "color_only_semantics"]
    ))
    seed.setdefault("composition_rules", {}).setdefault("max_shadowed_objects", 1)
    seed.setdefault("composition_rules", {}).setdefault("primary_secondary_ratio", 1.5)
    return {"extractor": "prompt", "semantic": seed}
