# 安装指南

三个 Skill 使用同一 descriptor 流程安装；`ppt-start`、`ppt-editable` 与 `ppt-style-extract` 必须成对安装，任一 Skill 的 `SKILL.md`、`references/`、`assets/`、`scripts/` 都不可拆分。技能启动标识：`ppt-start`、`ppt-editable`、`ppt-style-extract`。

## 一键安装 / 更新三宿主（推荐）

在仓库根目录的本机终端运行：

```bash
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

脚本同时更新：

1. DeepSeek Harness 插件市场（调用 `tools/install-deepseek-plugin.ps1`）；
2. Claude Code 用户级技能 `~/.claude/skills/` 与 SVG Agent `~/.claude/agents/ppt-svg-generator.md`；
3. 共享用户级技能 `$HOME/.agents/skills/`（Codex 与 DSH 都可能发现此路径）。

安装器对 source inventory、staging copy 与 digest 使用同一过滤规则，排除 `__pycache__`、`.pyc`、`.pyo` 和测试／构建缓存；每个目标先 staging 校验再备份替换。Skill 备份位于扫描根外的 `skill-backups/`，Agent 备份位于 `agent-backups/`。输出列出实际 path、文件数和 digest。多目标混合结果返回非零 `PARTIAL_FAILURE`，并列出 `updated`、`rolled_back`、`failed`，不会声称全部完成。

可选参数：`-SkipDeepSeek` / `-SkipClaudeCode` / `-SkipCodex` 跳过对应用户宿主；`-ClaudeSkillsRoot` / `-ClaudeAgentsRoot` / `-CodexSkillsRoot` / `-MarketplaceRoot` 覆盖默认路径；`-CodexPluginRoot <plugin-root>` 只刷新该物理插件的 `skills/` 并保留无关内容；`-ProjectRoot <path[]>` 增加项目安装目标。`RepoRoot` 与每个额外项目中已存在的 `.agents/skills`／`.claude/skills` 默认自动刷新；刷新 Claude project Skill 时同时创建／刷新 `.claude/agents/ppt-svg-generator.md`。没有相关 discovery root 的额外项目会跳过而不创建 scope。旧 `-ProjectClaude` / `-ProjectCodex` 保持参数兼容，但已有仓库 scope 不再依赖它们。

推荐在仓库根目录从 PowerShell 直接调用（数组不会被 `powershell.exe -File` 折叠成单一字符串；用户目录由环境提供）：

```powershell
$pptRepoRoot = (Get-Location).Path
$pptPluginRoot = Join-Path $env:USERPROFILE '.codex/plugins/cache/personal/ppt-pilot/local'
& (Join-Path $pptRepoRoot 'tools/update-hosts.ps1') `
  -RepoRoot $pptRepoRoot `
  -CodexPluginRoot $pptPluginRoot `
  -ProjectRoot @($pptRepoRoot)
```

如需更新额外项目，把该项目的真实绝对路径加入 `-ProjectRoot` 数组；不要照抄其他机器的路径。上例的 Codex 插件缓存位置也应与当前机器实际安装位置核对。

`RepoRoot` 的 `skills/` 是不可变 source；同一仓库内已存在的 discovery scopes 是独立安装目标，并会默认刷新。`ProjectRoot` 与 `RepoRoot` 去重。

实时进度面板随 ppt-start 的 `scripts/` 和 `assets/dashboard/` 自动安装，需 Python 3.9+ 标准库。使用方法见[实时面板](LIVE-DASHBOARD.md)。项目级副本覆盖用户级 Skill 时，也应同步该副本后重新开启会话。

仅需单独更新 DeepSeek 时：

```bash
powershell -ExecutionPolicy Bypass -File tools/install-deepseek-plugin.ps1
```

单独安装除插件目录外，还刷新 `MarketplaceRoot` 父目录的 `skills/` 下**已存在**的三个 PPT Skill 副本；默认即 `$HOME/.agents/skills/`，不创建缺失的共享根／Skill，不修改无关技能。自定义 `MarketplaceRoot` 时只检查其对应兄弟目录，不暗中写真实用户目录。未知别名目录声明同名 Skill 时，在任何安装写入前报告具体冲突路径；共享目标失败会返回非零 `PARTIAL_FAILURE`，列出已成功目标并回滚失败目标，不声称全部成功。

统一 `update-hosts.ps1` 自己管理共享目标，避免同一路径更新两次而丢失旧版备份；`-CodexSkillsRoot` 仍指定该共享根，`-SkipCodex` 明确跳过此用户级根（即使同时更新 DSH 插件）。有项目级 `.agents/skills` 覆盖时，使用统一脚本的 `-ProjectRoot` 指定真实项目，不靠更新用户级插件覆盖项目副本。

安装后重新加载 Skill（必要时新开会话），从宿主返回的实际 Skill 根目录执行 `python "<实际 Skill 根>/scripts/ppt_runtime.py" inspect-host --host deepseek-harness`，确认输出路径与当前适配器。恢复旧运行还须按[DSH 入口诊断](../skills/ppt-start/references/deepseek-harness.md#入口诊断与升级后恢复)重新观测并构建 capability；安装成功不会自动改写运行目录中遗留的能力文件。

## Claude Code

- 用户级安装：`~/.claude/skills/ppt-start/`、`~/.claude/skills/ppt-editable/`，以及 `~/.claude/agents/ppt-svg-generator.md`
- 项目级安装：`.claude/skills/ppt-start/`、`.claude/skills/ppt-editable/`，以及 `.claude/agents/ppt-svg-generator.md`
- Agent 源文件：`hosts/claude-code/agents/ppt-svg-generator.md`
- 显式启动命令：`/ppt-start`、`/ppt-editable`

用户级复制示例：

以下命令只复制 Skill **目录内容**，不会在已有目标下再生成同名嵌套目录。手动升级不要用 `cp -R skills/ppt-start <已有目标>`；优先运行上方更新脚本，由脚本先备份再安装干净副本。

```bash
mkdir -p ~/.claude/skills/ppt-start ~/.claude/skills/ppt-editable ~/.claude/agents
cp -R skills/ppt-start/. ~/.claude/skills/ppt-start/
cp -R skills/ppt-editable/. ~/.claude/skills/ppt-editable/
cp hosts/claude-code/agents/ppt-svg-generator.md ~/.claude/agents/ppt-svg-generator.md
```

项目级符号链接示例：

```bash
mkdir -p .claude/skills .claude/agents
ln -s ../../skills/ppt-start .claude/skills/ppt-start
ln -s ../../skills/ppt-editable .claude/skills/ppt-editable
ln -s ../../hosts/claude-code/agents/ppt-svg-generator.md .claude/agents/ppt-svg-generator.md
```

`ppt-svg-generator` 使用普通 fresh-context subagent，并省略 worktree isolation；普通非 Git PPT 工作目录无需初始化仓库或创建首个提交。安装或更新 Agent 后必须重新开启 Claude Code 会话，当前会话不会重新扫描 Agent。

若仍出现 `Failed to resolve base branch "HEAD"`，说明当前会话仍在走旧的 worktree 路径：检查是否有项目级 Skill 或 Agent（`.claude/skills/ppt-start/`、`.claude/agents/ppt-svg-generator.md`）覆盖用户级安装，更新有效定义后重新开会话；不要用 `git init` 或空提交解锁。

调用示例：

```text
/ppt-start
请根据 inputs/ 中的资料制作一份 10 页中文策略演示文稿，使用 guided 模式。

/ppt-editable
请把 ppt-output/example-deck/ 的完成运行转换为原生可编辑 PowerPoint。
```

## OpenAI Codex

- 用户级安装：`$HOME/.agents/skills/ppt-start/`、`$HOME/.agents/skills/ppt-editable/`
- 项目级安装：`.agents/skills/ppt-start/`、`.agents/skills/ppt-editable/`
- 显式启动命令：`$ppt-start`、`$ppt-editable`

用户级复制示例：

以下命令只复制 Skill 目录内容；已有目标的升级应交给更新脚本完成安全备份与干净替换，禁止把源目录直接复制到同名已有目标中。

```bash
mkdir -p "$HOME/.agents/skills/ppt-start" "$HOME/.agents/skills/ppt-editable"
cp -R skills/ppt-start/. "$HOME/.agents/skills/ppt-start/"
cp -R skills/ppt-editable/. "$HOME/.agents/skills/ppt-editable/"
```

项目级符号链接示例：

```bash
ln -s ../../skills/ppt-start .agents/skills/ppt-start
ln -s ../../skills/ppt-editable .agents/skills/ppt-editable
```

调用示例：

```text
$ppt-start
请从 ppt-output/example-deck/ 恢复运行并继续生成 SVG。

$ppt-editable
请将该完成运行转换为可编辑 PPTX，并保留递归分组和备注。
```

## DeepSeek Harness

按 harness 插件约定安装到 `$HOME/.agents/plugins/plugins/ppt-pilot/`：一个 `ppt-pilot` 插件条目，`skills/` 下同时包含完整的 `skills/ppt-start/` 与 `skills/ppt-editable/`；per-ID 备份位于扫描根之外的插件 `backups/`。

SVG 生成使用插件已接受的 `deepseek-harness / native-subagent / 1.0.0` 适配器，直接调用当前宿主公开的普通 `functions.subagent`（`run_in_background: true`）。不安装专用 generator，不读取／修改 DSH 配置，不要求 profile patch、DSH 重启或 DSH 部署。普通 subagent 不可用时按契约停止，不通过配置探测解锁。

worker 获得 fresh context，但仍继承工具；“不调用工具、不再委派、只返回文本”是提示策略，不是硬工具隔离。coordinator 传入冻结完整 Prompt，独占运行目录写入；返回的 durable `subagent_id` 绑定为 `host_task_id`，不当作 `jobId` 交给 `job_output`。生成、补位与恢复前必须读取[DSH 协议](../skills/ppt-start/references/deepseek-harness.md)。实际并发受可观察容量和当前固定运行时新批次上限 5 约束；容量未知时为 1，不承诺五路活动任务。

手动安装时，在用户级/项目级 agents 根下分别复制两个 Skill 目录：

若目标已存在，先使用更新脚本备份并替换；下面的内容复制形式不会创建 `ppt-start/ppt-start/` 或 `ppt-editable/ppt-editable/`。

```bash
mkdir -p "$HOME/.agents/skills/ppt-start" "$HOME/.agents/skills/ppt-editable"
cp -R skills/ppt-start/. "$HOME/.agents/skills/ppt-start/"
cp -R skills/ppt-editable/. "$HOME/.agents/skills/ppt-editable/"
```

DeepSeek harness 无统一斜杠命令约定，使用显式启动词：

```text
ppt-start
请根据 inputs/ 中的资料制作一份 10 页中文策略演示文稿，使用 auto 模式。

ppt-editable
请把 ppt-output/example-deck/ 转换为经验证的原生可编辑 PowerPoint。
```

说明：

- 若 harness 提供子代理／委派原语，文稿审查按契约优先独立 subagent；未提供时自动走已定义的 `inline_fallback` 正式降级审查；
- 技能发现与启动语法的最终行为以真实宿主验证为准，见[验收文档](acceptance.md)的 DeepSeek Harness 行。

## PPT Style Extract

从模板 PPT／参考图／风格 prompt 提取风格并固化成 `ppt-start` 风格包（详见[提取设计](style-extract-design.md)）。

- 依赖：Python 3.9+；`python-pptx` 用于 `.pptx` 提取（`pip install python-pptx`），`Pillow` 用于 PNG/JPEG 像素取样（环境缺该能力时如实返回 `UNAVAILABLE`，不伪造）。
- 启动词：`ppt-style-extract`
- 示例：

```text
ppt-style-extract
请用一个品牌模板 pptx 提取一套风格，id 设为 acme-brand，注册到当前 ppt-start 的 registry。
```

包结构与内置风格包一致，产物为 `manifest.json` + `tokens.json` + `STYLE.md` + `prompt.md`，并幂等写入 `registry.json`。

## 通用注意事项

- 历史设计、计划和验收记录中的 `<USER_HOME>`、`<REPO_ROOT>`、`<EXAMPLE_PROJECT>`、`<EXPERIMENTS_ROOT>` 是隐私脱敏占位符，不是可直接执行的路径；需要重跑历史命令时先用当前环境的实际位置替换。它们不改变已记录的测试或验收状态。
- 符号链接是否可用取决于操作系统和宿主沙箱；无法使用时改为复制，并始终把本仓库 `skills/ppt-start/` 与 `skills/ppt-editable/` 视为标准源。
- 若 harness 不扫描标准技能目录，两个 Skill 的 `SKILL.md`、`references/`、`assets/` 与 `scripts/` 必须保持相对结构并置于工作区可访问位置；不能只粘贴 ppt-start 或漏掉 ppt-editable 脚本。
- Skill 核心流程为纯指令，不强制依赖 MCP、SDK 或 Hook；`ppt-start` 面板使用 Python 标准库本地服务，`ppt-editable` 随包提供 Python/PowerShell 转换与验证脚本，检查依赖但不自动安装。
