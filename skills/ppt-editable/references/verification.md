# Verification gates

All authoritative threshold and render-size values come from [verification-config.json](../assets/verification-config.json). Do not copy those configured values into prose, scripts, or prompts.

## Pre-Office gates

1. Candidate bytes are atomically written, reread, and hash-checked.
2. ZIP entries, CRCs, content types, relationships, slide order, dimensions, and image/media prohibitions pass.
3. Recursive group/leaf identity, order, counts, native geometry, text runs, notes, titles, descriptions, bounds, flips, and source-derived custom geometry pass.
4. Visible text contains no internal `SRC-<digits>` IDs; machine trace metadata remains present.

A required structural/content failure produces `FAILED_VERIFICATION`, keeps public authority unchanged, and retains evidence.

## Capability degradation

PowerPoint and Pillow are optional verification capabilities, not auto-installed dependencies. If either is unavailable after pre-Office gates pass, publish only the distinct unverified output with `GENERATED_UNVERIFIED`. This can never become `PASS` by assumption.

## Office gates

The Python request/result protocol binds candidate, normalized and geometry decks, selected and geometry SVGs, exact ordered IDs/counts/config, and four render streams.

The adapter:

- owns a PowerPoint process only when a complete pre-snapshot proves its PID/start identity is new;
- never quits or kills a pre-existing process;
- normalizes, reopens, recursively counts, and exports through the same application;
- releases every opened/created presentation and COM object in `finally`.

The normalized candidate is rechecked by the complete structural verifier.

## Visual gates

Compare source/editable full renders and source/editable geometry-only renders at configured size. Full, geometry, and nonoverlapping tile metrics use inclusive thresholds. Partial edge tiles use their actual area. No resize or downsample is allowed.

Per-slide full/geometry difference images and tile JSON are persisted atomically before the ordered summary. Metrics are diagnostic evidence; they do not authorize promotion by themselves.

## Promotion

Only a candidate that passes structural, Office, normalized, and visual gates can produce `PASS`. Promotion replaces the verified target, rehashes it, then writes `editable-result.json` last. Failed gates never replace a previous verified final.

## Exit codes

Public generator and verifier use:

- `0`: PASS or valid degraded unverified result;
- `2`: blocked or failed verification;
- `3`: invalid invocation/configuration;
- `4`: unexpected execution or report-write failure.
