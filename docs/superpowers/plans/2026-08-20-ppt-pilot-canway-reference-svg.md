# PPT Pilot Canway Abstract Style Asset Guard Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

**Goal:** Keep the “嘉为年中总结风格” recognizable through machine-readable tokens and abstract design guidance without supplying a canonical rendered composition that generated decks can imitate.

**Architecture:** The style manifest exposes only `tokens.json` and `STYLE.md`. Per-slide visual briefs record those two provenance paths and derive layout from current content semantics. Static tests recursively reject SVG files anywhere inside this style pack and reject rendered-exemplar fields or instructions.

**Tech Stack:** JSON and Markdown assets with Python `unittest` contract tests.

## Global Constraints

- This is Plan 6 of 7 and depends on the style registry/tokens and Canway guidance plans.
- Preserve the palette, typography, spacing, shape, semantic-surface, and content-driven composition rules.
- Do not add a single-slide finished example, composition reference, fixed region map, or renamed equivalent.
- Office-safe SVG remains a generated-slide and QA contract, not a style-pack asset.
- Do not modify FY26 content or runtime acceptance evidence.

---

### Task 1: Enforce abstract-only style assets

**Files:**
- Modify: `skills/ppt-start/assets/styles/canway-midyear-review/manifest.json`
- Modify: `skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`
- Modify: `skills/ppt-start/references/design-system.md`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `tests/fixtures/visual-briefs/S05.md`
- Test: `tests/test_style_packs.py`
- Test: `tests/test_visual_generation_contract.py`

**Interfaces:**
- Consumes: the registered Canway style ID, tokens, and abstract design rules.
- Produces: an abstract-only style pack and provenance contract that cannot silently reintroduce a canonical layout.

- [x] **Step 1: Add a failing no-exemplar contract**

Require the style manifest file map to equal:

```json
{
  "tokens": "tokens.json",
  "guidance": "STYLE.md"
}
```

Recursively assert that the style-pack directory contains no SVG file. Require active runtime guidance to prohibit deriving page composition from a finished example or existing SVG.

- [x] **Step 2: Remove the rendered exemplar and its active references**

Keep tokens and abstract design rules. Replace visual-brief provenance with:

```text
style_token_path
style_guidance_path
```

Do not retain a style-level rendered-composition path.

- [x] **Step 3: Version the changed style interface**

Set the style manifest version to `1.1.0` and keep the visual-brief fixture synchronized so an older provenance snapshot is not treated as current.

- [x] **Step 4: Verify focused and complete tests**

```bash
python -m unittest tests.test_style_packs tests.test_visual_generation_contract -v
```

```bash
python -m unittest discover -s tests -v
```

The focused suite must prove the abstract-only boundary; the complete suite must preserve style discovery, visual-brief assembly, workflow, review, and generic SVG contracts.
