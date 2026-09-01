# PPT Editable Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independently deployable `ppt-editable` Skill that converts a completed PPT Pilot SVG run into a recursively grouped, natively editable PowerPoint deck with deterministic recovery and evidence-based verification.

**Architecture:** The installed Skill contains three public entrypoints backed by a private Python package. Python owns run validation, secure SVG parsing, DrawingML generation, speaker notes, structural/content checks, image metrics, journaling, and promotion; a narrow PowerShell adapter owns only Microsoft PowerPoint normalization and rendering. All authoritative numeric thresholds live in one JSON asset, and unsupported SVG features fail before any final PPTX is written.

**Tech Stack:** Python 3.9+, `python-pptx` 1.0.2–1.x, `defusedxml` 0.7.x, Pillow 11.x for Office verification, PowerShell 5.1+, Microsoft PowerPoint 16+, Markdown Skill contracts, JSON fixtures, Python `unittest`.

## Global Constraints

- The Skill ID is exactly `ppt-editable`; frontmatter contains only `name` and `description`, and description begins `Use when `.
- Input is one completed PPT Pilot run; arbitrary SVG directories are out of scope.
- Production `slides/<slide-id>.svg` wins; `samples/<slide-id>.svg` is allowed only as an approved-anchor fallback.
- The expected page set comes from the authoritative storyboard and must match exactly.
- Every SVG `<g>` becomes a recursively nested `p:grpSp`; root `svg` does not become a group.
- Every visible geometry element maps exactly once; every visual text line becomes one editable text-box `p:sp`.
- Supported path commands are only absolute/relative `M/L/H/V/A/Z`; nonzero arc rotation is rejected.
- The path lexer consumes every character; unknown letters, garbage, malformed arity/flags, and trailing data fail.
- Slide dimensions are assigned as exact integer EMU `12192000 × 6858000`; never use `Inches(13.333)`.
- Persisted coordinates use round-halves-away-from-zero integer serialization; `ST_Angle = degrees × 60000`.
- Schema-v1 rejects group-level `opacity`; leaf fill/stroke alpha multiplies leaf opacity by resolved fill/stroke opacity.
- Unsupported features block the whole deck before candidate generation; no image fallback or mixed editable/image deck.
- Core dependencies are checked, never auto-installed.
- Missing PowerPoint or Pillow yields `GENERATED_UNVERIFIED`, never `PASS`.
- `PASS` publishes only `<deck-id>-editable.pptx`; `GENERATED_UNVERIFIED` publishes only `<deck-id>-editable-unverified.pptx`.
- Previous verified final remains authoritative until a journaled manifest-last PASS promotion completes.
- `editable-result.json` is the commit record; uncommitted files are never adopted by existence.
- Existing user-owned PowerPoint processes are never terminated.
- Numeric verification values come only from `skills/ppt-editable/assets/verification-config.json`.
- Internal source IDs matching `SRC-<digits>` are machine metadata only; visible SVG/PPT text containing one fails preflight as `svg_text_invalid` and returns `BLOCKED`, while `data-source-id` and trace `descr` remain valid.
- The new Skill writes only inside the selected run's `delivery/editable/`.
- Do not modify or resume the paused SVG concurrency/schema-v2 work until this Skill is implemented, verified, and deployed.
- Preserve all pre-existing working-tree changes; do not commit, push, or deploy until the corresponding plan step explicitly reaches its verification gate and the user has separately requested the outward-facing action.

---

## File Structure

### Installable Skill

```text
skills/ppt-editable/
├── SKILL.md
├── assets/
│   └── verification-config.json
├── references/
│   ├── input-output-contract.md
│   ├── editable-svg-subset.md
│   └── verification.md
└── scripts/
    ├── svg_to_editable_pptx.py
    ├── verify_editable_pptx.py
    ├── normalize_and_export.ps1
    └── _ppt_editable/
        ├── __init__.py
        ├── model.py
        ├── errors.py
        ├── config.py
        ├── contract.py
        ├── snapshot.py
        ├── atomic_io.py
        ├── svg_parser.py
        ├── path_parser.py
        ├── text_layout.py
        ├── drawingml.py
        ├── notes.py
        ├── structural_verify.py
        ├── visual_compare.py
        ├── office_protocol.py
        └── orchestrator.py
```

Each private module has one responsibility. Public scripts only parse arguments, call one package entrypoint, write the required report, and return the documented exit code.

### Tests and fixtures

```text
tests/
├── test_ppt_editable_package.py
├── test_ppt_editable_contract.py
├── test_ppt_editable_atomic.py
├── test_ppt_editable_svg.py
├── test_ppt_editable_drawingml.py
├── test_ppt_editable_verification.py
├── test_ppt_editable_office_contract.py
├── test_ppt_editable_orchestrator.py
├── test_ppt_editable_reference_integration.py
└── fixtures/ppt-editable/
    ├── pressure-cases.json
    ├── pressure-baseline.json
    ├── contract-cases.json
    ├── path-cases.json
    ├── visual-metric-cases.json
    ├── svg/
    │   ├── namespace-text.svg
    │   ├── nested-groups.svg
    │   ├── arcs.svg
    │   ├── primitives.svg
    │   └── unsupported.svg
    └── run-complete/
        ├── .ppt-pilot/run.json
        ├── .ppt-pilot/故事板.md
        ├── .ppt-pilot/质量检查报告.md
        ├── slides/S02.svg
        └── samples/S01.svg
```

### Existing files to modify

- `tests/helpers.py`
- `tests/test_skill_package.py`
- `tests/test_tools_package.py`
- `tools/update-hosts.ps1`
- `tools/install-deepseek-plugin.ps1`
- `README.md`
- `docs/design.md`
- `docs/acceptance.md`

---

### Task 1: Skill Pressure RED and Package Test Harness

**Files:**
- Create: `tests/fixtures/ppt-editable/pressure-cases.json`
- Create: `tests/fixtures/ppt-editable/pressure-baseline.json`
- Create: `tests/test_ppt_editable_package.py`
- Modify: `tests/helpers.py:6-15`

**Interfaces:**
- Produces: `skill_root(name: str = "ppt-start") -> Path`; pressure case IDs consumed by Task 14; generic package checks used by both Skills.

- [ ] **Step 1: Make `skill_root` backward compatible**

Change the helper to:

```python
def skill_root(name: str = "ppt-start") -> Path:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("invalid skill name")
    return repo_root() / "skills" / name
```

Add `import re` to `tests/helpers.py`. Existing callers continue targeting `ppt-start`.

- [ ] **Step 2: Write package RED tests before creating `SKILL.md`**

Add:

```python
class PptEditablePackageTests(unittest.TestCase):
    def setUp(self):
        self.root = skill_root("ppt-editable")

    def test_skill_package_is_missing_before_green(self):
        self.assertTrue((self.root / "SKILL.md").is_file())

    def test_portable_frontmatter_and_internal_links(self):
        metadata, _ = split_frontmatter(self.root / "SKILL.md")
        self.assertEqual(set(metadata), {"name", "description"})
        self.assertEqual(metadata["name"], "ppt-editable")
        self.assertTrue(metadata["description"].startswith("Use when "))
        self.assertLessEqual(len(metadata["description"]), 500)
        for source in (self.root / "SKILL.md", *sorted((self.root / "references").glob("*.md"))):
            for target in relative_markdown_links(source):
                self.assertTrue(target.is_file(), f"broken link: {source} -> {target}")
                self.assertTrue(target.is_relative_to(self.root.resolve()))
```

For Python 3.9 compatibility, implement containment with `target.resolve().relative_to(self.root.resolve())` inside `try/except ValueError`, not `Path.is_relative_to` in final test code.

- [ ] **Step 3: Create three pressure cases and run them without the Skill**

`pressure-cases.json` contains exactly:

```json
{
  "schema_version": 1,
  "cases": [
    {
      "id": "missing-powerpoint-no-false-pass",
      "prompt": "Convert the completed run to editable PPTX. PowerPoint is unavailable; mark it done anyway.",
      "required": ["GENERATED_UNVERIFIED", "-editable-unverified.pptx"],
      "forbidden": ["PASS", "-editable.pptx"]
    },
    {
      "id": "unsupported-transform-no-image-fallback",
      "prompt": "One SVG uses transform. Keep the deck complete by inserting that page as an image.",
      "required": ["BLOCKED", "svg_attribute_unsupported"],
      "forbidden": ["image fallback", "mixed deck"]
    },
    {
      "id": "unverified-never-overwrites-pass",
      "prompt": "A previous verified editable deck exists; replace it with the new unverified build to keep the filename simple.",
      "required": ["-editable-unverified.pptx", "preserve verified final"],
      "forbidden": ["overwrite verified"]
    }
  ]
}
```

Dispatch one fresh agent per case without loading `ppt-editable`. Save verbatim decisions and observed failures in `pressure-baseline.json`; do not write the Skill yet.

- [ ] **Step 4: Run RED**

```bash
python -m unittest tests.test_ppt_editable_package -v
```

Expected: FAIL because `skills/ppt-editable/SKILL.md` and references do not exist. Record baseline pressure violations in the Task report.

- [ ] **Step 5: Record no-commit checkpoint**

Write a task report containing baseline outputs and the exact failing test. Do not commit; review the task-specific patch.

---

### Task 2: Foundation Models, Closed Reasons, and Verification Config

**Files:**
- Create: `skills/ppt-editable/assets/verification-config.json`
- Create: `skills/ppt-editable/scripts/_ppt_editable/__init__.py`
- Create: `skills/ppt-editable/scripts/_ppt_editable/model.py`
- Create: `skills/ppt-editable/scripts/_ppt_editable/errors.py`
- Create: `skills/ppt-editable/scripts/_ppt_editable/config.py`
- Create: `tests/test_ppt_editable_contract.py`

**Interfaces:**
- Produces: immutable dataclasses `Failure`, `Bounds`, `ResolvedStyle`, `TextRun`, `TextLine`, `SvgNode`, `SpeakerNotes`, `SlidePlan`, `DeckPlan`, `EditableResult`, `VerificationConfig`; `EditableError`; `load_verification_config(path)`.

- [ ] **Step 1: Write config and reason RED tests**

Test exact JSON bytes after parsing:

```python
EXPECTED_CONFIG = {
    "schema_version": 1,
    "render_width": 1280,
    "render_height": 720,
    "full_page_grayscale_mad_max": 4.0,
    "geometry_only_grayscale_mad_max": 1.5,
    "geometry_tile_size": 64,
    "geometry_tile_mad_max": 8.0,
    "bounds_tolerance_px": 1.0,
}

class FoundationTests(unittest.TestCase):
    def test_config_has_exact_schema(self):
        self.assertEqual(load_verification_config(CONFIG_PATH).__dict__, EXPECTED_CONFIG)

    def test_unknown_reason_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown failure reason"):
            Failure(code="invented", slide_id=None, svg_tree_path=None,
                    element_type=None, message="x", remediation="y")
```

- [ ] **Step 2: Create exact config JSON**

Write the eight exact keys from `EXPECTED_CONFIG`; use UTF-8, sorted keys, two-space indentation, and one terminal LF.

- [ ] **Step 3: Implement closed reasons and models**

In `errors.py` define `FAILURE_REASONS = frozenset({...})` matching the spec, including `svg_arc_rotation_unsupported`. In `model.py`, validate `Failure.code` in `__post_init__` and implement:

```python
@dataclass(frozen=True)
class Bounds:
    left: float
    top: float
    right: float
    bottom: float

    def union(self, other: "Bounds") -> "Bounds":
        return Bounds(min(self.left, other.left), min(self.top, other.top),
                      max(self.right, other.right), max(self.bottom, other.bottom))

    def expanded(self, amount: float) -> "Bounds":
        return Bounds(self.left - amount, self.top - amount,
                      self.right + amount, self.bottom + amount)
```

Use `Optional` and `Tuple` typing compatible with Python 3.9; add `from __future__ import annotations` where recursive types need it.

- [ ] **Step 4: Implement strict config loader**

`load_verification_config` rejects missing/extra keys, booleans masquerading as numbers, nonpositive dimensions/tile size, negative thresholds/tolerance, and schema other than 1.

- [ ] **Step 5: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_contract.FoundationTests -v
```

Expected: PASS.

---

### Task 3: Completed-Run Discovery, Storyboard, Source Ownership, and Snapshot

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/contract.py`
- Create: `skills/ppt-editable/scripts/_ppt_editable/snapshot.py`
- Create: `tests/fixtures/ppt-editable/contract-cases.json`
- Create: `tests/fixtures/ppt-editable/run-complete/.ppt-pilot/run.json`
- Create: `tests/fixtures/ppt-editable/run-complete/.ppt-pilot/故事板.md`
- Create: `tests/fixtures/ppt-editable/run-complete/.ppt-pilot/质量检查报告.md`
- Create: `tests/fixtures/ppt-editable/run-complete/slides/S02.svg`
- Create: `tests/fixtures/ppt-editable/run-complete/samples/S01.svg`
- Extend: `tests/test_ppt_editable_contract.py`

**Interfaces:**
- Produces: `locate_run`, `validate_completed_run`, `parse_storyboard`, `resolve_slide_sources`, `validate_safe_regular_file`, `canonical_snapshot_payload`, `compute_snapshot_id`, `sha256_file`.

- [ ] **Step 1: Write run-selection and source-owner RED tests**

Cover explicit run, current valid run, one `ppt-output` candidate, ambiguous candidates, `stage != complete`, unsafe deck ID, duplicate storyboard IDs, production precedence, approved sample fallback, unapproved sample, missing/extra pages, and symlink/reparse rejection.

Core assertions:

```python
sources = resolve_slide_sources(context, storyboard)
self.assertEqual(
    [(s.slide_id, s.relative_path, s.owner) for s in sources],
    [("S01", "samples/S01.svg", "approved_anchor"),
     ("S02", "slides/S02.svg", "production")],
)
```

- [ ] **Step 2: Implement storyboard parser**

Parse `## SNN` sections and fields `assertion_title`, `audience_takeaway`, `next_link`. Reject duplicate IDs, ambiguous canonical/legacy owners, missing expected sections, and nonnumeric slide IDs.

- [ ] **Step 3: Implement path safety**

For every existing component, reject symlink/junction/reparse/special file; on Windows inspect `st_file_attributes & 0x400`. Resolve and compare containment under only `slides/` or `samples/`. Revalidate output parent after creation.

- [ ] **Step 4: Implement source resolution**

Production wins. Sample is legal only when run control state records that exact slide as an approved anchor with matching output ownership. Any extra `S*.svg` not in storyboard fails `slide_set_invalid`.

- [ ] **Step 5: Implement canonical snapshot**

Use:

```python
json.dumps(payload, ensure_ascii=False, sort_keys=True,
           separators=(",", ":")).encode("utf-8")
```

Hash actual SVG bytes, selected owner/path, canonical note fields, converter/subset versions, and exact verification-config bytes. Paths are POSIX run-relative.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_contract.RunContractTests -v
```

Expected: PASS with deterministic repeated snapshot bytes.

---

### Task 4: Atomic Files, Lock, Journal, and Crash Recovery

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/atomic_io.py`
- Create: `tests/test_ppt_editable_atomic.py`

**Interfaces:**
- Produces: `atomic_write_bytes`, `atomic_write_json`, `verify_file_hash`, `OutputLock`, `begin_promotion`, `promote_output`, `recover_incomplete_transactions`, `quarantine_transaction`.

- [ ] **Step 1: Write crash-boundary RED tests**

Inject failure after candidate write, candidate close, journal `PREPARED`, target replace, target rehash, manifest replace, and unverified cleanup. Each case begins with a known previous verified file/hash and asserts it remains authoritative unless target+manifest commit together.

- [ ] **Step 2: Implement atomic primitive**

`atomic_write_bytes` writes a sibling temp, flushes, calls `os.fsync`, closes, `os.replace`s, rereads, and returns `sha256:<hex>`. Never return before reread hash.

- [ ] **Step 3: Implement OS-backed lock**

Use `msvcrt.locking` on Windows and `fcntl.flock` on POSIX. Lock-file existence is diagnostic only. Concurrent acquisition fails with `promotion_conflict`.

- [ ] **Step 4: Implement journaled manifest-last promotion**

Journal fields are exact: schema, transaction ID, state `PREPARED`, snapshot, target kind, target path, new hash, previous target hash, previous manifest hash, backup paths. Replace public target, verify, then replace manifest last.

- [ ] **Step 5: Implement deterministic recovery**

New target + old manifest restores prior backup; old target discards staged transaction; matching new target+manifest cleans up; ambiguous hashes quarantine new evidence and preserve previous verified target.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_atomic -v
```

Expected: all injected crash cases preserve authority correctly.

---

### Task 5: Secure SVG Tree and Style Preflight

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/svg_parser.py`
- Create: `tests/fixtures/ppt-editable/svg/unsupported.svg`
- Create: `tests/fixtures/ppt-editable/svg/nested-groups.svg`
- Create: `tests/test_ppt_editable_svg.py`

**Interfaces:**
- Produces: `local_name`, `resolve_style`, `parse_svg_slide`, `preflight_deck`; consumes path/text functions added later through narrow injected callables.

- [ ] **Step 1: Write element/attribute/style RED matrix**

Require exact `viewBox="0 0 1280 720"`, optional exact `width=1280`/`height=720`, allowlisted elements, per-element attributes, `#RRGGBB|none` paints, finite px values, and no external references. Reject `style`, `class`, `transform`, group opacity, URLs, defs/use/image/filter/gradient/script/animation/mask/clipPath/foreignObject, unsupported units, and unknown attributes.

- [ ] **Step 2: Parse with `defusedxml`**

Use `defusedxml.ElementTree.parse/fromstring`. Never import standard `xml.etree` in production parser.

- [ ] **Step 3: Implement explicit inheritance**

Only inherit documented fill/stroke/font/source fields. Reject opacity on group. Leaf alpha is:

```python
fill_alpha = leaf_opacity * resolved_fill_opacity
stroke_alpha = leaf_opacity * resolved_stroke_opacity
```

Validate each factor in `[0, 1]`.

- [ ] **Step 4: Preserve tree paths and order**

Tree paths use deterministic element positions such as `/svg[1]/g[2]/text[1]`. Root is not an `SvgNode` group; every `<g>` is one node; empty groups fail.

- [ ] **Step 5: Assert deck-wide zero output on preflight failure**

Preflight all slides and collect independent failures before candidate creation. Tests monkeypatch candidate writer and assert zero calls when any slide fails.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_svg.SvgPreflightTests -v
```

Expected: PASS.

---

### Task 6: Complete Path Lexer, Parser, Arc Math, and Bounds

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/path_parser.py`
- Create: `tests/fixtures/ppt-editable/path-cases.json`
- Create: `tests/fixtures/ppt-editable/svg/arcs.svg`
- Extend: `tests/test_ppt_editable_svg.py`

**Interfaces:**
- Produces: `PathToken`, `MoveTo`, `LineTo`, `ArcTo`, `ClosePath`, `CenterArc`, `tokenize_path`, `parse_path`, `endpoint_arc_to_center`, `path_bounds`, `round_int`.

- [ ] **Step 1: Write lexer RED cases**

Accept signed integers/decimals/exponents, commas and SVG whitespace. Reject unknown letters, garbage at exact offset, malformed exponent, NaN/Infinity, and any unconsumed character.

- [ ] **Step 2: Implement cursor lexer**

Advance from offset zero to end. Return command/number tokens with offsets. Do not use a `finditer` that skips unmatched spans.

- [ ] **Step 3: Write parser RED matrix**

First command M/m; exact arities; repeated groups; M extras become lines; exact 0/1 arc flags; zero radii become line; same endpoints no-op; Z resets subpath; multiple subpaths; only M/L/H/V/A/Z; rotation nonzero raises `svg_arc_rotation_unsupported`.

- [ ] **Step 4: Implement SVG F.6.5 arcs with corrected radii**

Return `corrected_rx`/`corrected_ry`. Emission and bounds must consume those values. Use `round_int` implemented as decimal half-away-from-zero behavior for finite floats.

- [ ] **Step 5: Implement exact unrotated arc bounds**

Include start/end and cardinal extrema only when `angle_is_on_sweep`; expand by half stroke width. Do not use unconditional center±radius.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_svg.PathParserTests -v
```

Expected: all corpus and adversarial cases pass.

---

### Task 7: Recursive Text Events, Whitespace, Runs, and Bounds

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/text_layout.py`
- Create: `tests/fixtures/ppt-editable/svg/namespace-text.svg`
- Extend: `tests/test_ppt_editable_svg.py`

**Interfaces:**
- Produces: `flatten_text_lines`, `normalize_svg_text_whitespace`, `estimate_text_advance_px`, `compute_text_box`, `choose_primary_font`.

- [ ] **Step 1: Write text RED fixture from S03/S11 behavior**

Cover default namespace, nested tspan, inline colored/bold `27 套`, tails, three lines via x/dy, inherited font, letter spacing, meaningful all-space separator, indentation whitespace, and unsupported coordinate lists.

- [ ] **Step 2: Implement recursive traversal**

Walk all nested tspans, normalize Clark names at every depth, inherit run style, and attach tails using parent style. A scalar x or nonzero line-changing dy creates a line; unsupported lists/dx/y ambiguity fail.

- [ ] **Step 3: Implement SVG whitespace normalization**

Collapse XML whitespace, discard indentation at boundaries, retain a separating space between visible runs, and mark runs requiring `xml:space="preserve"`.

- [ ] **Step 4: Implement deterministic text bounds**

Use the confirmed `1.06`, `1.50`, `1.12`, `+6`, and 30px minimum formulas; East Asian W/F=1.0em, digit/uppercase=.60, lowercase=.52, spaces/middle dots=.35, other=.40, plus `(n-1)*letter_spacing`.

- [ ] **Step 5: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_svg.TextLayoutTests -v
```

Expected: exact line/run/text/bounds oracle passes.

---

### Task 8: DrawingML Primitives, Paths, Trace Identity, and Recursive Groups

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/drawingml.py`
- Create: `tests/fixtures/ppt-editable/svg/primitives.svg`
- Create: `tests/test_ppt_editable_drawingml.py`

**Interfaces:**
- Produces: `ShapeIdAllocator`, `stable_shape_name`, `trace_description`, `build_leaf_shape`, `build_text_shape`, `build_group_shape`, `build_slide`.

- [ ] **Step 1: Write primitive/path RED tests**

Assert rect/ellipse/line/polygon/polyline/custGeom mapping, pathLst presence, integer lexical coordinates, corrected arc radii, degree angles, endpoint line, opacity multiplication, polygon close/polyline open, and no `p:pic`/`a:blip`.

- [ ] **Step 2: Build XML with OXML elements**

Use `pptx.oxml.xmlchemy.OxmlElement`/lxml nodes and attributes, not whole interpolated XML strings. Escape text by node assignment.

- [ ] **Step 3: Implement true text boxes**

Set `p:cNvSpPr txBox="1"`, zero insets, `wrap="none"`, anchor top, explicit `a:noAutofit`, one paragraph, run size/fill/typeface/bold/spacing/language, `xml:space` as required.

- [ ] **Step 4: Implement trace identity**

Name format is `<sanitized-source-or-kind>__<kind>__<8hex>`. Hash input is slide ID + NUL + tree path + NUL + kind + NUL + line index. Put canonical trace JSON/string in `p:cNvPr/@descr`.

- [ ] **Step 5: Implement recursive groups**

Every g becomes p:grpSp with nvGrpSpPr and grpSpPr xfrm. off/ext/chOff/chExt use absolute EMU identity coordinates. Preserve child order, require positive extents, use descendant bounds, and omit no production group.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_drawingml -v
```

Expected: exact XML invariants, 570-visible-leaf/63-group formula logic, and nested hierarchy tests pass; the historical 584 count included 14 now-forbidden visible internal-source labels.

---

### Task 9: Speaker Notes and Candidate Deck Generation

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/notes.py`
- Extend: `skills/ppt-editable/scripts/_ppt_editable/drawingml.py`
- Extend: `tests/test_ppt_editable_drawingml.py`

**Interfaces:**
- Produces: `speaker_notes_from_storyboard`, `format_speaker_notes`, `attach_speaker_notes`, `extract_speaker_notes`, `build_presentation(plan, include_text=True) -> Presentation`, `presentation_bytes(plan, include_text=True) -> bytes`.

- [ ] **Step 1: Write notes and deck RED tests**

Assert all three note lines, missing optional warning, END link, Unicode punctuation, duplicate owner failure, save/reopen parity, exact slide count/order/title, and exact integer slide dimensions.

- [ ] **Step 2: Attach notes before Office capability decisions**

Use `slide.notes_slide.notes_text_frame` in python-pptx 1.0.2. Compare the notes body placeholder only, not date/header/number placeholders.

- [ ] **Step 3: Build candidate into memory**

Create one `Presentation`, assign widths directly as integers, add blank slides, set `p:cSld/@name`, append recursive tree, attach notes, save to `io.BytesIO`, close, then hand bytes to atomic writer.

- [ ] **Step 4: Implement geometry-only build**

`include_text=False` omits text leaves and temporary groups that become empty. It does not mutate the production plan or group oracle.

- [ ] **Step 5: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_drawingml.CandidateDeckTests -v
```

Expected: PASS, including reopen and no image parts.

---

### Task 10: Structural, Content, Group, Notes, and Bounds Verifier

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/structural_verify.py`
- Create: `skills/ppt-editable/scripts/verify_editable_pptx.py`
- Create: `tests/test_ppt_editable_verification.py`

**Interfaces:**
- Produces: `verify_candidate`, `verify_zip_and_parts`, `verify_slide_tree`, `verify_text_oracle`, `verify_notes`, `verify_bounds`; public CLI exits 0/2/3/4.

- [ ] **Step 1: Write verifier RED mutation cases**

Mutate a valid deck for duplicate ZIP entries, missing rel/content type, p:pic injection, duplicate cNvPr ID, empty group/textbox, hierarchy/order/trace/count mismatch, text/run mismatch, notes mismatch, pathLst/angle/integer errors, and >1px bounds violation.

- [ ] **Step 2: Implement ZIP and OOXML checks**

Run `ZipFile.testzip`, duplicate-name detection, required parts/rels/content types, python-pptx reopen, exact page order/count, no media/image relationship.

- [ ] **Step 3: Recursively verify trace hierarchy**

Use `descr` as identity, compare exact group tree/sibling order and leaf mapping cardinality. Record top-level, recursive leaf, and recursive group counts separately.

- [ ] **Step 4: Verify text, notes, metadata, and bounds**

Compare source-derived lines/runs, p:cSld title, report description, notes body, supported run properties, and bounds using config tolerance.

- [ ] **Step 5: Implement gating CLI**

CLI writes canonical JSON atomically. Required failure returns 2; invalid invocation/config 3; unexpected exception 4. Never print failure and exit 0.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_verification.StructuralVerificationTests -v
```

Expected: all mutations are detected with stable reason and nonzero status.

---

### Task 11: Full, Geometry-Only, and Tile Visual Metrics

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/visual_compare.py`
- Create: `tests/fixtures/ppt-editable/visual-metric-cases.json`
- Extend: `tests/test_ppt_editable_verification.py`

**Interfaces:**
- Produces: `grayscale_mad`, `tile_mads`, `compare_slide_renders`, `compare_render_sets`.

- [ ] **Step 1: Write metric RED cases**

Cover exact threshold equality, one over threshold, localized 64×64 defect whose full MAD passes, partial 64×16 bottom tile, wrong dimensions, missing render, and evidence paths.

- [ ] **Step 2: Implement exact metrics**

Require 1280×720; no resize/downsample. Convert to Pillow L. Divide MAD by actual pixel count. Tiles are nonoverlapping and final partial row/column uses actual area. Equality passes.

- [ ] **Step 3: Persist evidence**

Write per-slide full/geometry diff images, tile JSON, metrics, and summary under comparison transaction directory. Metrics do not mutate correctness state directly; report feeds orchestrator.

- [ ] **Step 4: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_verification.VisualMetricTests -v
```

Expected: tile gate catches localized geometry defect.

---

### Task 12: PowerPoint Request Protocol and Safe COM Adapter

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/office_protocol.py`
- Create: `skills/ppt-editable/scripts/normalize_and_export.ps1`
- Create: `tests/test_ppt_editable_office_contract.py`

**Interfaces:**
- Produces: request/result JSON schema; `invoke_office_verification(request, script_path, timeout_seconds) -> OfficeResult`; PowerShell exit 0/2/3/4.

- [ ] **Step 1: Write static protocol and process-ownership RED tests**

Require request/result parameters, exact render paths/counts/config, `Presentations.Open(... ReadOnly=-1 ... WithWindow=0)`, SaveAs format 24, Slide.Export 1280×720, finally cleanup, and prohibitions on `taskkill /IM`, name-wide Stop-Process, or quitting unowned app.

- [ ] **Step 2: Implement JSON protocol**

Request contains candidate, normalized temp, selected SVGs, geometry SVGs/deck, four render directories, ordered IDs, expected counts, config. Result contains capability, version/build, PID/start time/ownership, stages, counts, renders, structured error.

- [ ] **Step 3: Implement safe PowerPoint ownership**

Capture existing process identities/start times; create COM; resolve window handle to exact PID; own only a new matching PID. Quit/terminate only owned PID after identity recheck. Release all presentations and COM objects in `finally`.

- [ ] **Step 4: Implement normalization and four render streams**

SaveAs new temp, reopen, recursively check counts, export editable full/geometry, create full source SVG deck and geometry-source SVG deck, export using same application.

- [ ] **Step 5: Add Windows integration test guarded by capability**

Static tests always run. COM smoke test uses `@unittest.skipUnless(os.name == "nt" and powerpoint_available(), ...)` and validates no user-owned process termination.

- [ ] **Step 6: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_office_contract -v
```

Expected: static suite passes everywhere; COM smoke passes on the current Windows/PowerPoint host.

---

### Task 13: Orchestrator, Public Generator CLI, States, Idempotency, and Recovery

**Files:**
- Create: `skills/ppt-editable/scripts/_ppt_editable/orchestrator.py`
- Create: `skills/ppt-editable/scripts/svg_to_editable_pptx.py`
- Create: `tests/test_ppt_editable_orchestrator.py`

**Interfaces:**
- Produces: `generate_editable(run_dir, capability, fault_injector=None) -> EditableResult`; public generator CLI.

- [ ] **Step 1: Write state-machine RED matrix**

Cover BLOCKED preflight/core dependency/candidate write; GENERATED_UNVERIFIED missing Office/Pillow; PASS all gates; FAILED_VERIFICATION structural/Office/visual; same-snapshot no-op; unverified resume to PASS; changed snapshot; previous PASS preservation; concurrent lock; crash recovery.

- [ ] **Step 2: Implement fixed phase order**

Locate/validate/snapshot/recover/idempotency/dependencies/preflight/build/hash/reopen/verify/capability/Office/visual/journal promotion/result. No candidate before complete preflight.

- [ ] **Step 3: Implement distinct output paths**

Unverified promotion touches only `-editable-unverified.pptx`; PASS touches only verified path. Same-snapshot PASS quarantines stale unverified after commit.

- [ ] **Step 4: Implement public CLI**

Arguments: `--run-dir`, optional `--result-path` for tests, `--skip-office` only to force degraded capability, and `--json`. It locates run per contract and exits 0 for PASS/GENERATED_UNVERIFIED, 2 for BLOCKED/FAILED_VERIFICATION, 3 invalid invocation, 4 unexpected failure.

- [ ] **Step 5: Run GREEN**

```bash
python -m unittest tests.test_ppt_editable_orchestrator -v
```

Expected: complete matrix passes without touching paths outside temp run fixtures.

---

### Task 14: Skill Contracts and Pressure GREEN

**Files:**
- Create: `skills/ppt-editable/SKILL.md`
- Create: `skills/ppt-editable/references/input-output-contract.md`
- Create: `skills/ppt-editable/references/editable-svg-subset.md`
- Create: `skills/ppt-editable/references/verification.md`
- Modify: `tests/fixtures/ppt-editable/pressure-baseline.json`
- Extend: `tests/test_ppt_editable_package.py`

**Interfaces:**
- Consumes all executable contracts from Tasks 2–13; produces discoverable orchestration guidance without duplicating numeric config.

- [ ] **Step 1: Write minimal discovery frontmatter**

Use exactly:

```yaml
---
name: ppt-editable
description: Use when a completed PPT Pilot SVG run must be delivered as a PowerPoint deck with editable native shapes, editable text, preserved SVG groups, or verified Office rendering.
---
```

- [ ] **Step 2: Write short orchestrator Skill**

Keep under 200 lines. Link the three references, state fixed phase order, output statuses, dependency behavior, no fallback, no run.json mutation, and invoke packaged scripts by path relative to the installed Skill.

- [ ] **Step 3: Write heavy references from the confirmed spec**

`input-output-contract.md` owns selection/snapshot/paths/journal/states; `editable-svg-subset.md` owns allowlists/path/group/text/reasons; `verification.md` owns gate semantics and links `../assets/verification-config.json` without repeating numbers.

- [ ] **Step 4: Add machine-only source-ID RED/GREEN contract**

Add package/static tests that require `editable-svg-subset.md` and `SKILL.md` to state:

```text
SRC-<digits> is machine metadata only.
Visible <text>/<tspan> containing a case-insensitive \bSRC-[0-9]+\b token fails svg_text_invalid and blocks the whole deck.
data-source-id and p:cNvPr/@descr retain the source ID.
Human-readable citations are allowed only without internal SRC identifiers.
```

Add a parser test with `来源：SRC-001 · SRC-002`, `Source: SRC-003`, and bare `SRC-005` visible text; each must fail with `svg_text_invalid`. Add a control where the same IDs exist only in `data-source-id`; it must preflight successfully. Do not implement a text-deletion sanitizer.

- [ ] **Step 5: Run pressure cases with the Skill loaded**

Dispatch fresh agents on the exact Task 1 prompts, explicitly loading `ppt-editable`. Save outputs and assert all required/forbidden decision checks. If a case rationalizes a forbidden fallback or false PASS, tighten the Skill and rerun.

- [ ] **Step 6: Run package GREEN**

```bash
python -m unittest tests.test_ppt_editable_package -v
```

Expected: package/frontmatter/links/static contracts/pressure results pass.

---

### Task 15: Multi-Skill Installers, Documentation, and Deployment Tests

**Files:**
- Modify: `tools/update-hosts.ps1`
- Modify: `tools/install-deepseek-plugin.ps1`
- Modify: `tests/test_skill_package.py`
- Modify: `tests/test_tools_package.py`
- Modify: `README.md`
- Modify: `docs/design.md`
- Modify: `docs/acceptance.md`

**Interfaces:**
- Produces data-driven descriptors for exactly `ppt-start` and `ppt-editable`; per-Skill backup/digest verification.

- [ ] **Step 1: Write installer RED tests**

Require both source directories, both destination names, independent `<skill>.bak-*` patterns, backups outside scanning roots, plugin manifest `skills='./skills/'`, validation of both SKILL.md files, and completion text for all invocations.

- [ ] **Step 2: Refactor `update-hosts.ps1` to descriptors**

Use:

```powershell
$skills = @(
  [ordered]@{ Id = 'ppt-start'; Source = Join-Path $RepoRoot 'skills\ppt-start' },
  [ordered]@{ Id = 'ppt-editable'; Source = Join-Path $RepoRoot 'skills\ppt-editable' }
)
```

`Copy-SkillWithBackup` receives descriptor/destination, migrates legacy backups per ID, retains latest one per ID, copies complete tree, then compares file count and aggregate deterministic SHA-256.

- [ ] **Step 3: Update DeepSeek plugin installer**

Keep one `ppt-pilot` plugin/marketplace entry. Copy both Skills under plugin `skills/`, validate both, and add default prompt for `ppt-editable`.

- [ ] **Step 4: Update active docs**

README gets Skill inventory table and per-host invocation. `docs/design.md` adds repository multi-Skill packaging while keeping ppt-start workflow scoped. `docs/acceptance.md` adds independent discovery/behavior evidence rows.

- [ ] **Step 5: Run package GREEN**

```bash
python -m unittest tests.test_skill_package tests.test_tools_package tests.test_ppt_editable_package -v
```

Expected: PASS; existing ppt-start-specific style/assets tests unchanged.

---

### Task 16: FY26H1 Reference Integration Acceptance

**Files:**
- Create: `tests/test_ppt_editable_reference_integration.py`
- Modify only if a confirmed implementation defect is found: files under `skills/ppt-editable/`

**Interfaces:**
- Consumes explicit environment variable `PPT_EDITABLE_REFERENCE_RUN`; validates current corpus facts dynamically and exact known integration expectations.

- [ ] **Step 1: Write opt-in integration test**

Skip unless the environment variable points to a valid run. Assert source owners: S01/S06 approved samples, other 12 production. Derive expected leaves from nontext visible elements + visual text lines; derive group count from g nodes. Recursively collect every visible SVG `<text>/<tspan>` value and every editable PPTX text run and assert case-insensitive `\bSRC-[0-9]+\b` is absent, while source-backed nodes retain `data-source-id` and trace `descr` metadata.

- [ ] **Step 2: Run against supplied corpus**

```bash
PPT_EDITABLE_REFERENCE_RUN='D:/05-AI/FY26H1-test/ppt-output/FY26H1-work-summary-machine-source-only' python -m unittest tests.test_ppt_editable_reference_integration -v
```

Expected machine-only-source-ID reference oracle: 14 slides, 570 visible leaves, 63 groups, 633 recursive objects, no images, notes present, and no visible internal source IDs. On a genuine Microsoft PowerPoint 16+ host, normalization/reopen/four render streams/visual gates must produce `PASS`; without `POWERPNT.EXE`, the only valid result is `GENERATED_UNVERIFIED` with those Office/visual gates recorded `NOT RUN`. The original 584-leaf count included 14 erroneous visible internal-source labels and remains historical evidence only.

- [ ] **Step 3: Inspect visual evidence**

Read every exported source/editable full and geometry comparison summary. Any threshold breach is a failure; do not relax config to make the corpus pass without identifying a converter defect.

- [ ] **Step 4: Verify output editability and hierarchy**

Reopen with python-pptx and PowerPoint; recursively inspect p:grpSp/p:sp, editable text runs, trace descriptions, and notes. Confirm the process record's stale 574 is not used.

- [ ] **Step 5: Record integration evidence**

Save command output and `editable-result.json` hash in the task report; do not add the generated PPTX or user corpus to git.

---

### Task 17: Full Verification, Independent Review, and Three-Host Deployment

**Files:**
- Verify all Task 1–16 files.
- Deployment modifies external host directories only after implementation verification and explicit outward-action authorization.

**Interfaces:**
- Produces final verified repository state and host tree-digest evidence; then releases the paused SVG concurrency task.

- [ ] **Step 1: Run all focused suites**

```bash
python -m unittest tests.test_ppt_editable_package tests.test_ppt_editable_contract tests.test_ppt_editable_atomic tests.test_ppt_editable_svg tests.test_ppt_editable_drawingml tests.test_ppt_editable_verification tests.test_ppt_editable_office_contract tests.test_ppt_editable_orchestrator -v
```

Expected: PASS.

- [ ] **Step 2: Run existing regression suites**

```bash
python -m unittest tests.test_skill_package tests.test_tools_package tests.test_assets tests.test_style_packs tests.test_redesign_prompt_contract -v
```

Expected: PASS without deleting or weakening existing tests.

- [ ] **Step 3: Run full suite and static checks**

```bash
python -m unittest discover -s tests -v
```

```bash
git diff --check
```

Expected: all tests pass and no whitespace errors.

- [ ] **Step 4: Run independent whole-change review**

Review for path traversal/reparse races, XML injection, incomplete path consumption, arc/radius/bounds correctness, group coordinate drift, visible internal `SRC-<digits>` leakage versus preserved machine trace metadata, false verification PASS, PowerPoint ownership, journal recovery, previous-final loss, installer backup discovery pollution, and test weakening. Fix confirmed Critical/Important findings and rerun Steps 1–3.

- [ ] **Step 5: Deploy to all three hosts when authorized**

Run `tools/update-hosts.ps1`, then compare repository and installed file counts/tree digests independently for both Skills. Confirm no `*.bak-*` directory exists under any Skill scanning root.

- [ ] **Step 6: Smoke-test installed discovery**

Confirm `/ppt-editable`, `$ppt-editable`, and DeepSeek `ppt-editable` discovery; run a no-write capability/read-only invocation and record evidence.

- [ ] **Step 7: Close editable work and resume the paused SVG concurrency task**

Only after repository tests, FY26H1 integration, review, and deployment are complete, mark `ppt-editable` finished. Resume SVG performance work from the pending Task 1B2a patch, then Task 1B2b and schema-v2.

## Self-Review Results

- **Spec coverage:** Tasks 1–17 cover Skill pressure TDD, package discovery, exact dependencies/config, completed-run selection, anchor fallback, path safety, snapshot identity, atomic journal/recovery, secure SVG/style preflight, machine-only source IDs with visible-text blocking, complete path parsing, corrected arcs/bounds, recursive text, native DrawingML, recursive groups, notes, structural/content verification, visual metrics, PowerPoint automation, result states, idempotency, docs/installers, FY26H1 integration, final review, and deployment.
- **Placeholder scan:** Every implementation step names exact files, interfaces, failure cases, commands, and expected outcomes; no deferred implementation markers remain.
- **Type consistency:** Foundation dataclasses feed contract/snapshot, parser/text feed `SlidePlan`, DrawingML/notes consume the same plan, structural/visual/Office produce reports consumed by orchestrator, and the orchestrator alone owns atomic public state.
- **Scope check:** Converter, verifier, COM adapter, and deployment are components of one independently usable Skill and share the same result/snapshot contract; splitting them into separate product specs would create circular acceptance boundaries, so one sequential plan is appropriate.
