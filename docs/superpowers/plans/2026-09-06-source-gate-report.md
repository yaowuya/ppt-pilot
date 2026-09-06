# Task 2 source workflow gate implementation evidence

Implemented only the assigned gate modules and behavioral tests, plus this report. No commits, installations, reference-directory changes or customer source data were made by this worker. Core gate and phase evidence live in separate modules, each below 450 lines.

## RED / GREEN

- Initial RED: `py -3 -m unittest discover -s tests -p test_source_workflow_gate.py -v` exited 1: one import error, `ModuleNotFoundError: No module named '_workflow_gate'`, before implementation existed.
- The first implemented focused run encountered Windows restricted-environment `PermissionError` creating/cleaning ordinary `tempfile.TemporaryDirectory` fixtures (26 tests, 52 setup/cleanup errors). This was environmental, not treated as a passing or behavioral result. Subsequent focused commands used approved normal temporary-directory permissions (`require_escalated`).
- First GREEN: the same `-v` command exited 0, 26 tests passed.
- Additional behavior RED: `py -3 -m unittest discover -s tests -p test_source_workflow_gate.py -q` exited 1 with two failures in 35 tests: non-SVG anchor accepted; snapshot rejected an empty log file. Fixed shared SVG verification and diagnostic empty-file hashing.
- Additional behavior RED: the same `-q` command exited 1 with three failures in 38 tests: non-PNG render accepted, invalid SVG viewBox accepted, and guided approval selection depended on dictionary insertion order. Added PNG header validation, finite positive SVG viewBox, and maximum unique positive approval_attempt selection among checkpoint approval records.
- Additional behavior RED: the same `-q` command exited 1 with two failures in 40 tests: reordered older PASS hid a later round; unresolved historical HIGH finding disappeared. Added chronological unique cycle/round checks and historical blocker continuity.
- Final GREEN: `py -3 -m unittest discover -s tests -p test_source_workflow_gate.py -q` exited 0: `Ran 40 tests in 6.023s`, `OK (skipped=1)`.
- Optimization GREEN: `py -3 -O -m unittest discover -s tests -p test_source_workflow_gate.py -q` exited 0: `Ran 40 tests in 5.267s`, `OK (skipped=1)`.

The skipped test attempts actual filesystem symlink creation, which this Windows environment does not grant. Unsafe absolute/traversal paths are exercised normally; symlink and junction rejection is implemented but that integration case was not executed here.

## Exercised behavior

Real temporary files and actual CLI subprocesses cover all nine cumulative stages, missing upstream files despite a late stage label, frozen manuscript hashes, current source/inventory/mapping bindings, coverage/cardinality, explicit applied authorization for nondefault mapping, warned-page visual audit records, current guided brief/outline approval hashes, latest approval attempt ordering, formal review evidence and counters, unresolved findings, current target style identity, anchor hashes/status, final SVG existence, PNG render/input/current SVG hash binding, manual PASS status, dirty slides, five-control recovery priority, malformed JSON/types/versions, duplicate JSON keys, non-import NOT_APPLICABLE, `--snapshot`, optimization mode and unchanged file bytes.

New import formal review snapshots keep their existing `files` list and add `file_hashes`; the latter must equal both the checkpoint manuscript map and current files. Updating only checkpoint hashes cannot retrofit changed inputs to an old frozen review. `--snapshot` emits diagnostic `status: SNAPSHOT`, current hash map and explicit nonapproval notice; it never writes or emits a replacement manuscript approval record.

## Deliberate limits

- This is an additive source-import consistency gate, not the entire pre-existing workflow implementation or a host execution interceptor. Runs without source_deck return NOT_APPLICABLE, not global workflow PASS.
- The gate checks source bytes against the inventory binding and audit-bound inventory. It does not rerun extraction or independently attest deliberately forged inventory, reviewer execution, interaction history, manual visual verdicts or provenance records. Those remain auditable author/host records.
- PNG is the supported render evidence format. Checks cover signature, IHDR size, header CRC, supported IHDR fields and positive dimensions, plus stored current render/input hashes. They do not perform a complete PNG decode or establish that the pixels visually match the slide.
- SVG checks establish XML root and valid viewBox, reject DTD/entity declarations, and bind hashes. The existing full Office-safe SVG and style traversal/preflight gates remain required.
- Synthetic PNG and SVG fixture files exercise binding and validation logic; no test result here claims an actual renderer or manual visual review ran.

## Final review fix wave

Three independent-review defects were reproduced before changes: source inputs were not rechecked inside active-batch recovery; any applied history record could authorize a nondefault mapping even when its decision was negative or unrelated; and the SVG ASCII declaration scan allowed UTF-16 DTD/entity input. The required final SVG canvas was also tightened to `viewBox="0 0 1280 720"`.

- RED: `py -3 -m unittest discover -s tests -p test_source_workflow_recovery.py -q` exited 1: `Ran 7 tests in 0.597s`, `FAILED (failures=3, errors=4)`. Four errors identified the absent active-recovery entry point; three failures reproduced negative mapping authorization, wrong canvas acceptance and UTF-16 SVG declaration acceptance.
- GREEN: `py -3 -m unittest discover -s tests -p test_source_workflow*.py -q` exited 0: `Ran 47 tests in 5.641s`, `OK (skipped=1)`.
- Shared-parser compatibility: `py -3 -m unittest discover -s tests -p test_source_intake.py -q` exited 0: `Ran 11 tests in 2.397s`, `OK`.
- Final combined optimized GREEN, including the controller's source integration tests: `py -3 -O -m unittest discover -s tests -p test_source_*.py -q` exited 0: `Ran 63 tests in 11.402s`, `OK (skipped=1)`.

`check_active_batch(run_dir)` and CLI `--resume-active-batch` require an existing schema-v2 pointer and readable matching manifest plus current stage anchor/production. They check higher-priority controls first, then run cumulative import input checks for that phase. Ordinary `--before` still blocks any active batch. The new entry point performs no recovery writes, adoption, dispatch or promotion and does not replace the original coordinator's full transaction/manifest validation. Its caller must use it before those recovery side effects; this is an input consistency preflight, not transaction approval.

Mapping authorizations now require an applied `decision: approve`, `kind: authorization` history record and a `source_mapping_authorizations` entry equal to the current source digest, source slide ID, action and ordered targets. One authorization can explicitly cover multiple rows. Negative decisions and different source/page/action/target scopes fail closed.

The shared `_xml_safety.parse_xml` uses an encoding-aware XML parser callback to reject declarations. Intake retains `_parse_xml` as an import alias. Tests cover malicious and benign UTF-16 LE/BE plus expected-root validation. SVG root/canvas checks remain supplemental to the existing full Office-safe checks. New regression tests are in `test_source_workflow_recovery.py`; the existing gate test file remains below 450 lines.
