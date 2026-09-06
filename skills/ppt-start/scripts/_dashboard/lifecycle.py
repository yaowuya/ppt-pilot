"""Bounded lifecycle for a detached observer; never signal a PID from disk."""
import contextlib
import http.client
import json
import os
import secrets
import stat
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

from .server import make_server, run_key


def safe_location(run_dir):
    selected = Path(run_dir).absolute()
    # A junction or symlink must not redirect observer control writes.
    for part in (selected, *selected.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('运行目录不可经过符号链接或 reparse 点')
    if not selected.is_dir():
        raise ValueError('运行目录不存在或不是文件夹')
    internal = selected / '.ppt-pilot'
    if internal.exists() or internal.is_symlink():
        info = internal.lstat()
        if not stat.S_ISDIR(info.st_mode) or internal.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('内部状态目录无效')
    return selected.resolve(), internal


def check_control_file(path):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('服务控制文件无效')


@contextlib.contextmanager
def launch_lock(internal):
    internal.mkdir(exist_ok=True)
    path = internal / 'dashboard.lock'
    check_control_file(path)
    stream = path.open('a+b')
    if stream.tell() == 0:
        stream.write(b'0')
        stream.flush()
    deadline = time.monotonic() + 12
    while True:
        try:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.monotonic() >= deadline:
                stream.close()
                raise RuntimeError('另一个面板启动操作尚未完成，请稍后重试')
            time.sleep(0.1)
    try:
        yield
    finally:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def read_metadata(root, internal):
    path = internal / 'dashboard.json'
    check_control_file(path)
    if not path.exists():
        return None
    if path.stat().st_size > 8192:
        raise ValueError('服务控制文件无效：文件过大')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        url = urlsplit(data['url'])
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
                or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment
                or data.get('run_key') != run_key(root)
                or not isinstance(data.get('instance_id'), str) or not data['instance_id']
                or not isinstance(data.get('token'), str) or not data['token']):
            raise ValueError('invalid metadata')
    except (ValueError, KeyError, TypeError, UnicodeError) as error:
        raise ValueError('服务控制文件无效；请保留文件并核查，不会访问其中未知地址') from error
    return data


def request_local(data, path, method='GET'):
    port = urlsplit(data['url']).port
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
    try:
        headers = {'X-Dashboard-Token': data['token']} if method == 'POST' else {}
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        content = response.read(8193)
        if response.status != 200 or len(content) > 8192:
            raise ValueError('本地端口的服务响应不符合面板协议')
        return json.loads(content)
    finally:
        connection.close()


def is_live(data):
    if not data:
        return False
    try:
        health = request_local(data, '/api/health')
    except (OSError, http.client.HTTPException):
        return False
    if (not isinstance(health, dict) or health.get('service') != 'ppt-pilot-dashboard'
            or health.get('instance_id') != data['instance_id'] or health.get('run_key') != data['run_key']):
        raise ValueError('本地端口属于另一个服务实例，不会复用或停止它')
    return True


def public_status(data, reused=False):
    return {'status': 'running', 'url': data['url'], 'pid': data['pid'],
            'instance_id': data['instance_id'], 'reused': reused}


def write_metadata(internal, data):
    target = internal / 'dashboard.json'
    check_control_file(target)
    temporary = internal / ('dashboard-' + secrets.token_hex(8) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def remove_owned_metadata(root, internal, instance_id):
    with launch_lock(internal):
        current = read_metadata(root, internal)
        if current and current['instance_id'] == instance_id:
            (internal / 'dashboard.json').unlink()


def serve(run_dir, port=0, instance_id=None):
    root, internal = safe_location(run_dir)

    def prepare():
        current = read_metadata(root, internal)
        if is_live(current):
            raise ValueError('此运行已有面板，请使用 start 复用现有服务')
        try:
            server = make_server(root, port=port, instance_id=instance_id)
        except OSError as error:
            raise RuntimeError('面板端口不可用，请选择其他 --port 或省略以自动分配') from error
        data = {'schema_version': 1, 'instance_id': server.instance_id, 'run_key': run_key(root),
                'url': f'http://127.0.0.1:{server.server_port}/', 'pid': os.getpid(), 'token': server.stop_token}
        try:
            write_metadata(internal, data)
        except Exception:
            server.server_close()
            raise
        return server, data

    if instance_id:  # The start parent holds the launch lock until health succeeds.
        server, data = prepare()
    else:
        with launch_lock(internal):
            server, data = prepare()
    try:
        print(json.dumps(public_status(data)), flush=True)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            remove_owned_metadata(root, internal, data['instance_id'])
        except (OSError, ValueError):
            pass


def start(run_dir, port=0, open_browser=False):
    root, internal = safe_location(run_dir)
    with launch_lock(internal):
        current = read_metadata(root, internal)
        if is_live(current):
            result = public_status(current, reused=True)
        else:
            identity = secrets.token_hex(16)
            script = Path(__file__).resolve().parents[1] / 'ppt_dashboard.py'
            log_path = internal / 'dashboard.log'
            check_control_file(log_path)
            kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
            with log_path.open('wb') as log:
                child = subprocess.Popen([sys.executable, str(script), 'serve', '--run-dir', str(root),
                                          '--port', str(port), '--instance-id', identity],
                                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, **kwargs)
            deadline = time.monotonic() + 10
            try:
                while time.monotonic() < deadline:
                    if child.poll() is not None:
                        raise RuntimeError('面板启动失败（端口占用或目录不可写），详情见 .ppt-pilot/dashboard.log')
                    current = read_metadata(root, internal)
                    if current and current['instance_id'] == identity and is_live(current):
                        result = public_status(current)
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError('面板启动超时，详情见 .ppt-pilot/dashboard.log')
            except Exception:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
                raise
    if open_browser:
        try:
            opened = webbrowser.open(result['url'])
        except (OSError, webbrowser.Error):
            opened = False
        result['browser_opened'] = bool(opened)
        if not opened:
            result['warning'] = '浏览器未自动打开，请手动访问 url'
    return result


def status(run_dir):
    root, internal = safe_location(run_dir)
    current = read_metadata(root, internal)
    return public_status(current, reused=True) if is_live(current) else {'status': 'stopped'}


def stop(run_dir):
    root, internal = safe_location(run_dir)
    with launch_lock(internal):
        current = read_metadata(root, internal)
        if not is_live(current):
            return {'status': 'stopped'}
        request_local(current, '/api/stop', 'POST')
        # Keep start excluded until the old listening socket has closed.
        # The server closes its socket before taking this lock for cleanup.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not is_live(current):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('已请求停止，但尚未观察到服务退出，请用 status 核查')
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        remaining = read_metadata(root, internal)
        if not remaining or remaining['instance_id'] != current['instance_id']:
            return {'status': 'stopped'}
        time.sleep(0.1)
    raise RuntimeError('服务已关闭，但控制文件尚未清理，请用 status 核查')
