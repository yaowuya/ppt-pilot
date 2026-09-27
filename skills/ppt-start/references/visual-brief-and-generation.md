# Prompt 编译与 SVG 生成

本分支只在文稿状态为 `manuscript_approved` 后进入。

## 完整 Prompt

每页从已批准故事板、`theme.json`、适用的页面视觉修订和 SVG 契约编译一份自包含 Prompt，并保存为 `.ppt-pilot/generation-prompts/<slide-id>.md`。

Prompt 包含：

- 页面结论、受众 takeaway、精确 display copy、指标、限定和 forbidden claims；
- 每个 content block 的稳定 **block ID**；
- 当前主题、视觉意图、布局家族和 Office-safe SVG 规则；
- “只返回一个完整 XML fence”的输出要求。

Prompt 不包含：原始对话／历史 JSON、机密、绝对路径、URL、运行状态、内部 **source ID**，或要求读取文件／调用工具的指令。文件路径只是恢复证据，不能替代 Prompt 字节传给 generator。

## 两类 ID

- **block ID**：例如 `S03-B1`。它是临时结构 join key，可以进入 Prompt；generator 只在对应语义 `<g data-block-id="S03-B1">` 上原样回显，不能放进可见文字或其他属性。
- **source ID**：例如 `SRC-001`。它只属于 AI/coordinator 机器元数据，不能进入 Prompt、generator 上下文或可见文字。

## Host-native generator boundary

把完整冻结 Prompt 按值交给当前宿主的 fresh-context generator。Generator 只依据任务文本返回一个 `xml` fenced SVG；它不读取工作区、不写文件、不拥有 run state。不得运行 local Claude CLI、触发登录／认证浏览器／API key 流程，或把本地 CLI 作为备用生成器。Codex 与 DeepSeek Harness 使用各自原生能力，不走 Claude Code 的 Git 修复分支。

### Native first

**fresh context 是独立上下文，不等于 worktree。普通原生调用不以 Git/HEAD 为前置条件。** Claude Code 新建非 fork 的 `ppt-svg-generator` Agent，按实际工具 schema 传参；`isolation` 可选时省略它，不请求文件系统隔离，也不虚构 `none`／`false` 等值：

```json
{"subagent_type":"ppt-svg-generator","prompt":"<完整冻结 Prompt 字节，不是文件路径>"}
```

不继承父对话、不复用旧 Agent 上下文。不要在普通调用前检查 `git rev-parse HEAD`。若之前失败来自主动选择了可选 worktree，先改用上述原生调用；只有宿主确实强制 Git 隔离或返回真实 Git/HEAD 启动错误，才进入下一分支。

### Claude Code HEAD repair

仅对 Claude Code 在接受 Prompt 前返回的实际错误：缺 Git 仓库记为 `host_git_required`，缺有效提交基准记为 `host_git_head_required`。不要把缺 Agent、缺工具、权限拒绝、网络或模型错误改称 Git 问题。`git init` 成功不等于 HEAD 可用：空仓库的 HEAD 尚未指向提交。

**先判断资格，再执行命令：**

1. 从宿主实际启动目录判断仓库归属。已有有效 HEAD 直接复用；不新建嵌套仓库、不新增提交。HEAD 错误却已有历史／refs 时属于另一个问题，不按空仓库处理。
2. 需要修复时，只选择已批准的专用 presentation workspace root：它是 `run_dir` 的祖先，不能是用户主目录、磁盘根目录、无关项目目录或符号链接／junction 目标。若宿主根就是 `run_dir`，仅在其直接父目录名为 `ppt-output` 且该父目录也在授权范围内时使用父目录。`.git` 始终在 run artifact tree 外。
3. 创建初始提交的唯一例外：用户明确授权此项本地空基准修复，且仓库由本插件创建、没有提交／refs、没有 remote。旧版初始化记录须能对应到同一个安全根目录。已有用户仓库、所有权不明、损坏仓库或含 remote 的空仓库均不擅自修改；说明具体限制，不假称再次“继续”就能恢复。
4. 资格满足后，按下列顺序执行。`PPT_PILOT_GIT_ROOT` 和 `PPT_PILOT_LAUNCH_ROOT` 是已确认的绝对路径；每次工具调用都显式传入，不依赖跨调用的 shell 变量或 `cd` 状态。任一步失败立即停止此修复，不绕过 hooks、签名或权限。

仅未初始化时创建仓库，旧版空仓库不重新初始化：

```bash
if [ ! -e "${PPT_PILOT_GIT_ROOT:?}/.git" ]; then
    git init "$PPT_PILOT_GIT_ROOT"
fi
```

仅缺提交基准时创建一次空初始提交；`--allow-empty --only` 排除已暂存文件，单独 `--allow-empty` 做不到。身份只作用于此子进程，不改用户 Git 配置：

```bash
if git -C "${PPT_PILOT_GIT_ROOT:?}" rev-parse --verify --quiet 'HEAD^{commit}' >/dev/null; then
    git -C "$PPT_PILOT_GIT_ROOT" rev-parse --verify 'HEAD^{commit}'
elif head_ref=$(git -C "$PPT_PILOT_GIT_ROOT" symbolic-ref -q HEAD) && [[ "$head_ref" == refs/heads/* ]] &&
     refs=$(git -C "$PPT_PILOT_GIT_ROOT" for-each-ref --format='%(refname)') && [ -z "$refs" ] &&
     remotes=$(git -C "$PPT_PILOT_GIT_ROOT" remote) && [ -z "$remotes" ]; then
    GIT_AUTHOR_NAME='PPT Pilot Bootstrap' GIT_AUTHOR_EMAIL='bootstrap@ppt-pilot.invalid' \
    GIT_COMMITTER_NAME='PPT Pilot Bootstrap' GIT_COMMITTER_EMAIL='bootstrap@ppt-pilot.invalid' \
    git -C "$PPT_PILOT_GIT_ROOT" commit --allow-empty --only -m "$(cat <<'PPT_BOOTSTRAP_MESSAGE'
Initialize local PPT generator baseline
PPT_BOOTSTRAP_MESSAGE
)"
else
    false
fi
```

从**宿主实际启动目录**验证 HEAD 和仓库根，根必须等于选定的安全根；新建的初始提交还须验证 tree 为空。任一验证不符，都不能记为修复成功：

```bash
git -C "${PPT_PILOT_LAUNCH_ROOT:?}" rev-parse --verify 'HEAD^{commit}'
```

```bash
git -C "${PPT_PILOT_LAUNCH_ROOT:?}" rev-parse --show-toplevel
```

```bash
git -C "${PPT_PILOT_GIT_ROOT:?}" ls-tree -r --name-only HEAD
```

`ls-tree` 对新建初始提交必须无文件输出；复用已有有效 HEAD 不要求原有 tree 为空。保留 staged index 和所有用户文件。除上述初始空提交外，不允许其他提交；不执行 `git add`、`git reset`、`git clean`、`git checkout`、`git branch`、`git push`、`git pull`、`git fetch`、`git clone`、手工 `git worktree`、写入 `git config` 或设置 remote。不上传文件、不复制原始 PPT／Prompt 到隔离 checkout、不绕过 hooks 或签名；宿主若仍要求远程基准，也不创建远程来迎合它。

### Resume and dispatch

HEAD 验证通过才记录 [AI 状态协议](ai-state.md) 的 head-ready 证据，然后以 byte-identical 的 **same frozen Prompt** 重新启动一次原生 Agent。若宿主强制创建隔离 checkout，由宿主管理，并且只有其实际支持本地 HEAD 时才使用；Git 修复成功不代表 Agent 或 SVG 已成功。

旧 `claude_code_local_git_initialized` 记录只是 init-only：即使旧规则已重试过，仍可在确认资格后完成本协议的一次 HEAD 修复。恢复时先尝试可用原生路由或执行有据可依的修复，不把旧 HEAD 失败变成永久前置门。

同一宿主、同一根目录、同一错误且环境未变时，不重复 HEAD-only 检查、相同失败写入或自动启动；协议从 init-only 升级到 head-ready 是一次有意义的修复机会，不是循环许可。修复后仍失败则记录一次 `generator_unavailable`，保留 Prompt、source map、theme、旧 final 和 attempts，继续不依赖该宿主的动作；没有可执行动作就一次性说明所缺能力，不反复要求“继续”。只有 Agent 真正接受 Prompt 开始生成才增加 attempts；不得伪造 SVG。

## Candidate 到 final

1. 提取唯一 XML fence；
2. 校验 raw candidate：XML、画布、元素／属性、几何、文本，以及 block-ID 集与冻结 source map 的 key 完全一致；
3. 用 source map 在对应组写 machine-only `data-source-id`，然后移除所有 `data-block-id`；
4. 校验 final：允许合法 `data-source-id`，拒绝残留或可见 block ID、可见 `SRC-<digits>`；
5. 只在所有检查通过后发布 `slides/<slide-id>.svg` 并读回。

没有可关联来源的 content block 仍使用稳定 block ID，并在冻结 source map 中保留 `{"S03-B1": []}`；finalize 只删除该临时 ID，不写 source metadata。只有没有任何 content block 的页面才使用空对象 `{}`。

`scripts/svg_tool.py finalize` 可以完成步骤 1–4 的确定性部分。其 `INVALID` 只使该页失败；`UNAVAILABLE` 时 AI 直接执行同一检查并记录降级，工具不得改变 attempts 或 stage。
