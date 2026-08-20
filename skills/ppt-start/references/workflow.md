# PPT Pilot 工作流参考

## 阶段顺序

`brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`

任何入口都先读取[用户交互与确认协议](interaction-protocol.md)。它定义模式默认值、决策队列、单问题回合、明确确认和可恢复等待；本文件只规定这些交互位于哪个阶段。

## 入口动作与执行策略

- `new`：从主题或简报开始创建新演示文稿；它是入口动作，不是写入 `run.json.mode` 的值。新运行未显式指定策略时使用 `guided`。
- `guided`：持久执行策略；在简报、大纲和锚点批准节点提出一个直接问题，并等待明确批准。
- `auto`：持久执行策略且只有显式指定时才使用；采用默认值并跳过可选人工批准，但不能跳过用户权限、无安全默认值的决策或任何硬质量门。
- `resume`：入口动作；重新打开已有运行，先读取 `run.json` 并处理 `pending_interaction`，保留既有 `run.json.mode`，再从第一个未完成或脏阶段继续。
- `revise`：入口动作；保留既有 `run.json.mode`，依据失效规则只使受影响的下游产物失效并重新生成。

因此，`run.json.mode` 只能持久化 `guided` 或 `auto`；`new`、`resume`、`revise` 都不写入该字段。

新运行统一生成 `简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md`、`文稿审查.md` 和 `质量检查报告.md`。`resume`／`revise` 打开旧英文运行时，必须先依据 `run.json` 与完整文件集合解析该运行实际使用的名称，然后原位读取；不得自动重命名、复制或迁移。后续写回沿用该运行已经采用的同一套名称。

## guided 检查点

- `brief`：重要简报决策解决后，写入待回答问题并请求简报批准；批准前不得进入研究或大纲。
- `outline`：展示核心论点和证明顺序后请求大纲批准；批准前不得创建故事板。
- `anchor`：展示两页锚点和真实渲染证据后请求锚点批准；批准前不得设置 `stage: production`。

等待期间，顶层 `stage` 保持当前阶段，不得新增暂停或等待阶段。`pending_interaction.status: pending` 时只等待明确回答；`answered` 时使用保存的规范化决定完成幂等写入，并以单次原子替换同时提交阶段转换和交互对象删除／替换，不得重新提问。推荐、叙述性暂停或没有反对都不是批准。

## 文稿审查硬质量门

完成并冻结 `简报.md`、`研究.md`、`来源.md`、`大纲.md` 和 `故事板.md` 后，必须立即进入文稿审查硬质量门。

- 审稿上下文必须是全新且独立的子 Agent，只能读取指定输入；独立性必须由宿主真实返回的子上下文，以及归属于同一上下文的完成／结果事件证明。
- 启动必须在任何等待前成功并返回非空子上下文。接收者列表或 Agent 状态为空的等待说明启动没有发生；应立即进入 `review_unavailable`，不得再次等待或推断结果。
- 审稿人只能看到五个文稿输入：`简报.md`、`研究.md`、`来源.md`、`大纲.md` 和 `故事板.md`。
- 不得向审稿人提供创作对话、主题上下文、样例、`theme.json` 或任何页面产物。
- 如果无法启动独立审稿人，或子上下文启动／结果缺少可归因的宿主证据，必须写入当前运行的审查报告文件：新运行使用 `文稿审查.md`，旧英文运行沿用 `run.json.manuscript_review.latest_report` 指向的 `manuscript-review.md`；随后进入 `review_unavailable` 并停止。
- 最多执行三轮审查。
- 三轮文稿审查后仍未通过时，进入终止状态 `manuscript_blocked`。
- 审查未完成或被阻断时，任何生产阶段都不得运行。
- 同上下文审查不能满足这个质量门。

### 批准检查点与视觉阶段转换

审查通过时，把 `run.json.manuscript_review.state` 设置为 `manuscript_approved`，并记录顶层 `manuscript_approved` 检查点。解析主题令牌前设置 `stage: theme`，制作锚点前设置 `stage: anchor`，生成正式页面前设置 `stage: production`。因此，顶层阶段始终表示当前工作流位置，而嵌套审查状态持续授权所有视觉阶段。

视觉 brief 不是新的顶层阶段。`theme` 阶段解析当前有效主题后组装锚点页面 brief；锚点批准或 `auto` 内部验证完成后，在 `production` 中按页组装其余 brief。任何页面在对应 `visual-briefs/<slide-id>.md` 有效前都不能生成；brief 的组装、内容保护和旧运行补建规则遵循[逐页视觉 brief 与生成契约](visual-brief-and-generation.md)。

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
- `ACCEPTED_RISK` 对 `BLOCKER` 与 `HIGH` 仍然阻断；修正或限定文稿后，必须再次进行独立审查。

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
