# PPT Pilot Style Registry and Canway Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fast style-pack tests, an extensible registry, and machine-readable “嘉为年中总结风格” identity/tokens.

**Architecture:** Preserve flat legacy seeds, add `registry.json`, and introduce a non-default directory-based rich style pack selectable by ID or Chinese display name.

**Tech Stack:** JSON assets and Python `unittest` static validation.

## Global Constraints

- This is Plan 4 of 7 and depends on both visual-contract plans plus the revision-mode plan.
- Preserve the three legacy seed files and keep Canway non-default.
- Default Canway canvas is `#F5F8FC`.
- Use no FY26 content, remote asset, or runtime dependency.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Add failing style-pack discovery tests

**Files:**
- Create: `tests/test_style_packs.py`
- Modify: `tests/test_assets.py:12-49`

**Interfaces:**
- Consumes: `tests/helpers.py`, existing style seeds, SVG helpers from `tests/test_svg_contract.py`.
- Produces: the registry/manifest/token/reference contract for all rich style packs.

- [ ] **Step 1: Prevent the legacy seed test from treating the registry as a seed**

In `tests/test_assets.py`, rename `STYLE_FILES` to `LEGACY_STYLE_FILES` and load only those explicit files:

```python
LEGACY_STYLE_FILES = {
    "minimal-business.json",
    "tech-dark.json",
    "bold-editorial.json",
}

paths = {
    filename: self.style_root / filename
    for filename in LEGACY_STYLE_FILES
}
self.assertTrue(all(path.is_file() for path in paths.values()))
```

Keep all existing exact top-level seed assertions unchanged.

- [ ] **Step 2: Create the failing rich-style tests**

Create `tests/test_style_packs.py`:

```python
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root
from test_svg_contract import ALLOWED, local_name, numeric_font_size


class StylePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.style_root = skill_root() / "assets" / "styles"
        self.registry_path = self.style_root / "registry.json"
        self.pack_root = self.style_root / "canway-midyear-review"
        self.manifest_path = self.pack_root / "manifest.json"
        self.tokens_path = self.pack_root / "tokens.json"
        self.rules_path = self.pack_root / "STYLE.md"
        self.reference_path = self.pack_root / "reference.svg"

    def test_registry_has_unique_ids_names_and_existing_entrypoints(self):
        payload = json.loads(read_text(self.registry_path))
        self.assertEqual(payload["schema_version"], 1)
        styles = payload["styles"]
        ids = [style["id"] for style in styles]
        names = [style["display_name"] for style in styles]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))
        for style in styles:
            self.assertTrue((self.style_root / style["entrypoint"]).is_file())
        canway = next(style for style in styles if style["id"] == "canway-midyear-review")
        self.assertEqual(canway["display_name"], "嘉为年中总结风格")
        self.assertEqual(canway["kind"], "style_pack")

    def test_manifest_references_complete_pack(self):
        manifest = json.loads(read_text(self.manifest_path))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "canway-midyear-review")
        self.assertEqual(manifest["display_name"], "嘉为年中总结风格")
        self.assertIn("嘉为年中总结风格", manifest["selection_aliases"])
        for path in manifest["files"].values():
            self.assertTrue((self.pack_root / path).is_file())
        self.assertTrue(manifest["compatibility"]["office_safe_svg"])
        self.assertFalse(manifest["default"])

    def test_tokens_encode_approved_canway_style(self):
        tokens = json.loads(read_text(self.tokens_path))
        self.assertEqual(tokens["schema_version"], 1)
        self.assertEqual(tokens["id"], "canway-midyear-review")
        expected_colors = {
            "canvas": "#F5F8FC",
            "hero_dark": "#10233F",
            "brand_primary": "#156BFF",
            "title_accent": "#1E63FF",
            "sky": "#65B7F9",
            "ai_pilot": "#8866FD",
            "ink": "#0B1930",
            "fact_surface": "#FFFFFF",
            "border": "#DCE9F8",
        }
        for name, value in expected_colors.items():
            self.assertEqual(tokens["colors"][name], value)
        self.assertGreaterEqual(tokens["typography"]["slide_title"], 40)
        self.assertGreaterEqual(tokens["typography"]["body"], 20)
        self.assertGreaterEqual(tokens["typography"]["micro_label"], 14)
        self.assertEqual(tokens["spacing"]["outer_margin"], 64)
        self.assertEqual(tokens["composition"]["max_shadowed_objects"], 1)
        self.assertEqual(tokens["composition"]["primary_secondary_ratio"], 1.5)

    def test_rules_capture_identity_and_prohibitions(self):
        rules = read_text(self.rules_path)
        for token in (
            "单行结论标题",
            "短语级",
            "深色主卡",
            "白色事实卡",
            "证据边界",
            "AI",
            "有界试点",
            "40%–60%",
            "最多一处轻阴影",
            "左侧长蓝条",
            "背景图片",
            "渐变",
            "等权卡片墙",
            "根据内容选择",
        ):
            self.assertIn(token, rules)

    def test_reference_is_standalone_office_safe_svg(self):
        raw = read_text(self.reference_path)
        lowered = raw.lower()
        for forbidden in ("<style", "<defs", "<filter", "<lineargradient", "<image", "url(", "javascript:"):
            self.assertNotIn(forbidden, lowered)
        root = ET.fromstring(raw)
        self.assertEqual(root.attrib.get("width"), "1280")
        self.assertEqual(root.attrib.get("height"), "720")
        self.assertEqual(root.attrib.get("viewBox"), "0 0 1280 720")
        ids = set()
        for element in root.iter():
            self.assertIn(local_name(element.tag), ALLOWED)
            element_id = element.attrib.get("id")
            if element_id:
                self.assertNotIn(element_id, ids)
                ids.add(element_id)
            if local_name(element.tag) == "text":
                self.assertTrue(any(local_name(child.tag) == "tspan" for child in element))
                role = element.attrib.get("data-role", "body")
                size = numeric_font_size(element.attrib["font-size"])
                minimum = 40 if role == "title" else 14 if role == "footnote" else 20
                self.assertGreaterEqual(size, minimum)
        self.assertEqual(root.find("{http://www.w3.org/2000/svg}path").attrib["fill"], "#F5F8FC")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the focused tests and verify they fail for missing assets**

Run:

```bash
python -m unittest tests.test_assets tests.test_style_packs -v
```

Expected: legacy seed tests pass; style-pack tests fail because registry and pack files do not exist.

- [ ] **Step 4: Record checkpoint**

Record that only test code changed and no style assets or FY26 files exist yet.

### Task 2: Create the registry, manifest, and token interface

**Files:**
- Create: `skills/ppt-start/assets/styles/registry.json`
- Create: `skills/ppt-start/assets/styles/canway-midyear-review/manifest.json`
- Create: `skills/ppt-start/assets/styles/canway-midyear-review/tokens.json`
- Test: `tests/test_style_packs.py`

**Interfaces:**
- Consumes: existing legacy seed file names and the approved style specification.
- Produces: style ID/name discovery and machine-readable token roles.

- [ ] **Step 1: Create the style registry**

Write `registry.json`:

```json
{
  "schema_version": 1,
  "styles": [
    {
      "id": "minimal-business",
      "display_name": "极简商务",
      "kind": "legacy_seed",
      "entrypoint": "minimal-business.json"
    },
    {
      "id": "tech-dark",
      "display_name": "深色科技",
      "kind": "legacy_seed",
      "entrypoint": "tech-dark.json"
    },
    {
      "id": "bold-editorial",
      "display_name": "强调编辑",
      "kind": "legacy_seed",
      "entrypoint": "bold-editorial.json"
    },
    {
      "id": "canway-midyear-review",
      "display_name": "嘉为年中总结风格",
      "kind": "style_pack",
      "entrypoint": "canway-midyear-review/manifest.json"
    }
  ]
}
```

- [ ] **Step 2: Create the style manifest**

Write `manifest.json`:

```json
{
  "schema_version": 1,
  "id": "canway-midyear-review",
  "display_name": "嘉为年中总结风格",
  "version": "1.0.0",
  "kind": "style_pack",
  "default": false,
  "summary": "面向 SaaS、研发、交付与组织管理层年中或年度汇报的层级 Bento 风格。",
  "recommended_for": ["SaaS 管理汇报", "研发复盘", "交付总结", "组织与治理提案"],
  "not_for": ["营销海报", "活动发布", "重数据大屏"],
  "selection_aliases": ["canway-midyear-review", "嘉为年中总结风格"],
  "files": {
    "tokens": "tokens.json",
    "guidance": "STYLE.md",
    "reference_svg": "reference.svg"
  },
  "compatibility": {
    "office_safe_svg": true,
    "canvas": "1280x720",
    "languages": ["zh-CN", "en"]
  }
}
```

- [ ] **Step 3: Create the machine-readable tokens**

Write `tokens.json`:

```json
{
  "schema_version": 1,
  "id": "canway-midyear-review",
  "display_name": "嘉为年中总结风格",
  "colors": {
    "canvas": "#F5F8FC",
    "hero_dark": "#10233F",
    "brand_primary": "#156BFF",
    "title_accent": "#1E63FF",
    "sky": "#65B7F9",
    "ai_pilot": "#8866FD",
    "ink": "#0B1930",
    "text_secondary": "#52637B",
    "fact_surface": "#FFFFFF",
    "evidence_surface": "#EFF6FF",
    "pilot_surface": "#F7F5FF",
    "border": "#DCE9F8"
  },
  "typography": {
    "font_stack": ["Microsoft YaHei", "PingFang SC", "Arial", "sans-serif"],
    "slide_title": 40,
    "primary_proposition": 30,
    "section_title": 24,
    "body": 20,
    "support": 16,
    "micro_label": 14,
    "title_weight": 700,
    "emphasis_weight": 700,
    "body_weight": 400
  },
  "spacing": {
    "outer_margin": 64,
    "standard_gap": 24,
    "card_gap": 20,
    "compact_gap": 16,
    "micro_gap": 8,
    "card_padding": 24
  },
  "shape": {
    "primary_radius": 20,
    "secondary_radius": 14,
    "stroke_width": 1.2,
    "connector_width": 2,
    "shadow_offset": 6
  },
  "composition": {
    "card_coverage": "40%-60%",
    "primary_secondary_ratio": 1.5,
    "max_shadowed_objects": 1,
    "title_single_line_preferred": true,
    "phrase_emphasis_allowed": true
  }
}
```

- [ ] **Step 4: Run registry/token tests**

Run:

```bash
python -m unittest tests.test_style_packs.StylePackTests.test_registry_has_unique_ids_names_and_existing_entrypoints tests.test_style_packs.StylePackTests.test_tokens_encode_approved_canway_style -v
```

Expected: registry/token tests pass; manifest test may still fail until all referenced files exist.

- [ ] **Step 5: Record checkpoint**

Record the public style ID, display name, default status, and exact color tokens.
