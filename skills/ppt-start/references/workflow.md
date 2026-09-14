# PPT Pilot 工作流参考

## 阶段、交付与验证

兼容工作顺序保持，终态分支显式化：

```text
brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete|partial|failed
```

`stage` 表示当前工作流状态，并在结算后诚实记录终态；`run.delivery.status` 保存同名交付分区结果。两者的固定对应关系是：`prepared` 仅存在于 `stage: qa`，final `complete|partial|failed` 分别要求 `stage: complete|partial|failed`。`complete` 仍只表示无遗漏；验证结果另看 QA／editable 状态，不能由任一终态推断。

任何入口先读[交互与确认协议](interaction-protocol.md)。该文件拥有模式、问题队列、批准和生产策略授权；本文件只规定它们发生在何处。

## 固定入口

先用当前安装 Skill 的 `scripts/ppt_entry.py` 选择、新建或恢复唯一运行；默认 `resume`。同源既有运行原位恢复，只有明确授权才建独立副本。外部 PPT/PPTX 首次导入按[旧稿导入](source-deck-redesign.md)建立源清单和映射，之后仍按同一阶段顺序原位恢复。

运行根目录只放用户可读的 `大纲.md`、最终 `slides/` 和 `.ppt-pilot/`。内部 owner 包括 `run.json`、简报、研究、来源、故事板、审查、主题、prompt、sample、QA 和 runtime evidence。运行目录不承载维护脚本、依赖或 runtime 副本。

最小 `run.json` 一旦存在，入口、恢复和修订都先执行固定 audit。以下任一结果全局阻断并保持现场：

- artifact firewall 污染；
- owner schema、共享 snapshot 或路径身份损坏；
- CAS／pointer 冲突；
- 固定 runtime 缺失或完整性校验失败；
- 未接受、不可安全调用或当前不可用的宿主 adapter；
- 权限、旧稿绑定或其他共享完整性 gate 失败。

audit `PASS` 只说明运行可继续，不是内容批准、生成授权、QA PASS 或 Office 验证。

## 模型面对的视觉接口

视觉阶段优先使用两项高层操作：

```text
python <skill-dir>/scripts/ppt_runtime.py advance --run-dir RUN [--allow-partial] [--skip-slide SID ...]
python <skill-dir>/scripts/ppt_runtime.py finalize --run-dir RUN
```

### `advance`

`advance` 校验当前 durable graph，并返回下一项声明式动作、输入和完成条件。coordinator 执行这一个动作后再次调用 `advance`。动作可能是等待批准、启动或关联一个已保留 dispatch、验证／修复一页、处理 active batch、写 QA，或报告全局 blocker。

- 新运行持久化 `production_policy`，默认 `best_effort`；显式 strict 请求写 `strict`。
- 缺少字段的旧运行保持 strict。
- `--allow-partial` 是把既有运行显式持久化为 `best_effort` 的授权；没有该参数就不能升级。
- `--skip-slide SID` 只用于已经获得的显式用户跳过决定，可重复传多个 ID；runtime 保存审计证据并保持这些页 dirty。
- 普通页面失败不会令独立页面不可推进。strict 只限制最终遗漏结算，不改变页面故障的局部性。

### `finalize`

`finalize` 只消费当前 owner 和真实证据，不生成页面，也不推断缺失记录。任何 `prepared|complete|partial|failed` 显式结算都先要求 `run.json.manuscript_review.state == manuscript_approved` 且当前批准快照仍有效；否则保持原 owner 并拒绝交付，不给 delivery 增加字段。它验证原始 targets 的 ordered partition、storyboard/theme/QA hash、每个 delivered SVG 及其 render-bound QA，以及每个 omission 的 immutable failed transaction／显式 skip 和终态 manifest seal。

- 无遗漏产生 `delivery.status: complete` 并原子进入 `stage: complete`。
- `best_effort` 且 delivered、missing 均非空时可产生 `delivery.status: partial` 并原子进入 `stage: partial`。
- 零 delivered 产生 `delivery.status: failed` 并原子进入 `stage: failed`，且不生成 PPTX。
- strict 且仍有未解决页面时不能结算 partial；可先处理运行时列出的独立可执行工作，但最终仍需合法解决失败页或由用户明确授权 `--allow-partial`。未获授权的缺页不生成 prepared／partial 交付分区。

低层 mutation／replay 命令仍是[固定运行时参考 API](runtime-canonical-owners.md#low-level-reference-apis)，供 runtime 开发、诊断和其高层响应引用，不是模型逐项执行清单。coordinator 不手写哈希、事务、attempt、manifest、pointer、CAS 或 delivery。

## 四节点执行图

### 1. 意图与内容基线

1. `brief`：确认目标受众、行动、范围、语言、交付形式、权限、品牌硬规则和无安全默认值的决策。
2. `research`：保存事实、数字、单位、期间、限定词和来源映射；明确未知项。
3. `outline`：确定核心论点、证明顺序和页面角色。
4. `storyboard`：为每页冻结叙事、显示素材、content blocks、block/source 映射和前后逻辑。
5. `manuscript_review`：按[文稿审查](manuscript-review.md)审查五份内容 owner。`BLOCKER`／`HIGH` 必须成为 `RESOLVED`；零问题也持久化明确 PASS。

新审查快照同时拥有 exact 与 semantic fingerprints；semantic 只排除已知结构化视觉／元数据字段，事实、主张、限定、来源和叙事仍绑定。旧批准 exact-byte strict，不追补字段。

**节点完成：** 当前 `manuscript_review.state == manuscript_approved`，五份 owner 与批准快照一致。

### 2. 视觉基线

1. `theme`：从批准内容选择已注册风格，写入并验证 `theme.json`。
2. `anchor`：由模型选择能覆盖主要版式与复杂内容的代表页，不固定页号；执行 SVG 合同、真实非 Office 渲染和逐页 QA。
3. `guided` 等待真实锚点批准；`auto` 保存同等内部验证。

风格、字体、色彩、品牌表达和构图方向只写 `theme.json` 或 `projection: runtime_visual` 的受控视觉修订。它们不改内容-owned brief/storyboard 来逃避审查。实际事实或叙事变化仍按正式失效和重审处理。

**节点完成：** 当前 theme identity 有效，所选 sample 与真实 render evidence 绑定，锚点状态是 `approved` 或 `validated`。兼容协议要求多页稿至少两个 sample，单页稿一个；额外代表页由模型按覆盖需要选择。

### 3. 页面局部生产

在 `production` 反复调用 `advance`。页面从批准 storyboard + theme + 适用视觉 overlay 直接编译 frozen prompt；fresh-context generator 只接收完整 prompt bytes 并只返回一个 SVG。coordinator 拥有来源 enrichment、candidate write、验证、hash 和 promotion。

每页整条生产链最多三次真实 dispatch，包括 initial、retry、recompose／runtime visual repair；本地修复也必须位于 runtime 返回的剩余预算内。新 request ID、新 transaction、fallback 名称或另建运行均不能重置／隐藏调用。

失败分类：

| scope | examples | effect |
|---|---|---|
| page-local | generator refused/timeout/malformed；SVG contract；fact/source mismatch；visual QA | 原失败 transaction 字节与 attempt 不变；该页 repair、exhaust 或 omit，独立页继续 |
| global | shared owner/snapshot integrity；CAS/pointer；unsafe/unknown adapter；adapter unavailable；permission | 所有写入停止，保留 durable evidence，先修复同一共享问题 |

页面局部失败不写成 deck-wide blocker。预算耗尽只终止该页当前生产路径；`best_effort` 可结算 omission，strict 可继续 sibling 但不能交付 partial。真正 global blocker 不能被 omission、skip 或 best-effort 绕过。

候选只在 XML、安全、事实来源、真实 geometry 和页面 QA 通过后 promoted。`0.88` 估算宽仅触发人工／视觉核验；解析后的 safe-bound 越界、最小字号、unsafe SVG、来源事实错误和用户硬约束仍是该页 hard failure。

**节点完成：** 每个原始 target 已 promoted，或有 immutable exhausted failure／explicit skip；missing 页仍 dirty，active batch 已以 terminal manifest 结算，且无 global blocker。

### 4. 诚实交付

`qa` 仅评估将被 delivered 的当前正式 SVG，并审计 original target/delivered/missing partition。每个 delivered 页必须有与当前 SVG digest 绑定的真实 render evidence；源码静态检查不能替代视觉 PASS。partial 的整套 QA 仍检查已交付序列的叙事连续性、事实、来源、节奏和风格，并明确遗漏如何影响阅读。

调用 `finalize` 后：

- `complete`：`stage` 与 `delivery.status` 均为 `complete`，所有 targets delivered，missing 为空；
- `partial`：`stage` 与 `delivery.status` 均为 `partial`，仅 `best_effort`，delivered 与 missing 都非空，名称与 manifest 明确标为 partial；
- `failed`：`stage` 与 `delivery.status` 均为 `failed`，delivered 为空，无 PPTX；
- omitted pages 保持 dirty，失败原件和 counters 不变；
- complete／partial 与 `PASS|GENERATED_UNVERIFIED|BLOCKED|FAILED_VERIFICATION` 等验证状态分别报告。

用户明确需要 PPTX 或原生可编辑内容时，才把 final `complete|partial` delivery 交给 `ppt-editable`；prepared 不可导出，partial 使用独立 partial artifact 与 manifest，不能覆盖完整产物。SVG 生产和 QA 不自动启动 PowerPoint、WPS 或 Office。

**节点完成：** delivery evidence 全部 hash-bound，报告列出 ordered delivered/missing、完整度、QA 能力与 Office 状态，没有把 partial 或未验证产物表述成完整 PASS。

## Durable 恢复优先级

audit 通过后，恢复按以下 owner precedence 执行。它保证重放确定性，不意味着一个普通页面失败停止其他页面：

| order | durable owner | action |
|---:|---|---|
| 1 | `pending_interaction` | 验证／消费同一问题与已保存决定；pending 时等待 |
| 2 | `manuscript_review.pending_round` | 恢复同一 cycle/round/snapshot；幂等提交已有匹配报告 |
| 3 | global `visual_generation_blocker` | 处理共享阻断；页面局部失败不进入此 owner |
| 4 | schema-v1 `visual_generation_transaction` | 执行零模型调用迁移；不跨过它新建 transaction |
| 5 | `active_visual_generation_batch` | 从 manifest 与 per-slide transactions 重建 cursor，继续、settle partial/failed 或完成 promotion |
| 6 | stage scan | 前五类均不存在后寻找首个未完成／dirty work |

pointer-before-files、hash mismatch 或第三方 owner 变更 fail closed。files 完整而 pointer 缺失只做 pointer-last completion。orphan candidate 不等于有效结果；previous final 始终保留，直到同页 candidate 在 CAS 下成功提升。

## Guided 检查点

- `brief`：关键简报决定解决后请求批准；
- `outline`：展示论点与证明顺序后请求批准；
- `anchor`：展示所选代表页及真实 render evidence 后请求批准。

等待期间顶层 stage 保持当前位置。`pending` 只接受明确回答；`answered` 使用保存的规范化决定幂等提交。推荐、沉默和叙述性暂停均不是批准。

## 宿主与并发边界

新批次或新 dispatch epoch 前按[宿主适配器](host-isolation-adapters.md)重新协商。Claude SDK／legacy 的选择、隔离与工具限制、task-binding 顺序、完整 receipt identity 和独立 adapter-upgrade 边界只以该 ceremony 为准。

DeepSeek Harness 分支按[普通 subagent 与 managed dashboard 协议](deepseek-harness.md)执行；该文件拥有 fresh-context、继承工具的 prompt policy、durable child 绑定、发现接口和持久面板生命周期。

并发宽度由 runtime 响应与真实 worker capacity 决定；capacity 0 是 WAIT。页面 validation 可与 sibling generation 并发，final promotion、visible global blocker、batch settlement 和 pointer mutation 按 original order 确定执行。无论并发数多少，锚点／正式页生成和 SVG QA 都不启动 Office。
