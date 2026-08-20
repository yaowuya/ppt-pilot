# Resume Pending Interaction Scenario

## Setup

Create `ppt-output/pending-outline-approval/` and copy `tests/fixtures/run-pending-interaction.json` to it as `run.json`. Assume the approved brief, research, sources, and current outline artifacts already exist and match the recorded `outline` stage.

## Task

Resume the run using only workspace artifacts. Read run.json first and resolve its durable interaction state before doing other work.

## Expected behavior

- [ ] Detect `pending_interaction.status: pending` before searching for another incomplete stage.
- [ ] Present the same pending question, options, option effects, recommendation, and recommendation reason recorded in `run.json`; do not ask a new question.
- [ ] Stop without generating the storyboard. Do not repeat briefing, research, source inventory, or outlining.
- [ ] After an explicit finite-choice answer, first persist `status: answered`, the original `answer`, and a normalized `decision` from `options` while stage remains `outline`, so a crash cannot cause the question to be repeated or reinterpreted.
- [ ] Apply the answer idempotently. For approval, atomically replace `run.json` so `stage: storyboard` and removal of the old object become visible together; this single commit must remove pending_interaction and must never expose a new stage with the old interaction.
- [ ] If the answer requests revision without a concrete scope, remain at `outline`, write one `clarification_pending` user revision record keyed by the interaction ID, and atomically replace the answered object with one focused `revision-clarification` pending question.
- [ ] If an already-answered interaction is supplied on resume, consume its saved `decision` without repeating the approval question or duplicating its revision record.
- [ ] If the interaction object is malformed, stop and report the conflict instead of guessing or rebuilding upstream work.
