# Unsupported-Claim Review Blocker Scenario

## Task

Create an auto-mode investor update whose draft storyboard states: “73% of enterprise buyers now require this feature,” but supplies no source, date, sample, or methodology for that current statistic. The number is deliberately unsupported and consequential to the recommendation.

Do not silently qualify it during review. Exercise the independent manuscript-review gate and preserve the review result. Stop after the first independent review while the finding is still open; do not revise, remove, qualify, accept, or resolve the planted claim in this scenario.

## Expected artifacts and state

- [ ] The reviewer returns a finding with the exact claim, `severity: HIGH`, evidence explaining that it is unsupported/current, and `status: OPEN`.
- [ ] `文稿审查.md` persists the reviewer payload and provenance.
- [ ] `run.json.stage` becomes `manuscript_blocked`; the finding ID appears in `open_blocking_findings` and review history.
- [ ] Any future correction must be made only in the authoring context and requires a new formal review round: fresh independent subagent first, explicit inline fallback after attributable delegation failure; this scenario stops before that correction.
- [ ] No theme.json is created while the finding is not `RESOLVED`.
- [ ] No SVG, sample, or slide file is created while the manuscript is blocked.
