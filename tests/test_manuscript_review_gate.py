import json
import re
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, skill_root


BLOCKING = {"BLOCKER", "HIGH"}
REQUIRED_FIELDS = {
    "id",
    "severity",
    "category",
    "slide_ids",
    "claim",
    "evidence",
    "recommendation",
    "status",
}
ALLOWED_SEVERITIES = {"BLOCKER", "HIGH", "MEDIUM", "LOW"}
ALLOWED_STATUSES = {"OPEN", "RESOLVED", "ACCEPTED_RISK"}
MANUSCRIPT_FILES = {
    "简报.md",
    "研究.md",
    "来源.md",
    "大纲.md",
    "故事板.md",
}
LEGACY_MANUSCRIPT_FILES = {
    "brief.md",
    "research.md",
    "sources.md",
    "outline.md",
    "storyboard.md",
}
DELEGATION_FIELDS = {
    "child_context_id",
    "completion_event_id",
    "result_context_id",
}


def json_blocks(text: str) -> list[Any]:
    return [
        json.loads(match.group(1).strip())
        for match in re.finditer(r"```json\s*(.*?)```", text, flags=re.I | re.S)
    ]


def extract_findings(container: dict[str, Any]) -> list[dict[str, Any]]:
    if "findings" not in container:
        raise KeyError("report must contain a findings list")
    findings = container["findings"]
    if not isinstance(findings, list):
        raise TypeError("findings must be a list")
    if not all(isinstance(finding, dict) for finding in findings):
        raise TypeError("each finding must be an object")
    return findings


def validate_findings(findings: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for finding in findings:
        missing = REQUIRED_FIELDS - set(finding)
        if missing:
            raise ValueError(f"missing finding fields: {sorted(missing)}")
        finding_id = finding["id"]
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise ValueError("finding id must be non-empty text")
        if finding_id in seen:
            raise ValueError(f"duplicate finding id: {finding_id}")
        seen.add(finding_id)
        if finding["severity"] not in ALLOWED_SEVERITIES:
            raise ValueError(f"invalid severity: {finding['severity']}")
        if finding["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {finding['status']}")
        if not isinstance(finding["slide_ids"], list):
            raise TypeError("slide_ids must be a list")
        for field in ("category", "claim", "evidence", "recommendation"):
            if not isinstance(finding[field], str) or not finding[field].strip():
                raise ValueError(f"{field} must be non-empty text")


def gate_passes(findings: list[dict[str, Any]]) -> bool:
    validate_findings(findings)
    return not any(
        finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
        for finding in findings
    )


def validate_delegation_evidence(round_record: dict[str, Any]) -> None:
    evidence = round_record.get("delegation_evidence")
    if not isinstance(evidence, dict):
        raise TypeError("review round must contain delegation_evidence")
    missing = DELEGATION_FIELDS - set(evidence)
    if missing:
        raise ValueError(f"missing delegation evidence fields: {sorted(missing)}")
    for field in DELEGATION_FIELDS:
        value = evidence[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be non-empty host-returned text")
    if evidence["child_context_id"] != evidence["result_context_id"]:
        raise ValueError("review result must originate from the launched child context")


class ManuscriptReviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference_root = skill_root() / "references"
        self.fixture_root = Path(__file__).resolve().parent / "fixtures"
        self.skill_text = read_text(skill_root() / "SKILL.md").lower()
        self.workflow_text = read_text(self.reference_root / "workflow.md").lower()
        self.review_text = read_text(self.reference_root / "manuscript-review.md").lower()
        self.design_text = read_text(Path(__file__).resolve().parents[1] / "docs" / "design.md").lower()

    def load_fixture(self, name: str) -> str:
        return read_text(self.fixture_root / name)

    def test_review_protocol_is_independent_and_read_only(self):
        self.assertIn("全新且独立", self.review_text)
        self.assertIn("只读", self.review_text)
        for name in MANUSCRIPT_FILES:
            self.assertIn(name, self.review_text)
        for excluded in ("创作对话", "theme.json", "samples/", "slides/"):
            self.assertIn(excluded, self.review_text)
        self.assertIn("绝不修改文稿", self.review_text)
        self.assertIn("同上下文", self.review_text)

    def test_review_rounds_require_host_returned_delegation_evidence(self):
        for token in (
            "宿主返回",
            "child_context_id",
            "completion_event_id",
            "result_context_id",
            "空等待",
            "必须先启动、后等待",
            "接收者列表为空",
            "`run.json` 本身",
            "宿主 transcript",
            "不得虚构",
            "review_unavailable",
        ):
            self.assertIn(token, self.review_text)

        with self.assertRaises(TypeError):
            validate_delegation_evidence({})
        with self.assertRaises(ValueError):
            validate_delegation_evidence({"delegation_evidence": {}})
        with self.assertRaises(ValueError):
            validate_delegation_evidence(
                {
                    "delegation_evidence": {
                        "child_context_id": "",
                        "completion_event_id": "completion-1",
                        "result_context_id": "child-1",
                    }
                }
            )
        with self.assertRaises(ValueError):
            validate_delegation_evidence(
                {
                    "delegation_evidence": {
                        "child_context_id": "child-1",
                        "completion_event_id": "completion-1",
                        "result_context_id": "different-child",
                    }
                }
            )

        pass_report = json_blocks(self.load_fixture("review-pass.md"))[0]
        blocked_report = json_blocks(self.load_fixture("review-blocked.md"))[0]
        resolved_report = json_blocks(self.load_fixture("review-resolved-rounds.md"))[0]
        validate_delegation_evidence(pass_report)
        validate_delegation_evidence(blocked_report)
        for round_record in resolved_report["rounds"]:
            validate_delegation_evidence(round_record)

    def test_review_protocol_covers_accuracy_dimensions(self):
        for dimension in (
            "来源覆盖",
            "事实准确性",
            "时效性",
            "逻辑",
            "重复",
            "遗漏",
            "风险",
        ):
            self.assertIn(dimension, self.review_text)
        self.assertIn("pass", self.review_text)
        self.assertIn("没有发现问题", self.review_text)

    def test_review_gate_has_strict_terminal_states(self):
        combined = "\n".join((self.skill_text, self.workflow_text, self.review_text))
        self.assertIn("review_unavailable", combined)
        self.assertIn("manuscript_blocked", combined)
        self.assertRegex(combined, r"最多(?:执行)?三轮|一次运行最多三轮")
        for artifact in ("theme.json", "samples/", "slides/"):
            self.assertIn(artifact, combined)

    def test_unavailable_review_still_writes_the_required_report(self):
        unavailable = json.loads(self.load_fixture("run-review-unavailable.json"))
        self.assertEqual(
            unavailable["manuscript_review"]["latest_report"],
            "文稿审查.md",
        )
        self.assertRegex(
            self.review_text,
            r"review_unavailable(?s:.*?)文稿审查\.md|文稿审查\.md(?s:.*?)review_unavailable",
        )
        self.assertIn("没有审稿人问题", self.review_text)

    def test_contract_blocks_every_unresolved_high_or_blocker(self):
        for text, label in (
            (self.skill_text, "SKILL.md"),
            (self.workflow_text, "workflow.md"),
            (self.review_text, "manuscript-review.md"),
        ):
            self.assertIn("accepted_risk", text, f"{label} must discuss ACCEPTED_RISK")
            self.assertIn("不是 `resolved`", text, f"{label} 必须采用非 RESOLVED 阻断语义")
        self.assertIn("仍然阻断", self.skill_text)
        self.assertIn("仍然阻断", self.review_text)

    def test_gate_truth_table(self):
        base = {
            "id": "MR-001",
            "severity": "HIGH",
            "category": "factuality",
            "slide_ids": ["S03"],
            "claim": "A claim",
            "evidence": "The source does not support it.",
            "recommendation": "Remove or qualify it.",
            "status": "OPEN",
        }
        self.assertFalse(gate_passes([base]))
        self.assertFalse(gate_passes([{**base, "status": "ACCEPTED_RISK"}]))
        self.assertTrue(gate_passes([{**base, "status": "RESOLVED"}]))
        self.assertTrue(gate_passes([{**base, "severity": "MEDIUM"}]))

    def test_design_contract_uses_the_same_five_file_boundary(self):
        match = re.search(
            r"## 强制独立文稿审查\s+(.*?)(?=\n##\s|\Z)",
            self.design_text,
            flags=re.S,
        )
        self.assertIsNotNone(match, "docs/design.md must define the manuscript review section")
        review_section = match.group(1)
        for name in MANUSCRIPT_FILES:
            self.assertIn(name, review_section, f"docs/design.md manuscript boundary must include {name}")

    def test_report_payload_and_persistence_responsibilities_are_unambiguous(self):
        for text, label in (
            (self.review_text, "manuscript-review.md"),
            (self.design_text, "docs/design.md"),
        ):
            self.assertRegex(text, r"审稿人(?:只)?返回", f"{label} 必须说明审稿人返回载荷")
            self.assertRegex(text, r"创作上下文.*(?:保存|持久化)", f"{label} 必须把持久化职责分配给创作上下文")

    def test_parser_rejects_malformed_findings(self):
        with self.assertRaises(KeyError):
            extract_findings({})
        with self.assertRaises(TypeError):
            extract_findings({"findings": {"id": "MR-001"}})
        with self.assertRaises(TypeError):
            extract_findings({"findings": ["MR-001"]})
        with self.assertRaises(ValueError):
            validate_findings([{"id": "MR-001"}])
        duplicate = {
            "id": "MR-001",
            "severity": "LOW",
            "category": "wording",
            "slide_ids": ["S01"],
            "claim": "A claim",
            "evidence": "Evidence",
            "recommendation": "Recommendation",
            "status": "OPEN",
        }
        with self.assertRaises(ValueError):
            validate_findings([duplicate, duplicate.copy()])

    def test_fixtures_live_only_under_tests(self):
        expected = {
            "review-pass.md",
            "review-blocked.md",
            "review-resolved-rounds.md",
            "run-review-approved.json",
            "run-review-blocked.json",
            "run-review-unavailable.json",
        }
        self.assertTrue(self.fixture_root.is_dir())
        self.assertTrue(expected.issubset({path.name for path in self.fixture_root.iterdir()}))
        old_root = self.reference_root / "fixtures"
        self.assertFalse(old_root.exists() and any(old_root.iterdir()))

    def test_pass_and_blocked_reports_match_gate(self):
        pass_report = json_blocks(self.load_fixture("review-pass.md"))[0]
        self.assertEqual(pass_report["verdict"], "PASS")
        pass_findings = extract_findings(pass_report)
        self.assertEqual(pass_findings, [])
        self.assertTrue(gate_passes(pass_findings))

        blocked_report = json_blocks(self.load_fixture("review-blocked.md"))[0]
        self.assertEqual(blocked_report["verdict"], "BLOCK")
        blocked_findings = extract_findings(blocked_report)
        self.assertTrue(blocked_findings)
        self.assertFalse(gate_passes(blocked_findings))

    def test_resolved_rounds_preserve_ids_and_use_fresh_reviewers(self):
        report = json_blocks(self.load_fixture("review-resolved-rounds.md"))[0]
        rounds = report["rounds"]
        self.assertGreaterEqual(len(rounds), 2)
        first, second = rounds[0], rounds[1]
        for index, round_record in enumerate((first, second), start=1):
            self.assertEqual(round_record["round"], index)
            self.assertTrue(round_record["reviewer_id"])
            self.assertTrue(round_record["reviewer_context"])
            validate_delegation_evidence(round_record)
            snapshot = round_record["reviewed_file_snapshot"]
            self.assertEqual(set(snapshot["files"]), MANUSCRIPT_FILES)
            self.assertTrue(snapshot["snapshot_id"])
        self.assertNotEqual(first["reviewer_id"], second["reviewer_id"])
        self.assertNotEqual(first["reviewer_context"], second["reviewer_context"])
        self.assertTrue(first["author_revision_notes"].strip())

        first_findings = extract_findings(first)
        second_findings = extract_findings(second)
        validate_findings(first_findings)
        validate_findings(second_findings)
        self.assertFalse(gate_passes(first_findings))
        self.assertTrue(gate_passes(second_findings))

        first_blocking_ids = {
            finding["id"]
            for finding in first_findings
            if finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
        }
        second_by_id = {finding["id"]: finding for finding in second_findings}
        self.assertTrue(first_blocking_ids)
        for finding_id in first_blocking_ids:
            self.assertIn(finding_id, second_by_id)
            self.assertEqual(second_by_id[finding_id]["status"], "RESOLVED")
            self.assertTrue(second_by_id[finding_id]["evidence"].strip())

    def test_run_histories_store_full_findings_and_revision_trace(self):
        for fixture_name in ("run-review-approved.json", "run-review-blocked.json"):
            run = json.loads(self.load_fixture(fixture_name))
            review = run["manuscript_review"]
            history = review["review_history"]
            self.assertTrue(history, f"{fixture_name} must preserve review history")
            expected_snapshot_files = (
                LEGACY_MANUSCRIPT_FILES
                if fixture_name == "run-review-approved.json"
                else MANUSCRIPT_FILES
            )

            previous_blocking_ids: set[str] = set()
            for index, round_record in enumerate(history):
                for field in ("round", "reviewer_id", "reviewer_context", "reviewed_file_snapshot"):
                    self.assertIn(field, round_record, f"{fixture_name} round {index + 1} missing {field}")
                validate_delegation_evidence(round_record)
                self.assertEqual(
                    set(round_record["reviewed_file_snapshot"]["files"]),
                    expected_snapshot_files,
                )
                self.assertTrue(round_record["reviewed_file_snapshot"]["snapshot_id"])

                findings = extract_findings(round_record)
                validate_findings(findings)
                by_id = {finding["id"]: finding for finding in findings}
                self.assertTrue(
                    previous_blocking_ids.issubset(by_id),
                    f"{fixture_name} round {index + 1} dropped a prior blocking finding",
                )
                previous_blocking_ids = {
                    finding["id"]
                    for finding in findings
                    if finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
                }
                if index < len(history) - 1:
                    self.assertTrue(
                        round_record.get("author_revision_notes", "").strip(),
                        f"{fixture_name} round {index + 1} needs author revision notes before re-review",
                    )

            if run["stage"] == "manuscript_approved":
                self.assertTrue(gate_passes(extract_findings(history[-1])))
            else:
                self.assertFalse(gate_passes(extract_findings(history[-1])))
                current_ids = {
                    finding["id"] for finding in review["open_blocking_findings"]
                }
                self.assertEqual(previous_blocking_ids, current_ids)

    def test_run_states_distinguish_approved_blocked_and_unavailable(self):
        approved = json.loads(self.load_fixture("run-review-approved.json"))
        blocked = json.loads(self.load_fixture("run-review-blocked.json"))
        unavailable = json.loads(self.load_fixture("run-review-unavailable.json"))

        self.assertEqual(approved["stage"], "manuscript_approved")
        self.assertEqual(approved["manuscript_review"]["state"], "manuscript_approved")
        self.assertEqual(approved["manuscript_review"]["open_blocking_findings"], [])
        self.assertGreaterEqual(len(approved["manuscript_review"]["review_history"]), 2)

        self.assertEqual(blocked["stage"], "manuscript_blocked")
        self.assertEqual(blocked["manuscript_review"]["state"], "manuscript_blocked")
        self.assertEqual(blocked["manuscript_review"]["round"], 3)
        self.assertFalse(gate_passes(blocked["manuscript_review"]["open_blocking_findings"]))

        self.assertEqual(unavailable["stage"], "review_unavailable")
        self.assertEqual(unavailable["manuscript_review"]["state"], "review_unavailable")
        self.assertEqual(unavailable["manuscript_review"]["mode"], "unavailable")
        self.assertTrue(unavailable["manuscript_review"]["reason"].strip())


if __name__ == "__main__":
    unittest.main()
