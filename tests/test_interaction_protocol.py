import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import read_text, repo_root, skill_root  # noqa: E402


class InteractionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.root = skill_root()
        self.protocol = self.root / "references" / "interaction-protocol.md"
        self.state = self.root / "references" / "ai-state.md"
        self.workflow = self.root / "references" / "workflow.md"

    def _text(self):
        return read_text(self.protocol)

    def test_protocol_is_host_neutral_and_does_not_name_a_command_runner(self):
        text = self._text()
        for token in (
            "AskUserQuestion",
            "SendMessage",
            "mcp__",
            "/ppt-start",
            "$ppt-start",
            "ppt_runtime.py",
            "ppt_entry.py",
            "--skip-slide",
            "advance --allow-partial",
            "revise-visual",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_guided_auto_and_direct_answer_application_are_explicit(self):
        text = self._text()
        for token in (
            "guided",
            "auto",
            "简报",
            "大纲",
            "锚点",
            "status: pending",
            "status: answered",
            "interaction_history",
            "原始回答",
            "规范化决定",
            "幂等",
            "最早可执行动作",
        ):
            self.assertIn(token, text)
        self.assertIn("AI 直接完成以下单次状态迁移", text)
        self.assertIn("不调用回答命令", text)

    def test_skip_and_retry_preserve_attempt_rules(self):
        text = self._text()
        self.assertIn("skip", text)
        self.assertIn("attempts 不变", text)
        self.assertIn("再次调用 generator", text)
        self.assertIn("最多一次", read_text(self.root / "references" / "qa-and-revision.md"))
        self.assertIn("不得重建运行", read_text(self.state))

    def test_pending_example_is_minimal_but_replayable(self):
        pending = {
            "id": "anchor-approval",
            "stage": "anchor",
            "kind": "question",
            "question": "Approve anchor?",
            "status": "pending",
            "options": ["approve", "request_revision"],
            "option_effects": {
                "approve": "enter production",
                "request_revision": "stay at anchor",
            },
            "recommendation": "approve",
            "recommendation_reason": "checks passed",
            "checkpoint": "anchor",
            "approval_attempt": 1,
        }
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(set(pending["options"]), set(pending["option_effects"]))
        answered = dict(pending, status="answered", answer="approve", decision="approve")
        self.assertEqual(answered["answer"], "approve")
        self.assertEqual(answered["decision"], "approve")
        self.assertEqual(json.loads(json.dumps(answered))["id"], "anchor-approval")

    def test_workflow_keeps_stage_order_without_a_pause_stage(self):
        workflow = read_text(self.workflow)
        self.assertIn(
            "brief → research → outline → storyboard → manuscript_review → theme → anchor → production → qa → complete|partial|failed",
            workflow,
        )
        self.assertIn("pending_interaction", workflow)
        self.assertIn("不启动后台任务、轮询或隐藏并发", workflow)
        self.assertNotIn("可并发", workflow)
        self.assertNotIn("paused", workflow)
        self.assertNotIn("active_visual_generation_batch", workflow)


if __name__ == "__main__":
    unittest.main()
