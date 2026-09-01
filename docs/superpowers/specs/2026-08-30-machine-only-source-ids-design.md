# Machine-Only Source IDs Design

**Date:** 2026-08-30  
**Status:** Approved design; pending written-spec review

## Goal

Prevent internal source identifiers such as `SRC-001`, `SRC-002`, and `SRC-005` from appearing as visible text in generated slide SVGs or editable PowerPoint decks, while preserving machine-readable traceability.

## User-visible rule

- Internal identifiers matching `SRC-<digits>` must not appear in any visible SVG `<text>` or `<tspan>` content.
- The default slide must not contain an internal-source footer such as `来源：SRC-001 · SRC-002` or `Source: SRC-001`.
- When the user explicitly requests visible citations, the slide may show human-readable source names or URLs, but it must still not expose internal `SRC-<digits>` identifiers.

## Machine traceability

Internal source IDs remain permitted and required where applicable in non-visible metadata:

- SVG `data-source-id` attributes.
- Canonical source mappings in storyboard/research artifacts.
- Editable-PowerPoint trace metadata such as `p:cNvPr/@descr`.
- Verification reports and non-rendered diagnostic evidence.

Removing visible IDs must not remove or rewrite these machine-owned identities.

## Generation contract

The direct-compile prompt authority must replace the current visible-footer requirement with these rules:

1. Source-backed claims carry source IDs through `data-source-id` on the relevant group or leaf.
2. Internal `SRC-<digits>` values are metadata only and must never be rendered as visible text.
3. No visible source footer is required by default.
4. Explicitly requested visible citations use human-readable labels or URLs without internal IDs.

Historical plan/spec text may retain old wording as history, but active Skill/reference/template/example files must converge to this contract.

## QA and promotion gate

Before a generated SVG page can be promoted:

1. Parse visible text from every `<text>` and nested `<tspan>` node.
2. Normalize text for inspection without reading attributes as visible content.
3. Reject the page if visible text contains the case-insensitive pattern `\bSRC-[0-9]+\b`.
4. Report a deterministic content/source-metadata failure and preserve the previous final.
5. Continue to require valid `data-source-id` metadata for source-backed claims.

The scan must not reject source IDs that exist only in attributes, trace descriptions, storyboard fields, or reports.

## ppt-editable behavior

`ppt-editable` must never introduce a visible source label. It converts only source-visible text, while copying source IDs into machine trace metadata.

Acceptance must verify:

- No editable text run contains `SRC-<digits>`.
- Source-backed shapes/groups still retain trace identity.
- Existing SVGs containing visible internal IDs fail before final editable output rather than silently preserving the error.

This is a content gate, not a post-generation sanitizer: the converter must not delete text and reflow the page after generation.

## Files and tests

Active updates belong in:

- `skills/ppt-start/references/generation-prompt-template.md`
- `skills/ppt-start/references/generation-prompt-byte-grammar.md`
- `skills/ppt-start/references/qa-and-revision.md`
- `skills/ppt-start/references/svg-contract.md`
- `skills/ppt-start/assets/examples/office-safe-slide.svg`
- `tests/test_redesign_prompt_contract.py`
- `tests/test_svg_contract.py`
- generation-prompt fixtures affected by byte-exact changes
- `ppt-editable` package/reference and integration acceptance tests

Required tests:

1. Active prompt authority requires machine-only source IDs and does not require a visible source footer.
2. Example SVGs contain `data-source-id` where appropriate but no visible `SRC-<digits>` text.
3. Visible-text scanning rejects `来源：SRC-001 · SRC-002`, `Source: SRC-001`, and a bare visible `SRC-005`.
4. The same IDs in `data-source-id` and trace metadata pass.
5. Explicit human-readable citations without internal IDs pass.
6. Byte-exact prompt fixtures and hashes are regenerated deterministically.
7. Editable-PowerPoint text and reference-corpus acceptance contain no visible internal IDs.

## Error handling

- `ppt-start` records `fact_source_mismatch` when generated visible text contains an internal source ID.
- `ppt-editable` preflight records `svg_text_invalid` and returns `BLOCKED` when an input SVG already contains a visible internal source ID.
- A newly generated page with a visible internal source ID is not promoted.
- A previous verified SVG/PPTX remains authoritative.
- The failure is reported as a content/source-metadata contract violation; no image fallback or text-deletion fallback is allowed.

## Non-goals

- Removing source IDs from machine metadata.
- Hiding user-requested human-readable citations.
- Post-processing generated SVG layout to delete offending text.
- Renumbering or rewriting source IDs in research/storyboard artifacts.

## Integration order

1. Finish and verify `ppt-editable` implementation.
2. Add its no-visible-SRC acceptance checks.
3. Update the active `ppt-start` direct-compile prompt/QA contract and byte fixtures as part of the concurrent SVG plan.
4. Run full package and reference-corpus verification before deployment.
