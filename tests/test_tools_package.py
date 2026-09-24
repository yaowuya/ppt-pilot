import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "tools" / "update-hosts.ps1"
DEEPSEEK = ROOT / "tools" / "install-deepseek-plugin.ps1"
SKILL_IDS = ("ppt-start", "ppt-editable", "ppt-style-extract")


def filtered_tree_digest(root: Path):
    ignored_parts = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox"}
    ignored_suffixes = {".pyc", ".pyo"}
    digest = hashlib.sha256()
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and not ignored_parts.intersection(path.relative_to(root).parts)
        and path.suffix.lower() not in ignored_suffixes
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
    return len(files), digest.hexdigest()


class PackageShapeTests(unittest.TestCase):
    def test_companion_delivery_tool_is_repo_local_and_documented(self):
        tool = ROOT / "tools" / "deck-deliver.ps1"
        self.assertTrue(tool.is_file())
        text = tool.read_text(encoding="utf-8")
        self.assertIn("$RunDir", text)
        self.assertIn("$SkipPptx", text)
        self.assertIn("preview.html", text)
        self.assertIn("delivery-result.json", text)
        self.assertIn(".ppt-pilot\\run.json", text)
        self.assertIn("deck-deliver.ps1", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_ppt_start_ships_only_stateless_tool_files(self):
        scripts = {path.name for path in (ROOT / "skills" / "ppt-start" / "scripts").glob("*.py")}
        self.assertEqual(
            scripts,
            {
                "_source_intake.py",
                "_svg_geometry.py",
                "_svg_runtime.py",
                "_xml_safety.py",
                "ppt_source_intake.py",
                "svg_tool.py",
            },
        )


@unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
class InstallerTests(unittest.TestCase):
    def _run(self, script, *args, cwd=None):
        return subprocess.run(
            [shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, args)],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )

    def _copy_source(self, root):
        source = root / "source"
        for name in ("skills", "hosts", "tools"):
            shutil.copytree(
                ROOT / name,
                source / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        return source

    def test_update_installs_three_skills_retires_sdk_and_preserves_unrelated_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._copy_source(root)
            cache = source / "skills" / "ppt-start" / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "stale.pyc").write_bytes(b"cache")
            claude_skills = root / "claude" / "skills"
            claude_agents = root / "claude" / "agents"
            claude_agents.mkdir(parents=True)
            (claude_agents / "ppt-svg-generator-sdk.md").write_text("retired", encoding="utf-8")
            (claude_agents / "unrelated.md").write_text("keep", encoding="utf-8")

            for _ in range(3):
                result = self._run(
                    source / "tools" / "update-hosts.ps1",
                    "-RepoRoot", source,
                    "-SkipDeepSeek", "-SkipCodex", "-SkipRepoProject",
                    "-ClaudeSkillsRoot", claude_skills,
                    "-ClaudeAgentsRoot", claude_agents,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            for skill_id in SKILL_IDS:
                self.assertEqual(
                    filtered_tree_digest(claude_skills / skill_id),
                    filtered_tree_digest(source / "skills" / skill_id),
                )
            self.assertFalse((claude_skills / "ppt-start" / "scripts" / "__pycache__").exists())
            self.assertEqual(
                (claude_agents / "ppt-svg-generator.md").read_bytes(),
                (source / "hosts" / "claude-code" / "agents" / "ppt-svg-generator.md").read_bytes(),
            )
            self.assertFalse((claude_agents / "ppt-svg-generator-sdk.md").exists())
            self.assertEqual((claude_agents / "unrelated.md").read_text(encoding="utf-8"), "keep")
            backups = claude_agents.parent / "agent-backups"
            self.assertEqual(len(list(backups.glob("ppt-svg-generator.bak-*.md"))), 1)
            self.assertFalse(list(backups.glob("ppt-svg-generator-sdk.bak-*.md")))

    def test_project_scope_refresh_replaces_retired_workflow_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            for scope in (project / ".claude" / "skills", project / ".agents" / "skills"):
                stale = scope / "ppt-start"
                (stale / "scripts").mkdir(parents=True)
                (stale / "SKILL.md").write_text(
                    "run ppt_entry.py and ppt_runtime.py\n",
                    encoding="utf-8",
                )
                (stale / "scripts" / "ppt_entry.py").write_text("stale\n", encoding="utf-8")
                (stale / "scripts" / "ppt_runtime.py").write_text("stale\n", encoding="utf-8")

            result = self._run(
                UPDATE,
                "-RepoRoot", ROOT,
                "-SkipDeepSeek", "-SkipClaudeCode", "-SkipCodex", "-SkipRepoProject",
                "-ProjectRoot", project,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for scope in (project / ".claude" / "skills", project / ".agents" / "skills"):
                for skill_id in SKILL_IDS:
                    self.assertEqual(
                        filtered_tree_digest(scope / skill_id),
                        filtered_tree_digest(ROOT / "skills" / skill_id),
                    )
                self.assertFalse((scope / "ppt-start" / "scripts" / "ppt_entry.py").exists())
                self.assertFalse((scope / "ppt-start" / "scripts" / "ppt_runtime.py").exists())
            self.assertFalse((project / ".claude" / "agents" / "ppt-svg-generator-sdk.md").exists())

    def test_paired_scope_failure_restores_current_and_retired_agents_without_false_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            skills = project / ".claude" / "skills"
            agents = project / ".claude" / "agents"
            agents.mkdir(parents=True)
            current = agents / "ppt-svg-generator.md"
            retired = agents / "ppt-svg-generator-sdk.md"
            current.write_bytes(b"old-current")
            retired.write_bytes(b"old-retired")
            for skill_id in SKILL_IDS:
                target = skills / skill_id
                target.mkdir(parents=True)
                (target / "SKILL.md").write_text("old", encoding="utf-8")
            (project / ".claude" / "skill-backups").write_text("not a directory", encoding="utf-8")

            result = self._run(
                UPDATE,
                "-RepoRoot", ROOT,
                "-SkipDeepSeek", "-SkipClaudeCode", "-SkipCodex", "-SkipRepoProject",
                "-ProjectRoot", project,
            )
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertEqual(current.read_bytes(), b"old-current")
            self.assertEqual(retired.read_bytes(), b"old-retired")
            updated = next(line for line in output.splitlines() if line.startswith("updated:"))
            self.assertNotIn(str(retired), updated)
            self.assertFalse((project / ".claude" / "agent-backups").exists())

    def test_deepseek_installer_packages_all_three_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._copy_source(root)
            marketplace = root / "marketplace"
            result = self._run(
                source / "tools" / "install-deepseek-plugin.ps1",
                "-RepoRoot", source,
                "-MarketplaceRoot", marketplace,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plugin_skills = marketplace / "plugins" / "ppt-pilot" / "skills"
            for skill_id in SKILL_IDS:
                self.assertEqual(
                    filtered_tree_digest(plugin_skills / skill_id),
                    filtered_tree_digest(source / "skills" / skill_id),
                )


if __name__ == "__main__":
    unittest.main()
