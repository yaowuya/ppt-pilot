# 外部旧 PPT 重设计验收记录

## 范围

分支 `codex/legacy-ppt-redesign`，起点 `5871a4c306949098eb5984a94b0807d7228222ab`。参考目录仅只读调查，本轮不含安装、推送或真实客户稿件生成。

## 基线与 TDD

- 原基线：`py -3 -m unittest discover -s tests -q`，600 tests，7 skipped，0 failures，66.858s。Windows 受限执行首次因临时目录权限失败；在获准的正常临时目录权限下重跑通过，非代码回归。原有 TemporaryDirectory ResourceWarning 仍存在。
- 主集成 RED：新增 `test_source_redesign_integration.py` 后执行同名 discover，失败于 `ppt_source_intake.py` 尚不存在（退出 2）。
- 主集成 GREEN：公开 intake CLI 创建真实合成 PPTX 清单，随后普通及 `python -O` gate 均拒绝 auto/production/pending-review 直接进入 theme，检查前后目录文件 hash 相同，源文件不变；1 test 通过。
- 解析器与 gate 的独立 RED/GREEN 记录见同日 source-intake-report / source-gate-report；最终总结果见下方验证记录。

## 行为基线

fresh、无历史继承的 `redesign_baseline` 读取修改前当前 Skill 及其引用，面对“旧 PPTX、无 run、内容不变、赶时间”选择 new + source-driven、默认 guided、正式文稿审查。它并未复现用户报告的跳步，但指出旧稿专用入口／解析产物契约缺失，路径是推导结果。auto/production/pending 变体也拒绝凭顶层 stage 生成。

该基线是路由计划验证，不是读取真实稿件后的完整执行。不能将单次合规回答声称为已证明 Agent 稳定遵守工作流。

修改后六类路由检查：原始旧稿、显式 auto、production/pending 审查、替换源文件、缺目标风格、原生保护页。执行者只读当前 Skill 及相关引用，全部给出对应入口、真实命令、停止点与后续检查点；没有生成原稿或伪造执行。因新 agent thread limit 无法再创建上下文，复用此前仅解释 dashboard 的独立任务，此结果不是六次独立 fresh Agent 实测。未完成用户真实稿件、各宿主、带时间压力的执行统计对照。

## 实现审查

独立 intake reviewer 在初稿发现 UTF-16 XML 声明绕过、缺图片关系／目标仍成功、任意 XML 当 slide 接受三项问题；均进入修复流程，不能以最初五测试通过作为交付依据。

已修复并扩展为 11 项解析回归。OPC 包根关系 `/ppt/...` 与操作系统绝对路径区分：支持前者，仍拒绝网络／盘符／越界；技术依据见 [Microsoft Package.CreateRelationship](https://learn.microsoft.com/en-us/dotnet/api/system.io.packaging.package.createrelationship)。

## 最终验证

- `py -3 -m unittest discover -s tests -q`：663 tests，8 skipped，0 failures，79.210s。相对基线新增 63 项；新跳过项是 Windows 无符号链接创建权限，其余 7 项为原基线跳过项。原有 TemporaryDirectory ResourceWarning 保留，未按测试成功掩盖此警告。
- Python 3.9：`-m unittest discover -s tests -p 'test_source*.py' -q`：63 tests，1 skipped，0 failures，14.087s。
- 优化模式：`py -3 -O -m unittest discover -s tests -p 'test_source*.py' -q`：63 tests，1 skipped，0 failures（实现者最终复测 11.402s）。
- `git diff --check` 退出 0；仅 Git 的 LF→CRLF 提示。Skill-package 16 项、workflow-contract 15 项检查均通过，且包含于最终全量测试。
- 可选 skill-creator `quick_validate.py` 已尝试，但多个可用 Python 均缺 PyYAML；未安装依赖，不能声称此验证器通过。
- 最终独立审查提出活跃批次源稿变更漏检、负向授权误用和 SVG UTF-16 DTD 三项问题；统一修复后 scoped re-review 全部 ADDRESSED，无新重要回归。活跃恢复通过 `--resume-active-batch`，保留前四类控制优先级，在采用／提升旧候选前核对输入。

## 执行边界（交付声明）

本轮验证脚本确定性行为与 Skill 路由，未在 Claude Code／Codex／DeepSeek 各宿主完成整套真实 PPTX 重设计。检查器不是宿主钩子，不能阻止任意绕过；机器一致性不证明真实用户批准、独立审查或视觉美观。原生保护页依赖闭包复制、Office 渲染器安装及直接 PPTX 编辑不在本轮实现范围。
