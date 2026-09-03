# 安装指南

两个 Skill 使用同一 descriptor 流程安装；`ppt-start` 与 `ppt-editable` 必须成对安装，任一 Skill 的 `SKILL.md`、`references/`、`assets/`、`scripts/` 都不可拆分。技能启动标识：`ppt-start`、`ppt-editable`。

## 一键安装 / 更新三宿主（推荐）

在仓库根目录的本机终端运行：

```bash
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

脚本同时更新：

1. DeepSeek Harness 插件市场（调用 `tools/install-deepseek-plugin.ps1`）；
2. Claude Code 用户级技能 `~/.claude/skills/`；
3. Codex 用户级技能 `$HOME/.agents/skills/`。

旧版按 Skill ID 备份到 skills 扫描根之外的 `skill-backups/`，各保留最近一份；复制完成后做树摘要一致性校验。可选参数：`-SkipDeepSeek` / `-SkipClaudeCode` / `-SkipCodex` 跳过对应宿主；`-ProjectClaude` / `-ProjectCodex` 额外更新仓库内项目级目录；`-ClaudeSkillsRoot` / `-CodexSkillsRoot` / `-MarketplaceRoot` 覆盖默认路径。

仅需单独更新 DeepSeek 时：

```bash
powershell -ExecutionPolicy Bypass -File tools/install-deepseek-plugin.ps1
```

## Claude Code

- 用户级安装：`~/.claude/skills/ppt-start/`、`~/.claude/skills/ppt-editable/`
- 项目级安装：`.claude/skills/ppt-start/`、`.claude/skills/ppt-editable/`
- 显式启动命令：`/ppt-start`、`/ppt-editable`

用户级复制示例：

```bash
cp -R skills/ppt-start ~/.claude/skills/ppt-start
cp -R skills/ppt-editable ~/.claude/skills/ppt-editable
```

项目级符号链接示例：

```bash
ln -s ../../skills/ppt-start .claude/skills/ppt-start
ln -s ../../skills/ppt-editable .claude/skills/ppt-editable
```

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

```bash
cp -R skills/ppt-start "$HOME/.agents/skills/ppt-start"
cp -R skills/ppt-editable "$HOME/.agents/skills/ppt-editable"
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

手动安装时，在用户级/项目级 agents 根下分别复制两个 Skill 目录：

```bash
cp -R skills/ppt-start "$HOME/.agents/skills/ppt-start"
cp -R skills/ppt-editable "$HOME/.agents/skills/ppt-editable"
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

## 通用注意事项

- 符号链接是否可用取决于操作系统和宿主沙箱；无法使用时改为复制，并始终把本仓库 `skills/ppt-start/` 与 `skills/ppt-editable/` 视为标准源。
- 若 harness 不扫描标准技能目录，两个 Skill 的 `SKILL.md`、`references/`、`assets/` 与 `scripts/` 必须保持相对结构并置于工作区可访问位置；不能只粘贴 ppt-start 或漏掉 ppt-editable 脚本。
- Skill 本体纯指令，不强制依赖 MCP、SDK、Hook、后台服务或运行时软件包；`ppt-editable` 随 Skill 打包 Python/PowerShell 转换与验证脚本，检查依赖但不自动安装。
