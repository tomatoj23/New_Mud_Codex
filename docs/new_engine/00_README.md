# New_Mud 新引擎构建文档集（设计层入口）

> 状态：设计层入口文档。凡涉及 New_Mud 当前架构、模块边界、接口约束、实施路线与开发顺序，以 `docs/new_engine/` 为准。`docs/00-18` 与 `docs/20_evennia_modernity_assessment.md` 仅作为 Evennia 源码分析依据、问题归档与回查材料。详见 `docs/19_documentation_governance.md`。

> 术语约束：本目录当前统一以 `requirements_v6.md` 与根目录 `CONTEXT.md` 为准；`requirements_v5.md` 已冻结为历史基线。若术语仅用于说明 Evennia 来源，会在上下文中明确标注。

## 1. 文档目标

这套文档不是对 Evennia 6.0 的功能介绍，而是基于本仓库的 `requirements_v6.md`、V5 历史基线与本地 `evennia-main` 源码审计结果，产出一套可直接指导 New_Mud 自研引擎开发的设计规范。

核心目标只有三个：

1. 明确哪些 Evennia 设计可以复用语义、处理顺序和不变量，而不复制源码或运行时形状。
2. 明确哪些 Evennia 实现不适合本项目，必须彻底重写。
3. 把“新引擎应该如何落地”写成按模块、按开放式 Engine Stage 可执行的建设文档。

## 2. 需求基线

本文档集默认以下约束已经成立，来源均为 `requirements_v6.md`（V5 仅作历史差异参考）：

- 引擎必须自研，不依赖 Evennia 运行。
- 技术路线以 `Django + DRF + Channels + Daphne + PostgreSQL` 为核心必选栈，并以 ASGI/`asyncio` 承接实时层。
- 单实例、单 MUDLib、启动期绑定，不支持运行时切换 MUDLib。
- 客户端主通道是 `WebSocket`；REST 负责注册、登录、Refresh Token 轮换、角色管理与后台操作。
- 首发面向 `PC 浏览器 + 移动端浏览器`，预留微信小程序，不以传统 telnet-first 为目标。
- 首发认证固定为用户名密码注册与独立登录、短期 JWT Access Token 与每次刷新后轮换的 Refresh Token。
- Refresh Token 仅可作为 REST refresh 的轮换凭据，或作为 REST logout 的受保护 Cookie locator；不得进入 WebSocket payload 或 Authorization header。
- 首发每个 `GameAccount` 最多拥有一个 `Character`，同时保留可扩展的 `CharacterOwnership`。
- 同一 `GameAccount` 跨会话与设备最多有一个 `active` 或 `grace_disconnected` Presence 租约；普通 enter 拒绝占用，只有显式且获授权的 takeover 才能原子替换租约与 ticket，并在提交后通知旧端。
- 当前唯一转换目标为 XKX100；输入必须绑定受控 `source_snapshot.json`、独立的 `xkx100-village-alley-v1` 与 `xkx100-skill-combat-v1` manifest，以及同时引用二者的复合验收 bundle。
- M0 必须批准 capacity profile、精确浏览器测试矩阵与恢复预算。
- 必须保留后台内容制作、运营管理、帮助系统、聊天系统、经济系统与调度能力。
- 产品需求使用 `M0-M6`；实施路线使用开放式 `Engine Stage Ex`，两者不得按编号等同。
- M1-A / M1-B 是内部封闭步骤；`PublicV1Gate`（`RELEASE-001`）独立决定是否允许公开运营。
- Public V1 仅验证一个 owner-operated 官方实例，使用 `VillageTopologyEnvelope` 与 `VillageInteractionEnvelope`。

## 2.1 阅读顺序

- 先看 `requirements_v6.md` 与根目录 `CONTEXT.md`，确定产品和领域术语边界；只有需要工程名称、来源别名或合同导航时，再看非权威索引 `UBIQUITOUS_LANGUAGE.md`。
- 再看本目录中的架构、运行时、领域模型与路线图。
- 真正准备编码前，按顺序精读 `11_PROTOCOL_CATALOG.md` 到 `16_OPERATIONS_TESTING_CONTRACT.md` 六份实施合同。
- 协议与会话先读 11、13；Registry 与发布读 12；玩法、H5、运维验收依次读 14、15、16。
- 从需求定位实施合同、里程碑和证据时，读取 `17_REQUIREMENTS_TRACEABILITY.md`。
- 核对当前实现、环境、验证结果和阻塞项时，读取 `18_IMPLEMENTATION_STATUS.md`。

## 3. 本轮源码审计范围

本轮设计结论建立在以下本地源码文件之上，而不是建立在旧知识上：

- Typeclass / Attributes / Tags
  - `evennia-main/evennia/typeclasses/models.py`
  - `evennia-main/evennia/typeclasses/attributes.py`
  - `evennia-main/evennia/typeclasses/tags.py`
- Objects / Accounts
  - `evennia-main/evennia/objects/models.py`
  - `evennia-main/evennia/objects/objects.py`
  - `evennia-main/evennia/accounts/models.py`
  - `evennia-main/evennia/accounts/accounts.py`
- Commands
  - `evennia-main/evennia/commands/command.py`
  - `evennia-main/evennia/commands/cmdparser.py`
  - `evennia-main/evennia/commands/cmdset.py`
  - `evennia-main/evennia/commands/cmdhandler.py`
- Scripts / Scheduling
  - `evennia-main/evennia/scripts/scripts.py`
  - `evennia-main/evennia/scripts/taskhandler.py`
  - `evennia-main/evennia/scripts/tickerhandler.py`
  - `evennia-main/evennia/scripts/ondemandhandler.py`
- Locks / Comms / Help
  - `evennia-main/evennia/locks/lockhandler.py`
  - `evennia-main/evennia/comms/models.py`
  - `evennia-main/evennia/comms/comms.py`
  - `evennia-main/evennia/help/models.py`
  - `evennia-main/evennia/help/filehelp.py`
- Server / Session / Web
  - `evennia-main/evennia/server/session.py`
  - `evennia-main/evennia/server/serversession.py`
  - `evennia-main/evennia/server/sessionhandler.py`
  - `evennia-main/evennia/server/inputfuncs.py`
  - `evennia-main/evennia/server/service.py`
  - `evennia-main/evennia/server/portal/service.py`
  - `evennia-main/evennia/server/portal/portalsessionhandler.py`
  - `evennia-main/evennia/server/evennia_launcher.py`
  - `evennia-main/evennia/web/api/views.py`
  - `evennia-main/evennia/web/api/serializers.py`
- Prototypes / Spawner
  - `evennia-main/evennia/prototypes/prototypes.py`
  - `evennia-main/evennia/prototypes/spawner.py`

## 4. 总体判断

Evennia 6.0 最有价值的不是整套运行框架，而是以下抽象：

- 统一实体模型
- 基于上下文的命令解析与命令来源合并
- 房间移动与外观渲染的标准 hook 顺序
- Evennia Prototype 的继承与标准化思路，以及 New_Mud Blueprint 的显式契约
- 帮助系统、频道系统与后台内容管理流程

Evennia 6.0 最不适合直接沿用的部分是：

- `Portal/Server + AMP + Twisted` 双进程架构
- 运行时动态改写 `__class__` 的 typeclass 机制
- 把大量业务状态放进 Attribute/pickle
- 用通用 `Script` 模型承担定时器、系统对象、后台服务、Daemon 映射
- 过于依赖字符串 DSL，例如 lockstring、nick 模板、文本命令入口

## 5. 文档导航

1. `01_BORROW_REWRITE_MATRIX.md`
   - Evennia 各模块“复用语义 / 保留思想重写 / 放弃”的决策矩阵。
2. `02_ARCHITECTURE.md`
   - 新引擎总体分层、进程模型、模块边界与目录建议。
3. `03_RUNTIME_SESSIONS.md`
   - 连接、认证、角色进入世界、Presence 与多端同步模型。
4. `04_DOMAIN_WORLD_MODEL.md`
   - 实体、房间、出口、角色、物品、地图与区域组织模型。
5. `05_COMMAND_INTERACTION.md`
   - 命令系统、结构化动作、文本适配器与上下文解析。
6. `06_CONTENT_CHAT_HELP.md`
   - Blueprint、帮助系统、聊天域与内容制作工作流。
7. `07_SCHEDULER_EFFECTS.md`
   - 调度、周期任务、Buff/状态、世界事件与 Daemon 替代方案。
8. `08_PERMISSIONS_ADMIN_API.md`
   - 权限、后台、REST/WebSocket 契约与安全边界。
9. `09_MUDLIB_CONVERTER.md`
   - MUDLib 接口与 LPC 转换器设计。
10. `10_ROADMAP.md`
   - 开放式 Engine Stage 实施路线、需求追溯、验收标准与首批编码顺序。
11. `11_PROTOCOL_CATALOG.md`
   - WebSocket 请求、事件、错误 envelope 与动作解析的冻结协议目录。
12. `12_REGISTRY_BLUEPRINT_CONTRACT.md`
   - `manifest.py`、typed registries、`Blueprint` schema、发布与生效契约。
13. `13_SESSION_AUTH_STATE_MACHINE.md`
   - `ConnectionSession / AuthSession / Presence / PresenceSnapshot` 的实施级状态机。
14. `14_COMBAT_SKILL_ITEM_CONTRACT.md`
   - 战斗、武学、物品、持久化边界与首发玩法纵切。
15. `15_FRONTEND_H5_CONTRACT.md`
   - H5 客户端工程、状态 store、协议接入、双端布局与首发流程。
16. `16_OPERATIONS_TESTING_CONTRACT.md`
   - 可观测性、备份恢复、发布门禁、黄金测试与上线验收。
17. `17_REQUIREMENTS_TRACEABILITY.md`
   - 稳定需求 ID，以及 V6（必要时回链 V5 历史）、实施合同、里程碑和验收证据的映射。
18. `18_IMPLEMENTATION_STATUS.md`
   - 当前实现、环境基线、验证证据、已知警告和阻塞项。
19. `19_V6_CONTRACT_DIFFERENCES.md`
   - V6 相对 V5 的合同同步差异和对应落点；不取代 11-16 的冻结语义。

### 5.1 过程与交接文档

- `NEXT_SESSION_HANDOFF.md`
  - 新会话的最小阅读顺序、工作树边界和当前续作入口。
- `PHASE2_CONTENT_STARTUP_WORKLOG.md`
  - `Engine Stage E0 / Slice 2` 的实施过程快照；不作为需求或完成证明。

20. `../20_evennia_modernity_assessment.md`
   - Evennia 6.0 的现代性、历史包袱与项目适配边界；它是分析入口，不覆盖本目录的设计权威。

## 6. 与现有分析文档的关系

仓库现有 `docs/01` 到 `docs/18` 更接近 Evennia 源码模块分析与初步项目判断。

本目录 `docs/new_engine/` 的定位更靠后一步：

- 不再重复“Evennia 有什么”。
- 直接回答“New_Mud 新引擎应该怎么设计与实现”。
- 可作为后续建模、编码、拆 issue 和排迭代的主文档集。

## 7. 使用原则

后续真正开始写代码时，优先遵守以下约束：

- 借鉴 Evennia 的语义、处理顺序和经过验证的不变量，不引入 Evennia 运行依赖或运行时对象形状。
- 优先显式 ORM 模型与服务边界，避免再造 `obj.db.xxx` 式魔法层。
- 优先结构化事件与 WebSocket 消息，不把文本命令当唯一主入口。
- 优先单逻辑运行时的 `ASGI/Channels` 方案，不回退到 Portal/Server 双进程。
- 当前基线按单实例单写者实现；若未来为了部署形态拆分进程，再补显式协调机制。
- 优先把 MUDLib 与转换器的落点想清楚，再写引擎核心表结构。
- 涉及协议、registry、Blueprint 发布、会话、玩法、H5 或运维验收的实现，以 11-16 六份实施合同优先于概念说明文档。
- 产品范围与验收结果以 V6 为准；实施字段和机制以对应冻结合同为准，具体冲突处理遵守 `docs/19_documentation_governance.md`。


