# 文稿审查契约

审查执行自动发生，不是可选批准点。审稿后需要用户承担的业务取舍遵循[用户交互与确认协议](interaction-protocol.md)，但任何用户回答都不能替代正式 subagent／inline 审查或放宽质量门。

## 完整文稿定义

只有以下五个输入全部写完并冻结，文稿才算完整：

- `简报.md`
- `研究.md`
- `来源.md`
- `大纲.md`
- `故事板.md`

这些是新运行的标准名称。旧英文运行可以继续使用 `brief.md`、`research.md`、`sources.md`、`outline.md` 和 `storyboard.md`；同一轮必须读取并冻结该运行实际使用的一整套名称，不得混用或自动改名。

这些文件稳定后，创作上下文才可以移交文稿审查。

## 硬质量门位置

文稿审查紧接在这五个文件之后。无论持久策略为 `guided` 或 `auto`，也无论当前入口动作为 `new`、`resume` 或 `revise`，都必须执行。

## 审查输入、权限与模式

每轮先尝试把审查委派给一个**全新且独立的子 Agent／上下文**，只授予以下只读输入：

- `简报.md`
- `研究.md`
- `来源.md`
- `大纲.md`
- `故事板.md`
- 本审查规范文件

独立审稿人不得接收创作对话、设计主题、样例、`theme.json`、`samples/`、`slides/`、截图或其他视觉产物。

如果子 Agent 无法启动、接收者为空、完成事件缺失或结果上下文不匹配，则本轮改用 `inline_fallback`：当前上下文在当前步骤中直接读取同一五文件冻结快照和本规范，重新列出主张／来源映射并执行完整审查。inline 正式审查不得使用视觉产物、先前辩解或用户偏好作为事实支持，报告必须声明“当前上下文降级审查，不具备独立上下文隔离”。

审查模式只能是 `subagent` 或 `inline_fallback`。两种模式使用相同 findings schema 和质量门；`subagent` 优先，只有委派失败后才能 inline。

## 执行证据与降级

`subagent` round 必须记录宿主返回且非空的 `delegation_evidence`：`child_context_id`、`completion_event_id`、`result_context_id`，并要求 child 与 result context 一致。不得虚构审稿人名称、上下文 ID、完成事件或结果来源；叙述、休眠或空等待都不是证据。

启动顺序固定为：必须先启动、后等待。先请求启动并检查响应；成功后记录 child context；只等待该 child；只接收归属于同一 child 的结果。接收者列表为空、Agent 状态为空或尚未获得 child 就等待，说明委派失败，不能重复空等待。

委派失败后立即持久化 `inline_fallback` pending round 并在当前步骤直接审查。inline round 不得包含 `delegation_evidence`，必须记录互斥的 `fallback_evidence`：

- `delegation_attempted: true`
- `reason`：`child_context_unavailable`、`child_start_failed`、`completion_event_missing`、`result_context_mismatch`、`delegation_capability_unavailable` 之一
- 非空且不含机密的 `host_detail`

`run.json` 本身只能记录来源声明。真实 subagent 独立性仍需保存的宿主 transcript／协作日志交叉核对；inline 报告只能证明已按降级契约执行，不能证明独立性。

如果冻结输入不可读、当前上下文也不能执行审查，或 pending 状态发生不可恢复冲突，才进入 `review_unavailable`。委派不可用本身不再导致 `review_unavailable`。

## 审查输出与持久化职责

审稿人返回包含问题和审查来源的结构化报告载荷。审稿人绝不修改文稿文件，也不写入工作区文件。创作上下文负责把返回载荷原样保存到当前运行实际使用的审查报告；新运行写入 `文稿审查.md`，旧英文运行沿用 `manuscript-review.md`，并把后续作者修订说明单独记录到 `run.json.manuscript_review.review_history`。

每条问题必须包含以下全部字段：

- `id`
- `severity`
- `category`
- `slide_ids`
- `claim`
- `evidence`
- `recommendation`
- `status`

允许值：

- `severity`：`BLOCKER`、`HIGH`、`MEDIUM`、`LOW`
- `status`：`OPEN`、`RESOLVED`、`ACCEPTED_RISK`

同一报告中的 `id` 必须唯一。

即使没有发现问题，也必须写入明确的 `PASS` 报告。

## 审查维度

每轮至少检查：

1. 来源覆盖；
2. 事实准确性；
3. 时效性主张是否仍然有效；
4. 逻辑与叙事流；
5. 重复或冗余；
6. 遗漏或缺失主张；
7. 风险与缺少支持的建议。

## 重大影响与实时核验

- 除非明确允许并实际完成实时核验，缺少支持或具有时效性的重大影响主张必须标为 `HIGH` 或更高。
- 如果当前约束下无法实时核验，应把这类重大影响且未支持／有时效性的主张记录为 `HIGH`。

## 质量门判定

只有每个 `BLOCKER` 或 `HIGH` 问题都为 `RESOLVED` 时，质量门才能通过。任一阻断级问题不是 `RESOLVED` 都会阻断。

- `OPEN` 在 `BLOCKER` 与 `HIGH` 级别会阻断；
- `ACCEPTED_RISK` 在 `BLOCKER` 与 `HIGH` 级别仍然阻断。记录接受风险不会把缺少核验变成批准；
- 文稿修订或限定后，后续轮次仍先尝试全新独立审稿人；委派失败时由正式 inline fallback round 核验，并在有冻结证据时把同一问题 ID 标记为 `RESOLVED`；
- ID 重复、字段缺失、`findings` 不是列表或其他格式错误都会导致验证失败，不能产生批准。

当前上下文只有在 `inline_fallback` round 已持久化委派失败、冻结快照、fallback evidence 和隔离限制，并输出完整结构化报告时，才能满足正式质量门。未进入该模式的随手自审仍只能记录为建议性 QA，不能改写批准状态。inline PASS 与 subagent PASS 均只有在全部阻断级 finding 为 `RESOLVED` 时才能进入 `manuscript_approved`。

## 轮次可追踪性

每轮记录必须保存：

- `cycle`：新运行和新审查周期必需；旧 schema-version 1 记录缺少时按 `1`；
- `round`：所属 cycle 内的轮次；
- `reviewer_id`
- `reviewer_context`
- `review_mode`：`subagent` 或 `inline_fallback`；旧记录缺少且含 delegation evidence 时按 `subagent`；
- `delegation_evidence` 或 `fallback_evidence`，按模式互斥；
- `reviewed_file_snapshot`，包含该运行实际使用的五个文件名和稳定的 `snapshot_id`；
- 完整 `findings` 列表
- 再审前的作者修订说明

`run.json.manuscript_review.review_history` 保存这些轮次记录。后续轮次必须重复此前每个阻断问题 ID；新的 subagent 或 inline fallback round 都可以在冻结证据支持时把同一 ID 标为 `RESOLVED`，但必须保留实际 review mode。问题不得悄然消失。

## 审查可用性、pending round 与最大轮次

- 每轮开始前持久化 `manuscript_review.pending_round`：`cycle`、下一 `round`、`mode`、冻结 `reviewed_file_snapshot`、mode-specific 启动 evidence 和 `status: in_progress`。subagent pending 只记录 `delegation_attempt_evidence.child_context_id`；inline pending 记录完整 `fallback_evidence`。完成后用一次原子 `run.json` 替换追加 history、更新 round／state／status 并删除 pending round。
- crash／resume 复用相同 cycle、round、mode 和 snapshot，不重复增加轮次；pending round 必须是当前 cycle 中 `review.round + 1` 且不超过 3。completed report 的 `review_mode` 必须匹配 pending `mode`；inline fallback evidence 必须一致，subagent completed delegation 的 child/result 必须等于 pending child。snapshot 改变时旧 pending round 失效并重新冻结。同一运行只允许一个 pending round。
- durable report 已存在时，resume 必须验证同一 cycle／round／mode／snapshot，并要求前一轮每个未解决 `BLOCKER/HIGH` ID 在本轮继续出现；只有有冻结证据的 `RESOLVED` 才能放行。验证后只追加一次 history、原子删除 pending；重复 resume 为 no-op。
- 独立委派不可用时设置 `mode: inline_fallback` 并在当前步骤审查，不进入 `review_unavailable`。只有 inline 也无法执行时才保留 legacy-compatible `mode/state: unavailable` 并停止。
- 既有 `review_unavailable` 历史不自动改写；resume 可以保留旧原因并创建下一合法 inline pending round。legacy unavailable 报告继续记录 `review_mode: unavailable`、失败原因以及“没有审稿人问题，因为没有任何审查 round 完成”，并让 `review_history` 保持为空。
- `review_unavailable` 不等于 `manuscript_blocked`；后者表示实际 subagent 或 inline 审查已运行但仍有未解决阻断问题。
- 每个审查周期最多三轮，subagent 与 inline round 共同计数：
  - 第 1 轮，之后可以由作者修订；
  - 第 2 轮，之后可以由作者修订；
  - 第 3 轮是该周期最后一次审查。

当前周期只有在通过并记录 `manuscript_approved` 后，未来新的事实、来源、主张、大纲或故事板修改才可以按产物契约开启 `cycle + 1` 并设置 `round: 0`。处于 `manuscript_blocked` 的周期不得开启新周期或第 4 轮；否则三轮硬门可以被伪装修订绕过。旧记录没有 `cycle` 时按 cycle 1 读取。

有未解决阻断问题的轮次记录为 `manuscript_blocked`。一个周期三轮均未通过后，停在 `manuscript_blocked` 并展示未解决问题；不得启动该周期第 4 轮，也不得重置计数。

## 多轮解决要求

有效的多轮报告必须展示：

- 第 1 轮包含阻断问题 ID 和冻结文稿快照；
- 作者修订记录位于审稿人上下文之外；
- 第 2 轮重新优先尝试独立子 Agent；不可用时由 inline fallback 执行，并在通过前用冻结证据把相同问题 ID 标记为 `RESOLVED`。

## 用户业务决策与作者修订

审稿人返回阻断问题后，创作上下文先判断修订是否具有唯一、证据保持型修复：删除无支持数字、补回来源限定、修正与来源不一致的事实或缩小主张范围，只要不改变核心立场、建议和受众行动，就直接修订并进入下一轮正式审查，不询问用户。

如果多个修订方向都合理，或修订会改变核心立场、业务建议、风险取舍或预期受众行动，则产生一个业务决策问题。问题必须先写入 `pending_interaction`，每轮只询问一个选择，并明确说明推荐方案。审稿人的 `recommendation` 只是审查建议，不是用户确认。

用户回答不能把 `BLOCKER`／`HIGH` 的 `OPEN` 或 `ACCEPTED_RISK` 改写为通过，也不能授权创作上下文在没有正式 round 的情况下自行标记 `RESOLVED`。只有修订后的新冻结文稿经过后续 subagent 或明确记录的 inline fallback round 核验，质量门才可能通过。

## 报告模式声明

每轮报告必须记录 `review_mode: subagent | inline_fallback`、cycle／round／snapshot、对应 execution evidence、verdict 和完整 findings。inline 报告必须包含原文：`当前上下文降级审查，不具备独立上下文隔离`；标题不得写成“独立审查通过”。

## 审查后的生产限制

顶层 `manuscript_approved` 检查点之前，不得创建 `theme.json`、`samples/` 或 `slides/`。顶层 `stage` 进入视觉阶段后，也只有 `run.json.manuscript_review.state` 持续为 `manuscript_approved` 时才允许创建这些产物。
