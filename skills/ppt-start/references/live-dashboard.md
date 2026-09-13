# 浏览器实时进度面板

面板以静态 HTML/CSS/JavaScript 展示运行目录中的真实持久状态，Python 3.9+ 标准库提供本地服务。浏览器每秒自动读取任务、阻断和 SVG；没有 Node 构建、包安装或远程资源。启动脚本随本 Skill 的 scripts/ 和 assets/dashboard/ 一起安装，三个宿主使用同一入口。

## 启动与生命周期

从当前已加载 SKILL.md 的实际位置解析 scripts/ppt_dashboard.py，不能假定宿主工作目录就是插件源码目录。先由[固定入口](interaction-protocol.md#固定工作区入口)确定唯一运行目录；新建的最小运行与已有运行均先审计，只有 `ppt_workflow_gate.py --audit-run` PASS 后才可启动或复用。dashboard 自身允许观察空目录不代表创建／恢复授权，不能用它绕过入口。审计 BLOCKED 时不启动或重启 dashboard，因为服务会写元数据；同时停止其他写入。不能为了展示而擅自创建第二个演示运行。

使用可用的 Python 3.9+ 执行（Windows 可用 `py -3` 替代 python，macOS/Linux 可用 python3）。生命周期命令为：

```text
python "<Skill绝对目录>/scripts/ppt_dashboard.py" start --run-dir "<运行绝对目录>" --open
python "<Skill绝对目录>/scripts/ppt_dashboard.py" serve --run-dir "<运行绝对目录>" --port 0
python "<Skill绝对目录>/scripts/ppt_dashboard.py" status --run-dir "<运行绝对目录>"
python "<Skill绝对目录>/scripts/ppt_dashboard.py" stop --run-dir "<运行绝对目录>"
```

`start` 适用于能保留普通脱离进程的宿主或独立终端：它启动隐藏服务，并在就绪后返回 `status`、`url`、`pid`、`instance_id`、`reused`。重复调用复用同一已验证服务，`--port` 省略／为 0 时自动选空闲端口，`--open` 仅负责打开浏览器。**DeepSeek Harness 中禁止使用 `start`**：DSH 可能在 coordinator 回合结束时回收这种未被宿主管理的进程；新版脚本在检测到 DSH 环境时会在写控制文件前失败，而不是返回短暂的 `running`。

### DeepSeek Harness 的持久启动

由主 coordinator 执行，不能交给 subagent：

1. **先查再建**：用前台 `functions.pwsh` 运行 `status --run-dir`。已返回 `running` 时直接复用它给出的实际 `instance_id`／`url`，不得再启动第二个 serve；若当前 coordinator 仍保存对应 `job_id` 和首次 JSON，继续跟踪该 job。新会话没有旧 job ID 也可依据 status 的协议健康检查复用服务，停止时仍走 `stop`。
2. 只有 status 返回 `stopped` 时，才创建受管理后台作业；不要把 `start` 的脱离子进程当作后台作业：

```text
functions.pwsh({
  command: 'python -B "<Skill绝对目录>/scripts/ppt_dashboard.py" serve --run-dir "<运行绝对目录>" --port 0',
  description: 'Run PPT live dashboard service',
  run_in_background: true
})
```

3. 保存工具返回的真实后台 `job_id`；该 ID 是 dashboard 命令作业，不是 SVG generator 的 `subagent_id`。
4. 用一次非阻塞 `job_output({job_id})` 读取 serve 的首行 JSON；尚无输出时继续其他工作并稍后再读，不得 sleep／忙轮询。**不能仅凭这一行发布 URL**。
5. 紧接着用另一条前台 `functions.pwsh` 调用 `status --run-dir`。只有它返回 `running`，并且 `instance_id`、`url` 与首行完全一致时，才把实际 URL 发给用户；不要预测或固定端口。
6. 保留并跟踪作业；正常回合结束不得调用 `job_kill`。用户要求关闭时先调用 `stop --run-dir`，再读取该 job 的终态；仅当协议停止失败且确认是同一作业时才取消作业。
7. 浏览器拒绝连接或 status 变为 stopped 时，不复述旧 URL；启动新的 managed serve 并重复双重验证。若并发启动返回“已有面板”，重新执行 status：running 就复用，stopped 才允许重试；不得转去调用 DSH 已禁止的 start。

宿主没有持久后台作业能力时，先执行 status；已有健康实例仍应复用。只有 status 为 stopped 才明确报告面板未启动，并把 `serve` 命令交给用户在独立终端前台运行；不得伪称已启动。`serve` 默认仅监听 127.0.0.1。status/stop 根据 health 的实例身份核验，不根据持久 PID 终止进程。用户明确禁用服务或浏览器时遵从；面板不可用只降低可观察性，不改变生成门禁。

## 让用户看见实际执行过程

新建／恢复运行时启动；真正进入阶段之前原子更新 run.json.stage，完成阶段或批次后更新原有产物。现有 pending_interaction、pending_round、active batch 和 per-slide transaction 都按原本协议落盘，不能为“看起来有进度”提前写入完成状态或跳过 pointer-last。页面展示当前阶段任务、待回答问题、生成／验证／失败页和最新文件更新时间；用户仍回到宿主对话回答批准问题。

页面的十个步骤均保留工作说明和已观测成果，包括已完成、当前及尚未开始的步骤；窄屏也可横向浏览完整说明。详情从既有白名单产物和运行状态投影，展示文档记录、故事板实际解析页数、审查轮次／阻断数量、样张和正式页状态；缺少产物时明确标注，不用统一的进度占位文案代替步骤信息。当前步骤同时呈现待确认问题或阻断原因。文档存在不代表审查通过，面板不展开原始正文，也不要求工作流另写一份展示状态。

已经存在但被标为 dirty 的 SVG 显示为旧版本；生成中的临时候选不是已提交页面。只有 candidate_written／validated 且持久 hash 匹配的候选可显示。预览只使用 img，不执行 SVG 脚本，也不改变质量检查结论。无产物更新时只能说明没有新磁盘事件，不能证明模型存活或停止。面板断线后自动重试，重启服务若更换端口需打开新的实际 URL。

## 存储与兼容

新运行读取 `.ppt-pilot/run.json`，旧运行兼容根 run.json；两份同时存在则显示冲突，面板不修复、不选择、不迁移。服务自身只写 `.ppt-pilot/dashboard.json`、dashboard.lock、dashboard.log；它们不属于工作流授权，不能用于恢复生成。dashboard.json 含本地停止令牌，不能加入提示词、共享截图或提交；stop 正常退出删除本实例元数据，保留诊断日志和空闲锁文件。新旧运行的流程数据均只读。

完成后保留页面以便查看产物，交付时同时给出链接和 stop 命令。仅当用户要求关闭服务时执行 stop；不要为了 UI 测试关闭不属于本次启动的其他运行服务。
