# Public evidence redaction

The public repository's evidence, documentation, and planning records were captured from real local work and then privacy-redacted for release. Paths and quoted historical command/log fragments containing machine-specific locations are therefore **not byte-for-byte raw output**; only sensitive locations and private example-run identifiers were replaced. Original source hashes, test counts, timestamps, exit codes, results, errors, and `PENDING` distinctions are preserved. Local implementation commit identifiers may remain as provenance in the records even though those private commits are not ancestors of the public release commit.

Placeholder semantics:

- `<USER_HOME>`: the local user's home directory
- `<REPO_ROOT>`: this repository checkout
- `<EXAMPLE_PROJECT>`: the example presentation project
- `<EXPERIMENTS_ROOT>`: the parent experiments directory
- `<GIT_BASH>`: the discovered Git Bash executable
- `<PYTHON_39>`: the Python 3.9 executable used by the recorded command

All redacted paths use `/` separators. Stable example identifiers replace private project/run names where needed; `jiawei-product` remains an actual plugin/style identifier and is not a machine identity.
