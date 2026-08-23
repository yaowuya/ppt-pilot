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
INLINE_FALLBACK_REASONS = {
    "child_context_unavailable",
    "child_start_failed",
    "completion_event_missing",
    "result_context_mismatch",
    "delegation_capability_unavailable",
}


def validate_review_execution(round_record: dict[str, Any]) -> None:
    mode = round_record.get("review_mode") or round_record.get("mode")
    if mode is None and "delegation_evidence" in round_record:
        mode = "subagent"
    if mode == "subagent":
        validate_delegation_evidence(round_record)
        if "fallback_evidence" in round_record:
            raise ValueError("subagent round cannot contain fallback_evidence")
        return
    if mode == "inline_fallback":
        if "delegation_evidence" in round_record:
            raise ValueError("inline round cannot contain delegation_evidence")
        evidence = round_record.get("fallback_evidence")
        if not isinstance(evidence, dict):
            raise TypeError("inline round requires fallback_evidence")
        if evidence.get("delegation_attempted") is not True:
            raise ValueError("inline fallback must follow a delegation attempt")
        if evidence.get("reason") not in INLINE_FALLBACK_REASONS:
            raise ValueError("invalid fallback reason")
        detail = evidence.get("host_detail")
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("fallback host_detail must be non-empty")
        return
    raise ValueError("invalid review_mode")


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


def validate_pending_round(pending: dict[str, Any]) -> None:
    mode = pending.get("mode")
    if "review_mode" in pending:
        raise ValueError("pending round cannot contain review_mode")
    if mode == "inline_fallback":
        validate_review_execution(pending)
        return
    if mode == "subagent":
        if "fallback_evidence" in pending or "delegation_evidence" in pending:
            raise ValueError("pending subagent round requires launch evidence only")
        evidence = pending.get("delegation_attempt_evidence")
        if not isinstance(evidence, dict):
            raise TypeError("pending subagent round requires delegation_attempt_evidence")
        if set(evidence) != {"child_context_id"}:
            raise ValueError("pending delegation attempt has invalid fields")
        child = evidence["child_context_id"]
        if not isinstance(child, str) or not child.strip():
            raise ValueError("pending child_context_id must be non-empty")
        return
    raise ValueError("invalid pending review mode")


def commit_completed_review(run: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(run, ensure_ascii=False))
    review = result["manuscript_review"]
    validate_review_execution(report)
    findings = extract_findings(report)
    validate_findings(findings)
    key = (report["cycle"], report["round"])
    existing = [
        record
        for record in review.get("review_history", [])
        if (record.get("cycle", 1), record.get("round")) == key
    ]
    pending = review.get("pending_round")
    if pending is None:
        if len(existing) == 1 and existing[0] == report:
            return result
        raise ValueError("completed review has no matching pending round")
    if "review_mode" in pending or "mode" in report:
        raise ValueError("pending and completed records must use distinct mode fields")
    if pending.get("mode") != report.get("review_mode"):
        raise ValueError("pending and completed review modes differ")
    current_cycle = review.get("cycle", 1)
    current_round = review.get("round", 0)
    if pending.get("cycle") != current_cycle:
        raise ValueError("pending review cycle is not current")
    if pending.get("round") != current_round + 1 or pending["round"] > 3:
        raise ValueError("pending review round is not the next legal round")
    validate_pending_round(pending)
    if pending["mode"] == "inline_fallback":
        if pending["fallback_evidence"] != report.get("fallback_evidence"):
            raise ValueError("inline fallback evidence changed between pending and report")
    else:
        child = pending["delegation_attempt_evidence"]["child_context_id"]
        delegation = report.get("delegation_evidence", {})
        if delegation.get("child_context_id") != child or delegation.get("result_context_id") != child:
            raise ValueError("subagent result does not match pending child context")
    if (pending["cycle"], pending["round"]) != key:
        raise ValueError("pending round identity mismatch")
    if pending["reviewed_file_snapshot"] != report["reviewed_file_snapshot"]:
        raise ValueError("pending round snapshot mismatch")
    if existing:
        raise ValueError("review round already exists")
    prior_history = review.get("review_history", [])
    prior_findings = extract_findings(prior_history[-1]) if prior_history else []
    prior_blocking_ids = {
        finding["id"]
        for finding in prior_findings
        if finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
    }
    report_by_id = {finding["id"]: finding for finding in findings}
    if not prior_blocking_ids.issubset(report_by_id):
        raise ValueError("completed review dropped a prior blocking finding")
    review.setdefault("review_history", []).append(report)
    review.pop("pending_round")
    review["cycle"] = report["cycle"]
    review["round"] = report["round"]
    review["mode"] = report["review_mode"]
    review["open_blocking_findings"] = [
        finding
        for finding in findings
        if finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
    ]
    if gate_passes(findings):
        review["state"] = "manuscript_approved"
        review["status"] = "PASSED"
        result["stage"] = "manuscript_approved"
    else:
        review["state"] = "manuscript_blocked"
        review["status"] = "BLOCKED"
        result["stage"] = "manuscript_blocked"
    return result


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
        self.assertIn("当前上下文", self.review_text)

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

    def test_review_execution_evidence_is_discriminated_by_mode(self):
        subagent = {
            "review_mode": "subagent",
            "delegation_evidence": {
                "child_context_id": "child-1",
                "completion_event_id": "completion-1",
                "result_context_id": "child-1",
            },
        }
        inline = {
            "review_mode": "inline_fallback",
            "fallback_evidence": {
                "delegation_attempted": True,
                "reason": "child_context_unavailable",
                "host_detail": "no child context returned",
            },
        }
        validate_review_execution(subagent)
        validate_review_execution(inline)
        validate_review_execution({"delegation_evidence": subagent["delegation_evidence"]})
        pending_inline = {
            "mode": "inline_fallback",
            "fallback_evidence": inline["fallback_evidence"],
        }
        pending_subagent = {
            "mode": "subagent",
            "delegation_attempt_evidence": {"child_context_id": "child-1"},
        }
        validate_pending_round(pending_subagent)
        validate_pending_round(pending_inline)

        invalid = (
            {**subagent, "fallback_evidence": inline["fallback_evidence"]},
            {**inline, "delegation_evidence": subagent["delegation_evidence"]},
            {"review_mode": "inline_fallback"},
            {
                "review_mode": "inline_fallback",
                "fallback_evidence": {
                    "delegation_attempted": False,
                    "reason": "child_context_unavailable",
                    "host_detail": "not attempted",
                },
            },
            {
                "review_mode": "inline_fallback",
                "fallback_evidence": {
                    "delegation_attempted": True,
                    "reason": "unknown",
                    "host_detail": "unknown",
                },
            },
        )
        for record in invalid:
            with self.subTest(record=record):
                with self.assertRaises((TypeError, ValueError)):
                    validate_review_execution(record)

        invalid_pending = (
            {"mode": "inline_fallback"},
            {"mode": "inline_fallback", "delegation_evidence": subagent["delegation_evidence"]},
            {"mode": "subagent", "fallback_evidence": inline["fallback_evidence"]},
            {"mode": "subagent", "delegation_evidence": subagent["delegation_evidence"]},
            {"mode": "subagent", "delegation_attempt_evidence": {"child_context_id": ""}},
            {"mode": "subagent", "delegation_attempt_evidence": {"child_context_id": "child-1", "completion_event_id": "too-early"}},
        )
        for record in invalid_pending:
            with self.subTest(pending=record):
                with self.assertRaises((TypeError, ValueError)):
                    validate_pending_round(record)

    def test_inline_fallback_pass_can_approve(self):
        run = json.loads(self.load_fixture("run-review-inline-approved.json"))
        review = run["manuscript_review"]
        self.assertEqual(run["stage"], "manuscript_approved")
        self.assertEqual(review["mode"], "inline_fallback")
        self.assertEqual(review["state"], "manuscript_approved")
        self.assertEqual(review["status"], "PASSED")
        self.assertNotIn("pending_round", review)
        self.assertGreaterEqual(len(review["review_history"]), 2)
        previous_blocking_ids = set()
        modes = []
        for round_record in review["review_history"]:
            validate_review_execution(round_record)
            modes.append(round_record.get("review_mode", "subagent"))
            findings = extract_findings(round_record)
            validate_findings(findings)
            by_id = {finding["id"]: finding for finding in findings}
            self.assertTrue(previous_blocking_ids.issubset(by_id))
            previous_blocking_ids = {
                finding["id"]
                for finding in findings
                if finding["severity"] in BLOCKING and finding["status"] != "RESOLVED"
            }
        self.assertIn("subagent", modes)
        self.assertIn("inline_fallback", modes)
        self.assertTrue(gate_passes(extract_findings(review["review_history"][-1])))

    def test_inline_fallback_blocking_findings_still_block(self):
        run = json.loads(self.load_fixture("run-review-inline-blocked.json"))
        review = run["manuscript_review"]
        self.assertEqual(review["mode"], "inline_fallback")
        self.assertEqual(review["state"], "manuscript_blocked")
        self.assertEqual(review["round"], 3)
        self.assertNotIn("pending_round", review)
        last = review["review_history"][-1]
        validate_review_execution(last)
        self.assertFalse(gate_passes(extract_findings(last)))
        self.assertFalse(gate_passes(review["open_blocking_findings"]))

    def test_inline_pending_round_is_resumable_without_increment(self):
        pending = {
            "cycle": 2,
            "round": 1,
            "mode": "inline_fallback",
            "reviewed_file_snapshot": {
                "snapshot_id": "sha256:manuscript-v3",
                "files": sorted(MANUSCRIPT_FILES),
            },
            "fallback_evidence": {
                "delegation_attempted": True,
                "reason": "delegation_capability_unavailable",
                "host_detail": "subagents disabled",
            },
            "status": "in_progress",
        }
        run = {
            "manuscript_review": {
                "cycle": 2,
                "round": 0,
                "mode": "inline_fallback",
                "pending_round": pending,
                "review_history": [],
            }
        }
        restored = json.loads(json.dumps(run))
        self.assertEqual(restored["manuscript_review"]["pending_round"], pending)
        self.assertEqual(restored["manuscript_review"]["round"], 0)
        self.assertEqual(restored["manuscript_review"]["pending_round"]["round"], 1)

    def test_delegation_failure_routes_to_inline_fallback(self):
        skill = read_text(skill_root() / "SKILL.md")
        workflow = read_text(self.reference_root / "workflow.md")
        artifact = read_text(self.reference_root / "artifact-contract.md")
        review = read_text(self.reference_root / "manuscript-review.md")
        qa = read_text(self.reference_root / "qa-and-revision.md")
        combined = "\n".join((skill, workflow, artifact, review, qa))
        for token in (
            "inline_fallback",
            "pending_round",
            "fallback_evidence",
            "当前上下文降级审查",
            "不具备独立上下文隔离",
            "manuscript_approved",
        ):
            self.assertIn(token, combined)
        self.assertRegex(
            combined.lower(),
            r"(?:子 agent|子审稿人|委派).*?(?:失败|不可用|没有).*?inline_fallback|inline_fallback.*?(?:委派|子 agent).*?(?:失败|不可用)",
        )
        self.assertRegex(combined, r"inline(?:\s+|_)?PASS.*manuscript_approved|manuscript_approved.*inline(?:\s+|_)?PASS")
        self.assertNotIn("委派不可用时必须阻断视觉设计，不能降级为同上下文自审放行", combined)
        self.assertNotIn("同上下文审查不能满足这个质量门", combined)

    def test_inline_completed_report_commit_is_idempotent_after_crash(self):
        payload = json.loads(self.load_fixture("inline-review-recovery-cases.json"))
        before = payload["before_run"]
        report = payload["durable_report"]
        committed = commit_completed_review(before, report)
        self.assertEqual(committed, payload["expected_run"])
        self.assertNotIn("pending_round", committed["manuscript_review"])
        matching = [
            record
            for record in committed["manuscript_review"]["review_history"]
            if record["cycle"] == report["cycle"] and record["round"] == report["round"]
        ]
        self.assertEqual(matching, [report])
        repeated = commit_completed_review(committed, report)
        self.assertEqual(repeated, committed)

    def test_inline_completed_report_rejects_invalid_recovery(self):
        payload = json.loads(self.load_fixture("inline-review-recovery-cases.json"))

        mode_swap = json.loads(json.dumps(payload["durable_report"]))
        mode_swap["review_mode"] = "subagent"
        mode_swap.pop("fallback_evidence")
        mode_swap["delegation_evidence"] = {
            "child_context_id": "child-swapped",
            "completion_event_id": "completion-swapped",
            "result_context_id": "child-swapped",
        }
        with self.assertRaises(ValueError):
            commit_completed_review(payload["before_run"], mode_swap)

        subagent_run = json.loads(json.dumps(payload["before_run"]))
        subagent_run["manuscript_review"]["mode"] = "subagent"
        subagent_run["manuscript_review"]["pending_round"] = {
            **subagent_run["manuscript_review"]["pending_round"],
            "mode": "subagent",
            "delegation_attempt_evidence": {"child_context_id": "child-pending"},
        }
        subagent_run["manuscript_review"]["pending_round"].pop("fallback_evidence")
        mismatched_result = json.loads(json.dumps(payload["durable_report"]))
        mismatched_result["review_mode"] = "subagent"
        mismatched_result.pop("fallback_evidence")
        mismatched_result["delegation_evidence"] = {
            "child_context_id": "different-child",
            "completion_event_id": "completion-different",
            "result_context_id": "different-child",
        }
        with self.assertRaises(ValueError):
            commit_completed_review(subagent_run, mismatched_result)

        prior_finding = {
            "id": "MR-RECOVERY-001",
            "severity": "HIGH",
            "category": "factuality",
            "slide_ids": ["S03"],
            "claim": "A prior unsupported claim",
            "evidence": "No supporting source",
            "recommendation": "Remove or support the claim",
            "status": "OPEN",
        }
        dropped_run = json.loads(json.dumps(payload["before_run"]))
        dropped_run["manuscript_review"]["round"] = 1
        dropped_run["manuscript_review"]["review_history"] = [
            {
                "cycle": 1,
                "round": 1,
                "reviewer_id": "reviewer-round-1",
                "reviewer_context": "context-round-1",
                "review_mode": "inline_fallback",
                "fallback_evidence": payload["durable_report"]["fallback_evidence"],
                "reviewed_file_snapshot": {
                    "snapshot_id": "sha256:prior",
                    "files": sorted(MANUSCRIPT_FILES),
                },
                "verdict": "BLOCK",
                "findings": [prior_finding],
            }
        ]
        dropped_run["manuscript_review"]["pending_round"]["round"] = 2
        dropped_report = json.loads(json.dumps(payload["durable_report"]))
        dropped_report["round"] = 2
        with self.assertRaises(ValueError):
            commit_completed_review(dropped_run, dropped_report)

        accepted_report = json.loads(json.dumps(dropped_report))
        accepted_report["findings"] = [{**prior_finding, "status": "ACCEPTED_RISK"}]
        accepted = commit_completed_review(dropped_run, accepted_report)
        self.assertEqual(accepted["stage"], "manuscript_blocked")
        self.assertEqual(accepted["manuscript_review"]["state"], "manuscript_blocked")

        fourth_run = json.loads(json.dumps(payload["before_run"]))
        fourth_run["manuscript_review"]["round"] = 3
        fourth_run["manuscript_review"]["pending_round"]["round"] = 4
        fourth_report = json.loads(json.dumps(payload["durable_report"]))
        fourth_report["round"] = 4
        with self.assertRaises(ValueError):
            commit_completed_review(fourth_run, fourth_report)

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

    def test_designer_perspective_material_gap_protocol(self):
        for token in (
            "设计师视角的材料充分性",
            "汇报场景",
            "material_gap",
            "`missing_evidence`",
            "`proposed_question`",
            "头脑风暴",
            "一次只提出一个问题",
            "pending_interaction",
            "回答本身不是事实来源，落盘产物才是",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.review_text)
        for token in (
            "material_gap",
            "missing_evidence",
            "proposed_question",
            "设计师视角的材料充分性",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.skill_text)

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
            r"## 强制文稿审查（独立优先、inline 降级）\s+(.*?)(?=\n##\s|\Z)",
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
            "run-review-inline-approved.json",
            "run-review-inline-blocked.json",
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
