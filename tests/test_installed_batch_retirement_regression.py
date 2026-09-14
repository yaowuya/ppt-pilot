import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ppt-start"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _runtime_commands import Runtime, can_retire_theme_batch


class InstalledThemeBatchRetirementRegressionTests(unittest.TestCase):
    def test_allows_retirement_after_all_generators_reach_terminal_states(self):
        transactions = {
            "s1": {"state": "validated"},
            "s2": {"state": "validated"},
        }

        self.assertTrue(can_retire_theme_batch(transactions))

    def test_rejects_retirement_while_generation_is_in_flight(self):
        transactions = {
            "s1": {"state": "validated"},
            "s2": {"state": "generating"},
        }

        self.assertFalse(can_retire_theme_batch(transactions))

    def test_refresh_preserves_superseded_manifest_state(self):
        runtime = Runtime(".")
        manifest = {
            "state": "superseded",
            "transaction_refs": ["s1"],
            "promotion_cursor": 0,
            "blocker_cursor": 1,
            "active_blocker_ref": None,
        }
        transactions = {"s1": {"state": "validated"}}

        runtime.refresh(manifest, transactions)

        self.assertEqual(manifest["state"], "superseded")


if __name__ == "__main__":
    unittest.main()
