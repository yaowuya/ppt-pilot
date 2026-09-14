"""Behavior tests for the read-only dashboard projection."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE = Path(__file__).resolve().parents[1] / "skills/ppt-start/scripts/_dashboard/snapshot.py"
SCRIPTS = MODULE.parent.parent
ASSETS = MODULE.parents[2] / "assets/dashboard"
if str(SCRIPTS) not in os.sys.path:
    os.sys.path.insert(0, str(SCRIPTS))
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><text>One</text></svg>'


class DashboardSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "deck"
        self.root.mkdir()

    def module(self):
        self.assertTrue(MODULE.is_file(), "The dashboard state projection is not implemented")
        spec = importlib.util.spec_from_file_location("dashboard_snapshot_under_test", MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def put(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        elif isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def run_state(self, **changes):
        state = {"schema_version": 1, "deck_id": "deck", "mode": "guided", "stage": "brief",
                 "manuscript_review": {"state": "pending"}, "dirty_slides": []}
        if isinstance(changes.get('delivery'), dict):
            state['manuscript_review'] = {'required': True, 'state': 'manuscript_approved',
                                         'status': 'PASSED', 'open_blocking_findings': []}
        state.update(changes)
        return state

    def snapshot(self):
        return self.module().build_snapshot(self.root)

    def batch(self, state="generating"):
        fixture = Path(__file__).parent / "fixtures/visual-generation-batch-v2-cases.json"
        case = copy.deepcopy(json.loads(fixture.read_text(encoding="utf-8"))["cases"]["one-slide-final"])
        transaction = next(iter(case["transactions"].values()))
        transaction["state"] = state
        self.put(case["run"]["active_visual_generation_batch"]["manifest_path"], case["manifest"])
        for path, data in case["transactions"].items():
            self.put(path, data)
        self.put(".ppt-pilot/run.json", self.run_state(stage="production", **case["run"]))
        return case, transaction

    def save_transaction(self, case):
        for path, data in case["transactions"].items():
            self.put(path, data)

    def sha(self, relative):
        return "sha256:" + hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def prepare_partial_delivery(self, *, omission_reason="attempts_exhausted",
                                 failure_reason="svg_contract_failed",
                                 generation_attempt=3):
        storyboard = "# 故事板\n## S01\n- `slide_id`: `S01`\n- `assertion_title`: 完成页\n## S02\n- `slide_id`: `S02`\n- `assertion_title`: 缺失页\n"
        self.put(".ppt-pilot/故事板.md", storyboard)
        self.put(".ppt-pilot/theme.json", {"name": "synthetic"})
        self.put(".ppt-pilot/质量检查报告.md", "S01 reviewed PASS; S02 omitted.")
        self.put("slides/S01.svg", SVG)
        transaction_id = "sha256:" + "b" * 64
        transaction_ref = (
            ".ppt-pilot/visual-generation-transactions/S02-" + "b" * 64 + ".json"
        )
        transaction = {
            "schema_version": 2,
            "kind": "visual_generation_transaction",
            "batch_id": "batch-partial",
            "slide_id": "S02",
            "transaction_id": transaction_id,
            "state": "failed",
            "failure_reason": failure_reason,
            "generation_attempt": generation_attempt,
        }
        self.put(transaction_ref, transaction)
        self.put(".ppt-pilot/visual-generation-batches/batch-partial.json", {
            "batch_id": "batch-partial",
            "state": "partial",
            "ordered_slide_ids": ["S01", "S02"],
            "transaction_refs": [
                ".ppt-pilot/visual-generation-transactions/S01-" + "a" * 64 + ".json",
                transaction_ref,
            ],
            "omitted_transaction_refs": [transaction_ref],
            "omitted_transaction_sha256": {
                transaction_ref: self.sha(transaction_ref),
            },
        })
        delivery = {
            "schema_version": 1,
            "status": "partial",
            "policy": "best_effort",
            "target_slide_ids": ["S01", "S02"],
            "delivered_slide_ids": ["S01"],
            "missing_slides": [{
                "slide_id": "S02",
                "reason": omission_reason,
                "failure_reason": failure_reason,
                "generation_attempt": generation_attempt,
                "transaction_id": transaction_id,
                "transaction_ref": transaction_ref,
                "transaction_sha256": self.sha(transaction_ref),
            }],
            "storyboard_sha256": self.sha(".ppt-pilot/故事板.md"),
            "theme_sha256": self.sha(".ppt-pilot/theme.json"),
            "quality_report_sha256": self.sha(".ppt-pilot/质量检查报告.md"),
            "slide_sha256": {"S01": self.sha("slides/S01.svg")},
        }
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="partial",
            production_policy="best_effort",
            dirty_slides=["S02"],
            delivery=delivery,
        ))
        return delivery

    def prepare_active_batch(self, first_failure="generator_timeout"):
        batch_id = "batch-locality"
        refs = []
        transactions = {}
        for sid, digest, state in (("S01", "a" * 64, "failed"),
                                   ("S02", "b" * 64, "generating")):
            transaction_id = "sha256:" + digest
            ref = (
                ".ppt-pilot/visual-generation-transactions/" + sid + "-" + digest + ".json"
            )
            refs.append(ref)
            transaction = {
                "schema_version": 2,
                "kind": "visual_generation_transaction",
                "batch_id": batch_id,
                "slide_id": sid,
                "transaction_id": transaction_id,
                "prompt_snapshot_id": transaction_id,
                "candidate_path": "slides/.candidates/" + sid + "-" + digest + ".svg",
                "final_path": "slides/" + sid + ".svg",
                "state": state,
                "generation_attempt": 1,
            }
            if state == "failed":
                transaction["failure_reason"] = first_failure
            transactions[ref] = transaction
            self.put(ref, transaction)
        manifest_path = ".ppt-pilot/visual-generation-batches/" + batch_id + ".json"
        self.put(manifest_path, {
            "schema_version": 2,
            "kind": "visual_generation_batch",
            "batch_id": batch_id,
            "state": "generating",
            "ordered_slide_ids": ["S01", "S02"],
            "transaction_refs": refs,
        })
        self.put(".ppt-pilot/故事板.md", (
            "## S01\n- `slide_id`: `S01`\n- `assertion_title`: 失败页\n"
            "## S02\n- `slide_id`: `S02`\n- `assertion_title`: 健康页\n"
        ))
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="production",
            dirty_slides=["S01", "S02"],
            active_visual_generation_batch={
                "schema_version": 2,
                "batch_id": batch_id,
                "manifest_path": manifest_path,
            },
        ))
        return refs, transactions

    def prepare_failed_delivery(self):
        delivery = self.prepare_partial_delivery()
        (self.root / "slides/S01.svg").unlink()
        transaction_id = "sha256:" + "a" * 64
        transaction_ref = (
            ".ppt-pilot/visual-generation-transactions/S01-" + "a" * 64 + ".json"
        )
        self.put(transaction_ref, {
            "schema_version": 2,
            "kind": "visual_generation_transaction",
            "batch_id": "batch-partial",
            "slide_id": "S01",
            "transaction_id": transaction_id,
            "state": "failed",
            "failure_reason": "generator_timeout",
            "generation_attempt": 3,
        })
        second = delivery["missing_slides"][0]
        self.put(".ppt-pilot/visual-generation-batches/batch-partial.json", {
            "batch_id": "batch-partial",
            "state": "failed",
            "ordered_slide_ids": ["S01", "S02"],
            "transaction_refs": [transaction_ref, second["transaction_ref"]],
            "omitted_transaction_refs": [transaction_ref, second["transaction_ref"]],
            "omitted_transaction_sha256": {
                transaction_ref: self.sha(transaction_ref),
                second["transaction_ref"]: second["transaction_sha256"],
            },
        })
        delivery.update(
            status="failed",
            delivered_slide_ids=[],
            quality_report_sha256=None,
            slide_sha256={},
        )
        delivery["missing_slides"].insert(0, {
            "slide_id": "S01",
            "reason": "attempts_exhausted",
            "failure_reason": "generator_timeout",
            "generation_attempt": 3,
            "transaction_id": transaction_id,
            "transaction_ref": transaction_ref,
            "transaction_sha256": self.sha(transaction_ref),
        })
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="failed",
            production_policy="best_effort",
            dirty_slides=["S01", "S02"],
            delivery=delivery,
        ))
        return delivery

    def test_valid_partial_delivery_counts_only_verified_declared_outputs(self):
        self.prepare_partial_delivery()

        snap = self.snapshot()

        self.assertEqual(snap["status"], "partial")
        self.assertEqual(snap["progress"], {
            "done": 1, "total": 2, "delivered": 1, "processed": 2,
        })
        self.assertEqual([slide["id"] for slide in snap["slides"]], ["S01", "S02"])
        self.assertEqual([slide["status"] for slide in snap["slides"]], ["delivered", "failed"])
        self.assertEqual(snap["delivery"], {
            "status": "partial",
            "policy": "best_effort",
            "target_slide_ids": ["S01", "S02"],
            "delivered_slide_ids": ["S01"],
            "missing_slides": [{
                "slide_id": "S02",
                "reason": "attempts_exhausted",
                "failure_reason": "svg_contract_failed",
                "generation_attempt": 3,
            }],
        })
        public = json.dumps(snap, ensure_ascii=False)
        self.assertNotIn("visual-generation-transactions", public)
        self.assertNotIn("transaction_id", public)
        self.assertNotEqual(snap["status"], "complete")

    def test_malformed_partial_delivery_fails_closed_without_svg_completion(self):
        delivery = self.prepare_partial_delivery()
        delivery["delivered_slide_ids"] = ["S01", "S02"]
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="partial",
            production_policy="best_effort",
            dirty_slides=["S02"],
            delivery=delivery,
        ))

        snap = self.snapshot()

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "invalid_delivery")
        self.assertEqual(snap["delivery"], None)
        self.assertEqual(snap["progress"], {
            "done": 0, "total": 2, "delivered": 0, "processed": 0,
        })
        self.assertNotIn("delivered", [slide["status"] for slide in snap["slides"]])
        tasks = {task["id"]: task for task in snap["tasks"]}
        self.assertNotIn("partial", [task["status"] for task in snap["tasks"]])
        self.assertEqual(tasks["complete"]["status"], "pending")

    def test_terminal_stage_without_delivery_metadata_is_not_trusted(self):
        for stage in ("partial", "failed"):
            with self.subTest(stage=stage):
                self.put(".ppt-pilot/run.json", self.run_state(stage=stage))
                snap = self.snapshot()
                self.assertEqual(snap["status"], "unknown")
                self.assertTrue(all(
                    task["status"] == "pending" for task in snap["tasks"]
                ))

    def test_omitted_page_keeps_old_svg_as_stale_preview_not_delivery(self):
        self.prepare_partial_delivery(
            omission_reason="user_skipped",
            failure_reason="svg_contract_failed",
            generation_attempt=1,
        )
        self.put("slides/S02.svg", SVG.replace(b"One", b"Old"))

        snap = self.snapshot()
        omitted = snap["slides"][1]

        self.assertEqual(omitted["status"], "omitted")
        self.assertTrue(omitted["stale_preview"])
        self.assertEqual(omitted["preview_kind"], "final")
        self.assertIn("用户已跳过", omitted["detail"])
        self.assertIn("SVG 合规校验失败", omitted["detail"])
        self.assertIn("旧版正式预览", omitted["detail"])
        self.assertEqual(snap["progress"]["delivered"], 1)
        self.assertEqual(snap["progress"]["processed"], 2)

    def test_page_local_failed_transaction_does_not_block_healthy_sibling(self):
        self.prepare_active_batch("generator_timeout")

        snap = self.snapshot()
        slides = {slide["id"]: slide for slide in snap["slides"]}

        self.assertEqual(snap["status"], "running")
        self.assertEqual(slides["S01"]["status"], "failed")
        self.assertIn("生成器响应超时", slides["S01"]["detail"])
        self.assertEqual(slides["S02"]["status"], "running")
        self.assertEqual(snap["progress"], {
            "done": 0, "total": 2, "delivered": 0, "processed": 1,
        })
        self.assertEqual(snap["notice"]["kind"], "page_failures")
        self.assertIn("S01", snap["notice"]["message"])
        self.assertIn("S02", snap["notice"]["message"])

    def test_all_declared_page_failure_reasons_remain_page_local(self):
        reasons = (
            "generator_refused", "generator_timeout", "generator_output_malformed",
            "svg_contract_failed", "fact_source_mismatch", "visual_qa_failed",
        )
        for reason in reasons:
            with self.subTest(reason=reason):
                self.prepare_active_batch(reason)
                snap = self.snapshot()
                self.assertEqual(snap["status"], "running")
                self.assertEqual(snap["slides"][0]["status"], "failed")
                self.assertEqual(snap["slides"][1]["status"], "running")

    def test_generator_unavailable_still_globally_blocks_active_batch(self):
        self.prepare_active_batch("generator_unavailable")

        snap = self.snapshot()

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "generation_state")
        self.assertEqual(snap["slides"][0]["status"], "blocked")
        self.assertEqual(snap["slides"][1]["status"], "running")

    def test_zero_output_terminal_failure_is_not_complete_or_qa_complete(self):
        self.prepare_failed_delivery()

        snap = self.snapshot()
        tasks = {task["id"]: task for task in snap["tasks"]}

        self.assertEqual(snap["status"], "failed")
        self.assertEqual(snap["notice"]["kind"], "failed_delivery")
        self.assertEqual(snap["progress"], {
            "done": 0, "total": 2, "delivered": 0, "processed": 2,
        })
        self.assertEqual([slide["status"] for slide in snap["slides"]], ["failed", "failed"])
        self.assertEqual(tasks["production"]["status"], "failed")
        self.assertEqual(tasks["qa"]["status"], "pending")
        self.assertEqual(tasks["complete"]["status"], "pending")

    def test_delivery_rejects_stale_artifacts_and_unverified_omissions(self):
        mutations = {
            "storyboard": lambda: self.put(".ppt-pilot/故事板.md", "changed"),
            "theme": lambda: self.put(".ppt-pilot/theme.json", {"name": "changed"}),
            "qa": lambda: self.put(".ppt-pilot/质量检查报告.md", "changed"),
            "formal_svg": lambda: self.put("slides/S01.svg", SVG.replace(b"One", b"Changed")),
            "omission": self.remove_omission_authorization,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.prepare_partial_delivery()
                mutate()
                snap = self.snapshot()
                self.assertEqual(snap["status"], "blocked")
                self.assertEqual(snap["notice"]["kind"], "invalid_delivery")
                self.assertEqual(snap["progress"]["delivered"], 0)
                self.assertNotIn("delivered", [slide["status"] for slide in snap["slides"]])

    def remove_omission_authorization(self):
        path = self.root / ".ppt-pilot/visual-generation-batches/batch-partial.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["omitted_transaction_refs"] = []
        self.put(".ppt-pilot/visual-generation-batches/batch-partial.json", manifest)

    def test_delivery_target_inventory_cannot_shrink_storyboard(self):
        delivery = self.prepare_partial_delivery()
        delivery.update(
            status="complete",
            target_slide_ids=["S01"],
            delivered_slide_ids=["S01"],
            missing_slides=[],
        )
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="complete",
            production_policy="best_effort",
            delivery=delivery,
        ))

        snap = self.snapshot()

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "invalid_delivery")
        self.assertEqual(snap["progress"]["delivered"], 0)
        self.assertEqual(snap["progress"]["total"], 2)

    def test_explicit_complete_delivery_uses_verified_target_inventory(self):
        delivery = self.prepare_partial_delivery()
        self.put("slides/S02.svg", SVG.replace(b"One", b"Two"))
        delivery.update(
            status="complete",
            delivered_slide_ids=["S01", "S02"],
            missing_slides=[],
            slide_sha256={
                "S01": self.sha("slides/S01.svg"),
                "S02": self.sha("slides/S02.svg"),
            },
        )
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="complete",
            production_policy="best_effort",
            delivery=delivery,
        ))

        snap = self.snapshot()

        self.assertEqual(snap["status"], "complete")
        self.assertEqual(snap["progress"], {
            "done": 2, "total": 2, "delivered": 2, "processed": 2,
        })
        self.assertEqual([slide["status"] for slide in snap["slides"]], ["delivered", "delivered"])

    def test_invalid_complete_delivery_does_not_claim_qa_completion(self):
        delivery = self.prepare_partial_delivery()
        self.put("slides/S02.svg", SVG.replace(b"One", b"Two"))
        delivery.update(
            status="complete",
            delivered_slide_ids=["S01", "S02"],
            missing_slides=[],
            slide_sha256={
                "S01": self.sha("slides/S01.svg"),
                "S02": self.sha("slides/S02.svg"),
            },
        )
        self.put(".ppt-pilot/质量检查报告.md", "stale after delivery")
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="complete",
            production_policy="best_effort",
            delivery=delivery,
        ))

        snap = self.snapshot()
        tasks = {task["id"]: task for task in snap["tasks"]}

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "invalid_delivery")
        self.assertEqual(tasks["production"]["status"], "blocked")
        self.assertEqual(tasks["qa"]["status"], "pending")
        self.assertEqual(tasks["complete"]["status"], "pending")

    def test_dirty_declared_output_does_not_erase_healthy_delivery_count(self):
        delivery = self.prepare_partial_delivery()
        self.put("slides/S02.svg", SVG.replace(b"One", b"Two"))
        delivery.update(
            status="complete",
            delivered_slide_ids=["S01", "S02"],
            missing_slides=[],
            slide_sha256={
                "S01": self.sha("slides/S01.svg"),
                "S02": self.sha("slides/S02.svg"),
            },
        )
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="complete",
            production_policy="best_effort",
            dirty_slides=["S02"],
            delivery=delivery,
        ))

        snap = self.snapshot()

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "invalid_delivery")
        self.assertEqual(snap["progress"], {
            "done": 1, "total": 2, "delivered": 1, "processed": 2,
        })
        self.assertEqual([slide["status"] for slide in snap["slides"]], [
            "delivered", "blocked",
        ])

    def test_prepared_delivery_is_not_complete_while_qa_is_actionable(self):
        delivery = self.prepare_partial_delivery()
        delivery.update(status="prepared", quality_report_sha256=None)
        self.put(".ppt-pilot/run.json", self.run_state(
            stage="qa",
            production_policy="best_effort",
            dirty_slides=["S02"],
            delivery=delivery,
        ))

        snap = self.snapshot()
        tasks = {task["id"]: task for task in snap["tasks"]}

        self.assertEqual(snap["status"], "prepared")
        self.assertNotEqual(snap["status"], "complete")
        self.assertEqual(snap["notice"]["kind"], "prepared_delivery")
        self.assertEqual(tasks["production"]["status"], "complete")
        self.assertEqual(tasks["qa"]["status"], "running")
        self.assertEqual(tasks["complete"]["status"], "pending")
        self.assertEqual(snap['progress']['done'], 1)
        self.assertEqual(snap['progress']['delivered'], 0)
        self.assertEqual(snap['slides'][0]['status'], 'ready')

    def test_incidental_svg_alone_cannot_complete_legacy_run(self):
        self.put(".ppt-pilot/run.json", self.run_state(stage="complete"))
        self.put("slides/S01.svg", SVG)

        snap = self.snapshot()

        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["notice"]["kind"], "incomplete_delivery")
        self.assertNotEqual(snap["status"], "complete")

    def test_runtime_structured_storyboard_preserves_original_targets_and_titles(self):
        self.put('run.json', self.run_state(stage='production'))
        value = {'outline_snapshot_id': 'sha256:' + 'a' * 64,
                 'storyboard_snapshot_id': 'sha256:' + 'b' * 64,
                 'slides': [{'slide_id': 'S01', 'assertion_title': '首要结论'},
                            {'slide_id': 'S02', 'assertion_title': '支持证据'},
                            {'slide_id': 'S03', 'assertion_title': '下一步'}]}
        self.put('.ppt-pilot/故事板.md', '# 故事板\n\n```ppt-pilot-json\n' + json.dumps(value, ensure_ascii=False) + '\n```\n')
        snap = self.snapshot()
        self.assertEqual(snap['progress']['total'], 3)
        self.assertEqual([slide['title'] for slide in snap['slides']], ['首要结论', '支持证据', '下一步'])
        self.assertIn('已解析 3 页', next(t['detail'] for t in snap['tasks'] if t['id'] == 'storyboard'))

    def test_empty_directory_waits_without_creating_state(self):
        before = list(self.root.iterdir())
        first = self.snapshot()
        self.assertEqual(first["status"], "waiting")
        self.assertEqual(first["slides"], [])
        self.assertEqual(first["progress"], {"done": 0, "total": 0})
        self.assertEqual(len(first["tasks"]), 10)
        self.assertEqual(first["revision"], self.snapshot()["revision"])
        self.assertEqual(before, list(self.root.iterdir()))

    def test_new_and_legacy_run_layouts_read_same_state(self):
        for path in [".ppt-pilot/run.json", "run.json"]:
            with self.subTest(path=path):
                run = self.put(path, self.run_state(stage="outline"))
                snap = self.snapshot()
                self.assertEqual(snap["deck_id"], "deck")
                self.assertEqual(snap["stage"], "outline")
                self.assertEqual(snap["status"], "running")
                self.assertIn(path, [item["path"] for item in snap["artifacts"]])
                self.assertTrue(snap["updated_at"].endswith("Z"))
                run.unlink()

    def test_two_run_files_fail_closed_even_when_identical(self):
        for path in ["run.json", ".ppt-pilot/run.json"]:
            self.put(path, self.run_state(stage="complete"))
        self.put("slides/S01.svg", SVG)
        snap = self.snapshot()
        self.assertEqual(snap["status"], "blocked")
        self.assertTrue(snap["warnings"])
        self.assertEqual(snap["slides"], [])
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.module().read_preview(self.root, "slides/S01.svg")

    def test_storyboard_ids_titles_counts_and_dirty_are_preserved(self):
        self.put(".ppt-pilot/run.json", self.run_state(stage="production", dirty_slides=["S07"], slide_count=2))
        self.put(".ppt-pilot/故事板.md", "# 故事板\n## S02\n- `slide_id`: `S02`\n- `assertion_title`: 结论一\n## S07\n- `slide_id`: `S07`\n- `assertion_title`: 结论二\n")
        self.put("slides/S02.svg", SVG)
        self.put("slides/S07.svg", SVG)
        snap = self.snapshot()
        self.assertEqual([slide["id"] for slide in snap["slides"]], ["S02", "S07"])
        self.assertEqual([slide["title"] for slide in snap["slides"]], ["结论一", "结论二"])
        self.assertTrue(snap["slides"][1]["dirty"])
        self.assertNotEqual(snap["slides"][1]["status"], "complete")
        self.assertEqual(snap["progress"], {"done": 1, "total": 2})
        self.assertIn("正式", snap["slides"][0]["detail"])

    def test_count_creates_waiting_pages_before_storyboard_exists(self):
        self.put("run.json", self.run_state(stage="storyboard", slide_count=3))
        snap = self.snapshot()
        self.assertEqual([slide["id"] for slide in snap["slides"]], ["S01", "S02", "S03"])
        self.assertEqual(snap["progress"], {"done": 0, "total": 3})

    def test_integer_slides_and_count_alias_create_all_planned_pages(self):
        for field in ("slides", "count"):
            with self.subTest(field=field):
                self.put("run.json", self.run_state(stage="production", **{field: 4}))
                self.put("slides/S01.svg", SVG)
                snap = self.snapshot()
                self.assertEqual([slide["id"] for slide in snap["slides"]], ["S01", "S02", "S03", "S04"])
                self.assertEqual(snap["progress"], {"done": 1, "total": 4})

    def test_open_observer_handle_does_not_block_coordinator_atomic_replace(self):
        module = self.module()
        path = self.put("run.json", self.run_state(stage="brief"))
        replacement = self.put("replacement.json", self.run_state(stage="production"))
        if os.name == "nt":
            # Some Windows/filesystem combinations reject replacing any open
            # target even with FILE_SHARE_DELETE. Establish that platform
            # capability using an independent ordinary Win32 handle first.
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            create.restype = wintypes.HANDLE
            close = kernel.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            control = self.put("control.json", {"state": "before"})
            control_new = self.put("control-new.json", {"state": "after"})
            handle = create(str(control), 0x80000000, 7, None, 3, 0x80, None)
            self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
            try:
                try:
                    os.replace(control_new, control)
                except PermissionError:
                    self.skipTest("This Windows filesystem rejects replacement of an independently opened FILE_SHARE_DELETE target")
            finally:
                close(handle)
        with module._open_regular(self.root, "run.json") as stream:
            original = stream.read()
            os.replace(replacement, path)
            stream.seek(0)
            self.assertEqual(stream.read(), original)
        self.assertEqual(self.snapshot()["stage"], "production")

    def test_legacy_storyboard_and_sample_are_visible_without_claiming_completion(self):
        self.put("run.json", self.run_state(stage="anchor"))
        self.put("storyboard.md", "## S09\n- **slide_id**: S09\n- **assertion_title**: Sample\n")
        self.put("samples/S09.svg", SVG)
        snap = self.snapshot()
        slide = snap["slides"][0]
        self.assertEqual((slide["id"], slide["title"], slide["preview_kind"]), ("S09", "Sample", "sample"))
        self.assertEqual(snap["progress"], {"done": 0, "total": 1})

    def test_current_layout_sample_is_visible_and_preferred_to_legacy(self):
        self.put(".ppt-pilot/run.json", self.run_state(stage="anchor", slides=1))
        self.put(".ppt-pilot/samples/S01.svg", SVG)
        self.put("samples/S01.svg", SVG.replace(b"One", b"Old"))
        snap = self.snapshot()
        self.assertEqual(snap["slides"][0]["preview_path"], ".ppt-pilot/samples/S01.svg")
        self.assertEqual(snap["slides"][0]["preview_kind"], "sample")
        self.assertEqual(self.module().read_preview(self.root, ".ppt-pilot/samples/S01.svg"), SVG)
        self.assertEqual(snap["progress"]["done"], 0)

    def test_research_document_activity_changes_revision_at_same_stage(self):
        self.put(".ppt-pilot/run.json", self.run_state(stage="research"))
        self.put(".ppt-pilot/研究.md", "Initial findings")
        first = self.snapshot()
        self.assertIn(".ppt-pilot/研究.md", [item["path"] for item in first["artifacts"]])
        self.put(".ppt-pilot/研究.md", "Updated findings")
        second = self.snapshot()
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(second["stage"], "research")

    def test_pending_interaction_precedes_review_blocker_and_batch(self):
        state = self.run_state(stage="production", pending_interaction={"id": "p", "stage": "production", "kind": "question", "question": "选择哪个方向？", "status": "pending"},
                               visual_generation_blocker={"status": "active", "slide_id": "S01", "reason": "registry_missing"},
                               active_visual_generation_batch={"schema_version": 2, "batch_id": "missing", "manifest_path": ".ppt-pilot/visual-generation-batches/missing.json"})
        state["manuscript_review"]["pending_round"] = {"status": "in_progress", "round": 1}
        self.put("run.json", state)
        snap = self.snapshot()
        self.assertEqual(snap["status"], "waiting")
        self.assertEqual(snap["notice"]["kind"], "pending_interaction")
        self.assertIn("选择哪个方向", snap["notice"]["message"])
        del state["pending_interaction"]
        self.put("run.json", state)
        self.assertEqual(self.snapshot()["notice"]["kind"], "pending_review")
        del state["manuscript_review"]["pending_round"]
        self.put("run.json", state)
        self.assertEqual(self.snapshot()["notice"]["kind"], "visual_generation_blocker")

    def test_answered_interaction_is_awaiting_application_not_asking_again(self):
        self.put("run.json", self.run_state(pending_interaction={"id": "p", "stage": "brief", "kind": "question", "question": "用途？", "status": "answered", "answer": "汇报"}))
        snap = self.snapshot()
        self.assertEqual(snap["status"], "waiting")
        self.assertIn("已回答", snap["notice"]["message"])

    def test_each_stage_has_its_own_goal_before_any_artifacts_exist(self):
        tasks = self.snapshot()["tasks"]
        self.assertEqual(len({task["detail"] for task in tasks}), 10)
        for task in tasks:
            with self.subTest(stage=task["id"]):
                self.assertEqual(task["status"], "pending")
                self.assertGreater(len(task["detail"]), 20)
                self.assertNotIn("依据已记录的流程阶段", task["detail"])
                self.assertNotIn("已通过", task["detail"])

    def test_step_details_include_observed_outputs_without_document_bodies(self):
        self.put("run.json", self.run_state(stage="production", dirty_slides=["S02"],
                 manuscript_review={"state": "manuscript_approved", "cycle": 1, "round": 2,
                                    "open_blocking_findings": []}))
        for path in (".ppt-pilot/简报.md", ".ppt-pilot/研究.md", ".ppt-pilot/来源.md",
                     "大纲.md", ".ppt-pilot/文稿审查.md", ".ppt-pilot/theme.json",
                     ".ppt-pilot/质量检查报告.md"):
            self.put(path, "PRIVATE_DOCUMENT_BODY")
        self.put(".ppt-pilot/故事板.md", "## S01\n## S02\n## S03\n")
        self.put("slides/S01.svg", SVG)
        self.put("slides/S02.svg", SVG)
        self.put(".ppt-pilot/samples/S03.svg", SVG)
        snap = self.snapshot()
        details = {task["id"]: task["detail"] for task in snap["tasks"]}
        expected = {
            "brief": ["简报.md"], "research": ["研究.md", "来源.md"],
            "outline": ["大纲.md"], "storyboard": ["已解析 3 页"],
            "manuscript_review": ["第 2 轮", "未解决阻断 0 项", "文稿审查.md"],
            "theme": ["theme.json"], "anchor": ["可预览样张 1 页"],
            "production": ["正式页 1 / 3 页", "待更新 1 页"],
            "qa": ["质量检查报告.md", "不代表检查通过"],
            "complete": ["正式页 1 / 3 页", "尚未确认交付完成"],
        }
        for stage, phrases in expected.items():
            with self.subTest(stage=stage):
                for phrase in phrases:
                    self.assertIn(phrase, details[stage])
        self.assertNotIn("PRIVATE_DOCUMENT_BODY", json.dumps(snap))
        self.assertNotIn(str(self.root), json.dumps(snap))

    def test_legacy_documents_are_identified_in_step_details(self):
        self.put("run.json", self.run_state(stage="research"))
        for path in ("brief.md", "research.md", "sources.md", "outline.md", "theme.json",
                     "manuscript-review.md", "qa-report.md"):
            self.put(path, "Legacy content")
        details = {task["id"]: task["detail"] for task in self.snapshot()["tasks"]}
        for stage, name in (("brief", "brief.md"), ("research", "research.md"),
                            ("outline", "outline.md"), ("theme", "theme.json"),
                            ("manuscript_review", "manuscript-review.md"), ("qa", "qa-report.md")):
            with self.subTest(stage=stage):
                self.assertIn(name, details[stage])
        self.assertIn("sources.md", details["research"])

    def test_planned_page_count_does_not_claim_storyboard_was_written(self):
        self.put("run.json", self.run_state(stage="storyboard", slide_count=4))
        task = next(task for task in self.snapshot()["tasks"] if task["id"] == "storyboard")
        self.assertIn("尚未发现故事板", task["detail"])
        self.assertNotIn("已解析 4 页", task["detail"])
        self.put("storyboard.md", "## S01\n## S02\n")
        task = next(task for task in self.snapshot()["tasks"] if task["id"] == "storyboard")
        self.assertIn("已解析 2 页", task["detail"])

    def test_review_detail_is_bounded_and_handles_invalid_counters(self):
        for review in ({"state": "review_unavailable", "cycle": [], "round": {},
                        "open_blocking_findings": "PRIVATE_REVIEW_DATA"},
                       {"state": "pending", "round": True, "cycle": -1},
                       {"state": "pending", "round": 10**100, "cycle": 10**100}):
            with self.subTest(review=review):
                self.put("run.json", self.run_state(stage="manuscript_review", manuscript_review=review))
                detail = next(task["detail"] for task in self.snapshot()["tasks"] if task["id"] == "manuscript_review")
                self.assertNotIn("PRIVATE_REVIEW_DATA", detail)
                self.assertNotIn("True", detail)
                self.assertLess(len(detail), 500)

    def test_current_step_shows_waiting_question_or_blocker(self):
        for changes, expected in (
            ({"pending_interaction": {"status": "pending", "question": "确认使用这个配色？"}}, "确认使用这个配色？"),
            ({"visual_generation_blocker": {"status": "active", "reason": "候选写入失败"}}, "候选写入失败"),
        ):
            with self.subTest(changes=changes):
                self.put("run.json", self.run_state(stage="theme", **changes))
                tasks = {task["id"]: task for task in self.snapshot()["tasks"]}
                self.assertIn(expected, tasks["theme"]["detail"])
                self.assertNotIn(expected, tasks["brief"]["detail"])

    def test_generation_details_distinguish_active_failed_and_finished_output(self):
        case, tx = self.batch("generating")
        for state, phrase in (("generating", "处理中 1 页"), ("failed", "受阻 1 页")):
            with self.subTest(state=state):
                tx["state"] = state
                self.save_transaction(case)
                task = next(task for task in self.snapshot()["tasks"] if task["id"] == "production")
                self.assertIn(phrase, task["detail"])
                self.assertIn("正式页 0 / 1 页", task["detail"])
        self.put(".ppt-pilot/run.json", self.run_state(stage="complete", slide_count=1))
        self.put("slides/S01.svg", SVG)
        task = next(task for task in self.snapshot()["tasks"] if task["id"] == "complete")
        self.assertIn("已记录交付完成", task["detail"])
        self.assertIn("正式页 1 / 1 页", task["detail"])

    def test_stage_checkpoints_map_to_workflow_tasks(self):
        self.put("run.json", self.run_state(stage="manuscript_approved"))
        tasks = {task["id"]: task for task in self.snapshot()["tasks"]}
        self.assertEqual(tasks["manuscript_review"]["status"], "complete")
        self.assertEqual(tasks["theme"]["status"], "pending")

    def test_review_blocked_stage_maps_to_current_review_task(self):
        for stage in ("manuscript_blocked", "review_unavailable"):
            with self.subTest(stage=stage):
                self.put("run.json", self.run_state(stage=stage))
                snap = self.snapshot()
                tasks = {task["id"]: task for task in snap["tasks"]}
                self.assertEqual(snap["status"], "blocked")
                self.assertEqual(tasks["storyboard"]["status"], "complete")
                self.assertEqual(tasks["manuscript_review"]["status"], "blocked")
                self.assertEqual(tasks["theme"]["status"], "pending")
                self.assertEqual(snap["notice"]["kind"], "pending_review")

    def test_candidate_is_not_exposed_until_durable_hash_matches(self):
        case, transaction = self.batch()
        self.put(transaction["candidate_path"], SVG)
        slide = self.snapshot()["slides"][0]
        self.assertEqual(slide["status"], "running")
        self.assertIsNone(slide["preview_path"])
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.module().read_preview(self.root, transaction["candidate_path"])
        transaction.update(state="candidate_written", candidate_sha256="sha256:" + hashlib.sha256(SVG).hexdigest())
        self.save_transaction(case)
        snap = self.snapshot()
        self.assertEqual(snap["slides"][0]["preview_kind"], "candidate")
        self.assertEqual(self.module().read_preview(self.root, transaction["candidate_path"]), SVG)
        self.put(transaction["candidate_path"], SVG.replace(b"One", b"Two"))
        invalid = self.snapshot()
        self.assertIsNone(invalid["slides"][0]["preview_path"])
        self.assertEqual(invalid["status"], "blocked")
        self.assertTrue(invalid["warnings"])

    def test_candidate_read_rechecks_current_owner_not_historic_allowlist(self):
        case, tx = self.batch("validated")
        tx["candidate_sha256"] = "sha256:" + hashlib.sha256(SVG).hexdigest()
        self.put(tx["candidate_path"], SVG)
        self.save_transaction(case)
        self.assertEqual(self.module().read_preview(self.root, tx["candidate_path"]), SVG)
        self.put(".ppt-pilot/run.json", self.run_state(stage="production"))
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.module().read_preview(self.root, tx["candidate_path"])

    def test_candidate_read_rechecks_bytes_after_snapshot_allowlist(self):
        case, tx = self.batch("validated")
        tx["candidate_sha256"] = "sha256:" + hashlib.sha256(SVG).hexdigest()
        self.put(tx["candidate_path"], SVG)
        self.save_transaction(case)
        module = self.module()
        original_read = module._read
        candidate_reads = 0

        def read_then_replace(root, relative, limit):
            nonlocal candidate_reads
            if relative == tx["candidate_path"]:
                candidate_reads += 1
                if candidate_reads == 2:
                    self.put(relative, b'<svg malformed partial write')
            return original_read(root, relative, limit)

        with mock.patch.object(module, "_read", side_effect=read_then_replace):
            with self.assertRaises(ValueError):
                module.read_preview(self.root, tx["candidate_path"])

    def test_malformed_recovery_fields_do_not_crash_or_claim_complete(self):
        for change in (
            {"pending_interaction": {"status": []}},
            {"pending_interaction": ["bad"]},
            {"manuscript_review": {"state": []}},
            {"manuscript_review": {"pending_round": "bad"}},
            {"visual_generation_blocker": {"status": []}},
            {"dirty_slides": "S01"},
        ):
            with self.subTest(change=change):
                self.put("run.json", self.run_state(stage="complete", slides=1, **change))
                self.put("slides/S01.svg", SVG)
                snap = self.snapshot()
                self.assertNotEqual(snap["status"], "complete")
                self.assertTrue(snap["warnings"])

    def test_active_ref_mismatch_is_blocked(self):
        case, transaction = self.batch()
        transaction["batch_id"] = "different-batch"
        self.save_transaction(case)
        snap = self.snapshot()
        self.assertEqual(snap["status"], "blocked")
        self.assertTrue(snap["warnings"])

    def test_dirty_page_preserves_running_or_failed_transaction_status(self):
        case, tx = self.batch("generating")
        self.put(".ppt-pilot/run.json", self.run_state(stage="production", dirty_slides=[tx["slide_id"]], **case["run"]))
        self.put(tx["final_path"], SVG)
        for state, expected in (("generating", "running"), ("failed", "blocked")):
            with self.subTest(state=state):
                tx["state"] = state
                self.save_transaction(case)
                snap = self.snapshot()
                self.assertEqual(snap["slides"][0]["status"], expected)
                self.assertTrue(snap["slides"][0]["dirty"])
                self.assertEqual(snap["progress"]["done"], 0)

    def test_pending_recomposition_does_not_count_old_final_as_current_output(self):
        case, tx = self.batch("generating")
        self.put(tx["final_path"], SVG)
        self.assertEqual(self.snapshot()["progress"]["done"], 0)

    def test_missing_transaction_is_diagnostic_not_complete(self):
        case, _ = self.batch()
        (self.root / next(iter(case["transactions"]))).unlink()
        snap = self.snapshot()
        self.assertEqual(snap["status"], "blocked")
        self.assertEqual(snap["progress"]["done"], 0)

    def test_partial_json_recovers_and_changes_revision_without_writes(self):
        file = self.put(".ppt-pilot/run.json", '{"stage":')
        before = file.read_bytes()
        bad = self.snapshot()
        self.assertEqual(bad["status"], "unknown")
        self.assertTrue(bad["warnings"])
        self.assertEqual(file.read_bytes(), before)
        self.put(".ppt-pilot/run.json", self.run_state(stage="production"))
        good = self.snapshot()
        self.assertNotEqual(bad["revision"], good["revision"])
        self.assertFalse(good["warnings"])

    def test_overlimit_json_and_page_count_are_bounded(self):
        self.put("run.json", self.run_state(slide_count=10**9))
        snap = self.snapshot()
        self.assertLessEqual(len(snap["slides"]), 1000)
        self.assertTrue(snap["warnings"])
        self.put("run.json", b" " * (5 * 1024 * 1024))
        snap = self.snapshot()
        self.assertEqual(snap["status"], "unknown")
        self.assertTrue(snap["warnings"])

    def test_preview_version_changes_when_svg_bytes_change(self):
        self.put("run.json", self.run_state(stage="production"))
        self.put("slides/S01.svg", SVG)
        first = self.snapshot()
        self.put("slides/S01.svg", SVG.replace(b"One", b"Two"))
        second = self.snapshot()
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertNotEqual(first["slides"][0]["version"], second["slides"][0]["version"])

    def test_complete_with_dirty_or_missing_planned_final_is_not_complete(self):
        self.put("run.json", self.run_state(stage="complete", slide_count=2))
        self.put("slides/S01.svg", SVG)
        self.assertNotEqual(self.snapshot()["status"], "complete")
        self.put("slides/S02.svg", SVG)
        self.assertEqual(self.snapshot()["status"], "complete")
        self.put("run.json", self.run_state(stage="complete", slide_count=2, dirty_slides=["S02"]))
        self.assertNotEqual(self.snapshot()["status"], "complete")

    def test_preview_rejects_non_svg_unknown_paths_and_traversal(self):
        self.put("run.json", self.run_state(stage="production"))
        self.put("slides/S01.svg", SVG)
        self.put("private.svg", SVG)
        self.put("slides/S02.svg", b'{"secret":true}')
        module = self.module()
        for path in ["../private.svg", "/slides/S01.svg", "C:/secret.svg", "slides\\S01.svg", "slides/../private.svg", "private.svg", "run.json", "slides/S02.svg", "slides/S01.svg:secret", "slides/%2e%2e/private.svg"]:
            with self.subTest(path=path), self.assertRaises((ValueError, FileNotFoundError)):
                module.read_preview(self.root, path)
        self.assertEqual(module.read_preview(self.root, "slides/S01.svg"), SVG)

    def test_symbolic_links_are_not_followed(self):
        self.put("run.json", self.run_state(stage="production"))
        target = Path(self.temp.name) / "outside.svg"
        target.write_bytes(SVG)
        slides = self.root / "slides"
        slides.mkdir()
        try:
            (slides / "S01.svg").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symbolic links is not available to this user")
        snap = self.snapshot()
        self.assertFalse(any(slide["preview_path"] for slide in snap["slides"]))
        self.assertNotIn(str(target), json.dumps(snap))
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.module().read_preview(self.root, "slides/S01.svg")

    def test_frontend_progress_distinguishes_delivery_processing_and_target_total(self):
        markup = (ASSETS / "index.html").read_text(encoding="utf-8")
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="progress-processed"', markup)
        self.assertIn('progress.delivered', script)
        self.assertIn('progress.processed', script)
        self.assertIn("已交付 ${delivered}，已处理 ${processed}，原目标 ${total}", script)
        self.assertIn('"已产出正式页 / 原目标"', script)
        self.assertIn('"已交付 / 原目标"', script)

    def test_frontend_names_explicit_delivery_and_page_outcomes(self):
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        for label in ['prepared: "待质量检查"', 'partial: "部分交付"',
                      'delivered: "已交付"', 'omitted: "已跳过"']:
            with self.subTest(label=label):
                self.assertIn(label, script)
        self.assertIn('status === "omitted"', script)
        self.assertIn('status === "failed"', script)
        self.assertIn('status === "delivered"', script)

    def test_frontend_marks_omitted_formal_preview_as_old_and_undelivered(self):
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        self.assertIn("slide.stale_preview === true", script)
        self.assertIn("旧版预览 · 未计入交付", script)
        self.assertIn('element("preview-dirty").hidden = !(url && (slide.dirty || slide.stale_preview === true))', script)

    def test_partial_delivery_cannot_hide_an_unapproved_content_node(self):
        self.prepare_partial_delivery()
        path = self.root / '.ppt-pilot/run.json'
        run = json.loads(path.read_text(encoding='utf-8'))
        run['manuscript_review'] = {'required': True, 'state': 'pending', 'status': 'PENDING',
                                    'open_blocking_findings': []}
        self.put('.ppt-pilot/run.json', run)
        snap = self.snapshot()
        self.assertEqual(snap['status'], 'blocked')
        self.assertEqual(snap['progress']['delivered'], 0)

    def test_final_partial_delivery_is_finished_without_suggesting_exhausted_retries(self):
        self.prepare_partial_delivery()
        snap = self.snapshot()
        final_task = next(task for task in snap['tasks'] if task['id'] == 'complete')
        self.assertIn('本轮制作已结束', final_task['detail'])
        self.assertIn('部分交付', final_task['detail'])
        self.assertNotIn('尚未确认交付完成', final_task['detail'])
        missing = next(slide for slide in snap['slides'] if slide['id'] == 'S02')
        self.assertTrue(missing.get('terminal_omission'))
        self.assertIn('本轮不再自动重试', missing['detail'])
        self.assertNotIn('请修正后重新生成', missing['detail'])
        self.prepare_failed_delivery()
        failed = self.snapshot()
        self.assertNotIn('重试', failed['notice']['message'])

    def test_page_failure_notice_does_not_authorize_an_exhausted_retry(self):
        refs, transactions = self.prepare_active_batch()
        transactions[refs[0]]['generation_attempt'] = 3
        self.put(refs[0], transactions[refs[0]])
        snap = self.snapshot()
        self.assertNotIn('重试', snap['notice']['message'])
        self.assertIn('健康页面', snap['notice']['message'])

    def test_frontend_does_not_present_omitted_pages_as_still_preparing(self):
        script = (ASSETS / 'app.js').read_text(encoding='utf-8')
        self.assertIn('slide.terminal_omission === true', script)
        self.assertIn('"本页未交付"', script)
        self.assertIn('"本轮已跳过此页，不会自动重试。"', script)

    def test_frontend_explains_explicit_delivery_outcomes(self):
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        for copy_text in [
            'prepared: "交付范围已准备，等待质量检查"',
            'partial: "演示文稿已部分交付"',
            'failed: "演示文稿交付失败"',
            'prepared_delivery: "交付范围已准备，等待质量检查"',
            'partial_delivery: "本轮已结束，部分页面未交付"',
            'failed_delivery: "交付失败，尚无成功交付页面"',
        ]:
            with self.subTest(copy_text=copy_text):
                self.assertIn(copy_text, script)
        self.assertIn("OUTCOME_TITLES[status]", script)
        self.assertIn("NOTICE_TITLES[kind]", script)

    def test_frontend_maps_only_valid_terminal_delivery_to_actionable_stage(self):
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        self.assertIn('const TERMINAL_STAGE_IDS = { partial: "complete", failed: "production" }', script)
        self.assertIn('const actionable = state.tasks.find', script)
        self.assertIn('["running", "waiting", "blocked", "failed", "partial"].includes(task.status)', script)
        self.assertIn('status === stage && Object.hasOwn(TERMINAL_STAGE_IDS, stage)', script)
        self.assertIn('currentStageId(state)', script)

    def test_frontend_announces_delivered_processed_and_original_totals(self):
        script = (ASSETS / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            '`${STATUS_NAMES[state.status] || "状态已更新"}，已交付 ${delivered} 页，已处理 ${processed} 页，原目标 ${total} 页。`',
            script,
        )
        self.assertIn('const processed = element("progress-processed").textContent', script)
        self.assertIn('const total = element("progress-total").textContent', script)

    def test_frontend_status_palette_distinguishes_delivery_outcomes(self):
        styles = (ASSETS / "styles.css").read_text(encoding="utf-8")
        expectations = [
            r'\.stage-item\[data-status="failed"\]\s*\{[^}]*var\(--red-soft\)[^}]*var\(--red\)',
            r'\.stage-item\[data-status="partial"\][^{]*\{[^}]*var\(--amber-soft\)[^}]*var\(--amber\)',
            r'\.stage-item\[data-status="waiting"\][^{]*\{[^}]*var\(--amber-soft\)[^}]*var\(--amber\)',
            r'\.badge\[data-status="failed"\]\s*\{[^}]*var\(--red-soft\)[^}]*var\(--red\)',
            r'\[data-status="omitted"\] > \.slide-card-status[^{]*\{[^}]*var\(--amber\)',
            r'\[data-status="failed"\] > \.slide-card-status[^{]*\{[^}]*var\(--red\)',
            r'\.notice\[data-kind="prepared_delivery"\]\s*\{[^}]*var\(--blue-soft\)[^}]*var\(--blue\)',
            r'\.notice\[data-kind="failed_delivery"\][^{]*\{[^}]*var\(--red-soft\)[^}]*var\(--red\)',
        ]
        for pattern in expectations:
            with self.subTest(pattern=pattern):
                self.assertRegex(styles, pattern)


if __name__ == "__main__":
    unittest.main()
