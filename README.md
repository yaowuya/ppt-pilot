# PPT Pilot

PPT Pilot 是一个可同时用于 Claude Code 与 OpenAI Codex 的可移植、纯指令 Agent Skill。它通过工作区中的持久产物开发有证据支撑的 16:9 演示文稿，并把每页幻灯片交付为独立 SVG 文件。

MVP 不强制依赖 MCP 服务、SDK、Hook、后台服务、运行时软件包或外部审稿服务。Python 只用于本仓库的一致性测试；安装后的 Skill 直接使用宿主已有的文件、研究、委派与检查能力。

## 能做什么

统一工作流如下：

1. 规范化需求简报，并按需研究；
2. 编写结论先行的大纲与逐页故事板；
3. 在全新子 Agent／上下文中执行强制独立文稿审查；
4. 确定主题并生成两页视觉锚点；
5. 逐页生成 Office-safe SVG；
6. 执行单页与整套演示文稿 QA；
7. 从文件化状态恢复运行或进行局部修订。

`BLOCKER` 或 `HIGH` 级问题只有在后续独立审稿人提供证据并标记为 `RESOLVED` 后才可放行；这两个级别的 `OPEN` 与 `ACCEPTED_RISK` 都继续阻断。每轮审查还必须具有宿主返回的真实子上下文、完成事件和一致的结果来源；虚构审稿人名称或空等待不构成独立审查。如果宿主无法启动可归因的独立审稿人，运行必须进入 `review_unavailable` 并在设计前停止；同上下文自审不能替代该质量门。每个文稿审查周期最多三轮；只有此前已经 `manuscript_approved` 的版本后来发生实质性修订，才会递增可选 `manuscript_review.cycle` 并从该新周期第 1 轮重新审查。被阻断的周期不能借“新周期”绕过三轮上限。

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
- **resume**：先读取 `run.json` 和待回答交互，保留既有 `run.json.mode`，再从第一个未完成或脏阶段继续；
- **revise**：保留既有 `run.json.mode`，只使受影响的产物失效；事实、来源、主张、大纲或故事板变化必须重新进行文稿审查。

`run.json.mode` 只保存 `guided` 或 `auto`，不保存 `new`、`resume` 或 `revise`。

### 问答与可恢复等待

Skill 先检查请求和工作区，已有答案不得重复询问。剩余重要决策按依赖顺序处理，一次只提出一个实质性问题；有限选择给出 2–4 个互斥选项并把推荐项放在第一位。推荐不是确认，收到明确回答前不会推进被该问题阻塞的下游阶段。

运行目录已经建立时，当前问题保存在 `run.json.pending_interaction`。有限选择还保存逐项效果、推荐理由以及回答后的规范化决定，使另一个宿主能够原样重放并无需重新解释自然语言。恢复运行会先重发同一个 `pending` 问题，或幂等处理已经保存为 `answered` 的答案，再以原子状态提交避免阶段与问题错位；它不会重新计算有效上游工作。完成的答案保存在可选 `run.json.interaction_history`，阶段产物中的记录只是可重建镜像，因此主题或页面失效不会抹掉批准／修订轨迹。这些字段是 `schema_version: 1` 的可选扩展；没有这些字段的旧运行仍然有效。

当 `resume`／`revise` 有多个候选运行且目标无法唯一确定时，选择问题先保存在工作区级 `ppt-output/run-selection.json`；该文件同时保存入口动作和原始操作载荷，不会写入任何候选运行。选定目标并让该运行到达下一个持久状态后才删除该路由文件，崩溃恢复不会重复询问或丢失修订请求。

同一 guided 检查点修订后再次批准会使用单调的 `approval_attempt`：首次 ID 保持 `<checkpoint>-approval`，后续使用 `<checkpoint>-approval-2`、`-3` 等。每次答案在 `interaction_history` 中占独立键，后来的批准不会覆盖早先的修订事件。

`auto` 只跳过可选偏好和批准，不能自行获得网络传输、机密披露或其他用户权限。没有安全默认值的业务决策仍会产生一个阻塞问题。

### 逐页视觉 brief 与修订

主题确认后，PPT Pilot 为每个待生成或待修订页面创建 `visual-briefs/<slide-id>.md`。该文件组装已批准内容、当前主题、有效视觉修订、信息层级、构图和 SVG／QA 契约，是跨对话和跨宿主恢复视觉意图的唯一页面输入。SVG 是派生结果，不是设计状态；没有有效的逐页视觉 brief 就不能生成页面。

局部碰撞、越界、令牌或对齐错误使用 `patch`；焦点、层级、布局、卡片密度、字体、语义色、品牌方向或视觉参考变化使用 `recompose`。`patch` 读取完整 brief、当前 SVG 和一个精确 defect；`recompose` 从锁定故事板、当前主题和完整 brief 重新构图，不以旧 SVG 为几何底稿。事实和来源变化仍必须重新进行独立文稿审查。

已应用视觉决定以单调 `visual-revision-<N>` 保存在 `run.json.interaction_history`，后来的同字段规则显式标记 `supersedes`。废弃规则保留在历史中，但不会进入当前生成指令；整套决定镜像到 `theme.json.user_revision_notes`，页面决定镜像到对应 visual brief。

### 可选风格

新安装从 `assets/styles/registry.json` 发现可选风格。三个既有扁平种子继续兼容；内置 rich style pack `canway-midyear-review` 的中文显示名为“嘉为年中总结风格”。只有用户明确选择或主题阶段按既有 guided／auto 规则安全选中时使用，不是新的默认主题。风格包中的 `reference.svg` 只表达视觉语言，不能覆盖逐页 brief 的内容和构图语义。

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
├── samples/
├── slides/
└── 质量检查报告.md
```

这些文件构成跨宿主交接接口：另一个受支持宿主无需原始对话即可恢复运行。

### 旧英文运行兼容

中文文件名只作为**新运行**的标准。`resume`／`revise` 遇到使用 `brief.md`、`research.md`、`sources.md`、`outline.md`、`storyboard.md`、`manuscript-review.md`、`qa-report.md` 的旧英文运行时，必须原位读取并继续使用该运行已有的名称，不自动重命名、复制或迁移文件。`run.json.manuscript_review.latest_report` 与 `reviewed_file_snapshot.files` 中记录的实际文件名优先；如果同一语义的中英文文件同时存在且状态无法判定，必须停止并报告冲突，不能猜测或覆盖。

## 研究、隐私与能力降级

可选网络研究不是运行时依赖。用户提供的资料和本地资料优先；默认不得把机密内容发送到网络。当实时研究或渲染不可用时，Skill 必须记录限制、限定未验证主张，并使用 `visual_qa: not_rendered`，不得虚构验证结果。

独立子 Agent 委派与一般能力降级不同：文稿审查属于强制独立质量门，因此委派不可用时必须阻断视觉设计，不能降级为同上下文自审放行。

## SVG 与 PowerPoint 范围

交付物是静态、独立 SVG：画布为 1280×720，使用系统字体回退、显式 `<tspan>` 换行、内联矢量几何，不包含远程资源或仅浏览器可用的效果。

受支持的 PowerPoint 版本可以插入静态 SVG，但 PPT Pilot 不保证所有 Office 版本与平台都能一致导入，也不保证转换后每个元素都完全可编辑。浏览器渲染和代表性 PowerPoint 导入仍属于人工验收项。

MVP 不生成 PPTX、不导入既有 PowerPoint 模板、不搜索图库图片、不生成位图、不制作动画，也不创建演讲者备注。

## 开发验证

运行仓库一致性测试：

```bash
python -m unittest discover -s tests -v
```

架构说明见[设计文档](docs/design.md)，Claude Code、Codex 与跨宿主交接检查见[验收文档](docs/acceptance.md)。尚未执行的人工结果必须继续标记为 `PENDING`；自动化测试本身不能证明宿主行为或 PowerPoint 渲染结果。
