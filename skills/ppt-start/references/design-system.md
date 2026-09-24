# 设计系统契约

只有 `run.json.manuscript_review.state == manuscript_approved` 且没有 blocking finding 时才能进入视觉阶段。视觉样式不得改变、隐藏或扩张已批准主张。

## 风格选择

从 `assets/styles/registry.json` 读取注册风格。当前内置：

- `jiawei-product`（嘉为产品，默认）；
- `canway-midyear-review`（嘉为年中总结风格）。

优先级：当前明确请求 > 本运行已批准选择 > 工作区偏好 > 默认 `jiawei-product`。明确请求未注册 ID 时报告 `style_not_registered`，不得静默替换。

每个可选 style pack 的 manifest、`tokens.json`、`STYLE.md` 和 `prompt.md` 必须存在、可读且身份一致。路径必须位于该 pack 内，不跟随 link／junction，不使用远程或绝对路径。`prompt.md` 恰好有一个 whole-line `{{NARRATIVE}}` 注点，并与验证过的 tokens 相符。

用户品牌覆盖改变颜色、字体、间距、形状语言、构图规则或禁止母题时，使用 `ppt-style-extract` 创建新的 immutable 派生 style ID，验证后再注册和选择。无法安全创建时持久化问题，让用户选择原 pack 或停止；不得原地改写已注册 pack。

## `theme.json`

记录：

- selected style ID、display name、kind、manifest version；
- 最终色板角色、系统字体栈、字号、间距、形状和构图规则；
- 语言、已批准品牌决定、适用 visual revision IDs；
- style assets 的工作区／Skill 相对身份，不记录远程 URL 或机器绝对路径。

当前安装风格身份或模板变化会使相关视觉产物 stale；AI 返回 theme／anchor 分支重新确认，不靠补字段沿用旧批准。

## 视觉规则

- 画布 1280×720，外部安全边距 64 px，标准节奏 24 px；
- 一页一个结论、一个主强调焦点和一个有意义的关系：比较、证据、顺序、层级、分组或行动；
- 标题是结论而非主题标签；通用下限 40 px，已验证 strict-brand 标题不得低于 34 px；
- 正文至少 20 px，脚注至少 14 px；使用 style pack 的系统字体栈；
- 每行使用一个简单 `<tspan>` 和绝对 `x/y`，不依赖自动换行或 `dy`；
- 内容过多时拆页／压缩语义，不缩到字号下限以下；
- 正文对比度至少 4.5:1，大号文字和关键图形至少 3:1；
- 强调色只服务关键比较／行动，不作为装饰母题；
- 使用平面填充、简单路径和清晰轮廓；不依赖滤镜、mask、远程字体或位图填充；
- 来源只通过 final SVG machine metadata 保存，不在页面显示内部 ID、来源行或 URL。

具体布局按内容关系从 [布局目录](layout-catalog.md)选择，不为套版式新增事实或卡片。

## 锚点

生成两页锚点到 `.ppt-pilot/samples/`：

1. 封面，用于验证语气、标题和品牌；
2. 密度最高／技术最难的内容页，用于验证真实信息约束。

两页先完成结构 QA。`guided` 还需展示真实渲染并获得明确 anchor 批准；渲染不可用时写 `not_rendered` 并披露，不把 XML 检查说成视觉批准。`auto` 省略可选批准但不省略检查。

视觉反馈只更新 theme 或对应页面视觉修订；改变文案、事实、来源或故事板时返回文稿审查。
