import importlib
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock
import zipfile

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "ppt-editable" / "scripts"
FIXTURE_RUN = REPO_ROOT / "tests" / "fixtures" / "ppt-editable" / "run-complete"
sys.path.insert(0, str(SCRIPTS_ROOT))


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run = self.root / "run"
        shutil.copytree(FIXTURE_RUN, self.run)

    def _module(self):
        return importlib.import_module("_ppt_editable.orchestrator")

    @staticmethod
    def _sha256(data):
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def _configure_partial_run(self):
        pilot = self.run / ".ppt-pilot"
        storyboard = pilot / "故事板.md"
        theme = pilot / "theme.json"
        quality = pilot / "质量检查报告.md"
        theme.write_text('{"name":"partial-test"}\n', encoding="utf-8")
        shutil.copy2(self.run / "samples" / "S01.svg", self.run / "slides" / "S01.svg")

        transaction_id = "sha256:" + "a" * 64
        transaction_ref = (
            ".ppt-pilot/visual-generation-transactions/S02-" + "a" * 64 + ".json"
        )
        transaction = {
            "schema_version": 2,
            "kind": "visual_generation_transaction",
            "batch_id": "batch-partial-test",
            "slide_id": "S02",
            "transaction_id": transaction_id,
            "state": "failed",
            "failure_reason": "svg_contract_failed",
            "generation_attempt": 3,
        }
        transaction_path = self.run / Path(transaction_ref)
        transaction_path.parent.mkdir(parents=True)
        transaction_bytes = json.dumps(
            transaction,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        transaction_path.write_bytes(transaction_bytes)

        batch_path = (
            pilot / "visual-generation-batches" / "batch-partial-test.json"
        )
        batch_path.parent.mkdir(parents=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": "batch-partial-test",
                    "state": "partial",
                    "ordered_slide_ids": ["S01", "S02"],
                    "transaction_refs": ["unused", transaction_ref],
                    "omitted_transaction_refs": [transaction_ref],
                    "omitted_transaction_sha256": {
                        transaction_ref: self._sha256(transaction_bytes)
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        missing = {
            "slide_id": "S02",
            "reason": "attempts_exhausted",
            "failure_reason": "svg_contract_failed",
            "generation_attempt": 3,
            "transaction_id": transaction_id,
            "transaction_ref": transaction_ref,
            "transaction_sha256": self._sha256(transaction_bytes),
        }
        run_path = pilot / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run.update(
            stage="partial",
            production_policy="best_effort",
            dirty_slides=["S02"],
            manuscript_review={'required': True, 'state': 'manuscript_approved', 'status': 'PASSED',
                               'open_blocking_findings': []},
            delivery={
                "schema_version": 1,
                "status": "partial",
                "policy": "best_effort",
                "target_slide_ids": ["S01", "S02"],
                "delivered_slide_ids": ["S01"],
                "missing_slides": [missing],
                "storyboard_sha256": self._sha256(storyboard.read_bytes()),
                "theme_sha256": self._sha256(theme.read_bytes()),
                "quality_report_sha256": self._sha256(quality.read_bytes()),
                "slide_sha256": {
                    "S01": self._sha256((self.run / "slides" / "S01.svg").read_bytes())
                },
            },
        )
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return missing

    def _configure_legacy_best_effort_complete_run(self):
        pilot = self.run / ".ppt-pilot"
        storyboard = pilot / "故事板.md"
        theme = pilot / "theme.json"
        quality = pilot / "质量检查报告.md"
        theme.write_text('{"name":"legacy-best-effort"}\n', encoding="utf-8")
        shutil.copy2(self.run / "samples" / "S01.svg", self.run / "slides" / "S01.svg")
        digest = lambda data: "sha256:" + hashlib.sha256(data).hexdigest()
        run_path = pilot / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run.update(
            stage="complete",
            production_policy="best_effort",
            dirty_slides=[],
            manuscript_review={
                "required": True,
                "state": "manuscript_approved",
                "status": "PASSED",
                "open_blocking_findings": [],
                "pending_round": None,
            },
            delivery={
                "schema_version": 1,
                "status": "complete",
                "policy": "best_effort",
                "target_slide_ids": ["S01", "S02"],
                "delivered_slide_ids": ["S01", "S02"],
                "missing_slides": [],
                "storyboard_sha256": digest(storyboard.read_bytes()),
                "theme_sha256": digest(theme.read_bytes()),
                "quality_report_sha256": digest(quality.read_bytes()),
                "slide_sha256": {
                    "S01": digest((self.run / "slides" / "S01.svg").read_bytes()),
                    "S02": digest((self.run / "slides" / "S02.svg").read_bytes()),
                },
            },
        )
        run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _configure_ai_state_partial_run(self):
        pilot = self.run / ".ppt-pilot"
        shutil.copy2(self.run / "samples" / "S01.svg", self.run / "slides" / "S01.svg")
        run_path = pilot / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run.update(
            stage="partial",
            manuscript_review={
                "required": True,
                "state": "manuscript_approved",
                "status": "PASSED",
                "open_blocking_findings": [],
                "pending_round": None,
            },
            slides={
                "S01": {
                    "state": "promoted",
                    "attempts": 1,
                    "svg": "slides/S01.svg",
                    "failure": None,
                    "qa": {"structure": "pass", "tool": "pass"},
                },
                "S02": {
                    "state": "failed",
                    "attempts": 2,
                    "svg": None,
                    "failure": {"code": "generator_unavailable", "message": "host unavailable"},
                    "qa": {"structure": "not_run", "tool": "unavailable"},
                },
            },
            delivery={"status": "partial"},
        )
        run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (pilot / "theme.json").write_text('{"name":"ai-state"}\n', encoding="utf-8")
        (pilot / "质量检查报告.md").write_text(
            "# QA\n\n```ppt-pilot-qa-json\n"
            '{"schema_version":1,"status":"partial","target_slide_ids":["S01","S02"],"promoted_slide_ids":["S01"],"missing_slide_ids":["S02"]}'
            "\n```\n",
            encoding="utf-8",
        )

    def _degraded(self):
        module = self._module()
        return module.GenerationCapability(
            office_available=False,
            pillow_available=True,
            office_runner=None,
        )

    def _office_runner(self, request):
        from _ppt_editable.office_protocol import OfficeResult

        shutil.copy2(request["candidate_path"], request["normalized_path"])
        renders = {}
        for key, directory in request["render_directories"].items():
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            entries = []
            for slide_id in request["ordered_slide_ids"]:
                path = directory / (slide_id + ".png")
                Image.new("L", (1280, 720), color=0).save(path)
                entries.append({"slide_id": slide_id, "path": str(path)})
            renders[key] = tuple(entries)
        return OfficeResult(
            capability=True,
            powerpoint_version="16.0",
            powerpoint_build="test",
            process_id=123,
            process_started_at="2026-08-30T00:00:00+00:00",
            process_owned=True,
            stages=(
                {"name": "capability", "status": "passed"},
                {"name": "normalize", "status": "running"},
                {"name": "normalize", "status": "passed"},
                {"name": "counts", "status": "running"},
                {"name": "counts", "status": "passed"},
                {"name": "source_decks", "status": "running"},
                {"name": "source_decks", "status": "passed"},
                {"name": "render", "status": "running"},
                {"name": "render", "status": "passed"},
            ),
            counts=dict(request["expected_counts"]),
            renders=renders,
            normalized_path=request["normalized_path"],
            error=None,
            exit_code=0,
        )

    def _full(self):
        module = self._module()
        return module.GenerationCapability(
            office_available=True,
            pillow_available=True,
            office_runner=self._office_runner,
        )

    def test_legacy_best_effort_complete_rehydrates_its_own_output(self):
        self._configure_legacy_best_effort_complete_run()
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")
        self.assertEqual(first.delivery_status, "complete")
        self.assertEqual(first.delivery_policy, "best_effort")

        repeated = module.generate_editable(self.run, self._degraded())
        self.assertEqual(repeated.status, "GENERATED_UNVERIFIED")
        self.assertEqual(repeated.output_path, first.output_path)
        self.assertEqual(repeated.delivery_policy, "best_effort")

    def test_ai_state_partial_exports_promoted_subset_without_legacy_evidence(self):
        self._configure_ai_state_partial_run()
        module = self._module()
        contract = importlib.import_module("_ppt_editable.contract")
        with mock.patch.object(contract, "_load_shared_delivery_contract", side_effect=AssertionError):
            result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "GENERATED_UNVERIFIED")
        self.assertEqual(result.delivery_status, "partial")
        self.assertEqual(result.delivery_policy, "best_effort")
        self.assertEqual(result.target_slide_ids, ("S01", "S02"))
        self.assertEqual(result.delivered_slide_ids, ("S01",))
        self.assertEqual(result.missing_slides[0].evidence_type, "ai_state")
        output = self.run / "delivery" / "editable" / "fixture-deck-editable-partial-unverified.pptx"
        self.assertTrue(output.is_file())

        repeated = module.generate_editable(self.run, self._degraded())
        self.assertEqual(repeated.status, "GENERATED_UNVERIFIED")
        self.assertEqual(repeated.missing_slides[0].evidence_type, "ai_state")
        self.assertEqual(repeated.output_path, result.output_path)

    def test_ai_state_committed_manifest_cannot_change_current_partition(self):
        self._configure_ai_state_partial_run()
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")
        manifest_path = self.run / "delivery" / "editable" / "editable-result-partial.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["delivered_slide_ids"] = ["S02"]
        manifest["missing_slides"] = [{
            "slide_id": "S01",
            "reason": "failed",
            "evidence_type": "ai_state",
            "evidence": {
                "attempts": 1,
                "failure_code": "forged",
                "failure_message": "forged omission",
            },
        }]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        repeated = module.generate_editable(self.run, self._degraded())
        self.assertEqual(repeated.status, "BLOCKED")
        self.assertIn("promotion_conflict", {failure.code for failure in repeated.failures})

    def test_preflight_failure_blocks_before_candidate_write(self):
        module = self._module()
        source = self.run / "samples" / "S01.svg"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "<text ",
                '<text transform="translate(1 1)" ',
                1,
            ),
            encoding="utf-8",
        )
        with mock.patch.object(module, "_write_candidate_bytes") as writer:
            result = module.generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, "BLOCKED")
        writer.assert_not_called()
        self.assertFalse(any((self.run / "delivery" / "editable").glob("*.pptx")))

    def test_visible_internal_source_id_blocks_before_write_and_preserves_pass(self):
        module = self._module()
        invalid_run = self.root / "visible-src-run"
        shutil.copytree(FIXTURE_RUN, invalid_run)
        invalid_source = invalid_run / "samples" / "S01.svg"
        invalid_source.write_text(
            invalid_source.read_text(encoding="utf-8").replace(
                "封面",
                "来源：src-001",
            ),
            encoding="utf-8",
        )
        with mock.patch.object(module, "_write_candidate_bytes") as writer:
            blocked = module.generate_editable(invalid_run, self._degraded())
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertIn("svg_text_invalid", {failure.code for failure in blocked.failures})
        writer.assert_not_called()

        passed = module.generate_editable(self.run, self._full())
        verified = self.run / passed.output_path
        before = verified.read_bytes()
        source = self.run / "slides" / "S02.svg"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "第二页",
                "SrC-002",
            ),
            encoding="utf-8",
        )
        blocked = module.generate_editable(self.run, self._degraded())
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertIn("svg_text_invalid", {failure.code for failure in blocked.failures})
        self.assertEqual(verified.read_bytes(), before)
        manifest = json.loads(
            (self.run / "delivery" / "editable" / "editable-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "PASS")

    def test_missing_office_publishes_only_unverified_and_is_idempotent(self):
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")
        output = self.run / first.output_path
        self.assertTrue(output.is_file())
        self.assertTrue(output.name.endswith("-editable-unverified.pptx"))
        verified = output.with_name(output.name.replace("-editable-unverified", "-editable"))
        self.assertFalse(verified.exists())
        before = output.read_bytes()
        with mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("idempotent run rebuilt candidate"),
        ):
            second = module.generate_editable(self.run, self._degraded())
        self.assertEqual(second.status, "GENERATED_UNVERIFIED")
        self.assertEqual(output.read_bytes(), before)

    def test_same_pass_reuse_precedes_dependency_checks_and_cleans_stale_unverified(self):
        module = self._module()
        passed = module.generate_editable(self.run, self._full())
        self.assertEqual(passed.status, "PASS")
        stale = self.run / "delivery" / "editable" / "fixture-deck-editable-unverified.pptx"
        stale.write_bytes(b"stale")
        dependency_failure = module._failure(
            "core_dependency_missing",
            "dependency unavailable after committed PASS",
        )
        with mock.patch.object(
            module,
            "_core_dependency_failure",
            return_value=dependency_failure,
        ), mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("same PASS rebuilt"),
        ):
            reused = module.generate_editable(self.run, self._full())
        self.assertEqual(reused.status, "PASS")
        self.assertFalse(stale.exists())

    def test_candidate_write_failure_is_blocked_not_invalid_invocation(self):
        module = self._module()
        with mock.patch.object(
            module,
            "_write_candidate_bytes",
            side_effect=OSError("disk failed"),
        ):
            result = module.generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("candidate_write_failed", {failure.code for failure in result.failures})

    def test_generated_unverified_resumes_to_pass_with_office_capability(self):
        module = self._module()
        degraded = module.generate_editable(self.run, self._degraded())
        self.assertEqual(degraded.status, "GENERATED_UNVERIFIED")
        passed = module.generate_editable(self.run, self._full())
        self.assertEqual(passed.status, "PASS")
        self.assertTrue((self.run / passed.output_path).is_file())
        self.assertFalse(
            (self.run / "delivery" / "editable" / "fixture-deck-editable-unverified.pptx").exists()
        )
        manifest = json.loads(
            (self.run / "delivery" / "editable" / "editable-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "PASS")

    def test_office_protocol_failure_never_degrades_to_unverified(self):
        module = self._module()
        from _ppt_editable.office_protocol import OfficeResult

        protocol_failure = OfficeResult(
            capability=False,
            powerpoint_version=None,
            powerpoint_build=None,
            process_id=None,
            process_started_at=None,
            process_owned=False,
            stages=(),
            counts={},
            renders={key: () for key in module.RENDER_KEYS},
            normalized_path=None,
            error={
                "code": "powerpoint_timeout",
                "message": "adapter timed out",
                "stage": "capability",
            },
            exit_code=4,
        )
        result = module.generate_editable(
            self.run,
            module.GenerationCapability(True, True, lambda request: protocol_failure),
        )
        self.assertEqual(result.status, "FAILED_VERIFICATION")
        self.assertIn(
            "powerpoint_render_failed",
            {failure.code for failure in result.failures},
        )
        self.assertFalse(any((self.run / "delivery" / "editable").glob("*.pptx")))

    def test_office_failure_is_failed_verification_without_publication(self):
        module = self._module()
        from _ppt_editable.office_protocol import OfficeResult

        failure = OfficeResult(
            capability=True,
            powerpoint_version="16.0",
            powerpoint_build="test",
            process_id=123,
            process_started_at="2026-08-30T00:00:00+00:00",
            process_owned=True,
            stages=({"name": "render", "status": "failed"},),
            counts={},
            renders={key: () for key in module.RENDER_KEYS},
            normalized_path=None,
            error={"code": "render_failed", "message": "bad", "stage": "render"},
            exit_code=4,
        )
        capability = module.GenerationCapability(True, True, lambda request: failure)
        result = module.generate_editable(self.run, capability)
        self.assertEqual(result.status, "FAILED_VERIFICATION")
        self.assertFalse(any((self.run / "delivery" / "editable").glob("*.pptx")))

    def test_office_success_must_match_request_counts_renders_and_normalized_path(self):
        module = self._module()

        def mismatched_runner(request):
            result = self._office_runner(request)
            return result.__class__(
                capability=result.capability,
                powerpoint_version=result.powerpoint_version,
                powerpoint_build=result.powerpoint_build,
                process_id=result.process_id,
                process_started_at=result.process_started_at,
                process_owned=result.process_owned,
                stages=result.stages,
                counts=dict(result.counts, recursive_leaves=result.counts["recursive_leaves"] + 1),
                renders=result.renders,
                normalized_path=result.normalized_path,
                error=result.error,
                exit_code=result.exit_code,
            )

        result = module.generate_editable(
            self.run,
            module.GenerationCapability(True, True, mismatched_runner),
        )
        self.assertEqual(result.status, "FAILED_VERIFICATION")
        self.assertFalse(any((self.run / "delivery" / "editable").glob("*.pptx")))

        def duplicate_stage_runner(request):
            valid = self._office_runner(request)
            return valid.__class__(
                capability=valid.capability,
                powerpoint_version=valid.powerpoint_version,
                powerpoint_build=valid.powerpoint_build,
                process_id=valid.process_id,
                process_started_at=valid.process_started_at,
                process_owned=valid.process_owned,
                stages=valid.stages + ({"name": "normalize", "status": "passed"},),
                counts=valid.counts,
                renders=valid.renders,
                normalized_path=valid.normalized_path,
                error=valid.error,
                exit_code=valid.exit_code,
            )

        stage_failed = module.generate_editable(
            self.run,
            module.GenerationCapability(True, True, duplicate_stage_runner),
        )
        self.assertEqual(stage_failed.status, "FAILED_VERIFICATION")

    def test_geometry_verification_failure_and_runner_exception_retain_evidence(self):
        module = self._module()
        from _ppt_editable.model import Failure

        geometry_failure = Failure(
            code="structure_mismatch",
            slide_id=None,
            svg_tree_path=None,
            element_type=None,
            message="geometry deck invalid",
            remediation="rebuild",
        )
        with mock.patch.object(
            module,
            "_verify_geometry_candidate",
            return_value=(geometry_failure,),
        ):
            failed = module.generate_editable(self.run, self._full())
        self.assertEqual(failed.status, "FAILED_VERIFICATION")

        def exploding_runner(request):
            raise RuntimeError("office exploded")

        with self.assertRaisesRegex(RuntimeError, "office exploded"):
            module.generate_editable(
                self.run,
                module.GenerationCapability(True, True, exploding_runner),
            )
        quarantine = self.run / "delivery" / "editable" / "quarantine"
        self.assertTrue(any(path.name.startswith("failed-verification-") for path in quarantine.iterdir()))

    def test_missing_pillow_degrades_without_invoking_office(self):
        module = self._module()
        capability = module.GenerationCapability(
            office_available=True,
            pillow_available=False,
            office_runner=lambda request: self.fail("Office runner must not be called"),
        )
        result = module.generate_editable(self.run, capability)
        self.assertEqual(result.status, "GENERATED_UNVERIFIED")

    def test_later_blocked_build_preserves_previous_pass_authority(self):
        module = self._module()
        passed = module.generate_editable(self.run, self._full())
        verified = self.run / passed.output_path
        before = verified.read_bytes()
        source = self.run / "slides" / "S02.svg"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "<text ",
                '<text transform="translate(1 1)" ',
                1,
            ),
            encoding="utf-8",
        )
        blocked = module.generate_editable(self.run, self._degraded())
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertEqual(verified.read_bytes(), before)
        manifest = json.loads(
            (self.run / "delivery" / "editable" / "editable-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "PASS")

    def test_committed_transaction_cleanup_failure_does_not_block_same_pass(self):
        module = self._module()
        import _ppt_editable.atomic_io as atomic_io

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("post-commit crash")

        with self.assertRaisesRegex(RuntimeError, "post-commit crash"):
            module.generate_editable(self.run, self._full(), fault_injector=crash)
        manifest = json.loads(
            (self.run / "delivery" / "editable" / "editable-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "PASS")
        real_rmtree = atomic_io.shutil.rmtree

        def fail_transaction_cleanup(path, *args, **kwargs):
            if Path(path).name.startswith("txn-"):
                raise OSError("cleanup unavailable")
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            atomic_io.shutil,
            "rmtree",
            side_effect=fail_transaction_cleanup,
        ):
            reused = module.generate_editable(self.run, self._full())
        self.assertEqual(reused.status, "PASS")

    def test_lock_contention_and_crash_recovery_are_typed_and_repeatable(self):
        module = self._module()
        from _ppt_editable.atomic_io import OutputLock, build_output_paths

        paths = build_output_paths(self.run, "fixture-deck")
        with OutputLock(paths.lock_path):
            result = module.generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("promotion_conflict", {failure.code for failure in result.failures})

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaisesRegex(RuntimeError, "crash"):
            module.generate_editable(self.run, self._degraded(), fault_injector=crash)
        recovered = module.generate_editable(self.run, self._degraded())
        self.assertEqual(recovered.status, "GENERATED_UNVERIFIED")

    def test_public_cli_exports_authorized_partial_subset_without_office(self):
        missing = self._configure_partial_run()
        cli = importlib.import_module("svg_to_editable_pptx")
        report = self.root / "partial-cli-result.json"

        with mock.patch.object(
            cli,
            "powerpoint_available",
            side_effect=AssertionError("--skip-office must not probe or launch Office"),
        ) as office_probe:
            code = cli.main(
                [
                    "--run-dir",
                    str(self.run),
                    "--result-path",
                    str(report),
                    "--skip-office",
                    "--json",
                ]
            )

        self.assertEqual(code, 0)
        office_probe.assert_not_called()
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "GENERATED_UNVERIFIED")
        self.assertEqual(result["delivery_status"], "partial")
        self.assertEqual(result["delivery_policy"], "best_effort")
        self.assertEqual(result["target_slide_ids"], ["S01", "S02"])
        self.assertEqual(result["delivered_slide_ids"], ["S01"])
        self.assertEqual(result["missing_slides"], [missing])
        self.assertEqual(result["slide_count"], 1)
        self.assertEqual(
            Path(result["output_path"]).name,
            "fixture-deck-editable-partial-unverified.pptx",
        )

        output = self.run / result["output_path"]
        self.assertTrue(output.is_file())
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("ppt/slides/slide1.xml", names)
            self.assertNotIn("ppt/slides/slide2.xml", names)
            self.assertFalse(any(name.startswith("ppt/media/") for name in names))
            slide_xml = archive.read("ppt/slides/slide1.xml")
            self.assertNotIn(b"<p:pic", slide_xml)
            self.assertNotIn(b"<a:blip", slide_xml)

        partial_manifest = (
            self.run / "delivery" / "editable" / "editable-result-partial.json"
        )
        manifest = json.loads(partial_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "ppt_editable_result")
        for key in (
            "status",
            "delivery_status",
            "delivery_policy",
            "target_slide_ids",
            "delivered_slide_ids",
            "missing_slides",
            "slide_count",
            "output_path",
            "output_sha256",
        ):
            self.assertEqual(manifest[key], result[key])
        self.assertFalse(
            (self.run / "delivery" / "editable" / "editable-result.json").exists()
        )
        self.assertFalse(
            (
                self.run
                / "delivery"
                / "editable"
                / "fixture-deck-editable-unverified.pptx"
            ).exists()
        )

    def test_bound_complete_delivery_uses_full_namespace_and_inventory(self):
        self._configure_partial_run()
        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["stage"] = "complete"
        run["production_policy"] = "strict"
        run["dirty_slides"] = []
        run["delivery"]["status"] = "complete"
        run["delivery"]["policy"] = "strict"
        run["delivery"]["delivered_slide_ids"] = ["S01", "S02"]
        run["delivery"]["missing_slides"] = []
        run["delivery"]["slide_sha256"]["S02"] = self._sha256(
            (self.run / "slides" / "S02.svg").read_bytes()
        )
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        module = self._module()
        result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "GENERATED_UNVERIFIED")
        self.assertEqual(result.delivery_status, "complete")
        self.assertEqual(result.delivery_policy, "strict")
        self.assertEqual(result.target_slide_ids, ("S01", "S02"))
        self.assertEqual(result.delivered_slide_ids, ("S01", "S02"))
        self.assertEqual(result.missing_slides, ())
        self.assertEqual(result.slide_count, 2)
        editable = self.run / "delivery" / "editable"
        self.assertTrue((editable / "editable-result.json").is_file())
        self.assertTrue(
            (editable / "fixture-deck-editable-unverified.pptx").is_file()
        )
        self.assertFalse((editable / "editable-result-partial.json").exists())
        manifest = json.loads(
            (editable / "editable-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["delivery_status"], "complete")
        self.assertEqual(manifest["delivered_slide_ids"], ["S01", "S02"])

    def test_fake_office_verifies_only_delivered_partial_subset(self):
        self._configure_partial_run()
        module = self._module()
        captured = {}

        def runner(request):
            captured.update(request)
            return self._office_runner(request)

        result = module.generate_editable(
            self.run,
            module.GenerationCapability(
                office_available=True,
                pillow_available=True,
                office_runner=runner,
            ),
        )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.delivery_status, "partial")
        self.assertEqual(result.slide_count, 1)
        self.assertEqual(captured["ordered_slide_ids"], ["S01"])
        self.assertEqual(
            [item["slide_id"] for item in captured["selected_svgs"]],
            ["S01"],
        )
        self.assertEqual(
            [item["slide_id"] for item in captured["geometry_svgs"]],
            ["S01"],
        )
        self.assertEqual(captured["expected_counts"]["slides"], 1)

        editable = self.run / "delivery" / "editable"
        verified = editable / "fixture-deck-editable-partial.pptx"
        manifest_path = editable / "editable-result-partial.json"
        self.assertEqual(result.output_path, "delivery/editable/" + verified.name)
        self.assertTrue(verified.is_file())
        self.assertFalse(
            (editable / "fixture-deck-editable-partial-unverified.pptx").exists()
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(manifest["delivered_slide_ids"], ["S01"])
        self.assertFalse((editable / "editable-result.json").exists())
        self.assertFalse((editable / "fixture-deck-editable.pptx").exists())

        reused = module.generate_editable(
            self.run,
            module.GenerationCapability(
                office_available=True,
                pillow_available=True,
                office_runner=lambda request: self.fail(
                    "verified partial authority must be reused"
                ),
            ),
        )
        self.assertEqual(reused, result)
        self.assertEqual(
            module.generate_editable(self.run, self._degraded()),
            result,
        )
        self.assertFalse(
            (editable / "fixture-deck-editable-partial-unverified.pptx").exists()
        )

    def test_partial_unverified_refresh_preserves_prior_verified_authority(self):
        self._configure_partial_run()
        module = self._module()
        passed = module.generate_editable(self.run, self._full())
        self.assertEqual(passed.status, "PASS")

        editable = self.run / "delivery" / "editable"
        verified_path = editable / "fixture-deck-editable-partial.pptx"
        verified_before = verified_path.read_bytes()
        verified_sha256 = self._sha256(verified_before)

        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["delivery"]["missing_slides"][0]["reason"] = "user_skipped"
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        unverified = module.generate_editable(self.run, self._degraded())

        self.assertEqual(unverified.status, "GENERATED_UNVERIFIED")
        self.assertNotEqual(unverified.input_snapshot_id, passed.input_snapshot_id)
        self.assertEqual(verified_path.read_bytes(), verified_before)
        self.assertTrue(
            (editable / "fixture-deck-editable-partial-unverified.pptx").is_file()
        )
        manifest = json.loads(
            (editable / "editable-result-partial.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "GENERATED_UNVERIFIED")
        self.assertEqual(
            manifest["authoritative_verified"],
            {
                "status": "PASS",
                "input_snapshot_id": passed.input_snapshot_id,
                "output_path": "delivery/editable/fixture-deck-editable-partial.pptx",
                "output_sha256": verified_sha256,
            },
        )
        self.assertEqual(manifest["delivery_status"], "partial")

    def test_partial_export_is_idempotent_and_preserves_full_authority(self):
        self._configure_partial_run()
        editable = self.run / "delivery" / "editable"
        editable.mkdir(parents=True)
        full_output = editable / "fixture-deck-editable.pptx"
        full_output.write_bytes(b"existing-full-authority")
        full_manifest = {
            "schema_version": 1,
            "kind": "ppt_editable_result",
            "status": "PASS",
            "deck_id": "fixture-deck",
            "input_snapshot_id": "sha256:" + "b" * 64,
            "slide_count": 2,
            "output_path": "delivery/editable/fixture-deck-editable.pptx",
            "output_sha256": self._sha256(full_output.read_bytes()),
            "failures": [],
            "warnings": [],
        }
        full_manifest_path = editable / "editable-result.json"
        full_manifest_path.write_text(
            json.dumps(full_manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        full_output_before = full_output.read_bytes()
        full_manifest_before = full_manifest_path.read_bytes()

        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")
        partial_output = self.run / first.output_path
        partial_before = partial_output.read_bytes()
        with mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("idempotent partial run rebuilt candidate"),
        ):
            second = module.generate_editable(self.run, self._degraded())

        self.assertEqual(second.status, "GENERATED_UNVERIFIED")
        self.assertEqual(second.delivery_status, "partial")
        self.assertEqual(partial_output.read_bytes(), partial_before)
        self.assertEqual(full_output.read_bytes(), full_output_before)
        self.assertEqual(full_manifest_path.read_bytes(), full_manifest_before)

    def test_tampered_partial_manifest_partition_and_namespace_are_rejected(self):
        self._configure_partial_run()
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")

        editable = self.run / "delivery" / "editable"
        manifest_path = editable / "editable-result-partial.json"
        output_path = editable / "fixture-deck-editable-partial-unverified.pptx"
        original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output_before = output_path.read_bytes()

        def break_partition(value):
            value["delivered_slide_ids"] = []

        def break_namespace(value):
            value["delivery_status"] = "complete"

        for label, mutation in (
            ("partition", break_partition),
            ("namespace", break_namespace),
        ):
            with self.subTest(label=label):
                tampered = json.loads(json.dumps(original_manifest))
                mutation(tampered)
                manifest_path.write_text(
                    json.dumps(tampered, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                with mock.patch.object(
                    module,
                    "_build_presentation_bytes",
                    side_effect=AssertionError(
                        "tampered manifest reached candidate generation"
                    ),
                ):
                    result = module.generate_editable(self.run, self._degraded())
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(
                    [failure.code for failure in result.failures],
                    ["promotion_conflict"],
                )
                self.assertEqual(result.delivery_status, "partial")
                self.assertEqual(output_path.read_bytes(), output_before)

    def test_tampered_partial_omission_transaction_blocks_before_generation(self):
        missing = self._configure_partial_run()
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")

        editable = self.run / "delivery" / "editable"
        manifest_path = editable / "editable-result-partial.json"
        output_path = editable / "fixture-deck-editable-partial-unverified.pptx"
        manifest_before = manifest_path.read_bytes()
        output_before = output_path.read_bytes()

        transaction_path = self.run / Path(missing["transaction_ref"])
        transaction_path.write_bytes(transaction_path.read_bytes() + b"\n")
        with mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("tampered evidence reached candidate generation"),
        ):
            result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual([failure.code for failure in result.failures], ["source_unreadable"])
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(output_path.read_bytes(), output_before)

    def test_failing_delivered_svg_blocks_subset_without_dropping_inventory(self):
        missing = self._configure_partial_run()
        delivered_svg = self.run / "slides" / "S01.svg"
        delivered_svg.write_text("not an svg", encoding="utf-8")
        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["delivery"]["slide_sha256"]["S01"] = self._sha256(
            delivered_svg.read_bytes()
        )
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        module = self._module()
        result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.delivery_status, "partial")
        self.assertEqual(result.target_slide_ids, ("S01", "S02"))
        self.assertEqual(result.delivered_slide_ids, ("S01",))
        self.assertEqual(result.missing_slides[0].slide_id, missing["slide_id"])
        editable = self.run / "delivery" / "editable"
        self.assertFalse((editable / "editable-result-partial.json").exists())
        self.assertFalse(
            (editable / "fixture-deck-editable-partial-unverified.pptx").exists()
        )

    def test_partial_failed_verification_retains_selected_inventory(self):
        missing = self._configure_partial_run()
        module = self._module()
        failure = module._failure("structure_mismatch", "forced structural failure")
        report = mock.Mock(passed=False, failures=(failure,))

        with mock.patch.object(module, "_verify_candidate", return_value=report):
            result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "FAILED_VERIFICATION")
        self.assertEqual(result.delivery_status, "partial")
        self.assertEqual(result.target_slide_ids, ("S01", "S02"))
        self.assertEqual(result.delivered_slide_ids, ("S01",))
        self.assertEqual(result.missing_slides[0].slide_id, missing["slide_id"])
        self.assertEqual([item.code for item in result.failures], ["structure_mismatch"])
        editable = self.run / "delivery" / "editable"
        self.assertFalse((editable / "editable-result-partial.json").exists())
        self.assertTrue(any((editable / "quarantine" / "partial").iterdir()))

    def test_invalid_production_policy_blocks_legacy_complete_run(self):
        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["production_policy"] = "lenient"
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        module = self._module()
        with mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("invalid policy reached candidate generation"),
        ):
            result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual([failure.code for failure in result.failures], ["source_unreadable"])

    def test_final_partial_delivery_rejects_an_active_generation_batch(self):
        self._configure_partial_run()
        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["active_visual_generation_batch"] = {
            "schema_version": 2,
            "batch_id": "batch-partial-test",
            "manifest_path": (
                ".ppt-pilot/visual-generation-batches/batch-partial-test.json"
            ),
        }
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        module = self._module()
        with mock.patch.object(
            module,
            "_build_presentation_bytes",
            side_effect=AssertionError("active batch reached candidate generation"),
        ):
            result = module.generate_editable(self.run, self._degraded())

        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual([failure.code for failure in result.failures], ["run_not_complete"])

    def test_final_partial_delivery_rejects_legacy_active_control(self):
        self._configure_partial_run()
        run_path = self.run / '.ppt-pilot' / 'run.json'
        run = json.loads(run_path.read_text(encoding='utf-8'))
        run['visual_generation_transaction'] = {}
        run_path.write_text(json.dumps(run), encoding='utf-8')
        result = self._module().generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, 'BLOCKED')
        self.assertEqual([failure.code for failure in result.failures], ['run_not_complete'])
        self.assertFalse(list((self.run / 'delivery' / 'editable').glob('*.pptx')))

    def test_partial_delivery_cannot_bypass_manuscript_approval(self):
        self._configure_partial_run()
        run_path = self.run / '.ppt-pilot' / 'run.json'
        run = json.loads(run_path.read_text(encoding='utf-8'))
        run['manuscript_review'] = {'required': True, 'state': 'pending', 'status': 'PENDING',
                                    'open_blocking_findings': []}
        run_path.write_text(json.dumps(run), encoding='utf-8')
        result = self._module().generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, 'BLOCKED')
        self.assertFalse(list((self.run / 'delivery' / 'editable').glob('*.pptx')))

    def test_standalone_verifier_accepts_the_authorized_partial_subset(self):
        self._configure_partial_run()
        result = self._module().generate_editable(self.run, self._degraded())
        self.assertEqual(result.status, 'GENERATED_UNVERIFIED')
        verifier = importlib.import_module('verify_editable_pptx')
        report = self.root / 'partial-verification.json'
        code = verifier.main([
            '--candidate', str(self.run / result.output_path), '--run-dir', str(self.run),
            '--input-snapshot-id', result.input_snapshot_id,
            '--config', str(REPO_ROOT / 'skills/ppt-editable/assets/verification-config.json'),
            '--report', str(report),
        ])
        self.assertEqual(code, 0, report.read_text(encoding='utf-8'))
        self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['slide_count'], 1)

    def test_partial_contract_contradictions_block_before_generation(self):
        self._configure_partial_run()
        module = self._module()
        case_root = self.run.parent / "invalid-partial-cases"
        case_root.mkdir()

        def without_delivery(run, root):
            run.pop("delivery")

        def prepared(run, root):
            run["stage"] = "prepared"

        def failed(run, root):
            run["stage"] = "failed"

        def mismatched_stage(run, root):
            run["stage"] = "complete"

        def mismatched_policy(run, root):
            run["production_policy"] = "strict"

        def missing_theme(run, root):
            (root / ".ppt-pilot" / "theme.json").unlink()

        def reordered_targets(run, root):
            run["delivery"]["target_slide_ids"] = ["S02", "S01"]

        def dirty_delivered(run, root):
            run["dirty_slides"] = ["S01", "S02"]

        def missing_delivered_svg(run, root):
            (root / "slides" / "S01.svg").unlink()

        mutations = (
            ("missing-delivery", without_delivery),
            ("prepared", prepared),
            ("failed", failed),
            ("stage-status", mismatched_stage),
            ("policy", mismatched_policy),
            ("theme", missing_theme),
            ("target-order", reordered_targets),
            ("dirty-delivered", dirty_delivered),
            ("missing-delivered-svg", missing_delivered_svg),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                case = case_root / label
                shutil.copytree(self.run, case)
                run_path = case / ".ppt-pilot" / "run.json"
                run = json.loads(run_path.read_text(encoding="utf-8"))
                mutate(run, case)
                run_path.write_text(
                    json.dumps(run, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                with mock.patch.object(
                    module,
                    "_build_presentation_bytes",
                    side_effect=AssertionError(
                        "invalid partial contract reached candidate generation"
                    ),
                ):
                    result = module.generate_editable(case, self._degraded())
                self.assertEqual(result.status, "BLOCKED")
                editable = case / "delivery" / "editable"
                self.assertFalse((editable / "editable-result-partial.json").exists())
                self.assertFalse(
                    (editable / "fixture-deck-editable-partial-unverified.pptx").exists()
                )

    def test_partial_snapshot_identity_binds_complete_delivery_record(self):
        self._configure_partial_run()
        module = self._module()
        first = module.generate_editable(self.run, self._degraded())
        self.assertEqual(first.status, "GENERATED_UNVERIFIED")

        run_path = self.run / ".ppt-pilot" / "run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["delivery"]["missing_slides"][0]["reason"] = "user_skipped"
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        second = module.generate_editable(self.run, self._degraded())
        self.assertEqual(second.status, "GENERATED_UNVERIFIED")
        self.assertNotEqual(second.input_snapshot_id, first.input_snapshot_id)
        self.assertEqual(second.missing_slides[0].reason, "user_skipped")

    def test_public_cli_uses_fixed_exit_codes_and_result_report(self):
        cli = importlib.import_module("svg_to_editable_pptx")
        report = self.root / "cli-result.json"
        code = cli.main(
            [
                "--run-dir",
                str(self.run),
                "--result-path",
                str(report),
                "--skip-office",
                "--json",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(report.read_text(encoding="utf-8"))["status"],
            "GENERATED_UNVERIFIED",
        )
        self.assertEqual(cli.main([]), 3)
        self.assertEqual(cli.main(["--help"]), 0)
        with mock.patch.object(cli, "generate_editable", side_effect=RuntimeError("boom")):
            self.assertEqual(cli.main(["--run-dir", str(self.run)]), 4)
        with mock.patch.object(cli, "generate_editable", side_effect=OSError("disk")):
            self.assertEqual(cli.main(["--run-dir", str(self.run)]), 4)


if __name__ == "__main__":
    unittest.main()
