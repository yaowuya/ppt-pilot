# Synthetic style-registry identity-recovery pressure input

selected_style_id: minimal-business
scenario: registry missing
operation: initial_generation

expected_artifacts:
- An identity-recovery diagnostic may restore only the selected style identity from the closed built-in table.
- A durable `style_assets_unavailable: registry_missing` blocker with zero prompt, transaction, candidate, SVG, and generator side effects.

expected_state:
- Identity recovery never authorizes generation and never supplies runtime assets.
- Generation remains fail closed until the registry and selected manifest → tokens → guidance → prompt traversal verify successfully.

forbidden_behavior:
- Do not treat the identity-recovery table as a complete registry or runtime fallback.
- Do not assemble a prompt from repository templates, legacy dual markers, or guessed companion files.
- Do not cross-load style-owned prompt content from another style or write any generation artifact.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
