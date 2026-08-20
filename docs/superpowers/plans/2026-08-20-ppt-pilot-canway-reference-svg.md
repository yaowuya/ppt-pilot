# PPT Pilot Canway Reference SVG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the “嘉为年中总结风格” pack with one synthetic, standalone, Office-safe 1280×720 reference SVG.

**Architecture:** Encode the approved palette, one deep focal card, white fact cards, pale-blue evidence boundary, violet bounded-pilot card, nested KPI cards, and a six-level typography ladder using only allowed SVG elements.

**Tech Stack:** UTF-8 SVG and Python XML/static contract tests.

## Global Constraints

- This is Plan 6 of 7 and depends on the style registry/tokens and Canway guidance plans.
- Use no customer, project, FY26, logo, remote image, gradient, filter, CSS block, or script.
- The reference is visual guidance only and cannot override a page visual brief.
- Run only fast local SVG tests.
- This workspace is not a Git repository; do not initialize Git or attempt commits.

---

### Task 1: Create the synthetic Office-safe reference SVG

**Files:**
- Create: `skills/ppt-start/assets/styles/canway-midyear-review/reference.svg`
- Test: `tests/test_style_packs.py`

**Interfaces:**
- Consumes: Canway tokens and STYLE.md.
- Produces: a content-neutral visual anchor with only allowed SVG elements.

- [ ] **Step 1: Create the complete reference SVG**

Use this standalone structure; preserve all explicit IDs, text sizes, safe margins, and direct presentation attributes:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <title>嘉为年中总结风格参考：有界验证管理假设</title>
  <desc>浅灰蓝画布上，白色事实卡、深色主命题卡、浅蓝证据边界和紫色有界试点形成层级 Bento。</desc>
  <path id="ref-bg" d="M0 0 H1280 V720 H0 Z" fill="#F5F8FC"/>

  <g id="ref-header">
    <text id="ref-kicker" x="64" y="82" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="64" dy="0">嘉为年中总结风格 · SYNTHETIC REFERENCE</tspan></text>
    <text id="ref-title" x="64" y="126" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="40" font-weight="700" data-role="title"><tspan x="64" dy="0">管理假设：统一闭环可能是</tspan><tspan fill="#1E63FF">共同短板</tspan><tspan fill="#0B1930">，但必须验证</tspan></text>
    <text id="ref-subtitle" x="64" y="158" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="400" data-role="body"><tspan x="64" dy="0">先区分已观察信号、证据边界和替代解释，再决定是否扩围</tspan></text>
  </g>

  <g id="ref-facts" data-source-id="SYNTHETIC">
    <path id="ref-facts-bg" d="M84 188 H324 A20 20 0 0 1 344 208 V612 A20 20 0 0 1 324 632 H84 A20 20 0 0 1 64 612 V208 A20 20 0 0 1 84 188 Z" fill="#FFFFFF" stroke="#DCE9F8" stroke-width="1.2"/>
    <text id="ref-facts-kicker" x="88" y="224" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="88" dy="0">01 / OBSERVED SIGNALS</tspan></text>
    <text id="ref-facts-title" x="88" y="264" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="88" dy="0">已观察信号</tspan></text>
    <circle id="ref-fact-dot-1" cx="98" cy="310" r="6" fill="#156BFF"/>
    <text id="ref-fact-1" x="118" y="318" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="700" data-role="body"><tspan x="118" dy="0">交付周期波动</tspan></text>
    <text id="ref-fact-1-note" x="118" y="344" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="16" font-weight="400" data-role="footnote"><tspan x="118" dy="0">需要统一口径</tspan></text>
    <circle id="ref-fact-dot-2" cx="98" cy="392" r="6" fill="#156BFF"/>
    <text id="ref-fact-2" x="118" y="400" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="700" data-role="body"><tspan x="118" dy="0">返工来源分散</tspan></text>
    <text id="ref-fact-2-note" x="118" y="426" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="16" font-weight="400" data-role="footnote"><tspan x="118" dy="0">不能直接归因</tspan></text>
    <path id="ref-boundary-bg" d="M88 476 H320 V588 H88 Z" fill="#EFF6FF"/>
    <text id="ref-boundary-title" x="108" y="510" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="700" data-role="body"><tspan x="108" dy="0">证据边界</tspan></text>
    <text id="ref-boundary-copy" x="108" y="546" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="400" data-role="body"><tspan x="108" dy="0">足以提出假设</tspan><tspan x="108" dy="30">不足以证明因果</tspan></text>
  </g>

  <g id="ref-hero" data-source-id="SYNTHETIC">
    <path id="ref-hero-bg" d="M388 188 H868 A20 20 0 0 1 888 208 V612 A20 20 0 0 1 868 632 H388 A20 20 0 0 1 368 612 V208 A20 20 0 0 1 388 188 Z" fill="#10233F" stroke="#203C5E" stroke-width="1.2"/>
    <text id="ref-hero-kicker" x="396" y="224" fill="#65B7F9" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="396" dy="0">02 / FALSIFIABLE PROPOSITION</tspan></text>
    <text id="ref-hero-title" x="396" y="276" fill="#FFFFFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="30" font-weight="700" data-role="body"><tspan x="396" dy="0">前置验收与门禁</tspan><tspan x="396" dy="42">能否减少周期和返工？</tspan></text>
    <text id="ref-hero-copy" x="396" y="374" fill="#C8D6E8" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="400" data-role="body"><tspan x="396" dy="0">同时不增加质量逃逸</tspan><tspan x="396" dy="30">同一范围 · 相近复杂度 · 清晰责任</tspan></text>

    <path id="ref-kpi-1" d="M396 462 H532 A14 14 0 0 1 546 476 V560 A14 14 0 0 1 532 574 H396 Z" fill="#FFFFFF"/>
    <path id="ref-kpi-2" d="M552 462 H688 A14 14 0 0 1 702 476 V560 A14 14 0 0 1 688 574 H552 Z" fill="#FFFFFF"/>
    <path id="ref-kpi-3" d="M708 462 H844 A14 14 0 0 1 858 476 V560 A14 14 0 0 1 844 574 H708 Z" fill="#FFFFFF"/>
    <text id="ref-kpi-1-label" x="414" y="494" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="16" font-weight="400" data-role="footnote"><tspan x="414" dy="0">周期</tspan></text>
    <text id="ref-kpi-1-value" x="414" y="536" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="414" dy="0">缩短？</tspan></text>
    <text id="ref-kpi-2-label" x="570" y="494" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="16" font-weight="400" data-role="footnote"><tspan x="570" dy="0">返工</tspan></text>
    <text id="ref-kpi-2-value" x="570" y="536" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="570" dy="0">下降？</tspan></text>
    <text id="ref-kpi-3-label" x="726" y="494" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="16" font-weight="400" data-role="footnote"><tspan x="726" dy="0">质量逃逸</tspan></text>
    <text id="ref-kpi-3-value" x="726" y="536" fill="#8866FD" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="726" dy="0">不增加</tspan></text>
    <text id="ref-hero-note" x="396" y="610" fill="#65B7F9" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="396" dy="0">假设，不是定论 · 三类指标共同判断</tspan></text>
  </g>

  <g id="ref-controls" data-source-id="SYNTHETIC">
    <path id="ref-control-bg" d="M932 188 H1196 A20 20 0 0 1 1216 208 V366 A20 20 0 0 1 1196 386 H932 A20 20 0 0 1 912 366 V208 A20 20 0 0 1 932 188 Z" fill="#FFFFFF" stroke="#DCE9F8" stroke-width="1.2"/>
    <text id="ref-control-kicker" x="936" y="224" fill="#156BFF" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="936" dy="0">03 / CONTROL</tspan></text>
    <text id="ref-control-title" x="936" y="264" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="936" dy="0">替代解释</tspan></text>
    <text id="ref-control-copy" x="936" y="312" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="400" data-role="body"><tspan x="936" dy="0">容量 · 复杂度</tspan><tspan x="936" dy="34">环境 · 外部等待</tspan></text>

    <path id="ref-pilot-bg" d="M932 410 H1196 A20 20 0 0 1 1216 430 V612 A20 20 0 0 1 1196 632 H932 A20 20 0 0 1 912 612 V430 A20 20 0 0 1 932 410 Z" fill="#F7F5FF" stroke="#E5DCFF" stroke-width="1.2"/>
    <text id="ref-pilot-kicker" x="936" y="446" fill="#8866FD" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="700" data-role="footnote"><tspan x="936" dy="0">04 / BOUNDED PILOT</tspan></text>
    <text id="ref-pilot-title" x="936" y="488" fill="#0B1930" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="24" font-weight="700" data-role="body"><tspan x="936" dy="0">8 周有界验证</tspan></text>
    <text id="ref-pilot-copy" x="936" y="536" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="20" font-weight="400" data-role="body"><tspan x="936" dy="0">一个完整范围</tspan><tspan x="936" dy="34">成功 · 证据不足 · 回退</tspan></text>
  </g>

  <text id="ref-footnote" x="64" y="650" fill="#52637B" font-family="Microsoft YaHei, PingFang SC, Arial, sans-serif" font-size="14" font-weight="400" data-role="footnote" data-source-id="SYNTHETIC"><tspan x="64" dy="0">合成风格参考 · 不含真实客户、项目或经营数据</tspan></text>
</svg>
```

- [ ] **Step 2: Run the SVG style-pack test**

Run:

```bash
python -m unittest tests.test_style_packs.StylePackTests.test_reference_is_standalone_office_safe_svg -v
```

Expected: PASS.

- [ ] **Step 3: Run all style tests**

Run:

```bash
python -m unittest tests.test_assets tests.test_style_packs -v
```

Expected: PASS.

- [ ] **Step 4: Record checkpoint**

Record the final pack file list and focused-test duration. Stop before Plan 3 if any style or SVG static check fails.
