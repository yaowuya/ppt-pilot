"""Installed CLI diagnostics: no run, no host configuration, no fabricated observation."""
import copy
import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / 'skills/ppt-start'


class HostDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'skills/ppt-start'
        shutil.copytree(SOURCE, self.skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.cap = self.root / 'capability.json'
        registry = json.loads((self.skill / 'assets/host-adapters.json').read_text(encoding='utf-8'))
        self.adapter = next(a for a in registry['adapters'] if a['host'] == 'deepseek-harness')
        self.receipt = dict(self.adapter, schema_version=1, kind='host_capability', observation={
            'native_fresh_isolation': True, 'remote_fresh_isolation': False,
            'concurrent_tasks': True, 'durable_lookup': False, 'worker_capacity': None,
            'prompt_by_value': True, 'fresh_history': True, 'filesystem_none': False,
            'data_tools_none': False, 'attribution': True, 'nested_cli_required': False,
            'credential_probe_required': False, 'current_context_only': False}, evidence={
            'tool_name': 'subagent', 'instruction_sha256': self.adapter['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'tool_policy': 'inherited-not-isolated',
            'ambient_context': ['deployment_system_prompt', 'agent_preset', 'workspace_instructions'],
            'result_type': 'text', 'attribution_type': 'subagent_id',
            'session_id': 'fixture-not-live-host-attestation'})

    def inspect(self, receipt=None, host='deepseek-harness', capability_path=None):
        if receipt is not None:
            self.cap.write_text(json.dumps(receipt), encoding='utf-8')
            capability_path = self.cap
        args = [] if capability_path is None else ['--capability', str(capability_path)]
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, '-B', str(self.skill / 'scripts/ppt_runtime.py'),
            'inspect-host', '--host', host, *args], cwd=self.root,
            capture_output=True, text=True, encoding='utf-8')
        self.assertIn(result.returncode, (0, 2), result.stderr)
        self.assertTrue(result.stdout.startswith('{'), 'Expected diagnostic JSON, got: ' + result.stderr)
        body = json.loads(result.stdout)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'Read-only diagnostics modified files')
        self.assertEqual(body['writes'], [])
        return result, body

    def test_inspect_without_run_reports_installation_not_live_capability(self):
        result, body = self.inspect()
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['skill_root'], str(self.skill))
        self.assertEqual(body['result']['registry_path'], str(self.skill / 'assets/host-adapters.json'))
        self.assertEqual(body['result']['adapter'], self.adapter)
        self.assertFalse(body['result']['receipt_checked'])
        self.assertFalse(body['result']['live_host_verified'])
        self.assertNotIn('selected_width', body['result'])
        self.assertNotIn('capability', body['result'])

    def test_stale_receipt_reports_identity_mismatch_instead_of_missing_dsh(self):
        receipt = dict(self.receipt, adapter_id='unregistered', adapter_version='none', adapter_digest='none')
        result, body = self.inspect(receipt)
        self.assertEqual(result.returncode, 2)
        error = body['errors'][0]
        self.assertEqual(error['code'], 'generator_unavailable')
        self.assertEqual(error['details']['reason'], 'adapter_identity_mismatch')
        self.assertEqual(error['details']['field'], 'adapter_id')
        self.assertEqual(error['details']['expected'], 'native-subagent')
        self.assertEqual(error['details']['skill_root'], str(self.skill))
        self.assertNotIn('canonical owner conflict', error['next_action'])

    def test_native_receipt_checks_declared_capacity_without_attesting_host(self):
        result, body = self.inspect(self.receipt)
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue(body['result']['receipt_checked'])
        self.assertFalse(body['result']['live_host_verified'])
        self.assertEqual(body['result']['selected_width'], 1)

    def test_observation_and_evidence_errors_identify_field_without_echoing_values(self):
        for section, key, value, reason in (
            ('observation', 'filesystem_none', True, 'observation_mismatch'),
            ('observation', 'fresh_history', False, 'observation_mismatch'),
            ('observation', 'worker_capacity', -1, 'invalid_observation'),
            ('evidence', 'tool_name', 'SECRET_VALUE_DO_NOT_ECHO', 'evidence_mismatch'),
            ('evidence', 'session_id', '', 'invalid_evidence'),
        ):
            with self.subTest(section=section, key=key):
                receipt = copy.deepcopy(self.receipt)
                receipt[section][key] = value
                result, body = self.inspect(receipt)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(body['errors'][0]['details']['reason'], reason)
                self.assertEqual(body['errors'][0]['details']['field'], section + '.' + key)
                self.assertNotIn('SECRET_VALUE_DO_NOT_ECHO', json.dumps(body))

    def test_inspection_checks_bundled_instruction_even_without_receipt(self):
        (self.skill / 'references/deepseek-harness.md').write_text('tampered', encoding='utf-8')
        result, body = self.inspect()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['details']['reason'], 'instruction_digest_mismatch')
        self.assertEqual(body['errors'][0]['details']['field'], 'adapter_digest')

    def test_malformed_or_missing_receipt_fails_without_writes(self):
        for raw in (b'{"host":"deepseek-harness","host":"claude-code"}', b'not JSON', b'\xff'):
            with self.subTest(raw=raw):
                self.cap.write_bytes(raw)
                result, body = self.inspect(capability_path=self.cap)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(body['errors'][0]['details']['reason'], 'capability_unreadable')
        self.cap.unlink()
        result, body = self.inspect(capability_path=self.cap)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['details']['reason'], 'capability_unreadable')

    def test_selected_host_must_match_receipt(self):
        result, body = self.inspect(dict(self.receipt, host='claude-code'))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['details']['field'], 'host')
        self.assertEqual(body['errors'][0]['details']['expected'], 'deepseek-harness')

    def test_nonregular_receipt_is_rejected_without_opening_it(self):
        with mock.patch.object(sys, 'path', [str(SOURCE / 'scripts'), *sys.path]):
            import _host_adapter_runtime as host_runtime
        self.cap.write_text(json.dumps(self.receipt), encoding='utf-8')
        original_lstat = Path.lstat
        original_open = os.open
        opened = []

        def fifo_info(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            return os.stat_result((stat.S_IFIFO, *info[1:]), {'st_file_attributes': 0}) if path == self.cap else info

        def track_open(path, *args, **kwargs):
            if Path(path) == self.cap:
                opened.append(path)
            return original_open(path, *args, **kwargs)

        # A real local fixture reports FIFO mode; no actual pipe or blocking I/O.
        with mock.patch.object(Path, 'lstat', fifo_info), mock.patch.object(os, 'open', track_open):
            with self.assertRaises(ValueError) as caught:
                host_runtime.inspect_host('deepseek-harness', str(self.cap))
        self.assertEqual(caught.exception.details['reason'], 'capability_unreadable')
        self.assertEqual(opened, [])

    def test_remote_and_device_receipts_are_rejected_before_filesystem_access(self):
        with mock.patch.object(sys, 'path', [str(SOURCE / 'scripts'), *sys.path]):
            import _host_adapter_runtime as host_runtime
        original_lstat = Path.lstat
        for value in (r'\\review-invalid-host\share\capability.json',
                      '//review-invalid-host/share/capability.json',
                      r'\\?\C:\capability.json', r'\\.\pipe\capability.json',
                      r'\??\C:\capability.json', 'C:/capability.json:stream', 'NUL'):
            with self.subTest(value=value):
                attempted = []

                def local_only(path, *args, **kwargs):
                    root = host_runtime.ROOT
                    if path != root and root not in path.parents and path not in root.parents:
                        attempted.append(str(path))
                        raise OSError('Test blocked external path access')
                    return original_lstat(path, *args, **kwargs)

                # Intercept the real old bug before it can initiate network/device I/O.
                with mock.patch.object(Path, 'lstat', local_only):
                    with self.assertRaises(ValueError) as caught:
                        host_runtime.inspect_host('deepseek-harness', value)
                self.assertEqual(attempted, [], 'Unsafe input reached filesystem I/O')
                self.assertEqual(caught.exception.details['reason'], 'unsafe_capability_path')

    def test_missing_registered_host_is_distinguished_from_stale_receipt(self):
        path = self.skill / 'assets/host-adapters.json'
        registry = json.loads(path.read_text(encoding='utf-8'))
        registry['adapters'] = [a for a in registry['adapters'] if a['host'] == 'claude-code']
        path.write_text(json.dumps(registry), encoding='utf-8')
        result, body = self.inspect()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['details']['reason'], 'adapter_not_registered')


if __name__ == '__main__':
    unittest.main()
