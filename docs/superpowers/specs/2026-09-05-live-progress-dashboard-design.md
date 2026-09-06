# 本地实时进度面板设计

## 目标与范围

在 Claude Code、Codex、DeepSeek Harness 执行 PPT Pilot 时，启动本地服务，通过静态 HTML 页面实时查看阶段任务、待处理问题、逐页生成状态与 SVG。源码在 `codex/live-progress-dashboard` 分支；无需 Node、第三方 Python 包或云端服务。Python 3.9+ 标准库服务随 ppt-start 安装。

## 数据和显示

一个服务绑定一个明确运行目录，允许目录刚创建、尚无 run.json。优先读取 `.ppt-pilot/run.json`，兼容根 run.json；两者共存时报告冲突，不擅自采用其中一个。浏览器每秒轮询 `/api/state`，不会写入流程产物或消费待确认问题。阶段任务固定为 brief/research/outline/storyboard/manuscript_review/theme/anchor/production/qa/complete；批准检查点映射到对应阶段。逐页任务结合故事板 slide_id、运行页数、active batch 的 transaction refs、dirty_slides、final 和 sample 文件推导。文件存在只表示可预览，不能伪造质量门通过。脏页、阻断、等待回答、生成中和状态未知分别显示。无新产物不能据此判定宿主仍在运行。

`GET /api/state` 返回：`schema_version:1, deck_id, mode, stage, status, revision, updated_at, tasks:[{id,label,status,detail}], slides:[{id,title,status,dirty,preview_path,preview_kind,version,updated_at,detail}], progress:{done,total}, notice:{kind,message}|null, artifacts:[{path,updated_at}], warnings:[string]`。时间为 UTC ISO 或 null；revision 和 version 为内容摘要；status 为 waiting/running/blocked/complete/unknown，任务可含 pending。preview_kind 为 final/sample/candidate，路径不含绝对地址。progress 只统计已产出的非脏正式页，不宣称是耗时百分比。

候选仅在 durable candidate_written/validated 且 hash 匹配后可预览；generating orphan 不展示。解析失败显示诊断并自动重试，不能导致服务器退出或显示错误完成状态。revision 改变时刷新 DOM，保留用户选择和滚动。用 img 显示 SVG，不把 SVG/XML/Markdown 插入页面 HTML。

## 服务与生命周期

入口 `skills/ppt-start/scripts/ppt_dashboard.py` 提供 start/serve/status/stop，必需 `--run-dir`。start 默认动态空闲端口，可指定端口，支持 `--open`；后台进程 Windows 隐藏窗口，POSIX 新会话。状态写入该运行 `.ppt-pilot/dashboard.json`，不改 run.json。状态包含实例 ID、运行路径摘要、URL、PID、停止令牌；先 health 验证身份再复用或停止，禁止只靠 PID 操作进程。重复 start 在目录级锁下复用同一已验证实例。启动失败及时返回非零和可读原因，端口冲突不能终止其他服务。stop 用本地带随机令牌 POST；退出清理仅自己的元数据。

服务仅监听 127.0.0.1，验证 Host/Origin，拒绝路径穿越、绝对路径、符号链接及 Windows reparse 点。HTTP 只公开静态资产、投影状态和白名单 SVG，不提供目录或任意文件浏览。SVG 响应使用 CSP sandbox/default-src none；顶层 CSP 禁止外站资源、内联脚本、对象和框架。状态读取有大小/数量限制；异常输入不导致泄露或执行代码。

## 工作流接入

新运行创建目录后、开始资料处理前启动；resume/revise 确定目录后启动或复用。输出 URL 后继续原工作流。每次进入阶段先持久化真实阶段；transaction/pending/dirty 状态沿用既有契约。观察服务失败只提示修复命令，不改变批准和生成门禁。已完成运行保持可预览，用户通过 stop 结束服务。手动命令适用于所有宿主；被明确禁用浏览器/服务时尊重用户选择。安装器已经递归复制整个 Skill，不需增加宿主专用依赖。

## 验收

真实临时运行测试：等待初始化 → brief → production/逐页状态 → 添加与改写 SVG → dirty/阻断 → complete；同一页面无手动刷新自动更新。浏览器测试桌面及窄屏、放大/键盘关闭、失联提示恢复、无脚本注入。HTTP 测试越界/链接/Host/Origin/非法 JSON/孤儿候选。进程测试 start 复用、指定端口冲突、status、stop、重启和空目录。执行既有完整测试；确认三端安装包均包含服务和静态资产。测试不冒充模型从文档到 PPT 的完整验收。
