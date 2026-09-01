---
name: ppt-start
description: Use when creating, revising, or resuming multi-slide presentations whose final slide files must be standalone SVG, especially for evidence-backed decks, workspace handoffs, or PowerPoint-compatible vector delivery.
---

# PPT Pilot

## 概述

通过工作区中的持久产物开发演示文稿，而不是只在对话中一次性输出。内容决策与视觉设计必须分离；正式文稿审查通过之前禁止开始视觉设计，审查优先独立 subagent，委派失败时使用明确记录的 inline fallback。

## 输入、入口与执行策略

可接收主题、完整简报、资料集合、既有运行目录或定向修订请求。开始任何阶段前先读取[用户交互与确认协议](references/interaction-protocol.md)，检查请求和工作区，避免重复提问。

持久执行策略只有两种：

- **guided**：新运行未显式指定策略时的默认值；在简报、大纲和锚点页批准节点提出一个直接问题，并等待明确回答。
- **auto**：只有显式指定时才使用；采用合理默认值并跳过可选问题，但需要用户权限或没有安全默认值时仍须询问。

`resume` 和 `revise` 是入口动作，不写入 `run.json.mode`：

- **resume**：先读取 `run.json`，按[工作流](references/workflow.md)的全局恢复顺序表处理 durable control state；保留既有 `run.json.mode`，只有前四者都不存在或已完成时才从第一个未完成或脏阶段继续。
- **revise**：先读取并保留既有 `run.json.mode`，同样先按[工作流](references/workflow.md)的全局恢复顺序表处理 durable control state，再按照产物契约只使受影响的产物失效；修改类别无法唯一判断时先询问。

推荐不是确认。提出阻塞问题后必须停止，不得在收到并持久化明确答案前推进下游工作。每次运行写入 `ppt-output/<deck-id>/`。禁止把产物写入本 Skill 或宿主配置目录。新运行的过程 Markdown 使用中文文件名；`resume`／`revise` 对旧英文运行只做原位读取并沿用既有名称，不自动重命名、复制或迁移，具体规则见产物契约。

## 必须执行的工作流

执行某阶段前，先读取该阶段链接的参考文档。

1. 简报与可选研究——[简报与研究](references/brief-and-research.md)
2. 把叙事规范化为可组合字段：金字塔原理只定 `argument_framework` 论证层级，SCQA 只定 `opening_framework` 开场过渡，三段式／Why-What-How／总-分-总只定 `sequence_template` 页面推进；冻结 `narrative_id`、`narrative_step1_bullets`、选择理由与 `outline_snapshot_id`，再产出结论先行的大纲和带稳定块／主张／来源映射的逐页故事板——[叙事与故事板](references/narrative-and-storyboard.md)
3. 文稿审查（subagent 优先，失败时 inline fallback）——[文稿审查](references/manuscript-review.md)
4. 主题、风格包与语义布局选择——[设计系统](references/design-system.md)和[布局目录](references/layout-catalog.md)
5. 在生成任何视觉页面前，先按[页面编译路径](references/visual-brief-and-generation.md)从已批准故事板与 `theme.json` 编译并验证对应 `generation-prompts/<slide-id>.md`；没有有效 prompt 不得生成 SVG。
6. 每个页面的首次生成和任何 `recompose` 都必须按[页面生成与重新排版专用 Prompt](references/redesign-prompt.md)：把故事板拥有的叙事／素材／事实／来源与 `theme.json` 拥有的软风格基线编译到 repository [generation-prompt-template.md](references/generation-prompt-template.md)，只替换两个规范 marker；完整内存 preflight 后先协商 fresh isolation，无能力则零 prompt／transaction／candidate 写入；能力通过才按 pointer-last 写 schema-v2 per-slide transactions、batch manifest 与 `active_visual_generation_batch`。隔离任务只接收 `prompt_by_value`，fresh history、filesystem none、tools none、text-only；旧 `.ppt-pilot/redesign-prompts/` 永远只读且 inert。
7. 两页锚点 SVG——[SVG 契约](references/svg-contract.md)
8. 生成任何正式页面前，先读取 [QA、恢复与修订](references/qa-and-revision.md)；默认 `batch_width: 4`（可配置 3）。宿主有 concurrent fresh isolation 与 durable lookup 时批内最多 4 个 generator 并发，缺一项则 width 1；非 Git 不降级。每页生成与 validation 可重叠，但 candidate/transaction 写入、final promotion、visible blocker 和 `run.json` pointer 只由 coordinator 按 `ordered_slide_ids` 确定性提交。

阶段转换遵循[工作流](references/workflow.md)，文件和状态字段遵循[产物契约](references/artifact-contract.md)。

## 文稿审查是硬质量门

`简报.md`、`研究.md`、`来源.md`、`大纲.md`、`故事板.md` 全部完成即冻结并进入审查：优先委派**全新且独立的子 Agent**（只读五文件）；启动或结果归因失败时，当前步骤执行正式 `inline_fallback`，报告必须声明"当前上下文降级审查，不具备独立上下文隔离"。任一 `BLOCKER`／`HIGH` 问题状态不是 `RESOLVED` 就阻断——`OPEN` 与 `ACCEPTED_RISK` 仍然阻断；零问题也必须保存显式 `PASS` 报告；subagent 与 inline 共同计入每 cycle 三轮上限。设计师视角的材料充分性缺口以 `category: material_gap` 记录（必填 `missing_evidence` 与 `proposed_question`），由创作上下文按交互协议逐一向用户提问。findings 字段 schema、八项检查维度、重大影响判定、业务决策与批准后生产限制，一律以[文稿审查](references/manuscript-review.md)为单一权威。

## 生产、恢复与修订

- 顶层 `stage` 表示当前工作流位置。批准检查点之后，每个视觉阶段都要求 `run.json.manuscript_review.state` 持续为 `manuscript_approved`。
- 每完成一个持久阶段或一个生产批次，都更新 `run.json`。
- 每页最多修复两次，之后使用简单布局回退；回退后仍有硬检查失败时必须停止。
- `resume` 入口必须先读取 `run.json` 并保留既有 `run.json.mode`；除非产物缺失、格式错误或被标记为脏，否则不得重新计算已批准的上游工作。
- 纯视觉修改或可证明不改变事实的文字修正，只把受影响页面和 QA 标记为脏，不重新进行文稿审查。
- 所有首次页面生成和 `recompose` 必须从唯一 [generation-prompt-template.md](references/generation-prompt-template.md) 编译 `.ppt-pilot/generation-prompts/<slide-id>.md`，完成 canonical bytes 与关系门禁后按 pointer-last 激活 schema-v2 batch。fresh 隔离任务只接收完整 prompt bytes by value；coordinator 提取裸 SVG、原子写 candidate、复读 hash 并提交 per-slide transaction。
- 确定性 preflight 失败必须产生零 transaction 写入、零 prompt 写入、零 generator 调用和零 SVG 写入。authoritative outline／storyboard／theme 缺陷返回对应 owner；只有规范模板／规范字节或无法唯一解释的 provenance 自身失败，才在没有本次 transaction/prompt 的情况下独立写 `run.json.visual_generation_blocker`。历史 crash 留下旧协议的 prompt／`compiling`／blocker 组合时，不采用旧 Prompt，必须从完整无副作用 preflight 重启。
- 主张、来源、事实性文案、大纲或故事板变化会使批准失效；重新生成视觉页面前必须进行新的文稿审查。

## 输出规则

- 最终页面是独立 UTF-8 SVG 文件，并包含 `viewBox="0 0 1280 720"`。
- 过程文件与页面保存在同一运行目录，使另一个受支持宿主可以恢复运行。
- 只使用 Office-safe SVG 子集，不使用远程资源。
- 事实无法验证时，必须限定或删除，不得把证据缺失改写成确定结论。
- 无法视觉渲染时，记录 `visual_qa: not_rendered`，不得声称视觉检查通过。

## 完成条件

只有文稿质量门通过、全部 SVG 硬检查通过、整套 QA 已写入 `.ppt-pilot/质量检查报告.md`，并且 `run.json` 的阶段为 `complete`，本次运行才算完成。
