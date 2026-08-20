import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, relative_markdown_links, skill_root


class InteractionProtocolTests(unittest.TestCase):
    REQUIRED_PENDING_FIELDS = {"id", "stage", "kind", "question", "status"}

    def setUp(self):
        self.skill_path = skill_root() / "SKILL.md"
        self.reference_root = skill_root() / "references"
        self.protocol_path = self.reference_root / "interaction-protocol.md"
        self.workflow_path = self.reference_root / "workflow.md"
        self.artifact_path = self.reference_root / "artifact-contract.md"
        self.brief_path = self.reference_root / "brief-and-research.md"
        self.narrative_path = self.reference_root / "narrative-and-storyboard.md"
        self.review_path = self.reference_root / "manuscript-review.md"
        self.design_path = self.reference_root / "design-system.md"
        self.qa_path = self.reference_root / "qa-and-revision.md"
        self.fixture_root = repo_root() / "tests" / "fixtures"
        self.prompt_root = repo_root() / "tests" / "prompts"

    def _protocol(self) -> str:
        self.assertTrue(
            self.protocol_path.exists(),
            f"Missing interaction protocol: {self.protocol_path}",
        )
        return read_text(self.protocol_path)

    @staticmethod
    def _markdown_table_rows(text: str):
        rows = []
        for line in text.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = tuple(cell.strip().strip("`") for cell in stripped[1:-1].split("|"))
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
        return rows

    def test_interaction_reference_is_reachable_from_shared_entrypoints(self):
        protocol = self.protocol_path.resolve()
        self.assertIn(protocol, relative_markdown_links(self.skill_path))
        self.assertIn(protocol, relative_markdown_links(self.workflow_path))

    def test_interaction_protocol_is_host_neutral(self):
        combined = "\n".join(
            (
                read_text(self.skill_path),
                read_text(self.workflow_path),
                self._protocol(),
            )
        )
        forbidden = (
            "AskUserQuestion",
            "SendMessage",
            "CLAUDE_SKILL_DIR",
            "CLAUDE_PROJECT_DIR",
            "$ARGUMENTS",
            "mcp__",
            "allowed-tools:",
            "/ppt-start",
            "$ppt-start",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_new_runs_default_to_guided_and_auto_keeps_authority_boundary(self):
        combined = "\n".join(
            (
                self._protocol(),
                read_text(self.workflow_path),
                read_text(self.brief_path),
            )
        ).lower()
        self.assertRegex(
            combined,
            r"未显式指定(?:模式|执行策略).*`guided`|(?:模式|执行策略)未显式指定.*`guided`",
        )
        self.assertRegex(combined, r"只有显式指定.*`auto`|`auto`.*必须显式")
        self.assertIn("可选问题", combined)
        self.assertIn("用户权限", combined)
        self.assertIn("安全默认", combined)
        self.assertIn("run.json.mode", combined)
        self.assertIn("delivery_mode", combined)

    def test_decision_queue_asks_one_direct_question_and_recomputes(self):
        text = self._protocol().lower()
        for token in (
            "先检查",
            "不得再次询问",
            "一次只提出一个实质性问题",
            "2–4 个互斥选项",
            "推荐不是确认",
            "明确回答",
            "提出问题后立即停止本轮",
            "重新计算决策队列",
        ):
            self.assertIn(token.lower(), text, f"interaction-protocol.md 缺少 {token}")

    def test_guided_checkpoints_and_conditional_triggers_are_explicit(self):
        combined = "\n".join(
            read_text(path)
            for path in (
                self.protocol_path,
                self.brief_path,
                self.narrative_path,
                self.review_path,
                self.design_path,
                self.qa_path,
            )
            if path.exists()
        ).lower()
        for token in (
            "简报批准",
            "大纲批准",
            "锚点批准",
            "网络",
            "机密",
            "故事板冲突",
            "业务决策",
            "品牌",
            "生产阻断",
        ):
            self.assertIn(token.lower(), combined, f"交互契约缺少条件分支：{token}")
        self.assertRegex(combined, r"简报批准.*明确|明确.*简报批准")
        self.assertRegex(combined, r"大纲批准.*明确|明确.*大纲批准")
        self.assertRegex(combined, r"锚点批准.*明确|明确.*锚点批准")

    def test_pending_interaction_is_additive_and_legacy_runs_remain_valid(self):
        pending_path = self.fixture_root / "run-pending-interaction.json"
        pending_run = json.loads(read_text(pending_path))
        interaction = pending_run["pending_interaction"]

        self.assertEqual(pending_run["schema_version"], 1)
        self.assertTrue(self.REQUIRED_PENDING_FIELDS.issubset(interaction))
        self.assertEqual(interaction["status"], "pending")
        self.assertEqual(interaction["stage"], pending_run["stage"])
        self.assertEqual(interaction["checkpoint"], "outline")
        self.assertEqual(interaction["approval_attempt"], 1)
        self.assertTrue(interaction["question"].strip())
        self.assertIn(len(interaction.get("options", [])), range(2, 5))
        self.assertIn(interaction.get("recommendation"), interaction["options"])
        self.assertEqual(set(interaction["option_effects"]), set(interaction["options"]))
        self.assertTrue(interaction["recommendation_reason"].strip())

        legacy = json.loads(read_text(self.fixture_root / "run-review-approved.json"))
        self.assertEqual(legacy["schema_version"], 1)
        self.assertNotIn("pending_interaction", legacy)

        artifact = read_text(self.artifact_path).lower()
        for token in (
            "pending_interaction",
            "可选",
            "status: answered",
            "answer",
            "不得新增",
            "格式错误",
        ):
            self.assertIn(token.lower(), artifact, f"artifact-contract.md 缺少 {token}")
        self.assertRegex(artifact, r"缺少.*pending_interaction.*有效|不存在.*pending_interaction.*有效")

    def test_pending_interaction_does_not_change_stage_order(self):
        workflow = read_text(self.workflow_path).lower()
        expected = (
            "brief -> research -> outline -> storyboard -> manuscript_review -> "
            "theme -> anchor -> production -> qa -> complete"
        )
        self.assertIn(expected, workflow)
        self.assertNotRegex(workflow, r"brief\s*->\s*(?:paused|awaiting_user)")
        self.assertIn("等待期间", workflow)
        self.assertIn("保持当前阶段", workflow)

    def test_stage_references_link_the_protocol_and_own_local_triggers(self):
        stage_paths = (
            self.brief_path,
            self.narrative_path,
            self.review_path,
            self.design_path,
            self.qa_path,
        )
        protocol = self.protocol_path.resolve()
        for path in stage_paths:
            with self.subTest(path=path.name):
                self.assertIn(protocol, relative_markdown_links(path))

        brief = read_text(self.brief_path).lower()
        for token in (
            "决策依赖顺序",
            "简报批准",
            "run.json.mode",
            "delivery_mode",
            "外部传输",
        ):
            self.assertIn(token.lower(), brief, f"brief-and-research.md 缺少 {token}")

        narrative = read_text(self.narrative_path).lower()
        for token in ("大纲批准", "故事板冲突", "不增加固定暂停"):
            self.assertIn(token.lower(), narrative, f"narrative-and-storyboard.md 缺少 {token}")

        review = read_text(self.review_path).lower()
        for token in ("证据保持型修复", "业务决策", "用户回答不能"):
            self.assertIn(token.lower(), review, f"manuscript-review.md 缺少 {token}")

        design = read_text(self.design_path).lower()
        for token in ("条件式主题问题", "锚点批准", "明确回答", "真实渲染证据"):
            self.assertIn(token.lower(), design, f"design-system.md 缺少 {token}")

        qa = read_text(self.qa_path).lower()
        for token in (
            "pending_interaction",
            "status: answered",
            "生产阻断",
            "修改类别无法唯一判断",
        ):
            self.assertIn(token.lower(), qa, f"qa-and-revision.md 缺少 {token}")

    def test_topic_only_safe_defaults_make_brief_approval_the_first_question(self):
        brief = read_text(self.brief_path).lower()
        for token in (
            "topic、audience、purpose／desired audience action、slide count 和交付格式",
            "presentation time: not supplied",
            "请求所用语言",
            "brand/style: not supplied",
            "离线证据路径",
            "第一个问题必须是简报批准",
        ):
            self.assertIn(token.lower(), brief, f"topic-only 首题规则缺少 {token}")

    def test_approval_and_revision_answers_have_exact_durable_effects(self):
        protocol = self._protocol().lower()
        artifact = read_text(self.artifact_path).lower()
        combined = protocol + "\n" + artifact

        for token in (
            "`approve`",
            "`request_revision`",
            "保持原阶段",
            "用户修订记录",
            "替换为新的 `pending_interaction`",
            "revision-clarification",
        ):
            self.assertIn(token.lower(), combined, f"批准／修订分支缺少 {token}")

        for token in ("`approved`", "不是必需字段", "保持一致", "不能授权"):
            self.assertIn(token.lower(), artifact, f"approved 镜像规则缺少 {token}")

    def test_persisted_mode_is_policy_and_resume_revise_are_entry_actions(self):
        artifact = read_text(self.artifact_path).lower()
        combined = "\n".join(
            (
                read_text(self.skill_path),
                read_text(self.workflow_path),
                self._protocol(),
                artifact,
            )
        ).lower()

        self.assertIn("`mode` 只能是 `guided` 或 `auto`", artifact)
        self.assertIn("`resume`／`revise` 是入口动作", artifact)
        self.assertIn("保留既有 `run.json.mode`", combined)
        self.assertNotIn("`mode` 必须是 `guided`、`auto`、`resume` 或 `revise`", artifact)

    def test_no_blocking_question_is_asked_before_durable_state_exists(self):
        protocol = self._protocol().lower()
        for token in (
            "不存在不持久化的阻塞问题例外",
            "新建且不冲突的运行目录",
            "先持久化",
            "不能创建安全运行目录时停止",
        ):
            self.assertIn(token.lower(), protocol, f"首次问题持久化规则缺少 {token}")
        self.assertNotRegex(protocol, r"可以先在当前交互中询问[^。]*获得[^。]*立即创建")

    def test_ambiguous_run_selection_uses_durable_workspace_control_state(self):
        selection = json.loads(read_text(self.fixture_root / "workspace-run-selection.json"))
        self.assertEqual(selection["schema_version"], 1)
        self.assertEqual(selection["kind"], "run_selection")
        self.assertIn(selection["entry_action"], {"resume", "revise"})
        self.assertEqual(selection["entry_action"], "revise")
        self.assertTrue(selection["operation_payload"]["request"].strip())
        self.assertEqual(selection["operation_payload"]["requested_scope"], "claim_or_source")
        self.assertEqual(selection["status"], "pending")
        self.assertNotIn("stage", selection)
        self.assertEqual(set(selection["candidates"]), set(selection["options"]))
        self.assertEqual(set(selection["option_effects"]), set(selection["options"]))
        self.assertIn(selection["recommendation"], selection["options"])
        self.assertTrue(selection["recommendation_reason"].strip())

        combined = (self._protocol() + "\n" + read_text(self.artifact_path)).lower()
        for token in (
            "ppt-output/run-selection.json",
            "工作区级路由状态",
            "`entry_action`",
            "`operation_payload`",
            "原始操作载荷",
            "不得写入任何候选运行",
            "先写为 `answered`",
            "保留既有 `run.json.mode`",
            "删除 `run-selection.json`",
        ):
            self.assertIn(token.lower(), combined, f"运行选择持久化缺少 {token}")

    def test_reapproval_uses_monotonic_attempt_ids_without_overwriting_revision(self):
        run = json.loads(read_text(self.fixture_root / "run-outline-reapproval.json"))
        history = run["interaction_history"]
        self.assertEqual(set(history), {"outline-approval", "outline-approval-2"})

        revision = history["outline-approval"]
        approval = history["outline-approval-2"]
        self.assertEqual(revision["checkpoint"], "outline")
        self.assertEqual(approval["checkpoint"], "outline")
        self.assertEqual(revision["approval_attempt"], 1)
        self.assertEqual(approval["approval_attempt"], 2)
        self.assertEqual(revision["decision"], "request_revision")
        self.assertEqual(approval["decision"], "approve")
        self.assertEqual(run["stage"], "storyboard")

        combined = (self._protocol() + "\n" + read_text(self.artifact_path)).lower()
        for token in (
            "`checkpoint`",
            "`approval_attempt`",
            "第 1 次批准问题",
            "`<checkpoint>-approval-<n>`",
            "不得覆盖此前修订事件",
            "沿用同一规范性转移",
        ):
            self.assertIn(token.lower(), combined, f"再次批准 ID 规则缺少 {token}")

    def test_review_cycle_reset_allows_re_review_after_round_three_approval_only(self):
        payload = json.loads(read_text(self.fixture_root / "review-cycle-reset.json"))
        before = payload["before_revision"]
        after = payload["after_material_revision"]
        before_review = before["manuscript_review"]
        after_review = after["manuscript_review"]

        self.assertEqual(before_review["cycle"], 1)
        self.assertEqual(before_review["round"], 3)
        self.assertEqual(before_review["state"], "manuscript_approved")
        self.assertEqual(after_review["cycle"], 2)
        self.assertEqual(after_review["round"], 0)
        self.assertEqual(after_review["state"], "pending")
        self.assertEqual(after_review["review_history"], before_review["review_history"])
        self.assertTrue(after["dirty_slides"])

        combined = "\n".join(
            (
                read_text(self.artifact_path),
                read_text(self.review_path),
                read_text(self.qa_path),
            )
        ).lower()
        for token in (
            "`cycle` 是可选",
            "缺少时按 `1`",
            "每个审查周期最多三轮",
            "此前状态必须是 `manuscript_approved`",
            "`cycle` 加一",
            "`round: 0`",
            "`manuscript_blocked`",
            "不得开启新周期",
        ):
            self.assertIn(token.lower(), combined, f"审查周期规则缺少 {token}")

    def test_interaction_history_is_canonical_and_survives_invalidation(self):
        artifact = read_text(self.artifact_path).lower()
        for token in (
            "可选 `interaction_history`",
            "权威交互历史",
            "不得因阶段产物失效",
            "artifact_snapshot_id",
            "clarification_index",
            "阶段产物镜像",
        ):
            self.assertIn(token.lower(), artifact, f"权威交互历史缺少 {token}")

        payload = json.loads(read_text(self.fixture_root / "interaction-transition-cases.json"))
        cases = {case["name"]: case for case in payload["cases"]}
        for case in cases.values():
            committed = case["committed_run"]
            self.assertIn("interaction_history", committed)

        clarification = cases["outline-revision-needs-clarification"]
        record = clarification["committed_run"]["interaction_history"]["outline-approval"]
        self.assertEqual(record["clarification_index"], 1)
        self.assertTrue(
            clarification["committed_run"]["pending_interaction"]["id"].endswith(
                f"-{record['clarification_index']}"
            )
        )

        upstream = cases["anchor-claim-revision"]
        self.assertEqual(
            upstream["canonical_record_owner"],
            "run.json.interaction_history.anchor-approval",
        )
        self.assertIn("anchor-approval", upstream["committed_run"]["interaction_history"])
        self.assertTrue(upstream["committed_run"]["dirty_slides"])

    def test_direct_visual_revisions_are_durable_and_precedence_aware(self):
        artifact = read_text(self.artifact_path).lower()
        protocol = self._protocol().lower()
        design = read_text(self.reference_root / "design-system.md").lower()
        combined = "\n".join((artifact, protocol, design))
        for token in (
            "visual-revision-<n>",
            "kind: visual_revision",
            "normalized_changes",
            "affected_scope",
            "supersedes",
            "theme.json.user_revision_notes",
            "visual-briefs/<slide-id>.md",
            "废弃规则",
            "冲突",
        ):
            self.assertIn(token, combined)

    def test_normative_tables_pair_approvals_reentry_and_revision_owners(self):
        protocol_rows = self._markdown_table_rows(self._protocol())
        artifact_rows = self._markdown_table_rows(read_text(self.artifact_path))

        approval_rows = {
            ("brief-approval", "brief", "approve", "research"),
            ("outline-approval", "outline", "approve", "storyboard"),
            ("anchor-approval", "anchor", "approve", "production"),
        }
        for expected in approval_rows:
            self.assertTrue(
                any(row[:4] == expected for row in protocol_rows),
                f"批准转移表缺少 {expected}",
            )

        reentry_rows = {
            ("brief", "brief", "pending"),
            ("claim_or_source", "research", "pending"),
            ("outline", "outline", "pending"),
            ("storyboard", "storyboard", "pending"),
            ("theme", "theme", "preserve"),
            ("anchor_only", "anchor", "preserve"),
        }
        for expected in reentry_rows:
            self.assertTrue(
                any(row[:3] == expected for row in artifact_rows),
                f"失效重入表缺少 {expected}",
            )

        owner_tokens = {
            "brief": "简报.md",
            "outline": "大纲.md",
            "anchor": "theme.json.user_revision_notes",
        }
        for stage, owner in owner_tokens.items():
            self.assertTrue(
                any(len(row) >= 2 and row[0] == stage and owner in row[1] for row in artifact_rows),
                f"修订记录所有者缺少 {stage} -> {owner}",
            )

    def test_transition_fixtures_model_answered_atomic_commit_and_recovery(self):
        transition_path = self.fixture_root / "interaction-transition-cases.json"
        payload = json.loads(read_text(transition_path))
        self.assertEqual(payload["schema_version"], 1)
        cases = {case["name"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "outline-approve",
                "outline-revision-needs-clarification",
                "anchor-claim-revision",
            },
        )

        for case in cases.values():
            answered = case["answered_run"]
            interaction = answered["pending_interaction"]
            self.assertEqual(answered["schema_version"], 1)
            self.assertIn(answered["mode"], {"guided", "auto"})
            self.assertEqual(interaction["status"], "answered")
            self.assertEqual(interaction["stage"], answered["stage"])
            self.assertTrue(interaction["answer"].strip())
            self.assertIn(interaction["decision"], interaction["options"])
            if interaction["kind"] == "approval":
                self.assertEqual(interaction["checkpoint"], interaction["stage"])
                self.assertGreaterEqual(interaction["approval_attempt"], 1)
            self.assertEqual(set(interaction["option_effects"]), set(interaction["options"]))
            self.assertIn(interaction["recommendation"], interaction["options"])
            self.assertTrue(interaction["recommendation_reason"].strip())

            committed = case["committed_run"]
            self.assertEqual(committed["schema_version"], 1)
            if "pending_interaction" in committed:
                replacement = committed["pending_interaction"]
                self.assertEqual(replacement["status"], "pending")
                self.assertEqual(replacement["stage"], committed["stage"])
                self.assertIn("revision-clarification", replacement["id"])
                self.assertNotIn("answer", replacement)
                self.assertNotIn("decision", replacement)

        approved = cases["outline-approve"]
        self.assertEqual(approved["answered_run"]["stage"], "outline")
        self.assertEqual(approved["committed_run"]["stage"], "storyboard")
        self.assertNotIn("pending_interaction", approved["committed_run"])

        clarification = cases["outline-revision-needs-clarification"]
        self.assertEqual(clarification["committed_run"]["stage"], "outline")
        self.assertEqual(clarification["revision_record"]["status"], "clarification_pending")

        upstream = cases["anchor-claim-revision"]
        self.assertEqual(upstream["answered_run"]["stage"], "anchor")
        self.assertEqual(upstream["committed_run"]["stage"], "research")
        self.assertEqual(upstream["committed_run"]["manuscript_review"]["cycle"], 2)
        self.assertEqual(upstream["committed_run"]["manuscript_review"]["round"], 0)
        self.assertEqual(upstream["committed_run"]["manuscript_review"]["state"], "pending")
        self.assertEqual(upstream["committed_run"]["manuscript_review"]["status"], "PENDING")
        self.assertTrue(upstream["committed_run"]["dirty_slides"])
        self.assertNotIn("pending_interaction", upstream["committed_run"])

        history = upstream["committed_run"]["manuscript_review"]["review_history"]
        self.assertTrue(history)
        required_history_fields = {
            "cycle",
            "round",
            "reviewer_id",
            "reviewer_context",
            "delegation_evidence",
            "reviewed_file_snapshot",
            "findings",
            "author_revision_notes",
        }
        for entry in history:
            self.assertTrue(required_history_fields.issubset(entry))
            evidence = entry["delegation_evidence"]
            self.assertTrue(evidence["child_context_id"])
            self.assertTrue(evidence["completion_event_id"])
            self.assertEqual(evidence["child_context_id"], evidence["result_context_id"])
            self.assertEqual(
                set(entry["reviewed_file_snapshot"]["files"]),
                {"简报.md", "研究.md", "来源.md", "大纲.md", "故事板.md"},
            )

        combined = (self._protocol() + "\n" + read_text(self.artifact_path)).lower()
        for token in (
            "单次原子替换",
            "原阶段仍与 `pending_interaction.stage` 一致",
            "规范化 `decision`",
            "幂等",
        ):
            self.assertIn(token.lower(), combined, f"崩溃恢复契约缺少 {token}")

    def test_finite_choice_replay_metadata_and_nested_legacy_report_path(self):
        artifact = read_text(self.artifact_path).lower()
        for token in (
            "option_effects",
            "recommendation_reason",
            "规范化",
            "decision",
            "必须是 `options` 中的值",
        ):
            self.assertIn(token.lower(), artifact, f"有限选择持久字段缺少 {token}")

        readme = read_text(repo_root() / "README.md")
        self.assertIn("run.json.manuscript_review.latest_report", readme)
        self.assertNotRegex(readme, r"`run\.json\.latest_report`")

    def test_user_docs_and_acceptance_expose_the_same_protocol(self):
        readme = read_text(repo_root() / "README.md").lower()
        for token in (
            "未显式指定策略",
            "默认 `guided`",
            "只有显式",
            "一次只",
            "推荐不是确认",
            "pending_interaction",
        ):
            self.assertIn(token.lower(), readme, f"README.md 缺少 {token}")

        design = read_text(repo_root() / "docs" / "design.md").lower()
        for token in (
            "决策队列",
            "schema_version: 1",
            "pending_interaction",
            "跨宿主",
        ):
            self.assertIn(token.lower(), design, f"docs/design.md 缺少 {token}")

        acceptance = read_text(repo_root() / "docs" / "acceptance.md")
        acceptance_lower = acceptance.lower()
        for token in (
            "resume-pending-interaction.md",
            "直接问题",
            "一次只提出一个实质性问题",
            "明确回答",
            "pending_interaction",
            "不得推进下游",
            "安全默认值",
            "用户权限",
        ):
            self.assertIn(token.lower(), acceptance_lower, f"docs/acceptance.md 缺少 {token}")
        self.assertRegex(
            acceptance,
            r"\| 待回答恢复 \| Claude Code \|[^\n]*\| PENDING \|",
        )
        self.assertRegex(
            acceptance,
            r"\| 待回答恢复 \| Codex \|[^\n]*\| PENDING \|",
        )

    def test_behavior_prompts_cover_guided_auto_and_pending_resume(self):
        guided = read_text(self.prompt_root / "guided-topic-only.md").lower()
        for token in (
            "mode is omitted",
            "defaults to `guided`",
            "one substantive question",
            "explicit approval",
            "do not ask again",
            "no downstream",
        ):
            self.assertIn(token, guided)

        source = read_text(self.prompt_root / "source-driven.md").lower()
        for token in (
            "auto-mode",
            "do not ask optional",
            "safe defaults",
            "user authority",
        ):
            self.assertIn(token, source)

        resume = read_text(self.prompt_root / "resume-pending-interaction.md").lower()
        for token in (
            "run-pending-interaction.json",
            "read run.json first",
            "same pending question",
            "do not ask a new question",
            "do not repeat",
            "status: answered",
            "remove pending_interaction",
        ):
            self.assertIn(token, resume)


if __name__ == "__main__":
    unittest.main()
