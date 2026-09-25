import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import read_text, skill_root  # noqa: E402


BLOCKING = {"BLOCKER", "HIGH"}


def gate_passes(findings):
    if not isinstance(findings, list):
        raise TypeError("findings must be a list")
    seen = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise TypeError("finding must be an object")
        for field in ("id", "severity", "status", "claim", "evidence", "recommendation"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ValueError("missing finding field: {}".format(field))
        if finding["id"] in seen:
            raise ValueError("duplicate finding id")
        seen.add(finding["id"])
        if finding["severity"] not in BLOCKING | {"MEDIUM", "LOW"}:
            raise ValueError("invalid severity")
        if finding["status"] not in {"OPEN", "RESOLVED", "ACCEPTED_RISK"}:
            raise ValueError("invalid status")
    return not any(item["severity"] in BLOCKING and item["status"] != "RESOLVED" for item in findings)


class ManuscriptReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.reference = skill_root() / "references" / "manuscript-review.md"
        self.text = read_text(self.reference)

    def test_review_contract_uses_five_frozen_inputs_and_inline_fallback(self):
        for name in ("简报.md", "研究.md", "来源.md", "大纲.md", "故事板.md"):
            self.assertIn(name, self.text)
        for token in ("全新独立上下文", "inline_fallback", "当前上下文降级审查", "最多三轮"):
            self.assertIn(token, self.text)
        self.assertNotIn("ppt_review_snapshot.py", self.text)
        self.assertNotIn("固定只读命令", self.text)

    def test_review_snapshot_is_honest_when_hashing_is_unavailable(self):
        self.assertIn("SHA-256", self.text)
        self.assertIn("unhashed", self.text)
        self.assertIn("verification: ai_read", self.text)
        self.assertIn("不能伪造 hash", self.text)

    def test_blocking_findings_require_resolution(self):
        passed = [
            {"id": "F1", "severity": "HIGH", "status": "RESOLVED", "claim": "x", "evidence": "y", "recommendation": "z"},
            {"id": "F2", "severity": "LOW", "status": "OPEN", "claim": "x", "evidence": "y", "recommendation": "z"},
        ]
        self.assertTrue(gate_passes(passed))
        for status in ("OPEN", "ACCEPTED_RISK"):
            with self.subTest(status=status):
                blocked = list(passed)
                blocked[0] = dict(blocked[0], status=status)
                self.assertFalse(gate_passes(blocked))

    def test_review_records_can_be_machine_readable_without_a_runner(self):
        record = {
            "required": True,
            "state": "manuscript_approved",
            "status": "PASSED",
            "open_blocking_findings": [],
            "pending_round": None,
            "review_history": [{"mode": "inline_fallback", "verification": "ai_read"}],
        }
        encoded = json.dumps(record, ensure_ascii=False)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["state"], "manuscript_approved")
        self.assertEqual(decoded["open_blocking_findings"], [])
        self.assertRegex(self.text, r"BLOCKER.*HIGH")


if __name__ == "__main__":
    unittest.main()
