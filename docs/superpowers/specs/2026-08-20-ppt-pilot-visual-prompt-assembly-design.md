# PPT Pilot 视觉提示组装机制设计

- **日期**：2026-08-20
- **状态**：设计已逐节批准
- **范围**：仅改造 PPT Pilot 通用机制；不修改或重新生成 FY26 年中总结的正式 SVG

## 1. 背景与问题

PPT Pilot 是纯指令型 Agent Skill，没有独立运行时或确定性的 prompt-builder。现有机制能够持久化文稿、审查、主题、SVG 和 QA 状态，但视觉修订可能只在当前对话或临时预览中生效。后续宿主恢复时仍可能读取旧 `theme.json`，导致已经被新决定覆盖的规则重新出现。

另一个问题是视觉修订没有区分局部缺陷修补和完整页面重组。“重点不突出”“更高级”“改变卡片层级”等请求可能继续沿用旧 SVG 几何，只做局部修改。模型因此能够满足每一条局部要求，却没有重新执行内容优先级、焦点、阅读路径和布局选择，产生视觉债务。

本设计将一次性完整 prompt 中有效的设计过程固化为文件契约：每页先形成一份自包含视觉 brief，再生成或修订 SVG。

## 2. 目标

1. 每次视觉生成都使用完整、当前、无冲突的设计上下文，不依赖对话记忆。
2. 把已批准内容边界、主题、用户视觉修订、布局和质量要求组装到逐页文件中。
3. 明确区分 `patch` 与 `recompose`，防止广泛设计请求退化为局部修补。
4. 让 Claude Code 与 Codex 能仅凭运行目录恢复同一视觉意图。
5. 保留 PPT Pilot 的纯指令、无运行时依赖和 Office-safe SVG 架构。
6. 使用合成夹具验证状态归并与修订行为，不把内部演示材料写入共享测试。
7. 把已确认的管理汇报视觉语言固化为可选择的“嘉为年中总结风格”，并建立可继续扩展新风格的包结构。

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

在 `theme` 阶段内部增加视觉上下文组装：

```text
approved storyboard
+ active theme
+ authoritative visual revision history
+ SVG and QA contracts
= active visual contract
= visual-briefs/<slide-id>.md
```

`visual-briefs/<slide-id>.md` 是该页正式视觉生成的唯一入口。锚点和正式页面都必须先有有效 brief。最终 SVG 是生成结果，不再承担主题、构图或修订历史的权威状态。

### 4.1 组件边界

| 组件 | 职责 | 权威性 |
|---|---|---|
| 已批准故事板 | 内容、主张、限定条件、来源与视觉意图 | 文稿权威 |
| `run.json.interaction_history` | 用户视觉决定和覆盖关系的完整历史 | 修订权威 |
| `theme.json` | 整套演示当前有效的设计令牌和主题决定镜像 | 主题镜像 |
| `visual-briefs/Sxx.md` | 已消解冲突的逐页自包含生成包 | 页面视觉输入 |
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

1. 读取 `run.json` 并验证文稿批准状态。
2. 读取已批准故事板、当前 `theme.json` 和权威视觉修订历史。
3. 归并当前有效契约并显式排除废弃规则。
4. 创建或更新逐页视觉 brief。
5. 验证 brief 完整性与内部一致性。
6. 先压缩和排序信息，再确定焦点和阅读顺序。
7. 选择语义布局并分配面积、字体和语义色。
8. 按 `patch` 或 `recompose` 规则生成 SVG。
9. 与锁定内容、来源和 forbidden claims 逐项核对。
10. 执行结构硬检查和真实渲染 QA。
11. 只有验证成功后才清除该页脏状态。

## 9. 失效规则

| 变化 | 失效范围 | 文稿批准 |
|---|---|---|
| 整套品牌／主题 | 全部 visual briefs、锚点、SVG、视觉与整套 QA | 保留，前提是内容未变 |
| 锚点级艺术方向 | 受影响锚点及依赖正式页的 briefs、SVG、QA | 保留 |
| 单页层级／布局 | 该页 brief、SVG、视觉与整套 QA | 保留 |
| 单页 patch | 该页 SVG、视觉与整套 QA；brief 记录 defect | 保留 |
| 主张／来源／故事板 | 按现有最早阶段重入，全部视觉产物失效 | 重置为 pending |

## 10. 旧运行兼容

缺少 `visual-briefs/` 的 schema-v1 运行仍然可读取。若其有效 SVG 不需要修改，可以保持原状；当它进入新的锚点生成、正式页面生成或视觉修订时，必须先从以下内容合成缺失 brief：

- 已批准故事板
- 当前有效主题
- `run.json.interaction_history`
- 当前 SVG 契约和 QA 规则

如果旧运行没有权威视觉历史，只能使用可验证的主题与故事板；不得从未知的旧预览或对话中猜测决定。若现有主题内部矛盾，则停止并报告冲突。

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

- brief 缺少必需章节：停止生成，补齐 brief。
- 锁定内容与故事板不一致：停止并修正 brief；若主张本身变化则返回文稿阶段。
- 当前规则存在未消解冲突：停止并持久化冲突，不生成折中 SVG。
- `patch` 请求实际涉及层级或构图：重新分类为 `recompose`。
- `recompose` 仍沿用旧 SVG 几何：视为流程失败，重新从 brief 生成。
- 视觉渲染不可用：记录 `visual_qa: not_rendered`，不得声称视觉质量门通过。
- 旧运行没有足够信息合成 brief：停止并披露缺失项，不依赖对话猜测。

## 13. 测试策略

### 13.1 契约测试

验证：

- `SKILL.md` 在视觉生成前链接本规范。
- `visual-briefs/` 被定义为视觉阶段必需派生产物。
- brief 包含来源、锁定内容、层级、构图、视觉系统、修订模式和输出质量章节。
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

### 13.3 风格包测试

快速验证：

- `assets/styles/registry.json` 可以解析，风格 ID 和中文显示名唯一。
- `canway-midyear-review/manifest.json` 引用的 tokens、设计说明和参考 SVG 均存在。
- 颜色、字体、间距和形状令牌符合风格包 schema。
- 合成 `reference.svg` 通过现有 XML、Office-safe 元素、1280×720 画布、安全区和字体检查。
- Skill 可以按稳定 ID `canway-midyear-review` 或中文显示名“嘉为年中总结风格”选择该风格。

### 13.4 修订分支契约测试

使用静态合成夹具断言三条分支，不启动模型做耗时行为验收：

- 24 px 对齐修正：`patch`，契约要求读取当前 SVG 和完整 brief。
- “重点不突出，使用新的参考图重组”：`recompose`，契约禁止把旧 SVG 作为几何底稿。
- 把 12% 改为 27% 并更换来源：事实变更，契约要求重新进入文稿审查。
- 旧 schema-v1 已批准运行缺少 briefs 时仍可读取，并在下一次视觉生产前补建 brief。

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
├── tech-dark.json
├── bold-editorial.json
└── canway-midyear-review/
    ├── manifest.json
    ├── tokens.json
    ├── STYLE.md
    └── reference.svg
```

`registry.json` 是新安装的风格发现入口，列出稳定 ID、中文显示名、资产类型和入口路径。现有三个 JSON 作为 legacy seed 继续使用；新风格统一使用目录式 style pack。缺少 registry 的旧安装仍按现有三个种子工作。

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

### 14.5 合成参考 SVG

`reference.svg` 使用无客户、无项目、无 FY26 数据的管理假设页，展示浅灰蓝画布、短语级标题强调、深色中央主卡、白色事实卡、浅蓝证据边界、紫色有界试点、嵌套 KPI、编号与完整字体阶梯。它必须遵守现有 Office-safe SVG 契约，并只作为风格参考，不能覆盖具体页面视觉 brief 的内容语义。

## 15. 影响文件

主要修改范围：

- `skills/ppt-start/SKILL.md`
- `skills/ppt-start/references/visual-brief-and-generation.md`（新增）
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
- `skills/ppt-start/assets/styles/canway-midyear-review/reference.svg`（新增）
- `README.md`
- `docs/design.md`
- `docs/acceptance.md`
- `tests/test_visual_generation_contract.py`（新增）
- 相关 workflow、interaction、asset 和 package contract tests
- 合成 visual revision、visual brief 和三分支修订夹具

## 16. 验收标准

1. 任一新生成或视觉修订页面都有自包含 brief。
2. 新宿主无需对话历史即可恢复同一锁定内容和当前有效视觉约束。
3. 后续决定能够显式覆盖旧规则，旧规则不会回流到生成 prompt。
4. 广泛视觉反馈稳定分类为 `recompose`，局部 defect 稳定分类为 `patch`。
5. 内容或来源变化仍触发独立文稿审查，不被视觉模式绕过。
6. 视觉 QA 同时检查文件正确性和焦点、阅读路径、层级、语义色及卡片密度。
7. PPT Pilot 可以按 `canway-midyear-review` 或“嘉为年中总结风格”发现并选择完整风格包。
8. 风格包的合成参考 SVG 通过 Office-safe、画布、安全区和字体静态检查。
9. 快速本地测试通过：

```bash
python -m unittest discover -s tests -v
```

10. 验证不依赖跨宿主现场运行、PowerPoint 人工导入、整套浏览器检查或 FY26 页面重生成。
11. 共享 Skill 未引入运行时依赖、远程资源、宿主专属调用或内部 FY26 内容。
