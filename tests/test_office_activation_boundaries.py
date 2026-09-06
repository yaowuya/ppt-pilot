"""Exercise Office activation boundaries without launching Office or COM."""
import importlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/ppt-editable/scripts'))


class LiveOfficeOptInTests(unittest.TestCase):
    def _run_smoke_safely(self, setting):
        module = importlib.import_module('_ppt_editable.office_protocol')
        environment = dict(os.environ)
        environment.pop('PPT_EDITABLE_LIVE_OFFICE_TESTS', None)
        if setting is not None:
            environment['PPT_EDITABLE_LIVE_OFFICE_TESTS'] = setting
        # Real discovery/decorator and smoke body; only external capability,
        # process inventory and Office invocation are replaced.
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(module, 'powerpoint_available', return_value=True), \
                mock.patch.object(module, 'powerpoint_process_snapshot', return_value=()), \
                mock.patch.object(module, 'invoke_office_verification',
                                  return_value=type('Result', (), {'capability': True})()):
            namespace = runpy.run_path(str(ROOT / 'tests/test_ppt_editable_office_contract.py'))
            case = namespace['OfficeContractTests'](
                'test_com_smoke_preserves_preexisting_powerpoint_processes')
            return unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([case]))

    def test_live_smoke_is_skipped_without_exact_opt_in(self):
        for setting in (None, '', '0', 'true', 'yes'):
            with self.subTest(setting=setting):
                result = self._run_smoke_safely(setting)
                self.assertTrue(result.wasSuccessful())
                self.assertEqual(len(result.skipped), 1)

    @unittest.skipUnless(os.name == 'nt', 'Live Office adapter is Windows-only')
    def test_exact_opt_in_keeps_live_smoke_available(self):
        result = self._run_smoke_safely('1')
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.skipped, [])


@unittest.skipUnless(shutil.which('powershell'), 'Windows PowerShell unavailable')
class PreviewBoundaryTests(unittest.TestCase):
    def _invoke(self, run, *flags):
        # Keep the real tool's stage routing and preview output. Replace only
        # executable discovery with a tripwire BEFORE any COM acquisition.
        wrapper = r'''
$tool = $env:PPT_TEST_DELIVERY_TOOL
$source = [System.IO.File]::ReadAllText($tool)
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Tool parse failed' }
$probe = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-PowerPointExe' }, $true)
if (-not $probe) { throw 'Office tripwire boundary missing' }
$body = $probe.Body.Extent
$source = $source.Substring(0, $body.StartOffset) + "{ throw 'OFFICE_PROBE_REACHED' }" + $source.Substring($body.EndOffset)
$invokeArgs = @{ RunDir = $env:PPT_TEST_RUN; WorkspaceRoot = $env:PPT_TEST_RUN }
if ($env:PPT_TEST_PREVIEW -eq '1') { $invokeArgs.SkipPptx = $true }
try { & ([scriptblock]::Create($source)) @invokeArgs } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
'''
        environment = dict(os.environ, PPT_TEST_DELIVERY_TOOL=str(ROOT / 'tools/deck-deliver.ps1'),
                           PPT_TEST_RUN=str(run), PPT_TEST_PREVIEW='1' if '-SkipPptx' in flags else '0')
        return subprocess.run([shutil.which('powershell'), '-NoProfile', '-NonInteractive',
                               '-ExecutionPolicy', 'Bypass', '-Command', wrapper],
                              env=environment, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=30)

    def _fixture(self, root, stage):
        (root / '.ppt-pilot').mkdir()
        (root / 'slides').mkdir()
        (root / '.ppt-pilot/run.json').write_text(
            json.dumps({'deck_id': 'preview-only', 'stage': stage}), encoding='utf-8')
        (root / 'slides/S01.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><title>Preview</title></svg>',
            encoding='utf-8')

    def test_incomplete_run_blocks_office_before_probe_or_delivery_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root, 'production')
            result = self._invoke(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('OFFICE_PROBE_REACHED', result.stdout + result.stderr)
            self.assertFalse((root / 'preview.html').exists())
            self.assertFalse((root / 'delivery').exists())

    def test_explicit_preview_works_during_production_without_office(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root, 'production')
            original = (root / '.ppt-pilot/run.json').read_bytes()
            result = self._invoke(root, '-SkipPptx')
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertNotIn('OFFICE_PROBE_REACHED', result.stdout + result.stderr)
            self.assertTrue((root / 'preview.html').is_file())
            manifest = json.loads((root / 'delivery/delivery-result.json').read_text('utf-8'))
            self.assertEqual(manifest['result'], 'PASS_WITHOUT_PPTX')
            self.assertIsNone(manifest['powerPoint'])
            self.assertIsNone(manifest['pptxPath'])
            self.assertEqual((root / '.ppt-pilot/run.json').read_bytes(), original)

    def test_completed_pptx_delivery_keeps_office_path_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root, 'complete')
            result = self._invoke(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('OFFICE_PROBE_REACHED', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
