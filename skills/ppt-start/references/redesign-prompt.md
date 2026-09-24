# 页面生成 Prompt

本文件只说明 recompose 分支；通用编译和 source join 以 [Prompt 编译与 SVG 生成](visual-brief-and-generation.md) 与 [字节规则](generation-prompt-byte-grammar.md) 为准。

每次 initial generation 或 recompose 都写一份新的完整 Prompt。它只使用当前已批准故事板、`theme.json`、适用页面视觉修订和 SVG 契约，不从对话记忆补事实。

- 事实／来源／主张变化：先返回文稿审查；
- 纯视觉变化：保留 content blocks、block IDs、指标、限定和 source map，只改变视觉 intent／layout；
- 保存 Prompt 到 `.ppt-pilot/generation-prompts/<slide-id>.md`，但向 generator 传完整 Prompt 字节；
- Generator 只返回一个 XML fence，不拥有文件或状态；
- 失败保留旧 Prompt、旧 final 和 failure，不自动循环。

只有真正再次调用 generator 才增加 attempts。工具提取／校验失败或不可用不构成额外生成 attempt。
