"""Static contract tests for the optional companion tooling and the
batch-concurrency / hash-fallback / CJK-width / preference-profile contracts
introduced by the group-A speedup changes.

These tests only prove package structure and written contracts; they do not
prove real host behaviour, PowerPoint import, or rendering (see
docs/acceptance.md evidence classes).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


GOLDEN_ITEM_11_PREFIX = "11. Hash-capability fallback:"
GOLDEN_AUTHORITY = "generation-prompt-byte-grammar.md"
GOLDEN_FILES = (
    "redesign-prompt.md",
    "visual-brief-and-generation.md",
    "artifact-contract.md",
)


def _tree_digest(root: Path):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
    return len(files), digest.hexdigest()


def _filtered_tree_digest(root: Path):
    excluded_directories = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    excluded_suffixes = {".pyc", ".pyo"}
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not excluded_directories.intersection(path.relative_to(root).parts)
        and path.suffix.lower() not in excluded_suffixes
    )
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{relative}\0{path.stat().st_size}\0{content_hash}\n".encode())
    return len(files), digest.hexdigest()


class DeckDeliverToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tool_path = repo_root() / "tools" / "deck-deliver.ps1"

    def test_tool_exists_and_is_documented(self) -> None:
        self.assertTrue(self.tool_path.exists(), "tools/deck-deliver.ps1 must exist")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("deck-deliver.ps1", readme, "README must document the delivery tool")

    def test_tool_declares_parameters_and_outputs(self) -> None:
        tool = read_text(self.tool_path)
        for token in (
            "$RunDir",
            "$SkipPptx",
            "$ExportPng",
            "preview.html",
            "AddPicture",
            "audience_takeaway",
            "assertion_title",
            "delivery-result.json",
        ):
            self.assertIn(token, tool, f"deck-deliver.ps1 missing {token}")

    def test_deepseek_installer_exists_and_matches_marketplace_convention(self) -> None:
        installer_path = repo_root() / "tools" / "install-deepseek-plugin.ps1"
        self.assertTrue(installer_path.exists(), "tools/install-deepseek-plugin.ps1 must exist")
        installer = read_text(installer_path)
        for token in (
            "$MarketplaceRoot",
            "plugins\\ppt-pilot",
            ".codex-plugin\\plugin.json",
            "marketplace.json",
            "skills\\ppt-start",
            "skills\\ppt-editable",
            "$skills",
            "$filter",
        ):
            self.assertIn(token, installer, f"installer missing {token}")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("install-deepseek-plugin.ps1", readme, "README must document the installer")

    def test_tool_never_writes_into_skill_or_slides(self) -> None:
        tool = read_text(self.tool_path)
        # The tool's only persistent writes are preview.html and the delivery
        # manifest. Reading slides/ is expected; writing there is not.
        write_calls = [line for line in tool.splitlines() if "Write-Utf8File -Path" in line]
        self.assertEqual(len(write_calls), 2)
        self.assertTrue(any("$previewPath" in line for line in write_calls))
        self.assertTrue(any("$resultPath" in line for line in write_calls))
        for line in tool.splitlines():
            if "slides" in line.lower():
                self.assertNotRegex(line, r"Set-Content|Out-File|WriteAllText")


class MultiSkillInstallerTests(unittest.TestCase):
    def setUp(self):
        self.update_path = repo_root() / "tools" / "update-hosts.ps1"
        self.deepseek_path = repo_root() / "tools" / "install-deepseek-plugin.ps1"

    def test_installers_are_descriptor_driven_for_both_skills(self):
        update = read_text(self.update_path)
        deepseek = read_text(self.deepseek_path)
        packaging = read_text(repo_root() / "tools" / "packaging.ps1")
        for source in (update, deepseek):
            for token in (
                "ppt-start",
                "ppt-editable",
                "$skills",
            ):
                with self.subTest(source=source[:20], token=token):
                    self.assertIn(token, source)
            self.assertNotIn("Get-FileHash", source)
        for token in ("$ClaudeAgentsRoot", "ppt-svg-generator.md", "agent-backups"):
            self.assertIn(token, update)
            self.assertNotIn(token, deepseek)
        for token in ("Get-PptPilotTreeInfo", "Get-PptPilotFileSha256", "Copy-PptPilotFilteredTree"):
            self.assertIn(token, packaging)
        self.assertIn("Join-Path (Split-Path -Parent $ClaudeSkillsRoot) 'agents'", update)
        self.assertIn("Join-Path $project '.claude\\agents'", update)
        self.assertIn("skill-backups", update)
        self.assertIn("'backups'", deepseek)
        self.assertIn("$arguments = @{ RepoRoot = $RepoRoot }", update)
        self.assertIn("skills      = './skills/'", deepseek)
        self.assertIn("ppt-editable：", deepseek)
        self.assertIn("$marketplaceAttemptBackup", deepseek)
        self.assertRegex(
            deepseek,
            r"(?s)marketplacePath\.bak-\$timestamp.*?Test-Path.*?guid.*?marketplaceAttemptBackup",
        )
        self.assertIn("New session required", update)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_update_hosts_filters_cache_and_refreshes_existing_project_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_repo = root / "source"
            for relative in ("skills", "hosts", "tools"):
                shutil.copytree(repo_root() / relative, source_repo / relative)
            cache = source_repo / "skills" / "ppt-start" / "scripts" / "__pycache__"
            cache.mkdir(exist_ok=True)
            (cache / "runtime.cpython-313.pyc").write_bytes(b"bytecode")
            (source_repo / "skills" / "ppt-start" / ".pytest_cache").mkdir(exist_ok=True)
            project = root / "project"
            for scope in (project / ".agents" / "skills", project / ".claude" / "skills"):
                (scope / "ppt-start").mkdir(parents=True)
                (scope / "ppt-start" / "stale.txt").write_text("stale", encoding="utf-8")
            command = [
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(source_repo / "tools" / "update-hosts.ps1"),
                "-RepoRoot", str(source_repo), "-SkipDeepSeek", "-SkipClaudeCode",
                "-SkipCodex", "-ProjectRoot", str(project),
            ]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            expected = _filtered_tree_digest(source_repo / "skills" / "ppt-start")
            for installed in (
                project / ".agents" / "skills" / "ppt-start",
                project / ".claude" / "skills" / "ppt-start",
            ):
                self.assertEqual(_filtered_tree_digest(installed), expected)
                self.assertFalse((installed / "scripts" / "__pycache__").exists())
            self.assertTrue((project / ".claude" / "agents" / "ppt-svg-generator.md").is_file())

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_repo_root_existing_scopes_refresh_without_legacy_project_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            source_repo = Path(directory) / "source"
            for relative in ("skills", "hosts", "tools"):
                shutil.copytree(repo_root() / relative, source_repo / relative)
            for scope in (source_repo / ".agents" / "skills", source_repo / ".claude" / "skills"):
                (scope / "ppt-start").mkdir(parents=True)
                (scope / "ppt-start" / "stale.txt").write_text("stale", encoding="utf-8")
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(source_repo / "tools" / "update-hosts.ps1"),
                "-RepoRoot", str(source_repo), "-SkipDeepSeek", "-SkipClaudeCode", "-SkipCodex",
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            for installed in (
                source_repo / ".agents" / "skills" / "ppt-start",
                source_repo / ".claude" / "skills" / "ppt-start",
            ):
                self.assertEqual(
                    _filtered_tree_digest(installed),
                    _filtered_tree_digest(source_repo / "skills" / "ppt-start"),
                )
            self.assertTrue((source_repo / ".claude" / "agents" / "ppt-svg-generator.md").is_file())

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_explicit_codex_plugin_root_updates_only_skills_and_preserves_unrelated_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugin"
            (plugin / "skills" / "ppt-start").mkdir(parents=True)
            (plugin / "skills" / "ppt-start" / "stale.txt").write_text("stale", encoding="utf-8")
            (plugin / ".git").mkdir()
            (plugin / "docs").mkdir()
            (plugin / "docs" / "keep.txt").write_text("keep", encoding="utf-8")
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.update_path), "-RepoRoot", str(repo_root()),
                "-SkipDeepSeek", "-SkipClaudeCode", "-SkipCodex", "-SkipRepoProject",
                "-CodexPluginRoot", str(plugin),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertTrue((plugin / ".git").is_dir())
            self.assertEqual((plugin / "docs" / "keep.txt").read_text(), "keep")
            self.assertEqual(
                _filtered_tree_digest(plugin / "skills" / "ppt-start"),
                _filtered_tree_digest(skill_root()),
            )

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_mixed_destination_failure_is_nonzero_partial_failure_and_rolls_back_failed_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good" / "skills"
            bad_parent = root / "bad"
            bad_parent.write_text("not a directory", encoding="utf-8")
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.update_path), "-RepoRoot", str(repo_root()),
                "-SkipDeepSeek", "-SkipClaudeCode", "-SkipRepoProject", "-CodexSkillsRoot", str(good),
                "-ProjectRoot", str(bad_parent),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            output = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, output)
            self.assertIn("PARTIAL_FAILURE", output)
            self.assertIn("updated", output)
            self.assertIn("failed", output)
            self.assertNotIn("全部完成", output)
            self.assertTrue((good / "ppt-start" / "SKILL.md").is_file())

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_backup_preparation_failure_is_failed_but_not_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "host" / "skills"
            destination = skills / "ppt-start"
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_text("stale", encoding="utf-8")
            (root / "host" / "skill-backups").write_text("not a directory", encoding="utf-8")
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.update_path), "-RepoRoot", str(repo_root()),
                "-SkipRepoProject", "-SkipDeepSeek", "-SkipClaudeCode",
                "-CodexSkillsRoot", str(skills),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            output = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, output)
            self.assertIn(str(destination), output)
            rolled_back = next(line for line in output.splitlines() if line.startswith("rolled_back:"))
            self.assertNotIn(str(destination), rolled_back)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_project_claude_scope_restores_agent_when_later_skill_copy_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            skills = project / ".claude" / "skills"
            agent = project / ".claude" / "agents" / "ppt-svg-generator.md"
            agent.parent.mkdir(parents=True)
            agent.write_bytes(b"old-agent\n")
            for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract"):
                target = skills / skill_id
                target.mkdir(parents=True)
                (target / "SKILL.md").write_text("stale " + skill_id, encoding="utf-8")
            before = agent.read_bytes()
            before_skills = {
                skill_id: (skills / skill_id / "SKILL.md").read_bytes()
                for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract")
            }
            self.assertNotEqual(
                before,
                (repo_root() / "hosts" / "claude-code" / "agents" / "ppt-svg-generator.md").read_bytes(),
            )
            (project / ".claude" / "skill-backups").write_text("not a directory", encoding="utf-8")
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.update_path), "-RepoRoot", str(repo_root()),
                "-SkipRepoProject", "-SkipDeepSeek", "-SkipClaudeCode", "-SkipCodex",
                "-ProjectRoot", str(project),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(agent.read_bytes(), before)
            for skill_id, original in before_skills.items():
                self.assertEqual((skills / skill_id / "SKILL.md").read_bytes(), original)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_direct_child_shadowing_skill_fails_and_names_path_before_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "skills"
            live = skills / "ppt-start"
            shadow = skills / "ppt-start.bak-legacy"
            for target in (live, shadow):
                target.mkdir(parents=True)
                (target / "SKILL.md").write_text("---\nname: ppt-start\n---\n", encoding="utf-8")
            before = (live / "SKILL.md").read_bytes()
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.update_path), "-RepoRoot", str(repo_root()),
                "-SkipRepoProject", "-SkipDeepSeek", "-SkipClaudeCode",
                "-CodexSkillsRoot", str(skills),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            output = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, output)
            self.assertIn(str(shadow), output)
            self.assertEqual((live / "SKILL.md").read_bytes(), before)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_final_claude_snapshot_failure_after_deepseek_success_reports_and_cleans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("skills", "hosts", "tools"):
                shutil.copytree(repo_root() / relative, source / relative)
            claude = root / "claude"
            agent = claude / "agents" / "ppt-svg-generator.md"
            agent.parent.mkdir(parents=True)
            agent.write_bytes(b"prior-agent")
            for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract"):
                skill = claude / "skills" / skill_id
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_bytes(b"prior-skill")
            before = {str(p.relative_to(claude)): p.read_bytes() for p in claude.rglob('*') if p.is_file()}
            updater = source / "tools" / "update-hosts.ps1"
            script = read_text(updater)
            copy = "Copy-Item -LiteralPath $target.Path -Destination $target.Snapshot -Recurse -Force"
            self.assertIn(copy, script)
            # Fail after one partial snapshot copy; the previous agent snapshot also exists.
            updater.write_text(script.replace(copy, copy + "; throw 'injected snapshot copy failure'", 1), encoding="utf-8")
            temporary = root / "temporary"
            temporary.mkdir()
            marketplace = root / "marketplace"
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(updater), "-RepoRoot", str(source), "-SkipCodex", "-SkipRepoProject",
                "-MarketplaceRoot", str(marketplace), "-ClaudeSkillsRoot", str(claude / "skills"),
                "-ClaudeAgentsRoot", str(agent.parent),
            ], env=dict(os.environ, TEMP=str(temporary), TMP=str(temporary)),
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            output = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, output)
            self.assertIn("PARTIAL_FAILURE", output)
            updated = next(line for line in output.splitlines() if line.startswith("updated:"))
            failed = next(line for line in output.splitlines() if line.startswith("failed:"))
            restored = next(line for line in output.splitlines() if line.startswith("rolled_back:"))
            self.assertIn("deepseek-plugin", updated)
            self.assertIn(str(claude / "skills"), failed)
            self.assertIn("injected snapshot copy failure", failed)
            self.assertNotIn(str(claude), updated)
            self.assertNotIn(str(claude), restored)
            self.assertEqual({str(p.relative_to(claude)): p.read_bytes() for p in claude.rglob('*') if p.is_file()}, before)
            self.assertFalse(list(temporary.glob("ppt-claude-scope-*")))
            self.assertEqual(_filtered_tree_digest(marketplace / "plugins/ppt-pilot/skills/ppt-start"),
                             _filtered_tree_digest(source / "skills/ppt-start"))

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_final_deepseek_shadow_fails_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace"
            plugin = marketplace / "plugins/ppt-pilot"
            shadow = plugin / "skills/legacy-ppt"
            shadow.mkdir(parents=True)
            (shadow / "SKILL.md").write_text("---\nname: ppt-start\n---\n", encoding="utf-8")
            for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract"):
                live = plugin / "skills" / skill_id
                live.mkdir()
                (live / "SKILL.md").write_bytes(b"prior-live")
            (marketplace / "marketplace.json").write_bytes(b'{"name":"personal","plugins":[]}')
            before = {str(p.relative_to(marketplace)): p.read_bytes() if p.is_file() else None
                      for p in marketplace.rglob('*')}
            completed = subprocess.run([
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(self.deepseek_path), "-RepoRoot", str(repo_root()),
                "-MarketplaceRoot", str(marketplace),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            output = completed.stdout + completed.stderr
            self.assertNotEqual(completed.returncode, 0, output)
            self.assertIn(str(shadow), output)
            self.assertEqual({str(p.relative_to(marketplace)): p.read_bytes() if p.is_file() else None
                              for p in marketplace.rglob('*')}, before)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_update_hosts_copies_and_verifies_both_skill_trees_with_per_id_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_skills = root / "claude" / "skills"
            claude_agents = root / "claude" / "agents"
            codex_skills = root / "codex" / "skills"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipRepoProject",
                "-SkipDeepSeek",
                "-ClaudeSkillsRoot",
                str(claude_skills),
                "-ClaudeAgentsRoot",
                str(claude_agents),
                "-CodexSkillsRoot",
                str(codex_skills),
            ]
            for _ in range(2):
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            for skills_root in (claude_skills, codex_skills):
                for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract"):
                    source = repo_root() / "skills" / skill_id
                    installed = skills_root / skill_id
                    self.assertTrue((installed / "SKILL.md").is_file())
                    self.assertEqual(
                        _filtered_tree_digest(installed), _filtered_tree_digest(source)
                    )
                    backups = list(
                        (skills_root.parent / "skill-backups").glob(skill_id + ".bak-*")
                    )
                    self.assertEqual(len(backups), 1)
                self.assertFalse(any(skills_root.glob("*.bak-*")))

            source_agent = (
                repo_root()
                / "hosts"
                / "claude-code"
                / "agents"
                / "ppt-svg-generator.md"
            )
            installed_agent = claude_agents / "ppt-svg-generator.md"
            self.assertEqual(installed_agent.read_bytes(), source_agent.read_bytes())
            self.assertEqual(
                len(
                    list(
                        (claude_agents.parent / "agent-backups").glob(
                            "ppt-svg-generator.bak-*.md"
                        )
                    )
                ),
                1,
            )
            self.assertFalse(any(claude_agents.glob("*.bak-*")))
            self.assertFalse(
                (codex_skills.parent / "agents" / "ppt-svg-generator.md").exists()
            )

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_backup_preparation_failure_never_deletes_live_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_skills = root / "claude" / "skills"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipRepoProject",
                "-SkipDeepSeek",
                "-SkipCodex",
                "-ClaudeSkillsRoot",
                str(claude_skills),
            ]
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            before = {
                skill_id: _tree_digest(claude_skills / skill_id)
                for skill_id in ("ppt-start", "ppt-editable")
            }
            backup_root = claude_skills.parent / "skill-backups"
            backup_root.write_text("not a directory", encoding="utf-8")
            second = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(second.returncode, 0)
            for skill_id, digest in before.items():
                self.assertEqual(_tree_digest(claude_skills / skill_id), digest)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_claude_agent_backup_failure_leaves_agent_and_skills_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_root = root / "claude"
            claude_skills = claude_root / "skills"
            claude_agents = claude_root / "agents"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipRepoProject",
                "-SkipDeepSeek",
                "-SkipCodex",
                "-ClaudeSkillsRoot",
                str(claude_skills),
                "-ClaudeAgentsRoot",
                str(claude_agents),
            ]
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            live_agent = claude_agents / "ppt-svg-generator.md"
            live_agent.write_bytes(b"old-live-agent-sentinel\n")
            (claude_skills / "ppt-start" / "old-live-sentinel.txt").write_text(
                "preserve me\n", encoding="utf-8"
            )
            before_agent = live_agent.read_bytes()
            before_skills = {
                skill_id: _tree_digest(claude_skills / skill_id)
                for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract")
            }
            backup_root = claude_root / "agent-backups"
            backup_root.write_text("not a directory", encoding="utf-8")

            second = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(
                (claude_agents / "ppt-svg-generator.md").read_bytes(), before_agent
            )
            for skill_id, digest in before_skills.items():
                self.assertEqual(_tree_digest(claude_skills / skill_id), digest)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_claude_agent_post_copy_failure_restores_live_agent_and_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_root = root / "claude"
            claude_skills = claude_root / "skills"
            claude_agents = claude_root / "agents"
            base_command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipRepoProject",
                "-SkipDeepSeek",
                "-SkipCodex",
                "-ClaudeSkillsRoot",
                str(claude_skills),
                "-ClaudeAgentsRoot",
                str(claude_agents),
            ]
            first = subprocess.run(
                base_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            live_agent = claude_agents / "ppt-svg-generator.md"
            live_agent.write_bytes(b"old-live-agent-sentinel\n")
            (claude_skills / "ppt-start" / "old-live-sentinel.txt").write_text(
                "preserve me\n", encoding="utf-8"
            )
            before_agent = live_agent.read_bytes()
            before_skills = {
                skill_id: _tree_digest(claude_skills / skill_id)
                for skill_id in ("ppt-start", "ppt-editable", "ppt-style-extract")
            }

            installer_text = read_text(self.update_path)
            copy_line = (
                "        $newCopied = $true\n"
                "        Copy-Item -LiteralPath $agentSource -Destination $destination -Force\n"
            )
            self.assertEqual(installer_text.count(copy_line), 1)
            injected_installer = root / "update-hosts-agent-failure.ps1"
            injected_installer.write_text(
                installer_text.replace(
                    copy_line,
                    copy_line + "        throw 'injected agent verification failure'\n",
                    1,
                ),
                encoding="utf-8",
            )
            shutil.copy2(repo_root() / "tools" / "packaging.ps1", root / "packaging.ps1")
            failed_command = list(base_command)
            failed_command[failed_command.index(str(self.update_path))] = str(
                injected_installer
            )
            failed = subprocess.run(
                failed_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(
                "injected agent verification failure", failed.stderr + failed.stdout
            )
            self.assertEqual(
                (claude_agents / "ppt-svg-generator.md").read_bytes(), before_agent
            )
            self.assertEqual(
                list(
                    (claude_root / "agent-backups").glob(
                        "ppt-svg-generator.bak-*.md"
                    )
                ),
                [],
            )
            for skill_id, digest in before_skills.items():
                self.assertEqual(_tree_digest(claude_skills / skill_id), digest)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_keeps_one_plugin_and_both_skills_outside_backup_scan_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.deepseek_path),
                "-RepoRoot",
                str(repo_root()),
                "-MarketplaceRoot",
                str(marketplace),
                "-Version",
                "1.0.0-test",
            ]
            marketplace.mkdir(parents=True)
            (marketplace / "marketplace.json").write_text(
                json.dumps({"name": "personal", "plugins": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            market_path = marketplace / "marketplace.json"
            normalized = json.loads(market_path.read_text(encoding="utf-8-sig"))
            normalized["plugins"] = normalized["plugins"] * 2
            market_path.write_text(json.dumps(normalized), encoding="utf-8")
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            plugin = marketplace / "plugins" / "ppt-pilot"
            manifest = json.loads(
                (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8-sig")
            )
            self.assertEqual(manifest["name"], "ppt-pilot")
            self.assertEqual(manifest["skills"], "./skills/")
            for skill_id in ("ppt-start", "ppt-editable"):
                source = repo_root() / "skills" / skill_id
                installed = plugin / "skills" / skill_id
                self.assertEqual(
                    _filtered_tree_digest(installed), _filtered_tree_digest(source)
                )
                self.assertEqual(
                    len(list((plugin / "backups").glob(skill_id + ".bak-*"))),
                    1,
                )
            self.assertFalse(any((plugin / "skills").glob("*.bak-*")))
            market = json.loads((marketplace / "marketplace.json").read_text(encoding="utf-8-sig"))
            self.assertEqual([entry["name"] for entry in market["plugins"]], ["ppt-pilot"])
    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_installer_never_changes_host_profile(self):
        for legacy_flag in (False, True):
            with self.subTest(legacy_flag=legacy_flag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                marketplace = root / "marketplace"
                marketplace.mkdir()
                market = marketplace / "marketplace.json"
                market.write_text(json.dumps({"name": "personal", "plugins": []}), encoding="utf-8")
                original_market = market.read_bytes()
                profile = root / "host" / "profiles" / "web"
                profile.mkdir(parents=True)
                patch = profile / "cordis.patch.yml"
                patch.write_bytes(b"# keep user settings\r\n[]\r\n")
                original_patch = patch.read_bytes()
                command = [shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(self.deepseek_path), "-RepoRoot", str(repo_root()),
                    "-MarketplaceRoot", str(marketplace)]
                if legacy_flag:
                    command += ["-DshWebProfileRoot", str(profile)]
                completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120, check=False,
                    env=dict(os.environ, DSH_HOME=str(root / "host")))
                self.assertEqual(patch.read_bytes(), original_patch)
                if legacy_flag:
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertEqual(market.read_bytes(), original_market)
                    self.assertFalse((marketplace / "plugins").exists())
                else:
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    self.assertTrue((marketplace / "plugins/ppt-pilot/skills/ppt-start/SKILL.md").is_file())

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_post_copy_failure_restores_live_plugin_and_marketplace(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace"
            marketplace.mkdir(parents=True)
            market_path = marketplace / "marketplace.json"
            market_path.write_text(
                json.dumps({"name": "personal", "plugins": []}),
                encoding="utf-8",
            )
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.deepseek_path),
                "-RepoRoot",
                str(repo_root()),
                "-MarketplaceRoot",
                str(marketplace),
                "-Version",
                "1.0.0-before",
            ]
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            plugin = marketplace / "plugins" / "ppt-pilot"
            before_skills = {
                skill_id: _tree_digest(plugin / "skills" / skill_id)
                for skill_id in ("ppt-start", "ppt-editable")
            }
            manifest_path = plugin / ".codex-plugin" / "plugin.json"
            before_manifest = manifest_path.read_bytes()

            broken_marketplace = b'{"name":"personal","plugins":['
            market_path.write_bytes(broken_marketplace)
            failed_command = list(command)
            failed_command[-1] = "2.0.0-should-rollback"
            failed = subprocess.run(
                failed_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            for skill_id, digest in before_skills.items():
                self.assertEqual(_tree_digest(plugin / "skills" / skill_id), digest)
            self.assertEqual(manifest_path.read_bytes(), before_manifest)
            self.assertEqual(market_path.read_bytes(), broken_marketplace)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_staged_copy_failure_preserves_live_skill_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("skills", "tools"):
                shutil.copytree(repo_root() / relative, source / relative)
            marketplace = root / "marketplace"
            marketplace.mkdir()
            (marketplace / "marketplace.json").write_text(
                json.dumps({"name": "personal", "plugins": []}), encoding="utf-8"
            )
            command = [
                shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(source / "tools" / "install-deepseek-plugin.ps1"),
                "-RepoRoot", str(source), "-MarketplaceRoot", str(marketplace),
            ]
            first = subprocess.run(command, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            live = marketplace / "plugins" / "ppt-pilot" / "skills" / "ppt-start"
            before = _filtered_tree_digest(live)
            helper = source / "tools" / "packaging.ps1"
            helper_text = read_text(helper)
            marker = "        Copy-PptPilotFilteredTree $Source $stage\n"
            self.assertIn(marker, helper_text)
            helper.write_text(
                helper_text.replace(marker, marker + "        throw 'injected staged copy failure'\n", 1),
                encoding="utf-8",
            )
            failed = subprocess.run(command, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("injected staged copy failure", failed.stdout + failed.stderr)
            self.assertEqual(_filtered_tree_digest(live), before)


@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
class SharedSkillInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.source = self.root / "source"
        self.marketplace = self.home / ".agents" / "plugins"
        self.shared = self.home / ".agents" / "skills"
        self.skill_ids = ("ppt-start", "ppt-editable", "ppt-style-extract")
        for skill_id in self.skill_ids:
            skill = self.source / "skills" / skill_id
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {skill_id}\n---\nCurrent portable Skill 中文\n", encoding="utf-8"
            )
        registry = self.source / "skills/ppt-start/assets/host-adapters.json"
        registry.parent.mkdir()
        shutil.copy2(skill_root() / "assets/host-adapters.json", registry)
        agent = self.source / "hosts/claude-code/agents/ppt-svg-generator.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("fixture agent\n", encoding="utf-8")
        (self.source / "tools").mkdir()
        for name in ("install-deepseek-plugin.ps1", "update-hosts.ps1", "packaging.ps1"):
            shutil.copy2(repo_root() / "tools" / name, self.source / "tools" / name)

    def run_tool(self, name, *arguments):
        return subprocess.run([
            shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(self.source / "tools" / name), "-RepoRoot", str(self.source),
            *map(str, arguments),
        ], env=dict(os.environ, USERPROFILE=str(self.home)), cwd=self.root,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, check=False)

    def seed_shared(self, skills_root=None):
        skills_root = skills_root or self.shared
        for skill_id in self.skill_ids:
            skill = skills_root / skill_id
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {skill_id}\n---\nOld Claude-only Skill\n", encoding="utf-8"
            )
        registry = skills_root / "ppt-start/assets/host-adapters.json"
        registry.parent.mkdir()
        registry.write_text('{"schema_version":1,"adapters":[{"host":"claude-code"}]}', encoding="utf-8")
        return {skill_id: _tree_digest(skills_root / skill_id) for skill_id in self.skill_ids}

    def test_standalone_refreshes_existing_shared_registry_and_preserves_prior_version(self):
        before = self.seed_shared()
        unrelated = self.shared / "unrelated" / "SKILL.md"
        unrelated.parent.mkdir()
        unrelated.write_bytes(b"---\nname: unrelated\n---\nkeep me\n")
        completed = self.run_tool("install-deepseek-plugin.ps1", "-Version", "test-shared")
        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        source_registry = self.source / "skills/ppt-start/assets/host-adapters.json"
        self.assertIn(b"deepseek-harness", source_registry.read_bytes())
        plugin = self.marketplace / "plugins/ppt-pilot"
        self.assertEqual((plugin / "skills/ppt-start/assets/host-adapters.json").read_bytes(), source_registry.read_bytes())
        self.assertEqual((self.shared / "ppt-start/assets/host-adapters.json").read_bytes(), source_registry.read_bytes())
        for skill_id in self.skill_ids:
            self.assertEqual(_tree_digest(self.shared / skill_id), _tree_digest(self.source / "skills" / skill_id))
            backups = list((self.shared.parent / "skill-backups").glob(skill_id + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(_tree_digest(backups[0]), before[skill_id])
        self.assertEqual(unrelated.read_bytes(), b"---\nname: unrelated\n---\nkeep me\n")
        self.assertFalse(list(self.shared.glob("*.bak-*")))
        self.assertIn("scope=shared-user", output)

    def test_standalone_shared_alias_blocks_before_any_scope_mutation(self):
        self.seed_shared()
        alias = self.shared / "old-ppt-alias" / "SKILL.md"
        alias.parent.mkdir()
        alias.write_text("---\nname: ppt-start\n---\n", encoding="utf-8")
        before = _tree_digest(self.home)
        completed = self.run_tool("install-deepseek-plugin.ps1")
        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0, output)
        self.assertIn(str(alias.parent), output)
        self.assertIn("shadowing", output)
        self.assertEqual(_tree_digest(self.home), before)
        self.assertFalse(self.marketplace.exists())

    def test_standalone_shared_alias_recognizes_quoted_and_commented_name_scalars(self):
        for index, scalar in enumerate(('"ppt-start"', "'ppt-start'", "ppt-editable # old alias",
                                       '"ppt-style-extract" # old alias')):
            with self.subTest(scalar=scalar):
                custom = self.root / f"scalar-{index}"
                shared = custom / "skills"
                self.seed_shared(shared)
                alias = shared / "legacy-alias/SKILL.md"
                alias.parent.mkdir()
                alias.write_text(f"---\nname: {scalar}\n---\n", encoding="utf-8-sig")
                before = _tree_digest(custom)
                completed = self.run_tool("install-deepseek-plugin.ps1", "-MarketplaceRoot", custom / "plugins")
                output = completed.stdout + completed.stderr
                self.assertNotEqual(completed.returncode, 0, output)
                self.assertIn(str(alias.parent), output)
                self.assertEqual(_tree_digest(custom), before)
                self.assertFalse((custom / "plugins").exists())

    def test_standalone_shared_alias_ignores_names_outside_real_frontmatter(self):
        documents = (
            "---\nname: unrelated\n---\n```yaml\nname: ppt-start\n```\n",
            "---\nname: unrelated\n...\nname: ppt-start\n",
            "# Example, not frontmatter\n---\nname: ppt-start\n---\n",
            "---\nname: ppt-start\n",  # No closing frontmatter delimiter.
            "---\nname: unrelated\nmetadata:\n  name: ppt-start\n---\n",
            "---\nname: ppt-start#different-scalar\n---\n",
        )
        for index, document in enumerate(documents):
            with self.subTest(document=document):
                custom = self.root / f"body-{index}"
                shared = custom / "skills"
                unrelated = shared / "unrelated/SKILL.md"
                unrelated.parent.mkdir(parents=True)
                unrelated.write_text(document, encoding="utf-8")
                before = _tree_digest(shared)
                completed = self.run_tool("install-deepseek-plugin.ps1", "-MarketplaceRoot", custom / "plugins")
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertEqual(_tree_digest(shared), before)
                self.assertTrue((custom / "plugins/plugins/ppt-pilot/skills/ppt-start/SKILL.md").is_file())

    def test_standalone_shared_failure_reports_plugin_success_and_restores_failed_tree(self):
        before = self.seed_shared()
        failed_skill = self.shared / "ppt-editable"
        previous = self.shared.parent / "skill-backups/ppt-editable.bak-older"
        previous.mkdir(parents=True)
        (previous / "SKILL.md").write_bytes(b"older backup\n")
        previous_digest = _tree_digest(previous)
        helper = self.source / "tools/packaging.ps1"
        text = read_text(helper)
        marker = "        $installedInfo = Get-PptPilotTreeInfo $Destination\n"
        self.assertEqual(text.count(marker), 1)
        helper.write_text(text.replace(marker, marker +
            f"        if ($Destination -eq '{failed_skill}') {{ throw 'injected shared verification failure' }}\n"), encoding="utf-8")
        completed = self.run_tool("install-deepseek-plugin.ps1")
        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0, output)
        self.assertIn("PARTIAL_FAILURE", output)
        updated = next(line for line in output.splitlines() if line.startswith("updated:"))
        failed = next(line for line in output.splitlines() if line.startswith("failed:"))
        restored = next(line for line in output.splitlines() if line.startswith("rolled_back:"))
        plugin = self.marketplace / "plugins/ppt-pilot"
        self.assertIn(str(plugin), updated)
        self.assertIn(str(failed_skill), failed)
        self.assertIn("injected shared verification failure", failed)
        self.assertIn(str(failed_skill), restored)
        self.assertNotIn(str(failed_skill), updated)
        self.assertNotIn(str(plugin), restored)
        self.assertEqual(_tree_digest(failed_skill), before["ppt-editable"])
        self.assertEqual(_tree_digest(previous), previous_digest)
        self.assertEqual(list(previous.parent.glob("ppt-editable.bak-*")), [previous])
        for skill_id in ("ppt-start", "ppt-style-extract"):
            self.assertIn(str(self.shared / skill_id), updated)
            self.assertEqual(_tree_digest(self.shared / skill_id), _tree_digest(self.source / "skills" / skill_id))
        for skill_id in self.skill_ids:
            self.assertEqual(_tree_digest(plugin / "skills" / skill_id), _tree_digest(self.source / "skills" / skill_id))
        self.assertFalse((self.shared.parent / ".ppt-pilot-install-staging").exists())

    def test_standalone_plugin_failure_leaves_shared_scope_untouched(self):
        self.seed_shared()
        before = _tree_digest(self.shared)
        self.marketplace.mkdir()
        market = self.marketplace / "marketplace.json"
        market.write_bytes(b'{"plugins":[')
        completed = self.run_tool("install-deepseek-plugin.ps1")
        self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(_tree_digest(self.shared), before)
        self.assertEqual(market.read_bytes(), b'{"plugins":[')
        self.assertFalse((self.marketplace / "plugins/ppt-pilot").exists())
        self.assertFalse((self.shared.parent / "skill-backups").exists())

    def test_updater_installs_shared_skills_once_and_keeps_original_backup(self):
        before = self.seed_shared()
        completed = self.run_tool("update-hosts.ps1", "-SkipClaudeCode", "-SkipRepoProject")
        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        for skill_id in self.skill_ids:
            installed = self.shared / skill_id
            self.assertEqual(_tree_digest(installed), _tree_digest(self.source / "skills" / skill_id))
            backups = list((self.shared.parent / "skill-backups").glob(skill_id + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(_tree_digest(backups[0]), before[skill_id])
            self.assertEqual(output.count(f"path={installed} "), 1)

    def test_updater_overlapping_selected_project_keeps_original_shared_backup(self):
        before = self.seed_shared()
        completed = self.run_tool("update-hosts.ps1", "-SkipClaudeCode", "-SkipRepoProject",
            "-ProjectRoot", self.home)
        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, output)
        for skill_id in self.skill_ids:
            backups = list((self.shared.parent / "skill-backups").glob(skill_id + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(_tree_digest(backups[0]), before[skill_id])
            self.assertEqual(output.count(f"path={self.shared / skill_id} "), 1)

    def test_standalone_override_refreshes_only_custom_sibling_not_userprofile(self):
        self.seed_shared()
        custom = self.root / "custom"
        custom_shared = custom / "skills"
        self.seed_shared(custom_shared)
        before_home = _tree_digest(self.home)
        before_source = _tree_digest(self.source)
        completed = self.run_tool("install-deepseek-plugin.ps1", "-MarketplaceRoot", "custom/plugins/")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        for skill_id in self.skill_ids:
            self.assertEqual(_tree_digest(custom_shared / skill_id), _tree_digest(self.source / "skills" / skill_id))
        self.assertEqual(_tree_digest(self.home), before_home)
        self.assertEqual(_tree_digest(self.source), before_source)
        self.assertFalse(self.marketplace.exists())
        self.assertTrue((custom / "plugins/plugins/ppt-pilot/.codex-plugin/plugin.json").is_file())

    def test_standalone_relative_override_uses_powershell_location(self):
        shared = self.root / "custom/skills"
        self.seed_shared(shared)
        script = self.source / "tools/install-deepseek-plugin.ps1"
        completed = subprocess.run([
            shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            f"Set-Location -LiteralPath '{self.root}'; & '{script}' -RepoRoot '{self.source}' -MarketplaceRoot 'custom/plugins/'",
        ], env=dict(os.environ, USERPROFILE=str(self.home)), cwd=self.source,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        for skill_id in self.skill_ids:
            self.assertEqual(_tree_digest(shared / skill_id), _tree_digest(self.source / "skills" / skill_id))
        self.assertFalse((self.source / "custom").exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_standalone_preserves_shared_ordinary_file_named_for_supported_skill(self):
        self.shared.mkdir(parents=True)
        ordinary = self.shared / "ppt-start"
        ordinary.write_bytes(b"not an installed Skill\x00\r\n")
        completed = self.run_tool("install-deepseek-plugin.ps1")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(ordinary.is_file(), "auto-sync must not replace an ordinary file")
        self.assertEqual(ordinary.read_bytes(), b"not an installed Skill\x00\r\n")
        self.assertEqual(list(self.shared.iterdir()), [ordinary])
        self.assertFalse((self.shared.parent / "skill-backups").exists())
        self.assertTrue((self.marketplace / "plugins/ppt-pilot/skills/ppt-start/SKILL.md").is_file())

    def test_standalone_never_creates_absent_shared_roots_or_missing_skills(self):
        for existing in (None, "unrelated", "ppt-start"):
            with self.subTest(existing=existing):
                custom = self.root / (existing or "absent")
                shared = custom / "skills"
                if existing:
                    (shared / existing).mkdir(parents=True)
                    (shared / existing / "SKILL.md").write_text(
                        f"---\nname: {existing}\n---\nkeep unless supported\n", encoding="utf-8"
                    )
                completed = self.run_tool("install-deepseek-plugin.ps1", "-MarketplaceRoot", custom / "plugins")
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                if existing is None:
                    self.assertFalse(shared.exists())
                else:
                    self.assertEqual([path.name for path in shared.iterdir()], [existing])
                    if existing == "ppt-start":
                        self.assertEqual(_tree_digest(shared / existing), _tree_digest(self.source / "skills" / existing))
                    else:
                        self.assertIn("keep unless supported", (shared / existing / "SKILL.md").read_text())
                if existing != "ppt-start":
                    self.assertFalse((custom / "skill-backups").exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_updater_skip_codex_preserves_shared_scope_even_with_alias(self):
        self.seed_shared()
        alias = self.shared / "legacy-alias" / "SKILL.md"
        alias.parent.mkdir()
        alias.write_text("---\nname: ppt-start\n---\n", encoding="utf-8")
        before = _tree_digest(self.shared)
        completed = self.run_tool("update-hosts.ps1", "-SkipClaudeCode", "-SkipCodex", "-SkipRepoProject")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(_tree_digest(self.shared), before)
        self.assertFalse((self.shared.parent / "skill-backups").exists())
        self.assertTrue((self.marketplace / "plugins/ppt-pilot/.codex-plugin/plugin.json").is_file())

    def test_updater_explicit_codex_root_does_not_select_marketplace_sibling(self):
        self.seed_shared()
        custom_market = self.root / "custom/plugins"
        custom_shared = custom_market.parent / "skills"
        self.seed_shared(custom_shared)
        selected = self.root / "selected/skills"
        self.seed_shared(selected)
        before_home = _tree_digest(self.home)
        before_sibling = _tree_digest(custom_shared)
        completed = self.run_tool("update-hosts.ps1", "-SkipClaudeCode", "-SkipRepoProject",
            "-MarketplaceRoot", custom_market, "-CodexSkillsRoot", selected)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(_tree_digest(self.home), before_home)
        self.assertEqual(_tree_digest(custom_shared), before_sibling)
        for skill_id in self.skill_ids:
            self.assertEqual(_tree_digest(selected / skill_id), _tree_digest(self.source / "skills" / skill_id))

    def test_updater_shared_backup_failure_preserves_scope_and_reports_plugin_success(self):
        self.seed_shared()
        before = _tree_digest(self.shared)
        (self.shared.parent / "skill-backups").write_bytes(b"not a directory\n")
        completed = self.run_tool("update-hosts.ps1", "-SkipClaudeCode", "-SkipRepoProject")
        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2, output)
        self.assertIn("PARTIAL_FAILURE", output)
        updated = next(line for line in output.splitlines() if line.startswith("updated:"))
        restored = next(line for line in output.splitlines() if line.startswith("rolled_back:"))
        failed = next(line for line in output.splitlines() if line.startswith("failed:"))
        self.assertIn("deepseek-plugin", updated)
        self.assertNotIn(str(self.shared), updated)
        self.assertNotIn(str(self.shared), restored)
        for skill_id in self.skill_ids:
            self.assertIn(str(self.shared / skill_id), failed)
        self.assertEqual(_tree_digest(self.shared), before)
        self.assertEqual((self.shared.parent / "skill-backups").read_bytes(), b"not a directory\n")
        self.assertTrue((self.marketplace / "plugins/ppt-pilot/.codex-plugin/plugin.json").is_file())


class GoldenHashFallbackContractTest(unittest.TestCase):
    """The golden byte-grammar block lives once in the authority file; the three
    stage contracts reference it by link and must not inline it anymore."""

    def setUp(self) -> None:
        self.authority_path = skill_root() / "references" / GOLDEN_AUTHORITY
        self.authority = read_text(self.authority_path)

    def test_authority_holds_item_11_exactly_once(self) -> None:
        matches = [
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        ]
        self.assertEqual(
            len(matches), 1, f"{GOLDEN_AUTHORITY} must contain item 11 exactly once"
        )

    def test_stage_contracts_reference_the_authority_without_inlining(self) -> None:
        for name in GOLDEN_FILES:
            text = read_text(skill_root() / "references" / name)
            self.assertIn(
                "generation-prompt-byte-grammar.md",
                text,
                f"{name} must link the byte-grammar authority",
            )
            self.assertNotIn(
                GOLDEN_ITEM_11_PREFIX,
                text,
                f"{name} must not inline item 11 anymore",
            )

    def test_item_11_defines_unhashed_fallback_rules(self) -> None:
        item = next(
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        )
        for token in (
            "`unhashed`",
            "`unhashed:<token>`",
            "`slides/.candidates/<slide-id>-<token>.svg`",
            "must not fabricate digests",
            "hard integrity violation",
        ):
            self.assertIn(token, item, f"item 11 missing {token}")

    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )
    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )


class BatchConcurrencyContractTest(unittest.TestCase):
    """Generation and per-slide validation may overlap; only coordinator
    writes and deterministic publication stays serial."""

    def setUp(self) -> None:
        self.skill = read_text(skill_root() / "SKILL.md")
        self.workflow = read_text(skill_root() / "references" / "workflow.md")
        self.redesign = read_text(skill_root() / "references" / "redesign-prompt.md")
        self.qa = read_text(skill_root() / "references" / "qa-and-revision.md")
        self.artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.combined = "\n".join(
            (self.skill, self.workflow, self.redesign, self.qa, self.artifact)
        )

    def test_concurrent_generation_validation_and_serial_publication_ownership(self):
        for token in (
            "batch_width",
            "prompt_by_value",
            "fresh_history=true",
            "filesystem=none",
            "data_tools=none",
            "host_attribution_id",
            "host_task_id",
            "ordered_slide_ids",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.combined)
        self.assertIn("host-isolation-adapters.md", self.combined)
        self.assertIn(
            "不得轮询",
            read_text(skill_root() / "references" / "host-isolation-adapters.md"),
        )
        ownership_documents = {
            "SKILL.md": self.skill,
            "workflow.md": self.workflow,
            "redesign-prompt.md": self.redesign,
            "qa-and-revision.md": self.qa,
            "artifact-contract.md": self.artifact,
        }
        for name, text in ownership_documents.items():
            with self.subTest(document=name):
                self.assertIn("coordinator", text)
                self.assertIn("ordered_slide_ids", text)
        self.assertIn("generator 与各页", self.qa)
        self.assertIn("可以重叠", self.qa)
        self.assertIn("只有 coordinator", self.qa)
        self.assertIn("串行确定", self.qa)
        self.assertIn("coordinator 独占 candidate 写入", self.workflow)
        self.assertIn("callback", self.artifact)

    def test_host_capability_degrades_safely_without_nested_cli_or_current_context(self):
        for token in (
            "非 Git",
            "width 1",
            "generator_unavailable",
            "禁止嵌套调用 Claude、Codex 或 DeepSeek CLI",
            "不得探测凭据或 profile",
            "不得使用 coordinator 当前上下文",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.combined)
        lowered = self.combined.lower()
        for executable_fallback in (
            "claude -p",
            "codex exec",
            "deepseek chat",
            ".claude/credentials",
            ".codex/auth",
        ):
            self.assertNotIn(executable_fallback, lowered)


class CjkLineWidthContractTest(unittest.TestCase):
    def test_svg_contract_defines_width_formula(self) -> None:
        svg = read_text(skill_root() / "references" / "svg-contract.md")
        self.assertIn("行宽估算", svg)
        self.assertIn("1.0 × font-size", svg)
        self.assertIn("0.88", svg)
        self.assertIn("12% 余量", svg)

    def test_qa_geometry_check_references_the_formula(self) -> None:
        qa = read_text(skill_root() / "references" / "qa-and-revision.md")
        self.assertIn("行宽估算公式", qa)
        self.assertRegex(qa, r"svg-contract\.md\) 的行宽估算公式")


class PreferenceProfileContractTest(unittest.TestCase):
    def test_interaction_protocol_defines_profile_semantics(self) -> None:
        protocol = read_text(skill_root() / "references" / "interaction-protocol.md")
        for token in (
            "pilot-preferences.json",
            "当前请求明确答案 > 本运行已批准产物 > 偏好档案 > 安全默认值",
            "standing 授权",
            "咨询性输入",
        ):
            self.assertIn(token, protocol, f"interaction-protocol.md missing {token}")

    def test_artifact_contract_defines_profile_schema(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn("## 可选工作区偏好档案", artifact)
        self.assertIn("standing_authorizations", artifact)
        self.assertIn("不进入任何 `run.json` 恢复链", artifact)

    def test_brief_and_design_system_consume_the_profile(self) -> None:
        brief = read_text(skill_root() / "references" / "brief-and-research.md")
        design = read_text(skill_root() / "references" / "design-system.md")
        self.assertIn("pilot-preferences.json", brief)
        self.assertIn("偏好档案已记录品牌方向", design)


if __name__ == "__main__":
    unittest.main()
