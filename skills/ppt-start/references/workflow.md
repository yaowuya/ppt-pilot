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
2. 检查共享状态能否一致解释，并优先恢复已有 `active_generation_wave`；
3. 选择最早未完成阶段、dirty 页面或 independently eligible 页面组；
4. 执行一个非生成动作，或一个有界 generation wave；
5. 先写并读回证据，再原子更新 state 并报告。

恢复旧运行时保留未知 transaction/batch/dashboard 等字段，但不执行旧 runner、迁移或隐藏队列。

## 生产

默认并发 5；用户明确串行时宽度为 1，明确并发宽度可为 2–10。实际宽度取 target、剩余 eligible 页面和已知宿主容量的最小值。只有同一阶段、同一已批准故事板／文稿／theme 快照，Prompt 与 page-specific source map 完整，且不依赖彼此输出的页面可并发；锚点批准仍是 production 前硬边界。

一个 wave 按以下顺序执行：

1. 按故事板顺序选择 eligible 页面，并限制在实际宽度内；
2. coordinator-only 地串行编译、写入、读回每份完整 Prompt 和 source map，计算实际 Prompt digest；
3. 原子写入 `active_generation_wave.status: prepared`；
4. 在同一工具轮为每页 dispatch 一个 prompt-only Agent；生成调用可并发，Agent 不拥有文件或 state，支持时使用可追踪 task ID 的 background task；
5. 只把宿主实际接受的 task attribution 写入 `accepted_tasks`，并让对应页面 attempts 各增加一次；容量拒绝不消耗 attempt；
6. 等待宿主 completion notification，不忙轮询、不 sleep-loop，也不建立自动调度器；
7. 结果可以乱序到达，但按 `ordered_slide_ids` 的故事板顺序消费；遇到首个未 terminal 页面就停止本次消费，较晚完成的结果继续留在宿主 task evidence；
8. 对每页依次提取 XML、校验／enrich／finalize，并对 candidate、final、QA 和 `run.json` 串行提交；
9. accepted tasks 均终止并处理、未接受页面恢复 eligible 后清除 wave，再选择下一动作。

用户要求并行且至少两页独立 eligible 时，必须尝试多页 wave。宿主只接受更少任务时记录实际 accepted 数；已知容量为零时不创建空 wave、不消耗 attempt，只等待能力变化通知而不制造容量。没有 eligible 页面时选择其他动作，不写空 wave。宿主确实不能并发时实际宽度降为 1，并报告 `host_concurrency_unavailable`，不能把它写成通用单页规则。一个页面失败不取消或降级已接受 siblings。

先选不依赖 Git/HEAD 的原生 fresh-context 路由；只有实际宿主 Git/HEAD 错误才按 [生成器恢复协议](visual-brief-and-generation.md) 处理，同一冻结 Prompt 修复后最多重启一次。宿主准备和接受 Prompt 前失败不增加 attempts；工具结果按 `PASS|INVALID|UNAVAILABLE` 处理。

恢复时先读取 active wave：有 durable task attribution 的调用只 resume／consume，不重新 dispatch；prepared 但未接受的页面未消耗 attempt，可回到下一 wave。归因不明只影响该页，不猜测完成状态或重复计数。旧 init-only 或 ambiguous HEAD 按可用原生路由／HEAD 修复处理，而不是 HEAD-only 检查后原样等待；同一环境已修复但仍不可用时只保留一次失败证据并转向其他动作。

## 失效边界

事实、来源、主张、大纲或故事板变化返回文稿审查；整套视觉变化返回 theme/anchor；单页纯视觉变化只使该页 dirty。页面失败不阻止独立 siblings。

## 交付

按 `slides` 页面状态推导完整度：全 promoted 为 complete；部分 promoted 且其余有失败／skip 证据为 partial；零 promoted 为 failed。结构、视觉渲染和 Office 验证分别报告。`ppt-editable` 是可选后处理，不推进本工作流。
