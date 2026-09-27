# AI-Owned Bounded Parallel SVG Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore default width-5 parallel generation for independent PPT pages while keeping all filesystem, validation, promotion and `run.json` writes under one AI coordinator.

**Architecture:** Treat one bounded generation wave as one coordinator action. The coordinator serially freezes inputs and records a durable wave, launches prompt-only page Agents concurrently, then consumes results in storyboard order with serial writes. Tests include a pure in-memory contract oracle, but no scheduler, queue, planner or Git/helper module ships in the Skill.

**Tech Stack:** Markdown Skill/reference contracts, Claude Code prompt-only Agent tool semantics, Python 3.9+ `unittest`, the existing `ppt-editable` delivery adapter, PowerShell installer digest tests.

## Global Constraints

- Default target width is exactly `5`; explicit serial width is `1`; explicit parallel width is an integer from `2` through `10`.
- Only pages sharing one approved manuscript/storyboard/theme scope and current stage may share a wave.
- Page Agents receive complete Prompt bytes and own no files, source maps, candidate SVGs, final SVGs or state.
- Generator calls may overlap; Prompt/source preparation, result consumption, validation, publication and `run.json` writes remain coordinator-only and serial.
- Page results publish only as the maximal contiguous terminal prefix of `ordered_slide_ids`, never callback completion order.
- Attempts increment once per host-accepted Prompt. Launch intent and capacity rejection do not consume attempts.
- Durable host task attribution is resumed rather than redispatched; duplicate attribution is idempotent and conflicting attribution fails closed page-locally.
- No busy polling, hidden queue, unlimited fan-out, retired transaction/batch runtime, `_generation_concurrency.py`, `ppt_concurrency.py`, dashboard or new shipped workflow helper.
- Keep the host-native/no-local-Claude-CLI and valid-local-HEAD repair contracts intact.
- Do not commit, push, update a PR, or deploy local Claude Code/Codex/DeepSeek Harness installations unless separately requested.

---

## File structure

| File | Responsibility |
|---|---|
| `tests/test_parallel_generation_contract.py` | Test-only pure oracle for width, eligibility, accepted attempts, resume and deterministic result order. It is not packaged. |
| `tests/test_ai_workflow_contract.py` | Static active-document assertions for bounded waves and coordinator ownership. |
| `tests/test_interaction_protocol.py` | Removes the accidental anti-concurrency assertion and pins explicit parallel behavior. |
| `skills/ppt-start/SKILL.md` | Always-loaded short rule: one action may be one bounded wave; default width 5. |
| `skills/ppt-start/references/ai-state.md` | Single schema owner for `active_generation_wave`, task acceptance, attempts and recovery. |
| `skills/ppt-start/references/workflow.md` | Eligibility, dispatch, notification and ordered serial processing flow. |
| `skills/ppt-start/references/visual-brief-and-generation.md` | Prompt-only Agent calls in one tool round; optional worktree/HEAD branch remains per page. |
| `skills/ppt-start/references/qa-and-revision.md` | Out-of-order completion may overlap, but validation evidence and promotion publish serially. |
| `skills/ppt-start/references/artifact-contract.md` | Atomic writer and final-state prohibition for active waves. |
| `skills/ppt-editable/scripts/_ppt_editable/contract.py` | Rejects AI-state final delivery while `active_generation_wave` remains non-null. |
| `skills/ppt-editable/references/input-output-contract.md` | Documents the final handoff constraint. |
| `README.md`, `docs/ARCHITECTURE.md`, `docs/USER-GUIDE.md`, `docs/RESILIENT-WORKFLOW.md`, `docs/design.md`, `docs/acceptance.md` | Public behavior and evidence level. |
| `docs/superpowers/specs/2026-09-24-ai-owned-non-blocking-tools-design.md` | Clarifies historical “one action” means a bounded wave, not one page call. |
| `docs/superpowers/plans/2026-09-25-claude-code-native-generator-bootstrap.md` | Removes stale historical statement that the one-call rule remains required. |
| `tests/test_ppt_editable_contract.py` | Final-delivery active-wave regression. |
| `tests/test_tools_package.py` | Installed copy contains the updated parallel Skill and no retired scheduler files. |

### Task 1: Establish the parallel-wave contract with RED tests

**Files:**
- Create: `tests/test_parallel_generation_contract.py`
- Modify: `tests/test_ai_workflow_contract.py`
- Modify: `tests/test_interaction_protocol.py`
- Modify: `tests/test_skill_package.py`

**Interfaces:**
- Test-only oracle consumes ordered slide records with run/stage/snapshot identity, Prompt/source-map readiness, unresolved dependencies, `state`, `attempts` and retry authorization.
- Test-only oracle produces a wave-shaped dictionary matching the documented `active_generation_wave` fields.
- Production behavior remains agent-facing Markdown; no oracle code is copied into `skills/`.

- [x] **Step 1: Create the test-only pure oracle and behavior cases**

Create `tests/test_parallel_generation_contract.py` with this complete implementation and tests:

```python
"""Executable oracle for AI-owned parallel generation-wave rules."""

from copy import deepcopy
import unittest


DEFAULT_WIDTH = 5
MAX_WIDTH = 10


def plan_wave(
    ordered_slide_ids,
    records,
    *,
    run_id,
    stage,
    storyboard_id,
    manuscript_id,
    theme_id,
    user_width=None,
    host_capacity=None,
    dirty_slide_ids=(),
    pending_interaction=False,
    shared_state_consistent=True,
):
    if pending_interaction or shared_state_consistent is not True:
        raise ValueError("generation_wave_shared_gate_blocked")
    if user_width is None:
        target = DEFAULT_WIDTH
    elif type(user_width) is not int or not 1 <= user_width <= MAX_WIDTH:
        raise ValueError("generation_wave_width_invalid")
    else:
        target = user_width
    if host_capacity is not None and (
        type(host_capacity) is not int or host_capacity < 0
    ):
        raise ValueError("generation_wave_capacity_invalid")
    dirty = set(dirty_slide_ids)
    eligible = []
    for slide_id in ordered_slide_ids:
        record = records[slide_id]
        same_scope = (
            record["run_id"] == run_id
            and record["stage"] == stage
            and record["storyboard_id"] == storyboard_id
            and record["manuscript_id"] == manuscript_id
            and record["theme_id"] == theme_id
        )
        inputs_ready = (
            record.get("prompt_ready") is True
            and record.get("source_map_ready") is True
        )
        independent = not record.get("unresolved_dependencies")
        state = record["state"]
        initial = state == "planned" or (
            slide_id in dirty and state in ("validated", "promoted")
        )
        retry = state == "failed" and record.get("retry_authorized") is True
        if same_scope and inputs_ready and independent and (initial or retry):
            eligible.append(slide_id)
    capacity = target if host_capacity is None else host_capacity
    selected = eligible[: min(target, capacity, len(eligible))]
    if not selected:
        if eligible and capacity == 0:
            raise ValueError("generation_wave_capacity_unavailable")
        raise ValueError("generation_wave_no_eligible_pages")
    wave_id = "wave-{}-{}-01".format(selected[0], selected[-1])
    return {
        "schema_version": 1,
        "wave_id": wave_id,
        "stage": stage,
        "status": "prepared",
        "target_width": target,
        "ordered_slide_ids": selected,
        "prompt_sha256": {
            slide_id: "sha256:" + ("0" * 62) + slide_id[-2:]
            for slide_id in selected
        },
        "accepted_tasks": {},
    }


def record_acceptance(records, wave, accepted):
    updated_records = deepcopy(records)
    updated_wave = deepcopy(wave)
    for slide_id, task_id in accepted.items():
        if slide_id not in wave["ordered_slide_ids"] or not task_id:
            raise ValueError("generation_wave_attribution_invalid")
        record = updated_records[slide_id]
        prompt_sha256 = updated_wave["prompt_sha256"][slide_id]
        existing = updated_wave["accepted_tasks"].get(slide_id)
        if existing is not None:
            if (
                existing.get("task_id") != task_id
                or existing.get("prompt_sha256") != prompt_sha256
                or existing.get("attempt") != record["attempts"]
            ):
                raise ValueError("generation_wave_attribution_conflict")
            continue
        if any(
            task.get("task_id") == task_id
            for other_slide_id, task in updated_wave["accepted_tasks"].items()
            if other_slide_id != slide_id
        ):
            raise ValueError("generation_wave_attribution_conflict")
        record["attempts"] += 1
        record["state"] = "generating"
        updated_wave["accepted_tasks"][slide_id] = {
            "task_id": task_id,
            "attempt": record["attempts"],
            "prompt_sha256": prompt_sha256,
            "state": "in_flight",
        }
    updated_wave["status"] = (
        "collecting" if updated_wave["accepted_tasks"] else "prepared"
    )
    return updated_records, updated_wave


def redispatchable_slide_ids(wave):
    accepted = set(wave["accepted_tasks"])
    return [
        slide_id
        for slide_id in wave["ordered_slide_ids"]
        if slide_id not in accepted
    ]


def serial_publication_order(wave, terminal_results):
    publication_order = []
    for slide_id in wave["ordered_slide_ids"]:
        if slide_id not in terminal_results:
            break
        publication_order.append(slide_id)
    return publication_order


def publish_terminal_result(records, wave, slide_id, outcome):
    if slide_id not in wave["accepted_tasks"] or outcome not in ("passed", "failed"):
        raise ValueError("generation_wave_terminal_result_invalid")
    updated_records = deepcopy(records)
    updated_wave = deepcopy(wave)
    updated_wave["accepted_tasks"][slide_id]["state"] = outcome
    record = updated_records[slide_id]
    if outcome == "passed":
        record["state"] = "validated"
        record["failure"] = None
    else:
        record["state"] = "failed"
        record["failure"] = {
            "code": "generator_output_invalid",
            "message": "accepted generator task returned an invalid page",
        }
    return updated_records, updated_wave


class ParallelGenerationContractTests(unittest.TestCase):
    def records(self):
        return {
            "S%02d" % number: {
                "run_id": "run-1",
                "stage": "production",
                "storyboard_id": "storyboard-1",
                "manuscript_id": "manuscript-1",
                "theme_id": "theme-1",
                "prompt_ready": True,
                "source_map_ready": True,
                "unresolved_dependencies": [],
                "state": "planned",
                "attempts": 0,
            }
            for number in range(2, 15)
        }

    def plan(self, records, **kwargs):
        return plan_wave(
            list(records),
            records,
            run_id="run-1",
            stage="production",
            storyboard_id="storyboard-1",
            manuscript_id="manuscript-1",
            theme_id="theme-1",
            **kwargs,
        )

    def test_default_width_five_and_explicit_width_one_through_ten(self):
        records = self.records()
        default = self.plan(records)
        self.assertEqual(default["target_width"], 5)
        self.assertEqual(
            default["ordered_slide_ids"],
            ["S02", "S03", "S04", "S05", "S06"],
        )
        self.assertEqual(
            self.plan(records, user_width=1)["ordered_slide_ids"],
            ["S02"],
        )
        self.assertEqual(
            len(self.plan(records, user_width=10)["ordered_slide_ids"]),
            10,
        )
        for invalid in (0, 11, True, 5.0, "5"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.plan(records, user_width=invalid)

    def test_all_page_gates_and_capacity_filter_wave_membership(self):
        records = self.records()
        records["S03"]["run_id"] = "other-run"
        records["S04"]["stage"] = "anchor"
        records["S05"]["storyboard_id"] = "other-storyboard"
        records["S06"]["manuscript_id"] = "other-manuscript"
        records["S07"]["theme_id"] = "other-theme"
        records["S08"]["prompt_ready"] = False
        records["S09"]["source_map_ready"] = False
        records["S10"]["unresolved_dependencies"] = ["S09"]
        records["S11"].update(state="failed", retry_authorized=False)
        records["S12"].update(state="failed", retry_authorized=True)
        records["S13"]["state"] = "promoted"
        wave = self.plan(
            records,
            host_capacity=3,
            dirty_slide_ids=("S11", "S13"),
        )
        self.assertEqual(
            wave["ordered_slide_ids"],
            ["S02", "S12", "S13"],
        )
        self.assertEqual(records["S14"]["attempts"], 0)

    def test_pending_interaction_and_shared_conflict_block_dispatch(self):
        records = self.records()
        for options in (
            {"pending_interaction": True},
            {"shared_state_consistent": False},
        ):
            with self.subTest(options=options), self.assertRaisesRegex(
                ValueError, "generation_wave_shared_gate_blocked"
            ):
                self.plan(records, **options)
        self.assertTrue(all(record["attempts"] == 0 for record in records.values()))

    def test_zero_capacity_and_no_eligible_pages_do_not_create_a_wave(self):
        records = self.records()
        with self.assertRaisesRegex(
            ValueError, "generation_wave_capacity_unavailable"
        ):
            self.plan(records, host_capacity=0)
        for record in records.values():
            record["state"] = "promoted"
        with self.assertRaisesRegex(ValueError, "generation_wave_no_eligible_pages"):
            self.plan(records)
        self.assertTrue(all(record["attempts"] == 0 for record in records.values()))

    def test_only_accepted_tasks_increment_attempts(self):
        records = self.records()
        wave = self.plan(records)
        updated, collecting = record_acceptance(
            records, wave, {"S02": "task-02", "S04": "task-04"}
        )
        self.assertEqual(updated["S02"]["attempts"], 1)
        self.assertEqual(updated["S04"]["attempts"], 1)
        self.assertEqual(updated["S03"]["attempts"], 0)
        self.assertEqual(updated["S03"]["state"], "planned")
        self.assertEqual(set(collecting["accepted_tasks"]), {"S02", "S04"})

    def test_task_attribution_replay_is_idempotent_and_conflicts_fail_closed(self):
        records = self.records()
        wave = self.plan(records)
        updated, collecting = record_acceptance(
            records, wave, {"S02": "task-02"}
        )
        replayed_records, replayed_wave = record_acceptance(
            updated, collecting, {"S02": "task-02"}
        )
        self.assertEqual(replayed_records, updated)
        self.assertEqual(replayed_wave, collecting)
        self.assertEqual(replayed_records["S02"]["attempts"], 1)
        with self.assertRaisesRegex(
            ValueError, "generation_wave_attribution_conflict"
        ):
            record_acceptance(updated, collecting, {"S02": "task-02-replacement"})

    def test_resume_does_not_redispatch_accepted_tasks(self):
        records = self.records()
        wave = self.plan(records)
        _, collecting = record_acceptance(
            records, wave, {"S02": "task-02", "S04": "task-04"}
        )
        self.assertEqual(
            redispatchable_slide_ids(collecting),
            ["S03", "S05", "S06"],
        )

    def test_publication_stops_at_first_unresolved_predecessor(self):
        records = self.records()
        wave = self.plan(records)
        terminal = {
            "S06": "failed",
            "S04": "passed",
            "S02": "passed",
            "S05": "passed",
        }
        self.assertEqual(serial_publication_order(wave, terminal), ["S02"])
        terminal["S03"] = "unavailable"
        self.assertEqual(
            serial_publication_order(wave, terminal),
            ["S02", "S03", "S04", "S05", "S06"],
        )

    def test_page_failure_preserves_accepted_and_promoted_siblings(self):
        records = self.records()
        records["S02"].update(state="promoted", svg="slides/S02.svg")
        records["S08"].update(state="promoted", svg="slides/S08.svg")
        wave = self.plan(records, dirty_slide_ids=("S02",))
        accepted_records, collecting = record_acceptance(
            records, wave, {"S02": "task-02", "S03": "task-03"}
        )
        failed_records, failed_wave = publish_terminal_result(
            accepted_records,
            collecting,
            "S02",
            "failed",
        )
        self.assertEqual(failed_records["S02"]["state"], "failed")
        self.assertEqual(failed_records["S02"]["svg"], "slides/S02.svg")
        self.assertEqual(failed_records["S03"]["state"], "generating")
        self.assertEqual(failed_wave["accepted_tasks"]["S03"]["state"], "in_flight")
        self.assertEqual(failed_records["S08"]["state"], "promoted")
        self.assertEqual(failed_records["S08"]["svg"], "slides/S08.svg")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Add RED static assertions for the active Skill contract**

Add to `tests/test_ai_workflow_contract.py` after the AI-state ownership test:

```python
def test_parallel_generation_is_one_bounded_coordinator_action(self):
    skill = read_text(PPT_START / "SKILL.md")
    state = read_text(PPT_START / "references" / "ai-state.md")
    workflow = read_text(PPT_START / "references" / "workflow.md")
    visual = read_text(PPT_START / "references" / "visual-brief-and-generation.md")
    combined = "\n".join((skill, state, workflow, visual))
    for token in (
        "active_generation_wave",
        "target_width",
        "ordered_slide_ids",
        "accepted_tasks",
        "默认并发 5",
        "2–10",
        "同一工具轮",
        "故事板顺序",
        "coordinator-only",
        "host_concurrency_unavailable",
        "重复归因幂等",
        "归因冲突",
        "首个未 terminal",
    ):
        self.assertIn(token, combined)
    self.assertNotIn("A turn may make at most one real generator call for one page", skill)
    self.assertNotIn("每轮最多执行一个真实页面生成调用", state)
    self.assertNotIn("每轮最多一次真实页面生成调用", workflow)
```

Update `tests/test_interaction_protocol.py::test_workflow_keeps_stage_order_without_a_pause_stage` to replace:

```python
self.assertIn("不启动后台任务、轮询或隐藏并发", workflow)
self.assertNotIn("可并发", workflow)
```

with:

```python
self.assertIn("不忙轮询", workflow)
self.assertIn("可并发", workflow)
self.assertIn("串行提交", workflow)
self.assertIn("默认并发 5", workflow)
```

Extend `tests/test_skill_package.py::test_ppt_start_is_a_short_ai_owned_orchestrator` with:

```python
self.assertIn("bounded generation wave", text)
self.assertIn("default width is 5", text)
```

- [x] **Step 3: Run RED tests and confirm the serial contract is the failure**

Run:

```bash
python -B -m unittest tests.test_parallel_generation_contract tests.test_ai_workflow_contract.AIWorkflowContractTests.test_parallel_generation_is_one_bounded_coordinator_action tests.test_interaction_protocol.InteractionProtocolTests.test_workflow_keeps_stage_order_without_a_pause_stage tests.test_skill_package.SkillPackageTests.test_ppt_start_is_a_short_ai_owned_orchestrator -v
```

Expected: the pure oracle tests pass; static tests fail because current active instructions explicitly require one page call and forbid “可并发”.

### Task 2: Replace the serial regression with AI-owned bounded waves

**Files:**
- Modify: `skills/ppt-start/SKILL.md:14-21,35-44`
- Modify: `skills/ppt-start/references/ai-state.md:35-43,57-101,109-118`
- Modify: `skills/ppt-start/references/workflow.md:17-37`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md:23-105`
- Modify: `skills/ppt-start/references/qa-and-revision.md:3-19,28-42`
- Modify: `skills/ppt-start/references/artifact-contract.md:19-58`
- Modify: `README.md:57-73`
- Modify: `docs/ARCHITECTURE.md:23-33,63-78`
- Modify: `docs/USER-GUIDE.md:26-46`
- Modify: `docs/RESILIENT-WORKFLOW.md:7-45`
- Modify: `docs/design.md:17-32,41-47`
- Modify: `docs/acceptance.md:17-27,36-44,63-65`
- Modify: `docs/superpowers/specs/2026-09-24-ai-owned-non-blocking-tools-design.md:51-72`
- Modify: `docs/superpowers/plans/2026-09-25-claude-code-native-generator-bootstrap.md:1-9,285-291`

**Interfaces:**
- `active_generation_wave` exactly matches the schema in the approved design.
- `slides` remains authoritative; wave evidence contains ordered coordination only.
- Agent task launch uses complete Prompt bytes, one Agent per page, and concurrent calls in one tool round.

- [x] **Step 1: Make `SKILL.md` expose one bounded wave as one action**

Replace the heading `## Run one action` with `## Run one action or bounded wave` and replace step 4 with:

```text
4. Perform one non-generation action, or one bounded generation wave of independent pages. The default width is 5; an explicit serial request uses 1, and an explicit parallel width may be 2–10. Read Prompt and generation before dispatch.
```

In the Visual path paragraph, state:

```text
In Claude Code, dispatch one prompt-only ppt-svg-generator Agent per page in the same tool round. A bounded generation wave is one AI action; Agents own no files or state, and AI serially validates and publishes results in storyboard order.
```

Keep the Skill at no more than 90 lines and retain all existing content/review/source/tool pointers.

- [x] **Step 2: Make `ai-state.md` the single wave-state authority**

Replace the current one-generator-call completion criterion with:

```text
3. 每轮执行一个非生成动作，或一个独立页面的有界生成 wave；默认并发 5，显式串行 1，显式并发 2–10。没有隐藏队列、忙等或自动循环。
```

After the page evidence section, add the exact `active_generation_wave` schema from the approved design, including these invariants:

```text
- status is prepared or collecting;
- ordered_slide_ids follows storyboard order and contains no duplicates;
- every prompt_sha256 is derived from reread Prompt bytes;
- accepted_tasks keys are a subset of ordered_slide_ids;
- attempts increments only after a host-accepted task ID is recorded;
- prepared, unaccepted pages consume no attempt;
- accepted task IDs are resumed, never redispatched;
- replaying the same slide/task ID/Prompt digest attribution is idempotent, while conflicting attribution fails closed without changing attempts;
- publication stops at the first nonterminal predecessor and leaves later results in host evidence;
- final complete|partial|failed requires active_generation_wave: null/absent.
```

Use the concrete `wave-S02-S06-01`, task IDs and illustrative digests already recorded in the approved design. Link to that design only as historical rationale; this reference owns active behavior.

- [x] **Step 3: Define the exact dispatch and deterministic publication sequence**

Replace the production paragraph in `workflow.md` with the nine-step wave flow from the approved design. It must include these exact phrases for tests and agent attention:

```text
默认并发 5
同一工具轮
可并发
coordinator-only
故事板顺序
串行提交
不忙轮询
host_concurrency_unavailable
```

State that a user request for parallel generation must launch more than one eligible page when possible. Explain a width-1 result using the actual gate/capacity reason rather than the removed one-call rule.

In `visual-brief-and-generation.md`, retain the host-native Git/HEAD sections unchanged, then add `### Parallel page wave` before Candidate-to-final. Define:

```json
{"subagent_type":"ppt-svg-generator","prompt":"S02 complete frozen Prompt bytes"}
```

for each page and require independent Agent calls in one host tool round. If the actual tool schema requires worktree isolation, each task follows the existing safe HEAD repair; it does not gain file access. Result text stays host evidence until the coordinator consumes it.

- [x] **Step 4: Bind concurrent results to serial writes and QA**

Add to `artifact-contract.md`:

```text
Parallel generators never write run artifacts. Prompt/source-map preparation, candidate/final files, QA evidence and run.json are coordinator-only serial writes. A wave is not a second slide inventory, and final delivery cannot retain one.
```

Add to `qa-and-revision.md`:

```text
Generator completion may be out of order. The coordinator consumes and publishes terminal results in storyboard order; one page failure does not cancel or demote accepted siblings. Capacity rejection before Prompt acceptance does not increment attempts.
```

Do not add transaction, batch, queue, dashboard or scheduler terminology as active owners.

- [x] **Step 5: Update public behavior and historical correction notes**

Update README and the listed docs so each says:

- default page-generation concurrency is 5;
- explicit width 2–10 and serial width 1 are supported;
- only page Agents overlap;
- shared writes are serial and deterministic;
- actual host capacity can lower width;
- real host overlap is a Host-level acceptance claim, not proven by static tests.

Amend `2026-09-24-ai-owned-non-blocking-tools-design.md` with a dated correction stating that “perform one action” includes one bounded generation wave and never meant one page call. Mark the one-call assertion in the historical 2026-09-25 bootstrap plan as superseded by the 2026-09-27 concurrency design; do not rewrite historical test results.

- [x] **Step 6: Run active Skill and oracle tests GREEN**

Run:

```bash
python -B -m unittest tests.test_parallel_generation_contract tests.test_ai_workflow_contract tests.test_interaction_protocol tests.test_skill_package -v
```

Expected: PASS. No current instruction rejects parallel generation, and no shipped scheduler file is added.

### Task 3: Prevent editable delivery while a wave remains active

**Files:**
- Modify: `skills/ppt-editable/scripts/_ppt_editable/contract.py:529-558`
- Modify: `skills/ppt-editable/references/input-output-contract.md:15-26`
- Modify: `tests/test_ppt_editable_contract.py:492-565`

**Interfaces:**
- Consumes: optional `run_data["active_generation_wave"]` from the new AI state.
- Produces: `EditableError(code="run_not_complete")` before final delivery selection when an AI-state wave remains active.
- Legacy adapters remain byte-compatible and do not reinterpret historical unknown fields.

- [x] **Step 1: Add the failing AI-state final-delivery regression**

Add this test after `test_ai_state_inventory_without_delivery_does_not_fall_back_to_legacy_complete`:

```python
def test_ai_state_final_rejects_active_generation_wave(self):
    contract = self._contract()
    run = self._write_ai_state_partial_run(self._temp_root() / "ai-active-wave")
    run_path = run / ".ppt-pilot" / "run.json"
    value = json.loads(run_path.read_text(encoding="utf-8"))
    value["active_generation_wave"] = {
        "schema_version": 1,
        "wave_id": "wave-S02-S06-01",
        "stage": "production",
        "status": "collecting",
        "target_width": 5,
        "ordered_slide_ids": ["S02"],
        "prompt_sha256": {"S02": "sha256:" + "a" * 64},
        "accepted_tasks": {
            "S02": {
                "task_id": "task-S02-01",
                "attempt": 2,
                "prompt_sha256": "sha256:" + "a" * 64,
                "state": "in_flight",
            }
        },
    }
    run_path.write_text(json.dumps(value), encoding="utf-8")
    context = contract.validate_final_run(run)
    with self.assertRaises(EditableError) as raised:
        contract.validate_delivery_selection(
            context, contract.parse_storyboard(context.storyboard_path)
        )
    self.assertEqual(raised.exception.code, "run_not_complete")
```

- [x] **Step 2: Run the test RED**

Run:

```bash
python -B -m unittest tests.test_ppt_editable_contract.RunContractTests.test_ai_state_final_rejects_active_generation_wave -v
```

Expected: FAIL because the current AI-state adapter ignores `active_generation_wave`.

- [x] **Step 3: Add the minimal AI-state adapter guard**

In `AIStateDeliveryAdapter.select`, immediately after reading `status`, add:

```python
if context.run_data.get("active_generation_wave") is not None:
    raise _error(
        "run_not_complete",
        "AI state final run retains an active generation wave",
    )
```

Do not add this check to the legacy adapters: unknown legacy fields stay historical evidence unless the run uses the new AI-state route.

Add to the AI-state adapter bullet list in `input-output-contract.md`:

```text
- complete/partial requires active_generation_wave to be null or absent; editable conversion never consumes in-flight host tasks.
```

- [x] **Step 4: Run editable contract tests GREEN**

Run:

```bash
python -B -m unittest tests.test_ppt_editable_contract -v
```

Expected: PASS, including the new active-wave guard and existing AI-state/legacy routes.

### Task 4: Prove installer fidelity and complete regression safety

**Files:**
- Modify: `tests/test_tools_package.py:85-156`
- Verify: all files from Tasks 1–3

**Interfaces:**
- Installer continues copying the same three filtered Skill trees and Claude Agent byte-for-byte.
- No local installation is changed during implementation testing.

- [x] **Step 1: Extend temporary installer assertions**

In `test_update_installs_three_skills_retires_sdk_and_preserves_unrelated_agent`, after loading the installed Agent, also read installed `ppt-start/SKILL.md` and assert:

```python
installed_skill = (claude_skills / "ppt-start" / "SKILL.md").read_text(encoding="utf-8")
self.assertIn("bounded generation wave", installed_skill)
self.assertIn("default width is 5", installed_skill)
self.assertNotIn("A turn may make at most one real generator call for one page", installed_skill)
```

Keep the existing exact tree digest comparison, retired SDK cleanup and unrelated Agent preservation assertions.

- [x] **Step 2: Run installer and focused regression tests**

Run:

```bash
python -B -m unittest tests.test_tools_package tests.test_parallel_generation_contract tests.test_ai_workflow_contract tests.test_interaction_protocol tests.test_skill_package tests.test_ppt_editable_contract -v
```

Expected: PASS. PowerShell tests may skip only when PowerShell is unavailable.

- [x] **Step 3: Run the complete suite**

Run:

```bash
PYTHONIOENCODING=utf-8 python -B -m unittest discover -s tests -v
```

Expected: PASS with only documented environment/capability skips. Record exact totals without representing static/oracle coverage as real multi-Agent overlap.

- [x] **Step 4: Verify no scheduler or workflow helper reappeared**

Run:

```bash
python -B -c "from pathlib import Path; expected={'_source_intake.py','_svg_geometry.py','_svg_runtime.py','_xml_safety.py','ppt_source_intake.py','svg_tool.py'}; actual={p.name for p in Path('skills/ppt-start/scripts').glob('*.py')}; assert actual == expected, (actual, expected); print(sorted(actual))"
```

Expected: the six existing stateless files only.

Run:

```bash
if git grep -n -E 'ppt_concurrency|_generation_concurrency' -- skills README.md docs/ARCHITECTURE.md docs/USER-GUIDE.md docs/RESILIENT-WORKFLOW.md; then exit 1; else printf '%s\n' 'No retired scheduler helpers in active surfaces'; fi
```

```bash
if git grep -n 'active_visual_generation_batch' -- skills/ppt-start README.md docs/ARCHITECTURE.md docs/USER-GUIDE.md docs/RESILIENT-WORKFLOW.md; then exit 1; else printf '%s\n' 'No retired batch owner in ppt-start or public guidance'; fi
```

Expected: no active matches. The separate legacy delivery adapter may still name `active_visual_generation_batch` when validating historical evidence; that is not an active `ppt-start` owner. Historical `docs/superpowers/**` and `acceptance-evidence/**` are excluded.

- [x] **Step 5: Run final static checks and report evidence limits**

Run:

```bash
git -c core.safecrlf=false diff --check
```

Expected: no whitespace errors.

Run:

```bash
git status --short
```

Expected: only this uncommitted implementation/spec/plan set. Report that real 2+ Agent overlap remains Host-level acceptance until exercised in a restarted host session; do not deploy, commit, push or update a PR.

## Plan self-review

- **Spec coverage:** Task 1 covers width, every run/stage/snapshot/input/dependency gate, no-empty-wave behavior, exactly-once attribution, attempts, resume, contiguous publication order, sibling isolation and prior-final preservation. Task 2 updates every active agent-facing owner and public behavior. Task 3 prevents in-flight delivery. Task 4 verifies package fidelity and explicitly separates static/oracle evidence from Host evidence.
- **No placeholders:** All snippets use concrete slide IDs, wave IDs, task IDs and valid example digests. No TBD/TODO or undefined production function is referenced.
- **Interface consistency:** `active_generation_wave`, `target_width`, `ordered_slide_ids`, `prompt_sha256`, `accepted_tasks`, `task_id`, `attempt` and `state` use the same names in the design, tests, docs and editable guard.
- **Scope discipline:** No shipped concurrency code or runtime scheduler is added. The only production Python change is the narrow final-delivery guard.

## Execution record — 2026-09-27

- Baseline: 431 tests passed with 6 documented skips.
- TDD: the active serial-contract tests and editable active-wave test failed for the expected missing behavior before their fixes; review follow-ups also demonstrated the publication, snapshot-gate, retry-authorization and empty-wave defects before correction.
- Focused regression: 95 tests passed with 1 environment skip.
- Final repository suite: 442 tests passed with 6 documented skips.
- Independent review: four findings were corrected; the second pass reported no unresolved verified findings.
- Static checks: exact six-file stateless script inventory, no retired scheduler/batch owner in active `ppt-start` guidance, no stale one-page-call rule, plan oracle byte-equivalent to its test source, and `git diff --check` clean.
- Evidence limit: real 2+ Agent overlap remains Host-level acceptance. This working tree was not committed, pushed, used to update a PR, or deployed to local hosts.
