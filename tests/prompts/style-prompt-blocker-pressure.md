# Synthetic unsafe style-prompt blocker pressure input

selected_style_id: canway-midyear-review
scenario: style_prompt_unavailable
operation: user_recompose

expected_artifacts:
- A persisted blocker record with `state: style_prompt_unavailable` and a resolver-specific reason such as `prompt_file_missing` or `prompt_path_unsafe` when the Canway manifest points to a missing or unsafe style-owned prompt.
- Diagnostic counters showing `generator calls: 0` and `SVG writes: 0`.

expected_state:
- Prompt assembly stops before invoking the generator when the manifest-referenced Canway prompt is missing or fails safety validation.
- The operation remains blocked and exposes the missing or unsafe prompt path and blocker reason.

forbidden_behavior:
- Do not fall through to a generic prompt, a different style, or stale cached Canway content.
- Do not invoke the generator; generator calls must remain 0.
- Do not create, overwrite, or patch any SVG; SVG writes must remain 0.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
