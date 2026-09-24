# AI 主导工作流

## 阶段

`brief → research → outline → storyboard → manuscript_review → theme → anchor → production → qa → complete|partial|failed`

阶段用于交接和报告，只由 AI 根据真实产物推进。脚本不选择下一阶段。

## 入口

- `new`：创建不覆盖已有目录的新运行；
- `resume`：读取既有 `run.json` 和产物原位继续；
- `revise`：记录用户请求，使最早受影响阶段或页面变脏。

这些是意图，不是 CLI 命令。目标不唯一时先持久化选择问题；不猜测、不复制运行。

## 每轮

1. 先处理 `pending_interaction`；
2. 检查共享状态能否一致解释；
3. 选择最早未完成阶段或 dirty 页面；
4. 执行一个动作并写证据；
5. 原子更新 state 并报告。

恢复旧运行时保留未知 transaction/batch/dashboard 等字段，但不执行旧 runner、迁移或后台任务。

## 生产

按页面逐个生成。每轮最多一次真实页面生成调用；AI 在调用前后分别记录该页证据和状态，不启动后台任务、轮询或隐藏并发。工具结果按 `PASS|INVALID|UNAVAILABLE` 处理，工具不可用不消耗 attempt。

## 失效边界

事实、来源、主张、大纲或故事板变化返回文稿审查；整套视觉变化返回 theme/anchor；单页纯视觉变化只使该页 dirty。页面失败不阻止独立 siblings。

## 交付

按 `slides` 页面状态推导完整度：全 promoted 为 complete；部分 promoted 且其余有失败／skip 证据为 partial；零 promoted 为 failed。结构、视觉渲染和 Office 验证分别报告。`ppt-editable` 是可选后处理，不推进本工作流。
