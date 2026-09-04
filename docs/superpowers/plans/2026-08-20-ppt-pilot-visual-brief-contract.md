# PPT Pilot Visual Brief Contract Wiring Plan

> **SUPERSEDED（历史记录）：** 当前执行权威是 `skills/ppt-start/references/generation-prompt-byte-grammar.md`、`skills/ppt-start/references/artifact-contract.md` 与 `skills/ppt-start/references/workflow.md`。本文中的旧模板、marker、runtime fallback、来源注入、visual-brief 与恢复规则仅保留作审计历史，不得用于新运行。

**Goal:** Add the self-contained visual-brief contract and require it before anchor or production SVG generation.

**Architecture:** Keep stable workflow stages unchanged; assemble `visual-briefs/<slide-id>.md` inside theme/production using approved storyboard, theme, revision history, and SVG/QA constraints.

**Tech Stack:** Markdown Agent Skill contracts and focused Python `unittest` checks.

## Global Constraints

- This is Plan 2 of 7 and depends on the visual brief fixtures/tests plan.
- Do not modify FY26 artifacts or add a runtime compiler.
- Preserve the manuscript-review hard gate and stable stage list.
- Run focused local tests only.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Implement the self-contained visual brief and workflow boundary

**Files:**
- Create: `skills/ppt-start/references/visual-brief-and-generation.md`
- Modify: `skills/ppt-start/SKILL.md:28-39`
- Modify: `skills/ppt-start/references/workflow.md:1-55`
- Modify: `skills/ppt-start/references/artifact-contract.md:3-22,156-181`
- Modify: `skills/ppt-start/references/design-system.md:3-62`
- Test: `tests/test_visual_generation_contract.py`

**Interfaces:**
- Consumes: the approved storyboard, `theme.json`, `run.json.interaction_history`, SVG and QA contracts.
- Produces: `visual-briefs/<slide-id>.md` as the only visual-generation input.

- [ ] **Step 1: Write the visual brief reference**

Create `skills/ppt-start/references/visual-brief-and-generation.md` with these exact normative sections:

```markdown
# 逐页视觉 brief 与生成契约

## 进入条件
只有文稿保持 manuscript_approved，且故事板和 theme.json 有效时才能组装视觉 brief。

## 唯一视觉生成入口
每个待生成或待修订页面必须先有 visual-briefs/<slide-id>.md。宿主必须能只依靠该文件和它引用的当前运行产物生成页面，不得依赖对话记忆。SVG 是派生结果，不是主题、构图或修订历史的权威来源。

## 必需章节
逐项定义：来源与版本、锁定内容、信息层级、构图、视觉系统、修订模式、输出与质量要求。缺少任一章节、快照引用或来源边界时停止生成。

## 组装顺序
approved storyboard -> active theme -> authoritative visual revision history -> SVG/QA contracts -> active visual contract -> visual brief。

## 内容保护
允许压缩展示标签，但不得改变主张、置信度、范围、因果、比较、建议、数字、限定条件、来源映射或受众行动。

## 当前有效契约
按不可覆盖层、种子层、品牌／主题层、页面层、修复层归并。后一条明确规则可以覆盖前一条同字段规则，但必须记录 supersedes。废弃规则只能保留在历史中，不得进入当前有效生成指令。冲突无法消解时停止。

## 生成模式
patch 读取完整 brief、当前 SVG 和唯一 defect。recompose 读取完整 brief、锁定故事板和当前主题；旧 SVG 不得作为几何底稿，只能在新候选完成后核对内容与来源。

## 旧运行
缺少 visual-briefs/ 的 schema-v1 运行仍可读取；下一次锚点、正式页面生成或视觉修订前，从批准故事板、当前主题和权威历史补建 brief。信息不足或主题冲突时停止，不从旧对话猜测。
```

Under `必需章节`, enumerate the exact fields so implementers do not infer them:

```markdown
- 来源与版本：slide_id、storyboard_snapshot_id、theme_snapshot_id、applied_visual_revision_ids、brief_snapshot_id。
- 锁定内容：assertion_title、audience_takeaway、required_content_blocks、qualifiers、numbers_and_units、source_ids、forbidden_claims、render_copy_policy。
- 信息层级：primary_message、2–5 supporting_arguments、de_emphasized_details、reading_order、management_judgment。
- 构图：layout_family、rationale、focal_object、region_map、primary_secondary_ratio、card_count、nesting、connector_semantics、density_strategy。
- 视觉系统：active_palette_roles、typography_ladder、phrase_emphasis、spacing_and_shape、prohibited_motifs、exceptions。
- 修订模式：mode、reason、patch_defect、fix_attempts_for_candidate。
- 输出与质量要求：canvas、safe_area、office_safe_svg、text、source_metadata、qa。
```

Keep the reference self-contained and Chinese-first.

- [ ] **Step 2: Link the reference before SVG generation**

In `skills/ppt-start/SKILL.md`, replace visual steps 4–6 with:

```markdown
4. 主题、风格包与语义布局选择——[设计系统](references/design-system.md)和[布局目录](references/layout-catalog.md)
5. 在生成任何视觉页面前，先按[逐页视觉 brief 与生成](references/visual-brief-and-generation.md)组装并验证对应 `visual-briefs/<slide-id>.md`；没有有效 brief 不得生成 SVG。
6. 两页锚点 SVG——[SVG 契约](references/svg-contract.md)
7. 生成任何正式页面前，先读取 [QA、恢复与修订](references/qa-and-revision.md)；按每批 3–4 页生产，但每次只写入并验证一个 SVG，通过后才能继续。
```

- [ ] **Step 3: Place brief assembly inside existing stages**

Add to `workflow.md` without changing the stable stage list:

```markdown
视觉 brief 不是新的顶层阶段。`theme` 阶段解析当前有效主题后组装锚点页面 brief；锚点批准或 auto 内部验证完成后，在 `production` 中按页组装其余 brief。任何页面在其 brief 有效前都不能生成。
```

- [ ] **Step 4: Add the artifact and invalidation contract**

In `artifact-contract.md`:

- add `visual-briefs/` to the visual artifact list;
- state that the folder is mandatory before new visual generation but absent schema-v1 runs remain readable;
- add invalidation behavior:

```markdown
| `theme` | `theme` | `preserve` | 全部 `visual-briefs/`、`samples/`、`slides/` 和 QA 产物。 |
| `anchor_only` | `anchor` | `preserve` | 受影响锚点 brief、锚点、依赖正式页面 brief/SVG 和 QA。 |
| `slide_recompose` | `production` | `preserve` | 受影响页面 brief、SVG 和 QA。 |
| `slide_patch` | `production` | `preserve` | 受影响页面 SVG 和 QA；brief 只更新 defect 与候选版本。 |
```

- [ ] **Step 5: Require theme-stage hierarchy reduction**

Add to `design-system.md`:

```markdown
主题阶段不能直接从故事板生成 SVG。先把当前有效主题、布局选择和权威视觉修订历史归并到逐页 brief。每页必须明确唯一焦点、第一至第三阅读位置、主次面积或替代层级编码、完整字体阶梯、语义色和禁止母题。
```

- [ ] **Step 6: Run the focused tests**

Run:

```bash
python -m unittest tests.test_visual_generation_contract -v
```

Expected: the reference/link/brief tests pass; revision-mode token test may still fail until Task 3 completes.

- [ ] **Step 7: Record checkpoint**

Record the new artifact boundary and exact focused-test result. Confirm the stable stage list remains unchanged and no FY26 files were touched.
