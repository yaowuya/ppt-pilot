import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ppt-start"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _host_adapter_runtime import CapabilityError, validate_capability


def claude_receipt(isolation):
    registry = json.loads(
        (SKILL_ROOT / "assets" / "host-adapters.json").read_text(encoding="utf-8")
    )
    adapter = next(
        entry
        for entry in registry["adapters"]
        if entry["host"] == "claude-code"
        and entry["adapter_id"] == "ppt-svg-generator-sdk"
    )
    return {
        "schema_version": 1,
        "kind": "host_capability",
        **adapter,
        "observation": {
            "native_fresh_isolation": True,
            "remote_fresh_isolation": False,
            "concurrent_tasks": True,
            "durable_lookup": True,
            "worker_capacity": None,
            "prompt_by_value": True,
            "fresh_history": True,
            "filesystem_none": True,
            "data_tools_none": True,
            "attribution": True,
            "nested_cli_required": False,
            "credential_probe_required": False,
            "current_context_only": False,
        },
        "evidence": {
            "agent_name": "ppt-svg-generator-sdk",
            "loaded_agent_sha256": adapter["adapter_digest"],
            "spawn_primitive": "fresh-context-subagent",
            "allowed_tools": ["ListAgents"],
            "ambient_context": ["CLAUDE.md", "parent_git_status"],
            "isolation": isolation,
            "execution_mode": "foreground",
            "result_type": "text",
            "session_id": "test-session",
        },
    }


class InstalledClaudeCodeCapabilityRegressionTests(unittest.TestCase):
    def test_accepts_worktree_isolation_for_tool_limited_generator(self):
        validated = validate_capability(claude_receipt("worktree"))

        self.assertEqual(validated["selected_width"], 1)
        self.assertEqual(validated["evidence"]["isolation"], "worktree")

    def test_keeps_accepting_omitted_isolation(self):
        validated = validate_capability(claude_receipt("omitted"))

        self.assertEqual(validated["evidence"]["isolation"], "omitted")

    def test_rejects_remote_isolation(self):
        with self.assertRaises(CapabilityError):
            validate_capability(claude_receipt("remote"))


if __name__ == "__main__":
    unittest.main()
