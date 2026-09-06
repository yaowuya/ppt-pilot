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


if __name__ == "__main__":
    unittest.main()
