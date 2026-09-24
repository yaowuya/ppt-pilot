# 用户交互协议

只有不同答案会实质改变内容、权限、视觉方向或交付时才询问。请求、工作区或已批准产物已经给出的答案不得重复询问。推荐不是确认。

## 模式与问题选择

- 新运行默认 `mode: guided`；只有用户明确指定才写 `auto`。
- `resume` 和 `revise` 是当前意图，不是 mode 值；它们保留既有 mode。
- `guided` 的固定批准点是简报、大纲和锚点；`auto` 跳过这些可选批准，但不跳过外部传输、机密披露或无安全默认的决定。
- 每轮只提出最早的一个决策节点；同一节点的紧密字段可一起收集。
- 有合理选择时提供 2–4 个互斥选项、逐项影响、推荐与理由；没有合理选项时提出一个开放问题和回答格式。

## 先持久化，再提问

提出问题前，AI 在 `run.json.pending_interaction` 写入：

- `id`、`stage`、`kind`、`question`、`status: pending`；
- 有限选择时写 `options`、`option_effects`、`recommendation`、`recommendation_reason`；
- 批准问题写 `checkpoint` 和正整数 `approval_attempt`。

写入并读回后提出同一个问题，然后停止本轮。等待期间 stage 保持不变；不得继续下游工作，也不得把推荐、沉默或摘要展示当作回答。

## 直接消费回答

收到回答后，AI 直接完成以下单次状态迁移，不调用回答命令：

1. 读取 `pending_interaction` 与用户原始回答；
2. 在一次原子写入中把对象标记为 `status: answered`，保存原始回答；有限选择还保存规范化决定；
3. 幂等应用到该节点拥有的文稿、主题或页面状态；
4. 在 `run.json.interaction_history` 追加同一 `id` 的一条 `status: applied` 记录；重复恢复不得重复追加；
5. 清除原对象，或在答案仍不充分时替换为新的 pending 澄清对象；
6. 重新选择最早可执行动作并继续。

如果写入中断，恢复看到 `answered` 时依据同一 ID 补完步骤 3–5，不重复询问。

### Retry 与 skip

- `retry`／`recompose`：保留旧失败证据；只有真正再次调用 generator 时才把该页 attempts 增加 1。
- `skip`：把指定页改为 `skipped`，记录 `skip.decision: user_skipped`、原始回答和应用时间；attempts 不变，然后继续最早的独立页面或 QA 动作。
- skip 只作用于该页，不能豁免共享状态冲突、未批准文稿、安全要求或其他页面错误。

## Guided 批准

批准问题使用 `approve|request_revision`：

| checkpoint | approve 后 stage | 效果 |
|---|---|---|
| `brief` | `research` | 冻结简报版本并记录批准 |
| `outline` | `storyboard` | 冻结大纲版本并记录批准 |
| `anchor` | `production` | 冻结当前锚点视觉方向并记录批准 |

`request_revision` 保持当前 stage。答案足够具体时直接修订并重新检查；只表达“不批准”时替换为一个聚焦澄清问题。涉及事实、来源、核心主张、大纲或故事板时返回最早受影响内容阶段并重新文稿审查；纯视觉修改只使相应 theme/page 变脏。

## 条件式问题

以下情况没有安全默认时才阻塞提问：

- 外部网络研究或机密派生查询；
- 受众、行动、必需内容或页数之间的实质冲突；
- 会改变业务立场的审稿修订；
- 明确品牌约束与可用风格冲突；
- 用户是否 retry、skip 或停止一个已失败页面；
- 多个运行目标无法唯一选择。

其他低影响、可逆未知项采用保守默认并写入 `assumptions`。
