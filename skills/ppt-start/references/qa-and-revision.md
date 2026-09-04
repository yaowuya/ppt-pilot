# 生产 QA、恢复与修订契约

生产阻断、恢复中的待回答问题和修订分类歧义遵循[用户交互与确认协议](interaction-protocol.md)。硬检查及确定性回退仍由本文件定义，用户不能豁免无效交付。

## 进入条件与生产顺序

生成锚点或正式页面前必须读取本参考。每个视觉阶段都要求 `run.json.manuscript_review.state` 精确为 `manuscript_approved`，同时具有有效且已批准的故事板和审查产物。顶层阶段依次经过 `theme`、`anchor` 并进入 `production` 后才能生产，而且必须已有验证通过的 `theme.json`。

正式页面默认 `batch_width: 4`（可配置 3）。批内所有页面先完成内存 preflight 与能力协商，随后 pointer-last 写 per-slide transactions／manifest／active pointer；没有 fresh isolation 时保持零 prompt／transaction／candidate 写入。generation 与 per-slide validation 可重叠，但 coordinator 独占 candidate/transaction/final 写入，并按 `ordered_slide_ids` 串行 promotion 与最低 blocker publication。页面只有在 transaction promoted、页面 QA 与整套 QA 都通过后才从 `dirty_slides` 清除。每完成一个批次都更新可恢复状态，使另一个宿主无需对话历史即可继续。

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
- 来源说明可读且不与正文碰撞；
- 内部 `SRC-<digits>` 只保留在 `data-source-id`／trace 机器元数据中；可见 `<text>`／`<tspan>` 出现该模式时以 `fact_source_mismatch` 硬失败，不能删除文字或改用栅格回退；
- 只有用户明确请求时才允许显示人类可读的来源名称或 URL，且可见文字必须省略内部 ID。

重要主张缺失或变化属于硬失败，必须使文稿批准失效，不能只做视觉修补。

### 检查项契约

QA 以冻结故事板为事实基准，不要求逐字拷贝；阅读顺序预设已由视觉层级检查取代：

| 检查项 | 契约 |
|---|---|
| `fact_source_consistency` | 数字/单位/期间/限定词/因果/来源映射与冻结故事板一致；措辞自由 |
| `narrative_integrity` | assertion_title / role / audience_takeaway / visual_intent 保留；SCQA 顺序完好 |
| `visual_hierarchy` | 主次可辨：主信息面积/字号/明暗显著强于次信息；等权卡片墙视为失败 |
| `supplement_traceability` | 素材外新增的实质内容必须能在研究.md/来源.md 中溯源；无事实内容的过渡句豁免 |

`fact_source_consistency` 与 `narrative_integrity` 取代旧的逐字内容保真检查；措辞可以提纯、改写或重排，但事实底线与叙事边界不可破。`visual_hierarchy` 取代旧的固定阅读顺序检查，主次支配与扫描顺序以视觉层级达成。

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
- **扫描顺序**：视觉层级决定阅读路径：第一、第二、第三阅读位置由主次信息显著区分，主信息在面积、位置、字号或对比上明确强于次信息，等权卡片墙视为失败；
- **主次支配**：主要信息是否通过面积、位置、字号、对比或替代编码明确强于次要信息；等权卡片墙视为失败；
- **字体阶梯**：标题、主命题、区块标题、正文、辅助文字和微标签是否具有可辨别且一致的层级；
- **语义色**：事实、证据边界、风险／试点、行动等颜色角色是否稳定，是否避免把品牌色用于所有对象；
- **卡片语义**：卡片是否真正表达分组或层级，而不是形成等权卡片墙；
- **假设页证据边界**：观察、替代解释、验证问题与可证伪条件是否可区分，是否避免把假设视觉化成定论；
- **视觉债务**：连续局部修补是否已造成对齐漂移、层级削弱、例外令牌增多或不一致的阅读路径。

每个未通过项必须记录可定位、可验证的具体问题，并分类为 `patch`、`recompose` 或事实／来源重入；不得只写“继续优化”“更美观”等无法执行的说明。多个局部问题共同改变焦点、层级或阅读路径时按 `recompose`，不能拆成一串 patch 规避重构。

渲染不可用时，记录 `visual_qa: not_rendered` 及原因。只完成 XML／源文件检查时，不得声称页面“看起来正确”。结构硬检查仍须执行，交付时必须披露缺少视觉验证。

## 视觉修订分类与输入

编辑任何视觉产物前，先把请求唯一分类为 `patch`、`recompose` 或事实／来源重入，并把已应用修订投影到其权威 owner：故事板拥有叙事、显示素材、事实、主张、限定词与来源映射，`theme.json` 拥有风格身份与软风格基线。

- `patch` 只适用于保持已接受构图的可测量局部 defect：碰撞、溢出、令牌不一致、小范围对齐位移、连接线错误或不改变事实的错字。它不能改变焦点、层级、阅读路径、布局家族、卡片密度、嵌套、字体系统、语义色、品牌方向或视觉参考。
- `recompose` 对以下变化是强制的：焦点、层级、阅读路径、布局家族、卡片密度、嵌套、字体系统、语义色、品牌方向、新视觉参考、“重新优化／更高级”等广泛要求，或者反复 patch 已形成视觉债务。
- 事实、主张、来源、大纲或故事板变化不属于任一视觉模式，必须使文稿批准失效并返回规范性上游阶段。

组装与派发输入精确为：

```text
direct-compile projection = approved storyboard + theme.json + applicable applied visual revisions
patch = complete direct-compile inputs + 当前 SVG + one exact defect
initial/recompose generator = durable generation prompt only
```

`patch` 必须读取完整直接编译输入、当前 SVG 与一个精确 `patch_defect`；只修复该 defect，并把受影响页面 SVG 与 QA 标脏。`recompose` 必须先把已应用修订投影回故事板或 `theme.json` 的相应所有权，再从这两个权威 owner 重新编译持久化 Prompt 并从空白构图生成候选。旧 SVG 不得提供给 `recompose` 生成上下文，也不得作为几何底稿、坐标参考、卡片骨架或复制起点。模式无法唯一判断时，持久化一个直接澄清问题并停止。

### 页面首次生成与 recompose 的统一 Prompt QA

每个首次生成和任何 `recompose` 都必须使用[页面首次生成与重新排版专用 Prompt 契约](redesign-prompt.md)。QA 必须先验证固定生产顺序：读取已批准 outline／storyboard／theme 与适用 revisions → 按 `theme.selected_style_id` 解析 style-owned `files.prompt_template`，未声明时采用 repository fallback → 向唯一 whole-line `{{NARRATIVE}}` 注点投影叙事／素材并完成确定性 preflight → 能力协商 → 按页持久化并复读 schema-v2 transaction/prompt → 写 batch manifest → pointer-last 激活 → prompt-by-value isolated dispatch → coordinator 写 candidate／hash → per-slide QA → validated → ordered serial promotion。`tokens.json.prompt_baseline` 只参与风格数据、QA 与 snapshot provenance，不是第二个 prompt 正文注入域。

确定性 preflight 失败必须产生零 transaction 写入、零 prompt 写入、零 generator 调用和零 SVG 写入。该失败不得留下半 transaction、半成品 prompt 或可采用 candidate；canonical blocker 只能在没有为本次尝试创建 transaction/prompt 后独立写入。

随后检查：

- 验证 `.ppt-pilot/generation-prompts/<slide-id>.md` 的 `prompt_snapshot_id`、`storyboard_snapshot_id`、`theme_snapshot_id` 与已应用视觉修订 ID；
- 风格身份／资产或 authoritative outline／storyboard／theme 验证失败时返回对应 owner；只有当前解析出的 style-owned generation prompt 模板（或未声明模板时的 repository fallback）／字节或无法唯一解释的 snapshot／provenance 自身失败，才按产物契约独立写入 `run.json.visual_generation_blocker`，只保存安全 Skill 相对 `resource` 或 `none`；保持 `stage`、`mode`、`interaction_history` 和 dirty slide，不启动 generator、不写 prompt/SVG、不改用其他风格、不降级为 patch；
- 对每个候选重新检查冻结故事板的 `fact_source_consistency` 与 `narrative_integrity`，并检查 `theme.json` 的软风格基线；
- fresh 独立生成上下文只接收该持久化 Prompt；首次生成不接收其他页面，`recompose` 还不得接收旧 SVG 或创作对话；
- 生成回复必须恰好一个 `xml` 代码围栏；提取后裸内容从 `<svg` 开始并以 `</svg>` 结束；不得把代码围栏写入工作区 SVG；
- 圆角卡片拒绝 `rect[rx]`／`rect[ry]`，必须检查 `path` 与 `A` 圆弧；普通直角 `rect` 仍允许；
- 每个可见行一个独立 `text`，每个 `text` 一个简单 `tspan`；拒绝 nested tspan、混合 run 和自动换行；
- 除浏览器／宿主渲染外，条件允许时执行实际 PowerPoint 插入、保存、重开与导出；未执行或失败时必须披露，不能声称 PowerPoint 通过。

## 生成 transaction、失败 consumer 与 QA 边界

页面首次生成与 `recompose` 的 QA 只消费 per-slide schema-v2 transaction；manifest 不复制或授权页面 state。`candidate_written` 与 `validated` 都不是交付成功，只有 transaction 的 final CAS 提升为 `promoted`，且页面／整套 QA 通过后才能清除 dirty slide。`candidate_sha256` 在候选写入、关闭、复读后才存在；promotion 前的任何 orphan candidate never adopted，previous final SVG 必须保留。

同一批次的 generator 与各页 XML/source/narrative/render/visual validation 可以重叠：某页 QA 可在 sibling 仍生成时运行。但只有 coordinator 能提交该页 `validation`、发布 visible blocker 或替换 final；promotion、blocker publication 与 `run.json` pointer 改变必须按 `ordered_slide_ids` 串行确定，不能按 completion order。隔离任务与 callback 对工作区零写入。

每页 transaction 的 `validation` 精确为：

```json
{
  "state": "pending|running|passed|failed",
  "checks": {
    "xml": "pending|passed|failed",
    "office": "pending|passed|failed",
    "geometry_text": "pending|passed|failed",
    "fact_source": "pending|passed|failed",
    "narrative": "pending|passed|failed",
    "visual": "pending|passed|failed|not_rendered"
  }
}
```

只有 coordinator 可原子提交该对象；任一 required check failed 时 state 必须 failed。`not_rendered` 只允许 visual check 使用且必须披露，不能冒充视觉通过。

每页 QA 的 `qa` span 记录真实 monotonic duration 与其 model/render parent；promotion span 按 manifest 顺序串行连接。telemetry 只用于比较 compile/model/render/QA/promotion、queue 与 batch wall/critical path；它是非权威诊断。span 写入／解析失败记录 `telemetry_diagnostic_failed`，但保持当前 `validation` 与 transaction correctness outcome，不得改写 passed/failed、blocker 或 final。

失败 consumer 固定：`prompt_write_failed` 只来自 prompt 原子 temp+rename、复读或 hash 验证失败，失败前及恢复至 `compiled` 前 generator calls、candidate writes 与 SVG writes 均为 0。transport retry reasons `generator_unavailable`、`generator_refused`、`generator_timeout`、`generator_output_malformed`、`candidate_write_failed`、`candidate_hash_mismatch` 只更新对应 per-slide transaction，使用 `generation_attempt + 1`；同一 transaction 的 `generation_attempt` 达到 `3` 后持久化 blocker 并停止。新 schema-v2 QA reasons 使用 `svg_contract_failed`、`fact_source_mismatch`、`visual_qa_failed`；`locked_content_mismatch` 只允许原样保留在 migration batch。`final_promotion_conflict` 与 `transaction_state_conflict` 保留 previous final 与 failed transaction。No arbitrary delete/cancel。

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

## 生成完毕后的下一步：转可编辑 PowerPoint

整套演示 QA 通过、`run.json.stage` 达到 `complete` 后，必须向用户提示下一步可把本次运行交付为**可编辑 PowerPoint**：

- 引导调用 `ppt-editable` 技能，把 `slides/<slide-id>.svg` 转成带原生可编辑形状／可编辑文本／保留 SVG 分组的 `delivery/editable/<deck-id>-editable.pptx`；
- 只在用户明确需要 PowerPoint（可编辑原生形状、可编辑文本、保留 SVG 分组、Office 渲染验证）时调用；用户只要 SVG 时不强行转换；
- 不越过 `ppt-editable` 自身的门禁与结果状态（`PASS`／`GENERATED_UNVERIFIED`／`BLOCKED`／`FAILED_VERIFICATION`），本阶段只在完成时引导用户。

## 生产阻断

正常生产批次不提出问题。每页两次修复和 single-column／two-column 确定性回退都失败后，如果继续需要删除已批准内容、改变主张、牺牲来源可读性或选择不同交付兼容策略，先写入一个 `kind: blocker` 的 `pending_interaction` 并提出一个生产阻断问题。问题必须说明不能继续的具体硬失败和推荐的安全路径。

如果唯一剩余方案仍违反 XML、安全、来源忠实度、最低字号、边界或其他 SVG 硬检查，则停止并记录 `BLOCKED`；不得把无效 SVG 作为用户可以批准的选项。需要改变主张或来源时先使文稿批准失效，返回相应阶段。

## 恢复（`resume`）

`resume` 入口必须先读取 `run.json` 并保留既有 `run.json.mode`。在验证其他阶段字段或寻找第一个未完成阶段前，按全局顺序处理 durable control state：

1. `pending_interaction`：`pending` 原样重发并停止；`status: answered` 使用已保存的 answer／decision 幂等提交；存在时不得处理其他 durable state。
2. `manuscript_review.pending_round`：没有 pending interaction 时恢复相同 cycle／round／snapshot 的审查。若匹配的完整报告已 durable，验证后只追加一次 history，并在一次原子 `run.json` 替换中删除 pending；重复 resume 为 no-op。报告不存在时复用同一 pending round，不重复计数。
3. `visual_generation_blocker`：只有没有更高优先级状态时处理；仍失败则刷新并停止。
4. `active_visual_generation_batch`：只有没有 pending 与 blocker 时处理；验证 pointer/manifest/transactions，从 per-slide state 恢复，不做 stage scan。schema-v1 singular transaction 先零模型调用迁移。
5. stage scan：前四者都不存在时，才验证普通阶段字段并寻找第一个未完成或脏阶段。

恢复时按每轮 `review_mode` 验证互斥 execution evidence：subagent round 必须有非空且 child/result 一致的宿主 delegation evidence；inline fallback round 必须有合法 fallback evidence、冻结快照和隔离限制，且不能含 delegation evidence。任一模式证据缺失或格式错误时使批准失效；下一轮仍先尝试独立审查，失败则在当前步骤 inline 审查。只有两种方式都不能执行时才设置 `review_unavailable`。绝不能根据无效 evidence 的批准恢复视觉阶段。

活动路径固定为：运行根目录 `大纲.md`，以及 `.ppt-pilot/简报.md`、`.ppt-pilot/研究.md`、`.ppt-pilot/来源.md`、`.ppt-pilot/故事板.md`、`.ppt-pilot/文稿审查.md`、`.ppt-pilot/质量检查报告.md` 六个内部中文文件；`.ppt-pilot/大纲.md` 不得作为活动读取或写入路径。`resume` 必须从运行根目录 `大纲.md` 读取并验证 `outline_snapshot_id`；`outline_snapshot_id` 的读取与计算来源始终是运行根目录 `大纲.md`，再由故事板和下游 provenance 原样携带。

`resume`／`revise` 对既有旧英文运行必须原位读取并使用 `brief.md`、`research.md`、`sources.md`、`outline.md`、`storyboard.md` 及已有 `manuscript-review.md`。不得仅因文件名为英文而拒绝运行、重命名文件、复制或迁移文件，或重算／重建已批准上游产物；不得混用中英文两套路径。兼容性不豁免状态校验：文件缺失、内容无效、stale／过期或 dirty／脏状态仍必须阻断，并按正常依赖失效规则处理。

找到第一个未完成或脏阶段。复用有效且已批准的上游产物；不能仅仅因为更换宿主或对话就重新计算已批准的上游工作。状态声称某产物已完成但文件缺失或格式错误时，把该阶段标脏，并且只使其依赖项失效。

顶层位于 `manuscript_approved` 检查点的运行直接进入主题／锚点工作，不重复简报、研究、大纲、故事板或审查。进入这些阶段后，顶层 `stage` 正常前进，而 `manuscript_review.state: manuscript_approved` 持续作为视觉授权护栏。阻断或不可用的审查状态绝不能恢复到视觉设计。

## 修订（`revise`）

编辑前先分类请求。修改类别无法唯一判断时，先提出一个直接问题，确认是否允许改变事实主张、限定条件或来源映射；记录答案后再更新失效状态。

- **局部修补（patch；visual-only／non-factual copy edit 的受限子集）**：仅处理一个可测量局部 defect。保持冻结故事板的事实／叙事／来源与当前 SVG 的已接受构图，只把受影响页面 SVG 和整套 QA 标脏；不重新运行文稿审查。
- **页面重构（recompose）**：已批准文案、限定条件、数字、来源映射和受众行动不变，但焦点、层级、阅读路径、布局、卡片密度、字体、语义色、品牌方向或参考发生变化。记录页级视觉修订，把其内容或风格变化投影到故事板或 `theme.json` 的权威字段，重新编译该页 `generation-prompts/<slide-id>.md`，并只把该 prompt、SVG 和整套 QA 标脏；不重新运行文稿审查，且不把旧 SVG 提供给生成上下文。
- **主题变化（theme change）**：记录 deck 级视觉修订并更新 `theme.json` 的软风格基线；把全部依赖主题的 generation prompts、锚点、页面及视觉／整套 QA 标脏，文案和含义不变时保留文稿批准。
- **事实、主张、来源、大纲或故事板变化**：不归入 patch 或 recompose。按产物契约返回最早受影响文稿阶段；把嵌套审查授权重置为 pending，保留历史并使视觉产物失效。此前状态为 `manuscript_approved` 才能开启新 cycle；尚未通过的周期保留计数。新的正式 subagent／inline 审查通过前不得回到视觉阶段。

非事实性文案修正只有在可证明不改变主张、限定条件、数字、来源映射和受众行动时才能作为 patch；如果文案修改可能改变含义、置信度、范围、因果、比较、建议或来源对齐，应按主张变化处理。不得滥用“non-factual copy edit”例外绕过审查。

重新生成前，在 `run.json` 中原子更新权威视觉修订、`dirty_slides` 与审查状态。验证成功后，只清除已经证明为当前版本的产物。
