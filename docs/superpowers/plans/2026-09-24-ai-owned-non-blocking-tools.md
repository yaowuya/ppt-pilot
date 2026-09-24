# AI-Owned Non-Blocking Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PPT Pilot AI-owned end-to-end: retained packaged tools provide stateless, non-blocking artifact operations; real artifact defects remain page-local; new complete and partial AI-state runs can produce editable PPTX without legacy state-machine owners.

**Architecture:** The workflow seam remains the agent-facing `run.json` contract; no Python module advances stages, consumes answers, schedules workers, or owns retries. Stateless CLI tools expose one three-state outcome interface (`PASS`, `INVALID`, `UNAVAILABLE`) over explicit files only. `ppt-editable` selects either a legacy explicit-delivery adapter or a new AI-state adapter, so historic evidence stays strict while new runs use the lightweight `slides` partition.

**Tech Stack:** Python 3.9+ standard library, `unittest`, PowerShell installation scripts, existing `python-pptx`/Pillow optional editable-delivery dependencies.

## Global Constraints

- AI is the sole workflow coordinator and the only writer of `.ppt-pilot/run.json`.
- A packaged tool must never advance a stage, create `pending_interaction`, consume a generator attempt, schedule/retry work, or read/write `run.json`.
- Every stateless tool returns exactly one JSON object: `PASS` exits `0`, deterministic artifact `INVALID` exits `2`, and environment/internal `UNAVAILABLE` exits `3`.
- Only a structured `INVALID` can reject an artifact; an unstructured tool crash is `UNAVAILABLE`.
- A real fresh-context generator call is the only operation allowed to increment `slides[slide_id].attempts`.
- New final runs use `slides` as the exact storyboard-keyed page inventory and `delivery.status` as a derived conclusion; they never create transaction, batch, dispatch, recovery, or runtime-input owners.
- Legacy state-machine fields and legacy explicit delivery objects remain readable evidence. Do not migrate, recreate, or silently reinterpret them as new state.
- Python 3.9 compatibility is required; no new third-party runtime dependency.
- Internal `SRC-<digits>` stays machine-only in final SVG `data-source-id` metadata and never appears in generator prompts or visible text.
- Never claim rendering, Office verification, or a live-host behavior that was not actually executed.
- Preserve existing user changes and do **not** commit, push, install into user locations, or alter external worktrees during this implementation.

---

## File structure and module seams

| File | Responsibility after this change |
|---|---|
| `skills/ppt-start/scripts/_svg_runtime.py` | Pure SVG lifecycle validation and source/block metadata transformation. No I/O, run state, model, or host behavior. |
| `skills/ppt-start/scripts/svg_tool.py` | Small CLI adapter over `_svg_runtime`: parse explicit files, classify outcomes, perform atomic output publication. |
| `skills/ppt-start/scripts/ppt_source_intake.py` | Small CLI adapter for the existing safe PPTX extractor, with the same non-blocking outcome vocabulary. |
| `skills/ppt-editable/scripts/_ppt_editable/contract.py` | Delivery-selection seam and adapters: legacy implicit, legacy explicit, and new AI-state selection. |
| `skills/ppt-editable/scripts/_ppt_editable/model.py` | Immutable delivery omission shapes, including a distinct AI-state omission type. |
| `skills/ppt-editable/scripts/_ppt_editable/{snapshot.py,orchestrator.py,atomic_io.py}` | Bind, serialize, restore, and validate the selected adapter's omission shape without changing legacy records. |
| `skills/ppt-start/SKILL.md` + references | Short executable agent recipe and progressively disclosed branch rules. `ai-state.md` is the sole state reference. |
| `tests/test_svg_tool.py` | Process-level behavior of the retained SVG CLI. |
| `tests/test_ai_workflow_contract.py` | Agent-instruction contract: no deleted workflow commands, direct interaction consumption, and layered tool degradation. |
| `tests/fixtures/ppt-editable/run-ai-state-{complete,partial}/` | Minimal new-state converter fixtures, independent of transaction/batch evidence. |

The four implementation tasks below form one migration rather than four independent features: the direct AI state defined in the documents is the state consumed by the editable adapter; the stateless tools are evidence producers only.

---

### Task 1: Make retained artifact tools Python-3.9-safe and non-blocking

**Files:**
- Create: `tests/test_svg_tool.py`
- Modify: `skills/ppt-start/scripts/_svg_runtime.py`
- Modify: `skills/ppt-start/scripts/svg_tool.py`
- Modify: `skills/ppt-start/scripts/ppt_source_intake.py`
- Modify: `tests/test_runtime_modules.py`
- Modify: `tests/test_svg_arc_bounds.py`
- Modify: `tests/test_jiawei_prompt_fidelity.py`
- Modify: `tests/test_source_intake.py`
- Modify: `tests/test_installed_svg_runtime_normalization_regression.py`

**Interfaces:**
- Consumes: explicit input/output paths and an explicit UTF-8 JSON source map; no run directory or state object.
- Produces from `_svg_runtime.py`:

```python
def validate_title_min_size(value: object) -> float: ...
def validate_generator_svg(generator_output: str, *, title_min_size: float) -> str: ...
def validate_candidate_svg(
    svg_text: str,
    source_map: Mapping[str, Sequence[str]],
    *, title_min_size: float,
) -> str: ...
def validate_final_svg(svg_text: str, *, title_min_size: float) -> str: ...
def finalize_candidate_svg(
    svg_text: str,
    source_map: Mapping[str, Sequence[str]],
    *, title_min_size: float,
) -> bytes: ...
```

- Produces from `svg_tool.py`:

```text
extract --input INPUT --output OUTPUT
normalize-text --input INPUT --output OUTPUT [--title-min-size N]
validate --kind generator --input INPUT [--title-min-size N]
validate --kind candidate --input INPUT --source-map MAP [--title-min-size N]
validate --kind final --input INPUT [--title-min-size N]
finalize --input INPUT --output OUTPUT --source-map MAP [--title-min-size N]
```

Every non-help invocation writes one object shaped like:

```json
{"status":"PASS|INVALID|UNAVAILABLE","operation":"finalize","warnings":[],"reason":"..."}
```

`reason` is absent on `PASS`. `INVALID` is limited to deterministic input/contract violations. Missing files, permission failures, temporary-write/replace/reread failures, missing imports, and unexpected exceptions are `UNAVAILABLE`.

- Produces from `ppt_source_intake.py`: the same status/exit-code envelope around the existing deterministic inventory output, with atomic output publication on `PASS` only.

- [ ] **Step 1: Write process-level failing tests for the SVG tool contract.**

Create `tests/test_svg_tool.py` with a temporary valid raw candidate, a generator-fenced version, a source map, and a final SVG. Cover the actual CLI through `subprocess.run`, not only helper functions:

```python
def invoke(self, *args):
    return subprocess.run(
        [sys.executable, "-B", str(self.script), *args],
        cwd=str(self.script.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

def test_finalizes_candidate_without_leaking_block_ids(self):
    result = self.invoke(
        "finalize", "--input", str(self.candidate), "--output", str(self.final),
        "--source-map", str(self.source_map),
    )
    self.assertEqual(result.returncode, 0, result.stderr)
    payload = json.loads(result.stdout)
    self.assertEqual(payload["status"], "PASS")
    text = self.final.read_text(encoding="utf-8")
    self.assertNotIn("data-block-id", text)
    self.assertIn('data-source-id="SRC-001"', text)

def test_rejects_nan_and_underfloor_title_size(self):
    for value in ("0", "33", "nan", "inf", "4097"):
        result = self.invoke("validate", "--kind", "candidate", "--input", str(self.candidate),
                             "--source-map", str(self.source_map), "--title-min-size", value)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "INVALID")

def test_unavailable_write_preserves_prior_destination(self):
    self.final.write_bytes(b"prior-final")
    with mock.patch("svg_tool._publish_text", side_effect=OSError("full")):
        result = svg_tool.main([...])
    self.assertEqual(result, 3)
    self.assertEqual(self.final.read_bytes(), b"prior-final")
```

Add cases for exactly-one-JSON stdout, no `BLOCKED` status, generator/candidate rejection of preexisting `data-source-id`, final acceptance of legal `data-source-id`, final rejection of `data-block-id` and visible `SRC-001`, malformed XML/fence/map as `INVALID`, and unreadable input as `UNAVAILABLE`.

- [ ] **Step 2: Run the new tests and verify the expected red failures.**

Run:

```bash
python -B -m unittest tests.test_svg_tool -v
```

Expected: failures showing that `svg_tool.py` does not recognize `--kind`/`finalize`, produces `BLOCKED`, accepts `nan`, and Python 3.9's `Path.write_text()` rejects `newline=`.

- [ ] **Step 3: Separate SVG lifecycle validation from stateful assumptions.**

In `_svg_runtime.py`, retain the existing parsing/geometry logic but make lifecycle rules explicit:

```python
def validate_title_min_size(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("title_min_size_invalid")
    value = float(value)
    if not 34 <= value <= 4096:
        raise ValueError("title_min_size_invalid")
    return value
```

Implement the four lifecycle functions with these invariants:

- generator input must be exactly one XML code fence; extract it and validate a pre-enrichment SVG;
- candidate input is raw SVG and receives an explicit source map; a source-less content block keeps its `data-block-id` and maps it to `[]`, while `{}` is valid only when no content block / `data-block-id` exists;
- candidate rejects preexisting `data-source-id` and requires its block-ID set to equal the source-map keys exactly;
- final rejects every `data-block-id`, accepts legal `data-source-id` only on semantic `<g>` elements, and continues to reject visible or split `SRC-<digits>` / `S<digits>-B<digits>` metadata;
- finalize runs normalization, candidate validation, source enrichment, then final validation, returning final UTF-8 bytes.

Do not let `validate_svg()` itself accept an unchecked title floor. Call `validate_title_min_size()` at every public lifecycle entry before geometry work.

- [ ] **Step 4: Replace the SVG CLI with a thin outcome adapter.**

In `svg_tool.py`, replace direct `Path.write_text(..., newline="\n")` with a private publication helper that rejects a preexisting destination as `UNAVAILABLE`, writes and `fsync`s a sibling temporary file, rereads it, then atomically publishes only to the previously absent target. A failed validation or unavailable publication preserves any preexisting destination bytes.

Use a narrow classifier:

```python
def emit(status, operation, *, reason=None, warnings=()):
    payload = {"status": status, "operation": operation, "warnings": list(warnings)}
    if reason is not None:
        payload["reason"] = reason
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return {"PASS": 0, "INVALID": 2, "UNAVAILABLE": 3}[status]
```

Catch known lifecycle `ValueError` reasons as `INVALID`; classify filesystem, import, and unexpected failures as `UNAVAILABLE`. Never read a run path, import a file from the input directory, or alter a retry/attempt field.

- [ ] **Step 5: Give source intake the same non-blocking result behavior.**

Keep `extract_pptx()` pure. In `ppt_source_intake.py`, parse/validate the source, atomically publish the JSON inventory only after successful extraction, and emit the shared status vocabulary. A malformed or unsupported PPTX is `INVALID`; filesystem/environment/internal failures are `UNAVAILABLE`; failures preserve a prior output file.

Add direct CLI tests in `tests/test_source_intake.py` for one valid inventory, malformed `.pptx`, absent source, and write failure.

- [ ] **Step 6: Update direct/installed regression coverage and verify green.**

Replace tests that assume source metadata is injected before candidate persistence with lifecycle tests. Keep geometry, XML safety, CJK, and source-ID tests, but route them through `validate_candidate_svg`, `validate_final_svg`, or `finalize_candidate_svg` as appropriate.

Run:

```bash
python -B -m unittest tests.test_svg_tool tests.test_runtime_modules tests.test_svg_arc_bounds tests.test_jiawei_prompt_fidelity tests.test_source_intake tests.test_installed_svg_runtime_normalization_regression -v
```

Expected: PASS, except explicitly configured environment skips. Then execute the same SVG CLI suite under Python 3.9 when available:

```bash
py -3.9 -B -m unittest tests.test_svg_tool -v
```

Expected: PASS, proving no Python-3.10-only `Path.write_text` call remains.

- [ ] **Step 7: Inspect the task diff without committing.**

Run:

```bash
git diff --check -- skills/ppt-start/scripts/_svg_runtime.py skills/ppt-start/scripts/svg_tool.py skills/ppt-start/scripts/ppt_source_intake.py tests/test_svg_tool.py tests/test_source_intake.py
```

Expected: exit code `0`; retain all user-preexisting changes outside this task.

---

### Task 2: Add the AI-state complete/partial delivery adapter to `ppt-editable`

**Files:**
- Create: `tests/fixtures/ppt-editable/run-ai-state-complete/.ppt-pilot/run.json`
- Create: `tests/fixtures/ppt-editable/run-ai-state-partial/.ppt-pilot/run.json`
- Create: corresponding storyboard, quality-report, theme, and production `slides/` fixture files
- Modify: `skills/ppt-editable/scripts/_ppt_editable/model.py`
- Modify: `skills/ppt-editable/scripts/_ppt_editable/contract.py`
- Modify: `skills/ppt-editable/scripts/_ppt_editable/snapshot.py`
- Modify: `skills/ppt-editable/scripts/_ppt_editable/orchestrator.py`
- Modify: `skills/ppt-editable/scripts/_ppt_editable/atomic_io.py`
- Modify: `tests/test_delivery_contract.py`
- Modify: `tests/test_ppt_editable_contract.py`
- Modify: `tests/test_ppt_editable_orchestrator.py`
- Modify: `tests/test_ppt_editable_atomic.py`
- Modify: `tests/test_ppt_editable_package.py`

**Interfaces:**
- Consumes: a final run directory plus storyboard target order.
- Produces an adapter-selected `DeliverySelection` with:

```python
@dataclass(frozen=True)
class AIStateMissingSlide:
    slide_id: str
    reason: str  # "failed" or "skipped"
    evidence_type: str  # exactly "ai_state"
    evidence: Mapping[str, object]

@dataclass(frozen=True)
class DeliverySelection:
    explicit: bool
    status: str
    policy: str
    target_slide_ids: Tuple[str, ...]
    delivered_slide_ids: Tuple[str, ...]
    missing_slides: Tuple[Union[MissingSlide, AIStateMissingSlide], ...]
    origin: str  # legacy_implicit | legacy_explicit | ai_state
    requires_production: bool
    record: Optional[Mapping[str, Any]] = None
```

- The legacy `MissingSlide` and legacy `delivery_contract.py` schema remain byte-for-byte compatible.

- [ ] **Step 1: Write failing tests for AI-state selection and legacy isolation.**

Add a fixture helper to `tests/test_ppt_editable_contract.py` that constructs this new-state partial run:

```json
{
  "schema_version": 1,
  "deck_id": "ai-state-partial",
  "stage": "partial",
  "slides": {
    "S01": {"state": "promoted", "attempts": 1, "svg": "slides/S01.svg", "failure": null},
    "S02": {"state": "skipped", "attempts": 2, "svg": null,
             "skip": {"decision": "user_skipped", "answer": "skip S02"}}
  },
  "delivery": {"status": "partial"}
}
```

Add tests that assert:

```python
def test_ai_state_partial_derives_ordered_production_subset(self):
    context = validate_final_run(self.ai_partial)
    selection = validate_delivery_selection(context, parse_storyboard(context.storyboard_path))
    self.assertEqual(selection.origin, "ai_state")
    self.assertEqual(selection.delivered_slide_ids, ("S01",))
    self.assertEqual(selection.missing_slides[0].evidence_type, "ai_state")
    self.assertEqual(selection.missing_slides[0].reason, "skipped")

def test_legacy_shaped_delivery_cannot_fall_through_to_ai_state(self):
    run = self.ai_partial_run_data_with("delivery", {"schema_version": 1})
    with self.assertRaises(EditableError):
        validate_delivery_selection(replace(context, run_data=run), storyboard)
```

Also cover: complete all-promoted map; partial with a failed record; missing/extra/invalid target IDs; non-mapping slides; incomplete final states; partial with zero delivered pages; partial status mismatching promoted/omitted partition; skipped without explicit skip evidence; failed without a nonempty failure mapping; and AI state never using `samples/` fallback.

- [ ] **Step 2: Run those tests to prove the existing validator rejects new AI state.**

Run:

```bash
python -B -m unittest tests.test_ppt_editable_contract tests.test_ppt_editable_orchestrator tests.test_delivery_contract -v
```

Expected: AI-state cases fail with `delivery_invalid`, legacy transaction evidence errors, or `run_not_complete`; existing legacy explicit delivery tests remain the baseline.

- [ ] **Step 3: Model new omissions without fabricating legacy evidence.**

In `model.py`, add `AIStateMissingSlide` beside the existing frozen `MissingSlide`; do not add defaulted transaction fields or mutate the legacy dataclass. Change `EditableResult.missing_slides` to accept the two omission types, so `dataclasses.asdict()` emits either exact legacy seven-field objects or the new four-field AI-state objects.

Update `atomic_io.py` validation to accept exactly one of these disjoint shapes:

```python
_LEGACY_MISSING_SLIDE_KEYS = frozenset({
    "slide_id", "reason", "failure_reason", "generation_attempt",
    "transaction_id", "transaction_ref", "transaction_sha256",
})
_AI_STATE_MISSING_SLIDE_KEYS = frozenset({
    "slide_id", "reason", "evidence_type", "evidence",
})
```

Require `evidence_type == "ai_state"`, a `failed|skipped` reason, and JSON-only evidence values. Preserve every existing legacy exact-key check unchanged.

- [ ] **Step 4: Put delivery adaptation behind one seam in `contract.py`.**

Add the adapter protocol and dispatch in `contract.py`:

```python
class DeliveryAdapter(Protocol):
    def accepts(self, run_data: Mapping[str, Any]) -> bool: ...
    def select(self, context: RunContext, storyboard: Sequence[StoryboardSlide]) -> DeliverySelection: ...
```

Implement the exact selection order:

1. `LegacyExplicitDeliveryAdapter` wins when `run.delivery` contains any legacy explicit field (`schema_version`, policy, target/delivered IDs, hashes, omissions, or transaction data). It alone loads and calls `delivery_contract.py`.
2. `AIStateDeliveryAdapter` accepts only a `slides` mapping plus `delivery` exactly shaped as `{"status": "complete"}` or `{"status": "partial"}`.
3. Existing legacy implicit `stage == "complete"` fallback remains last.
4. Every other shape rejects rather than falling through.

The AI adapter must require its slide-map keys to equal storyboard IDs exactly, derive order from the storyboard, and project normalized evidence into this record for snapshot binding:

```python
{
  "kind": "ai_state_delivery",
  "status": "partial",
  "policy": "best_effort",
  "target_slide_ids": ["S01", "S02"],
  "delivered_slide_ids": ["S01"],
  "missing_slides": [
    {"slide_id": "S02", "reason": "skipped", "evidence_type": "ai_state",
     "evidence": {"decision": "user_skipped"}}
  ]
}
```

Do not read `production_policy`, `active_visual_generation_batch`, transactions, or batches for the AI adapter. It must set `explicit=True`, `origin="ai_state"`, and `requires_production=True`.

- [ ] **Step 5: Bind AI delivery records through snapshot, orchestration, and recovery.**

Update `snapshot.py` to bind the adapter projection whenever `explicit` is true. Update `orchestrator.py` to use:

```python
require_production = delivery.explicit or delivery.requires_production
```

so every AI-state delivery consumes only formal `slides/Sxx.svg`. Update `_committed_result()` to reconstruct an omission based on its exact field set; reject mixed/extra/unknown shapes as `promotion_conflict`.

Keep existing legacy partial namespace, journal, and promotion behavior unchanged. An AI-state partial must use the existing `-editable-partial[-unverified].pptx` namespace but may never force the converter to write or repair `ppt-start` state.

- [ ] **Step 6: Exercise complete/partial conversion and legacy regression behavior.**

Add orchestration tests proving:

```python
def test_ai_state_partial_exports_only_promoted_pages_without_legacy_loader(self):
    with mock.patch.object(contract, "_load_shared_delivery_contract", side_effect=AssertionError):
        result = generate_editable(self.ai_partial, self._degraded())
    self.assertEqual(result.status, "GENERATED_UNVERIFIED")
    self.assertEqual(result.delivery_status, "partial")
    self.assertEqual(result.delivered_slide_ids, ("S01",))
```

Also assert idempotent reread, partial result/manifest omission shape, Office request subset, no transaction/batch directories created, and unchanged legacy `_configure_partial_run()` output. Retarget `tests/test_delivery_contract.py::MODULE` to the bundled editable legacy validator instead of the deleted `ppt-start` file. Update `tests/test_ppt_editable_package.py` so its pressure/contract assertions cover the new AI-state complete/partial seam and no longer require fresh runtime-hash decisions.

Run:

```bash
python -B -m unittest tests.test_delivery_contract tests.test_ppt_editable_contract tests.test_ppt_editable_orchestrator tests.test_ppt_editable_atomic -v
```

Expected: PASS with existing optional Office/reference skips only.

- [ ] **Step 7: Inspect the delivery seam without committing.**

Run:

```bash
git diff --check -- skills/ppt-editable/scripts/_ppt_editable/model.py skills/ppt-editable/scripts/_ppt_editable/contract.py skills/ppt-editable/scripts/_ppt_editable/snapshot.py skills/ppt-editable/scripts/_ppt_editable/orchestrator.py skills/ppt-editable/scripts/_ppt_editable/atomic_io.py tests/test_ppt_editable_contract.py tests/test_ppt_editable_orchestrator.py
```

Expected: exit code `0`; legacy explicit delivery fixture bytes and omission shape are unchanged.

---

### Task 3: Rewrite active agent instructions and installation behavior around AI-owned state

**Files:**
- Create: `tests/test_ai_workflow_contract.py`
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/ai-state.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/interaction-protocol.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/manuscript-review.md`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `skills/ppt-start/references/generation-prompt-byte-grammar.md`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `skills/ppt-start/references/svg-contract.md`
- Modify: `skills/ppt-editable/SKILL.md`
- Modify: `skills/ppt-editable/references/input-output-contract.md`
- Modify: `README.md`
- Modify: `docs/INSTALL.md`
- Modify: `docs/USER-GUIDE.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/design.md`
- Modify: `docs/acceptance.md`
- Modify: `docs/RESILIENT-WORKFLOW.md`
- Delete: `docs/LIVE-DASHBOARD.md`
- Modify: `tools/update-hosts.ps1`
- Modify: `tools/install-deepseek-plugin.ps1`
- Modify: `tools/packaging.ps1`
- Modify: `tests/test_skill_package.py`
- Modify: `tests/test_interaction_protocol.py`
- Modify: `tests/test_tools_package.py`

**Interfaces:**
- Consumes: user request, actual workspace artifacts, user answer, and optionally stateless tool result JSON.
- Produces: direct AI state updates with this only workflow sequence:

```text
read run + artifacts
→ consume answered interaction or choose earliest executable action
→ do one action
→ write evidence
→ atomically update run.json
→ report outcome, degradation, and next action
```

- [ ] **Step 1: Write failing active-document tests before rewriting the instructions.**

Create `tests/test_ai_workflow_contract.py` that searches only active entrypoints, references, user docs, installer source, and packaged agent source—not `docs/superpowers/**` or `acceptance-evidence/**` historical records.

```python
ACTIVE_TEXTS = (
    repo_root() / "README.md",
    skill_root() / "SKILL.md",
    *sorted((skill_root() / "references").glob("*.md")),
    repo_root() / "docs" / "INSTALL.md",
    repo_root() / "docs" / "USER-GUIDE.md",
    repo_root() / "docs" / "ARCHITECTURE.md",
    repo_root() / "docs" / "RESILIENT-WORKFLOW.md",
)

def test_active_instructions_have_no_deleted_workflow_invocation(self):
    text = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_TEXTS)
    for token in ("ppt_runtime.py", "ppt_entry.py", "ppt_workflow_gate.py", "ppt_review_snapshot.py",
                  "advance --allow-partial", "--skip-slide", "revise-visual", "ListAgents",
                  "ppt-svg-generator-sdk", "runtime-canonical-owners.md"):
        self.assertNotIn(token, text)

def test_ai_state_reference_defines_tool_degradation_without_state_side_effects(self):
    state = read_text(skill_root() / "references" / "ai-state.md")
    self.assertIn("PASS", state)
    self.assertIn("INVALID", state)
    self.assertIn("UNAVAILABLE", state)
    self.assertIn("只有真实生成调用", state)
```

Add tests for direct pending-answer consumption, `skip` preserving attempts, `UNAVAILABLE` preserving stage/attempts, `INVALID` being page-local, block/source distinction, AI-state partial delivery, and link integrity for all active Markdown references.

- [ ] **Step 2: Run the new document tests and establish the red baseline.**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract -v
```

Expected: failures from stale `advance`, `--skip-slide`, `revise-visual`, deleted owner links, fixed snapshot command claims, SDK/ListAgents wording, and old batch/transaction delivery claims.

- [ ] **Step 3: Make `ai-state.md` the single state authority and shorten `SKILL.md` to steps.**

Keep `SKILL.md` to the ordered run recipe and branch pointers. It must positively instruct a generator handoff as:

```text
Pass the complete frozen Prompt by value to a fresh-context generator available on the current host.
The generator returns only the XML fence; AI owns extraction, evidence, and state.
```

Do not name the retired SDK path. Move detailed state rules into `ai-state.md`:

- `slides` is the storyboard-keyed page map;
- a real generator call alone increments attempts;
- tool `PASS` adds evidence, tool `INVALID` fails only that page, tool `UNAVAILABLE` records degradation and leaves stage/attempts alone;
- `complete`, `partial`, and `failed` derive from the page map;
- unknown legacy fields are preserved but not newly owned.

- [ ] **Step 4: Replace command-shaped interaction and review sediment with direct AI behavior.**

Rewrite `interaction-protocol.md` so an answered pending interaction follows exactly:

```text
read pending object + user answer
→ atomically record answered answer/decision
→ apply it to its artifact owner
→ append idempotent history
→ clear or replace pending object
→ continue earliest independent action
```

A skip changes only that slide to `skipped`, records explicit authorization, and preserves attempts. A retry starts another actual generator call only when permitted. Remove all `advance`, `--skip-slide`, `--workspace`, `--answer`, run-selection-command, fixed-entry, and `revise-visual` references.

Rewrite `manuscript-review.md` so AI directly records actual reviewed file paths; hashes are recorded when deterministic hashing is available and otherwise use `unhashed` plus `verification: ai_read`. Retain the hard `BLOCKER`/`HIGH` gate, but remove claims that a deleted snapshot script is the sole legal producer.

- [ ] **Step 5: Reconcile prompt, source, QA, and delivery branch references.**

Make these terms consistent everywhere:

```text
source ID = machine-only source metadata; never sent to generator
block ID  = transient structural join key; may be sent in narrative and echoed only on <g data-block-id>
```

In `generation-prompt-byte-grammar.md`, remove the blanket block-ID prohibition but retain the source-ID/URL/secret prohibition. In visual/SVG/QA references, document raw candidate → finalize/AI join → final SVG, including source-less pages with `{}` source map. Document the three tool outcomes and the fact that a tool availability failure is not a workflow blocker.

Update `ppt-editable` documents to describe legacy explicit evidence versus new AI-state `slides` selection, including AI-state partial omission evidence and no converter state mutation.

- [ ] **Step 6: Update user-facing docs and remove retired dashboard/runtime claims.**

Rewrite README, INSTALL, USER-GUIDE, ARCHITECTURE, design, acceptance, and RESILIENT-WORKFLOW around the same state seam. Delete `docs/LIVE-DASHBOARD.md` and remove its active references. Preserve historical `docs/superpowers/**` and `acceptance-evidence/**` as dated evidence; do not rewrite history to look current.

Explain that unavailable Office/rendering yields `not_verified`/`not_rendered`; it does not erase valid SVG work. Explain that a generator unavailable page can become a transparent partial result only after AI records the page-local evidence/user decision.

- [ ] **Step 7: Make host installation remove the retired SDK agent without claiming a hard sandbox.**

In `tools/update-hosts.ps1`, after staging a verified `ppt-svg-generator.md`, remove only the retired `ppt-svg-generator-sdk.md` from the same selected user/project Claude agent roots, using the same backup/rollback handling as a replaced agent. Preserve unrelated agents and never create a new discovery root solely for cleanup.

Keep the surviving agent's actual tool claim accurate: no filesystem/network data tools and a positive instruction not to use granted tools; never state that the host exposes “zero tools” unless a real host contract proves it. Correct `install-deepseek-plugin.ps1` wording to match its actual package inventory; do not promise DeepSeek adapter diagnostics or runtime registration.

- [ ] **Step 8: Update text/installer tests and verify green.**

Revise `test_skill_package.py`, `test_interaction_protocol.py`, and `test_tools_package.py` to assert active contract behavior instead of runtime/batch/dashboard internals. Add a temporary installer regression:

```python
def test_updater_retires_only_the_obsolete_sdk_agent(self):
    (claude_agents / "ppt-svg-generator-sdk.md").write_text("old", encoding="utf-8")
    (claude_agents / "unrelated.md").write_text("keep", encoding="utf-8")
    completed = run_update_hosts(...)
    self.assertEqual(completed.returncode, 0, completed.stderr)
    self.assertFalse((claude_agents / "ppt-svg-generator-sdk.md").exists())
    self.assertTrue((claude_agents / "ppt-svg-generator.md").is_file())
    self.assertEqual((claude_agents / "unrelated.md").read_text(encoding="utf-8"), "keep")
```

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract tests.test_skill_package tests.test_interaction_protocol tests.test_tools_package -v
```

Expected: PASS, with only platform-gated PowerShell tests skipped when unavailable.

- [ ] **Step 9: Inspect documentation and installation changes without committing.**

Run:

```bash
git diff --check -- skills/ppt-start/SKILL.md skills/ppt-start/references skills/ppt-editable/SKILL.md skills/ppt-editable/references README.md docs tools
```

Expected: exit code `0`; no current instructions point at a deleted file.

---

### Task 4: Retire state-machine-only tests and keep a focused supported regression suite

**Files:**
- Delete: `tests/test_generation_concurrency.py`
- Delete: `tests/test_adaptive_generation_contract.py`
- Delete: `tests/test_dashboard_lifecycle.py`
- Delete: `tests/test_dashboard_server.py`
- Delete: `tests/test_dashboard_snapshot.py`
- Delete: `tests/test_host_adapter_runtime.py`
- Delete: `tests/test_claude_agent_preservation.py`
- Delete: `tests/test_installed_host_adapter_runtime_regression.py`
- Delete: `tests/test_installed_sdk_agent_contract.py`
- Delete: `tests/test_installed_batch_retirement_regression.py`
- Delete: `tests/test_installed_runtime_retry_regression.py`
- Delete: `tests/test_ppt_runtime.py`
- Delete: `tests/test_runtime_artifacts.py`
- Delete: `tests/test_source_workflow_gate.py`
- Delete: `tests/fixtures/visual-generation-batch-v2-cases.json`
- Delete: `tests/fixtures/visual-generation-host-capability-cases.json`
- Delete: `tests/fixtures/visual-generation-transaction-cases.json`
- Delete: `tests/fixtures/visual-generation-timing-cases.json`
- Delete: `tests/fixtures/visual-revision-precedence.json`
- Delete: `tests/fixtures/claude-code-isolation-cases.json`
- Delete: `tests/fixtures/runtime-boundaries.json`
- Delete: `tests/fixtures/style-prompt-blocker-cases.json`
- Delete: `tests/fixtures/style-asset-blocker-cases.json`
- Delete: `tests/fixtures/style-prompt-active-revision-projection.json`
- Delete: `tests/fixtures/style-prompt-resolution-cases.json`
- Delete: `tests/fixtures/style-identity-migration-cases.json`
- Delete: `tests/fixtures/generation-prompt-snapshot.json`
- Delete: `tests/fixtures/workspace-run-selection.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/test_page_local_runtime.py`
- Modify: `tests/test_partial_workflow_gate.py`
- Modify: `tests/test_in_place_recovery.py`
- Modify: `tests/test_visual_repair.py`
- Modify: `tests/test_review_snapshot.py`
- Modify: `tests/test_workspace_entry.py`
- Modify: `tests/test_source_workflow_recovery.py`
- Modify: `tests/test_source_redesign_integration.py`
- Modify: `tests/test_workflow_contract.py`
- Modify: `tests/test_path_compat_contract.py`
- Modify: `tests/test_redesign_prompt_contract.py`
- Modify: `tests/test_style_packs.py`
- Modify: `tests/test_prompt_architecture_consistency.py`

**Interfaces:**
- Consumes: surviving static Skill/doc contracts, direct `run.json` fixtures, retained SVG/PPTX helpers.
- Produces: evidence that the installed package contains only supported stateless scripts and that all behavior not owned by Python is described, not simulated by test mocks.

- [ ] **Step 1: Write a failing package-inventory test before deleting obsolete test assumptions.**

Add to `tests/test_tools_package.py`:

```python
def test_ppt_start_package_contains_only_stateless_public_tools(self):
    scripts = {path.name for path in (skill_root() / "scripts").glob("*.py")}
    self.assertEqual(
        scripts,
        {"_source_intake.py", "_svg_geometry.py", "_svg_runtime.py", "_xml_safety.py",
         "ppt_source_intake.py", "svg_tool.py"},
    )
```

Add a second test that asserts no shipped file name begins with `_runtime`, `_generation`, `_dashboard`, `_workflow`, `ppt_runtime`, `ppt_entry`, `ppt_dashboard`, or `ppt_concurrency`.

- [ ] **Step 2: Run the package-inventory test and observe the expected red failure.**

Run:

```bash
python -B -m unittest tests.test_tools_package.StatelessToolPackageTests -v
```

Expected: current static expectations still require removed runtime/dashboard/host artifacts or the suite imports deleted files.

- [ ] **Step 3: Delete only tests and fixtures whose sole subject is the removed runtime.**

Delete the exact files listed above. Do not delete direct SVG, source intake, editable conversion, style extraction, geometry, or manuscript-gate tests. Move any still-useful source parsing assertion from `test_source_workflow_recovery.py` to `test_source_intake.py` before deleting its runtime-specific scaffold.

- [ ] **Step 4: Rewrite invariant tests instead of recreating a test-only state machine.**

Consolidate the retained product assertions into `test_ai_workflow_contract.py`, `test_svg_tool.py`, and existing direct-tool tests. Keep direct state examples as fixture data and assert the intended state semantics without shipping a controller:

```python
def test_tool_unavailable_is_recorded_without_changing_page_lifecycle(self):
    before = {
        "stage": "production",
        "slides": {"S02": {"attempts": 1, "state": "generating", "qa": {}}},
    }
    after = {
        "stage": "production",
        "slides": {"S02": {"attempts": 1, "state": "generating",
                             "qa": {"tool": "unavailable"}}},
    }
    self.assertEqual(before["stage"], after["stage"])
    self.assertEqual(before["slides"]["S02"]["attempts"], after["slides"]["S02"]["attempts"])

def test_structured_invalid_contract_is_page_local(self):
    state = {
        "slides": {
            "S01": {"state": "failed", "failure": {"code": "svg_contract_failed"}},
            "S02": {"state": "promoted", "svg": "slides/S02.svg"},
        }
    }
    self.assertEqual(state["slides"]["S01"]["state"], "failed")
    self.assertEqual(state["slides"]["S02"]["state"], "promoted")
```

These are documentation/fixture assertions only; they must not become shipped workflow logic. Rewrite prompt/style tests to assert the static generator boundary: source IDs never enter prompts; transient block IDs may; templates require the proper `<g data-block-id>` echo; no byte-compiler, transaction identity, adapter registry, or concurrency matrix is reintroduced.

- [ ] **Step 5: Run retained focused suites and fix only supported-contract failures.**

Run:

```bash
python -B -m unittest tests.test_ai_workflow_contract tests.test_svg_tool tests.test_source_intake tests.test_svg_contract tests.test_svg_arc_bounds tests.test_geometry_warnings tests.test_manuscript_review_gate tests.test_ppt_editable_contract tests.test_ppt_editable_orchestrator tests.test_ppt_editable_atomic tests.test_tools_package -v
```

Expected: PASS with documented external-capability skips only. A test failing because it names a deleted runtime module must be deleted or rewritten to a currently supported invariant—not restored through a compatibility wrapper.

- [ ] **Step 6: Run the full suite and verify package cleanliness.**

Run:

```bash
python -B -m unittest discover -s tests -v
```

Expected: exit code `0`; allowed skips must name unavailable PowerPoint, reference corpus, symlink, or PowerShell capability and must not hide removed runtime imports.

Then run:

```bash
python -B - <<'PY'
from pathlib import Path
scripts = Path("skills/ppt-start/scripts")
for path in scripts.rglob("*.py"):
    assert not path.name.startswith(("ppt_runtime", "ppt_entry", "ppt_dashboard", "ppt_concurrency")), path
    assert not path.name.startswith(("_runtime", "_generation", "_workflow")), path
print("stateless ppt-start scripts only")
PY
```

Expected output:

```text
stateless ppt-start scripts only
```

- [ ] **Step 7: Perform final repository verification without committing.**

Run:

```bash
git diff --check && git status --short
```

Expected: no whitespace errors; status lists the intended source, documentation, test, fixture, and design/plan changes only. Do not commit, push, install, or claim live-host/Office success beyond evidence actually collected.
