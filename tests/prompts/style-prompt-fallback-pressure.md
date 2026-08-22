# Synthetic style-registry fallback pressure input

selected_style_id: minimal-business
scenario: registry fallback
operation: initial_generation

expected_artifacts:
- Full-install diagnostic: when all six fallback files are present, record the complete six-file fallback set and the assembled generation prompt.
- Partial-install diagnostic: when exactly one required companion file is missing, record the missing companion and the resulting incomplete-install decision without treating the remaining five files as a complete fallback.

expected_state:
- A complete six-file fallback installation is accepted for `minimal-business` only when every required fallback file and companion is present and safe.
- A partial install with one missing companion is explicitly distinguished from the complete six-file fallback and remains observable as incomplete.

forbidden_behavior:
- Do not report a five-file partial install as a complete six-file fallback.
- Do not silently invent, copy, or substitute the missing companion.
- Do not cross-load style-owned prompt content from another style.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
