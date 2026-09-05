# PPT Start Concurrent SVG Generation Implementation Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PPT Start 收敛为故事板 + theme 的 direct-compile 单一路径，并以 schema-v2 的每页 transaction、batch manifest 和宿主隔离任务能力实现默认四路并发 SVG 生成，同时保持字节级 Prompt、一致恢复、确定 promotion 与可解释 telemetry。

**Architecture:** 本仓库以 Markdown Skill/reference、JSON fixtures 和 Python `unittest` 契约测试作为可执行规范，不新增依赖或假装存在运行时 scheduler。Prompt compiler oracle 留在 `tests/test_redesign_prompt_contract.py`；visual-generation v2 的 schema、迁移、能力协商、调度、恢复和 timing oracle 集中到 `tests/test_visual_generation_contract.py` 与三个职责单一的 JSON fixtures。生产规则分别由 byte grammar、artifact contract、redesign dispatch 和 QA/promotion 文档拥有，其他文档只链接权威定义。

**Tech Stack:** Python 3 standard library (`unittest`, `json`, `hashlib`, `base64`, `datetime`), Markdown contracts, deterministic UTF-8/LF JSON fixtures, PowerShell deployment scripts already present in the repository.

## Global Constraints

- Prompt `format` remains exactly `creative-brief-v1`.
- The only dynamic whole-line markers are `[[CANONICAL_NARRATIVE_BULLETS]]` and `[[STYLE_BASELINE]]`.
- Storyboard owns narrative, material, facts, claims, and source mappings; `theme.json` owns style identity and the soft style baseline.
- Internal IDs matching `SRC-<digits>` are machine metadata only: they remain in `data-source-id` and trace artifacts but are forbidden in visible SVG `<text>/<tspan>` and editable PPT text; visible human-readable citations are allowed only when explicitly requested and must omit internal IDs.
- New visual-generation persistence uses schema version 2: one transaction file per slide, one batch manifest, and only `active_visual_generation_batch` in `run.json`.
- Configured batch width is exactly `3` or `4`, default `4`; a final batch may contain `1..batch_width` slides.
- Generation and per-slide validation may overlap; final promotion, blocker publication, and `run.json` pointer changes are serial and deterministic in `ordered_slide_ids` order.
- Generator input is prompt-by-value with fresh history and text-only output; filesystem and tools are `none`.
- Never invoke nested Claude/Codex/DeepSeek CLIs, probe credentials/profiles, require Git/worktrees, or fall back to the coordinator's current context.
- An isolated task without concurrency or durable lookup degrades to width `1`; no fresh isolated task fails closed as `generator_unavailable` before prompt/transaction/candidate writes.
- Preserve every v1 state, failure reason, path, hash, attempt, trigger, dirty state, and previous final during zero-model-call v1→v2 migration.
- Preserve previous finals on every failure; never adopt a candidate that was not durably committed as `candidate_written`.
- Do not remove behavior tests. Restore the intent of tests deleted in commit `344c7ac` against direct-compile/schema-v2 semantics.
- Do not add dependencies, commit, push, or deploy unless separately requested.

---

## File Structure

### Prompt compilation authority

- Modify `skills/ppt-start/references/generation-prompt-byte-grammar.md`: sole byte/envelope/hash authority.
- Modify `skills/ppt-start/references/generation-prompt-template.md`: machine-only source-ID rendering rule; no default visible source footer.
- Modify `skills/ppt-start/references/svg-contract.md` and `skills/ppt-start/assets/examples/office-safe-slide.svg`: preserve `data-source-id` while removing visible internal IDs.
- Modify `skills/ppt-start/references/visual-brief-and-generation.md`: sole storyboard/theme/revision-to-two-replacements projection authority; retain filename only for link compatibility.
- Modify `skills/ppt-start/references/redesign-prompt.md`: preflight, schema-v2 transaction preparation, and isolated dispatch boundary.
- Modify `tests/test_redesign_prompt_contract.py`: executable byte compiler/envelope oracle and active-authority scan.
- Modify `tests/fixtures/generation-prompt-snapshot.json`: full golden body/envelope bytes and hashes.

### Batch persistence and recovery authority

- Modify `skills/ppt-start/references/artifact-contract.md`: schema-v2 paths, manifest/transaction schemas, pointer-last activation, migration, crash recovery, state ownership.
- Modify `tests/test_visual_generation_contract.py`: reusable pure oracles for v2 validation, migration, dispatch, promotion, blocker ordering, and critical path.
- Retain `tests/fixtures/visual-generation-transaction-cases.json`: read-only v1 migration corpus.
- Create `tests/fixtures/visual-generation-batch-v2-cases.json`: v2 schema, normal/crash/mixed-outcome/CAS fixtures.

### Host and scheduler authority

- Modify `skills/ppt-start/references/redesign-prompt.md`: capability negotiation and prompt-by-value task interface.
- Modify `skills/ppt-start/references/workflow.md`: batch selection and resume flow only.
- Modify `skills/ppt-start/references/qa-and-revision.md`: concurrent page QA, serial promotion/blocker gate.
- Create `tests/fixtures/visual-generation-host-capability-cases.json`: portable host matrix and expected side effects.
- Create `tests/fixtures/visual-generation-timing-cases.json`: overlapping spans and DAG longest-path examples.

### Active contract convergence

- Modify `skills/ppt-start/SKILL.md`, `skills/ppt-start/references/design-system.md`, `skills/ppt-start/references/layout-catalog.md`, `README.md`, `docs/design.md`, and `docs/acceptance.md`: remove active visual/effective-brief semantics and link the authorities above.
- Modify `tests/test_skill_package.py`, `tests/test_workflow_contract.py`, `tests/test_tools_package.py`, `tests/test_interaction_protocol.py`, `tests/test_assets.py`, and `tests/test_style_packs.py`: package-wide convergence and restored behavior coverage.
- Modify `tests/prompts/redesign-dedicated.md`: direct-compile synthetic prompt expectations with no active `visual-briefs/` dependency.

---

### Task 1: Direct-Compile Authority and Byte-Exact Envelope

**Files:**
- Modify: `tests/test_redesign_prompt_contract.py:20-133,438-527,965-1380,1940-1971`
- Modify: `tests/fixtures/generation-prompt-snapshot.json`
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/generation-prompt-byte-grammar.md`
- Modify: `skills/ppt-start/references/generation-prompt-template.md`
- Modify: `skills/ppt-start/references/svg-contract.md`
- Modify: `skills/ppt-start/assets/examples/office-safe-slide.svg`
- Modify: `tests/test_svg_contract.py`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md:127-186`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `skills/ppt-start/references/design-system.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/layout-catalog.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `tests/prompts/redesign-dedicated.md`

**Interfaces:**
- Consumes: existing `normalize_lf`, `compile_prompt_body`, `sha256_id`, `canonical_json_bytes`, and nine-field `METADATA_FIELD_ORDER` in `tests/test_redesign_prompt_contract.py`.
- Produces: `COMPILED_PROMPT_SEPARATOR = b"## Compiled Prompt\n\n"`; `render_generation_prompt(metadata: dict, body: bytes, slide_id: str) -> bytes`; `split_generation_prompt_envelope(envelope: bytes) -> tuple[bytes, bytes]`; a golden fixture containing `body_utf8`, `body_base64`, `envelope_utf8`, `envelope_base64`, `body_sha256`, `prompt_snapshot_id`, and `full_file_sha256`.

- [ ] **Step 1: Add exact-envelope RED tests**

Add the separator and strict splitter beside `METADATA_FIELD_ORDER`:

```python
import base64

COMPILED_PROMPT_SEPARATOR = b"## Compiled Prompt\n\n"


def split_generation_prompt_envelope(envelope: bytes) -> tuple[bytes, bytes]:
    if envelope.count(COMPILED_PROMPT_SEPARATOR) != 1:
        raise ValueError("prompt_preflight_invalid")
    prefix, body = envelope.split(COMPILED_PROMPT_SEPARATOR, 1)
    if not body.startswith(b"# Role") or not body.endswith(b"\n") or body.endswith(b"\n\n"):
        raise ValueError("prompt_preflight_invalid")
    return prefix, body
```

Add tests that require:

```python
def test_compiled_prompt_separator_is_exactly_two_lf(self):
    payload = self._load_generation_prompt_snapshot_payload()
    rendered = self._render_generation_prompt_fixture(payload)
    self.assertEqual(rendered["envelope"].count(COMPILED_PROMPT_SEPARATOR), 1)
    prefix, body = split_generation_prompt_envelope(rendered["envelope"])
    self.assertTrue(prefix.endswith(b"\n"))
    self.assertTrue(body.startswith(b"# Role"))
    self.assertEqual(rendered["compiled_prompt_sha256"], sha256_id(body))


def test_compiled_prompt_separator_rejects_fused_single_and_triple_lf(self):
    payload = self._load_generation_prompt_snapshot_payload()
    envelope = self._render_generation_prompt_fixture(payload)["envelope"]
    invalid = (
        envelope.replace(COMPILED_PROMPT_SEPARATOR, b"## Compiled Prompt"),
        envelope.replace(COMPILED_PROMPT_SEPARATOR, b"## Compiled Prompt\n"),
        envelope.replace(COMPILED_PROMPT_SEPARATOR, b"## Compiled Prompt\n\n\n"),
        envelope.replace(COMPILED_PROMPT_SEPARATOR, COMPILED_PROMPT_SEPARATOR * 2),
    )
    for candidate in invalid:
        with self.subTest(candidate=candidate[:80]):
            with self.assertRaisesRegex(ValueError, "^prompt_preflight_invalid$"):
                split_generation_prompt_envelope(candidate)


def test_generation_prompt_fixture_is_a_full_byte_oracle(self):
    payload = self._load_generation_prompt_snapshot_payload()
    rendered = self._render_generation_prompt_fixture(payload)
    expected = payload["expected"]
    self.assertEqual(base64.b64decode(expected["body_base64"]), rendered["body"])
    self.assertEqual(base64.b64decode(expected["envelope_base64"]), rendered["envelope"])
    self.assertEqual(expected["body_sha256"], sha256_id(rendered["body"]))
    self.assertEqual(expected["full_file_sha256"], sha256_id(rendered["envelope"]))
```

- [ ] **Step 2: Add active-authority RED scan**

Add a test over active runtime files only (exclude `docs/superpowers/plans`, fixtures explicitly marked legacy, and historical style assets):

```python
def test_active_runtime_authorities_have_no_effective_or_visual_brief_pipeline(self):
    active_paths = (
        skill_root() / "SKILL.md",
        skill_root() / "references" / "artifact-contract.md",
        skill_root() / "references" / "design-system.md",
        skill_root() / "references" / "generation-prompt-byte-grammar.md",
        skill_root() / "references" / "layout-catalog.md",
        skill_root() / "references" / "qa-and-revision.md",
        skill_root() / "references" / "redesign-prompt.md",
        skill_root() / "references" / "visual-brief-and-generation.md",
        skill_root() / "references" / "workflow.md",
    )
    forbidden = (
        "[[EFFECTIVE_PAGE_SPECIFICATION]]",
        "有效页面规格（唯一动态内容）",
        "visual_brief_snapshot_id",
        "visual-brief assembler",
        "visual brief owner",
    )
    combined = "\n".join(read_text(path) for path in active_paths)
    for token in forbidden:
        with self.subTest(token=token):
            self.assertNotIn(token, combined)
```

Allow the literal `.ppt-pilot/visual-briefs/` only in one inert-history sentence; assert each active file contains no operational verbs (`create`, `update`, `read`, `rebuild`, `validate`, `assemble`) within that sentence's paragraph.

- [ ] **Step 2B: Add machine-only source-ID RED tests**

Add a visible-text extractor for SVG `<text>/<tspan>` content and require:

```python
VISIBLE_INTERNAL_SOURCE_ID = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)

for visible_text in (
    "来源：SRC-001 · SRC-002",
    "Source: SRC-003",
    "SRC-005",
):
    self.assertRegex(visible_text, VISIBLE_INTERNAL_SOURCE_ID)
```

The active generation template, byte grammar, QA contract, SVG contract, and example must state/illustrate that IDs are retained only in `data-source-id` or trace metadata. Assert the example retains `data-source-id="SRC-001"` but its visible text contains no `SRC-<digits>`. Assert the active template no longer contains `页脚来源行必须存在`. Human-readable citations such as `来源：2026 年年度报告` remain legal when explicitly requested.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```bash
python -m unittest discover -s tests -p "test_redesign_prompt_contract.py" -v
```

Expected: failures show the current one-LF envelope (`## Compiled Prompt\n# Role`) and active visual/effective-brief text in Skill/reference files.

- [ ] **Step 4: Make envelope rendering strict**

Replace the current line-list join in `render_generation_prompt` with explicit metadata prefix assembly:

```python
metadata_lines = ["# " + slide_id + " 页面生成 Prompt", "", "## Snapshot metadata"]
metadata_lines.extend(
    f"- **{field}**：{_provenance_value_text(metadata[field])}"
    for field in METADATA_FIELD_ORDER
)
prefix = ("\n".join(metadata_lines) + "\n\n").encode("utf-8")
envelope = prefix + COMPILED_PROMPT_SEPARATOR + body
_, persisted_body = split_generation_prompt_envelope(envelope)
if sha256_id(persisted_body) != sha256_id(body):
    raise ValueError("prompt_snapshot_conflict")
return envelope
```

Keep `compiled_prompt_sha256` scoped to body bytes beginning at `# Role`, never the separator or metadata.

- [ ] **Step 5: Regenerate the complete golden fixture deterministically**

Update `expected.envelope` to contain exactly `## Compiled Prompt\n\n# Role`; add base64 and hashes using the test helper outputs rather than hand-edited hashes. Keep readable UTF-8 fields and base64 fields equal to the same bytes.

- [ ] **Step 6: Converge runtime documents to direct compile**

Make these ownership statements exact and non-overlapping:

```text
visual-brief-and-generation.md:
  storyboard + theme.json + applied revision projection
    -> [[CANONICAL_NARRATIVE_BULLETS]] + [[STYLE_BASELINE]]

byte grammar:
  metadata prefix + b"## Compiled Prompt\n\n" + compiled body

redesign-prompt.md:
  deterministic preflight -> transaction preparation -> isolated text dispatch

qa-and-revision.md:
  candidate checks -> validation result -> serial promotion gate
```

Replace the generation template's visible-footer requirement with:

```text
Source-backed claims MUST retain internal IDs in data-source-id metadata.
Internal SRC-<digits> identifiers MUST NOT appear in visible text.
A human-readable source name or URL MAY be visible only when explicitly requested and MUST omit internal IDs.
```

Remove the visible `Source: SRC-001 ...` line from `office-safe-slide.svg` while retaining its source-bearing `data-source-id`. Regenerate the byte-exact prompt body/envelope/base64/hashes after this normative text changes.

Replace `locked_content_mismatch` with `fact_source_mismatch` throughout active schema-v2 text. Keep the former only in the v1 migration corpus. Correct the byte-grammar reference from “11 rules” to the current enumerated count or, preferably, “all rules” so numbering cannot drift.

- [ ] **Step 7: Run focused direct-compile tests**

Run:

```bash
python -m unittest discover -s tests -p "test_redesign_prompt_contract.py" -v
```

Expected: all tests pass; fixture envelope contains one exact two-LF separator and no active legacy marker.

---

### Task 2: Schema-v2 Batch and Per-Slide Transaction Contract

**Files:**
- Modify: `tests/test_visual_generation_contract.py`
- Create: `tests/fixtures/visual-generation-batch-v2-cases.json`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/workflow.md`

**Interfaces:**
- Consumes: direct-compile prompt identity from Task 1; v1 fixture remains unchanged as migration input.
- Produces: `validate_v2_transaction(transaction: dict) -> None`; `validate_v2_manifest(manifest: dict, transactions: dict[str, dict]) -> None`; `rebuild_batch_cursors(manifest, transactions) -> tuple[int, int]`; deterministic `transaction_ref` and path rules.

- [ ] **Step 1: Define v2 constants and validators in tests**

Use exact field sets:

```python
V2_TRANSACTION_FIELDS = {
    "schema_version", "kind", "batch_id", "transaction_id", "slide_id",
    "generation_intent", "generation_trigger_id", "prompt_path",
    "prompt_snapshot_id", "compiled_prompt_sha256", "candidate_path",
    "final_path", "prior_final_sha256", "state", "generation_attempt",
    "candidate_sha256", "failure_reason", "dispatch_epoch",
    "host_attribution_id", "host_task_id", "validation", "timing",
}
V2_MANIFEST_FIELDS = {
    "schema_version", "kind", "batch_id", "batch_width",
    "ordered_slide_ids", "storyboard_snapshot_id", "theme_snapshot_id",
    "source_audit_snapshot_id", "generation_prompt_template_snapshot_id",
    "transaction_refs", "dispatch_epoch", "promotion_cursor",
    "blocker_cursor", "active_blocker_ref", "state", "created_at",
    "updated_at", "telemetry_summary",
}
```

Validation must enforce `schema_version == 2`, exact `kind`, `batch_width in {3, 4}`, unique sorted slide IDs, `1 <= len(slides) <= width`, aligned ordered refs, `transaction_id == prompt_snapshot_id`, same `batch_id`, and deterministic paths:

```text
.ppt-pilot/visual-generation-transactions/<slide-id>-<tx64>.json
slides/.candidates/<slide-id>-<tx64>.svg
slides/<slide-id>.svg
generation-prompts/<slide-id>.md
```

- [ ] **Step 2: Create a v2 fixture with normal and invalid cases**

The fixture must contain:

```json
{
  "schema_version": 2,
  "default_batch_width": 4,
  "valid_batches": ["four-slide-active", "three-slide-active", "one-slide-final"],
  "invalid_cases": [
    "width-two", "width-five", "duplicate-slide", "unsorted-slides",
    "ref-order-mismatch", "manifest-copies-transaction-state",
    "transaction-batch-mismatch", "transaction-id-mismatch",
    "candidate-path-mismatch", "untrusted-cursor"
  ],
  "recovery_cases": [
    "pointer-before-files-fails-closed", "prepared-files-before-pointer-reusable",
    "candidate-before-candidate-written-is-orphan",
    "candidate-written-hash-match-resumes", "validated-final-is-candidate-commits",
    "validated-final-is-prior-retries", "validated-final-third-hash-conflicts"
  ],
  "mixed_outcome_cases": ["four-way-out-of-order-two-pass-two-fail"]
}
```

Each named case must contain full manifest/transaction objects and explicit `expected` output; no prose-only cases.

- [ ] **Step 3: Run schema tests and confirm RED**

Run:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Expected: fixture missing and active docs still describe singular `run.json.visual_generation_transaction`.

- [ ] **Step 4: Document schema-v2 and pointer-last activation**

In `artifact-contract.md`, define:

```text
1. write/reread every per-slide transaction
2. write/reread the batch manifest
3. atomically replace run.json with active_visual_generation_batch
```

`run.json.active_visual_generation_batch` contains only `schema_version`, `batch_id`, and `.ppt-pilot/visual-generation-batches/<batch-id>.json`. The manifest never copies transaction state. Cursor values are hints rebuilt from transaction files and cannot authorize promotion.

- [ ] **Step 5: Add recovery and CAS tests**

Test all fixture recovery cases. For a validated transaction, allow only:

```python
if observed_final_sha256 == candidate_sha256:
    outcome = "commit_promoted"
elif observed_final_sha256 == prior_final_sha256:
    outcome = "retry_atomic_promotion"
else:
    outcome = "final_promotion_conflict"
```

Use an explicit no-file sentinel such as `"none"` for `prior_final_sha256`; reject null/omitted ambiguity.

- [ ] **Step 6: Run focused schema tests**

Run:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Expected: v2 field/path/order/recovery tests pass while v1 tests remain available for Task 3 migration.

---

### Task 3: Lossless v1→v2 Migration and Restored Recovery Coverage

**Files:**
- Modify: `tests/test_visual_generation_contract.py`
- Retain/Modify only annotations: `tests/fixtures/visual-generation-transaction-cases.json`
- Extend: `tests/fixtures/visual-generation-batch-v2-cases.json`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`

**Interfaces:**
- Consumes: all v1 states/failure reasons from `visual-generation-transaction-cases.json`; Task 2 validators.
- Produces: `migrate_v1_run_to_v2(run: dict, corpus_case: dict) -> dict`; deterministic one-slide batch bytes; `visual_generation_state_conflict` split-brain result; zero generator-call guarantee.

- [ ] **Step 1: Add migration matrix RED tests**

Parameterize every v1 state and every v1 failure reason. Assert:

```python
result = migrate_v1_run_to_v2(copy.deepcopy(case["before_run"]), case)
self.assertEqual(result["generator_calls"], 0)
self.assertNotIn("visual_generation_transaction", result["run"])
self.assertEqual(result["run"]["active_visual_generation_batch"]["schema_version"], 2)
self.assertEqual(result["transaction"]["dispatch_epoch"], 0)
```

Copy all v1 values exactly for identity, intent, trigger, attempts, prompt/candidate/final paths, hashes, failure reason, state, and dirty slide. Populate new fields only with deterministic migration sentinels.

- [ ] **Step 2: Restore deleted behavior intent from commit `344c7ac`**

Restore tests under new names and v2 semantics:

```text
test_generation_blocker_lifecycle_is_atomic_and_preflight_has_zero_dispatch
  replaces deleted style-prompt blocker lifecycle test

test_v1_prompt_and_transaction_migration_is_read_only_deterministic_and_zero_call
  replaces deleted old-run prompt migration test

test_visual_revisions_are_durable_and_project_into_storyboard_theme_owners
  replaces deleted visual-brief owner test

test_production_resume_and_revision_semantics_use_batch_pointer_and_per_slide_transactions
  replaces deleted singular-run resume test
```

Do not restore `visual-briefs/<slide-id>.md`, style-owned prompt, or singular transaction assertions.

- [ ] **Step 3: Add split-brain, crash, and idempotency tests**

Required cases:

```text
v1 only -> migrate
v2 only -> no-op
v1 + v2 -> visual_generation_state_conflict, zero writes
crash after tx -> rerun reuses byte-identical tx
crash after manifest -> rerun reuses byte-identical tx+manifest
crash before run pointer -> pointer-only completion
prepared bytes differ -> fail closed, no overwrite
second complete migration -> byte-identical no-op
```

Compare deterministic canonical JSON bytes, not only parsed objects.

- [ ] **Step 4: Document migration ordering and ownership**

Specify that migration first writes the v2 transaction, then manifest, then atomically replaces `run.json` to remove singular v1 ownership and publish the v2 pointer in the same replacement. A migration never calls a generator and never infers missing values from SVG content.

- [ ] **Step 5: Run migration-focused and full visual contract tests**

Run:

```bash
python -m unittest tests.test_visual_generation_contract.VisualGenerationContractTests.test_v1_migration_matrix -v
```

Then:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Expected: all v1 behaviors are represented through migration and all v2 recovery cases pass.

---

### Task 4: Portable Host Capability and Concurrent Dispatch

**Files:**
- Create: `tests/fixtures/visual-generation-host-capability-cases.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/test_tools_package.py`
- Modify: `skills/ppt-start/SKILL.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/workflow.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`

**Interfaces:**
- Consumes: prepared v2 batch from Task 2.
- Produces: `negotiate_host_capability(case: dict, configured_width: int = 4) -> dict`; `schedule_epoch(manifest, transactions, capability) -> list[dict]`; exact task interface `spawn_isolated_text_task(...)` and optional `get_isolated_text_task_result(...)`.

- [ ] **Step 1: Create capability matrix fixture**

Include complete inputs/expected outputs for:

```json
[
  "native-concurrent-durable-lookup-width-4",
  "remote-concurrent-durable-lookup-width-3",
  "native-isolated-no-concurrency-width-1",
  "native-isolated-no-lookup-width-1",
  "non-git-workspace-native-width-4",
  "no-fresh-isolation-generator-unavailable",
  "filesystem-required-rejected",
  "tools-required-rejected",
  "nested-cli-only-rejected",
  "credential-dependent-only-rejected",
  "current-context-only-rejected",
  "missing-attribution-rejected",
  "refused-result",
  "timeout-result",
  "unknown-durable-result"
]
```

Every case includes `workspace_is_git`, capability booleans, selected width, expected error, side-effect counters, and whether task lookup is permitted.

- [ ] **Step 2: Add negotiation RED tests**

Assert selection order and zero-side-effect failure:

```python
result = negotiate_host_capability(case)
self.assertEqual(result, case["expected"])
if result["error"] == "generator_unavailable":
    self.assertEqual(case["expected_side_effects"], {
        "prompt_writes": 0,
        "transaction_writes": 0,
        "candidate_writes": 0,
        "generator_calls": 0,
    })
```

Assert `workspace_is_git` does not affect the valid native result.

- [ ] **Step 3: Add scheduler one-call-per-epoch and overlap tests**

For each eligible transaction, schedule at most once per `(transaction_id, dispatch_epoch)`. Four distinct slide tasks may share an epoch. Task payload contains the complete Prompt bytes by value and these fixed restrictions:

```json
{
  "fresh_history": true,
  "filesystem": "none",
  "tools": "none",
  "output": "text",
  "expected_fence": "xml"
}
```

The coordinator alone extracts one XML fence, writes candidate temp+rename, rereads/hash-checks, then commits `candidate_written`.

- [ ] **Step 4: Restore batch concurrency package tests**

Replace deleted “dispatch parallel but write/validate serial” assertions with:

```text
up to batch_width fresh generators concurrently
coordinator-only candidate and transaction writes
per-slide validation may run concurrently
promotion and blocker publication are serial in ordered_slide_ids
```

Test `SKILL.md`, `workflow.md`, `redesign-prompt.md`, `qa-and-revision.md`, and `artifact-contract.md` for the same ownership rule without copying the full schema into every file.

- [ ] **Step 5: Document host capability fail-closed rules**

Define the interface exactly:

```text
spawn_isolated_text_task(
  prompt_by_value,
  fresh_history=true,
  filesystem=none,
  tools=none,
  timeout,
  cancellation
) -> attribution_id, task_id, text, status, error_code

get_isolated_text_task_result(attribution_id | task_id)
```

A new batch with no capability writes only a run-level blocker. An existing batch that temporarily loses capability retains its transactions, sets manifest state `blocked`, and publishes only the lowest ordered undispatched slide failure.

- [ ] **Step 6: Run host/scheduler tests**

Run:

```bash
python -m unittest discover -s tests -p "test_tools_package.py" -v
```

Then:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Expected: non-Git width-4 succeeds, sparse hosts use width-1, unavailable isolation has zero generation side effects, and forbidden fallbacks are absent.

---

### Task 5: Concurrent Validation with Deterministic Promotion and Blockers

**Files:**
- Extend: `tests/fixtures/visual-generation-batch-v2-cases.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `tests/test_workflow_contract.py`
- Modify: `tests/test_interaction_protocol.py`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/workflow.md`

**Interfaces:**
- Consumes: `candidate_written` transactions and host results from Task 4.
- Produces: `eligible_promotions(manifest, transactions) -> list[str]`; `lowest_eligible_blocker(manifest, transactions) -> str | None`; `promote_in_order(...)`; per-slide `validation` schema.

- [ ] **Step 1: Add four-way out-of-order RED fixture**

Use `ordered_slide_ids = ["S03", "S04", "S05", "S06"]` and completion order `S06, S04, S03, S05`. Outcomes:

```text
S03 validated
S04 generator_timeout
S05 validated
S06 fact_source_mismatch
```

Expected behavior:

```text
- candidate/QA completion records may be written in completion order
- promotion order is S03 then S05, never completion order
- visible blocker is S04 first; S06 remains only in its transaction
- S03/S05 previous finals are atomically replaced after CAS
- S04/S06 previous finals and dirty states are preserved
- a sibling failure never deletes or demotes S03/S05
```

- [ ] **Step 2: Add deterministic coordinator oracles**

Compute decisions only from the manifest's ordered slide list and durable transactions; do not trust completion callbacks or manifest cursors. Promotion is serialized, and each promotion span depends on the preceding promotion span. Blocker publication chooses the minimum eligible index.

- [ ] **Step 2B: Gate visible internal source IDs before validation commit**

Add a pure QA oracle that parses visible `<text>/<tspan>` content only and returns `fact_source_mismatch` when case-insensitive `\bSRC-[0-9]+\b` appears. Test these exact cases:

```text
来源：SRC-001 · SRC-002  -> fact_source_mismatch
Source: SRC-003          -> fact_source_mismatch
SRC-005                  -> fact_source_mismatch
data-source-id="SRC-001" with visible "88%" -> pass
来源：2026 年年度报告      -> pass when explicitly requested
```

The failure is written to that slide's transaction, preserves its previous final, and participates in `lowest_eligible_blocker`; it never triggers text deletion, raster fallback, or sibling demotion.

- [ ] **Step 3: Restore revision and resume behavior tests**

In `test_interaction_protocol.py`, assert each applied `visual-revision-<n>` persists `normalized_changes`, `affected_scope`, and `supersedes`, then projects into authoritative storyboard/theme owners and marks affected slides dirty. Do not assert a visual-brief owner.

In `test_workflow_contract.py`, restore batch/resume checks using per-slide transaction files, batch pointer, durable-stage stop points, patch/recompose distinction, current SVG for patch only, and manuscript-review re-entry only when facts/claims/sources change.

- [ ] **Step 4: Document parallel QA and serial publication**

`qa-and-revision.md` must permit XML/source/narrative/render/visual checks to overlap per slide, but only the coordinator can commit `validation`, publish a blocker, or promote a final. The fact/source check parses visible SVG text, rejects internal `SRC-<digits>` with `fact_source_mismatch`, and ignores matching IDs in `data-source-id`/trace metadata. The validation object contains:

```json
{
  "state": "pending|running|passed|failed",
  "checks": {
    "xml": "pending|passed|failed",
    "office": "pending|passed|failed",
    "geometry_text": "pending|passed|failed",
    "fact_source": "pending|passed|failed",
    "narrative": "pending|passed|failed",
    "visual": "pending|passed|failed|not_rendered"
  }
}
```

- [ ] **Step 5: Run coordination tests**

Run:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Then:

```bash
python -m unittest discover -s tests -p "test_workflow_contract.py" -v
```

Then:

```bash
python -m unittest discover -s tests -p "test_interaction_protocol.py" -v
```

Expected: completion order differs from deterministic publication order, sibling preservation holds, and legacy revision behavior intent is restored without brief ownership.

---

### Task 6: Performance Telemetry and Critical-Path Accounting

**Files:**
- Create: `tests/fixtures/visual-generation-timing-cases.json`
- Modify: `tests/test_visual_generation_contract.py`
- Modify: `skills/ppt-start/references/artifact-contract.md`
- Modify: `skills/ppt-start/references/redesign-prompt.md`
- Modify: `skills/ppt-start/references/qa-and-revision.md`
- Modify: `docs/acceptance.md`

**Interfaces:**
- Consumes: task/validation/promotion events from Tasks 4–5.
- Produces: `validate_span(span: dict) -> None`; `critical_path_duration_ms(spans: list[dict]) -> int`; `batch_wall_duration_ms(spans) -> int`; recovery deduplication by stable `span_id`.

- [ ] **Step 1: Define exact telemetry span schema**

Every span contains:

```python
TELEMETRY_SPAN_FIELDS = {
    "span_id", "parent_span_id", "critical_path_parent_ids",
    "run_id", "deck_id", "batch_id", "slide_id", "transaction_id",
    "attempt", "dispatch_epoch", "phase", "status", "error_reason",
    "host", "capability", "provider", "model", "isolation_mode",
    "fallback_mode", "host_attribution_id", "host_task_id",
    "wall_started_at", "wall_finished_at", "monotonic_started_ns",
    "monotonic_finished_ns", "duration_ms", "queue_ms", "timeout_ms",
    "input_tokens", "output_tokens", "finish_reason",
}
```

Phases are exactly `compile`, `model`, `render`, `qa`, `promotion`. Nullable host/token fields remain present as `null`; missing fields are invalid.

- [ ] **Step 2: Create overlapping timing fixture**

Include:

```text
serial-baseline-4x1000ms-model = about 4000ms plus promotion
parallel-width4-4x1000ms-model = about 1000ms plus serial promotion
parallel-width3-8-slides = ceil(8/3) model waves plus serial promotion
out-of-order-qa = longest dependency chain, not sum of all spans
recovery-replayed-span = stable span_id counted once
telemetry-corrupt = correctness outcome unchanged, diagnostic failure recorded
```

Give exact monotonic timestamps and expected integer durations for every case.

- [ ] **Step 3: Add DAG longest-path RED tests**

Validate acyclic parent references, non-negative durations, `duration_ms == (finished-started)/1_000_000`, and `queue_ms <= duration_ms` for the model phase. The critical path uses dynamic programming over `critical_path_parent_ids`; parallel siblings are maxed, never summed. Promotion spans form an ordered dependency chain.

- [ ] **Step 4: Document telemetry as non-authoritative**

Telemetry write/parse failure must never mutate transaction correctness state or authorize promotion. Record `telemetry_diagnostic_failed` separately while preserving the actual generation result. Distinguish queue, startup/TTFT where available, active model generation, render, QA, and promotion.

- [ ] **Step 5: Run telemetry tests**

Run:

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

Expected: width-4 fixture reports approximately one model wave rather than four summed model durations; recovery does not double count spans.

---

### Task 7: Package-Wide Convergence, Documentation, and Verification

**Files:**
- Modify: `tests/test_skill_package.py`
- Modify: `tests/test_assets.py`
- Modify: `tests/test_style_packs.py`
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_svg_contract.py`
- Modify: `README.md`
- Modify: `docs/design.md`
- Modify: `docs/acceptance.md`
- Verify all Skill/reference/test/fixture files changed in Tasks 1–6.

**Interfaces:**
- Consumes: every contract and fixture from Tasks 1–6.
- Produces: one coherent plugin package with no active legacy authority and a fully green test suite.

- [ ] **Step 1: Add package-wide active-authority tests**

Scan runtime Skill/reference files and root docs. Prohibit operational uses of:

```text
[[EFFECTIVE_PAGE_SPECIFICATION]]
有效页面规格（唯一动态内容）
visual_brief_snapshot_id
visual-brief assembler
run.json.visual_generation_transaction (except v1 migration section)
current-context generator fallback
nested claude / codex / deepseek CLI
credential/profile probing
```

Require schema-v2 links and exact `creative-brief-v1` marker pair. Require active authorities to state that internal source IDs are machine-only; scan every shipped example SVG's visible `<text>/<tspan>` content and fail on case-insensitive `\bSRC-[0-9]+\b` while permitting `data-source-id="SRC-001"` attributes.

- [ ] **Step 2: Update root documentation and acceptance criteria**

Document the observable acceptance cases: exact two-LF envelope, four overlapping isolated model tasks, non-Git portability, one-slide zero-call migration, out-of-order completion with ordered promotion, lowest-order blocker, previous-final preservation, critical-path timing, and machine-readable source IDs preserved without any visible `SRC-<digits>` text in promoted SVG/PPT output.

- [ ] **Step 3: Run all focused suites**

```bash
python -m unittest discover -s tests -p "test_redesign_prompt_contract.py" -v
```

```bash
python -m unittest discover -s tests -p "test_visual_generation_contract.py" -v
```

```bash
python -m unittest discover -s tests -p "test_skill_package.py" -v
```

```bash
python -m unittest discover -s tests -p "test_workflow_contract.py" -v
```

```bash
python -m unittest discover -s tests -p "test_interaction_protocol.py" -v
```

```bash
python -m unittest discover -s tests -p "test_tools_package.py" -v
```

```bash
python -m unittest discover -s tests -p "test_svg_contract.py" -v
```

Expected: every focused suite passes.

- [ ] **Step 4: Run the full suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass with no skipped restored behavior tests.

- [ ] **Step 5: Run static diff checks**

```bash
git diff --check
```

Expected: no whitespace errors.

```bash
git status --short
```

Expected: only intentional Skill/reference/docs/tests/fixture changes; no deployment backups, generated SVGs, cache files, or external workspace changes.

- [ ] **Step 6: Perform final independent review**

Review specifically for: schema ownership duplication, accidental active visual-brief language, envelope hash-domain drift, visible internal `SRC-<digits>` leakage versus preserved `data-source-id` trace metadata, promotion based on untrusted cursor/completion order, migration data loss, forbidden generator fallbacks, and telemetry affecting correctness. Apply only confirmed fixes, then rerun the full suite and `git diff --check`.

## Self-Review Results

- **Spec coverage:** Tasks 1–7 cover direct-compile convergence, exact envelope, machine-only source IDs with visible-text promotion blocking, schema-v2 batch/transaction persistence, v1 migration/recovery, portable host capability, concurrent dispatch/validation, serial promotion/blockers, telemetry, restored deleted behavior intent, and complete verification.
- **Placeholder scan:** The plan contains no deferred implementation markers; every fixture case, interface, state, failure mode, and verification command is named explicitly.
- **Type consistency:** Task 2 establishes the v2 manifest/transaction validators consumed by migration and scheduling; Task 4 produces host task identities consumed by Task 6 spans; Task 5 defines deterministic publication functions and validation fields consumed by telemetry and package acceptance.
