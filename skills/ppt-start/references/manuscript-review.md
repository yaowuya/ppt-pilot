# 文稿审查契约

文稿审查是视觉生产前的硬质量门，不是可选批准点。用户回答不能替代审查，也不能放宽未解决的 `BLOCKER`／`HIGH`。

## 冻结输入

审查只读取本运行实际使用的五份文稿：

- `.ppt-pilot/简报.md`
- `.ppt-pilot/研究.md`
- `.ppt-pilot/来源.md`
- 根目录 `大纲.md`
- `.ppt-pilot/故事板.md`

旧英文运行继续原位读取其实际英文文件名；不得仅为兼容重命名、复制或重建已批准文稿。

AI 在审查记录中保存实际相对路径。确定性 SHA-256 可用时记录每份文件的真实 bytes hash；不可用时记录 `snapshot_id: unhashed`、`verification: ai_read`，并在每次下游使用前重新完整读取五份文件。不能伪造 hash，也不需要某个固定脚本才能开始审查。

## 审查方式

优先委派一个全新独立上下文，只授予五份文稿和本契约的只读内容。独立委派失败时，在当前步骤执行正式 `inline_fallback`：直接读取同一冻结输入，完整执行相同检查，并在报告中声明“当前上下文降级审查，不具备独立上下文隔离”。

- `subagent` 记录真实 child/result attribution；
- `inline_fallback` 记录委派失败原因，不伪造 child ID；
- 每个 cycle 最多三轮，两种方式共同计数；
- pending round 在审查开始前保存，恢复复用同一 cycle、round 和输入快照，不重复计数。

## 必查项

1. 核心结论是否直接回答受众问题并推动预期行动；
2. 支撑论点是否 MECE、以上统下且顺序合理；
3. 数字、比较、因果、最高级和时效性主张是否映射到有效来源；
4. 限定词、单位、期间、范围和不确定性是否保留；
5. 大纲、故事板、content blocks、claim IDs 和 source IDs 是否一致；
6. 是否存在有页无据、有据无用、重复页、混合结论页或密度失控；
7. 反方观点、风险、材料缺口和下一步是否足以支持决策；
8. 旧 PPT 重设计时，源稿保留／删除／重组与未解析对象是否在五份文稿中可审查。

## Findings 与质量门

每项 finding 记录稳定 ID、严重性 `BLOCKER|HIGH|MEDIUM|LOW`、状态 `OPEN|RESOLVED|ACCEPTED_RISK`、证据、影响和具体修复。

只有所有 `BLOCKER` 和 `HIGH` 都是 `RESOLVED` 才能写：

```json
{"required": true, "state": "manuscript_approved", "status": "PASSED", "open_blocking_findings": [], "pending_round": null}
```

`OPEN` 和阻断级 `ACCEPTED_RISK` 都阻止视觉生产。后续事实、来源、主张、大纲或故事板变化开启新的 cycle；纯视觉变化不重审内容。

## 结果交接

审查报告写入 `.ppt-pilot/文稿审查.md`，历史轮次追加到 `run.json.manuscript_review.review_history`。报告与状态只描述真实审查方式和输入；工具不可用不等于审查不可执行，因为 AI 能直接读取文稿完成 inline fallback。
