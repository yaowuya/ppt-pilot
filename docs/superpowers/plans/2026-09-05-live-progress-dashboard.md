# Live Progress Dashboard Implementation Plan

**Goal:** 在三个宿主执行期间用浏览器实时查看任务和 SVG。

**Architecture:** 静态页面轮询 Python 本地只读状态投影；独立服务生命周期文件，复用现有 run/transaction 产物。

**Tech Stack:** Python 3.9+ 标准库、HTML、CSS、原生 JavaScript。

**Spec:** `docs/superpowers/specs/2026-09-05-live-progress-dashboard-design.md`

## 约束

仅回环接口；无第三方运行依赖；不改 run.json schema；观察不授权生成；所有文件范围受明确 run-dir 限制。共享分支协作、文件所有权分离，主代理负责整合。

## 任务与验证

- [x] 状态投影：`scripts/_dashboard/snapshot.py` 和 `tests/test_dashboard_snapshot.py`。先用临时文件测 missing/new/legacy、dirty、pending、active v2/candidate hash、非法路径与坏 JSON；实现 `build_snapshot(run_dir: Path) -> dict`、`read_preview(run_dir: Path, relative: str) -> bytes`。失败测试先行。
- [x] 静态面板：`assets/dashboard/index.html, styles.css, app.js`。消费 spec 的 `/api/state`；DOM textContent 和 img；每秒不重叠轮询、失败提示、选择保持、列表和放大预览、响应式中文界面。浏览器验证真实状态变更及安全显示。
- [x] HTTP 与生命周期：`scripts/ppt_dashboard.py`, `scripts/_dashboard/server.py`, `lifecycle.py` 和 `tests/test_dashboard_server.py`, `test_dashboard_lifecycle.py`。先测试真实本地 HTTP、Host/Origin、白名单、start/status/stop/reuse/端口占用，再实现。start 就绪验证后才报告 URL；stop 验证实例身份。
- [x] 接入与交付：修改 SKILL.md、workflow.md，增加 references/live-dashboard.md 与 docs/LIVE-DASHBOARD.md；安装包复制验证、回归测试、真实浏览器动态验收并保存截图。文档清楚区分部署验证、浏览器验证与宿主模型行为证据。

关键命令：`py -3 -m unittest tests.test_dashboard_snapshot tests.test_dashboard_server tests.test_dashboard_lifecycle -v`；`py -3 -m unittest discover -s tests -q`；`python skills/ppt-start/scripts/ppt_dashboard.py start --run-dir <run> --open`；对应 `status`/`stop`。

验收记录：`acceptance-evidence/2026-09-05/live-dashboard.md`。最终运行 600 项，0 失败，7 项跳过；其中新增面板测试 41 项。审查阶段别名缺失已通过失败回归测试复现后修正。
