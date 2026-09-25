# QA 与修订

## 每页 QA

1. XML 可解析，恰有一个 1280×720 根 SVG；
2. 元素、属性、路径、资源和活动内容满足 [SVG 契约](svg-contract.md)；
3. 可见文案、事实、指标、限定和 forbidden claims 与故事板一致；
4. final 已移除 block ID，重要主张保留合法 machine-only source ID，且可见文字没有 `SRC-<digits>`、transient `S<digits>-B<digits>`、来源行或 URL；
5. 文本、几何、安全区、层级和主焦点合理；
6. 有真实渲染才评价焦点、重叠、裁切和字体；否则写 `visual: not_rendered`；
7. 有真实 Office 实测才写 Office PASS；否则写 `office: not_verified`。

## 工具三态

- `PASS`：记录为额外确定性证据；
- `INVALID`：工具证明当前输入有真实契约缺陷。只把该页标记 `failed`，保留旧 final 和 siblings；
- `UNAVAILABLE`：工具没有得出产物结论。记录 `tool_unavailable`，保持 stage 和 attempts，AI 直接检查并继续，不宣称工具 PASS。

非结构化异常、找不到 Python、缺依赖、参数／版本不兼容和内部崩溃都属于 `UNAVAILABLE`，不是页面缺陷。

## 修订分类

- 事实、来源、主张、限定、大纲、storyboard content block 或阅读顺序变化：回到最早受影响内容阶段并重新文稿审查；
- 整套颜色、字体、形状语言或视觉身份变化：更新／选择有效 style pack 与 `theme.json`，使依赖页面变脏；
- 单页 layout／visual intent 变化：只把该页标记 dirty 并重编完整 Prompt；
- 已验证的纯字节缺陷可直接修正，但不得改变语义、来源或视觉意图。

## 生成预算

每页首发一次；真实生成失败后，下一轮最多一次明确 retry/recompose。只有真实 generator 调用增加 attempts。第二次失败后等待用户选择修复、skip 或停止；不自动循环、不删除证据、不重建运行归零。

`skip` 保存明确用户决定并保持 attempts。页面失败／skip 不阻止独立 siblings。共享 `run.json`、故事板 target、批准文稿或主题无法一致解释时才全局停止。

## Final partition

按 [AI 状态协议](ai-state.md) 从 `slides` 推导 `complete|partial|failed`。QA 报告分别列出：目标页、promoted 页、failed/skipped 页、结构结果、工具降级、渲染状态和 Office 状态，并且在报告中恰好写一个 `ppt-pilot-qa-json` 围栏，内容精确为：

```ppt-pilot-qa-json
{"schema_version":1,"status":"partial","target_slide_ids":["S01","S02"],"promoted_slide_ids":["S01"],"missing_slide_ids":["S02"]}
```

其中数组顺序以故事板为准，`status` 与 `run.json.delivery.status` 一致；complete 的 `missing_slide_ids` 为空且 promoted 等于 target。完整度不是视觉或 Office PASS 的同义词。
