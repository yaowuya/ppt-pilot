# Final scoped re-review — 6fff469..219c13d

Reviewer: `/root/final_fix_review`. Recorded 2026-09-08 from the completed reviewer response. This is a scoped re-review of all three Important findings in [final-review.md](final-review.md); it is not a new broad review or live-host acceptance.

## Findings

- **Existing owned anchor samples prevent anchor regeneration — ADDRESSED.** Ordinary/source prior owner file maps establish exact old bytes; all samples are preflighted and writes use digest CAS. Publication computes a new identity without recording approval; promotion requires a matching applied approval. Tests preserve old samples/finals, reject stale approval, accept actual new approval, preserve third-party files and cover a CAS race. Evidence: `_runtime_commands.py:510,558,562,574`, `_run_store.py:99`, `tests/test_ppt_runtime.py:568,628,654` at `219c13d`.
- **Claude snapshot preparation bypasses partial-failure reporting — ADDRESSED.** Snapshot creation/copy is cleanup-protected before mutation; the user-scope call catches preparation errors and aggregation reports actual updated/rolled-back/failed targets. The snapshot-copy injection follows successful DeepSeek installation and verifies reporting, unchanged Claude bytes and snapshot cleanup. Evidence: `tools/update-hosts.ps1:99,121,136,164`, `tests/test_tools_package.py:339` at `219c13d`.
- **DeepSeek skips shadowing-Skill inventory — ADDRESSED.** Shared direct-child inventory recognizes aliases for all three known Skill names. DeepSeek invokes it before transaction creation or installation mutation. The regression proves nonzero failure, concrete path disclosure and byte preservation. Evidence: `tools/packaging.ps1:5`, `tools/install-deepseek-plugin.ps1:15,127,129`, `tests/test_tools_package.py:387` at `219c13d`.

## Checks and verdict

No new breakage in the fix diff. No out-of-scope observations. Covering suites were not redundantly rerun by the reviewer; [final-fix-report.md](final-fix-report.md) contains meaningful RED failures and GREEN runs (installer 17, anchor 10 on Python 3.13 and 3.9, source approval 2). Interpreter identities were checked: Python 3.13.7 and Python 3.9.13. The coordinator separately ran the final integrated 781-test suite on the same source commit.

Reviewer verdict: **Fix round: All findings addressed, no new Critical/Important breakage.**
