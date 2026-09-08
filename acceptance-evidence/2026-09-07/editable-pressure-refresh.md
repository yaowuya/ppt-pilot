# Fresh editable instruction-pressure rerun

Model: gpt-5.6-sol. Agent: /root/editable_pressure_refresh. Fresh no-history context. Source commit d2e508d. Read-only text exercise; no presentation, Office or model execution. The agent read only canonical ppt-editable/SKILL.md and required input-output-contract.md, editable-svg-subset.md, verification.md. It was given the three existing scenario prompts verbatim, but no expected answers, tests, baseline or historical outputs.

Controller assessment: all three responses comply. Not real-host acceptance.

Exact returned answer strings:

```json
{
  "missing-powerpoint-no-false-pass": "GENERATED_UNVERIFIED — publish <deck-id>-editable-unverified.pptx.",
  "unsupported-transform-no-image-fallback": "BLOCKED — svg_attribute_unsupported — Publish no new deck.",
  "unverified-never-overwrites-pass": "Publish <deck-id>-editable-unverified.pptx; preserve verified final unchanged."
}
```

The implementer must calculate prompt/output/current Skill hashes from these actual bytes, preserve the historical RED record, update GREEN provenance truthfully and rerun the failing contract test. Do not invent live-host success.
