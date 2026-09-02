# Input/output and state contract

## Input

Input is one completed PPT Pilot run, never an arbitrary SVG directory. run selection precedence is:

1. explicit run directory;
2. valid completed current run;
3. exactly one completed run under `ppt-output/`.

The authoritative storyboard owns the exact ordered page set. `slides/<slide-id>.svg` is the production owner. `samples/<slide-id>.svg` is legal only for the exact approved anchor recorded by run control.

## Snapshot

The canonical snapshot hashes:

- actual selected SVG bytes;
- slide ID, run-relative path, and source owner;
- storyboard note fields;
- converter/subset versions;
- exact verification config bytes.

Canonical JSON uses sorted keys, compact separators, UTF-8, and no path aliases. Same snapshot plus coherent committed output is idempotent; changed input creates a new identity.

## Output paths

All writes stay under `delivery/editable/`:

- `<deck-id>-editable.pptx`
- `<deck-id>-editable-unverified.pptx`
- `editable-result.json`
- `.tmp/` transaction/work evidence
- `quarantine/` failed or ambiguous evidence

A `PASS` touches only the verified filename. `GENERATED_UNVERIFIED` touches only the unverified filename. A failed or blocked run never replaces public authority.

## Lock, journal, and recovery

One OS-backed lock covers recovery, generation, and promotion. Lock-file existence alone is not ownership.

Each promotion writes a `PREPARED` journal with snapshot, target kind/path, new hash, previous target hash, previous manifest hash, and backup names. Promotion order is:

1. atomically write and reread the journal;
2. replace and hash-check the public target;
3. replace `editable-result.json` last;
4. remove transaction evidence only after committed hashes match.

Recovery recognizes coherent committed, previous, new, and ambiguous states. Coherent previous public authority wins before untrusted backups. Invalid journals cannot manufacture authority. Ambiguous bytes are quarantined.

## Commit record and states

`editable-result.json` is the only commit record. Uncommitted files are never adopted by existence.

- `PASS`: verified output is authoritative.
- `GENERATED_UNVERIFIED`: unverified output is published separately; prior PASS remains authoritative when present.
- `BLOCKED`: no candidate is published.
- `FAILED_VERIFICATION`: no candidate is published; evidence is retained.

Never mutate `.ppt-pilot/run.json`.
