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

所有运行统一生成中文文件名并写入 `.ppt-pilot/`：`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md`、`文稿审查.md` 与 `质量检查报告.md`。

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

五文件冻结后立即进入审查：每轮优先委派全新独立子 Agent；启动或结果归因失败时按契约执行 `inline_fallback`（当前上下文降级，报告必须声明隔离限制）；只有两种方式都不可用时才使用 `review_unavailable`。任何 `BLOCKER`／`HIGH` 问题不是 `RESOLVED` 就阻断——`OPEN` 与 `ACCEPTED_RISK` 仍然阻断；零问题也必须保存显式 `PASS` 报告。subagent 与 inline 共同计入每 cycle 最多三轮；三轮仍有阻断问题时进入 `manuscript_blocked`。

findings 字段 schema、七维检查、设计师视角材料缺口协议、用户业务决策与多轮解决要求，以 [文稿审查](manuscript-review.md) 为单一权威。

### 批准检查点与视觉阶段转换

审查通过时记录顶层 `manuscript_approved` 检查点，并把 `run.json.manuscript_review.state` 保持为 `manuscript_approved`：解析主题令牌前设置 `stage: theme`，制作锚点前设置 `stage: anchor`，生成正式页面前设置 `stage: production`。视觉 brief 与页面生成 Prompt 不是新的顶层阶段；其组装、编译与 fresh generator 输入隔离分别遵循 [逐页视觉 brief 与生成](visual-brief-and-generation.md) 与 [redesign-prompt](redesign-prompt.md)。

### 生产护栏

- `manuscript_review.state = manuscript_approved` 持续有效前，不得创建 `theme.json`、样例或正式页面；
- 即使零问题，也必须写入并保存 `PASS` 报告。
