# PPT Pilot Canway Style Guidance Integration Plan

> **SUPERSEDED:** redesign prompt 所有权、编译、恢复与相关测试步骤已由 [`2026-08-21-ppt-start-style-owned-redesign-prompts-design.md`](../specs/2026-08-21-ppt-start-style-owned-redesign-prompts-design.md) 取代；本文不再作为当前执行说明。

**Goal:** Encode the human-readable “嘉为年中总结风格” art direction and wire registry-based selection into visual brief assembly.

**Architecture:** `STYLE.md` defines semantic surfaces, hierarchy, typography, layout families, and prohibitions; the design-system contract discovers it through the manifest and records style provenance in each page brief.

**Tech Stack:** Markdown design guidance and static Python contract tests.

## Global Constraints

- This is Plan 5 of 7 and depends on the style registry/tokens plan.
- The style pack contains only tokens and abstract guidance; it must not add a rendered slide exemplar.
- The style remains non-default and cannot override locked page semantics.
- Run fast local tests only; do not modify FY26 files.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Write the Canway style guidance and selection rules

**Files:**
- Create: `skills/ppt-start/assets/styles/canway-midyear-review/STYLE.md`
- Modify: `skills/ppt-start/references/design-system.md:7-29`
- Modify: `skills/ppt-start/references/visual-brief-and-generation.md`
- Test: `tests/test_style_packs.py`

**Interfaces:**
- Consumes: manifest and token files from Task 2.
- Produces: human-readable art direction used during visual brief assembly.

- [ ] **Step 1: Write `STYLE.md` with explicit semantic rules**

Use these required sections and rules:

```markdown
# 嘉为年中总结风格

## 使用场景
适用于 SaaS、研发、交付、组织和治理类管理汇报。结论先行，优先展示判断、证据边界、过程门槛和管理行动。

## 核心识别
默认画布 #F5F8FC。单行结论标题允许一个短语使用标题强调蓝。复杂论证页允许一张 #10233F 深色主卡建立唯一焦点；不能让所有页面都复制同一深色主卡。

## 语义表面
白色事实卡；浅蓝证据边界或核心结论；紫色 AI、有界试点、高风险或失败分支；深色主卡承载本页关键命题。颜色必须和文字标签同时表达语义。

## 层级 Bento
卡片覆盖约 40%–60%。主卡在面积、字号、明暗或位置上显著强于次卡；面积编码时默认至少 1.5 倍。主卡可以嵌套 KPI 子卡形成二级层级。每页最多一处轻阴影。

## 字体与标题
使用标题、主命题、区块标题、正文、辅助、微标签六级阶梯。关键决策信息使用正文及以上字号；微标签只承载编号或非关键元信息。标题优先单行，短语级强调不能拆散句义。

## 内容驱动构图
论证页使用事实—命题—控制—试点；流程页使用连续闸门和回退分支；时间箱页使用角色索引、比例时间轴和结果矩阵。不得为了统一外观机械重复一个模板。

## 禁止项
禁止左侧长蓝条、背景图片、渐变、等权卡片墙、全页阴影、无语义装饰线、把阶段交付写成最终验收，以及用颜色替代必要文字。

## 抽象风格资产
风格包只包含机器可读 tokens 与抽象设计规则，不得包含单页成品示例、参考构图或固定区域图。每页必须根据当前 visual brief 的内容语义重新推导构图。
```

- [ ] **Step 2: Add registry-based discovery to `design-system.md`**

State:

```markdown
新安装先读取 `assets/styles/registry.json`。`legacy_seed` 直接读取入口 JSON；`style_pack` 读取 manifest，再读取 tokens 和 STYLE.md。用户给出稳定 ID 或唯一中文显示名时直接选择；未明确选择时仍按现有 guided/auto 规则决定，不得因新增风格包把它设为默认。风格包不得携带单页成品 SVG 或固定构图参考。
```

Retain fallback behavior for installations without a registry: use the three existing flat seeds.

- [ ] **Step 3: Require style provenance in each visual brief**

In `visual-brief-and-generation.md`, require:

```text
selected_style_id
selected_style_display_name
style_manifest_version
style_token_path
style_guidance_path
```

Add this exact precedence rule:

```markdown
风格包说明服从已批准内容、证据边界和逐页语义。tokens 与 guidance 只提供抽象视觉规则；不得从成品示例或既有 SVG 反推构图，也不得把单页区域、卡片数量或连接关系当成模板。
```

- [ ] **Step 4: Run guidance tests**

Run:

```bash
python -m unittest tests.test_style_packs.StylePackTests.test_rules_capture_identity_and_prohibitions -v
```

Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Record that the style is discoverable by both ID and Chinese name but remains non-default.
