"""Static contract tests for the optional companion tooling and the
batch-concurrency / hash-fallback / CJK-width / preference-profile contracts
introduced by the group-A speedup changes.

These tests only prove package structure and written contracts; they do not
prove real host behaviour, PowerPoint import, or rendering (see
docs/acceptance.md evidence classes).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


GOLDEN_ITEM_11_PREFIX = "11. Hash-capability fallback:"
GOLDEN_AUTHORITY = "generation-prompt-byte-grammar.md"
GOLDEN_FILES = (
    "redesign-prompt.md",
    "visual-brief-and-generation.md",
    "artifact-contract.md",
)


def _tree_digest(root: Path):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
    return len(files), digest.hexdigest()


class DeckDeliverToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tool_path = repo_root() / "tools" / "deck-deliver.ps1"

    def test_tool_exists_and_is_documented(self) -> None:
        self.assertTrue(self.tool_path.exists(), "tools/deck-deliver.ps1 must exist")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("deck-deliver.ps1", readme, "README must document the delivery tool")

    def test_tool_declares_parameters_and_outputs(self) -> None:
        tool = read_text(self.tool_path)
        for token in (
            "$RunDir",
            "$SkipPptx",
            "$ExportPng",
            "preview.html",
            "AddPicture",
            "audience_takeaway",
            "assertion_title",
            "delivery-result.json",
        ):
            self.assertIn(token, tool, f"deck-deliver.ps1 missing {token}")

    def test_deepseek_installer_exists_and_matches_marketplace_convention(self) -> None:
        installer_path = repo_root() / "tools" / "install-deepseek-plugin.ps1"
        self.assertTrue(installer_path.exists(), "tools/install-deepseek-plugin.ps1 must exist")
        installer = read_text(installer_path)
        for token in (
            "$MarketplaceRoot",
            "plugins\\ppt-pilot",
            ".codex-plugin\\plugin.json",
            "marketplace.json",
            "skills\\ppt-start",
            "skills\\ppt-editable",
            "$skills",
            "$filter",
        ):
            self.assertIn(token, installer, f"installer missing {token}")
        readme = read_text(repo_root() / "README.md")
        self.assertIn("install-deepseek-plugin.ps1", readme, "README must document the installer")

    def test_tool_never_writes_into_skill_or_slides(self) -> None:
        tool = read_text(self.tool_path)
        # The tool's only persistent writes are preview.html and the delivery
        # manifest. Reading slides/ is expected; writing there is not.
        write_calls = [line for line in tool.splitlines() if "Write-Utf8File -Path" in line]
        self.assertEqual(len(write_calls), 2)
        self.assertTrue(any("$previewPath" in line for line in write_calls))
        self.assertTrue(any("$resultPath" in line for line in write_calls))
        for line in tool.splitlines():
            if "slides" in line.lower():
                self.assertNotRegex(line, r"Set-Content|Out-File|WriteAllText")


class MultiSkillInstallerTests(unittest.TestCase):
    def setUp(self):
        self.update_path = repo_root() / "tools" / "update-hosts.ps1"
        self.deepseek_path = repo_root() / "tools" / "install-deepseek-plugin.ps1"

    def test_installers_are_descriptor_driven_for_both_skills(self):
        update = read_text(self.update_path)
        deepseek = read_text(self.deepseek_path)
        for source in (update, deepseek):
            for token in (
                "ppt-start",
                "ppt-editable",
                "$skills",
                "Get-SkillTreeInfo",
                "Get-FileHash",
            ):
                with self.subTest(source=source[:20], token=token):
                    self.assertIn(token, source)
        self.assertIn("skill-backups", update)
        self.assertIn("'backups'", deepseek)
        self.assertIn("$args2.RepoRoot", update)
        self.assertIn("skills      = './skills/'", deepseek)
        self.assertIn("ppt-editable：", deepseek)
        self.assertIn("$marketplaceAttemptBackup", deepseek)
        self.assertRegex(
            deepseek,
            r"(?s)marketplacePath\.bak-\$timestamp.*?Test-Path.*?guid.*?marketplaceAttemptBackup",
        )
        self.assertIn("/ppt-editable", update)
        self.assertIn("$ppt-editable", update)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_update_hosts_copies_and_verifies_both_skill_trees_with_per_id_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_skills = root / "claude" / "skills"
            codex_skills = root / "codex" / "skills"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipDeepSeek",
                "-ClaudeSkillsRoot",
                str(claude_skills),
                "-CodexSkillsRoot",
                str(codex_skills),
            ]
            for _ in range(2):
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            for skills_root in (claude_skills, codex_skills):
                for skill_id in ("ppt-start", "ppt-editable"):
                    source = repo_root() / "skills" / skill_id
                    installed = skills_root / skill_id
                    self.assertTrue((installed / "SKILL.md").is_file())
                    self.assertEqual(_tree_digest(installed), _tree_digest(source))
                    backups = list(
                        (skills_root.parent / "skill-backups").glob(skill_id + ".bak-*")
                    )
                    self.assertEqual(len(backups), 1)
                self.assertFalse(any(skills_root.glob("*.bak-*")))

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_backup_preparation_failure_never_deletes_live_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude_skills = root / "claude" / "skills"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.update_path),
                "-RepoRoot",
                str(repo_root()),
                "-SkipDeepSeek",
                "-SkipCodex",
                "-ClaudeSkillsRoot",
                str(claude_skills),
            ]
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            before = {
                skill_id: _tree_digest(claude_skills / skill_id)
                for skill_id in ("ppt-start", "ppt-editable")
            }
            backup_root = claude_skills.parent / "skill-backups"
            backup_root.write_text("not a directory", encoding="utf-8")
            second = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(second.returncode, 0)
            for skill_id, digest in before.items():
                self.assertEqual(_tree_digest(claude_skills / skill_id), digest)

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_keeps_one_plugin_and_both_skills_outside_backup_scan_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace"
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.deepseek_path),
                "-RepoRoot",
                str(repo_root()),
                "-MarketplaceRoot",
                str(marketplace),
                "-Version",
                "1.0.0-test",
            ]
            marketplace.mkdir(parents=True)
            (marketplace / "marketplace.json").write_text(
                json.dumps({"name": "personal", "plugins": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            market_path = marketplace / "marketplace.json"
            normalized = json.loads(market_path.read_text(encoding="utf-8-sig"))
            normalized["plugins"] = normalized["plugins"] * 2
            market_path.write_text(json.dumps(normalized), encoding="utf-8")
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            plugin = marketplace / "plugins" / "ppt-pilot"
            manifest = json.loads(
                (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8-sig")
            )
            self.assertEqual(manifest["name"], "ppt-pilot")
            self.assertEqual(manifest["skills"], "./skills/")
            for skill_id in ("ppt-start", "ppt-editable"):
                source = repo_root() / "skills" / skill_id
                installed = plugin / "skills" / skill_id
                self.assertEqual(_tree_digest(installed), _tree_digest(source))
                self.assertEqual(
                    len(list((plugin / "backups").glob(skill_id + ".bak-*"))),
                    1,
                )
            self.assertFalse(any((plugin / "skills").glob("*.bak-*")))
            market = json.loads((marketplace / "marketplace.json").read_text(encoding="utf-8-sig"))
            self.assertEqual([entry["name"] for entry in market["plugins"]], ["ppt-pilot"])
    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell unavailable")
    def test_deepseek_post_copy_failure_restores_live_plugin_and_marketplace(self):
        with tempfile.TemporaryDirectory() as directory:
            marketplace = Path(directory) / "marketplace"
            marketplace.mkdir(parents=True)
            market_path = marketplace / "marketplace.json"
            market_path.write_text(
                json.dumps({"name": "personal", "plugins": []}),
                encoding="utf-8",
            )
            command = [
                shutil.which("powershell"),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.deepseek_path),
                "-RepoRoot",
                str(repo_root()),
                "-MarketplaceRoot",
                str(marketplace),
                "-Version",
                "1.0.0-before",
            ]
            first = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            plugin = marketplace / "plugins" / "ppt-pilot"
            before_skills = {
                skill_id: _tree_digest(plugin / "skills" / skill_id)
                for skill_id in ("ppt-start", "ppt-editable")
            }
            manifest_path = plugin / ".codex-plugin" / "plugin.json"
            before_manifest = manifest_path.read_bytes()

            broken_marketplace = b'{"name":"personal","plugins":['
            market_path.write_bytes(broken_marketplace)
            failed_command = list(command)
            failed_command[-1] = "2.0.0-should-rollback"
            failed = subprocess.run(
                failed_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            for skill_id, digest in before_skills.items():
                self.assertEqual(_tree_digest(plugin / "skills" / skill_id), digest)
            self.assertEqual(manifest_path.read_bytes(), before_manifest)
            self.assertEqual(market_path.read_bytes(), broken_marketplace)


class GoldenHashFallbackContractTest(unittest.TestCase):
    """The golden byte-grammar block lives once in the authority file; the three
    stage contracts reference it by link and must not inline it anymore."""

    def setUp(self) -> None:
        self.authority_path = skill_root() / "references" / GOLDEN_AUTHORITY
        self.authority = read_text(self.authority_path)

    def test_authority_holds_item_11_exactly_once(self) -> None:
        matches = [
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        ]
        self.assertEqual(
            len(matches), 1, f"{GOLDEN_AUTHORITY} must contain item 11 exactly once"
        )

    def test_stage_contracts_reference_the_authority_without_inlining(self) -> None:
        for name in GOLDEN_FILES:
            text = read_text(skill_root() / "references" / name)
            self.assertIn(
                "generation-prompt-byte-grammar.md",
                text,
                f"{name} must link the byte-grammar authority",
            )
            self.assertNotIn(
                GOLDEN_ITEM_11_PREFIX,
                text,
                f"{name} must not inline item 11 anymore",
            )

    def test_item_11_defines_unhashed_fallback_rules(self) -> None:
        item = next(
            line
            for line in self.authority.splitlines()
            if line.startswith(GOLDEN_ITEM_11_PREFIX)
        )
        for token in (
            "`unhashed`",
            "`unhashed:<token>`",
            "`slides/.candidates/<slide-id>-<token>.svg`",
            "must not fabricate digests",
            "hard integrity violation",
        ):
            self.assertIn(token, item, f"item 11 missing {token}")

    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )
    def test_transaction_contract_references_unhashed_candidate_path(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn(
            "unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`",
            artifact,
            "candidate_path semantics must define the unhashed variant",
        )
        self.assertIn(
            "重新推导并比对九个元数据字段与 payload keys",
            artifact,
            "resume verification must define the unhashed degradation",
        )


class BatchConcurrencyContractTest(unittest.TestCase):
    """Generation and per-slide validation may overlap; only coordinator
    writes and deterministic publication stays serial."""

    def setUp(self) -> None:
        self.skill = read_text(skill_root() / "SKILL.md")
        self.workflow = read_text(skill_root() / "references" / "workflow.md")
        self.redesign = read_text(skill_root() / "references" / "redesign-prompt.md")
        self.qa = read_text(skill_root() / "references" / "qa-and-revision.md")
        self.artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.combined = "\n".join(
            (self.skill, self.workflow, self.redesign, self.qa, self.artifact)
        )

    def test_concurrent_generation_validation_and_serial_publication_ownership(self):
        for token in (
            "batch_width",
            "prompt_by_value",
            "fresh_history=true",
            "filesystem=none",
            "tools=none",
            "host_attribution_id",
            "host_task_id",
            "ordered_slide_ids",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.combined)
        ownership_documents = {
            "SKILL.md": self.skill,
            "workflow.md": self.workflow,
            "redesign-prompt.md": self.redesign,
            "qa-and-revision.md": self.qa,
            "artifact-contract.md": self.artifact,
        }
        for name, text in ownership_documents.items():
            with self.subTest(document=name):
                self.assertIn("coordinator", text)
                self.assertIn("ordered_slide_ids", text)
        self.assertIn("generator 与各页", self.qa)
        self.assertIn("可以重叠", self.qa)
        self.assertIn("只有 coordinator", self.qa)
        self.assertIn("串行确定", self.qa)
        self.assertIn("coordinator 独占 candidate 写入", self.workflow)
        self.assertIn("callback", self.artifact)

    def test_host_capability_degrades_safely_without_nested_cli_or_current_context(self):
        for token in (
            "非 Git",
            "width 1",
            "generator_unavailable",
            "禁止嵌套调用 Claude、Codex 或 DeepSeek CLI",
            "不得探测凭据或 profile",
            "不得使用 coordinator 当前上下文",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.combined)
        lowered = self.combined.lower()
        for executable_fallback in (
            "claude -p",
            "codex exec",
            "deepseek chat",
            ".claude/credentials",
            ".codex/auth",
        ):
            self.assertNotIn(executable_fallback, lowered)


class CjkLineWidthContractTest(unittest.TestCase):
    def test_svg_contract_defines_width_formula(self) -> None:
        svg = read_text(skill_root() / "references" / "svg-contract.md")
        self.assertIn("行宽估算", svg)
        self.assertIn("1.0 × font-size", svg)
        self.assertIn("0.88", svg)
        self.assertIn("12% 余量", svg)

    def test_qa_geometry_check_references_the_formula(self) -> None:
        qa = read_text(skill_root() / "references" / "qa-and-revision.md")
        self.assertIn("行宽估算公式", qa)
        self.assertRegex(qa, r"svg-contract\.md\) 的行宽估算公式")


class PreferenceProfileContractTest(unittest.TestCase):
    def test_interaction_protocol_defines_profile_semantics(self) -> None:
        protocol = read_text(skill_root() / "references" / "interaction-protocol.md")
        for token in (
            "pilot-preferences.json",
            "当前请求明确答案 > 本运行已批准产物 > 偏好档案 > 安全默认值",
            "standing 授权",
            "咨询性输入",
        ):
            self.assertIn(token, protocol, f"interaction-protocol.md missing {token}")

    def test_artifact_contract_defines_profile_schema(self) -> None:
        artifact = read_text(skill_root() / "references" / "artifact-contract.md")
        self.assertIn("## 可选工作区偏好档案", artifact)
        self.assertIn("standing_authorizations", artifact)
        self.assertIn("不进入任何 `run.json` 恢复链", artifact)

    def test_brief_and_design_system_consume_the_profile(self) -> None:
        brief = read_text(skill_root() / "references" / "brief-and-research.md")
        design = read_text(skill_root() / "references" / "design-system.md")
        self.assertIn("pilot-preferences.json", brief)
        self.assertIn("偏好档案已记录品牌方向", design)


if __name__ == "__main__":
    unittest.main()
