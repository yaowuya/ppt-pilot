# Style-pack Verification

撰写产物前必须通过硬约束校验；失败即停止，零写入。

## manifest.json

- `schema_version == 1`
- `id` 与 `selection_aliases` 中至少一项一致
- `kind == "style_pack"`
- `files` 恰好等于 `{"tokens": "tokens.json", "guidance": "STYLE.md", "prompt_template": "prompt.md"}`
- `version` 为合法 semver（如 `1.0.0`）
- `compatibility.office_safe_svg == true`
- 四声明的 `files` 目标文件确实存在（且是本包目录下的相对路径，不允许 `..` 逃逸）

## tokens.json

- `schema_version == 2`
- 存在 `colors`、`typography`、`spacing`、`shape`、`composition`
- 存在 `prompt_baseline`，且其键恰为：
  `palette_roles, font_stack, spacing_rhythm, shape_language, composition_rules, prohibited_motifs`
- `palette_roles` 每项的 `token` 都出现在 `colors`
- `prompt_baseline.spacing_rhythm` 与 `prompt_baseline.shape_language` 键值属合理范围

## prompt.md

- `{{NARRATIVE}}` 恰好出现 1 次（且为独立整行）
- 不含 `[[CANONICAL_NARRATIVE_BULLETS]]`、`[[STYLE_BASELINE]]`、`source=`
- 保留结构标题：`# Role`、`## Workflow`、`### 步骤 1`、`### 步骤 2`、`### 步骤 3`、`### 兼容约束`
- 不含任何 HTML `[[...]]` 遗留 marker、不含 `.redesign.md` 引用

## STYLE.md

- 不含 `REDESIGN.md`、`完整生成 prompt`、`完整 prompt`、`可执行 prompt`
- 不含单页成品示例、参考构图、固定区域图；不含 `reference.svg`/`参考 svg`
- 明确说明本文件与 `tokens.json` 定义身份/令牌/指导，**不得**从成品示例反推构图
- 保底中文正文 ≥80 个汉字

## 校验失败处理

任何一条不满足 → `reason` 记录具体违例（如 `prompt_template_invalid` / `tokens_schema_invalid` / `manifest_identity_mismatch`），返回 `BLOCKED`，**不写任何包文件、不改 registry**。
