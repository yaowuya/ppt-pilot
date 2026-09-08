# Coordinator rulings — exact ledger extract

All 13 lines containing `Ruling:` from this plan's ledger, in their recorded order, preserved before generated-workspace cleanup. Plain-language decisions and costs are also in runtime-artifact-hygiene.md and the user handoff.

Ruling: use unittest rather than pytest — Python 3.13 lacks pytest and repository tests are unittest-compatible — commands change, test coverage does not.

Ruling: work in existing codex/legacy-ppt-redesign checkout — user explicitly requested deleting extra worktrees — changes remain on the existing feature branch.

Ruling: use apply_patch-created task briefs/ledger initially — bash was absent from PATH — later discovered `<GIT_BASH>` and ran sdd-workspace successfully with escalation.

Ruling: BLOCKED responses report actual recorded failure/blocker writes instead of always zero — spec also requires canonical blocker persistence — conformance and precondition errors still write nothing.

Ruling: require --capability on reserve-dispatch using the same exact receipt schema — neither exact schema-v2 owner stores host identity, capability staging is non-authoritative, and dispatch-plan is read-only; the original reserve signature otherwise has no legitimate host/adapter source — costs one additional CLI argument and corresponding documentation/tests, preserves all durable schemas and avoids guessing identity.

Ruling: expose deterministic legacy conversion as explicit migrate-v1 --run-dir rather than making resume mutate — existing compatibility requires v1-to-v2 writes but all ten initial command contracts exclude this transition and resume is explicitly read-only — costs one small additional public command and tests, preserves resume semantics and removes the need for migration glue scripts.

Ruling: preserve the exact v2 transaction field set and bind outline_snapshot_id through canonical prompt snapshot reconstruction — existing artifact-contract prose separately asks for an extra transaction field, contradicting its closed schema — costs a prose clarification in Task4; avoids invalidating every existing transaction validator and golden fixture. Current reviewed outline/storyboard byte hashes still must match.

Ruling: persist machine-readable QA records within existing 质量检查报告.md and use the existing fix_attempts_for_candidate name bound to slide/transaction/candidate and defects — the docs define the counter but no serialization, and generation_attempt measures transport retries, not patches — costs a documented strict QA representation; absent legitimate two-patch evidence cannot authorize fallback. No new run-level control fields or arbitrary patch programs are introduced.

Ruling: add explicit publish-anchors sample-only command and prohibit formal promote at stage anchor — the closed v2 final_path is slides/Sxx.svg but approved workflow requires sample SVGs before guided approval — costs one small command/test and preserves existing schemas; avoids circular approval gating, premature final publication, and ad-hoc copy scripts. Implementer confirmed the gap and accepted this bounded addition.

Ruling: expose computed prepare_request under read-only resume.result when prerequisites are ready — otherwise the strict request_id digest would force hosts to reinvent canonical hashing before invoking the fixed CLI — costs a read-only result field and tests, no additional command or durable owner.

Ruling: allow style_assets_unavailable + style_asset_malformed to reference the verified selected STYLE.md as well as tokens.json; keep style_asset_schema_unsupported tokens-only — the existing production resolver reports malformed guidance but the closed tuple contract had no honest resource for it — costs a narrow tuple-validator, regression-test and artifact-contract prose update, with no new reason or owner field. Structured exceptions must preserve actual resolver identity, never infer resources from error strings.

Ruling: add one closed canonical recovery journal at .ppt-pilot/visual-generation-recoveries/<slide-id>-<oldtx64>.json for shared-prompt replacement — exact v2 owners retain only prompt hashes and the shared path, so an interrupted replacement otherwise loses the old byte evidence and strands recovery — costs one immutable JSON audit artifact per recompose/fallback plus strict schema/firewall/CAS tests. It must bind old/new bytes and owner identities, never accept arbitrary paths or staging state, and never overwrite third-party conflicts.

Ruling: require the recomputed sample/style/review anchor digest for guided source-deck approvals as well as ordinary runs — the existing source checker only equates two caller-supplied IDs and can reuse approval after changed sample bytes — costs reapproval for legacy opaque or unbound anchor IDs; never retrofit a new digest onto an old user approval.
