# PPT Runtime Artifact Hygiene Design

**Date:** 2026-09-07

**Status:** Approved by user on 2026-09-07; implemented, locally verified and installed on 2026-09-08. Fresh-session live-host generation acceptance remains pending; see acceptance-evidence/2026-09-07/runtime-artifact-hygiene.md.

## Problem

PPT Pilot currently combines a detailed natural-language workflow contract with a small set of fixed helper programs. The contract says a new run root contains only `大纲.md`, `slides/`, and `.ppt-pilot/`, but the executable gate only rejects noncanonical state fields and misplaced PPTX files. It does not reject runtime-created Python, PowerShell, JavaScript, shell, binary, dependency, or cache artifacts.

The missing deterministic runtime operations also force host coordinators to recreate workflow glue. A read-only inventory of seven existing `ppt-output` trees under `<EXPERIMENTS_ROOT>` found 65 run-local scripts (`37 .py`, `27 .ps1`, `1 .js`) and 276 script/type files inside a run-local `node_modules`. None matched a packaged PPT Pilot tool by name or SHA-256. Typical files reimplemented prompt compilation, batch coordination, candidate recording, SVG validation, single-slide patching, native PowerPoint conversion, and diagnostics.

This is a workflow architecture defect. The defect is not that PPT Pilot uses Python; fixed, versioned programs in the installed Skill are appropriate. The defect is that a presentation run can create and retain new executable code or dependency trees.

## Goals

1. A PPT creation, redesign, resume, revision, QA, or delivery run never creates or executes run-local code.
2. All deterministic visual-generation mechanics that hosts currently recreate execute from the installed PPT Pilot Skill directory through one public runtime CLI.
3. Every workflow entry and stage transition detects pre-existing runtime code before consuming it.
4. Valid runs remain portable across Claude Code, Codex, and DeepSeek Harness.
5. Existing unexpected scripts are preserved for audit but never executed or silently deleted.
6. Project-level and user-level installations cannot silently select materially different PPT Pilot contracts after deployment.

## Non-goals

- Removing Python as the implementation language of packaged PPT Pilot tools.
- Treating short-lived atomic data files such as `run.json.<random>.tmp` as runtime code.
- Automatically deleting or migrating historical `ppt-output` directories.
- Giving an isolated SVG generator filesystem or data-tool access.
- Automating the model call itself inside a nested Claude, Codex, or DeepSeek CLI.
- Replacing `ppt-editable`; editable PowerPoint delivery remains a post-complete Skill.

## Considered approaches

### Policy text only

Add “do not create temporary scripts” to `SKILL.md`. This is inexpensive but cannot detect violations and leaves hosts without fixed replacements. Existing evidence shows instruction-only enforcement is insufficient.

### Gate-only denylist

Reject script extensions and dependency directories in `ppt_workflow_gate.py`. This prevents contaminated runs from proceeding, but a host that lacks prompt/state/validation helpers will simply stop instead of completing the workflow.

### Artifact firewall plus one fixed runtime facade

Add a universal artifact firewall and one public `ppt_runtime.py` facade backed by focused internal modules. This is the selected approach. It provides an enforceable boundary while moving repeatedly reinvented deterministic logic out of tests and one-off run scripts.

A fully monolithic autonomous engine was rejected: host-specific model dispatch and approval interaction must remain outside the deterministic runtime, while file/state mechanics belong inside it.

## Artifact boundary

### Allowed locations

- Packaged executable code exists only below the installed Skill's `scripts/` directory.
- A new run root contains `大纲.md`, `slides/`, and `.ppt-pilot/`.
- `.ppt-pilot/` contains only declarative Markdown, JSON, SVG, PNG, plain-text generator responses, prompt, transaction, batch, QA, and dashboard state described by the artifact contract.
- `.ppt-pilot/runtime-inputs/` may contain only contract-owned declarative request, capability, returned-text, and QA input files. These are non-authoritative staging data rather than throwaway programs; canonical prompt, transaction, manifest, candidate, and QA owners remain authoritative.
- `delivery/editable/` may contain post-complete PPTX output produced by `ppt-editable`.
- Atomic writers may create adjacent data temp files and must rename or remove them before returning.

### Forbidden run artifacts

At any depth below a run directory, reject files whose case-insensitive suffix chain contains any of:

```text
.py .pyw .pyc .pyo .ps1 .psm1 .psd1
.js .mjs .cjs .jsx .ts .tsx
.sh .bash .zsh .fish .bat .cmd .vbs .vbe .wsf .wsh .hta
.rb .pl .php .lua .r .jar .exe .com .scr .msi .dll
.html .htm .css .scss .less
```

Checking the full suffix chain rejects disguised leftovers such as `helper.py.tmp`.

Reject directories named, case-insensitively:

```text
node_modules __pycache__ .venv venv env vendor
```

This executable denylist supplies the stable `runtime_code_artifact` classification, but it is not the whole artifact firewall. Every other file and directory must also be admitted by the path-level artifact contract; an unrecognized artifact fails with `unexpected_run_artifact`. This prevents an extensionless script, renamed archive, notebook, package, or future executable format from bypassing the fixed suffix list. A bound external source PPTX located inside the run and post-complete `delivery/editable/` files retain their existing explicit exceptions.

The gate must not follow symbolic links or junctions. A linked entry remains an unsafe evidence error under the existing path rules.

The host must never pass any file below the run to an interpreter, module loader, shell source command, dynamic plugin loader, macro host, or code-evaluating template engine. Runtime data is parsed only by fixed safe parsers in the installed Skill. This execution rule applies even when a file has an allowed data extension or no extension.

### Error contract

A runtime-code conformance failure returns:

```json
{
  "status": "BLOCKED",
  "errors": [
    {
      "code": "runtime_code_artifact",
      "reentry_stage": "<current canonical stage>",
      "next_action": "Quarantine unexpected runtime code outside this run, then repeat the same gate.",
      "artifacts": ["normalized/run-relative/path"]
    }
  ]
}
```

Paths are normalized run-relative paths, sorted deterministically, and capped in the human message while the structured list remains complete. Detection is read-only.

Historical runtime code is never executed. Recovery may move it only after explicit user authorization to a sibling `ppt-output/.quarantine/<deck-id>-runtime-code-<timestamp>/` directory with a JSON manifest containing original relative paths, byte sizes, and SHA-256 values. The normal gate does not perform this move.

## Universal gate behavior

`Gate.conformance()` becomes a common run invariant rather than an external-source-only check.

- `--audit-run` always evaluates it.
- Every `--before <stage>` evaluates it immediately after `run.json` is loaded, including ordinary runs without `source_deck`.
- `--snapshot` evaluates it before returning hashes; a contaminated run returns `BLOCKED`, not a diagnostic snapshot that can be mistaken for approval.
- Clean ordinary runs retain `NOT_APPLICABLE` for source-specific evidence checks, but contaminated ordinary runs return `BLOCKED` before that result.
- `--resume-active-batch` evaluates it before reading or advancing the active owner.
- Script checks apply in every stage, including `complete`.
- Packaged Skill tools are outside the run tree and therefore never trigger the gate.

`--before` retains its current `research` through `complete` choices; the initial `brief` stage is covered by mandatory `--audit-run` immediately after the minimal `run.json` is created. Tests must not imply that `--before brief` exists.

The same implementation is reused as a library invariant rather than being reimplemented by callers:

- every mutating `ppt_runtime.py` command runs it before consuming returned model text and again under the same run lock immediately before its first write;
- `promote` repeats it immediately before final-file CAS;
- `ppt-editable` runs it as a mandatory preflight before creating `delivery/editable/` output;
- a failed invariant produces zero runtime, candidate, final, delivery, generator, renderer, or Office side effects.

`SKILL.md`, workflow references, and acceptance documentation require the same audit for new, resume, revise, stage entry, active-batch recovery, and delivery entry points. The contract must state that inline shell/Python expressions may be used only when they do not persist executable files; fixed CLI calls are preferred.

## Fixed runtime architecture

### Public entry point

`skills/ppt-start/scripts/ppt_runtime.py` is the only new public runtime program. It uses Python 3.9+ and emits exactly one JSON document to stdout. Success exits `0`; a valid workflow block or state conflict exits `2`; malformed invocation exits through argparse.

Existing single-purpose public tools such as source intake, workflow gate, concurrency planning, dashboard, and post-complete editable delivery remain public. The facade replaces host-invented prompt compilation, visual-generation state transitions, candidate ingestion, and promotion glue; it does not wrap or duplicate those established tools.

It never imports `tests.*`, invokes a nested AI CLI, installs packages, starts Office, follows links, or executes anything from the run directory.

### Internal modules

`scripts/_run_store.py`

- owns safe run-relative path resolution and no-follow checks;
- canonical JSON serialization;
- adjacent temp + atomic replace;
- close, reread, SHA-256 verification;
- compare-and-swap checks for `run.json`, transaction, manifest, candidate, and final files.

`scripts/_artifact_firewall.py`

- owns the single path-policy table and executable classifications used by the workflow gate, runtime facade, and editable-delivery preflight;
- validates links, junctions, full suffix chains, dependency directories, and contract-admitted path classes;
- performs no writes and never imports or executes run content.

`scripts/_host_adapter_runtime.py`

- validates a host capability receipt against a versioned packaged adapter registry;
- selects the adapter-specific exact observation/evidence schema;
- rejects unknown host, adapter, version, digest, or evidence combinations;
- contains no generic “trust these booleans” escape hatch.

`scripts/_prompt_runtime.py`

- owns style registry/manifest/tokens/guidance/prompt traversal;
- validates the single whole-line `{{NARRATIVE}}` injection contract;
- compiles canonical prompt body and nine-field envelope;
- derives prompt/body/template snapshot identities;
- rejects source annotations, raw answers, absolute paths, stale revisions, and legacy markers.

The implementation is migrated from tested helpers in `test_redesign_prompt_contract.py`; tests then import production functions rather than keeping a second implementation.

`scripts/_svg_runtime.py`

- extracts exactly one fenced XML SVG from generator text;
- performs pre-enrichment XML, Office-safe element/attribute, active-content, canvas, geometry/text, and block-ID checks;
- joins canonical block IDs to ordered source IDs from durable batch input;
- removes all temporary `data-block-id` attributes;
- performs post-enrichment validation and canonical serialization;
- never writes a candidate until every check succeeds.

`scripts/_generation_runtime.py`

- validates schema-v2 per-slide transactions and batch manifests;
- derives transaction refs and rebuilds cursors;
- plans dispatch without making the host call;
- records stable host attribution exactly once per dispatch epoch;
- owns pre-spawn dispatch reservations and post-spawn task binding without changing the exact schema-v2 manifest field set;
- records candidate, validation, failure, and promotion transitions;
- performs ordered promotion CAS while preserving prior final SVG;
- preserves the existing deterministic v1-to-v2 migration behavior.

The implementation is migrated from tested helpers in `test_visual_generation_contract.py`; the tests become consumers of production code.

### Commands

```text
ppt_runtime.py prepare-batch --run-dir R --input INPUT.json --capability CAPABILITY.json
ppt_runtime.py dispatch-plan --run-dir R --batch-id B --capability CAPABILITY.json
ppt_runtime.py reserve-dispatch --run-dir R --batch-id B --slide-id S --transaction-id T --capability CAPABILITY.json
ppt_runtime.py bind-task --run-dir R --dispatch-id D --host-task-id H
ppt_runtime.py ingest-result --run-dir R --dispatch-id D --response RESPONSE.txt
ppt_runtime.py record-generator-failure --run-dir R --dispatch-id D --reason REASON
ppt_runtime.py record-validation --run-dir R --slide-id S --transaction-id T --input QA.json
ppt_runtime.py prepare-recovery --run-dir R --slide-id S --transaction-id T --mode MODE
ppt_runtime.py promote --run-dir R --batch-id B --expected-manifest-sha256 H
ppt_runtime.py publish-anchors --run-dir R --batch-id B --expected-manifest-sha256 H
ppt_runtime.py resume --run-dir R
ppt_runtime.py migrate-v1 --run-dir R
```

Inputs are declarative data, not executable code. Every path supplied through `--input`, `--capability`, or `--response` must be a safe run-relative path below the contract-owned `.ppt-pilot/runtime-inputs/` directory; absolute paths, links, traversal, and paths outside the run are rejected. The runtime closes and fully rereads each input, computes its SHA-256, validates its complete schema, and only then derives the existing schema-v2 snapshots and owners. It must not add ad-hoc fields to the exact schema-v2 transaction or manifest. After a successful state commit, recovery depends only on canonical owners, never on mutable staging input. Runtime input files contain no commands, external paths, credentials, raw conversation history, or executable fields. The runtime never imports, invokes, or interprets them as code.

The staging-input hash is diagnostic, not a new durable owner. Existing canonical identities remain authoritative: prompt inputs derive `prompt_snapshot_id` and `compiled_prompt_sha256`; accepted generator text derives the normalized `candidate_sha256`; QA input must name the current `transaction_id` and `candidate_sha256`, and its exact six check outcomes are copied into the existing `validation` owner. Capability input is preflight-only and telemetry remains non-authoritative. This deliberately preserves the exact schema-v2 transaction and manifest field sets.

Dispatch crash safety uses a separate fixed owner rather than adding partial host fields to schema-v2 transactions:

```text
.ppt-pilot/visual-generation-dispatches/<slide-id>-<tx64>-e<dispatch-epoch>.json
```

It has exactly `schema_version`, `kind`, `batch_id`, `slide_id`, `transaction_id`, `dispatch_epoch`, `dispatch_id`, `host`, `adapter_id`, `adapter_version`, `host_attribution_id`, `state`, `host_task_id`, `created_at`, and `updated_at`. `state` is `reserved` or `bound`; only `bound` has a task ID. `dispatch_id` and `host_attribution_id` are deterministic hashes of batch, transaction, epoch, host, and adapter identity. Scheduler capacity and resume logic count both reserved and bound dispatch owners, so a transaction cannot be selected twice during a crash window. Binding then atomically projects both non-null host fields into the unchanged exact schema-v2 transaction.

Recovery clarification: recompose/fallback replaces the shared per-slide prompt path while preserving exact schema-v2 fields. Before replacement, the runtime therefore writes and verifies one closed canonical recovery journal at `.ppt-pilot/visual-generation-recoveries/<slide-id>-<oldtx64>.json`. It binds old/new prompt bytes and hashes, old/new transaction references, validated replacement transaction/manifest, and expected run/manifest identity. The focused runtime owner reference defines the exact schema. This is runtime-owned crash evidence, never caller-authored staging authority or a generic state replacement facility. Exact replay completes an interrupted transaction/manifest publication without manual JSON repair; conflicting third-party bytes block without overwrite. Completed journals remain immutable audit data. The shared artifact firewall admits only this fixed declarative path class; no existing transaction or manifest fields change.

### Exact request boundary

`INPUT.json` has exactly `schema_version`, `kind`, `request_id`, `expected_run_sha256`, `expected_snapshots`, `ordered_slide_ids`, and `generation_operations`. `schema_version` is `1`, `kind` is `prepare_visual_generation_batch`, and `expected_snapshots` has exactly the storyboard, theme, source-audit, and generation-template snapshot identities. Each operation has exactly `slide_id`, `generation_intent`, and `generation_trigger_id`. Narrative, source mappings, theme values, prompt templates, and revision projections are never accepted from the host request; the runtime reads them from the run's canonical owners and rejects snapshot disagreement.

`request_id` is `sha256:` plus the canonical JSON digest of `schema_version`, `kind`, `expected_snapshots`, `ordered_slide_ids`, and `generation_operations`; the mutable CAS precondition `expected_run_sha256` is deliberately excluded. The canonical `batch_id` is derived from the full request digest. On `prepare-batch`, the runtime first looks for that deterministic batch identity: a complete byte-equivalent owner graph is an idempotent no-op even though `run.json` has advanced; a partial or differing graph is `visual_generation_state_conflict`. Only when no matching graph exists does it enforce `expected_run_sha256` and create owners.

`CAPABILITY.json` has exactly `schema_version`, `kind`, `host`, `adapter_id`, `adapter_version`, `adapter_digest`, `observation`, and `evidence`. `observation` uses the existing exact capability fields: `native_fresh_isolation`, `remote_fresh_isolation`, `concurrent_tasks`, `durable_lookup`, `worker_capacity`, `prompt_by_value`, `fresh_history`, `filesystem_none`, `data_tools_none`, `attribution`, `nested_cli_required`, `credential_probe_required`, and `current_context_only`. The packaged adapter registry selects an exact evidence schema and approved digest for the named host/adapter/version; unknown or missing fields fail closed.

Claude Code accepts only the packaged `ppt-svg-generator` adapter whose installed Agent digest matches the registry. Codex accepts only a host-native adapter version that has its own checked-in contract and fresh-session acceptance evidence. No DeepSeek adapter is currently registered, so `host: deepseek` deterministically returns the canonical `generator_unavailable` blocker regardless of self-reported booleans. Enabling DeepSeek generation later requires shipping and acceptance-testing a real adapter registry entry; editing `CAPABILITY.json` alone can never enable it.

`QA.json` has exactly `schema_version`, `kind`, `slide_id`, `transaction_id`, `candidate_sha256`, `checks`, `defect_id`, and `failure_reason`. `checks` has exactly `xml`, `office`, `geometry_text`, `fact_source`, `narrative`, and `visual`; values use the existing validation vocabulary. Passing evidence has null `defect_id` and `failure_reason`. Failed evidence names one stable defect and one existing matching failure reason. It cannot carry shell commands, arbitrary output paths, or replacement state.

Every successful response contains exactly one JSON object with `status`, `command`, `run_sha256`, `state`, `writes`, and `next_action`; command-specific read-only values such as ordered dispatch items may appear only below `result`. Every blocked response contains `status: BLOCKED`, a stable error code, observed hashes, and an accurate `writes` list. Conformance and precondition errors preserve hashes and write nothing. When a command records a contract-authorized canonical blocker or failure, or reports an interrupted multi-file commit, it must disclose those observed writes rather than falsely reporting zero. These response envelopes and all error codes are contract-tested.

### Command state and idempotency

| Command | Accepted owner state | Writes and replay behavior |
|---|---|---|
| `prepare-batch` | no active batch and matching approved canonical inputs | Derives prompts and schema-v2 owners, then commits prompt → transactions → manifest → pointer. Stable request/batch identity makes exact replay a no-op after the CAS-changing commit; differing prepared bytes are `visual_generation_state_conflict`. Unsafe or unregistered capability writes only the existing canonical blocker allowed by the contract. |
| `dispatch-plan` | valid active batch | Read-only ordered plan. It returns complete prompt bytes by value and never spawns work. |
| `reserve-dispatch` | eligible `compiled` transaction or contract-authorized retry transition | Before spawn, atomically creates the canonical dispatch reservation with a deterministic attribution ID. Exact replay returns the same reservation; another reservation for the epoch is blocked. |
| `bind-task` | matching reserved dispatch | After spawn, binds exactly one host task ID, then projects both host IDs into the transaction together. Exact replay is a no-op; a different task ID is blocked. |
| `ingest-result` | matching bound/generating dispatch | Parses returned text in memory. Valid output atomically writes candidate then hash/state; malformed output records the existing failure reason with zero candidate/final writes. |
| `record-generator-failure` | matching bound/generating dispatch | Accepts only `generator_refused`, `generator_timeout`, or `generator_unavailable`; atomically records failure. Exact replay is a no-op. |
| `record-validation` | matching `candidate_written` transaction and candidate hash | Copies the six validated outcomes into the exact existing validation owner and transitions to `validated` or the matching failed state. It never edits SVG. |
| `prepare-recovery` | matching failed transaction | Implements only the recovery table already defined by the artifact contract. `retry` reuses unchanged authoritative inputs within the attempt limit; `recompose` or `fallback` creates the next canonical prompt/owner; conflicts and exhausted attempts stop. It returns dispatch work by value and never performs the host call. |
| `promote` | named batch with ordered validated transactions and matching manifest hash | Performs ordered final CAS and owner updates. The stable batch identity lets a completed old request replay as a no-op after its active pointer is cleared; a different active batch or third-party final bytes block. |
| `publish-anchors` | anchor-stage batch with validated candidate bytes and matching manifest hash | CAS-publishes sample SVGs under the canonical samples directory, retains validated transactions and active manifest, and returns sample hashes for the existing approval flow. It never publishes final slides or fabricates anchor approval. |
| `resume` | any valid canonical owner graph | Read-only validation and next-action projection. It never repairs JSON directly or invents state. |
| `migrate-v1` | a valid legacy visual-generation transaction with no conflicting v2 pointer | Explicit deterministic, model-free pointer-last migration. Byte-equivalent prepared owners are reused, conflicts are zero-write blocks, and an already completed matching migration is a no-op. |

`MODE` is exactly `retry`, `recompose`, or `fallback`; `REASON` is restricted as above. QA failure recovery never authorizes a run-local patch program. A truly supported deterministic patch must be a named, versioned operation implemented in the installed runtime; otherwise the workflow recompiles a canonical recompose/fallback prompt.

`prepare-batch` performs all deterministic in-memory preflight and capability validation before writes. On success it uses the existing pointer-last order: prompt and transaction files, then manifest, then the `run.json.active_visual_generation_batch` pointer.

`dispatch-plan` is read-only and returns ordered eligible slide IDs plus prompt text by value. The host performs only the attributed isolated model call.

`reserve-dispatch` persists a deterministic attribution ID before the host call. The host passes that ID into the native spawn operation, then `bind-task` persists the returned task ID. A crash after reservation but before spawn never authorizes a second reservation. A crash after spawn but before binding must resolve the existing task through durable lookup by attribution; when lookup is unavailable, the reservation stays blocked for explicit user resolution and is never blindly respawned.

Implementation clarification: `reserve-dispatch` revalidates the explicit capability receipt to bind host and adapter identity. The preflight-only receipt is not copied into a new durable owner, and the runtime does not infer the host from an earlier process invocation or mutable staging-file discovery.

`ingest-result` consumes returned text, validates and enriches SVG in memory, then atomically writes the candidate and its hash.

`record-validation` accepts declarative renderer/visual-review evidence, validates it, and advances only the named transaction.

`record-generator-failure` closes the no-response paths without asking the host to edit transaction JSON. `prepare-recovery` owns all allowed failed-state transitions, attempt increments, prompt recompilation, and fallback owner creation.

`promote` uses the manifest order and final-file CAS. It never promotes an unvalidated candidate.

Implementation clarification: anchor generation precedes anchor approval. `publish-anchors` supplies that sample-only publication boundary without changing the exact v2 `final_path`. `promote` is blocked at the anchor stage; formal publication requires the existing anchor approval/validation and production-stage authorization. Ordinary runs use their existing `run.anchor` owner, while source-deck runs retain `evidence.anchor`; both must bind sample file hashes, selected style bytes and the current formal review snapshot. Guided runs require a matching applied approval interaction, while auto runs require validated evidence. A stage field alone is insufficient. The existing `min(2, target slide count)` sample rule applies to one-page runs. Hosts do not copy candidates using ad-hoc programs.

Guided approval binding recomputes the canonical digest of the actual sample-file hash map, style hash and formal-review snapshot and requires both the anchor owner and applied approval to name that digest. This applies to the source gate as well as ordinary runtime promotion. Merely equating two supplied opaque snapshot IDs is insufficient. Legacy opaque/unbound anchor IDs require a new actual approval; the runtime must not retrofit a new digest onto an old decision.

`resume` validates the complete owner graph and returns the next deterministic action; it does not call a model or invent missing state.

When canonical prerequisites allow a new batch, `resume.result.prepare_request` supplies the exact declarative prepare request, including canonical request ID, current run hash and expected snapshots. All hashes are calculated by the packaged runtime. Hosts persist this returned data under runtime-inputs rather than reimplementing canonicalization or request hashing.

Implementation clarification: `migrate-v1` is a separate mutating command so legacy conversion does not weaken the explicitly read-only `resume` contract. It reuses the existing deterministic migration validator and never obtains replacement state from host-authored executable glue.

Implementation clarification: the existing resolver reports `style_asset_malformed` for malformed guidance as well as malformed tokens. That existing blocker reason may therefore name the verified selected `assets/styles/<style-id>/STYLE.md` or `tokens.json`; `style_asset_schema_unsupported` remains tokens-only. The resolver must carry its actual safe resource identity in a structured error, so canonical blocker persistence never guesses a path from exception text or misattributes a guidance error to tokens.

## Host responsibilities

The coordinator remains responsible for user interaction and the host-native isolated task call. It may:

1. write only contract-owned declarative inputs;
2. call installed PPT Pilot CLIs by absolute Skill path;
3. pass Prompt bytes by value to a supported isolated generator;
4. pass returned generator text to `ppt_runtime.py ingest-result`;
5. render SVG through an approved non-Office renderer and submit declarative QA evidence.

It may not create scripts, install dependencies, copy a packaged tool into a run, import code from a run, invoke PowerPoint/WPS before the existing delivery boundary, or repair the installed Skill during a presentation run.

DeepSeek continues to fail closed with canonical `visual_generation_blocker` when its actual call surface cannot prove the isolation contract. The runtime facade does not weaken that boundary.

## Deployment and packaging

`tools/update-hosts.ps1` separates its immutable repository source root from installation targets and must verify and synchronize all selected discovery scopes:

- user-level Claude Code, Codex, and DeepSeek installations;
- project-level `.claude/skills` and `.agents/skills` in the source repository when those directories already exist;
- every additional explicit `-ProjectRoot` target, without recursively scanning drives or guessing unrelated projects.

Existing project copies in a selected project root are synchronized by default; the current opt-in `-ProjectClaude` and `-ProjectCodex` behavior is removed for those existing roots. Before copying, the updater inventories every host discovery path inside the selected user and project roots. If an additional shadowing path is detected inside those roots but cannot be updated, deployment fails with the path and does not claim success.

The installer excludes `__pycache__`, `.pyc`, `.pyo`, test caches, and other ignored build residue from package copies and tree digests. Installed trees are compared to a filtered source inventory. Claude's `ppt-svg-generator` remains a readless/writeless text generator.

Deployment reports each installed scope, plugin version, file count, and digest. A new session is required after skill or agent replacement.

Each destination update is backup-and-restore atomic. If different host destinations produce a mixed result, the overall command exits nonzero with `PARTIAL_FAILURE` and lists `updated`, `rolled_back`, and `failed` destinations; it never prints “全部完成”. Rerunning with the same source converges safely. Static digest equality is necessary but fresh-session acceptance must additionally record the actual loaded Skill/Agent path and digest.

## Compatibility and migration

- Clean schema-v1 runs keep their existing paths and resume semantics.
- A historical run containing runtime code becomes `BLOCKED`; no file is deleted or executed.
- Short-lived atomic data temp files that remain after a crash are handled by their owning state recovery and are not classified as executable merely because they end in `.tmp`.
- Files such as `helper.py.tmp` are classified as executable because their full suffix chain contains `.py`.
- Legacy prompt and transaction migration remains deterministic and model-free.
- Current source-deck checks keep their existing PASS/BLOCKED semantics after the common conformance check.

## Testing strategy

### Artifact firewall

- table-driven coverage for every forbidden extension, mixed case, nested paths, and disguised suffixes;
- extensionless shebang/code payloads and attempts to pass any run file to an interpreter or dynamic loader;
- forbidden dependency/cache directories;
- ordinary and source-driven runs;
- `brief` through `complete` stages;
- audit and stage gates remain read-only;
- packaged scripts outside the run do not trigger;
- valid atomic data temp names are not misclassified.

### Runtime modules

- migrate existing prompt, transaction, manifest, source-enrichment, and migration tests to import production modules;
- add CLI integration tests for JSON stdout, exit codes, no-follow behavior, atomic write order, reread/hash checks, crash recovery, idempotency, and CAS conflicts;
- prove that a forged or unknown host capability receipt, including any DeepSeek receipt while no adapter is registered, yields the canonical blocker with zero generation writes;
- inject crashes before reservation, after reservation/before spawn, after spawn/before bind, and after bind; prove that no `(transaction, epoch)` can spawn twice;
- replay `prepare-batch` after its own pointer-changing commit and `promote` after pointer clearance; prove exact no-op for the named identity and conflict for differing bytes or batches;
- assert failure before candidate/final writes for malformed model output or source mapping;
- assert every runtime write remains inside the selected run, the installed Skill root remains read-only, and no command creates a script or dependency directory anywhere below the run.

### Packaging and hosts

- installer tests seed `__pycache__` and confirm it is excluded;
- project-level stale copies are replaced when their selected roots already exist;
- all selected user-level, project-level, plugin, and Claude Agent trees match their filtered source digest;
- partial multi-host failure is explicit, nonzero, and never reported as complete;
- fresh-session host acceptance remains separate from static package verification.

### Host acceptance matrix

Each of Claude Code, Codex, and DeepSeek Harness is exercised in a fresh session for new generation, source-deck redesign, resume, revise, and editable-delivery entry. Every case records the actually loaded Skill path/digest, common conformance result, runtime command envelopes, and resulting run inventory. DeepSeek without a proven isolation surface must produce the canonical `visual_generation_blocker` with zero generator, script, dependency, candidate, native PPTX, or Office side effects. Project-level override cases must prove the loaded path is the synchronized project copy rather than merely proving that a user-level copy exists.

## Success criteria

1. A minimal run containing `scratch.py`, `helper.PS1`, `build.js`, `helper.py.tmp`, or `node_modules/` is blocked deterministically by every relevant gate.
2. A clean ordinary run still reports source checks as `NOT_APPLICABLE` after passing common conformance.
3. Prompt compilation, candidate ingestion, transaction validation, and ordered promotion run through packaged production modules rather than test helpers or run-local scripts.
4. The complete automated test suite passes.
5. Filtered source and installed Skill digests match for user-level and existing project-level Claude Code/Codex plus DeepSeek.
6. The full fresh-session host acceptance matrix creates no executable file or dependency directory below `ppt-output/<deck-id>/`, and no run file is ever evaluated as code.
7. Historical contaminated runs are reported and preserved; no automatic deletion occurs.
