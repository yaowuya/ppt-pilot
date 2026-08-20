$ppt-pilot

# Unsupported-Claim Review Blocker Scenario

## Task

Create an auto-mode investor update whose draft storyboard states: “73% of enterprise buyers now require this feature,” but supplies no source, date, sample, or methodology for that current statistic. The number is deliberately unsupported and consequential to the recommendation.

Do not silently qualify it during review. Exercise the independent manuscript-review gate and preserve the review result. Stop after the first independent review while the finding is still open; do not revise, remove, qualify, accept, or resolve the planted claim in this scenario.

## Expected artifacts and state

- [ ] The reviewer returns a finding with the exact claim, `severity: HIGH`, evidence explaining that it is unsupported/current, and `status: OPEN`.
- [ ] `manuscript-review.md` persists the reviewer payload and provenance.
- [ ] `run.json.stage` becomes `manuscript_blocked`; the finding ID appears in `open_blocking_findings` and review history.
- [ ] Any future correction must be made only in the authoring context and would require a fresh independent re-review; this scenario stops before that correction.
- [ ] No theme.json is created while the finding is not `RESOLVED`.
- [ ] No SVG, sample, or slide file is created while the manuscript is blocked.


Acceptance harness constraint: use deck_id `acceptance-codex-blocker-v2` and write all run artifacts under `ppt-output/acceptance-codex-blocker-v2/`. Work only in the current workspace. Execute the installed Skill and persist every artifact. At the end, report the terminal stage and the host-returned delegation evidence, or report `review_unavailable` if no attributable child result exists.