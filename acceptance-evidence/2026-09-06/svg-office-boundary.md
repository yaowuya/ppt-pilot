# SVG 与 Office 启动边界验证

日期：2026-09-06。分支 `codex/legacy-ppt-redesign`；保留此前旧稿导入与自动并发的未提交改动。本次只修改源码、工作流说明和测试；未 commit／push／更新三个宿主安装。

## 范围与行为

- SVG 的锚点、生产、修订、逐页／整套 QA 使用静态结构／Office-safe 子集、事实来源、几何和浏览器／非 Office 实际视觉检查；不启动 PowerPoint／WPS，不逐页建临时 PPT。没有真实渲染仍按原规则披露／阻断，不降低视觉检查要求。
- 原稿在 `brief` 中按需本地渲染、已授权 `.ppt` 转换仍保留；同源 hash 的有效核对证据在生产阶段复用。原生可编辑／图片式 PPTX 的 Office 验证留到 `complete` 后且用户明确选择的交付路径。
- 仅预览文档与示例显式使用 `deck-deliver.ps1 -RunDir <run> -SkipPptx`，不附 `-ExportPng`。旧的已完成运行 PPTX 命令保持兼容；工具在非 `complete` 且未指定 `-SkipPptx` 时，于输出写入与 Office 探测前抛错。
- 原 `checks.office` 字段保留，明确为静态 Office-safe 子集检查，不代表实际应用验证。
- 真实 COM 冒烟仅在 `PPT_EDITABLE_LIVE_OFFICE_TESTS=1` 且能力可用时执行；普通回归默认 skipped。没有改动 Office 适配器、关闭进程逻辑或 `ppt-editable` 的验证门禁。

## RED → GREEN

### 技能行为诊断

`EVIDENCE_CLASS: DIAGNOSTIC`，不是实际宿主生成或 Office 验收。

修改前独立 agent 读取原 Skill 后，对于“5 路生成中、S03 返回、用户今天只要 SVG／浏览器预览、Office 已安装”的场景明确选择：

> I would also launch PowerPoint during S03 QA now

理由是原 `qa-and-revision.md:124` 的条件允许实测，以及原 `redesign-prompt.md:213` 的候选前 PowerPoint 检查。未实际启动应用。

修改后全新独立 agent 在同场景选择静态检查＋非 Office 实际视觉检查，遵守顺序提升；预览指定 `-SkipPptx`，知道退出码 3 仅代表 preview-only 成功。额外覆盖完成后的可编辑 PPTX、旧稿 brief 核对、已核对证据复用及“不要留 skipped”的测试压力，均区分授权／阶段与能力，不为消除 skip 启用 COM。诊断未写文件、生成页面或调用应用。

独立代码审查发现旧稿文档“完成前”段仍留有 Office 验证表述；已修正为完成前非 Office 渲染、完成后且明确请求才做 Office 验证，并经原 reviewer 只读复核确认无剩余 Critical／Important 问题。可复用诊断场景见 [`svg-office-boundary.md`](../../tests/prompts/svg-office-boundary.md)。

### 自动化行为测试

新增 `tests/test_office_activation_boundaries.py`，实际执行测试发现／skip 门禁和交付脚本分支。仅替换外部 Office 调用及其能力／进程快照，并将 `Find-PowerPointExe` 的函数体替换为探测前 tripwire；业务阶段判断、预览 HTML／JSON 输出和退出码保持真实。没有启动 Office，也没有将测试桩结果当作真实 Office 验证。

- RED：5 tests，6 failures，1.857s。未显式启用的 5 个环境变量变体均没有 skip；production 运行触达 Office probe（被 tripwire 阻止）。
- GREEN：同命令 `py -3 -m unittest discover -s tests -p test_office_activation_boundaries.py -q`，5 tests，0 failures，1.723s。
- Python 3.9 优化模式：`D:/ProgramFiles/miniconda3/envs/py39/python.exe -O -m unittest discover -s tests -p test_office_activation_boundaries.py -q`，5 tests，0 failures，2.205s。
- 第一次全量：690 tests，9 skipped，1 failure，76.403s。主任务同时运行 Python 3.9 测试，临时 `.pyc.<id>` 被安装摘要测试枚举后消失；失败来自字节码缓存竞争。没有修改安装器来隐藏失败。
- 串行复验：设置仅当前测试进程环境 `PYTHONDONTWRITEBYTECODE=1` 后运行 `py -3 -B -m unittest discover -s tests -q`，**690 tests，9 skipped，0 failures，67.548s**。此时真实 Office opt-in 环境变量未设置，所有 live COM 路径保持未启用。存在一个 `TemporaryDirectory` 自动清理 ResourceWarning，不影响测试结果。

## 限制

本次验证覆盖真实脚本的安全路由和预览输出、测试入口门禁、文档一致性与技能诊断，不是三宿主完整 SVG 生产现场验收。项目 `.agents/skills` 和用户级插件安装未同步，加载旧副本的会话仍可能执行旧规则。

此前真实 Office 进程保留测试失败仍是独立未解决事项。本次仅将它改成明确授权才启用；没有重跑，也没有将其标为 PASS。真实 Office／PPTX 集成测试需要保存工作并使用隔离测试桌面后另行授权。
