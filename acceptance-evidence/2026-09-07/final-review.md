# Final whole-approved-change review — cc8b1cf..6fff469

Reviewer: /root/runtime_final_review, gpt-6-astra. Read-only; no source/index/HEAD changes. Verdict: With fixes. No Critical findings.

## Important findings (verbatim)

1. **Existing owned anchor samples prevent anchor regeneration.**
   `_runtime_commands.py:561` accepts only an absent sample or bytes already matching the new candidate. A prior canonical anchor sample therefore blocks publication after anchor re-entry or revision.
   **Reproduced:** retained the installed-copy fixture’s `run.anchor`-bound sample, entered `anchor`, and completed reserve → bind → ingest → validation. `resume` returned `publish-anchors`; publication returned `BLOCKED / anchor_sample_conflict`, with zero writes. Existing publication tests delete the previous sample first.
   **Fix:** support replacement with proven prior ownership and CAS, or use transaction-specific sample paths. Preserve unrelated changes and require approval of the newly returned digest. Cover ordinary and source anchor revisions.

2. **Claude snapshot preparation can bypass the required partial-failure report.**
   `update-hosts.ps1:110` creates and copies snapshots before the function’s `try`; its user-scope invocation at line 148 is also unguarded. If DeepSeek has already updated and copying an existing Claude target fails—for example, on an unreadable file—the script terminates before emitting `PARTIAL_FAILURE` and its destination lists. Snapshot cleanup is also bypassed.
   **Fix:** include snapshot preparation inside guarded cleanup and aggregate this failure at the user-scope boundary. Test a snapshot-copy failure following an earlier successful destination.

3. **DeepSeek skips shadowing-Skill inventory.**
   `install-deepseek-plugin.ps1:134` updates the three named directories directly through `Install-PptPilotTree`. It never invokes the duplicate-discovery check used by `Install-SkillsRoot`. An existing direct child such as `skills/legacy-ppt/SKILL.md` declaring `name: ppt-start` therefore survives while deployment reports success. The manifest exposes the entire `./skills/` directory.
   **Fix:** move the inventory check into shared packaging code and invoke it for DeepSeek before mutation. Add a DeepSeek shadow fixture that proves nonzero failure, names the path, and preserves installed bytes.

## Minor triage

- `_runtime_commands.py:54`: 770-line lifecycle class remains a reasonable deferred maintainability item; later dispatch/QA/publication extraction, not independently blocking.
- TemporaryDirectory warning: changed test allocations inspected, use context managers or registered cleanup. Origin unconfirmed; not attributed to this change and no broad rerun solely for warning requested.

## Assessment

Shared firewall, CAS, durable reservations, recovery journals, and anchor identities are sound architectural direction. Keep synchronized installation and live-host acceptance pending; tests/pressure do not establish actual hosts. Reconcile early real-project-copy disclosure. Resolve all three Important findings in one final fix wave, followed by one scoped re-review and final verification.
