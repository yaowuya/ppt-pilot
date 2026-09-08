"""No-follow data store. Locks never create run artifacts; CAS preserves conflicts."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def anchor_snapshot_id(evidence):
    """Shared published identity for exactly the current anchor binding fields."""
    return sha(canonical({key: evidence[key] for key in
        ('files', 'style_sha256', 'review_snapshot_id')}).rstrip(b'\n'))


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('invalid_schema')
        result[key] = value
    return result


def parse_json(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_schema')))


def no_follow(path):
    for item in (path,) + tuple(path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('unsafe_evidence_path')


class RunStore:
    def __init__(self, root):
        self.root = Path(os.path.abspath(str(root)))
        no_follow(self.root)
        if not self.root.is_dir():
            raise ValueError('run_missing')
        self.writes = []
        self.observed = {}
        self.locked = False
        self.before_write = None

    def path(self, name):
        if (not isinstance(name, str) or not name or '\\' in name or ':' in name
                or any(p in ('', '.', '..') for p in name.split('/'))
                or any(ord(c) < 32 or ord(c) == 127 for c in name)):
            raise ValueError('unsafe_evidence_path')
        path = self.root.joinpath(*name.split('/'))
        no_follow(path)
        return path

    def read_bytes(self, name):
        path = self.path(name)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('unsafe_evidence_path')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(str(path), flags), 'rb') as stream:
            before = os.fstat(stream.fileno())
            data = stream.read()
            after = os.fstat(stream.fileno())
        no_follow(path)
        current = path.stat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) !=
            (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)):
            raise ValueError('visual_generation_state_conflict')
        self.observed[name] = sha(data)
        return data

    def read_json(self, name):
        return parse_json(self.read_bytes(name))

    def hash(self, name):
        try:
            return sha(self.read_bytes(name))
        except FileNotFoundError:
            self.observed[name] = 'none'
            return 'none'

    def write_bytes(self, name, data, expected):
        if not self.locked:
            raise ValueError('runtime_lock_required')
        if self.before_write:
            self.before_write()
        if self.hash(name) != expected:
            raise ValueError('visual_generation_state_conflict')
        if expected == sha(data):
            return expected
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        no_follow(path)
        fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self.hash(name) != expected:
                raise ValueError('visual_generation_state_conflict')
            no_follow(path)
            os.replace(temporary, path)
            self.writes.append(name)
            observed = self.read_bytes(name)
            if observed != data:
                raise ValueError('write_verification_failed')
            return sha(observed)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_json(self, name, value, expected):
        return self.write_bytes(name, canonical(value), expected)

    def remove_bytes(self, name, expected):
        if not self.locked:
            raise ValueError('runtime_lock_required')
        if self.before_write:
            self.before_write()
        if self.hash(name) != expected:
            raise ValueError('visual_generation_state_conflict')
        self.path(name).unlink()
        self.writes.append(name)
        self.observed[name] = 'none'

    @contextlib.contextmanager
    def lock(self):
        if self.locked:
            raise ValueError('runtime_lock_required')
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            name = 'Local\\PptPilot-' + hashlib.sha256(os.path.normcase(str(self.root)).encode()).hexdigest()
            handle = kernel.CreateMutexW(None, False, name)
            if not handle:
                raise ValueError('runtime_lock_unavailable')
            acquired = kernel.WaitForSingleObject(handle, 0) in (0, 0x80)
            if not acquired:
                kernel.CloseHandle(handle)
                raise ValueError('runtime_busy')
            release = lambda: (kernel.ReleaseMutex(handle), kernel.CloseHandle(handle))
        else:
            import fcntl
            fd = os.open(str(self.root), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise ValueError('runtime_busy')
            release = lambda: (fcntl.flock(fd, fcntl.LOCK_UN), os.close(fd))
        self.locked = True
        try:
            yield self
        finally:
            self.locked = False
            release()
