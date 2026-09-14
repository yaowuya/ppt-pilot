import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ppt-start"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _runtime_commands import adapter_upgrade_retry_eligible


class InstalledAdapterUpgradeRetryRegressionTests(unittest.TestCase):
    def test_allows_one_recovery_slot_after_newer_adapter_replaces_failed_launch(self):
        transaction = {
            "failure_reason": "generator_unavailable",
            "generation_attempt": 3,
            "candidate_sha256": None,
        }
        dispatch = {
            "host": "claude-code",
            "adapter_id": "ppt-svg-generator",
            "adapter_version": "1.3.0",
        }
        current = {
            "host": "claude-code",
            "adapter_id": "ppt-svg-generator-sdk",
            "adapter_version": "1.4.0",
        }

        self.assertTrue(
            adapter_upgrade_retry_eligible(transaction, dispatch, current)
        )

    def test_allows_one_recovery_slot_after_newer_adapter_fixes_prewrite_svg_contract(self):
        transaction = {
            "failure_reason": "svg_contract_failed",
            "generation_attempt": 3,
            "candidate_sha256": None,
        }
        dispatch = {
            "host": "claude-code",
            "adapter_id": "ppt-svg-generator-sdk",
            "adapter_version": "1.5.0",
        }
        current = {
            "host": "claude-code",
            "adapter_id": "ppt-svg-generator-sdk",
            "adapter_version": "1.6.0",
        }

        self.assertTrue(
            adapter_upgrade_retry_eligible(transaction, dispatch, current)
        )

    def test_rejects_retry_when_latest_dispatch_uses_current_adapter(self):
        transaction = {
            "failure_reason": "generator_unavailable",
            "generation_attempt": 3,
            "candidate_sha256": None,
        }
        dispatch = {
            "host": "claude-code",
            "adapter_id": "ppt-svg-generator-sdk",
            "adapter_version": "1.4.0",
        }

        self.assertFalse(
            adapter_upgrade_retry_eligible(transaction, dispatch, dispatch)
        )


if __name__ == "__main__":
    unittest.main()
