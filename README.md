# PPT Pilot

PPT Pilot 是一个可同时用于 Claude Code 与 OpenAI Codex 的可移植、纯指令 Agent Skill。它通过工作区中的持久产物开发有证据支撑的 16:9 演示文稿，并把每页幻灯片交付为独立 SVG 文件。

MVP 不强制依赖 MCP 服务、SDK、Hook、后台服务、运行时软件包或外部审稿服务。Python 只用于本仓库的一致性测试；安装后的 Skill 直接使用宿主已有的文件、研究、委派与检查能力。仓库另提供可选伴随工具（`tools/`，见[可选伴随工具与交付组装](#可选伴随工具与交付组装)），它们随仓库分发，不属于安装后的 Skill。

## 能做什么

统一工作流如下：

1. 规范化需求简报，并按需研究；
2. 编写结论先行的大纲与逐页故事板；
3. 优先在全新子 Agent／上下文中执行文稿审查；委派失败时由当前步骤执行正式降级审查；
4. 确定主题并生成两页视觉锚点；
5. 逐页生成 Office-safe SVG；
6. 执行单页与整套演示文稿 QA；
7. 从文件化状态恢复运行或进行局部修订。

`BLOCKER` 或 `HIGH` 级问题只有在后续正式审查 round 提供冻结证据并标记为 `RESOLVED` 后才可放行；`OPEN` 与阻断级 `ACCEPTED_RISK` 都继续阻断。每轮先尝试具有真实宿主证据的独立子 Agent；启动或结果归因失败时，不空等，而是在当前步骤持久化 `inline_fallback` 并执行同一严格审查。inline PASS 可以进入 `manuscript_approved`，但报告必须声明“当前上下文降级审查，不具备独立上下文隔离”，不能冒充独立审查。subagent 与 inline 轮次共同受每 cycle 三轮上限约束；被阻断周期不能借模式切换或“新周期”绕过上限。

## 安装同一份标准 Skill

技能启动标识：`ppt-start`

请复制或创建符号链接来安装完整的 [`skills/ppt-start`](skills/ppt-start/) 目录，不要拆分其中的 `SKILL.md`、`references/` 与 `assets/`。

### Claude Code

- 用户级安装：`~/.claude/skills/ppt-start/`
- 项目级安装：`.claude/skills/ppt-start/`
- 显式启动命令：`/ppt-start`

用户级复制示例：

```bash
cp -R skills/ppt-start ~/.claude/skills/ppt-start
```

项目级符号链接示例：

```bash
ln -s ../../skills/ppt-start .claude/skills/ppt-start
```

调用示例：

```text
/ppt-start
请根据 inputs/ 中的资料制作一份 10 页中文策略演示文稿，使用 guided 模式。
```

### OpenAI Codex

- 用户级安装：`$HOME/.agents/skills/ppt-start/`
- 项目级安装：`.agents/skills/ppt-start/`
- 显式启动命令：`$ppt-start`

用户级复制示例：

```bash
cp -R skills/ppt-start "$HOME/.agents/skills/ppt-start"
```

项目级符号链接示例：

```bash
ln -s ../../skills/ppt-start .agents/skills/ppt-start
```

调用示例：

```text
$ppt-start
请从 ppt-output/example-deck/ 恢复运行并继续生成 SVG。
```

符号链接是否可用取决于操作系统和宿主沙箱；无法使用时请改为复制，并始终把本仓库的 `skills/ppt-start/` 视为标准源。

## 使用方式

Skill 可接收主题、完整简报、资料集合、既有运行目录或定向修订请求。自然语言请求可以触发它；当自动发现不明确时，建议使用上面的显式启动命令。

持久执行策略：

- **guided**：新运行未显式指定策略时默认 `guided`；在简报、大纲和锚点页提出直接问题并等待明确批准；
- **auto**：只有显式指定时才使用；采用安全默认值并跳过可选问题，但仍创建全部产物、通过所有硬质量门，并在用户权限或无安全默认值时询问。

入口动作：

- **new**：创建新运行并把所选执行策略写入 `run.json.mode`；
- **resume**：先读取 `run.json`，按 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > visual_generation_transaction > stage scan` 恢复；保留既有 `run.json.mode`；
- **revise**：保留既有 `run.json.mode`，先完成同一 durable control chain，再使受影响产物失效；事实、来源、主张、大纲或故事板变化必须重新进行正式文稿审查。

`run.json.mode` 只保存 `guided` 或 `auto`，不保存 `new`、`resume` 或 `revise`。

### 工作区偏好档案（可选）

`ppt-output/pilot-preferences.json` 可跨运行复用品牌方向与交付偏好，减少重复提问：

```json
{
  "schema_version": 1,
  "brand": { "colors": ["#156BFF"], "font_stack": "Microsoft YaHei, Arial, sans-serif", "notes": "强调色只用于关键比较" },
  "style": { "preferred_style_id": "canway-midyear-review" },
  "audience": { "name": "运营管理层", "desired_action": "确认 H2 资源取舍" },
  "language": "zh-CN",
  "confidentiality_restriction": "内部资料不得外发到网络"
}
```

优先级固定为：当前请求明确答案 > 本运行已批准产物 > 偏好档案 > 安全默认值。档案只能记录限制型保密策略；跨运行有效的网络或披露授权必须由用户显式给出并记录为 standing 授权。格式错误时披露原因并整体忽略，不影响运行。完整规则见[用户交互与确认协议](skills/ppt-start/references/interaction-protocol.md)与[产物契约](skills/ppt-start/references/artifact-contract.md)。

### 问答与可恢复等待

Skill 先检查请求和工作区，已有答案不得重复询问。剩余重要决策按依赖顺序处理，一次只提出一个实质性问题；有限选择给出 2–4 个互斥选项并把推荐项放在第一位。推荐不是确认，收到明确回答前不会推进被该问题阻塞的下游阶段。

运行目录已经建立时，当前问题保存在 `run.json.pending_interaction`。有限选择还保存逐项效果、推荐理由以及回答后的规范化决定，使另一个宿主能够原样重放并无需重新解释自然语言。恢复运行会先重发同一个 `pending` 问题，或幂等处理已经保存为 `answered` 的答案，再以原子状态提交避免阶段与问题错位；它不会重新计算有效上游工作。完成的答案保存在可选 `run.json.interaction_history`，阶段产物中的记录只是可重建镜像，因此主题或页面失效不会抹掉批准／修订轨迹。这些字段是 `schema_version: 1` 的可选扩展；没有这些字段的旧运行仍然有效。

当 `resume`／`revise` 有多个候选运行且目标无法唯一确定时，选择问题先保存在工作区级 `ppt-output/run-selection.json`；该文件同时保存入口动作和原始操作载荷，不会写入任何候选运行。选定目标并让该运行到达下一个持久状态后才删除该路由文件，崩溃恢复不会重复询问或丢失修订请求。

同一 guided 检查点修订后再次批准会使用单调的 `approval_attempt`：首次 ID 保持 `<checkpoint>-approval`，后续使用 `<checkpoint>-approval-2`、`-3` 等。每次答案在 `interaction_history` 中占独立键，后来的批准不会覆盖早先的修订事件。

`auto` 只跳过可选偏好和批准，不能自行获得网络传输、机密披露或其他用户权限。没有安全默认值的业务决策仍会产生一个阻塞问题。

### 逐页视觉 brief 与修订

主题确认后，PPT Pilot 为每个待生成或待修订页面创建 `visual-briefs/<slide-id>.md`。visual brief 是权威页面状态和 prompt compiler 输入：它组装已批准内容、当前主题、有效视觉修订、信息层级、构图和 SVG／QA 契约，但不得把 visual brief 直接交给 generator。首次生成、`recompose` 和确定性回退必须先编译 `generation-prompts/<slide-id>.md`；fresh generator 只接收编译后的 `generation-prompts/<slide-id>.md`，不得直接接收 visual brief 或原始风格 prompt。SVG 是派生结果，不是设计状态。

局部碰撞、越界、令牌或对齐错误使用 `patch`；焦点、层级、布局、卡片密度、字体、语义色、品牌方向或视觉参考变化使用 `recompose`。`patch` 读取完整 brief、当前 SVG 和一个精确 defect；`recompose` 从锁定故事板、当前主题和完整 brief 重新构图，不以旧 SVG 为几何底稿。事实和来源变化仍必须重新进行正式文稿审查：优先 subagent，委派失败时 inline fallback。

已应用视觉决定以单调 `visual-revision-<N>` 保存在 `run.json.interaction_history`，后来的同字段规则显式标记 `supersedes`。废弃规则保留在历史中，但不会进入当前生成指令；整套决定镜像到 `theme.json.user_revision_notes`，页面决定镜像到对应 visual brief。

### 可选风格

新安装从 `assets/styles/registry.json` 发现可选风格。三个既有扁平种子继续兼容；内置 rich style pack `canway-midyear-review` 的中文显示名为“嘉为年中总结风格”，当前内容版本为 `1.2.0`。只有用户明确选择或主题阶段按既有 guided／auto 规则安全选中时使用，不是新的默认主题。

四个内置风格各自拥有一份独立可编译的完整模板，即完整、可独立编译的 redesign prompt 模板：`assets/styles/minimal-business.redesign.md`、`assets/styles/tech-dark.redesign.md`、`assets/styles/bold-editorial.redesign.md` 与 `assets/styles/canway-midyear-review/REDESIGN.md`。共享 `references/redesign-prompt.md` 只是 resolver-only 共享契约：解析 selected style、验证 registry／manifest／路径、编译 `generation-prompts/<slide-id>.md`、记录 provenance 和恢复失败；它不再包含跨风格通用的完整视觉 prompt、固定 Bento、固定卡片数量或某个风格的专属构图。只有替换完当前 brief／theme／revision 输入并持久化后的 generation prompt 才能交给 fresh generator，不能直接传递这些原始模板。

`theme.json` 与每份 `visual-briefs/<slide-id>.md` 都持久保存 selected style identity；编译后的 prompt provenance 继续保存 `generation_intent`、`generation_trigger_id`、style prompt snapshot、brief／theme／storyboard snapshot、`compiled_prompt_sha256` 与 `prompt_snapshot_id`。首次生成、用户 `recompose` 和确定性回退都会编译完整风格 prompt；局部 `patch` 只读取完整 brief、当前 SVG 和精确 defect，不加载完整 redesign prompt。风格 prompt 不可用时写入 `run.json.visual_generation_blocker`，可恢复生成过程写入 `run.json.visual_generation_transaction`。全局恢复顺序精确为 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > visual_generation_transaction > stage scan`；只有前四类 durable control state 都不存在或已经完成，才能执行 stage scan。旧 `redesign-prompts/` 目录始终 inert，只读保留历史，不写、不移动、不删除，也不参与当前 prompt 选择。

示例需求：

```text
为运营管理层制作一份 10 页中文策略演示文稿。使用给定报告，保留不确定性，并交付独立 SVG 页面。
```

所有运行产物都写入当前工作区的 `ppt-output/<deck-id>/`：

```text
ppt-output/<deck-id>/
├── run.json
├── 简报.md
├── 研究.md
├── 来源.md
├── 大纲.md
├── 故事板.md
├── 文稿审查.md
├── theme.json
├── visual-briefs/
│   └── <slide-id>.md
├── generation-prompts/
│   └── <slide-id>.md
├── samples/
├── slides/
└── 质量检查报告.md
```

这些文件构成跨宿主交接接口：另一个受支持宿主无需原始对话即可恢复运行。

### 旧英文运行兼容

中文文件名只作为**新运行**的标准。`resume`／`revise` 遇到使用 `brief.md`、`research.md`、`sources.md`、`outline.md`、`storyboard.md`、`manuscript-review.md`、`qa-report.md` 的旧英文运行时，必须原位读取并继续使用该运行已有的名称，不自动重命名、复制或迁移文件。`run.json.manuscript_review.latest_report` 与 `reviewed_file_snapshot.files` 中记录的实际文件名优先；如果同一语义的中英文文件同时存在且状态无法判定，必须停止并报告冲突，不能猜测或覆盖。

## 可选伴随工具与交付组装

Skill 本体保持纯指令；以下工具位于仓库 `tools/`，不进入 `skills/ppt-start/`，也不参与宿主 Skill 发现。

### `deck-deliver.ps1`——预览、PPTX 与演讲者备注

把一次运行的 `slides/*.svg` 组装为可交付成果：

```bash
powershell -ExecutionPolicy Bypass -File tools/deck-deliver.ps1                # 自动探测唯一运行
powershell -ExecutionPolicy Bypass -File tools/deck-deliver.ps1 -RunDir ppt-output/fy26-h1-midyear-review -ExportPng
```

- 始终生成 `<run>/preview.html` 联系表：缩略图网格 + 单页查看器（方向键翻页、Esc 关闭），纯静态、无外部资源；
- 从 `故事板.md`（旧运行 `storyboard.md`）解析每页 `assertion_title`／`audience_takeaway`／`next_link`，自动写入 PPTX 演讲者备注；
- 调用本机 PowerPoint（COM 自动化，与验收脚本同一模式）把每页 SVG 插入 16:9 PPTX 并复开校验；本机没有 PowerPoint 或指定 `-SkipPptx` 时跳过该步，preview.html 仍可用；
- `-ExportPng` 额外导出每页 1280×720 PNG 作为渲染证据；结果清单写入 `<run>/delivery/delivery-result.json`；
- 工具只新增 preview.html 与 `delivery/`，不修改任何 Skill 运行产物。

PPTX 组装需要交互式桌面会话中的真实 PowerPoint（与[验收文档](docs/acceptance.md)的 real host 要求一致）；无头环境中 preview.html 始终可用。退出码：`0`=PPTX+preview 成功；`3`=仅 preview 成功；致命失败以异常终止。

## 研究、隐私与能力降级

可选网络研究不是运行时依赖。用户提供的资料和本地资料优先；默认不得把机密内容发送到网络。当实时研究或渲染不可用时，Skill 必须记录限制、限定未验证主张，并使用 `visual_qa: not_rendered`，不得虚构验证结果。

文稿审查仍优先独立子 Agent，但委派不可用时使用 `inline_fallback`：当前步骤只依据冻结文稿和同一审查规范完成正式审查，并可按严格 findings 门放行。只有 inline 也无法执行时才使用 legacy-compatible `review_unavailable`。

## SVG 与 PowerPoint 范围

交付物是静态、独立 SVG：画布为 1280×720，使用系统字体回退、显式 `<tspan>` 换行、内联矢量几何，不包含远程资源或仅浏览器可用的效果。

受支持的 PowerPoint 版本可以插入静态 SVG，但 PPT Pilot 不保证所有 Office 版本与平台都能一致导入，也不保证转换后每个元素都完全可编辑。浏览器渲染和代表性 PowerPoint 导入仍属于人工验收项。

Skill 本体不生成 PPTX、不导入既有 PowerPoint 模板、不搜索图库图片、不生成位图、不制作动画，也不创建演讲者备注。最后一公里交付由可选伴随工具 `tools/deck-deliver.ps1` 以本机 PowerPoint COM 自动化补齐（含从故事板自动生成的演讲者备注与 preview.html 联系表），不改变 Skill 的纯指令边界。

## 开发验证

运行仓库一致性测试。Task 10 文档边界的聚焦命令是：

```bash
python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v
```

完整本地命令是：

```bash
python -m unittest discover -s tests -v
```

证据按类别记录：`static package` 只证明包结构、书面契约和 fixture oracle；`EVIDENCE_CLASS: DIAGNOSTIC` 只用于压力提示或诊断，不得当作 Claude Code、Codex、fresh generator、浏览器或 PowerPoint 验收；`deployment hash` 只证明同步后的安装文件集与仓库源一致；`real host` 才能证明带版本、transcript 和运行目录的真实宿主行为。架构说明见[设计文档](docs/design.md)，Claude Code、Codex 与跨宿主交接检查见[验收文档](docs/acceptance.md)。尚未执行的人工结果必须继续标记为 `PENDING`；自动化测试本身不能证明宿主行为、fresh 上下文、浏览器渲染或 PowerPoint 导入。
