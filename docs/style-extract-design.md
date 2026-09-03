# PPT Style Extract

## 目标

`ppt-style-extract` 是一个面向 PPT Pilot 的「风格固化」Skill：用户给一个**模板 PPT**（`.pptx`）、或若干**图片**（渲染图/SVG/PNG）、或一句**文字 prompt**，它把一个可复用的**内置风格包（style pack）** 固化成用户自己的风格，注册进 `assets/styles/registry.json`，让 `ppt-start` 之后能直接选用。

风格包的产物与 `ppt-start` 消费的契约完全一致：`manifest.json` + `tokens.json`（schema v2，含 `prompt_baseline`）+ `STYLE.md` + `prompt.md`（恰好一个 `{{NARRATIVE}}` 注点）。

## 输入与输出

| 输入形态 | 说明 | 提取来源 |
|---|---|---|
| 模板 PPT | 一个 `.pptx`，作为风格母版 | 主题 XML、母板/版式、形状填充/描边/圆角、文本字体/字号、色板 |
| 图片 | 一张或多张渲染图（SVG/PNG/JPEG） | 视觉取样：主色、字体族、间距、卡片圆角、阴影、构图倾向 |
| prompt | 一句自然语言，描述想要的感觉 | 语义映射到 tokens 与指导语 |

输出（写到一个用户风格包目录）：

```text
<user-style-packs>/<style-id>/
├── manifest.json
├── tokens.json
├── STYLE.md
└── prompt.md
```

注册：把 `<style-id>` 追加/同步到 `assets/styles/registry.json`（幂等，`kind: style_pack`），并保证 id/display_name 唯一。

## 硬约束（契约校验失败则停止，不写入）

1. `manifest.json`：`schema_version == 1`、`kind == "style_pack"`、`files` 恰好 `{tokens, guidance, prompt_template}`、id 与 `selection_aliases` 一致。
2. `tokens.json`：`schema_version == 2`；`prompt_baseline` 恰含 `palette_roles, font_stack, spacing_rhythm, shape_language, composition_rules, prohibited_motifs` 六键，且 `palette_roles[].token` 都出现在 `colors`。
3. `prompt.md`：`{{NARRATIVE}}` 恰好出现 1 次；不含 `[[CANONICAL_NARRATIVE_BULLETS]]` / `[[STYLE_BASELINE]]` / `source=`；保留 `# Role`、`## Workflow`、`### 步骤 1/2/3`、`### 兼容约束` 结构。
4. `STYLE.md`：不引用 `REDESIGN.md` / “完整生成 prompt” / “可执行 prompt”；不包含单页成品示例、参考构图或固定区域图；不反向从成品示例反推构图。

违反以上任何一条，返回 `BLOCKED`，且一个文件都不写。

## 确定性 extractor

核心是**从字节里可复现提取**，不靠主观臆断：

- `extract_pptx.py`：用 `python-pptx` + lxml 读 `ppt/theme/theme1.xml`（主色、字体、`latin/ea` 字体族、圆角/填充/描边统计）、`ppt/slideMasters/*.xml`（版式背景/占位符）、每页 `slides/*.xml`（形状填充/描边、`prstGeom` 圆角、`a:rPr` 字号/加粗）。剔除颜色、字号、圆角、间距的极小/极大离群值，给出主色 / 字体族 / 字号阶梯 / 圆角 / 间距节奏 / 形状语言。
- `extract_image.py`：对 SVG 逐 `<text>`/填充色取样；对 PNG 做像素取样（RGB 直方图聚主色），给出近似色板与间距/圆角参考。PNG 采样在本沙箱不可用时不降级为臆测，写入 `unavailable` 并如实披露。
- `analyze_prompt.py`：把一句 prompt 映射到颜色/字体/间距/构图倾向的初始 tokens（不伪造证据，缺省值以契约为准）。

## 编排

`SKILL.md` 负责：
1. 分辨输入形态（.pptx / 图片 / prompt）；
2. 跑对应 extractor，得到候选 token 集；
3. 补全 `prompt_baseline`（palette_roles 语义角色、composition_rules、prohibited_motifs）与 `STYLE.md` 指导语、`prompt.md` 模板；
4. 校验硬约束；通过则写包 + 幂等注册 registry，失败则 `BLOCKED` 零写入；
5. 返回产物路径与一段写进 `ppt-start` 的可复用说明。

## 模块结构

```text
skills/ppt-style-extract/
├── SKILL.md
├── references/
│   ├── input-and-output-contract.md
│   ├── extraction-contract.md
│   └── style-pack-verification.md
├── assets/
│   └── style-pack-schema.json        # 可选：作为校验的静态 Schema 参考
├── scripts/
│   ├── extract_pptx.py
│   ├── extract_image.py
│   ├── analyze_prompt.py
│   └── write_style_pack.py           # 组装 + 硬校验 + 幂等注册 registry
└── _style_extract/
    ├── __init__.py
    ├── builder.py
    ├── verify.py
    └── registry.py
```

## 非目标

- 不反向生成「单页成品示例/参考构图」进风格包（测试禁止）。
- 不把用户模板渲染成 SVG 再塞进 `ppt-start` 的示例资产。
- 不改动 `ppt-start` 运行时；只新增一个可复用的风格包。

## 验证

新增 `tests/test_style_extract.py`：
- 用内嵌的小型 `.pptx` fixture 或 lxml 构造的 XML 片段跑 `extract_pptx`，断言能得出主色/字体/字号/圆角；
- 校验 `write_style_pack` 对合法输入产出满足全部硬约束的包，且幂等注册 registry（重复运行不产生重复 id）；
- 校验非法输入（`{{NARRATIVE}}` 计数 ≠1、缺六键、含禁用 token）会 `BLOCKED` 且零写入。

保证既有 `tests/test_style_packs.py`、`tests/test_skill_package.py`、`tests/test_tools_package.py` 仍通过（新技能不改动 `ppt-start`/`ppt-editable`，也不改变安装脚本对两个技能的枚举）。
