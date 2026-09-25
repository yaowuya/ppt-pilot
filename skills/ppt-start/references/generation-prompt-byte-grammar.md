# Generation Prompt 字节规则

Prompt 文件是可读、可复制的恢复证据，不需要状态机编译。

## Envelope

```text
# <slide-id> 页面生成 Prompt

## Snapshot metadata
- **slide_id**：<slide-id>
- **storyboard_snapshot_id**：<id or unhashed>
- **theme_snapshot_id**：<id or unhashed>
- **applied_visual_revision_ids**：<ids or none>
- **prompt_snapshot_id**：<id or unhashed>
- **user_page_request**：<request or none>
- **expected_output**：恰好一个 xml 代码围栏中的完整 SVG
- **workspace_output_path**：slides/<slide-id>.svg
- **format**：creative-brief-v1

## Compiled Prompt

# Role: ...
```

`## Compiled Prompt` 后恰好一个空行；正文从 `# Role` 开始，以一个 LF 结束。使用 UTF-8 和工作区相对路径。记录 hash 时从实际规范化字节计算；没有确定性 hash 能力时写 `unhashed`，不伪造十六进制摘要。

## 正文约束

- 只注入一次已批准故事板叙事和精确内容素材；风格来自当前已验证 `theme.json`／style pack；
- 数字、单位、期间、限定词、因果与 forbidden claims 不得改变；
- 稳定 **block ID** 可以进入叙事，且必须要求 generator 仅在对应语义 `<g data-block-id="...">` 上回显；
- 内部 **source ID**、来源 URL／名称和 source map 不得进入正文或 generator；
- 不得包含未解析 marker、原始回答、历史 JSON、绝对路径、机密、外部文件读取或工具调用指令；
- 必须要求只返回一个完整 SVG XML fence；
- 不得把 Prompt 路径、run.json、任务 ID 或工具名称作为 generator 输入。

## Source join

Generator 返回 raw candidate 后，AI 或无状态 finalize 工具把 block ID 与冻结 source map 连接：添加 machine-only `data-source-id`，移除全部 `data-block-id`，再验证 final。没有可关联来源的 content block 仍保留 block ID，并在 source map 写成 `{"S01-B1": []}`；finalize 只移除该 block ID，不写 source metadata。只有完全没有 content block 的页面才使用 `{}`，且 candidate 不得含 block ID。

Prompt 或内容变化时生成新的 Prompt 证据和 snapshot identity；不得靠改名、重置 attempt 或复用旧 candidate 掩盖变化。
