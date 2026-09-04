# Synthetic unsafe style-prompt blocker pressure input

selected_style_id: canway-midyear-review
scenario: generation_prompt_unavailable
operation: user_recompose

expected_artifacts:
- A persisted blocker record with `state: generation_prompt_unavailable` and a resolver-specific reason such as `prompt_file_missing` or `prompt_path_unsafe` when the Canway manifest points to a missing or unsafe style-owned prompt. Its safe declared resource is `assets/styles/canway-midyear-review/prompt.md`; an unsafe path is recorded as `none`.
- A style registry, entrypoint, manifest, or tokens/guidance asset failure instead persists `state: style_assets_unavailable` with its existing corresponding reason.
- Diagnostic counters showing `generator calls: 0` and `SVG writes: 0`.

expected_state:
- Prompt assembly stops before invoking the generator when the manifest-referenced Canway prompt is missing or fails safety validation.
- The operation remains blocked and exposes the blocker reason. A validated missing-path resource may be shown, but an unsafe path is sanitized to `resource: none`.

forbidden_behavior:
- Every selectable style manifest must declare `files.prompt_template`. If the field is absent, persist `style_asset_field_missing` and stop with zero generator, transaction, or candidate writes. If the declared template is missing or invalid, do not fall through to a generic prompt, repository authoring seed, a different style, or stale cached Canway content.
- Do not invoke the generator; generator calls must remain 0.
- Do not create, overwrite, or patch any SVG; SVG writes must remain 0.

EVIDENCE_CLASS: DIAGNOSTIC
不得作为 Claude Code、Codex、浏览器或 PowerPoint 验收
