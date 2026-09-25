# Claude Code 原生生成器与条件式本地 Git Bootstrap

**日期：** 2026-09-25
**状态：** 用户已确认“条件式本地 Git bootstrap”方案；已实现并在 2026-09-25 验证（420 tests，6 skipped）；未部署本次变更到本地宿主。

## 问题

PPT Pilot 要求逐页 SVG 由不读取工作区的 fresh-context generator 按冻结 Prompt 生成。当前指令只说“使用可用 generator”，没有固定宿主失败时的边界。因此实际运行可能把本地 `claude` CLI 登录和 `claude -p` 当作备用路线。

这不符合目标：PPT 优化不应要求登录本地 CLI；Claude Code 已有的会话授权应是唯一 Claude 路径。少数 Claude Code 启动器若把 Git 仓库作为 fresh-context Agent 的前提，也不应使页面工作流卡死。

## 决策

采用 **host-native generator + 条件式本地 Git bootstrap**：

1. PPT coordinator 只把完整冻结 Prompt 按值交给当前宿主的 `ppt-svg-generator`；generator 不读工作区、不写文件、不维护状态。
2. coordinator 永不调用或提示调用本地 `claude` CLI；不触发登录、认证浏览器、API key、`claude -p` 或任何 CLI 备用生成器。
3. 仅当运行在 Claude Code，且宿主明确诊断 named Agent 因“当前启动目录不是 Git 仓库”而无法启动时，coordinator 才可初始化一个本地 Git 仓库并重试同一 Prompt 一次。
4. Git 只是 Claude Code 的启动垫片，不是 PPT workflow owner、状态机、证据来源或交付前提。

## 条件式 Git bootstrap

### 触发条件

以下条件必须同时成立：

- 当前 host 是 Claude Code；
- `ppt-svg-generator` 尚未开始处理 Prompt；
- 启动失败被明确归因为缺少 Git 仓库，而不是泛化的 Agent、权限、模型、网络、Prompt 或工具错误；
- coordinator 能确定 Claude Code 用于启动 Agent 的专用 presentation workspace root，且它是 run 的祖先或 run 本身；该 root 必须是 `ppt-output/` 容器或一个明确选择的 presentation workspace，绝不能是用户主目录、磁盘根目录或无关项目目录。

泛化失败、无法确定 root、Git 不可用或初始化失败都不得触发猜测性 Git 操作。

### 根目录与隔离

`run_dir` 是 `ppt-output/<deck-id>/`。`.git` 不得写在 `run_dir` 之内，因为 `.ppt-pilot` / SVG artifact firewall 必须继续只面对交付证据。

- 若 Claude Code workspace root 是 run 的祖先，在该 workspace root 初始化；
- 若 workspace root 恰好是 run，则仅在其父目录严格命名为 `ppt-output` 时，才在该父目录初始化，使 Git 向上发现但不污染 run artifact tree；否则不初始化并按页面级不可用处理；
- 若两种关系都不成立，不初始化 Git，改为页面级 `generator_unavailable`。

只执行一次：

```text
git init <selected-local-root>
```

禁止 `git add`、`commit`、`branch`、`remote`、`push`、`pull`、`fetch`、`clone`、`worktree` 和显式 `git config` 操作，以及读取或上传已有 Git 历史。初始化仓库没有 remote，也不产生提交。

### 重试和状态

bootstrap 成功后，仅重新启动 named Agent 一次，并将完全相同的冻结 Prompt 按值传入。AI 在页面的既有 evidence 中记录 `claude_code_local_git_initialized`、所选作用域和触发原因；这只是审计事实，不是新的 runtime owner。

- Agent 真正开始生成前的 Git / host 启动失败：`generator_unavailable`，不增加 attempts；
- Agent 已开始生成后产生无效 SVG：按现有 `INVALID` 页面局部失败规则处理，属于真实 attempt；
- bootstrap 后仍不可启动：页面局部 `generator_unavailable`；不调用 local CLI、不自动循环、不阻塞 sibling 页面。

## 宿主边界

Claude Code 使用当前会话的原生 Agent 路线。Codex 与 DeepSeek Harness 不调用 Claude CLI；它们只使用自身可用的 fresh-context route，或诚实记录 `generator_unavailable`。所有宿主仍安装同一组 Skill 文档和静态工具。

`hosts/claude-code/agents/ppt-svg-generator.md` 明确保持无文件、无目录、无 Git、无 CLI、无认证行为；它只根据 prompt-by-value 返回一个 XML fenced SVG。Git bootstrap 始终由 coordinator 处理，绝不由 generator 执行。

## 实现范围

1. 收紧 `skills/ppt-start/SKILL.md` 和生成/工作流/AI 状态参考：明确 native Agent 路线、条件、Git 作用域、一次重试和非阻塞结果。
2. 收紧 Claude Code generator Agent：拒绝本地 CLI、认证、Git 和任何 workspace 访问。
3. 更新 README / architecture 中与 host generation 相关的简短说明，避免把 local CLI 当成可选方案。
4. 扩展 package/workflow contract tests，验证：
   - active instructions 不包含可执行的 local Claude CLI fallback；
   - Git bootstrap 仅在 Claude Code + explicit Git prerequisite 条件下允许；
   - 禁止 Git 历史、remote、commit、push、worktree 和隐藏重试；
   - generator Agent 自身无 CLI/Git/workspace 行为；
   - installer 继续打包同一份更新后的 Skill / Agent。
5. 运行相关聚焦测试和完整测试套件。

## 不在范围内

- 不添加新的 Python workflow runtime、后台队列、Git helper 脚本或宿主 adapter registry；
- 不修改 SVG 生成质量、来源映射、editable PPT 转换或已有 AI-owned state model；
- 不自动部署到用户本地 Claude Code、Codex 或 DeepSeek Harness。实现和验证完成后，部署须单独获得授权。

## 完成标准

- 任何 active instruction 都不要求、建议或执行 local Claude CLI 登录/生成；
- Claude Code 因缺 Git 无法启动 generator 时，只有安全根目录内的一次本地 `git init` 和一次 Agent 重试；
- `.git` 不进入 PPT run artifact tree；
- 无法 bootstrap 时工作流诚实地页面级降级；
- 已有 `PASS | INVALID | UNAVAILABLE`、attempt 和 partial-delivery 契约保持不变；
- 相关测试和完整套件通过。
