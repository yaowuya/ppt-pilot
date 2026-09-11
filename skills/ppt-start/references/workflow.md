# PPT Pilot 工作流参考

## 阶段顺序

`brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`

任何入口都先读取[用户交互与确认协议](interaction-protocol.md)。它定义模式默认值、决策队列、单问题回合、明确确认和可恢复等待；本文件只规定这些交互位于哪个阶段。

## 入口动作与执行策略

确定唯一运行目录后分流：新建空运行按[实时进度面板](live-dashboard.md)在资料处理前启动观察服务；已有运行先审计，只有 audit PASS 后才可启动或复用 dashboard 并提供实际 URL。每次真正进入某阶段前原子持久化其 `stage`，随后执行阶段工作。待回答状态仍保留原阶段。面板读取磁盘产物，不拥有批准、恢复或生成权限，也不改变下述全局恢复顺序。

最小 `run.json` 存在后先执行 `scripts/ppt_workflow_gate.py --run-dir <运行目录绝对路径> --audit-run`；任何入口、恢复或修订都不能跳过。该只读审计先于全局恢复顺序，专门拒绝宿主自创的平行 stage/control、`complete` 前的非源稿 PPTX，以及不在 `delivery/editable/` 的完成后 PPTX。它不消费或改变合法 durable state；审计 PASS 后才按下述全局恢复顺序处理。外部旧稿的每个 `--before` 与 `--resume-active-batch` 已自动包含同一审计，不能因上游证据 PASS 而忽略运行目录副作用。

已有运行先审计；发现 `repair_state.ps1`、`node_modules/` 或其他 artifact-firewall 缺陷必然 `BLOCKED`。此时停止所有写入：不启动或重启 dashboard，不暂存 generator 响应，不调用 `ingest-result`，不得手写 owner，也不为继续运行而移动、删除或解释污染文件。固定 `ppt_runtime.py` 不存在或校验失败同样停止；维护插件必须发生在演示运行之外，不能自制 helper 或把 runtime／依赖复制进 run。

- `new`：从主题或简报开始创建新演示文稿；它是入口动作，不是写入 `run.json.mode` 的值。新运行未显式指定策略时使用 `guided`。
- 外部旧 PPT／PPTX 重设计是 `new + source-driven` 输入分支；先按[旧稿导入](source-deck-redesign.md)建立源清单、源页映射和 source_deck 绑定，不能因“只改风格”直接进入 revise／production。十阶段顺序不变；导入运行在进入阶段及生成／交付前调用该文档的只读 gate，失败时停止。
- `guided`：持久执行策略；在简报、大纲和锚点批准节点提出一个直接问题，并等待明确批准。
- `auto`：持久执行策略且只有显式指定时才使用；采用默认值并跳过可选人工批准，但不能跳过用户权限、无安全默认值的决策或任何硬质量门。
- `resume`：入口动作；重新打开已有运行，先读取 `run.json`，严格按“全局恢复顺序”依次处理 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、schema-v1 `visual_generation_transaction` 迁移、`active_visual_generation_batch`；前五项均不存在后才能扫描第一个未完成或脏阶段。始终保留既有 `run.json.mode`。
- `revise`：入口动作；保留既有 `run.json.mode`，同样必须先完成或停止于“全局恢复顺序”的 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、schema-v1 `visual_generation_transaction` 迁移、`active_visual_generation_batch`；只有五类 durable control state 均不存在后，才能依据失效规则标记受影响下游产物并重新生成。

因此，`run.json.mode` 只能持久化 `guided` 或 `auto`；`new`、`resume`、`revise` 都不写入该字段。

新运行的运行根目录只放用户可读的 `大纲.md`、最终页面 `slides/` 与内部目录 `.ppt-pilot/`。内部 `.ppt-pilot/` 存放 `run.json`、`简报.md`、`研究.md`、`来源.md`、`故事板.md`、`文稿审查.md`、`质量检查报告.md`、theme、generation prompts 与 samples；不得把新运行的 `大纲.md` 写入内部目录。旧英文或旧布局运行由 `resume`／`revise` 原位读取，保持一套连贯路径，不自动迁移。

## 固定视觉运行时 CLI

视觉生命周期只通过当前安装 Skill 的绝对路径调用 `scripts/ppt_runtime.py`。每次入口先执行只读 artifact audit；任一未知或未接受的宿主 adapter 都 fail closed。运行时不调用模型、Office 或宿主 CLI，也不读取、导入或执行运行目录中的代码。宿主只把声明式输入写到 `.ppt-pilot/runtime-inputs/`，并原样消费单个 JSON response envelope：

DSH 在新建目录／阶段写入前先做安装只读预检，已有运行仍先通过 artifact audit。取宿主本次加载 Skill 给出的真实根目录，运行以下 `inspect-host`；安装身份不能靠猜路径或旧会话记忆。该命令无需运行目录、不改变全局恢复顺序、不创建 canonical blocker；详细操作见 [DSH 入口诊断](deepseek-harness.md#入口诊断与升级后恢复)。

```text
inspect-host --host HOST [--capability ABSOLUTE_LOCAL_JSON]
prepare-batch --run-dir RUN --input INPUT.json --capability CAPABILITY.json
dispatch-plan --run-dir RUN --batch-id B --capability CAPABILITY.json
reserve-dispatch --run-dir RUN --batch-id B --slide-id S --transaction-id T --capability CAPABILITY.json
bind-task --run-dir RUN --dispatch-id D --host-task-id HOST_TASK
ingest-result --run-dir RUN --dispatch-id D --response RESPONSE.txt
record-generator-failure --run-dir RUN --dispatch-id D --reason generator_refused|generator_timeout|generator_unavailable
record-validation --run-dir RUN --slide-id S --transaction-id T --input QA.json
prepare-recovery --run-dir RUN --slide-id S --transaction-id T --mode retry|recompose|fallback
publish-anchors --run-dir RUN --batch-id B --expected-manifest-sha256 H
promote --run-dir RUN --batch-id B --expected-manifest-sha256 H
resume --run-dir RUN
migrate-v1 --run-dir RUN
```

`resume` 永远只读；可新建批次时使用它返回的 `result.prepare_request`，不得自行重算 request ID。返回 `capability_refresh_required=true` 时，由 coordinator 使用当前 registry 身份与真实宿主观测重新构建 capability，在合法 staging 路径保存新输入，并用 `inspect-host --capability` 只读验证；安装更新、旧 receipt 或单独执行 resume 都不等于已完成重新协商。`reserve-dispatch` 必须显式重交 capability，并先持久化 attribution；`publish-anchors` 只发布 sample，返回的 `anchor_evidence`（含共享 `sha256:` identity）原样用于真实批准，旧 opaque ID 必须重新实际批准。schema-v1 只经显式 `migrate-v1` 迁移。`recompose`／`fallback` 只经运行时的固定 recovery journal 重放，不创建 run-local patch、依赖或手工编辑 owner。

`generator_unavailable` 只在完整安全 preflight 后由固定 `prepare-batch` 或当前状态对应的固定 runtime 命令持久化；不得手写 `generator_unavailable`、blocker 或 transaction。

## 全局恢复顺序

任何 `resume`、`revise` 或生产重入在扫描普通阶段前，必须按下面恰好五步处理 durable control state。前一项存在时必须先完成或停止，后一项不得预读、创建或覆盖。

| control | order | required action |
|---|---:|---|
| `pending_interaction` | 1 | 先验证或消费待回答／已回答交互；存在时不得处理其他 durable state。 |
| `manuscript_review.pending_round` | 2 | 没有 pending interaction 时恢复同一 cycle／round／snapshot 的文稿审查；匹配的 durable 报告存在时幂等提交一次，不能重启或重复计数。 |
| `visual_generation_blocker` | 3 | 只有没有更高优先级状态时处理；同页 blocker 幂等刷新，同一运行内另一页 active blocker 先被处理。 |
| `visual_generation_transaction` | 4 | schema-v1 只读迁移输入；先执行零模型调用 v1→v2 migration，不能直接 dispatch 或 stage scan。 |
| `active_visual_generation_batch` | 5 | 读取 pointer 指向的 manifest 和全部 per-slide transactions，从 transaction 重建 cursor 后继续，不做普通 stage scan。 |
| stage scan | 6 | 只有前五类 durable control state 都不存在时，才寻找第一个未完成或脏阶段继续。 |

`visual_generation_blocker` 不是用户问题，不写入 `pending_interaction`。它只能记录安全 Skill 相对 `resource` 或 `none`，不能持久化未验证绝对路径、URL、工作区路径或机密内容；写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，并保持受影响 slide dirty。历史 crash 留下 durable prompt／`compiling` transaction／active blocker 旧协议组合时，prompt 必须视为不可信派生产物：保持受影响 slide dirty，保留 previous final，按需隔离旧 prompt 与 orphan candidate，并按 [artifact-contract.md](artifact-contract.md) 重新执行完整无副作用 preflight；不得采用旧 prompt，不得直接标记为 `compiled`，也不得直接移除 blocker。失败则按 canonical blocker 规则保留或幂等刷新 blocker。只有 style/prompt blocker 的完整 preflight 成功，或 `generator_unavailable` blocker 的快照复核与 adapter 重新协商都成功时，才能先以一次原子 `run.json` 替换移除 blocker；若 schema-v1 `visual_generation_transaction` 仍存在，必须原样保留并重新进入全局顺序，由下一步零模型调用 migration 按 pointer-last 发布 v2 owner，不能跨过迁移直接创建新的 `compiling` transaction。只有 v1 owner 不存在时，新操作才可创建新 transaction。阻断期间不得启动 generator、不得写 SVG、不得降级为 patch 或改用其他风格。

正式生产按[自动并发策略](adaptive-concurrency.md)由插件决定目标，不询问用户：规划器目标从 5 起，根据稳定通过检查的结果自动提高到最多 10；当前固定运行时新批次上限为 5，必须使用 runtime 返回的 prepare request，不能按目标值手改 `batch_width`。按 `ordered_slide_ids` 选择最多批次上限数量的页面，尾批可为 `1..batch_width` 页。旧 3／4 页活动批次原位恢复，v1 迁移默认值保持不变。确定性 preflight 先在内存完成，随后在任何 prompt／transaction／candidate durable write 前按[页面生成宿主隔离适配器](host-isolation-adapters.md)完成宿主能力协商；不符合已接受的宿主生成边界时只由固定运行时按[产物契约](artifact-contract.md#可选-visual_generation_blocker)原子写入闭合的 `generator_unavailable` blocker，且生产文件写入为 0。能力通过后才按 [artifact-contract.md](artifact-contract.md) 的 pointer-last 顺序写入每页 schema-v2 transaction、batch manifest，最后原子发布 `run.json.active_visual_generation_batch`。manifest 只拥有顺序、refs、批次快照与可重建 cursor 提示，不复制页面 state。

`active_visual_generation_batch` 恢复保持同一全局 order：只有无 pending、无 blocker 时处理。pointer 在 files 前出现属于 `visual_generation_state_conflict`；files 完整而 pointer 缺失只做 pointer-only completion。恢复按 manifest 的 `ordered_slide_ids` 读取完整 transaction inventory，重建 `promotion_cursor`／`blocker_cursor`，并忽略 completion callback 或 manifest cursor 的授权含义。候选只有在 durable `candidate_written` 且 hash 匹配时可采用；`generating` 上的 orphan candidate 必须隔离。`validated` final CAS 只允许 candidate 已在 final、prior final 仍在、或第三 hash conflict 三种结果，且始终保留 previous final。

新批次在 durable 写入前按[宿主隔离适配器](host-isolation-adapters.md)协商 fresh-context text task 与该宿主工具边界；已激活批次在恢复／新 epoch 前重新协商。Claude Code 在普通目录、unborn `HEAD` 和已有提交的仓库都选择已注册 `ppt-svg-generator` 普通 fresh-context subagent 并省略 `isolation`，既不需要 Git 也不需要可解析的 `HEAD`；worktree 与 remote 都是禁止的 fallback。DSH 使用下段已接受的 native-subagent；其他受支持宿主按其适配器优先 native、其次 remote；并发+durable lookup 使用自动目标与实际 worker capacity 的较小值，缺少并发或 lookup 时降为 width 1，未知容量保守使用 1。`worker_capacity == 0` 时进入容量 `WAIT`，不误报 isolation 不可用。缺少或不安全 adapter 属于结构性不可用：新批次只以一次 `run.json` 原子替换写入 `state/reason: generator_unavailable`、`resource: none` 的 blocker，现有批次保留 transactions 并标记 blocked，且不得轮询；绝不调用嵌套 CLI、探测 credentials/profiles、要求 worktree，或使用当前上下文生成。

DeepSeek Harness 生成、补位及恢复前必须读取[普通 subagent 协议](deepseek-harness.md)。已接受 `deepseek-harness / native-subagent / 1.0.0`：普通 `functions.subagent`，`run_in_background: true`，完整冻结 Prompt 按值传入，外加无页面内容的禁工具／禁委派／text-only wrapper。worker 继承工具，receipt 的 `filesystem_none=false`、`data_tools_none=false` 必须如实记录；fresh context 不是硬工具隔离。不使用 fork、专用 generator、workflow agent 或 CLI，不读取／修改 DSH 配置，也不要求重启或部署 DSH。

DSH 每页先 `reserve-dispatch`，仅在 `spawn_authorized: true` 时以含 `dispatch_id` 的无页面内容 `description` 启动；立即将真实返回的 durable `subagent_id` 用 `bind-task` 绑定为 `host_task_id`。完成通知的 child ID 必须匹配后才可 `ingest-result`；它不是供 `job_output` 使用的 `jobId`。`list_agents` 仅作发现，不轮询或读取结果；`send_message` 仅向同一 child 请求重发已完成原答案，不修订或重新生成。丢失 launch 无法唯一归因时保留 reservation 并停止，不能再次 spawn；具体重复／迟到通知、旧 epoch 和恢复证据按 DSH 协议处理。

每个 eligible `compiled` transaction 在同一 `dispatch_epoch` 最多一次 spawn。每次调用只读 `ppt_concurrency.py` 规划 dispatch／补位前，重建在途任务并扣除已运行和已预留任务，包括未终结旧 epoch；等待或重复观测不得重复派发。多页可共享 epoch 并在实际容量内并发生成；coordinator 将完整 prompt bytes 按值交给任务，不传源稿或工作区内容；任务固定 `fresh_history=true`、text-only；Claude／Codex 保持 `filesystem=none`、`data_tools=none`，DSH 使用已接受的非内容禁工具 wrapper 而非硬工具隔离。各宿主工具与 ambient context 边界以[宿主隔离适配器](host-isolation-adapters.md)为准。coordinator 独占 candidate 写入、hash 与 transaction 提交。每页 validation 可在 sibling 生成期间并行，但 final promotion、visible blocker publication 和 `run.json` pointer 改变始终按 `ordered_slide_ids` 串行确定；visible blocker 只发布最低 ordered failed／undispatched slide，不能按 completion order 选择。

上述并行 validation 使用 SVG 结构检查与非 Office 渲染，具体见 [SVG 渲染与 Office 边界](qa-and-revision.md#svg-渲染与-office-边界)。锚点／正式页面生成及预览不启动 PowerPoint／WPS；Office 实测不混入逐页任务，也不因提高并发而启动多个应用实例。

外部旧稿运行在步骤 5 的既有 active batch owner 内、完成原 manifest／transaction 校验后，还须在 dispatch、candidate adoption、final promotion 前运行[导入恢复前置检查](source-deck-redesign.md#3-可执行阶段检查)的 `--resume-active-batch`。它不增加恢复步骤、不处理／清除高优先级状态；检查失败保留 owner 与 previous final，禁止让旧源稿候选先提升到 final。

## guided 检查点

- `brief`：重要简报决策解决后，写入待回答问题并请求简报批准；批准前不得进入研究或大纲。
- `outline`：展示核心论点和证明顺序后请求大纲批准；批准前不得创建故事板。
- `anchor`：展示两页锚点和真实渲染证据后请求锚点批准；批准前不得设置 `stage: production`。

等待期间，顶层 `stage` 保持当前阶段，不得新增暂停或等待阶段。`pending_interaction.status: pending` 时只等待明确回答；`answered` 时使用保存的规范化决定完成幂等写入，并以单次原子替换同时提交阶段转换和交互对象删除／替换，不得重新提问。推荐、叙述性暂停或没有反对都不是批准。

## 文稿审查硬质量门

五文件冻结后立即进入审查：每轮优先委派全新独立子 Agent；启动或结果归因失败时按契约执行 `inline_fallback`（当前上下文降级，报告必须声明隔离限制）；只有两种方式都不可用时才使用 `review_unavailable`。任何 `BLOCKER`／`HIGH` 问题不是 `RESOLVED` 就阻断——`OPEN` 与 `ACCEPTED_RISK` 仍然阻断；零问题也必须保存显式 `PASS` 报告。subagent 与 inline 共同计入每 cycle 最多三轮；三轮仍有阻断问题时进入 `manuscript_blocked`。

findings 字段 schema、八项检查（含设计师视角材料充分性）、材料缺口协议、用户业务决策与多轮解决要求，以 [文稿审查](manuscript-review.md) 为单一权威。

### 批准检查点与视觉阶段转换

审查通过时记录顶层 `manuscript_approved` 检查点，并把 `run.json.manuscript_review.state` 保持为 `manuscript_approved`：解析主题令牌前设置 `stage: theme`，制作锚点前设置 `stage: anchor`，生成正式页面前设置 `stage: production`。主题阶段解析当前有效主题后直接编译锚点页 prompt；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页从故事板与 `theme.json` 直接编译其余页面 prompt。任何页面在对应 `generation-prompts/<slide-id>.md` 有效前都不能生成。页面生成 Prompt 不是新的顶层阶段；其编译与 fresh generator 输入隔离分别遵循[页面直接编译与生成](visual-brief-and-generation.md)与 [redesign-prompt](redesign-prompt.md)。

### 生产护栏

- `manuscript_review.state = manuscript_approved` 持续有效前，不得创建 `theme.json`、样例或正式页面；
- 即使零问题，也必须写入并保存 `PASS` 报告。
