# Synthetic style-prompt isolation pressure input

selected_style_id: tech-dark
scenario: style isolation
operation: initial_generation

expected_artifacts:
- A persisted generation prompt compiled from the selected `tech-dark` style-owned `prompt.md`, with its only whole-line `{{NARRATIVE}}` marker replaced once.
- Diagnostic records for the fixed manifest → tokens → guidance → prompt traversal and byte-exact tokens/prompt binding.

expected_state:
- The selected style remains `tech-dark` throughout compilation and generation.
- The final prompt contains the byte-exact hard shell, exactly seven typed Step-2 directives from verified `tech-dark` tokens, and the approved narrative—no concatenated registry, workflow, or guidance fragments.

forbidden_behavior:
- Do not allow another pack's wording, constraints, examples, or fragments into the final prompt.
- Do not silently substitute another style, reuse cached fragments, or fall back to the repository authoring seed.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
