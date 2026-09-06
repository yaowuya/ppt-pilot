"""Loopback-only HTTP transport for the read-only dashboard projection."""
import hashlib
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .snapshot import build_snapshot, read_preview

ASSETS = Path(__file__).resolve().parents[2] / 'assets' / 'dashboard'
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def run_key(run_dir):
    return hashlib.sha256(os.path.normcase(str(Path(run_dir).resolve())).encode('utf-8')).hexdigest()


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_server(run_dir, port=0, token=None, instance_id=None):
    root = Path(run_dir).resolve()
    stop_token = token or secrets.token_urlsafe(32)
    identity = instance_id or secrets.token_hex(16)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'PPTPilotDashboard/1'

        def log_message(self, *args):
            # Polls must not fill the background process log with deck information.
            pass

        def send_bytes(self, status, content, content_type, policy=CSP):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', policy)
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            if self.command != 'HEAD':
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def send_json(self, status, data):
            self.send_bytes(status, json.dumps(data, ensure_ascii=False).encode('utf-8'),
                            'application/json; charset=utf-8')

        def local_request(self):
            host = self.headers.get('Host', '')
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            origin = self.headers.get('Origin')
            if host not in allowed or (origin is not None and origin != 'http://' + host):
                self.send_json(403, {'error': 'local_origin_required'})
                return False
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.send_json(403, {'error': 'cross_site_request_denied'})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            target = urlsplit(self.path)
            if target.scheme or target.netloc:
                self.send_json(400, {'error': 'invalid_request_target'})
                return
            if target.path == '/favicon.ico':
                self.send_bytes(204, b'', 'image/x-icon')
                return
            if target.path == '/api/health':
                self.send_json(200, {'service': 'ppt-pilot-dashboard', 'schema_version': 1,
                                     'instance_id': identity, 'run_key': run_key(root), 'pid': os.getpid()})
            elif target.path == '/api/state':
                try:
                    self.send_json(200, build_snapshot(root))
                except (OSError, ValueError, TypeError, KeyError):
                    self.send_json(503, {'error': 'snapshot_temporarily_unavailable'})
            elif target.path == '/api/preview':
                try:
                    params = parse_qs(target.query, max_num_fields=4)
                    paths = params.get('path', [])
                    if len(paths) != 1:
                        raise ValueError('one preview path required')
                    svg = read_preview(root, paths[0])
                except FileNotFoundError:
                    self.send_json(404, {'error': 'preview_unavailable'})
                except (ValueError, PermissionError):
                    self.send_json(403, {'error': 'preview_not_allowed'})
                except OSError:
                    self.send_json(503, {'error': 'preview_temporarily_unavailable'})
                else:
                    self.send_bytes(200, svg, 'image/svg+xml; charset=utf-8',
                                    "sandbox; default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            else:
                static = {'/': ('index.html', 'text/html'), '/index.html': ('index.html', 'text/html'),
                          '/app.js': ('app.js', 'application/javascript'), '/styles.css': ('styles.css', 'text/css')}
                asset = static.get(target.path)
                if asset is None:
                    self.send_json(404, {'error': 'not_found'})
                    return
                try:
                    data = (ASSETS / asset[0]).read_bytes()
                except OSError:
                    self.send_json(503, {'error': 'dashboard_assets_missing'})
                else:
                    self.send_bytes(200, data, asset[1] + '; charset=utf-8')

        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            if not self.local_request():
                return
            if self.path != '/api/stop':
                self.send_json(405, {'error': 'read_only_dashboard'})
                return
            supplied = self.headers.get('X-Dashboard-Token', '')
            if not secrets.compare_digest(supplied.encode('utf-8'), stop_token.encode('utf-8')):
                self.send_json(403, {'error': 'stop_token_required'})
                return
            self.send_json(200, {'status': 'stopping'})
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = DashboardHTTPServer(('127.0.0.1', port), Handler)
    server.stop_token = stop_token
    server.instance_id = identity
    server.run_dir = root
    return server
