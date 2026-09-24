---
name: ppt-start
description: Use when creating, resuming, redesigning, or revising an evidence-backed presentation whose final pages are standalone Office-safe SVG files.
---

# PPT Pilot

## Ownership

AI is the only workflow coordinator. It reads the workspace, chooses the next action, writes artifacts, and maintains `.ppt-pilot/run.json`. Packaged scripts are stateless artifact tools; their availability never owns a stage, retry, user decision, or recovery path.

Do not require Git, a worktree, a workflow runner, a host registry, a dashboard, a hidden queue, or a polling loop. Never create helper programs or dependencies inside a presentation run.

## Run one action

1. Select an existing run or create a non-conflicting `ppt-output/<deck-id>/`.
2. Read `run.json`, the artifacts for its current stage, and the actual files in `slides/`.
3. If `pending_interaction` exists, replay or apply that decision first. Otherwise choose the earliest executable action.
4. Perform one action. A turn may make at most one real generator call for one page.
5. Write and reread the artifact evidence, then atomically update `run.json`.
6. Report what completed, any degraded tool evidence, failed/skipped pages, the next action, and any decision needed from the user.

Read [AI state](references/ai-state.md) whenever creating, resuming, retrying, skipping, revising, or finalizing a run. Read [interaction](references/interaction-protocol.md) only when a user decision is pending or has just been answered.

## Content path

`brief → research → outline → storyboard → manuscript_review`

- For brief, evidence, confidentiality, and research, read [brief and research](references/brief-and-research.md).
- For the argument, outline, and storyboard, read [narrative and storyboard](references/narrative-and-storyboard.md).
- Before any visual work, complete [manuscript review](references/manuscript-review.md). Unresolved `BLOCKER` or `HIGH` findings stop visual production.

`guided` requires explicit approval at brief, outline, and anchor checkpoints. `auto` is used only when the user explicitly requests it; it skips optional approvals, not permission questions or quality gates.

## Visual path

`theme → anchor → production → qa → complete|partial|failed`

- For theme selection and visual rules, read [design system](references/design-system.md) and, when choosing a layout, [layout catalog](references/layout-catalog.md).
- For compiling and dispatching one complete page Prompt, read [Prompt and generation](references/visual-brief-and-generation.md) and [Prompt byte grammar](references/generation-prompt-byte-grammar.md).
- For artifact safety and source metadata, read [SVG contract](references/svg-contract.md).
- For page-local recovery, truthfulness, and final partitioning, read [QA and revision](references/qa-and-revision.md) and [artifact contract](references/artifact-contract.md).

Save each complete Prompt at `.ppt-pilot/generation-prompts/<slide-id>.md`, then pass those Prompt bytes—not the path—to an available fresh-context generator. The generator returns one XML fence and owns no files or state. AI validates and promotes the result. A generator/tool failure is page-local; independent pages continue.

## Retained tools

- `scripts/svg_tool.py`: extract, normalize, finalize, and validate explicit SVG inputs.
- `scripts/ppt_source_intake.py`: inventory one explicit `.pptx` source without extracting or modifying it.
- `_svg_runtime.py`, `_svg_geometry.py`, `_xml_safety.py`, `_source_intake.py`: private pure implementations used by those CLIs.

Tool outcomes are `PASS`, `INVALID`, or `UNAVAILABLE`. `INVALID` may reject only the supplied artifact/page. `UNAVAILABLE` means the tool proved nothing: record the degradation and continue with direct AI inspection without claiming a tool PASS. Only a real generator call increments page `attempts`.

Use `ppt-editable` only after SVG completeness is honestly finalized. Editable conversion is optional post-processing and never advances or reopens this workflow.
