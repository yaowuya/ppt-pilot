# 📊 PPT Pilot

> 你说清目标，AI 把证据、叙事和设计整理成独立 SVG；需要时再转换为可编辑 PowerPoint。

PPT Pilot 提供三个可安装 Skill：

| Skill | 用途 |
|---|---|
| `ppt-start` | 从主题、资料或既有运行制作证据可追溯的 16:9 SVG 演示文稿 |
| `ppt-editable` | 将 complete 或明确 partial 的 SVG 运行转换为原生可编辑 PowerPoint |
| `ppt-style-extract` | 从模板 PPT、参考图或风格描述制作可复用 style pack |

核心工作流由 AI 协调。`.ppt-pilot/run.json` 是跨回合状态证据，不是 Python 状态机；保留脚本只处理显式 SVG/PPTX 输入。脚本缺失、环境不兼容或内部失败不会锁死阶段、耗尽页面 attempts 或阻止独立页面继续。

## 安装

```bash
git clone https://github.com/yaowuya/ppt-pilot.git
cd ppt-pilot
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

更新器同步 `ppt-start`、`ppt-editable`、`ppt-style-extract` 到已选择的 Claude Code、Codex 和 DeepSeek Harness discovery scope；Claude Code 还会安装 `hosts/claude-code/agents/ppt-svg-generator.md`。新增／更新 Skill 或 Agent 后重新开启会话。

只更新 DeepSeek 插件副本：

```bash
powershell -ExecutionPolicy Bypass -File tools/install-deepseek-plugin.ps1
```

完整参数见 [安装指南](docs/INSTALL.md)。

## 开始

Claude Code：

```text
/ppt-start
请根据 inputs/ 中的资料制作一份 10 页中文策略演示，guided 模式。
```

Codex：

```text
$ppt-start
```

> 如果宿主使用的命令名不同，以实际安装后的 Skill discovery 为准；Skill 本身是宿主中立的。

执行策略：

- `guided`（默认）：简报、大纲、锚点各需一次明确批准；
- `auto`：必须显式指定，省略可选批准，但不省略权限问题和质量门；
- `resume`：读取既有状态原位继续；
- `revise`：只使受影响阶段／页面变脏，不重建运行。

## 工作流

```text
简报/研究 → 大纲/故事板 → 文稿审查 → 主题 → 锚点 → 正式页面 → QA
                                                          ↓
                                           complete | partial | failed
```

1. **简报与研究**：明确受众、行动、证据和保密边界；
2. **大纲与故事板**：冻结每页结论、精确文案、指标、限定、来源和布局意图；
3. **文稿审查**：未解决的 `BLOCKER`／`HIGH` 阻止视觉生产；
4. **主题与锚点**：选择已验证 style pack，用封面和最难内容页验证方向；
5. **逐页生成**：把每页完整冻结 Prompt 按值交给 fresh-context generator；Claude Code 使用当前会话已安装的 Agent，无需登录 local Claude CLI。若宿主能力或安全 Git bootstrap 不可用，AI 只记录该页 `generator_unavailable` 并继续独立页面；详细边界由 [生成参考](skills/ppt-start/references/visual-brief-and-generation.md) 定义；
6. **QA**：结构、来源、视觉渲染和 Office 能力分别记录，不互相冒充；
7. **交付**：全部页面 promoted 才是 complete；有成功页且其余有失败／skip 证据才是 partial。

详情见 [可继续推进的工作流](docs/RESILIENT-WORKFLOW.md) 与 [架构](docs/ARCHITECTURE.md)。

## 工具不会控制流程

`ppt-start/scripts/` 只保留两项公开无状态工具：

```bash
python skills/ppt-start/scripts/svg_tool.py --help
```

```bash
python skills/ppt-start/scripts/ppt_source_intake.py --help
```

工具结果：

- `PASS`：操作成功；
- `INVALID`：确定性证明该输入产物无效，只影响相应页面／产物；
- `UNAVAILABLE`：工具自身不可用，AI 记录降级并直接检查，stage 和 attempts 不变。

只有真实 generator 调用增加页面 attempts。工具不能读写 `run.json`、安排任务、重试或应用用户答案。

## 运行产物

```text
ppt-output/<deck-id>/
├── 大纲.md
├── slides/S01.svg ...
└── .ppt-pilot/
    ├── run.json
    ├── 简报.md 研究.md 来源.md 故事板.md 文稿审查.md
    ├── theme.json 质量检查报告.md
    ├── generation-prompts/
    └── samples/
```

状态恢复顺序是：`pending_interaction` → 共享一致性 → 最早未完成阶段／dirty 页面。旧 transaction/batch/dashboard 字段保留为历史证据，但不再执行。

## 可编辑 PowerPoint

Finalized SVG 运行可调用 `ppt-editable`：

```bash
python skills/ppt-editable/scripts/svg_to_editable_pptx.py --run-dir ppt-output/<deck-id> --json
```

- `PASS`：结构、Office 和视觉验证通过；
- `GENERATED_UNVERIFIED`：已生成原生可编辑候选，但 Office/Pillow 未验证；
- `BLOCKED`／`FAILED_VERIFICATION`：不发布新的权威 deck。

AI-state complete/partial 直接从故事板和 `slides` 页面记录选择；不要求旧 transaction/batch。旧 explicit delivery 仍由独立 legacy adapter 严格验证。Editable 失败只影响这项可选交付，不反向改写 SVG 状态。

仓库可选伴随工具 `tools/deck-deliver.ps1` 可以生成静态预览和图片式 PPTX；它不是 Skill 工作流 owner。它只增加精确的 companion 产物：`preview.html`、`delivery/delivery-result.json`、可选的 `delivery/<deck-id>.pptx` 与 `delivery/png/S<id>.png`，这些不改写 SVG 状态，也不会阻断后续 `ppt-editable`；其他运行目录代码／未知交付文件仍由 firewall 拒绝。

## 风格

内置：

- `jiawei-product`（嘉为产品，默认）；
- `canway-midyear-review`（嘉为年中总结风格）。

自定义品牌使用 `ppt-style-extract` 创建新的 immutable style pack，不直接改写已注册 pack。

## 机器来源 ID

内部 `SRC-<digits>` 只允许出现在机器 metadata：`.ppt-pilot/来源.md`、冻结 source map、final SVG 的 `data-source-id` 或 PowerPoint trace metadata。它绝不出现在可见 SVG/PPT 文字。Generator 只接收临时 block ID，finalize 后移除 block ID 并加入机器 source ID。

## 开发验证

聚焦：

```bash
python -B -m unittest tests.test_svg_tool tests.test_ai_workflow_contract tests.test_ppt_editable_orchestrator -v
```

完整：

```bash
python -B -m unittest discover -s tests -v
```

自动化测试证明静态契约和本地工具行为；真实宿主生成、浏览器渲染和 Office 导入必须有实际运行证据，不能用静态测试冒充。

## 文档

- [用户指南](docs/USER-GUIDE.md)
- [安装指南](docs/INSTALL.md)
- [架构](docs/ARCHITECTURE.md)
- [设计原则](docs/design.md)
- [验收边界](docs/acceptance.md)
- [Style Extract 设计](docs/style-extract-design.md)
