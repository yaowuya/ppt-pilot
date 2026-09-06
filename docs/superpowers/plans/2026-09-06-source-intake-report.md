# Task 1 source-intake implementation report

## Scope

Implemented only Task 1 in:

- `skills/ppt-start/scripts/_source_intake.py`
- `skills/ppt-start/scripts/ppt_source_intake.py`
- `tests/test_source_intake.py`

No commits, installs, reference-directory changes, or source-deck fixtures were made.

## Behavior delivered

- `extract_pptx(path) -> dict` emits schema version 1 inventories with source identity,
  relationship-ordered slides, slide XML hashes, hidden state, paragraphs, tables,
  notes, embedded-object metadata, and visual-review warnings.
- The parser reads one immutable in-memory snapshot of the source package, never extracts
  files, ignores external relationship targets, and explicitly rejects binary `.ppt`,
  malformed/encrypted ZIP input, unsafe or non-canonical paths, duplicate members,
  missing slide relationships/parts, forbidden DOCTYPE/entity declarations, and the
  10,000-member / 32 MiB-member / 256 MiB-total limits.
- The CLI validates the complete source before opening the output with exclusive `xb`;
  it requires an existing parent, never overwrites, and removes only an output it created
  if writing that output fails.

## TDD evidence

Initial RED command:

`py -3 -m unittest discover -s tests -p test_source_intake.py -v`

Result: exit 1. The expected implementation failure was
`ModuleNotFoundError: No module named '_source_intake'`. The restricted Windows sandbox
also independently denied temporary-directory access, so subsequent focused runs used
the explicitly approved unrestricted test command as required by the task brief.

Additional behavioral RED evidence:

- The corrected no-text fixture failed because it still produced `[' tail']`; fixing the
  synthetic OOXML fixture made it exercise `NO_EXTRACTABLE_TEXT` correctly.
- The non-canonical ZIP member `ppt//odd.xml` initially was accepted; tightening package
  path canonicalization made the regression test pass.

Final GREEN command (fresh run):

`py -3 -m unittest discover -s tests -p test_source_intake.py -v`

Result: exit 0, 5 tests run, all `ok`, `Ran 5 tests in 0.793s`, `OK`.

Covered behaviors include reordered presentation relationships and independent source
digest, source preservation, text/table/notes extraction, hidden slides, image object and
visual warnings, no-text warnings, external relationships, missing relationships,
traversal/non-canonical/duplicate package names, forbidden XML declarations, wrong format,
oversized members, successful CLI output, exclusive no-overwrite, and zero output on
invalid-source failure.

## Self-review notes

- Budget enforcement for member count, total uncompressed bytes, and encrypted entries is
  implemented directly; the focused suite exercises the 32 MiB boundary, while the other
  two limits are not inflated into large synthetic fixtures to keep the suite lightweight.
- Object extraction is intentionally an inventory, not a claim of visual or semantic
  understanding. Slides containing image/chart/SmartArt/OLE/group-like objects receive a
  visual-review warning, and textless slides receive a separate warning.

## Review fixes (2026-09-06)

The reviewer subsequently took implementation ownership for this fix pass. This section
is implementation evidence, not independent final approval.

- XML parsing now rejects DOCTYPE through an ElementTree parser target callback, including
  UTF-16LE and UTF-16BE inputs. Every `.xml` and `.rels` package member is checked before
  inventory extraction, including unselected parts. Valid UTF-16 slide XML remains accepted.
- Presentation, relationship, slide and notes roots are checked against their expected
  namespace-qualified names. Empty slide inventories, missing/duplicate slide identifiers,
  and repeated source slide parts are rejected.
- Referenced slide/notes relationship IDs must resolve; internal relationship targets must
  exist. External targets remain unfetched. Invalid TargetMode values are rejected.
- The source snapshot has a 272 MiB cap (256 MiB content budget plus 16 MiB package
  overhead). A stat check rejects oversized sources before opening them, and a bounded
  read also handles growth between the check and read. Existing uncompressed budgets remain.
- SmartArt `r:dm`, `r:lo`, `r:qs`, and `r:cs` identifiers are retained alongside chart,
  OLE, and group metadata. Added fixtures verify these and paragraph whitespace/newlines.
- No changes were necessary to the exclusive-output CLI.

Focused command throughout (approved escalation for temporary-directory access):

`py -3 -m unittest discover -s tests -p test_source_intake.py -v`

RED before implementation: 8 tests, 12 failures and 1 error; both UTF-16 declarations,
dangling image references, wrong roots, empty/duplicate inventories, and early source-size
checking failed. The SmartArt fixture exposed missing relationship metadata.

An additional RED for an unused XML part containing a UTF-16 declaration produced
9 tests with 1 failure. This drove package-wide XML validation.

Final GREEN: exit 0, 9 tests, `Ran 9 tests in 2.240s`, `OK`. The existing source-preservation,
external-relationship, budget, exclusive-output and failure-zero-output tests also passed.
No commits, subagents, or unrelated-file changes were made in this pass.

### OPC package-root URI compatibility correction

Internal relationship targets such as `/ppt/slides/slide1.xml` and
`/ppt/media/image1.png` now resolve from the ZIP package root by removing exactly one
leading slash, then applying package member validation and existing member-existence
checks. They are never interpreted as filesystem paths. Double-slash authorities,
root-target traversal, drive/URL colons, and backslashes are rejected; ordinary
package-contained relative `../media/...` relationships remain valid. Source/output
filesystem handling is unchanged.

Added RED tests for root-relative slide/image relationships and unsafe target forms.
The focused suite initially reported 11 tests, 2 failures and 1 error (valid root URI
rejected; drive/URL targets normalized without rejection). After the correction, the
same approved command passed: exit 0, `Ran 11 tests in 3.038s`, `OK`.
