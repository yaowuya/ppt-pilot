# AI-Owned Workflow and Non-Blocking Tools Design

**Date:** 2026-09-24
**Status:** Approved by the user on 2026-09-24.
**Scope:** `ppt-start`, its retained stateless tools, and the `ppt-editable` handoff. This design supersedes the fixed Python workflow/state-machine path for new and resumed work. Historical owner files remain readable evidence, not active control state.

## Problem

The current cleanup deletes the fixed workflow runtime, but several agent instructions, validators, and delivery adapters still require its commands and owner graph. That split architecture preserves the original failure modes:

- an answer such as “skip S01” still points at deleted `advance`/`--skip-slide` commands;
- review evidence still describes a deleted snapshot command as the only legal producer;
- new AI-maintained state cannot enter `ppt-editable` without legacy transaction and batch files;
- the retained SVG CLI fails on the supported Python 3.9 runtime and cannot distinguish final SVGs from pre-enrichment candidates;
- generator prompt rules disagree about whether transient block IDs exist.

Deleting scripts is therefore necessary but insufficient. The active instructions and the surviving tools must share one interface: **AI owns workflow state; tools only inspect or transform explicit artifacts.**

## Goals

1. AI is the only workflow coordinator and the only writer of `run.json`.
2. Packaged tools remain usable as stateless accelerators, but tool startup, dependency, compatibility, and internal failures never change workflow stage, consume generation attempts, or create an interaction deadlock.
3. A tool that successfully proves an artifact invalid may reject only that artifact/page; independent pages continue.
4. `ppt-editable` consumes the minimal AI state for complete or partial delivery without requiring new transaction/batch owners.
5. Legacy runs remain readable in place; unknown and historical fields are preserved, not recreated.
6. Agent-facing documents contain one executable path and no stale command-shaped sediment.
7. The retained Python surface runs on Python 3.9+ and has behavioral regression tests.

## Non-goals

- Reintroducing a workflow runner, scheduler, dashboard, host registry, retry budget engine, or hidden queue.
- Making invalid SVGs publishable merely because a tool is optional.
- Claiming renderer or Office verification when neither ran.
- Rewriting historical runs into the new schema.
- Making `ppt-editable` responsible for advancing or repairing `ppt-start` state.

## Selected approach: layered degradation

Every tool invocation has one of three semantic outcomes:

| Outcome | Meaning | Workflow effect |
|---|---|---|
| `PASS` | The requested deterministic operation completed and its checks passed. | Record optional evidence and continue. |
| `INVALID` | The tool completed and proved the supplied artifact malformed, unsafe, or contract-invalid. | Mark only the affected page/artifact failed; preserve prior final bytes; siblings continue. |
| `UNAVAILABLE` | The tool could not decide because it could not start, lacked a dependency, hit an unsupported environment, or failed internally. | Record the degradation; AI directly inspects the artifact and continues without claiming a tool PASS. |

Only structured tool output may establish `INVALID`. A nonzero exit without a recognized structured result is `UNAVAILABLE`, not evidence that the artifact is invalid.

A tool result never writes `run.json`, changes `stage`, creates `pending_interaction`, increments `slides[slide_id].attempts`, or chooses whether to retry/skip. A real generator call is the only event that increments a generation attempt.

## Agent information hierarchy

### Primary steps: `SKILL.md`

The main Skill contains the short ordered recipe every run needs:

1. select or create the run;
2. read current state and artifacts;
3. consume an answered interaction or choose the earliest executable action;
4. perform one action;
5. write artifact evidence, then atomically update state;
6. report the completed action, degradation, failures, and next action.

The main file points to references by branch:

- read `ai-state.md` whenever creating, resuming, skipping, retrying, or finalizing state;
- read `interaction-protocol.md` only when a user decision is required or an answered decision must be applied;
- read manuscript, visual, SVG, and delivery references only when entering those branches.

### State reference: `ai-state.md`

This is the single source of truth for stage, page state, failure locality, attempts, tool degradation, and delivery completeness. Other references link to it rather than restating its rules.

### Branch references

Each branch document contains only knowledge needed in that branch. Command names belonging to deleted programs, canonical owners that new runs no longer create, and duplicated state-transition prose are removed.

## AI state contract

A new run contains at least:

```json
{
  "schema_version": 1,
  "deck_id": "example",
  "mode": "guided",
  "stage": "production",
  "pending_interaction": null,
  "dirty_slides": ["S02"],
  "slides": {
    "S01": {
      "state": "promoted",
      "attempts": 1,
      "prompt": ".ppt-pilot/generation-prompts/S01.md",
      "svg": "slides/S01.svg",
      "failure": null,
      "qa": {
        "structure": "pass",
        "visual": "not_rendered",
        "tool": "pass"
      }
    },
    "S02": {
      "state": "failed",
      "attempts": 2,
      "prompt": ".ppt-pilot/generation-prompts/S02.md",
      "svg": null,
      "failure": {
        "code": "generator_unavailable",
        "message": "fresh-context generator could not start"
      },
      "qa": {
        "structure": "not_run",
        "visual": "not_rendered",
        "tool": "unavailable"
      }
    }
  },
  "delivery": {"status": "in_progress"}
}
```

`slides` is the authoritative partition owner. For a final run, its keys equal the storyboard target IDs exactly; their values are the per-page records. `delivery.status` is a conclusion, not a second slide inventory:

- `complete`: every target record is `promoted` and has a readable final SVG;
- `partial`: at least one target record is `promoted`, every remaining target record is `failed` or `skipped`, and each omission retains a nonempty failure record or an explicit user-skip record;
- `failed`: no target is deliverable;
- `in_progress`: work remains executable or awaits a decision.

The converter derives target order from the storyboard and the delivered/missing partition from `slides`. It does not require transaction IDs, batch manifests, dispatch records, or a third attempt.

Historical fields such as `visual_generation_transaction` and `active_visual_generation_batch` are retained byte-for-byte where practical but ignored as control state once a run uses the new `slides` map. A legacy run without the new map continues through a separate legacy adapter and its existing strict evidence checks.

## Interaction flow

A question is persisted before it is asked. On the next turn, AI performs this sequence directly:

1. read the pending object and the user answer;
2. atomically mark that object `answered` with the original answer and normalized decision;
3. apply the decision to its owning artifact/state;
4. append one idempotent history entry;
5. clear or replace the pending object in the same final state write;
6. choose the next executable action.

For `retry`, AI leaves existing failure evidence intact and starts one additional real generator call only if the page has attempts remaining. For `skip`, AI changes that page to `skipped`, records the user decision, leaves attempts unchanged, and immediately continues to the next independent action. No answer-consumption command exists.

## Manuscript review evidence

AI reads the five manuscript files directly and records the paths it actually reviewed. When a deterministic SHA-256 facility is available, AI records exact hashes. When hashing is unavailable, it records `unhashed` plus explicit `verification: ai_read` and rereads all five files before downstream use. Hash tooling is evidence assistance, not the authority to begin review.

The review record owns its schema. It does not claim to copy output from a deleted script, and semantic hashes are not mandatory unless a currently available deterministic implementation produced them. The hard content gate remains unchanged: unresolved `BLOCKER`/`HIGH` findings prevent visual production.

## Stateless SVG tool interface

`svg_tool.py` remains independent of any run directory and receives only explicit paths/values.

Required operations:

- `extract`: extract exactly one XML fence;
- `normalize-text`: apply deterministic text-role/vertical normalization;
- `validate --kind generator`: validate an XML-fenced, pre-enrichment generator response;
- `validate --kind candidate --source-map`: validate a raw candidate and its exact transient block-ID inventory;
- `validate --kind final`: validate a finalized SVG with machine-only source metadata;
- `finalize --input --output --source-map`: normalize a raw candidate, join transient block IDs to the explicit source map, remove block IDs, and validate final SVG before writing output.

A source-less content block still has a block ID and a source-map entry such as `{"S01-B1": []}`. Candidate validation therefore still requires its block-ID set to exactly equal the map keys; finalization removes the ID but adds no source metadata. An empty JSON object is valid only for a page with no content blocks. A final SVG is self-contained and does not require a source map.

Properties:

- Python 3.9+ compatible;
- writes use adjacent temporary files, flush/close, replace, and reread verification;
- `title_min_size` must be finite and within `34..4096`;
- `final` accepts valid machine-only `data-source-id` metadata and still rejects visible / zero-width-split `SRC-<digits>` and transient `S<digits>-B<digits>` text;
- generator/candidate forms reject preexisting source metadata;
- the tool emits one JSON result and never uses workflow words such as `BLOCKED` for its own availability;
- `PASS` exits `0`, deterministic `INVALID` exits `2`, and `UNAVAILABLE` exits `3`; each result contains `status`, `operation`, and `warnings`, with a stable `reason` on non-PASS results;
- a transformation publishes its output only on `PASS` and only to an absent destination: it validates a sibling temporary file before an atomic publish; a preexisting destination returns `UNAVAILABLE` unchanged, so AI can choose an explicit fresh path rather than silently replacing evidence;
- no operation reads or writes `run.json`, calls a model, starts a host task, or retries itself.

## Prompt and source handoff

`SRC-<digits>` identifiers never enter the generator prompt or visible text. Transient non-source `block_id` values are different: every content block, whether sourced or source-less, includes a stable block ID in injected narrative, and the generator echoes each only as `data-block-id` on its semantic `<g>`.

The `finalize` operation joins those blocks to the frozen source map, adds machine-only `data-source-id`, removes every `data-block-id`, and then validates the final SVG. If that tool is unavailable, the coordinator performs the same join directly and records degraded tool evidence. Documents must use these terms consistently:

- **source ID**: coordinator-only machine metadata, never sent to the generator;
- **block ID**: transient structural join key, sent to the generator but never visible to the audience.

## Editable delivery seam

`ppt-editable` is an optional post-processing module. Its interface is a finalized run directory; its result never mutates `ppt-start` stage.

For a new AI-state run, preflight:

1. parses the storyboard target order;
2. requires the `slides` map keys to equal the target IDs and derives delivered pages from records whose `state == "promoted"`;
3. derives missing pages from records whose state is `failed` or `skipped`, requiring a nonempty failure record or explicit skip decision respectively;
4. verifies `delivery.status` matches the derived complete/partial partition;
5. binds a normalized projection of the missing-page evidence into the editable input snapshot without creating transaction/batch owners;
6. validates manuscript approval and quality-report honesty;
7. converts only the delivered subset.

AI-state omissions use the distinct `{slide_id, reason, evidence_type: "ai_state", evidence}` result shape. Legacy omissions retain their existing transaction evidence shape unchanged.

A converter/tool failure returns a delivery result such as `BLOCKED`, `GENERATED_UNVERIFIED`, or `FAILED_VERIFICATION` for that optional operation. It does not downgrade a valid SVG run or reopen generation. The old delivery-object validator remains behind the legacy adapter only.

## Error locality

- Generator/tool/page QA errors are page-local.
- A malformed or internally contradictory `run.json`, unreadable approved manuscript, or storyboard/target mismatch is global because AI cannot safely determine the next action.
- `ppt-editable` errors are local to editable delivery.
- Missing renderer/Office capability produces `not_rendered`/`not_verified`, never a fabricated PASS.
- Tool availability is never a global blocker.

## Migration and deletion

- Remove active references to deleted runtime commands and documents.
- Do not add compatibility wrappers whose only job is to imitate deleted commands.
- Preserve historical data readers only where an existing run needs them.
- Delete tests whose sole subject is the removed state machine, scheduler, dashboard, host registry, or owner graph.
- Retain and adapt tests for source intake, SVG/XML safety, geometry, source metadata, installation, editable conversion, and artifact safety.

## Verification criteria

The change is complete only when all of the following are demonstrated:

1. No active Skill/reference/README instruction tells an agent to call a deleted workflow command or read a deleted reference.
2. A pending `skip S01` answer is consumed by direct AI-state rules with no helper command.
3. Tool startup/internal failure leaves stage and attempts unchanged and permits the next independent action.
4. Structured `INVALID` rejects only the affected page and preserves any prior final SVG.
5. SVG extraction and normalization work under Python 3.9.
6. A title floor below 34 or non-finite value is rejected.
7. Final SVG validation accepts legal machine-only source metadata and rejects visible source IDs.
8. New complete and partial AI-state fixtures enter `ppt-editable` without transaction/batch owners.
9. Historical delivery fixtures still use the legacy adapter.
10. Obsolete runtime tests are removed or rewritten, and the full supported suite passes.
11. Static tests do not claim live generator, renderer, or Office acceptance.
