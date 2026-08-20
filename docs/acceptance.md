# 跨宿主验收

本文档给出同一标准 `skills/ppt-start/` 包在 Claude Code 与 OpenAI Codex 中的可重复人工验收矩阵。自动一致性测试验证书面契约，但不能证明宿主委派、跨宿主续作、浏览器渲染或 PowerPoint 导入。

未执行的项目一律保持 `PENDING`。只有记录运行日期、精确宿主版本和证据路径后，才能更新结果；没有可检查证据就不能标为通过。

## 前置条件

1. 把未经修改的 `skills/ppt-start/` 完整复制或链接到待测宿主的已记录发现路径。
2. 每个场景都从干净工作区开始。不得把运行产物写入已安装 Skill 或宿主配置目录。
3. 执行 `source-driven.md` 前，把仓库中的 `tests/inputs/` 复制到干净工作区的 `inputs/`。这些文件明确标注为合成验收样例，绝不能描述成真实研究或客户数据。
4. 执行 `resume-after-review.md` 前，创建 `ppt-output/resume-approved/`，把 `tests/fixtures/run-review-approved.json` 复制为其中的 `run.json`，再把 `tests/fixtures/resume-approved/` 的六个文件复制到同一目录，并把 `tests/inputs/` 复制到工作区的 `inputs/`。这是专门验证只读恢复能力的**旧英文运行兼容夹具**，所有文件名与内容必须保持不变，接收宿主不得自动重命名或迁移。
5. 执行 `resume-pending-interaction.md` 前，创建 `ppt-output/pending-outline-approval/`，把 `tests/fixtures/run-pending-interaction.json` 复制为其中的 `run.json`，并准备与其 `outline` 阶段匹配的已批准简报、研究、来源和当前大纲。接收宿主必须先处理同一个待回答问题，不得创建新问题或重做上游工作。
6. 执行 `revise-single-slide.md` 前，准备三个相互独立、完整且已通过的 source-driven 合成运行副本。patch、recompose 和 factual change 三个分支分别在不同副本中执行，避免一条分支污染另一条分支的起始状态。
7. 保存完整 `ppt-output/<deck-id>/` 和宿主 transcript／日志作为证据。
8. 验证审稿独立性时，保存宿主返回的子上下文 ID、完成事件 ID、匹配的结果来源上下文 ID 及审稿人受限输入。审稿人只能接收五个冻结文稿文件和审查规范。只有文字叙述，或没有子上下文／接收者状态的空等待，均视为失败，不构成来源证据。`run.json` 单独存在不是证据；每个声明的 ID 都必须与宿主 transcript 或协作日志关联。
9. 跨宿主交接时，不得向接收宿主提供发起宿主的对话。
10. 实时网络或渲染不可用时，应保留运行中明确的降级状态，不能将其解释为通过。

## 共用场景矩阵

每个提示都要分别在 Claude Code 与 Codex 中运行。预期契约完全相同，只有 Skill 发现路径和显式启动命令不同。

| 提示 | 目的 | 必须观察的行为 | 预期终止状态／产物 |
|---|---|---|---|
| [`guided-topic-only.md`](../tests/prompts/guided-topic-only.md) | 验证缺省 guided、主题规范化与三个检查点。 | 模式未显式指定时默认 `guided`；先检查已有输入；一次只提出一个实质性问题；简报、大纲和锚点都提出直接问题并等待明确回答。 | 每个问题等待期间保持当前阶段且不得推进下游；批准完成后才进入下一阶段。 |
| [`source-driven.md`](../tests/prompts/source-driven.md) | 验证 auto 安全默认值、用户资料优先、来源元数据和主张映射。 | `auto` 不提出可选问题；用户资料优先；网络／机密行为仍受用户权限约束；`研究.md`、`来源.md`、大纲和故事板保持稳定来源 ID 与限定。 | 只有每个 `BLOCKER`／`HIGH` 问题都为 `RESOLVED` 才能进入视觉阶段。 |
| [`review-blocker.md`](../tests/prompts/review-blocker.md) | 使用人为植入的无支持统计值验证严格文稿质量门。 | 独立报告把无支持主张记录为未解决的 `HIGH` 问题，并由 `run.json` 把该 ID 写入阻断列表。 | `manuscript_blocked`；不得生成 `theme.json`、`samples/`，也不得生成 SVG。 |
| [`resume-after-review.md`](../tests/prompts/resume-after-review.md) | 从已批准样例恢复，不重复上游工作。 | 从 [`run-review-approved.json`](../tests/fixtures/run-review-approved.json) 开始；先读 `run.json`；保留已批准文稿；没有失效时不重复研究或审查。 | 推进到 `theme` 与 `anchor`，嵌套审查状态仍为 `manuscript_approved`。 |
| [`resume-pending-interaction.md`](../tests/prompts/resume-pending-interaction.md) | 验证待回答、已回答和请求修订状态跨轮次／跨宿主恢复。 | 从 [`run-pending-interaction.json`](../tests/fixtures/run-pending-interaction.json) 开始；先读 `run.json`；重发同一个直接问题及完整效果／推荐理由；收到明确回答后先写 `status: answered`、原始 `answer` 和规范化 `decision`。 | 回答前不得推进下游；产物幂等写入后，以一次原子状态替换完成阶段更新和交互对象删除／替换，不重复上游工作。 |
| [`revise-single-slide.md`](../tests/prompts/revise-single-slide.md) | 验证 patch、recompose 与事实变更的三个独立分支。 | 分支 A 的 24 px 对齐和非事实错字分类为 patch，只读取完整 brief、当前 SVG 与精确 defect；分支 B 的焦点、卡片密度和视觉参考变化分类为 recompose，重建 S05 brief／SVG 且不以旧 SVG 为几何底稿；分支 C 的数字／来源变化不属于视觉模式，使文稿批准和全部依赖视觉产物失效。 | patch 只标脏 S05 SVG 与 QA；recompose 只标脏 S05 brief／SVG 与 QA；factual change 只有新的全新独立审查通过后才能重新生成视觉内容。 |

静态套件还解析 [`interaction-transition-cases.json`](../tests/fixtures/interaction-transition-cases.json)、[`workspace-run-selection.json`](../tests/fixtures/workspace-run-selection.json)、[`run-outline-reapproval.json`](../tests/fixtures/run-outline-reapproval.json) 和 [`review-cycle-reset.json`](../tests/fixtures/review-cycle-reset.json)，验证 `answered` 崩溃恢复、三个批准阶段映射、修订澄清替换、再次批准历史不覆盖、锚点上游修订重入、歧义目标路由及第 3 轮批准后的新审查周期。夹具只证明书面状态契约内部一致，不替代下面的真实宿主 transcript 验收。

## 快速视觉机制验证

本次机制改造只要求本地契约测试与 SVG 静态检查：visual brief 完整性、视觉修订优先级、patch/recompose 分支、风格注册表、嘉为年中总结风格资产引用，以及合成 `reference.svg` 的 Office-safe 结构。

本次不新增 Claude Code／Codex 现场运行、PowerPoint 导入、整套浏览器视觉检查或 FY26 页面重生成证据。历史验收台账保持原状态，不能把本地绿色测试描述为这些人工验收已经通过。

静态验证还检查：

- `visual-briefs/<slide-id>.md` 的七个必需章节、风格 provenance 与锁定来源边界；
- `visual-revision-<N>`、`supersedes` 和 deck／slide 作用域归并；
- `patch`、`recompose` 和事实重入三个互斥分支；
- `assets/styles/registry.json`、`canway-midyear-review` manifest／tokens／`STYLE.md`／`reference.svg`；
- 合成参考 SVG 的允许元素、禁止特性、画布、字号和唯一 ID。

每个场景至少检查：

- `run.json` 的顶层阶段、嵌套审查 cycle／状态／历史、脏页面和可选 `pending_interaction`／`interaction_history`；目标不唯一时还检查工作区 `run-selection.json`；
- 五个冻结文稿文件；
- 当前运行实际使用的审查报告：新运行检查 `文稿审查.md`，旧英文运行检查 `manuscript-review.md`，并核对审稿来源；
- 视觉产物是否只在正确质量门后出现；
- 每个待生成／修订页面是否先有有效 `visual-briefs/<slide-id>.md`，并且只含当前有效视觉规则；
- 当前运行实际使用的 QA 报告：新运行检查 `质量检查报告.md`，旧英文运行检查 `qa-report.md`，包括真实的 `visual_qa` 状态；
- 独立 SVG 结构和运行目录内容。

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

安装到 `~/.claude/skills/ppt-start/` 或 `.claude/skills/ppt-start/`。使用 `/ppt-start` 显式启动，再附上对应提示内容。记录精确 Claude Code 版本，以及证明全新审稿上下文的证据。

### Codex

安装到 `$HOME/.agents/skills/ppt-start/` 或 `.agents/skills/ppt-start/`。使用 `$ppt-start` 显式启动，再附上同一提示内容。记录精确 Codex 版本，以及证明全新审稿上下文的证据。

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

两个方向都要交接一份最新独立报告仍含未解决的 `HIGH` 问题的运行，并在接收宿主中尝试 `resume`。预期仍为 `manuscript_blocked`：不得生成 `theme.json`、样例 SVG 或最终 SVG。接收宿主如果把 `ACCEPTED_RISK`、缺失问题或同上下文自审当作批准，即为失败。

## 委派不可用场景

每个宿主都要在独立委派被禁用或确实不可用时运行一次。

预期行为：

- 顶层阶段与嵌套审查状态均为 `review_unavailable`；
- 记录原因并设置 `manuscript_review.mode: unavailable`，顶层 `run.json.mode` 仍为 `guided` 或 `auto`；
- 新运行使用 `文稿审查.md`，旧英文运行沿用 `manuscript-review.md`；报告说明不可用原因和没有审稿人运行，`latest_report` 必须指向该运行实际使用的文件；
- 同上下文自审不得冒充批准；
- 不得生成 `theme.json`、样例或 SVG；
- 不能错误标记为 `manuscript_blocked`，因为实际独立审查没有发生。

如果宿主配置无法安全禁用委派，把该项记录为 `NOT RUN` 并说明原因，不得伪造 unavailable 结果。

## SVG 浏览器检查

对内置示例和代表性生成页面执行：

1. 在当前浏览器中直接打开 SVG，并记录浏览器名称／版本；
2. 确认画布为 16:9，标题、正文和来源文字全部可见，没有裁切或意外换行；
3. 确认没有远程资源缺失、控制台资源错误、重叠、不安全元素或超出安全区域的内容；
4. 如果生成演示文稿包含这些页面，至少检查一个低密度结论页、一个高密度数据／流程页和一个含来源页；
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
| 委派不可用 | Claude Code | — | — | PENDING | — |
| 仅主题 guided | Codex | — | — | PENDING | — |
| 资料驱动 | Codex | — | — | PENDING | — |
| 审查阻断（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1 | FAIL — 空等待并虚构子上下文／结果来源 | [`codex-blocker-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-blocker-v3/codex-blocker-v3-evaluation.md) |
| 审查后恢复（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1 | PASS — 从合成批准样例生成并渲染两个锚点 | [`codex-resume-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-resume-v3/codex-resume-v3-evaluation.md) |
| 待回答恢复 | Codex | — | — | PENDING | — |
| 单页修订 | Codex | — | — | PENDING | — |
| 委派不可用（历史旧标识） | Codex | 2026-08-19 | Codex CLI 0.146.1（`multi_agent` 禁用） | PASS | [`codex-review-unavailable-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-review-unavailable-v3/codex-review-unavailable-v3-evaluation.md) |
| 已批准交接 | Claude Code -> Codex | — | — | PENDING | — |
| 已批准交接 | Codex -> Claude Code | — | — | PENDING | — |
| 被阻断交接 | Claude Code -> Codex | — | — | PENDING | — |
| 被阻断交接 | Codex -> Claude Code | — | — | PENDING | — |
| 内置示例 SVG 渲染 | 浏览器 | 2026-08-19 | Chrome 151.0.0.0 / Windows 11 | PASS | [`browser-svg.md`](../acceptance-evidence/2026-08-19/browser-svg.md) |
| 生成锚点 SVG 渲染（历史旧标识） | 浏览器 | 2026-08-19 | Chrome 151.0.0.0 / Windows 11 | PASS — Codex 恢复场景的两个锚点 | [`codex-resume-v3-evaluation.md`](../acceptance-evidence/2026-08-19/host-runs/codex-resume-v3/codex-resume-v3-evaluation.md) |
| 完整生成演示文稿 SVG 渲染 | 浏览器 | — | — | PENDING | — |
| 内置示例 SVG 导入 | 受支持的 PowerPoint | 2026-08-19 | Microsoft PowerPoint 16.0.20228.20190 / Windows 11 | PENDING — 当前资产重验被 COM 注册阻断 | [`powerpoint-svg.md`](../acceptance-evidence/2026-08-19/powerpoint-svg.md) |
| 生成演示文稿 SVG 导入 | 受支持的 PowerPoint | — | — | PENDING | — |

允许的结果值为 `PASS`、`FAIL`、`BLOCKED`、`NOT RUN` 和 `PENDING`。`FAIL`、`BLOCKED` 或 `NOT RUN` 必须在测试记录中附简短原因；无法测试绝不能改写为通过。
