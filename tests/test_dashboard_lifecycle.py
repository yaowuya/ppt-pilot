"""Exercise the shipped CLI against actual detached local server processes."""
import json
import os
import concurrent.futures
import socket
import subprocess
import sys
import threading
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts/ppt_dashboard.py'
sys.path.insert(0, str(SCRIPT.parent))


class DashboardLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / '演示 空目录'
        self.root.mkdir()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: self.cli('stop'))

    def cli(self, action, *args, environment=None):
        env = dict(os.environ)
        for name in ('DSH_SESSION_ID', 'DSH_SHELL'):
            env.pop(name, None)
        env.update(environment or {})
        return subprocess.run([sys.executable, str(SCRIPT), action, '--run-dir', str(self.root), *args],
                              capture_output=True, text=True, encoding='utf-8', timeout=20, env=env)

    def test_start_reuses_live_server_then_stops_and_restarts(self):
        first_result = self.cli('start')
        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        first = json.loads(first_result.stdout)
        self.assertEqual(first['status'], 'running')
        self.assertTrue(first['url'].startswith('http://127.0.0.1:'))
        second = json.loads(self.cli('start').stdout)
        self.assertEqual(first['instance_id'], second['instance_id'])
        self.assertTrue(second['reused'])
        status = json.loads(self.cli('status').stdout)
        self.assertEqual(status['instance_id'], first['instance_id'])
        self.assertEqual(self.cli('stop').returncode, 0)
        self.assertEqual(json.loads(self.cli('status').stdout)['status'], 'stopped')
        self.assertFalse((self.root / '.ppt-pilot/dashboard.json').exists())
        restarted = json.loads(self.cli('start').stdout)
        self.assertNotEqual(restarted['instance_id'], first['instance_id'])
        self.assertFalse((self.root / '.ppt-pilot/run.json').exists())

    def test_serve_collision_points_to_status_reuse_not_detached_start(self):
        launched = self.cli('start')
        self.assertEqual(launched.returncode, 0, launched.stderr)
        result = self.cli('serve')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('status', result.stderr)
        self.assertIn('复用', result.stderr)
        self.assertNotIn('使用 start', result.stderr)
        self.assertEqual(json.loads(self.cli('status').stdout)['status'], 'running')

    def test_dsh_start_rejects_turn_scoped_detach_before_writing_metadata(self):
        for marker in ('DSH_SESSION_ID', 'DSH_SHELL'):
            with self.subTest(marker=marker):
                result = self.cli('start', environment={marker: 'fixture'})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('DeepSeek Harness', result.stderr)
                self.assertIn('serve', result.stderr)
                self.assertIn('run_in_background', result.stderr)
                self.assertFalse((self.root / '.ppt-pilot').exists())

    def test_dsh_managed_serve_status_and_stop_remain_available(self):
        env = dict(os.environ)
        env['DSH_SESSION_ID'] = 'fixture-session'
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'serve', '--run-dir', str(self.root), '--port', '0'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=env)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                line = executor.submit(process.stdout.readline).result(timeout=10)
            launched = json.loads(line)
            status_result = self.cli('status', environment={'DSH_SESSION_ID': 'fixture-session'})
            self.assertEqual(status_result.returncode, 0, status_result.stderr)
            status = json.loads(status_result.stdout)
            self.assertEqual((status['status'], status['instance_id'], status['url']),
                             ('running', launched['instance_id'], launched['url']))
            stopped = self.cli('stop', environment={'DSH_SESSION_ID': 'fixture-session'})
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertEqual(process.wait(timeout=10), 0, process.stderr.read())
            self.assertEqual(json.loads(self.cli('status').stdout)['status'], 'stopped')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()

    def test_occupied_requested_port_fails_without_metadata_or_harming_owner(self):
        with socket.socket() as owner:
            owner.bind(('127.0.0.1', 0))
            owner.listen()
            result = self.cli('start', '--port', str(owner.getsockname()[1]))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('端口', result.stderr)
            self.assertFalse((self.root / '.ppt-pilot/dashboard.json').exists())
            self.assertGreater(owner.fileno(), -1)

    def test_metadata_cannot_redirect_health_to_external_host(self):
        internal = self.root / '.ppt-pilot'
        internal.mkdir()
        (internal / 'dashboard.json').write_text(json.dumps({
            'url': 'https://example.com/', 'pid': 1, 'instance_id': 'spoofed',
            'run_key': 'spoofed', 'token': 'spoofed',
        }))
        result = self.cli('stop')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('无效', result.stderr)

    def test_missing_directory_does_not_create_run_implicitly(self):
        self.root.rmdir()
        result = self.cli('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.root.exists())

    def test_concurrent_start_has_exactly_one_server_identity(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.cli('start'), range(2)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        payloads = [json.loads(result.stdout) for result in results]
        self.assertEqual(payloads[0]['instance_id'], payloads[1]['instance_id'])
        self.assertEqual(sorted(p['reused'] for p in payloads), [False, True])

    def test_mutated_identity_does_not_stop_service_at_same_port(self):
        launched = self.cli('start')
        self.assertEqual(launched.returncode, 0, launched.stderr)
        path = self.root / '.ppt-pilot/dashboard.json'
        original = path.read_bytes()
        payload = json.loads(original)
        payload['instance_id'] = 'incorrect-identity'
        path.write_text(json.dumps(payload))
        try:
            result = self.cli('stop')
            self.assertNotEqual(result.returncode, 0)
        finally:
            path.write_bytes(original)
        self.assertEqual(json.loads(self.cli('status').stdout)['status'], 'running')

    def test_old_cleanup_cannot_remove_replacement_instance_metadata(self):
        from _dashboard import lifecycle
        internal = self.root / '.ppt-pilot'
        old = {'url': 'http://127.0.0.1:8765/', 'instance_id': 'old',
               'run_key': lifecycle.run_key(self.root), 'token': 'secret', 'pid': 1}
        new = dict(old, instance_id='new')
        with lifecycle.launch_lock(internal):
            lifecycle.write_metadata(internal, old)
            cleanup = threading.Thread(target=lifecycle.remove_owned_metadata,
                                       args=(self.root, internal, 'old'))
            cleanup.start()
            lifecycle.write_metadata(internal, new)
        cleanup.join(timeout=3)
        self.assertFalse(cleanup.is_alive())
        self.assertEqual(lifecycle.read_metadata(self.root, internal)['instance_id'], 'new')
        # This test has no server. Remove only its own synthetic control file.
        (internal / 'dashboard.json').unlink()


if __name__ == '__main__':
    unittest.main()
