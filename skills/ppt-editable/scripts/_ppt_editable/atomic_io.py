"""Atomic files, output locking, and manifest-last promotion recovery."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
from typing import Callable, Mapping, Optional, Tuple
import uuid

from .contract import _deck_id_is_safe, _is_reparse_stat
from .errors import EditableError
from .model import EditableResult, Failure


@dataclass(frozen=True)
class OutputPaths:
    run_dir: Path
    deck_id: str
    root: Path
    tmp_dir: Path
    quarantine_dir: Path
    manifest_path: Path
    verified_path: Path
    unverified_path: Path
    lock_path: Path


@dataclass(frozen=True)
class PromotionTransaction:
    transaction_id: str
    directory: Path
    journal_path: Path
    paths: OutputPaths
    snapshot_id: str
    target_kind: str
    target_path: Path


@dataclass(frozen=True)
class RecoveryReport:
    cleaned: int = 0
    restored: int = 0
    quarantined: int = 0
    failures: Tuple[str, ...] = ()


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> Optional[str]:
    if not os.path.lexists(str(path)):
        return None
    _reject_unsafe_existing_file(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _ensure_safe_directory(path: Path) -> Path:
    absolute = Path(path).absolute()
    chain = []
    current = absolute
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(chain):
        if os.path.lexists(str(component)):
            try:
                metadata = os.lstat(str(component))
            except OSError as exc:
                raise EditableError("source_path_unsafe", "output path cannot be inspected") from exc
            if (
                stat.S_ISLNK(metadata.st_mode)
                or _is_reparse_stat(metadata)
                or not stat.S_ISDIR(metadata.st_mode)
            ):
                raise EditableError("source_path_unsafe", "output directory is unsafe")
        else:
            try:
                os.mkdir(str(component))
                metadata = os.lstat(str(component))
            except OSError as exc:
                raise EditableError("candidate_write_failed", "output directory cannot be created") from exc
            if _is_reparse_stat(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise EditableError("source_path_unsafe", "created output directory is unsafe")
    return absolute


def _reject_unsafe_existing_file(path: Path) -> None:
    if not os.path.lexists(str(path)):
        return
    try:
        metadata = os.lstat(str(path))
    except OSError as exc:
        raise EditableError("source_path_unsafe", "output file cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse_stat(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise EditableError("source_path_unsafe", "output file is unsafe")


def build_output_paths(run_dir: Path, deck_id: str) -> OutputPaths:
    if not _deck_id_is_safe(deck_id):
        raise EditableError("deck_id_invalid", "deck_id is not path-safe")
    run_dir = Path(run_dir).absolute()
    root = run_dir / "delivery" / "editable"
    tmp_dir = root / ".tmp"
    quarantine_dir = root / "quarantine"
    for path in (root, tmp_dir, quarantine_dir):
        _ensure_safe_directory(path)
    return OutputPaths(
        run_dir=run_dir,
        deck_id=deck_id,
        root=root,
        tmp_dir=tmp_dir,
        quarantine_dir=quarantine_dir,
        manifest_path=root / "editable-result.json",
        verified_path=root / "{}-editable.pptx".format(deck_id),
        unverified_path=root / "{}-editable-unverified.pptx".format(deck_id),
        lock_path=root / ".editable.lock",
    )


def atomic_write_bytes(path: Path, data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    path = Path(path).absolute()
    _ensure_safe_directory(path.parent)
    _reject_unsafe_existing_file(path)
    temporary = path.with_name(".{}.{}.tmp".format(path.name, uuid.uuid4().hex))
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _ensure_safe_directory(path.parent)
        _reject_unsafe_existing_file(path)
        os.replace(str(temporary), str(path))
        persisted = path.read_bytes()
    except EditableError:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    except (OSError, IOError) as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise EditableError("candidate_write_failed", "atomic file write failed") from exc
    if persisted != data:
        raise EditableError("candidate_hash_mismatch", "persisted bytes differ")
    return _sha256_bytes(persisted)


def atomic_write_json(path: Path, value: Mapping[str, object]) -> str:
    data = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(path, data)


def verify_file_hash(path: Path, expected_sha256: str) -> None:
    try:
        observed = _file_hash(Path(path))
    except OSError as exc:
        raise EditableError("candidate_hash_mismatch", "cannot reread file hash") from exc
    if observed != expected_sha256:
        raise EditableError("candidate_hash_mismatch", "file hash does not match")


class OutputLock:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).absolute()
        self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def __enter__(self) -> "OutputLock":
        _ensure_safe_directory(self.path.parent)
        _reject_unsafe_existing_file(self.path)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as exc:
            handle.close()
            raise EditableError("promotion_conflict", "editable output is locked") from exc
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _lock_context(
    paths: OutputPaths,
    output_lock: Optional[OutputLock],
):
    if output_lock is None:
        return OutputLock(paths.lock_path)
    if (
        not output_lock.held
        or output_lock.path != paths.lock_path.absolute()
    ):
        raise EditableError("promotion_conflict", "provided output lock is not held")
    return nullcontext()


def _active_transaction_directories(paths: OutputPaths) -> Tuple[Path, ...]:
    _ensure_safe_directory(paths.tmp_dir)
    directories = []
    try:
        with os.scandir(str(paths.tmp_dir)) as entries:
            discovered = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise EditableError("promotion_conflict", "transaction root cannot be enumerated") from exc
    for entry in discovered:
        if not entry.name.startswith("txn-"):
            continue
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise EditableError("promotion_conflict", "transaction entry cannot be inspected") from exc
        path = paths.tmp_dir / entry.name
        if entry.is_symlink() or _is_reparse_stat(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise EditableError("source_path_unsafe", "transaction entry is unsafe")
        directories.append(path)
    return tuple(directories)


def begin_promotion(
    paths: OutputPaths,
    snapshot_id: str,
    target_kind: str,
    *,
    output_lock: Optional[OutputLock] = None,
) -> PromotionTransaction:
    if target_kind not in ("verified", "unverified"):
        raise EditableError("promotion_conflict", "invalid promotion target kind")
    with _lock_context(paths, output_lock):
        if _active_transaction_directories(paths):
            raise EditableError("promotion_conflict", "an active promotion transaction already exists")
        transaction_id = "txn-{:020d}-{}".format(time.time_ns(), uuid.uuid4().hex)
        directory = paths.tmp_dir / transaction_id
        os.mkdir(str(directory))
        metadata = os.lstat(str(directory))
        if _is_reparse_stat(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise EditableError("source_path_unsafe", "created transaction directory is unsafe")
    target = paths.verified_path if target_kind == "verified" else paths.unverified_path
    return PromotionTransaction(
        transaction_id=transaction_id,
        directory=directory,
        journal_path=directory / "journal.json",
        paths=paths,
        snapshot_id=snapshot_id,
        target_kind=target_kind,
        target_path=target,
    )


def _copy_backup(source: Path, destination: Path) -> Optional[str]:
    if not os.path.lexists(str(source)):
        return None
    _reject_unsafe_existing_file(source)
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise EditableError("promotion_conflict", "previous output cannot be captured") from exc
    digest = _sha256_bytes(data)
    observed = atomic_write_bytes(destination, data)
    if observed != digest:
        raise EditableError("promotion_conflict", "promotion backup hash mismatch")
    verify_file_hash(destination, digest)
    return digest


def _call_fault(fault_injector: Optional[Callable[[str], None]], phase: str) -> None:
    if fault_injector is not None:
        fault_injector(phase)


_RESULT_BASE_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "status",
        "deck_id",
        "input_snapshot_id",
        "slide_count",
        "output_path",
        "output_sha256",
        "failures",
        "warnings",
    }
)


def _valid_authoritative_verified(
    value: object,
    paths: OutputPaths,
) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value)
        == {"status", "input_snapshot_id", "output_path", "output_sha256"}
        and value.get("status") == "PASS"
        and isinstance(value.get("input_snapshot_id"), str)
        and _SHA256_RE.fullmatch(str(value.get("input_snapshot_id"))) is not None
        and value.get("output_path")
        == paths.verified_path.relative_to(paths.run_dir).as_posix()
        and isinstance(value.get("output_sha256"), str)
        and _SHA256_RE.fullmatch(str(value.get("output_sha256"))) is not None
    )


def _result_manifest_is_valid(
    value: object,
    paths: OutputPaths,
) -> bool:
    if not isinstance(value, dict):
        return False
    keys = set(value)
    if keys not in (_RESULT_BASE_KEYS, _RESULT_BASE_KEYS | {"authoritative_verified"}):
        return False
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
        or value.get("kind") != "ppt_editable_result"
        or value.get("deck_id") != paths.deck_id
        or not isinstance(value.get("input_snapshot_id"), str)
        or _SHA256_RE.fullmatch(str(value.get("input_snapshot_id"))) is None
        or type(value.get("slide_count")) is not int
        or value.get("slide_count") < 0
        or not isinstance(value.get("failures"), (list, tuple))
        or not isinstance(value.get("warnings"), (list, tuple))
    ):
        return False
    status = value.get("status")
    if status == "PASS":
        expected_path = paths.verified_path.relative_to(paths.run_dir).as_posix()
    elif status == "GENERATED_UNVERIFIED":
        expected_path = paths.unverified_path.relative_to(paths.run_dir).as_posix()
    elif status in ("BLOCKED", "FAILED_VERIFICATION"):
        return value.get("output_path") is None and value.get("output_sha256") is None
    else:
        return False
    if (
        value.get("output_path") != expected_path
        or not isinstance(value.get("output_sha256"), str)
        or _SHA256_RE.fullmatch(str(value.get("output_sha256"))) is None
    ):
        return False
    authority = value.get("authoritative_verified")
    return authority is None or _valid_authoritative_verified(authority, paths)


def _authority_from_manifest(
    value: Optional[Mapping[str, object]],
    paths: OutputPaths,
) -> Optional[Mapping[str, str]]:
    if value is None or not _result_manifest_is_valid(value, paths):
        return None
    if value.get("status") == "PASS":
        return {
            "status": "PASS",
            "input_snapshot_id": str(value["input_snapshot_id"]),
            "output_path": str(value["output_path"]),
            "output_sha256": str(value["output_sha256"]),
        }
    authority = value.get("authoritative_verified")
    return dict(authority) if _valid_authoritative_verified(authority, paths) else None


def _manifest_files_match(value: Mapping[str, object], paths: OutputPaths) -> bool:
    if not _result_manifest_is_valid(value, paths):
        return False
    status = value.get("status")
    if status == "PASS":
        if _file_hash(paths.verified_path) != value.get("output_sha256"):
            return False
    elif status == "GENERATED_UNVERIFIED":
        if _file_hash(paths.unverified_path) != value.get("output_sha256"):
            return False
    authority = _authority_from_manifest(value, paths)
    if authority is not None and _file_hash(paths.verified_path) != authority["output_sha256"]:
        return False
    return True


def _result_manifest(
    result: EditableResult,
    transaction: PromotionTransaction,
    output_hash: str,
    previous_manifest: Optional[Mapping[str, object]],
) -> Mapping[str, object]:
    expected_status = "PASS" if transaction.target_kind == "verified" else "GENERATED_UNVERIFIED"
    if result.status != expected_status or result.input_snapshot_id != transaction.snapshot_id:
        raise EditableError("promotion_conflict", "result does not match promotion")
    output_relative = transaction.target_path.relative_to(transaction.paths.run_dir).as_posix()
    committed = replace(
        result,
        output_path=output_relative,
        output_sha256=output_hash,
    )
    value = asdict(committed)
    value["schema_version"] = 1
    value["kind"] = "ppt_editable_result"
    if transaction.target_kind == "unverified":
        authority = _authority_from_manifest(previous_manifest, transaction.paths)
        if authority is not None:
            value["authoritative_verified"] = authority
    return value


def promote_output(
    transaction: PromotionTransaction,
    staged_output: Path,
    result: EditableResult,
    *,
    fault_injector: Optional[Callable[[str], None]] = None,
    output_lock: Optional[OutputLock] = None,
) -> str:
    staged_output = Path(staged_output).absolute()
    try:
        staged_output.relative_to(transaction.directory.absolute())
    except ValueError as exc:
        raise EditableError("promotion_conflict", "staged output is outside transaction") from exc
    _ensure_safe_directory(staged_output.parent)
    try:
        metadata = os.lstat(str(staged_output))
    except OSError as exc:
        raise EditableError("candidate_write_failed", "staged output is missing") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or _is_reparse_stat(metadata)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise EditableError("promotion_conflict", "staged output is unsafe")
    new_hash = _file_hash(staged_output)
    if new_hash is None:
        raise EditableError("candidate_hash_mismatch", "staged output cannot be hashed")

    with _lock_context(transaction.paths, output_lock):
        manifest_exists = os.path.lexists(str(transaction.paths.manifest_path))
        previous_manifest = _read_json(transaction.paths.manifest_path)
        if manifest_exists and (
            previous_manifest is None
            or not _manifest_files_match(previous_manifest, transaction.paths)
        ):
            raise EditableError("promotion_conflict", "previous manifest authority is invalid")
        if not manifest_exists and (
            transaction.paths.verified_path.exists()
            or transaction.paths.unverified_path.exists()
        ):
            raise EditableError("promotion_conflict", "public output has no manifest authority")
        previous_target_backup = transaction.directory / "previous-target.pptx"
        previous_manifest_backup = transaction.directory / "previous-manifest.json"
        previous_target_hash = _copy_backup(
            transaction.target_path, previous_target_backup
        )
        previous_manifest_hash = _copy_backup(
            transaction.paths.manifest_path, previous_manifest_backup
        )
        journal = {
            "schema_version": 1,
            "kind": "ppt_editable_promotion",
            "transaction_id": transaction.transaction_id,
            "state": "PREPARED",
            "snapshot_id": transaction.snapshot_id,
            "target_kind": transaction.target_kind,
            "target_path": transaction.target_path.relative_to(
                transaction.paths.root
            ).as_posix(),
            "new_output_sha256": new_hash,
            "previous_target_sha256": previous_target_hash or "none",
            "previous_target_backup": (
                previous_target_backup.name if previous_target_hash else "none"
            ),
            "previous_manifest_sha256": previous_manifest_hash or "none",
            "previous_manifest_backup": (
                previous_manifest_backup.name if previous_manifest_hash else "none"
            ),
        }
        atomic_write_json(transaction.journal_path, journal)
        _call_fault(fault_injector, "after_journal_prepared")
        _ensure_safe_directory(transaction.target_path.parent)
        _reject_unsafe_existing_file(transaction.target_path)
        os.replace(str(staged_output), str(transaction.target_path))
        _call_fault(fault_injector, "after_target_replaced")
        verify_file_hash(transaction.target_path, new_hash)
        _call_fault(fault_injector, "after_target_verified")
        manifest = _result_manifest(
            result,
            transaction,
            new_hash,
            previous_manifest,
        )
        atomic_write_json(transaction.paths.manifest_path, manifest)
        _call_fault(fault_injector, "after_manifest_replaced")
        try:
            shutil.rmtree(transaction.directory)
        except OSError:
            pass
    return new_hash


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError("non-finite JSON constant: {}".format(value))


def _read_json(path: Path) -> Optional[Mapping[str, object]]:
    if not os.path.lexists(str(path)):
        return None
    try:
        _reject_unsafe_existing_file(path)
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (EditableError, OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _restore_backup(backup: Path, destination: Path, expected_hash: str) -> None:
    if not os.path.lexists(str(backup)):
        raise EditableError("promotion_conflict", "promotion backup is missing")
    _reject_unsafe_existing_file(backup)
    if _file_hash(backup) != expected_hash:
        raise EditableError("promotion_conflict", "promotion backup is invalid")
    atomic_write_bytes(destination, backup.read_bytes())
    verify_file_hash(destination, expected_hash)


def _quarantine_file(path: Path, destination: Path) -> None:
    if not os.path.lexists(str(path)):
        return
    _ensure_safe_directory(Path(path).parent)
    _ensure_safe_directory(Path(destination).parent)
    os.replace(str(path), str(destination))


def quarantine_transaction(
    transaction: PromotionTransaction,
    reason: Failure,
) -> Path:
    return _move_directory_to_quarantine(
        transaction.paths,
        transaction.directory,
        "-" + reason.code,
    )


_JOURNAL_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "transaction_id",
        "state",
        "snapshot_id",
        "target_kind",
        "target_path",
        "new_output_sha256",
        "previous_target_sha256",
        "previous_target_backup",
        "previous_manifest_sha256",
        "previous_manifest_backup",
    }
)
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _journal_is_valid(
    paths: OutputPaths,
    directory: Path,
    journal: Mapping[str, object],
) -> bool:
    if set(journal) != _JOURNAL_KEYS:
        return False
    if (
        type(journal.get("schema_version")) is not int
        or journal.get("schema_version") != 1
        or journal.get("kind") != "ppt_editable_promotion"
        or journal.get("state") != "PREPARED"
        or journal.get("transaction_id") != directory.name
        or journal.get("target_kind") not in ("verified", "unverified")
        or not isinstance(journal.get("snapshot_id"), str)
        or _SHA256_RE.fullmatch(str(journal.get("snapshot_id"))) is None
        or _SHA256_RE.fullmatch(str(journal.get("new_output_sha256"))) is None
    ):
        return False
    target = paths.verified_path if journal["target_kind"] == "verified" else paths.unverified_path
    if journal.get("target_path") != target.relative_to(paths.root).as_posix():
        return False
    for hash_key, backup_key, expected_backup in (
        ("previous_target_sha256", "previous_target_backup", "previous-target.pptx"),
        ("previous_manifest_sha256", "previous_manifest_backup", "previous-manifest.json"),
    ):
        hash_value = journal.get(hash_key)
        backup_value = journal.get(backup_key)
        if hash_value == "none":
            if backup_value != "none":
                return False
        elif (
            not isinstance(hash_value, str)
            or _SHA256_RE.fullmatch(hash_value) is None
            or backup_value != expected_backup
        ):
            return False
    return True


def _transaction_from_journal(paths: OutputPaths, directory: Path, journal: Mapping[str, object]) -> PromotionTransaction:
    target_kind = journal.get("target_kind")
    target = paths.verified_path if target_kind == "verified" else paths.unverified_path
    return PromotionTransaction(
        transaction_id=str(journal.get("transaction_id")),
        directory=directory,
        journal_path=directory / "journal.json",
        paths=paths,
        snapshot_id=str(journal.get("snapshot_id")),
        target_kind=str(target_kind),
        target_path=target,
    )


def _move_directory_to_quarantine(paths: OutputPaths, directory: Path, suffix: str) -> Path:
    destination = paths.quarantine_dir / (directory.name + suffix)
    _ensure_safe_directory(Path(directory).parent)
    _ensure_safe_directory(destination.parent)
    if os.path.lexists(str(destination)):
        metadata = os.lstat(str(destination))
        if stat.S_ISLNK(metadata.st_mode) or _is_reparse_stat(metadata):
            raise EditableError("source_path_unsafe", "quarantine destination is unsafe")
        if stat.S_ISDIR(metadata.st_mode):
            shutil.rmtree(destination)
        elif stat.S_ISREG(metadata.st_mode):
            destination.unlink()
        else:
            raise EditableError("source_path_unsafe", "quarantine destination is unsafe")
    _ensure_safe_directory(Path(directory).parent)
    _ensure_safe_directory(destination.parent)
    os.replace(str(directory), str(destination))
    return destination


def _recover_invalid_transaction(
    paths: OutputPaths,
    directory: Path,
) -> Tuple[int, int, Optional[str]]:
    current_manifest = _read_json(paths.manifest_path)
    if current_manifest is not None and _manifest_files_match(current_manifest, paths):
        _move_directory_to_quarantine(paths, directory, "-invalid")
        return 0, 1, None

    previous_manifest_path = directory / "previous-manifest.json"
    previous_manifest = _read_json(previous_manifest_path)
    try:
        current_manifest_hash = _file_hash(paths.manifest_path)
    except EditableError:
        current_manifest_hash = None
    try:
        backup_manifest_hash = _file_hash(previous_manifest_path)
    except EditableError:
        backup_manifest_hash = None
    public_manifest_anchors_backup = bool(
        current_manifest is not None
        and previous_manifest is not None
        and _result_manifest_is_valid(current_manifest, paths)
        and _result_manifest_is_valid(previous_manifest, paths)
        and current_manifest_hash is not None
        and current_manifest_hash == backup_manifest_hash
    )
    if public_manifest_anchors_backup:
        restored = 0
        previous_status = previous_manifest.get("status")
        if previous_status == "PASS":
            expected_target = paths.verified_path
        elif previous_status == "GENERATED_UNVERIFIED":
            expected_target = paths.unverified_path
        else:
            expected_target = None
        if expected_target is not None:
            expected_hash = str(previous_manifest.get("output_sha256"))
            if _file_hash(expected_target) != expected_hash:
                backup = directory / "previous-target.pptx"
                if _file_hash(backup) != expected_hash:
                    _move_directory_to_quarantine(paths, directory, "-recovery-failed")
                    return 0, 1, "invalid journal has no coherent previous target backup"
                _restore_backup(backup, expected_target, expected_hash)
                restored += 1
        authority = _authority_from_manifest(previous_manifest, paths)
        if authority is not None and _file_hash(paths.verified_path) != authority["output_sha256"]:
            backup = directory / "previous-target.pptx"
            if _file_hash(backup) == authority["output_sha256"]:
                _restore_backup(backup, paths.verified_path, authority["output_sha256"])
                restored += 1
            else:
                _move_directory_to_quarantine(paths, directory, "-recovery-failed")
                return restored, 1, "verified authority cannot be restored"
        if previous_status == "PASS" and paths.unverified_path.exists():
            _quarantine_file(
                paths.unverified_path,
                paths.quarantine_dir / (directory.name + "-uncommitted-unverified.pptx"),
            )
        atomic_write_bytes(paths.manifest_path, previous_manifest_path.read_bytes())
        if not _manifest_files_match(previous_manifest, paths):
            _move_directory_to_quarantine(paths, directory, "-recovery-failed")
            return restored, 1, "restored manifest is not coherent"
        _move_directory_to_quarantine(paths, directory, "-invalid")
        return restored, 1, None

    for label, public_path in (
        ("verified", paths.verified_path),
        ("unverified", paths.unverified_path),
        ("manifest", paths.manifest_path),
    ):
        if public_path.exists():
            _quarantine_file(
                public_path,
                paths.quarantine_dir / (directory.name + "-untrusted-" + label),
            )
    _move_directory_to_quarantine(paths, directory, "-invalid")
    return 0, 1, "invalid journal has no coherent authority backup"


def _manifest_references(
    value: Mapping[str, object],
    paths: OutputPaths,
) -> Mapping[str, str]:
    references = {}
    output_path = value.get("output_path")
    output_hash = value.get("output_sha256")
    if isinstance(output_path, str) and isinstance(output_hash, str):
        references[output_path] = output_hash
    authority = _authority_from_manifest(value, paths)
    if authority is not None:
        references[authority["output_path"]] = authority["output_sha256"]
    return references


def _previous_backups_are_coherent(
    paths: OutputPaths,
    transaction: PromotionTransaction,
    directory: Path,
    journal: Mapping[str, object],
) -> bool:
    previous_hash = journal.get("previous_target_sha256")
    previous_manifest_hash = journal.get("previous_manifest_sha256")
    target_backup = directory / "previous-target.pptx"
    manifest_backup = directory / "previous-manifest.json"
    if previous_manifest_hash == "none":
        return previous_hash == "none" and not os.path.lexists(str(target_backup))
    if (
        not isinstance(previous_manifest_hash, str)
        or _file_hash(manifest_backup) != previous_manifest_hash
    ):
        return False
    previous_manifest = _read_json(manifest_backup)
    if previous_manifest is None or not _result_manifest_is_valid(previous_manifest, paths):
        return False
    if previous_hash == "none":
        if os.path.lexists(str(target_backup)):
            return False
    elif not isinstance(previous_hash, str) or _file_hash(target_backup) != previous_hash:
        return False

    target_relative = transaction.target_path.relative_to(paths.run_dir).as_posix()
    for relative_path, expected_hash in _manifest_references(previous_manifest, paths).items():
        public_path = paths.run_dir / relative_path
        observed = previous_hash if relative_path == target_relative else _file_hash(public_path)
        if observed != expected_hash:
            return False
    return True


def _quarantine_untrusted_public_state(
    paths: OutputPaths,
    directory: Path,
) -> int:
    moved = 0
    for label, public_path in (
        ("verified", paths.verified_path),
        ("unverified", paths.unverified_path),
        ("manifest", paths.manifest_path),
    ):
        if os.path.lexists(str(public_path)):
            _quarantine_file(
                public_path,
                paths.quarantine_dir / (directory.name + "-untrusted-" + label),
            )
            moved += 1
    return moved


def _scan_transactions_for_recovery(paths: OutputPaths) -> Tuple[Tuple[Path, ...], int]:
    _ensure_safe_directory(paths.tmp_dir)
    directories = []
    quarantined = 0
    try:
        with os.scandir(str(paths.tmp_dir)) as entries:
            discovered = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise EditableError("promotion_conflict", "transaction root cannot be enumerated") from exc
    for entry in discovered:
        if not entry.name.startswith("txn-"):
            continue
        try:
            metadata = entry.stat(follow_symlinks=False)
        except OSError:
            metadata = None
        path = paths.tmp_dir / entry.name
        if (
            metadata is None
            or entry.is_symlink()
            or _is_reparse_stat(metadata)
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            _move_directory_to_quarantine(paths, path, "-unsafe")
            quarantined += 1
            continue
        directories.append(path)
    return tuple(sorted(directories, key=lambda path: path.name, reverse=True)), quarantined


def recover_incomplete_transactions(
    paths: OutputPaths,
    *,
    output_lock: Optional[OutputLock] = None,
) -> RecoveryReport:
    cleaned = restored = quarantined = 0
    failures = []
    with _lock_context(paths, output_lock):
        directories, unsafe_quarantined = _scan_transactions_for_recovery(paths)
        quarantined += unsafe_quarantined
        for directory in directories:
            journal = _read_json(directory / "journal.json")
            if not journal or not _journal_is_valid(paths, directory, journal):
                recovered, isolated, failure = _recover_invalid_transaction(
                    paths, directory
                )
                restored += recovered
                quarantined += isolated
                if failure:
                    failures.append("{}: {}".format(directory.name, failure))
                continue
            transaction = _transaction_from_journal(paths, directory, journal)
            target_hash = _file_hash(transaction.target_path)
            new_hash = journal.get("new_output_sha256")
            previous_hash = journal.get("previous_target_sha256")
            manifest_path_exists = os.path.lexists(str(paths.manifest_path))
            manifest = _read_json(paths.manifest_path)
            try:
                current_manifest_hash = _file_hash(paths.manifest_path)
            except EditableError:
                current_manifest_hash = None
            expected_status = (
                "PASS" if transaction.target_kind == "verified" else "GENERATED_UNVERIFIED"
            )
            committed = bool(
                target_hash == new_hash
                and manifest
                and _result_manifest_is_valid(manifest, paths)
                and _manifest_files_match(manifest, paths)
                and manifest.get("status") == expected_status
                and manifest.get("input_snapshot_id") == journal.get("snapshot_id")
                and manifest.get("output_sha256") == new_hash
                and manifest.get("output_path")
                == transaction.target_path.relative_to(paths.run_dir).as_posix()
            )
            if committed:
                try:
                    shutil.rmtree(directory)
                    cleaned += 1
                except OSError as exc:
                    failures.append("{}: post-commit cleanup failed: {}".format(directory.name, exc))
                continue

            previous_backup = directory / str(journal.get("previous_target_backup"))
            manifest_backup = directory / str(journal.get("previous_manifest_backup"))
            previous_manifest_hash = journal.get("previous_manifest_sha256")
            public_target_is_previous = (
                (previous_hash == "none" and target_hash is None)
                or target_hash == previous_hash
            )
            if previous_manifest_hash == "none":
                public_manifest_is_previous = not manifest_path_exists
            else:
                public_manifest_is_previous = bool(
                    current_manifest_hash == previous_manifest_hash
                    and manifest is not None
                    and _result_manifest_is_valid(manifest, paths)
                    and _manifest_files_match(manifest, paths)
                )
            if public_target_is_previous and public_manifest_is_previous:
                try:
                    shutil.rmtree(directory)
                    cleaned += 1
                except OSError as exc:
                    failures.append(
                        "{}: stale transaction cleanup failed: {}".format(
                            directory.name,
                            exc,
                        )
                    )
                continue
            if not _previous_backups_are_coherent(
                paths,
                transaction,
                directory,
                journal,
            ):
                _quarantine_untrusted_public_state(paths, directory)
                _move_directory_to_quarantine(paths, directory, "-incoherent")
                quarantined += 1
                failures.append("{}: previous target and manifest backups are incoherent".format(directory.name))
                continue
            try:
                if (
                    current_manifest_hash is not None
                    and current_manifest_hash != previous_manifest_hash
                ):
                    _quarantine_file(
                        paths.manifest_path,
                        paths.quarantine_dir
                        / (directory.name + "-ambiguous-manifest.json"),
                    )
                    quarantined += 1

                if target_hash == new_hash:
                    if previous_hash == "none":
                        _quarantine_file(
                            transaction.target_path,
                            directory / "uncommitted-target.pptx",
                        )
                        if previous_manifest_hash == "none":
                            if os.path.lexists(str(paths.manifest_path)):
                                _quarantine_file(
                                    paths.manifest_path,
                                    directory / "uncommitted-manifest.json",
                                )
                        else:
                            _restore_backup(
                                manifest_backup,
                                paths.manifest_path,
                                str(previous_manifest_hash),
                            )
                            restored_manifest = _read_json(paths.manifest_path)
                            if (
                                restored_manifest is None
                                or not _manifest_files_match(restored_manifest, paths)
                            ):
                                raise EditableError(
                                    "promotion_conflict",
                                    "restored previous manifest is incoherent",
                                )
                        _move_directory_to_quarantine(paths, directory, "")
                        quarantined += 1
                        continue
                    _restore_backup(
                        previous_backup,
                        transaction.target_path,
                        str(previous_hash),
                    )
                    restored += 1
                elif target_hash == previous_hash:
                    cleaned += 1
                else:
                    if target_hash is not None:
                        _quarantine_file(
                            transaction.target_path,
                            paths.quarantine_dir
                            / (directory.name + "-ambiguous-target.pptx"),
                        )
                        quarantined += 1
                    if previous_hash != "none":
                        _restore_backup(
                            previous_backup,
                            transaction.target_path,
                            str(previous_hash),
                        )
                        restored += 1

                if previous_manifest_hash == "none":
                    if paths.manifest_path.exists():
                        paths.manifest_path.unlink()
                else:
                    _restore_backup(
                        manifest_backup,
                        paths.manifest_path,
                        str(previous_manifest_hash),
                    )
                if directory.exists():
                    shutil.rmtree(directory)
            except (EditableError, OSError) as exc:
                failures.append("{}: {}".format(directory.name, exc))
                _quarantine_untrusted_public_state(paths, directory)
                quarantined += 1
    return RecoveryReport(
        cleaned=cleaned,
        restored=restored,
        quarantined=quarantined,
        failures=tuple(failures),
    )
