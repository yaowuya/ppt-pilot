# PPT Pilot 工作流参考

## 阶段顺序

`brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`

任何入口都先读取[用户交互与确认协议](interaction-protocol.md)。它定义模式默认值、决策队列、单问题回合、明确确认和可恢复等待；本文件只规定这些交互位于哪个阶段。

## 入口动作与执行策略

- `new`：从主题或简报开始创建新演示文稿；它是入口动作，不是写入 `run.json.mode` 的值。新运行未显式指定策略时使用 `guided`。
- `guided`：持久执行策略；在简报、大纲和锚点批准节点提出一个直接问题，并等待明确批准。
- `auto`：持久执行策略且只有显式指定时才使用；采用默认值并跳过可选人工批准，但不能跳过用户权限、无安全默认值的决策或任何硬质量门。
- `resume`：入口动作；重新打开已有运行，先读取 `run.json`，严格按“全局恢复顺序”依次处理 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、`visual_generation_transaction`；前四项均不存在后才能扫描第一个未完成或脏阶段。始终保留既有 `run.json.mode`。
- `revise`：入口动作；保留既有 `run.json.mode`，同样必须先完成或停止于“全局恢复顺序”的 `pending_interaction`、`manuscript_review.pending_round`、`visual_generation_blocker`、`visual_generation_transaction`；只有四类 durable control state 均不存在后，才能依据失效规则标记受影响下游产物并重新生成。

因此，`run.json.mode` 只能持久化 `guided` 或 `auto`；`new`、`resume`、`revise` 都不写入该字段。

新运行统一生成 `简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md`、`文稿审查.md` 和 `质量检查报告.md`。`resume`／`revise` 打开旧英文运行时，必须先依据 `run.json` 与完整文件集合解析该运行实际使用的名称，然后原位读取；不得自动重命名、复制或迁移。后续写回沿用该运行已经采用的同一套名称。

## 全局恢复顺序

任何 `resume`、`revise` 或生产重入在扫描普通阶段前，必须按下面恰好四步处理 durable control state。前一项存在时必须先完成或停止，后一项不得预读、创建或覆盖。

| control | order | required action |
|---|---:|---|
| `pending_interaction` | 1 | 先验证或消费待回答／已回答交互；存在时不得处理其他 durable state。 |
| `manuscript_review.pending_round` | 2 | 没有 pending interaction 时恢复同一 cycle／round／snapshot 的文稿审查；匹配的 durable 报告存在时幂等提交一次，不能重启或重复计数。 |
| `visual_generation_blocker` | 3 | 只有没有更高优先级状态时处理；同页 blocker 幂等刷新，同一运行内另一页 active blocker 先被处理。 |
| `visual_generation_transaction` | 4 | 只有没有 pending 与 blocker 时恢复；按 transaction 状态继续，不做普通 stage scan。 |
| stage scan | 5 | 只有前四类 durable control state 都不存在时，才寻找第一个未完成或脏阶段继续。 |

`visual_generation_blocker` 不是用户问题，不写入 `pending_interaction`。它只能记录安全 Skill 相对 `resource` 或 `none`，不能持久化未验证绝对路径、URL、工作区路径或机密内容；写入或刷新 blocker 时保持 `stage`、`mode`、`interaction_history` 不变，并保持受影响 slide dirty。prompt 已 durable 后允许恢复者看到 `visual_generation_transaction.state: compiling` 与 active blocker 同时存在；随后只能通过一次 `run.json` 原子替换同时把 transaction 改为 `compiled` 并移除匹配 blocker。阻断期间不得启动 generator、不得写 SVG、不得降级为 patch 或改用其他风格。

`visual_generation_transaction` 恢复保持同一全局 order：只有无 pending、无 blocker 时处理；默认同一运行一次只允许一个 active transaction，仅当多个事务同属当前生产批次且目标 slide 互不相同时，才允许最多一个批次页数（3–4）个并发 active transaction，恢复时按 slide_id 升序逐个处理。它的 schema、状态图、failure reason consumer 和 No arbitrary delete/cancel 规则以 [artifact-contract.md](artifact-contract.md) 为准；工作流层必须保持 `compiling -> compiled -> generating -> candidate_written -> validated -> promoted`、`generating | candidate_written | validated -> failed`、`failed -> generating`、`failed -> validated` 与 `failed transaction -> new compiling transaction` 的精确语义。transport retry 使用 `generation_attempt + 1` 且每次宿主调用最多 generator 1 次；production `blocker` 冲突解决只能走 unchanged valid candidate 的 promotion retry，或 authoritative inputs changed 的新 compiling replacement。

## guided 检查点

- `brief`：重要简报决策解决后，写入待回答问题并请求简报批准；批准前不得进入研究或大纲。
- `outline`：展示核心论点和证明顺序后请求大纲批准；批准前不得创建故事板。
- `anchor`：展示两页锚点和真实渲染证据后请求锚点批准；批准前不得设置 `stage: production`。

等待期间，顶层 `stage` 保持当前阶段，不得新增暂停或等待阶段。`pending_interaction.status: pending` 时只等待明确回答；`answered` 时使用保存的规范化决定完成幂等写入，并以单次原子替换同时提交阶段转换和交互对象删除／替换，不得重新提问。推荐、叙述性暂停或没有反对都不是批准。

## 文稿审查硬质量门

完成并冻结 `简报.md`、`研究.md`、`来源.md`、`大纲.md` 和 `故事板.md` 后，必须立即进入文稿审查硬质量门。

- 每轮先尝试全新独立子 Agent；成功时只接收五个冻结文稿和规范，并要求真实 delegation evidence。
- 启动失败、接收者为空、完成事件缺失或结果上下文不匹配时，不空等、不询问用户，持久化 `inline_fallback` 的 `pending_round`，由当前上下文在当前步骤中直接执行同一审查规范。
- inline round 使用互斥 `fallback_evidence`，报告必须声明“当前上下文降级审查，不具备独立上下文隔离”；不得伪造 delegation IDs 或称为独立审查。
- subagent 与 inline 使用相同五文件快照、七维审查、findings schema 和阻断规则；inline PASS 可以正式提交 `manuscript_approved`。
- 当前上下文也无法读取／审查冻结输入或 pending 状态冲突时才使用 `review_unavailable`；既有 unavailable 历史保持可读。
- 两种模式共同计入每 cycle 最多三轮；后续轮次仍先尝试子 Agent，失败再 inline。三轮仍有阻断问题时进入 `manuscript_blocked`。
- 审查未完成、pending、unavailable 或 blocked 时，任何生产阶段都不得运行。

### 批准检查点与视觉阶段转换

审查通过时，把 `run.json.manuscript_review.state` 设置为 `manuscript_approved`，并记录顶层 `manuscript_approved` 检查点。解析主题令牌前设置 `stage: theme`，制作锚点前设置 `stage: anchor`，生成正式页面前设置 `stage: production`。因此，顶层阶段始终表示当前工作流位置，而嵌套审查状态持续授权所有视觉阶段。

视觉 brief 不是新的顶层阶段。`theme` 阶段解析当前有效主题后组装锚点页面 brief；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页组装其余 brief。任何页面在对应 `visual-briefs/<slide-id>.md` 有效前都不能生成；brief 的组装、内容保护和旧运行补建规则遵循[逐页视觉 brief 与生成契约](visual-brief-and-generation.md)。

页面生成专用 Prompt 也不是新的顶层阶段。首次生成或 `recompose` 时，保持当前 `anchor` 或 `production` 阶段，先组装 visual brief，再按[页面首次生成与重新排版专用 Prompt 契约](redesign-prompt.md)写入 `generation-prompts/<slide-id>.md`，由 fresh 独立上下文只接收该 Prompt。首次生成不提供其他页面；重新排版还不得提供旧 SVG 或创作对话。提取并验证 SVG 前不得把候选标记为有效；通过后再按脏标记与 QA 规则提交。早期 `redesign-prompts/` 只读兼容。

来源、主张、大纲或故事板发生变化时，继续任何视觉工作前必须使嵌套批准失效。即使顶层阶段被错误记录为视觉阶段，只要审查状态为 `manuscript_blocked` 或 `review_unavailable`，该视觉阶段仍然无效。

### 问题质量契约

每轮审查都把问题写入当前运行的审查报告（新运行为 `文稿审查.md`，旧英文运行为 `manuscript-review.md`），每条问题包含：

- `id`
- `severity`（`BLOCKER`、`HIGH`、`MEDIUM`、`LOW`）
- `category`
- `slide_ids`
- `claim`
- `evidence`
- `recommendation`
- `status`（`OPEN`、`RESOLVED`、`ACCEPTED_RISK`）

要求：

- 每份报告内的问题 ID 必须唯一；
- 每条问题必须包含全部必填字段；
- 只有所有 `BLOCKER` 或 `HIGH` 问题都为 `RESOLVED` 时质量门才通过；任何阻断级问题不是 `RESOLVED` 都会继续阻断；
- `ACCEPTED_RISK` 对 `BLOCKER` 与 `HIGH` 仍然阻断；修正或限定文稿后，必须再次进行正式 subagent／inline 审查。

### 审查维度

审稿人至少检查：

1. 来源覆盖；
2. 事实准确性；
3. 时效性；
4. 逻辑；
5. 重复；
6. 遗漏；
7. 风险。

无法实时核验时，缺少支持且影响重大或具有时效性的主张必须标为 `HIGH`。

### 生产护栏

- `manuscript_review` 获批前，不得创建主题产物 `theme.json`、样例或正式页面；
- 即使没有发现问题，也必须写入并保存零问题的 `PASS` 报告。
