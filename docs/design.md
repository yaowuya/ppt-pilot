# PPT Pilot 设计原则

## 产品目标

把用户意图和本地证据转成一套可审查、可恢复、可继续推进的 SVG 演示；工具和单页故障不得把整套流程锁死。

## 原则

### AI owns workflow

AI 读取真实文件、维护 `run.json`、应用用户决定并选择下一动作。状态不是 Python 控制程序的投影；脚本不能拥有阶段、重试、skip 或任务调度。

### Evidence before design

简报、研究、来源、大纲和故事板先冻结并审查。未解决的高严重度内容问题不进入视觉。Source IDs 保持机器可追踪，但不进入可见页面。

### Page-local production

每页有独立 Prompt、attempt、failure、QA 和 final。页面失败保留 prior final 和 evidence；不依赖该页的 siblings 继续。真实 generator 调用之外的动作不消耗 attempts。

### Layered degradation

工具只能返回 `PASS|INVALID|UNAVAILABLE`：

- `INVALID` 是确定性产物结论；
- `UNAVAILABLE` 是工具能力结论，不是产物结论；
- 缺 renderer／Office 诚实报告，不伪造验证，也不反向抹掉有效 SVG。

### Small tool interfaces

保留工具只接受显式文件／参数并返回 JSON。它们不读 run state、不启动模型、不创建队列、不轮询、不修复 workflow。

### Honest completeness

`complete`、`partial` 和 `failed` 由故事板 target 与 `slides` 状态推导。完整度、结构 QA、真实渲染和 Office 验证是不同维度。

### Legacy evidence stays legacy

旧 transaction/batch 等 owner 保留可读，不为新运行重建。`ppt-editable` 使用独立 legacy adapter 验证历史格式；新 AI state 直接消费页面 map。

## 用户体验

- 未指定时默认 `guided`；
- 一轮一个关键问题，推荐不是确认；
- 问题先持久化，回答后由 AI 直接幂等应用；
- 用户可以明确 retry、skip 或停止失败页；
- resume 不要求记住旧命令或修复内部状态文件。

## 视觉与技术约束

- 1280×720、Office-safe SVG、64px 安全区；
- 标题／正文／脚注下限分别由验证过的主题确定，绝不低于 34／20／14px；
- 每页一条 assertion、一个主焦点和一个明确视觉关系；
- Generator 只接收完整 Prompt；transient block ID 用于 source join，final 只保留 machine-only source ID；
- 可编辑 PowerPoint 保留 group hierarchy 与 editable text，无 image fallback。

## 验收层级

1. **Static contract**：文档、包结构、fixture 和纯函数测试；
2. **Local tool**：真实 Python/PowerShell 进程与临时文件；
3. **Host**：真实 generator 启动、隔离和返回；
4. **Render**：真实浏览器／SVG renderer；
5. **Office**：真实 PowerPoint normalize/render/visual compare。

低层证据不能声称覆盖高层能力。
