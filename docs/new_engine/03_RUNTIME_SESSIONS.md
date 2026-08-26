# 03 运行时与会话模型

> 术语说明：本文统一使用 `ConnectionSession / AuthSession / Presence / PresenceSnapshot / GameAccount`。`Account` 仅用于描述 Evennia 来源事实。

> 权威边界：本文只解释概念分层与流程意图。请求信封、终结结果和事件以 `11_PROTOCOL_CATALOG.md` 为准；状态、TTL、字段、接管与恢复条件以 `13_SESSION_AUTH_STATE_MACHINE.md` 为准。

本文不复制 11 或 13 的完整字段表、错误码和状态枚举。实施时必须直接引用两份合同，不能从本概念页反向推导协议。

## 1. 核心判断

Evennia 正确区分了连接、账号和角色控制，但用 `PortalSession -> ServerSession -> Account -> puppet` 双边同步实现。New_Mud 只保留分层语义，不保留双进程与会话镜像。

四类对象的存储边界固定如下：

| 对象 | 定位 | 权威存储 |
|:---|:---|:---|
| ConnectionSession | 一个物理 WebSocket 连接 | 仅运行时内存 |
| AuthSession | 已认证账号会话与 token family | PostgreSQL 持久事实源 |
| Presence | GameAccount 当前控角上下文 | 仅运行时内存 |
| PresenceSnapshot | grace 与崩溃恢复所需的短期快照 | PostgreSQL 短期持久化 |

运行时可以缓存 AuthSession，但数据库仍是事实源。PresenceSnapshot 不是世界实体、长期日志或角色权威状态。

## 2. 对象职责

### 2.1 ConnectionSession

新 WebSocket 建立后立即创建 ConnectionSession。它只负责：

- socket 生命周期、连接序号与输出串行化
- 客户端平台、能力、网络与限流上下文
- 接收结构化请求并发送终结结果或事件
- 在 access token 鉴权后绑定既有 AuthSession

连接关闭后销毁 ConnectionSession。不得为了恢复连接而创建持久 ConnectionSession 主表。

### 2.2 AuthSession

AuthSession 由 REST 账号密码登录创建，并持久化以下职责：

- 表达已登录的 User 与 GameAccount
- 持有设备、refresh token family 与撤销状态
- 承担认证后请求幂等和 OOC 能力的身份边界
- 为新 ConnectionSession 提供可验证的持久绑定目标

Refresh Token 仅可在 REST refresh 中轮换，或由 REST logout 从受保护 Cookie 读取为 AuthSession locator。WebSocket 只携带短期 access token 完成 `session.authenticate`，不得接收 Refresh Token。

### 2.3 Presence

Presence 表达一个 AuthSession 当前控制 Character 的运行时上下文，是命令、移动、战斗和 IC 聊天的主上下文。

房间位置从 Character 的权威状态解析。Presence 只持有订阅、焦点和运行时控制信息，不复制 canonical room id 或角色持久属性。

首发每个 GameAccount 最多一个 Character。跨全部 AuthSession、ConnectionSession 与设备，同一 GameAccount 同时最多有一个处于 `active` 或 `grace_disconnected` 的 PresenceSnapshot 租约。

### 2.4 PresenceSnapshot

PresenceSnapshot 在 Presence 活跃期间保存最小恢复检查点；断线或崩溃后，它以 `grace_disconnected` 表达有界恢复租约，并协调 GameAccount、AuthSession 与 Character 的唯一占用。

它不替代 Character、Room 与背包等持久真源，也不把运行时 CombatInstance 变成可恢复的持久状态。

快照结构、到期规则和清理策略由 `13_SESSION_AUTH_STATE_MACHINE.md` 冻结。本页不复制字段清单。

## 3. 登录与连接顺序

首发连接顺序固定为：

```text
REST 已验证邮箱注册（首次使用）
  -> 先消费 registration VerificationChallenge
  -> 原子创建 User、GameAccount 与 VerifiedContactMethod，不创建认证会话
REST 账号密码登录
  -> 创建 active 持久 AuthSession
  -> 签发 access token 与轮换 refresh token
  -> 建立新 WebSocket
  -> 创建运行时 ConnectionSession
  -> session.authenticate(access token)
  -> 绑定持久 AuthSession
  -> presence.enter / session.resume / presence.takeover
  -> 请求终结结果直接交付 ticket 与完整 snapshot
```

已有账号跳过 register。register 与 login 是两个独立事务；注册成功不表示已经登录。

access token 过期时，客户端先走 REST refresh 取得新 access token，再建立或重新认证 WebSocket。新 socket 不得凭 Refresh Token 或未验证的本地状态直接绑定 AuthSession。

建立 ConnectionSession 和绑定 AuthSession 不会自动恢复控角状态。客户端必须显式选择 enter、resume 或 takeover。

## 4. Resume Ticket

`presence.enter`、`presence.takeover` 与 `session.resume` 只有在当前连接首次以 `delivery.status=bound` 成功绑定时，才直接交付新的 `resume_ticket` 和完整 snapshot。跨连接终结重放可能返回 `resume_required` 并省略历史 snapshot；`superseded` 不交付 ticket 或 snapshot。具体投影以 `11_PROTOCOL_CATALOG.md` 第 4.1 节为准。

明文 ticket 只交给客户端。ResumeTicketCredential 行只保存不可逆 hash 与必要元数据，终结记录只保存 credential 引用；日志、审计、追踪和异常上报不得记录明文。

普通网络断线不旋转 ticket。只有成功的 enter、takeover 或 resume 才产生新的 ticket；resume 成功时消费旧 ticket。

请求重试、终结重放、ticket 单次消费和 secret 重新物化必须遵守 `11_PROTOCOL_CATALOG.md`。领域事件不能代替携带 ticket 的请求终结结果。

## 5. 多端、占用与显式接管

同一 User 可以保持多个 OOC AuthSession，但 GameAccount 的控角占用覆盖 `active` 与 `grace_disconnected` PresenceSnapshot 租约。

普通 `presence.enter` 遇到占用时返回 `CHARACTER_OCCUPIED`，不得静默踢线，也不得隐式升级为 takeover。

`presence.takeover` 必须携带显式确认并通过策略授权。成功流程必须按冻结合同原子收敛：

1. 事务内终止旧 PresenceSnapshot 租约；提交后旧运行时 Presence 失权并关闭，不能再恢复。
2. 事务内建立新 PresenceSnapshot 租约与恢复凭据；提交后激活并绑定新运行时 Presence。
3. 保存唯一请求终结结果与接管审计。
4. 写入向旧连接发送 `presence.taken_over` 的事务 outbox。

任一步失败都整体回滚。事务提交后由 outbox 通知旧连接。旧 AuthSession 默认保留 OOC 登录态，但失去角色控制权；是否同时撤销认证由独立安全策略决定。

## 6. 断线、恢复与崩溃

非主动断线时，ConnectionSession 关闭，运行时 Presence 被解绑并关闭；对应 PresenceSnapshot 从 `active` 转为 `grace_disconnected`。断线本身不生成或旋转 resume ticket。

恢复流程固定为：

1. 建立新 WebSocket 和运行时 ConnectionSession。
2. 必要时先通过 REST refresh 取得新 access token。
3. 以 access token 完成 `session.authenticate` 并绑定 AuthSession。
4. 提交携带现有 ticket 的 `session.resume`。
5. 由终结结果取得新 ticket 和完整 snapshot。

resume 必须校验持久 AuthSession、ticket 与 `grace_disconnected` PresenceSnapshot，再创建并绑定新一代运行时 Presence。即使原进程仍存活，也不得复活断线时已经关闭的 Presence 对象。

崩溃恢复不得把 PresenceSnapshot 当成完整世界状态。场景、角色与背包从各自持久真源重构；CombatInstance 不恢复，战斗与动作摘要按 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 安全回退后重建。

grace 到期、ticket 无效、快照过期或占用冲突必须按 `11_PROTOCOL_CATALOG.md` 与 `13_SESSION_AUTH_STATE_MACHINE.md` 返回稳定终结错误，不得静默新建控制上下文。

## 7. 运行时分组

Channels 层至少维护以下 group：

- `conn:{id}`
- `auth:{id}`
- `presence:{id}`
- `room:{id}`
- `channel:{id}`

group 是运行时路由索引，不是持久事实源。连接、Presence 关闭或 takeover 后必须及时解除旧订阅。

## 8. 输入输出信封

客户端请求必须包含 `version / request_id / type / payload`：

```json
{
  "version": 1,
  "request_id": "req_look_01",
  "type": "action.invoke",
  "payload": {
    "source": "text_command",
    "input": "look"
  }
}
```

服务端事件必须包含 `version / type / seq / ts / payload`，且领域事件不携带 `request_id`：

```json
{
  "version": 1,
  "type": "scene.snapshot",
  "seq": 44,
  "ts": "2026-07-19T09:30:01.000Z",
  "payload": {
    "scene_scope": "room:1001"
  }
}
```

请求终结结果额外携带顶层 `request_id`。完整 schema、序号语义、幂等与错误码只以 `11_PROTOCOL_CATALOG.md` 为准。

## 9. 为什么不保留 Evennia PortalSessionHandler

Evennia 的连接节流、DoS 防护和命令速率限制意识值得保留。以下实现不保留：

- Portal/Server 双边同步
- 基于 AMP 的 session 镜像
- 协议层与游戏层的双份 session 状态

New_Mud 在单 ASGI 进程内保持明确对象边界，并通过 PostgreSQL 保存 AuthSession 与短期恢复事实。

## 10. 安全与审计

会话层从首版落实：

- WSS only 与输入频率限制
- access token、Refresh Token、resume ticket 全链路脱敏
- Refresh Token replay 撤销整个 token family
- enter、resume、takeover、登出与恢复失败审计
- takeover 的确认、策略授权与事务原子性

token TTL、状态流转、恢复失败路径与审计字段由 `13_SESSION_AUTH_STATE_MACHINE.md` 冻结；协议错误与终结语义由 `11_PROTOCOL_CATALOG.md` 冻结。

## 11. 最终原则

连接不是账号，账号不是角色。AuthSession 是持久认证事实，ConnectionSession 与 Presence 是运行时对象，PresenceSnapshot 只提供有期限的恢复依据。

## V6 增量：身份与 PresenceRecovery

在每个游戏实例内，一个 `User` 永久映射一个 `GameAccount`；未来多 Character 只通过 `CharacterOwnership` 扩展，不复制 GameAccount 身份。页面刷新丢失内存 `resume_ticket` 时，同一 AuthSession 可调用 `presence.recover`，由服务端检索并恢复它自己的 active / grace PresenceSnapshot 租约，创建新一代运行时 Presence、递增 generation、旋转 ticket 并返回完整 snapshot。该请求不得跨 AuthSession 夺取控制权；找不到当前 AuthSession 自有租约时统一返回 `PRESENCE_RECOVERY_UNAVAILABLE`，不得泄露其他会话是否占用。其他 AuthSession 如需控制角色，必须走显式 `presence.takeover`；`CHARACTER_OCCUPIED` 仅用于普通 `presence.enter`。
