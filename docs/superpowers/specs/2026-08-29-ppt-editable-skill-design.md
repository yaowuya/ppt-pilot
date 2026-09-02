# PPT Editable Skill Design

**Date:** 2026-08-29  
**Status:** Confirmed design, pending written-spec review  
**Skill:** `ppt-editable`

## 1. Goal

Add an independently invocable Skill that converts the completed standalone SVG slides of one PPT Pilot run into a PowerPoint deck made from editable native DrawingML shapes, editable text boxes, recursively preserved SVG groups, and speaker notes.

The design generalizes the successful process recorded in:

```text
D:\05-AI\FY26H1-test\ppt-output\FY26H1-work-summary\.ppt-pilot\可编辑PPTX生成过程记录.md
```

That process is treated as a proof of concept, not as reusable production code. Its hard-coded paths, fixed slide list, content-specific assertions, flattened groups, and inconsistent visual thresholds must not be carried into the Skill.

## 2. Scope

### 2.1 Included

- Accept one completed PPT Pilot run.
- Convert the supported SVG subset to native PowerPoint DrawingML.
- Preserve every SVG `<g>` as a recursively nested PowerPoint group shape.
- Convert visible text into editable text boxes and runs.
- Preserve SVG document order as PowerPoint z-order.
- Preserve style inheritance and source traceability.
- Write storyboard assertion, takeaway, and transition fields into speaker notes.
- Validate OOXML structure, content, grouping, bounds, notes, and editability.
- When available, use Microsoft PowerPoint to normalize, reopen, and render the deck.
- Compare PowerPoint renders of the source SVG deck and editable deck.
- Produce a deterministic result manifest and preserve previous successful output until promotion.
- Deploy the new Skill alongside `ppt-start` to Claude Code, Codex, and the DeepSeek harness.

### 2.2 Excluded

- Generating, revising, or repairing SVG.
- Accepting arbitrary SVG directories in the first release.
- Changing `.ppt-pilot/run.json` or the completed PPT Pilot workflow state.
- Replacing the ordinary SVG-embedded PPTX produced by `deck-deliver.ps1`.
- Automatically installing Python packages or changing the host environment.
- Silently rasterizing unsupported pages.
- Producing a mixed deck containing editable and image-only pages.
- Supporting SVG transforms, gradients, filters, images, external resources, or Bézier commands outside the approved subset.

## 3. Architecture

Create:

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
    └── normalize_and_export.ps1
```

Responsibilities:

- `SKILL.md`: orchestration, run selection, fixed stage order, capability decisions, and user-visible outcomes.
- `assets/verification-config.json`: machine-readable schema/version and the sole numeric owner for render dimensions and visual thresholds.
- `input-output-contract.md`: accepted run layout, snapshot identity, paths, result manifest, idempotency, atomic writes, and recovery.
- `editable-svg-subset.md`: supported elements, attributes, inheritance, path grammar, group mapping, text mapping, and stable reason codes.
- `verification.md`: semantics of the structural, content, Office, and pixel gates; it references rather than duplicates numeric values from `assets/verification-config.json`.
- `svg_to_editable_pptx.py`: no-side-effect preflight followed by deterministic SVG-tree-to-DrawingML candidate generation.
- `verify_editable_pptx.py`: OOXML, content, grouping, text, bounds, notes, and image-comparison verification.
- `normalize_and_export.ps1`: PowerPoint capability detection, SaveAs normalization, reopen checks, source/editable rendering, and lifecycle cleanup.

The Skill writes only inside the selected run's `delivery/editable/`. It never writes into its installed Skill directory.

## 4. Relationship to Existing Components

- `ppt-start` continues to finish at standalone SVG + complete deck QA. Editable PPTX generation is optional and separately invoked.
- `ppt-editable` consumes only a completed run and does not modify content or visuals.
- `tools/deck-deliver.ps1` continues to own preview HTML and ordinary SVG-embedded PPTX delivery. It does not absorb editable conversion logic.
- Host installers must copy both `skills/ppt-start/` and `skills/ppt-editable/` while keeping backups outside Skill discovery roots.

## 5. Input Contract

A valid input is one PPT Pilot run directory containing:

```text
.ppt-pilot/run.json
.ppt-pilot/故事板.md          # canonical new-run name
slides/S*.svg                # preferred production source
samples/S*.svg               # approved-anchor fallback only
.ppt-pilot/质量检查报告.md
```

Existing path-compatibility rules may allow the documented legacy storyboard filename for an old run, but the converter must never guess among competing files.

Required gates:

- `run.json.stage == "complete"`.
- `deck_id` is present and path-safe.
- The quality report exists.
- The expected ordered slide IDs are parsed from the authoritative storyboard; IDs are unique and numerically ordered.
- For each expected ID, source resolution is deterministic: use `slides/<slide-id>.svg` when present; otherwise use `samples/<slide-id>.svg` only when the run records that ID as an approved anchor and no production file exists.
- A production file always wins over an approved-anchor fallback. An unapproved sample, a missing expected page, an extra unmatched page, or competing path owners fails with `slide_set_invalid`.
- Every selected slide is a regular file inside `slides/` or `samples/` and passes no-follow containment checks.
- The resolved page set is non-empty and exactly matches the storyboard page set.

Run selection order:

1. Use an explicitly supplied run directory.
2. Otherwise use the current directory if it is a valid run.
3. Otherwise use the only completed run under `ppt-output/`.
4. If multiple completed runs exist, ask one direct selection question.
5. Never pick the newest directory heuristically.

## 6. Output Contract

All output is isolated under:

```text
delivery/editable/
├── <deck-id>-editable.pptx
├── <deck-id>-editable-unverified.pptx
├── editable-result.json
├── source-render/
├── editable-render/
├── comparison/
├── quarantine/
└── .tmp/
```

The ordinary PPTX and source SVG files are never overwritten. A fully verified `PASS` is published only as `<deck-id>-editable.pptx`. A degraded `GENERATED_UNVERIFIED` result is published only as `<deck-id>-editable-unverified.pptx`, so a newer unverified build can never replace or masquerade as an older verified final. When that same snapshot later passes Office verification, the unverified file is moved to `quarantine/` after the verified final is atomically promoted.

`editable-result.json` contains at least:

```json
{
  "schema_version": 1,
  "kind": "ppt_editable_result",
  "deck_id": "example",
  "input_snapshot_id": "sha256:<64hex>",
  "converter_version": "1.0.0",
  "status": "BLOCKED|GENERATED_UNVERIFIED|PASS|FAILED_VERIFICATION",
  "slide_count": 14,
  "shape_counts": {
    "top_level": 0,
    "recursive_leaves": 584,
    "recursive_groups": 63
  },
  "output_path": "delivery/editable/example-editable.pptx|delivery/editable/example-editable-unverified.pptx|none",
  "output_sha256": "sha256:<64hex>|none",
  "powerpoint": {
    "available": true,
    "version": "16.x|none",
    "normalized": true,
    "reopened": true
  },
  "validation": {
    "structure": "passed|failed|not_run",
    "content": "passed|failed|not_run",
    "groups": "passed|failed|not_run",
    "notes": "passed|failed|not_run",
    "visual": "passed|failed|not_run"
  },
  "failures": []
}
```

Each failure has a stable reason code, slide ID when applicable, SVG tree path, element type, message, and actionable remediation.

## 7. Execution Flow

```text
locate run
  → validate completed-run contract
  → compute input snapshot
  → check prior result and idempotency
  → check core Python capabilities
  → preflight every SVG in memory
  → atomically write candidate PPTX
  → structural/content/group/notes verification
  → negotiate Office verification capability
      → unavailable: publish structurally valid output as GENERATED_UNVERIFIED
      → available: normalize, reopen, dual-render, compare
          → pass: atomically promote as PASS
          → fail: quarantine candidate as FAILED_VERIFICATION
  → atomically write editable-result.json
```

No final PPTX is written before all SVG files pass preflight.

## 8. SVG Subset

### 8.1 Supported elements

- `svg`
- `g`
- `path`
- `rect`
- `circle`
- `ellipse`
- `line`
- `polyline`
- `polygon`
- `text`
- `tspan`
- `title`
- `desc`

`title` and `desc` contribute metadata but not visible slide shapes. The resolved SVG `title` is written to `p:cSld/@name`. Both title and description are retained in the source-derived slide plan and validation report; description is not encoded as an invisible shape or user-visible note.

### 8.2 Supported path commands

Both absolute and relative forms of:

```text
M L H V A Z
```

Unsupported path commands fail preflight:

```text
C Q S T
```

Malformed command arity, non-finite coordinates, unknown command letters, delimiters in illegal positions, and trailing unparsed path data also fail. The parser is a cursor-based lexer plus command-state/arity parser and must consume every byte of the `d` attribute; regex extraction of only recognized fragments is forbidden.

For schema-v1 `A/a`, `x-axis-rotation` must be exactly `0`. DrawingML `arcTo` is axis-aligned and cannot exactly encode a rotated elliptical SVG arc; nonzero rotation fails with `svg_arc_rotation_unsupported` rather than being silently approximated. Endpoint-to-center conversion must return the radii after SVG lambda correction, and the corrected radii must own both emitted `wR/hR` and arc bounds.

### 8.3 Unsupported features

Any occurrence blocks the complete deck before candidate generation:

- `transform`
- gradients
- filters
- animation
- script
- `foreignObject`
- `image`
- `defs`
- `use`
- `clipPath`
- `mask`
- external URL or file reference
- unsupported CSS or style syntax
- group-level `opacity`
- unsupported path command

There is no image fallback.

## 9. Coordinate and Geometry Mapping

- Canvas: `1280 × 720` px.
- Slide: exactly `12192000 × 6858000` EMU.
- Conversion: `1 px = 9525 EMU`.
- The writer assigns the exact integer EMU slide dimensions directly; `Inches(13.333)` is forbidden because it produces `12191695` EMU rather than `12192000`.
- All persisted DrawingML coordinates are integers, using one converter-wide “round halves away from zero” helper rather than Python banker’s rounding.
- `ST_Angle = degrees(angle) × 60000`, never radians.

Mapping:

| SVG | DrawingML |
|---|---|
| `rect` | `prstGeom rect` |
| `circle`, `ellipse` | `prstGeom ellipse` |
| `line` | `prstGeom line` |
| `polygon`, `polyline` | `custGeom` |
| `path` | `custGeom` with `pathLst` and `arcTo` |
| visible text line | native text-box `p:sp` |

SVG endpoint arcs use the SVG specification endpoint-to-center conversion. Arc radii lambda correction, corrected-radii propagation, large/sweep selection, start angle, sweep angle, and endpoint closure must be covered by direct unit tests. Schema-v1 emits only zero-rotation elliptical arcs; it does not approximate a rotated ellipse with axis-aligned `arcTo`. Arc bounds include the start, end, and only those 0/90/180/270-degree ellipse extrema that lie on the actual sweep; every visual bound expands by half the resolved stroke width.

## 10. Recursive Group Mapping

Every SVG `<g>` maps to a nested PowerPoint `p:grpSp`.

Before conversion, inheritable group attributes are resolved onto descendants:

- `fill`
- `stroke`
- `stroke-width`
- `fill-opacity`
- `stroke-opacity`
- `font-family`
- `font-size`
- `font-weight`
- `letter-spacing`
- `text-anchor`
- `data-source-id`

The original child order is preserved as z-order. SVG `opacity` is not inherited and group-level compositing cannot be represented exactly by the selected DrawingML subset, so schema-v1 rejects `opacity` on `<g>`. On a leaf, effective fill alpha is `leaf opacity × resolved fill-opacity`, and effective stroke alpha is `leaf opacity × resolved stroke-opacity`. Choosing one factor instead of multiplying them is invalid. Every factor is parsed in `[0, 1]`, and out-of-range or non-finite values fail preflight.

Because transforms are forbidden, the complete tree uses one absolute EMU coordinate model. For each group:

```text
off/ext = group bounds in the parent coordinate system
chOff   = the same group's top-left absolute EMU coordinate
chExt   = the same group's width and height in EMU
```

Children retain coordinates in that same absolute child coordinate space. Nested grouping therefore does not introduce cumulative scaling.

Rules:

- Empty groups fail preflight.
- A group bound is the union of all descendant visible geometry and text bounds.
- A group with no `data-source-id` receives a deterministic name from its SVG tree path.
- A group with `data-source-id` uses a sanitized source prefix plus a deterministic suffix.
- Every group and leaf writes a machine-readable trace identity to `p:cNvPr/@descr` containing schema version, slide ID, SVG tree path, element kind, inherited source ID, and text-line index when applicable. Verification uses `descr` as the primary identity and the human-readable shape name as a secondary invariant.
- Group hierarchy and group order must round-trip through PowerPoint normalization.

## 11. Text Mapping

- Every visible SVG line becomes one editable PowerPoint text box.
- `<text>` and nested `<tspan>` descendants are traversed recursively; direct-child-only parsing is forbidden.
- An inline `tspan` becomes a separate run in the same paragraph.
- A `tspan` with absolute `x` or line-changing `dy` begins a new visual line.
- Clark-notation namespaces are normalized at every traversal boundary.
- Pure indentation whitespace between XML elements is discarded. Whitespace inside a visible run is preserved, including an all-space run when it separates visible neighboring runs; the emitted `<a:t>` uses `xml:space="preserve"` when leading, trailing, or all-space content requires it.
- Text shapes set `p:cNvSpPr txBox="1"`; body properties use zero inset, explicit `<a:noAutofit/>`, and no wrapping unless the source explicitly defines a supported line break.
- `text-anchor` maps to left, center, or right paragraph alignment and deterministic box placement.
- Font family comes from the resolved SVG declaration rather than a converter-wide hard-coded font.
- Missing fonts produce a compatibility warning; the converter does not change the source font silently.

The content oracle is generated from each SVG, not from deck-specific hard-coded strings. SVG and PPTX text sequences, occurrence counts, and run properties must match.

## 12. Speaker Notes

For each slide, parse the corresponding storyboard section and write available fields:

```text
本页结论：<assertion_title>
听众要点：<audience_takeaway>
衔接下一页：<next_link>
```

Missing optional fields produce warnings. An absent or ambiguous storyboard owner blocks conversion because the selected design requires speaker-note parity with ordinary delivery.

Notes must exist in `GENERATED_UNVERIFIED` output as well as `PASS` output; they cannot depend solely on COM post-processing.

## 13. Capability and Dependency Contract

Core generation requires:

```text
Python >= 3.9
python-pptx >= 1.0.2, < 2
defusedxml >= 0.7, < 1
```

Full Office verification additionally requires:

```text
Windows
Microsoft PowerPoint 16+
PowerShell 5.1+
Pillow >= 11, < 12
```

The Skill never installs packages automatically.

- Missing core dependency: `BLOCKED`, no PPTX.
- Structurally valid candidate but PowerPoint or Pillow unavailable: `GENERATED_UNVERIFIED`.
- PowerPoint available but normalization/reopen/render/comparison fails: `FAILED_VERIFICATION`, no promoted final.

## 14. Structural and Content Verification

Required checks:

- ZIP integrity.
- Required OOXML parts, content types, and relationships.
- `python-pptx` reopen.
- Expected slide count and order.
- At least one visible shape per slide.
- No image shape or unexpected media fallback.
- Unique shape IDs.
- No empty text box or group.
- All shapes inside the slide bounds within the documented tolerance.
- SVG group count, nesting, and order match `p:grpSp` structure.
- Every visible SVG element maps exactly once.
- SVG and PPTX text sequences match.
- Text run properties match supported source properties.
- `data-source-id` traceability survives.
- Speaker notes match storyboard-derived values.

The verifier is a gating CLI, not a print-only diagnostic. It atomically writes a structured JSON report and uses fixed exit codes:

```text
verify_editable_pptx.py
  0 = every requested structural/content/group/notes gate passed
  2 = one or more required gates failed
  3 = invocation or configuration invalid
  4 = unexpected verifier failure

normalize_and_export.ps1
  0 = Office normalization, reopen, render, and comparison passed
  2 = Office or visual validation failed
  3 = Office verification capability unavailable
  4 = unexpected automation failure
```

A required finding such as an empty text box, off-slide shape, content miss, group mismatch, or visual threshold breach must set the report to failed and return nonzero. Printing `REVIEW NEEDED` while exiting 0 is forbidden.

## 15. PowerPoint Normalization and Rendering

When PowerPoint is available:

1. Open the candidate without a visible window.
2. SaveAs to a new temporary `.pptx`; never normalize in place.
3. Close and reopen read-only.
4. Verify slide, group, and shape counts.
5. Export editable slides at 1280×720.
6. Build a temporary source-reference deck with each original SVG inserted as one full-slide vector graphic.
7. Export source-reference slides from the same PowerPoint instance.
8. Build geometry-only comparison variants by removing visible text from temporary source SVGs and generating a temporary editable deck from the same preflight plan with text excluded; omit temporary groups that become empty without changing the production group oracle.
9. Run image comparison.
10. Close every presentation and release or terminate only the PowerPoint process started by this run.
11. Promote only after all checks pass.

An existing user-owned PowerPoint process must never be terminated. Before creating COM, record existing `POWERPNT` process identities and start times; resolve the COM application window handle to its exact PID. The adapter may call `Quit()` or, after rechecking PID/start-time identity, terminate only a PID proven to have been created by this run. Calling `taskkill /IM POWERPNT.EXE`, killing by process name, or assuming `New-Object -ComObject` implies ownership is forbidden.

## 16. Visual Verification

Numeric thresholds have one machine-readable owner: `assets/verification-config.json`. `references/verification.md` explains their semantics without repeating the values, and both scripts and tests load and validate the same JSON bytes.

Initial `verification-config.json` schema-v1 values:

```json
{
  "schema_version": 1,
  "render_width": 1280,
  "render_height": 720,
  "full_page_grayscale_mad_max": 4.0,
  "geometry_only_grayscale_mad_max": 1.5,
  "geometry_tile_size": 64,
  "geometry_tile_mad_max": 8.0,
  "bounds_tolerance_px": 1.0
}
```

The gates are:

- Full-page grayscale MAD ≤ 4.0 / 255.
- Geometry-only grayscale MAD ≤ 1.5 / 255.
- Every 64×64 geometry tile MAD ≤ 8.0 / 255.
- Emitted shape bounds may exceed the exact slide edge by at most 1.0 source pixel; any larger excursion is `bounds_violation`.

Text correctness is established independently by content/run/bounds checks. Geometry-only comparison catches localized arc and corner defects that whole-page downsampling can hide.

## 17. Result States

| State | Meaning | Promoted output |
|---|---|---|
| `BLOCKED` | Input, dependency, path-safety, or SVG preflight failed | No |
| `GENERATED_UNVERIFIED` | Structure/content/groups/notes passed, Office verification unavailable | `<deck-id>-editable-unverified.pptx` only |
| `PASS` | All structural, content, Office, and visual gates passed | `<deck-id>-editable.pptx` only |
| `FAILED_VERIFICATION` | Candidate exists but a post-generation gate failed | No; candidate retained under `quarantine/` |

A result state cannot claim a stronger gate than the recorded validation fields prove. Failure before a candidate is closed, hash-verified, and ZIP-reopened—including `candidate_write_failed` or `candidate_hash_mismatch`—maps to `BLOCKED`. Once a closed hash-verified candidate exists, any structural, content, group, notes, Office, or visual gate failure maps to `FAILED_VERIFICATION` and quarantines that candidate.

### 17.1 Stable reason-code closure

Schema-v1 failure reasons are closed to this set; adding a reason requires a schema/contract update and a consumer test:

```text
run_not_found
run_ambiguous
run_not_complete
deck_id_invalid
quality_report_missing
storyboard_missing
storyboard_ambiguous
slide_set_invalid
source_path_unsafe
source_unreadable
python_version_unsupported
core_dependency_missing
svg_xml_invalid
svg_canvas_invalid
svg_element_unsupported
svg_attribute_unsupported
svg_external_reference
svg_path_invalid
svg_arc_rotation_unsupported
svg_group_empty
svg_coordinate_invalid
svg_text_invalid
candidate_write_failed
candidate_hash_mismatch
pptx_zip_invalid
pptx_reopen_failed
structure_mismatch
content_mismatch
group_mismatch
notes_mismatch
bounds_violation
image_fallback_detected
powerpoint_normalize_failed
powerpoint_reopen_failed
powerpoint_render_failed
visual_mismatch
promotion_conflict
```

PowerPoint or Pillow absence is a capability outcome leading to `GENERATED_UNVERIFIED`, not a failure reason. The manifest records that absence under capability fields and warnings.

## 18. Identity, Idempotency, and Recovery

`input_snapshot_id` hashes canonical payload bytes containing:

- ordered slide IDs, relative paths, and SVG SHA-256 values;
- `deck_id` and completed-run identity;
- storyboard path and notes-field snapshot;
- converter schema/version;
- SVG-subset contract version;
- verification configuration version.

Rules:

- Same snapshot + valid `PASS` output hash: return without rebuilding.
- Same snapshot + valid `GENERATED_UNVERIFIED`: if Office capability later appears, continue verification without reconverting.
- Changed input: create a new candidate identity.
- Previous verified final remains untouched until a new `PASS` promotion; `GENERATED_UNVERIFIED` always uses its distinct `-unverified.pptx` path and cannot downgrade the verified path.
- If no verified final exists, an unverified output is still published only under the distinct unverified filename.
- All JSON and PPTX writes use sibling temp files, close/flush, atomic replace, reread, and hash verification.
- Orphan temp files and uncommitted candidates are never adopted.
- A verification failure retains the candidate and evidence in `quarantine/`.
- Cancellation follows the same rule as a crash: previous final remains authoritative.

An OS-backed exclusive lock covers the complete generation/promotion operation (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX); lock-file existence alone is never ownership. Public PPTX and `editable-result.json` cannot be replaced atomically as one filesystem operation, so every promotion uses a transaction journal under `.tmp/txn-<id>/`:

1. hash and back up the current public target and current manifest when present;
2. atomically write a `PREPARED` journal containing snapshot, target kind, new hash, previous target hash, and previous manifest hash;
3. replace and reread/hash the public target;
4. replace `editable-result.json` last as the commit record;
5. remove journal/backup only after both committed hashes match.

Recovery never adopts an output merely because it exists. If the target is new but the manifest is old or missing, restore the previous target or quarantine the uncommitted target when no prior output existed. If hashes are ambiguous, preserve the previous verified final and quarantine new evidence with `promotion_conflict`.

## 19. Security and Path Safety

- Resolve the run directory explicitly and enforce containment.
- Reject absolute or escaping paths stored in run artifacts.
- Use no-follow checks for input files and output destinations.
- Reject symlinks, junctions, reparse points, special files, URLs, and external resource references.
- Parse SVG using `defusedxml`.
- Escape all text before constructing OOXML.
- Never execute SVG script, CSS, URL, or embedded content.
- Do not terminate a pre-existing PowerPoint process.
- Do not overwrite files outside `delivery/editable/`.

## 20. Test Strategy

Repository tests use small deterministic fixtures, not the user's external absolute path.

Required regression fixtures cover:

1. deterministic `slides/` preference and approved `samples/` anchor fallback;
2. default namespace and Clark-notation recursive `tspan` handling;
3. mandatory `pathLst` around custom geometry;
4. exact slide dimensions `12192000 × 6858000` EMU;
5. degree × 60000 arc angles and round-halves-away-from-zero integer serialization;
6. corrected-radii propagation when SVG lambda correction is required;
7. nonzero arc rotation rejection;
8. absolute and relative `M/L/H/V/A/Z`, repeated groups, and multiple subpaths;
9. complete path consumption, unknown letters, garbage offsets, malformed arity, invalid flags, and trailing data rejection;
10. leaf opacity × resolved fill/stroke opacity and group-opacity rejection;
11. inline, nested, and line-breaking `tspan`, meaningful whitespace, `xml:space`, `txBox`, and `noAutofit`;
12. nested groups, group inheritance, `descr` trace identity, and z-order;
13. stable naming without `data-source-id`;
14. unsupported-feature zero-output behavior;
15. speaker notes and slide title/description metadata;
16. ZIP/OOXML gate failures and nonzero CLI exits;
17. previous-final, lock, journal, and crash-boundary recovery;
18. all four result states and candidate-write state mapping;
19. full-page, geometry-only, partial-tile, bounds-tolerance, and exact-threshold behavior;
20. PowerPoint PID ownership and cleanup safety;
21. installer discovery, copy, backup, and digest parity for both Skills.

Implementation acceptance also runs against the FY26H1 reference workspace as a non-repository integration corpus. Acceptance requires:

- all 14 pages converted, with S01/S06 resolved from their approved `samples/` anchors and the other pages from `slides/`;
- no image fallback;
- all text editable;
- recursive SVG grouping retained;
- PowerPoint opens without repair;
- source/editable dual-render gates pass;
- object counts are derived from the selected SVG tree rather than copied from the narrative record: the original corpus had 584 visible leaves and 63 groups, but 14 leaves were erroneous visible internal-source labels; the approved machine-only-source-ID migrated reference has 570 `p:sp` leaves plus 63 `p:grpSp` containers (633 total recursive objects). The process record's stated 574 is stale and is not an acceptance oracle;
- the manifest records top-level PowerPoint shape count, recursive leaf count, and recursive group count separately, because `slide.Shapes.Count` does not recursively count group children;

## 21. Deployment

Update host installers from a single hard-coded `ppt-start` copy to validated discovery and copying of both formal Skill directories:

```text
skills/ppt-start/
skills/ppt-editable/
```

Installed invocations:

- Claude Code: `/ppt-editable`
- Codex: `$ppt-editable`
- DeepSeek harness: `ppt-editable`

Backups remain outside Skill scanning roots and only the latest backup per Skill is retained. Deployment verification compares file counts and aggregate tree SHA-256 values for each Skill independently.

## 22. Acceptance Criteria

The feature is complete only when:

- `ppt-editable` is independently discoverable in all three hosts;
- it accepts only a completed PPT Pilot run;
- unsupported SVG features block the complete deck before final output;
- supported shapes and text become native editable PowerPoint objects;
- all SVG groups survive as nested PowerPoint groups;
- source order, styles, text, traceability, notes, and previous-final semantics are preserved;
- absence of PowerPoint produces an explicit `GENERATED_UNVERIFIED`, never a false PASS;
- PowerPoint-enabled verification can produce `PASS` only after normalization, reopen, structural checks, and all visual gates;
- failed verification cannot overwrite a previous final;
- the distilled regression suite and FY26H1 integration corpus both pass;
- the full repository test suite and `git diff --check` pass.
