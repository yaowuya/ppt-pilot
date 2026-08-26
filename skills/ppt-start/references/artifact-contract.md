# PPT Pilot 产物契约

## 必需产物

- `run.json`
- `简报.md`
- `研究.md`
- `来源.md`
- `大纲.md`
- `故事板.md`
- `文稿审查.md`
- `theme.json`
- `visual-briefs/`
- `generation-prompts/`
- `samples/`
- `slides/`
- `质量检查报告.md`

`generation-prompts/` 是新运行的必需视觉执行产物目录。每个首次生成或 `recompose` 的页面都必须创建 `generation-prompts/<slide-id>.md`；`patch` 不重新生成。每份文件严格遵循黄金格式：`# <slide-id> 页面生成 Prompt` 标题、恰好九个加粗字段的 `## Snapshot metadata`（slide_id、visual_brief_snapshot_id、storyboard_snapshot_id、theme_snapshot_id、applied_visual_revision_ids、prompt_snapshot_id、user_page_request、expected_output、workspace_output_path）、以及 `## Compiled Prompt` 后的精简编译体；期望输出是一个 fenced `xml` 中的完整 SVG。全文件只允许工作区相对路径，禁止绝对路径、盘符、UNC、URL、JSON 数据块与 UNTRUSTED 围栏。

`generation-prompts/<slide-id>.md` 是从 visual brief 派生的可恢复执行产物，不得成为主张、来源、主题或修订历史的唯一副本。输入快照变化后旧 Prompt 失效；恢复时必须重新编译，不能依赖旧对话。早期 `redesign-prompts/` 是 history/read-only only，never active prompt source：只可作为历史证据只读保留，新运行和恢复都不得写入该别名，也不得从该目录选择、激活或迁移 Prompt。

`visual-briefs/` 在任何新的锚点、正式页面生成或视觉修订前都是必需的视觉产物目录，每个待处理页面必须有有效的 `<slide-id>.md`。缺少该目录的旧 `schema-v1` 运行仍可读取，但继续视觉工作前必须按[逐页视觉 brief 与生成契约](visual-brief-and-generation.md)补建对应 brief；不得把现存 SVG 或对话记忆当作替代。

`samples/` 存放锚点页 SVG（封面与密度最高内容页）；正式页面写入 `slides/`。

### Task 6 identity 与旧 prompt 目录产物规则

theme.json 与每份 visual-briefs/<slide-id>.md 必须包含完全相同的四个 schema-v1 identity 字段：`selected_style_id`、`selected_style_display_name`、`style_kind`、`style_manifest_version`。这些 identity 字段以及 `generation_intent`、`generation_trigger_id`、`compiled_prompt_sha256` 和 `prompt_snapshot_id` 持久在 visual brief、`theme.json` 与 `run.json.visual_generation_transaction` 中；`generation-prompts/<slide-id>.md` 本身按黄金布局只显示九个元数据字段，不重复机器字段。missing fields 只能由已验证 registry／manifest／fallback identity table 与持久 operation owner 重建；不得从 SVG、目录、请求文案或用户措辞推断。

`generation_intent`／`generation_trigger_id` 的产物矩阵固定为：`initial_generation` + `initial:<slide-id>:<visual_brief_snapshot_id>` + `initial generation from approved visual brief` + `none (initial generation)`；`user_recompose` + `interaction:<applied-history-id>` + `raw answer from applied history record only`；`deterministic_fallback` + `fallback:<slide-id>:<failed-transaction-64hex>:2` + `deterministic single-column or two-column fallback after two failed patches` + `none (deterministic fallback after two failed patches)`；尾缀 `:2` 为常量标识（两次 patch 失败后的确定性回退），不随后续重试递增。`local_patch` + `patch:<slide-id>:<qa-defect-id>` + `requires_current_svg` + `compile_full_prompt: false`。

same `interaction:<id>` copied to every affected brief; each slide keeps distinct slide-specific transaction identities and prompt snapshots。Deck-scope user_recompose fan-out copies the same `interaction:<id>` to every affected brief; each slide keeps distinct slide-specific transaction identities and prompt snapshots.

`redesign-prompts/` 始终 inert，作为旧运行只读历史目录（history/read-only only，never active prompt source）：不写、不移动、不删除，不参与 active prompt 选择，也不作为 style identity、operation owner 或 stale/conflict 证据。双目录同页时只看 `generation-prompts/` provenance；旧目录不同 slide 时按页独立忽略；新目录缺 provenance 或 prompt path/hash 改变时是 ordinary stale 并重编新目录。只有持久 provenance 内部不一致、stored body/hash 不一致、brief/theme/storyboard snapshot 无法唯一解释、或多个 operation owner 冲突时才是 `prompt_snapshot_conflict`。


### Generation prompt golden layout, byte grammar, hash domains, and stale semantics

本节收敛为单一权威文件：完整定义见 [generation-prompt-byte-grammar.md](generation-prompt-byte-grammar.md)（generation prompt byte grammar 与 byte contract 的全部 11 条规则）。该文件对本文件同等具有约束力；编译、校验或恢复前必须完整阅读。
## 运行目录规则

- 标准运行目录是 `ppt-output/<deck-id>/`。
- 运行目录是安全的执行上下文，必须与宿主运行时目录相互独立。
- 禁止跨运行目录覆盖产物：`ppt-output/<deck-id>/` 内的文件不得覆盖该运行目录之外的任何既有文件。
- 每完成一个阶段，都要更新 `run.json` 和该阶段产物。

## 可选工作区路由状态

`ppt-output/run-selection.json` 是 schema-version 1 的可选工作区级路由状态，只在 `resume`／`revise` 无法唯一确定目标运行时存在。它不是演示文稿运行，也没有 `stage`，不得放进或改写任何候选运行。

该文件在 `pending` 时必须包含：

- `schema_version: 1`；
- `kind: run_selection`；
- `entry_action`：只能是 `resume` 或 `revise`；
- `operation_payload`：本地保存的非空对象，至少含原始操作载荷 `request`；已能安全分类时还记录 `requested_scope`，不得只保存候选而丢失选中后要执行的工作；
- `status: pending`；
- 一个直接 `question`；
- 非空且不重复的 `candidates`。

候选数为 2–4 时还必须包含与候选值完全相同的 `options`、完整 `option_effects`、属于候选的 `recommendation` 和非空 `recommendation_reason`。候选更多时可以提出一个开放选择问题，要求回复精确 `deck_id`，但必须把完整候选列表持久化且不得编造推荐。

处理顺序：原子创建该文件后才提问；等待时不得写入任何候选运行。`entry_action` 与 `operation_payload` 在整个路由生命周期保持不变。明确回答先写为 `answered`，保存原始 `answer`，并在有限选择时保存属于 `candidates` 的规范化 `decision`。随后验证所选目录与 `run.json`，读取并保留既有 `run.json.mode`，再按已保存入口动作执行完整原始操作载荷。只有所选运行到达下一个持久状态后才删除 `run-selection.json`；崩溃留下 answered 文件时继续消费而不重复提问。已有路由文件格式错误、候选已消失、操作载荷缺失或与新请求冲突时停止，不创建第二份也不猜测目标或操作。

## 可选工作区偏好档案

`ppt-output/pilot-preferences.json` 是 schema-version 1 的可选工作区级咨询性输入，用于跨运行复用品牌方向与交付偏好；交互语义见[用户交互与确认协议](interaction-protocol.md)。

- 顶层固定为 `schema_version: 1` 与可选的 `brand`、`style`、`audience`、`language`、`confidentiality_restriction`、`evidence_policy`、`standing_authorizations[]`、`notes`；字段全部可选，未使用时写 `none` 或省略；
- `brand` 记录颜色值、系统字体栈和品牌规则文本；`style` 记录 preferred style ID 或唯一显示名；两者都只是主题阶段的候选输入，视觉令牌仍只能在文稿批准后确定；
- 跨运行有效的网络或披露授权必须以 `standing_authorizations[]` 对象显式保存（含授权范围、用户原话与记录时间），且只能由用户明确给出；没有该对象时每次运行仍按权限问题询问；
- 偏好档案不进入任何 `run.json` 恢复链、不算 durable control state、不替代 guided 批准点或硬质量门；任何运行都不得因为读取偏好而修改或删除该文件之外的工作区状态；
- 文件格式错误、不可解码或 `schema_version` 非 1 时披露原因并整体忽略，继续当前运行；不得部分采用也无法唯一解释的内容。

## `run.json` 架构

每个运行目录都必须包含 `run.json`，其顶层字段至少且统一使用：`schema_version`、`deck_id`、`mode`、`stage`、`manuscript_review` 和 `dirty_slides`。

- `schema_version`
- `deck_id`
- `mode`
- `stage`
- `manuscript_review`
- `dirty_slides`

`schema_version` 是整数 `1`。`deck_id` 与运行目录名一致。`mode` 只能是 `guided` 或 `auto`，表示持久执行策略，不得改用 `delivery_mode` 等别名。`resume`／`revise` 是入口动作，不是该字段的值；打开既有运行时保留既有 `run.json.mode`，除非用户明确切换执行策略。`stage` 表示当前工作流状态。`dirty_slides` 保存需要重新生成的页面 ID。

部分既有夹具和运行包含可选 `approved` 对象。它不是必需字段，也不能授权阶段转换、替代 `pending_interaction` 的明确回答或覆盖文稿质量门；顶层 `stage` 和嵌套审查状态始终是权威记录。如果保留该对象，批准后必须与权威阶段保持一致：简报、大纲和锚点批准分别更新 `approved.brief`、`approved.outline` 和 `approved.style`。旧运行缺少该对象时不得自动添加。

### 可选 `interaction_history`

`interaction_history` 是 schema-version 1 的可选顶层对象；没有它的旧运行仍然有效。当该运行第一次应用交互答案时创建它。它是按 `pending_interaction.id` 为键的权威交互历史，必须跨恢复、失效和阶段产物重建保留，不得因阶段产物失效、主题重建或脏页面清理而删除。

每条已应用记录至少包含 `stage`、`kind`、原始 `answer`、`status` 和阶段产物的 `artifact_owner`。有限选择还包含规范化 `decision`。批准记录还包含 `checkpoint` 与 `approval_attempt`；`decision: approve` 使用 `status: applied` 并包含稳定 `artifact_snapshot_id`，指向获得批准的逻辑冻结版本。请求修订记录还包含 `affected_scope`；需要澄清时使用 `status: clarification_pending` 和正整数 `clarification_index`，替换问题 ID 必须复用该索引。

同一检查点再次批准时必须创建下一 `approval_attempt` 的新交互 ID 和新历史键，不得覆盖此前修订事件。第 1 次记录可以使用兼容键 `<checkpoint>-approval`，第 N 次使用 `<checkpoint>-approval-<N>`；所有尝试都按 `checkpoint` 沿用同一规范性转移。

`interaction_history` 与阶段产物镜像按交互 ID 幂等更新。若二者冲突，以 `interaction_history` 为权威并停止自动推进，先报告冲突；不得让容易被失效的阶段产物反向覆盖权威记录。

### 直接视觉修订记录

已经执行的直接视觉修订即使不来自 `pending_interaction`，也必须在修改视觉产物前立即写入 `interaction_history`。键使用单调 `visual-revision-<N>`：令 `N` 为既有同类键中的最大正整数加一，缺少既有键时从 1 开始；不得复用、重排或覆盖旧键。每条记录包含：

- `stage`：应用修订时的当前阶段；
- `kind: visual_revision`；
- `answer`：用户原始指令；
- `normalized_changes`：按稳定字段名保存的非空规范化变化；
- `affected_scope`：允许 `deck`、`anchor` 或非空页面 ID 列表；
- `supersedes`：被替换的 `<history-id>:<field>` 列表，没有替换时为空列表；
- `status: applied`；
- `artifact_owner`：权威记录所镜像到的当前阶段产物。

`affected_scope: deck` 或整套主题／品牌决定镜像到 `theme.json.user_revision_notes`；`affected_scope: anchor` 镜像到 `theme.json.user_revision_notes` 和受影响锚点的 visual brief；具体页面决定镜像到对应 `visual-briefs/<slide-id>.md`。镜像使用同一 `visual-revision-<N>` ID 并可以从历史重建；`run.json.interaction_history` 是权威记录并且必须跨失效保留。直接视觉修订与 guided 锚点修订采用同一记录、归并和冲突规则，不得把探索性预览、对话摘要或 SVG 本身作为唯一副本。

明确替换同一字段的后续记录必须在 `supersedes` 中列出旧记录及字段。被替换记录保留在历史中，但其废弃规则不得进入当前有效契约。若无法确定新规则是共存还是替换、作用域不明确、目标字段不存在，或镜像与权威记录冲突，停止应用并持久化一个澄清问题；不得同时激活互斥规则。

无论处于哪种状态，`manuscript_review` 对象都必须包含以下全部字段；允许使用空列表或 `reason` 表示无内容，但不得重命名或省略契约字段：

- `required`
- `round`
- `mode`
- `state`
- `status`
- `latest_report`
- `open_blocking_findings`
- `review_history`

`cycle` 是可选的 schema-version 1 正整数，位于 `manuscript_review.cycle`；缺少时按 `1` 解释，以兼容旧运行。`round` 表示当前 cycle 内已完成的审查轮数，新运行初始化为 `cycle: 1`、`round: 0`、`mode: pending`、`state: pending`、`status: PENDING`。新运行和新周期写入的每条 `review_history` 记录都包含所属 `cycle`；旧记录缺少该字段时按 cycle 1 解释。

不得把 `open_blocking_findings` 改名为 `unresolved_findings`。审查对象保存质量门状态、执行方式、轮次、最新报告、未解决阻断问题和完整历史。新运行的 `latest_report` 始终是 `文稿审查.md`；旧英文运行保留既有 `manuscript-review.md`。历史 `review_unavailable` 报告继续可读，但新运行的委派失败优先写 `inline_fallback` round，而不是空 review history。

`manuscript_review.review_history` 保存每轮的 `cycle`、`round`、`reviewer_id`、`reviewer_context`、`review_mode`、冻结的 `reviewed_file_snapshot`、问题列表和作者修订说明。`review_mode: subagent` 必须包含宿主返回且非空、child/result 一致的 `delegation_evidence`，且不能包含 fallback evidence；`review_mode: inline_fallback` 必须包含 `delegation_attempted: true`、稳定 `reason` 和非空 `host_detail` 的 `fallback_evidence`，且不能包含 delegation evidence。旧记录缺 `review_mode` 但含 delegation evidence 时按 `subagent`。此前阻断问题 ID 必须持续可追踪，直到后续正式 subagent 或 inline round 用冻结证据标为 `RESOLVED`。

这些字段只是可移植的交接记录，不是可以自证的审计证明。行为验收必须把它们与保存的宿主 transcript 或协作日志逐项关联。

委派失败或没有可归因结果时，保存失败原因并立即执行 `inline_fallback`；inline PASS 可以记录顶层 `manuscript_approved`。只有冻结输入不可读、当前上下文也无法审查或状态冲突不可恢复时使用 `review_unavailable`。实际审查轮次仍含未解决阻断问题时使用 `manuscript_blocked`；第三轮后该状态终止。视觉阶段只有在 `run.json.manuscript_review.state` 持续为 `manuscript_approved` 时才获得授权。

## 可选 `manuscript_review.pending_round`

`pending_round` 是 schema-version 1 的可选嵌套对象，用于持久化正在执行的 subagent 或 inline 审查轮次。它包含：

- `cycle` 与下一 `round`；
- `mode: subagent | inline_fallback`；
- 完整 `reviewed_file_snapshot`；
- subagent pending 使用只有非空 `child_context_id` 的 `delegation_attempt_evidence`；inline pending 使用完整 `fallback_evidence`；completed subagent round 才包含三字段 `delegation_evidence`；
- `status: in_progress`。

写入 pending round 后才执行审查。crash／resume 必须复用同一 current cycle、下一合法 round、mode 和 snapshot；round 必须等于已完成 `round + 1` 且不超过 3。completed report 的 `review_mode` 必须匹配 pending `mode`；inline 的 fallback evidence 必须一致，subagent completed delegation evidence 的 child/result context 必须等于 pending `delegation_attempt_evidence.child_context_id`。completed report 不得丢失此前未解决的 `BLOCKER/HIGH` IDs。snapshot 变化时旧 pending 失效并重新冻结。同一运行只能有一个 pending round。匹配 durable 报告存在时，以一次原子 `run.json` 替换追加恰好一条 history、更新 review 状态并删除 pending；重复 resume 为 no-op。格式错误、双 pending、模式／snapshot 冲突或非法第 4 轮时停止，不猜测。

## 可选 `pending_interaction`

`pending_interaction` 是 schema-version 1 的可选顶层对象，用于跨轮次和跨宿主持久保存一个正在阻塞当前阶段的问题。它不属于六个必需顶层字段；不存在 `pending_interaction` 的既有 schema-version 1 运行仍然有效，不得为了补充该字段迁移或重写旧运行。

对象存在时必须包含：

- `id`：当前问题在该运行中的稳定标识；
- `stage`：提出问题时的当前顶层阶段；对象存在期间必须与 `run.json.stage` 一致；
- `kind`：`question`、`approval`、`authorization` 或 `blocker`；
- `question`：将向用户提出的单个直接问题；
- `status`：`pending` 或 `answered`。

`kind: approval` 还必须包含 `checkpoint`（`brief`、`outline` 或 `anchor`）和正整数 `approval_attempt`。第 1 次批准问题使用兼容 ID `<checkpoint>-approval`；第 N 次（N >= 2）使用 `<checkpoint>-approval-<N>`。同一检查点的尝试号从权威 `interaction_history` 中取最大值后加一，不能复用已经记录的 ID。早期 schema-version 1 pending 对象若恰好使用第 1 次兼容 ID、stage 与 checkpoint 可唯一对应且没有历史冲突，可以在重放前原位补为 attempt 1；其他缺失情况按格式错误停止。

有限选择还必须记录：

- `options`：2–4 个互斥稳定值；
- `option_effects`：键集合与 `options` 完全相同，每个值对应非空的用户可见效果说明；
- `recommendation`：必须是 `options` 中的值；
- `recommendation_reason`：非空推荐理由。

开放问题可以省略这四个有限选择字段，但仍要在 `question` 中给出推荐回答格式或有依据的建议。

`status: answered` 还必须包含非空原始 `answer`。有限选择被回答时，必须同时写入规范化 `decision`，且 `decision` 必须是 `options` 中的值；自然语言“批准，继续”等原话保留在 `answer`，恢复时使用 `decision`，不得重新解释原话。开放问题不伪造 `decision`。

持久化顺序：

1. 提问前写入对象并设置 `status: pending`；
2. 等待期间保持当前阶段，禁止生成任何被该决定阻塞的下游产物；
3. 收到明确回答后，在一次 `run.json` 写入中设置 `status: answered`、原始 `answer` 和需要时的规范化 `decision`；此时仍保持原阶段；
4. 按 `interaction_id` 幂等写入当前阶段产物镜像，并准备同键的权威 `interaction_history` 记录；
5. 产物写入成功后，以单次原子替换提交完整的新 `run.json`：同时更新 `interaction_history`；批准时改变 `stage` 并删除原对象；需要澄清时保持原阶段并以新 pending 对象替换 answered 对象；
6. 如果恢复时状态已经是 `answered`，使用保存的 `answer` 与 `decision` 完成未结束的幂等写入和原子提交，不得再次询问。

不得先改变顶层 `stage` 再单独删除旧对象；这会制造 `pending_interaction.stage` 与顶层阶段不一致的不可恢复中间态。单次原子替换只能让恢复者看到“原阶段 + answered 对象”或“目标阶段 + 无原对象”中的一个完整状态。不能安全替换时保留 answered 状态并停止。

不得新增 `paused`、`awaiting_user` 或其他顶层 `stage` 值来表示等待。`pending` 状态缺少问题、`answered` 状态缺少答案、有限选择 answered 状态缺少有效 `decision`、记录阶段与顶层阶段不一致、选项重复、效果映射不完整或其他格式错误时，停止并报告冲突；不得猜测答案、静默清除对象或重新构建无关上游产物。

### 用户修订记录

批准点收到 `request_revision` 后，在删除或替换 answered 对象前，把权威记录写入 `run.json.interaction_history[interaction_id]`，并写入一份阶段产物镜像。重复恢复必须更新同一键而不是追加重复项。每条记录至少包含：`stage`、`kind`、`checkpoint`、`approval_attempt`、原始 `answer`、规范化 `decision: request_revision`、`affected_scope`、`status` 和 `artifact_owner`。范围尚不明确时使用 `affected_scope: unresolved`、`status: clarification_pending` 与正整数 `clarification_index`；替换问题 ID 使用这个已持久索引。应用后改为具体范围与 `status: applied`。

| approval stage | stage artifact mirror |
|---|---|
| `brief` | `简报.md` 的“用户修订记录”；旧运行写入 `brief.md` 的同名段落。 |
| `outline` | `大纲.md` 的“用户修订记录”；旧运行写入 `outline.md` 的同名段落。 |
| `anchor` | `theme.json.user_revision_notes`；数组元素使用上述同一字段结构。 |

Markdown 记录使用与 JSON 相同的字段名。阶段产物镜像可以随失效被重建，但重建时必须从权威交互历史恢复；`theme.json.user_revision_notes`、Markdown 段落或其他阶段产物都不得成为唯一副本。

## 可选 `visual_generation_blocker`

`visual_generation_blocker` 是 schema-version 1 的可选顶层对象，用于持久化页面首次生成或 `recompose` 的风格 prompt 解析／编译阻断。它不是用户问题，不写入 `pending_interaction`；缺少该对象的既有 schema-version 1 运行仍然有效。

对象存在时必须包含：

- `state: style_prompt_unavailable`；
- `slide_id`：被阻断页面；
- `reason`：下列稳定 resolver reason 之一；
- `selected_style_id`：来自当前 visual brief 的风格 ID；
- `resource`：只允许规范化 Skill 相对路径，或路径安全前失败时的 `none`；
- `visual_brief_snapshot_id` 与 `theme_snapshot_id`：阻断判定时使用的快照；
- `status: active`。

稳定 reason 集合固定为：`registry_missing`、`registry_path_unsafe`、`registry_target_invalid`、`registry_unreadable`、`registry_malformed`、`registry_schema_unsupported`、`registry_duplicate_style`、`style_not_registered`、`style_kind_invalid`、`entrypoint_missing`、`entrypoint_path_unsafe`、`entrypoint_target_invalid`、`legacy_entrypoint_malformed`、`legacy_identity_mismatch`、`manifest_malformed`、`manifest_schema_unsupported`、`manifest_identity_mismatch`、`manifest_version_invalid`、`style_asset_field_missing`、`style_asset_path_unsafe`、`style_asset_target_invalid`、`style_asset_unreadable`、`prompt_field_missing`、`prompt_path_unsafe`、`prompt_file_missing`、`prompt_target_invalid`、`prompt_unreadable`、`prompt_template_invalid`、`prompt_snapshot_conflict`。同一状态有多个缺陷时按 resolver traversal 的第一失败项选择唯一 reason：registry-wide 未选 pack root 错误先于 selected prompt 错误；selected tokens／guidance 错误先于 prompt 错误。

写入、刷新或清除规则：

1. blocker 写入使用单次原子 `run.json` 替换；保持 `stage`、`mode`、`interaction_history` 不变，并保持受影响 slide 在 `dirty_slides` 中。
2. `resource` 不得保存未验证绝对路径、Windows 盘符、UNC、URL、工作区路径、`..` 越界路径或机密内容；路径安全前失败统一写 `none`。
3. 同一 slide 已有 active blocker 时，恢复后重新验证当前资源和快照；仍失败则幂等刷新同一对象，不启动 generator。
4. 另一 slide 已有 active blocker 时，先处理原 blocker，不创建并行 blocker；同一运行一次只允许一个 active `visual_generation_blocker`。
5. prompt durable 后仍允许看到 `visual_generation_transaction.state: compiling` 和 active blocker；随后必须以一次 `run.json` 原子替换同时把匹配 transaction 改为 `compiled` 并移除 blocker。
6. 阻断只作用于受影响 slide：该 slide 的 generator calls 与 SVG writes 必须为 0，不得降级为 patch、不得改用其他风格、不得创建或覆盖 SVG。批内并发下，blocker 只暂停新事务派发与受影响 slide 的恢复；已进入 `generating`、`candidate_written` 或 `validated` 的其他 slide 事务照常完成验证与提升。

全局恢复顺序固定为：`pending_interaction` > `manuscript_review.pending_round` > `visual_generation_blocker` > `visual_generation_transaction` > stage scan。前一项存在时不得处理后一项。pending review 必须复用同一 cycle／round／snapshot；匹配 durable 报告只提交一次 history 并清除 pending。

## 可选 `visual_generation_transaction`

`visual_generation_transaction` 是 schema-version 1 的可选顶层对象，用于恢复页面首次生成和 `recompose` 的跨文件生产步骤；默认同一运行一次只允许一个 active transaction，仅当多个事务同属当前生产批次、目标 slide 互不相同且都处于 `compiling`／`compiled` 段时，才允许最多一个批次页数（3–4）个并发 active transaction，而候选写入、验证与 promotion 仍按 slide_id 升序逐页串行提交。完整 transaction schema 固定为：`transaction_id`、`slide_id`、`generation_intent`、`generation_trigger_id`、`prompt_path`、`prompt_snapshot_id`、`compiled_prompt_sha256`、`candidate_path`、`final_path`、`state`、`generation_attempt`、`candidate_sha256`、`failure_reason`。

字段语义固定如下：`transaction_id == prompt_snapshot_id`，值是完整 `sha256:<64hex>`（启用 golden block 第 11 条 unhashed 回退时为完整 `unhashed:<token>`）；`prompt_path` 必须是 `generation-prompts/<slide-id>.md`；`candidate_path` 必须是 `slides/.candidates/<slide-id>-<64hex>.svg`，其中 `<64hex>` 来自 transaction ID 去掉 `sha256:` 后的后缀（unhashed 回退时为 `slides/.candidates/<slide-id>-<token>.svg`）；`final_path` 必须是 `slides/<slide-id>.svg`。`compiled_prompt_sha256` 只覆盖 compiled prompt body bytes；`candidate_sha256` 只能在候选 SVG 写入、关闭并复读后计算并提交，`compiling`、`compiled` 与 `generating` 状态不得预填 candidate hash。

允许状态图精确为：

```text
normal: compiling -> compiled -> generating -> candidate_written -> validated -> promoted
failure: generating | candidate_written | validated -> failed
recovery: failed -> generating
recovery: failed -> validated
replacement: failed transaction -> new compiling transaction
```

`failed transaction -> new compiling transaction` 只用于 authoritative inputs changed 或 deterministic fallback，是原子对象替换，不是同一 transaction edge。新操作到来时若已有非终态 transaction，必须先按全局恢复顺序恢复或停止，不得覆盖；transaction 未达到 `promoted` 前不得清除对应 `dirty_slides`，没有 pending 和 blocker 时才恢复 transaction，transaction 未完成时不得进入普通 stage scan。

`failure_reason` 只能为 null 或以下 11 个稳定 reason：`generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch`、`svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed`、`final_promotion_conflict`、`transaction_state_conflict`。

固定跨文件顺序和 crash 恢复如下：先原子写入 `state: compiling` 并保留 previous final SVG；再持久化 `generation-prompts/<slide-id>.md`；prompt durable 后可以暂时保留 active `visual_generation_blocker`。只有复核 durable prompt 的 `prompt_snapshot_id` 与 `compiled_prompt_sha256` 匹配后，才能用一次 `run.json` 原子替换同时把 transaction 改为 `compiled` 并移除匹配 blocker；golden block 第 11 条 unhashed 回退生效时，该复核改为重新推导并比对九个元数据字段与 payload keys，不做摘要比较。随后先原子改为 `generating`，再调用 fresh generator。若 crash 留在 `generating`，此时没有 committed expected candidate hash；deterministic path 上的任何 orphan candidate 都必须 delete/isolate，never adopted，然后重新调用 generator。只有 transaction durable 为 `candidate_written` 且记录非空 `candidate_sha256` 时，resume 才可复读候选并比较 hash；不匹配转 `failed: candidate_hash_mismatch`，匹配才继续验证。

候选验证通过后原子改为 `validated`。只有 `validated` 能提升候选到 final：先把候选原子替换为 final path，再原子把 transaction 改为 `promoted`。如果 final 替换后、状态提交前 crash，resume 比较 final bytes 与记录的 `candidate_sha256`；相同补写 `promoted`，不同转 `failed: final_promotion_conflict`。dirty_slides 只在 promoted transaction 的页面和整套 QA 均通过后，随移除 transaction 的同一 `run.json` 原子替换清除；previous final SVG 在失败、验证和冲突期间始终保留。

失败 consumer 唯一且完整：

| failed reasons | 唯一下一步 |
|---|---|
| `generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch` | 下一次显式 resume 删除或隔离 orphan candidate，同一 transaction 原子 `failed -> generating`，`generation_attempt + 1`，保留同一 trigger 与 authoritative inputs，并重新调用 generator；每次宿主调用最多 generator 1 次，不自动循环；同一 transaction 的 `generation_attempt` 达到 `3` 后不得再次 resume 为 `generating`，改为持久化 production blocker 并停止，等待用户决定。 |
| `svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed` | 先把 failure reason 与一个精确 defect 幂等持久化到 visual brief／QA owner；然后进入 patch，或在已更新 brief 的同一次 `run.json` 替换中以新的 deterministic_fallback `compiling` transaction 替换 failed transaction。失败 candidate 不能提升为 final。 |
| `final_promotion_conflict`、`transaction_state_conflict` | 持久化一个 production `blocker` 的 `pending_interaction` 并停止；不得覆盖未知 final 或删除 failed transaction。用户解决后若是 unchanged valid candidate 且 candidate/hash/provenance 未变，则原子 `failed -> validated` 并重试 promotion；若 authoritative inputs changed，则以新的 `compiling` transaction 替换。 |

No arbitrary delete/cancel：除上述 failed consumer 与 promoted 后最终 QA 清理外，不存在取消、任意终止或直接删除 transaction。

## 旧英文运行的只读兼容

新运行必须使用上面的中文 Markdown 名称。`resume`／`revise` 可以原位读取下列旧英文运行名称，但不得自动重命名、复制、迁移或覆盖旧文件：

| 旧英文名称 | 新运行中文名称 |
|---|---|
| `brief.md` | `简报.md` |
| `research.md` | `研究.md` |
| `sources.md` | `来源.md` |
| `outline.md` | `大纲.md` |
| `storyboard.md` | `故事板.md` |
| `manuscript-review.md` | `文稿审查.md` |
| `qa-report.md` | `质量检查报告.md` |

恢复旧运行时，优先采用 `run.json` 中记录的实际文件名，包括 `manuscript_review.latest_report` 和 `review_history[*].reviewed_file_snapshot.files`。审查前尚无快照时，只能选择目录中完整存在的一套名称：全中文或全英文。不得在一个阶段内混用两套名称。若同一语义的中英文文件同时存在且状态不能唯一判定，停止并报告冲突，不得猜测内容优先级。

该兼容规则只允许读取和继续使用旧名称，不把英文名称重新作为新运行标准。

## 失效与脏标记规则

修订范围确定后，按下表返回最早受影响阶段。表中的 `pending` 表示在同一个原子 `run.json` 提交中把 `manuscript_review.mode`、`state`、`status` 分别设为 `pending`、`pending`、`PENDING`，清空 `open_blocking_findings`，并保留完整 `review_history` 作为审计历史；该状态不授权任何视觉工作。

- 尚未通过审查的当前周期发生上游修改时，保留 `cycle`，并根据已完成轮次继续受该周期三轮上限约束；不得借普通作者修订重置计数。
- 已批准版本之后发生新的事实、来源、主张、大纲或故事板修改时，开启新周期的此前状态必须是 `manuscript_approved`：把 `cycle` 加一、设置 `round: 0`，并让后续正式审查从该周期第 1 轮开始；仍优先 subagent，失败时允许 inline fallback。旧运行缺少 cycle 时先按 1 解释。
- `manuscript_blocked` 或 `review_unavailable` 不能通过修改字段开启新周期；尤其三轮仍被阻断时不得开启新周期或第 4 轮，只能保持终止／不可用状态。

表中的 `preserve` 表示仅在现有审查状态确为 `manuscript_approved` 时保留授权。

| affected_scope | return stage | manuscript authorization | invalidated dependents |
|---|---|---|---|
| `brief` | `brief` | `pending` | 研究、来源、大纲、故事板、审查和全部视觉／QA 产物。 |
| `claim_or_source` | `research` | `pending` | 受影响研究／来源、大纲或故事板、审查和全部视觉／QA 产物。 |
| `outline` | `outline` | `pending` | 故事板、审查和全部视觉／QA 产物。 |
| `storyboard` | `storyboard` | `pending` | 审查和全部视觉／QA 产物。 |
| `theme` | `theme` | `preserve` | 全部 `visual-briefs/`、`generation-prompts/`、`samples/`、`slides/` 和 QA 产物。 |
| `anchor_only` | `anchor` | `preserve` | 受影响锚点 brief、对应 generation prompt、锚点、依赖正式页面 brief／SVG 和 QA。 |
| `slide_recompose` | `production` | `preserve` | 受影响页面 brief、对应 generation prompt、SVG 和 QA。 |
| `slide_patch` | `production` | `preserve` | 受影响页面 SVG 和 QA；brief 只更新 defect 与候选版本。 |

上表保留以下依赖不变量：`brief` 变化会使全部下游产物失效；`outline` 变化会使 `storyboard` 及全部下游产物失效；`source` 或 `storyboard` 变化会使文稿审查及全部视觉产物失效；`theme` 变化会使全部 visual brief、generation prompt、`samples`、`slides` 和 QA 产物失效。

`request_revision` 刚被回答、范围仍未分类或正在等待澄清时保持批准问题的原阶段；一旦具体范围确定并开始应用修订，就必须使用上表，不能继续停在较晚视觉阶段。事实、来源、主张、大纲或故事板变化后，只有新的正式 subagent／inline 审查通过质量门才能重新设置 `manuscript_approved`。

对全部视觉产物失效时，把所有已知页面 ID 写入 `dirty_slides`，并把主题、锚点、正式页面及 QA 标记为无效，不能因文件仍存在而复用。无论失效范围多大，都保留权威 `interaction_history`；重建阶段产物时从中恢复需要的镜像。如果可选 `approved` 对象存在，同一原子提交还要把受影响镜像改为 `false`；镜像不能覆盖上表。

单页纯视觉修改只能把该页及其对应视觉／QA 产物标记为脏，不得影响无关页面。
