# PPT Pilot 工作流参考

## 阶段顺序

`brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`

任何入口都先读取[用户交互与确认协议](interaction-protocol.md)。它定义模式默认值、决策队列、单问题回合、明确确认和可恢复等待；本文件只规定这些交互位于哪个阶段。

## 入口动作与执行策略

- `new`：从主题或简报开始创建新演示文稿；它是入口动作，不是写入 `run.json.mode` 的值。新运行未显式指定策略时使用 `guided`。
- `guided`：持久执行策略；在简报、大纲和锚点批准节点提出一个直接问题，并等待明确批准。
- `auto`：持久执行策略且只有显式指定时才使用；采用默认值并跳过可选人工批准，但不能跳过用户权限、无安全默认值的决策或任何硬质量门。
- `resume`：入口动作；重新打开已有运行，先读取 `run.json`，严格按“全局恢复顺序”依次处理 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、schema-v1 `visual_generation_transaction` 迁移、`active_visual_generation_batch`；前五项均不存在后才能扫描第一个未完成或脏阶段。始终保留既有 `run.json.mode`。
- `revise`：入口动作；保留既有 `run.json.mode`，同样必须先完成或停止于“全局恢复顺序”的 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、schema-v1 `visual_generation_transaction` 迁移、`active_visual_generation_batch`；只有五类 durable control state 均不存在后，才能依据失效规则标记受影响下游产物并重新生成。

因此，`run.json.mode` 只能持久化 `guided` 或 `auto`；`new`、`resume`、`revise` 都不写入该字段。

新运行的运行根目录只放用户可读的 `大纲.md`、最终页面 `slides/` 与内部目录 `.ppt-pilot/`。内部 `.ppt-pilot/` 存放 `run.json`、`简报.md`、`研究.md`、`来源.md`、`故事板.md`、`文稿审查.md`、`质量检查报告.md`、theme、generation prompts 与 samples；不得把新运行的 `大纲.md` 写入内部目录。旧英文或旧布局运行由 `resume`／`revise` 原位读取，保持一套连贯路径，不自动迁移。

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

`visual_generation_blocker` 不是用户问题，不写入 `pending_interaction`。它只能记录安全 Skill 相对 `resource` 或 `none`，不能持久化未验证绝对路径、URL、工作区路径或机密内容；写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，并保持受影响 slide dirty。历史 crash 留下 durable prompt／`compiling` transaction／active blocker 旧协议组合时，prompt 必须视为不可信派生产物：保持受影响 slide dirty，保留 previous final，按需隔离旧 prompt 与 orphan candidate，并按 [artifact-contract.md](artifact-contract.md) 重新执行完整无副作用 preflight；不得采用旧 prompt，不得直接标记为 `compiled`，也不得直接移除 blocker。失败则按 canonical blocker 规则保留或幂等刷新 blocker。完整 preflight 成功时，只能先以一次原子 `run.json` 替换移除 blocker；若 schema-v1 `visual_generation_transaction` 仍存在，必须原样保留并重新进入全局顺序，由下一步零模型调用 migration 按 pointer-last 发布 v2 owner，不能跨过迁移直接创建新的 `compiling` transaction。只有 v1 owner 不存在时，新操作才可创建新 transaction。阻断期间不得启动 generator、不得写 SVG、不得降级为 patch 或改用其他风格。

正式生产按 `ordered_slide_ids` 选择每批 3–4 页，默认 `batch_width: 4`；最后一批可为 1–4 页。确定性 preflight 先在内存完成，随后在任何 prompt／transaction／candidate durable write 前完成宿主能力协商；无安全 fresh isolation 时只写 run-level blocker。能力通过后才按 [artifact-contract.md](artifact-contract.md) 的 pointer-last 顺序写入每页 schema-v2 transaction、batch manifest，最后原子发布 `run.json.active_visual_generation_batch`。manifest 只拥有顺序、refs、批次快照与可重建 cursor 提示，不复制页面 state。

`active_visual_generation_batch` 恢复保持同一全局 order：只有无 pending、无 blocker 时处理。pointer 在 files 前出现属于 `visual_generation_state_conflict`；files 完整而 pointer 缺失只做 pointer-only completion。恢复按 manifest 的 `ordered_slide_ids` 读取完整 transaction inventory，重建 `promotion_cursor`／`blocker_cursor`，并忽略 completion callback 或 manifest cursor 的授权含义。候选只有在 durable `candidate_written` 且 hash 匹配时可采用；`generating` 上的 orphan candidate 必须隔离。`validated` final CAS 只允许 candidate 已在 final、prior final 仍在、或第三 hash conflict 三种结果，且始终保留 previous final。

新批次在 durable 写入前协商 fresh isolated text task 能力；已激活批次在恢复／新 epoch 前重新协商。native 优先、remote 次之；并发+durable lookup 使用配置 width 3/4，缺少并发或 lookup 时降为 width 1。非 Git 工作区不降级。没有 fresh isolation 时，新批次只写 run-level `generator_unavailable` blocker，现有批次保留 transactions 并标记 blocked；绝不调用嵌套 CLI、探测 credentials/profiles、要求 worktree，或使用当前上下文生成。

每个 eligible `compiled` transaction 在同一 `dispatch_epoch` 最多一次 spawn。四个页面可共享 epoch 并并发生成；coordinator 将完整 prompt bytes 按值交给任务，任务固定 fresh history、无 filesystem、无 tools、text-only。coordinator 独占 candidate 写入、hash 与 transaction 提交。每页 validation 可在 sibling 生成期间并行，但 final promotion、visible blocker publication 和 `run.json` pointer 改变始终按 `ordered_slide_ids` 串行确定；visible blocker 只发布最低 ordered failed／undispatched slide，不能按 completion order 选择。

## guided 检查点

- `brief`：重要简报决策解决后，写入待回答问题并请求简报批准；批准前不得进入研究或大纲。
- `outline`：展示核心论点和证明顺序后请求大纲批准；批准前不得创建故事板。
- `anchor`：展示两页锚点和真实渲染证据后请求锚点批准；批准前不得设置 `stage: production`。

等待期间，顶层 `stage` 保持当前阶段，不得新增暂停或等待阶段。`pending_interaction.status: pending` 时只等待明确回答；`answered` 时使用保存的规范化决定完成幂等写入，并以单次原子替换同时提交阶段转换和交互对象删除／替换，不得重新提问。推荐、叙述性暂停或没有反对都不是批准。

## 文稿审查硬质量门

五文件冻结后立即进入审查：每轮优先委派全新独立子 Agent；启动或结果归因失败时按契约执行 `inline_fallback`（当前上下文降级，报告必须声明隔离限制）；只有两种方式都不可用时才使用 `review_unavailable`。任何 `BLOCKER`／`HIGH` 问题不是 `RESOLVED` 就阻断——`OPEN` 与 `ACCEPTED_RISK` 仍然阻断；零问题也必须保存显式 `PASS` 报告。subagent 与 inline 共同计入每 cycle 最多三轮；三轮仍有阻断问题时进入 `manuscript_blocked`。

findings 字段 schema、七维检查、设计师视角材料缺口协议、用户业务决策与多轮解决要求，以 [文稿审查](manuscript-review.md) 为单一权威。

### 批准检查点与视觉阶段转换

审查通过时记录顶层 `manuscript_approved` 检查点，并把 `run.json.manuscript_review.state` 保持为 `manuscript_approved`：解析主题令牌前设置 `stage: theme`，制作锚点前设置 `stage: anchor`，生成正式页面前设置 `stage: production`。主题阶段解析当前有效主题后直接编译锚点页 prompt；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页从故事板与 `theme.json` 直接编译其余页面 prompt。任何页面在对应 `generation-prompts/<slide-id>.md` 有效前都不能生成。页面生成 Prompt 不是新的顶层阶段；其编译与 fresh generator 输入隔离分别遵循[页面直接编译与生成](visual-brief-and-generation.md)与 [redesign-prompt](redesign-prompt.md)。

### 生产护栏

- `manuscript_review.state = manuscript_approved` 持续有效前，不得创建 `theme.json`、样例或正式页面；
- 即使零问题，也必须写入并保存 `PASS` 报告。
