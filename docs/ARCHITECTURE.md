# 架构与工作原理

本文面向想理解 PPT Pilot 内部机制的读者：编译范式、质量门、并发协议、修订模型与证据分级。使用方法见[用户指南](USER-GUIDE.md)，安装见[安装指南](INSTALL.md)，逐项验收台账见[验收文档](acceptance.md)。

## 总体架构

PPT Pilot 是纯指令的 Agent Skill 包，可移植运行于 Claude Code、OpenAI Codex 与 DeepSeek Harness，不强制依赖 MCP、SDK、Hook、后台服务或运行时软件包。仓库发布两个职责独立的 Skill：

- `ppt-start`：从主题/简报/资料/既有运行生成有证据支撑的 16:9 独立 SVG 演示；
- `ppt-editable`：只消费一个已完成的 `ppt-start` 运行，转换为递归分组、原生可编辑文本/形状的 PowerPoint，并完成结构/Office/视觉验证。

标准包结构（`skills/ppt-start/`）：

```text
skills/ppt-start/
├── SKILL.md                 # 精简编排与发现入口
├── references/              # 各阶段流程与契约（单一权威）
├── assets/styles/
│   ├── registry.json        # 风格发现注册表
│   └── <style-id>/          # style pack：manifest + tokens + STYLE.md + prompt.md
└── assets/examples/         # Office-safe SVG 示例
```

每个 style pack 的 `manifest.json` 声明机器可读资产（`files.tokens` / `files.guidance` / `files.prompt_template`）；`tokens.json`（schema 2）承载颜色/字体/间距/形状与结构化 `prompt_baseline`；`prompt.md` 是该风格**自带的完整生成指令模板**。所有可执行模板的 hard prefix/suffix 字节完全一致，只有 Step 2 的七条 closed typed 风格指令由同包 tokens 确定性变化。

## 核心范式：风格自带完整模板 + 单注入点

生成 Prompt 的编译范式是"**每个风格自带完整 prompt 模板，模板内嵌单一 `{{NARRATIVE}}` 注入点**"：

1. 从已批准故事板投影叙事、素材与事实值：叙事要点、显示素材，以及数字、单位、期间、限定词与因果组成的事实底线；
2. 每个可选择 `style_pack` 必须声明完整模板 `assets/styles/<style-id>/<files.prompt_template>`；缺字段 fail closed，仓库模板只作建包 authoring seed。在内存中把模板的**单一** `{{NARRATIVE}}` whole-line 注点替换为叙事要点；
3. 建包器把提取出的具体颜色、字体、间距、形状、构图与禁止母题静态物化进 `prompt.md`；运行时 `tokens.json.prompt_baseline` 只作为风格数据、QA 输入与 snapshot provenance，不投影进模板正文，也不另设第二个注入域；
4. 来源映射单独校验并留在故事板／coordinator／审查层；来源注解不得进入模板正文，prompt 只携带稳定非来源 `block_id`。generator 只能在唯一语义 `<g data-block-id>` 的精确属性值中临时回显每个 `block_id` 一次，禁止写入 text／tail／其他属性；coordinator 在 candidate 写入和 hash 前按冻结故事板完成 `block_id -> ordered source_ids` 关联、移除临时 block 属性，再写入 `data-source-id`／trace 机器元数据；任何映射缺失、未知、重复或泄漏均以 `fact_source_mismatch` 零 candidate 写入失败；
5. 持久化 `.ppt-pilot/generation-prompts/<slide-id>.md`，envelope `format` 精确为 `creative-brief-v1`：九字段 `## Snapshot metadata` + `## Compiled Prompt` 编译体，全文件只用工作区相对路径。

编译由确定性预检保护：拒绝旧 Role+S01 形式、`PROMPT_SCHEMA_VERSION`、遗留 `[[...]]` marker、注入的 ATX/Setext 标题、JSON 围栏、Unix 绝对路径与外部文件/工具指令。预检失败产生零 prompt/transaction/candidate/SVG 写入。

## 工作流与阶段

```text
brief -> research? -> outline -> storyboard -> manuscript_review
      -> theme -> anchor -> production -> qa -> complete
```

- **文稿审查是硬质量门**：`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md` 冻结后，优先委派全新独立子 Agent 只读审查；委派失败时在当前步骤执行正式 `inline_fallback`（声明"当前上下文降级审查，不具备独立上下文隔离"）。任一 `BLOCKER`／`HIGH` 未 `RESOLVED` 即阻断；`inline PASS` 与 subagent PASS 使用同一严格门，均可进入 `manuscript_approved`。subagent 与 inline 共同计入每 cycle 三轮上限。
- **执行策略**：`guided`（默认）在简报/大纲/锚点三个批准点各提一个直接问题；`auto` 仅显式指定时跳过可选问题，但用户权限与无安全默认值的决策仍会询问。`new`/`resume`/`revise` 是入口动作，不写入 `run.json.mode`。
- **交互持久化**：阻塞问题存 `run.json.pending_interaction`（含逐项效果、推荐理由与规范化决定），跨宿主可原样重放；等待期间 `stage` 不变。

## 并发生成协议（schema-v2）

能力协商在任何 durable 写入之前完成；没有 fresh isolation 时以 `generator_unavailable` 零写入停止。能力通过后按 **pointer-last** 顺序写 per-slide transactions、batch manifest，最后发布 `run.json.active_visual_generation_batch`：

- 默认 `batch_width: 4`（可配置 3）；并发或 durable lookup 缺失降为 width 1，非 Git 工作区不降级；
- 隔离任务只接收完整 `prompt_by_value`：fresh history、filesystem none、tools none、text-only；
- generator 与 per-slide validation 可并发，但 candidate/transaction/final 写入、visible blocker 与 pointer 只由 coordinator 按 `ordered_slide_ids` 串行提交；
- 每页请求预算固定 4 次（initial/recompose 1 + patch ≤2 + 确定性回退 1），每次派发输出一行进度说明；用尽即停，写 blocker；
- 页面只有在 transaction promoted、单页 QA 与整套 QA 都通过后才清除 dirty。

telemetry（compile/model/render/qa/promotion spans、DAG 关键路径、batch wall time）是非权威诊断：`telemetry_diagnostic_failed` 不能改变 correctness 或授权 promotion。

## 修订模型

编辑前先把请求唯一分类，并把已应用修订投影回其权威 owner（故事板拥有叙事/素材/事实/来源；`theme.json` 拥有风格身份与软风格基线）：

| 类别 | 适用 | 输入 | 审查 |
|---|---|---|---|
| `patch` | 保持构图的可测量局部 defect | 完整 direct-compile inputs + 当前 SVG + 一个精确 defect | 不重新审查 |
| `recompose` | 焦点/层级/布局/字体/语义色/品牌方向变化 | 重新编译 prompt，从空白构图生成；不接收旧 SVG | 不重新审查 |
| 事实/主张/来源/大纲/故事板变化 | 不属于视觉模式 | 返回最早受影响文稿阶段 | **必须重新审查** |

每页最多两次 `patch`，仍失败则确定性降级为单栏/双栏布局；回退后仍有硬检查失败即停止生产。

## Office-safe SVG 契约

1280×720 画布、64 px 安全边距、24 px 间距节奏、系统字体回退、显式 `<tspan>` 换行。圆角卡片用 `<path>` + `A` 圆弧（禁止 `rect rx/ry`）；每可见行一个 `text`、每 `text` 一个简单 `tspan`。禁止 `foreignObject`、脚本、动画、CSS import、远程资源与自动换行。宿主可渲染时执行视觉检查（3 秒焦点、扫描顺序、主次支配、字体阶梯、语义色等）；不可渲染时如实记录 `visual_qa: not_rendered`，不得冒充视觉通过。

## 交付链路

- `ppt-start` 完成后主动提示下一步可转可编辑 PowerPoint（见[用户指南](USER-GUIDE.md)）。
- `tools/deck-deliver.ps1`（可选伴随工具，不属于 Skill）：组装 `preview.html` 联系表、图片式 PPTX（COM 自动化，写入演讲者备注）与可选 PNG 导出；只新增 `delivery/`，不修改运行产物。
- `ppt-editable`：固定阶段序 `locate → validate → snapshot → recover → idempotency → dependencies → preflight → build → structural verify → capability → Office → visual compare → promotion → result`；结果状态 `PASS` / `GENERATED_UNVERIFIED` / `BLOCKED` / `FAILED_VERIFICATION`；永远保留已验证 final，不被未验证构建覆盖；只写 `delivery/editable/`，绝不改 `.ppt-pilot/run.json`。

## 测试与证据分级

```bash
python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v   # 聚焦
python -m unittest discover -s tests -v                                              # 完整
```

证据按类别严格区分：`static package` 只证明包结构、书面契约和 fixture oracle；`EVIDENCE_CLASS: DIAGNOSTIC` 只用于压力提示或诊断，不得当作宿主/浏览器/PowerPoint 验收；`deployment hash` 只证明部署文件与仓库源一致；`real host` 才能证明带版本、transcript 和运行目录的真实宿主行为。测试中的 resolver／hash oracle 不是运行时代码。结论以[验收台账](acceptance.md)中带日期的 `PASS`/`FAIL`/`NOT RUN`/`PENDING` 为准。
