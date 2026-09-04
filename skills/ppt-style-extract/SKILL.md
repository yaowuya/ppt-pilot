---
name: ppt-style-extract
description: Use when the user wants to turn a template PPT, reference images, or a style prompt into a reusable PPT Pilot style pack — freeze their own branded style so ppt-start can reuse it later.
---

# PPT Style Extract

Extract a reusable style from a **template PPT**, **reference image(s)**, or a **style prompt**, and freeze it into a user-owned PPT Pilot style pack. Register it into `assets/styles/registry.json` so a later `ppt-start` run can select it by id or display name.

This is the companion to `ppt-start`'s built-in style packs: it never edits `ppt-start`'s runtime — it only authors a new, fully-compliant style pack and registers it.

## Required references

Read before running:

- [Input/output and state contract](references/input-and-output-contract.md)
- [Extraction contract](references/extraction-contract.md)
- [Style-pack verification](references/style-pack-verification.md)

## Fixed phase order

`locate → classify → extract → compose → verify → write → register → report`

Do not reorder these phases. Verification finishes before any durable byte is written; a failed verify returns `BLOCKED` with **zero writes**.

## Run

Resolve paths relative to this installed Skill, not the repository or current directory.

```bash
python scripts/write_style_pack.py --input <pptx|image|prompt> --style-id <id> --out <user-style-packs> --registry <registry.json> --json
```

The `--input` form is detected automatically (`.pptx` / image path(s) / a quoted prompt string). `--json` writes a machine-readable result to stdout.

Individual extractors are also callable directly:

```bash
python scripts/extract_pptx.py --in <template.pptx> --json
python scripts/extract_image.py --in <image_or_folder> --json
python scripts/analyze_prompt.py --in "一句风格描述" --json
```

## Inputs and what they yield

| Input | Detect | Primary evidence |
|---|---|---|
| Template PPT | `.pptx` path | `ppt/theme/theme1.xml`, slide masters, per-page shape fill/stroke/geometry, text runs |
| Reference image(s) | image path or folder | SVG text/fill sampling; PNG pixel color histogram (subject to capability) |
| Style prompt | non-path string | semantics mapped to tokens + guidance |

## Verification and result states

- `PASS`: every style-pack hard constraint passed, pack written, registry updated idempotently. Outputs the package and a reusable note for `ppt-start`.
- `BLOCKED`: input unreadable, an extractor contradicted the contract, or a hard constraint failed. Write nothing.
- `UNAVAILABLE`: a required capability (e.g. PNG pixel sampling) is missing and cannot be satisfied without fabricating evidence. Disclose it; produce no pack.

## Non-negotiable behavior

- Never fabricate color/font/geometry evidence when an extractor returns `unavailable`; disclose it and stop.
- Never author a rendered slide exemplar, reference composition, or fixed-region diagram into the pack.
- Never write `[[CANONICAL_NARRATIVE_BULLETS]]`. Never write `[[STYLE_BASELINE]]`. Never write `source=`, `REDESIGN.md`, `.redesign.md`, or a reference SVG into any produced artifact.
- Never mutate an existing style pack in-place. A byte-different payload for an existing ID fails as `style_pack_immutable_conflict`; publish it under a new immutable style ID.
- `prompt.md` must contain exactly one `{{NARRATIVE}}` whole-line token.
- Materialize the extracted palette, font stack, spacing, shape language, composition rules, and prohibited motifs into `prompt.md` at authoring time; do not emit a generic template that depends on runtime token access.
- Treat Prompt-bound visual data as a closed typed schema: enum-backed palette roles/uses and prohibited motifs, allowlisted composition keys, numeric typography/spacing/shape values, fixed 64px/24px hard-shell spacing, and non-executable font-family values. Preserve safe ASCII brand fonts; record an explicit safe fallback for rejected font strings.
- Require `prompt.md` to equal the deterministic composition of the same pack's verified `tokens.json`; only the seven Step-2 style directive lines vary, while Role, Step 1, Step 3, compatibility, and output instructions stay byte-exact.
- Require each generated semantic content group to echo its stable non-source `block_id` exactly once and only as the canonical `data-block-id` attribute value; forbid it in text, tail, and every other attribute. Source IDs remain coordinator-owned and must not enter the prompt; leakage fails as `fact_source_mismatch` before any candidate write.
- Registry writes are idempotent only for a byte-identical pack. The writer reloads the registry while holding its file lock, merges the entry, and commits it pointer-last; it never blind-replaces a preflight snapshot.

## Pressure decisions

When a request conflicts with this contract, return the matching decision without repeating or endorsing the forbidden action:

- `{{NARRATIVE}}` count != 1 in the composed template: `BLOCKED — prompt_template_invalid — zero writes.`
- Missing `prompt_baseline` key or a palette role token absent from `colors`: `BLOCKED — tokens_schema_invalid — zero writes.`
- Image sampling not possible and no evidence-based fallback: `UNAVAILABLE — image_unavailable — no pack produced.`

## Safety

Reject unsafe paths, symlinks, junctions, reparse points, special files, and malformed input. Never read or write outside the selected `--out` and `--registry` scopes. Verify in a hidden staging directory, atomically publish the immutable pack directory, then update registry pointer-last under the registry lock. A crash before the pointer update may leave only an unregistered complete orphan, which the identical retry can safely adopt.
