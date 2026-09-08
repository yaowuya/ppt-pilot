# 实时进度面板验收记录

日期：2026-09-05。分支：codex/live-progress-dashboard。环境：Windows、Python 3.13、真实 Chromium 浏览器。范围为本地观察服务、静态页面、工作流指令与安装包；不是三个宿主模型分别从文档生成整套 PPT 的验收。

## 自动化证据

- 最终命令：`py -3 -m unittest discover -s tests -q`，600 项，51.836 秒，OK，7 项跳过，0 失败。测试输出另有临时目录清理 ResourceWarning，不影响退出码。
- 新增测试 41 项：状态投影 28、HTTP 6、服务生命周期 7；覆盖持久候选与摘要、dirty、恢复优先级、坏 JSON、安全路径、Host/Origin、控制令牌、端口冲突、并发启动、停止身份及退出清理竞争。
- 新增用例中的两项跳过：本机不具备创建符号链接权限；本机文件系统对独立普通 Win32 FILE_SHARE_DELETE 句柄也拒绝替换打开的目标，所以未完成“持有读取句柄期间原子覆盖”平台能力验收。实现保留共享删除，并在打开安全文件句柄后释放目录句柄；不据此声称所有 Windows 文件系统均无写入竞争。其余五项为已有测试跳过项。
- `node --check skills/ppt-start/assets/dashboard/app.js` 与 `git diff --check` 通过。
- 独立复核发现 manuscript_blocked/review_unavailable 未映射到审查阶段。新增回归先观察到 unknown != blocked，再修正并通过；前端同步修正批准检查点与 guided/auto 模式标签。

## 浏览器动态验收

使用独立的 `ppt-output/dashboard-browser-check` 合成验收运行，不改写用户既有演示产物。

- 同一页面不刷新：brief、0/4 → production、2/4；故事板页名和新写入 SVG 自动出现。
- 修改同一个 S01.svg：预览 URL 的内容摘要从 e14dbfb5… 变为 bf86ae08…，图片成功加载，当前 S01 选择保持。
- 放大、方向键切到 S02、Esc 关闭；选择状态正确。
- 将 S01 标为 dirty：完成数由 2 降为 1，显示旧版；待确认问题带 `<img ...>` 字符串时只显示文本，提示区域没有注入 img 元素。
- 停止本次测试服务：界面显示 disconnected，仍保留 S02；在相同端口重启后自动恢复 connected，仍选择 S02。
- 390 × 844 移动视口：document.scrollWidth = 390，无页面横向溢出；列表可横向浏览。桌面与手机截图均已人工查看。
- 写入剩余正式页、清除 dirty/待确认并记录 complete 后：显示已完成、4/4，提示隐藏。
- 最终安装版本：manuscript_approved 显示“内容审查 · 已批准”，manuscript_blocked 显示“内容审查 · 审查阻断”，此前故事板仍为 complete、当前审查为 blocked。
- 重载最终静态资产后正常连接时，控制台 0 错误、0 警告；刻意停止服务期间的网络错误属于预期断线验收。

本机截图（忽略于版本控制）：`output/playwright/dashboard-desktop.png`、`dashboard-mobile.png`、`dashboard-final.png`。最后一张连接既有 example-dashboard-run 运行，显示 4/4 正式页，未更改其 production 阶段或伪称 QA 完成。

## 安装与使用边界

执行现有 update-hosts.ps1，更新 Claude 用户技能、Codex 用户技能、DeepSeek 本地插件市场，以及当前项目 Claude/Codex 覆盖副本。安装器逐个技能校验文件数和树摘要一致；保留紧邻更新前一版，清理更早插件专用备份。DeepSeek 版本：1.0.0+codex.20260905175437。

三个宿主位置的入口都成功执行 status；最后从安装后的 Codex 用户 Skill 启动服务、加载静态资产并完成浏览器检查。新会话加载更新后的 ppt-start 指令，才会执行自动启动；已开启的会话不保证即时重读 Skill。此证据证明安装与本地服务可运行，不证明三个模型都严格执行过新指令。

验收结束时停止合成运行的服务，并启动既有 example-dashboard-run 的只读面板，返回 `http://127.0.0.1:8011/` 且 browser_opened=true。地址只在该本机服务存活时有效。不再查看时可运行：

```powershell
py -3 skills/ppt-start/scripts/ppt_dashboard.py stop --run-dir ppt-output/example-dashboard-run
```

观察面板不批准任何步骤、不替代内容审查/视觉质量门。文件更新时间不是模型心跳；正式页计数不是耗时百分比。
