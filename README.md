# PPT Pilot

PPT Pilot 是一个可同时用于 Claude Code、OpenAI Codex 与 DeepSeek Harness 的可移植 Agent Skill 包：`ppt-start` 生成有证据支撑的 16:9 独立 SVG 演示；`ppt-editable` 把完成运行转换为递归分组、原生可编辑文本/形状的 PowerPoint。Skill 本体纯指令，不强制依赖 MCP、SDK、Hook、后台服务或运行时软件包；可选网络研究默认不启用，机密内容默认不出网。PPT Pilot 不保证所有 Office 版本都能一致导入，也不保证转换后每个元素都完全可编辑；能力不足时如实披露，不冒充验证通过。

## 效果示例

同一套已批准故事板，由两个内置风格包直接编译生成（示例来自真实运行，含客户名称与人名的页面未收录）：

**嘉为产品风格 `jiawei-product`**

<p align="center">
  <img src="docs/assets/showcase/jiawei-s01-cover.svg" alt="嘉为产品风格 · 封面" width="32%">
  <img src="docs/assets/showcase/jiawei-s09-content.svg" alt="嘉为产品风格 · 内容页" width="32%">
  <img src="docs/assets/showcase/jiawei-s12-closing.svg" alt="嘉为产品风格 · 收尾页" width="32%">
</p>

**嘉为年中总结风格 `canway-midyear-review`**

<p align="center">
  <img src="docs/assets/showcase/canway-s01-cover.svg" alt="嘉为年中总结风格 · 封面" width="32%">
  <img src="docs/assets/showcase/canway-s09-content.svg" alt="嘉为年中总结风格 · 内容页" width="32%">
  <img src="docs/assets/showcase/canway-s12-closing.svg" alt="嘉为年中总结风格 · 收尾页" width="32%">
</p>

## 快速开始

技能启动标识：`ppt-start`、`ppt-editable`

| 宿主 | 用户级安装 | 项目级安装 | 启动命令 |
|---|---|---|---|
| Claude Code | `~/.claude/skills/ppt-start/` | `.claude/skills/ppt-start/` | `/ppt-start` |
| Codex | `$HOME/.agents/skills/ppt-start/` | `.agents/skills/ppt-start/` | `$ppt-start` |
| DeepSeek Harness | `$HOME/.agents/plugins/plugins/ppt-pilot/` | — | `ppt-start` |

一键安装/更新三宿主（旧版按 Skill ID 自动备份）：

```bash
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

手动安装时用复制或符号链接把完整的 `skills/ppt-start/` 与 `skills/ppt-editable/` 放入上表路径；不要拆分任一 Skill 的 `SKILL.md`、`references/`、`assets/` 或 `scripts/`。仅需单独更新 DeepSeek 时运行 `tools/install-deepseek-plugin.ps1`；逐宿主命令与插件细节见[安装指南](docs/INSTALL.md)。

一条典型请求：

```text
/ppt-start
请根据 inputs/ 中的资料制作一份 10 页中文策略演示文稿，使用 guided 模式。
```

执行策略：新运行未显式指定策略时默认 `guided`，在简报、大纲和锚点页逐步征求批准；`auto` 只有显式指定才使用，跳过可选问题但保留全部硬质量门。已完成运行支持 `resume` 续跑与 `revise` 定向修订；`resume` 先按 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > active_visual_generation_batch > stage scan` 顺序恢复 durable 状态，读取 `run.json`（含 `run.json.manuscript_review.latest_report`）并保留既有执行策略，不重算已批准上游。交互协议：技能先检查请求与工作区、已有答案不重复问，剩余决策按依赖顺序一次只提出一个实质性问题，有限选择给出 2–4 个互斥选项与推荐理由；推荐不是确认，回答前不推进下游。完整上手流程（含拿到可编辑 PPT 的最后一步）见 **[用户使用手册](docs/USER-GUIDE.md)**。

## 工作流一览

```text
简报/研究 → 大纲+故事板 → 文稿审查（硬质量门）→ 主题/风格包选择
  → 逐页编译生成（schema-v2 并发批次）→ 单页 QA + 整套 QA → complete
  → （可选）ppt-editable 转原生可编辑 PPTX ／ deck-deliver 组装预览与交付
```

活动视觉路径是**故事板 + `theme.json` 直接编译**：读取所选风格包自带的完整生成模板（`assets/styles/<style-id>/<files.prompt_template>`；未声明时兜底仓库模板），把已批准叙事注入其单一 `{{NARRATIVE}}` whole-line 注点，编译 byte-exact `creative-brief-v1` Prompt，完成无副作用 preflight 与宿主能力协商；早期 `[[CANONICAL_NARRATIVE_BULLETS]]`／`[[STYLE_BASELINE]]` 双 marker 协议已废弃为迁移历史。能力通过后以 pointer-last 顺序写 schema-v2 per-slide transactions、batch manifest 与 `run.json.active_visual_generation_batch`，以 `prompt_by_value` 向 fresh isolated generator 派发，默认 `batch_width: 4`（缺并发或 durable lookup 时 width 1，非 Git 不降级）；generator 与每页 validation 可并发，coordinator 按 `ordered_slide_ids` 串行提交 candidate/final、visible blocker 与 pointer。

风格经 `assets/styles/registry.json` 发现，当前内置五个 style pack：`canway-midyear-review`（嘉为年中总结风格，manifest `1.3.0`）、`jiawei-product`、`minimal-business`、`tech-dark`、`bold-editorial`。

内部 `SRC-<digits>` 只保留在 `data-source-id`／trace 机器元数据，可见文字出现即以 `fact_source_mismatch` 硬失败；telemetry 仅作诊断，`telemetry_diagnostic_failed` 不改变任何 correctness 结论。

## 运行目录与产物

所有运行产物写入当前工作区 `ppt-output/<deck-id>/`：

```text
ppt-output/<deck-id>/
├── 大纲.md          # 用户唯一需要亲自查看的内容，含每页排版逻辑
├── slides/          # 最终独立 SVG 页面
└── .ppt-pilot/      # 内部过程产物（用户无需查看）
    ├── run.json
    ├── 简报.md / 研究.md / 来源.md
    ├── 故事板.md / 文稿审查.md
    ├── theme.json / 质量检查报告.md
    ├── generation-prompts/<slide-id>.md
    ├── visual-generation-transactions/<slide-id>-<tx64>.json
    ├── visual-generation-batches/<batch-id>.json
    └── samples/
```

状态以 `.ppt-pilot/run.json` 为准。这些文件构成跨宿主交接接口：另一个受支持宿主无需对话历史即可 `resume` 运行。

## 文稿审查是硬质量门

`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md` 冻结后，优先委派全新独立子 Agent（独立子 agent 只读审查五文件）；启动或结果归因失败时，当前步骤执行正式 `inline_fallback`，报告必须声明"当前上下文降级审查，不具备独立上下文隔离"。inline PASS 与独立审查通过同一严格质量门，均可进入 `manuscript_approved`；任一 `BLOCKER`／`HIGH` 问题未 `RESOLVED` 都阻断（`OPEN` 与阻断级 `ACCEPTED_RISK` 亦然）；subagent 与 inline 轮次共同计入每 cycle 三轮上限，只有冻结输入不可读等极端情况才使用 legacy 兼容的 `review_unavailable`。修订请求先分类：`patch` 修一个可测量局部缺陷，`recompose` 整页重构，事实／来源／大纲／故事板变化必须重新进行文稿审查。

## 完成后的交付选择

- **只要 SVG / 预览**：直接使用 `slides/`，或运行 `tools/deck-deliver.ps1` 生成 `preview.html` 联系表、可选 1280×720 PNG 与图片式 PPTX + 演讲者备注；
- **要原生可编辑 PowerPoint**：运行完成时插件会主动提示——调用 `ppt-editable` 技能，得到 `delivery/editable/<deck-id>-editable.pptx`；它自带结构/Office/视觉验证与 `PASS`／`GENERATED_UNVERIFIED`／`BLOCKED`／`FAILED_VERIFICATION` 结果状态，已验证旧版永不被未验证构建覆盖。

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/USER-GUIDE.md](docs/USER-GUIDE.md) | 用户使用手册：从发起到拿到可编辑 PPT 的完整操作指引 |
| [docs/INSTALL.md](docs/INSTALL.md) | 安装指南：逐宿主复制/符号链接、DeepSeek 插件、一键更新 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与工作原理：编译范式、质量门、并发协议、修订模型 |
| [docs/design.md](docs/design.md) | MVP 设计文档：产品原则、共享 Skill 架构、验收标准 |
| [docs/acceptance.md](docs/acceptance.md) | 验收台账与证据分级 |
| [skills/ppt-start/SKILL.md](skills/ppt-start/SKILL.md) | ppt-start 运行时契约入口 |
| [skills/ppt-editable/SKILL.md](skills/ppt-editable/SKILL.md) | ppt-editable 转换契约入口 |

## 开发验证

聚焦命令：

```bash
python -m unittest tests.test_skill_package tests.test_redesign_prompt_contract -v
```

完整命令：

```bash
python -m unittest discover -s tests -v
```

自动化测试只证明包结构、书面契约与 fixture oracle，不能证明真实宿主行为、浏览器渲染或 PowerPoint 导入；证据分级与人工验收台账见[验收文档](docs/acceptance.md)。
