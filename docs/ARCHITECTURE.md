# PPT Pilot 架构

## 一句话

PPT Pilot 是**由 AI 协调的声明式演示工作流**：文稿和 `run.json` 保存可恢复意图；fresh-context generator 只生成一页 SVG；无状态工具只检查显式产物；可编辑 PowerPoint 是独立后处理。

## 四个 module

### 1. AI workflow

Interface：用户请求、运行目录、当前回答。
Implementation：选择最早动作、维护 `run.json`、组织文稿、调用 generator、处理工具证据、报告结果。

它是唯一状态 owner。阶段和 attempts 不由 Python runner、调度器、dashboard 或 host registry 推进。

### 2. Content compiler

Interface：简报、研究、来源、大纲和故事板。
Implementation：把受众决策、主张、精确 display copy、限定、指标、block IDs 和 source map 冻结为可审查文稿，再将单页内容与 theme 编成自包含 Prompt。

文稿审查是视觉前硬门。事实／来源变化重新审查；纯视觉变化不改 content owner。

### 3. SVG generation and tools

Generator interface：完整 Prompt bytes → 一个 XML fence。Generator 没有运行状态和文件 ownership。Claude Code 只使用当前会话已安装的 prompt-only Agent，不需要 local Claude CLI 登录；只有宿主明确报告 Git 启动前置条件时，coordinator 才能执行受限的本地 bootstrap。任何其他启动失败都是页面级 `generator_unavailable`，不影响 stage 或 attempts。

Stateless tool interface：显式输入文件 → `PASS|INVALID|UNAVAILABLE` JSON。

- `PASS` 提供额外证据；
- `INVALID` 证明该产物有确定性缺陷，仅页级失败；
- `UNAVAILABLE` 表示工具没有得出结论，AI 降级直接检查，stage／attempts 不变。

Raw candidate 暂存 block IDs。AI 或 finalize 工具将 block 与冻结 source map 确定性连接，加入 machine-only source IDs，移除 block IDs，再发布 final SVG。

### 4. Editable delivery

Interface：finalized run directory → editable PPTX result。它不写 `run.json`。

- 新 AI-state adapter 从故事板和 `slides` 推导 complete/partial；
- legacy explicit adapter 验证历史 hash、transaction 和 batch evidence；
- legacy implicit adapter 支持旧 complete run。

Adapters 按严格到宽松选择，非法形状不能 fall through。Converter failure 只影响 editable delivery。

## 数据流

```text
request + local evidence
  → brief / research / sources
  → outline / storyboard
  → manuscript review
  → theme
  → per-page frozen Prompt
  → fresh-context generator
  → raw SVG candidate
  → structure + source join + final validation
  → slides/<id>.svg
  → deck QA
  → complete | partial | failed
  → optional ppt-editable
```

## 状态与恢复

`run.json` 的 `slides` map 是页面 inventory；key 与故事板 target 完全一致。每页记录 state、attempts、Prompt、final、failure 和 QA。`delivery.status` 从该 map 推导，不复制另一份页面清单。

恢复顺序：pending interaction → 共享一致性 → 最早未完成阶段／dirty page。旧未知字段保留为证据，不驱动新流程。

每轮一个动作，先证据后状态。只有真实 generator 调用增加 attempts。用户 skip、工具运行、校验和恢复扫描都不增加它。

## 失败 locality

- 页面 SVG／事实／视觉缺陷：只失败该页；
- 工具不可用：降级，不判页面无效；
- editable 转换失败：只失败 optional delivery；
- `run.json` 无法解析、故事板 target 冲突、批准文稿不可读：全局停止，因为无法安全选择下一动作。

所有失败保留现场和 prior final，不创建替代运行绕过。

## 证据与来源

`SRC-<digits>` 永远是机器 metadata，允许存在于 `.ppt-pilot/来源.md`、冻结 source map、final SVG 的 `data-source-id` 和 PPT trace。它绝不出现在可见 SVG/PPT 文字。Generator 看到的是 transient block IDs，不看到 source IDs、来源 URL 或内部文件。

没有真实渲染写 `not_rendered`；没有 Office 实测写 `not_verified`。静态测试不能冒充真实宿主或 Office 验收。

## 安装 seam

三个 Skill 按目录部署。Claude Code 另外安装一个 Prompt-only `ppt-svg-generator` Agent；其“不调用工具”是 agent instruction，不宣称为硬沙箱。其他宿主使用实际可用的 fresh-context 能力；不可用时页面级失败、siblings 继续。
