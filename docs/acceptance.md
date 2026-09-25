# 验收边界

本文件定义什么证据可以支持什么结论。历史验收记录保存在 `acceptance-evidence/`，但不自动代表当前源码继续通过。

## 证据等级

| 等级 | 证明什么 | 不能证明什么 |
|---|---|---|
| Static | 包结构、文档指针、schema、纯函数／fixture | 真实宿主、渲染、Office |
| Local process | Python/PowerShell CLI、文件原子性、退出码 | generator 真实可用 |
| Host | 实际宿主启动 generator、返回归因、无 Git 依赖 | SVG 视觉正确 |
| Render | 实际 renderer 下的裁切、重叠、字体、层级 | Office 导入一致 |
| Office | 实际 PowerPoint normalize、重开、导出和视觉比较 | 其他 Office 版本普遍一致 |

任何报告必须写运行日期、宿主／Office 版本、命令或操作、结果和证据路径。未运行写 `PENDING`，不可用写真实原因。

## 必验场景

### AI workflow

- 新建 guided topic-only：首个实质问题是简报批准；
- pending interaction：回答被直接应用并幂等写 history；
- retry：只有真实 generator 调用增加 attempts；
- skip：页面变 `skipped`，attempts 不变，siblings 继续；
- tool unavailable：记录降级，stage／attempts 不变；
- tool invalid：只失败相应页面并保留 prior final；
- resume：从 pending → 共享一致性 → 最早未完成／dirty 项继续。

### Content gate

- 独立审稿与 inline fallback 使用同一 `BLOCKER/HIGH` 门；
- 未解决阻断 finding 不生成 theme/SVG；
- 事实／来源变化使文稿批准失效；
- 纯视觉变化不重写文稿。

### SVG

- Generator 输入为完整 Prompt bytes；
- Raw candidate block IDs 与 source map 精确匹配；
- Final 移除 block IDs、保留合法 machine-only source IDs；
- 可见 `SRC-<digits>`、活动内容、外部资源、非法几何和过小字号被拒绝；
- Python 3.9 下 extract/normalize/finalize/validate 可运行；
- 输出目标竞争时不覆盖既有证据。

### Completeness and editable delivery

- AI-state complete 与 partial 不需要 transaction/batch；
- legacy explicit 仍严格验证历史 evidence；
- malformed route 不 fall through；
- manifest 重入必须与当前 snapshot 和页面分区一致；
- partial 只转换 promoted subset；
- editable failure 不修改 SVG run；
- missing Office/Pillow 只能是 `GENERATED_UNVERIFIED`。

### Installation

- 三个 Skill tree 与源摘要一致且不含 cache；
- Claude Agent 与当前源一致；
- retired SDK Agent 被清理，其他 Agent 保留；
- mixed failure 返回非零并回滚对应 scope；
- 安装完成后明确提示重新开启会话。

## 当前声明

仓库测试结果只在本次实际运行后记录。不要把过去的测试数量、旧 dashboard／runtime 验收或旧 host adapter 证据复制为当前 PASS。真实 generator、render 和 Office 仍需针对当前安装重新执行。
