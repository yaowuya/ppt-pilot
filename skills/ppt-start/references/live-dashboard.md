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

新建／恢复运行时启动；真正进入阶段之前原子更新 `run.json.stage`，完成阶段或 batch settlement 后更新既有 owner。现有 `pending_interaction`、`pending_round`、active batch 和 per-slide transaction 都按原协议落盘；面板只读取它们，不为“看起来有进度”提前写完成、补 PASS、改失败 bytes 或跳过 pointer-last。

步骤视图保留已完成、当前和尚未开始的工作说明与观测成果；窄屏可横向浏览。详情从既有白名单产物投影：文档记录、故事板原始 target 数、审查轮次／阻断数、anchor、正式页、QA 和 delivery。缺少产物时明确标注；文档存在不等于审查通过，源码存在不等于页面验证通过，dashboard 状态也不是 QA evidence。当前步骤同时呈现一个 pending 用户问题或一个真实 global blocker。

生产视图以 original ordered target set 为分母，分别显示：

- **processed**：runtime 已有明确当前结果的 target，不与 delivered 混称；
- **validated/promoted**：通过当前 formal SVG digest 对应检查的页面；
- **delivered**：来自已验证的 final `run.delivery.delivered_slide_ids`，保持原顺序；prepared 页面仅标为已产出、待质检，不计为已交付；
- **missing**：来自 `run.delivery.missing_slides`，展示失败／跳过原因；冻结尝试次数与完整证据引用保留在对应持久记录中；
- **pending**：尚未 settled 的 original targets。

视图展示能够从持久产物验证的状态、失败原因、dirty 与文件更新时间。尝试次数保留在 transaction／missing 记录中，剩余预算和下一项可执行操作以固定运行时响应为准，面板不自行推断或授予重试。页面失败是 page-local 行状态；independent sibling 可继续且面板不能把它渲染成 deck-wide 停止。shared integrity、snapshot、CAS、permission 或 adapter blocker 单独显示为 global。预算 exhausted 后显示 exhausted／missing candidate，不显示 retry、fallback 或“恢复准备中”。历史 replacement transaction 保留审计链，但不能让 count 回退或隐藏第四次 dispatch。

`run.delivery.status` 必须与 `run.stage` 的合法组合原样显示：

- `prepared` 只配 `stage: qa`，标注“QA 阶段、不可导出”；
- `complete` 只配 `stage: complete`，要求 missing 为 0；
- `partial` 只配 `stage: partial`，同时展示 delivered 和按 original order 的 missing 清单，并明确 artifact 为 partial；
- `failed` 只配 `stage: failed`，显示 delivered 为 0 且无 PPTX。

其他 stage／delivery 组合显示为 owner conflict，不猜测或美化终态。完整度、QA verification 与 Office verification 使用独立标签。`partial` 不能显示为 complete，`GENERATED_UNVERIFIED` 不能显示为 verified；没有 Office 实测时明确标记未验证。

已经存在但 dirty 的 SVG 显示为旧版本；omitted／user-skipped 页面即使文件仍在也保持 dirty。生成中的临时候选不是已提交页面。只有 `candidate_written`／`validated` 且持久 digest 匹配的候选可预览；preview 只使用 `img`，不执行 SVG script，也不改变质量结论。无产物更新只说明没有新磁盘事件，不能证明 worker 存活或停止。面板断线后自动重试，重启服务若更换端口需打开新的实际 URL。

## 存储与兼容

新运行读取 `.ppt-pilot/run.json`，旧运行兼容根 run.json；两份同时存在则显示冲突，面板不修复、不选择、不迁移。服务自身只写 `.ppt-pilot/dashboard.json`、dashboard.lock、dashboard.log；它们不属于工作流授权，不能用于恢复生成。dashboard.json 含本地停止令牌，不能加入提示词、共享截图或提交；stop 正常退出删除本实例元数据，保留诊断日志和空闲锁文件。新旧运行的流程数据均只读。

完成后保留页面以便查看产物，交付时同时给出链接和 stop 命令。仅当用户要求关闭服务时执行 stop；不要为了 UI 测试关闭不属于本次启动的其他运行服务。
