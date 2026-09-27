"""Execute the documented Git repair in disposable, synthetic workspaces only."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "skills" / "ppt-start" / "references" / "visual-brief-and-generation.md"
GIT = shutil.which("git")
BASH = shutil.which("bash")


@unittest.skipUnless(GIT and BASH, "Git and Bash are required for the documented repair")
class GitHeadBootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="ppt-head-regression-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "presentation workspace"
        self.run = self.root / "ppt-output" / "example"
        self.run.mkdir(parents=True)
        self.env = dict(os.environ)
        for key in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(key, None)
        self.env.update(
            GIT_TERMINAL_PROMPT="0",
            PPT_PILOT_GIT_ROOT=self.root.as_posix(),
            PPT_PILOT_LAUNCH_ROOT=self.run.as_posix(),
        )

    def git(self, *args, cwd=None, check=True):
        result = subprocess.run(
            [GIT, "-C", str(cwd or self.root), *args],
            env=self.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def documented_steps(self):
        text = REFERENCE.read_text(encoding="utf-8")
        section = text.split("## Host-native generator boundary", 1)[1].split("## Candidate", 1)[0]
        steps = re.findall(r"```bash\n(.*?)\n```", section, re.DOTALL)
        self.assertTrue(steps, "The authoritative repair must include executable Git examples")
        # Exercise the old init-only recipe too: its obsolete placeholder must
        # point into this test, not be interpreted as shell input redirection.
        return [step.replace("<safe-local-root>", '"$PPT_PILOT_GIT_ROOT"') for step in steps]

    def run_documented_repair(self, check=True):
        for step in self.documented_steps():
            result = subprocess.run(
                [BASH, "--noprofile", "--norc", "-c", step],
                cwd=self.root, env=self.env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
            if result.returncode:
                if check:
                    self.fail(result.stdout + result.stderr)
                return result
        return result

    def assert_ready_empty_head(self):
        head = self.git("rev-parse", "--verify", "HEAD^{commit}", cwd=self.run).stdout.strip()
        self.assertRegex(head, r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
        self.assertEqual(self.git("ls-tree", "-r", "--name-only", "HEAD").stdout, "")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")
        self.assertEqual(self.git("remote").stdout, "")
        self.assertFalse((self.run / ".git").exists())
        top = self.git("rev-parse", "--show-toplevel", cwd=self.run).stdout.strip()
        self.assertEqual(Path(top).resolve(), self.root.resolve())
        return head

    def test_init_alone_reproduces_unborn_head(self):
        self.git("init", "--quiet")
        self.assertTrue(self.git("symbolic-ref", "HEAD").stdout.startswith("refs/heads/"))
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD^{commit}", check=False).returncode, 0)

    def test_documented_repair_provides_a_real_worktree_base(self):
        self.run_documented_repair()
        head = self.assert_ready_empty_head()
        checkout = self.root.parent / "host checkout"
        self.git("worktree", "add", "--detach", str(checkout), "HEAD")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=checkout).stdout.strip(), head)

    def test_recovers_old_init_only_workspace_without_changing_config(self):
        self.git("init", "--quiet")
        config = self.root / ".git" / "config"
        before = config.read_bytes()
        self.run_documented_repair()
        self.assert_ready_empty_head()
        self.assertEqual(config.read_bytes(), before)

    def test_initial_commit_excludes_staged_and_untracked_inputs(self):
        self.git("init", "--quiet")
        staged = self.run / "source.txt"
        prompt = self.run / "S32.md"
        staged.write_bytes(b"synthetic private source - not for Git")
        prompt.write_bytes(b"synthetic frozen prompt - not for Git")
        # Fixture setup only; the documented plugin repair must never stage.
        self.git("add", "--", staged.relative_to(self.root).as_posix())
        index_before = self.git("ls-files", "--stage", "-z").stdout
        status_before = self.git("status", "--porcelain=v1", "-z").stdout
        self.run_documented_repair()
        self.assert_ready_empty_head()
        self.assertEqual(self.git("ls-files", "--stage", "-z").stdout, index_before)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z").stdout, status_before)
        self.assertEqual(staged.read_bytes(), b"synthetic private source - not for Git")
        self.assertEqual(prompt.read_bytes(), b"synthetic frozen prompt - not for Git")
        checkout = self.root.parent / "staged host checkout"
        self.git("worktree", "add", "--detach", str(checkout), "HEAD")
        self.assertEqual([path.name for path in checkout.iterdir() if path.name != ".git"], [])

    def test_existing_head_is_reused_without_another_commit(self):
        self.run_documented_repair()
        head = self.assert_ready_empty_head()
        self.run_documented_repair()
        self.assertEqual(self.assert_ready_empty_head(), head)

    def test_unborn_head_with_existing_history_is_not_seeded(self):
        self.run_documented_repair()
        old_head = self.assert_ready_empty_head()
        branch = self.git("symbolic-ref", "HEAD").stdout.strip()
        self.git("symbolic-ref", "HEAD", "refs/heads/unborn-fixture")
        refs = self.git("show-ref").stdout
        result = self.run_documented_repair(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("show-ref").stdout, refs)
        self.assertEqual(self.git("rev-parse", "--verify", branch).stdout.strip(), old_head)

    def test_non_branch_head_is_not_repaired_as_a_new_repository(self):
        self.git("init", "--quiet")
        head_file = self.root / ".git" / "HEAD"
        head_file.write_bytes(b"ref: refs/tags/not-a-branch\n")
        result = self.run_documented_repair(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(head_file.read_bytes(), b"ref: refs/tags/not-a-branch\n")
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)").stdout, "")

    def test_commit_hook_failure_is_not_bypassed(self):
        self.git("init", "--quiet")
        hooks = Path(self.git("rev-parse", "--git-path", "hooks").stdout.strip())
        hooks = (self.root / hooks).resolve()
        if hooks != (self.root / ".git" / "hooks").resolve():
            self.skipTest("external user hooks directory is not a disposable fixture")
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nprintf 'fixture hook veto\\n' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        result = self.run_documented_repair(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fixture hook veto", result.stderr)
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD^{commit}", check=False).returncode, 0)

    def test_unborn_repository_with_a_remote_is_not_seeded(self):
        self.git("init", "--quiet")
        # Fixture metadata only; no network is contacted.
        self.git("remote", "add", "origin", "https://example.invalid/do-not-contact.git")
        result = self.run_documented_repair(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD^{commit}", check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
