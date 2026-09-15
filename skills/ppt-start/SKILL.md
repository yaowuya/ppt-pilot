---
name: ppt-start
description: Use when creating, resuming, redesigning, or revising an evidence-backed SVG presentation, including page-local recovery and honest full or partial PowerPoint delivery.
---

# PPT Pilot

通过可恢复的持久产物完成演示文稿。模型负责叙事、页面构图、视觉判断和有界修复；固定运行时负责快照、事务、计数、哈希、指针、CAS 和交付分区。

## 开始

1. 先读[交互协议](references/interaction-protocol.md)，通过当前 Skill 的 `scripts/ppt_entry.py` 选择、新建或恢复唯一运行。默认动作是 `resume`；已有同源运行原位恢复，不另建 recovery 副本。外部 PPT/PPTX 还要读[旧稿导入](references/source-deck-redesign.md)。
2. 对已选运行执行固定入口返回的 audit；`BLOCKED` 时停止写入并报告首个错误。运行目录中只放契约产物，不创建维护脚本、依赖或修复 helper。
3. 需要实时进度时按[面板协议](references/live-dashboard.md)启动或复用服务。面板只投影磁盘事实，不授权阶段转换。
4. 每次 dispatch 前读[宿主适配器](references/host-isolation-adapters.md)；该文件是 Claude SDK／legacy 选择、隔离、工具、任务绑定、receipt 和独立升级边界的唯一 ceremony。DeepSeek Harness 分支还必须读其[普通 subagent 与 managed dashboard 协议](references/deepseek-harness.md)。

视觉生产只调用当前安装 Skill 的固定运行时：

```text
python <skill-dir>/scripts/ppt_runtime.py advance --run-dir RUN [--allow-partial] [--skip-slide SID ...]
python <skill-dir>/scripts/ppt_runtime.py finalize --run-dir RUN
```

`advance` 返回下一项可执行动作及声明式输入；严格按响应执行并再次 `advance`，不要自行计算或编辑事务、摘要、计数、manifest、pointer、CAS 或 delivery。`finalize` 只结算已经有真实证据的页面。低层命令是[运行时参考 API](references/runtime-canonical-owners.md)，不是主工作清单。

## 四节点工作流

### 1. 意图与内容基线

把请求、资料和约束形成简报、研究、来源、大纲与逐页故事板。明确受众行动、结论顺序、事实、单位、期间、限定词、来源映射、品牌硬规则、权限和交付要求；只询问本节点仍影响结果的未决事项，紧密相关字段按交互协议集中收集，不重复询问已有答案。

五份内容 owner 冻结后执行[文稿审查](references/manuscript-review.md)。`BLOCKER`／`HIGH` 必须在正式审查轮中成为 `RESOLVED`；零问题也保存明确 PASS。新快照同时绑定 exact `file_hashes` 与只排除已知结构化视觉／元数据字段的 `semantic_file_hashes`；旧批准保持 exact-byte strict，绝不追补语义摘要。

**完成标准：** `manuscript_review.state` 为 `manuscript_approved`，事实、来源、限定、叙事和权限都由当前快照绑定。

### 2. 视觉基线

从批准故事板选择已注册风格并写 `theme.json`，由模型选择能覆盖主要版式与复杂内容的代表页作为锚点，不固定页号。按[设计系统](references/design-system.md)、[布局目录](references/layout-catalog.md)、[页面投影](references/visual-brief-and-generation.md)和[SVG 契约](references/svg-contract.md)工作；用真实非 Office 渲染检查焦点、层级、密度、字体、语义色和安全边界。

新的风格、字体、颜色、品牌或构图方向属于 `theme.json` 或受控视觉投影，不回写内容简报来规避审查。事实、来源、限定词、批准叙事和安全约束保持不变。`guided` 等待锚点明确批准；`auto` 执行同等内部检查。

**完成标准：** 当前主题有效，所选锚点均绑定真实渲染和逐页 QA，并已批准或按 auto 规则验证。兼容协议要求多页稿至少两页、单页稿一页；模型可按版式覆盖需要选择额外代表页。

### 3. 页面局部生产

在 `production` 中反复调用 `advance`，按其返回的 ordered work 生成、验证、修复或提升页面。每个首次生成或重构只接收按值传入的完整冻结 Prompt，并只返回一个 SVG；Prompt 正文只承载叙事、素材与事实值，来源映射由 coordinator 独立校验，来源注解不得进入正文。原始 host response 作为 task／dispatch 证据保留；coordinator 完成来源增强、临时 `data-block-id` 移除、确定性序列化和写入，不能把得到的 candidate 归作未经改动的 generator 输出。生成 Prompt 的唯一字节规则见[字节语法](references/generation-prompt-byte-grammar.md)。

逐页应用[QA 与修订](references/qa-and-revision.md)：真实 XML／安全／来源／事实／硬边界失败阻断该页；`0.88` 文本宽度估算只是保守预警，必须结合真实渲染确认，不能单独声称已经裁切。每个页面整条生产链最多三次真实 dispatch，retry、recompose 或本地修复都不能重置计数、把模型调用改名或制造新 transaction 绕过预算。

普通生成拒绝、超时、格式错误、SVG 契约、事实来源或视觉 QA 失败是**页面局部**结果：保留失败 transaction 原字节和计数，继续不依赖该页的 sibling／后续页面。当前校验器否定历史 `validated` 候选时，`resume` 返回 `revalidation_required`，`advance` 先保存旧 transaction／QA 精确证据，再把该页转成普通失败并提升健康 siblings。共享 owner 损坏、快照不一致、CAS 冲突、权限问题、宿主 adapter 不可用或其他完整性失败是**全局阻断**：保持现场并停止写入。绝不把失败 transaction 改成 PASS，也不把旧 final 或孤儿 candidate 当作新证据。

新运行持久化 `production_policy: best_effort`；显式 strict 请求写 `strict`。缺少该字段的旧运行按 strict。对既有运行，只有显式传入 `advance --allow-partial` 才持久化 `best_effort`；不能静默升级。`--skip-slide` 是显式用户跳过并保留审计证据，不是自动失败处理。

**完成标准：** 每个目标页都已 promoted，或以 unchanged failed transaction／显式 skip 形成可审计的页面局部结果；遗漏页保持 dirty，且没有未解决的全局阻断。

### 4. 诚实完整／部分交付

对可交付页面执行整套 QA，写 `.ppt-pilot/质量检查报告.md`，然后调用 `finalize`。逐页 QA 必须绑定该页当前正式 SVG 的真实 render；源码检查不能冒充视觉 PASS。整套 QA 检查已交付序列的叙事、证据、节奏与风格，并明确披露原始 targets 和 omissions。

`run.delivery` 与顶层终态必须同步：

- `prepared`：只存在于 `run.stage: qa` 的结算中间态，**不可导出**；
- `complete`：`run.stage: complete`，全部原始 target 按原顺序 delivered，missing 为空；
- `partial`：`run.stage: partial`，仅允许 `best_effort`，至少一页 delivered 且至少一页 missing；
- `failed`：`run.stage: failed`，零 delivered，不生成 PPTX。

`target_slide_ids` 始终保留原集合与顺序；delivered 与 missing 不重叠且完整分割 targets。每个 missing 项绑定未改写的失败 transaction 或显式 user skip；终态 manifest 密封 omission ref 与文件摘要。partial 不是 complete 的别名，验证状态也独立于完整度。严格策略有遗漏时可以继续处理其他页，但不能结算为 partial；修复遗漏，或由用户明确授权 `--allow-partial`。遗漏页的 dirty 标记不清除。

用户只要 SVG 时直接报告 complete／partial／failed、已交付页、缺失页、QA 能力和未执行 Office 验证。用户明确需要 PPTX、原生可编辑形状或文本时，仅对 `complete`／`partial` 调用 `ppt-editable`；partial 使用其独立 partial artifact／manifest 名称，不能覆盖或冒充完整成品。遵守 `ppt-editable` 自身的 `PASS`／`GENERATED_UNVERIFIED`／`BLOCKED`／`FAILED_VERIFICATION`，不自动启动 PowerPoint、WPS 或 Office。

**完成标准：** `finalize` 先验证当前 `manuscript_approved` 及其批准快照仍有效，再验证 storyboard、theme、QA、每个 delivered SVG 和每个 omission evidence；交付报告准确区分完整度、验证状态与 Office 状态。

## 不变量

- 显式事实、来源、限定词、批准叙事、品牌硬规则、安全 SVG 约束、用户权限、快照 identity 与 CAS guard 始终保留。
- 页面局部失败只影响该页；共享完整性失败影响全局。
- 生产预算真实、有界、不可重置；失败证据不可改写。
- 所有视觉页面都是独立 UTF-8、`viewBox="0 0 1280 720"` 的 Office-safe SVG，不含远程资源或活动内容。
- 无真实渲染时记录 `visual_qa: not_rendered`；无 Office 实测时明确写未验证，不制造 PASS。
