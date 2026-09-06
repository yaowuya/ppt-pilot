# 外部旧 PPT 重设计：已批准设计

用户于 2026-09-06 确认本方案。外部旧 PPT 是内容输入，不是已批准 PPT Pilot 运行；即使仅换产品风格，也要建立来源、页面去向与文稿审查证据。

## 范围与不变量

- 保留 `brief -> research -> outline -> storyboard -> manuscript_review -> theme -> anchor -> production -> qa -> complete`，不增加 mode；只有 `guided` / `auto`。
- 保留既有五类 durable control state 的全局恢复顺序；补充检查不得处理或清除这些状态。
- Python 3.9+ 标准库；源文件只读，不执行宏、不访问外部关系、不自动转换二进制 `.ppt`。
- 新运行内部产物放 `.ppt-pilot/`，根目录大纲为 `大纲.md`；不迁移旧运行。
- 风格来自目标产品风格包，不从旧稿外观推断；保留 style-owned 单 `{{NARRATIVE}}`、fresh isolation、现有 transaction 契约。
- 检查器只读、失败非零退出、不得用 `assert` 实现质量门，错误包含 code / reentry_stage / next_action。
- 不改宿主配置，不安装插件，不推送，不改参考目录。不承诺模型绝不会绕过脚本；本次提供强制调用规则和可执行检查，非宿主级拦截器。

## 组件

### 1. 源 PPTX 解析

`scripts/ppt_source_intake.py --source <file.pptx> --output <new-json-path>` 调用 `_source_intake.py` 的 `extract_pptx(path) -> dict`。先完整验证、后独占创建输出，已存在输出拒绝覆盖。输出父目录必须已存在。失败不留下输出；源文件不变。

JSON schema_version=1，kind=`pptx_source_inventory`，source={name,sha256,size_bytes}，slide_count，slides[]，warnings[]。每页含 source_slide_id=`SRC-S001`（实际展示次序），position，part，sha256（该 slide XML），texts（按 XML 顺序的段落字符串，保留段落内空格/换行），tables（rows/cells 的文本矩阵），notes（备注段落字符串），objects（图片、图表、SmartArt、OLE、group 等类型及关系/对象标识），warnings。解析 presentation.xml 的 sldIdLst / relationships 而非猜 slideN.xml；隐藏页也纳入并标 hidden。

不把 XML 顺序称为视觉阅读顺序，不声称从图片/OLE/图表获取了完整语义。对这些对象和无可提取文本页面产生需视觉核对警告。包路径、重复成员、缺失关系、加密/损坏、DOCTYPE/实体、大小预算（单成员 32 MiB、总解压 256 MiB、成员 10000）显式拒绝。不解压到文件系统、不跟随 External 关系。数字仍为原稿主张，不自动认证为事实。

实现审查补充：源字节快照在分配前也设 272 MiB 上限；所有 XML / relationship parts 拒绝声明，核心部分验证 namespace-qualified root，展示页必须非空且唯一。

### 2. 导入绑定与映射

仅外部旧稿运行新增 `run.json.source_deck`={kind:`external_pptx`,source_path:绝对本地路径,inventory:`源稿清单.json`,mapping:`源页映射.json`,evidence:`导入检查点.json`}；这些三个文件位于 `.ppt-pilot/`。原稿路径只在本地绑定，不进入生成 Prompt。普通运行无该字段时检查器返回 `NOT_APPLICABLE`，不能宣称已通过完整工作流。

映射 JSON：schema_version=1，source_sha256，slides=[{source_slide_id,action,targets,reason,authorization?}]。action 为 restyle / preserve / split / merge / omit；restyle/preserve 恰好一个目标，split 至少两个，merge 一个且至少两源共享，omit 无目标。目标为稳定 S01 风格 ID，必须与后续 target_slide_ids 完全覆盖，无孤儿源页。改变源事实/删页/保留原生页等非默认决定用 authorization={interaction_id} 引用真实 applied 交互历史，不自动批准。`preserve` 是保留内容重建，不是已实现原生 slide 复制；原生保护页需要明确冲突说明与后续交付策略。

最终审查补充：非默认行授权必须指向 kind=authorization/status=applied/decision=approve 的历史，并以 source_mapping_authorizations[] 中的 {source_sha256,source_slide_id,action,targets} 精确绑定；负向、无关或旧源版本交互不得授权。

### 3. 补充阶段检查

`scripts/ppt_workflow_gate.py --run-dir <run> --before <stage>`，stage 为 research / outline / storyboard / manuscript_review / theme / anchor / production / qa / complete。输出 status=PASS/BLOCKED/NOT_APPLICABLE、before、errors[]（code,reentry_stage,next_action），退出码 PASS/NOT_APPLICABLE=0、BLOCKED=2。`--snapshot` 只输出当前文件 hash，不写入/批准证据。所有源稿运行每次生成前与交付前调用；任何失败停止下游操作。

每次检查先读取唯一 run（双路径冲突拒绝），逐项停止于最高优先级 durable control state；验证 source_path 当前 SHA 与 inventory、一致页面 ID/页数、映射绑定。源码相对路径来自库存但不作为可写路径。检查所需文件必须在本运行内，不允许 `..`、绝对证据路径或 symlink 越界。

最终审查补充：CLI 新增与 --before / --snapshot 互斥的 --resume-active-batch，函数 check_active_batch(run_dir)->dict。仅供已有 active owner 在验证 manifest／transactions 后、任何 dispatch／candidate adoption／promotion 前调用，要求有 active pointer 和 run.stage=anchor|production，按该 stage 检查所有累计输入。前四类 durable state 仍以原顺序阻断；普通 --before 仍阻断 active。只读、不迁移、不清除 owner，不授权绕过原 transaction 验证。用于关闭源文件在崩溃期间变更而旧候选先提升的缺口。

`导入检查点.json` 顶层 schema_version=1，source_sha256，mapping_sha256，target_slide_ids。阶段字段按需增加：

- `approvals`: guided 的 brief/outline 各含 {interaction_id,artifact_snapshot_id,artifact_sha256}，匹配该检查点最新已应用批准的历史及当前简报/大纲文件 hash；auto 不要求此对象。
- `source_audit`: {status:`complete`,inventory_sha256,reviewed_slide_ids:[全部源页],visual_checked_slide_ids:[所有有警告源页],notes:非空}。人工或 Agent 核对的记录，不是假称脚本完成了视觉理解。
- `manuscript`: {files:{运行相对路径:sha256},report:{path,sha256},review_snapshot_id}；files 恰好五份当前简报/研究/来源/大纲/故事板文件。新导入的 reviewed_file_snapshot 保留 files 列表并必需新增 file_hashes 字典，匹配 manuscript.files 和当前文件，发起 pending round 时冻结并沿用到完成记录。绑定 run 的最新正式 PASS round snapshot_id，检查 approved/PASSED、无未解决 BLOCKER/HIGH、非空真实委派或 fallback 字段、对应报告存在。此字段在审查时冻结，不可用当前 snapshot 给旧审查补证据。
- `style`: {files:{运行相对路径:sha256},selected_style_id,style_manifest_version}；包含当前 `.ppt-pilot/theme.json`，风格包资产的验证仍由原有 style traversal/preflight 负责，theme 的身份必须一致。
- `anchor`: {files:{运行相对路径:sha256},style_sha256,review_snapshot_id,status:`approved`|`validated`,approval_interaction_id?,artifact_snapshot_id?}；至少两份 `.ppt-pilot/samples/` 样例 SVG（不足两页时全部），guided 必须引用最新 applied anchor approve 历史并匹配 artifact_snapshot_id，auto 仍须 validated。样例必须真实非空，当前 SHA 一致。
- `qa`: {status:`PASS`,report:{path,sha256},slides:[{slide_id,svg:{path,sha256},render:{path,sha256},render_input_sha256,renderer,visual_review:`PASS`}]}；每个目标恰好一条，SVG 在 slides/，渲染证据在运行内，render_input_sha256 必须是实际渲染时的输入 SVG hash 并匹配当前 SVG。缺渲染、手工检查 pending、dirty slides、旧渲染不匹配均不能 complete。这是一致性校验，不替代实际视觉审查。

实现审查补充：本版本渲染证据采用 PNG，校验基本签名/IHDR/尺寸，拒绝拿任意 JSON/文本代替渲染文件；不新增第三方图像库，也不声称基本格式检查证明视觉质量。SVG 共享基本 XML/root/viewBox 检查，完整 Office-safe 验证仍由既有生产门完成。

累计阶段条件：research 需要简报 + guided brief approval；outline 加 source_audit、研究/来源；storyboard 加大纲 + guided outline approval；manuscript_review 加故事板、target IDs；theme 加 manuscript；anchor 加 style；production 加 anchor；qa 加所有 target SVG 存在；complete 加 qa 和 dirty_slides 为空。GUIDED approval 通过 current checkpoint 的真实 applied interaction_history，而非 approved 布尔值；后续输入修改须重新批准，由现有交互快照协议处理。

## 验收

使用合成 OOXML 包测试次序、文本/表/备注、隐藏页、外部关系、对象警告、拒绝格式/包路径/预算、失败零输出、源不变。使用临时运行测试正常逐阶段通路、缺审查、陈旧 hash、漏页、非法映射、待回答优先、目标风格错配、陈旧锚点、渲染缺失和 python -O 不绕门禁。通过真实 CLI 串联 intake→gate，文档路由用 fresh Agent 场景检验；不把仅计划回答当作真实整套生产成功证据。
