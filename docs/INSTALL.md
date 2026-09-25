# 安装指南

## 一键更新

从仓库根目录运行：

```bash
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

默认目标：

| 宿主 | Skill 根 | 额外内容 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `~/.claude/agents/ppt-svg-generator.md` |
| Codex | `~/.agents/skills/` | 无 |
| DeepSeek Harness | `~/.agents/plugins/plugins/ppt-pilot/skills/` | marketplace/plugin metadata |

安装三个 Skill：`ppt-start`、`ppt-editable`、`ppt-style-extract`。安装采用过滤后的 staging tree、摘要校验、备份替换和失败回滚；不会复制 `__pycache__`、`.pytest_cache`、`.pyc` 等缓存。

替换 Skill 或 Agent 后重新开启宿主会话。

## 常用参数

```bash
powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1 \
  -SkipDeepSeek -SkipCodex \
  -ClaudeSkillsRoot C:\path\to\skills \
  -ClaudeAgentsRoot C:\path\to\agents
```

- `-ProjectRoot <path>`：刷新该项目已经存在的 `.claude/skills`／`.agents/skills` discovery scope；
- `-CodexPluginRoot <path>`：刷新一个明确指定的物理 Codex plugin tree；
- `-ProjectClaude`／`-ProjectCodex`：为仓库自身显式选择项目 scope；
- `-SkipDeepSeek`、`-SkipClaudeCode`、`-SkipCodex`：跳过宿主；
- `-Version`：只改变安装报告中的版本标签。

脚本不会递归扫描磁盘或任意插件 cache，也不会在没有相关 discovery scope 的额外项目中创建一套新的 scope。

## DeepSeek 单独安装

```bash
powershell -ExecutionPolicy Bypass -File tools/install-deepseek-plugin.ps1
```

该命令打包三个 Skill 和 plugin metadata。它不修改 DeepSeek profile/config，不注册 Python workflow runner，也不保证某种 generator 隔离能力；页面生成使用当前宿主实际可用的 fresh-context 能力，AI 对不可用情况执行页面级降级。

## Claude generator

仓库源文件：`hosts/claude-code/agents/ppt-svg-generator.md`。

Agent 只接收完整 Prompt 文本并返回一个 XML fence。其 frontmatter 可能因宿主 schema 声明 `TodoWrite`，但正文明确禁止调用工具；它没有文件／网络数据工具。不要把这种提示约束描述为硬沙箱或 byte-pure 进程隔离。Claude Code 使用当前会话授权的 Agent，不需要也不会安装 local Claude CLI 登录路线；若宿主生成能力不可用，AI 记录页面级 `generator_unavailable`，而不是把安装视为失败。

更新器在所选 Claude user/project scope 中同步当前 Agent，并移除同目录下已退休的 SDK Agent 文件；不触碰其他 Agent。

## 运行依赖

`ppt-start` 的 AI 协调路径没有 Python workflow 依赖。保留工具要求 Python 3.9+：

```bash
python skills/ppt-start/scripts/svg_tool.py --help
```

```bash
python skills/ppt-start/scripts/ppt_source_intake.py --help
```

`ppt_source_intake.py` 只使用标准库读取 `.pptx` OPC 包。`ppt-editable` 需要 `python-pptx`；Pillow 和本机 Microsoft PowerPoint 只用于更高等级验证，缺少时必须报告 `GENERATED_UNVERIFIED`／`not_verified`，不能伪造 PASS。

## 安装后检查

1. 确认三个 Skill 的 `SKILL.md` 存在；
2. Claude Code 确认 `ppt-svg-generator.md` 存在且退休 SDK 文件不存在；
3. 确认 `ppt-start/scripts/` 只有 source-intake 与 SVG 相关 Python 文件；
4. 运行聚焦测试：

```bash
python -B -m unittest tests.test_tools_package tests.test_svg_tool -v
```

安装摘要只证明文件部署；真实生成、渲染和 Office 导入仍需实际宿主／Office 证据。
