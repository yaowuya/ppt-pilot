"""Read-only regression coverage for the shared run artifact boundary."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'))
from _workflow_gate import audit_run, check_run, check_active_batch, snapshot_run
from test_source_workflow_gate import Fixture
from _artifact_firewall import audit_artifacts, CODE_SUFFIXES, FORBIDDEN_DIRECTORIES


class ArtifactRegressionTests(unittest.TestCase):
    def test_ordinary_and_source_entries_reject_code_without_writes(self):
        for source in (False, True):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if source:
                    Fixture(root)
                else:
                    (root / '.ppt-pilot').mkdir()
                    (root / '.ppt-pilot/run.json').write_text(json.dumps(
                        {'schema_version': 1, 'stage': 'brief'}))
                (root / 'helper.PS1.tmp').write_text('Write-Output 1')
                before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                for call in (audit_run, snapshot_run, check_active_batch,
                             lambda path: check_run(path, 'research')):
                    result = call(root)
                    self.assertEqual(result['status'], 'BLOCKED')
                    self.assertEqual(result['errors'][0]['code'], 'runtime_code_artifact')
                self.assertEqual(before, {p.relative_to(root): p.read_bytes()
                                         for p in root.rglob('*') if p.is_file()})

    def test_every_code_suffix_and_forbidden_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for suffix in CODE_SUFFIXES:
                path = root / ('helper.' + suffix.upper() + '.tmp')
                path.write_text('payload')
            for name in FORBIDDEN_DIRECTORIES:
                (root / name.upper()).mkdir()
            result = audit_artifacts(root)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['code'], 'runtime_code_artifact')
            self.assertEqual(len(result[0]['artifacts']), len(CODE_SUFFIXES) + len(FORBIDDEN_DIRECTORIES))
            self.assertEqual(result[0]['artifacts'], sorted(result[0]['artifacts']))

    def test_unknown_and_unowned_data_block(self):
        for name in ('helper', 'helper.zip', 'helper.ipynb', 'random.json', '.ppt-pilot/random.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text('#!/bin/sh')
                self.assertEqual(audit_artifacts(root)[0]['code'], 'unexpected_run_artifact')

    def test_canonical_legacy_temp_dashboard_and_bound_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = Fixture(root)
            for name in ('brief.md', 'theme.json', '.ppt-pilot/dashboard.json',
                         '.ppt-pilot/dashboard.lock', '.ppt-pilot/dashboard.log',
                         '.ppt-pilot/run.json.random.tmp', '.ppt-pilot/run.json.tmp',
                         '.ppt-pilot/.run.json.random.tmp',
                         '.ppt-pilot/runtime-inputs/response.txt',
                         '.ppt-pilot/generation-prompts/S01.md.abcd.tmp'):
                fixture.write(name, '{}')
            fixture.write('evidence/custom.png', 'evidence')
            fixture.evidence['qa']['slides'][0]['render']['path'] = 'evidence/custom.png'
            fixture.save()
            self.assertEqual(audit_artifacts(root, 'production', fixture.source), [])

    def test_source_exact_path_and_delivery_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source.pptx').write_bytes(b'source')
            self.assertEqual(audit_artifacts(root, source_path=root / 'source.pptx'), [])
            self.assertEqual(audit_artifacts(root, source_path=root / 'other.pptx')[0]['code'], 'precomplete_pptx')
            (root / 'source.pptx').unlink()
            delivery = root / 'delivery/editable'
            delivery.mkdir(parents=True)
            (delivery / 'deck.pptx').write_bytes(b'delivery')
            self.assertEqual(audit_artifacts(root, 'complete'), [])
            self.assertEqual(audit_artifacts(root)[0]['code'], 'precomplete_pptx')

    def test_all_stages_and_cli_actions(self):
        from _workflow_gate import WORKFLOW_STAGES
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = Fixture(root)
            fixture.write('.ppt-pilot/evil.py.tmp', 'payload')
            for stage in WORKFLOW_STAGES:
                fixture.run['stage'] = stage
                fixture.save()
                self.assertEqual(audit_run(root)['errors'][0]['reentry_stage'], stage)
            for action in (['--audit-run'], ['--snapshot'], ['--resume-active-batch'], ['--before', 'research']):
                proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] /
                    'skills/ppt-start/scripts/ppt_workflow_gate.py'), '--run-dir', str(root)] + action,
                    capture_output=True, text=True)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(json.loads(proc.stdout)['errors'][0]['code'], 'runtime_code_artifact')

    def test_editable_atomic_pptx_temps_keep_stage_and_path_restrictions(self):
        cases = (
            ('delivery/editable/.deck-editable.pptx.abc123.tmp', 'complete', None),
            ('delivery/editable/.deck-editable.pptx.abc123.tmp', 'qa', 'precomplete_pptx'),
            ('.deck-editable.pptx.abc123.tmp', 'complete', 'pptx_outside_delivery'),
            ('delivery/editable/helper.zip.abc123.tmp', 'complete', 'unexpected_run_artifact'),
            ('delivery/editable/helper.py.abc123.tmp', 'complete', 'runtime_code_artifact'),
        )
        for name, stage, expected in cases:
            with self.subTest(name=name, stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'atomic data')
                errors = audit_artifacts(root, stage)
                self.assertEqual(errors[0]['code'] if errors else None, expected)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source.pptx.abc123.tmp').write_bytes(b'not the bound source')
            self.assertEqual(audit_artifacts(root, source_path=root / 'source.pptx')[0]['code'],
                             'precomplete_pptx')

    def test_reparse_and_unreadable_entries_fail_closed(self):
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'brief.md'
            target.write_text('safe')
            original = Path.lstat
            def fake(path):
                if path == target:
                    return mock.Mock(st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                return original(path)
            with mock.patch.object(Path, 'lstat', fake):
                self.assertEqual(audit_artifacts(root)[0]['code'], 'unsafe_evidence_path')
            with mock.patch.object(Path, 'iterdir', side_effect=PermissionError):
                self.assertEqual(audit_artifacts(root)[0]['code'], 'unsafe_evidence_path')

    def test_editable_preflight_zero_delivery_writes_and_missing_dependency(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ppt-editable/scripts'))
        from _ppt_editable.contract import validate_completed_run
        from _ppt_editable.errors import EditableError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = Fixture(root)
            fixture.run['stage'] = 'complete'
            fixture.save()
            fixture.write('evil.py', 'payload')
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaises(EditableError) as caught:
                validate_completed_run(root)
            self.assertEqual(caught.exception.code, 'runtime_code_artifact')
            self.assertFalse((root / 'delivery').exists())
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            with mock.patch('importlib.util.spec_from_file_location', side_effect=ImportError):
                with self.assertRaises(EditableError) as caught:
                    validate_completed_run(root)
                self.assertEqual(caught.exception.code, 'artifact_firewall_unavailable')
