# Style-pack Verification

撰写产物前必须通过硬约束校验；失败即停止，零写入。

已发布 style ID 是不可变身份。相同 ID 只允许字节完全一致的幂等重试；任何 manifest、tokens、guidance 或 prompt 字节变化都必须使用新 ID，并以 `style_pack_immutable_conflict` 停止原地覆盖。writer 先在隐藏 staging 目录完成四文件写入与验证，再原子发布不可变 pack 目录，最后在 registry 文件锁内重新读取并以 pointer-last 更新 registry。崩溃发生在 registry 更新前时只留下未注册 orphan，不会让现有 registry 指向缺失或半写 pack；同一输入重试可采用该完整 orphan 并完成注册。registry 更新不得使用预检时的陈旧 payload blind replace。

## manifest.json

- `schema_version == 1`
- `id` 与 `selection_aliases` 中至少一项一致
- `kind == "style_pack"`
- `files` 恰好等于 `{"tokens": "tokens.json", "guidance": "STYLE.md", "prompt_template": "prompt.md"}`；所有可选择的 `style_pack` 都必须自带完整模板，不允许运行时静默 fallback
- `version` 为合法 semver（如 `1.0.0`）
- `compatibility.office_safe_svg == true`
- 三个声明的 `files` 目标文件确实存在（且是本包目录下的相对路径，不允许 `..` 逃逸）

## tokens.json

- `schema_version == 2`
- 存在 `colors`、`typography`、`spacing`、`shape`、`composition`
- 存在 `prompt_baseline`，且其键恰为：
  `palette_roles, font_stack, spacing_rhythm, shape_language, composition_rules, prohibited_motifs`
- `palette_roles` 每项恰含 `token/role/use`，`token` 唯一且出现在 `colors`；`role/use` 只能使用 verifier 的闭合枚举，`prohibited_motifs` 也只能使用闭合枚举，不能把自由文本写进 Prompt 数据面
- `typography` 至少包含安全字体栈、`body >= 20`、一个标题层级和一个 `>= 14` 的支撑层级；ASCII 品牌字体可原样保留，包含换行／Prompt 语法或未知中文短语的字体值必须显式回退为 `Arial, sans-serif`，并写 `font_resolution.fallback_applied: true`
- `prompt_baseline.spacing_rhythm` 必须非空并固定包含 `outer_margin: 64`、`standard_gap: 24`；所有值为正数。`shape_language` 必须非空，至少含一个正圆角值和正 `stroke_width`
- `composition_rules` 必须非空，键和值只能使用 verifier 的闭合类型／枚举；根层 `spacing/shape/composition` 与 `prompt_baseline` 中同名数据必须逐值一致

## prompt.md

- `{{NARRATIVE}}` 恰好出现 1 次（且为独立整行）；移除该 token 后不得残留或缺配 `{{`、`}}`、`[[`、`]]` 分隔符
- 不含 `[[CANONICAL_NARRATIVE_BULLETS]]`、`[[STYLE_BASELINE]]`，也不含大小写或空格变体的结构化来源标注（`source =`、`[claim = ...]`、`data-source-id`、`SRC-<数字>`）
- 从 byte 0 开始按顺序各保留且仅保留一个结构标题：`# Role`、`## Workflow`、`### 步骤 1`、`### 步骤 2`、`### 步骤 3`、`### 兼容约束`；不得缺失、粘连、重复、重排或带前导正文
- 必须包含 generator 对稳定非来源 `block_id` 的明确指令：每个 ID 只能在规范 `data-block-id` 精确属性值中临时回显一次，禁止进入 text／tail／其他属性名值；不得要求 generator 自行生成来源 ID，泄漏以 `fact_source_mismatch` 在 candidate write 前失败
- 创建模板时必须把本次提取出的具体颜色、字体、间距、形状、构图与禁止母题静态物化进正文；不同风格证据不得产生相同的通用 prompt bytes
- 除步骤 2 的七行规范风格指令外，Role、步骤 1、步骤 3、兼容约束和最终输出命令必须与 canonical hard shell 字节一致；整份 `prompt.md` 必须精确等于 verifier 从同包 `tokens.json` 确定性合成的结果，任一同步篡改也要拒绝
- CRLF／CR 可规范化为 LF；VT、FF、FS／GS／RS、NEL、U+2028、U+2029 不算换行并必须拒绝；最多剥离文件开头一个 UTF-8 BOM
- 不含任何 HTML `[[...]]` 遗留 marker、不含 `.redesign.md` 引用

## STYLE.md

- 不含 `REDESIGN.md`、`完整生成 prompt`、`完整 prompt`、`可执行 prompt`
- 不含单页成品示例、参考构图、固定区域图；不含 `reference.svg`/`参考 svg`
- 明确说明本文件与 `tokens.json` 定义身份/令牌/指导，**不得**从成品示例反推构图
- 保底中文正文 ≥80 个汉字

## 校验失败处理

任何一条不满足 → `reason` 记录具体违例（如 `prompt_template_invalid` / `tokens_schema_invalid` / `manifest_identity_mismatch`），返回 `BLOCKED`，**不写任何包文件、不改 registry**。
