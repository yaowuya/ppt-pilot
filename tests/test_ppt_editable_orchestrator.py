import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

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
