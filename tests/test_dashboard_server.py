"""Real HTTP tests: an observer must never become an arbitrary file server."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))

from _dashboard.server import make_server


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / '.ppt-pilot').mkdir()
        (self.root / '.ppt-pilot/run.json').write_text(json.dumps({
            'deck_id': 'http-demo', 'stage': 'production', 'dirty_slides': [],
        }), encoding='utf-8')
        (self.root / 'slides').mkdir()
        (self.root / 'slides/S01.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><text>First</text></svg>', encoding='utf-8')
        self.server = make_server(self.root, port=0, token='test-token', instance_id='test-instance')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path, method='GET', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_state_and_preview_change_without_restarting_service(self):
        status, headers, body = self.request('/api/state')
        self.assertEqual(status, 200)
        first = json.loads(body)
        self.assertEqual(first['deck_id'], 'http-demo')
        (self.root / 'slides/S01.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg">Second</svg>')
        second = json.loads(self.request('/api/state')[2])
        self.assertNotEqual(first['revision'], second['revision'])
        code, headers, svg = self.request('/api/preview?path=slides%2FS01.svg')
        self.assertEqual(code, 200)
        self.assertIn(b'Second', svg)
        self.assertIn('sandbox', headers['Content-Security-Policy'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_static_dashboard_is_served_with_restrictive_policy(self):
        code, headers, body = self.request('/')
        self.assertEqual(code, 200)
        self.assertIn(b'<!', body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        for path in ('/app.js', '/styles.css'):
            self.assertEqual(self.request(path)[0], 200)

    def test_private_files_and_traversal_never_served(self):
        for path in ('/.ppt-pilot/run.json', '/api/preview?path=.ppt-pilot%2Frun.json',
                     '/api/preview?path=..%2Fsecret.svg', '/api/preview?path=C%3A%5Csecret.svg',
                     '/%2e%2e/README.md'):
            with self.subTest(path=path):
                self.assertIn(self.request(path)[0], (400, 403, 404))

    def test_foreign_host_and_origin_rejected(self):
        self.assertEqual(self.request('/api/state', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/state', headers={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/state', headers={'Origin': 'null'})[0], 403)

    def test_health_has_identity_but_no_stop_token_or_absolute_path(self):
        code, _, body = self.request('/api/health')
        self.assertEqual(code, 200)
        health = json.loads(body)
        self.assertEqual(health['instance_id'], 'test-instance')
        self.assertEqual(health['service'], 'ppt-pilot-dashboard')
        self.assertNotIn('test-token', body.decode())
        self.assertNotIn(str(self.root), body.decode())

    def test_stop_requires_secret_and_rejects_all_other_mutations(self):
        self.assertEqual(self.request('/api/stop', 'POST')[0], 403)
        self.assertEqual(self.request('/api/state', 'POST')[0], 405)
        self.assertEqual(self.request('/api/stop', 'POST', {'X-Dashboard-Token': 'wrong'})[0], 403)
        self.assertEqual(self.request('/api/stop', 'POST', {'X-Dashboard-Token': 'test-token'})[0], 200)
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
