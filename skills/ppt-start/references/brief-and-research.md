# 简报与研究契约

## 目的

把初始请求和证据整理为三个持久文稿输入：`简报.md`、`研究.md` 和 `来源.md`。必须保留不确定性与来源，使后续独立审稿人能够检查每个重要主张。本阶段所有补充问题和批准都遵循[用户交互与确认协议](interaction-protocol.md)。

## 进入路径

根据用户输入与工作区文件选择路径；已经完成的上游阶段不得重新计算。

- **topic-only（仅主题）**：根据主题拟定简报。`guided` 模式按决策依赖顺序询问实质性缺失项，并在研究或编写大纲前请求明确的简报批准；`auto` 模式明确记录安全假设后继续。
- **complete brief（完整简报）**：在不改变原意的前提下规范化用户简报。只有缺失决策会实质改变演示文稿时才需要补充；否则记录保守假设。
- **source-driven（资料驱动）**：先盘点用户提供的资料，再根据覆盖情况和缺口生成简报与研究问题。
- **resume（恢复）**：先读取 `run.json`，严格按全局恢复链 `pending_interaction > manuscript_review.pending_round > visual_generation_blocker > visual_generation_transaction > stage scan` 处理；只有前四类 durable control state 均不存在或已完成后，才进入 `stage scan`，再从第一个未完成或脏输入继续。

## 决策依赖顺序与简报批准

先检查请求、用户资料、既有运行和工作区偏好档案（`ppt-output/pilot-preferences.json`，规则见[用户交互与确认协议](interaction-protocol.md)），删除已经回答的事项。只有缺失答案会实质改变演示文稿时才询问；低影响且可逆的未知项使用保守默认值并写入 `assumptions`。

按以下依赖顺序选择最早的一个未决事项，而不是一次展示完整问卷：

`topic／intent -> audience -> desired audience action -> required／forbidden content -> evidence／confidentiality -> slide count／presentation time -> language／brand/style -> success criteria`

`run.json.mode` 是权威执行策略，只能是 `guided` 或 `auto`。`resume`／`revise` 是入口动作并保留既有 `run.json.mode`。`简报.md` 中的 `delivery_mode` 只是便于阅读的镜像记录，不得替代、覆盖或作为 `run.json.mode` 的别名。新运行未显式指定策略时，两处都记录 `guided`。

### 信息充分的 topic-only 首题

当请求已经提供 topic、audience、purpose／desired audience action、slide count 和交付格式时，不得为了低影响未知项延迟简报批准：

- 记录 `presentation time: not supplied`；
- 使用请求所用语言，除非请求明确要求其他语言；
- 记录 `brand/style: not supplied`，把最终视觉选择留到文稿批准后的主题阶段；
- 没有来源或联网授权时采用离线证据路径，记录限制且不虚构公司指标；
- 把请求中的明确决策目的视为 `desired audience action`，不换一种说法重复询问。

在这些条件下，完成简报和安全假设后，第一个问题必须是简报批准。只有请求仍缺少会改变核心主题、受众或行动的值，或者需要外部传输权限时，才在批准前询问该最早阻塞项。

所有实质性缺失项解决后，先写完整简报和假设摘要，再提出一个简报批准问题。`guided` 必须获得明确回答才能进入研究或大纲；推荐、摘要展示或没有反对都不是批准。`auto` 跳过该可选批准，但用户权限和无安全默认值的问题仍然阻塞。

## `简报.md` 必需决策

以下字段必须全部记录；信息缺失时使用 `unknown`、`not supplied` 或明确假设，不得直接省略：

- `topic`：演示文稿的明确主题边界；
- `audience`：受众及其预期知识水平；
- `purpose`：告知、决策、说服、教学、汇报或对齐；
- `desired audience action`：演示结束后可观察的受众决策或行动；
- `slide count`：用户要求的页数，或 MVP 默认范围 6–15 页；
- `presentation time`：可用演讲时间，未知时写 `not supplied`；
- `required content`：必须出现的事实、章节、信息和行动号召；
- `forbidden content`：禁止出现的主张、主题、披露内容、视觉或措辞；
- `evidence policy`：资料质量、引用密度及对未核验主张的容忍度；
- `confidentiality`：公开、内部、机密或用户指定的处理规则；
- `language`：中文、英文或指定的双语方式；
- `brand/style`：已有品牌规范、简短风格要求或工作区偏好档案中预置的品牌方向；视觉令牌只能在文稿批准后确定；
- `delivery_mode`：`guided` 或 `auto`；
- `success_criteria`：内容与交付的可观察成功条件；
- `assumptions`：所有未经用户直接确认而采用的默认值。

请求或工作区中已有的信息不得再次询问。完整简报是决策记录，不是对话抄本。

## 研究决策

研究应按需要执行，而不是形式化步骤。

1. 使用任何网络能力前，先盘点用户提供的资料。用户资料在意图、机密事实和内部术语上优先。
2. 只为支撑核心论点、回应可能质疑、比较重要数字和核验时效性主张而提出研究问题。
3. 只有网络研究可用、得到允许且符合 `confidentiality` 时，才进行实时网络研究。安全的本地盘点和离线综合不需要询问；外部传输、敏感派生查询或不明确的披露范围必须先获得用户权限。
4. 默认不得把机密内容、资料摘录、专有名称或由机密内容推导的敏感查询发送到网络。除非用户明确授权披露，否则离线工作。
5. 网络研究不可用或被禁止时，依赖用户提供／本地证据，并在 `研究.md` 中说明限制。
6. 绝不能虚构来源、日期、统计值、引语或核验结果。缺少支持的主张必须删除、限定或明确标记。

当计划中的主张已得到充分覆盖，或剩余缺口已经明确时，研究即应停止。链接数量不是质量目标。

## `来源.md` 证据台账

每个来源使用稳定 ID，例如 `SRC-001`，修订时保持 ID 不变。

每条来源记录包含：

- `source_id`
- `title`
- `author_or_publisher`
- `location`：URL 或工作区相对路径；
- `source_type`：primary、secondary、internal、dataset、interview 或 other；
- `publication_date`：已知时使用 ISO 日期，否则为 `unknown`；
- `accessed_at`：实时来源使用 ISO 日期，其他情况为 `not_applicable`；
- `confidence`：high、medium 或 low，并说明简短理由；
- `scope`：该来源能够支持的范围；
- `limitations`：时效、样本、方法、偏差、访问或上下文缺失；
- `claim_ids`：当前映射到该来源的重要主张。

不得用访问日期推断发布日期，也不得把搜索结果摘要当作原始来源。

## `研究.md` 研究综合

研究内容应围绕主张组织，而不是围绕链接罗列。每个重要主张记录：

- 稳定的 `claim_id`；
- 建议表述；
- 支持它的 `source_id`；
- 证据摘要；
- 反证或限定条件；
- 时效要求；
- `confidence`；
- 计划中的页面或叙事角色。

无法核验的主张使用 `[UNVERIFIED]`；没有支持来源时使用 `[SOURCE NEEDED]`。影响重大、数值型、比较型、最高级、当前状态或推动建议的主张不能在未核验状态下悄然保留；故事板批准前必须删除或限定。若仍保留，文稿审查应把它作为可能的 `HIGH` 问题处理。

证据相互冲突时，保留分歧并说明文稿采用哪一种解释。不得对不可比较的数字取平均，也不得只选最方便的来源。

## 完成检查

进入大纲阶段前确认：

- `简报.md` 包含全部必需决策与假设；
- `来源.md` 包含稳定来源 ID 和来源元数据；
- `研究.md` 把每个重要主张映射到证据或明确的未核验标记；
- 机密资料没有违反其策略被传输；
- 离线或不可用能力已披露；
- 不存在虚构事实或来源。

后续任何来源、证据或重要主张变化，都必须依照产物契约使文稿批准及全部视觉产物失效。
