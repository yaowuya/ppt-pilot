# Synthetic style-prompt isolation pressure input

selected_style_id: tech-dark
scenario: style isolation
operation: initial_generation

expected_artifacts:
- A persisted generation prompt assembled only from the selected `tech-dark` style assets.
- Diagnostic records identifying every style-owned prompt fragment that was loaded.

expected_state:
- The selected style remains `tech-dark` throughout prompt assembly and generation.
- The final prompt contains only registry, workflow, and `tech-dark` style guidance applicable to this operation.

forbidden_behavior:
- Do not allow Canway-specific or Bento-specific wording, constraints, examples, or fragments into the final prompt.
- Do not silently substitute another style or reuse prompt fragments cached for another style.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
