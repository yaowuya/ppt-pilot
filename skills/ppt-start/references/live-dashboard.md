# 浏览器实时进度面板

面板以静态 HTML/CSS/JavaScript 展示运行目录中的真实持久状态，Python 3.9+ 标准库提供本地服务。浏览器每秒自动读取任务、阻断和 SVG；没有 Node 构建、包安装或远程资源。启动脚本随本 Skill 的 scripts/ 和 assets/dashboard/ 一起安装，三个宿主使用同一入口。

## 启动与生命周期

从当前已加载 SKILL.md 的实际位置解析 scripts/ppt_dashboard.py，不能假定宿主工作目录就是插件源码目录。先确定唯一运行目录。新建空运行创建目录后即可启动，允许尚无 run.json；已有运行先审计，只有 `ppt_workflow_gate.py --audit-run` PASS 后才可启动或复用。审计 BLOCKED 时不启动或重启 dashboard，因为服务会写元数据；同时停止其他写入。不能为了展示而擅自创建第二个演示运行。

使用可用的 Python 3.9+ 执行（Windows 可用 `py -3` 替代 python，macOS/Linux 可用 python3）：

```text
python "<Skill绝对目录>/scripts/ppt_dashboard.py" start --run-dir "<运行绝对目录>" --open
```

该命令启动隐藏后台服务并在就绪后返回单行 JSON：status、url、pid、instance_id、reused。必须确认 status 为 running 后才发布实际 url；不要预测或固定端口。重复 start 复用同一已验证服务。`--port 8765` 可选，默认自动选空闲端口；端口占用时失败，不接管别的进程。`--open` 打开默认浏览器，打开失败仍可手动访问 URL。宿主限制后台执行时按宿主权限机制请求实际所需权限，或给出终端命令；不得伪称已启动。

```text
python "<Skill绝对目录>/scripts/ppt_dashboard.py" status --run-dir "<运行绝对目录>"
python "<Skill绝对目录>/scripts/ppt_dashboard.py" stop --run-dir "<运行绝对目录>"
python "<Skill绝对目录>/scripts/ppt_dashboard.py" serve --run-dir "<运行绝对目录>" --port 8765
```

serve 在前台运行，适合宿主不能保留后台任务时由用户在独立终端启动。默认仅监听 127.0.0.1。status/stop 根据 health 的实例身份核验，不根据持久 PID 终止进程。用户明确禁用服务或浏览器时遵从；面板不可用只降低可观察性，不改变生成门禁。

## 让用户看见实际执行过程

新建／恢复运行时启动；真正进入阶段之前原子更新 run.json.stage，完成阶段或批次后更新原有产物。现有 pending_interaction、pending_round、active batch 和 per-slide transaction 都按原本协议落盘，不能为“看起来有进度”提前写入完成状态或跳过 pointer-last。页面展示当前阶段任务、待回答问题、生成／验证／失败页和最新文件更新时间；用户仍回到宿主对话回答批准问题。

已经存在但被标为 dirty 的 SVG 显示为旧版本；生成中的临时候选不是已提交页面。只有 candidate_written／validated 且持久 hash 匹配的候选可显示。预览只使用 img，不执行 SVG 脚本，也不改变质量检查结论。无产物更新时只能说明没有新磁盘事件，不能证明模型存活或停止。面板断线后自动重试，重启服务若更换端口需打开新的实际 URL。

## 存储与兼容

新运行读取 `.ppt-pilot/run.json`，旧运行兼容根 run.json；两份同时存在则显示冲突，面板不修复、不选择、不迁移。服务自身只写 `.ppt-pilot/dashboard.json`、dashboard.lock、dashboard.log；它们不属于工作流授权，不能用于恢复生成。dashboard.json 含本地停止令牌，不能加入提示词、共享截图或提交；stop 正常退出删除本实例元数据，保留诊断日志和空闲锁文件。新旧运行的流程数据均只读。

完成后保留页面以便查看产物，交付时同时给出链接和 stop 命令。仅当用户要求关闭服务时执行 stop；不要为了 UI 测试关闭不属于本次启动的其他运行服务。
