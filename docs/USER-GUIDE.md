# PPT Pilot 用户指南

## 1. 选择任务

- 制作／恢复 SVG 演示：`ppt-start`；
- 把 finalized SVG 转成原生可编辑 PowerPoint：`ppt-editable`；
- 从模板／参考图／风格描述制作 style pack：`ppt-style-extract`。

安装见 [INSTALL.md](INSTALL.md)。

## 2. 发起演示

在支持 Skill 的宿主中调用 `ppt-start`，自然语言描述主题、受众、页数、资料目录和模式。例如：

```text
请根据 inputs/ 中资料制作 10 页中文策略演示，guided 模式。
```

- `guided` 默认在简报、大纲和锚点等待明确批准；
- `auto` 只有明确指定才启用；
- `resume` 原位恢复，不重建运行；
- `revise` 只重做受影响内容／页面。

推荐不是确认。AI 提问后会先把问题写入 `pending_interaction`，等你回答后直接应用，不需要额外命令。

## 3. 你会看到的步骤

1. **简报／研究**：明确受众、行动、证据、保密和未核验项；
2. **大纲／故事板**：冻结每页结论、文案、指标、限定、来源和布局意图；
3. **文稿审查**：未解决 `BLOCKER`／`HIGH` 不进入设计；
4. **主题／锚点**：选择 style pack，用两页样例验证方向；
5. **逐页 SVG**：每页完整 Prompt 交给 fresh-context generator；Claude Code 使用当前会话的已安装 Agent，不需要登录 local Claude CLI。若宿主无法安全启动 generator，AI 记录该页 `generator_unavailable` 并继续其他独立页面；
6. **QA**：结构、来源、视觉和 Office 分别记录；
7. **交付结论**：`complete`、`partial` 或 `failed`。

普通页面失败不会停止其他独立页面。首次失败后最多一次明确 retry/recompose；再次失败时 AI 询问修复、skip 或停止。Skip 保留原失败证据，不重置 attempts。

## 4. 工具降级

工具脚本可以帮助提取／校验，但不控制流程：

- `PASS`：工具成功；
- `INVALID`：输入产物确有错误，只影响该页；
- `UNAVAILABLE`：工具自身不可用，AI 记录降级并继续直接检查，stage 和 attempts 不变。

没有真实渲染时报告 `not_rendered`，没有 Office 实测时报告 `not_verified`。这些状态不能冒充 PASS，也不会因为工具缺失而卡死整套演示。

## 5. 输出

```text
ppt-output/<deck-id>/
├── 大纲.md
├── slides/*.svg
└── .ppt-pilot/
    ├── run.json
    ├── 简报.md 研究.md 来源.md 故事板.md 文稿审查.md
    ├── theme.json 质量检查报告.md
    └── generation-prompts/ samples/
```

`大纲.md` 是主要审阅入口；`slides/` 是正式页面；`.ppt-pilot/` 是可恢复证据。

## 6. 继续或修改

- “继续”：AI 读取 pending interaction、共享一致性和最早未完成／dirty 项；
- “修改 S05 的布局”：只使 S05 视觉变脏；
- “修改数字／来源／核心结论”：返回内容阶段并重新审稿；
- “跳过 S05，继续”：S05 记为 skipped，独立页面继续；
- “重试 S05”：只有真实 generator 再调用才增加 attempts。

旧运行中的 transaction/batch/dashboard 字段保留为历史证据，不再启动旧状态机。

## 7. 可编辑 PowerPoint

Finalized complete 或 partial 运行可调用 `ppt-editable`：

```bash
python skills/ppt-editable/scripts/svg_to_editable_pptx.py --run-dir ppt-output/<deck-id> --json
```

`--skip-office` 可在 Office 不可用／不允许时生成 `GENERATED_UNVERIFIED` 候选。可编辑转换失败只影响该交付，不改变 SVG complete/partial 状态。

新 AI-state 运行直接从故事板和 `slides` 选页；旧 explicit delivery 继续严格验证其历史证据。

## 8. 安全与来源

内部 `SRC-<digits>` 只用于机器 metadata：来源台账、冻结 source map、final SVG `data-source-id` 和 PowerPoint trace；不能显示在页面文字。机密资料默认离线；联网研究或敏感派生查询需要明确授权。任何来源、数字、日期或核验结果都不得虚构。
