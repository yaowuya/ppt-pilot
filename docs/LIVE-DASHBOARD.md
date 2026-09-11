# 实时进度与 SVG 预览

PPT Pilot 现在带有一个本地浏览器面板。在 Claude Code、Codex 或 DeepSeek Harness 使用更新后的 ppt-start 时，运行目录确定后会启动服务、给出 URL，然后继续执行任务。页面自动展示阶段列表、待确认问题、逐页生成状态和最新 SVG，可以点开放大、用方向键切页。

## 手动启动

在源码仓库的独立终端或支持普通脱离进程的宿主中，指定一个已存在的运行目录：

```powershell
py -3 skills/ppt-start/scripts/ppt_dashboard.py start --run-dir ppt-output/demo-fy26-h1 --open
```

macOS/Linux 用 python3；面板只需要 Python 3.9+ 标准库。安装版的脚本位于对应宿主 skills/ppt-start/scripts/ 下，使用实际安装路径即可。新运行可以先创建空目录再启动面板，页面会等待 run.json 出现。

start 返回实际 URL，如 `http://127.0.0.1:随机端口/`。重复启动会复用当前服务；无需每生成一页重启或刷新。可选 `--port 8765` 固定端口，冲突时明确报错。静态页面需通过该服务打开，直接双击 index.html 无法读取磁盘运行状态。DeepSeek Harness 内不要使用 `start`，新版会拒绝这种可能在回合结束时失效的脱离进程。

```powershell
py -3 skills/ppt-start/scripts/ppt_dashboard.py status --run-dir ppt-output/demo-fy26-h1
py -3 skills/ppt-start/scripts/ppt_dashboard.py stop --run-dir ppt-output/demo-fy26-h1
```

## DeepSeek Harness

DSH 中先由主 coordinator 用一条前台命令执行 `status --run-dir`。若返回 running，直接复用该 URL，不再启动第二个进程；只有 stopped 才通过 `functions.pwsh` 的 `run_in_background: true` 运行：

```text
python -B "<实际 Skill 根>/scripts/ppt_dashboard.py" serve --run-dir "<运行绝对目录>" --port 0
```

保存后台 job ID，用 `job_output` 读取 serve 的首行 JSON；随后另开一条前台命令执行 `status --run-dir`。只有 status 的 `status` 为 `running`，且 `instance_id`、`url` 与首行一致时才能发布 URL。正常回合结束不得取消该 job。关闭时先执行 `stop`，再读取 job 终态。后续 resume 仍从 status 开始：running 就复用（即使新会话没有旧 job ID），stopped 才启动新 job；并发启动提示已有服务时也回到 status，绝不改用 DSH 已禁止的 start。

如果宿主没有可持续的后台作业能力，先执行 status；已有健康实例仍可复用。只有 stopped 时才能把 `serve` 命令交给用户在独立终端前台运行并明确说明面板尚未启动。使用 Ctrl+C 或 stop 关闭。任务完成后服务保留供查看；不再使用时执行 stop。

## 页面含义

- 阶段和页面状态来自 run.json、故事板及活跃批次的逐页 transaction；原始 JSON 暂时写入不完整时显示读取提示并自动重试。
- “已产出页数”统计非脏的正式 SVG，不是模型耗时百分比，也不意味着整套质量门通过。
- “旧版本”表示该页仍待重生成；候选会标识为候选，不冒充正式交付。
- 待确认问题显示在页面上，请回到原宿主对话回答。页面没有批准或修改工作流功能。
- 最新更新时间表示最近磁盘产物更新，不是模型心跳。页面断线会自动重试；服务重启更换端口后使用新 URL。

## 更新到三个宿主

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/update-hosts.ps1
```

安装器自动包含 scripts/ 与 assets/dashboard/。项目级 Skill 如果覆盖用户级版本，可追加 -ProjectClaude / -ProjectCodex 同步当前项目，重新开始会话读取新指令。页面本地监听，不需要联网；服务控制和日志保存在对应运行 `.ppt-pilot/`，原有 run.json 及质量门不受影响。
