# Manuscript Review — Blocked

```json
{
  "schema_version": 1,
  "review_mode": "subagent",
  "verdict": "BLOCK",
  "round": 1,
  "reviewer_id": "independent-reviewer-block-1",
  "reviewer_context": "fresh-independent-context-block-1",
  "delegation_evidence": {
    "child_context_id": "fresh-independent-context-block-1",
    "completion_event_id": "completion-block-1",
    "result_context_id": "fresh-independent-context-block-1"
  },
  "reviewed_file_snapshot": {
    "snapshot_id": "sha256:blocked-manuscript-v1",
    "files": [
      "简报.md",
      "研究.md",
      "来源.md",
      "大纲.md",
      "故事板.md"
    ]
  },
  "findings": [
    {
      "id": "MR-001",
      "severity": "HIGH",
      "category": "factuality",
      "slide_ids": ["S03"],
      "claim": "The market grew by exactly 47% in the current year.",
      "evidence": "No cited source contains the 47% value, and the claim is time-sensitive.",
      "recommendation": "Remove the number or replace it with a dated, source-backed and qualified statement.",
      "status": "OPEN"
    }
  ]
}
```
