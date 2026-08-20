# Resume After Manuscript Approval Scenario

## Setup

Create `ppt-output/resume-approved/` and use `tests/fixtures/run-review-approved.json` as its starting `run.json`. This is a legacy English-name compatibility fixture. The run is already `manuscript_approved`; the five frozen manuscript files and `manuscript-review.md` exist and match its review history. Preserve those filenames exactly: read them in place and do not rename, copy, or migrate them.

## Task

Resume the deck in auto mode and continue through theme and anchor generation. Read run.json first and use only the workspace artifacts as handoff context.

## Expected behavior

- [ ] Validate the existing `manuscript_approved` state and review history.
- [ ] Do not repeat research, briefing, outlining, storyboarding, or manuscript review.
- [ ] Select a bundled style and write `theme.json`.
- [ ] Generate and validate the cover anchor and hardest-content anchor.
- [ ] Update `run.json` after each durable stage before later slide production.
- [ ] If a required approved artifact is missing or malformed, mark the correct stage dirty instead of silently rebuilding unrelated upstream work.
