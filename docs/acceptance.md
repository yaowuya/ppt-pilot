# 跨宿主验收

本文档给出标准 `skills/ppt-start/` 与 `skills/ppt-editable/` 在 Claude Code、OpenAI Codex 与 DeepSeek Harness 中的可重复验收矩阵。自动一致性测试验证书面契约，但不能代替真实宿主、浏览器、PowerPoint 或 FY26H1 集成证据。

未执行的项目一律保持 `PENDING`。只有记录运行日期、精确宿主版本和证据路径后，才能更新结果；没有可检查证据就不能标为通过。当前活动架构是**故事板 + `theme.json` 直接编译**：每个可选择 `style_pack` 都必须由 manifest `files.prompt_template` 声明并携带经过 tokens 精确绑定验证的 style-owned 完整模板；字段缺失立即 fail closed。运行时固定执行 manifest → tokens → guidance → prompt traversal；所有模板 hard prefix/suffix 字节相同，只有 Step 2 的七条 closed typed 风格指令由同包 tokens 确定性变化。仓库 `generation-prompt-template.md` 仅是建包 authoring seed，运行时不可执行。模板只有一个 whole-line `{{NARRATIVE}}` 注点，编译器只注入已批准、逐块带稳定 `block_id` 且不含来源注解的叙事／素材，持久格式为 `creative-brief-v1`。generator 仅可把每个 `block_id` 临时回显一次于规范 `data-block-id` 精确属性值；text／tail／其他属性泄漏以 `fact_source_mismatch` 零 candidate write 阻断。`tokens.json.prompt_baseline` 只作为闭合类型风格数据、QA 与 snapshot provenance，不是第二个正文注入域。早期 legacy `[[CANONICAL_NARRATIVE_BULLETS]]`／`[[STYLE_BASELINE]]` 双 marker 协议已废弃，新运行必须拒绝。新运行使用 schema-v2 per-slide transaction/batch manifest 与 `active_visual_generation_batch`，默认 width 4 isolated generation、per-slide validation 并发、coordinator ordered serial publication。Canway manifest 版本为 `1.3.0`。历史 visual briefs 与 singular v1 transaction 只作 inert migration evidence。

## 前置条件

1. 把未经修改的 `skills/ppt-start/` 与 `skills/ppt-editable/` 完整复制或链接到待测宿主的已记录发现路径；每个源/安装树分别记录文件数和摘要。
2. 每个场景都从干净工作区开始。不得把运行产物写入已安装 Skill 或宿主配置目录。
3. 执行 `source-driven.md` 前，把仓库中的 `tests/inputs/` 复制到干净工作区的 `inputs/`。这些文件明确标注为合成验收样例，绝不能描述成真实研究或客户数据。
4. 执行 `resume-after-review.md` 前，创建 `ppt-output/resume-approved/`，把 `tests/fixtures/run-review-approved.json` 复制为其中的 `run.json`，再把 `tests/fixtures/resume-approved/` 的六个文件复制到同一目录，并把 `tests/inputs/` 复制到工作区的 `inputs/`。这是专门验证只读恢复能力的**旧英文运行兼容夹具**，所有文件名与内容必须保持不变，接收宿主不得自动重命名或迁移。
5. 执行 `resume-pending-interaction.md` 前，创建 `ppt-output/pending-outline-approval/`，把 `tests/fixtures/run-pending-interaction.json` 复制为其中的 `run.json`，并准备与其 `outline` 阶段匹配的已批准简报、研究、来源和当前大纲。接收宿主必须先处理同一个待回答问题，不得创建新问题或重做上游工作。
6. 执行 `revise-single-slide.md` 前，准备三个相互独立、完整且已通过的 source-driven 合成运行副本。patch、recompose 和 factual change 三个分支分别在不同副本中执行，避免一条分支污染另一条分支的起始状态。
7. 保存完整 `ppt-output/<deck-id>/` 和宿主 transcript／日志作为**本地证据**，但不得提交运行时产物。版本库只保留可复现提示、人工整理的 Markdown 评估／索引和必要的验收自动化脚本；运行工作区、原始 transcript、last-message、截图、PPTX 和 JSON／TXT 诊断由 `.gitignore` 排除。
8. 验证审稿独立性时，保存宿主返回的子上下文 ID、完成事件 ID、匹配的结果来源上下文 ID 及审稿人受限输入。审稿人只能接收五个冻结文稿文件和审查规范。只有文字叙述，或没有子上下文／接收者状态的空等待，均视为失败，不构成来源证据。`run.json` 单独存在不是证据；每个声明的 ID 都必须与宿主 transcript 或协作日志关联。
9. 跨宿主交接时，不得向接收宿主提供发起宿主的对话。
10. 实时网络或渲染不可用时，应保留运行中明确的降级状态，不能将其解释为通过。

## 共用场景矩阵

每个提示都要分别在 Claude Code 与 Codex 中运行。预期契约完全相同，只有 Skill 发现路径和显式启动命令不同。

| 提示 | 目的 | 必须观察的行为 | 预期终止状态／产物 |
|---|---|---|---|
| [`guided-topic-only.md`](../tests/prompts/guided-topic-only.md) | 验证缺省 guided、主题规范化与三个检查点。 | 模式未显式指定时默认 `guided`；先检查已有输入；一次只提出一个实质性问题；简报、大纲和锚点都提出直接问题并等待明确回答。 | 每个问题等待期间保持当前阶段且不得推进下游；批准完成后才进入下一阶段。 |
| [`source-driven.md`](../tests/prompts/source-driven.md) | 验证 auto 安全默认值、用户资料优先、来源元数据和主张映射。 | `auto` 不提出可选问题；用户资料优先；网络／机密行为仍受用户权限约束；`研究.md`、`来源.md`、大纲和故事板保持稳定来源 ID 与限定。 | 只有每个 `BLOCKER`／`HIGH` 问题都为 `RESOLVED` 才能进入视觉阶段。 |
| [`review-blocker.md`](../tests/prompts/review-blocker.md) | 使用人为植入的无支持统计值验证严格文稿质量门。 | 正式 subagent／inline 报告把无支持主张记录为未解决的 `HIGH` 问题，并由 `run.json` 把该 ID 写入阻断列表。 | `manuscript_blocked`；不得生成 `theme.json`、`samples/`，也不得生成 SVG。 |
| inline fallback（宿主场景） | 验证子 Agent 不可用时当前步骤直接审查。 | 先尝试委派并保存失败原因；不空等、不询问；持久化 `pending_round` 和 `fallback_evidence`；当前上下文只依据冻结五文件审查，并声明“当前上下文降级审查，不具备独立上下文隔离”。 | inline PASS 可进入 `manuscript_approved`；inline BLOCK 继续阻断；真实宿主结果在台账中保持 `PENDING` 直到执行。 |
| [`resume-after-review.md`](../tests/prompts/resume-after-review.md) | 从已批准样例恢复，不重复上游工作。 | 从 [`run-review-approved.json`](../tests/fixtures/run-review-approved.json) 开始；先读 `run.json`；保留已批准文稿；没有失效时不重复研究或审查。 | 推进到 `theme` 与 `anchor`，嵌套审查状态仍为 `manuscript_approved`。 |
| [`resume-pending-interaction.md`](../tests/prompts/resume-pending-interaction.md) | 验证待回答、已回答和请求修订状态跨轮次／跨宿主恢复。 | 从 [`run-pending-interaction.json`](../tests/fixtures/run-pending-interaction.json) 开始；先读 `run.json`；重发同一个直接问题及完整效果／推荐理由；收到明确回答后先写 `status: answered`、原始 `answer` 和规范化 `decision`。 | 回答前不得推进下游；产物幂等写入后，以一次原子状态替换完成阶段更新和交互对象删除／替换，不重复上游工作。 |
| [`revise-single-slide.md`](../tests/prompts/revise-single-slide.md) | 验证 patch、recompose 与事实变更的三个独立分支。 | 分支 A 的 24 px 对齐和非事实错字分类为 patch，只读取完整 direct-compile inputs、当前 SVG 与精确 defect；分支 B 的焦点、卡片密度和视觉参考变化分类为 recompose，把修订投影回故事板／theme，重编该页 prompt 且不以旧 SVG 为几何底稿；分支 C 的数字／来源变化不属于视觉模式，使文稿批准和全部依赖视觉产物失效。 | patch 只标脏 S05 SVG 与 QA；recompose 只标脏 S05 prompt／transaction／SVG 与 QA；factual change 只有新的正式 subagent／inline 审查通过后才能重新生成视觉内容。 |

静态套件还解析 [`interaction-transition-cases.json`](../tests/fixtures/interaction-transition-cases.json)、[`workspace-run-selection.json`](../tests/fixtures/workspace-run-selection.json)、[`run-outline-reapproval.json`](../tests/fixtures/run-outline-reapproval.json) 和 [`review-cycle-reset.json`](../tests/fixtures/review-cycle-reset.json)，验证 `answered` 崩溃恢复、三个批准阶段映射、修订澄清替换、再次批准历史不覆盖、锚点上游修订重入、歧义目标路由及第 3 轮批准后的新审查周期。夹具只证明书面状态契约内部一致，不替代下面的真实宿主 transcript 验收。

## 快速视觉机制验证

本次机制改造要求本地契约测试与 SVG 静态检查验证：故事板/theme direct projection、必需且无运行时 fallback 的 style-owned `files.prompt_template`、唯一 whole-line `{{NARRATIVE}}` 注入和 byte-exact envelope、schema-v2 per-slide transaction/batch manifest、pointer-last、host capability、prompt-by-value isolation、并发 generation/validation、ordered publication，以及 Office-safe SVG。

本次不把未执行的 Claude Code／Codex 现场运行、完整生成页面浏览器视觉检查或 Microsoft PowerPoint 行描述成通过。历史验收台账保持原状态；WPS `wpp.exe` 不等同于 Microsoft `POWERPNT.EXE`，只能产生明确降级证据。

静态验证还检查：

- storyboard + `theme.json` 只向解析模板的唯一 whole-line `{{NARRATIVE}}` 注点投影已批准叙事／素材，并拒绝来源注解；`tokens.json.prompt_baseline` 只参与风格数据、QA 与 snapshot provenance，format 精确为 `creative-brief-v1`；
- style resolver 必须按 manifest → tokens → guidance → prompt 的 no-follow traversal 执行，前序资产失败不得触碰后序资产；每个 manifest 必须恰好声明 tokens、guidance、prompt 三个固定目标；
- 每份 style-owned prompt 的 hard prefix/suffix 必须字节一致，只有 Step 2 七条 closed typed 行可随 tokens 改变，且整份 prompt 必须与同包 tokens 的确定性合成结果精确相等；
- 每个 `block_id` 只能临时出现一次于规范 `<g data-block-id>` 精确属性值，禁止进入 text／tail／其他属性名值；任何泄漏以 `fact_source_mismatch` 在 candidate write/hash 前失败且 candidate writes 为 0；
- deterministic preflight 与 fresh-isolation capability negotiation 在任何 prompt／transaction／candidate write 前完成；
- active `visual_generation_blocker` 修复且 preflight 成功后，必须先原子移除 blocker、原样保留可能存在的 schema-v1 owner并重新进入全局顺序；不得跨过 v1 零模型迁移创建新 transaction；
- transaction→manifest→`run.json.active_visual_generation_batch` pointer-last，manifest 不复制页面 state，cursor 不能授权；
- native/remote isolated task 只收完整 `prompt_by_value`、fresh history、filesystem none、tools none；无 fresh isolation 零生产写入，缺 concurrency/lookup 降为 width 1，非 Git 不降级；
- generator 与 per-slide validation 可重叠；coordinator 按 `ordered_slide_ids` 串行 promotion，并只发布最低 visible blocker；
- `assets/styles/registry.json` 与 `canway-midyear-review` manifest/tokens/STYLE 的抽象边界，manifest 版本 `1.3.0`；
- 内部 `SRC-<digits>` 不得成为可见文字，机器 `data-source-id` 必须保留；显式人类 citation 可显示名称／URL 但省略内部 ID；
- telemetry critical path 使用 DAG max、batch wall 使用真实跨度，损坏只记 `telemetry_diagnostic_failed`。

### schema-v2 并发性能 telemetry 验收

并发 telemetry 只属于 `EVIDENCE_CLASS: DIAGNOSTIC`，不能授权 transaction、validation 或 promotion。静态 fixture 必须证明：串行 4×1000 ms model 基线约为 4400 ms critical path；并发 width 4 为一个约 1000 ms model wave 加串行 promotion（1400 ms）；width 3 的 8 页为 `ceil(8/3)` model waves 加串行 promotion（3400 ms）；out-of-order QA 使用 DAG 最长依赖链而不是 span 总和；恢复重放同一 `span_id` 只计一次；telemetry corrupt 只记录 `telemetry_diagnostic_failed`，原 correctness outcome 不变。真实宿主验收还必须记录 host、provider、model、isolation、attribution/task IDs、queue、timeout、token（可用时）与 batch wall time。

每个场景至少检查：

- `run.json` 的顶层阶段、嵌套审查 cycle／状态／历史／可选 `pending_round`、脏页面和可选 `pending_interaction`／`interaction_history`；目标不唯一时还检查工作区 `run-selection.json`；
- 五个冻结文稿文件；
- 当前运行实际使用的审查报告：新运行检查 `文稿审查.md`，旧英文运行检查 `manuscript-review.md`，并核对审稿来源；
- 视觉产物是否只在正确质量门后出现；
- 每个待生成／修订页面是否先有 byte-exact generation prompt、per-slide transaction 与 batch manifest，`run.json` 是否只发布 `active_visual_generation_batch`，修订是否只投影一次；
- 当前运行实际使用的 QA 报告：新运行检查 `质量检查报告.md`，旧英文运行检查 `qa-report.md`，包括真实的 `visual_qa` 状态；
- 独立 SVG 结构和运行目录内容。

### 证据类别与命令边界

本轮验收必须按证据类别记录，不得互相冒充：

- `static package`：本地测试和文件检查只证明包结构、书面契约和 fixture oracle，并验证 direct compile、单一活动 prompt template、schema-v2 per-slide transactions／batch manifest、host capability、ordered publication 与文档一致；测试中的 resolver／hash oracle 不是运行时代码，也不能证明宿主 Agent 会按这些规则执行。
- `EVIDENCE_CLASS: DIAGNOSTIC`：诊断压力提示（例如 style isolation、registry identity-recovery、style blocker）只暴露风险或辅助复测，不得作为 Claude Code、Codex、fresh generator、浏览器或 PowerPoint 验收通过依据。
- `deployment hash`：只证明部署的 `skills/ppt-start/` 与仓库源一致；`ppt-editable` 也必须以独立 per-Skill 摘要证明其安装树与 `skills/ppt-editable/` 一致。它不证明运行行为，且任何 `*.bak-*` 都必须位于 `skills/` 扫描根之外。
- `real host`：只有记录真实宿主版本、启动命令、transcript／协作日志、运行目录和必要截图／PPTX 的证据，才能更新当前 Claude Code、Codex、fresh、浏览器或 PowerPoint 行。

Task 10 聚焦 GREEN 命令固定为：

```bash
python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v
```

完整本地命令固定为：

```bash
python -m unittest discover -s tests -v
```

这些命令的通过只能更新 `static package` 结论；真实宿主、浏览器和 PowerPoint 行仍按下方结果台账单独执行。

### 交互行为证据

交互通过必须同时具有 transcript 和对应的 `run.json`／阶段产物，不能只检查最终文件：

1. 新运行未显式指定执行策略时，`run.json.mode` 为 `guided`；`resume`／`revise` 作为入口动作保留既有 `run.json.mode`。宿主先检查请求和工作区，已经给出的主题、受众、目的和页数不再询问。
2. 每轮一次只提出一个实质性问题。有限选择包含 2–4 个互斥选项、逐项效果、推荐值和推荐理由；推荐不是确认，持久状态足以让另一个宿主原样重放。
3. 简报、大纲和锚点检查点包含一个直接问题，并在明确回答前实际停止。首次阻塞问题也必须先建立不冲突的运行目录并持久化。等待期间 `pending_interaction.status` 为 `pending`，顶层阶段不变，且不得推进下游或创建受阻产物。
4. 收到有限选择回答时，先在原阶段保存 `status: answered`、非空原始 `answer` 与属于 `options` 的规范化 `decision`；按交互 ID 幂等写入产物镜像后，以单次原子 `run.json` 替换同时提交权威 `interaction_history`、目标阶段与对象删除／替换。恢复 `answered` 状态不得重复问题或重复记录。
5. `approve` 必须严格映射为 `brief -> research`、`outline -> storyboard`、`anchor -> production`；可选 `approved` 只能在同一提交中作为镜像。修订后的再次批准必须递增 `approval_attempt` 并使用新历史键，不能覆盖修订事件。
6. `request_revision` 在范围未分类或等待澄清时保持原阶段；权威记录保存在 `run.json.interaction_history`，阶段产物只保留可重建镜像，持久 `clarification_index` 决定替换问题 ID。上游范围确定后按最早受影响阶段重入，并把文稿授权重置为 pending。不得从 `anchor` 绕过新独立审查。
7. 显式 `auto` 使用安全默认值并跳过可选问题；但网络传输、机密披露等用户权限，或确实没有安全默认值的业务决策，仍然只提出一个阻塞问题。
8. `resume` 必须先处理既有待回答问题；问题 ID、正文、选项、逐项效果和推荐理由与原记录一致，不得重做已批准上游工作。
9. 目标运行不唯一时，`ppt-output/run-selection.json` 必须同时保存候选、`entry_action` 与完整本地 `operation_payload`，然后才提出一个选择问题；任何候选运行都不得因路由而被修改，answered 路由状态恢复时不得重复提问或丢失原始修订请求。
10. 已在第 3 轮通过的版本以后发生实质修订时，cycle 加一、round 归零且历史完整保留；未通过或 `manuscript_blocked` 的周期不得借修订开启新周期。

只有描述“已暂停”但 transcript 中没有问题和真实停止，或者宿主采用推荐项后继续执行，均判为失败。

## 宿主执行

### Claude Code

安装两个 Skill 到 `~/.claude/skills/<skill-id>/` 或 `.claude/skills/<skill-id>/`。分别使用 `/ppt-start` 与 `/ppt-editable` 显式启动；后者必须以一个完成运行为输入。记录精确 Claude Code 版本、发现证据与行为证据。

### Codex

安装两个 Skill 到 `$HOME/.agents/skills/<skill-id>/` 或 `.agents/skills/<skill-id>/`。分别使用 `$ppt-start` 与 `$ppt-editable`；记录精确 Codex 版本、发现证据与行为证据。

### DeepSeek Harness

一个 `ppt-pilot` 插件的 `skills/` 下同时安装 `ppt-start` 与 `ppt-editable`；使用启动词 `ppt-start`、`ppt-editable`。记录精确 harness 名称/版本、两个 Skill 的发现证据，以及 `ppt-start` 的审稿委派/降级证据。

宿主专属调用语法只允许出现在安装与验收文档中；共享 `SKILL.md` 必须保持宿主中立。

## 跨宿主交接

交接只使用持久运行目录。不得粘贴第一个宿主的对话，也不得悄然重新生成已批准上游产物。

### Claude Code -> Codex

1. 在 Claude Code 中执行资料驱动场景，推进到临时 `manuscript_approved` 检查点，并在创建主题前停止。
2. 核对 `run.json.manuscript_review.state` 为 `manuscript_approved`、审查历史指向全新审稿人，并且五文件快照完整。
3. 用 Codex 打开同一工作区，请求从该运行目录恢复。
4. 核对 Codex 先读 `run.json`，不重复简报／研究／大纲／故事板／审查，继续主题和锚点，并保留批准来源。
5. 完成生产与 QA，保存两个宿主的 transcript 和最终运行目录。

### Codex -> Claude Code

反向重复同一流程：Codex 创作并推进到 `manuscript_approved`，Claude Code 恢复视觉生产。接收宿主必须保留来源审查历史，不得依赖发起宿主对话。

### 双向严格质量门交接

两个方向都要交接一份最新正式报告仍含未解决 `HIGH` 问题的运行，并在接收宿主中尝试 `resume`。预期仍为 `manuscript_blocked`：不得生成 `theme.json`、样例 SVG 或最终 SVG。接收宿主如果把 `ACCEPTED_RISK`、缺失问题、无 evidence 的随手自审或伪装成独立的 inline 审查当作批准，即为失败。

## 委派不可用与 inline fallback 场景

每个宿主都要在独立委派被禁用或确实不可用时运行一次。

当前预期行为：

- 先尝试委派并保存可归因失败原因；不得空等待或伪造 child／completion／result IDs；
- 设置 `manuscript_review.mode: inline_fallback`，持久化相同 cycle／round／冻结快照的 `pending_round`；
- 当前步骤执行同一七维审查，报告记录 `fallback_evidence` 和“当前上下文降级审查，不具备独立上下文隔离”；
- inline PASS 可以提交 `manuscript_approved`，inline BLOCK 使用同一 `BLOCKER/HIGH` 规则继续阻断；
- subagent 与 inline round 共同计入每 cycle 三轮上限；
- 只有冻结输入不可读、inline 也无法执行或状态冲突不可恢复时，才使用 legacy-compatible `review_unavailable`。

既有 `review_unavailable` 台账行保留为历史旧行为证据，不能证明当前 fallback。当前 Claude Code／Codex inline fallback 场景在真实运行前保持 `PENDING`。

## SVG 浏览器检查

对内置示例和代表性生成页面执行：

1. 在当前浏览器中直接打开 SVG，并记录浏览器名称／版本；
2. 确认画布为 16:9，标题和正文全部可见，没有裁切或意外换行；内部 source ID、人类可读来源名称、URL 与 citation 均不得成为可见文字，可见引用请求必须在生成前阻断并改选机器 trace 或单独来源报告；
3. 确认没有远程资源缺失、控制台资源错误、重叠、不安全元素或超出安全区域的内容；
4. 如果生成演示文稿包含这些页面，至少检查一个低密度结论页、一个高密度数据／流程页，以及一个来源可追溯页面；后者只允许 canonical `data-source-id="SRC-<digits>"`／trace 机器元数据，不允许可见引用；
5. 把截图或录屏保存到证据路径。

只做 XML 源文件检查而没有实际渲染，不能记录为视觉批准。

## 受支持的 PowerPoint 检查

使用支持 SVG 导入的 PowerPoint 桌面版本，并记录产品渠道、完整 build、操作系统和测试日期。

1. 使用 PowerPoint 的图片／SVG 插入流程，插入内置示例及相同的代表性生成 SVG；
2. 确认每页比例正确，文字、几何、引用或会改变含义的颜色均未丢失；
3. 关闭并重新打开演示文稿，确认导入图形仍然存在；
4. 记录字体替换、裁切、分组、转换或可编辑性限制；
5. 把测试 PPTX 与截图保存到证据路径。

导入通过只证明已测试的静态 SVG 路径，不代表其他 PowerPoint 版本／平台普遍兼容，也不代表所有元素都可编辑。

## ppt-editable 独立行为验收

对同一完成运行分别验证：

1. 无 PowerPoint/Pillow 时只生成 `GENERATED_UNVERIFIED` 和独立 unverified 文件名；
2. 支持子集生成原生 `p:sp`/`p:grpSp`、可编辑文本、备注与 trace `descr`，没有图片 fallback；
3. unsupported SVG、可见 `SRC-<digits>`、结构/Office/视觉失败阻断新 final，并保留 previous PASS；
4. PowerPoint 正常化、重开、递归计数和四路 render 全部通过后才可 `PASS`；
5. FY26H1 参考运行的页面/owner/leaf/group/notes/视觉 gate 与无可见内部来源 ID 验收通过；
6. 三宿主分别能发现并启动 `ppt-editable`，安装树摘要与仓库源一致。

这些行为必须把 `static package`、`deployment hash`、`real host` 与 PowerPoint/reference integration 证据分开记录。

## 结果台账

每次实际执行新增一行，不覆盖既有证据。日期使用 `YYYY-MM-DD`，版本必须精确，不能只写“最新”。

> 2026-08-19 的宿主行为证据使用旧 Skill 标识 `ppt-pilot` 和当时的英文指令生成。它们保留为历史行为证据，不能证明重命名、中文化后的 `ppt-start` 在当前宿主中可发现或表现相同。浏览器 SVG 证据仍适用于未改变的 SVG 资产；当前宿主调用场景必须使用新命令重新执行后才能形成新的当前通过结论。

| 场景 | 方向／宿主 | 运行日期 | 宿主版本 | 结果 | 证据路径 |
|---|---|---|---|---|---|
| 仅主题 guided | Claude Code | — | — | PENDING | — |
| 资料驱动 | Claude Code | — | — | PENDING | — |
| 审查阻断（历史旧标识） | Claude Code | 2026-08-19 | Claude Code 2.1.223 | NOT RUN — 嵌套 CLI 认证不可用 | [`claude-attempt.md`](../acceptance-evidence/2026-08-19/host-runs/claude-blocker/claude-attempt.md) |
| 审查后恢复 | Claude Code | — | — | PENDING | — |
| 待回答恢复 | Claude Code | — | — | PENDING | — |
| 单页修订 | Claude Code | — | — | PENDING | — |
| 文稿 inline fallback | Claude Code | — | — | PENDING | — |
| schema-v2 isolated generation | Claude Code | — | — | PENDING | — |
| 仅主题 guided | Codex | — | — | PENDING | — |
| 资料驱动 | Codex | — | — | PENDING | — |
| 审查阻断（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1 | FAIL — 空等待并虚构子上下文／结果来源 | [`codex-blocker-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-blocker-v3/codex-blocker-v3-evaluation.md) |
| 审查后恢复（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1 | PASS — 从合成批准样例生成并渲染两个锚点 | [`codex-resume-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-resume-v3/codex-resume-v3-evaluation.md) |
| 待回答恢复 | Codex | — | — | PENDING | — |
| 单页修订 | Codex | — | — | PENDING | — |
| 委派不可用（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1（`multi_agent` 禁用） | PASS | [`codex-review-unavailable-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-review-unavailable-v3/codex-review-unavailable-v3-evaluation.md) |
| 文稿 inline fallback | Codex | — | — | PENDING | — |
| schema-v2 isolated generation | Codex | — | — | PENDING | — |
| 已批准交接 | Claude Code -> Codex | — | — | PENDING | — |
| 仅主题 guided | DeepSeek Harness | — | — | PENDING | — |
| 资料驱动 | DeepSeek Harness | — | — | PENDING | — |
| 审查阻断 | DeepSeek Harness | — | — | PENDING | — |
| 审查后恢复 | DeepSeek Harness | — | — | PENDING | — |
| 待回答恢复 | DeepSeek Harness | — | — | PENDING | — |
| 单页修订 | DeepSeek Harness | — | — | PENDING | — |
| 文稿 inline fallback | DeepSeek Harness | — | — | PENDING | — |
| schema-v2 isolated generation | DeepSeek Harness | — | — | PENDING | — |
| ppt-start deployment hash | 三宿主安装树 | — | — | PENDING | — |
| ppt-editable deployment hash | 三宿主安装树 | — | — | PENDING | — |
| ppt-editable 发现 | Claude Code | — | — | PENDING | — |
| ppt-editable 行为 | Claude Code | — | — | PENDING | — |
| ppt-editable 发现 | Codex | — | — | PENDING | — |
| ppt-editable 行为 | Codex | — | — | PENDING | — |
| ppt-editable 发现 | DeepSeek Harness | — | — | PENDING | — |
| ppt-editable 行为 | DeepSeek Harness | — | — | PENDING | — |
| ppt-editable 无 Office 降级 | 本机 Python | — | — | PENDING | — |
| ppt-editable 完整 Office/视觉 PASS | 受支持的 PowerPoint | — | — | PENDING | — |
| ppt-editable FY26H1 参考运行 | Windows + PowerPoint | — | — | PENDING | — |
| 已批准交接 | Codex -> Claude Code | — | — | PENDING | — |
| 被阻断交接 | Claude Code -> Codex | — | — | PENDING | — |
| 被阻断交接 | Codex -> Claude Code | — | — | PENDING | — |
| 内置示例 SVG 渲染（历史资产证据，仍适用于未改变资产） | 浏览器 | 2026-08-19 | Chrome 151.0.0.0 / Windows 11 | PASS | [`browser-svg.md`](../acceptance-evidence/2026-08-19/browser-svg.md) |
| 生成锚点 SVG 渲染（历史旧标识） | 浏览器 | 2026-08-19 | Chrome 151.0.0.0 / Windows 11 | PASS — Codex 恢复场景的两个锚点 | [`codex-resume-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-resume-v3/codex-resume-v3-evaluation.md) |
| 完整生成演示文稿 SVG 渲染 | 浏览器 | — | — | PENDING | — |
| 内置示例 SVG 导入 | 受支持的 PowerPoint | 2026-08-19 | Microsoft PowerPoint 16.0.20228.20190 / Windows 11 | PENDING — 当前资产重验被 COM 注册阻断 | [`powerpoint-svg.md`](../acceptance-evidence/2026-08-19/powerpoint-svg.md) |
| 生成演示文稿 SVG 导入 | 受支持的 PowerPoint | — | — | PENDING | — |

允许的结果值为 `PASS`、`FAIL`、`BLOCKED`、`NOT RUN` 和 `PENDING`。`FAIL`、`BLOCKED` 或 `NOT RUN` 必须在测试记录中附简短原因；无法测试绝不能改写为通过。
