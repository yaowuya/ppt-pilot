# Fixed runtime owner encoding

本文件是视觉运行时机器 owner、命令边界与恢复证据的唯一权威。宿主必须读取并校验现有规范产物，只能写入闭合契约允许的声明式输入；批次请求身份、快照、候选、事务、清单、锚点和恢复日志都由已安装运行时确定性计算；`revise-visual` 的调用方只提供稳定请求幂等键与闭合修订输入。任何字段缺失、额外字段、路径越界、摘要冲突、未知适配器或历史不透明批准都应封闭阻断，保留原始证据，不得手工修复、猜测迁移或调用运行目录中的程序。

The fixed runtime reads canonical Markdown data, never inferred prose. New machine-readable owners use exactly one fenced `ppt-pilot-json` object in the existing Markdown file. Other prose is descriptive. The JSON object is authoritative and duplicate JSON keys are rejected. Do not mix this fence with bold machine fields.

Existing explicit `- **field**：value` (or ASCII colon) fields remain readable. JSON object/list/string values must be valid JSON; other scalars are literal text. A single `### narrative_step1_bullets` section may hold the exact persisted bullet bytes. Duplicate fields, mixed representations, and missing structured owners block. No parser guesses narrative choices from titles or page prose.

`大纲.md` carries `outline_snapshot_id` plus the six normalized narrative fields from narrative-and-storyboard.md. `故事板.md` carries the identical `outline_snapshot_id`, its `storyboard_snapshot_id`, `applied_visual_revision_ids` and `slides` array with the exact locked page/block grammar. The runtime copies narrative bullets and display/qualifier/metric values mechanically. It never takes narrative or source mappings from runtime-inputs. Each block uses its own `- block_id: S01-B1` line in the compiled replacement.

`文稿审查.md` contains the exact latest formal review-history object in the same fence. New snapshots come only from `python <skill-dir>/scripts/ppt_review_snapshot.py --run-dir RUN`; a successful `status: SNAPSHOT` response supplies `reviewed_file_snapshot` with exactly `{snapshot_id, files, file_hashes, semantic_file_hashes}`. `schema_version` and `kind` belong only to the fixed digest domain and are not persisted snapshot fields. Copy the returned object unchanged; the report's semantic snapshot machine block must equal the latest review-history record. Semantic normalization excludes only the helper's closed allowlist of structured storyboard visual/metadata fields; prose, facts, claims, qualifiers, sources, content blocks, order, and narrative remain bound. A new-format approval may survive only a proven allowlisted change with identical semantic hashes; such visual/metadata-only changes do not require rewriting source-gate `evidence.files`. Legacy approvals without semantic hashes remain exact-byte strict and are never amended or augmented in place. The independent-review validator applies to ordinary runs as well as source runs. For English legacy filenames, retain the complete English family recorded in the review snapshot. Mixed or ambiguous owners block. IDs are explicit immutable owner values; current fingerprints bind them to the approved content.

Theme identities must match the selected immutable registry manifest. `theme_snapshot_id` is SHA-256 of theme.json bytes; ordinary `source_audit_snapshot_id` is SHA-256 of the canonical sources document; imported runs hash canonical JSON of the bound evidence's `source_audit` section without terminal LF (later anchor evidence must not invalidate source audit). The normalized verified template supplies the template identity. Soft-baseline provenance uses the verified tokens' canonical seven style-directive lines, normalized to exactly one terminal LF. This uses the existing deterministic style-directive renderer and creates no second body replacement domain. The exact schema-v2 transaction field set is unchanged: outline identity participates in reconstructed prompt snapshot provenance rather than becoming an extra transaction field.

The runtime's canonical QA report is `.ppt-pilot/质量检查报告.md`, with `schema_version: 1`, `kind: runtime_qa`, and `records`. Records retain the exact submitted QA object per transaction and candidate digest. Before finalizing an ordinary run, preserve `records` and add `final_review` with exactly `status: PASS` and a `slides` array. Each selected page record uses `{slide_id, svg: {path, sha256}, render: {path, sha256}, render_input_sha256, renderer, visual_review: PASS}`; paths are run-relative, SHA values are unprefixed lowercase digests, SVG is `slides/<id>.svg`, and render is an actual PNG bound to that SVG digest. Finalization verifies coverage, PNG headers, file hashes and the unchanged content baseline; booleans alone cannot authorize delivery. Imported runs retain the equivalent source-evidence `qa` section. For current `runtime_visual` production, each page has one inherited lifetime budget of at most three real dispatches across initial generation, retry, recompose and visual repair. A local deterministic repair may be selected only by a runtime action inside the remaining budget; it never resets `generation_attempt`, creates a fresh lifetime, or relabels a model call as non-dispatch. A transaction with no remaining attempt does not advertise another recovery action. Historical named/versioned patch and fallback evidence remains readable for replay, but never authorizes a fourth current dispatch. The closed QA input accepts neither counters nor patch code. A full batch snapshot change still requires a one-slide batch or explicit scope resolution; multi-batch rebasing is not implemented.

## Failed-page visual revision

`revise-visual --run-dir RUN --slide-id S --transaction-id OLD_T --input .ppt-pilot/runtime-inputs/REVISION.json` 仅处理当前 active batch 内的 `failed` 页面，stage 必须为 `anchor` 或 `production`，文稿、来源与所有既有 owner 仍须通过验证。输入恰好六键：

```json
{
  "schema_version": 1,
  "kind": "visual_revision",
  "request_id": "repair-S01-1",
  "expected_run_sha256": "<复制当前 runtime response 的 run_sha256>",
  "changes": {"layout_family": "single-column", "visual_intent": "保持原有事实，改为单栏层级"},
  "answer": "<真实修订请求或明确的 QA 修复依据>"
}
```

`changes` 非空且只允许 `layout_family`（最多 128 字符）／`visual_intent`（最多 2000 字符）；不得带控制字符、路径、来源注解或新增事实。`answer` 非空且最多 8192 字符，只留在本地历史，不进入 Prompt。`request_id` 是本次决定稳定、非空的幂等键，满足 `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`；重试原请求时连同原 `expected_run_sha256` 原样复用，不换 ID 绕过冲突。

运行时唯一写入下一 `visual-revision-N` 历史，使用 `projection: runtime_visual`、单页 `affected_scope`、`supersedes: []`、`artifact_owner: <当前run.json路径>`，绑定原 failed transaction、请求与当前 review snapshot。它在内存中覆盖该页的两项视觉字段，**不回写故事板或 theme，不更新五份审查输入、审查报告或既有 review hash**。此为旧 materialized revision 协议的受控例外，不得手写或把该 ID 加入冻结故事板的 `applied_visual_revision_ids`。

编译按该页 operation 的 revision ID 截止，仅应用同页不晚于该 ID 的 runtime overlays；旧 transaction 按原历史截止点重建，未修改 sibling 的 Prompt／transaction 不变。保持 batch 全局 snapshots，沿现有 recovery journal 只替换失败页引用，保留原 failed transaction／candidate、已验证 sibling 与 previous final。native `runtime_visual` 替换继承原 failed transaction 的 `generation_attempt`，整条视觉修复链含首次最多 3 次真实派发；达到 3 时在记录新决定前拒绝，换 request ID 或新 transaction 不能重置预算。旧 materialized recompose／patch／fallback 证据仅供历史 replay，不能给当前链增加 dispatch。历史提交或 journal 中断后，原请求精确重放；不自动迁移曾直接改写故事板的旧修订，不复制旧批准来适配新字节。事实、来源、文案、叙事或其他审查输入真有变化时，仍须在同一运行按正式失效／重审协议处理。

## High-level workflow operations

The coordinator-facing production interface is deliberately small:

```text
advance --run-dir RUN [--allow-partial] [--skip-slide SID ...]
finalize --run-dir RUN
```

`advance` audits the durable graph, applies only deterministic state transitions it owns, and returns one next action with closed declarative inputs. Repeated calls are idempotent against current evidence. `--allow-partial` explicitly persists `run.production_policy: best_effort` for an existing run; it is never inferred from failure or mode. New runs persist `best_effort` unless the user requested `strict`; legacy absence means strict. Each `--skip-slide` must correspond to an explicit user decision and is recorded as `user_skipped`, never silently synthesized.

Ordinary `generator_refused`, `generator_timeout`, `generator_output_malformed`, `svg_contract_failed`, `fact_source_mismatch`, and `visual_qa_failed` outcomes are page-local. The runtime leaves the failed transaction bytes and `generation_attempt` unchanged, advances independent ordered work, and, only under best-effort or explicit skip authorization, seals the omission in the owning terminal manifest. Shared owner/snapshot integrity, path/firewall, CAS/pointer, unsafe or unavailable adapter, and permission failures are global blockers. Best-effort does not waive them.

A batch settles as `completed`, `partial`, or `failed`. `partial|failed` manifests bind paired `omitted_transaction_refs` and `omitted_transaction_sha256` entries to the original failed slots and on-disk digests. Settlement never changes the failed file to PASS, invents a candidate, clears an omitted slide's dirty flag, or resets attempts.

`finalize` verifies the exact [delivery contract](artifact-contract.md#delivery) and its bound bytes, then atomically aligns the top-level stage. Any explicit settlement, including `prepared`, first requires the current `manuscript_approved` gate and its approval snapshot to remain valid; failure preserves the existing owners and does not add a delivery field. `prepared` exists only with `stage: qa` and is not exportable. Final `complete`, `partial`, and `failed` require `stage: complete`, `stage: partial`, and `stage: failed`, respectively. Complete has no missing page; partial requires best-effort plus nonempty delivered and missing partitions; failed has no delivered page and no PPTX. Verification status is separate from completeness. The runtime creates neither PPTX nor Office evidence.

## Runtime commands and evidence

### Low-level reference APIs

The following commands remain implementation, recovery, and conformance APIs. Use one only when an `advance` response or runtime diagnosis explicitly names it; they are not the primary workflow checklist:

```text
inspect-host --host HOST [--capability ABSOLUTE_LOCAL_JSON]
prepare-batch --run-dir RUN --input INPUT.json --capability CAPABILITY.json
dispatch-plan --run-dir RUN --batch-id B --capability CAPABILITY.json
reserve-dispatch --run-dir RUN --batch-id B --slide-id S --transaction-id T --capability CAPABILITY.json
bind-task --run-dir RUN --dispatch-id D --host-task-id HOST_TASK
submit-result --run-dir RUN --dispatch-id D --host-task-id HOST_TASK --response .ppt-pilot/runtime-inputs/NAME.txt
ingest-result --run-dir RUN --dispatch-id D --response RESPONSE.txt
record-generator-failure --run-dir RUN --dispatch-id D --reason REASON
record-validation --run-dir RUN --slide-id S --transaction-id T --input QA.json
prepare-recovery --run-dir RUN --slide-id S --transaction-id T --mode MODE
revise-visual --run-dir RUN --slide-id S --transaction-id T --input REVISION.json
publish-anchors --run-dir RUN --batch-id B --expected-manifest-sha256 H
promote --run-dir RUN --batch-id B --expected-manifest-sha256 H
retire-batch --run-dir RUN --batch-id B --expected-manifest-sha256 H --input .ppt-pilot/runtime-inputs/NAME.json
resume --run-dir RUN
migrate-v1 --run-dir RUN
```

`inspect-host --host HOST [--capability ABSOLUTE_LOCAL_JSON]` is a read-only advisory check outside the run lifecycle; it needs no run directory or prepared batch. Invoke it through the actual Skill root returned by the host's Skill loader. It reports `skill_root`, `registry_path`, `instruction_path`, registered `adapter`, `receipt_checked`, and always `live_host_verified: false`. It verifies bundled instruction integrity and, optionally, a no-follow regular local receipt without rewriting it; UNC/network, device, and alternate-stream path syntax is rejected before input-path I/O. PASS is not live-host attestation, workflow approval, or permission to create artifacts. Failures retain `generator_unavailable` but add response-only `details.reason`, `field`, optional `expected`, and installed paths; these diagnostic fields never enter the closed canonical blocker. Unknown command means an older installed runtime, not missing host subagent support.

Run `resume` before a new batch. For a ready ordinary run it returns `result.prepare_request`, including the computed request identity, exact snapshot identities, ordered next slides and run CAS hash. Copy that declarative object into `.ppt-pilot/runtime-inputs/request.json`; no caller-written hashing program is necessary. When its next command is `prepare-batch` or `dispatch-plan`, `capability_refresh_required: true` directs the coordinator to reobserve the host and stage a fresh capability input from the current registered identity. Resume remains read-only and neither constructs evidence nor clears the blocker. Preserve stale inputs for diagnosis; explicitly supply the newly checked capability to the next command. Capability `kind` is `host_capability`; QA `kind` is `visual_generation_qa`. Request JSON is schema version 1. Input paths are direct run-relative children of `.ppt-pilot/runtime-inputs/` ending in `.json` (requests/QA/capabilities) or `.txt` (returned text).

Completed batches are historical evidence. The current shared prompt identifies the current promoted transaction for each slide, whose candidate hash must match the final bytes. Older promoted transactions do not claim ownership of later finals. Resume compares that current transaction with freshly reconstructed canonical provenance: a dirty slide with new approved snapshots/revisions gets a new prepare request using the latest applicable `interaction:visual-revision-N`; an unchanged completed slide does not regenerate. Current `prepare-batch` transactions accept only `initial_generation` or `user_recompose`. Historical `deterministic_fallback`／`local_patch` identities and already-persisted recovery journals remain replay-readable, but runtime does not emit them as new current generation intents or use them to bypass the inherited three-dispatch limit.

Claude adapter support is additive: retain the registered legacy `ppt-svg-generator` path defined by [host isolation adapters](host-isolation-adapters.md), and on hosts exposing the installed Agent SDK 1.9.0 adapter use `ppt-svg-generator-sdk` rather than silently downgrading to legacy semantics. SDK capability evidence has exactly `agent_name`, `loaded_agent_sha256`, `spawn_primitive`, `allowed_tools`, `ambient_context`, `isolation`, `execution_mode`, `result_type`, `session_id`. Its values are `ppt-svg-generator-sdk`, the registered agent digest, `fresh-context-subagent`, `["ListAgents"]`, `["CLAUDE.md","parent_git_status"]`, `omitted` or `worktree`, `foreground`, `text`, and a nonempty current session identifier. `foreground` means `run_in_background: false`: the host returns completed text plus the real task ID, then coordinator binds that ID before staging or ingesting the response. `worktree` is accepted only when that SDK requires explicit isolation and a user-authorized repository with resolvable `HEAD` exists; `remote` remains invalid. Every installed adapter receipt binds the complete `host` + `adapter_id` + `version` + digest identity; all four must match the selected registered adapter, and a matching digest from another host/version is insufficient. `inspect-host`, audit, `advance`, and resume validate observed identity but never auto-run the standalone adapter-upgrade helper; upgrading is a separate explicitly authorized maintenance action. The runtime verifies the actual registered sibling agent, not an input-supplied path. Agent digests normalize UTF-8 BOM/newlines and one terminal LF. Capability is declared current-host evidence, not cryptographic live-host attestation. Codex has no registered adapter. Hermetic installed-agent fixtures are tests, not host acceptance.

DeepSeek Harness uses the registered `host: deepseek-harness`, `adapter_id: native-subagent`, version `1.0.0`; read [the DSH protocol](deepseek-harness.md) before preparing capability evidence, dispatching, or recovering. Its receipt records `native_fresh_isolation=true` as fresh CONTEXT only, `fresh_history=true`, `current_context_only=false`, `filesystem_none=false`, and `data_tools_none=false`. This accepted prompt-policy boundary is not hard tool isolation. Evidence comes from actual exposed host tools and task results, not DSH configuration inspection or a profile patch. Current fixed-runtime new batches are capped at 5; a planner target of 10 does not enlarge them.

`publish-anchors --batch-id B --expected-manifest-sha256 H` writes validated candidates only to `.ppt-pilot/samples/`, retaining the active batch and validated transactions. It returns deterministic sample hashes and `anchor_evidence`; it does not record user approval. Existing conflicting sample bytes are preserved. After real review, ordinary runs use `run.anchor` with `files`, `style_sha256`, `review_snapshot_id`, and `status` (`validated` auto / `approved` guided). Guided runs also bind `approval_interaction_id` and `artifact_snapshot_id` to the applied anchor approval in interaction history. Source runs retain their existing `evidence.anchor` owner. Final promotion requires production stage and current anchor evidence; it never grants approval itself.

For guided ordinary promotion and the source-import production gate, artifact_snapshot_id is recomputed as SHA-256 of canonical JSON (without terminal LF) of exactly `files`, `style_sha256`, and `review_snapshot_id`. Both anchor and applied approval IDs must equal this computed value; changing sample bytes and hashes cannot reuse an old approval. Historical opaque anchor IDs fail closed and require actual reapproval; the runtime never retrofits a user decision. At anchor stage, a validated batch resumes to `publish-anchors` until every sample equals its candidate; after publication it resumes to `anchor_review`. Only production resumes to `promote`.

Anchor identity encoding is shared by publication, ordinary promotion and source-import approval validation: `sha256:` followed by the lowercase hexadecimal digest. Record the returned `anchor_evidence.artifact_snapshot_id` unchanged; do not strip its prefix or calculate a separate approval identity.

## Immutable replacement recovery journal

Before current recompose replaces a shared prompt—or while replaying an already-persisted historical fallback—the runtime writes and verifies `.ppt-pilot/visual-generation-recoveries/<slide-id>-<oldtx64>.json`. No host-authored staging file is a journal. The exact closed schema remains backward-compatible and has these fields:

- `schema_version`: integer 1; `kind`: `visual_generation_recovery`; `mode`: `recompose` or `fallback`.
- `slide_id`, `batch_id`: validated existing ownership; `expected_run_sha256`: the original raw run.json hash.
- `old_transaction_ref`, `old_transaction_sha256`, `new_transaction_ref`, `new_transaction_sha256`: canonical transaction paths and complete hashes.
- `expected_transaction_hashes`: exact old manifest transaction-ref inventory mapped to raw on-disk hashes, including all siblings.
- `manifest_path`: canonical active manifest path; `old_manifest`, `new_manifest`: exact schema-v2 manifest objects; `old_manifest_sha256`, `new_manifest_sha256`: hashes of their canonical JSON bytes with terminal LF.
- `prompt_path`: existing `.ppt-pilot/generation-prompts/<slide-id>.md`; `old_prompt`, `new_prompt`: complete UTF-8 envelope strings; `old_prompt_sha256`, `new_prompt_sha256`: hashes of those exact UTF-8 bytes.
- `new_transaction`: the exact prepared schema-v2 replacement object, whose canonical JSON with terminal LF yields new_transaction_sha256.

The runtime derives paths and payloads, validates old/new envelope identities, preserves the old failed transaction, verifies all old transaction hashes, and reconstructs the replacement from current approved owners before publication. The new manifest must be exactly the old manifest with the permitted replacement ref, current canonical snapshots, and rebuilt cursor/state fields. Fallback evidence is revalidated on replay. Publication order is journal → shared prompt → replacement transaction → manifest; no v2 field is added.

An interrupted journal publication leaves the old graph unchanged. An existing complete journal permits exact replay after prompt or transaction replacement. Before any replay write, the run must still match expected_run_sha256, all old transactions must match expected_transaction_hashes, and prompt/new-transaction/manifest bytes must be either the recorded prior state or the exact recorded replacement. A published replacement manifest requires its prompt and transaction already to match. Third-party changes and extra journal fields block without overwrites. Completed journals remain immutable audit evidence; they do not authorize rollback after later workflow transitions.

Resume returns `next_command: prepare-recovery` plus journal `recoveries` entries (`slide_id`, old `transaction_id`, `mode`) when a journal's old transaction is still active. Exact `prepare-recovery` or the original `revise-visual` request replays it; unrelated mutators stop at `recovery_pending`. No custom hashing, prompt backup, or manual owner repair is needed.

失败页恢复还返回 `failure_reason`、`mode`、`remaining_attempts`，需新决定时有 `required_input`；`in_flight` 列出已有 generating 页及真实 `host_task_id`。优先消费返回动作，`same_run_required: true` 要求保持原运行；未返回此字段也不授权新建。`await-interaction`／`apply-interaction`、`await-review`／`manuscript-review`、`review-content`、`wait-for-generator`、`durable_lookup`、`anchor_review` 和 `stage_scan` 是 coordinator 动作，不是 CLI 子命令。未批准文稿停在原文稿 owner，保留已有 active batch，不重置 cycle／round。

`prepare-recovery --mode retry` 在 canonical 已批准输入未变时复用同一 Prompt／transaction／siblings。除既有 transport／写入失败外，`svg_contract_failed` 或 `fact_source_mismatch` **仅在 `candidate_sha256: null` 时**可走此路径；下一真实派发计入同一页面继承的最多 3 次 `generation_attempt`（含首次），耗尽即停止，不换运行、request ID、transaction 或 recovery label 绕过。非空 candidate hash 的 QA 失败不自动重试：按具体事实／视觉 defect 分类，只执行 `advance` 在剩余预算内返回的 local repair／`user_recompose`，或进入正式内容重审。历史 fallback evidence 仅用于精确 replay，不授权新的 current dispatch。

Resume is read-only. An unbound dispatch reservation returns durable lookup as its next action; repeating reserve returns `spawn_authorized: false`. For DSH, correlate the reserved `dispatch_id` in the launch description with the real host return/log, then `bind-task` with that durable `subagent_id` before ingesting the same child's result. `list_agents` discovers IDs, not results or terminal status; `send_message` may request only that same child's already-completed answer. If launch attribution is ambiguous, preserve the reservation and stop without another spawn or a guessed ID. Full completion, stale-epoch and replay handling follows [the DSH protocol](deepseek-harness.md). An orphan candidate is not adopted: record the bound generator failure, then follow the next `advance` action. A retry is permitted only when runtime reports inherited budget remaining; exhausted pages retain the failed evidence and receive no retry/recompose/fallback action. Any permitted retry removes only that owned candidate under its observed hash and resets the next dispatch epoch, preserving previous finals. Migration is a separate pointer-last mutator. Partial preparations without a complete manifest fail closed; a complete matching graph with only its pointer missing is completed by exact prepare replay. Historical legacy prompts that cannot reconstruct current canonical provenance remain blocked until canonical recompose inputs are available.

All mutators acquire a process lock without run lock-file writes, audit before consuming inputs, and audit/recheck observed bytes before writes. Responses list actual changed owner paths, including blocker writes and explicit orphan removal. A conformance failure is always zero-write. No runtime command calls a model, imports run code, starts Office, or launches another program.

Style resolution retains the actual resource in `AssetFailure`; preflight does not guess file identity from human exception text. After canonical identity/review checks, a style or template failure records the existing closed visual_generation_blocker. `style_asset_malformed` may name verified tokens.json or STYLE.md; schema_unsupported remains tokens-only. Missing/unsafe canonical identities never authorize a blocker write.
