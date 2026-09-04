# PPT Pilot 视觉提示组装机制设计

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

- **日期**：2026-08-20
- **状态**：设计已逐节批准
- **范围**：仅改造 PPT Pilot 通用机制；不修改或重新生成 FY26 年中总结的正式 SVG

## 1. 背景与问题

PPT Pilot 是纯指令型 Agent Skill，没有独立运行时或确定性的 prompt-builder。现有机制能够持久化文稿、审查、主题、SVG 和 QA 状态，但视觉修订可能只在当前对话或临时预览中生效。后续宿主恢复时仍可能读取旧 `theme.json`，导致已经被新决定覆盖的规则重新出现。

另一个问题是视觉修订没有区分局部缺陷修补和完整页面重组。“重点不突出”“更高级”“改变卡片层级”等请求可能继续沿用旧 SVG 几何，只做局部修改。模型因此能够满足每一条局部要求，却没有重新执行内容优先级、焦点、阅读路径和布局选择，产生视觉债务。

本设计先把设计上下文固化为逐页自包含 visual brief；按照 2026-08-21 规范，首次生成、`recompose` 与确定性回退还必须解析所选风格自有模板，编译并持久化 `generation-prompts/<slide-id>.md`，再由 fresh generator 生成候选 SVG。

## 2. 目标

1. 每次视觉生成都使用完整、当前、无冲突的设计上下文，不依赖对话记忆。
2. 把已批准内容边界、主题、用户视觉修订、布局和质量要求组装到逐页文件中。
3. 明确区分 `patch` 与 `recompose`，防止广泛设计请求退化为局部修补。
4. 让 Claude Code 与 Codex 能仅凭运行目录恢复同一视觉意图。
5. 保留 PPT Pilot 的纯指令、无运行时依赖和 Office-safe SVG 架构。
6. 使用合成夹具验证状态归并与修订行为，不把内部演示材料写入共享测试。
7. 把已确认的管理汇报视觉语言固化为可选择的“嘉为年中总结风格”，并建立可继续扩展新风格的包结构。
8. 风格包以机器可读 tokens 与抽象 `STYLE.md` 表达风格身份，并以风格自有 `REDESIGN.md` 承载可独立交给 fresh generator 的完整生成指令模板；该模板不是单页成品示例或固定版式。

## 3. 非目标

- 不引入 Python、JavaScript、SDK、Hook 或后台服务作为强制运行时。
- 不修改现有稳定阶段值，也不新增 `visual_brief` 顶层阶段。
- 不改变独立文稿审查的授权边界。
- 不在本次改造中更新 FY26 运行的 `theme.json`、`run.json` 或 S09/S11/S12 SVG。
- 不执行耗时的 Claude Code／Codex 跨宿主现场行为验收、PowerPoint 人工导入、整套浏览器视觉验收或 FY26 全套页面重生成。
- 不承诺不同模型采样产生逐像素相同的 SVG；本设计保证输入边界、优先级和流程一致。

## 4. 总体架构

现有阶段保持不变：

```text
brief
  -> research
  -> outline
  -> storyboard
  -> manuscript_review
  -> theme
  -> anchor
  -> production
  -> qa
  -> complete
```

在 `theme` 阶段内部增加视觉上下文组装和 prompt 编译：

```text
approved storyboard
+ active theme
+ authoritative visual revision history
+ SVG and QA contracts
= active visual contract
= visual-briefs/<slide-id>.md
+ selected style-owned redesign template
= generation-prompts/<slide-id>.md
= fresh generator candidate SVG
```

`visual-briefs/<slide-id>.md` 是该页已消解冲突的权威视觉输入，但不是可直接交给生成器的完整 prompt。首次生成、`recompose` 和确定性回退必须按已持久化的风格 ID 解析风格自有模板，编译并持久化 generation prompt，再启动 fresh generator；`patch` 仍使用完整 brief、当前 SVG 和唯一 defect。最终 SVG 是生成结果，不承担主题、构图、prompt 或修订历史的权威状态。

### 4.1 组件边界

| 组件 | 职责 | 权威性 |
|---|---|---|
| 已批准故事板 | 内容、主张、限定条件、来源与视觉意图 | 文稿权威 |
| `run.json.interaction_history` | 用户视觉决定和覆盖关系的完整历史 | 修订权威 |
| `theme.json` | 整套演示当前有效的设计令牌和主题决定镜像 | 主题镜像 |
| `visual-briefs/Sxx.md` | 已消解冲突的逐页自包含视觉输入与持久风格身份 | 页面视觉权威输入 |
| 风格自有 `REDESIGN.md` | 所选风格的完整、版本化生成模板 | 风格生成指令权威 |
| `generation-prompts/Sxx.md` | 由 brief、theme、有效修订和风格模板确定性编译的完整 prompt | 当前生成事务输入 |
| `slides/Sxx.svg` | Office-safe 最终结果 | 非权威派生产物 |
| QA 报告 | 结构、内容、几何和真实渲染结论 | 验证记录 |

## 5. 逐页视觉 brief 契约

每份 `visual-briefs/<slide-id>.md` 必须包含以下章节，缺少任一章节时不得生成 SVG。

### 5.1 来源与版本

- `slide_id`
- 已批准故事板快照 ID
- 当前主题快照 ID
- 已应用的 `visual-revision-<N>` 交互 ID
- brief 自身稳定快照 ID
- 所选风格 ID、显示名、`style_kind` 与 manifest 版本；legacy seed 的版本写字符串 `none`
- 风格 token 路径与抽象 guidance 路径
- 已解析的风格自有 redesign prompt 路径、模板 snapshot，以及对应 generation prompt／transaction provenance；不得记录单页成品参考路径

### 5.2 锁定内容

- 原结论标题
- 受众要点
- 必须呈现的内容块
- 数字、单位、期间、比较基准和限定条件
- 来源 ID
- 禁止新增或强化的主张
- 允许压缩但不得改变含义的展示文案

视觉 brief 可以把长句压缩成标签或关键词，但不得改变置信度、范围、因果、比较、建议、数字、来源映射或受众行动。

### 5.3 信息层级

- 唯一主信息
- 2–5 个支持论点
- 被有意弱化或移至辅助层的信息
- 第一、第二、第三阅读位置
- 本页管理者最终应形成的判断

### 5.4 构图

- 语义布局家族和选择理由
- 焦点对象
- 区域映射
- 主次对象面积关系
- 卡片数量和层级
- 是否使用嵌套卡片
- 连接线的方向和语义
- 留白与密度策略

层级 Bento 默认要求主信息承载区域至少为单个次信息区域的 1.5 倍；如使用字号、明暗或位置建立更强层级，brief 必须解释替代编码。

### 5.5 视觉系统

- 当前有效颜色及其语义角色
- 标题、主命题、区块标题、正文、辅助文字和微标签的字体阶梯
- 可进行短语级强调的标题片段
- 圆角、描边、间距、阴影和表面规则
- 禁止母题，例如已被取消的标题长蓝条
- 本页允许的例外及理由

### 5.6 修订模式

- `mode: patch | recompose`
- `patch` 时必须给出唯一、可验证的 defect
- `recompose` 时必须说明需要重新设计的层级或艺术方向
- 修复次数只统计当前候选版本生成后的硬失败修补

### 5.7 输出与质量要求

- 1280×720 画布和安全区
- Office-safe SVG 元素与禁止特性
- 字体和 `<tspan>` 规则
- `data-source-id` 等来源元数据要求
- 结构 QA、内容 QA、几何 QA 和视觉 QA 清单

## 6. 视觉决定的持久化与优先级

### 6.1 历史记录

所有已经应用的直接视觉修订都写入 `run.json.interaction_history`，即使该指令不是 guided 批准问题的回答。稳定键采用：

```text
visual-revision-1
visual-revision-2
visual-revision-3
```

每条记录至少包含：

- `stage`
- `kind: visual_revision`
- 原始 `answer`
- 规范化字段变化
- `affected_scope`: `deck`、`anchor` 或 slide IDs
- `supersedes`
- `status: applied`
- `artifact_owner`

整套视觉决定镜像到 `theme.json.user_revision_notes`；单页决定同时镜像到对应 brief。镜像可以重建，权威历史不能因失效或恢复被删除。

### 6.2 优先级

当前有效视觉契约按以下顺序归并：

1. **不可覆盖层**：已批准内容、证据、保密、安全区和 Office-safe 规则。
2. **种子层**：内置主题默认值。
3. **品牌／主题层**：用户确认的整套品牌与艺术方向。
4. **页面层**：针对具体页面的最新视觉决定。
5. **修复层**：不改变构图的局部 defect 修复。

后一条明确指令可以覆盖前一条同字段规则，但必须记录 `supersedes`。废弃规则继续保留在历史中，不得进入视觉 brief 的当前有效规则。

无法判断两条规则是覆盖还是并存时，视觉生成停止并报告冲突；不得把矛盾约束一起交给模型自行取舍。

## 7. 修订模式

### 7.1 `patch`

`patch` 只适用于保留当前构图的可测量缺陷：

- 文字碰撞、溢出或裁切
- 明确的间距或对齐修正
- 错误的设计令牌
- 连接线穿过文字或表达错误方向
- 不改变含义的错别字、标点或语法修正

输入必须是：

```text
完整视觉 brief
+ 当前 SVG
+ 一个明确 defect
```

修改范围不得扩展到与 defect 无关的构图或艺术方向。

### 7.2 `recompose`

以下请求必须完整重组：

- 焦点、阅读路径或主次层级变化
- 布局家族、卡片密度、嵌套关系变化
- 字体系统、语义色或品牌方向变化
- 用户提供新的参考 SVG、截图或完整视觉 prompt
- “重点不突出”“更高级”“重新优化”等广泛视觉反馈
- 多次局部修改已经形成视觉债务

输入是完整视觉 brief、已批准故事板锁定内容和当前有效主题。旧 SVG 不得作为几何底稿；新候选完成后，可以把旧 SVG 作为内容和来源覆盖的核对对象。

`recompose` 生成新候选后重新开始该候选的修复计数。最多两次硬失败 patch 后，才执行现有单栏／双栏回退。

### 7.3 内容变化

任何可能改变主张、置信度、范围、因果、比较、建议、数字或来源映射的请求都不是 `recompose`，必须按现有产物契约使文稿批准失效并重新进行独立审查。

## 8. 生成流程

每次锚点或正式页面生成按固定顺序执行：

1. 读取 `run.json`，先处理 `pending_interaction`，再恢复已有 visual generation blocker／transaction，并验证文稿批准状态。
2. 读取已批准故事板、当前 `theme.json` 和权威视觉修订历史。
3. 归并当前有效契约并显式排除废弃规则。
4. 创建或更新逐页 visual brief，持久化唯一风格身份、`generation_intent` 与 trigger。
5. 验证 brief 完整性、内部一致性以及 theme／brief 的风格身份握手。
6. 对首次生成、`recompose` 或确定性回退，按 brief 中的风格 ID 解析 registry／manifest 或受限 legacy fallback，读取该风格自有 `REDESIGN.md`（legacy 使用声明或 companion prompt）；`patch` 不加载完整风格 prompt。
7. 建立可恢复 transaction，将 brief 各章节、active theme、有效规范化修订和低权威用户措辞编译为 `generation-prompts/<slide-id>.md`；prompt 持久且 hash 核对成功后才可启动 fresh generator。
8. fresh generator 只接收 compiled prompt，不接收旧 SVG 或工作区写权限；创建上下文提取唯一 SVG 并写入 transaction 的确定性 candidate 路径。
9. 与锁定内容、来源和 forbidden claims 逐项核对，并执行结构硬检查和真实渲染 QA。
10. 候选验证成功后才原子提升为 final SVG；失败保持上一有效 SVG 和 dirty 状态，并按稳定 reason 恢复或阻断。
11. 只有 promoted transaction 的最终 QA 成功后才清除该页脏状态。

## 9. 失效规则

| 变化 | 失效范围 | 文稿批准 |
|---|---|---|
| 整套品牌／主题 | 全部 visual briefs、锚点、SVG、视觉与整套 QA | 保留，前提是内容未变 |
| 锚点级艺术方向 | 受影响锚点及依赖正式页的 briefs、SVG、QA | 保留 |
| 单页层级／布局 | 该页 brief、SVG、视觉与整套 QA | 保留 |
| 单页 patch | 该页 SVG、视觉与整套 QA；brief 记录 defect | 保留 |
| 主张／来源／故事板 | 按现有最早阶段重入，全部视觉产物失效 | 重置为 pending |

## 10. 旧运行与缺 Registry 兼容

缺少 `visual-briefs/` 的 schema-v1 运行仍然可读取。若其有效 SVG 不需要修改，可以保持原状；当它进入新的锚点生成、正式页面生成或视觉修订时，必须先从已批准故事板、当前有效主题、`run.json.interaction_history`、当前 SVG 契约和 QA 规则重建缺失 brief，并补齐可验证的持久风格身份与 generation intent。无法从权威 artifact 唯一重建时返回 `prompt_snapshot_conflict`，不得从文案、目录、旧 SVG、未知预览或对话猜测。

registry 路径只有经 no-follow／`lstat` 确认为不存在时才能进入兼容 fallback；已存在但不安全、不可读或 malformed 的 registry 必须按对应稳定 reason 阻断，不能伪装成 missing。完整 fallback 仅允许三个内置 legacy seed，并要求三份 seed JSON 与三份 companion `*.redesign.md` 全部存在、身份匹配且模板有效；六个文件中任一个缺失或无效都使 fallback 不成立并返回 `registry_missing`。缺 registry 时不得发现 Canway 或其他 style pack，也不得只因所选 seed 的一对文件存在而部分回退。

registry 存在时，三个已知 legacy 条目缺 `redesign_prompt` 字段可确定性使用 `<entrypoint-stem>.redesign.md`；其他 legacy 或 style-pack 缺少 prompt 声明时返回 `prompt_field_missing`，声明目标缺失时返回 `prompt_file_missing`。旧运行中的有效 SVG 在没有视觉请求时可只读保留；下一次首次生成、`recompose` 或 fallback 必须使用当前风格 prompt 重新编译 generation prompt。

## 11. 视觉质量门

除现有 XML、安全区、碰撞、对比度和来源覆盖外，真实渲染 QA 增加：

1. **焦点**：3 秒内能够识别唯一主信息。
2. **扫描顺序**：第一、第二、第三阅读位置符合 brief。
3. **层级**：主信息在面积、字号、明暗或位置上明显强于次信息。
4. **字体**：形成标题、主命题、区块、正文、辅助和微标签等有意层级。
5. **语义色**：色彩分别承担事实、结论、风险、提案或状态，不是无差别装饰。
6. **卡片密度**：卡片只表达分组或层级，避免等权卡片墙。
7. **证据边界**：假设页显式区分已观察信号、不能证明的因果和可证伪验证。
8. **视觉债务**：页面没有因连续 patch 留下不一致的间距、形状、字号或局部母题。

任一质量问题不一定等同 XML 硬失败，但必须记录为具体 rendered issue，并触发 patch 或 recompose 分类，不能只写“继续优化”。

## 12. 错误处理

- brief 缺少必需章节、持久风格身份或 generation intent：停止生成；只能从唯一权威 owner 重建，无法唯一解释时记录 `prompt_snapshot_conflict`。
- 锁定内容与故事板不一致：停止并修正 brief；若主张本身变化则返回文稿阶段。
- 当前规则存在未消解冲突：停止并持久化冲突，不生成折中 SVG。
- registry／entrypoint／manifest／style asset／prompt 的路径、结构、身份、版本、读取或模板契约失败：写入 `run.json.visual_generation_blocker`，使用 2026-08-21 规范定义的单一稳定 reason，保持 slide dirty，不启动 generator、不覆盖 SVG，也不改用其他风格。
- blocker 恢复必须先重新验证同一 slide 的资源与 snapshots；prompt 已 durable 且 hash 匹配时只补交 transaction `compiled` 状态和 blocker 清除，否则重新编译。任何时刻只处理一个 active blocker。
- `patch` 请求实际涉及层级或构图：重新分类为 `recompose`，重新解析风格 prompt 并建立新 transaction。
- `recompose` 或首次生成仍沿用旧 SVG 几何，或 fresh generator 获得 compiled prompt 之外的旧 SVG／工作区写权限：视为流程失败。
- generator、候选写入／hash、SVG 契约、锁定内容、视觉 QA 或 final promotion 失败：以 transaction 的稳定 `failure_reason` 持久化；按唯一恢复 consumer 重试、进入 patch／deterministic fallback 或询问冲突，不能静默删除 transaction。
- 视觉渲染不可用：记录 `visual_qa: not_rendered`，不得声称视觉质量门通过。
- 旧运行信息或缺 registry fallback 文件集不完整：按第 10 节阻断，不依赖对话猜测，也不执行部分 fallback。

## 13. 测试策略

### 13.1 契约测试

验证：

- `SKILL.md` 在视觉生成前链接 visual brief 与风格 prompt resolver 规范。
- `visual-briefs/` 被定义为视觉阶段必需的权威输入，`generation-prompts/` 被定义为首次生成、`recompose` 与确定性回退的必需编译产物。
- brief 包含来源、持久风格身份、锁定内容、层级、构图、视觉系统、修订模式、generation intent 和输出质量章节。
- `patch` 不加载完整风格 prompt；其他生成分支必须使用持久风格 ID 解析模板并建立可恢复 transaction。
- 纯指令包未引入宿主专属工具名或运行时依赖。

### 13.2 状态归并测试

使用合成历史：

```text
visual-revision-1: 使用品牌蓝和标题竖条
visual-revision-2: 取消标题竖条
visual-revision-3: 采用层级 Bento
```

预期：

- 历史保留三条记录。
- 当前有效契约包含品牌蓝、无标题竖条和层级 Bento。
- 标题竖条只出现在废弃历史，不出现在生成 brief 的有效规则。

### 13.3 风格包与 Prompt 编译测试

快速验证：

- `assets/styles/registry.json` 可以解析，风格 ID 和中文显示名唯一；registry／manifest／legacy entrypoint 的身份、kind 与 containment 握手一致。
- `canway-midyear-review/manifest.json` 引用存在且包内安全的 `tokens`、`guidance` 与 `redesign_prompt`，内容版本为 `1.2.0`；不再断言 files 精确只有两键或版本为 `1.1.0`。
- 四个内置风格各有完整 prompt；模板 `STYLE_ID`、schema、hard-constraint markers 和十一个唯一占位符满足表面契约，Canway 专属视觉字面量不泄漏到共享 resolver 或三个 legacy prompt。
- 风格包目录仍不得包含单页成品 SVG、参考构图或固定区域图；`REDESIGN.md` 是完整生成指令模板，不是成品示例。
- resolver／hash oracle 覆盖安全路径、缺失资源、identity mismatch、完整缺-registry fallback、blocker、compiled prompt provenance、snapshot 失效和 generation transaction；这些静态测试不宣称真实宿主行为通过。
- Skill 可以按稳定 ID `canway-midyear-review` 或中文显示名“嘉为年中总结风格”选择该风格，但实际生成只使用 visual brief 已持久化的唯一 ID。

### 13.4 修订分支契约测试

使用静态合成夹具断言三条分支，不启动模型做耗时行为验收：

- 24 px 对齐修正：`patch`，契约要求读取当前 SVG 和完整 brief，且不加载完整风格 prompt。
- “重点不突出，使用新的参考图重组”：`recompose`，契约禁止把旧 SVG 作为几何底稿，并要求按持久风格 ID 编译 generation prompt 后启动 fresh generator。
- 把 12% 改为 27% 并更换来源：事实变更，契约要求重新进入文稿审查。
- 旧 schema-v1 已批准运行缺少 briefs 时仍可读取，并在下一次视觉生产前按权威 owner 补建 brief、风格身份与 generation intent；无法唯一重建则阻断。

### 13.5 验证时限与排除项

验证只运行本地 Python 契约测试和 SVG 静态检查，目标是快速确认修改后的 Skill 包结构、引用与核心分支正常。明确不执行 Claude Code／Codex 跨宿主现场运行、PowerPoint 人工导入、整套浏览器视觉验收、FY26 页面重生成或多轮模型行为测试。

### 13.6 安全与保密

所有新增夹具使用合成数据。共享 Skill、文档和测试不得包含 FY26 客户、交付、组织或项目材料。

## 14. 可扩展风格包

### 14.1 注册与兼容结构

新增统一注册表并保留现有平面 JSON 种子：

```text
skills/ppt-start/assets/styles/
├── registry.json
├── minimal-business.json
├── minimal-business.redesign.md
├── tech-dark.json
├── tech-dark.redesign.md
├── bold-editorial.json
├── bold-editorial.redesign.md
└── canway-midyear-review/
    ├── manifest.json
    ├── tokens.json
    ├── STYLE.md
    └── REDESIGN.md
```

`registry.json` 是新安装的风格发现入口，列出稳定 ID、中文显示名、资产类型和入口路径。三个 legacy seed 保留平面 JSON，并由 registry 的可选 `redesign_prompt` 字段或已知 `<entrypoint-stem>.redesign.md` companion 声明完整 prompt。目录式 style pack 的 manifest 在 `files` 中声明 `tokens`、`guidance` 和 `redesign_prompt`；Canway manifest schema 保持 1，当前内容版本为 `1.2.0`。缺 registry 只允许第 10 节定义的完整六文件 legacy fallback，不允许无条件按三个种子工作，也不能发现 style pack。

### 14.2 “嘉为年中总结风格”身份

- 稳定 ID：`canway-midyear-review`
- 中文显示名：`嘉为年中总结风格`
- 适用：SaaS、研发、交付、组织和管理层年中／年度汇报
- 不适用：营销海报、活动发布和重数据大屏
- 选择方式：用户明确给出稳定 ID 或中文显示名；未选择时不得自动替换其他主题

### 14.3 视觉令牌

- 画布：`#F5F8FC`
- 深色主卡：`#10233F`
- 品牌蓝：`#156BFF`
- 标题强调蓝：`#1E63FF`
- 天空蓝：`#65B7F9`
- AI／试点紫：`#8866FD`
- 主文字：`#0B1930`
- 次文字：`#52637B`
- 白色事实卡：`#FFFFFF`
- 边框：`#DCE9F8`

`tokens.json` 还定义标题、主命题、区块、正文、辅助和微标签的字体阶梯，以及圆角、描边、间距和单一轻阴影规则。关键决策内容继续满足全局可读性下限；微标签只能承载非关键索引或元信息。

### 14.4 设计语言

`STYLE.md` 固化：

- 单行结论标题和短语级蓝色强调。
- 每页一个明确焦点；复杂论证页允许一张深色主卡。
- 白卡表示事实，浅蓝表示证据边界或核心结论，紫色表示 AI、试点、高风险或失败分支。
- 主卡在面积、字号、明暗或位置上显著强于次卡；卡片密度目标为 40%–60%。
- 主卡可以嵌套 KPI 子卡形成二级层级。
- 每页最多一处轻阴影。
- 禁止左侧长蓝条、背景图片、渐变、等权卡片墙和机械复用同一版式。
- 根据内容选择论证、流程、时间箱、决策矩阵等构图。

### 14.5 风格自有 Prompt 与防同质化边界

风格身份继续由 tokens 与 `STYLE.md` 中的抽象规则表达：颜色、字体、间距、形状、语义角色和内容驱动的构图原则可以复用。每个风格另外拥有一份 `REDESIGN.md`（legacy 使用同级 `*.redesign.md`）作为可独立交给 fresh generator 的完整生成指令模板；它必须包含通用硬约束和该风格艺术方向，但不是成品示例、参考图、固定区域图或可复制页面。

风格包仍不得包含单页成品 SVG，也不得把某一页的区域、卡片数量、连接关系或阅读路径作为固定模板。每个 visual brief 必须从本页论证、流程、时间、比较或决策语义重新推导构图；页面语义与常用风格构图冲突时，由 brief 的 `视觉系统.exceptions` 明确覆盖。首次生成、`recompose` 与确定性回退将该 brief 编译进所选风格模板，Office-safe 能力由模板 hard constraints、生成 SVG 的通用契约与 QA 共同验证。

## 15. 影响文件

主要修改范围：

- `skills/ppt-start/SKILL.md`
- `skills/ppt-start/references/visual-brief-and-generation.md`（新增）
- `skills/ppt-start/references/redesign-prompt.md`
- `skills/ppt-start/references/design-system.md`
- `skills/ppt-start/references/layout-catalog.md`
- `skills/ppt-start/references/qa-and-revision.md`
- `skills/ppt-start/references/artifact-contract.md`
- `skills/ppt-start/references/interaction-protocol.md`
- `skills/ppt-start/references/workflow.md`
- `skills/ppt-start/assets/styles/registry.json`（新增）
- `skills/ppt-start/assets/styles/canway-midyear-review/manifest.json`（新增）
- `skills/ppt-start/assets/styles/canway-midyear-review/tokens.json`（新增）
- `skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`（新增）
- `skills/ppt-start/assets/styles/minimal-business.redesign.md`
- `skills/ppt-start/assets/styles/tech-dark.redesign.md`
- `skills/ppt-start/assets/styles/bold-editorial.redesign.md`
- `skills/ppt-start/assets/styles/canway-midyear-review/REDESIGN.md`
- `README.md`
- `docs/design.md`
- `docs/acceptance.md`
- `tests/test_visual_generation_contract.py`（新增）
- `tests/test_redesign_prompt_contract.py`
- 相关 workflow、interaction、asset 和 package contract tests
- 合成 visual revision、visual brief 和三分支修订夹具

## 16. 验收标准

1. 任一首次生成、`recompose` 或确定性回退页面都有自包含 brief、可验证的持久风格身份、风格自有完整模板和已持久化 compiled generation prompt；局部 `patch` 保持其独立输入边界。
2. 新宿主无需对话历史即可从 blocker、prompt provenance、snapshot 和 generation transaction 恢复同一锁定内容、当前视觉约束与操作 intent。
3. 后续决定能够显式覆盖旧规则；raw 历史 answer 和已废弃字段不会回流到 compiled prompt。
4. 广泛视觉反馈稳定分类为 `recompose`，局部 defect 稳定分类为 `patch`；首次生成、`recompose` 和确定性回退都按 brief 已持久化风格 ID 解析模板并使用 fresh generator。
5. 内容或来源变化仍触发独立文稿审查，不被视觉模式绕过。
6. 视觉 QA 同时检查文件正确性和焦点、阅读路径、层级、语义色及卡片密度；transaction 未 promoted 且最终 QA 未通过时不得清除 dirty。
7. 四个现有风格各自拥有完整 redesign prompt；Canway 由 manifest 声明 `REDESIGN.md`，内容版本为 `1.2.0`，registry／manifest／prompt identity 与安全 containment 一致。
8. 风格身份仍由 tokens 与抽象 `STYLE.md` 表达；完整 `REDESIGN.md` 是风格自有生成模板而非单页成品，风格包中不存在可被当作固定版式模仿的 SVG、参考构图或固定区域图。
9. 缺 registry 只对完整且全部有效的三 seed／三 companion prompt 文件集执行 legacy fallback；其他缺失、非法或冲突状态使用稳定 blocker reason，不静默换风格或部分回退。
10. 聚焦 package-contract 测试与完整本地测试通过：

```bash
python -m unittest tests.test_redesign_prompt_contract tests.test_style_packs tests.test_visual_generation_contract -v
python -m unittest discover -s tests -v
```

11. 静态测试只证明仓库文件契约与 oracle；Claude Code／Codex、fresh delegation、浏览器和 PowerPoint 行为在没有真实证据前保持 `PENDING`。
12. 共享 Skill 未引入运行时依赖、远程资源、宿主专属调用或内部 FY26 内容。
