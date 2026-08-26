# 生产 QA、恢复与修订契约

生产阻断、恢复中的待回答问题和修订分类歧义遵循[用户交互与确认协议](interaction-protocol.md)。硬检查及确定性回退仍由本文件定义，用户不能豁免无效交付。

## 进入条件与生产顺序

生成锚点或正式页面前必须读取本参考。每个视觉阶段都要求 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，同时具有有效且已批准的故事板和审查产物。顶层阶段依次经过 `theme`、`anchor` 并进入 `production` 后才能生产，而且必须已有验证通过的 `theme.json`。

正式页面按每批 3–4 页生产，但每次只写入并验证一个 SVG。同一批次内，允许把已编译完成的多个 generation prompt 并发派发给多个 fresh generator；每个 SVG 的提取、硬检查与 promotion 仍然逐页串行提交，页与页之间不共享候选状态。每页通过硬检查后，只记录该页检查结果；不得立即从 `dirty_slides` 清除其 ID。只有 promoted transaction 的 final SVG、页面 QA 和整套演示 QA 都通过后，才能在移除对应 `visual_generation_transaction` 的同一次原子 `run.json` 替换中清除该页 dirty 状态。每完成一个持久阶段和一个批次，都更新 `run.json`，使另一个宿主无需对话历史即可恢复运行。

某页耗尽修复与回退策略后仍有硬检查失败时，不得继续生成后续页面。

## 单页硬检查

所有适用检查通过前，页面不能标记为有效。

### XML 与安全

- 能解析为 UTF-8 XML；
- `width`、`height` 与 `viewBox` 精确正确；
- 只使用允许的 SVG 元素；
- 不含禁止特性、远程资源、脚本、事件处理器、DTD／实体、CSS、动画、data URL 或绝对路径；
- ID 唯一，本地引用有效；
- XML 转义正确；
- 字号明确，并使用 `<tspan>` 显式换行；
- 存在 `<title>` 与 `<desc>`。

任何 XML 或安全失败都会阻断。

### 内容与来源覆盖

把 SVG 与其已批准故事板记录逐项比较：

- 结论标题和受众要点都已呈现；
- 每个必需内容块均已表示；
- 数字、单位、期间、标签、限定条件和来源 ID 一致；
- 图表尺度与比较基准忠实于证据；
- 设计过程中没有新增缺少支持的文案；
- 来源说明可读且不与正文碰撞。

重要主张缺失或变化属于硬失败，必须使文稿批准失效，不能只做视觉修补。

### 几何与可读性

检查源文件几何：

- 每个非背景元素都在 64 px 安全区域 `x=64..1216`、`y=64..656` 内，包括页脚／来源文字和页码；放置文字时预留下降部，不把下边界直接当作基线；
- 不存在潜在文字溢出或裁切；无法实际渲染时，必须按 [SVG 契约](svg-contract.md) 的行宽估算公式对每个可见行复核；
- 文字、标签、形状、连接线和来源之间没有非预期重叠；
- 与最终主题相比具有足够对比度；
- 对齐、间距、卡片尺寸和令牌使用一致；
- 标题／正文／脚注不低于字号下限；
- 连接线不穿过标签，也不暗示错误关系。

发现文字溢出、内容重叠、对比度不可读或关键元素超出画布时，按硬失败处理。

## 视觉 QA 状态

宿主能够准确渲染 SVG 时，必须检查实际渲染结果，并记录 `visual_qa: rendered`、渲染方法、具体渲染证据（rendering evidence，例如截图路径或渲染产物）及发现的问题。源文件检查、XML 解析或声称已修复都不能替代视觉检查，也不能标记为 `rendered`。

实际渲染检查至少回答：

- **3 秒焦点识别**：第一次看到页面时能否在 3 秒内识别唯一主结论或主对象；
- **扫描顺序**：第一、第二、第三阅读位置是否与 brief 的 `reading_order` 一致；
- **主次支配**：主要信息是否通过面积、位置、字号、对比或 brief 指定的替代编码明确强于次要信息；
- **字体阶梯**：标题、主命题、区块标题、正文、辅助文字和微标签是否具有可辨别且一致的层级；
- **语义色**：事实、证据边界、风险／试点、行动等颜色角色是否稳定，是否避免把品牌色用于所有对象；
- **卡片语义**：卡片是否真正表达分组或层级，而不是形成等权卡片墙；
- **假设页证据边界**：观察、替代解释、验证问题与可证伪条件是否可区分，是否避免把假设视觉化成定论；
- **视觉债务**：连续局部修补是否已造成对齐漂移、层级削弱、例外令牌增多或不一致的阅读路径。

每个未通过项必须记录可定位、可验证的具体问题，并分类为 `patch`、`recompose` 或事实／来源重入；不得只写“继续优化”“更美观”等无法执行的说明。多个局部问题共同改变焦点、层级或阅读路径时按 `recompose`，不能拆成一串 patch 规避重构。

渲染不可用时，记录 `visual_qa: not_rendered` 及原因。只完成 XML／源文件检查时，不得声称页面“看起来正确”。结构硬检查仍须执行，交付时必须披露缺少视觉验证。

## 视觉修订分类与输入

编辑任何视觉产物前，先把请求唯一分类为 `patch`、`recompose` 或事实／来源重入，并更新对应 visual brief：

- `patch` 只适用于保持已接受构图的可测量局部 defect：碰撞、溢出、令牌不一致、小范围对齐位移、连接线错误或不改变事实的错字。它不能改变焦点、层级、阅读路径、布局家族、卡片密度、嵌套、字体系统、语义色、品牌方向或视觉参考。
- `recompose` 对以下变化是强制的：焦点、层级、阅读路径、布局家族、卡片密度、嵌套、字体系统、语义色、品牌方向、新视觉参考、“重新优化／更高级”等广泛要求，或者反复 patch 已形成视觉债务。
- 事实、主张、来源、大纲或故事板变化不属于任一视觉模式，必须使文稿批准失效并返回规范性上游阶段。

生成输入精确为：

```text
patch = complete brief + current SVG + one exact defect
recompose = complete brief + locked storyboard + active theme
```

`patch` 必须在 brief 中写明唯一 `patch_defect`，并且只把受影响页面 SVG 与 QA 标脏。`recompose` 必须重新组装受影响页面 brief，并从空白构图重建 SVG；旧 SVG 不得作为几何底稿、坐标参考、卡片骨架或复制起点，只能在新候选完成后用于核对锁定内容和来源一致性。模式无法唯一判断时，持久化一个直接澄清问题并停止。

### 页面首次生成与 recompose 的统一 Prompt QA

每个首次生成和任何 `recompose` 都必须使用[页面首次生成与重新排版专用 Prompt 契约](redesign-prompt.md)，不能直接把 visual brief 交给同一创作上下文生成：

- 验证 `.ppt-pilot/generation-prompts/<slide-id>.md` 的 `prompt_snapshot_id`、brief 快照和视觉修订 ID；
- 风格 prompt 解析／编译失败时写入 `run.json.visual_generation_blocker`，只保存安全 Skill 相对 `resource` 或 `none`；保持 `stage`、`mode`、`interaction_history` 和 dirty slide，不启动 generator、不写 SVG、不改用其他风格、不降级为 patch；
- fresh 独立生成上下文只接收该 Prompt；首次生成不接收其他页面，重新排版还不得接收旧 SVG 或创作对话；
- 生成回复必须恰好一个 `xml` 代码围栏；提取后裸内容从 `<svg` 开始并以 `</svg>` 结束；不得把代码围栏写入工作区 SVG；
- 圆角卡片拒绝 `rect[rx]`／`rect[ry]`，必须检查 `path` 与 `A` 圆弧；普通直角 `rect` 仍允许；
- 每个可见行一个独立 `text`，每个 `text` 一个简单 `tspan`；拒绝 nested tspan、混合 run 和自动换行；
- 除浏览器／宿主渲染外，条件允许时执行实际 PowerPoint 插入、保存、重开与导出；未执行或失败时必须披露，不能声称 PowerPoint 通过。

## 生成 transaction、失败 consumer 与 QA 边界

页面首次生成与 `recompose` 的 QA 只能消费 promoted transaction：`visual_generation_transaction` 的 full schema 和状态图以 [artifact-contract.md](artifact-contract.md) 为准，QA 层不得把 `candidate_written` 或 `validated` 当作交付成功。`candidate_sha256` 在候选写入、关闭、复读后才存在；promotion 前的任何 orphan candidate never adopted，previous final SVG 必须保留。dirty_slides 只在 promoted transaction 的 final、页面 QA 和整套 QA 都通过后清除。

失败 consumer 固定：transport retry reasons `generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch` 只能显式 resume 为同一 transaction 的 `failed -> generating`，`generation_attempt + 1`，每次宿主调用最多 generator 1 次；同一 transaction 的 `generation_attempt` 达到 `3` 后不得再次 resume 为 `generating`，改为持久化 production blocker 并停止，等待用户决定。QA reasons `svg_contract_failed`、`locked_content_mismatch`、`visual_qa_failed` 必须先持久化精确 defect，再进入 patch 或 deterministic fallback 的 new compiling transaction。`final_promotion_conflict` 与 `transaction_state_conflict` 是 production `blocker`：final 和 failed transaction 都保持不变；用户解决后 unchanged valid candidate 走 `failed -> validated` 并重试 promotion，authoritative inputs changed 走 `failed transaction -> new compiling transaction`。No arbitrary delete/cancel。

## 修复与确定性回退

每次全新生成或 `recompose` 都创建新的候选版本，并把该候选的 `fix_attempts_for_candidate` 重置为 `0`。此前探索或旧候选的修复次数和视觉债务记录保留在历史中，但不能让新候选直接进入回退。

一个候选最多允许两次硬失败 `patch`：

1. 在不改变已批准主张和已接受构图的情况下，修复一个具体的溢出、重叠、对比度、对齐、连接线或契约问题；
2. 如仍有另一个局部硬失败，修复该唯一 defect，同时保留内容、布局家族、层级和最低字号。

每次 patch 后重新执行所有受影响硬检查和适用的渲染检查。修复请求一旦需要改变构图层级，停止累计 patch，改为 `recompose` 并重置新候选次数。候选的两次 patch 仍未通过时，确定性降级为简单单栏（single-column）或双栏（two-column）布局，并保留相同结论、证据、来源 ID 与主题令牌；把回退结果作为新 SVG 验证。回退仍有硬检查失败时，停止生产并把该页记录为阻断；不得作为完整产物交付。

## 请求预算与派发可观测

generator 交互是严格单轮的：一次请求提交完整输入，一次响应返回恰好一个围栏；禁止与生成上下文多轮往返（追问、确认、迭代修改）。"反复优化"只允许通过上面的离散阶梯表达，每个阶梯都是一次全新的单轮调用。

每个候选的宿主请求上限固定为 **4 次**：首次生成／`recompose` 1 次 + `patch` ≤2 次 + 确定性回退 1 次（transport retry 计入同一 transaction 的 `generation_attempt`，不额外占用该预算）。用尽即停：写 blocker 或按阻断记录，不得静默开启第 5 次请求，也不得通过"新周期""换个说法重试"绕过计数。

每次调用 generator 前必须向用户输出一行派发说明，使请求消耗全程可见：

```text
[<deck-id>] 第 N 次请求 slide=S03 mode=patch attempt=2/2 transaction=e4282f23… 原因=微事实字号低于下限
```

其中 N 是本页累计请求序号，mode 取 `initial`／`patch`／`recompose`／`fallback`，attempt 显示当前候选内 patch 或 transport 重试进度，原因引用已持久化的 defect／reason。缺少这行说明的调用属于违规；用户随时可以依据它判断"在干什么、还剩几次"。上游修订（故事板／大纲失效重审）导致的重新生成按新候选重新计数，但派发说明必须注明触发它的修订来源。

## 整套演示 QA

每页单独通过后，执行整套演示 QA，并写入 `.ppt-pilot/质量检查报告.md`：

- 叙事：核心论点、证明顺序、反方观点、影响与收束保持连贯；
- 结论／证据映射：每个重要结论有支持，限定条件没有丢失；
- 节奏：密度、尺度和强调有意变化，不出现突兀风格漂移；
- 布局多样性：相邻重复必须有语义理由；
- 对齐与令牌：字体、间距、颜色、来源处理和 ID 一致；
- 转场：上一页／下一页链接与实际序列一致；
- 文稿质量门：不存在未解决的 `BLOCKER` 或 `HIGH` 问题；
- 文件集合：`slides/` 中每个故事板页面恰有一个最终 SVG，不包含非 SVG 交付物。

整套内容不一致会使受影响的文稿阶段失效；纯视觉不一致只把受影响页面与整套 QA 标记为脏。

## QA 报告记录内容

QA 报告统一写入 `.ppt-pilot/质量检查报告.md`，记录：

- 运行 ID 与演示文稿 ID；
- 验证时间和能力限制；
- 每页的结构、内容、来源、几何与视觉 QA 状态；
- 修复次数和使用的回退；
- 整套问题与解决情况；
- 尚未解决的硬失败；
- 最终结果：`PASS`、`BLOCKED` 或 `PASS_WITH_VISUAL_QA_NOT_RENDERED`。

只有不存在未解决硬失败的结果，才能把 `run.json.stage` 推进到 `complete`。

## 生产阻断

正常生产批次不提出问题。每页两次修复和 single-column／two-column 确定性回退都失败后，如果继续需要删除已批准内容、改变主张、牺牲来源可读性或选择不同交付兼容策略，先写入一个 `kind: blocker` 的 `pending_interaction` 并提出一个生产阻断问题。问题必须说明不能继续的具体硬失败和推荐的安全路径。

如果唯一剩余方案仍违反 XML、安全、来源忠实度、最低字号、边界或其他 SVG 硬检查，则停止并记录 `BLOCKED`；不得把无效 SVG 作为用户可以批准的选项。需要改变主张或来源时先使文稿批准失效，返回相应阶段。

## 恢复（`resume`）

`resume` 入口必须先读取 `run.json` 并保留既有 `run.json.mode`。在验证其他阶段字段或寻找第一个未完成阶段前，按全局顺序处理 durable control state：

1. `pending_interaction`：`pending` 原样重发并停止；`status: answered` 使用已保存的 answer／decision 幂等提交；存在时不得处理其他 durable state。
2. `manuscript_review.pending_round`：没有 pending interaction 时恢复相同 cycle／round／snapshot 的审查。若匹配的完整报告已 durable，验证后只追加一次 history，并在一次原子 `run.json` 替换中删除 pending；重复 resume 为 no-op。报告不存在时复用同一 pending round，不重复计数。
3. `visual_generation_blocker`：只有没有更高优先级状态时处理；仍失败则刷新并停止。
4. `visual_generation_transaction`：只有没有 pending 与 blocker 时处理；按 transaction 契约恢复，不做 stage scan。
5. stage scan：前四者都不存在时，才验证普通阶段字段并寻找第一个未完成或脏阶段。

恢复时按每轮 `review_mode` 验证互斥 execution evidence：subagent round 必须有非空且 child/result 一致的宿主 delegation evidence；inline fallback round 必须有合法 fallback evidence、冻结快照和隔离限制，且不能含 delegation evidence。任一模式证据缺失或格式错误时使批准失效；下一轮仍先尝试独立审查，失败则在当前步骤 inline 审查。只有两种方式都不能执行时才设置 `review_unavailable`。绝不能根据无效 evidence 的批准恢复视觉阶段。

运行目录使用固定中文文件名，存放于 `.ppt-pilot/`：`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md`、`文稿审查.md` 和 `质量检查报告.md`。

找到第一个未完成或脏阶段。复用有效且已批准的上游产物；不能仅仅因为更换宿主或对话就重新计算已批准的上游工作。状态声称某产物已完成但文件缺失或格式错误时，把该阶段标脏，并且只使其依赖项失效。

顶层位于 `manuscript_approved` 检查点的运行直接进入主题／锚点工作，不重复简报、研究、大纲、故事板或审查。进入这些阶段后，顶层 `stage` 正常前进，而 `manuscript_review.state: manuscript_approved` 持续作为视觉授权护栏。阻断或不可用的审查状态绝不能恢复到视觉设计。

## 修订（`revise`）

编辑前先分类请求。修改类别无法唯一判断时，先提出一个直接问题，确认是否允许改变事实主张、限定条件或来源映射；记录答案后再更新失效状态。

- **局部修补（patch；visual-only／non-factual copy edit 的受限子集）**：仅处理一个可测量局部 defect。保持页面 brief 的构图与层级，只把受影响页面 SVG 和整套 QA 标脏；不重新运行文稿审查。
- **页面重构（recompose）**：已批准文案、限定条件、数字、来源映射和受众行动不变，但焦点、层级、阅读路径、布局、卡片密度、字体、语义色、品牌方向或参考发生变化。重新组装该页 brief，只把该页 brief、SVG 和整套 QA 标脏；不重新运行文稿审查，且不以旧 SVG 为几何底稿。
- **主题变化（theme change）**：记录 deck 级视觉修订并把全部 visual brief、依赖主题的锚点、所有页面及视觉／整套 QA 标脏；文案和含义不变时保留文稿批准。
- **事实、主张、来源、大纲或故事板变化**：不归入 patch 或 recompose。按产物契约返回最早受影响文稿阶段；把嵌套审查授权重置为 pending，保留历史并使视觉产物失效。此前状态为 `manuscript_approved` 才能开启新 cycle；尚未通过的周期保留计数。新的正式 subagent／inline 审查通过前不得回到视觉阶段。

非事实性文案修正只有在可证明不改变主张、限定条件、数字、来源映射和受众行动时才能作为 patch；如果文案修改可能改变含义、置信度、范围、因果、比较、建议或来源对齐，应按主张变化处理。不得滥用“non-factual copy edit”例外绕过审查。

重新生成前，在 `run.json` 中原子更新权威视觉修订、`dirty_slides` 与审查状态。验证成功后，只清除已经证明为当前版本的产物。
