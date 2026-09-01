import hashlib
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "ppt-editable" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import _ppt_editable.atomic_io as atomic_io  # noqa: E402
from _ppt_editable import EditableError, EditableResult  # noqa: E402
from _ppt_editable.atomic_io import (  # noqa: E402
    OutputLock,
    atomic_write_bytes,
    atomic_write_json,
    begin_promotion,
    build_output_paths,
    promote_output,
    recover_incomplete_transactions,
    verify_file_hash,
)


def sha256_id(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_path(path):
    return sha256_id(Path(path).read_bytes())


class AtomicIoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.run_dir = Path(self.directory.name) / "run"
        self.run_dir.mkdir()
        self.paths = build_output_paths(self.run_dir, "example-deck")
        self.snapshot = "sha256:" + "a" * 64

    def _result(self, status="PASS"):
        return EditableResult(
            status=status,
            deck_id="example-deck",
            input_snapshot_id=self.snapshot,
            slide_count=2,
        )

    def _stage(self, transaction, data=b"new-pptx"):
        path = transaction.directory / "candidate.pptx"
        digest = atomic_write_bytes(path, data)
        self.assertEqual(digest, sha256_id(data))
        return path

    def _old_manifest(self, target, data=b"old-pptx"):
        target_hash = atomic_write_bytes(target, data)
        value = {
            "schema_version": 1,
            "kind": "ppt_editable_result",
            "deck_id": "example-deck",
            "input_snapshot_id": "sha256:" + "0" * 64,
            "status": "PASS",
            "output_path": target.relative_to(self.run_dir).as_posix(),
            "output_sha256": target_hash,
            "slide_count": 2,
            "failures": [],
            "warnings": [],
        }
        atomic_write_json(self.paths.manifest_path, value)
        return target_hash, value

    def test_atomic_writes_are_canonical_and_reread_hash_verified(self):
        binary = self.paths.root / "binary.bin"
        self.assertEqual(atomic_write_bytes(binary, b"abc"), sha256_id(b"abc"))
        verify_file_hash(binary, sha256_id(b"abc"))
        with self.assertRaises(EditableError) as raised:
            verify_file_hash(binary, sha256_id(b"wrong"))
        self.assertEqual(raised.exception.code, "candidate_hash_mismatch")

        document = self.paths.root / "value.json"
        digest = atomic_write_json(document, {"z": 1, "a": "中文"})
        expected = '{\n  "a": "中文",\n  "z": 1\n}\n'.encode("utf-8")
        self.assertEqual(document.read_bytes(), expected)
        self.assertEqual(digest, sha256_id(expected))

    def test_output_lock_rejects_concurrent_holder(self):
        with OutputLock(self.paths.lock_path):
            with self.assertRaises(EditableError) as raised:
                with OutputLock(self.paths.lock_path):
                    pass
        self.assertEqual(raised.exception.code, "promotion_conflict")
        with OutputLock(self.paths.lock_path):
            pass

    def test_successful_promotion_writes_manifest_last_and_cleans_journal(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)
        phases = []
        digest = promote_output(
            transaction,
            staged,
            self._result(),
            fault_injector=phases.append,
        )
        self.assertEqual(digest, sha256_id(b"new-pptx"))
        self.assertEqual(self.paths.verified_path.read_bytes(), b"new-pptx")
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(manifest["output_sha256"], digest)
        self.assertEqual(
            manifest["output_path"],
            self.paths.verified_path.relative_to(self.run_dir).as_posix(),
        )
        self.assertFalse(transaction.directory.exists())
        self.assertLess(
            phases.index("after_target_verified"),
            phases.index("after_manifest_replaced"),
        )

    def test_recovery_restores_previous_target_when_crash_precedes_manifest(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaisesRegex(RuntimeError, "crash"):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"new-pptx")
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        self.assertEqual(sha256_id(self.paths.verified_path.read_bytes()), old_hash)
        self.assertEqual(report.restored, 1)

    def test_previous_public_commit_wins_even_when_transaction_backup_is_corrupt(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_journal_prepared":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        (transaction.directory / "previous-target.pptx").unlink()

        report = recover_incomplete_transactions(self.paths)

        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        self.assertFalse(transaction.directory.exists())
        self.assertEqual(report.cleaned, 1)
        self.assertEqual(report.quarantined, 0)

    def test_recovery_quarantines_uncommitted_target_without_previous_final(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        report = recover_incomplete_transactions(self.paths)
        self.assertFalse(self.paths.verified_path.exists())
        self.assertFalse(self.paths.manifest_path.exists())
        self.assertEqual(report.quarantined, 1)
        self.assertTrue(any(self.paths.quarantine_dir.iterdir()))

    def test_recovery_keeps_committed_target_when_manifest_was_replaced(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"new-pptx")
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))["input_snapshot_id"],
            self.snapshot,
        )
        self.assertEqual(report.cleaned, 1)
        self.assertFalse(transaction.directory.exists())

    def test_ambiguous_target_is_quarantined_before_previous_final_is_restored(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        self.paths.verified_path.write_bytes(b"third-party")
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertGreaterEqual(report.quarantined, 1)
        quarantined_bytes = [
            path.read_bytes()
            for path in self.paths.quarantine_dir.rglob("*")
            if path.is_file()
        ]
        self.assertIn(b"third-party", quarantined_bytes)

    def test_ambiguous_manifest_is_quarantined_before_previous_commit_is_restored(self):
        _, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        ambiguous_manifest = b'{"corrupt":true}\n'
        self.paths.manifest_path.write_bytes(ambiguous_manifest)

        report = recover_incomplete_transactions(self.paths)

        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        evidence = self.paths.quarantine_dir / (
            transaction.transaction_id + "-ambiguous-manifest.json"
        )
        self.assertTrue(evidence.is_file(), "ambiguous manifest evidence was not quarantined")
        self.assertEqual(evidence.read_bytes(), ambiguous_manifest)
        self.assertGreaterEqual(report.quarantined, 1)

    def test_unverified_promotion_never_touches_or_forgets_verified_authority(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "unverified")
        staged = self._stage(transaction, b"unverified")
        promote_output(transaction, staged, self._result("GENERATED_UNVERIFIED"))
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(self.paths.unverified_path.read_bytes(), b"unverified")
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "GENERATED_UNVERIFIED")
        self.assertEqual(
            manifest["authoritative_verified"],
            {
                "input_snapshot_id": old_manifest["input_snapshot_id"],
                "output_path": old_manifest["output_path"],
                "output_sha256": old_hash,
                "status": "PASS",
            },
        )

    def test_corrupt_journal_after_target_replace_restores_previous_final(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        journal = json.loads(transaction.journal_path.read_text(encoding="utf-8"))
        journal["target_kind"] = "forged"
        atomic_write_json(transaction.journal_path, journal)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(sha256_id(self.paths.verified_path.read_bytes()), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        self.assertEqual(report.quarantined, 1)

    def test_invalid_journal_without_public_manifest_never_manufactures_authority(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        journal = json.loads(transaction.journal_path.read_text(encoding="utf-8"))
        journal["state"] = "BROKEN"
        atomic_write_json(transaction.journal_path, journal)
        self.paths.manifest_path.unlink()

        report = recover_incomplete_transactions(self.paths)

        self.assertFalse(self.paths.verified_path.exists())
        self.assertFalse(self.paths.manifest_path.exists())
        self.assertFalse(transaction.directory.exists())
        self.assertGreaterEqual(report.quarantined, 1)
        self.assertTrue(report.failures)

    def test_corrupt_first_unverified_manifest_restores_previous_pass_authority(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "unverified")
        staged = self._stage(transaction, b"unverified")

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(
                transaction,
                staged,
                self._result("GENERATED_UNVERIFIED"),
                fault_injector=crash,
            )
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        manifest["kind"] = "corrupt"
        atomic_write_json(self.paths.manifest_path, manifest)
        ambiguous_manifest = self.paths.manifest_path.read_bytes()
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        self.assertFalse(self.paths.unverified_path.exists())
        evidence = self.paths.quarantine_dir / (
            transaction.transaction_id + "-ambiguous-manifest.json"
        )
        self.assertEqual(evidence.read_bytes(), ambiguous_manifest)
        self.assertEqual(report.quarantined, 2)

    def test_schema_valid_but_incoherent_backups_are_never_published(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        forged = b"forged-previous-target"
        atomic_write_bytes(transaction.directory / "previous-target.pptx", forged)
        journal = json.loads(transaction.journal_path.read_text(encoding="utf-8"))
        journal["previous_target_sha256"] = sha256_id(forged)
        atomic_write_json(transaction.journal_path, journal)
        report = recover_incomplete_transactions(self.paths)
        self.assertFalse(self.paths.verified_path.exists())
        self.assertFalse(self.paths.manifest_path.exists())
        self.assertGreaterEqual(report.quarantined, 1)
        self.assertTrue(report.failures)

    def test_corrupt_committed_manifest_does_not_authorize_new_target(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        manifest["kind"] = "forged_result"
        atomic_write_json(self.paths.manifest_path, manifest)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        restored_manifest = json.loads(
            self.paths.manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(restored_manifest["input_snapshot_id"], "sha256:" + "0" * 64)
        self.assertGreaterEqual(report.restored, 1)

    def test_duplicate_manifest_key_is_not_authoritative(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        text = self.paths.manifest_path.read_text(encoding="utf-8")
        text = text.replace(
            '  "kind": "ppt_editable_result",\n',
            '  "kind": "forged",\n  "kind": "ppt_editable_result",\n',
        )
        self.paths.manifest_path.write_text(text, encoding="utf-8")
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertGreaterEqual(report.restored, 1)

    def test_previous_manifest_target_mismatch_blocks_before_replacement(self):
        self._old_manifest(self.paths.verified_path)
        self.paths.verified_path.write_bytes(b"tampered-old")
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)
        with self.assertRaises(EditableError) as raised:
            promote_output(transaction, staged, self._result())
        self.assertEqual(raised.exception.code, "promotion_conflict")
        self.assertEqual(self.paths.verified_path.read_bytes(), b"tampered-old")

    def test_output_tree_rejects_reparse_parent_before_creating_children(self):
        run = Path(self.directory.name) / "unsafe-run"
        delivery = run / "delivery"
        delivery.mkdir(parents=True)
        real_lstat = atomic_io.os.lstat

        def reparse_delivery(path):
            value = real_lstat(path)
            if Path(path) == delivery:
                return SimpleNamespace(
                    st_mode=stat.S_IFDIR,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(atomic_io.os, "lstat", side_effect=reparse_delivery):
            with self.assertRaises(EditableError) as raised:
                build_output_paths(run, "unsafe-deck")
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertFalse((delivery / "editable").exists())

    def test_quarantine_file_revalidates_destination_parent_before_replace(self):
        source = self.paths.root / "ambiguous.bin"
        source.write_bytes(b"evidence")
        destination = self.paths.quarantine_dir / "ambiguous.bin"

        with mock.patch.object(
            atomic_io,
            "_ensure_safe_directory",
            side_effect=EditableError(
                "source_path_unsafe",
                "quarantine parent identity changed",
            ),
        ):
            with self.assertRaises(EditableError) as raised:
                atomic_io._quarantine_file(source, destination)
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertTrue(source.exists())
        self.assertFalse(destination.exists())

    def test_quarantine_directory_revalidates_destination_parent_before_replace(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")

        with mock.patch.object(
            atomic_io,
            "_ensure_safe_directory",
            side_effect=EditableError(
                "source_path_unsafe",
                "quarantine parent identity changed",
            ),
        ):
            with self.assertRaises(EditableError) as raised:
                atomic_io._move_directory_to_quarantine(
                    self.paths,
                    transaction.directory,
                    "-unsafe",
                )
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertTrue(transaction.directory.exists())

    def test_recovery_quarantines_forged_journal_identity(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_journal_prepared":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        journal = json.loads(transaction.journal_path.read_text(encoding="utf-8"))
        journal["target_kind"] = "forged"
        atomic_write_json(transaction.journal_path, journal)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(report.quarantined, 1)
        self.assertFalse(transaction.directory.exists())
        self.assertFalse(self.paths.verified_path.exists())
        self.assertFalse(self.paths.unverified_path.exists())

    def test_outer_lock_can_cover_begin_stage_and_promotion(self):
        with OutputLock(self.paths.lock_path) as output_lock:
            transaction = begin_promotion(
                self.paths,
                self.snapshot,
                "verified",
                output_lock=output_lock,
            )
            staged = self._stage(transaction)
            promote_output(
                transaction,
                staged,
                self._result(),
                output_lock=output_lock,
            )
        self.assertEqual(self.paths.verified_path.read_bytes(), b"new-pptx")

    def test_crash_after_target_rehash_restores_previous_verified_commit(self):
        old_hash, _ = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_target_verified":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(report.restored, 1)

    def test_recovery_quarantines_reparse_transaction_without_following(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        real_scandir = atomic_io.os.scandir

        class ReparseEntry:
            name = transaction.directory.name
            path = str(transaction.directory)

            def is_symlink(self):
                return False

            def stat(self, follow_symlinks=True):
                return SimpleNamespace(
                    st_mode=stat.S_IFDIR,
                    st_file_attributes=0x400,
                )

        class Scan:
            def __enter__(self):
                return iter((ReparseEntry(),))

            def __exit__(self, exc_type, exc, traceback):
                return False

        def controlled_scandir(path):
            if Path(path) == self.paths.tmp_dir:
                return Scan()
            return real_scandir(path)

        with mock.patch.object(atomic_io.os, "scandir", side_effect=controlled_scandir):
            report = recover_incomplete_transactions(self.paths)
        self.assertEqual(report.quarantined, 1)
        self.assertFalse(transaction.directory.exists())

    def test_boolean_journal_schema_is_quarantined(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_journal_prepared":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        journal = json.loads(transaction.journal_path.read_text(encoding="utf-8"))
        journal["schema_version"] = True
        atomic_write_json(transaction.journal_path, journal)
        report = recover_incomplete_transactions(self.paths)
        self.assertEqual(report.quarantined, 1)

    def test_promotion_revalidates_public_parent_immediately_before_replace(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)
        real_ensure_safe_directory = atomic_io._ensure_safe_directory
        public_parent_checks = 0

        def parent_becomes_unsafe(path):
            nonlocal public_parent_checks
            if Path(path) == self.paths.root:
                public_parent_checks += 1
                if public_parent_checks >= 2:
                    raise EditableError(
                        "source_path_unsafe",
                        "public output parent identity changed",
                    )
            return real_ensure_safe_directory(path)

        with mock.patch.object(
            atomic_io,
            "_ensure_safe_directory",
            side_effect=parent_becomes_unsafe,
        ):
            with self.assertRaises(EditableError) as raised:
                promote_output(transaction, staged, self._result())
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertGreaterEqual(public_parent_checks, 2)
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )

    def test_public_target_reparse_is_rejected_before_backup_or_replace(self):
        self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)
        real_lstat = atomic_io.os.lstat

        def target_reparse(path):
            value = real_lstat(path)
            if Path(path) == self.paths.verified_path:
                return SimpleNamespace(
                    st_mode=stat.S_IFREG,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(atomic_io.os, "lstat", side_effect=target_reparse):
            with self.assertRaises(EditableError) as raised:
                promote_output(transaction, staged, self._result())
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")

    def test_second_active_transaction_is_rejected(self):
        first = begin_promotion(self.paths, self.snapshot, "verified")
        with self.assertRaises(EditableError) as raised:
            begin_promotion(
                self.paths,
                "sha256:" + "b" * 64,
                "unverified",
            )
        self.assertEqual(raised.exception.code, "promotion_conflict")
        self.assertTrue(first.directory.exists())

    def test_staged_parent_reparse_is_rejected_before_hash_or_replace(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        nested = transaction.directory / "nested"
        nested.mkdir()
        staged = nested / "candidate.pptx"
        staged.write_bytes(b"candidate")
        real_lstat = atomic_io.os.lstat

        def reparse_parent(path):
            value = real_lstat(path)
            if Path(path) == nested:
                return SimpleNamespace(
                    st_mode=stat.S_IFDIR,
                    st_file_attributes=0x400,
                )
            return value

        with mock.patch.object(atomic_io.os, "lstat", side_effect=reparse_parent):
            with self.assertRaises(EditableError) as raised:
                promote_output(transaction, staged, self._result())
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertFalse(self.paths.verified_path.exists())

    def test_atomic_write_revalidates_parent_after_temp_close(self):
        target = self.paths.root / "parent-swap.bin"
        real_ensure_safe_directory = atomic_io._ensure_safe_directory
        checks = []

        def parent_becomes_unsafe(path):
            checks.append(Path(path))
            if len(checks) == 1:
                return real_ensure_safe_directory(path)
            raise EditableError("source_path_unsafe", "output parent identity changed")

        with mock.patch.object(
            atomic_io,
            "_ensure_safe_directory",
            side_effect=parent_becomes_unsafe,
        ):
            with self.assertRaises(EditableError) as raised:
                atomic_write_bytes(target, b"candidate")
        self.assertEqual(raised.exception.code, "source_path_unsafe")
        self.assertEqual(checks, [target.parent, target.parent])
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(".parent-swap.bin.*.tmp")), [])

    def test_fsync_failure_preserves_previous_pass_and_removes_temp(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        candidate = transaction.directory / "candidate.pptx"

        with mock.patch.object(
            atomic_io.os,
            "fsync",
            side_effect=OSError("fsync failed"),
        ):
            with self.assertRaises(EditableError) as raised:
                atomic_write_bytes(candidate, b"candidate")
        self.assertEqual(raised.exception.code, "candidate_write_failed")
        self.assertFalse(candidate.exists())
        self.assertEqual(list(candidate.parent.glob(".candidate.pptx.*.tmp")), [])
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )

    def test_atomic_replace_failure_leaves_no_public_or_temp_file(self):
        target = self.paths.root / "replace-failure.bin"
        with mock.patch.object(
            atomic_io.os,
            "replace",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(EditableError) as raised:
                atomic_write_bytes(target, b"candidate")
        self.assertEqual(raised.exception.code, "candidate_write_failed")
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(".replace-failure.bin.*.tmp")), [])

    def test_post_commit_cleanup_failure_does_not_change_commit_outcome(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)
        real_rmtree = atomic_io.shutil.rmtree

        def fail_transaction_cleanup(path, *args, **kwargs):
            if Path(path) == transaction.directory:
                raise OSError("cleanup failed")
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            atomic_io.shutil,
            "rmtree",
            side_effect=fail_transaction_cleanup,
        ):
            digest = promote_output(transaction, staged, self._result())
        self.assertEqual(digest, sha256_id(b"new-pptx"))
        self.assertEqual(self.paths.verified_path.read_bytes(), b"new-pptx")
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))["status"],
            "PASS",
        )
        self.assertTrue(transaction.directory.exists())

    def test_unverified_cleanup_failure_preserves_verified_authority(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "unverified")
        staged = self._stage(transaction, b"unverified")
        real_rmtree = atomic_io.shutil.rmtree

        def fail_transaction_cleanup(path, *args, **kwargs):
            if Path(path) == transaction.directory:
                raise OSError("cleanup failed")
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            atomic_io.shutil,
            "rmtree",
            side_effect=fail_transaction_cleanup,
        ):
            digest = promote_output(
                transaction,
                staged,
                self._result("GENERATED_UNVERIFIED"),
            )
        self.assertEqual(digest, sha256_id(b"unverified"))
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(self.paths.unverified_path.read_bytes(), b"unverified")
        manifest = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "GENERATED_UNVERIFIED")
        self.assertEqual(
            manifest["authoritative_verified"]["output_sha256"],
            old_manifest["output_sha256"],
        )
        self.assertTrue(transaction.directory.exists())

    def test_restore_failure_quarantines_public_state_and_preserves_retry_transaction(self):
        old_hash, old_manifest = self._old_manifest(self.paths.verified_path)
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        staged = self._stage(transaction)

        def crash(phase):
            if phase == "after_manifest_replaced":
                raise RuntimeError("crash")

        with self.assertRaises(RuntimeError):
            promote_output(transaction, staged, self._result(), fault_injector=crash)
        corrupt = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
        corrupt["kind"] = "corrupt"
        atomic_write_json(self.paths.manifest_path, corrupt)
        real_atomic_write = atomic_io.atomic_write_bytes

        def fail_manifest_restore(path, data):
            if Path(path) == self.paths.manifest_path:
                raise EditableError("candidate_write_failed", "transient restore failure")
            return real_atomic_write(path, data)

        with mock.patch.object(
            atomic_io,
            "atomic_write_bytes",
            side_effect=fail_manifest_restore,
        ):
            first = recover_incomplete_transactions(self.paths)
        self.assertTrue(first.failures)
        self.assertTrue(transaction.directory.exists())
        self.assertFalse(self.paths.verified_path.exists())
        self.assertFalse(self.paths.manifest_path.exists())

        second = recover_incomplete_transactions(self.paths)
        self.assertEqual(self.paths.verified_path.read_bytes(), b"old-pptx")
        self.assertEqual(_sha256_path(self.paths.verified_path), old_hash)
        self.assertEqual(
            json.loads(self.paths.manifest_path.read_text(encoding="utf-8")),
            old_manifest,
        )
        self.assertFalse(transaction.directory.exists())
        self.assertGreaterEqual(second.restored, 1)

    def test_staged_output_must_belong_to_transaction(self):
        transaction = begin_promotion(self.paths, self.snapshot, "verified")
        outside = self.paths.root / "outside.pptx"
        atomic_write_bytes(outside, b"outside")
        with self.assertRaises(EditableError) as raised:
            promote_output(transaction, outside, self._result())
        self.assertEqual(raised.exception.code, "promotion_conflict")


if __name__ == "__main__":
    unittest.main()
