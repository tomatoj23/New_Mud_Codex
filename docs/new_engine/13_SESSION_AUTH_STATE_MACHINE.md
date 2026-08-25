# 13 会话、认证与 Presence 状态机

> 状态：`Engine Stage E0-E1` 必须冻结的实施级契约。本文负责 `ConnectionSession / AuthSession / Presence / PresenceSnapshot`、access/refresh token、`resume_ticket`、多端占用、接管、登出和崩溃恢复；协议信封与终结规则以 `11_PROTOCOL_CATALOG.md` 为准。

## 1. 核心不变量

1. `ConnectionSession` 是物理 WebSocket，`AuthSession` 表示已认证账号会话，`Presence` 表示当前角色控制上下文；三者不能合并。
2. `Presence` 是运行时对象。PostgreSQL 中的 `PresenceSnapshot` 是恢复租约与临时检查点，不是世界实体或角色权威状态。
3. 角色位置、属性、物品、装备和已提交结算始终以 PostgreSQL 领域表为准。
4. 首发每个 `GameAccount` 最多拥有一个角色；仍保留 `CharacterOwnership`，以后只能通过显式迁移放宽上限。
5. 一个 `GameAccount` 跨全部 AuthSession、连接和设备，同时最多有一个 `active` 或 `grace_disconnected` 的 Presence 租约。
6. 一个 `AuthSession` 和一个 `Character` 也分别最多有一个 `active` 或 `grace_disconnected` 的 Presence 租约。
7. `resume_ticket` 是单次使用秘密，只向客户端返回明文，数据库只保存 hash。
8. 断线不能生成客户端从未收到的新秘密；恢复使用客户端在 `presence.enter` 或上一次恢复时已经持有的 ticket。
9. 新 WebSocket 已创建新的 `ConnectionSession`；`session.resume` 只把恢复出的 Presence 绑定到该连接，不能再创建第二个连接对象。
10. 进程崩溃后不复活内存对象，不恢复半完成攻击；从 snapshot 与数据库安全创建新的运行时 Presence。
11. `session.authenticate` 只按 `ConnectionSession` 本地幂等；跨连接必须重新校验 token 并重新执行绑定。
12. `presence.enter / session.resume / presence.recover / presence.takeover` 的历史终结不得把新连接伪装成已绑定，也不得隐式触发 takeover。
13. 所有会创建或重新绑定 Presence 的路径都先创建 inert `pending_enter`；提交前不得接受命令、订阅或接收广播、注册调度或派发领域事件。
14. REST refresh 的网络重试与攻击 replay 必须由持久幂等终结记录区分，不能把同一逻辑请求的安全重试误判为 token replay。
15. 依赖 active Presence 的终结必须绑定精确 generation；`state.sync` 还绑定来源 ConnectionSession 与 seq 屏障，不能跨上下文重放 snapshot。
16. REST register 只原子创建 User、GameAccount 与 RecoveryCode 哈希，不进入本状态机，不得隐式创建 AuthSession、refresh family、Character 或 Presence；RecoveryCode 明文只在注册响应出现一次。
17. 在每个游戏实例内，一个 User 永久映射一个 GameAccount；CharacterOwnership 是未来多 Character 的唯一扩展边界。
18. `presence.recover` 只恢复同一 AuthSession 自己的 active/grace Presence；它不接受跨会话接管。找不到自有可恢复租约时统一返回 `PRESENCE_RECOVERY_UNAVAILABLE`，不得把恢复流程当作普通 enter 或隐式 takeover。
19. GameAccount 生命周期为 `active -> cooling_off -> retired`；关闭立即撤销该 User 的全部 AuthSession、Presence、ticket 和 refresh family。只有有效 RecoveryCode 能在冷静期内恢复到 `active`，恢复不会自动复活旧 Presence。

## 2. 对象与存储边界

### 2.1 `ConnectionSession`

职责：

- 表示一条物理 WebSocket。
- 持有连接本地 `seq`、速率限制、客户端能力、IP 与 user agent 摘要。
- 绑定零个或一个 `AuthSession`。
- 绑定零个或一个当前 `Presence`。

状态：

```text
opening -> active -> closing -> closed
```

建立 socket 时创建，consumer ready 后进入 `active`。主动关闭、空闲超时、协议错误和网络异常都先进入 `closing`，清理后进入 `closed`。它只存在于运行时，关键边界写结构化审计。

### 2.2 `AuthSession`

职责：

- 表示一次已认证设备会话和 OOC 能力。
- 关联 `User`、`GameAccount`、设备信息与恰好一个 lifetime refresh family。
- 是认证后请求幂等键的作用域。

持久状态：

```text
active -> revoked
active -> expired
active -> logged_out
```

REST 登录创建 `active` AuthSession，并按 `08_PERMISSIONS_ADMIN_API.md` 4.2 由服务端生成随机 opaque `device_id`；
不得用 IP、User-Agent 或浏览器指纹作为该标识。access token 过期不等于 AuthSession 立即失效；
refresh family replay、风控或管理员操作进入 `revoked`，绝对 TTL 到期进入 `expired`，当前设备主动登出进入 `logged_out`。

### 2.3 `Presence`

职责：

- 表示某个 AuthSession 通过某条 ConnectionSession 正在控制一个 Character。
- 承载命令、移动、IC 聊天、战斗和场景订阅上下文。
- 从 Character 权威位置计算场景，不维护第二份 canonical room id。

运行时状态：

```text
pending_enter -> active
active -> taken_over -> closed
active -> closed
```

网络断开后，运行时 Presence 被解绑并关闭；逻辑控制租约转由 `PresenceSnapshot.state=grace_disconnected` 表达。实现可以短暂保留缓存对象，但正确性与恢复不得依赖该对象仍存在。

`pending_enter` 只能持有已准备好的不可变上下文和待激活计划。它不进入命令路由、场景 group、广播目标、战斗/调度注册表或 active Presence 索引，也不能对外产生可观察副作用。只有数据库提交成功后，才能通过 5.2 的本地原子切换进入 `active`。

### 2.4 `PresenceSnapshot`

职责：

- Presence 活跃期间保存最小恢复检查点。
- 异常断线或进程崩溃后提供有界 grace 租约。
- 协调跨连接、跨 AuthSession 和跨设备的唯一占用。

它不是 Character、Item 或 Combat 主表，不是长期行为日志，不恢复半完成战斗，也不替代 Character canonical location。

持久状态：

```text
active -> grace_disconnected -> active
active -> taken_over -> closed
active -> closed
grace_disconnected -> taken_over -> closed
grace_disconnected -> closed
```

恢复到 `active` 表示创建并绑定新一代运行时 Presence；不是复活已经死亡的 Python 对象。

## 3. 默认时间参数

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `WS_HEARTBEAT_INTERVAL_S` | `20` | 客户端应用 ping 建议周期 |
| `WS_IDLE_TIMEOUT_S` | `60` | 连接空闲关闭阈值 |
| `ACCESS_TOKEN_TTL_MIN` | `15` | access token TTL |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | refresh family 最长有效期 |
| `PRESENCE_GRACE_TTL_S` | `120` | 异常断线恢复窗口 |
| `PRESENCE_ACTIVATION_TIMEOUT_S` | `10` | 已提交 pending 激活必须终结或补偿的上限 |
| `WS_REQUEST_RETRY_WINDOW_HOURS` | `24` | 认证后 WebSocket request id 幂等重试窗口 |
| `REFRESH_REQUEST_RETRY_WINDOW_HOURS` | `24` | REST refresh 同 key 网络重试窗口 |
| `TERMINAL_SECRET_CLEANUP_GRACE_HOURS` | `24` | secret reference 失效后的最短清理缓冲 |

`resume_ticket` 在 Presence 活跃时不单独倒计时。进入 grace 时，它的 `expires_at` 与 `PresenceSnapshot.grace_expires_at` 使用同一截止时间，避免两套 TTL 漂移。

`PRESENCE_ACTIVATION_TIMEOUT_S` 只允许 1-30 的整数，`activation_deadline_at` 必须使用提交事务的数据库时钟精确计算为 `now + timeout`，提交后不得续期。到期立即进入 5.3 的补偿候选，不能把 timeout 当成仅告警阈值。

## 4. 持久结构

### 4.1 `AuthSession`

| 字段 | 说明 |
|------|------|
| `id` | AuthSession id |
| `user_id` | 认证主体 |
| `game_account_id` | 游戏域账号 |
| `device_id` | 受控设备标识 |
| `refresh_family_id` | lifetime 唯一 RefreshTokenFamily id |
| `state` | `active / revoked / expired / logged_out` |
| `issued_at / last_seen_at` | 创建与最近活动 |
| `absolute_expires_at` | 会话绝对到期 |
| `revoked_at / revoke_reason` | 可空撤销信息 |
| `version` | 乐观并发版本 |

登录事务提交后，AuthSession 与 RefreshTokenFamily 必须形成不可变的一一对应关系。两侧引用使用 deferrable 外键或等价 deferred constraint trigger 校验，不能在登录之外补建、换绑或替换 family。

### 4.2 `RefreshTokenFamily` 与 `RefreshTokenCredential`

`RefreshTokenFamily` 至少包含 `id`、`auth_session_id`、`state`、`current_generation`、`absolute_expires_at`、`revoked_at`、`revoke_reason` 和 `version`。

state 只允许 `active / revoked / expired`；`auth_session_id` 与 `absolute_expires_at` 创建后不可变，family 截止时间不得晚于 AuthSession。终态 family 不得回到 active。

`RefreshTokenCredential` 至少包含 `id`、`family_id`、`generation`、`token_hash`、`jti_hash`、`state`、`issued_at`、`used_at`、`expires_at`、`replaced_by_id` 和 `version`。

credential 状态为 `active / used / revoked / expired`；`family_id` 与 generation 创建后不可变，refresh 只追加 generation，不新建 family。明文 refresh token 永不落库。

### 4.3 `RefreshRequestTerminalRecord`

每个逻辑 REST refresh 必须持久化独立终结记录，至少包含：

| 字段 | 说明 |
|------|------|
| `family_id` | RefreshTokenFamily id |
| `idempotency_key` | 安全格式的请求幂等键 |
| `canonical_request_hash` | endpoint 版本、credential 身份与规范化输入的 SHA-256 |
| `predecessor_credential_id` | 本次消费的旧 credential |
| `successor_credential_id` | 成功轮换出的 credential；失败时为空 |
| `access_claims_json` | 成功时固定的 access token claims；不含明文 token |
| `terminal_kind / error_code` | `succeeded / failed` 与稳定错误码 |
| `created_at / expires_at` | 创建时间与幂等保留窗口 |

`family_id + idempotency_key` 必须唯一。成功轮换、旧 credential 置为 used、successor credential、family generation、固定 access claims 与该终结记录必须在同一 PostgreSQL 事务提交。access/refresh token 明文都不得写入该记录。

family、credential 与 terminal history 至少保留到 family 绝对到期加 secret cleanup grace，且直到引用清空。family 身份行作为 AuthSession 的 tombstone，在 AuthSession 删除前不得硬删除。

清理 token material 或终结记录不能为同一 AuthSession 腾出重建 family 的空间。used/revoked credential 的 hash/JTI 可用于 logout 定位，但不能恢复为可用 credential。

### 4.4 `PresenceSnapshot`

| 字段 | 说明 |
|------|------|
| `id` | snapshot / 租约 id |
| `presence_id` | 当前逻辑 Presence id |
| `generation` | 每次 enter、resume、recover 或 takeover 递增 |
| `auth_session_id` | 当前控制会话 |
| `game_account_id` | 跨设备唯一约束键 |
| `character_id` | 当前角色 |
| `state` | `active / grace_disconnected / taken_over / closed` |
| `scene_scope` | 恢复提示，不是 canonical location |
| `transient_state_json` | 最小订阅、UI focus 等短期状态 |
| `runtime_instance_id` | 最后持有它的进程启动 id |
| `checkpointed_at` | 最近检查点 |
| `disconnected_at / grace_expires_at` | 可空断线与截止时间 |
| `disconnect_reason` | 可空稳定原因码 |
| `version` | 并发版本 |

活跃期间也必须存在 snapshot 并按状态边界或有界节流策略检查点，否则进程崩溃没有可恢复租约。`transient_state_json` 只允许 schema 白名单字段。

### 4.5 `ResumeTicketCredential`

| 字段 | 说明 |
|------|------|
| `id` | 凭据 id |
| `snapshot_id` | 对应恢复租约 |
| `auth_session_id` | 签发时 AuthSession |
| `game_account_id / character_id` | 账号与角色绑定 |
| `generation` | ticket 代次 |
| `token_hash` | 明文 ticket hash |
| `key_id` | 密钥管理器 key 标识 |
| `state` | `active / used / revoked / expired` |
| `issued_at / used_at / expires_at` | 生命周期时间 |
| `replaced_by_id` | 轮换后的 credential |
| `version` | 并发版本 |

数据库不保存明文 ticket。ticket 可由 credential id、generation 和 `key_id` 指向的密钥确定性物化，物化后必须核对 `token_hash`。`RequestTerminalRecord` 只保存 credential 引用。密钥保留期必须覆盖相关 ticket 与终结记录的最长有效期，否则安全重放无法完成。

### 4.6 `SessionEventOutbox`

enter/resume/recover/takeover 事务内必须为需要通知的旧连接或状态订阅者写 outbox。记录至少包含
`id`、`request_terminal_record_id`、`event_type`、`delivery_class`、`target_connection_session_id`、脱敏 `payload_json`、`dedupe_key`、`state`、`attempt_count`、`created_at` 与 `delivered_at`；
`state` 至少支持 `pending / delivering / delivered / canceled`。

`delivery_class` 只允许：

- `activation_success`：`presence.entered`、`session.resumed` 以及任何声称新 Presence 已可用的事件。dispatcher 只有在关联终结记录为 `activation_state=active` 时才可领取；`activation_pending` 时保持 pending，`compensated` 时原子改为 `canceled`，永不投递。
- `committed_revocation`：只表达事务提交即已成立且补偿也不会逆转的旧端失权事实。首发仅允许发给旧连接的 `presence.taken_over`；事务提交后即可领取，即使关联终结仍为 `activation_pending` 或后来变为 `compensated`，也不得暗示新端已经激活。

`dedupe_key` 唯一，outbox 不保存 token 或 ticket。dispatcher 可先无锁读取候选 id，
但领取时必须按 `RequestTerminalRecord -> SessionEventOutbox(dedupe_key)` 的顺序在同一数据库事务加锁并重读终结状态，不能仅凭 outbox 行已经提交就发送。
事务回滚时 outbox 一并消失；允许投递的事件提交后幂等发送。投递失败不能回滚已经提交的领域状态，接收端通过下一请求的 Presence 校验或重连同步收敛。

### 4.7 PostgreSQL 约束

必须提供：

- `PresenceSnapshot(game_account_id) WHERE state IN ('active', 'grace_disconnected')` 的 partial unique constraint。
- `PresenceSnapshot(auth_session_id) WHERE state IN ('active', 'grace_disconnected')` 的 partial unique constraint。
- `PresenceSnapshot(character_id) WHERE state IN ('active', 'grace_disconnected')` 的 partial unique constraint。
- `ResumeTicketCredential(snapshot_id) WHERE state = 'active'` 的 partial unique constraint。
- `RefreshTokenFamily(auth_session_id)` 唯一约束，并以 deferred 约束保证它与 `AuthSession.refresh_family_id` 对称且不可变。
- `RefreshTokenCredential(family_id, generation)` 唯一约束。
- `RefreshTokenCredential(family_id) WHERE state = 'active'` 的 partial unique constraint。
- `RefreshRequestTerminalRecord(family_id, idempotency_key)` 唯一约束。
- `SessionEventOutbox(dedupe_key)` 唯一约束。

首发必须对 `CharacterOwnership(game_account_id)` 建唯一约束，使每个 GameAccount 最多拥有一个角色；未来放宽上限必须通过显式数据库迁移，不能只改前端或配置。

迁移若发现同一 AuthSession 已有多个 family，必须阻断并进入人工修复，不能静默选择“最新”family。

### 4.8 终结记录保留与清理

`RequestTerminalRecord.expires_at` 不得早于 `created_at + WS_REQUEST_RETRY_WINDOW_HOURS`。`RefreshRequestTerminalRecord.expires_at` 不得早于以下两者的较晚值：

- `created_at + REFRESH_REQUEST_RETRY_WINDOW_HOURS`
- `RefreshTokenFamily.absolute_expires_at + TERMINAL_SECRET_CLEANUP_GRACE_HOURS`

即使 `expires_at` 已到，清理器也只能在以下条件全部满足时删除：

- 终结不是 `activation_pending`；pending 必须先由 5.3 正常激活或稳定补偿。
- 所有关联 outbox 已是 `delivered` 或 `canceled`。
- 所有 secret reference 已不可交付，且对应 credential 进入 used/revoked/expired 后已满 `TERMINAL_SECRET_CLEANUP_GRACE_HOURS`。
- 被终结记录引用的 credential 行不得先于该终结记录删除。
- 用于确定性物化和 hash 校验的密钥仍保留到记录实际删除完成。

因此，引用仍 active 的 resume ticket 会阻止对应 `RequestTerminalRecord` 清理；refresh terminal 至少保留到 family 绝对到期后的缓冲结束，安全同 key 重试不能因后台清理被降级为攻击 replay。清理器必须按主键稳定顺序分批加锁且可重入。配置只能延长未来重试窗口；缩短配置不得回写既有 `expires_at` 或提前删除既有记录。

## 5. 认证与入场

首次使用者先按 `08_PERMISSIONS_ADMIN_API.md` 4.2 完成 register，再调用独立 login。已有账号直接从 login 开始。

固定流程：

```text
REST login / refresh
  -> obtain valid access token
  -> open /ws/v1/game
  -> create ConnectionSession
  -> session.authenticate(access token)
  -> bind AuthSession
  -> presence.enter(character_id)
  -> prepare inert pending_enter + snapshot/ticket/outbox plan
  -> commit PresenceSnapshot + credential + activation_pending terminal
  -> atomically activate and bind prepared Presence
  -> return delivery.status=bound + ticket + complete snapshot
```

规则：

- refresh token 只可作为 REST refresh 的轮换凭据，或作为 REST logout 的受保护 Cookie locator；不得进入 WebSocket 或 Authorization header。
- `session.authenticate` 只绑定 AuthSession，不自动创建 Presence。
- `presence.enter` 锁定 AuthSession 与 GameAccount，校验 CharacterOwnership 和首发单角色约束。
- GameAccount 已有 active/grace 租约时，普通 enter 返回 `CHARACTER_OCCUPIED`。
- 入场租约、ticket credential、`activation_pending` 请求记录与 outbox 必须原子提交。
- `presence.entered` 是无 request id 的状态事件，不能替代 `request.succeeded`。

### 5.1 `session.authenticate` 的连接本地幂等

`session.authenticate` 始终使用 `(connection_session_id, request_id)`，并沿用 `11` 的 request id 语法与请求 hash。首次成功必须先校验 access token 和 AuthSession 状态，再绑定当前连接。

同一连接以相同 id 和 hash 重试时，服务端必须确认当前连接仍绑定记录中的 active AuthSession；绑定缺失时幂等补绑后才可重放成功。绑定到其他 AuthSession、token payload 冲突或 AuthSession 已失效时，不得重放旧成功。

新 WebSocket 的 `ConnectionSession` id 不同。即使客户端复用旧 `request_id`，也必须重新校验 token 并给新连接执行绑定；旧连接的本地终结不能命中，更不能把旧连接绑定副作用重放到新连接。

### 5.2 Presence 准备、提交与激活

`presence.enter`、`session.resume`、`presence.recover` 与 `presence.takeover` 共用以下协议；recover 额外要求租约属于当前 AuthSession：

1. 按操作规定的锁序校验 AuthSession、GameAccount、Character、snapshot、ticket 和占用版本。
2. 创建 inert `pending_enter`，完成所有可能失败的权限、canonical location、snapshot 投影、路由计划、调度计划、ticket 元数据、终结 payload 与 outbox 序列化准备；此时不安装任何计划。
3. 事务内写入租约变化、credential、`RequestTerminalRecord.activation_state=activation_pending`、`activation_owner_runtime_instance_id`、`activation_deadline_at = now + PRESENCE_ACTIVATION_TIMEOUT_S`、审计和所需 `SessionEventOutbox`，然后提交。
4. 任一准备或提交失败都回滚数据库、销毁 `pending_enter`，且不得发送终结成功或领域事件。takeover 在此边界前不得关闭旧 runtime Presence、撤销其内存路由或通知旧端，因此回滚后旧端继续可用。
5. 提交后调用 `activate_prepared_presence`。该操作必须是单线程、无 await、无外部 I/O、无动态分配的本地原子切换：安装预构建路由与调度计划、绑定新 ConnectionSession、切换 active Presence 索引，并在 takeover 时同时移除旧端命令能力。正常路径按设计不可失败。
6. 激活完成后把终结记录转为 `active`，才可交付 `delivery.status=bound` 的 `request.succeeded`，并释放 `activation_success` outbox。对来源连接，输出串行器必须先排入终结响应，再排入无 request id 的成功状态事件。任何重放在此之前都只能在 deadline 内有界等待或触发恢复，不能读取准备中的成功 payload。

若激活或终结 finalization 仍发生非预期异常，必须关闭并移除新 runtime Presence，并在补偿事务中把新 snapshot 置为 `closed`、撤销新 ticket、
将终结记录转为 `compensated + request.failed(PRESENCE_ACTIVATION_FAILED)`，同时取消全部 `activation_success` outbox。
补偿完成前不交付成功；补偿后也不得重放原准备 payload。takeover 已提交时不自动复活旧租约，`committed_revocation` 通知仍有效，
旧端通过通知、下一请求校验或重连收敛。

outbox 在原事务内写入；提交后严格按 4.6 的 `delivery_class` 门禁幂等投递。独立 worker 不得在 `activation_pending` 时发送成功类事件。投递失败只记录重试，不回滚已经提交的状态切换；旧端没有收到 `presence.taken_over` 时，下一次需要 Presence 的请求仍必须通过 snapshot/generation 校验失败，重连后再以权威状态收敛。

### 5.3 `activation_pending` 崩溃恢复

`activation_pending` 不允许依赖原请求协程最终返回。启动协调器必须在接受新 WebSocket/Presence 建立请求前扫描一次，运行期间由 lease sweeper 持续扫描。以下任一条件成立即为待补偿候选：

- `activation_owner_runtime_instance_id` 已不在存活实例租约集合中。
- `activation_deadline_at <= now`，无论 owner 进程是否仍存活。

sweeper 按 `AuthSession -> GameAccount -> PresenceSnapshot -> ResumeTicketCredential -> RequestTerminalRecord -> SessionEventOutbox` 取行锁，
并重验终结仍为 `activation_pending`、snapshot/generation/credential 仍匹配且 owner 已死亡或 deadline 已到。
若同一进程仍残留新 runtime Presence，先以无 await、无 I/O 的本地切换移除其命令路由、订阅、调度和连接绑定；随后在一个补偿事务中：

1. 将本次新 `PresenceSnapshot` 置为 `closed`，释放 GameAccount、AuthSession 与 Character 的 active/grace 唯一占用。
2. 将本次新 `ResumeTicketCredential` 置为 `revoked`；已经消费的 predecessor 不复活。
3. 将终结记录固定为 `compensated + request.failed(PRESENCE_ACTIVATION_FAILED)`，清除任何可交付成功 payload。
4. 将关联 `activation_success` outbox 改为 `canceled`；`committed_revocation` 仍按 4.6 投递。
5. 写脱敏恢复审计并提交。

该补偿必须可重入且与正常 finalization 竞争安全：锁定后若终结已经是 `active` 或 `compensated` 就不重复处理。
不得从持久字段重建 `pending_enter` 或再次尝试激活，因为预构建路由/调度计划不是持久权威；不得无限等待原 owner，也不得重放准备阶段的成功。
若进程在本地激活后、把终结转为 `active` 前崩溃，同样走本节补偿；若终结已是 `active` 后才崩溃，则走第 7 节的 active snapshot grace 收敛。

## 6. Resume ticket 生命周期

### 6.1 签发

明文 `resume_ticket` 只在 `presence.enter`、成功 `session.resume`、成功 `presence.recover` 和 `presence.takeover` 的终结结果中签发。它绑定 snapshot、AuthSession、GameAccount、Character 与 generation，不能跨账号或角色使用。

### 6.2 异常断线

异常断线事务：

1. 关闭并解绑 ConnectionSession。
2. snapshot 从 `active` 改为 `grace_disconnected`。
3. 设置 `disconnected_at` 和 `grace_expires_at = now + PRESENCE_GRACE_TTL_S`。
4. 将现有 active ticket 的 `expires_at` 设为相同截止时间。
5. 写脱敏审计。

该流程不创建新 ticket，也不改变客户端已知 ticket。主动 `presence.leave`、登出或接管不是可恢复断线，必须关闭租约并撤销 ticket。

### 6.3 恢复顺序

```text
REST refresh when needed
  -> open new WebSocket
  -> ConnectionSession already exists
  -> session.authenticate(valid access token)
  -> session.resume(existing resume_ticket)
  -> prepare inert pending_enter for new Presence generation
  -> consume old credential and rotate new ticket
  -> commit activation_pending terminal and outbox
  -> atomically activate and bind to existing ConnectionSession
  -> return delivery.status=bound + new ticket + complete snapshot
```

`session.resume` 不接受 refresh token，也不隐式刷新 access token。若 access token 过期：

- `session.authenticate` 返回 `TOKEN_EXPIRED`。
- 不读取或消费 resume ticket。

### 6.4 PresenceRecovery

页面刷新或客户端内存清理可能丢失 `resume_ticket`。同一 AuthSession 在完成 `session.authenticate` 后可提交无 ticket 的 `presence.recover`。服务端按 `AuthSession -> GameAccount -> Character -> PresenceSnapshot` 锁序查找该会话自己的 `active` 或 `grace_disconnected` 租约；成功时递增 generation、撤销旧 ticket、创建新 ticket 并复用 5.2 的 pending/commit/activate 事务。恢复不跨 AuthSession 迁移控制权，也不把另一会话的占用转化为成功。无自有可恢复租约时返回 `PRESENCE_RECOVERY_UNAVAILABLE`，统一对外响应。
- 客户端先走 REST refresh，再认证和恢复。

### 6.5 恢复事务与并发

事务固定锁序：

```text
AuthSession
  -> GameAccount
  -> PresenceSnapshot
  -> ResumeTicketCredential
```

锁定后校验：

- AuthSession 仍为 `active`，并属于 ticket 绑定的 GameAccount。
- snapshot 为未过期的 `grace_disconnected`，版本匹配。
- ticket 为 `active`，hash、generation、绑定和期限匹配。
- GameAccount、AuthSession 与 Character 没有另一条 active/grace 租约。
- 当前进程可以完成 5.2 的全部 pending Presence 准备。

成功路径遵循 5.2；数据库事务内原子执行：

1. 旧 credential 置为 `used`。
2. snapshot 写入 pending Presence 的新 `presence_id`、递增 generation、改为 `active`，并更新 AuthSession、runtime instance 和 checkpoint。
3. 创建下一代 active `ResumeTicketCredential`，并记录旧 credential 的 `replaced_by_id`。
4. 保存带来源 ConnectionSession、Presence generation、新 credential 引用和 `activation_pending` 的 `RequestTerminalRecord`。
5. 写入需要的 `SessionEventOutbox` 与审计记录。
6. 提交后执行 5.2 的原子激活；只有终结记录变为 `active`，才返回新 ticket、完整 snapshot 和 `delivery.status=bound`，并可发送无 request id 的 `session.resumed`。

行锁、`version` 检查与 partial unique constraints 必须同时使用。并发恢复只有一个赢家；失败者不创建 Presence、不生成 ticket、不覆盖赢家。

同一 `request_id` 的重试由终结记录交付，不再次消费 ticket。当前连接与记录绑定不匹配时，必须按 `11` 返回 `resume_required` 或 `superseded` 投影，不能把历史 snapshot 绑定到当前连接。不同 request id 并发使用同一旧 ticket 时，失败者返回 `SESSION_RESUME_FAILED` 或不泄露内部状态的 ticket 错误。

## 7. 崩溃恢复

进程崩溃后：

- 该进程的 ConnectionSession 与 runtime Presence 全部消失。
- 启动协调器先按 5.3 补偿死亡实例遗留的 `activation_pending`，再接受新的 Presence 建立请求。
- Character、位置、物品、装备和已提交结算继续来自 PostgreSQL。
- 启动协调器把死亡 `runtime_instance_id` 的 `active` snapshot 转为 `grace_disconnected` 并设置有界截止。
- 现有 active ticket 随 snapshot 获得相同截止时间，不生成新 ticket。
- 认证和 resume 后创建新的 runtime Presence，不能复活旧对象。
- `scene_scope` 和 transient state 只是提示，必须按 canonical Character location 重新校验和订阅。
- CombatInstance 安全结束，不恢复半完成攻击；已提交结算保留，遵循 `14_COMBAT_SKILL_ITEM_CONTRACT.md`。

清理任务将过期 grace snapshot 置为 `closed`，对应 ticket 置为 `expired`，释放 GameAccount、AuthSession 和 Character 占用。清理遵循固定锁序并可重复执行。

## 8. 显式接管

`presence.takeover` 是独立、显式确认的请求；普通进入不能自动升级为接管。

准备、事务与激活步骤：

1. 按 `AuthSession -> GameAccount -> PresenceSnapshot -> ResumeTicketCredential` 锁序取行。
2. 重验权限、CharacterOwnership 和占用版本，按 5.2 创建并完整准备 inert `pending_enter`。
3. 事务内把旧 snapshot 置为 `taken_over`、撤销旧 active ticket，创建新 generation 的 active snapshot 与 ticket credential。
4. 同一事务保存带 `activation_pending` 的接管终结记录、安全审计，以及定向旧连接、分类为 `committed_revocation` 的 `presence.taken_over` outbox；提交前不关闭旧 runtime Presence，也不移除旧端命令路由。
5. 任一步失败或事务回滚时销毁 pending Presence；旧 snapshot、ticket、runtime Presence 和路由均保持原状，旧端继续可用。
6. 提交后在一次无 I/O 本地原子切换中移除旧端能力、激活并绑定新 Presence，再把终结记录转为 `active`。
7. 新连接只有在第 6 步完成后才收到含 `delivery.status=bound`、新 ticket 与完整 snapshot 的 `request.succeeded`。
8. `committed_revocation` outbox 在提交后即可幂等投递，因为旧租约和 ticket 的撤销不会被激活补偿逆转；它不得声称新端已经 active。成功类事件仍须等终结为 `active`。投递失败不回滚接管；旧端下一请求返回 `PRESENCE_NOT_ACTIVE`，或在重连时按权威 snapshot 收敛。

旧 AuthSession 可保留 OOC 登录态，但失去角色控制权。旧连接后续 IC 请求返回 `PRESENCE_NOT_ACTIVE`，不能收到推送错误信封。

## 9. Refresh family 旋转与 replay

一个 AuthSession 终身只有一个 family；本节旋转只推进该 family 的 credential generation，不创建或替换 family。

每个逻辑 REST refresh 必须携带 `Idempotency-Key`。语法冻结为 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`，即 1-128 个安全 ASCII 字节；空白、控制字符、非 ASCII 与其他字符以 `REFRESH_IDEMPOTENCY_KEY_INVALID` 拒绝。一次逻辑刷新及其网络重试复用同一 key；新的逻辑刷新必须生成新 key。

服务端先以 token hash/JTI 只读解析 predecessor credential 与 family，再按以下顺序锁定：

```text
RefreshTokenFamily
  -> RefreshRequestTerminalRecord(family_id, idempotency_key)
  -> RefreshTokenCredential
```

锁定后必须先处理终结记录，再判断 credential 的 used 状态：

1. 已有同 key 记录但 `canonical_request_hash` 不同，返回 `REFRESH_IDEMPOTENCY_CONFLICT`；不轮换 token，也不撤销 family。
2. 已有同 key、同 hash 的成功记录，且其 successor credential 仍是当前 active generation，按记录中的 credential 引用与固定 access claims 重新物化同一逻辑 access/refresh 结果；不再次消费或轮换。
3. 已有同 key、同 hash 的成功记录，但 successor 已被后续刷新消费、撤销、过期或不再是当前 generation，返回稳定 `REFRESH_REQUEST_SUPERSEDED`；不返回旧秘密，也不得把该安全重试判为 replay 或撤销 family。
4. 没有匹配终结记录时，只有 family active、predecessor credential active 且 generation 正好等于 `current_generation` 才能执行新轮换。
5. 新轮换在一个事务内把 predecessor 置为 `used`、创建 generation + 1 successor、更新 family、固定 access claims，并写入 `RefreshRequestTerminalRecord` 后提交。
6. 只有在没有同 key 匹配终结记录的情况下，再次提交 used predecessor，才视为 `REFRESH_TOKEN_REPLAYED`。使用不同 key 重放旧 token 也属于此类攻击路径。

`REFRESH_TOKEN_REPLAYED` 是内部安全判定与审计原因。它必须在事务内撤销整个 RefreshTokenFamily 与 AuthSession，
关闭 active/grace Presence 租约，撤销 resume ticket，并关闭连接或让后续请求返回 `SESSION_REVOKED`；
REST 对外也只返回 `SESSION_REVOKED`，不暴露 replay 取证细节。同时写不含 token、ticket 或私密 payload 的高优先级安全审计。

`RefreshRequestTerminalRecord` 只保存 credential 引用和固定 claims。明文 token 不落库；同 key 重放使用确定性物化并核对 hash。若固定 access token 已过期，客户端使用当前 successor 发起带新 key 的下一次逻辑 refresh，不能修改旧终结的 claims 或复用旧 key。

## 10. 离场、登出与封禁

`presence.leave` 关闭 runtime Presence，将 snapshot 置为 `closed`，撤销 ticket 并退出场景 group；AuthSession 保持 active，可继续 OOC。

当前设备登出以 refresh Cookie 和正常有效 access Bearer 作为独立 locator，按 `auth_session_id` 稳定排序锁定并撤销两者识别出的候选集合。Cookie 与 Bearer 指向不同会话时撤销两者；used predecessor 只用于显式撤销，不进入 refresh replay 判定。

active 候选的 lifetime family 与 active credentials 置为 revoked，AuthSession 置为 `logged_out`，并在同一事务关闭 active/grace 租约和撤销 ticket；连接提交后关闭。

候选已是 revoked/expired/logged_out 时不覆盖原终态，只幂等收敛子记录。零个 locator 可识别时统一 `204` 并清客户端，但不能声称服务端未知会话已撤销。端点、Cookie 与 no-store 语义由 `08` 4.2 冻结。

AuthSession 到达 `absolute_expires_at` 时，清理任务必须将其置为 `expired`，关闭该会话的 active/grace 租约并撤销 resume ticket；否则过期会话会继续占住 GameAccount 的 partial unique constraint。该清理遵循与 resume 相同的固定锁序并可重入。

全局封禁或管理员撤销按稳定顺序处理 User 的全部 AuthSession、refresh family、连接、active/grace 租约和 resume ticket，并审计操作者、原因、关联请求和前后状态。

### 10.1 RecoveryCode 与 GameAccount 生命周期

REST 路径及请求 / 响应外形以 `08_PERMISSIONS_ADMIN_API.md` 4.4 为准；本节冻结它们的状态机和事务语义：

- `POST /api/v1/auth/recover` 只在 RecoveryCode 验证成功且 GameAccount 仍为 `active` 时更新密码。旧 code 在同一事务消费，生成的新 code 取代它，并撤销该 User 的全部 AuthSession、RefreshTokenFamily、active/grace Presence 与未使用 ticket；成功后必须重新 login 和 enter。
- `POST /api/v1/auth/recovery-code/rotate` 要求调用者属于仍为 `active` 的 AuthSession 与 GameAccount。成功事务撤销旧 code、生成新 code，并撤销包括调用会话在内的全部旧 AuthSession、refresh family、Presence 与 ticket；响应只一次展示新 code，客户端随后处于登出状态。
- `POST /api/v1/account/close` 锁定并把 `active` GameAccount 改为 `cooling_off`，记录 `cooling_off_started_at / reopen_deadline_at`，立即执行同样的全会话与控角撤销。关闭不消费当前有效 RecoveryCode，因为它是冷静期内 reopen 的唯一玩家证明。
- `POST /api/v1/account/reopen` 只接受 `cooling_off` 且未超过 30 天 `reopen_deadline_at` 的 GameAccount。有效 code 在同一事务消费，账号回到 `active`，生成并一次展示替代 code；不得恢复旧 AuthSession、Presence、Character 控制上下文或任何已撤销 ticket。

服务端只保存 RecoveryCode 的不可逆 hash、generation、`active / used / revoked` 状态、版本和必要审计时间；明文只在注册或成功替换 code 的响应中出现一次。recover、rotate 和 reopen 的 code 消费与新 hash 创建必须和密码 / lifecycle 变化及全部撤销在一个 PostgreSQL 事务提交，任一步失败都整体回滚。重复使用旧 code、两个请求并发消费同一 generation，或 reopen 与退休任务竞跑时只能有一个赢家；失败者不得签发 code、改变密码、复活会话或覆盖赢家状态。

账号生命周期事务固定按 `GameAccount -> RecoveryCode hash -> AuthSession（按 id） -> RefreshTokenFamily / credential -> PresenceSnapshot（按 id） -> ResumeTicketCredential（按 id） -> CharacterOwnership / Character` 持锁，并用 row version 与唯一约束重验。login、refresh、Presence 建立及清理路径在提交前必须重读 GameAccount lifecycle/version；看到非 `active` 或版本已变化就回滚，因此恢复、关闭与退休提交后不会留下新建或漏撤销的会话。数据库选择的序列化 / deadlock loser 只能按稳定失败收敛，不能局部提交。

退休任务在 deadline 后按同一锁序把仍为 `cooling_off` 的 GameAccount 改为 `retired`，撤销 RecoveryCode，匿名化 / 禁用 User，并把 Character 置为 `RetiredCharacter`；稳定 id 与要求保留的历史关系不删除。`retired` 是终态，`account/reopen` 不得恢复它。reopen 先提交则退休任务重验后无操作；退休先提交则 reopen 不得把终态改回 `active`。

所有 RecoveryCode 验证在读取敏感账号状态前执行账号、IP 与设备合并限流，并返回相同结构、缓存策略与无账号存在性泄露的稳定错误。账号不存在、code 错误、code 已消费或敏感状态不可确认时不得暴露区别；只有持有有效 code 后才能返回窗口过期或不可 reopen 的状态错误。失败尝试不得锁死或改变正常密码登录，日志、指标和审计不得记录明文 code、密码、token 或 ticket。

M1 后台冻结 / 撤销与最小修复也必须使用本节同一锁序、RecoveryCode 验证和撤销事务。操作者可以冻结恢复尝试、撤销账号会话，或在玩家仍提交有效 code 时修复卡住的 recover 事务；不得读取或代填明文 code、绕过 code 校验、从游戏资料推断所有权、把账号转给其他 User，或在密码与 code 均丢失时生成替代凭据。后台修复成功与玩家 recover 相同：轮换 code、撤销全部旧会话与控角状态，且不自动创建 AuthSession / Presence；失败原子保持原状态。

## 11. 审计与脱敏

必须审计登录、refresh 与 replay、Presence enter/leave/grace、resume、takeover、登出、封禁、崩溃租约收敛和过期清理。

普通日志、审计 payload、指标 label 与异常上报禁止出现 access token、refresh token、resume ticket、Authorization header、Cookie、密码、验证码、手机号明文或无授权私聊正文。

可以记录 credential id、generation、key id、hash 不可逆短摘要、稳定错误码、AuthSession id、GameAccount id、request id 和 trace id。字段白名单与 `16_OPERATIONS_TESTING_CONTRACT.md` 一致。

## 12. 事务与事件顺序

- 数据库提交前不得发送成功终结或领域事件。
- 唯一约束、版本或锁竞争失败必须回滚，再以 `request.failed` 返回稳定错误码。
- `activation_pending` 不是成功终结；只有本地原子激活与 finalization 完成后才能交付 `delivery.status=bound`。
- 成功类 outbox 必须同时满足关联终结为 `active`；`activation_pending` 不投递，`compensated` 必须取消。只有不声称新端成功的 `committed_revocation` 可在提交后立即投递。
- Presence-required 终结重放必须先校验当前 active generation；`state.sync` 还必须校验来源连接与 barrier seq，失败按 `11` 返回 `REQUEST_CONTEXT_CHANGED`。
- 终结重放不重新广播 `session.resumed`、`presence.entered` 或接管事件。
- 非请求触发的断线、封禁或崩溃收敛只发送状态事件，不制造 request id。
- ticket 首次交付失败时，同一连接可用同一请求 ID 取回；跨连接重放只按 `11` 返回 `resume_required` 与仍安全可用的 ticket，不能返回可应用的历史 snapshot。
- enter/resume/takeover 的旧端通知只通过事务 outbox 按 4.6 门禁投递；投递失败不回滚状态，接收端依赖下一请求校验或重连同步收敛。

## 13. Engine Stage E1 必测场景

- REST register 原子创建 User 与 GameAccount，重复或非法账号名返回稳定错误，且不产生任何认证会话或 token 行。
- REST 登录、WebSocket authenticate、单角色 enter 与完整 snapshot。
- `session.authenticate` 同连接同请求重放确认绑定；跨连接复用 request id 仍重新验证 token 和绑定新连接。
- 同一 GameAccount 两个 AuthSession 并发 enter，只有一个获得 Presence。
- 即使未来拥有多个角色，同一 GameAccount 也不能跨设备同时控制两个 Presence。
- 断线不创建未知 ticket；120 秒内用已有 ticket 恢复。
- access token 过期时 ticket 不被消费，REST refresh 后仍可恢复。
- 相同 resume request 重放不重复消费 ticket，并返回同一逻辑新 ticket。
- 页面重载丢失 ticket 后，同一 AuthSession 的 `presence.recover` 递增 generation、撤销旧 ticket、签发新 ticket并返回完整 snapshot；另一 AuthSession、无自有 active/grace 租约或与 takeover 竞跑时统一失败且不泄露占用详情。
- enter/resume/recover/takeover 成功在其他 ConnectionSession 重放时不绑定新连接、不应用旧 snapshot，只返回 `resume_required`；新 request id 的 resume 成功后才进入 active。
- action/ui/sync 等 Presence-required 终结在新 generation 重放时不返回旧结果；`state.sync` 跨连接或 barrier 推进后要求新 request id。
- 两个不同 request id 并发使用同一 ticket，只有一个成功。
- grace 超时后 resume 失败并释放 partial unique 占用。
- takeover 原子撤销旧 ticket，旧端收到 `presence.taken_over`，新端取得完整 snapshot。
- 对 pending Presence 分别在准备、提交前、提交后激活和 finalization 注入失败；回滚保持 takeover 旧端可用，补偿路径关闭新 snapshot、撤销新 ticket 且不重放虚假成功。
- 在事务提交与 runtime 激活之间、激活与 finalization 之间分别杀死 owner 进程；启动扫描或超时 sweeper 必须稳定补偿、释放唯一占用，重复运行不重复副作用。
- outbox worker 抢在激活前运行时，`activation_success` 保持 pending；激活成功后只投递一次，补偿后改为 canceled 且永不发送。`committed_revocation` 可在 takeover 提交后发送，即使新端最终补偿。
- takeover outbox 投递失败不回滚接管；旧端下一请求或重连能收敛到非 active 状态。
- refresh 同 key 同 payload 安全重放，同 key 不同 payload 返回冲突，不同 key 重用 used token 才撤销 family、AuthSession、Presence 租约和 ticket。
- 并发路径不能为同一 AuthSession 创建第二个 family；family 终态不可复活，身份 tombstone 不可通过清理删除后重建。
- used refresh Cookie 可完成显式 logout；损坏 Cookie 加有效 access Bearer 仍撤销会话；Cookie/Bearer 指向不同会话时撤销候选集合。
- RecoveryCode recover/rotate 只允许一个并发 code 消费赢家，原子轮换 code 并撤销全部旧 AuthSession、RefreshTokenFamily、Presence 和 ticket；统一错误与账号/IP/设备合并限流不泄露账号存在性，也不锁死密码登录。
- M1 后台恢复测试覆盖角色权限、重新认证、reason/support case、冻结 / 撤销和持有效 code 的最小修复；无 code、越权、并发消费或故障注入都不能改密、重分配账号或产生新凭据。
- account close/reopen/retirement 覆盖 `active -> cooling_off -> active` 与 `active -> cooling_off -> retired` 两条边界、30 天截止竞跑、RetiredCharacter 和 reopen 后零 AuthSession / Presence。
- 两个 locator 都无效时仍统一 `204 / no-store` 并清 Cookie，且审计不得伪称已撤销无法定位的服务端会话。
- successor 已被后续轮换后，同 key 重试返回 `REFRESH_REQUEST_SUPERSEDED` 且不撤销 family。
- 终结清理在 24 小时重试边界、active ticket、family 绝对到期和 secret cleanup grace 各边界正确保留；`activation_pending` 只能先补偿，不能直接删除。
- 进程崩溃后创建新 runtime Presence，不复活旧对象。
- 崩溃不恢复半完成攻击，已提交物品与角色结算不丢失。
- 日志、审计、trace 与异常上报通过 token/ticket 脱敏扫描。
- PostgreSQL 真库验证 partial unique constraints、锁序、版本冲突和清理幂等。

## 14. Engine Stage E0-E1 实施门禁

`Engine Stage E0` 必须固化：

- 状态枚举、TTL、持久 schema、迁移、索引和 partial unique constraints。
- 24 小时 WebSocket/refresh 重试窗口、secret reference 清理缓冲、1-30 秒激活 deadline 与可重入终结清理器。
- token/ticket hash、密钥轮换与脱敏库。
- `session.authenticate` 连接本地幂等、`RequestTerminalRecord` Presence/连接/seq 与激活交付元数据、`RefreshRequestTerminalRecord` 和固定锁序基础设施。
- pending Presence 原子激活、dead-runtime/超时补偿、outbox delivery class 门禁与 `SessionEventOutbox`。
- PostgreSQL 契约测试环境。

`Engine Stage E1` 必须完成：

- register 与 login 的显式边界，以及注册后零认证会话不变量。
- enter、leave、resume、recover 与 takeover。
- refresh family 幂等旋转、superseded 结果和攻击 replay 撤销。
- active snapshot 检查点、崩溃收敛与 grace 清理。
- 稳定错误码及与 `11_PROTOCOL_CATALOG.md`、`15_FRONTEND_H5_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md` 的端到端契约测试。

`Engine Stage` 是新引擎设计/实施阶段，不等同于 `requirements_v6.md` 的产品里程碑 `M0-M6`。
