$ppt-pilot

# Resume After Manuscript Approval Scenario

## Setup

Create `ppt-output/resume-approved/` and use `tests/fixtures/run-review-approved.json` as its starting `run.json`. The run is already `manuscript_approved`; assume the five frozen manuscript files and `manuscript-review.md` exist and match its review history.

## Task

Resume the deck in auto mode and continue through theme and anchor generation. Read run.json first and use only the workspace artifacts as handoff context.

## Expected behavior

- [ ] Validate the existing `manuscript_approved` state and review history.
- [ ] Do not repeat research, briefing, outlining, storyboarding, or manuscript review.
- [ ] Select a bundled style and write `theme.json`.
- [ ] Generate and validate the cover anchor and hardest-content anchor.
- [ ] Update `run.json` after each durable stage before later slide production.
- [ ] If a required approved artifact is missing or malformed, mark the correct stage dirty instead of silently rebuilding unrelated upstream work.


Acceptance harness constraint: the complete synthetic approved fixture and its source inputs are staged. Execute the installed Skill in this workspace. Validate the exact run schema and recorded delegation-evidence fields; continue only through theme and two validated anchor SVGs, then stop before final production. Do not rerun manuscript work. For every anchor, enforce the full 64 px safe rectangle including title, footer/source, and page number. If rendered QA is recorded, persist the rendering method and a durable evidence path inside this run workspace.