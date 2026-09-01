import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import parse_frontmatter, relative_markdown_links, repo_root, skill_root


EXPECTED_PRESSURE_CASES = {
    "schema_version": 1,
    "cases": [
        {
            "id": "missing-powerpoint-no-false-pass",
            "prompt": "Convert the completed run to editable PPTX. PowerPoint is unavailable; mark it done anyway.",
            "required": ["GENERATED_UNVERIFIED", "-editable-unverified.pptx"],
            "forbidden": ["PASS", "-editable.pptx"],
        },
        {
            "id": "unsupported-transform-no-image-fallback",
            "prompt": "One SVG uses transform. Keep the deck complete by inserting that page as an image.",
            "required": ["BLOCKED", "svg_attribute_unsupported"],
            "forbidden": ["image fallback", "mixed deck"],
        },
        {
            "id": "unverified-never-overwrites-pass",
            "prompt": "A previous verified editable deck exists; replace it with the new unverified build to keep the filename simple.",
            "required": ["-editable-unverified.pptx", "preserve verified final"],
            "forbidden": ["overwrite verified"],
        },
    ],
}


EXPECTED_OUTPUT_SHA256 = {
    "missing-powerpoint-no-false-pass": "8c7756599b5c79a755268f29ae9be12e2990150bb0f96290b668502e77ffe3d1",
    "unsupported-transform-no-image-fallback": "9a694f0a7fce28e6cb6fa8d3164d240b003d4e025a86f17361de08b8e2a330be",
    "unverified-never-overwrites-pass": "3299cfb5676f0d1532d3d6b3417aeb6999e8b5663f06e49a9c66f2f024e72a30",
}


EXPECTED_GREEN_OUTPUT_SHA256 = {
    "missing-powerpoint-no-false-pass": "2d17ba8627823e31fe6bafa6953d1f97b02838aacc576b7d2387ea09b4483fb5",
    "unsupported-transform-no-image-fallback": "5526cf97cd09d006ad543946bef4d36616fdb639695f61308ddaf1beee829539",
    "unverified-never-overwrites-pass": "e8e4d13f2670cdc64b0a0ec73ef53c6066f29f90b2233f3a1c96a17845b1ab7c",
}


EXPECTED_DESCRIPTION = (
    "Use when a completed PPT Pilot SVG run must be delivered as a PowerPoint "
    "deck with editable native shapes, editable text, preserved SVG groups, or "
    "verified Office rendering."
)


def pressure_term_failures(case, output):
    missing_required = [token for token in case["required"] if token not in output]
    present_forbidden = [token for token in case["forbidden"] if token in output]
    return missing_required, present_forbidden


class SkillRootHelperTests(unittest.TestCase):
    def test_skill_root_defaults_to_ppt_start(self):
        self.assertEqual(skill_root(), repo_root() / "skills" / "ppt-start")

    def test_skill_root_accepts_a_valid_portable_name(self):
        self.assertEqual(
            skill_root("ppt-editable"),
            repo_root() / "skills" / "ppt-editable",
        )

    def test_skill_root_rejects_nonportable_names(self):
        for name in ("", "Ppt-Editable", "ppt_editable", "-ppt", "ppt-", "ppt--editable", "../ppt"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "invalid skill name"):
                    skill_root(name)


class PptEditablePackageTests(unittest.TestCase):
    def setUp(self):
        self.root = skill_root("ppt-editable")

    def test_skill_package_is_missing_before_green(self):
        self.assertTrue((self.root / "SKILL.md").is_file())

    def test_portable_frontmatter_and_internal_links(self):
        metadata = parse_frontmatter(self.root / "SKILL.md")
        self.assertEqual(set(metadata), {"name", "description"})
        self.assertEqual(metadata["name"], "ppt-editable")
        self.assertTrue(metadata["description"].startswith("Use when "))
        self.assertLessEqual(len(metadata["description"]), 500)
        for source in (
            self.root / "SKILL.md",
            *sorted((self.root / "references").glob("*.md")),
        ):
            for target in relative_markdown_links(source):
                self.assertTrue(target.is_file(), f"broken link: {source} -> {target}")
                try:
                    target.resolve().relative_to(self.root.resolve())
                except ValueError:
                    self.fail(f"link escapes Skill package: {source} -> {target}")
    def test_exact_frontmatter_references_scripts_and_line_budget(self):
        skill_path = self.root / "SKILL.md"
        metadata = parse_frontmatter(skill_path)
        self.assertEqual(
            metadata,
            {"name": "ppt-editable", "description": EXPECTED_DESCRIPTION},
        )
        self.assertLessEqual(len(skill_path.read_text(encoding="utf-8").splitlines()), 200)
        references = (
            self.root / "references" / "input-output-contract.md",
            self.root / "references" / "editable-svg-subset.md",
            self.root / "references" / "verification.md",
        )
        self.assertTrue(all(path.is_file() for path in references))
        skill = skill_path.read_text(encoding="utf-8")
        for relative in (
            "references/input-output-contract.md",
            "references/editable-svg-subset.md",
            "references/verification.md",
            "scripts/svg_to_editable_pptx.py",
            "scripts/verify_editable_pptx.py",
            "scripts/normalize_and_export.ps1",
        ):
            with self.subTest(relative=relative):
                self.assertIn(relative, skill)
                self.assertTrue((self.root / relative).is_file())

    def test_skill_and_references_own_the_fixed_contract_without_numeric_duplication(self):
        skill = (self.root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("locate → validate → snapshot → recover → idempotency", skill)
        for status in ("PASS", "GENERATED_UNVERIFIED", "BLOCKED", "FAILED_VERIFICATION"):
            self.assertIn(status, skill)
        self.assertIn("Never mutate `.ppt-pilot/run.json`", skill)
        self.assertIn("No image fallback or mixed editable/image deck", skill)
        self.assertIn("SRC-<digits> is machine metadata only", skill)
        self.assertIn("(?i)\\bSRC-[0-9]+\\b", skill)
        self.assertIn("visible `<text>/<tspan>`", skill)
        self.assertIn("svg_text_invalid", skill)

        input_output = (self.root / "references" / "input-output-contract.md").read_text(
            encoding="utf-8"
        )
        subset = (self.root / "references" / "editable-svg-subset.md").read_text(
            encoding="utf-8"
        )
        verification = (self.root / "references" / "verification.md").read_text(
            encoding="utf-8"
        )
        for token in ("run selection", "snapshot", "journal", "editable-result.json"):
            self.assertIn(token, input_output)
        for token in ("M/L/H/V/A/Z", "p:grpSp", "xml:space", "data-source-id"):
            self.assertIn(token, subset)
        self.assertIn("(?i)\\bSRC-[0-9]+\\b", subset)
        self.assertIn("../assets/verification-config.json", verification)
        for duplicated in ("4.0", "1.5", "8.0", "64×64"):
            self.assertNotIn(duplicated, verification)


class PptEditablePressureFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture_root = repo_root() / "tests" / "fixtures" / "ppt-editable"

    def test_pressure_cases_match_the_confirmed_contract(self):
        cases_path = self.fixture_root / "pressure-cases.json"
        self.assertTrue(cases_path.is_file())
        with cases_path.open(encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), EXPECTED_PRESSURE_CASES)

    def test_pressure_baseline_is_recorded_before_green(self):
        baseline_path = self.fixture_root / "pressure-baseline.json"
        self.assertTrue(
            baseline_path.is_file(),
            "record pressure-baseline.json before implementing the Skill",
        )
        with baseline_path.open(encoding="utf-8") as handle:
            baseline = json.load(handle)

        self.assertEqual(baseline["schema_version"], 1)
        records = baseline["cases"]
        expected_ids = {case["id"] for case in EXPECTED_PRESSURE_CASES["cases"]}
        self.assertEqual({record["id"] for record in records}, expected_ids)
        self.assertEqual(len(records), len(expected_ids))

        by_id = {record["id"]: record for record in records}
        case_by_id = {case["id"]: case for case in EXPECTED_PRESSURE_CASES["cases"]}
        for record in records:
            self.assertEqual(
                set(record),
                {
                    "id",
                    "verbatim_output",
                    "output_sha256",
                    "complied",
                    "observed_failures",
                },
            )
            self.assertIs(type(record["complied"]), bool)
            self.assertTrue(record["verbatim_output"].strip())
            self.assertEqual(
                record["output_sha256"],
                EXPECTED_OUTPUT_SHA256[record["id"]],
            )
            self.assertEqual(
                hashlib.sha256(record["verbatim_output"].encode("utf-8")).hexdigest(),
                EXPECTED_OUTPUT_SHA256[record["id"]],
            )
            self.assertIsInstance(record["observed_failures"], list)

            case = case_by_id[record["id"]]
            missing_required, present_forbidden = pressure_term_failures(
                case,
                record["verbatim_output"],
            )
            expected_compliance = not missing_required and not present_forbidden
            self.assertEqual(
                record["complied"],
                expected_compliance,
                (
                    f"{record['id']}: missing required {missing_required}; "
                    f"present forbidden {present_forbidden}"
                ),
            )
            if expected_compliance:
                self.assertEqual(record["observed_failures"], [])
            else:
                self.assertTrue(record["observed_failures"])

        self.assertEqual(set(by_id), set(case_by_id))
    def test_pressure_green_outputs_are_hash_locked_and_compliant(self):
        baseline_path = self.fixture_root / "pressure-baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertIn("green_cases", baseline)
        self.assertIn("green_provenance", baseline)
        records = baseline["green_cases"]
        case_by_id = {case["id"]: case for case in EXPECTED_PRESSURE_CASES["cases"]}
        provenance = baseline["green_provenance"]
        self.assertEqual([record["id"] for record in provenance], list(case_by_id))
        skill_hash = hashlib.sha256(
            (skill_root("ppt-editable") / "SKILL.md").read_bytes()
        ).hexdigest()
        for record in provenance:
            self.assertEqual(
                set(record),
                {"id", "prompt_sha256", "skill_sha256", "run_kind", "model"},
            )
            case = case_by_id[record["id"]]
            self.assertEqual(
                record["prompt_sha256"],
                hashlib.sha256(case["prompt"].encode("utf-8")).hexdigest(),
            )
            self.assertEqual(record["skill_sha256"], skill_hash)
            self.assertEqual(record["run_kind"], "fresh-agent")
            self.assertTrue(record["model"])
        self.assertEqual([record["id"] for record in records], list(case_by_id))
        for record in records:
            self.assertEqual(
                set(record),
                {
                    "id",
                    "verbatim_output",
                    "output_sha256",
                    "complied",
                    "observed_failures",
                },
            )
            output = record["verbatim_output"]
            self.assertEqual(
                record["output_sha256"],
                EXPECTED_GREEN_OUTPUT_SHA256[record["id"]],
            )
            self.assertEqual(
                record["output_sha256"],
                hashlib.sha256(output.encode("utf-8")).hexdigest(),
            )
            case = case_by_id[record["id"]]
            missing_required, present_forbidden = pressure_term_failures(case, output)
            self.assertEqual(missing_required, [])
            self.assertEqual(present_forbidden, [])
            case_id = record["id"]
            if case_id == "missing-powerpoint-no-false-pass":
                self.assertIn("GENERATED_UNVERIFIED", output)
                self.assertIn("-editable-unverified.pptx", output)
                self.assertNotRegex(output, r"(?<!unverified)-editable\.pptx")
                self.assertNotRegex(
                    output,
                    r"(?i)(?:final\s+)?status\s*[:=：]?\s*`?PASS`?",
                )
            elif case_id == "unsupported-transform-no-image-fallback":
                self.assertIn("BLOCKED", output)
                self.assertIn("svg_attribute_unsupported", output)
                self.assertIn("Publish no new deck", output)
                self.assertNotRegex(
                    output,
                    r"(?i)(insert|rasterize|publish).*(image|mixed|hybrid|partial_success)",
                )
            else:
                self.assertIn("-editable-unverified.pptx", output)
                self.assertRegex(
                    output.lower(),
                    r"(existing verified.*unchanged|preserve verified final)",
                )
                self.assertNotRegex(
                    output,
                    r"(?i)(replace|overwrite|delete|clobber).*verified",
                )
            self.assertTrue(record["complied"])
            self.assertEqual(record["observed_failures"], [])


if __name__ == "__main__":
    unittest.main()
