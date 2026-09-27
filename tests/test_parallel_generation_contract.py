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
