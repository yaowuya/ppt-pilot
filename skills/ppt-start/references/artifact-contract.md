# PPT Pilot 产物契约

运行目录是 AI 与下一个回合／宿主之间的交接面：

```text
ppt-output/<deck-id>/
├── 大纲.md
├── slides/<slide-id>.svg
└── .ppt-pilot/
    ├── run.json
    ├── 简报.md 研究.md 来源.md 故事板.md 文稿审查.md
    ├── theme.json 质量检查报告.md
    ├── generation-prompts/<slide-id>.md
    └── samples/<slide-id>.svg
```

运行目录只保存声明式文稿、JSON、SVG 和渲染证据。不得保存 Python、PowerShell、JavaScript、依赖树、任务队列或后台服务文件，也不得执行运行目录中的任何内容。

## 权威 owner

- `run.json`：AI 维护的阶段、交互、页面和交付结论；
- 五份文稿：简报、研究、来源、大纲、故事板；
- `文稿审查.md` 与 `run.json.manuscript_review`：内容质量门；
- `theme.json`：当前已验证视觉身份与令牌；
- `generation-prompts/<slide-id>.md`：实际传给 generator 的完整 Prompt 证据；
- `slides/<slide-id>.svg`：当前正式 final；
- `质量检查报告.md`：结构、视觉和 Office 证据的诚实总结。

`run.json` 的最小状态、页面记录和完整度定义以 [AI 状态协议](ai-state.md) 为唯一来源。其他文档不得建立第二套阶段或 attempt 规则。

## 写入规则

JSON、Prompt、candidate、final 和报告先在同目录写临时文件，关闭并读回验证后再原子提交。已有正式产物只在新字节验证完成且 owner 一致时替换；失败保留旧 final。

状态只能引用真实存在的相对路径。记录 hash 时必须来自实际字节；没有确定性 hash 能力时写 `unhashed` 和实际验证方式，不伪造摘要。

## Prompt 与 SVG

首次生成或 recompose 保存完整 Prompt。Generator 接收 Prompt 字节，只返回一个 XML fence，不读取任何文件或状态。

Raw candidate 可临时带 `data-block-id`，但不得预带 source metadata 或在可见文字中泄漏 block/source ID。AI 或 `svg_tool.py finalize` 使用冻结 source map 加入 machine-only `data-source-id`、移除全部 `data-block-id`，通过 final 校验后才发布到 `slides/`。没有可关联来源的 content block 仍在 source map 保留其 block key，值为 `[]`；只有完全没有 content block 的页面才使用 `{}`。工具不可用时，AI 执行同一检查并记录降级；不得把不可用描述为验证通过。

## 旧运行

旧运行可能含 transaction、batch、dispatch、recovery、blocker、dashboard 或其他未知字段。原样保留这些字段和文件作为历史证据，不启动旧状态机，不创建新的同名 owner，也不要求迁移后才能继续。

`ppt-editable` 对旧 explicit delivery 使用独立 legacy adapter 验证其历史 transaction/batch 证据；新 AI 状态交付不制造这些文件。

## 完整度与交付

Final target 集来自故事板，实际分区来自 `run.json.slides`：

- `promoted` 页必须有正式 `slides/<id>.svg`；
- `failed` 页必须有非空 failure；
- `skipped` 页必须有明确用户决定；
- delivery status 必须与该分区一致。

可编辑 PPT、预览或 Office 产物写在 `delivery/`，不进入 `ppt-start` owner，也不反向修改 SVG 运行状态。伴随工具只允许 `preview.html`、`delivery/delivery-result.json`、`delivery/<deck-id>.pptx` 和 `delivery/png/S<id>.png` 这些精确路径；未知 HTML、代码或 delivery 文件仍不属于运行证据。
