# Ubiquitous Language — Engineering Index

> 状态：现行、非权威的工程术语索引。
>
> 领域概念只在根目录 `CONTEXT.md` 定义；产品语义以 `requirements_v6.md` 为准；协议、状态机、持久结构、事务和失败语义以 `docs/new_engine/11-16` 对应冻结合同为准。本文件只统一未进入领域词汇表的工程名称、来源术语和常见歧义，不重复定义领域概念或实施规则。

## 使用方式

1. 先读 `CONTEXT.md`，确定 New_Mud 的领域概念及禁止混用的名称。
2. 涉及产品范围、里程碑或验收结果时，回到 `requirements_v6.md`。
3. 涉及协议、状态机、持久化、事务或失败行为时，回到对应冻结合同。
4. 只有在需要统一工程名称、Evennia/LPC 来源名称或分析层别名时，才使用本索引。

## 领域术语入口

以下概念的规范定义只存在于 `CONTEXT.md`，本文件不建立第二份定义：

- 身份与控制：**User**、**AuthIdentity**、**GameAccount**、**PlatformRole**、**Character**、**CharacterOwnership**、**ConnectionSession**、**AuthSession**、**Presence**、**PresenceSnapshot**、**GameAccountLifecycle**、**VerifiedContactMethod**、**VerificationChallenge**、**RecoveryCode**（已退役历史术语）、**CharacterCreationProfile**、**CharacterDisplayName**、**RetiredCharacter**、**PresenceRecovery**。
- 世界与内容：**Entity**、**Actor**、**NPC**、**Room**、**Exit**、**Region**、**Item**、**Blueprint**、**BlueprintRevision**、**ContentReleaseBatch**、**MUDLib**。
- 玩法与生命周期：**Sparring**、**SafeDefeat**、**GoldenSkillChain**、**VillageTopologyEnvelope**、**VillageInteractionEnvelope**、**UnavailableInteraction**、**LootClaim**、**ItemRetirement**、**EffectTypeDefinition**、**ConditionDefinition**、**EffectInstance**。
- 通信与治理：**PlayerBlock**、**ChannelMute**、**ModerationCase**、**ChatChannel**、**DirectMessage**、**SystemNotice**。
- 来源与发布：**SourceSnapshot**、**CompatibilityEnvelope**、**ReleaseManifest**、**CapacityProfile**、**PublicV1Gate**、**PublicV1**。

## 工程术语

这些词用于统一设计、合同、代码和测试中的跨文档工程表达。只在一个冻结合同内使用、且没有跨文档歧义的 schema、表或状态类型继续由该合同定义，不要求全部收入本索引。索引中的名称不得覆盖 `CONTEXT.md` 中的领域定义，也不得替代对应冻结合同。

### 内容物化与运行时绑定

| Term | Engineering meaning | Aliases to avoid |
| --- | --- | --- |
| **StaticEntityBinding** | 将静态 Room/Exit 的 Blueprint 身份、精确 revision 与已物化 Entity 关联的持久记录。 | static spawn row, active room pointer |
| **SpawnMaterialization** | 记录某个 pinned spawn entry 的指定 ordinal 已完成初次物化的幂等证据。 | respawn row, spawn cache |
| **ActorSkill** | Actor 已学习并固定到精确 Skill revision 的持久状态。 | skill key row, character-only skill |
| **EquipmentBinding** | Actor、装备槽和 Item instance 之间的唯一穿戴关系。 | equipped flag, item slot field |
| **CompiledBlueprint** | 从精确 published BlueprintRevision 编译并绑定精确依赖的不可变运行时产物。 | flattened prototype, runtime proto |
| **BehaviorProfileDefinition** | 在 typed registry 中定义 Entity kind 或 Blueprint 可绑定的运行时行为配置。 | BehaviorProfile, typeclass, behavior class path |
| **CharacterCreationProfileDefinition** | 在 typed registry 中实现一个精确版本 CharacterCreationProfile 的工程定义。 | character creation config, starter preset |
| **QuestState** | 任务在 Character 或 GameAccount 范围内的持久进度表示。 | quest flag blob, mission progress row |
| **FactionMembership** | Character 与门派、帮派或其他组织之间的持久关系表示。 | guild join row, sect relation |

### 动作、通信与帮助

| Term | Engineering meaning | Aliases to avoid |
| --- | --- | --- |
| **ActorRef** | 命令、战斗、聊天和审计中指向 Character 或 NPC 的统一 Actor 引用；不得引用 GameAccount、SystemNotice 或平台操作者。 | SpeakerRef, sender ref, principal ref |
| **ActionDefinition** | 一个可调用动作的标准注册定义。 | command class, action meta |
| **ActionContext** | 一次动作执行所需的结构化上下文。 | caller bundle, runtime vars |
| **ActionProviderDefinition** | 在 typed registry 中定义特定上下文可提供哪些动作的工程条目。 | ActionProvider, CmdSet provider |
| **ResolvedActionSet** | 针对当前上下文解析后的可用动作集合。 | merged CmdSet, current cmdset |
| **ChatSubscription** | Actor 与 ChatChannel 之间的参与关系。 | subscription handler entry |
| **ChatMessage** | ChatChannel 中的持久消息记录。 | Msg, channel message record |
| **HelpEntry** | 被统一索引和检索的一条帮助内容项。 | help topic row, filehelp record |
| **CommandHelp** | 从 ActionDefinition 元数据生成的帮助内容。 | auto-help, command doc help |
| **FileHelp** | 从受版本控制文档加载的帮助内容。 | filehelp record, markdown help |
| **DbHelp** | 从后台维护的持久数据加载的帮助内容。 | dynamic help row, sethelp entry |

### 调度、来源与转换

| Term | Engineering meaning | Aliases to avoid |
| --- | --- | --- |
| **ScheduledJob** | 持久化的一次性调度任务。 | delayed script, one-shot task |
| **RecurringJob** | 按重复节拍执行的持久化调度任务。 | ticker, repeat task |
| **WorldProcess** | 由调度系统管理的世界级长期过程。 | daemon, global script |
| **ProgressClock** | 表达多阶段推进的计时对象。 | staged timer, ondemand task |
| **Source LPC MUDLib** | 只用于分析、转换和参考的历史 LPC 内容库。 | runtime MUDLib, plugin pack |
| **ConversionProfile** | 指导 LPC 转换器解析和归一化的配置画像。 | BehaviorProfile, generic profile |
| **StartupPlan** | 由运行时 MUDLib 声明的启动期 world process 与 recurring job 计划。 | boot script list, startup jobs |

## 权威合同索引

| 关注点 | 权威来源 |
| --- | --- |
| 身份、恢复、后台授权 | `requirements_v6.md` 第八章、`docs/new_engine/08_PERMISSIONS_ADMIN_API.md`、`13_SESSION_AUTH_STATE_MACHINE.md` |
| WebSocket 请求、事件与错误 | `docs/new_engine/11_PROTOCOL_CATALOG.md` |
| Blueprint、Registry、内容发布与物化 | `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` |
| 连接、AuthSession、Presence 与 takeover/recovery | `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md` |
| 战斗、技能、Condition/Effect 与 Item | `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` |
| H5 页面、缓存、重连与交互 | `docs/new_engine/15_FRONTEND_H5_CONTRACT.md` |
| 部署、ReleaseManifest、容量、恢复与测试 | `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` |
| 世界、命令、聊天、帮助、调度与转换概念设计 | `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`–`09_MUDLIB_CONVERTER.md` |

## 常见歧义

| 模糊说法 | 应使用的精确名称 |
| --- | --- |
| account | 认证主体用 **User**；游戏域身份用 **GameAccount**；Evennia 来源事实才使用 `AccountDB`。 |
| session | 物理连接用 **ConnectionSession**；认证生命周期用 **AuthSession**；当前连接上的控角上下文用 **Presence**；持久恢复租约用 **PresenceSnapshot**。 |
| role | 后台授权用 **PlatformRole**；其他角色或职位必须带具体领域前缀。 |
| profile | 角色创建领域概念用 **CharacterCreationProfile**，其 registry 实现用 **CharacterCreationProfileDefinition**；运行时行为 registry 用 **BehaviorProfileDefinition**；转换配置用 **ConversionProfile**；容量门禁用 **CapacityProfile**。 |
| MUDLib | New_Mud 运行时内容包用 **MUDLib**；历史 LPC 输入必须写 **Source LPC MUDLib**。 |
| prototype | New_Mud 内容身份用 **Blueprint**；只有 Evennia 来源事实保留 `Prototype`。 |
| condition/status | 内容定义用 **ConditionDefinition**；具体挂载用 **EffectInstance**；类别语义用 **EffectTypeDefinition**。 |
| object | New_Mud 世界对象用 **Entity** 或具体子类型；只有 Evennia 来源事实使用泛化 `Object`。 |
| help | 统一索引项用 **HelpEntry**；来源分类必须写 **CommandHelp**、**FileHelp** 或 **DbHelp**。 |

新增或修改术语时，先判断它是领域概念、产品语义还是工程名称，并只修改相应权威来源。不得为了让现有代码显得正确而反向改写术语边界。
