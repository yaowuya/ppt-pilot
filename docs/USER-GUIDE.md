# PPT Pilot 用户使用手册

面向使用者的操作手册：如何用 PPT Pilot 从一个主题或一份资料出发，产出有证据支撑的 SVG 演示，并在需要时交付原生可编辑的 PowerPoint。安装、目录结构与契约细节见 [README](../README.md)；本文只讲"怎么用"。

---

## 1. 它能为你做什么

| 你想要 | 用的技能 | 得到什么 |
|---|---|---|
| 一套演示文稿（SVG 页面） | `ppt-start` | `ppt-output/<deck-id>/slides/*.svg`（16:9，独立文件，可跨宿主恢复） |
| 原生可编辑的 PowerPoint | `ppt-editable` | `delivery/editable/<deck-id>-editable.pptx`（递归分组、可编辑文本/形状、Office 验证证据） |
| 预览页 + 图片式 PPTX + 演讲者备注 | `tools/deck-deliver.ps1` | `preview.html` + PPTX + 1280×720 PNG（可选伴随工具，不是 Skill） |

一次 `ppt-start` 运行会走完整条质量流水线：简报 → 大纲/故事板 → 文稿审查（硬质量门）→ 主题/风格 → 逐页生成 → QA → 完成。你不需要记住这些阶段，只需要在关键节点回答问题、做批准。

---

## 2. 开始之前

- **装好技能**：按 [README](../README.md) 的安装章节把 `ppt-start` 与 `ppt-editable` 装到你的宿主（Claude Code / Codex / DeepSeek Harness），或直接用一键脚本：

  ```bash
  powershell -ExecutionPolicy Bypass -File tools/update-hosts.ps1
  ```

- **准备输入**（三选一，越具体越好）：
  - 只给一个主题；
  - 给一份完整简报（受众、时长、页数、关键结论）;
  - 给一批资料（报告、数据、来源文件）。

- **可选：写一份工作区偏好档案** `ppt-output/pilot-preferences.json`，记录品牌色、字体、偏好风格、语言与保密限制，避免每次重复回答。示例：

  ```json
  {
    "schema_version": 1,
    "brand": { "colors": ["#156BFF"], "font_stack": "Microsoft YaHei, Arial, sans-serif", "notes": "强调色只用于关键比较" },
    "style": { "preferred_style_id": "canway-midyear-review" },
    "audience": { "name": "运营管理层", "desired_action": "确认 H2 资源取舍" },
    "language": "zh-CN",
    "confidentiality_restriction": "内部资料不得外发到网络"
  }
  ```

  优先级固定为：当前请求明确答案 > 本运行已批准产物 > 偏好档案 > 安全默认值。档案只能记录限制型保密策略；跨运行有效的网络或披露授权必须由用户显式给出并记录为 standing 授权。格式错误时披露原因并整体忽略，不影响运行。

---

## 3. 发起一次新运行

在宿主对话里用显式启动词，后跟一句自然语言需求：

| 宿主 | 启动词 | 示例 |
|---|---|---|
| Claude Code | `/ppt-start` | `/ppt-start` + "根据 inputs/ 里的季度报告做一份 10 页中文策略演示，guided 模式" |
| Codex | `$ppt-start` | `$ppt-start` + "从 ppt-output/example-deck/ 恢复运行并继续" |
| DeepSeek Harness | `ppt-start` | `ppt-start` + "做一份 FY26 上半年总结演示，auto 模式" |

自然语言请求（不写启动词）通常也能触发技能；自动发现不明确时再补启动词。

### 执行策略：guided 还是 auto

- **guided**（默认，推荐）：在简报、大纲、锚点页三个批准点各提一个直接问题，等你明确回答后才推进。
- **auto**：只有你显式指定才使用；跳过可选问题直接走完，但涉及权限（如联网研究、对外披露）或没有安全默认值的业务决策时仍会问你。

> 推荐 ≠ 确认。技能给出推荐项后必须等你答复，不会替你拍板。

---

## 4. 运行中你会经历什么

1. **简报确认**：技能复述它理解的需求；缺信息会按依赖顺序一次只问一个问题。
2. **大纲 + 故事板**：产出结论先行的 `大纲.md`（这是你唯一必须亲自看的文件，含每页排版逻辑）与内部故事板。**大纲批准前不会进入视觉设计。**
3. **文稿审查（硬质量门）**：优先由独立子 Agent 只读审查五个文稿文件；任何 `BLOCKER`/`HIGH` 问题未解决都会阻断，材料不足会以"材料缺口"逐条向你提问。零问题也会保存显式 PASS。
4. **主题与风格**：确认 `theme.json` 与风格包（可用 `canway-midyear-review`、`jiawei-product` 等内置风格，也可给品牌色覆盖）。
5. **逐页生成**：每页在隔离上下文中生成 SVG，默认每批 4 页；每次派发都会打印一行进度（`[deck-id] 第 N 次请求 slide=S03 …`），让你随时知道在做什么、还剩几次请求预算（每页上限 4 次）。
6. **QA**：单页硬检查 + 实际渲染视觉检查 + 整套演示 QA，全部通过才推进；无法渲染时如实记录 `visual_qa: not_rendered`。

### 你需要做的决定只有三类

- **批准**：大纲、锚点页、最终交付——明确说"批准"或提出修改；
- **回答问题**：一次一个，答完才继续；
- **修订分类**：改几个字（`patch`）、整页重排（`recompose`）、还是动事实/来源（会触发重新审查）——分不清时技能会先问你。

---

## 5. 完成后：拿你的交付物

运行目录 `ppt-output/<deck-id>/` 里：

- `大纲.md` —— 给你看的；
- `slides/*.svg` —— 最终页面；
- `.ppt-pilot/质量检查报告.md` —— QA 结论；
- 其余 `.ppt-pilot/` 内部产物无需查看。

整套 SVG 完成并通过 QA 后，插件会**主动提示下一步**，按你需要选择：

| 你要什么 | 怎么做 | 得到什么 |
|---|---|---|
| 只看 SVG / 浏览器预览 | 直接用 `slides/`，或运行 `tools/deck-deliver.ps1`（自动生成 `preview.html`，可选 `-ExportPng`） | 静态预览页 / PNG |
| 图片式 PPTX + 演讲者备注 | `tools/deck-deliver.ps1`（需本机 PowerPoint） | PPTX + 备注清单 |
| **原生可编辑 PPTX**（可改字、可改形状） | 调用 `ppt-editable` 技能 | `delivery/editable/<deck-id>-editable.pptx` |

`deck-deliver.ps1` 用法（可选伴随工具，在仓库根目录运行）：

```bash
powershell -ExecutionPolicy Bypass -File tools/deck-deliver.ps1                # 自动探测唯一运行
powershell -ExecutionPolicy Bypass -File tools/deck-deliver.ps1 -RunDir ppt-output/<deck-id> -ExportPng
```

- 始终生成 `<run>/preview.html` 联系表：缩略图网格 + 单页查看器（方向键翻页、Esc 关闭），纯静态、无外部资源；
- 从 `.ppt-pilot/故事板.md` 解析每页 `assertion_title`／`audience_takeaway`／`next_link`，自动写入 PPTX 演讲者备注；
- 调用本机 PowerPoint（COM 自动化）把每页 SVG 插入 16:9 PPTX 并复开校验；本机没有 PowerPoint 或指定 `-SkipPptx` 时跳过该步，preview.html 仍可用；
- `-ExportPng` 额外导出每页 1280×720 PNG 作为渲染证据；结果清单写入 `<run>/delivery/delivery-result.json`；
- 工具只新增 preview.html 与 `delivery/`，不修改任何运行产物。退出码：`0`=PPTX+preview 成功；`3`=仅 preview 成功。

调用 `ppt-editable` 的方式（与 `ppt-start` 同宿主同前缀）：

```text
Claude Code:  /ppt-editable  请把 ppt-output/<deck-id>/ 转换为原生可编辑 PowerPoint。
Codex:        $ppt-editable  请将该完成运行转换为可编辑 PPTX，并保留递归分组和备注。
DeepSeek:     ppt-editable  请把 ppt-output/<deck-id>/ 转换为经验证的原生可编辑 PowerPoint。
```

`ppt-editable` 会自带完整门禁并返回四种结果之一：

- `PASS` —— 全部结构/Office/视觉验证通过，发布 `<deck-id>-editable.pptx`；
- `GENERATED_UNVERIFIED` —— 本机缺 PowerPoint/Pillow 能力，只发布 `<deck-id>-editable-unverified.pptx`，并保留已验证旧版不动；
- `BLOCKED` / `FAILED_VERIFICATION` —— 不发布新文件，保留证据。

> 任何时候已验证的旧版 PPTX 都不会被未验证的新构建覆盖。

---

## 6. 中断了怎么办：resume

运行状态全部持久化在 `run.json`，换一台机器、换一个宿主都能继续。直接说：

```text
/ppt-start  请从 ppt-output/<deck-id>/ 恢复运行并继续。
```

恢复顺序：待回答问题 → 审查轮次 → 生成 blocker → 活动批次 → 阶段扫描。已批准的上游工作（大纲、故事板、主题）不会被重算。

---

## 7. 改内容：revise 的三种粒度

| 你说 | 技能理解为 | 代价 |
|---|---|---|
| "第 3 页标题字号太小" | `patch`（局部修补） | 只重生成该页，不重新审查 |
| "第 3 页信息太多，重新排版" | `recompose`（整页重构） | 重新编译该页 prompt，从空白构图重做；不重新审查 |
| "这个数字改成 X" / "结论改成 Y" | 事实/主张变化 | **使文稿批准失效，必须重新进行文稿审查**后才可再生成视觉页 |

分不清时技能会先提一个直接问题确认，再动手。纯视觉修改不会让你重走审查。

---

## 8. 常见问题

**Q: 一定要联网吗？**
不需要。默认用你提供的资料；联网研究是可选能力，且机密内容默认不出网。研究不可用时技能会限定未验证主张，不会编造。

**Q: 生成的 SVG 能直接改成 PPT 吗？**
两条路：`tools/deck-deliver.ps1`（图片式插入，快）；`ppt-editable`（原生可编辑形状/文本，带 Office 验证，慢但真正可编辑）。

**Q: 运行到一半报 `BLOCKED` 怎么办？**
看 `run.json.visual_generation_blocker` 与 QA 报告里的具体失败项；修掉对应上游问题（事实、来源、模板、宿主能力）后 `resume`。每页最多 2 次 patch + 1 次确定性回退，用尽即停，不会无限重试。

**Q: 可以只用 ppt-start、不用 ppt-editable 吗？**
可以，两者独立安装、独立触发。`ppt-start` 完成时只是"提示"你可以转可编辑 PPT，不会替你执行。

**Q: 产物写到哪里？会不会污染我的配置目录？**
全部写入当前工作区 `ppt-output/<deck-id>/`；禁止写入 Skill 或宿主配置目录。

---

## 9. 术语速查

| 术语 | 含义 |
|---|---|
| deck-id | 本次运行的目录名，`ppt-output/<deck-id>/` |
| guided / auto | 逐步询问批准 / 跳过可选问题直接完成 |
| 文稿审查 | 冻结五文件后的独立质量门；`BLOCKER`/`HIGH` 未解决即阻断 |
| generation prompt | 每页编译出的完整生成指令，持久化于 `.ppt-pilot/generation-prompts/` |
| patch / recompose | 局部修补 / 整页重构（不改变事实时） |
| `visual_qa: not_rendered` | 无法实际渲染时的如实记录，不算视觉通过 |
| `PASS` / `GENERATED_UNVERIFIED` | `ppt-editable` 的验证通过 / 能力缺失未验证两种发布状态 |

---

*安装、架构与验收细节见 [README](../README.md)、[设计文档](design.md) 与[验收文档](acceptance.md)。*
