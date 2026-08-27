# 10 实施路线图

## 1. 编号与追溯规则

`requirements_v6.md` 使用需求里程碑 `M0-M6` 描述产品结果；`requirements_v5.md` 仅保留为历史基线。本路线图使用开放式 `Engine Stage Ex` 描述实现依赖与可交付增量。

两套编号不等价，也不建立一一映射。一个需求里程碑可以跨多个 Engine Stage，一个 Engine Stage 也可以承接多个需求里程碑。

本路线图中的现有 Engine Stage 可按工程需要拆分、合并、插入或重排，不冻结最大编号。变更时必须同步每个 Engine Stage 的需求追溯、依赖和验收证据。

后续任务、issue 与提交说明必须写明“需求里程碑 Mx”或“Engine Stage Ex”，不得使用无命名空间的阶段编号。

## 2. 实施原则

- 每个 Engine Stage 都交付可运行、可测试、可审计的纵向增量。
- H5 客户端随服务端能力逐步增长，不留到后端全部完成后一次接入。
- 首发每个 GameAccount 最多一个 Character，同时最多一个 `active` 或 `grace_disconnected` PresenceSnapshot 租约。
- 单实例、单写者、PostgreSQL 持久真源和冷发布边界始终成立。
- ConnectionSession、Presence、CombatInstance 与 runtime_only Effect 只在运行时内存。
- AuthSession、PresenceSnapshot、durable Effect 与结算结果按合同持久化。
- `11_PROTOCOL_CATALOG.md` 到 `16_OPERATIONS_TESTING_CONTRACT.md` 六份合同共同约束实施，不得只冻结其中一部分。
- `17_REQUIREMENTS_TRACEABILITY.md` 维护稳定需求 ID、合同责任和验收证据。
- XKX100 对齐必须绑定受控源快照、独立的世界与武学 manifest、复合验收 bundle 和黄金差分。

## 3. Engine Stage E0：合同基线与工程骨架

需求追溯：需求里程碑 M0、M1；V6 第 5.4、6.13-6.14、7.2、7.3、15.1 节。

目标：

- 建立 Django、DRF、Channels、Daphne 与 PostgreSQL 工程骨架
- 建立 apps 分层、配置、迁移、测试和健康检查
- 冻结六份实施合同的首个兼容版本
- 冻结 MUDLib、Registry、Blueprint、协议和会话边界
- 建立 XKX100 可复现来源与制品依赖记录
- 批准 capacity profile、浏览器矩阵和恢复预算
- 建立后续世界纵切可合法依赖的最小内容发布真源

交付：

- 基础目录、settings、CI 与 PostgreSQL 测试环境
- 由合同生成或双向校验的协议、错误码、状态与 registry schema
- BlueprintHead、immutable draft/published BlueprintRevision、两类 Resolved Dependency 与 ContentReleaseHead/Batch/Item 最小模型
- registry definition hash、compiler contract version，以及 content/compiled/resolved-dependency/release hash 字段与校验
- 仅用于 `(instance_id, mudlib_key)` 首次初始化的受审计 seed bootstrap 与活动批次切换
- 为新选择读取 active batch、为 pinned 实例读取 exact historical revision 的内容解析器
- `source_snapshot.json` 与不可变 `xkx100-village-alley-v1` 世界 manifest
- 同一 `source_snapshot_id` 下不可变 `xkx100-skill-combat-v1` 武学 manifest
- 同时引用两个 manifest 的复合验收 bundle
- 逐文件哈希、树哈希、聚合哈希、定义数、运行时生成数、依赖闭包和外部边界记录
- requirements traceability 索引及 CI 引用检查

验收：

- ASGI、REST 与 WebSocket 健康检查可运行
- 11-16 的 schema 和关键枚举能进入自动合同测试
- 首次 seed bootstrap 可原子建立一个活动批次；普通启动不能重复导入或绕过批次读取包内内容
- 新 spawn 与 batch-scoped 请求只消费 active batch；pinned 实例只消费自身 exact revision
- 没有活动批次时拒绝启动世界，但已钉定历史 revision 的保留责任不因此消失
- source snapshot、任一 manifest 或复合验收 bundle 的 ID/哈希不一致时 CI 拒绝继续
- 世界 manifest 固定五个 roots 并另列其 dependency closure；skill/command roots 与武学依赖闭包在独立 manifest 冻结
- 在源快照产生前，任何报告都不宣称已与 XKX100 权威基线对齐
- capacity profile、浏览器矩阵或恢复预算缺失时 E0 不得完成

### 3.1 当前执行状态（2026-08-25，Issue #5 验收通过）

E0 已建立文档与 Git 基线、Django/ASGI/PostgreSQL 工程骨架、初始内容模型与迁移、机器合同、来源快照、双 manifest、复合 bundle、CI 和可执行结构校验。Python 3.14.2 私有运行时、完整依赖锁、PostgreSQL 18.4 迁移往返和静态检查均已验证。三个非功能 profile 已批准；浏览器矩阵冻结官方精确目标组合，恢复预算绑定了 schema、迁移历史和逐表行数均一致的 M0 隔离恢复报告。Engine Stage E0 / Slice 2 的实现已通过 Issues #1–#4 完成 Registry exact dependency、冻结 seed artifact、受审计 bootstrap、active/pinned resolver、服务器启动生命周期、只读 readiness、并发收敛、事务回滚和失败审计。

Issue #5 已在 V6 权威基线 `d14ce67` 上完成分层收口：PostgreSQL 合同与启动 E2E、内容/seed/runtime/health 集成、启用真库的全量 pytest、Ruff、mypy、Django、迁移漂移、依赖、M0 与 Markdown 门禁均通过。因此产品里程碑 M0 已 `complete`，其追踪记录 `MILESTONE-001` 为 `verified`；`ENGINE-001 / Engine Stage E0` 也为 `verified` 并已关闭，后续 frontier 交给 E1。现行结果见 `18_IMPLEMENTATION_STATUS.md`；完整历史命令、环境、结果和失败边界见 `archive/handoffs/2026-08-26-e0-closeout/PHASE2_CONTENT_STARTUP_WORKLOG.md`。

该结论不改变后续产品边界：`CONTENT-001` 仍为 `implemented`，完整后台发布服务待 M1；`WORLD-001` 仍为 `specified`，固定小巷世界物化与玩法 E2E 待 M1；浏览器实测、容量/soak、五业务范围恢复和公开试运行仍未完成，`RELEASE-001 / PublicV1Gate` 继续 `blocked`。

2026-07-19 已确认的 E0 收口与 E1 连接闭环纵向实施计划见 `plans/m0-e1-tracer-bullets.md`。该计划细化执行顺序与阶段验收，但不改变本路线图的 Engine Stage 边界。

## 4. Engine Stage E1：认证、会话与 H5 连接闭环

需求追溯：需求里程碑 M0、M1；V6 第 8、9、15.2 节。

目标：

- 保留 Issue #9 已验证的账号名/密码登录和零隐式登录历史
- 在 Character Slice 2 前完成 `Auth Baseline Amendment`：已验证邮箱注册、邮箱密码重置、即时认证撤销与 RecoveryCode 退役
- 固定账号密码、JWT Access Token 与轮换 Refresh Token
- 落地 ConnectionSession、AuthSession、Presence 与 PresenceSnapshot
- 落地首发单角色和跨设备单 PresenceSnapshot 租约约束
- 建立 H5 登录、连接、恢复和错误处理骨架
- 建立 enter/resume 所需的最小 Character、Room、权威位置与 snapshot 投影

交付：

- REST registration-verification request、register、login、refresh、logout、password-reset request/confirm，以及两个 RecoveryCode 410 兼容端点
- VerifiedContactMethod、VerificationChallenge、验证投递 outbox、持久限流与独立 worker
- User、GameAccount、CharacterOwnership、Character、Entity/Room 与 AuthSession 持久模型
- Character 权威位置、最小 scene/character snapshot，以及从 E0 活动批次生成的起始 Room
- 运行时 ConnectionSession 与 Presence，以及短期持久 PresenceSnapshot
- `session.authenticate / presence.enter / session.resume / presence.takeover`
- resume ticket hash、终结重放、显式 takeover 与旧连接通知
- uni-app + Vue 3 H5 壳、类型化协议客户端、token store 与连接状态 store

验收：

- register 原子消费 verified email challenge 并创建 User/GameAccount/VerifiedContactMethod，不创建 AuthSession 或 token；H5 随后普通 login
- password reset 原子撤销 User 跨实例全部旧 AuthSession/family/credential，旧 access/refresh 立即失败且不改变 GameAccount lifecycle
- RecoveryCode 不再签发、展示或消费；历史 Issue #9/E1 Slice 1 证据保持可回查
- 每个 GameAccount 最多创建一个 Character
- Refresh Token 只用于 REST refresh 轮换或 REST logout Cookie locator；不得进入 WebSocket 或 Authorization header
- 新 WebSocket 先建 ConnectionSession，再用 access token 绑定 AuthSession
- 同账号 active 或 grace PresenceSnapshot 租约已占用时，普通 enter 返回 `CHARACTER_OCCUPIED`
- 显式 takeover 原子替换租约与 ticket、保存 outbox，提交后旧连接收到 `presence.taken_over`
- H5 可完成登录、进入起始 Room、取得完整最小 snapshot、断线恢复和明确失败展示

### 4.1 当前执行顺序（2026-08-27 Auth Baseline Amendment 收口中）

1. Issue #9 / E1 Slice 1 保持 `verified` 历史检查点，不重写为未完成。
2. Issue #10 固定新的 `AUTH-005` 规格；Issue #11 已完成 V6、冻结合同、追踪、状态、计划和交接权威修订。
3. Issues #12–#15 已按原生 blocked-by 链完成 challenge/outbox、已验证邮箱注册、密码重置与即时撤销、RecoveryCode 原子退役；#16 的分层验证已执行，首轮双轴 findings 正在修复，证据见 `20_AUTH_BASELINE_EVIDENCE.md`。
4. 只有 #16 正式复审无未解决 hard finding 并完成 Issue 回填后，Character Slice 2 才解除阻塞；PresenceRecovery 属于该后续切片，显式 takeover 继续属于 Slice 3。

当前修订不实现 SMS、联系方式换绑、账号关闭/重开、Character、Presence、PresenceRecovery 或 takeover。163 SMTP 只用于显式 opt-in 的本机开发 smoke，不能作为 Public V1 provider 证据。

## 5. Engine Stage E2：世界、动作与 H5 场景纵切

需求追溯：需求里程碑 M1；V6 第 4、5、11.1-11.4 节。

目标：

- 在 E1 最小 Character/Room 基础上扩展 Exit、NPC、Item 与完整场景模型
- 让文本命令和结构化动作进入同一 Action 服务
- 让 H5 显示并操作固定小巷纵切

交付：

- Character 入场、Room/Exit 拓扑与 NPC/Item 生成服务
- `look / movement / get / drop` 及统一 `action.invoke`
- 房间广播、完整 scene/character snapshot 与 ResolvedActionSet
- H5 事件流、场景描述、方向控制、输入区与基础背包视图
- `alley1.east -> sroad3` 外部边界的显式不可通行表示

验收：

- 玩家进入 `alley1` 后可查看并西北移动到 `alley2`
- 两条内部有向 Exit 可通行，外部边界不可通行且未被静默删除
- 文本输入与 H5 控件驱动同一领域服务
- snapshot 能在新连接上原子重建 H5 权威 store

## 6. Engine Stage E3：聊天、帮助与 H5 交互增量

需求追溯：需求里程碑 M1、M2；V6 第 10.9、11.2、12 节。

目标：

- 完成公共聊天、私聊、系统通知与帮助检索
- 让 H5 提供首发通信和帮助工作流

交付：

- ChatChannel、ChatMessage、DirectMessage 与 SystemNotice
- CommandHelp、FileHelp、DbHelp 的统一索引
- 聊天权限、限流、审计与完整消息事件
- H5 聊天面板、未读状态、帮助搜索与错误反馈

验收：

- 两个玩家可在同一房间看见彼此并公共聊天
- 私聊、系统通知和帮助检索可通过 H5 完成
- 事件不携带请求 request_id，所有连接 seq 连续

## 7. Engine Stage E4：战斗、武学、物品与 H5 玩法纵切

需求追溯：需求里程碑 M1；V6 第 10.1-10.5、11.2、15.2 节。

目标：

- 打通 XKX100 原版战斗机制的首发纵切
- 打通 `jifa / prepare / perform / exert` 关键语义
- 打通背包、装备、使用、死亡掉落和战利品查看
- 为 H5 增加战斗、武学与物品操作

交付：

- 运行时 CombatInstance 与确定性战斗结算
- Skill、SkillMove、ConditionDefinition 与 EffectInstance
- runtime_only / durable Effect 持久化与恢复分流
- Inventory、Equipment、Item version 与冲突处理
- H5 角色状态、战斗摘要、武学、背包和装备面板

验收：

- 固定小巷中的两个 NPC 可进入基础战斗并产生正确掉落
- 两个 NPC 各穿戴一个由同一 `cloth.c` 定义生成的 Item 实例
- 至少一条已进入冻结武学 manifest 的技能链完成学习、jifa、prepare 与 perform/exert 校验
- 武学 manifest 未冻结时，该黄金链只能标记 `manual_review` 或 `blocked`，不得把 E4 或 M1-A 标为完成
- 首发 `compatibility_envelope_id` 内的必做能力全部为 `verified` 后，E4 才可形成 M1-A 候选
- 合成 fixture 只能验证引擎机制，不能替代 XKX100 黄金差分
- CombatInstance 不落库，关键结算结果原子回写持久真源
- 进程退出后 runtime_only Effect 丢弃，durable Effect 按精确版本恢复

## 8. Engine Stage E5：调度、恢复与世界过程

需求追溯：需求里程碑 M1、M2；V6 第 4.5-4.7、5.8、13 节。

目标：

- 实现单实例 Scheduler、周期任务、世界过程和 durable Effect 恢复
- 固化重试、幂等、misfire、overlap 与提交后事件语义

交付：

- ScheduledJob、RecurringJob、WorldProcess 与 ProgressClock
- 世界时间、NPC 作息、刷新与基础世界事件
- durable Effect 恢复、过期与补算边界
- 进程重启扫描、孤儿清理和安全回退

验收：

- 持久任务重启后按合同恢复且不重复结算
- 调度事件只在事务提交后发送
- 半完成攻击不恢复，战斗按 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 安全结束
- runtime_only Effect 不产生持久行

## 9. Engine Stage E6：Blueprint 后台、完整发布与回滚

需求追溯：需求里程碑 M0、M1、M2；V6 第 5.4、6.13-6.14、11.2、12 节。

目标：

- 在 E0 最小发布真源上实现完整 Blueprint 编译、差异审阅与普通批次发布
- 实现后台内容编辑、权限、审计、冷发布和批次回滚

交付：

- Blueprint schema、继承/引用依赖闭包、校验、diff 与并发编辑版本检查
- Admin draft 编辑、依赖重编译 revision、普通原子 ContentReleaseBatch 发布与批次回滚
- 活动指针、发布失败审计、缓存刷新与安全重载的完整服务
- Django Admin 与自定义管理页的最小制作流程
- M1 白名单只覆盖 Room、Exit、Region 元数据、NPC、Item、Skill、SkillMove 与 ConditionDefinition
- 发布成功后缓存刷新、安全重载与事件发送

验收：

- 编辑 draft 和发布都创建新 revision，不改写历史行
- 任一发布步骤失败时，revision、批次项和活动指针全部回滚
- 发布失败审计与成功批次严格分离
- 固定小巷可经草稿、校验、冷发布进入世界，并能以新批次回滚
- content editor 可提交但不能批准自己的普通批次，QA 保持只读
- 已加载活体实例不会被发布静默改写

## 10. Engine Stage E7：XKX100 转换与黄金差分

需求追溯：需求里程碑 M4；V6 第 7、15.5 节。

目标：

- 基于受控源快照实现 XKX100 扫描、IR、导入和人工适配报告
- 复用 E0 冻结的世界与武学 manifest 及复合验收 bundle，建立可复现黄金行为与差分验收

交付：

- include、宏、继承、feature 与命令语义扫描
- Room、Exit、NPC、Item、Skill 与 ConditionDefinition IR
- `xkx100-village-alley-v1` 转换、导入与外部边界报告
- `xkx100-skill-combat-v1` 依赖闭包、转换引用与武学链报告
- 同一 source snapshot 下的复合验收 bundle
- 人工适配、风险分级、导入校验与未支持项清单
- 固定随机种子、时钟、时区、黄金行为和差分测试工具

验收：

- source snapshot、任一 manifest 或复合验收 bundle 的 ID/哈希不匹配时拒绝转换
- 定义数与初始运行时生成数完全符合 V6 第 7.3 节
- 黄金行为的必做状态差异与事件输出全部通过；只有纯展示差异或非必做项可进入有负责人、依据和复核日期的例外清单
- 武学文件不得追加为世界 roots；转换与差分必须复用 E0 冻结的两类 roots/dependency 清单
- 合成 fixture 结果不得作为 XKX100 对齐证据
- 转换器不得静默跳过关键对象或伪造 `sroad3`

## 11. Engine Stage E8：原版玩法与内容扩展

需求追溯：需求里程碑 M3、M5；V6 第 10.7-10.10、15.4、15.6 节。

目标：

- 在已验证的核心契约上补齐 XKX100 原版子域
- 扩大区域、门派、任务、经济和非战斗指令覆盖

交付：

- 组队、交易、门派、组织与社交链路
- 正邪、声望、师门忠诚与 FactionMembership
- 任务、商店、频道、世界事件与经济深化
- 扩大转换与人工适配范围

验收：

- 新子域不绕过 Action、权限、发布与审计边界
- Quest、Dialogue、Shop 与 Reputation/Faction 不反向成为 M1 固定纵切前置
- 扩展内容按批次发布并有回归与回滚证据

## 12. Engine Stage E9：运维、恢复与发布门禁

需求追溯：需求里程碑 M1、M2、M4、M5；V6 第 13、14 节。

目标：

- 把可观测性、备份恢复、安全、容量与制品来源完整性变成发布门禁
- 形成可重复执行的生产发布与回滚流程

交付：

- 结构化日志、指标、告警、审计查询与敏感字段脱敏
- PostgreSQL 备份、恢复演练与发布前后快照
- 并发压测、故障注入、恢复、合同、黄金与差分测试套件
- 单 ASGI 进程部署、健康检查、冷发布与回滚 runbook
- 隐私、安全与制品来源检查

验收：

- 16 定义的必测项和发布证据全部通过
- 各部署环境已在发布审批前批准 RPO/RTO 目标，恢复演练的实测恢复点与恢复时长均达标
- M1 内部候选至少完成其范围内的安全、数据一致性、调度与基础恢复证据；完整 capacity profile、浏览器矩阵、soak、五个业务范围恢复与备份保留证据由 `PublicV1Gate` 重新执行
- 任何协议、迁移、原子发布、黄金差分或来源完整性门禁失败都阻断上线
- 生产环境不依赖未声明的 Redis、Celery 或多实例语义

E1-E4 通过后可形成 M1-A 内部可玩验证。E5、E6 与 E9 的 M1 范围门禁全部通过后才形成 M1-B；只有 M1-B 等同需求里程碑 M1 完成。完整 Public V1 运维证据不计入 M1-B，且 M1-A / M1-B 都是内部、封闭步骤，不构成公开发布。

运维能力必须从 Engine Stage E0 起持续建设；Engine Stage E9 是完整发布门禁的收口点，不是首次开始写日志和测试。

## 13. Engine Stage E10：微信小程序交付

需求追溯：需求里程碑 M6；V6 第 9.6、15.7 节。

目标：

- 交付实际微信小程序客户端与微信 AuthIdentity
- 复用既有协议、恢复和单 PresenceSnapshot 租约约束

交付：

- uni-app 微信小程序构建目标与真机调试
- 微信授权登录、身份绑定与账号恢复
- 前后台切换、网络中断、token 失效与 PresenceRecovery
- 自动构建、隐私、安全与平台审核材料

验收：

- 不以 H5 壳或接口预留代替真实小程序
- 微信登录仍进入持久 AuthSession、access token 与 REST refresh 边界
- 小程序与 H5 共享 11 的协议合同和同一服务端权威状态
- 平台审核、隐私与安全门禁全部通过

## 14. 首批编码顺序

当前建议顺序如下，但 Engine Stage 仍可按依赖和团队并行度调整：

1. Engine Stage E0：合同、工程骨架、源快照与 CI
2. Engine Stage E1：先完成 Auth Baseline Amendment，再进入 Character Slice 2 的会话与 H5 连接
3. Engine Stage E2：世界、Action 与 H5 场景
4. Engine Stage E3：聊天、帮助与 H5 通信
5. Engine Stage E4：战斗、武学、物品与 H5 玩法
6. Engine Stage E5：调度、Effect 与恢复
7. Engine Stage E6：Blueprint、后台与原子发布
8. Engine Stage E7：转换器与黄金差分
9. Engine Stage E8：原版玩法扩展
10. Engine Stage E9：运维与发布门禁
11. Engine Stage E10：微信小程序

任何并行工作都必须先满足共享合同依赖。不能以赶工为由复制协议、会话、Blueprint 或客户端状态模型。

## 15. 成功标准

路线图成立至少表现为：

- 不依赖 Evennia 运行，且保持单实例单写者边界
- H5 从登录到固定小巷战斗和战利品查看形成真实闭环
- 新玩家可从注册开始完成该闭环，注册不隐式创建认证会话
- 文本命令与结构化动作驱动同一领域服务
- Presence、resume、takeover 与崩溃恢复符合 `11_PROTOCOL_CATALOG.md` 和 `13_SESSION_AUTH_STATE_MACHINE.md`
- 战斗、武学、物品、Effect 与持久化符合 `14_COMBAT_SKILL_ITEM_CONTRACT.md`
- Blueprint 可原子发布和批次回滚
- XKX100 世界与武学 manifest 的复合验收 bundle 在明确兼容包络内通过可复现黄金差分
- 发布具备备份恢复、可观测性、安全与来源完整性证据
- 新玩法无需推翻核心身份、协议、内容和发布模型

### 15.1 PublicV1Gate（RELEASE-001）

PublicV1Gate 独立于 M0-M6 和 Engine Stage Ex，由 owner-operated 官方单实例执行。它要求完整 `ReleaseManifest` 绑定 commit、`requirements_v6.md`、11-16 合同、迁移 head、active ContentReleaseBatch、SourceSnapshot、Village / combat envelopes 与所有发布候选报告；代码、迁移和内容必须协调回滚。

Gate 证据还必须包含 7 天封闭试运行、至少 5 名非管理员测试者、至少 20 次核心循环、完整浏览器矩阵、容量与 soak、五个业务范围恢复、S0/S1 清零以及受约束 S2 例外记录。Gate 通过后才开放 `open` 注册；实例可审计切换为 `paused` 或 `invite_only`。公开状态页、维护通知、SystemNotice 和恢复 / 举报 / 申诉 / 客服入口是 gate 交付物。
