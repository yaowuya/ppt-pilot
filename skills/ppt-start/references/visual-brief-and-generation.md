# Prompt 编译与 SVG 生成

本分支只在文稿状态为 `manuscript_approved` 后进入。

## 完整 Prompt

每页从已批准故事板、`theme.json`、适用的页面视觉修订和 SVG 契约编译一份自包含 Prompt，并保存为 `.ppt-pilot/generation-prompts/<slide-id>.md`。

Prompt 包含：

- 页面结论、受众 takeaway、精确 display copy、指标、限定和 forbidden claims；
- 每个 content block 的稳定 **block ID**；
- 当前主题、视觉意图、布局家族和 Office-safe SVG 规则；
- “只返回一个完整 XML fence”的输出要求。

Prompt 不包含：原始对话／历史 JSON、机密、绝对路径、URL、运行状态、内部 **source ID**，或要求读取文件／调用工具的指令。文件路径只是恢复证据，不能替代 Prompt 字节传给 generator。

## 两类 ID

- **block ID**：例如 `S03-B1`。它是临时结构 join key，可以进入 Prompt；generator 只在对应语义 `<g data-block-id="S03-B1">` 上原样回显，不能放进可见文字或其他属性。
- **source ID**：例如 `SRC-001`。它只属于 AI/coordinator 机器元数据，不能进入 Prompt、generator 上下文或可见文字。

## Generator 边界

把完整冻结 Prompt 按值交给当前宿主可用的 fresh-context generator。Generator 只依据任务文本生成一页，返回一个 `xml` fenced SVG；它不读取工作区、不写文件、不请求补充上下文，也不拥有 run state。

无法启动 generator 时记录该页 `generator_unavailable`。这不消耗未发生的生成 attempt，也不阻塞独立页面；不要改用当前创作上下文伪造 SVG。

## Candidate 到 final

1. 提取唯一 XML fence；
2. 校验 raw candidate：XML、画布、元素／属性、几何、文本，以及 block-ID 集与冻结 source map 的 key 完全一致；
3. 用 source map 在对应组写 machine-only `data-source-id`，然后移除所有 `data-block-id`；
4. 校验 final：允许合法 `data-source-id`，拒绝残留或可见 block ID、可见 `SRC-<digits>`；
5. 只在所有检查通过后发布 `slides/<slide-id>.svg` 并读回。

没有可关联来源的 content block 仍使用稳定 block ID，并在冻结 source map 中保留 `{"S03-B1": []}`；finalize 只删除该临时 ID，不写 source metadata。只有没有任何 content block 的页面才使用空对象 `{}`。

`scripts/svg_tool.py finalize` 可以完成步骤 1–4 的确定性部分。其 `INVALID` 只使该页失败；`UNAVAILABLE` 时 AI 直接执行同一检查并记录降级，工具不得改变 attempts 或 stage。
