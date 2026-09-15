# 生产 QA、页面局部恢复与交付

生成锚点、正式页面、修复页面或执行整套 QA 前读取本参考。用户决策和批准按[交互协议](interaction-protocol.md)；durable mutation 只由[固定运行时](runtime-canonical-owners.md)执行。模型负责识别缺陷、选择布局和判断修复是否真实改善，不能手写 attempts、transaction、manifest、hash、pointer、CAS 或 delivery。

## 进入条件

视觉工作要求：

- `run.json.manuscript_review.state == manuscript_approved`；
- 当前 outline、storyboard、review snapshot、theme 和适用 visual revisions 有效；
- `theme -> anchor -> production -> qa` 的阶段顺序成立；
- artifact audit、source/import gate 和宿主 adapter preflight 均通过。

并发宽度由 runtime 与真实 worker capacity 决定。generation 与 sibling 的 per-page QA 可以重叠；coordinator 独占 enrichment、candidate、transaction、final 和 delivery 写入。promotion、terminal manifest 与 pointer mutation 按 original `ordered_slide_ids` 确定执行，而不是 completion order。

## 页面局部与全局失败

| scope | reason / condition | required result |
|---|---|---|
| page-local | `generator_refused`、`generator_timeout`、`generator_output_malformed` | 保留同页失败 transaction，仍有预算时按 runtime action 重试；不影响 independent siblings |
| page-local | `svg_contract_failed`、`fact_source_mismatch`、`visual_qa_failed` | 拒绝该 candidate；在真实预算内局部修复／recompose，或按 policy 结算该页 |
| global | shared owner/snapshot/path/firewall integrity | 全局停止写入并保持现场 |
| global | CAS/pointer/state conflict | 保留 previous final 与所有 transaction，先解决同一冲突 |
| global | unsafe、unknown 或 unavailable host adapter；permission/source-import gate | 不 dispatch，不以 best-effort／skip 绕过 |

页面局部失败不创建 deck-wide blocker，也不反复中断用户。一个页面 exhausted 只结束该页当前生产路径；independent sibling／后续页继续。strict 仍允许继续这些页面，只是不授权 partial final。共享 blocker 才停止整套生产。

失败 transaction 的原始 bytes、reason、candidate evidence 与 `generation_attempt` 是审计事实：不能改成 PASS、归零 counter、换 ID 建“新生命周期”或采用 orphan candidate。previous final 始终保留到同页 valid candidate 在 CAS 下成功提升。

## 单页检查

页面只有所有 applicable hard checks 通过，并具有当前 candidate digest 对应的真实非 Office render evidence，才可 `validated`／promoted 并进入 delivered partition。

### XML 与静态安全

- UTF-8 XML 可解析；root canvas 精确符合[SVG 契约](svg-contract.md)；
- 元素和属性落在 Office-safe allowlist，禁止特性不得进入候选；
- 无 DTD／entity、script、事件处理器、远程资源、data URL、CSS、动画、外部／绝对路径；
- ID 唯一，本地引用闭合，XML 转义正确；
- 文字用显式 `<tspan>` 行，字体大小可确定；
- 存在 `<title>` 与 `<desc>`。

任何实际 XML、安全或 unsupported SVG feature 失败都是该页 hard failure。

### 内容与来源覆盖

逐项对照批准 storyboard 与当前 visual projection：

- assertion title、audience takeaway、role 与叙事顺序保持；
- 每个 required content block 都有唯一对应；
- 数字、单位、期间、标签、限定、因果、比较基准与来源映射不变；
- 实质内容均来自当前已批准素材；新增事实须先更新内容 owner 并重新通过审查，无事实过渡句可自由表达；
- canonical `SRC-[0-9]+` 仅存在于 `data-source-id`／trace 机器元数据，任何大小写变体都不得成为可见文本；
- 页面不显示内部 ID、URL、来源说明或 citation。用户要求 visible citation 时，在生成前走交互协议选择机器 trace 或单独来源报告。

`fact_source_consistency` 与 `narrative_integrity` 允许措辞提纯、重排和视觉化，不允许改变内容底线。批准内容本身若需改事实、主张、限定或来源，失效并正式重审；generator 漏写／误写只拒绝该页输出，不重置有效内容批准。

### 几何与可读性

硬检查：

- 每个非背景元素的**实际解析 geometry** 在 64 px safe area 内，文字预留下降部；
- 标题、正文、脚注均满足 minimum font size；
- 真实 render 不出现裁切、非预期重叠、不可读对比、连接线穿字或错误关系；
- 正文、页脚与页码均检查溢出、遮挡、对比度和对齐，不因文字较小或属于装饰而豁免；
- user hard constraints 与 strict brand rules 满足；
- path `A/a` 用真实椭圆弧极值检查；超出浮点稳定范围 fail closed。

文本行宽估算 `Σ(字符系数 × font-size) <= 可用宽 × 0.88` 是**保守 warning**。超出该 margin 表示必须检查真实 render、字体 metrics、换行和容器，不是已发生 clipping 的证明，也不能单独作为 geometry hard failure。反之，估算通过也不能覆盖真实裁切。实际 safe-bound 越界、minimum font failure、解析 geometry overflow 或 render-confirmed clipping 仍然阻断该页。

### 视觉层级与判断

真实 render 至少检查：

1. 3 秒内是否能识别唯一主结论／主对象；
2. 第一、第二、第三阅读位置是否由面积、位置、字号、对比和连接明确区分；
3. 主信息是否显著支配次信息，是否退化为等权卡片墙；
4. 标题、命题、区块标题、正文、辅助文字、微标签的字体阶梯；
5. 品牌色、事实色、风险色、行动色等语义角色是否稳定；
6. card 是否表达真实分组／层级；
7. 假设页是否区分观察、替代解释、验证问题和可证伪条件；
8. 连续修复是否形成 alignment drift、例外令牌或阅读路径债务。

每个失败项写成可定位、可复验的 defect，并判断 local repair 还是 recompose。多个局部问题共同改变焦点、层级或阅读路径时必须 recompose。

只有真实渲染完成时才记录 `visual_qa: rendered` 及对应 digest、renderer 和检查结果。无 render 能力时记录 `visual_qa: not_rendered` 和原因。该记录不能冒充 `rendered`／PASS，也不能进入最终 delivered partition；可以让该页保持失败／dirty，并在 best-effort 下作为 missing 明确披露。

## 修订分类

编辑视觉产物前先唯一分类：

- **local repair**：只修一个可测量 defect，例如碰撞、已确认溢出、对齐、连接线、token 或不改变含义的 typo；保持 layout family、焦点、层级、事实和来源。
- **recompose**：焦点、层级、阅读路径、layout family、密度、嵌套、字体系统、语义色、品牌方向或视觉参考发生变化，或 local repair 已形成视觉债务。
- **content re-entry**：事实、主张、限定、来源、大纲、content blocks、叙事或受众行动变化；返回内容 owner 并正式重审。

style-only 变更写 `theme.json` 或 `projection: runtime_visual`，不重写 content-owned brief/storyboard。失败页仅调整 `layout_family`／`visual_intent` 时使用 runtime 返回的 `revise-visual` 路径；它在内存投影，保持五份内容 owner、review evidence、sibling 和 previous final。recompose 接收完整 frozen prompt，不接收旧 SVG 作为底稿。

## 真实三次 dispatch 预算

每页从 initial generation 开始拥有一个 inherited lifetime budget：**最多三次真实 generator dispatch**。retry、recompose、runtime visual repair、fallback 或 replacement transaction 共享该计数；任何实际模型调用都计一次。

- 每个 dispatch 是单轮：完整 prompt in，恰好一个 SVG text response out。
- DSH 向同一 bound child 取回其已完成原答案属于 replay，不是新生成；再次 spawn 才计新 dispatch。
- deterministic local repair 只有在 `advance` 返回该动作且仍有预算时可执行；它不创建新的模型调用别名，也不重置 counter。
- 历史 four-request／two-patch evidence 只为旧 owner replay 可读，不授权当前页面第四次调用。
- remaining attempts 为 0 时 runtime 不再返回 retry／recompose／fallback。原 transaction 保持 `failed`，页面进入 `attempts_exhausted` 候选 omission；不制造“恢复准备中”。

coordinator 使用 runtime 返回的 page attempt／remaining count 进行用户可见报告，不自行推导或递增。预算耗尽后 ordinary page failure 不自动问用户；只有内容／业务取舍、visible citation、policy 变化或无法安全默认的全局决定才创建一个 pending interaction。

## Candidate、QA 与 promotion

生成 reply 先由 coordinator 验证恰好一个 `xml` fence。裸 SVG 必须从 `<svg` 开始、以 `</svg>` 结束。source enrichment 在任何 candidate write/hash 前完成：每个 canonical `block_id` 只在唯一语义 `<g data-block-id>` 临时回显一次；runtime 以冻结 `block_id -> ordered source_ids` 注入 nested machine metadata，移除临时属性并扫描 text、tail 和所有属性。任何未知、遗漏、重复或泄漏是 `fact_source_mismatch`，candidate writes 为 0。

绑定任务的原始 host response 是 task／dispatch 原始证据；经 coordinator 提取、来源增强、移除临时 `data-block-id` 与确定性序列化后形成的 candidate bytes 是 coordinator 产物，不能描述为未经改动的 generator 输出。

candidate 原子写入、关闭、复读后才记录 digest。只有 digest 匹配的 `candidate_written` 可验证；orphan candidate never adopted。validation object 的必需 check 为 XML、Office-safe subset、geometry/text、fact/source、narrative、visual。`checks.office` 仅表示静态 Office-safe SVG subset，不表示 PowerPoint 实测。

某页 validation 可在 sibling 仍生成时完成。通过页无需等待所有 batch pages 都 PASS：到达 deterministic ordered promotion slot 后即可 CAS promote。提升前用当前校验器重验 `validated` candidate；历史 PASS 失效时，固定 runtime 通过自校验 journal 保留原 transaction bytes 与 QA record，将该页转换为普通页面失败，并继续提升健康 sibling。该转换不删除候选、不重置 attempt，也不能吞掉 candidate hash、final CAS、owner/snapshot 等全局冲突。失败页保留 immutable transaction；后续 independent slot 继续。batch 最终为：

- `completed`：所有 slots promoted；
- `partial`：至少一个 promoted、至少一个 authorized omitted；
- `failed`：无 promoted slot。

terminal `partial|failed` manifest 必须按 original slot 密封 `omitted_transaction_refs` 与 `omitted_transaction_sha256`。omitted page 保持 dirty。

## 整套 QA 与 delivery

逐页结果 settled 后，对**将被 delivered 的页面**执行整套 QA并写 `.ppt-pilot/质量检查报告.md`。报告同时审计原始 target partition，不能因 missing pages 而缩短 targets。

检查：

- delivered sequence 的核心论点、证明顺序、限定和收束；
- 每个结论的 evidence/source support；
- 节奏、密度、尺度、强调和相邻布局重复是否有语义理由；
- typography、spacing、semantic color、machine source metadata 和 IDs；
- previous/next links 与实际 delivered sequence，以及 omission 对叙事的明确影响；
- manuscript review 无 unresolved `BLOCKER|HIGH`；
- 每个 delivered ID 恰好一个 current formal SVG，digest 与 per-page QA 和真实 render evidence 一致；
- 每个 missing ID 恰好一个 unchanged failed transaction／explicit skip 和 terminal manifest seal。

QA 报告至少记录 run/deck ID、能力限制、target/delivered/missing IDs、逐页 checks 与真实渲染证据（render evidence）、实际 dispatch count、修复记录、整套 findings、unresolved failures 和 verification verdict。源码检查、candidate existence 或 dashboard 状态不能替代 render evidence。

任何 `prepared|complete|partial|failed` 显式交付结算都先重新验证 `run.json.manuscript_review.state == manuscript_approved` 且当前批准快照仍有效。不满足时拒绝结算并保持原 owner；该门复用现有审查证据，不给 delivery 增加字段。

固定 runtime 先可在 `run.stage: qa` 建立 `run.delivery.status: prepared` 供 QA 绑定；prepared 不可导出。QA report 写入后调用 `finalize`，并把 delivery 与顶层终态原子同步：

- `complete`：`stage: complete`，delivered 按 original order 等于 targets，missing 为空；
- `partial`：`stage: partial`，仅 `best_effort`，delivered 与 missing 都非空；
- `failed`：`stage: failed`，delivered 为空，不生成 PPTX；
- strict 有未解决页时不创建缺页交付分区，也不转 partial；只有在合法解决问题或用户显式 `advance --allow-partial` 持久化 policy 后，才继续对应结算。

final complete／partial 的 `storyboard_sha256`、`theme_sha256`、`quality_report_sha256`、每个 delivered `slide_sha256` 与每个 missing transaction evidence 都必须匹配当前 bytes。delivered 和 missing 互斥、穷尽并保持 original target order。partial 名称和 manifest 明确标识 partial，不能覆盖 full artifact。完整度与验证状态分别报告。

## SVG 渲染与 Office 边界

anchor、production、repair 和 QA 只使用 XML／静态 SVG 检查及浏览器或其他非 Office renderer。它们不启动 PowerPoint、WPS，不逐页临时建 PPTX，不运行 COM probe，也不以已安装 Office 为由改变流程。

Office 只在两个明确分支出现：

1. 外部旧稿 intake 为读取／核对源稿，在用户权限和 source hash 绑定下按[旧稿导入](source-deck-redesign.md)执行；
2. 用户明确要求 PPTX、可编辑原生形状／文本或 Office 验证，且 delivery 已是 final `complete|partial`，再进入 `ppt-editable` 或用户选择的独立交付工具。

`ppt-editable` 的 `PASS|GENERATED_UNVERIFIED|BLOCKED|FAILED_VERIFICATION` 不由 SVG QA 推断。用户只要 SVG 时明确说明未执行 Office 实测；这不把 verified SVG 自动变成 Office PASS。

## Resume

恢复先调用高层 `advance`。runtime 按 durable precedence 处理：pending interaction → pending review → global visual blocker → v1 migration → active batch → stage scan。这个顺序防止 split-brain，不把 page-local failed transaction 升格为 global blocker。

active batch 从 manifest 和每页 transaction 重建 cursor。valid promoted siblings 保留；failed 页按 inherited attempts 返回唯一可执行 action 或 exhausted outcome；terminal omission evidence 已存在时 byte-identical replay。状态或 hash 冲突时全局 fail closed，不新建 recovery deck、不复制 runtime、不手写 owner。
