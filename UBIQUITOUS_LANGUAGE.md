# Ubiquitous Language

> 状态：现行术语表，依据 `requirements_v5.md`、`docs/new_engine/*` 与已审定分析文档重建。
>
> 若本文件与 `requirements_v5.md` 第八章发生冲突，以 `requirements_v5.md` 为准；本文件负责补足跨文档统一用词与边界说明。

## 身份与在线状态

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **User** | Django 认证主体，用于登录、安全、后台授权与账号绑定。 | Account, player, AccountDB |
| **AuthIdentity** | 绑定到 User 的一个外部认证身份来源。 | login source, credential record |
| **GameAccount** | 玩家游戏域账号，承载玩家侧关系、权益与角色归属。 | User, AccountDB, player account |
| **PlatformRole** | 归属于 User 的后台平台授权角色。 | admin permission, backend role, game permission |
| **CharacterOwnership** | GameAccount 与 Character 之间的拥有关系。 | slot, character link |
| **ConnectionSession** | 一个活跃的客户端连接。 | Session, socket session |
| **AuthSession** | 一个已认证的账号会话；只有 active 会话可轮换其 token family，并持有 OOC 能力。 | login session, account session |
| **Presence** | 一个 AuthSession 当前控制某个 Character 的在场上下文。 | puppet state, active character session |
| **PresenceSnapshot** | 活跃期间保存最小检查点，并在断线或崩溃后表达有界恢复租约的短期持久记录。 | persisted presence, session archive |

## 世界与内容

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Entity** | 世界持久实体的统一根概念。 | Object, TypedObject |
| **Character** | 玩家可控制的世界内化身。 | puppet, player object |
| **NPC** | 由规则或运行时服务驱动的非玩家角色。 | mob, monster object |
| **Room** | 提供场景上下文与容器边界的地点实体。 | place, scene object |
| **Exit** | 从一个 Room 指向另一个 Room 的有向连接。 | portal, link object |
| **Item** | 可携带或可交互且不属于 Room、Exit、Character、NPC 的实体。 | object, prop |
| **StaticEntityBinding** | 一个游戏实例内，将 static Room/Exit Blueprint head 唯一绑定到 exact published revision 与 Entity 的持久记录。 | static spawn row, active room pointer |
| **SpawnMaterialization** | 证明某个 pinned Room spawn entry 的指定 ordinal 已经 initial-once 生成目标 Entity 的不可变幂等记录。 | respawn row, spawn cache |
| **ActorSkill** | Character 或 NPC 的已学武学状态，固定 Skill head、exact published revision、等级与状态版本。 | skill key row, character-only skill |
| **EquipmentBinding** | Character/NPC、装备槽与 Item instance 的唯一穿戴关系；槽位必须匹配 pinned Item definition。 | equipped flag, item slot field |
| **Region** | 用于房间分组、工具归类与内容组织的命名世界分区。 | area, zone |
| **Blueprint** | 内容模板的规范定义，用于校验、编译与生成内容。 | Prototype, proto |
| **BlueprintRevision** | Blueprint 的不可变 draft 或 published 快照；draft 不能直接活动，发布从选定 draft 创建 published revision。 | mutable draft row, prototype version |
| **ContentReleaseBatch** | 一个发布流内不可变的完整 published revision 映射；active batch 只为新选择和 batch-scoped 请求提供权威映射。 | partial release diff, latest draft set |
| **CompiledBlueprint** | 从精确 published BlueprintRevision 编译并绑定 exact dependencies 的不可变产物；pinned 实例继续消费自身 revision 的产物。 | flattened prototype, runtime proto |
| **BehaviorProfile** | 绑定到 Entity kind 或 Blueprint 的运行时行为配置包。 | typeclass, behavior class path |
| **QuestState** | 一个任务在角色或账号范围内的持久进度状态。 | quest flag blob, mission progress row |
| **FactionMembership** | 角色与门派、帮派或其他组织之间的持久关系。 | guild join row, sect relation |

## 交互、通信与帮助

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **ActorRef** | 命令、聊天与审计中统一使用的行动者或发言者引用。 | SpeakerRef, sender ref |
| **ActionDefinition** | 一个可调用动作的标准定义。 | command class, action meta |
| **ActionContext** | 一次动作执行的完整上下文。 | caller bundle, runtime vars |
| **ActionProvider** | 在特定上下文中暴露可用动作的来源。 | CmdSet provider |
| **ResolvedActionSet** | 对当前上下文收敛后的可用动作集合。 | merged CmdSet, current cmdset |
| **ChatChannel** | 结构化聊天频道。 | Channel, chat room |
| **ChatSubscription** | 参与者与 ChatChannel 的成员关系。 | subscription handler entry |
| **ChatMessage** | 频道内的持久消息。 | Msg, channel message record |
| **DirectMessage** | 频道外的一对一私信消息。 | page, tell, whisper |
| **SystemNotice** | 由系统发出的公告或推送。 | system msg, broadcast text |
| **HelpEntry** | 被统一索引和检索的一条帮助中心内容项。 | help topic row, filehelp record |
| **CommandHelp** | 从 ActionDefinition 元数据生成的帮助内容。 | auto-help, command doc help |
| **FileHelp** | 来自文档文件的帮助内容。 | filehelp record, markdown help |
| **DbHelp** | 来自后台编辑的帮助内容。 | dynamic help row, sethelp entry |

## 调度、发布与内容包

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **ScheduledJob** | 持久化的一次性调度任务。 | delayed script, one-shot task |
| **RecurringJob** | 按重复节拍执行的持久化调度任务。 | ticker, repeat task |
| **EffectTypeDefinition** | 已注册的效果运行时契约，唯一决定负载结构、叠加、tick、持久化、恢复与 handler。 | condition rule, effect config |
| **ConditionDefinition** | 通过 `effect_type_key + effect_type_version` 精确引用 EffectTypeDefinition 的版本化内容定义；参数须通过该版本的 `payload_schema`。 | condition row, status template |
| **EffectInstance** | 以 `condition_definition_revision_id` 精确引用 published ConditionDefinition revision 的具体状态挂载。 | buff script, debuff script |
| **WorldProcess** | 受调度器管理的世界级长期过程。 | daemon, global script |
| **ProgressClock** | 用于多阶段推进的计时对象。 | staged timer, ondemand task |
| **MUDLib** | 单实例在启动期加载的运行时内容包。 | runtime mudlib, plugin pack, game package |
| **Source LPC MUDLib** | 仅用于分析、转换与参考的历史 LPC 内容库。 | source mudlib, legacy mudlib |
| **ConversionProfile** | 用于指导 LPC 转换器解析与归一化的配置画像。 | profile, mudlib profile |
| **StartupPlan** | 由 MUDLib 声明的启动期 world process / recurring job 计划。 | boot script list, startup jobs |
| **SourceSnapshot** | 由 `source_snapshot_id` 标识、包含逐文件与聚合哈希的不可变 Source LPC MUDLib 输入基线。 | snapshot_id, local source path |
| **CompatibilityEnvelope** | 绑定 source snapshot、双 manifest、bundle、golden case 与逐项验证状态的不可变 XKX100 对齐范围。 | full compatibility, tested sample |
| **CapacityProfile** | 版本化的首发参考环境、数据集、负载、延迟、稳定运行与恢复预算。 | performance target, load script |

## 关系与当前约束

除非明确说明为 Evennia 来源事实，以下条目描述的是当前 New_Mud 设计约束。

- 一个 **User** 可以绑定零个或多个 **AuthIdentity**。
- 一个 **User** 可以拥有零个或多个 **PlatformRole**。
- 在单个游戏实例内，一个 **User** 映射到一个 **GameAccount**。
- 首发 register 原子创建 **User** 与 **GameAccount**，但不创建 **AuthSession**、token、Character 或 Presence；只有独立 login 创建认证会话。
- 首发时，一个 **GameAccount** 通过 **CharacterOwnership** 最多拥有一个 **Character**。
- 首发后允许放宽角色数量，但必须保留 **CharacterOwnership**，并通过显式迁移调整上限。
- **AuthSession** 只由 REST 登录创建并持久化；refresh 仅为仍处于 `active` 的既有 AuthSession 轮换 credential，不创建、恢复或复活会话。新 WebSocket 只创建 **ConnectionSession**，再用 access token 通过 `session.authenticate` 绑定既有 **AuthSession**。
- 一个 **AuthSession** 同时最多持有一个处于 `active` 或 `grace_disconnected` 的 **Presence** 租约。
- 一个 **GameAccount** 跨全部 AuthSession、ConnectionSession 与设备，同时最多有一个处于 `active` 或 `grace_disconnected` 的 **Presence** 租约。
- 普通第二控制请求默认拒绝；不得把 enter 或 resume 隐式升级为 takeover。
- 显式 `presence.takeover` 必须确认并通过策略授权，再以同一事务终止旧 **Presence** 租约、撤销旧 ticket、建立新租约与 ticket，并保存终结结果和通知 outbox。
- 事务提交后才通知旧连接；通知失败不得回滚已提交接管，旧端须在后续请求校验或状态同步时失去控制权。
- 一个活跃 **Presence** 恰好控制一个 **Character**。
- 一个 **PresenceSnapshot** 只服务唯一占用协调与有界恢复，不替代 **Presence** 或 **Character** 的权威状态。
- `grace_disconnected` 由短期 **PresenceSnapshot** 表达；断线后的运行时 **Presence** 已关闭，不得把租约状态理解为仍存活的内存对象。
- 每个 **ConditionDefinition** 必须通过 `effect_type_key + effect_type_version` 精确引用一个已注册 **EffectTypeDefinition**，且参数通过该版本的 `payload_schema`。
- 每个 **EffectInstance** 以 `condition_definition_revision_id` 精确引用 published definition revision。直接选择走请求固定的 active batch，pinned Entity 行为走其 compiled exact dependency；两者都不得漂移。
- “配置型 / 规则型 / 人工适配效果”只描述内容 authoring 与 adapter 路径，不是三套运行时效果类型；叠加、tick、持久化、恢复与 handler 仍只归精确 **EffectTypeDefinition** 版本。
- 一个 **BlueprintRevision** 是不可变快照；编辑创建新 draft，发布创建 published revision，回滚创建新 **ContentReleaseBatch**，都不改写旧 revision。依赖目标变化时，raw 未变的引用方也创建 dependency-recompile revision。
- 新 spawn 与 batch-scoped 选择只消费 active **ContentReleaseBatch** 的 **CompiledBlueprint**；既有持久实例继续消费所钉 revision 的 immutable compiled payload 和 exact dependencies，直到显式迁移。
- world init 先通过 **StaticEntityBinding** 幂等物化 Room/Exit，再通过 **SpawnMaterialization** 执行 pinned Room 的 initial-once 刷点；active batch 变化不移动既有 binding。
- 一个 **ActorSkill** 固定一个 actor 的 exact Skill revision；`JifaBinding` 与 `PrepareBinding` 引用它，prepare 另存基础 enable slot 与有向 combine order。
- 一个 **EquipmentBinding** 只绑定 quantity=1 且 exact definition 槽位匹配的 Item；Item 的位置仍只由 `location_entity_id` 表达。
- 一个 **ChatMessage** 属于一个 **ChatChannel**，并由一个 **ActorRef** 发出。
- 一个 **DirectMessage** 从一个 **ActorRef** 发往另一个 **ActorRef**。
- 一个服务器实例在启动期只加载一个 **MUDLib**。
- seed bootstrap 的“空”按 `(instance_id, mudlib_key)` namespace 判断；其他实例或 MUDLib 的数据既不阻断也不授权当前 namespace bootstrap。
- **Source LPC MUDLib** 不直接作为运行时内容包加载，而是转换为 **Blueprint**、帮助内容、seed 数据与适配骨架。
- 每个可复现转换或黄金验收输入都绑定一个不可变 **SourceSnapshot**，不得用本机路径或裸 `snapshot_id` 代替 `source_snapshot_id`。
- 只有 **CompatibilityEnvelope** 内状态为 `verified` 的能力可声明与 XKX100 对齐；包络外行为必须标为未验证或未纳入。
- 内容许可、权利证明与公开发布法律判断不属于工程里程碑；工程只冻结可复现的 **SourceSnapshot**、逐文件哈希、manifest、bundle 与制品依赖。
- M1 发布候选必须达到已批准 **CapacityProfile**；部署配置不能自行降低 V5 的最低目标。
- **BehaviorProfile** 描述运行时行为绑定；**ConversionProfile** 描述转换器解析规则；两者不是同一类 profile。

## 示例对话

> **Dev:** "用户密码登录成功后，是直接让这个 **User** 进世界吗？"
> **Domain expert:** "不是。REST 登录创建持久 **AuthSession**；refresh 只能轮换仍 active 会话的 credential。新 WebSocket 只创建 **ConnectionSession**，再用 access token 经 `session.authenticate` 绑定它，选角后才形成 **Presence**。"
>
> **Dev:** "那 `gm` 权限和玩家角色归属都挂在 **GameAccount** 上吗？"
> **Domain expert:** "不是。后台授权属于 **User** 的 **PlatformRole**；角色归属走 **GameAccount** 到 **Character** 的 **CharacterOwnership**。"
>
> **Dev:** "文档里说的 profile，到底是 NPC 行为还是 LPC 转换规则？"
> **Domain expert:** "要拆开说。运行时叫 **BehaviorProfile**；转换器配置叫 **ConversionProfile**。"
>
> **Dev:** "源 LPC 代码库能直接作为运行时 **MUDLib** 启动吗？"
> **Domain expert:** "不能。运行时加载的是 **MUDLib**；历史源码要明确叫 **Source LPC MUDLib**，它只作为转换输入。"

## Flagged ambiguities

- “account” 曾同时指 **User**、**GameAccount** 和 Evennia 的 `AccountDB`；今后默认拆开使用，认证主体叫 **User**，游戏域账号叫 **GameAccount**。
- “session” 曾同时指物理连接、认证态与控角态；今后分别使用 **ConnectionSession**、**AuthSession**、**Presence**。
- “role” 可能指后台平台授权、帮派职位、频道成员身份或 GM 裁决能力；后台授权统一叫 **PlatformRole**，其他场景必须带具体领域前缀。
- “profile” 曾混指运行时行为配置与转换器配置；今后分别使用 **BehaviorProfile** 与 **ConversionProfile**。
- “MUDLib” 在当前设计中默认指运行时内容包；若讨论历史 LPC 输入，必须明确写 **Source LPC MUDLib**。
- “prototype” 与 “blueprint” 曾并行出现；今后在 New_Mud 设计层统一使用 **Blueprint**，仅在描述 Evennia 现状时保留 Prototype 作为来源名词。
- “condition” 与 “status” 曾同时指规则定义和运行时挂载结果；规则定义统一叫 **ConditionDefinition**，挂载实例统一叫 **EffectInstance**。
- “draft row” 不表示可原地编辑的记录；**BlueprintRevision** 一经创建即不可变。
- `SpeakerRef`、sender、发言者对象等说法曾并行出现；今后统一使用 **ActorRef**。
- “help entry” 若指统一索引项，可用 **HelpEntry**；若指来源分类，必须明确写 **CommandHelp**、**FileHelp** 或 **DbHelp**。
- “object” 在 Evennia 语境中可指泛化世界对象；在 New_Mud 设计层应优先使用 **Entity** 或其具体子类名词。
