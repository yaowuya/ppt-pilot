import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "hosts" / "claude-code" / "agents" / "ppt-svg-generator-sdk.md"


class InstalledSdkGeneratorContractRegressionTests(unittest.TestCase):
    def test_declares_exact_text_role_thresholds(self):
        text = AGENT.read_text(encoding="utf-8")

        self.assertIn(
            "`title` requires `font-size >= 40`; `body` requires `font-size >= 20`; "
            "sizes 14 through 19 use `footnote`",
            text,
        )

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_host_updater_installs_sdk_agent_beside_legacy_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ".claude"
            completed = subprocess.run(
                [
                    shutil.which("powershell"),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools" / "update-hosts.ps1"),
                    "-RepoRoot",
                    str(ROOT),
                    "-SkipRepoProject",
                    "-SkipDeepSeek",
                    "-SkipCodex",
                    "-ClaudeSkillsRoot",
                    str(target / "skills"),
                    "-ClaudeAgentsRoot",
                    str(target / "agents"),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            for name in ("ppt-svg-generator.md", "ppt-svg-generator-sdk.md"):
                with self.subTest(agent=name):
                    self.assertEqual(
                        (target / "agents" / name).read_bytes(),
                        (ROOT / "hosts" / "claude-code" / "agents" / name).read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
