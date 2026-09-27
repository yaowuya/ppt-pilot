# Claude Code 原生生成器与条件式本地 Git Bootstrap

**日期：** 2026-09-25
**状态：** 2026-09-27 修订。2026-09-25 的 init-only 方案虽然通过静态契约测试，却不能产生有效 HEAD；本次修复明确替代该限制。执行细节以 [生成器恢复协议](../../../skills/ppt-start/references/visual-brief-and-generation.md) 为准。

## 问题

PPT Pilot 要求逐页 SVG 由不读取工作区的 fresh-context generator 按冻结 Prompt 生成。当前指令只说“使用可用 generator”，没有固定宿主失败时的边界。因此实际运行可能把本地 `claude` CLI 登录和 `claude -p` 当作备用路线。

这不符合目标：PPT 优化不应要求登录本地 CLI；Claude Code 已有的会话授权应是唯一 Claude 路径。少数 Claude Code 启动器若把 Git 仓库作为 fresh-context Agent 的前提，也不应使页面工作流卡死。

## 决策

采用 **host-native generator + 条件式本地 Git bootstrap**：

1. PPT coordinator 只把完整冻结 Prompt 按值交给当前宿主的 `ppt-svg-generator`；generator 不读工作区、不写文件、不维护状态。
2. coordinator 永不调用或提示调用本地 `claude` CLI；不触发登录、认证浏览器、API key、`claude -p` 或任何 CLI 备用生成器。
3. Claude Code 默认新建非 fork 的原生 Agent，省略可选的 filesystem isolation，不执行 Git/HEAD 前置检查。只有宿主实际强制 Git 或返回真实的 HEAD 启动错误时，才进入受限修复。
4. Git 只是 Claude Code 的启动基准，不是 PPT workflow owner、状态机或交付前提。

## 条件式 HEAD 修复（2026-09-27 修订）

原方案只允许初始化目录，同时禁止所有提交，导致 unborn HEAD 永远无法自愈。允许空仓库并不意味着允许提交文稿：本修订的唯一提交例外是用户已明确授权、由插件创建、无历史／refs／remote 的专用本地仓库中的一次空初始提交。

### 资格与目录

- 错误必须发生在 Prompt 被接受前，且实际原因是缺少 Git 仓库或有效 HEAD，不是权限、网络、模型或缺 Agent。
- 现有有效 HEAD 直接复用；已有用户仓库、所有权不明、损坏仓库或带 remote 的空仓库不擅自修改。
- 从宿主实际启动目录确认安全根目录：必须为已授权的专用 presentation workspace，并在 `run_dir` 之外。宿主根等于 run 时，仅可选择已授权且名为 `ppt-output` 的直接父目录。
- 不选择主目录、盘根、无关项目或链接目标，不创建嵌套仓库。

### 提交与验证

原生独立上下文不要求 HEAD。若宿主确实要求，受限修复使用带 `--allow-empty --only` 的初始提交排除 staged 文件；身份仅放在子进程环境，不写 Git 配置。已有 index 和所有文件保持不变，保留 hooks／签名要求，失败不绕过。

从实际启动目录验证 `HEAD^{commit}` 与根目录；新建初始提交的 tree 必须为空。只初始化目录不算完成，Git 基准可用也不等于宿主已生成 SVG。禁止暂存资料、改写历史、设置 remote、推送或上传；具体可执行序列由生成参考唯一维护，不再在设计稿复制。

### 恢复与预算

旧 `claude_code_local_git_initialized` 仅表示 init-only，不消耗本次 HEAD 修复机会。新 `generator_setup` 记录 `protocol_version: 2`、`claude_code_local_git_head_ready` 和实际 HEAD；失败也记录所处步骤，避免相同错误／相同环境反复 HEAD-only 检查。

修复完成后，同一冻结 Prompt 最多重新启动一次原生 Agent。启动前失败不增加 attempts；实际开始生成后的失败才消耗一次生成机会。若宿主仍不可用，一次性披露限制并转向其他可执行动作；不要求用户反复“继续”，不生成替代 SVG。

## 宿主边界

Claude Code 使用当前会话的原生 Agent 路线。Codex 与 DeepSeek Harness 不调用 Claude CLI；它们只使用自身可用的 fresh-context route，或诚实记录 `generator_unavailable`。所有宿主仍安装同一组 Skill 文档和静态工具。

`hosts/claude-code/agents/ppt-svg-generator.md` 明确保持无文件、无目录、无 Git、无 CLI、无认证行为；它只根据 prompt-by-value 返回一个 XML fenced SVG。Git bootstrap 始终由 coordinator 处理，绝不由 generator 执行。

## 实现范围

1. 收紧 `skills/ppt-start/SKILL.md` 和生成/工作流/AI 状态参考：明确 native Agent 路线、条件、Git 作用域、一次重试和非阻塞结果。
2. 收紧 Claude Code generator Agent：拒绝本地 CLI、认证、Git 和任何 workspace 访问。
3. 更新 README / architecture 中与 host generation 相关的简短说明，避免把 local CLI 当成可选方案。
4. 扩展 package/workflow contract tests，验证：
   - active instructions 不包含可执行的 local Claude CLI fallback；
   - Git/HEAD 修复仅在 Claude Code 的真实启动错误下允许；
   - 普通路由无 HEAD 前置门，空提交例外不包含文件，不改变配置／index／remote；
   - generator Agent 自身无 CLI/Git/workspace 行为；
   - installer 继续打包同一份更新后的 Skill / Agent。
5. 运行相关聚焦测试和完整测试套件。

## 不在范围内

- 不添加新的 Python workflow runtime、后台队列、Git helper 脚本或宿主 adapter registry；
- 不修改 SVG 生成质量、来源映射、editable PPT 转换或已有 AI-owned state model；
- 不自动部署到用户本地 Claude Code、Codex 或 DeepSeek Harness。实现和验证完成后，部署须单独获得授权。

## 完成标准

- 任何 active instruction 都不要求、建议或执行 local Claude CLI 登录/生成；
- 默认原生路由不要求 Git/HEAD；确需 Git 时，安全根中的空初始提交必须通过实际 HEAD 和空 tree 校验，之后至多重启一次 Agent；
- 临时目录内用真实 Git 测试 init-only 失败、可用 worktree 基准、暂存文件排除、旧空仓库恢复、有效 HEAD 复用和 hook 失败；
- `.git` 不进入 PPT run artifact tree；
- 无法 bootstrap 时工作流诚实地页面级降级；
- 已有 `PASS | INVALID | UNAVAILABLE`、attempt 和 partial-delivery 契约保持不变；
- 相关测试和完整套件通过。
