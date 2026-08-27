# Plan: M0 收口与 E1 连接闭环

> Source PRD: `requirements_v6.md`；`requirements_v5.md` 仅作历史基线；实施路线：`docs/new_engine/10_ROADMAP.md`。
>
> 冻结合同：`docs/new_engine/11_PROTOCOL_CATALOG.md`、`12_REGISTRY_BLUEPRINT_CONTRACT.md`、`13_SESSION_AUTH_STATE_MACHINE.md`、`15_FRONTEND_H5_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md`。

## Architectural decisions

以下决策跨越全部阶段，不在单个切片中重新解释或放宽：

- **部署边界**：保持单实例、单写者、单 MUDLib；没有 Redis channel layer 时只运行一个 ASGI 逻辑进程。
- **持久真源**：PostgreSQL 18 是持久状态权威；连接态 `ConnectionSession` 和活动 `Presence` 留在内存，`AuthSession`、`PresenceSnapshot`、内容 revision 与发布批次按冻结合同持久化。
- **内容身份**：启动内容只能来自受审计 seed、immutable published revision、exact dependencies 与完整 `ContentReleaseBatch`；新选择读取 active batch，已钉定对象读取 exact historical revision。
- **REST 路由**：认证基线修订的目标入口包括 registration-verification request、register、login、refresh、logout 与 password-reset request/confirm；Issue #15 已把旧 recover/rotate 切换为统一 410 兼容期，兼容路由仍须在 Public V1 前删除。
- **WebSocket 协议**：连接后依次使用 `session.authenticate`、`presence.enter`、`session.resume`；跨设备替换只能使用显式 `presence.takeover`。
- **认证边界**：新注册先验证 email 并创建 VerifiedContactMethod，注册与密码重置都不隐式登录；login 创建 AuthSession 与唯一 RefreshTokenFamily；每个受保护入口验证 active AuthSession，access token 只在内存，Refresh Token 只进入受保护 Cookie 与 refresh/logout REST 边界。
- **账号与角色**：首发每个 GameAccount 最多一个 Character，同时最多一个 `active` 或 `grace_disconnected` PresenceSnapshot 租约。
- **客户端**：uni-app + Vue 3 H5 与服务端共享机器合同；PC 与移动浏览器在同一纵向切片内验收，不维护独立业务语义。
- **失败语义**：协议错误码、终结重放、generation、ticket 和 takeover 语义只引用冻结合同，不在实现中创建平行枚举。
- **证据规则**：每个阶段必须同时提交需求 ID、迁移/合同兼容证据、自动测试和可重复执行命令；结构门禁通过不等同于阶段完成。

---

## Engine Stage E0 / Slice 1: 非功能证据收口

**Status**: `completed`（2026-08-25）

**User stories**: 作为发布负责人，我可以看到经过批准且身份明确的最低浏览器、容量和恢复基线，并能通过自动门禁确认这些基线不是待定占位符。覆盖 `MILESTONE-001`、`CLIENT-001`、`NFR-001`、`NFR-002`。

### What to build

完成三个非功能 profile 的评审与机器可读证据链。浏览器矩阵从官方版本源冻结精确目标组合和视口，实际 `tested_versions` 留给发布候选测试填写；容量 profile 冻结负责人、适用环境与批准状态；恢复预算通过一次隔离恢复演练绑定不可变 M0 基础设施报告。运营人员通过同一 M0 校验入口查看结果，校验器同时保留浏览器、容量与完整业务恢复尚未执行的边界。

### Acceptance criteria

- [x] 三个 profile 均包含负责人、批准日期、非 pending 状态和可回查依据。
- [x] PC 与移动浏览器条目均冻结精确 `target_versions`，保持 V6 要求的视口、中文输入和无障碍最低范围，并明确不伪造 `tested_versions`。
- [x] 在隔离环境完成 PostgreSQL 备份恢复演练，记录数据集身份、开始/结束时间、实测 RPO/RTO、校验结果和报告哈希。
- [x] 恢复报告满足独立 schema，由恢复预算通过路径、报告 ID 与 SHA-256 引用，并明确不具备发布门禁资格。
- [x] M0 合同校验不再报告 profile 审批、浏览器目标版本或恢复基础设施报告缺失。
- [x] 演练脚本与证据引用不依赖开发者机器绝对路径，可在 CI 或等价受控环境复核。

---

## Engine Stage E0 / Slice 2: 受审计内容启动闭环

**Status**: `completed`（2026-08-25；Issues #1-#5）

**User stories**: 作为服务器运营人员，我可以从受审计内容包首次启动一个实例；重复启动不会重复导入，新对象读取活动批次，已有钉定对象在发布切换后仍读取原 revision。覆盖 `CONTENT-001`、`WORLD-001`、`MILESTONE-001`。

### What to build

实现从已冻结 seed 制品到 PostgreSQL 活动发布真源、再到运行时读取的最窄完整路径。首次启动原子创建 seed revisions、exact dependency records、完整 release batch 与活动指针；后续启动只验证和读取。提供 active-batch 与 pinned-revision 两种解析路径，并通过运营可见的启动/健康结果暴露内容身份与失败原因。

### Acceptance criteria

- [x] 空实例首次启动只能从 schema 与哈希均通过的受审计 seed 创建一个完整活动批次。
- [x] 同一 `(instance_id, mudlib_key)` 重复启动保持幂等，不产生重复 revisions、依赖行、批次或活动指针漂移。
- [x] 新 spawn 和 batch-scoped 读取只解析当前 active batch 中的 exact published revisions。
- [x] 已钉定实例在活动批次切换后仍解析原 historical revision 及其两类 exact dependencies。
- [x] 缺少活动批次、哈希不一致、依赖缺失或 compiler contract 不匹配时启动明确失败。
- [x] PostgreSQL 约束测试、服务集成测试和启动级端到端测试覆盖成功、重试、篡改和批次切换路径。
- [x] Engine Stage E0 / Slice 1 与本阶段全部通过后，产品 M0 已同步为 `complete`，`MILESTONE-001` 与 `ENGINE-001 / Engine Stage E0` 已同步为 `verified`；两套状态保持独立。

---

## Engine Stage E1 / Slice 1: 注册与独立登录闭环

**Status**: `completed`（2026-08-26；Issue #9）

本节保持 Issue #9 当时的历史措辞和验收事实。RecoveryCode 后续被 Issue #10/ADR-0005 取代，不再是现行实现授权。

**User stories**: 作为新玩家，我可以在 H5 注册账号，再独立登录、刷新会话并退出；注册成功不会让我处于已登录状态。覆盖 `AUTH-001`、`AUTH-002`、`CLIENT-001`、`MILESTONE-002`。

### What to build

交付从 H5 表单到 REST、持久身份、token 轮换和错误展示的完整认证生命周期。注册原子创建用户与 GameAccount；login 创建 AuthSession、唯一 RefreshTokenFamily、短期 access token 与受保护 Refresh Cookie；refresh 轮换同一 family 内的 credential generation；logout 通过 Cookie 与可选 Bearer 双定位幂等收敛。

### Acceptance criteria

- [x] 注册校验用户名和密码，原子创建 User/GameAccount，且不创建 AuthSession、token 或隐式登录状态。
- [x] 注册事务一次性签发明文 `RecoveryCode`，服务端只保存不可逆哈希；恢复或主动轮换时生成新 code，并撤销旧 AuthSession、RefreshTokenFamily 与未使用票据、终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence。
- [x] login 为账号创建符合唯一性约束的 AuthSession 与 RefreshTokenFamily，并返回短期 access token。
- [x] Refresh Token 只存在于受保护 Cookie，不进入 WebSocket payload、响应 JSON、本地持久存储或 Authorization header。
- [x] refresh 每次轮换 credential generation，旧凭据重放按冻结状态机终结相关 family/session。
- [x] logout 在 access token 存在、仅 Cookie 存在、凭据已终结及重复请求情况下均幂等收敛。
- [x] H5 在 PC 和移动视口完成注册、独立登录、刷新与退出，并展示机器错误码对应的明确失败状态。
- [x] 数据库约束、API 集成、安全属性和浏览器端到端测试全部通过。

---

## Engine Stage E1 / Auth Baseline Amendment: 已验证联系方式注册与账号恢复

**Status**: `in_progress`（2026-08-27；Issue #10；Issues #11–#15 已完成，#16 正在复审收口）

**User stories**: 作为新玩家，我先验证邮箱再创建账号；作为忘记密码的玩家，我通过已验证邮箱重置密码并让全部旧认证立即失效；作为普通玩家，我始终使用账号名和密码登录，不需要理解“独立登录”或 RecoveryCode。覆盖 `AUTH-005`、`CLIENT-001`、`MILESTONE-002`。

### What to build

按原生阻塞链完成六张 ticket：Issue #11 修订权威；#12 建立 challenge/outbox/crypto/限流投递 tracer；#13 完成已验证邮箱注册；#14 完成密码重置与即时认证撤销；#15 原子退役 RecoveryCode 并切换 H5；#16 完成分层证据。当前 #16 已执行门禁并修复首轮双轴 hard findings，正式复审和 Issue 回填尚未完成，`AUTH-005=implemented`。

#16 正式复审、回填和关闭前，Character Slice 2 仍阻塞且尚未认领或实现。

### Acceptance criteria

- [x] Issue #11 将 V6、冻结合同、追踪、状态、差异、计划与交接统一到 VerifiedContactMethod/VerificationChallenge，并保留 Issue #9 历史。
- [x] #12 交付 email challenge、独立密钥、加密联系方式/lookup、PostgreSQL 持久限流/outbox、worker 与非枚举 request。
- [x] #13 最终 register 原子消费 challenge，创建 User/GameAccount/VerifiedContactMethod，返回零认证状态，并完成 H5 注册/普通登录文案。
- [x] #14 password reset 原子撤销跨实例全部 AuthSession/family/credential，旧 access/refresh 立即失败，通知投递失败不回滚密码；Git `638e8cf` 与 `docs/new_engine/18_IMPLEMENTATION_STATUS.md` 保留实现和验证证据。
- [x] #15 两个旧 RecoveryCode 端点统一 410，现有开发 code 全撤销；注册/reset 由两类 live worker heartbeat 与共享 provider circuit 原子门禁，生产启动 fail closed，普通登录保持可用。
- [ ] #16 已完成 PostgreSQL 并发、迁移、静态、全量、E2E、秘密扫描和可选 SMTP smoke 边界；SMTP 因未获显式 opt-in/收件人/秘密授权记录为 1 skipped。首轮双轴 hard findings 已修复，待正式复审和 Issue 回填，完整证据见 `docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md`。
- [x] SMS、联系方式换绑、账号关闭/重开、Character、Presence、PresenceRecovery 与 takeover 均未提前实现。

---

## Engine Stage E1 / Slice 2: Character Slice 2——创建角色、连接、进入与恢复闭环

**Blocked by**: Auth Baseline Amendment Issue #16 的正式复审、回填与关闭。当前切片尚未认领或实现。

**User stories**: 作为已登录玩家，我可以创建唯一角色，建立 WebSocket，进入起始房间并取得完整最小状态；断线后可以在新连接上安全重建。覆盖 `AUTH-003`、`WORLD-001`、`CLIENT-001`、`MILESTONE-002`。

### What to build

将身份、唯一角色、WebSocket 会话、E0 起始 Room 与 H5 权威 store 连成一个纵向路径。连接先创建 ConnectionSession，再用 access token 绑定 AuthSession；角色进入时建立 Presence 与持久 PresenceSnapshot，返回原子 scene/character snapshot。断线进入 grace 状态，新连接使用一次性 resume ticket 重建，不依赖旧进程内对象或事件补齐。

### Acceptance criteria

- [ ] 每个 GameAccount 最多创建一个 Character，并保留明确的 CharacterOwnership 关系。
- [ ] 角色创建通过版本化 `CharacterCreationProfile`，提交 `CharacterDisplayName` 及仅用于展示的性别/代词；名称按 NFKC、实例内唯一和 V6 字符策略校验，`RetiredCharacter` 不得自助重建。
- [ ] 新 WebSocket 在认证前只有 ConnectionSession，`session.authenticate` 成功后才绑定现有 AuthSession。
- [ ] `presence.enter` 只允许账号拥有的角色，并从 E0 活动批次解析起始 Room 的 exact revision。
- [ ] 首次进入返回完整且自洽的 scene/character snapshot，H5 只在 snapshot 屏障完成后替换权威 store。
- [ ] 网络断开关闭旧运行时 Presence，并把对应 PresenceSnapshot 转为 grace；`session.resume` 在新连接上轮换 ticket 与 generation。
- [ ] 页面刷新丢失内存 `resume_ticket` 时，同一 AuthSession 可调用 `presence.recover`；成功轮换 ticket/generation 并返回完整 snapshot，找不到自有租约时返回 `PRESENCE_RECOVERY_UNAVAILABLE`，不得跨会话接管。
- [ ] 同一角色已有 active/grace 租约时，普通 enter 返回 `CHARACTER_OCCUPIED`，不会隐式接管。
- [ ] REST、WebSocket、数据库并发、断线恢复及 PC/移动 H5 端到端测试全部通过。

---

## Engine Stage E1 / Slice 3: 跨设备占用与显式接管闭环

**User stories**: 作为在另一设备重新登录的玩家，我能看见角色已被占用并主动确认接管；接管成功后新设备取得唯一控制权，旧设备明确失权。覆盖 `AUTH-003`、`CLIENT-001`、`MILESTONE-002`。

### What to build

在 Engine Stage E1 / Slice 2 的单 PresenceSnapshot 租约上增加显式 takeover 纵向流程。H5 对 `CHARACTER_OCCUPIED` 展示确认交互；获授权请求在一个事务中替换租约、generation、resume ticket 与 snapshot，并写入事务 outbox。提交后关闭旧运行时 Presence、通知旧连接；失败或并发竞争保持单一赢家和可恢复状态。

### Acceptance criteria

- [ ] 占用错误只提供明确状态和允许的下一步，不泄露其他账号或连接信息。
- [ ] 只有显式、已认证且拥有角色的 `presence.takeover` 请求可以替换现有租约。
- [ ] 租约、generation、ticket、snapshot 与 outbox 在同一原子提交中收敛，失败时不留下双 active 状态。
- [ ] 提交后旧连接收到 `presence.taken_over` 并失去后续动作权限；通知失败不回滚新权威状态。
- [ ] 两个并发 takeover 至多一个成功，失败方获得稳定机器错误且不能复用旧 ticket。
- [ ] H5 在两台浏览器上下文完成占用提示、确认接管、新端同步和旧端失权端到端验证。
- [ ] Engine Stage E1 / Slices 1-3 的认证、恢复和 takeover 证据共同满足 E1 连接闭环；状态账本和追踪索引按实际结果更新。

---

## Out of scope

本计划不把 E2 及之后的完整移动、物品、聊天、帮助、战斗、调度、Blueprint 后台、转换黄金差分或生产发布门禁提前塞入 E1。Auth Baseline Amendment 不实现 SMS、联系方式换绑、账号关闭/重开或任何 Character/Presence 行为；Character Slice 2 只实现进入与恢复所必需的最小 Character、Room 和 snapshot；后续玩法继续按 `10_ROADMAP.md` 形成新的纵向计划。
