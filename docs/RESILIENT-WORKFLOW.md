# 可继续推进的 PPT 工作流

## 核心

页面生产是可恢复的 AI 工作，而不是 batch 状态机。AI 每轮读取 `run.json` 和真实文件，选择一个动作，记录证据，然后更新状态。

## 页面独立

每页记录：

- `state`：planned/generating/validated/promoted/failed/skipped；
- `attempts`：真实 generator 调用次数；
- 当前 Prompt 与 final 路径；
- failure、QA 和工具 evidence。

一个页面的 generator、SVG、来源或视觉错误不阻止独立页面。旧 final 不被失败 candidate 覆盖。

## 工具分层降级

- `PASS`：可作为确定性证据；
- `INVALID`：输入产物有真实问题，只失败该页；
- `UNAVAILABLE`：工具没有产物结论，AI 直接检查并继续，stage/attempts 不变。

不要把工具启动失败记为 generator attempt，也不要因为 Python／renderer／Office 不可用创建全局 blocker。Claude Code 使用当前会话的 Agent，不要求 local Claude CLI 登录；若明确的安全 Git bootstrap 或宿主启动仍不可用，记录该页 `generator_unavailable`，stage/attempts 不变并继续独立页面。

## Retry 与 skip

首次真实生成失败后，只有明确 retry/recompose 才再次调用。第二次失败后询问：

- 修复输入／环境；
- skip 该页继续；
- 停止。

用户回答由 AI 直接写入并应用：skip 保存原始授权，页面变 skipped，attempts 不变；无需任何回答消费命令。

## 恢复

按顺序：

1. pending/answered interaction；
2. `run.json`、批准文稿、故事板 target、theme 的共享一致性；
3. 最早未完成阶段；
4. dirty/failed 页面和实际 final 文件。

旧 transaction/batch/dispatch 等文件只作历史证据，不重新排队、轮询或迁移。

## 最终结论

- all promoted → `complete`；
- promoted 非空，其他均有 failed/skipped 证据 → `partial`；
- promoted 为空 → `failed`。

`质量检查报告.md` 分开列完整度、结构、真实 render 和 Office 状态。`not_rendered`／`not_verified` 是能力披露，不是假 PASS，也不等于流程卡死。

## Editable handoff

`ppt-editable` 直接消费新 AI-state 页面分区；partial 不需要制造 legacy transaction/batch。历史 explicit delivery 仍走严格 legacy adapter。转换失败只影响 editable 输出，SVG 状态保持不变。
