# Plan: M0 收口与 E1 连接闭环

> Source PRD: `requirements_v5.md`；实施路线：`docs/new_engine/10_ROADMAP.md`。
>
> 冻结合同：`docs/new_engine/11_PROTOCOL_CATALOG.md`、`12_REGISTRY_BLUEPRINT_CONTRACT.md`、`13_SESSION_AUTH_STATE_MACHINE.md`、`15_FRONTEND_H5_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md`。

## Architectural decisions

以下决策跨越全部阶段，不在单个切片中重新解释或放宽：

- **部署边界**：保持单实例、单写者、单 MUDLib；没有 Redis channel layer 时只运行一个 ASGI 逻辑进程。
- **持久真源**：PostgreSQL 18 是持久状态权威；连接态 `ConnectionSession` 和活动 `Presence` 留在内存，`AuthSession`、`PresenceSnapshot`、内容 revision 与发布批次按冻结合同持久化。
- **内容身份**：启动内容只能来自受审计 seed、immutable published revision、exact dependencies 与完整 `ContentReleaseBatch`；新选择读取 active batch，已钉定对象读取 exact historical revision。
- **REST 路由**：首发认证入口固定为 `/api/v1/auth/register`、`/api/v1/auth/login`、`/api/v1/auth/refresh` 和 `/api/v1/auth/logout`。
- **WebSocket 协议**：连接后依次使用 `session.authenticate`、`presence.enter`、`session.resume`；跨设备替换只能使用显式 `presence.takeover`。
- **认证边界**：注册不隐式登录；login 创建 AuthSession 与唯一 RefreshTokenFamily；access token 只在内存，Refresh Token 只进入受保护 Cookie 与 refresh/logout REST 边界。
- **账号与角色**：首发每个 GameAccount 最多一个 Character，同时最多一个 `active` 或 `grace_disconnected` Presence 租约。
- **客户端**：uni-app + Vue 3 H5 与服务端共享机器合同；PC 与移动浏览器在同一纵向切片内验收，不维护独立业务语义。
- **失败语义**：协议错误码、终结重放、generation、ticket 和 takeover 语义只引用冻结合同，不在实现中创建平行枚举。
- **证据规则**：每个阶段必须同时提交需求 ID、迁移/合同兼容证据、自动测试和可重复执行命令；结构门禁通过不等同于阶段完成。

---

## Phase 1: E0 非功能证据收口

**User stories**: 作为发布负责人，我可以看到经过批准且身份明确的最低浏览器、容量和恢复基线，并能通过自动门禁确认这些基线不是待定占位符。覆盖 `MILESTONE-001`、`CLIENT-001`、`NFR-001`、`NFR-002`。

### What to build

完成三个非功能 profile 的评审与机器可读证据链。浏览器矩阵冻结精确测试版本和视口，容量 profile 冻结负责人、适用环境与批准状态，恢复预算通过一次隔离恢复演练绑定不可变报告。运营人员通过同一 M0 校验入口查看结果；无真实执行证据时继续失败，不允许用人工备注绕过。

### Acceptance criteria

- [ ] 三个 profile 均包含负责人、批准日期、非 pending 状态和可回查依据。
- [ ] PC 与移动浏览器条目均填写精确 tested versions，并保持 V5 要求的视口、中文输入和无障碍最低范围。
- [ ] 在隔离环境完成 PostgreSQL 备份恢复演练，记录数据集身份、开始/结束时间、实测 RPO/RTO、校验结果和报告哈希。
- [ ] 恢复报告满足既有 schema，并由恢复预算通过不可变身份引用。
- [ ] M0 校验不再报告 profile 审批、浏览器版本或恢复报告缺失。
- [ ] 所有证据都能在 CI 或等价受控环境中复核，不依赖开发者机器的绝对路径。

---

## Phase 2: E0 受审计内容启动闭环

**User stories**: 作为服务器运营人员，我可以从受审计内容包首次启动一个实例；重复启动不会重复导入，新对象读取活动批次，已有钉定对象在发布切换后仍读取原 revision。覆盖 `CONTENT-001`、`WORLD-001`、`MILESTONE-001`。

### What to build

实现从已冻结 seed 制品到 PostgreSQL 活动发布真源、再到运行时读取的最窄完整路径。首次启动原子创建 seed revisions、exact dependency records、完整 release batch 与活动指针；后续启动只验证和读取。提供 active-batch 与 pinned-revision 两种解析路径，并通过运营可见的启动/健康结果暴露内容身份与失败原因。

### Acceptance criteria

- [ ] 空实例首次启动只能从 schema 与哈希均通过的受审计 seed 创建一个完整活动批次。
- [ ] 同一 `(instance_id, mudlib_key)` 重复启动保持幂等，不产生重复 revisions、依赖行、批次或活动指针漂移。
- [ ] 新 spawn 和 batch-scoped 读取只解析当前 active batch 中的 exact published revisions。
- [ ] 已钉定实例在活动批次切换后仍解析原 historical revision 及其两类 exact dependencies。
- [ ] 缺少活动批次、哈希不一致、依赖缺失或 compiler contract 不匹配时启动明确失败。
- [ ] PostgreSQL 约束测试、服务集成测试和启动级端到端测试覆盖成功、重试、篡改和批次切换路径。
- [ ] Phase 1 与本阶段全部通过后，E0 才能从 `blocked` 转为完成，并同步状态账本与需求追踪索引。

---

## Phase 3: E1 注册与独立登录闭环

**User stories**: 作为新玩家，我可以在 H5 注册账号，再独立登录、刷新会话并退出；注册成功不会让我处于已登录状态。覆盖 `AUTH-001`、`AUTH-002`、`CLIENT-001`、`MILESTONE-002`。

### What to build

交付从 H5 表单到 REST、持久身份、token 轮换和错误展示的完整认证生命周期。注册原子创建用户与 GameAccount；login 创建 AuthSession、唯一 RefreshTokenFamily、短期 access token 与受保护 Refresh Cookie；refresh 轮换同一 family 内的 credential generation；logout 通过 Cookie 与可选 Bearer 双定位幂等收敛。

### Acceptance criteria

- [ ] 注册校验用户名和密码，原子创建 User/GameAccount，且不创建 AuthSession、token 或隐式登录状态。
- [ ] login 为账号创建符合唯一性约束的 AuthSession 与 RefreshTokenFamily，并返回短期 access token。
- [ ] Refresh Token 只存在于受保护 Cookie，不进入 WebSocket payload、响应 JSON、本地持久存储或 Authorization header。
- [ ] refresh 每次轮换 credential generation，旧凭据重放按冻结状态机终结相关 family/session。
- [ ] logout 在 access token 存在、仅 Cookie 存在、凭据已终结及重复请求情况下均幂等收敛。
- [ ] H5 在 PC 和移动视口完成注册、独立登录、刷新与退出，并展示机器错误码对应的明确失败状态。
- [ ] 数据库约束、API 集成、安全属性和浏览器端到端测试全部通过。

---

## Phase 4: E1 创建角色、连接、进入与恢复闭环

**User stories**: 作为已登录玩家，我可以创建唯一角色，建立 WebSocket，进入起始房间并取得完整最小状态；断线后可以在新连接上安全重建。覆盖 `AUTH-003`、`WORLD-001`、`CLIENT-001`、`MILESTONE-002`。

### What to build

将身份、唯一角色、WebSocket 会话、E0 起始 Room 与 H5 权威 store 连成一个纵向路径。连接先创建 ConnectionSession，再用 access token 绑定 AuthSession；角色进入时建立 Presence 与持久 PresenceSnapshot，返回原子 scene/character snapshot。断线进入 grace 状态，新连接使用一次性 resume ticket 重建，不依赖旧进程内对象或事件补齐。

### Acceptance criteria

- [ ] 每个 GameAccount 最多创建一个 Character，并保留明确的 CharacterOwnership 关系。
- [ ] 新 WebSocket 在认证前只有 ConnectionSession，`session.authenticate` 成功后才绑定现有 AuthSession。
- [ ] `presence.enter` 只允许账号拥有的角色，并从 E0 活动批次解析起始 Room 的 exact revision。
- [ ] 首次进入返回完整且自洽的 scene/character snapshot，H5 只在 snapshot 屏障完成后替换权威 store。
- [ ] 网络断开原子关闭旧 Presence 并写入 grace PresenceSnapshot；`session.resume` 在新连接上轮换 ticket 与 generation。
- [ ] 同一角色已有 active/grace 租约时，普通 enter 返回 `CHARACTER_OCCUPIED`，不会隐式接管。
- [ ] REST、WebSocket、数据库并发、断线恢复及 PC/移动 H5 端到端测试全部通过。

---

## Phase 5: E1 跨设备占用与显式接管闭环

**User stories**: 作为在另一设备重新登录的玩家，我能看见角色已被占用并主动确认接管；接管成功后新设备取得唯一控制权，旧设备明确失权。覆盖 `AUTH-003`、`CLIENT-001`、`MILESTONE-002`。

### What to build

在 Phase 4 的单 Presence 租约上增加显式 takeover 纵向流程。H5 对 `CHARACTER_OCCUPIED` 展示确认交互；获授权请求在一个事务中替换租约、generation、resume ticket 与 PresenceSnapshot，并写入事务 outbox。提交后通知旧连接，失败或并发竞争保持单一赢家和可恢复状态。

### Acceptance criteria

- [ ] 占用错误只提供明确状态和允许的下一步，不泄露其他账号或连接信息。
- [ ] 只有显式、已认证且拥有角色的 `presence.takeover` 请求可以替换现有租约。
- [ ] 租约、generation、ticket、snapshot 与 outbox 在同一原子提交中收敛，失败时不留下双 active 状态。
- [ ] 提交后旧连接收到 `presence.taken_over` 并失去后续动作权限；通知失败不回滚新权威状态。
- [ ] 两个并发 takeover 至多一个成功，失败方获得稳定机器错误且不能复用旧 ticket。
- [ ] H5 在两台浏览器上下文完成占用提示、确认接管、新端同步和旧端失权端到端验证。
- [ ] Phase 3-5 的认证、恢复和 takeover 证据共同满足 E1 连接闭环；状态账本和追踪索引按实际结果更新。

---

## Out of scope

本计划不把 E2 及之后的完整移动、物品、聊天、帮助、战斗、调度、Blueprint 后台、转换黄金差分或生产发布门禁提前塞入 E1。Phase 4 只实现进入与恢复所必需的最小 Character、Room 和 snapshot；后续玩法继续按 `10_ROADMAP.md` 形成新的纵向计划。
