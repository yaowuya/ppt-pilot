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
- `samples/`
- `slides/`
- `质量检查报告.md`

`visual-briefs/` 在任何新的锚点、正式页面生成或视觉修订前都是必需的视觉产物目录，每个待处理页面必须有有效的 `<slide-id>.md`。缺少该目录的旧 `schema-v1` 运行仍可读取，但继续视觉工作前必须按[逐页视觉 brief 与生成契约](visual-brief-and-generation.md)补建对应 brief；不得把现存 SVG 或对话记忆当作替代。

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

不得把 `open_blocking_findings` 改名为 `unresolved_findings`。审查对象保存质量门状态、执行方式、轮次、最新报告、未解决的阻断问题和完整历史。新运行的 `latest_report` 始终是 `文稿审查.md`，包括 `review_unavailable`；该报告说明不可用原因，而 `review_history` 保持为空，因为没有审稿人实际运行。旧英文运行保留其既有 `manuscript-review.md` 值。

`manuscript_review.review_history` 保存每轮的 `reviewer_id`、`reviewer_context`、`delegation_evidence`、冻结的 `reviewed_file_snapshot`、问题列表和作者修订说明。`delegation_evidence` 必须包含宿主返回且非空的 `child_context_id`、`completion_event_id` 和 `result_context_id`；子上下文与结果上下文 ID 必须一致。此前的阻断问题 ID 必须持续可追踪，直到后续独立审稿人提供证据并把它们标记为 `RESOLVED`。

这些字段只是可移植的交接记录，不是可以自证的审计证明。行为验收必须把它们与保存的宿主 transcript 或协作日志逐项关联。

独立委派无法运行，或没有宿主可归因的子上下文完成／结果证据时，使用 `review_unavailable`。已经完成且有证据的审查轮次仍含未解决阻断问题时，使用 `manuscript_blocked`；第三轮后该状态终止。审查通过时，先记录顶层 `manuscript_approved` 检查点。此后顶层 `stage` 可以进入 `theme`、`anchor`、`production` 或 `qa`，但每个视觉阶段只有在 `run.json.manuscript_review.state` 持续为 `manuscript_approved` 时才获得授权。

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
- 已批准版本之后发生新的事实、来源、主张、大纲或故事板修改时，开启新周期的此前状态必须是 `manuscript_approved`：把 `cycle` 加一、设置 `round: 0`，并让后续全新独立审稿人从该周期第 1 轮开始。旧运行缺少 cycle 时先按 1 解释。
- `manuscript_blocked` 或 `review_unavailable` 不能通过修改字段开启新周期；尤其三轮仍被阻断时不得开启新周期或第 4 轮，只能保持终止／不可用状态。

表中的 `preserve` 表示仅在现有审查状态确为 `manuscript_approved` 时保留授权。

| affected_scope | return stage | manuscript authorization | invalidated dependents |
|---|---|---|---|
| `brief` | `brief` | `pending` | 研究、来源、大纲、故事板、审查和全部视觉／QA 产物。 |
| `claim_or_source` | `research` | `pending` | 受影响研究／来源、大纲或故事板、审查和全部视觉／QA 产物。 |
| `outline` | `outline` | `pending` | 故事板、审查和全部视觉／QA 产物。 |
| `storyboard` | `storyboard` | `pending` | 审查和全部视觉／QA 产物。 |
| `theme` | `theme` | `preserve` | 全部 `visual-briefs/`、`samples/`、`slides/` 和 QA 产物。 |
| `anchor_only` | `anchor` | `preserve` | 受影响锚点 brief、锚点、依赖正式页面 brief／SVG 和 QA。 |
| `slide_recompose` | `production` | `preserve` | 受影响页面 brief、SVG 和 QA。 |
| `slide_patch` | `production` | `preserve` | 受影响页面 SVG 和 QA；brief 只更新 defect 与候选版本。 |

上表保留以下依赖不变量：`brief` 变化会使全部下游产物失效；`outline` 变化会使 `storyboard` 及全部下游产物失效；`source` 或 `storyboard` 变化会使文稿审查及全部视觉产物失效；`theme` 变化会使全部 visual brief、`samples`、`slides` 和 QA 产物失效。

`request_revision` 刚被回答、范围仍未分类或正在等待澄清时保持批准问题的原阶段；一旦具体范围确定并开始应用修订，就必须使用上表，不能继续停在较晚视觉阶段。事实、来源、主张、大纲或故事板变化后，只有新的全新独立审稿人通过质量门才能重新设置 `manuscript_approved`。

对全部视觉产物失效时，把所有已知页面 ID 写入 `dirty_slides`，并把主题、锚点、正式页面及 QA 标记为无效，不能因文件仍存在而复用。无论失效范围多大，都保留权威 `interaction_history`；重建阶段产物时从中恢复需要的镜像。如果可选 `approved` 对象存在，同一原子提交还要把受影响镜像改为 `false`；镜像不能覆盖上表。

单页纯视觉修改只能把该页及其对应视觉／QA 产物标记为脏，不得影响无关页面。
