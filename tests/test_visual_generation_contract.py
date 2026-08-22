import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


STYLE_IDENTITY_FIELDS = (
    "selected_style_id",
    "selected_style_display_name",
    "style_kind",
    "style_manifest_version",
)


STABLE_RESOLVER_REASONS = (
    "registry_missing",
    "registry_path_unsafe",
    "registry_target_invalid",
    "registry_unreadable",
    "registry_malformed",
    "registry_schema_unsupported",
    "registry_duplicate_style",
    "style_not_registered",
    "style_kind_invalid",
    "entrypoint_missing",
    "entrypoint_path_unsafe",
    "entrypoint_target_invalid",
    "legacy_entrypoint_malformed",
    "legacy_identity_mismatch",
    "manifest_malformed",
    "manifest_schema_unsupported",
    "manifest_identity_mismatch",
    "manifest_version_invalid",
    "style_asset_field_missing",
    "style_asset_path_unsafe",
    "style_asset_target_invalid",
    "style_asset_unreadable",
    "prompt_field_missing",
    "prompt_path_unsafe",
    "prompt_file_missing",
    "prompt_target_invalid",
    "prompt_unreadable",
    "prompt_template_invalid",
    "prompt_snapshot_conflict",
)


BLOCKER_CASE_IDS = {
    "create-blocker-on-missing-prompt",
    "sanitize-unsafe-resource-to-none",
    "refresh-same-slide-blocker",
    "serialize-other-slide-blocker-first",
    "still-failing-skips-generator-and-svg",
    "durable-prompt-keeps-compiling-blocker-before-commit",
    "compiling-crash-recovers-by-compiled-and-clears-blocker",
    "precedence-unselected-pack-root-before-selected-prompt",
    "precedence-selected-tokens-before-prompt",
}


DUAL_DEFECT_EXPECTATIONS = {
    "precedence-unselected-pack-root-before-selected-prompt": {
        "defects": {"unselected_pack_root_invalid", "selected_prompt_invalid"},
        "reason": "entrypoint_path_unsafe",
    },
    "precedence-selected-tokens-before-prompt": {
        "defects": {"selected_tokens_target_invalid", "selected_prompt_invalid"},
        "reason": "style_asset_target_invalid",
    },
}


SAFE_RESOURCE_PREFIX = "assets/styles/"

REQUIRED_TRANSACTION_FIELDS = {
    "transaction_id",
    "slide_id",
    "generation_intent",
    "generation_trigger_id",
    "prompt_path",
    "prompt_snapshot_id",
    "compiled_prompt_sha256",
    "candidate_path",
    "final_path",
    "state",
    "generation_attempt",
    "candidate_sha256",
    "failure_reason",
}

TRANSACTION_STATES = (
    "compiling",
    "compiled",
    "generating",
    "candidate_written",
    "validated",
    "promoted",
    "failed",
)

TRANSACTION_FAILURE_REASONS = (
    "generator_unavailable",
    "generator_refused",
    "generator_timeout",
    "generator_output_malformed",
    "candidate_write_failed",
    "candidate_hash_mismatch",
    "svg_contract_failed",
    "locked_content_mismatch",
    "visual_qa_failed",
    "final_promotion_conflict",
    "transaction_state_conflict",
)

NORMAL_TRANSACTION_EDGES = (
    ("compiling", "compiled"),
    ("compiled", "generating"),
    ("generating", "candidate_written"),
    ("candidate_written", "validated"),
    ("validated", "promoted"),
)

FAILURE_TRANSACTION_EDGES = (
    ("generating", "failed"),
    ("candidate_written", "failed"),
    ("validated", "failed"),
)

RECOVERY_TRANSACTION_EDGES = (
    ("failed", "generating"),
    ("failed", "validated"),
)

TRANSACTION_CRASH_CASE_IDS = {
    "compiling-durable-prompt-match-commits-compiled",
    "compiling-durable-prompt-mismatch-recompiles",
    "generating-orphan-candidate-is-never-adopted",
    "candidate-written-hash-match-continues-validation",
    "candidate-written-hash-mismatch-fails",
    "validated-final-hash-match-promotes",
    "validated-final-conflict-fails",
    "illegal-recovery-transition-fails",
    "promoted-final-qa-cleans-transaction-and-dirty-slide",
}

EXPECTED_OPERATION_FIELDS = (
    "first_action",
    "stop",
    "resolver_calls",
    "generator_calls",
    "svg_writes",
    "stage_scan_calls",
    "style_fallback_calls",
    "patch_downgrade_calls",
)


def parse_brief_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for section_fields in parse_brief_sections(path).values():
        fields.update(section_fields)
    return fields


def parse_brief_sections(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in read_text(path).splitlines():
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            sections[current] = {}
            continue
        stripped = line.strip()
        if current is None or not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped.removeprefix("- ").split(":", 1)
        sections[current][key.strip()] = value.strip()
    return sections


class VisualGenerationContractTests(unittest.TestCase):
    REQUIRED_BRIEF_HEADINGS = {
        "来源与版本",
        "锁定内容",
        "信息层级",
        "构图",
        "视觉系统",
        "修订模式",
        "输出与质量要求",
    }

    def setUp(self) -> None:
        self.reference = skill_root() / "references" / "visual-brief-and-generation.md"
        self.skill = skill_root() / "SKILL.md"
        self.workflow = skill_root() / "references" / "workflow.md"
        self.artifact = skill_root() / "references" / "artifact-contract.md"
        self.qa = skill_root() / "references" / "qa-and-revision.md"
        self.brief = repo_root() / "tests" / "fixtures" / "visual-briefs" / "S05.md"
        self.style_manifest = (
            skill_root()
            / "assets"
            / "styles"
            / "canway-midyear-review"
            / "manifest.json"
        )
        self.precedence = repo_root() / "tests" / "fixtures" / "visual-revision-precedence.json"
        self.blocker = repo_root() / "tests" / "fixtures" / "style-prompt-blocker-cases.json"
        self.transaction = repo_root() / "tests" / "fixtures" / "visual-generation-transaction-cases.json"

    def test_skill_requires_visual_brief_contract_before_svg(self):
        self.assertTrue(self.reference.exists())
        skill = read_text(self.skill)
        self.assertIn("visual-brief-and-generation.md", skill)
        self.assertLess(skill.index("visual-brief-and-generation.md"), skill.index("SVG 契约"))

    def test_fixture_has_every_required_brief_section(self):
        text = read_text(self.brief)
        headings = {
            line.removeprefix("## ").strip()
            for line in text.splitlines()
            if line.startswith("## ")
        }
        self.assertEqual(headings, self.REQUIRED_BRIEF_HEADINGS)
        for token in (
            "storyboard_snapshot_id",
            "theme_snapshot_id",
            "applied_visual_revision_ids",
            "selected_style_id",
            "selected_style_display_name",
            "style_manifest_version",
            "style_token_path",
            "style_guidance_path",
            "primary_message",
            "reading_order",
            "layout_family",
            "focal_object",
            "typography_ladder",
            "prohibited_motifs",
            "mode: recompose",
            "office_safe_svg",
        ):
            self.assertIn(token, text)
        self.assertNotIn("style_reference_path", text)
        manifest = json.loads(read_text(self.style_manifest))
        self.assertIn(f"style_manifest_version: {manifest['version']}", text)

    def test_fixture_has_complete_style_identity_and_generation_owner(self):
        sections = parse_brief_sections(self.brief)
        source = sections["来源与版本"]
        revision = sections["修订模式"]
        expected_identity = {
            "selected_style_id": "canway-midyear-review",
            "selected_style_display_name": "嘉为年中总结风格",
            "style_kind": "style_pack",
            "style_manifest_version": "1.2.0",
        }
        expected_owner = {
            "generation_intent": "user_recompose",
            "generation_trigger_id": "interaction:visual-revision-3",
        }
        self.assertEqual({field: source.get(field) for field in STYLE_IDENTITY_FIELDS}, expected_identity)
        for field in expected_owner:
            self.assertNotIn(field, source)
        for field, value in expected_owner.items():
            with self.subTest(field=field):
                self.assertEqual(revision.get(field), value)
        for field in STYLE_IDENTITY_FIELDS:
            self.assertNotIn(field, revision)

    def test_s05_and_theme_fixture_share_style_identity(self):
        theme_fixture = repo_root() / "tests" / "fixtures" / "theme-canway-S05.json"
        self.assertTrue(theme_fixture.is_file(), f"missing fixture: {theme_fixture}")
        brief_fields = parse_brief_fields(self.brief)
        theme = json.loads(read_text(theme_fixture))
        self.assertEqual(theme["schema_version"], 1)
        for field in STYLE_IDENTITY_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(theme.get(field), brief_fields.get(field))

    def test_style_prompt_blocker_fixture_models_atomic_lifecycle_and_precedence(self):
        self.assertTrue(self.blocker.is_file(), f"missing fixture: {self.blocker}")
        payload = json.loads(read_text(self.blocker))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(tuple(payload["stable_resolver_reasons"]), STABLE_RESOLVER_REASONS)

        reference = read_text(skill_root() / "references" / "redesign-prompt.md")
        for reason in STABLE_RESOLVER_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(f"`{reason}`", reference)

        cases = {case["id"]: case for case in payload["blocker_cases"]}
        self.assertEqual(set(cases), BLOCKER_CASE_IDS)

        for case in cases.values():
            before = case["before_run"]
            after = case["after_run"]
            expected = case["expected"]
            with self.subTest(case=case["id"]):
                self.assertEqual(before["schema_version"], 1)
                self.assertEqual(after["schema_version"], 1)
                self.assertEqual(after["mode"], before["mode"])
                self.assertEqual(after["stage"], before["stage"])
                self.assertEqual(after.get("interaction_history"), before.get("interaction_history"))
                self.assertIn(expected["slide_id"], after["dirty_slides"])
                for field in EXPECTED_OPERATION_FIELDS:
                    self.assertIn(field, expected, f"{case['id']} missing {field}")
                self.assertIsInstance(expected["stop"], bool)
                self.assertTrue(expected["first_action"])
                for field in (
                    "resolver_calls",
                    "generator_calls",
                    "svg_writes",
                    "stage_scan_calls",
                    "style_fallback_calls",
                    "patch_downgrade_calls",
                ):
                    self.assertIsInstance(expected[field], int)
                    self.assertGreaterEqual(expected[field], 0)
                for field in (
                    "generator_calls",
                    "svg_writes",
                    "stage_scan_calls",
                    "style_fallback_calls",
                    "patch_downgrade_calls",
                ):
                    self.assertEqual(expected[field], 0, f"{case['id']} unexpectedly performs {field}")

                for run_name, run in (("before", before), ("after", after)):
                    transaction = run.get("visual_generation_transaction")
                    if transaction is not None:
                        self.assertEqual(
                            set(transaction),
                            REQUIRED_TRANSACTION_FIELDS,
                            f"{case['id']} {run_name} transaction schema",
                        )
                        self.assertEqual(transaction["transaction_id"], transaction["prompt_snapshot_id"])
                        self.assertGreaterEqual(transaction["generation_attempt"], 0)

                blocker = after.get("visual_generation_blocker")
                if expected["active_blocker"]:
                    self.assertIsNotNone(blocker)
                    self.assertEqual(blocker["state"], "style_prompt_unavailable")
                    self.assertEqual(blocker["status"], "active")
                    self.assertEqual(blocker["slide_id"], expected["slide_id"])
                    self.assertEqual(blocker["reason"], expected["reason"])
                    self.assertEqual(blocker["selected_style_id"], "canway-midyear-review")
                    self.assertIn(blocker["reason"], STABLE_RESOLVER_REASONS)
                    resource = blocker["resource"]
                    self.assertTrue(
                        resource == "none" or (
                            resource.startswith(SAFE_RESOURCE_PREFIX)
                            and not resource.startswith("/")
                            and ":" not in resource
                            and ".." not in resource.split("/")
                        ),
                        resource,
                    )
                else:
                    self.assertNotIn("visual_generation_blocker", after)

        sanitize = cases["sanitize-unsafe-resource-to-none"]["after_run"]["visual_generation_blocker"]
        self.assertEqual(sanitize["resource"], "none")

        refresh = cases["refresh-same-slide-blocker"]
        self.assertEqual(refresh["before_run"]["visual_generation_blocker"]["slide_id"], "S07")
        self.assertEqual(refresh["after_run"]["visual_generation_blocker"]["slide_id"], "S07")
        self.assertNotEqual(
            refresh["before_run"]["visual_generation_blocker"]["reason"],
            refresh["after_run"]["visual_generation_blocker"]["reason"],
        )

        other_slide = cases["serialize-other-slide-blocker-first"]
        self.assertEqual(other_slide["before_run"], other_slide["after_run"])
        self.assertEqual(other_slide["attempted_operation"]["requested_slide_id"], "S07")
        self.assertEqual(other_slide["attempted_operation"]["kind"], "create_style_prompt_blocker")
        self.assertEqual(other_slide["before_run"]["visual_generation_blocker"]["slide_id"], "S03")
        self.assertNotEqual(
            other_slide["attempted_operation"]["requested_slide_id"],
            other_slide["before_run"]["visual_generation_blocker"]["slide_id"],
        )
        self.assertEqual(other_slide["expected"]["first_action"], "process_existing_blocker")
        for field in (
            "resolver_calls",
            "generator_calls",
            "svg_writes",
            "stage_scan_calls",
            "style_fallback_calls",
            "patch_downgrade_calls",
        ):
            self.assertEqual(other_slide["expected"][field], 0)
        self.assertTrue(other_slide["expected"]["stop"])

        still_failing = cases["still-failing-skips-generator-and-svg"]
        self.assertEqual(still_failing["expected"]["resolver_calls"], 1)
        self.assertEqual(still_failing["expected"]["generator_calls"], 0)
        self.assertEqual(still_failing["expected"]["svg_writes"], 0)

        for case_id in (
            "durable-prompt-keeps-compiling-blocker-before-commit",
            "compiling-crash-recovers-by-compiled-and-clears-blocker",
        ):
            case = cases[case_id]
            with self.subTest(compiling_case=case_id):
                self.assertEqual(
                    case["before_run"]["visual_generation_transaction"]["state"],
                    "compiling",
                )
                self.assertEqual(
                    case["before_run"]["visual_generation_blocker"]["status"],
                    "active",
                )
                self.assertEqual(
                    case["after_run"]["visual_generation_transaction"]["state"],
                    "compiled",
                )
                self.assertNotIn("visual_generation_blocker", case["after_run"])
                transaction = case["before_run"]["visual_generation_transaction"]
                durable = case["durable_prompt"]
                self.assertEqual(durable["path"], transaction["prompt_path"])
                self.assertEqual(durable["prompt_snapshot_id"], transaction["prompt_snapshot_id"])
                self.assertEqual(durable["compiled_prompt_sha256"], transaction["compiled_prompt_sha256"])
                self.assertEqual(
                    case["expected"]["atomic_run_replacements"],
                    [
                        {
                            "single_run_json_replacement": True,
                            "transaction_id": transaction["transaction_id"],
                            "from_state": "compiling",
                            "to_state": "compiled",
                            "remove_blocker_slide_id": "S07",
                        }
                    ],
                )

        for case_id, expectation in DUAL_DEFECT_EXPECTATIONS.items():
            case = cases[case_id]
            with self.subTest(precedence_case=case_id):
                self.assertEqual(set(case["before_run"]["resolver_defects"]), expectation["defects"])
                self.assertEqual(case["after_run"]["visual_generation_blocker"]["reason"], expectation["reason"])

    def test_visual_generation_transaction_fixture_models_legal_transitions_and_crashes(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(tuple(payload["states"]), TRANSACTION_STATES)
        self.assertEqual(tuple(payload["failure_reasons"]), TRANSACTION_FAILURE_REASONS)
        self.assertEqual(set(payload["transaction_schema"]), REQUIRED_TRANSACTION_FIELDS)

        legal = payload["legal_transitions"]
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["normal"]),
            NORMAL_TRANSACTION_EDGES,
        )
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["failure"]),
            FAILURE_TRANSACTION_EDGES,
        )
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["recovery"]),
            RECOVERY_TRANSACTION_EDGES,
        )
        self.assertEqual(
            payload["replacement_rules"],
            [
                {
                    "from_state": "failed",
                    "to_new_state": "compiling",
                    "same_transaction_edge": False,
                    "when": "authoritative_inputs_changed_or_deterministic_fallback",
                }
            ],
        )

        crash_cases = {case["id"]: case for case in payload["transaction_cases"]}
        self.assertEqual(set(crash_cases), TRANSACTION_CRASH_CASE_IDS)

        def assert_transaction_schema(transaction: dict, label: str) -> None:
            self.assertEqual(set(transaction), REQUIRED_TRANSACTION_FIELDS, label)
            self.assertEqual(transaction["transaction_id"], transaction["prompt_snapshot_id"], label)
            self.assertRegex(transaction["transaction_id"], r"^sha256:[0-9a-f]{64}$", label)
            candidate_hex = transaction["transaction_id"].removeprefix("sha256:")
            self.assertEqual(
                transaction["candidate_path"],
                f"slides/.candidates/{transaction['slide_id']}-{candidate_hex}.svg",
                label,
            )
            self.assertEqual(transaction["prompt_path"], f"generation-prompts/{transaction['slide_id']}.md", label)
            self.assertEqual(transaction["final_path"], f"slides/{transaction['slide_id']}.svg", label)
            self.assertIn(transaction["state"], TRANSACTION_STATES, label)
            if transaction["state"] == "failed":
                self.assertIn(transaction["failure_reason"], TRANSACTION_FAILURE_REASONS, label)
            else:
                self.assertIsNone(transaction["failure_reason"], label)
            if transaction["state"] in {"compiling", "compiled", "generating"}:
                self.assertIsNone(transaction["candidate_sha256"], label)
            if transaction["state"] in {"candidate_written", "validated", "promoted"}:
                self.assertRegex(transaction["candidate_sha256"], r"^sha256:[0-9a-f]{64}$", label)

        for case in crash_cases.values():
            before_tx = case["before_run"].get("visual_generation_transaction")
            after_tx = case["after_run"].get("visual_generation_transaction")
            if before_tx is not None:
                assert_transaction_schema(before_tx, f"{case['id']} before transaction")
            if after_tx is not None:
                assert_transaction_schema(after_tx, f"{case['id']} after transaction")

            slide_id = case["slide_id"]
            if before_tx and before_tx["state"] != "promoted":
                self.assertIn(
                    slide_id,
                    case["after_run"].get("dirty_slides", []),
                    f"{case['id']} clears dirty before promoted final QA",
                )

        compiling_match = crash_cases["compiling-durable-prompt-match-commits-compiled"]
        self.assertEqual(compiling_match["before_run"]["visual_generation_transaction"]["state"], "compiling")
        self.assertEqual(compiling_match["after_run"]["visual_generation_transaction"]["state"], "compiled")
        self.assertNotIn("visual_generation_blocker", compiling_match["after_run"])
        self.assertEqual(
            compiling_match["durable_prompt"],
            {
                "path": compiling_match["before_run"]["visual_generation_transaction"]["prompt_path"],
                "prompt_snapshot_id": compiling_match["before_run"]["visual_generation_transaction"]["prompt_snapshot_id"],
                "compiled_prompt_sha256": compiling_match["before_run"]["visual_generation_transaction"]["compiled_prompt_sha256"],
            },
        )

        compiling_mismatch = crash_cases["compiling-durable-prompt-mismatch-recompiles"]
        self.assertEqual(compiling_mismatch["expected"]["first_action"], "recompile_prompt")
        self.assertEqual(compiling_mismatch["expected"]["generator_calls"], 0)
        self.assertNotEqual(
            compiling_mismatch["durable_prompt"]["compiled_prompt_sha256"],
            compiling_mismatch["before_run"]["visual_generation_transaction"]["compiled_prompt_sha256"],
        )

        generating_orphan = crash_cases["generating-orphan-candidate-is-never-adopted"]
        self.assertEqual(generating_orphan["before_run"]["visual_generation_transaction"]["state"], "generating")
        self.assertEqual(generating_orphan["orphan_candidate"]["path"], generating_orphan["before_run"]["visual_generation_transaction"]["candidate_path"])
        self.assertFalse(generating_orphan["expected"]["adopt_orphan_candidate"])
        self.assertIn(generating_orphan["expected"]["orphan_candidate_action"], {"delete", "isolate"})
        self.assertEqual(generating_orphan["expected"]["generator_calls"], 1)

        candidate_match = crash_cases["candidate-written-hash-match-continues-validation"]
        self.assertEqual(candidate_match["observed_candidate_sha256"], candidate_match["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(candidate_match["after_run"]["visual_generation_transaction"]["state"], "validated")

        candidate_mismatch = crash_cases["candidate-written-hash-mismatch-fails"]
        self.assertNotEqual(candidate_mismatch["observed_candidate_sha256"], candidate_mismatch["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(candidate_mismatch["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(candidate_mismatch["after_run"]["visual_generation_transaction"]["failure_reason"], "candidate_hash_mismatch")

        final_match = crash_cases["validated-final-hash-match-promotes"]
        self.assertEqual(final_match["observed_final_sha256"], final_match["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(final_match["after_run"]["visual_generation_transaction"]["state"], "promoted")

        final_conflict = crash_cases["validated-final-conflict-fails"]
        self.assertNotEqual(final_conflict["observed_final_sha256"], final_conflict["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(final_conflict["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(final_conflict["after_run"]["visual_generation_transaction"]["failure_reason"], "final_promotion_conflict")

        illegal = crash_cases["illegal-recovery-transition-fails"]
        self.assertEqual(illegal["requested_transition"], {"from": "compiled", "to": "promoted"})
        self.assertEqual(illegal["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(illegal["after_run"]["visual_generation_transaction"]["failure_reason"], "transaction_state_conflict")

        cleanup = crash_cases["promoted-final-qa-cleans-transaction-and-dirty-slide"]
        self.assertEqual(cleanup["before_run"]["visual_generation_transaction"]["state"], "promoted")
        self.assertTrue(cleanup["expected"]["final_qa_passed"])
        self.assertNotIn("visual_generation_transaction", cleanup["after_run"])
        self.assertNotIn(cleanup["slide_id"], cleanup["after_run"].get("dirty_slides", []))

    def test_failed_transaction_reasons_have_one_complete_consumer(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        self.assertEqual(tuple(payload["failure_reasons"]), TRANSACTION_FAILURE_REASONS)
        self.assertEqual(tuple(payload["covered_failure_reasons"]), TRANSACTION_FAILURE_REASONS)

        consumer_cases = payload["failed_consumer_cases"]
        reasons = [case["reason"] for case in consumer_cases]
        self.assertEqual(set(reasons), set(TRANSACTION_FAILURE_REASONS))
        self.assertEqual(len(reasons), len(set(reasons)), "each reason must have exactly one consumer case")

        retry_reasons = {
            "generator_unavailable",
            "generator_refused",
            "generator_timeout",
            "generator_output_malformed",
            "candidate_write_failed",
            "candidate_hash_mismatch",
        }
        qa_reasons = {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"}
        conflict_reasons = {"final_promotion_conflict", "transaction_state_conflict"}

        for case in consumer_cases:
            with self.subTest(reason=case["reason"]):
                before_tx = case["before_run"]["visual_generation_transaction"]
                after_tx = case["after_run"].get("visual_generation_transaction")
                self.assertEqual(before_tx["state"], "failed")
                self.assertEqual(before_tx["failure_reason"], case["reason"])
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))

                if case["reason"] in retry_reasons:
                    self.assertEqual(case["consumer"], "explicit_resume_retry_same_transaction")
                    self.assertIsNotNone(after_tx)
                    self.assertEqual(after_tx["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(after_tx["state"], "generating")
                    self.assertIsNone(after_tx["failure_reason"])
                    self.assertEqual(after_tx["generation_attempt"], before_tx["generation_attempt"] + 1)
                    self.assertEqual(after_tx["generation_trigger_id"], before_tx["generation_trigger_id"])
                    self.assertEqual(case["expected"]["generator_calls"], 1)
                    self.assertEqual(case["expected"]["max_generator_calls_per_host_call"], 1)
                    self.assertIn(case["expected"]["orphan_candidate_action"], {"delete", "isolate"})
                elif case["reason"] in qa_reasons:
                    self.assertIn(case["consumer"], {"persist_defect_then_patch", "persist_defect_then_deterministic_fallback"})
                    self.assertTrue(case["expected"]["defect_persisted_before_next_action"])
                    self.assertIn(case["expected"]["next_action"], {"patch", "new_deterministic_fallback_transaction"})
                    if case["expected"]["next_action"] == "new_deterministic_fallback_transaction":
                        self.assertIsNotNone(after_tx)
                        self.assertNotEqual(after_tx["transaction_id"], before_tx["transaction_id"])
                        self.assertEqual(after_tx["state"], "compiling")
                        self.assertEqual(after_tx["generation_intent"], "deterministic_fallback")
                else:
                    self.assertIn(case["reason"], conflict_reasons)
                    self.assertEqual(case["consumer"], "production_blocker_then_user_resolution")
                    self.assertIsNotNone(after_tx)
                    self.assertEqual(after_tx, before_tx)
                    blocker = case["after_run"]["pending_interaction"]
                    self.assertEqual(blocker["stage"], "production")
                    self.assertEqual(blocker["kind"], "blocker")
                    self.assertEqual(blocker["status"], "pending")
                    self.assertTrue(case["expected"]["retain_failed_transaction_until_user_resolution"])

                    branches = {branch["id"]: branch for branch in case["post_user_resolution_branches"]}
                    self.assertEqual(set(branches), {"unchanged-valid-candidate", "authoritative-inputs-changed"})

                    unchanged = branches["unchanged-valid-candidate"]
                    unchanged_pending = unchanged["before_run"]["pending_interaction"]
                    self.assertEqual(unchanged_pending["status"], "answered")
                    self.assertTrue(unchanged_pending["answer"].strip())
                    self.assertEqual(unchanged_pending["decision"], "accept_candidate_after_review")
                    unchanged_after = unchanged["after_run"]["visual_generation_transaction"]
                    self.assertEqual(unchanged["before_run"]["visual_generation_transaction"], before_tx)
                    self.assertEqual(unchanged_after["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(unchanged_after["state"], "validated")
                    self.assertIsNone(unchanged_after["failure_reason"])
                    self.assertEqual(unchanged_after["candidate_sha256"], before_tx["candidate_sha256"])
                    self.assertTrue(unchanged["expected"]["promotion_retry"])

                    changed = branches["authoritative-inputs-changed"]
                    changed_pending = changed["before_run"]["pending_interaction"]
                    self.assertEqual(changed_pending["status"], "answered")
                    self.assertTrue(changed_pending["answer"].strip())
                    self.assertEqual(changed_pending["decision"], "restart_from_updated_inputs")
                    self.assertEqual(changed["before_run"]["visual_generation_transaction"], before_tx)
                    self.assertTrue(changed["durable_choice"]["old_failed_transaction_retained_until_choice"])
                    changed_after = changed["after_run"]["visual_generation_transaction"]
                    self.assertNotEqual(changed_after["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(changed_after["state"], "compiling")
                    self.assertIsNone(changed_after["failure_reason"])

    def test_old_run_prompt_migration_is_read_only_and_deterministic(self):
        fixture = repo_root() / "tests" / "fixtures" / "style-identity-migration-cases.json"
        self.assertTrue(fixture.is_file(), f"missing fixture: {fixture}")
        payload = json.loads(read_text(fixture))
        for case in payload["cases"]:
            case.setdefault("defaults", payload.get("defaults", {}))
            case.setdefault("fallback_identity_table", payload.get("fallback_identity_table", {}))
        cases = {case["id"]: case for case in payload["cases"]}
        required_ids = (
            "old-directory-only-is-inert",
            "new-stale-with-old-directory-rebuilds-from-new-owner",
            "dual-directory-prefers-new-owner",
            "old-directory-different-slide-is-inert",
            "prompt-hash-changed-is-ordinary-stale",
            "stored-body-mismatch-conflicts",
            "conflicting-legacy-provenance-is-inert",
        )
        for case_id in required_ids:
            with self.subTest(case_id=case_id):
                case = cases[case_id]
                old_directory = dict(payload.get("defaults", {}).get("old_directory", {}))
                old_directory.update(case.get("old_directory", {}))
                self.assertEqual(old_directory.get("action"), "read_only")
                self.assertFalse(old_directory.get("write"), case_id)
                self.assertFalse(old_directory.get("move"), case_id)
                self.assertFalse(old_directory.get("delete"), case_id)
                from test_redesign_prompt_contract import evaluate_style_identity_case
                self.assertEqual(evaluate_style_identity_case(case), case["expected"])

    def test_precedence_fixture_keeps_history_and_one_active_value(self):

        payload = json.loads(read_text(self.precedence))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["history"]), 3)
        self.assertEqual(payload["expected_active_contract"]["title_rail"], "none")
        self.assertEqual(payload["expected_active_contract"]["layout_family"], "hierarchical-bento")
        self.assertIn("visual-revision-1:title_rail", payload["expected_superseded_rules"])

    def test_transaction_negative_invariants_preserve_final_dirty_and_active_owner(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        cases = {case["id"]: case for case in payload["negative_invariant_cases"]}
        self.assertEqual(
            set(cases),
            {
                "generation-failure-preserves-pre-existing-final",
                "qa-failure-preserves-pre-existing-final",
                "promotion-failure-preserves-pre-existing-final",
                "promoted-page-qa-pending-retains-transaction-and-dirty",
                "promoted-page-qa-failing-retains-transaction-and-dirty",
                "promoted-deck-qa-pending-retains-transaction-and-dirty",
                "promoted-deck-qa-failing-retains-transaction-and-dirty",
                "new-operation-nonterminal-transaction-recovers-stops-no-replace",
                "arbitrary-cancel-delete-request-rejected",
            },
        )

        final_preserving = {
            "generation-failure-preserves-pre-existing-final",
            "qa-failure-preserves-pre-existing-final",
            "promotion-failure-preserves-pre-existing-final",
            "arbitrary-cancel-delete-request-rejected",
        }
        for case_id in final_preserving:
            case = cases[case_id]
            with self.subTest(case=case_id):
                self.assertEqual(case["after_run"]["final_svg"], case["before_run"]["final_svg"])
                self.assertEqual(case["after_run"]["final_svg"], case["expected"]["retained_final_svg"])
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))
                self.assertFalse(case["expected"].get("final_overwritten"))

        for case_id in (
            "promoted-page-qa-pending-retains-transaction-and-dirty",
            "promoted-page-qa-failing-retains-transaction-and-dirty",
            "promoted-deck-qa-pending-retains-transaction-and-dirty",
            "promoted-deck-qa-failing-retains-transaction-and-dirty",
        ):
            case = cases[case_id]
            with self.subTest(case=case_id):
                before_tx = case["before_run"]["visual_generation_transaction"]
                after_tx = case["after_run"]["visual_generation_transaction"]
                self.assertEqual(before_tx["state"], "promoted")
                self.assertEqual(after_tx, before_tx)
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))
                self.assertIn(case["expected"]["qa_status"], {"pending", "failed"})
                self.assertIn(case["expected"]["qa_scope"], {"page", "deck"})
                self.assertTrue(case["expected"]["retain_transaction"])

        active = cases["new-operation-nonterminal-transaction-recovers-stops-no-replace"]
        before_tx = active["before_run"]["visual_generation_transaction"]
        after_tx = active["after_run"]["visual_generation_transaction"]
        self.assertNotEqual(before_tx["state"], "promoted")
        self.assertNotEqual(before_tx["state"], "failed")
        self.assertEqual(after_tx["transaction_id"], before_tx["transaction_id"])
        self.assertEqual(after_tx["generation_trigger_id"], before_tx["generation_trigger_id"])
        self.assertTrue(active["expected"]["recover_or_stop_before_new_operation"])
        self.assertFalse(active["expected"]["replace_active_transaction"])

        cancel = cases["arbitrary-cancel-delete-request-rejected"]
        self.assertEqual(cancel["after_run"]["visual_generation_transaction"], cancel["before_run"]["visual_generation_transaction"])
        self.assertEqual(cancel["after_run"]["final_svg"], cancel["before_run"]["final_svg"])
        self.assertIn(cancel["slide_id"], cancel["after_run"].get("dirty_slides", []))
        self.assertFalse(cancel["expected"]["cancelled"])
        self.assertFalse(cancel["expected"]["deleted_transaction"])

    def test_qa_failure_consumers_persist_structured_defect_before_next_action(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        cases = {
            case["reason"]: case
            for case in payload["failed_consumer_cases"]
            if case["reason"] in {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"}
        }
        self.assertEqual(set(cases), {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"})

        for reason, case in cases.items():
            with self.subTest(reason=reason):
                before_tx = case["before_run"]["visual_generation_transaction"]
                defect = case["expected"]["durable_defect"]
                self.assertRegex(defect["id"], rf"^{case['slide_id']}-{reason}-[0-9a-f]{{12}}$")
                self.assertIn(defect["artifact_owner"], {f"visual-briefs/{case['slide_id']}.md", f"qa/{case['slide_id']}.md"})
                self.assertEqual(defect["slide_id"], case["slide_id"])
                self.assertEqual(defect["failure_reason"], reason)
                self.assertEqual(defect["candidate_sha256"], before_tx["candidate_sha256"])
                self.assertEqual(defect["transaction_id"], before_tx["transaction_id"])
                self.assertTrue(case["expected"]["defect_persisted_before_next_action"])
                self.assertIn(case["expected"]["next_action"], {"patch", "new_deterministic_fallback_transaction"})

    def test_references_define_recoverable_transaction_contract_and_consumers(self):
        combined = "\n".join(
            read_text(path)
            for path in (self.artifact, self.reference, self.workflow, self.qa, skill_root() / "references" / "redesign-prompt.md")
            if path.exists()
        )
        required_tokens = (
            "visual_generation_transaction",
            "transaction_id == prompt_snapshot_id",
            "compiling -> compiled -> generating -> candidate_written -> validated -> promoted",
            "generating | candidate_written | validated -> failed",
            "failed -> generating",
            "failed -> validated",
            "failed transaction -> new compiling transaction",
            "slides/.candidates/<slide-id>-<64hex>.svg",
            "candidate_sha256",
            "generator_unavailable",
            "generator_refused",
            "generator_timeout",
            "generator_output_malformed",
            "candidate_write_failed",
            "candidate_hash_mismatch",
            "svg_contract_failed",
            "locked_content_mismatch",
            "visual_qa_failed",
            "final_promotion_conflict",
            "transaction_state_conflict",
            "generation_attempt + 1",
            "每次宿主调用最多 generator 1 次",
            "orphan candidate",
            "never adopted",
            "previous final SVG",
            "dirty_slides",
            "promoted transaction",
            "production `blocker`",
            "unchanged valid candidate",
            "authoritative inputs changed",
            "No arbitrary delete/cancel",
        )
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_contract_names_patch_recompose_and_legacy_synthesis(self):
        combined = "\n".join(
            read_text(path).lower()
            for path in (self.reference, self.workflow, self.artifact, self.qa)
            if path.exists()
        )
        for token in (
            "visual-briefs/<slide-id>.md",
            "visual-revision-<n>",
            "`affected_scope`：允许 `deck`、`anchor`",
            "supersedes",
            "patch",
            "recompose",
            "几何底稿",
            "schema-v1",
            "generation prompt byte grammar",
            "compiled_prompt_sha256",
            "prompt_snapshot_id",
            "transaction_id",
            "candidate path",
            "ordinary stale",
            "prompt_snapshot_conflict",
        ):
            self.assertIn(token, combined)


if __name__ == "__main__":
    unittest.main()
