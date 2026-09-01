import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "ppt-editable"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))


REQUEST_FIELDS = {
    "schema_version",
    "request_id",
    "capability_only",
    "protocol_dir",
    "candidate_path",
    "normalized_path",
    "geometry_candidate_path",
    "source_full_deck_path",
    "source_geometry_deck_path",
    "selected_svgs",
    "geometry_svgs",
    "render_directories",
    "ordered_slide_ids",
    "expected_counts",
    "config",
}
RESULT_FIELDS = {
    "schema_version",
    "request_id",
    "capability",
    "powerpoint",
    "process",
    "stages",
    "counts",
    "renders",
    "normalized_path",
    "error",
    "exit_code",
}
RENDER_KEYS = {
    "source_full",
    "editable_full",
    "source_geometry",
    "editable_geometry",
}


class OfficeContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def _module(self):
        return importlib.import_module("_ppt_editable.office_protocol")

    def _request(self, *, capability_only=False):
        protocol_dir = self.root / "delivery" / "editable" / ".tmp" / "office"
        candidate = self.root / "candidate.pptx"
        geometry = self.root / "geometry.pptx"
        candidate.write_bytes(b"candidate")
        geometry.write_bytes(b"geometry")
        selected = []
        geometry_svgs = []
        for slide_id in ("S01", "S02"):
            full = self.root / (slide_id + ".svg")
            geom = self.root / (slide_id + "-geometry.svg")
            full.write_text("<svg/>", encoding="utf-8")
            geom.write_text("<svg/>", encoding="utf-8")
            selected.append({"slide_id": slide_id, "path": str(full)})
            geometry_svgs.append({"slide_id": slide_id, "path": str(geom)})
        return {
            "schema_version": 1,
            "request_id": "a" * 32,
            "capability_only": capability_only,
            "protocol_dir": str(protocol_dir),
            "candidate_path": str(candidate),
            "normalized_path": str(self.root / "normalized.pptx"),
            "geometry_candidate_path": str(geometry),
            "source_full_deck_path": str(self.root / "source-full.pptx"),
            "source_geometry_deck_path": str(self.root / "source-geometry.pptx"),
            "selected_svgs": selected,
            "geometry_svgs": geometry_svgs,
            "render_directories": {
                key: str(self.root / "renders" / key)
                for key in RENDER_KEYS
            },
            "ordered_slide_ids": ["S01", "S02"],
            "expected_counts": {
                "slides": 2,
                "top_level_shapes": 2,
                "recursive_leaves": 2,
                "recursive_groups": 0,
            },
            "config": {
                "render_width": 1280,
                "render_height": 720,
            },
        }

    def _success_result(self, request):
        return {
            "schema_version": 1,
            "request_id": request["request_id"],
            "capability": True,
            "powerpoint": {"version": "16.0", "build": "12345"},
            "process": {
                "pid": 123,
                "started_at": "2026-08-30T00:00:00.0000000+00:00",
                "owned": True,
            },
            "stages": [
                {"name": "normalize", "status": "passed"},
                {"name": "render", "status": "passed"},
            ],
            "counts": dict(request["expected_counts"]),
            "renders": {
                key: [
                    {
                        "slide_id": slide_id,
                        "path": str(
                            Path(request["render_directories"][key])
                            / (slide_id + ".png")
                        ),
                    }
                    for slide_id in request["ordered_slide_ids"]
                ]
                for key in RENDER_KEYS
            },
            "normalized_path": request["normalized_path"],
            "error": None,
            "exit_code": 0,
        }

    def test_protocol_field_sets_and_request_validation_are_exact(self):
        module = self._module()
        self.assertEqual(module.REQUEST_FIELDS, REQUEST_FIELDS)
        self.assertEqual(module.RESULT_FIELDS, RESULT_FIELDS)
        self.assertEqual(module.RENDER_KEYS, RENDER_KEYS)
        request = self._request()
        self.assertEqual(set(request), REQUEST_FIELDS)
        self.assertEqual(module.validate_office_request(request), request)
        with self.assertRaisesRegex(ValueError, "request fields"):
            module.validate_office_request(dict(request, surprise=True))
        malformed = dict(request)
        malformed["ordered_slide_ids"] = ["S02", "S01"]
        with self.assertRaisesRegex(ValueError, "ordered"):
            module.validate_office_request(malformed)
        noncanonical = dict(request)
        noncanonical["config"] = {"render_width": 640, "render_height": 360}
        with self.assertRaisesRegex(ValueError, "1280x720"):
            module.validate_office_request(noncanonical)

    def test_result_must_align_exactly_with_request_and_state(self):
        module = self._module()
        request = self._request()
        payload = self._success_result(request)
        try:
            result = module._validate_result_payload(payload, request)
        except ValueError as exc:
            self.fail(f"valid aligned result was rejected: {exc}")
        self.assertEqual(result.counts, request["expected_counts"])

        mutations = []
        wrong_counts = json.loads(json.dumps(payload))
        wrong_counts["counts"]["recursive_leaves"] += 1
        mutations.append(wrong_counts)
        missing_render = json.loads(json.dumps(payload))
        missing_render["renders"]["source_full"].pop()
        mutations.append(missing_render)
        wrong_render_order = json.loads(json.dumps(payload))
        wrong_render_order["renders"]["editable_full"].reverse()
        mutations.append(wrong_render_order)
        wrong_normalized = json.loads(json.dumps(payload))
        wrong_normalized["normalized_path"] = str(self.root / "other.pptx")
        mutations.append(wrong_normalized)
        wrong_version = json.loads(json.dumps(payload))
        wrong_version["powerpoint"]["version"] = 16
        mutations.append(wrong_version)
        impossible_owned = json.loads(json.dumps(payload))
        impossible_owned["process"] = {"pid": None, "started_at": None, "owned": True}
        mutations.append(impossible_owned)
        success_with_error = json.loads(json.dumps(payload))
        success_with_error["error"] = {
            "code": "unexpected",
            "message": "bad",
            "stage": "render",
        }
        mutations.append(success_with_error)
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                with self.assertRaises(ValueError):
                    module._validate_result_payload(mutated, request)

    def test_invoke_writes_request_invokes_adapter_and_parses_exact_result(self):
        module = self._module()
        request = self._request()
        script = self.root / "adapter.ps1"
        script.write_text("# adapter", encoding="utf-8")
        observed = {}

        def fake_run(command, **kwargs):
            observed["command"] = command
            observed["kwargs"] = kwargs
            request_path = Path(command[command.index("-RequestPath") + 1])
            result_path = Path(command[command.index("-ResultPath") + 1])
            observed["request"] = json.loads(request_path.read_text(encoding="utf-8"))
            result_path.write_text(
                json.dumps(self._success_result(request)),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "powerpoint_process_snapshot",
            return_value=(),
        ), mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            result = module.invoke_office_verification(request, script, 30)

        self.assertEqual(observed["request"], request)
        self.assertEqual(observed["kwargs"]["timeout"], 30)
        self.assertFalse(observed["kwargs"]["shell"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.capability)
        self.assertTrue(result.process_owned)
        self.assertEqual(set(result.renders), RENDER_KEYS)

    def test_timeout_and_missing_powershell_return_structured_unavailable_result(self):
        module = self._module()
        request = self._request()
        script = self.root / "adapter.ps1"
        script.write_text("# adapter", encoding="utf-8")
        with mock.patch.object(module, "_powershell_executable", return_value=None):
            result = module.invoke_office_verification(request, script, 1)
        self.assertFalse(result.capability)
        self.assertEqual(result.error["code"], "powerpoint_unavailable")

        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "powerpoint_process_snapshot",
            return_value=(),
        ), mock.patch.object(
            module.subprocess,
            "run",
            side_effect=module.subprocess.TimeoutExpired("powershell", 1),
        ):
            result = module.invoke_office_verification(request, script, 1)
        self.assertFalse(result.capability)
        self.assertEqual(result.exit_code, 4)
        self.assertEqual(result.error["code"], "powerpoint_timeout")

    def test_stale_result_and_launch_failure_cannot_be_reported_as_success(self):
        module = self._module()
        request = self._request()
        script = self.root / "adapter.ps1"
        script.write_text("# adapter", encoding="utf-8")
        protocol_dir = Path(request["protocol_dir"])
        protocol_dir.mkdir(parents=True)
        stale = protocol_dir / (request["request_id"] + "-result.json")
        stale.write_text(json.dumps(self._success_result(request)), encoding="utf-8")

        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "powerpoint_process_snapshot",
            return_value=(),
        ), mock.patch.object(
            module.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ):
            result = module.invoke_office_verification(request, script, 30)
        self.assertFalse(result.capability)
        self.assertEqual(result.error["code"], "powerpoint_protocol_failed")

        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "powerpoint_process_snapshot",
            return_value=(),
        ), mock.patch.object(
            module.subprocess,
            "run",
            side_effect=OSError("launch failed"),
        ):
            try:
                result = module.invoke_office_verification(request, script, 30)
            except OSError as exc:
                self.fail(f"launch failure leaked raw OSError: {exc}")
        self.assertFalse(result.capability)
        self.assertEqual(result.error["code"], "powerpoint_launch_failed")

    def test_capability_rejects_non_microsoft_powerpoint_com_server(self):
        module = self._module()
        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "_powerpoint_local_server",
            return_value=r"D:\ProgramFiles\WPS Office\office6\wpp.exe /Automation",
        ):
            self.assertFalse(module.powerpoint_available())
        with mock.patch.object(
            module,
            "_powershell_executable",
            return_value="powershell.exe",
        ), mock.patch.object(
            module,
            "_powerpoint_local_server",
            return_value=r'"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE" /Automation',
        ):
            self.assertTrue(module.powerpoint_available())

    def test_side_by_side_registry_selects_microsoft_powershell_view(self):
        module = self._module()
        microsoft = r'"C:\Program Files\Microsoft Office\Root\Office16\POWERPNT.EXE" /AUTOMATION'
        wps = r"D:\ProgramFiles\WPS Office\office6\wpp.exe /Automation"

        def local_server(view=None):
            return {64: wps, 32: microsoft, None: microsoft}[view]

        with mock.patch.object(module.os, "name", "nt"), mock.patch.object(
            module,
            "_powershell_candidates_by_view",
            return_value=((64, "powershell-64.exe"), (32, "powershell-32.exe")),
            create=True,
        ), mock.patch.object(
            module,
            "_powerpoint_local_server",
            side_effect=local_server,
        ):
            self.assertEqual(module._powershell_executable(), "powershell-32.exe")
            self.assertTrue(module.powerpoint_available())

    def test_timeout_cleanup_uses_only_exact_adapter_ownership_claim(self):
        module = self._module()
        claim = self.root / "owner.json"
        claim.write_text(
            json.dumps({"pid": 101, "started_at": "start-a", "owned": False}),
            encoding="utf-8",
        )
        with mock.patch.object(module, "_terminate_powerpoint_identity") as terminate:
            module._cleanup_claimed_powerpoint_process(claim)
        terminate.assert_not_called()

        claim.write_text(
            json.dumps({"pid": 202, "started_at": "start-b", "owned": True}),
            encoding="utf-8",
        )
        with mock.patch.object(module, "_terminate_powerpoint_identity") as terminate:
            module._cleanup_claimed_powerpoint_process(claim)
        terminate.assert_called_once_with(202, "start-b")
        self.assertNotIn(
            "_cleanup_new_powerpoint_processes",
            Path(module.__file__).read_text(encoding="utf-8"),
        )

    def test_powershell_adapter_static_ownership_and_render_contract(self):
        script = SCRIPTS_ROOT / "normalize_and_export.ps1"
        self.assertTrue(script.is_file())
        source = script.read_text(encoding="utf-8")
        required = (
            "GetWindowThreadProcessId",
            "Get-OoxmlRecursiveShapeCounts",
            "$presentations.Open",
            "-1, 0, 0",
            "SaveAs",
            ", 24)",
            ".Export(",
            "1280, 720",
            "source_full",
            "editable_full",
            "source_geometry",
            "editable_geometry",
            "FinalReleaseComObject",
            "finally",
            "StartTime",
            "owned",
            "$firstHwnd",
            "$secondHwnd",
            "$confirmedPidValue -ne $pidValue",
            "$confirmedStartedAt -ne $startedAt",
            "$process.ProcessName -ne 'POWERPNT'",
            "$process.ProcessName -eq 'POWERPNT'",
            "$activeStage",
            "Add-Stage $result $stageName 'failed'",
            "powerpoint_normalize_failed",
            "powerpoint_reopen_failed",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertGreaterEqual(source.count("GetWindowThreadProcessId"), 3)
        ownership_claim = source.index("$ownedProcess = $confirmedProcess")
        for prior_check in (
            "$process.ProcessName -ne 'POWERPNT'",
            "$confirmedPidValue -ne $pidValue",
            "$confirmedStartedAt -ne $startedAt",
        ):
            self.assertLess(source.index(prior_check), ownership_claim)
        self.assertRegex(
            source,
            r"(?s)if\s*\(\$null\s+-ne\s+\$activeStage\).*?Add-Stage\s+\$result\s+\$stageName\s+'failed'.*?Set-ResultError\s+\$result\s+\$errorCode",
        )
        lowered = source.lower()
        self.assertNotIn("taskkill", lowered)
        self.assertNotIn("stop-process", lowered)
        self.assertNotIn("get-process powerpoint |", lowered)
        self.assertRegex(source, r"(?s)if\s*\(\$ownedProcess\).*?\.Quit\(\)")
        self.assertRegex(source, r"(?s)finally\s*\{.*?Release-ComObject")

    @unittest.skipUnless(
        os.name == "nt"
        and importlib.util.find_spec("_ppt_editable.office_protocol") is not None
        and importlib.import_module("_ppt_editable.office_protocol").powerpoint_available(),
        "PowerPoint COM capability unavailable",
    )
    def test_com_smoke_preserves_preexisting_powerpoint_processes(self):
        module = self._module()
        before = module.powerpoint_process_snapshot(strict=True)
        request = self._request(capability_only=True)
        result = module.invoke_office_verification(
            request,
            SCRIPTS_ROOT / "normalize_and_export.ps1",
            60,
        )
        after = module.powerpoint_process_snapshot(strict=True)
        self.assertTrue(result.capability)
        for identity in before:
            self.assertIn(identity, after)


if __name__ == "__main__":
    unittest.main()
