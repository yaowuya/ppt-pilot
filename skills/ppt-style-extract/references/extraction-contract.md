# Extraction Contract

提取的目标不是「画像」，而是**能用 token 和指导语表达、能被 `ppt-start` 消费的软风格基线**。每类输入只提取其客观可复现的部分，禁止臆测。

## 模板 PPT（.pptx）

用 `python-pptx` 与 `lxml` 解析：

- **主题主色**：`ppt/theme/theme1.xml` 的 `<a:clrScheme>` 的 12 个颜色槽；仅保留 `dk1/dk2/lt1/lt2/accent1..6` 槽读出的有值颜色。
- **主题字体**：`<a:fontScheme>` 的 `<a:latin typeface>` 与 `<a:ea typeface>`（东亚字体）。
- **页面形状证据**：遍历 `slides/*.xml`，取：
  - 填充颜色（`<a:solidFill><a:srgbClr val="...">` 或 `<a:schemeClr>`）；
  - 描边色与描边宽；
  - 圆角：`<a:prstGeom prst="roundRect">` 及其 `<a:adj val="...">`（折算为像素）；
  - 字号：`<a:rPr sz="...">` 与 `<a:defRPr sz="...">`；
  - 加粗/字重：`<a:rPr b="...">`。
- **版面背景**：slide master 的 `<p:bg>` 颜色。

**离群值剔除**：对颜色/字号/圆角做简单去重与排序，保留出现频率最高的主色集合、字号阶梯、圆角值；对极小（如 <6px）或极大（如 >窗口宽）的圆角/字号剔除，避免被个别装饰元素带偏。

**输出**：`colors`（含 `canvas` 背景与主色集）、`typography`（`font_stack`、字号阶梯 `slide_title/primary_proposition/section_title/body/support/micro_label`）、`spacing`（`outer_margin` 取 64 默认，`standard_gap` 取常见卡片间距）、`shape`（`primary_radius` 取最高频圆角，`stroke_width` 取常见描边宽）。

## 参考图片

`PRIMARY IMAGE`（SVG/Png 采样）输出近似色板与间距/圆角参考。

- **SVG**：逐个 `text`/`tspan` 取 `fill`，`path`/`rect` 取 `fill`/`stroke`，统计出现频率最高的色值作为主色；从 `viewBox` 与元素坐标估间距与圆角。
- **PNG/JPEG**：像素级 RGB 直方图聚主色（若环境不支持 Pillow/像素读取，则返回 `unavailable`，不得臆测）。

## 风格 prompt

把一句话映射到初始 tokens（颜色、字体、间距、构图倾向），缺省值以契约为准；不凭空造证据。它主要影响 `STYLE.md` 的指导语与 `prompt_baseline` 的语义角色命名，具体色值仍以契约默认/用户后续校准为准。

## 边界

- 提取出的 `colors` 是**候选**，最终 `tokens.json` 可能需要在 `compose` 阶段补充 `prompt_baseline.palette_roles` 的语义角色（结论强调/次级关系/风险等），并确保每个 `palette_roles[].token` 都出现在 `colors`。
- `composition_rules` 与 `prohibited_motifs` 由 `compose` 阶段基于提取到的构图倾向生成；若 extractor 无法判定，则采用保守默认并如实披露。
- 任何 extractor 返回 `unavailable` 的部分，`write_style_pack` 必须**跳过或披露**，不能伪造。
