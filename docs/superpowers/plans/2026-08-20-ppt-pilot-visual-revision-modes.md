# PPT Pilot Visual Revision Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist visual revision precedence and deterministically separate local `patch` work from blank-canvas `recompose` work.

**Architecture:** Use `run.json.interaction_history` as the authoritative revision ledger with `supersedes`; mirror current decisions into theme/page briefs. Classify revision input before SVG work and preserve manuscript invalidation for factual changes.

**Tech Stack:** Markdown contracts, JSON fixtures, Python `unittest` contract tests.

## Global Constraints

- This is Plan 3 of 7 and depends on the visual brief fixtures and contract wiring plans.
- Do not modify FY26 run artifacts or SVGs.
- Do not add model calls, runtime dependencies, or live host tests.
- Use synthetic fixtures only; preserve existing manuscript review behavior.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Persist visual revision precedence

**Files:**
- Modify: `skills/ppt-start/references/artifact-contract.md:57-65,126-136`
- Modify: `skills/ppt-start/references/interaction-protocol.md:76-129`
- Modify: `skills/ppt-start/references/design-system.md:17-29`
- Modify: `tests/test_interaction_protocol.py:374-447`
- Test: `tests/test_visual_generation_contract.py`

**Interfaces:**
- Consumes: direct visual user instructions and guided anchor revision answers.
- Produces: authoritative `visual-revision-<N>` records, `supersedes`, active theme mirror, and page brief mirror.

- [ ] **Step 1: Add failing interaction-history assertions**

Extend `tests/test_interaction_protocol.py` with:

```python
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
```

Run:

```bash
python -m unittest tests.test_interaction_protocol.InteractionProtocolTests.test_direct_visual_revisions_are_durable_and_precedence_aware -v
```

Expected: FAIL because direct visual-revision records are not yet documented.

- [ ] **Step 2: Define direct visual-revision records**

Add to `artifact-contract.md`:

```markdown
已经执行的直接视觉修订即使不来自 pending_interaction，也必须立即写入 interaction_history。键使用单调 `visual-revision-<N>`；记录包含 `stage`、`kind: visual_revision`、原始 `answer`、`normalized_changes`、`affected_scope`、`supersedes`、`status: applied` 和 `artifact_owner`。
```

Add this exact ownership rule:

```markdown
`affected_scope: deck` 或主题／品牌决定镜像到 `theme.json.user_revision_notes`；具体页面决定镜像到对应 `visual-briefs/<slide-id>.md`。镜像可以从历史重建，`run.json.interaction_history` 是权威记录并且必须跨失效保留。
```

- [ ] **Step 3: Define reduction and conflict rules**

Add the exact five layers and behavior to `design-system.md` and `interaction-protocol.md`:

```markdown
不可覆盖内容／证据／兼容性规则 > seed defaults > latest deck theme/brand decision > latest scoped slide decision > local patch defect.
```

Require explicit `supersedes` for a replaced field. Keep superseded records in history, exclude them from the active contract, and stop when coexistence versus replacement is ambiguous.

- [ ] **Step 4: Run interaction and visual contract tests**

Run:

```bash
python -m unittest tests.test_interaction_protocol tests.test_visual_generation_contract -v
```

Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Record that direct and guided visual revisions now share one durable history model and that no visual content was generated.

### Task 2: Implement deterministic patch/recompose behavior

**Files:**
- Modify: `skills/ppt-start/references/qa-and-revision.md:63-70,119-130`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `tests/prompts/revise-single-slide.md`
- Modify: `tests/test_workflow_contract.py:366-481`
- Test: `tests/test_visual_generation_contract.py`

**Interfaces:**
- Consumes: a classified visual revision request and current page brief.
- Produces: either a bounded local patch input or a blank-canvas recompose input; factual changes continue to the manuscript path.

- [ ] **Step 1: Expand the revision behavior prompt into three independent branches**

Replace `tests/prompts/revise-single-slide.md` with three branches:

```markdown
# Revise One Slide Scenario

Start each branch from a separate complete approved synthetic run.

## Branch A — patch
On S05, move one card exactly 24 px to restore alignment and correct a non-factual typo.
Expected: classify as patch; preserve composition and manuscript approval; read full brief + current SVG + exact defect; dirty only S05 SVG and QA.

## Branch B — recompose
On S05, make the focal point stronger, change card density, and use a supplied visual reference while preserving all claims and source IDs.
Expected: classify as recompose; rebuild S05 brief and SVG; do not use old SVG as a geometric base; preserve manuscript approval; dirty only S05 brief/SVG and QA.

## Branch C — factual change
On S05, change a sourced 12% result to 27% and point it to another source.
Expected: not patch or recompose; invalidate manuscript approval and all dependent visual artifacts; require a fresh independent review before SVG generation.
```

- [ ] **Step 2: Add failing branch-token assertions**

In `tests/test_workflow_contract.py`, replace the current revise token list with:

```python
for token in (
    "branch a — patch",
    "branch b — recompose",
    "branch c — factual change",
    "24 px",
    "full brief + current svg + exact defect",
    "do not use old svg as a geometric base",
    "fresh independent review",
):
    self.assertIn(token, revise)
```

Run the focused test and expect failure until the prompt and QA contract are updated.

- [ ] **Step 3: Define deterministic classification in QA**

Add to `qa-and-revision.md`:

```markdown
`patch` applies only to measurable local defects that preserve accepted composition: collision, overflow, token mismatch, small alignment shift, connector defect, or non-factual typo.

`recompose` is mandatory for focal point, hierarchy, reading path, layout family, card density, nesting, typography system, semantic color, brand direction, a new visual reference, “重新优化/更高级”, or accumulated visual debt.
```

State exact inputs:

```text
patch = complete brief + current SVG + one exact defect
recompose = complete brief + locked storyboard + active theme
```

For recompose, prohibit the old SVG as a geometric base. Reset fix attempts for the new candidate, then allow at most two hard-failure patches before existing single/two-column fallback.

- [ ] **Step 4: Add rendered design-quality checks**

Add to `qa-and-revision.md`:

- 3-second focal recognition;
- first/second/third scan order;
- primary dominance over secondary information;
- title/proposition/section/body/support/micro typography ladder;
- semantic color roles;
- card grouping rather than equal-weight wallpaper;
- evidence boundary and falsifiability for hypothesis pages;
- visual debt from repeated patching.

Require specific rendered issues and a patch/recompose classification instead of a vague “continue optimizing” note.

- [ ] **Step 5: Run focused revision tests**

Run:

```bash
python -m unittest tests.test_workflow_contract tests.test_visual_generation_contract -v
```

Expected: PASS.

- [ ] **Step 6: Run the plan checkpoint suite**

Run:

```bash
python -m unittest tests.test_visual_generation_contract tests.test_interaction_protocol tests.test_workflow_contract -v
```

Expected: PASS with no skipped or live-host tests.

- [ ] **Step 7: Record checkpoint**

Record the exact test count and duration. Stop before Plan 2 if any focused test fails.
