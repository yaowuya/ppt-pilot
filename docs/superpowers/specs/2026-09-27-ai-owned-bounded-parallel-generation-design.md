# AI-Owned Bounded Parallel SVG Generation Design

**Date:** 2026-09-27
**Status:** Approved by the user on 2026-09-27 and implemented in the current working tree. Not committed, pushed, or deployed; real 2+ Agent overlap remains a Host-level acceptance item.

## Problem and root cause

PPT Pilot previously supported concurrent fresh-context page generation. The completed 2026-08-29 concurrency design allowed multiple isolated page tasks to overlap while preserving coordinator-only writes and deterministic promotion order.

During the 2026-09-24 migration from Python-owned workflow state to AI-owned `run.json`, the implementation correctly removed the scheduler, batch runtime, queue and dashboard, but accidentally changed:

```text
one coordinator action per turn
```

into:

```text
at most one page generator call per turn
```

The active Skill, `ai-state.md` and `workflow.md` now enforce that serial rule, and `tests/test_interaction_protocol.py` explicitly rejects the words “可并发”. Claude Code therefore followed the installed contract when it refused the user's request. This is a plugin regression, not a Claude Code concurrency limitation and not a necessary consequence of AI-owned state.

## Decision

Restore **bounded parallel generator waves** without restoring the retired Python scheduler.

A generation wave is one AI coordinator action. Only prompt-only page Agents run concurrently. The coordinator remains the only writer of the filesystem and `.ppt-pilot/run.json`, and all candidate processing, validation, promotion and state publication remain deterministic and serial.

## Concurrency policy

- Default target width: **5**.
- Explicit user width: integer **2–10**.
- Explicit user request for serial generation: width **1**.
- Actual width: the minimum of target width, eligible pages remaining and known host capacity.
- If host capacity is unknown, Claude Code attempts the default bounded wave and records the number of tasks actually accepted; the host is allowed to accept fewer.
- Capacity refusal before Prompt acceptance does not increment the page attempt and leaves that page eligible for a later wave.
- This design does not restore the retired adaptive `5→7→9→10` algorithm. A user may explicitly request up to 10.
- A request such as “继续，并行生成多个页面” must attempt more than one page whenever at least two pages are independently eligible. If only one is eligible, the coordinator reports the real dependency or capacity limit, not a blanket one-call rule.

## Eligibility and stage boundaries

Pages may share a wave only when all of these hold:

- they belong to the same run and current stage;
- their storyboard, approved manuscript and theme snapshots are the same and readable;
- each page has a complete frozen Prompt and page-specific source map;
- each page is independently eligible for an initial call or has an explicit retry/recompose authorization;
- no pending interaction or shared-state conflict gates the page;
- the pages do not depend on each other's generated output.

Selected anchor pages may be generated in one anchor wave. Production pages cannot join that wave: guided anchor approval or equivalent auto validation remains a hard boundary. No wave crosses manuscript, theme, anchor or delivery gates.

## AI-owned wave evidence

`run.json` may contain one transient, AI-owned `active_generation_wave` object:

```json
{
  "schema_version": 1,
  "wave_id": "wave-S02-S06-01",
  "stage": "production",
  "status": "prepared",
  "target_width": 5,
  "ordered_slide_ids": ["S02", "S03", "S04", "S05", "S06"],
  "prompt_sha256": {
    "S02": "sha256:d4df06e9137784f7529d8a018c4801f664c512389c2656bbf3b12b8ff1df9f12",
    "S03": "sha256:c41ec4b66d5bf8b7b1723e827ad29aa953dd055c8eff00334c0735407cffa141",
    "S04": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "S05": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "S06": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  },
  "accepted_tasks": {}
}
```

The example digests show field syntax only; a real run computes them from the exact reread Prompt bytes and never reuses these illustrative values.

This object is coordination evidence, not a queue or second page inventory. `slides` remains the page authority. The coordinator writes the prepared wave only after every listed Prompt/source map has been written, reread and bound to the same upstream snapshots.

After the host accepts task launches, `accepted_tasks` records only actual accepted calls:

```json
{
  "S02": {
    "task_id": "task-S02-01",
    "attempt": 1,
    "prompt_sha256": "sha256:d4df06e9137784f7529d8a018c4801f664c512389c2656bbf3b12b8ff1df9f12",
    "state": "in_flight"
  }
}
```

The page's `attempts` increases exactly once when the host has accepted that Prompt for generation. A prepared page that the host rejects for capacity remains unchanged. The coordinator writes task attribution as soon as the launch returns; it never infers acceptance merely from launch intent.

The wave is removed after every accepted task is terminal and every result has been processed, or after all unaccepted pages have been returned to eligibility. Final `complete|partial|failed` runs cannot retain an active wave.

## Dispatch and result flow

1. Select eligible pages in storyboard order and cap the ordered set to the actual width.
2. Compile and reread each complete Prompt and source map serially.
3. Atomically write the prepared wave.
4. Dispatch all selected prompt-only Agents in one host tool round, preferably as background tasks. Each Agent receives only its Prompt by value and has no file or state ownership.
5. Record accepted task IDs and per-page attempts in one coordinator state update. Preserve unaccepted pages without an attempt.
6. Wait for host completion notifications; do not busy-poll or create a sleep loop.
7. Results may arrive out of order, but the coordinator processes only the maximal contiguous terminal prefix of `ordered_slide_ids`. At the first nonterminal page it stops publication; every later completed result remains in host task evidence until all preceding ordered results are terminal or explicitly unavailable.
8. For each page, serially extract the XML fence, validate/enrich/finalize the SVG, atomically publish the final and update that page record.
9. Clear the terminal wave and choose the next earliest action or wave.

Generator overlap is therefore real. Shared artifact and state writes do not overlap.

## Recovery and failure locality

- On resume, an active wave is read before selecting new generation work.
- Accepted tasks with durable host attribution are resumed or consumed; they are never redispatched merely because a new turn began.
- Replaying the same slide/task ID/Prompt digest attribution is idempotent and never increments attempts again.
- Replacing an accepted task ID, changing its Prompt digest, reusing one task ID for another slide or finding an attempt mismatch is a page-local `generator_attribution_unknown` conflict; the coordinator fails closed without overwriting evidence or guessing.
- A prepared page with no accepted task evidence has not consumed an attempt and may be included in a later wave.
- If launch attribution is ambiguous, only that page becomes `generator_attribution_unknown`; the coordinator does not guess, increment twice or block already attributed siblings.
- Generator refusal, malformed output, SVG invalidity and page QA failure remain page-local.
- A shared storyboard/theme/source-map identity conflict blocks the wave before dispatch and consumes no attempts.
- One page failure never cancels accepted sibling tasks or demotes their prior finals.
- Known zero host capacity is a wait condition: no empty wave is created and no attempt is consumed. The coordinator does not poll or cancel other work to manufacture capacity.
- If the host cannot run concurrent tasks, actual width becomes 1 and the coordinator reports `host_concurrency_unavailable`; this is a capability limit, not a universal workflow rule.

## Ordering and writes

- Prompts and source maps: coordinator-only, serial preparation.
- Generator calls: concurrent, prompt-only.
- Raw host results: host-owned task evidence until consumed.
- Extraction, source join and deterministic SVG validation: coordinator invokes per-page logic serially in storyboard order.
- Candidate/final writes and `run.json` mutation: coordinator-only, atomic and serial.
- Visible failure reporting: ordered by storyboard, not task completion time.

This prevents the shared-state and source-map races cited by the refusal message without sacrificing generation concurrency.

## Documentation changes

The active authority will be updated as follows:

- `skills/ppt-start/SKILL.md`: “one action” becomes “one bounded wave or one non-generation action”; default width 5 and branch pointer.
- `references/ai-state.md`: exact wave evidence, attempts and recovery semantics.
- `references/workflow.md`: bounded parallel dispatch, serial publication and no polling.
- `references/visual-brief-and-generation.md`: per-page Agent boundary and concurrent tool-round behavior.
- `references/qa-and-revision.md` and `artifact-contract.md`: concurrent generator results, serial candidate/final/state writes.
- Public README/architecture/user guidance: parallel generation is permitted and capability-bounded.
- The 2026-09-24 AI-owned design is amended to clarify that one action may be a bounded wave; no historical evidence is rewritten as if it had tested the new implementation.

## Tests

Add static and behavioral contract tests that prove:

- the active Skill no longer says one generator call per turn;
- default width is 5 and explicit width is 2–10;
- “parallel” is accepted rather than rejected;
- only independent pages sharing the same frozen scope enter a wave;
- five calls may be accepted in one wave while attempts increment once per accepted page;
- completion order may differ from publication order, and publication stops at the first unresolved predecessor;
- partial launch/capacity rejection consumes no attempt for unaccepted pages;
- resuming a wave does not redispatch accepted task IDs, duplicate attribution is idempotent, and conflicting attribution fails closed;
- sibling failure does not cancel or demote other pages;
- no shipped Python scheduler, queue, dashboard or polling loop is reintroduced;
- installers continue copying the exact Skill tree.

The behavior tests use pure in-memory wave fixtures/oracles in the test suite. They describe AI-owned coordination but are not packaged as production workflow code. Full repository tests and `git diff --check` remain required. Real multi-Agent overlap is a Host-level acceptance item and must be reported separately from static/oracle evidence.

## Non-goals

- Restoring `_generation_concurrency.py`, `ppt_concurrency.py`, legacy transactions/batches or the old adaptive planner.
- Allowing page Agents to read or write files, `run.json`, source maps or final SVGs.
- Parallel coordinator writes, unordered promotion or callback-owned state.
- Busy polling, invisible queues or unlimited fan-out.
- Changing page attempt budgets, content approvals, source-ID policy or editable-PPT behavior.
