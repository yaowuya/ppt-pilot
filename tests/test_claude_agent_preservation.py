"""Local Agent overrides survive installation while registered SDK identity stays usable."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skills/ppt-start/scripts'))


class ClaudeAgentPreservationTests(unittest.TestCase):
    def test_source_sdk_bytes_match_the_registered_digest(self):
        registry = json.loads((REPO / 'skills/ppt-start/assets/host-adapters.json').read_text(encoding='utf-8'))
        entry = next(item for item in registry['adapters'] if item['adapter_id'] == 'ppt-svg-generator-sdk')
        source = REPO / 'hosts/claude-code/agents/ppt-svg-generator-sdk.md'
        self.assertEqual('sha256:' + hashlib.sha256(source.read_bytes()).hexdigest(), entry['adapter_digest'])

    def test_inspection_selects_a_matching_registered_agent_without_overwriting_local_override(self):
        module = importlib.import_module('_host_adapter_runtime')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / 'skills/ppt-start'
            (skill / 'assets').mkdir(parents=True)
            agents = root / 'agents'
            agents.mkdir()
            legacy = agents / 'ppt-svg-generator.md'
            sdk = agents / 'ppt-svg-generator-sdk.md'
            legacy.write_bytes(b'local ListAgents override')
            sdk.write_bytes(b'registered SDK instruction\n')
            entries = [
                {'host': 'claude-code', 'adapter_id': 'ppt-svg-generator', 'adapter_version': '1.0.0',
                 'adapter_digest': 'sha256:' + hashlib.sha256(b'official legacy instruction\n').hexdigest()},
                {'host': 'claude-code', 'adapter_id': 'ppt-svg-generator-sdk', 'adapter_version': '1.9.0',
                 'adapter_digest': 'sha256:' + hashlib.sha256(sdk.read_bytes()).hexdigest()},
            ]
            registry = skill / 'assets/host-adapters.json'
            registry.write_text(json.dumps({'schema_version': 1, 'adapters': entries}), encoding='utf-8')
            with mock.patch.object(module, 'ROOT', skill), mock.patch.object(module, 'REGISTRY', registry):
                try:
                    result = module.inspect_host('claude-code')
                except module.CapabilityError as exc:
                    self.fail('A local legacy override hid the valid SDK adapter: ' + str(exc))
                self.assertEqual(result['adapter']['adapter_id'], 'ppt-svg-generator-sdk')
                self.assertEqual(legacy.read_bytes(), b'local ListAgents override')
                legacy.write_bytes(b'official legacy instruction\n')
                self.assertEqual(module.inspect_host('claude-code')['adapter']['adapter_id'], 'ppt-svg-generator')

    @unittest.skipUnless(shutil.which('powershell'), 'Windows PowerShell unavailable')
    def test_standard_updater_can_preserve_existing_claude_agent_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / 'agents'
            agents.mkdir()
            legacy = agents / 'ppt-svg-generator.md'
            legacy.write_bytes(b'local ListAgents override')
            result = subprocess.run([
                shutil.which('powershell'), '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', str(REPO / 'tools/update-hosts.ps1'), '-RepoRoot', str(REPO),
                '-SkipDeepSeek', '-SkipCodex', '-SkipRepoProject',
                '-ClaudeSkillsRoot', str(root / 'skills'), '-ClaudeAgentsRoot', str(agents),
                '-PreserveExistingClaudeAgents',
            ], capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(legacy.read_bytes(), b'local ListAgents override')
            self.assertEqual((agents / 'ppt-svg-generator-sdk.md').read_bytes(),
                             (REPO / 'hosts/claude-code/agents/ppt-svg-generator-sdk.md').read_bytes())
            self.assertTrue((root / 'skills/ppt-start/scripts/_delivery_contract.py').is_file())
            diagnostic = subprocess.run([sys.executable, '-B', str(root / 'skills/ppt-start/scripts/ppt_runtime.py'),
                                         'inspect-host', '--host', 'claude-code'],
                                        capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(diagnostic.returncode, 0, diagnostic.stdout + diagnostic.stderr)
            self.assertEqual(json.loads(diagnostic.stdout)['result']['adapter']['adapter_id'], 'ppt-svg-generator-sdk')
    @unittest.skipUnless(shutil.which('powershell'), 'Windows PowerShell unavailable')
    def test_preservation_mode_rejects_an_unreconciled_sdk_before_any_install_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / 'agents'
            agents.mkdir()
            (agents / 'ppt-svg-generator.md').write_bytes(b'local legacy')
            (agents / 'ppt-svg-generator-sdk.md').write_bytes(b'newer local SDK')
            old = root / 'skills/ppt-start'
            old.mkdir(parents=True)
            (old / 'keep.txt').write_bytes(b'existing enhanced installation')
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = subprocess.run([
                shutil.which('powershell'), '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', str(REPO / 'tools/update-hosts.ps1'), '-RepoRoot', str(REPO),
                '-SkipDeepSeek', '-SkipCodex', '-SkipRepoProject',
                '-ClaudeSkillsRoot', str(root / 'skills'), '-ClaudeAgentsRoot', str(agents),
                '-PreserveExistingClaudeAgents',
            ], capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Preserved SDK Agent differs', result.stdout + result.stderr)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
