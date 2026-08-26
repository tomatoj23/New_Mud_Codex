# New_Mud 项目需求文档 V6

## 一、文档定位

### 1.1 文档用途

本版本用于统一项目边界、技术路线、首发闭环与长期扩展方向。

本版本不是直接拆任务开工的实施细案。

本版本是产品目标、范围、里程碑与验收结果的权威基线。协议、状态机、持久结构和测试机制由对应冻结实施合同负责。

本版本可以冻结影响产品验收的跨系统不变量，但不复制实现合同作为第二份字段或流程权威。第十七章定义两层文档的同步与冲突处理规则。

### 1.2 与既有文档的关系

- `archive/requirements/requirements_v1.md` 是已废弃的历史草案。
- `archive/requirements/requirements_v2.md` 是已废弃的技术路线收敛版本。
- `archive/requirements/requirements_v3.md` 是已废弃的首发范围与即时战斗收敛版本。
- `archive/requirements/requirements_v4.md` 是已废弃的 XKX100-first 收敛版本。
- `requirements_v5.md` 自 V6 生效起冻结为历史基线，不再接受原地语义修改。
- 本版本为新的主需求基线。
- `docs/new_engine/` 是本版本的下游设计文档集。
- 根目录 `CONTEXT.md` 是项目特有领域词汇表；`UBIQUITOUS_LANGUAGE.md` 是非权威工程术语索引。若领域词汇表、工程索引或下游文档与本版本发生产品语义冲突，以本版本为准。

### 1.3 `evennia-main/` 的角色

`evennia-main/` 在本项目中的角色已经明确如下：

- 它是本地参考源码。
- 它是架构分析与设计审计的依据。
- 当前参考快照版本为 `6.0.0`。
- 它不是运行时依赖。
- 它不参与本项目最终部署。
- 本项目不要求与 Evennia 工程结构兼容。

### 1.4 文档层级约束

本版本负责回答以下问题：

- 项目做什么。
- 项目不做什么。
- 首发闭环做到哪里。
- 关键系统按什么方向设计。

本版本不负责回答以下问题：

- 每个模块的最终 Python API 细节。
- 每张表的最终字段与索引定义。
- 每条 WebSocket 协议的最终 schema。
- 每个需求里程碑的任务级拆分与工期估算。

发生重复时按关注点确定权威：

- 产品目标、范围、里程碑和验收结果以本版本为准。
- 协议字段、状态机、持久结构、事务与失败语义以 `docs/new_engine/11-16` 的对应冻结合同为准。
- 项目领域概念的规范名称与紧凑定义以根目录 `CONTEXT.md` 为准；产品范围和产品语义以本版本为准，其中身份产品语义集中在第八章。`UBIQUITOUS_LANGUAGE.md` 只索引非重复工程名称和常见歧义。
- 无法按关注点判定的冲突必须阻断合并，由需求与合同所有者在同一变更中共同裁决。

### 1.5 `V1` 的含义

本文中的 `V1` 专指 New_Mud 的首发产品版本，与历史文件 `archive/requirements/requirements_v1.md` 无关。

需要引用历史需求文件时，必须写出完整文件名，不得只写“V1 需求”。

### 1.6 V6 的关键分层

V6 把此前混写为“首发”的两种结果拆开：

- 需求里程碑 M1 及其 M1-A / M1-B 是内部、封闭交付步骤；M1 完成不等于允许公众注册或对外运营。
- `PublicV1Gate` 是独立于需求里程碑 M0-M6 和 Engine Stage Ex 的公开发布门禁，稳定需求 ID 为 `RELEASE-001`。
- 本文单独写“Public V1”时，专指通过 `PublicV1Gate` 后由项目方运营的首个公开版本；旧段落中未限定的“首发合同”只描述实现的第一版合同，不自动构成公开发布证据。

V6 同时以可度量兼容包络替代任何全量或全局 XKX100 兼容承诺。只有明确绑定来源、范围和验证状态的能力可以声明为已对齐。

---

## 二、项目定位与边界

### 2.1 项目目标

构建一款中文武侠题材的多人在线文字 MUD。

项目的第一目标是以现代技术体系重构 XKX100 的核心世界、武学与战斗体验。

项目采用自研引擎 + XKX100 领域内容包的架构。

当前不以打造通用可替换 MUDLib 平台为目标，但保留后续内容扩展能力。

项目当前支持 Web 接入，首发覆盖 PC 浏览器与移动端浏览器，预留微信小程序接入点。

项目以纯文字体验为主，预留图标、图片、音效扩展接口。

项目需把稳定性、可维护性、安全性放在最高优先级。

### 2.2 目标使用者与成功条件

首发服务以下使用者：

- 熟悉文字 MUD、重视键盘效率与原版语义的 PC 玩家。
- 使用移动浏览器、依赖触控和中文输入法完成主要流程的移动玩家。
- 制作和发布房间、NPC、物品、武学等内容的内容编辑。
- 负责账号处置、巡检、恢复与发布审批的运营、GM 和 QA。

M1 的内部交付成功必须同时满足：

- 新玩家无需数据库或开发者人工介入，即可注册账号、创建唯一角色并完成固定首发纵切。
- 两个独立账号可进入同一世界，完成公共聊天、私聊和权威状态同步。
- 玩家可在固定兼容包络内完成移动、战斗、战利品与 `jifa / prepare / perform / exert` 验收。
- 内容编辑可对首发白名单对象创建草稿、校验、查看差异、发布和回滚。
- M1-B 完成其已实现范围内的安全、数据一致性、故障恢复与来源可复现检查。

Public V1 的成功还必须满足第 11.6-11.11 节的 `PublicV1Gate`：完整浏览器矩阵、容量与 soak、五个业务范围恢复、封闭试运行、社区治理、公开运营资料和可回滚发布证据均不得由 M1 完成状态替代。

### 2.3 总体原则

- 不使用 Evennia 作为运行时框架。
- 借鉴 Evennia 的设计思想，但不复用其运行时代码。
- 对 Evennia 的借鉴只以本地 `evennia-main/` 的 `6.0.0` 快照源码为准。
- 后端采用模块化单体架构。
- 只做单实例。
- 不做多实例水平扩展。
- 不做跨实例状态同步。
- 当前主线只服务 XKX100 内容重构。
- 一个服务器实例只加载一个原生内容包。
- 运行中不切换内容包。
- 内容与规则可扩展。
- 扩展性服务于 XKX100 长期演进与未来现代网游玩法接入。
- 稳定性、可维护性、安全性与核心玩法目标同级，优先级最高。
- 不为了短期复刻速度牺牲架构清晰度、可测试性与安全边界。
- 代码热更新不作为目标。
- 内容发布以冷发布为主。
- 首发闭环优先于长期能力完整度。

### 2.4 借鉴 Evennia 的范围

- 仅基于本地 `evennia-main/` 的 `6.0.0` 可验证快照源码进行借鉴。
- 借鉴 Typeclass 思想。
- 借鉴命令系统与权限校验思路。
- 借鉴对象生命周期 Hook 设计。
- 借鉴 Script、Scheduler、世界事件的抽象方式。
- 借鉴 Evennia `Prototype` 的模板归一化与继承思路；New_Mud 的规范术语固定为 `Blueprint`，仅描述 Evennia 来源事实时使用 `Prototype`。
- 借鉴房间、出口、对象、角色的统一实体建模方式。

### 2.5 明确不借鉴的范围

- 不使用 Evennia 的 Twisted + Autobahn 网络栈。
- 不使用 Evennia 的 Portal / Server 双进程模型。
- 不使用 Evennia 自带 Admin 扩展。
- 不复用 Evennia 的 Attribute 魔法层作为项目主状态模型。
- 不要求兼容 Evennia 的目录结构、加载流程与对象实现。

### 2.6 首发边界概述

M1 内部闭环不是完整武侠大世界，也不是 XKX100 的一次性全量重建。

M1 内部闭环是 XKX100 现代化重构的第一条可玩纵切。

M1 内部闭环只要求打通以下最小链路：

- 可注册并登录
- 可进世界
- 可查看
- 可移动
- 可聊天
- 可实时战斗
- 可使用基础物品
- 可通过后台编辑内容

以下能力移出首发闭环：

- 短信验证码
- 微信小程序接入
- 微信授权登录
- XKX100 首轮转换验收

Public V1 不是把这条两房间纵切直接公开。其起始区域、玩家循环、内容规模、社区安全和运维门禁由第 11.6-11.11 节另行定义。

### 2.7 内容来源与发布责任边界

内容许可、权利证明和公开发布的法律判断不属于本项目工程需求，不进入 M0-M6 完成条件，也不由 CI、构建或部署合同执行。

工程侧仍必须记录源文件的技术来源、不可变快照身份、逐文件哈希、转换链与制品依赖，以保证可复现、可审计和可验证；这些记录不表达或推断任何权利结论。

具体部署者自行承担目标环境中的内容使用与发布责任。工程文档不得用 `content_release_mode` 或同类许可状态阻断实现、测试或 M0-M6。

Public V1 前，运营者必须公开确认其内容责任并发布第 11.9 节列出的玩家资料。该人工确认不表达法律判断，也不得重新引入 M0-M6 或 CI 自动许可门禁。

---

## 三、技术路线与调整结论

### 3.1 调整结论

基于新增约束与 XKX100 调研，技术栈需要做有限调整。

调整原则不是推翻历史 `archive/requirements/requirements_v4.md` 已收敛的 XKX100-first 方向，而是进一步冻结首发平台、身份策略、可复现验收与阶段边界。

本轮调整结论如下：

- `Django + DRF + Channels + PostgreSQL` 仍然保留。
- `uni-app + Vue 3 + Pinia` 仍然保留。
- 项目主轴是 XKX100 的现代化重构，而不是构建通用 LPC 兼容平台。
- 归一化后的已发布内容以 PostgreSQL 为唯一持久化真源。
- 原生 MUDLib 包定位为 `seed / rules / adapters / tests` 集合，而不是运行时可变内容真源。
- `Redis` 不再承担分布式锁职责。
- `Celery` 不再作为首发闭环的必选基础设施。
- WebSocket 断线恢复以“安全重建”为默认策略，不要求 V1 事件流补齐缓冲。
- 首发核心运行时以单实例、单写者、进程内调度为准。
- 转换器当前只服务 XKX100 重构，不以兼容其他 MUDLib 为当前需求约束。
- 所有架构取舍都必须优先满足稳定性、可维护性与安全性。

### 3.2 后端核心必选栈

- 语言：Python 3.14+
- Web 框架：Django
- REST API：Django REST Framework
- 实时通信：Django Channels
- ASGI 服务：Daphne
- 数据库：PostgreSQL 18+

### 3.3 前端核心栈

- 框架：uni-app（Vue 3）
- 状态管理：Pinia
- 首发平台：H5（覆盖 PC 浏览器与移动端浏览器）
- 微信小程序为后续接入项
- PC 端通过 H5 提供增强输入体验
- 移动端 H5 必须保证触控操作与窄屏布局可用

### 3.4 推荐但非首发必选的基础设施

以下技术保留为推荐能力，但不强制成为首发闭环前置：

- Redis
- Celery
- Celery Beat
- 外部对象存储
- 专用消息告警平台

### 3.5 Redis 的定位

Redis 在 V5 中不是首发核心必选项。

它的定位调整为按需引入的基础设施。

允许的用途包括：

- Channels 的 Redis channel layer
- 在线状态辅助缓存
- 短期缓存
- 限流辅助

如果不引入 Redis channel layer，则首发部署必须保持单 ASGI 进程，不允许拆成多个相互独立的 Channels worker / Daphne 进程后再依赖进程内状态广播。

不允许把 Redis 写成“多实例协调前提”，因为本项目只做单实例。

### 3.6 Celery 的定位

高频游戏节拍由引擎内 Scheduler / Tick Service 负责。

战斗节拍、`busy` / `condition` 等短期状态推进不交给 Celery。

首发闭环不要求 Celery。

后续若接入以下能力，再按需引入 Celery：

- 短信验证码发送
- 微信异步回调处理
- 数据导出
- 定时备份触发
- 低频审计汇总任务

### 3.7 单实例并发控制策略

单实例前提下，优先采用以下并发控制方式：

- PostgreSQL 事务
- 行级锁
- 乐观版本号
- 进程内锁

明确不引入以下语义：

- 分布式锁
- 跨实例一致性协议
- 跨实例 Presence 同步
- 事件总线中台

### 3.8 数据库策略

- 开发、测试、生产统一使用 PostgreSQL。
- SQLite 仅允许用于个人实验，不作为主线环境。
- 所有正式模型、迁移、索引策略均以 PostgreSQL 为准。
- 所有首发性能判断均以 PostgreSQL 行为为准。

---

## 四、运行时架构

### 4.1 HTTP / API 层

职责如下：

- 已验证邮箱、账号名和密码组成的自助注册
- 登录、登出、刷新 Token
- 角色创建与角色列表
- 背包、武学、任务等非高频查询
- 后台管理接口
- 后续预留手机号、微信、支付接入点

### 4.2 WebSocket 实时层

职责如下：

- 游戏主交互流
- 房间广播
- 战斗事件推送
- 聊天消息推送
- 在线状态变化
- 即时技能释放结果回传

客户端请求信封固定包含 `version / request_id / type / payload`。

服务端应用信封固定包含 `version / type / seq / ts / payload`，其中 `seq` 与 `ts` 不是建议字段。

只有请求终结响应额外包含顶层 `request_id`。广播和领域事件不得携带触发请求的 `request_id`。

### 4.3 WebSocket 可靠性原则

V1 不做复杂实时帧同步。

V1 默认采用“安全重建”而不是“事件补齐”作为断线恢复策略。

必须满足：

- 客户端断线重连后可恢复当前角色状态摘要。
- 当前房间、角色状态、战斗摘要可由服务端重新下发。
- 角色状态摘要必须原子包含核心资源及完整背包、装备、已学技能、激发与准备绑定，并携带可核对的角色、背包和行级版本；空集合不得解释为增量未变化。
- 关键动作必须有显式失败反馈。
- 客户端不得根据本地预测直接修改权威状态。
- 若未来引入事件补齐，必须另行定义有界缓冲、生命周期与存储位置；本版本不作为前提。

### 4.4 游戏应用层

职责如下：

- 命令解析与路由
- 权限与前置条件校验
- 房间移动与场景交互
- 战斗结算
- 任务推进
- 交易校验
- 声望与组织关系变更
- 内容与交互事件输出

### 4.5 游戏调度层

职责如下：

- 世界时间推进
- NPC 作息切换
- 定时刷新
- `busy`、中毒、流血、点穴等状态推进
- 战斗中 `EffectInstance` 的短期生命周期
- 随机事件触发
- 非战斗中的周期世界逻辑

调度层是引擎核心，不依赖第三方任务队列的执行语义。

### 4.6 权威状态与持久化边界

以下状态以 PostgreSQL 为持久化真源：

- User
- GameAccount
- AuthSession
- 短期 PresenceSnapshot
- Character
- 物品实例
- 房间与出口拓扑
- 任务进度
- 声望与组织关系
- `ScheduledJob` 与 `RecurringJob` 主记录，以及需恢复的 occurrence、run 与 lock lease 状态
- `durable` EffectInstance
- 已发布 Blueprint、内容定义与发布批次

以下状态以单实例运行时内存为主：

- ConnectionSession
- 当前连接上已激活的运行时 Presence
- 房间订阅关系
- 活跃 CombatInstance
- `runtime_only` EffectInstance
- 战斗中的临时动作上下文
- 到期候选队列与当前 worker / coroutine 句柄
- `CombatLoop` 与 `RuntimeTimer`
- 短期 UI 推送上下文

关键结算结果必须回写 PostgreSQL。

`grace_disconnected` 仅是短期 PresenceSnapshot 表达的逻辑控制租约状态，不表示内存中仍存在 Presence。

ScheduledJob 与 RecurringJob 的主记录、occurrence、attempt/run、concurrency key、策略决策及可恢复 lock lease 必须持久化；内存只保留到期候选队列和当前 worker/coroutine 句柄。CombatLoop 与 RuntimeTimer 不建立数据库主记录。

原生 MUDLib 包中的 seed 数据只用于初始导入、离线导出或测试，不作为运行中后台编辑后的事实真源。

### 4.7 故障恢复原则

进程重启后，短期运行时状态允许丢失，但必须有安全回退策略。

例如：

- 战斗中断后角色回到非战斗状态。
- `busy`、临时战斗上下文与短期状态在无法恢复时按安全策略重置。
- 在线 Presence 全量重建。
- 活跃交互上下文在无法恢复时安全失效，而不是半残留。

---

## 五、核心领域与引擎设计

### 5.1 核心对象模型

引擎采用“基础类型 + 组件 / Handler 组合”的对象模型。

保留 Typeclass 思想，但避免深层继承失控。

基础实体至少覆盖以下范围：

- User
- AuthIdentity
- GameAccount
- Character
- Region
- Room
- Exit
- NPC
- ItemDefinition
- Item
- SkillDefinition
- SkillMoveDefinition
- ConditionDefinition
- EffectInstance
- Quest
- Dialogue
- Shop
- Reputation / Faction
- LootTable
- Trigger
- CombatInstance

### 5.2 核心对象的定位

| 对象 | 主要职责 | 状态与持久化边界 | 固定首发纵切 |
|:---|:---|:---|:---|
| User | 认证与后台授权主体 | 登录凭据、后台角色 | 必做 |
| GameAccount | 玩家游戏域账号 | 角色归属、玩家侧关系 | 必做 |
| Character | 玩家可控角色 | 属性、背包、任务、声望、已学技能、激发 / 准备状态 | 必做 |
| Room | `kind=room` Blueprint 与静态 Entity | 描述、区域、坐标、刷点；实例固定 exact revision | 必做 |
| Exit | `kind=exit` Blueprint 与静态 Entity | exact source/target Room refs、方向、条件；外部边界不物化 | 必做 |
| StaticEntityBinding | 静态世界实体的幂等绑定 | 一个实例内把 Room/Exit head 唯一绑定到 exact revision 与 Entity | 必做 |
| SpawnMaterialization | 房间初始刷点的幂等物化记录 | 固定 room revision、spawn entry、ordinal 与生成 Entity；首发仅 `initial_once` | 必做 |
| NPC | 非玩家角色 | 对话、AI、掉落、商店及以 BlueprintRef 表达的初始 skill/item loadout | 必做 |
| ItemDefinition | `kind=item` Blueprint / CompiledBlueprint 的领域语义 | 分类、效果、装备位、堆叠、容器策略与必填 `source_ref`；不建平行主表 | 必做 |
| Item | `Entity(kind=item)` 持久实例 | 精确 `blueprint_revision_id`、quantity、统一 `location_entity_id` 与 `state_version`；不复制定义字段 | 必做 |
| EquipmentBinding | Actor 装备关系 | 绑定 Character/NPC 与 Item；槽位必须匹配 pinned Item revision，且是当前穿戴状态的唯一真源 | 必做 |
| SkillDefinition / SkillMoveDefinition | `kind=skill/skill_move` Blueprint 的领域语义 | 可激发用途、组合规则、exact move revision、perform / exert action 与规则引用；不建独立定义主表 | 必做 |
| ActorSkill / JifaBinding / PrepareBinding | Character/NPC 武学状态 | 固定 exact skill head/revision、等级、激发与准备绑定；升级只允许显式受审计迁移 | 必做 |
| ConditionDefinition | 状态效果的版本化内容定义 | 以 `effect_type_key + effect_type_version` 精确引用已注册类型；内容参数须通过该版本的 `payload_schema` | 必做 |
| EffectInstance | 引用 ConditionDefinition 并附着到运行时目标的实例 | 以 `condition_definition_revision_id` 精确引用定义 revision；`runtime_only` 仅内存，`durable` 才持久化 | M1 按策略实现 |
| Quest | 任务定义与进度 | 定义与角色进度持久化 | 非 M1 前置；M2 后续 |
| Dialogue | 对话树与文本 | 节点、条件、选项持久化 | 非 M1 前置；M2 后续 |
| Shop | 商店定义 | 货品、价格、限制持久化 | 非 M1 前置；M2 后续 |
| Reputation / Faction | 声望与组织关系 | 定义、正邪、门派与组织归属持久化 | 非 M1 前置；M3 后续 |
| CombatInstance | 活跃战斗上下文 | 仅运行时内存；结算结果回写 Character、Item 与 `durable` Effect | M1 战斗纵切 |

本节只冻结以下产品可观察不变量：

- 世界、角色、物品、技能和状态实例必须绑定可追溯的内容版本；新发布不得静默改写既有实例。
- 世界初始化和 NPC loadout 必须可重入；重启不得重复生成房间、NPC、物品、技能或装备关系。
- 转换范围外的出口必须明确显示为不可通行边界，不得静默删除、伪造目标或生成猜测内容。
- 背包、装备、容器、数量和消耗必须原子一致；冲突请求不得自动重放、复制物品、超容或形成容器环。
- 已装备物品只有一个穿戴真源；可装备物品不得堆叠，耗尽后不得复活。
- Condition 与 Effect 必须固定精确版本；发布新定义不得改变既有状态的叠加、tick、恢复或处理语义。
- 无法唯一解析的来源必须失败或进入人工复核，不得依赖活动最新版补齐缺失引用。

Entity、Blueprint、binding、版本字段、约束和发布读取规则以 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 与 `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 为实施权威。

snapshot、并发版本和协议错误以 `docs/new_engine/11_PROTOCOL_CATALOG.md` 为实施权威。

调度与 Effect 的概念分层见 `docs/new_engine/07_SCHEDULER_EFFECTS.md`；registry 与恢复 schema、战斗持久化边界、恢复验收分别以合同 12、14、16 为实施权威。

### 5.3 内容框架覆盖原则

本项目当前的内容框架以 XKX100 首轮落地为第一优先级。

当前版本不再把“兼容更多 MUDLib”作为首发技术约束，也不为了未知样本提前做过宽抽象。

抽象层的主要职责是承接 XKX100 重构与未来现代网游玩法扩展，而不是服务通用 LPC 兼容。

因此引擎内容层在当前阶段必须优先支持以下类别：

- 世界拓扑
- 静态实体定义
- 技能与 action 定义
- `jifa` / `prepare` 对应的技能槽位与激活关系
- `perform` / `exert` 引用与前置条件
- 门派 / class / 师承关系
- ConditionDefinition，以及毒素、忙乱等 EffectInstance
- 对话、商店、基础任务
- 掉落、刷新与场景交互
- 面向未来扩展的多人玩法与长期成长挂点
- 无法自动归一化行为的未适配清单

### 5.4 Blueprint 与实例

- Blueprint 用于定义静态模板。
- 实例用于承载运行时状态。
- 可转换的 XKX100 数据优先落为 Blueprint。
- 玩家角色、掉落物、战斗状态属于实例数据。
- Blueprint 必须支持版本号、来源标记与导入批次标记。
- 已发布 Blueprint 与内容定义以 PostgreSQL 为准。
- V1 只要求草稿 / 已发布两个层次与批次级回滚。
- V1 不要求运行中对活体实例做字段级热同步。

### 5.5 组件与 Handler

建议优先采用组合，而不是持续增加继承层级。

可复用组件包括：

- CombatComponent
- InventoryComponent
- EquipmentComponent
- DialogueComponent
- AIComponent
- TradeComponent
- QuestGiverComponent
- EffectComponent
- ReputationComponent
- VisibilityComponent

### 5.6 生命周期 Hook

引擎统一提供以下 Hook：

- `at_spawn`
- `at_enter`
- `at_leave`
- `at_receive_command`
- `at_tick`
- `at_skill_cast`
- `at_damage`
- `at_combat_start`
- `at_combat_end`
- `at_destroy`

MUDLib 只能使用公开 Hook 与服务接口扩展行为。

### 5.7 命令系统

客户端按钮、快捷键、文本输入最终统一进入同一命令总线。

命令处理顺序如下：

1. 输入标准化
2. 命令识别
3. 权限与状态校验
4. 业务执行
5. 事件输出
6. 日志与审计记录

命令系统必须同时支持：

- 文字命令输入
- UI 按钮触发
- 快捷键映射
- 管理员命令

### 5.8 Script 与效果系统

V1 不允许从转换后的 LPC 直接执行任意 Python 代码。

内容制作与转换阶段可以把效果适配工作分为三类：

- 配置型 authoring：把纯数据参数映射为 ConditionDefinition。
- 规则型 adapter：引用已注册 RuleDefinition。
- 人工适配 adapter：由开发者实现、登记并测试受控 HandlerDefinition。

这三类只描述 authoring/adapter 路径，不是运行时效果分类，也不得形成平行的叠加、tick、持久化、恢复或 handler 模型。
运行时统一走 `ConditionDefinition revision -> EffectTypeDefinition key/version -> EffectInstance`。

长周期逻辑通过 Scheduler 注册。

短周期战斗状态通过 EffectInstance 生命周期管理。

### 5.9 公共服务边界

引擎公共服务包括：

- ChatService
- CombatService
- MovementService
- QuestService
- ReputationService
- TradeService
- WeatherTimeService
- PathfindingService
- ContentImportService
- ContentPublishService

MUDLib 不应直接依赖底层私有 ORM 细节。

---

## 六、MUDLib 架构

### 6.1 目标

本章中的 MUDLib 更接近“内容包”概念。

当前主线目标不是构建通用 MUDLib 平台，而是承载 XKX100 重构后的世界内容、数值规则、门派体系、任务与事件。

引擎负责提供通信、存储、调度、命令路由与公共服务。

### 6.2 必须区分的两类 MUDLib

本项目中必须明确区分以下两类 MUDLib：

- 原生 MUDLib：面向本项目自研引擎的 Python 内容包。
- 源 LPC MUDLib：用于分析、转换、参考的历史 LPC 代码库。

两者不是同一概念。

原生 MUDLib 需要遵守本项目的加载契约。

源 LPC MUDLib 不要求遵守本项目目录结构。

转换器的职责是把源 LPC MUDLib 归一化为本项目可消费的数据与适配骨架。

### 6.3 基本约束

- 每个原生内容包为独立 Python 包。
- 启动时通过配置指定加载目标原生内容包。
- 当前主线默认只加载 XKX100 原生内容包。
- 运行中不切换内容包。
- 一个实例只加载一个内容包。

### 6.4 XKX100 揭示的现实约束

基于 `D:\My_Projects\xkx100-20201118`，可确认以下事实：

- 根目录包含 `adm/`、`cmds/`、`d/`、`kungfu/`、`feature/`、`inherit/`、`clone/`、`quest/`、`questobj/`、`include/`、`data/`、`u/` 等语义区域。
- 技能、门派 / class、condition 主要位于 `kungfu/skill`、`kungfu/class`、`kungfu/condition`。
- 命令入口与运行时机制紧密耦合，尤其是 `enable|jifa`、`prepare|bei`、`perform`、`exert`。
- `feature/` 与 `inherit/` 提供大量共享行为，不能只看对象文件本身。
- `include/` 中的路径宏与公共定义会直接影响解析结果。
- `u/`、`backup/`、`tmp/`、`www/` 不应被默认视为正式世界内容。

因此，当前转换与引擎约束必须以 XKX100 的实际语义为中心，而不是以泛化目录假设为中心。

### 6.5 XKX100 中的主要语义区域

从 XKX100 看，当前必须重点处理以下语义区域：

| 语义区域 | 常见目录示例 | 作用 | 当前处理方式 |
|:---|:---|:---|:---|
| 系统与安全 | `adm/` | 核心 daemon、权限、安全、配置 | 扫描与引用分析 |
| 玩家命令 | `cmds/usr`、`cmds/std`、`cmds/skill` | 玩法入口、武学指令 | 提炼命令语义并建立 XKX100 玩家命令基线，按类别分批落地 |
| 管理命令 | `cmds/wiz`、`cmds/imm`、`cmds/arch`、`cmds/adm` | 巫师与维护命令 | 作为后台需求参考，不直接兼容 |
| 世界区域 | `d/` | 房间、出口、区域、NPC、场景物件 | 首轮核心转换目标 |
| 技能体系 | `kungfu/skill` | 技能、action、perform、exert | 首轮核心转换目标 |
| 门派 / class | `kungfu/class` | 师承、门派、类 NPC、技能派生 | 首轮核心转换目标 |
| 条件系统 | `kungfu/condition` | 毒、伤、封脉、异常状态 | 首轮核心转换目标 |
| 物品体系 | `clone/`、`questobj/` | 武器、防具、药物、任务物品 | 首轮核心转换目标 |
| 共享行为层 | `feature/`、`inherit/` | 房间/NPC/物品基类、战斗与技能共享逻辑 | 必须分析继承与能力来源 |
| 宏与公共定义 | `include/` | 路径宏、常量、公共头文件 | 必须进入解析范围 |
| 数据与私有区 | `data/`、`backup/`、`u/`、`tmp/` | 存档、缓存、实验内容 | 默认不纳入首轮自动导入 |
| 文档与网页 | `doc/`、`help/`、`www/` | 文档、帮助、网页资源 | 参考输入，不作为核心玩法对象 |

### 6.6 兼容抽象原则

XKX100 的兼容抽象必须遵守以下原则：

- 先还原 XKX100 的实际语义，再决定目标模型。
- 继承链、宏定义、路径宏和 include 文件必须进入分析范围。
- `SKILL_D`、`CLASS_D`、`CONDITION_D` 等路径展开必须被识别。
- `feature/skill.c` 中的 `map_skill` / `prepare_skill` 与 `feature/attack.c` 的动作选择逻辑必须被视为一等语义。
- `valid_enable`、`valid_combine`、`perform_action`、`exert_function` 必须保留为可查询数据或适配入口。
- `replace_program(ROOM)`、坐标字段、地图标签、动态刷怪等都是合法变体。
- 无法归一化的行为必须明确进入人工适配清单。

### 6.7 源内容与目标内容的边界

引擎最终消费的是“XKX100 归一化后的目标内容”，而不是源 LPC 目录本身。

目标内容当前至少要归一化为以下层次：

- 世界层：区域、房间、出口、坐标、地图标签、刷新点。
- 角色层：玩家角色、普通 NPC、门派师父、商贩、守卫、特殊事件 NPC。
- 物品层：武器、防具、药物、书籍、货币、材料、任务物品、容器。
- 武学层：技能、action、`valid_enable`、`valid_combine`、perform、exert、练习 / 学习条件。
- 激发层：基础槽位、当前 `jifa` 映射、徒手 `prepare` 状态、技能组合规则。
- 状态层：condition、毒、伤、封脉、点穴、忙乱。
- 任务层：任务节点、条件、奖励、流程状态。
- 系统层：daemon 引用、命令元数据、未适配行为与导入批次信息。

### 6.8 原生 MUDLib 的目标契约

原生 MUDLib 仍作为本项目引擎的内容包存在。

但当前阶段的契约收缩为“seed + rules + adapters + tests”。

它应满足以下目标契约：

- 有一个 manifest 作为入口。
- 能显式声明版本、依赖、兼容的引擎版本与稳定目标发布流键 `target_content_release`；该键不等于一次性发布批次 ID。
- 能提供初始 seed 导入与离线导出所需元数据。
- 能注册规则函数、Hook 适配与人工适配器。
- 能提供最小自测。
- 不把包内静态文件声明为运行中后台编辑后的事实真源。

### 6.9 推荐目录契约

以下目录是原生 MUDLib 的推荐最小契约，而不是对源 LPC MUDLib 的要求：

- `manifest.py`：名称、版本、依赖、入口声明
- `seed/`：初始导入用的归一化内容种子
- `rules/`：战斗公式、成长规则、掉落规则
- `hooks/`：公开 Hook 适配代码
- `adapters/`：人工适配逻辑与兼容桥接
- `tests/`：MUDLib 自测

如果内部不完全采用该目录，只要 manifest 能完成显式注册，也允许接受。

### 6.10 加载边界

启动流程如下：

1. 读取引擎配置
2. 加载目标 MUDLib manifest
3. 注册规则、Hook 与人工适配器
4. 从 PostgreSQL 读取已发布内容定义
5. 仅当当前 `(instance_id, mudlib_key)` namespace 没有任何 `BlueprintHead` 且没有活动 `ContentReleaseBatch` 时，才允许执行一次受审计的 seed bootstrap
6. 执行启动期校验
7. 启动世界

### 6.11 MUDLib 公开接口原则

MUDLib 只能通过以下方式扩展引擎：

- 提供 seed 导入 / 导出元数据
- 注册规则函数
- 注册 Hook 适配
- 注册人工适配器
- 调用公开服务接口
- 提供测试与校验入口

MUDLib 不应直接：

- 操作私有 ORM 细节
- 越过服务层写跨域状态
- 执行未经登记的任意 Python 代码片段
- 假设运行时是 Evennia 风格对象系统
- 假设包内 seed 文件会天然覆盖数据库中的已发布内容
- 假设源 LPC MUDLib 的目录结构会在目标引擎中原样存在

### 6.12 MUDLib 能力分层

为了避免范围失控，当前阶段能力分为三层：

| 层级 | 内容 | 说明 |
|:---|:---|:---|
| L1 归一化内容层 | 房间、出口、NPC、物品、文本、基础技能、`jifa` / `prepare` 元数据 | 首轮自动转换与后台编辑主战场 |
| L2 规则适配层 | `valid_enable` / `valid_combine` 抽取结果、perform / exert 路由、公式参数 | 以配置为主，必要时辅以规则函数 |
| L3 人工适配层 | 无法自动归一化的技能逻辑、daemon 状态机、特殊任务链 | 必须登记、测试、审计 |

V1 以 L1 落地和 L2 最小闭环为主，不以 L3 大规模覆盖为前提。

### 6.13 发布边界

V1 以冷发布为默认策略。

允许的发布方式：

- 草稿内容写入 PostgreSQL
- 审核后切换发布批次
- 非战斗时触发安全重载
- 文本与非关键数值在明确安全窗口下生效

发布必须满足以下产品结果：

- draft 与 published 内容都是不可变快照；编辑产生新 revision，不改写历史。
- 一次发布切换完整批次；失败时不得暴露部分新内容或留下活动指针漂移。
- parent、Blueprint、Registry 或编译契约变化必须重新评估完整反向依赖闭包。
- 发布、复用和回滚必须绑定可验证的 raw、编译结果与精确依赖身份，不得仅按内容 key 或活动最新版判断。
- 发布预检和结果必须展示显式变更、派生重编译、失败项、批次身份与可回滚证据。

revision 字段、依赖数组、compiler contract、哈希覆盖范围、锁序、复用条件与事务步骤只由 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 冻结。

不要求的能力：

- 活跃战斗实例字段级热同步
- Python 规则代码热替换
- 房间拓扑在线变更后的无缝迁移
- 对已加载活体对象做差分覆盖

代码更新统一通过重启发布。

### 6.14 实例生效规则

V1 不做实例级自动热同步系统。

发布后的生效规则如下：

1. 新进入世界或新生成的对象只使用活动 `ContentReleaseBatch` 完整映射中的 published revisions，并消费由其编译出的 `CompiledBlueprint`。
2. 已加载的静态对象不会因发布或安全重载自动移动 revision；只有显式 apply/migration job 可在安全重载窗口内更新允许字段或协调迁移。
3. 玩家角色、活跃战斗对象、交易对象、任务上下文对象默认不因发布被强制改写；它们继续消费所钉 revision 的 immutable compiled payload、两类 exact dependencies 与兼容 registry catalog，直到显式迁移。
4. 战斗中的变更如涉及关键规则，统一通过冷发布处理。
5. 每次发布至少输出发布批次、显式变更与依赖重编译清单、导入校验结果和失败项。

这意味着后台编辑与发布存在明确生效边界，而不是即时改写所有运行时实例。

---

## 七、XKX100 重构输入与转换器

### 7.1 转换目标

本章中的转换器是 XKX100 现代化重构的辅助工具，而不是项目主产品形态。

当前唯一转换目标为 XKX100。

其他 MUDLib 暂不纳入当前需求范围，不再作为内容模型或转换器设计的约束来源。

XKX100 首轮转换仍不属于首发闭环前置条件。

转换策略为一次性导入 + 人工适配清单，不保持与源 MUDLib 的持续同步。

重构过程中允许“自动抽取 + 人工重建 + 规则适配”并行存在，不要求所有能力都由自动转换器完成。

### 7.2 可复现来源基线

本机路径 `D:\My_Projects\xkx100-20201118` 只用于发现源文件，不构成可复现的权威标识。

当前冻结来源基线为 `xkx100-20201118-sha256-1b101b7a99c60803`。该 `SourceSnapshot` 永不原地改写；未来任何源字节、纳入范围或分类变化都创建新的 snapshot ID、fixture manifest 和兼容包络，旧版本继续可解析和审计。

需求里程碑 M0 必须生成并受版本控制的 `source_snapshot.json`。在该文件产生前，不得宣称战斗或转换结果已与 XKX100 权威基线对齐。

清单至少记录：

- 不可变 `source_snapshot_id`
- 哈希算法与 `tree_sha256`
- 按相对路径排序的文件清单及逐文件 SHA-256
- 纳入与排除规则
- 生成工具版本和生成时间
- 原始编码探测结果

快照身份必须跨平台、可重复并能检测路径分类与原始字节变化。路径规范化、排序、JCS 输入和哈希算法以 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` 为唯一实施权威。

`tree_sha256` 对 `{"files":[{"path":...,"sha256":...}]}` 执行 RFC 8785/JCS，编码为无 BOM UTF-8 后计算 SHA-256 小写十六进制值；每项 sha256 对源文件原始字节计算。

任何纳入路径、分类或原始字节变化都必须产生新的 snapshot ID，不得原地覆盖旧基线。

CI 必须通过受控制品渠道取得带哈希的最小测试夹具，不得依赖开发者机器的绝对路径。夹具可以受版本控制，也可以从有访问控制的制品仓库取得，但验收身份只认冻结哈希。

每个 fixture manifest 必须绑定不可变 `source_snapshot_id`。复合验收只能引用同一 source snapshot 下已冻结的 manifest 名称、版本与聚合哈希，不得把未登记文件临时并入验收输入。

原版行为验收必须建立黄金行为用例。每条用例至少记录前置状态、命令输入、固定随机种子、冻结时钟、期望状态差异、期望事件和允许忽略的展示差异。

差分测试必须在同一随机种子、时钟、时区和初始状态下运行原版夹具与 New_Mud。必做能力的任何非允许差异都必须失败并保持 `blocked / unverified`；只有包络预先声明的纯展示差异或非必做项才能进入有负责人、依据和复核日期的例外清单。

来源记录必须覆盖 XKX100 源码、文本、角色名称与题材内容的技术来源、快照身份和纳入范围。该记录只服务可复现性，不承担内容许可或权利审查。

### 7.2.1 XKX100 对齐兼容包络

任何“与 XKX100 对齐”的结论都必须绑定一个不可变 `compatibility_envelope_id`。包络至少包含：

- `source_snapshot_id`，以及世界、武学 manifest 和复合验收 bundle 的名称、版本与聚合哈希。
- 纳入验收的命令、Action、技能、状态、NPC、物品和世界边界清单。
- golden case 的不可变 id、内容哈希、初始状态、随机种子、时钟与时区。
- 期望状态差异、事件输出、允许忽略的纯展示差异，以及仅适用于非必做项的已批准例外。
- 每项能力的 `verified / blocked / unverified` 状态、负责人和最近复核日期。

只有包络内状态为 `verified` 的行为可以声明为“已对齐”。包络外行为必须写成“未验证”或“未纳入”，不得从局部黄金用例外推全量兼容。

V6 建档时当前复合验收 bundle 仍为 `blocked`：golden case 与 `compatibility_envelope_id` 尚未形成可发布的冻结证据。任何现有合成 fixture、局部测试或源码候选命令都不得把该状态改写为 `verified`。

M1 的战斗对齐范围固定为首发复合验收 bundle 所声明的兼容包络。除非未来包络覆盖并验证 XKX100 全部相关路径，否则文档、发布说明和界面不得使用无范围限定的“战斗完全对齐”。

Public V1 的 Village 起始区必须拆成两个彼此独立的包络：

- `VillageTopologyEnvelope` 固定 `d/village` 起始区的 Room、Exit、外部边界和静态 Entity 身份，不因此声称任何 NPC 或物品交互已对齐。
- `VillageInteractionEnvelope` 逐项列出已有来源证据并通过行为验证的交互；任何未验证的源码交互必须返回明确的 `UnavailableInteraction`，不得静默省略、猜测、近似实现或在界面上暗示可用。

这两个包络都绑定同一不可变 `SourceSnapshot`，但可以独立扩展版本和验证状态。拓扑可用不能作为交互已验证的替代证据。

### 7.3 固定 M1 内部样板夹具

M1-A 的内部样板区域固定为 `xkx100-village-alley-v1`，来源为 `d/village` 的小巷纵切。该两房间 fixture 用于引擎纵切和黄金差分，不等于 Public V1 起始区。

世界 manifest 的 `root_files` 固定为以下五个排序路径：

- `d/village/alley1.c`
- `d/village/alley2.c`
- `d/village/npc/dipi.c`
- `d/village/npc/obj/cloth.c`
- `d/village/npc/punk.c`

同一 manifest 还必须有独立 `dependency_files`，覆盖五个 roots 的完整 transitive include、inherit 与可静态解析的 runtime helper 闭包。依赖不计入五文件 root 白名单、定义计数或自动导入 roots。

每个 root/dependency 项都保存规范 path 与原始字节 SHA-256；两个数组各自 path 唯一且互斥，并分别按规范 path 的 UTF-8 字节升序排序。

`aggregate_sha256` 对 `{"root_files":[{"path":...,"sha256":...}],"dependency_files":[...]}` 执行同一 RFC 8785/JCS + UTF-8 + 小写 SHA-256 算法。移动分类、增删路径或改变字节都必须改变哈希。

任一动态 helper 无法闭合、依赖缺失或路径未进入同一 `source_snapshot_id` 时，转换与黄金验收必须为 `manual_review` 或 `blocked`。

该夹具包含两间双向互通房间、两个可战斗 NPC 和一个装备物品定义。Room `spawn_entries` 以 exact NPC refs 各生成一个 NPC；每个 NPC 的 `item_loadout` 以 exact Item ref 创建并穿戴一个该物品实例。

上述生成链必须使用 `initial_once` 与 `SpawnMaterialization` 幂等键，可覆盖进入世界、查看、移动、生成、基础战斗、死亡掉落与物品加载；服务重启不得重复生成。

入口固定为 `alley1`，最小引导固定为“查看 -> 西北移动 -> 发起战斗 -> 查看战利品”。该引导是测试流程，不新增脱离 XKX100 的任务语义。

`alley1.east` 指向夹具外的 `sroad3`。转换器必须把它记录为外部边界引用；夹具运行时不得开放该出口，也不得静默删除或伪造目标房间。

需求里程碑 M0 必须生成版本化 `xkx100-village-alley-v1` manifest，记录 root/dependency 两类逐文件哈希、聚合哈希、边界引用、期望定义数和运行时生成数。源快照变化时必须创建新 fixture 版本。

定义计数固定为：2 个 `kind=room` Blueprint、2 个独立 `kind=exit` Blueprint、1 条 Room external boundary、2 个 NPC 和 1 个 Item。external boundary 不计为 Exit Blueprint 或可通行 Exit。

初始运行时生成计数固定为：2 个 Room、2 个可通行 Exit、2 个 NPC 和 2 个 Item 实例。两个 Item 实例都来源于同一个 `cloth.c` 定义。

`xkx100-village-alley-v1` 的五个 roots、dependency closure schema、定义计数与运行时计数已经冻结。实际 dependency paths、逐文件哈希与聚合哈希必须由 M0 基于受控 source snapshot 生成；批准后不得原地修改。

技能或 command 文件不得追加为世界 `root_files`。世界 roots 实际依赖的 feature/include/inherit/helper 只能进入 `dependency_files`，不得据此生成额外 fixture 定义；任何依赖变化都必须创建新世界 fixture 版本。

同一 `source_snapshot_id` 下必须另建不可变 `xkx100-skill-combat-v1` manifest。它分别列出受审技能/command/feature roots 与完整 transitive dependency_files，并使用相同的分类数组聚合哈希算法。

两个 manifest 可共享 dependency path，但必须记录同一 SHA-256；共享不等于把 skill root 并入 world roots。任一 manifest 的依赖闭包未冻结，都不得运行复合黄金验收。

复合验收 bundle 必须同时引用世界与武学 manifest 的名称、版本、`source_snapshot_id` 和聚合哈希，不复制或合并两者文件清单。

武学清单与依赖闭包实际冻结前，相关战斗或武学黄金链状态必须为 `manual_review` 或 `blocked`，不得宣称已完全对齐 XKX100。合成 fixture 只能验证引擎机制，不能作为 XKX100 对齐证据。

Public V1 的 `VillageTopologyEnvelope` 以 `d/village` 的完整拓扑为起点：当前已核验输入共 52 个源码文件，其中 30 个为顶层 Room 文件，22 个为 NPC / object 来源文件。最终 Room / Exit / Entity 数必须由冻结转换产物给出，不以源码文件数冒充运行时定义数。Public V1 不得退回只开放 `xkx100-village-alley-v1` 两房间纵切。

### 7.4 XKX100 范围界定

当前转换只覆盖 XKX100 中与首轮纵切直接相关的内容。

优先范围包括：

- `d/` 下的静态区域切片
- `clone/` 与区域内直接刷新的静态 NPC / 物品
- `kungfu/skill`、`kungfu/class`、`kungfu/condition` 中与样板区域有关的定义
- `cmds/skill` 与 `feature/` 中决定 `jifa` / `prepare` / `perform` / `exert` / `attack` 语义的关键机制
- `include/` 中的路径宏与公共常量

以上武学范围只是依赖发现入口。只有进入 `xkx100-skill-combat-v1` roots/dependency closure 并通过哈希冻结的文件，才能用于 XKX100 对齐验收；不得借此扩写世界 `root_files`。

默认不纳入首轮自动导入的范围包括：

- `u/`
- `backup/`
- `tmp/`
- `www/`
- 玩家存档与运行中缓存数据

### 7.5 XKX100 驱动下的转换结论

XKX100 已经说明以下事实：

- 解析器必须理解 `include` 宏入口及 `SKILL_D`、`CLASS_D`、`CONDITION_D` 等路径宏。
- 技能体系不只是一组 skill 文件，还包括 `enable|jifa`、`prepare|bei`、`perform`、`exert` 命令与 `feature/skill.c`、`feature/attack.c` 的共享逻辑。
- `valid_enable` 与 `valid_combine` 是核心语义，不能在转换时丢失。
- 普通攻击动作选择与当前武器、`jifa` 映射、`prepare` 状态直接相关。
- 特殊招式可能依赖多个槽位同时满足特定 `jifa` / `prepare` 前置。
- `feature/`、`inherit/`、`clone/` 中的共享能力必须进入分析范围。

因此，转换器必须先恢复 XKX100 的武学语义骨架，再抽取静态内容切片。

### 7.6 转换总原则

- 以 XKX100 成功落地为第一目标。
- 先服务 XKX100 重构纵切，再考虑导入覆盖率扩张。
- 先转结构与静态数据，再补规则适配骨架。
- `jifa` / `prepare` 语义必须作为一等数据进入模型。
- 复杂逻辑允许生成“人工适配清单”。
- 不追求对 LPC 运行时的完整模拟。
- 在 XKX100 纵切成立前，不为其他 MUDLib 预埋过宽抽象。

### 7.7 转换前发现阶段

在正式抽取内容前，转换器必须先完成发现阶段。

发现阶段至少包括：

1. 根目录、区域目录与样板区域识别。
2. 编码与文件扩展名识别。
3. include 搜索路径与宏入口文件识别。
4. `SKILL_D`、`CLASS_D`、`CONDITION_D` 等路径宏识别。
5. `feature/`、`inherit/`、`clone/` 的继承与共享行为识别。
6. `kungfu/skill`、`kungfu/class`、`kungfu/condition` 命名空间识别。
7. `enable|jifa`、`prepare|bei`、`perform`、`exert` 的调用链识别。
8. 私有目录、动态目录与非正式内容识别。

### 7.8 转换管线

转换流程如下：

1. 源码扫描
2. 根目录、样板区域与语义目录发现
3. include / 宏 / 路径别名抽取
4. 继承关系与 `feature/` 共享行为分析
5. Skill / Class / Condition / Command 语义识别
6. 房间 / NPC / 物品 / 技能 / 条件 / `jifa` 元数据转中间表示
7. 中间表示生成目标数据与人工适配骨架
8. 生成人工适配报告
9. 在 PostgreSQL 中仅创建 immutable draft revisions，完成全量校验、编译并输出相对当前 active batch 的 diff；此步不得发布
10. 由有权限的操作者显式提交原子 `ContentReleaseBatch` 发布
11. 仅在发布成功后，从 active batch 生成新的样板实例并消费对应 `CompiledBlueprint`，再进行样板区域烟雾测试

### 7.9 中间表示设计要求

转换器必须先生成稳定的中间表示，而不是直接把源代码翻成目标运行时对象。

中间表示至少应覆盖以下定义：

- `SourceFile`
- `MacroRef`
- `IncludeRef`
- `InheritRef`
- `RegionDef`
- `RoomDef`
- `ExitDef`
- `NPCDef`
- `ItemDef`
- `SkillDef`
- `SkillActionDef`
- `SkillEnableRule`
- `SkillCombineRule`
- `JifaSlotDef`
- `PerformRef`
- `ExertRef`
- `ConditionDefinitionIR`
- `ClassRef`
- `CommandSemanticRef`
- `UnresolvedBehavior`

其中：

- `RoomDef` 至少应保留 `short`、`long`、规范化 `spawn_entries / external_exit_boundaries`、`item_desc`、区域归属、可选坐标、可选地图标签与映射状态。
- `ExitDef` 是独立 `kind=exit` 的 IR，至少保存 candidate source/target Room refs、direction、aliases、可选 traversal rule 与来源位置；不是 Room 内嵌的第二种出口定义。
- `NPCDef` 至少应保留基础属性、规范化 `skill_loadout / item_loadout`、门派 / class、关键行为来源与每项映射状态。
- `ItemDef` 至少应保留分类、堆叠规则、`container_policy.mode / max_slots / accept_rule_key`、装备位、可用效果、价值、源文件位置与字段映射状态。
- `SkillDef` 至少应保留技能类型、`valid_enable` 结果、可选 `valid_combine` 结果、基础 action、学习 / 练习条件、perform / exert 引用。
- `JifaSlotDef` 至少应保留基础槽位名称、是否要求 `prepare`、是否允许组合。
- `CommandSemanticRef` 至少应保留 `enable|jifa`、`prepare|bei`、`perform`、`exert` 与共享 combat feature 的语义入口。
- `ConditionDefinitionIR` 描述源 LPC condition，至少保留候选 `effect_type_key + effect_type_version`、parameters、来源文件与位置、映射状态及复核依据；运行时挂载结果必须生成 EffectInstance，两者不得混为一张状态表。
- `UnresolvedBehavior` 必须保留来源文件、位置、原因、影响级别与建议处理方式。

### 7.10 自动转换范围

可自动转换的内容包括：

- 房间与出口拓扑
- 静态 NPC / 物品属性
- 可唯一解析的 NPC 技能等级、`jifa` 与 `prepare` 映射；输出为带 BlueprintRef 的 `skill_loadout`
- 可唯一解析的房间 `objects` 与 NPC carry/wear；分别输出为 `spawn_entries` 与 `item_loadout`
- 区域结构
- 技能基础定义
- 技能 action 列表与基础表现文本
- `valid_enable`、可抽取的 `valid_combine`、基础学习条件、基础练习消耗
- `perform` / `exert` 引用关系
- `SKILL_D`、`CLASS_D`、`CONDITION_D` 等路径宏引用
- `item_desc`、`objects`、可选 `coor/x` `coor/y` `coor/z` `map` 等场景字段
- 门派 / class / 师承的基础归属关系
- LPC condition 的来源、parameters 与 `effect_type_key + effect_type_version` 候选；只有精确版本已注册且参数通过该版本的 `payload_schema` 时，才可自动生成 `kind=condition` 的 immutable draft `BlueprintRevision`

转换器只能建议 `effect_type_key + effect_type_version` 映射或标记 `manual_review`，不得从源 condition 另建 stacking、tick、persistence、recovery 或 handler 规则。
最终导入必须解析到精确的已注册 EffectTypeDefinition 版本，否则阻断。转换器不得直接创建 published ConditionDefinition、切换活动发布批次或生成运行时 EffectInstance。

### 7.11 半自动转换范围

需要人工审核的内容包括：

- 无法唯一解析到已注册 EffectTypeDefinition key/version，或 parameters 未通过该精确版本 `payload_schema` 的 condition 映射
- 无法唯一解析 skill key、等级、`jifa` 槽位或 `prepare` 关系的 NPC 技能映射
- 无法唯一解析房间刷点目标、数量，或 NPC 物品目标、数量、穿戴槽的映射

- 战斗公式
- 特殊技能效果
- Daemon 行为
- 复杂任务条件
- 跨文件动态调用
- 数据库存取代码
- `call_out`、`heart_beat`、临时变量驱动的状态机
- 动态房间、迷宫模板、私有房屋
- 与命令系统深度耦合的玩法入口
- 使用 `perform_action`、`exert_function`、自定义 combat helper 的复杂技能链
- 玩家存档与运行中数据的导入

### 7.12 高风险但应被识别的内容

以下内容即使不能首轮自动转换，也必须在扫描结果中被识别和归类：

- `F_MASTER`、`F_VENDOR`、`F_DEALER` 等 NPC 角色能力
- `replace_program(ROOM)` 这类优化写法
- 命令分层与权限级别
- 通过 include 宏隐藏的路径引用
- 以 daemon 持有运行时状态的系统
- 技能子目录中的 perform 文件
- 对多个 `jifa` / `prepare` 槽位有同时要求的特殊前置
- 保存文件、`F_SAVE` 与离线数据结构

### 7.13 不纳入 V1 的能力

- 不做 LPC 代码即时解释执行。
- 不做源 MUDLib 双向同步。
- 不做玩家存档导入。
- 对未纳入当前实现范围的系统，不要求一次性复刻完毕。
- 凡纳入 V1、首发闭环或验收范围的行为，必须与 XKX100 原语义对齐，不得以近似实现替代。
- 不把“可扩展到其他 MUDLib”作为当前验收项。

### 7.14 转换配置项

转换器需支持以下配置：

- XKX100 根目录偏移
- 文本编码策略
- include 搜索路径
- 宏入口文件
- 样板区域白名单
- 导入对象白名单 / 黑名单
- 动态内容目录排除规则
- 私有目录排除规则
- 特殊文件排除规则
- 玩家存档导入策略（V1 固定为不导入）

### 7.15 输出产物

每次转换至少输出：

- 扫描统计报告
- 宏与继承关系报告
- 结构化内容数据
- 中间表示数据
- 人工适配骨架
- 转换日志
- 未适配项清单
- 风险分级报告
- 导入校验报告
- 样板区域烟雾测试报告
- 源快照、两个 fixture manifest 与复合验收 bundle 的校验结果
- 黄金行为差分测试报告

### 7.16 XKX100 最小验收标准

XKX100 的最小验收标准定义如下。

达到以下条件，即视为“首轮转换闭环成立”：

1. 能完成源码扫描并输出基础统计报告。
2. 能识别 mudlib 根目录、include 搜索路径、`SKILL_D` / `CLASS_D` / `CONDITION_D` 等路径宏与命名空间。
3. 能输出继承关系、宏引用、`feature/skill.c`、`feature/attack.c` 与 `cmds/skill/*.c` 的关键语义引用报告。
4. 能把房间、出口、静态 NPC、静态物品、基础技能定义转换为结构化中间表示。
5. 中间表示中能把对象刷点、NPC 技能与 carry/wear 映射归一化为带目标 kind 的 BlueprintRef，并保留房间描述、出口、可选坐标 / 地图标签、Item `container_policy`、`valid_enable`、可选 `valid_combine`、perform / exert 引用。
6. 能校验 `source_snapshot.json`、世界 manifest、武学 manifest 与复合验收 bundle；source snapshot ID 或任一哈希不一致时拒绝运行。
7. 能把固定样板夹具导入目标数据库，并显式报告 `alley1.east` 外部边界。
8. 进入游戏后，玩家可按固定引导执行查看、移动、基础战斗与战利品查看。
9. 武学 manifest 冻结后，至少一门纳入闭包的技能可以完成“已学 -> `jifa` -> `prepare`（如适用）-> `perform` / `exert` 校验”的端到端链路；冻结前该项必须为 `manual_review` 或 `blocked`。
10. 固定随机种子与时钟后，复合验收 bundle 纳入范围的黄金行为差分测试必须通过。
11. 所有未支持逻辑必须进入未适配清单。
12. 不允许静默跳过关键对象而不留痕迹。

首条 `GoldenSkillChain` 的来源检查目标冻结为：

- `bahuang-gong` 的 force / exert 路径，候选命令为 `exert powerup`。
- `baihua-cuoquan` 的 `jifa` / `prepare` / `perform` 路径，候选命令为 `perform cuo`。
- `benlei-shou` 与双准备组合另建后续 golden chain，不得混入首条用例扩大通过范围。

以上命令名仍是待源码逐行确认的候选入口。精确参数、初始 Actor 状态、前置条件、随机输入和期望差异必须从冻结来源检查生成；在对应 golden case 与 `compatibility_envelope_id` 实际存在前，状态保持 `blocked`，不得凭名称推断语义。日常 Public Character 的技能学习和成长状态不得复用或继承确定性 golden-test Actor 的预置状态。

Item 的容器能力、容量或接受规则无法唯一解析时必须进入 `manual_review`，不得猜测 `container_policy` 或输出可导入 draft。

`manual_review` 与 `blocked` 只是中间状态，不计为通过。两个 manifest 未冻结或复合验收 bundle 的黄金差分未通过时，不得认定首轮转换闭环成立。

以下内容不属于首轮最小验收范围：

- 未纳入本次样板区域与首轮转换范围的战斗分支，不以自动化验收覆盖率为准
- 原任务链完全可玩
- 原 Daemon 行为完全复现
- 原数值平衡完全一致
- 全量世界一次性无人工接入导入
- 玩家存档导入
- 所有玩家命令的逐条兼容
- 其他 MUDLib 的兼容能力

已纳入复合验收 bundle 的战斗公式、状态判定与指令语义必须与 XKX100 一致。合成 fixture 的测试结果只能证明引擎机制可用，不能替代原版黄金差分或证明 XKX100 对齐。

---

## 八、账号、身份与认证

### 8.1 术语约束

根目录 `CONTEXT.md` 是项目领域概念名称与紧凑定义的词汇权威；本章冻结身份产品语义，V6 其他章节冻结各自产品范围和结果。词汇定义与产品语义粒度不同；发生实质产品冲突时以本章及 V6 其他已冻结约束为准，并同步修正 `CONTEXT.md`。`UBIQUITOUS_LANGUAGE.md` 是非权威工程术语索引，只索引未进入领域词汇表的工程名称、来源名称和常见歧义，不建立第三份定义或权威。

以下列表只导航本章使用的身份领域概念；其规范名称与紧凑定义仍只在 `CONTEXT.md` 维护，本章负责冻结相关产品语义，不建立第二份词汇定义：

当前冻结的是这些术语所表达的边界与职责，不要求继续沿用旧术语表中的命名风格；后续若改用更合适的中文或其他名称，必须保持本章定义的语义不变。

- User
- AuthIdentity
- GameAccount
- PlatformRole
- CharacterOwnership
- AuthSession
- Presence
- VerifiedContactMethod
- VerificationChallenge
- RecoveryCode（已退役历史概念）

### 8.2 身份模型

| 术语 | 作用 | 是否首发必做 |
|:---|:---|:---|
| User | 登录与后台授权主体 | 是 |
| AuthIdentity | 外部登录身份绑定 | 否 |
| GameAccount | 玩家游戏域账号 | 是 |
| PlatformRole | 后台角色权限 | 是 |
| CharacterOwnership | 角色归属关系 | 是 |
| AuthSession | 登录后认证会话 | 是 |
| Presence | 控角中的在线状态 | 是 |
| VerifiedContactMethod | User 已证明控制的恢复与安全通知渠道；不是登录名 | 是，首期仅 email |
| VerificationChallenge | 按用途、渠道、目标和适用 User 隔离的短期单次证明 | 是，首期用于注册与密码重置 |

在每个游戏实例内，一个 `User` 永久映射到一个 `GameAccount`。`CharacterOwnership` 仍作为独立关系建模，以便未来扩展多个 Character，但该扩展不能改变现有 `User -> GameAccount` 身份边界，也不能把同一 User 拆成多个游戏账号。

### 8.3 长期目标

长期目标仍包括以下能力：

- 支持以已验证手机号作为注册与恢复渠道，但手机号仍不是登录名
- 支持微信小程序授权登录
- 同一 User 可绑定多种登录身份
- 支持受重新认证、双渠道证明或高风险等待期约束的联系方式换绑
- 支持与密码重置用途分离的账号重新启用 challenge
- 首发后可放宽一账号多角色，具体上限由产品策略另行冻结；该变化只影响 `CharacterOwnership`，不改变每实例一 User 一 GameAccount。

### 8.4 首发闭环边界

以下能力移出首发闭环：

- 短信验证码
- 手机号注册正式接入
- 微信授权登录

首发必须提供已验证邮箱、独立账号名和密码组成的自助注册。邮箱只用于证明可用联系方式、账号恢复和安全通知，不是登录名、无密码登录凭据或 MFA。未来短信可以作为另一个验证与恢复渠道，但本轮只启用 `channel=email`。Public V1 通过 `PublicV1Gate` 后默认开放自助注册；运营可审计地将实例置于 `open`、`paused` 或 `invite_only` 模式，模式变化必须有操作者、原因和生效时间。

注册发码阶段不得创建 User 或预留账号名。最终注册必须在一个事务中消费 active registration `VerificationChallenge`，创建 `User`、对应 `GameAccount` 与唯一 verified email `VerifiedContactMethod`，但不得创建 `AuthSession`、RefreshTokenFamily、token、Character 或 Presence。客户端随后使用普通 login 端点以账号名和密码登录。

账号名采用大小写不敏感的规范化唯一键，首发只允许 3-32 位 ASCII 小写字母、数字和下划线。角色显示名属于 Character，不得与登录账号名混用。

注册必须使用 Django 密码校验、Origin 校验、限流和稳定错误码。重复账号名、不可接受输入和策略拒绝不得泄露内部用户记录。

RecoveryCode 已退役：不得继续签发、展示或消费，既有记录只作为撤销后的历史事实。旧 `/api/v1/auth/recover` 与 `/api/v1/auth/recovery-code/rotate` 在兼容期统一返回 HTTP `410` 与错误码 `RECOVERY_CODE_RETIRED`，并在 Public V1 前删除。

忘记密码时，用户通过 verified email 接收短期 `VerificationChallenge` 并设置新密码；成功事务必须消费 challenge、撤销该 User 跨实例的全部 AuthSession、RefreshTokenFamily 与 active credential，并取消适用的未完成恢复任务。旧 access/refresh 凭据在事务提交后立即失效，用户必须重新登录；密码重置不得改变 GameAccount lifecycle、自动恢复 Presence 或取得 Character 控制权。

验证码 request 对格式有效的未知、占用、不可恢复或不可达联系方式返回相同 `202` 外形，不暴露 challenge、User、投递或 provider 状态。request 必须使用 `Idempotency-Key`，并通过 PostgreSQL 持久化的联系方式、IP、匿名设备合并限流；普通账号名/密码登录不依赖邮件 provider。六位验证码从成功激活起十分钟有效，最多五次校验，手动重发冷却为 60 秒。

完整联系方式只允许应用层密文保存，精确查询与唯一性使用独立 keyed lookup digest；Django `User.email` 保持为空且不是回退来源。验证码只长期保存带用途上下文的摘要，临时完整目标和验证码只存在于加密 outbox payload，terminal 后擦除。HTTP 请求不得同步连接 SMTP；持久 outbox worker 负责投递与有界重试。

每个 User 每种渠道最多一个 active 或 unreachable `VerifiedContactMethod`；同一规范化联系方式最多属于一个未永久退休 User。失去一个渠道不会自动解绑或转移所有权；同时失去密码和全部已验证渠道时，人工支持只能冻结账号并保全审计，不能依据游戏资料重新分配所有权。联系方式换绑、账号关闭与重新启用由后续独立规格实现；`cooling_off -> active` 必须使用用途独立的 account-reopen challenge，不能复用 password-reset challenge。

本认证基线修订的稳定需求标识为 `AUTH-005`，实施单元称为 `Engine Stage E1 / Auth Baseline Amendment`，必须先于 Character Slice 2 完成。Issue #9 与原 E1 / Slice 1 仍是当时 RecoveryCode 实现和零隐式登录的历史证据；该历史不授权继续把 RecoveryCode 当作现行产品凭据。

首发与 Public V1 均不提供玩家自助改名、删除或重建 Character。GM 改名 / 重置必须审计，测试环境允许显式 reset。账号关闭时只立即撤销控制权并进入可恢复的 `cooling_off`；只有冷静期届满、GameAccount 进入 `retired` 后，Character 才成为 `RetiredCharacter`，其名称永不自动复用。退休时对相关 User 数据执行匿名化 / 禁用，但不硬删除稳定 ID 和历史关系。

首发登录固定为账号名和密码；邮箱和未来手机号不作为登录名、passwordless 或 MFA。

登录成功后创建 active AuthSession，并签发短期 JWT Access Token 与首代 Refresh Token。refresh 只允许为仍处于 `active` 的同一 AuthSession
轮换 refresh credential 并签发新 access token；不得创建新 AuthSession，也不得复活 `revoked / expired / logged_out` 会话。
开发与内测环境不得使用绕过该流程的简化认证替代验收。

每个 AuthSession 在登录事务中创建且终身只关联一个 RefreshTokenFamily。轮换只追加 credential generation，不替换 family；family 身份行不得先删除再为同一 AuthSession 重建，终态 family 不得恢复为 active。

H5 logout 以 refresh Cookie 和内存中仍可用的 access token 作为独立定位凭据，撤销两者能够识别的全部 AuthSession 和 ticket、终止对应 active/grace PresenceSnapshot 租约，并关闭运行时 Presence。两者都无法识别会话时仍统一返回 `204` 并清 Cookie，但该结果只表示客户端清理完成，不得伪称已撤销无法定位的服务端会话。

AuthIdentity、手机号和微信身份绑定均为首发后能力。

### 8.5 认证策略

玩家侧注册和密码重置均不签发 token。登录成功后采用 JWT Access Token + 轮换 Refresh Token；每个受保护 HTTP/WebSocket 入口必须确认 token 仍解析到 `active` AuthSession 及可用 User/GameAccount，轮换前也必须重新确认 AuthSession 仍为 `active`。

Refresh Token 仅可在 REST refresh endpoint 中作为轮换凭据，或由 REST logout endpoint 从受保护 Cookie 读取作为 AuthSession locator。它不得进入 WebSocket payload 或 Authorization header。

logout 还可以使用内存中的 access token Bearer 作为独立 locator；这不改变 Refresh Token 的 Cookie-only 边界。

管理后台采用 Django Session / Cookie。

两套认证边界必须分离。

### 8.6 首发角色与多端约束

- 首发每个 GameAccount 最多拥有一个 Character。
- CharacterOwnership 必须建模为可扩展关系，不把永久一对一写死在领域结构中。
- 首发上限由应用服务和数据库约束共同保证，未来放宽时必须提供显式迁移。
- 同一 GameAccount 跨所有 AuthSession、ConnectionSession 与设备，同时最多有一个处于 `active` 或 `grace_disconnected` 的 PresenceSnapshot 租约；运行时 Presence 只在实际绑定连接并控角时存在。
- 普通第二控角请求默认以 `CHARACTER_OCCUPIED` 拒绝，`presence.enter` 不得隐式升级为接管。
- 只有显式 `presence.takeover` 携带确认且通过策略授权，才可在同一事务终止旧 PresenceSnapshot 租约、撤销旧 ticket、建立新租约与 ticket，并保存终结结果和通知 outbox；旧运行时 Presence 在提交后失权并关闭。
- 事务内任一步失败必须整体回滚，不得留下两个可恢复租约、半关闭旧租约或无终结结果的新请求。
- 事务提交后才通知旧连接；通知失败不得回滚已提交接管，旧端须在后续请求校验或状态同步时失去控制权。

### 8.7 安全要求

- 密码哈希采用 Django 标准密码哈希体系
- 完整邮箱、手机号等敏感字段应用层加密存储，精确查询使用独立 keyed digest
- 注册、验证码、密码重置与登录接口使用彼此适用的持久化限流
- 验证消息通过持久 outbox 异步投递，公开 request 使用非枚举响应
- 支持异地登录检测
- 关键账号操作进入审计日志

### 8.8 CharacterCreationProfile 与 CharacterDisplayName

Character 创建使用版本化 `CharacterCreationProfile`。Public V1 输入只包含 `CharacterDisplayName` 与仅用于展示的性别 / 代词选择；性别不得改变属性、成长、资格、门派或武学能力。初始状态固定并可由来源材料解释，不采用不可复现随机值。

`CharacterDisplayName` 在实例内唯一，按 NFKC 规范化后比较；长度为 2-12 个可见字符。允许 CJK、Latin、数字和中点；拒绝空白、控制字符、双向控制符、emoji、纯数字名称和保留词。名称验证必须返回稳定的策略错误，不泄露已存在名称的额外信息。没有 Public V1 自助 rename / delete / rebuild；RetiredCharacter 的名称不自动回收。

---

## 九、客户端与多端接入

### 9.1 支持平台

- 首发支持：PC 浏览器、移动端浏览器
- 后续预留：微信小程序

### 9.2 一致性原则

首发 Web 双端保持核心流程一致。

PC 与移动端浏览器不强求完全一致的交互细节。

PC 端允许增强键盘输入与窗口布局。

移动端浏览器必须保证主要流程在窄屏和触控条件下可用。

微信小程序后续接入时允许为平台限制做轻量调整。

### 9.2.1 首发浏览器与交互验收矩阵

每个发布候选必须记录实际测试的浏览器和操作系统精确版本。最低支持范围如下：

- 桌面端：Chrome、Edge、Firefox 最近两个稳定主版本，以及 macOS Safari 最近两个稳定主版本。
- 移动端：iOS 16 及以上 Safari，Android 10 及以上 Chrome 最近两个稳定主版本。
- 视口：至少覆盖 360x640、768x1024、1280x720 和 1920x1080 CSS 像素。
- 桌面端在 200% 页面缩放下仍可完成注册、登录、移动、聊天、战斗和物品主流程。
- 中文输入法 composition 期间不得误提交命令；候选文本确认后才可响应 Enter 或发送动作。
- 主要触控目标最小为 44x44 CSS 像素，键盘焦点可见，核心文本与背景达到 WCAG 2.1 AA 对比度。

低于支持矩阵的环境可以展示兼容性提示，但不得计入首发验收。矩阵升级属于普通测试基线更新；降低范围必须走有意需求变更。

M0 批准的是基于官方版本信息冻结的精确目标组合，不等同于浏览器测试已经执行。机器合同必须分别记录 `target_versions` 与 `tested_versions`；后者只能由发布候选的实际 PC/移动 H5 测试证据填写，且必须是已批准目标的覆盖结果。

### 9.3 主交互模型

客户端主界面至少包含以下区域：

- 场景描述区
- 事件流区
- 命令输入区
- 快捷操作区
- 状态区
- 聊天区

### 9.4 客户端功能面板

| 面板 | 主要内容 | 首发要求 |
|:---|:---|:---|
| 主视窗 | 场景描述、事件流、输入区 | 必做 |
| 移动控制 | 方向按钮、上下层切换、快捷移动 | 必做 |
| 角色状态 | 气血、内力、精力、状态效果 | 必做 |
| 背包面板 | 分类筛选、使用、丢弃、查看 | 必做 |
| 装备面板 | 装备槽位、属性对比 | 基础版必做 |
| 武学面板 | 已学武学、激发状态、准备状态、资源状态 | 基础版必做 |
| 地图面板 | 当前区域、出口、简图 | 推荐 |
| 任务面板 | 主线、支线、当前目标 | 基础版推荐 |
| 社交面板 | 私聊、频道、组织关系摘要 | 推荐 |
| 设置面板 | 字体、主题、提示与音效开关 | 推荐 |

首发武学面板至少必须显示当前 `jifa` / `prepare` 状态，并提供对应设置与取消操作；面板控件和文本入口必须复用同一 Action 服务。

### 9.5 PC 端增强能力

- 命令历史
- 自动补全
- 快捷键
- 面板布局优化
- 更强的文本可读性配置

### 9.6 微信小程序预留约束

首发只要求保留兼容边界；实际小程序客户端与微信认证必须在需求里程碑 M6 按第 15.7 节交付。

- 避免依赖复杂悬浮交互
- 避免依赖连续键盘操作
- 网络波动下优先保证文本事件流可恢复
- 避免把复杂 GM 工具直接塞到小程序端

### 9.7 表现层扩展

V1 以纯文字为主。

保留以下扩展接口：

- 图标
- 图片插槽
- 音效开关
- 主题配置

---

## 十、游戏内容设计

本章定义的是 XKX100 当前完整内容设定基线。

它不等于首发必须一次做完的实现范围。

首发阶段范围见第十一章。第十章维护未来兼容包络的候选内容基线，第十一章只定义实现顺序与纵切范围；任何阶段的对齐声明仍必须遵守第 7.2.1 节，不能把本章目录本身当成已验证证据。

凡是超出 XKX100 当前内容设定的新增想法，统一后置为“后续可选增强”。

### 10.0 XKX100 内容规模基线

当前内容规模基线按 XKX100 本地源码扫描与现状理解，至少包括以下量级口径：

- 约 `31` 个门派 / class 一级目录
- 约 `362` 个唯一武功技能 ID
- `5500+` 个 `inherit ROOM` 的房间源码文件

这里的量级口径用于约束未来覆盖规划不能被缩减成少量示例内容，不构成已验证的对齐范围或验收证据。

其中房间源码文件包含模板、变体与可进一步去重的房间定义；精确可玩房间数由后续扫描与归一化报告给出。

首发阶段仍然只实现最小可玩纵切；后续扩展包络与覆盖规划必须以这一规模级别为参考，并逐项冻结、验证后才能扩大对齐声明。

### 10.1 角色系统

#### 10.1.1 角色状态与基础属性

当前角色属性以 XKX100 现有状态体系为基线。

| 属性类别 | 典型字段 | 当前作用 |
|:---|:---|:---|
| 战斗与精神状态 | `qi`、`eff_qi`、`max_qi`、`jing`、`eff_jing`、`max_jing`、`neili`、`max_neili` | 战斗、生存、学习与运功的核心资源 |
| 辅助资源 | `jingli`、`max_jingli`、`tili`、`max_tili`、`food`、`water` | 精力、体力、饮食与日常恢复相关资源 |
| 成长资源 | `combat_exp`、`potential`、`score` | 推动角色成长、技能提升与任务进度 |
| 角色信息 | `age`、`per`、`kar` | 体现年龄、容貌与福缘等个人特征 |
| 身份关系 | 门派、师承、江湖身份 | 决定可学内容、任务入口与 NPC 互动 |

此外，部分玩法还会使用条件性资源或状态条，例如 `nuqi` / `max_nuqi`；其出现条件与效果以 XKX100 现有实现为准。

#### 10.1.2 成长基线

当前成长基线与 XKX100 保持一致，主要围绕经验、潜能、江湖阅历、技能等级与门派身份推进。

| 成长项 | 作用 | 典型来源 |
|:---|:---|:---|
| 实战经验 | 角色成长与部分门槛 | 战斗、任务 |
| 潜能 | 转化为技能提升资源 | 任务、历练 |
| 江湖阅历 | 记录闯荡进程 | 任务、事件 |
| 技能等级 | 决定武功表现与学习上限 | `xue`、`du`、`lian`、`yanjiu`、实战 |
| 门派身份 | 决定武功与剧情入口 | 拜师、门派任务 |

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 等级化成长
- 境界分层
- 自创武学
- 传承系统

### 10.2 内力与运功系统

当前基线与 XKX100 一致，围绕内力、精气、精力、体力、基础内功与运功指令组织。

| 子系统 | 基线内容 | 当前作用 |
|:---|:---|:---|
| 内力 | `neili`、`max_neili` | 运功、绝招与战斗消耗 |
| 精气 | `jing`、`eff_jing`、`max_jing` | 学习、研究、疗伤与精神状态相关消耗 |
| 精力 | `jingli`、`max_jingli` | 部分内功、法术与恢复相关消耗 |
| 体力 | `tili`、`max_tili` | 日常行动与部分恢复语义相关资源 |
| 内功技能 | `force` 体系与 `jifa force` | 决定当前内功功能与恢复 / 护体能力 |
| 运功指令 | `yun`、`exert` | 疗伤、恢复、护体、特殊功能 |
| 恢复行为 | `dazuo`、`tuna` | 非战斗中的恢复与修炼 |

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 经脉细化
- 丹田 / 内力属性标签
- 走火入魔风险系统

### 10.3 武学系统

#### 10.3.1 武学数据模型

| 类型层 | 典型类型 | 说明 |
|:---|:---|:---|
| 内修与防御 | `force`、`dodge`、`parry` | 内功、轻功、招架 |
| 兵器武学 | `sword`、`blade`、`staff`、`club`、`stick`、`whip`、`spear`、`axe`、`hammer`、`dagger`、`hook` | 各类兵器技能 |
| 徒手武学 | `cuff`、`strike`、`hand`、`claw`、`finger`、`leg`、`unarmed` | 徒手技艺 |
| 特殊武学 | `throwing`、`array`、`poison`、`magic` | 暗器、阵法、毒技、法术 |

具体武功名称、门派归属、绝学获取条件与招式集合以 XKX100 原有内容为准。

#### 10.3.2 激发与准备机制

V5 武学系统采用 XKX100 式的 `jifa` 机制。

核心规则如下：

- Actor（Character/NPC）维护“已学技能”“激发映射”“准备映射”三层状态。
- `jifa` 的本质是把一个具体技能绑定到基础用途槽位，而不是简单选择当前武功。
- 基础用途槽位至少包括 `force`、`dodge`、`parry`、武器类型槽位与徒手类型槽位。
- 一个具体技能能否占用某个槽位，由该技能的 `valid_enable` 语义决定。
- 徒手系技能在 `jifa` 之后还需要进入 `prepare` 才能作为当前准备武学参与部分普通攻击与 `perform` 判定。
- `prepare` 在 V1 采用 XKX100 的双准备上限，最多同时准备两门可组合的徒手技能。
- 两门徒手技能能否同时准备，由 `valid_combine` 语义决定。
- 每条准备关系必须保存其基础 `enable_slot`，并引用同 actor、同技能的 `jifa` 绑定；数字顺序不能替代用途槽位。
- 双准备是有序关系：`combine_order=1` 是 primary，2 是 combo，只调用 primary 的 exact `valid_combine` 规则并把 combo 作为参数。
- 一次指定两门时保留输入顺序；从单准备增量加入新技能时，新技能成为 primary，原技能成为 combo。结构化客户端与文本命令必须复用同一 Action 服务。
- combine order 集合只允许 `[] / {1} / {1,2}`；取消 primary 且保留 combo 时，必须在同一事务把剩余技能压缩为 order 1。
- 普通攻击动作选择、招架 / 闪避取技、`perform`、`exert` 与部分特殊前置条件，都必须读取当前 `jifa` / `prepare` 状态。
- 特殊招式允许要求多个槽位同时满足特定激发条件，例如“手法已激发且已准备，同时招架槽位也激发为同门武学”。

#### 10.3.3 学习与使用机制

当前学习与使用机制以 XKX100 原版流程为准：

- `xue`：向师父学习
- `du`：读书自学
- `lian`：练习武功
- `yanjiu`：研究武功
- 实战提升：战斗中自动提升
- `yong`：使用绝招
- `yun` / `exert`：运功与内功功能
- `jiali`：调整加力

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 玩家自创武学系统
- 非原版的天赋树式成长

### 10.4 XKX100 战斗系统

#### 10.4.1 核心结论

当前需求以 XKX100 原版战斗机制为唯一行为基线，但对齐结论只能覆盖第 7.2.1 节定义并验证的兼容包络。

只要某条战斗路径被纳入实现、首发闭环或验收范围，其公式、状态判定、节拍语义、`busy` / `condition` 处理与指令限制都必须与 XKX100 一致。

凡是与 XKX100 不一致的额外战斗语义，本版本一律不引入，包括但不限于：

- 独立技能 cooldown
- 默认公共冷却
- 自定义实时-lite 动作锁模型
- 非 XKX100 的战斗模式切换
- 为前端交互额外发明的技能轮盘或技能槽语义

#### 10.4.2 战斗方式与指令

玩家侧战斗相关命令、别名、限制与源码语义以 XKX100 现有实现为准。

本文不再另外定义一套简化版战斗命令集。

其中，`perform` 与 `yong` 按 XKX100 现有实现视为同一路径命令入口。

当前已确认的核心命令如下：

| 指令 / 方式 | 作用 |
|:---|:---|
| `kill` | 生死战 |
| `fight` | 切磋 |
| `hit` | 直接攻击 |
| `halt` | 停止战斗 |
| `guard` | 守护 |
| `touxi` | 偷袭 |
| `ansuan` | 暗算 |
| `jifa` / `prepare` | 配置当前武功状态 |
| `yong` | 使用绝招 |
| `yun` / `exert` / `jiali` | 运功、内功功能与加力控制 |

Public V1 只开放互相确认、非致命的 `Sparring`。Character 目标的 involuntary 或致命 `kill` / `hit` 必须拒绝；完整 PvP 另建独立需求和兼容包络，不得从 NPC 战斗推导为已支持。

玩家失败采用 `SafeDefeat`：不永久死亡、不丢失玩家 Item、不回退不可逆成长，并返回安全且可继续游玩的状态。NPC 的死亡、掉落和生命周期仍由服务器权威持久化，不能用玩家 SafeDefeat 语义复活 NPC。

#### 10.4.3 状态、伤害与判定

当前战斗判定必须与 XKX100 现有状态体系保持一致，至少覆盖：

- 武器装备状态
- `jifa` / `prepare` 状态
- 当前内力、气血、精力与有效气血
- `busy`、点穴、中毒、流血、内伤等状态
- 门派武功、绝招与内功运用前置
- 比武场景下的 `perform` 限制等原版特殊规则

伤害类型至少包括：

| 类型 | 说明 |
|:---|:---|
| 割伤 | 利器切割伤害 |
| 刺伤 | 穿刺伤害 |
| 瘀伤 | 钝器击打伤害 |
| 内伤 | 内力造成的内伤 |
| 抓伤 | 爪类伤害 |

本版本不新增脱离 XKX100 语义的玩法效果分类。技术注册仍统一使用 ConditionDefinition 通过
`effect_type_key + effect_type_version` 精确引用已注册 EffectTypeDefinition，并由该精确版本唯一决定负载、叠加、tick、持久化、恢复与 handler。

未在本文逐条列尽的战斗细节，以 XKX100 现有命令与源码语义为准。

#### 10.4.4 后续可选增强

以下内容不属于当前 XKX100 战斗基线，保留为后续可选增强：

- 战斗回放与观战界面
- 额外的技能标签体系
- 现代化战斗 UI 辅助层
- 在不破坏原版机制前提下的数值可视化

### 10.5 物品与装备系统

| 物品类型 | 当前基线 | 说明 |
|:---|:---|:---|
| 武器 | 剑、刀、杖、棍、棒、鞭、枪、斧、锤、匕首、钩等 | 战斗装备 |
| 防具 | 各类穿戴装备 | 防御与生存 |
| 书籍 | 秘籍、读本 | 学习武功与读书识字 |
| 药品 | 疗伤、解毒、恢复类道具 | 战斗与生存消耗 |
| 食物饮品 | 吃喝恢复类物品 | 生存需求 |
| 货币 | 黄金、白银、铜钱、银票 | 交易与携带 |
| 珠宝首饰 | 玉佩、手镯、戒指、夜明珠等 | 装饰或特殊用途 |
| 任务物品 | 特定任务道具 | 任务推进 |

内容定义的 `source_ref` 从首版起必填，用于转换、黄金差分与审计溯源；它不等于玩家可见的物品实例获取来源履历。

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 耐久度
- 绑定规则
- 品质与稀有度
- 玩家可见的物品实例获取来源履历

Public V1 的 Item 生命周期规则：

- 静态 Entity 只物化一次；显式允许刷新的 hostile NPC 在有界持久延迟后创建新的 Entity，死亡 Entity 永不复活。
- NPC 掉落先创建 30 秒 `LootClaim`；期满后公开。拾取必须原子竞争且只有一个赢家；NPC loot 约 15 分钟后进入 `ItemRetirement`。
- 玩家普通丢弃 Item 默认保留 60 分钟并提前告警；背包、装备和受保护 Item 不自动清理。
- 清理表示 `ItemRetirement`，不是硬删除；身份、来源和审计关系继续可读。

### 10.6 地图与移动系统

#### 10.6.1 房间图原则

当前地图与移动以 XKX100 的房间制世界为基线。

玩家主要通过 `look`、方向移动与 `map` 等方式进行探索。

#### 10.6.2 区域结构

地图内容至少应覆盖以下语义层次：

| 类型 | 示例 |
|:---|:---|
| 主要城市 | 扬州、长安等主城 |
| 门派驻地 | 少林、武当、峨眉、丐帮等门派区域 |
| 特殊区域 | 密室、岛屿、特殊任务地点 |
| 其他重要区域 | 山林、水域、客栈、官道等公共区域 |

#### 10.6.3 后续可选增强

以下内容不属于当前 XKX100 非技术基线，作为后续可选增强：

- 显式 Z 轴玩法层
- 通用自动寻路系统
- 大地图流式加载与导航 UI

### 10.7 门派、师徒、声望、组织与社交系统

当前内容基线与 XKX100 保持一致，至少覆盖：

- 门派体系
- 正邪 / 声望类状态
- 师门忠诚与相关关系状态
- 拜师 / 收徒 / 开除 / 背叛师门
- 玩家帮会 / 组织系统
- 帮会创建、入会、升降职、驱逐、让位与帮会频道
- 组队
- 结拜
- 婚姻
- 跟随与询问

门派、武功、场景、身份关系以及 `shen` 等关系状态以 XKX100 原有设定与源码语义为准。

玩家自创帮会 / 组织属于 XKX100 既有内容，不再归类为新增增强。

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 非原版的阵营外交扩展玩法

### 10.8 任务与世界事件

当前任务内容以 XKX100 现有任务体系为基线，至少包括：

| 类型 | 示例 |
|:---|:---|
| 日常 / 收集任务 | 韦小宝任务、动态任务 |
| 讨伐任务 | 锄奸、斩杀叛徒、捉捕奸细 |
| 组织任务 | 一品堂任务、门派任务 |
| 护送 / 寻找任务 | 护送人质、寻找秘籍 |
| 追杀 / 江湖事件 | 追杀类任务与相关事件 |

当前任务体系应保留 XKX100 原版的任务等级框架。

任务发放、难度控制、奖励门槛与阶段推进，不应脱离原版任务等级语义另起一套等级化模型。

具体等级划分与经验阈值以 XKX100 当前任务数据为准。

复杂因果分支、随机奇遇系统与大规模世界演化不属于当前 XKX100 基线，作为后续可选增强。

### 10.9 聊天、查询与玩家辅助指令系统

当前基线与 XKX100 玩家侧指令系统保持一致。

玩家侧非战斗指令至少覆盖以下类别：

- 基础互动：`look`、方向移动、`say`、`tell`、`whisper`、`reply`
- 物品操作：`get`、`drop`、`put`、`give`、`wield`、`unwield`、`wear`、`remove`、`open`、`close`
- 生存行为：`eat` / `chi`、`drink` / `he`、`sleep`
- 师徒与关系：`bai`、`shou`、`kaichu`、`bei`、`follow`、`follow none`、`team`、`jiebai`、`marry` / `unmarry`、`ask`
- 交易：`buy`、`sell`、`list`、`baitan`、`redeem`
- 查询与信息：`who`、`score`、`hp`、`i` / `inventory`、`cha` / `skills`、`help`、`finger`、`time`、`map`
- 频道与收听控制：至少包括 `chat`、`rumor`、`party`、`xkx`、`sing`、`snow`、`es` 等玩家频道，以及 `tune`
- 系统设置：`set`、`unset`、`alias`、`nick`、`title`、`describe`、`passwd`
- 玩家自管理：`quit` / `exit`、`save`、`suicide`

未在本文逐条列尽的玩家常用非战斗命令，其可用性、限制与语义以 XKX100 现有实现为准。

富文本聊天、跨端通知系统与脱离原版语义的频道增强不属于当前 XKX100 基线，作为后续可选增强。

### 10.10 经济系统

Public V1 经济只覆盖白名单 NPC 的买卖、基础货币、掉落处置和消耗品。银行、当铺、玩家交易、摆摊、拍卖、动态价格和真实货币经济均后置；不可由已有命令名暗示为可用。

M2-M3 才恢复 XKX100 的完整经济候选基线：

- NPC 商店、当铺、银行、摆摊、拍卖
- 掉落与消耗回收
- 多级货币体系

货币以 XKX100 现有体系为准：

| 货币 | 兑换关系 |
|:---|:---|
| 黄金 | 1 两 = 10000 文 |
| 白银 | 1 两 = 100 文 |
| 铜钱 | 基础货币 |
| 银票 | 大额携带形式 |

以下内容不属于当前 XKX100 基线，作为后续可选增强：

- 非原版的拍卖规则扩展
- 跨服或跨实例交易
- 现代 MMO 式经济调控系统

### 10.11 表现形式与后续可选增强

当前表现形式以 XKX100 的纯文字体验为基线。

当前需求不把图片、图标、音效、图形化 UI 当成 XKX100 对齐目标的一部分。

以下内容保留为后续可选增强：

- 图标与图片插槽
- 音效与背景音乐
- 更强的移动端界面包装
- 图形化地图与可视化辅助

---

## 十一、首发闭环与阶段范围

### 11.1 首发闭环目标

首发闭环的目标不是一次做完整武侠世界。

首发闭环的目标是打通“可登录、可进世界、可移动、可战斗、可聊天、可编辑内容”的最小可玩链路。

第十章定义的是 XKX100 完整内容基线。

第十一章只定义首发的实现顺序与最小纵切，不缩减第十章的长期候选内容基线；后续仍须通过逐步扩大的兼容包络验证，不能预先宣称未纳入行为已经对齐。

### 11.2 首发闭环必做能力

- 已验证邮箱、独立账号名和密码注册；账号名和密码登录
- 已验证邮箱短期验证码找回密码，并即时撤销全部旧认证状态
- 角色创建
- H5 适配 PC 浏览器与移动端浏览器
- 房间 / 出口 / 场景浏览
- 基础移动与查看
- 公共聊天与私聊
- 背包、装备、物品使用
- 首发兼容包络内的 XKX100 战斗机制与相关指令语义闭环
- Web 管理后台对首发白名单内容的草稿、校验、差异、发布与回滚
- 最小 Blueprint 草稿、校验、发布批次、冷发布与批次回滚闭环
- 一个最小可玩区域

### 11.3 首发闭环不包含的能力

以下能力明确移出首发闭环：

- 短信验证码
- 微信小程序接入
- 微信授权登录
- XKX100 全量内容闭环
- XKX100 首轮转换验收

以下能力不作为首发闭环前置：

- 31 门派全量开放
- XKX100 任务、经济、帮会 / 组织、社交系统的完整复刻
- XKX100 正邪 / 声望 / 师门忠诚等关系状态的完整复刻
- XKX100 频道系统、队伍消息与帮会 / 组织消息闭环
- 全量地图与特殊区域导入
- 后台对全量内容的编辑覆盖

### 11.4 固定首发纵切与验收流程

首发区域固定使用第 7.3 节的 `xkx100-village-alley-v1`，不得用任意自造区域替代验收。

武学与战斗对齐验收必须同时使用同一 `source_snapshot_id` 下的 `xkx100-skill-combat-v1`。复合验收 bundle 只引用两个独立 manifest，不得把 skill/command 添加为世界 roots。

该纵切由两间房间、两个可战斗 NPC 和一个装备物品定义组成。两个 NPC 各穿戴一个物品实例。纵切覆盖进入世界、查看、移动、生成、基础战斗、死亡掉落、物品加载及后台内容发布，不额外虚构 XKX100 任务语义。

验收流程固定如下：

1. 校验 `source_snapshot.json`、世界与武学 manifest、复合验收 bundle、逐文件哈希和聚合哈希。
2. 将白名单内容以 Blueprint 草稿导入 PostgreSQL，执行校验并创建发布批次。
3. 完成冷发布后，验证邮箱并注册账号、使用账号名和密码登录、创建唯一角色并进入 `alley1`。
4. 执行“查看 -> 西北移动 -> 发起战斗 -> 查看战利品”的固定流程。
5. 使用武学 manifest 纳入闭包的技能完成 `jifa` / `prepare` 与 `perform` / `exert` 校验链。
6. 确认 `alley1.east` 被报告为不可进入的外部边界，且未被静默删除或伪造。
7. 校验黄金行为、状态差异、事件输出、仅适用于纯展示差异或非必做项的例外清单，并验证发布批次可回滚。

武学 manifest 未实际冻结时，第 5 与第 7 步中的武学/战斗对齐项必须标记 `manual_review` 或 `blocked`，不得以合成 fixture 通过替代 XKX100 黄金差分。此时 M1-A 与 M1 均不得标记完成。

### 11.5 首发后迭代方向

优先恢复项：

- XKX100 首轮转换闭环
- XKX100 全量门派与区域
- XKX100 任务系统完整复刻
- XKX100 正邪 / 声望 / 关系状态补齐
- XKX100 帮会 / 组织、社交与经济系统完整复刻
- XKX100 频道系统与队伍 / 组织消息补齐
- XKX100 非战斗玩法与辅助指令补齐

后续可选增强：

- 自创武学
- 多周目与传承
- 音效与图形化增强
- 现代网游化扩展玩法

---

### 11.6 Public V1Gate：公开发布边界

`PublicV1Gate`（需求 ID `RELEASE-001`）是独立于 M0-M6 的公开发布门禁。它只评估一个由项目方运营的官方单实例；自托管、任意多实例部署或第三方运营不是 Public V1 的发布目标。

M1-A / M1-B 继续作为内部、封闭交付检查点：M1-B 可以证明内部候选可运行，但不能自动开启公开注册、对外宣传或公共服务。Public V1 必须在一个完整 `ReleaseManifest` 上单独签署 gate 结论。

### 11.7 Public V1 玩家循环与内容目标

Public V1 的玩家核心循环固定为：探索 → 学习武学 → 战斗 → 获得战利品 / 资源 → 成长 → 社交互动。

最低内容目标为可连通的约 30-60 个 Room、至少一条武学路径、10 个以上具功能或敌对行为的 NPC、20 个以上 Item 定义、至少一条可重复 PvE 循环，以及首次游玩约 2-4 小时的内容量。起始区使用完整 `d/village` 拓扑并受 `VillageTopologyEnvelope` 约束；行为只按 `VillageInteractionEnvelope` 中的 verified 能力开放。超出包络的交互统一解析为 `UnavailableInteraction`。

### 11.8 Public V1 试运行与缺陷门禁

Public V1 前必须完成至少 7 天的封闭试运行，至少 5 名非管理员测试者参与，并完成至少 20 次核心循环。发布时 S0 / S1 问题不得存在；受约束的 S2 例外必须记录负责人、用户可行 workaround 和到期日；S3 可以作为已知问题公开记录。任何 S2 例外都不能把必做能力的 `blocked` / `unverified` 改写为通过。

### 11.9 Public V1 运营、注册与支持入口

Public V1 仅验证一个 owner-operated 官方实例。通过 gate 后，实例默认进入 `open` 自助注册；运营可审计地切换为 `paused` 或 `invite_only`，切换不改变历史账号和 Character 身份。

初始 superuser 只能由安全的一次性管理命令创建；禁止默认账号、默认密码或提交到仓库的初始凭据。

每次部署都必须带完整 `ReleaseManifest`，绑定代码提交、需求版本、契约版本、迁移 head、active `ContentReleaseBatch`、`SourceSnapshot`、兼容包络和测试报告。代码、迁移和内容必须协调回滚；紧急回滚须记录原因和受影响批次。

运维必须提供公开状态页、维护公告、游戏内 `SystemNotice`，以及统一的恢复 / 申诉 / 举报 / 客服入口。计划中的冷维护至少提前 24 小时公告，执行 drain、证据记录、健康检查和异常事件记录；紧急维护必须建立 incident 记录。

Public V1 发布前必须公开：社区规则、已验证联系方式恢复与账号关闭说明、数据保留摘要、可用性声明，以及运营者对发布内容责任的确认。上述资料不把法律判断重新引入工程自动化门禁。

Public V1 开放自助注册前必须使用受控域名和正式邮件服务，并完成 SPF、DKIM、DMARC、退信处理、配额、告警与基础送达证据。163 SMTP 只允许显式 opt-in 的本机开发 smoke，不属于发布证据。

### 11.10 Public V1 社区治理与保留

Public V1 必须提供 `PlayerBlock`、`ChannelMute`、带不可变消息 ID 的举报、服务器取证上下文、GM 警告 / 定时禁言 / 定时停权 / 封禁，以及每案一次的审计申诉。`PlayerBlock` 只影响执行者看到的普通公共消息和私聊，不删除证据或改变其他接收者；`ChannelMute` 只抑制个人订阅；系统、安全和 GM 通知不可屏蔽。

默认保留期：普通 `ChatMessage` / `DirectMessage` 30 天；举报证据为结案后 180 天；认证、安全与 GM 审计 365 天；内容发布历史长期保留。未来账号关闭立即撤销会话并进入 30 天可恢复冷静期，保留已验证联系方式并只允许用途独立的 account-reopen challenge 恢复；期满后 User 数据匿名化 / 禁用，联系方式撤销并解绑，GameAccount 与 Character 退休，稳定 ID 仍可用于历史记录。账号关闭、重新启用和联系方式换绑不属于当前 Auth Baseline Amendment 的运行实现。

### 11.11 Public V1 例外与后置能力

Public V1 不包含支付、订阅、付费 Item 或真实货币经济；UI 与内容仅提供简体中文，Unicode 全面支持但暂不建设 i18n 内容流水线。完整致命 PvP、玩家交易、银行、拍卖、摊位和动态经济均作为后续独立需求，不得借用 Public V1 的 gate 结论预先宣称支持。

## 十二、后台管理需求

### 12.1 内容制作

首发内容后台只冻结以下白名单：

| 内容类型 | M1 必做操作 | 阶段边界 |
|:---|:---|:---|
| Room / Exit / Region 元数据 | 查看、创建 draft revision、编辑、校验、diff、批次发布、批次回滚 | M1 |
| NPC / Item | 查看、创建 draft revision、编辑、校验、diff、批次发布、批次回滚 | M1 |
| Skill / SkillMove / ConditionDefinition | 查看、创建 draft revision、编辑、校验、diff、批次发布、批次回滚 | M1 |
| Quest / Dialogue / Shop / LootTable | 不要求 M1 编辑器 | M2 |
| 世界事件、定时活动、组织与经济内容 | 不要求 M1 编辑器 | M2-M3 |

M1 不要求硬删除已发布 revision、活体实例热同步或任意 ORM 表编辑。后台只能调用 ContentPublishService 等公开服务，不得直接改写 published revision、活动批次指针或运行时实例。

M2 再补齐任务、世界事件、商店、掉落、对话树与触发条件的完整制作流程。

### 12.2 运营管理

- 账号查询、封禁、解封
- 受审计的密码重置 / 账号恢复
- 角色数据查看与修正
- 在线状态查看
- 公告发布
- 敏感操作审计

### 12.3 数据与巡检工具

- 批量导入导出
- 转换器结果校验
- 数据一致性巡检
- 失效引用检测
- 操作日志查看
- 异常日志查看
- 内容发布差异对比
- 发布批次与导入结果查看

### 12.4 后台权限层次

首发后台必须区分以下角色：

- 超管
- 运营
- 内容编辑
- GM / 客服
- QA / 只读巡检

这些角色属于 `PlatformRole`，不属于玩家侧 `GameAccount` 权限。

超管负责角色授予与紧急处置；运营负责账号、公告和发布审批；内容编辑只能处理草稿与被授权发布流；GM / 客服处理玩家问题；QA / 只读巡检不得执行写操作。

玩家密码重置只通过仍可用的 `VerifiedContactMethod` 自助完成。后台不得查看完整联系方式或验证码、绕过 challenge、直接替用户设置密码，或依据 Character/游戏资料重分配账号；密码与全部已验证渠道同时丢失时只能冻结账号并保全审计。

---

## 十三、非功能性要求

稳定性、可维护性、安全性是与玩法目标同级的最高约束。

任何方案取舍都应先满足这三项，再讨论功能覆盖率与开发速度。

### 13.1 安全性

- 全站 HTTPS / WSS
- 服务端权威计算
- 接口限流
- 权限分层
- 操作审计
- 常见输入过滤与校验
- 后台与玩家认证边界分离
- VerifiedContactMethod 密文、lookup digest、验证码 pepper、投递 payload、Django、SMTP 与 token 密钥彼此独立
- 认证 request 非枚举、幂等、持久限流；缺钥、限流或投递基础设施异常时验证功能 fail closed，普通登录保持可用

### 13.2 稳定性

- 关键异常隔离
- 优雅停机
- 自动重启
- 定时备份
- 恢复演练
- 长连接异常回收
- 关键状态回写失败时有补救策略

### 13.3 可维护性

- 模块边界清晰，领域逻辑、应用服务、基础设施职责分离。
- 核心规则可测试，不依赖隐式全局状态与难以追踪的副作用。
- 公开接口稳定，禁止绕过服务层任意穿透写状态。
- 关键流程必须有类型约束、日志审计点与必要文档。

### 13.4 可观测性

- 分级日志
- 结构化日志
- 核心指标监控
- 在线连接数监控
- 慢查询监控
- 任务失败告警
- 验证 outbox backlog/oldest age、claim lease、投递延迟/结果、challenge 激活/消费/锁定、限流与安全通知失败告警
- 战斗错误与协议错误统计

### 13.5 测试要求

- 单元测试覆盖核心规则
- 集成测试覆盖登录、移动、战斗、聊天
- PostgreSQL 集成测试覆盖已验证邮箱注册、密码重置、跨实例认证撤销、challenge/outbox、幂等与持久限流
- 转换器测试覆盖 XKX100 样例与关键回归样本
- 黄金行为测试固定随机种子、时钟、时区与初始状态
- 差分测试在相同输入下对比 XKX100 夹具与 New_Mud 的状态差异和事件输出
- 世界与武学 manifest 必须引用同一 `source_snapshot_id`；复合验收 bundle 或任一哈希不匹配时测试必须阻断
- 武学依赖闭包未冻结时，相关黄金链必须标记 `manual_review` 或 `blocked`
- 合成 fixture 只能进入引擎机制测试，不得计作 XKX100 黄金差分或对齐证据
- 必做能力的未通过差异必须阻断验收；只有纯展示差异或非必做项可进入包含负责人、依据与复核日期的例外清单
- 后台关键操作有回归测试
- 上线前执行并发压测

### 13.6 性能与扩展性原则

- 只为单实例优化，不为分布式扩展提前设计过重机制。
- 优先优化房间广播、战斗结算、路径查询、内容加载四类热点。
- 允许后续增加缓存层，但不得让缓存先于数据库成为事实真源。

### 13.7 首发容量与恢复预算

M0 必须批准并版本控制 Public V1 的 `capacity_profile`。在没有更高目标的已批准 profile 时，Public V1 使用以下最低基线；M1-B 可以按同一 profile 做内部工程抽样，但抽样不计作 PublicV1Gate 证据：

| 维度 | 最低验收目标 |
|:---|:---|
| 参考环境 | 应用 4 vCPU / 8 GiB，PostgreSQL 4 vCPU / 8 GiB，同区域网络，生产构建，不依赖 Redis |
| 数据规模 | 10000 个账号与角色、10000 个 Blueprint revision、100000 个 Item Entity |
| 在线负载 | 200 条 WebSocket、100 个 active Presence、25 场并行战斗 |
| 突发负载 | 每秒 5 次注册/登录、20 条公共聊天消息，持续 5 分钟 |
| REST 延迟 | 注册、登录和 refresh 的 P95 不超过 750 ms，错误率低于 1% |
| 实时延迟 | 非调度型 Action 终结 P95 不超过 300 ms；聊天投递 P95 不超过 500 ms |
| 恢复体验 | 已取得新连接后的完整状态重建 P95 不超过 2 秒 |
| 稳定运行 | 基线负载持续 2 小时，无数据不一致、重复结算、未处理异常或非计划断线 |
| 数据恢复 | 生产 RPO 不超过 15 分钟，RTO 不超过 60 分钟 |
| 备份保留 | 至少保留 7 份每日备份和 4 份每周备份，并通过隔离恢复演练 |

延迟从服务端收到完整请求到产生可交付终结或事件计算；不包含客户端公网传输和显式 Scheduler 等待。Public V1 测试报告必须记录硬件、数据集、采样窗口和 P50/P95/P99；M1-B 的内部报告必须明确标记为非 gate 证据。

提高目标可以通过新的 capacity profile 执行。降低任一最低目标必须修改本版本，不得只在部署配置或测试报告中放宽。

---

## 十四、部署方案

### 14.1 开发环境

- 本机开发
- PostgreSQL 本地实例
- PC 与移动端浏览器 H5 联调

Redis 与 Celery 在开发环境中不是强制项。

### 14.2 测试环境

- 接近生产的 Linux 环境
- 与生产同版本 PostgreSQL
- 独立域名或测试子域名

若测试阶段需要验证 Redis channel layer 或限流，再引入 Redis。

### 14.3 生产环境

首发推荐部署形态如下：

- Nginx
- 单 Daphne / 单 ASGI 游戏进程
- Django / Channels 应用
- PostgreSQL
- systemd 或 Supervisor

如果未引入 Redis channel layer，不允许把 WebSocket 层拆成多个相互独立的进程后依赖进程内状态广播。

按需引入的可选组件如下：

- Redis
- Celery Worker
- Celery Beat

Redis 只有在需要 Channels channel layer、缓存或限流时才引入，不作为当前单实例部署前提。

### 14.4 备份策略

- PostgreSQL 定时备份
- 关键配置文件备份
- 转换结果与导入报告归档
- 发布前后关键数据快照

### 14.5 运维原则

- 首发以单实例稳定运行为第一目标。
- 生产环境优先保证可运维性、可回滚性与安全边界清晰。
- 不为了“未来可能上多实例”而提前引入复杂协调层。
- 任何新增基础设施都必须有明确收益与维护边界。

---

## 十五、需求里程碑与引擎路线图

本章定义产品需求里程碑 `M0-M6`。下游 `docs/new_engine/10_ROADMAP.md` 使用开放式 `Engine Stage Ex` 定义子系统编码顺序，两套编号不等价。

后续文档必须写明“需求里程碑 Mx”或“引擎阶段 Engine Stage Ex”。禁止使用没有命名空间的“Phase x”或“Stage Ex”。

### 15.0 里程碑完成规则

每个需求里程碑只允许 `not_started / in_progress / blocked / complete` 四种状态。

标记 `complete` 必须同时满足：

- 所有必做交付和验收项都有可定位的代码、迁移、测试报告或审批记录。
- 必做项不存在 `manual_review`、`blocked`、未批准例外或缺失外部依赖。
- 所有前置里程碑已经完成；内部检查点不能替代里程碑完成。
- 受影响的需求、冻结合同、追踪索引和测试证据在同一变更中同步。

例外只能使非必做项继续推进，不能把必做失败改写为通过。阻断原因消除后必须重跑受影响验收。

本文只定义里程碑完成规则，不维护会随实施变化的当前状态。需求里程碑状态以 `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 的追踪记录和 `18_IMPLEMENTATION_STATUS.md` 的可回查证据为准；产品 M0 与 Engine Stage E0 必须继续独立判断，任何一方的完成都不能替代另一方证据。

### 15.1 需求里程碑 M0：基线、契约与工程骨架

- 建立 Django + DRF + Channels + PostgreSQL 骨架
- 建立分层架构、测试骨架、健康检查与基础可观测性
- 冻结协议信封、错误码、Registry、MUDLib 与 Blueprint 最小契约
- 冻结 AuthSession、Presence/PresenceSnapshot 边界、单角色和跨设备单 PresenceSnapshot 租约约束
- 冻结 Blueprint 草稿、校验、发布批次、冷发布与批次回滚契约
- 生成并版本控制 `source_snapshot.json`、独立的世界与武学 fixture manifest，以及同时引用二者的复合验收 bundle
- 批准首发 capacity profile、精确浏览器测试矩阵与恢复预算
- 冻结已验证联系方式注册、账号名/密码登录、邮箱密码重置、RecoveryCode 退役和后台角色权限边界

M0 只有在上述制品、合同和决策记录全部存在且通过自动校验后才可完成。源快照、任一 manifest 或复合 bundle 未冻结时，M0 必须保持 `blocked`。

### 15.2 需求里程碑 M1：首发可玩闭环

- 实现已验证邮箱、账号名和密码注册，普通账号名/密码登录，JWT Access Token 与轮换 Refresh Token
- 实现邮箱密码重置、跨实例全部认证状态即时撤销与 RecoveryCode 退役
- 实现唯一角色创建、进入世界、断线安全重建与跨设备单 PresenceSnapshot 租约
- 实现 PC 与移动端浏览器 H5 主流程
- 实现移动、查看、公共聊天、私聊、背包、装备与物品使用
- 实现首发兼容包络内的 XKX100 战斗机制及 `jifa` / `prepare` 关键语义；武学 manifest 未冻结时 M1 不得完成
- 以人工重构或已验证产物装载 `xkx100-village-alley-v1`
- 实现 Blueprint 草稿、校验、发布批次、冷发布与批次回滚闭环
- 按第 11.4 节完成固定首发验收

M1 使用两个内部检查点降低反馈周期；二者都是内部 / 封闭交付步骤：

| 检查点 | 可交付结果 | 完成边界 |
|:---|:---|:---|
| M1-A 可玩验证 | 已验证邮箱注册、登录、进入固定区域、移动、聊天、战斗、武学链和战利品闭环 | 首发兼容包络必须 verified；只用于内部验收，不构成公开发布 |
| M1-B 发布候选 | 白名单后台编辑、发布/回滚、调度恢复，以及 M1 范围内的安全和恢复检查通过 | 等同 M1 完成，但不构成公开发布 |

M1-A 不是独立需求里程碑。只有 M1-B 通过，需求里程碑 M1 才能标记 `complete`。浏览器完整矩阵、容量 / soak、五个业务范围恢复与 Public V1 试运行证据属于 `RELEASE-001`，不能用 M1-B 替代。

### 15.3 需求里程碑 M2：后台与内容深化

- 完善内容编辑、差异对比、发布审计与回滚工具
- 完善任务、商店、掉落、刷新与公告能力
- 完善联系方式管理、账号关闭/重新启用、日志查看与巡检工具
- 补齐关键后台操作的权限、审计与回归测试

### 15.4 需求里程碑 M3：原版玩法补齐

- 补齐组队与玩家交易
- 补齐正邪、声望、师门忠诚等关系状态
- 补齐频道系统与队伍 / 组织消息链路
- 补齐门派体系、原版组织与社交系统

### 15.5 需求里程碑 M4：XKX100 导入与适配闭环

- 基于需求里程碑 M0 的固定源快照完成 XKX100 结构扫描
- 实现房间、NPC、物品、技能与条件定义的基础导入
- 打通至少一条 `jifa` / `prepare` / `perform` / `exert` 链路
- 输出人工适配清单、边界引用、导入校验与风险报告
- 对同一 source snapshot 下的世界与武学 manifest 执行复合黄金行为与差分测试
- 武学依赖闭包未冻结时不得完成 M4 对齐验收，也不得以合成 fixture 代替
- 完成第 7.16 节的首轮转换验收

### 15.6 需求里程碑 M5：内容与玩法扩展

- 深化武学、任务、经济与世界事件
- 扩大 XKX100 导入和人工适配范围
- 补齐全量门派、区域、频道与非战斗指令
- 在不破坏现行契约的前提下迭代高级玩法

### 15.7 需求里程碑 M6：微信小程序交付

- 交付实际可运行的微信小程序客户端，不以 H5 壳或接口预留代替
- 接入微信 AuthIdentity、授权登录、身份绑定与账号恢复
- 复用 JWT 续期、单角色与跨设备单 PresenceSnapshot 租约约束
- 处理前后台切换、网络中断、Token 失效与 PresenceRecovery
- 建立微信开发者工具、真机调试、自动构建与发布工具链
- 完成隐私、安全和平台审核

### 15.8 与下游引擎阶段的关系

- 需求里程碑描述产品结果与验收边界，编号在本需求内保持稳定。
- Engine Stage 描述实现依赖与编码顺序，可由路线图按工程需要新增、删除、拆分、合并或重排。
- 一个需求里程碑可以跨多个 Engine Stage，一个 Engine Stage 也可以承接多个需求里程碑。
- 路线图必须为每个 Engine Stage 标注承接的需求章节或里程碑，但不得按数字建立默认对应关系。
- 需求里程碑 M6 必须在路线图中获得实际交付落点，具体 Engine Stage 编号由路线图决定。

---

## 十六、当前确认项

- 项目第一目标是以现代技术重构 XKX100
- 采用自研引擎路线
- 不使用 Evennia 运行时
- `evennia-main/` 仅作为本地参考源码
- 保留 Evennia 设计思想借鉴
- 对 Evennia 的借鉴仅以本地 `6.0.0` 快照源码为准
- 前端采用 uni-app + Vue 3
- 首发支持 H5，并覆盖 PC 浏览器与移动端浏览器
- 首发浏览器、视口、中文输入和无障碍最低范围以第 9.2.1 节为准
- 首发注册固定为已验证邮箱、独立账号名和密码；登录仍只使用账号名与密码，并采用 JWT Access Token 与轮换 Refresh Token
- 密码重置使用已验证邮箱的短期 VerificationChallenge，成功后即时撤销全部旧认证状态且不自动登录
- 每个游戏实例内一个 User 永久映射一个 GameAccount；CharacterOwnership 为未来多角色扩展边界
- RecoveryCode 已退役，只保留历史 provenance；现行认证权威使用 VerifiedContactMethod 与 VerificationChallenge
- Auth Baseline Amendment 必须先于 Character Slice 2；本轮不实现 SMS、联系方式换绑、账号关闭/重开、Character、Presence、PresenceRecovery 或 takeover
- Character 创建使用版本化 CharacterCreationProfile；CharacterDisplayName 按 NFKC 在实例内唯一，性别 / 代词只影响展示
- 首发每个 GameAccount 最多一个 Character，未来扩展保留 CharacterOwnership
- 同一 GameAccount 跨会话与设备最多一个处于 `active` 或 `grace_disconnected` 的 PresenceSnapshot 租约
- 同一 AuthSession 可用 `presence.recover` 恢复自身 active / grace PresenceSnapshot 租约并创建新一代运行时 Presence；跨 AuthSession 仍必须显式 takeover
- 普通第二控角请求默认拒绝；显式 `presence.takeover` 必须确认、通过策略授权并原子替换旧 PresenceSnapshot 租约与 ticket，提交后再关闭旧运行时 Presence
- 后端正式环境统一采用 PostgreSQL
- 只做单实例
- 不做多实例水平扩展
- 首发必须具备 Blueprint 草稿、校验、发布批次、冷发布与批次回滚闭环
- M1 内容后台只覆盖第 12.1 节白名单对象和操作
- 战斗对齐结论只覆盖已绑定、已验证的 XKX100 兼容包络
- Public V1 只允许非致命 Sparring，并以 SafeDefeat 处理玩家失败
- Public V1 使用 VillageTopologyEnvelope 与 VillageInteractionEnvelope；未验证交互必须显式 UnavailableInteraction
- 武学采用 XKX100 的 `jifa` / `prepare` 机制
- 非技术内容以 XKX100 当前设定为基线，超出部分转为后续可选增强
- 第十章定义 XKX100 完整基线，第十一章仅定义首发实现顺序
- 扩展性服务于未来现代网游玩法接入
- 稳定性、可维护性、安全性为最高优先级
- 当前唯一转换目标为 XKX100
- XKX100 对齐结论必须绑定不可变源快照、两个独立 fixture manifest、复合验收 bundle 和可复现测试
- 固定世界夹具为五个 roots 及其 dependency closure，武学与战斗 roots/dependencies 另由 `xkx100-skill-combat-v1` 冻结
- 内容许可与公开发布法律判断不属于工程里程碑；工程只冻结可复现来源和制品依赖
- PublicV1Gate（RELEASE-001）独立于 M0-M6；只验证一个 owner-operated 官方实例
- Public V1 需要 7 天封闭试运行、至少 5 名非管理员测试者和至少 20 次核心循环，并完成社区治理、公开运营资料与 ReleaseManifest
- M0 必须批准 capacity profile、精确浏览器目标矩阵与恢复预算；实际浏览器版本只由发布候选测试证据填写
- 微信小程序客户端与微信授权登录属于需求里程碑 M6
- 需求里程碑 `M0-M6` 与开放式引擎阶段 `Engine Stage Ex` 不按编号对应

## 十七、下游同步与变更规则

以下范围已纳入本版本的同步与持续交叉审查：

- `docs/new_engine/00_README.md`
- `docs/new_engine/03_RUNTIME_SESSIONS.md` 与 `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`
- `docs/new_engine/06_CONTENT_CHAT_HELP.md` 与 `docs/new_engine/07_SCHEDULER_EFFECTS.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- `docs/new_engine/09_MUDLIB_CONVERTER.md` 与 `docs/new_engine/10_ROADMAP.md`
- `docs/new_engine/11_PROTOCOL_CATALOG.md` 到 `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
- `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 到 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`
- `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`
- `docs/new_engine/19_V6_CONTRACT_DIFFERENCES.md` 与 `docs/new_engine/NEXT_SESSION_HANDOFF.md`（仅同步/交接材料，不取代 11-18），以及 `archive/handoffs/2026-08-26-e0-closeout/`（只读历史过程）
- `plans/` 与 `contracts/v1/` 中受 V6 影响的计划、机器合同和验收制品（语义仍回链 V6 与对应冻结合同）
- `docs/00-20` 中涉及现行术语、权威顺序、路线图编号或 Evennia 参考边界的分析或治理说明
- 根目录 `UBIQUITOUS_LANGUAGE.md`

同步重点包括已验证联系方式注册与恢复、认证撤销、控角约束、ConditionDefinition / EffectInstance、固定夹具、兼容包络、发布闭环、来源可复现性、容量恢复预算、需求追溯和小程序交付。

V5 已冻结为历史基线。后续修改产品目标、范围、里程碑或验收结果时，必须先修改 V6，并在同一变更中同步受影响合同和追踪索引；实质变化不得回写 V5。

只改变协议字段、状态机、持久结构、事务或失败语义且不改变产品结果时，应修改对应冻结合同和追踪索引；V6 只在跨系统不变量或验收结果变化时同步。

冲突必须先按第 1.4 节确定关注点。产品问题以 V6 为准，实施问题以对应冻结合同为准；无法分类时阻断合并，不能用简单的文件总排序掩盖问题。

---

## 十八、需求标识与追踪

`docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 维护稳定需求 ID、V6 来源（必要时保留 V5 历史指针）、实施合同、里程碑和验收证据。

需求 ID 一经发布不得复用或改变原义。废弃需求保留 ID 并标记 `retired`；语义发生实质变化时必须创建新 ID。

M0 起的 issue、提交、迁移、测试和发布证据必须至少引用一个需求 ID。不能追溯到需求或经批准技术债的实现不得进入发布候选。
