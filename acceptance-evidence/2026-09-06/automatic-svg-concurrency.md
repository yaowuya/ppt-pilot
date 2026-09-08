# 自动 SVG 并发验证记录

日期：2026-09-06。工作分支：`codex/legacy-ppt-redesign`，基准 `5871a4c306949098eb5984a94b0807d7228222ab` 上的未提交源码。保留此前旧 PPT 导入／阶段门禁改动。本次未 commit、push、创建 PR 或更新 Claude Code／Codex／DeepSeek Harness 安装。

## 实现范围

- 无需用户选择，目标最低 5；每 5 个连续、唯一、持久验证通过的结果增加 2，最高 10，压力／失败重置至 5。
- 只读 `_generation_concurrency.plan_dispatch` 与 `ppt_concurrency.py --input` 计算目标、容量上限、可用槽位、有序 dispatch IDs 和限制原因。不启动模型、不改宿主设置、不拥有工作流状态。
- 实际并发受宿主分配给本运行的总 generator 槽位、活动批次上限、剩余页和在途任务约束。未知容量保守 1，已知 0 等待，无安全隔离阻断。不能把目标最低 5 声称为任何时刻都有 5 个在途任务。
- 旧 width 3／4 活动批次和 v1 迁移 width 4 保持兼容；不可变 inventory、一次派发、旧 epoch 预留、串行提交、文稿／源稿／QA 和全局恢复门禁不变。
- `tests/test_visual_generation_contract.py` 仍是可执行契约 oracle，不是宿主生产调度器。它调用真实规划器，并修正补位时未扣除生成中／已预留任务的问题。

源码 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `skills/ppt-start/scripts/_generation_concurrency.py` | `4c9ddc2f3a80b13233a8b74d3ca2c350e611a26dabc6d6e3f40dca617539073f` |
| `skills/ppt-start/scripts/ppt_concurrency.py` | `22ab21f3120bf8f5da359d29c264b252ce939275ee9b4dde4cb9b57df29eb71f` |

## 测试优先与回归

先记录缺少实际 planner 的 RED，以及 manifest 拒绝 5／8／10、数字容量和大批次调度的 RED，再实现。新增 15 项 planner 测试、7 项 adaptive contract 测试；原 33 项 visual contract 保留并通过。

| 命令／检查 | 实际结果 |
|---|---|
| `py -3 -O -m unittest discover -s tests -p test_generation_concurrency.py -q`（实现 worker） | 15 tests，0 failures，1.090s |
| `py -3 -m unittest discover -s tests -p test_adaptive_generation_contract.py -q`（契约 worker） | 7 tests，0 failures，0.089s |
| `py -3 -m unittest discover -s tests -p test_visual_generation_contract.py -q`（契约 worker） | 33 tests，0 failures，0.218s |
| `<PYTHON_39> -O -m unittest discover -s tests -p '*generation*' -q` | 55 tests，0 failures，0.986s；最低支持版本与优化模式 |
| 第一轮 `py -3 -m unittest discover -s tests -q` | 685 tests，8 skipped，1 failure，72.235s：README／design 改写遗漏 `batch_width` 说明 |
| 修复后 `py -3 -m unittest discover -s tests -p test_skill_package.py -q` | 16 tests，0 failures，0.115s |
| 第二轮完整套件 | 685 tests，8 skipped，1 failure，78.048s：既有 live Office COM 进程保留断言失败；并发／文档测试通过 |
| 明确排除上述 live COM 项的回归 | 684 tests，8 skipped，0 failures，62.188s，退出码 0；不是完整套件全通过 |
| `git diff --check`（沿用仓库的正常换行配置） | PASS |

没有删除、改写或跳过失败断言来伪造全量通过。排除 live COM 的复验使用 `unittest` discovery 后仅筛掉完整 ID `test_ppt_editable_office_contract.OfficeContractTests.test_com_smoke_preserves_preexisting_powerpoint_processes`，其余测试保持原状。完整套件的失败记录仍保留。

## 独立复核与技能诊断

独立只读代码复核未发现本次并发范围内的 BLOCKER／重要问题：容量计算、重放去重、旧 epoch 占位、部分归因记录 fail-closed、门禁保留和历史迁移兼容均已核对。

`EVIDENCE_CLASS: DIAGNOSTIC`：独立 agent 完整读取 canonical Skill 与自动并发参考，演算了 30 页／容量 10、容量 3 已占满、单槽补位、容量 0／未知／无隔离、旧批次4、源变更／审稿 pending、超时和尾批场景；未发现要求用户选择并发量或允许超额派发的实质歧义。“width 1”已明确为实际调度上限，不修改 manifest。诊断发现 30 页只能形成 5、7、9、9 的批次，因此后续真实验收提示使用 40 页，留出 10 页完整批次的观测窗口。

提示见 [`automatic-svg-concurrency.md`](../../tests/prompts/automatic-svg-concurrency.md)。诊断没有生成 SVG，没有实际验证 5～10 个宿主模型任务同时运行，也没有性能倍数测量。

## 单列：既有 Office COM 冒烟失败

失败位于 `tests/test_ppt_editable_office_contract.py:456`：测试前记录的进程身份 `(36236, 2026-09-06T03:43:37.3473859Z)` 不在测试后快照中。该失败只证明两次快照间进程消失，不能据此确定谁关闭了它。

只读诊断确认此测试会真实激活 COM；`capability_only` 只跳过文稿操作，仍进入清理。适配器按内部进程基线与确切身份识别 owned 实例后执行 Quit／必要时 Kill，基线已存在的身份有显式保护，但测试外部退出或基线竞争仍可能影响断言。未重跑该 live 项，未启动 Office 诊断、未杀进程、未修改 Office 模块。后续如修复此问题，应单独授权与验证，不能算作本次自动并发通过证据。

## 真实宿主状态

Claude Code、Codex、DeepSeek Harness 的新版安装与 5～10 路实际模型生成均为 `PENDING`。当前会话协作工具总槽位上限为 4（含主任务），不能证明实际 5 路或 10 路。仅确认源代码、运行时纯规划器、契约 oracle 和技能诊断范围内的行为。
