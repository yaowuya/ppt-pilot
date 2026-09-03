# Input / Output and State Contract

本技能把「用户给的模板/图片/描述」转成一个满足 `ppt-start` 风格包契约的、可复用的用户自有风格包。

## 输入

`--input` 需要是以下三种之一（按顺序检测）：

1. **模板 PPT**：一个 `.pptx` 文件路径。
2. **参考图片**：一个图片路径，或一个文件夹路径（含 SVG/PNG/JPEG）。
3. **风格 prompt**：一段不是文件路径的文本（含空格/中文），描述想要的视觉感觉。

检测规则：存在且以 `.pptx` 结尾 → PPT；存在且是图片或目录 → 图片；否则 → prompt。检测到不安全路径（symlink/junction/outside scope）→ `BLOCKED`。

## 输出

`--out` 指向「用户风格包根目录」，本技能在该目录下写入一个子目录 `<style-id>/`：

```text
<user-style-packs>/<style-id>/
├── manifest.json
├── tokens.json
├── STYLE.md
└── prompt.md
```

`--registry` 指向要注册的 `registry.json`（通常是某个 `ppt-start` 安装里的 `assets/styles/registry.json`）。本技能把 `<style-id>` 幂等追加/同步为 `kind: style_pack` 条目。

## 状态与产物

- `PASS`：四个包文件已写入、registry 已同步。stdout JSON 含 `result: PASS`、`style_id`、`output_dir`、`note`。
- `BLOCKED`：输入不可读，或硬约束失败，或路径不安全。stdout JSON 含 `result: BLOCKED`、`reason`。**不写任何文件**。
- `UNAVAILABLE`：某能力缺失（如 PNG 像素采样）且无法在不伪造证据的情况下满足。stdout JSON 含 `result: UNAVAILABLE`、`reason`。

## 幂等与重跑

同一 `--style-id` 重新运行：先通过完整 verify，然后覆盖这四个包文件（每个文件先写临时文件再原子替换），registry 只更新既有条目（不新增重复 id）。任何一次运行在 verify 失败时都不覆盖已有文件。

## 不变量

- 本技能**不写** `ppt-start`/`ppt-editable` 的 `skills/` 树，除非 `--registry` 恰好指向该技能的 `assets/styles/registry.json`（那是唯一被允许的注册点）。
- 本技能**不生成**单页成品 SVG、参考构图或固定区域图进包。
- 本技能**不改写**用户提供的 `.pptx` 或图片。
