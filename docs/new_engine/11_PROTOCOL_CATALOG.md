# 11 WebSocket 协议目录

> 状态：`Engine Stage E0` 必须冻结的首发实施级契约。本文是实时协议的权威来源；其他文档中的旧信封示例若与本文冲突，以本文为准。

## 1. 核心不变量

- WebSocket endpoint 固定为 `/ws/v1/game`。
- 每个客户端和服务端应用信封都携带 `version`；首发协议中 `version="1"`。
- 每个可关联请求只有一个逻辑终结结果：成功用 `request.succeeded`，失败用 `request.failed`。
- 领域事件只描述状态变化，不承担请求终结。
- 只有终结响应携带 `request_id`；事件和广播永远不携带触发请求 ID。
- 服务端应用信封统一使用 `type`，禁止外层 `event_type` 或无 `type` 的错误信封。
- 错误只终结请求；非请求触发的状态变化使用事件或 snapshot。
- 首发协议用完整 snapshot 恢复状态，不承诺通用事件补发。

## 2. 信封

客户端请求：

```json
{
  "version": "1",
  "request_id": "req_01J2Z7M8",
  "type": "action.invoke",
  "payload": {
    "action": "inventory.use_item",
    "args": {
      "item_id": "item_3001"
    },
    "expected_inventory_version": 12,
    "source": "ui_button"
  }
}
```

客户端顶层字段固定为 `version / request_id / type / payload`。`payload` 必须是 object；`request_id` 是客户端生成、幂等窗口内唯一的 opaque ASCII string，语法冻结为 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`。长度为 1-128 字节，控制字符、空白、非 ASCII 与其他字符一律以 `REQUEST_ID_INVALID` 拒绝。

若畸形信封仍能提取并验证 `request_id`，服务端用 `request.failed` 终结。若无法提取有效 `request_id`，服务端不能伪造终结响应或错误事件；应以应用关闭码 `4400`（protocol error）关闭连接，并写不含原始秘密和未授权 payload 的脱敏协议日志。

成功终结：

```json
{
  "version": "1",
  "seq": 42,
  "ts": "2026-07-19T09:30:00.123Z",
  "request_id": "req_01J2Z7M8",
  "type": "request.succeeded",
  "payload": {
    "request_type": "action.invoke",
    "result": {
      "accepted": true
    }
  }
}
```

失败终结：

```json
{
  "version": "1",
  "seq": 43,
  "ts": "2026-07-19T09:30:00.456Z",
  "request_id": "req_01J2Z7M8",
  "type": "request.failed",
  "payload": {
    "request_type": "action.invoke",
    "error": {
      "code": "ACTION_FORBIDDEN",
      "message": "当前状态不能执行该动作",
      "retryable": false,
      "details": {}
    }
  }
}
```

领域事件：

```json
{
  "version": "1",
  "seq": 44,
  "ts": "2026-07-19T09:30:01.000Z",
  "type": "room.actor_entered",
  "payload": {
    "scene_scope": "room:1001",
    "actor_id": "character_2001"
  }
}
```

每个服务端应用信封都有 `version / type / seq / ts / payload`。终结响应额外有顶层 `request_id`。客户端只按 `error.code` 分支；`details` 不得暴露堆栈、token、ticket、SQL 或未授权数据。

## 3. 请求生命周期与序号

成功必须直接发送 `request.succeeded`，不能等待领域事件作为成功标志。事务提交后可以另外发送零个或多个无关联事件。
socket 在终结送达前断开时，客户端可用同一 `request_id` 重试；交付保存结果仍必须通过 4.1 的绑定投影与 4.2 的 Presence/连接/seq 上下文校验。

`seq` 是单个 `ConnectionSession` 上从 1 开始、逐应用信封严格递增的正整数。它不跨连接、不用于业务幂等，也不等于领域版本。重放终结结果时分配当前连接的新 `seq` 和 `ts`；控制帧不占用 `seq`。

活跃 Presence 上发现序号缺口时，客户端必须将权威 store 标为 stale，暂停应用状态事件，以新 `request_id` 提交 `state.sync`，再用其成功结果中的完整 snapshot bundle 原子替换本地状态。该成功信封的 `seq` 是新基线。服务端必须串行化快照捕获与连接输出，使该终结成为同步屏障；首发协议不接受 `from_seq`。

尚未绑定 active Presence 时不得调用 `state.sync`。认证或绑定阶段发现序号缺口，客户端必须关闭当前连接、建立新的 `ConnectionSession` 并重新执行认证与 enter/resume 流程。

## 4. 幂等与终结重放

`session.authenticate` 始终使用连接本地幂等键：

```text
(connection_session_id, request_id)
```

同一连接、相同请求 hash 的重放必须确认该连接仍绑定到记录中的 active `AuthSession`；绑定缺失时可幂等补绑，绑定冲突或会话失效时不得重放旧成功。不同 `ConnectionSession` 即使使用相同 `request_id`，也必须重新校验 access token 并为新连接执行绑定，禁止重放旧连接的绑定副作用。该本地结果不写入认证后的全局终结记录。

除 `session.authenticate` 外，认证后请求的幂等键固定为：

```text
(auth_session_id, request_id)
```

`session.ping` 也只按连接本地去重。其他认证后请求即使换 WebSocket 或并发到达，也必须命中同一逻辑记录，但连接绑定型请求的交付必须遵循 4.1，不能把历史副作用投影到新连接。服务端幂等重试窗口至少为 `13_SESSION_AUTH_STATE_MACHINE.md` 冻结的 24 小时；secret reference 或未完成 outbox 可令记录保留更久，客户端不得主动复用 request id。

服务端对规范化的 `version + type + payload` 计算 SHA-256：

- 首次出现时执行并保存逻辑终结结果。
- 相同键、相同 hash 时不再执行；通过 4.1/4.2 的交付上下文校验后才可重放或投影结果。
- 相同键、不同 hash 时返回 `REQUEST_ID_CONFLICT`。
- 重放不得再次修改状态、消费 ticket、写重复审计或广播事件。
- `REQUEST_DUPLICATED` 不是错误码。

PostgreSQL 表 `RequestTerminalRecord` 至少包含：
`auth_session_id`、`request_id`、`request_type`、`canonical_request_hash`、`terminal_kind`、
`terminal_payload_json`、`secret_references_json`、`origin_connection_session_id`、
`presence_context_id`、`presence_context_generation`、`sync_barrier_seq`、
`bound_presence_id`、`bound_presence_generation`、`activation_state`、
`activation_owner_runtime_instance_id`、`activation_deadline_at`、`created_at`、`expires_at`，
并有 `UNIQUE (auth_session_id, request_id)`。领域写入与终结记录必须原子提交。

`activation_state` 为 `not_required / activation_pending / active / compensated`。连接绑定型请求在领域事务中先写 `activation_pending`，并记录激活所有者与有限 deadline；
它不是可交付的成功终结。重放只能在 deadline 内有界等待，或触发 `13_SESSION_AUTH_STATE_MACHINE.md` 的恢复处理，不能返回成功或无限等待。
激活后才转为 `active`；异常或崩溃补偿后转为 `compensated` 并保存稳定失败，永远不得重放准备阶段的成功 payload。

非连接绑定型请求仍要求领域写入与最终终结记录原子提交。若结果包含新 `resume_ticket`，终结记录只保存 `ResumeTicketCredential` 引用。交付层用 credential id、generation 与密钥管理器 key 确定性重新物化并核对 hash；明文 ticket 不进入数据库、日志、审计或异常上报。

### 4.1 连接绑定型终结的交付投影

`presence.enter`、`session.resume`、`presence.recover` 与 `presence.takeover` 的逻辑终结必须保存来源 `ConnectionSession`、Presence id、generation 和 ticket credential 引用。交付时动态生成 `delivery.status`，不得直接把历史 payload 当成当前连接状态：

- 当前连接仍绑定记录中的同一 Presence generation 时，返回 `delivery.status=bound`、`resume_required=false`，可交付新 ticket 与完整 snapshot。
- 当前连接不是来源连接，或来源连接已不再绑定该 Presence generation 时，不执行绑定、不广播事件、不隐式接管。若记录引用的 ticket 仍可安全使用，只返回 `delivery.status=resume_required`、`resume_required=true`、ticket 与 Presence 标识，省略历史 snapshot；客户端必须以新 `request_id` 调用 `session.resume`。
- 记录引用的 ticket 已 used、revoked、expired 或被后续 generation 取代时，返回 `delivery.status=superseded`，不返回 ticket 或 snapshot，也不声称当前连接已绑定。客户端只能进入正常的 enter/占用提示/显式 takeover 流程。

`delivery.status` 是交付状态，不改变已经保存的逻辑终结。跨连接交付永远不能让 `state.sync` 变得可用；只有新的 `session.resume` 成功并返回 `bound` 后，当前连接才拥有 active Presence。

### 4.2 Presence 上下文型终结的重放

请求目录中上下文为“活跃 Presence”的请求在首次接受时，必须把当时的 `presence_id + generation` 写入
`presence_context_id + presence_context_generation`。同键同 hash 重放前，交付层必须确认当前连接仍绑定同一 active Presence generation。

若当前没有 active Presence、连接绑定不同或 generation 已变化，服务端不得执行请求，也不得返回历史 terminal payload；
必须动态返回 `request.failed`，错误为 `REQUEST_CONTEXT_CHANGED`、`retryable=false`、`details.new_request_id_required=true`，
并要求客户端根据当前状态生成新 `request_id`。
原逻辑终结保持不变，旧 snapshot、动作结果或 UI action set 都不能投影到新 generation。

`state.sync` 还必须绑定 `origin_connection_session_id` 与 `sync_barrier_seq`。首次交付在连接输出锁内捕获 snapshot、预留 barrier seq，
再保存这些元数据并排入终结信封。同 id 重放只有在来源 ConnectionSession、Presence generation 均相同，且当前连接最后分配的应用 seq 仍等于记录中的 barrier seq 时才可返回旧 snapshot；
重放时在同一输出锁内预留新 seq 并更新 `sync_barrier_seq`。只要换连接或 barrier 后已经发送过任何应用信封，就返回 `REQUEST_CONTEXT_CHANGED`，
省略 snapshot，并要求用新 request id 再执行 `state.sync`。跨连接永远不能把历史 snapshot 或历史屏障升级为当前连接的同步基线。

## 5. 请求目录

| 请求 | 上下文 | 成功结果 |
|------|--------|----------|
| `session.ping` | 已连接 | 服务端时间与可选 nonce |
| `session.authenticate` | 未认证连接 | AuthSession 摘要 |
| `session.resume` | 已认证 | 交付状态、新 ticket 与完整 snapshot |
| `presence.recover` | 已认证、同 AuthSession 自有 active/grace PresenceSnapshot 租约 | 新 generation、旋转 ticket 与完整 snapshot |
| `presence.enter` | 已认证、无 Presence | 交付状态、Presence、新 ticket 与完整 snapshot |
| `presence.leave` | 活跃 Presence | 已关闭 Presence id |
| `presence.takeover` | 已认证、显式确认 | 交付状态、新 Presence、新 ticket 与完整 snapshot |
| `state.sync` | 活跃 Presence | 完整 snapshot |
| `action.invoke` | 活跃 Presence | 确定性动作结果 |
| `ui.actions.resolve` | 活跃 Presence | `ResolvedActionSet` |

除 `session.ping` 和 `session.authenticate` 外都要求有效 `AuthSession`。`session.resume` 必须在新连接先以 access token 完成 `session.authenticate` 后调用。

refresh token 不进入 WebSocket；它只可作为 REST refresh 的轮换凭据，或作为 REST logout 的受保护 Cookie locator。

请求 payload 的最小 schema：

- `session.ping`：`{}` 或 `{"nonce": "<opaque string>"}`。
- `session.authenticate`：`{"access_token": "<access token>"}`；不得携带 refresh token。
- `presence.enter`：`{"character_id": "<opaque id>"}`。
- `presence.recover`：`{}`；只允许当前 AuthSession 恢复自己仍 active 或 grace 的 PresenceSnapshot 租约并创建新一代运行时 Presence，不接受跨会话 locator。
- `presence.leave`：`{}`。
- `presence.takeover`：`{"character_id": "<opaque id>", "confirm": true}`。
- `state.sync`：`{"include_actions": true}`；`include_actions` 可省略，默认仍返回完整 actions。
- `ui.actions.resolve`：`{}`。

`session.resume` payload：

```json
{
  "version": "1",
  "request_id": "req_resume_1",
  "type": "session.resume",
  "payload": {
    "resume_ticket": "opaque-single-use-ticket"
  }
}
```

首次成功消费旧 ticket、旋转新 ticket，并在激活完成后以 `delivery.status=bound` 直接返回新 ticket 和完整 snapshot；不能只触发事件。终结重放按 4.1 投影交付状态。`presence.takeover` 要求 `character_id` 与 `confirm=true`，普通 `presence.enter` 不得自动升级成接管。

`state.sync` 只接受 active Presence，并必须一次返回 `scene / character / combat / actions`；无活跃战斗时 `combat=null`。

`presence.recover` 不依赖内存 `resume_ticket`，但必须锁定当前 AuthSession、GameAccount、Character 与其 active/grace `PresenceSnapshot`。成功时递增 generation、使旧 ticket 失效、签发新 ticket，并以 `delivery.status=bound` 返回完整 snapshot；找不到自有可恢复租约时返回统一的 `PRESENCE_RECOVERY_UNAVAILABLE`，不得泄露其他 AuthSession 的占用细节。
只有满足 4.2 连接/generation/barrier 条件的成功重放才返回完整可恢复结果；其他重放返回 `REQUEST_CONTEXT_CHANGED`，不得返回旧 snapshot。

`state.sync` 的 `result` 最小结构：

```json
{
  "presence_id": "presence_9001",
  "snapshot": {
    "scene": {},
    "character": {},
    "combat": null,
    "actions": {}
  }
}
```

## 6. 动作协议

客户端 `action.invoke.payload.source` 只允许：

- `text_command`
- `ui_button`
- `ui_menu`
- `shortcut`

`text_command` 必须携带非空 `input`；其他来源必须携带 `action` 和 object 类型 `args`。客户端发送 `source=system` 必须以 `ACTION_SOURCE_FORBIDDEN` 失败。内部 `NormalizedAction` 可以使用 `system`，但只能由受信服务端代码赋值，不能从客户端透传。

active Presence 发起任何 `action.invoke` 时，无论文本还是结构化入口，`payload.expected_inventory_version` 都必须是当前 snapshot 中的非负整数。缺失或类型错误返回 `PAYLOAD_INVALID`。尚未进入 Presence 的连接不得伪造该版本来执行需要背包上下文的动作。

服务端只在解析后的 exact ActionDefinition 声明 `requires_inventory_version=true` 时比较版本。它按领域稳定顺序持锁后重读 Character 的持久化版本；不同时返回 `INVENTORY_VERSION_CONFLICT`，不得执行动作、写成功审计或发送成功事件。

`requires_inventory_version=false` 的动作忽略该并发前提，避免背包变化阻断移动或聊天。客户端取得新 snapshot 后只能等待新的用户意图，不能自动重放失败的背包或装备动作。

文本动作解析先规范化输入与别名。同一 action key 经多个 provider 暴露时先去重，并以这些 provider 中最小的 `priority` 作为有效 provider priority。

不同 action key 的候选依次按 `match_priority`（小优先）、`provider.priority`（小优先）、最长规范化别名排序。完成全部排序后仍有多个不同 action key 并列，才返回 `ACTION_AMBIGUOUS`；随后解析参数并执行权限、状态和限流校验。

`ui.actions.resolve` 返回的 `ResolvedActionSet` 至少包含 `action_version` 和动作数组。每项包含 `key`、`label`、`args_schema`、`enabled` 与 `disabled_reason`。动作 key 是全局唯一的 `ActionDefinition.key`；客户端不能用旧 action set 绕过服务端校验。

Public V1 的 Character-targeted combat 只允许双方明确确认的非致命 `Sparring`。`combat.fight` 的第一次有效同意只提交等待对方确认的状态，不造成伤害或启动敌对战斗；同一邀请的对方确认提交后才开始 sparring。对应 `action.invoke.result` 必须以稳定机器字段区分 `combat_mode=sparring` 和 `consent_state=pending / confirmed`，客户端不得从叙事文本猜测同意状态。

任何会对 Character 形成 involuntary 或致命结果的动作，包括已确认 Sparring 之外的 `combat.kill / combat.hit / combat.touxi / combat.ansuan`，统一以 `ACTION_FORBIDDEN` 失败。邀请已撤回、过期、目标或发起者已进入冲突战斗状态、重复确认不能应用到当前状态等 consent / state 竞态统一以 `COMBAT_STATE_CONFLICT` 失败；文本命令和结构化 Action 必须得到相同 code。NPC 目标仍按 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 的权威战斗规则处理。

Character 在 sparring 中败北时，战斗终结结果必须以稳定机器字段返回 `combat_outcome=safe_defeat`。`SafeDefeat` 结束对应战斗并投影新的完整状态，但不得产生 Character death、玩家 Item 丢失或不可逆成长回退；它不能套用于 NPC death/drop。

## 7. 事件目录

- `session.ready`：AuthSession 已绑定。
- `session.resumed`：Presence 已从持久 snapshot 安全重建。
- `presence.entered`：当前连接获得角色控制上下文。
- `presence.left`：当前连接离开角色上下文。
- `presence.taken_over`：旧连接已经失去角色控制权。
- `scene.snapshot`、`character.snapshot`、`combat.snapshot`：完整状态摘要。
- `ui.actions.resolved`：可用动作集合变化。
- `room.actor_entered`、`room.actor_left`、`room.output`：房间状态与叙事。
- `chat.channel_message`、`chat.private_message`：聊天投递。
- `system.notice`、`system.maintenance`：非错误通知与维护。

`presence.taken_over` 是发给旧连接的状态事件，不是推送错误。旧连接随后发起需要 Presence 的请求时，才以 `request.failed` 返回 `PRESENCE_NOT_ACTIVE`。

## 8. Snapshot contract

每个 snapshot 使用自己的领域版本，外层 `seq` 不能代替它。

`scene.snapshot` 至少包含 `scene_version`、`scene_scope`、room 摘要、occupants、objects 与 exits。

`character.snapshot` 至少包含：

```json
{
  "character_id": "character_2001",
  "instance_id": "world_instance_1",
  "character_version": 33,
  "resources": [],
  "inventory_version": 12,
  "inventory": [
    {
      "id": "item_3001",
      "instance_id": "world_instance_1",
      "blueprint_revision_id": "blueprint_revision_item_cloth_3",
      "quantity": 1,
      "location_entity_id": "character_2001",
      "state_version": 4
    }
  ],
  "equipment": [
    {
      "wearer_entity_id": "character_2001",
      "equip_slot": "body",
      "item_instance_id": "item_3001",
      "state_version": 5
    }
  ],
  "skills": [
    {
      "id": "actor_skill_5001",
      "actor_entity_id": "character_2001",
      "skill_head_id": "blueprint_head_skill_unarmed_1",
      "skill_blueprint_revision_id": "blueprint_revision_skill_unarmed_7",
      "level": 20,
      "state_version": 6
    }
  ],
  "jifa_bindings": [
    {
      "actor_entity_id": "character_2001",
      "enable_slot": "unarmed",
      "actor_skill_id": "actor_skill_5001",
      "state_version": 7
    }
  ],
  "prepare_bindings": [
    {
      "actor_entity_id": "character_2001",
      "enable_slot": "unarmed",
      "combine_order": 1,
      "actor_skill_id": "actor_skill_5001",
      "state_version": 8
    }
  ]
}
```

`resources / inventory / equipment / skills / jifa_bindings / prepare_bindings` 都是权威完整集合，空集合必须显式为 `[]`，不能省略或解释为“无变化”。客户端必须原子替换这些集合，不能把 snapshot 当成增量 patch。

`inventory` 包含占有链最终归属该 Character 的全部 active Item，包括已装备 Item 与容器内 Item；retired tombstone 不进入该数组。每项 `instance_id` 必须等于 snapshot 顶层的 Character 游戏实例，`location_entity_id` 是占有和包含关系的唯一真源。

`equipment` 只投影 `EquipmentBinding`，其中 `item_instance_id` 引用 `inventory[].id`，不能复制 Item 状态。

Item 的 `blueprint_revision_id` 与 ActorSkill 的 `skill_head_id / skill_blueprint_revision_id` 都是 immutable pinned context。服务端和客户端不得按裸 key 或当前 active batch 重解释既有物品、技能或 binding。

`character_version` 是整个 `character.snapshot` 的持久化单调聚合版本；上述任一集合或核心资源发生已提交变化时都必须递增。`inventory_version` 是背包与装备动作的持久化窄化并发版本。进程重启不得重置或重新推导两者。

Item 新增、移除、位置或数量变化，以及任一 `EquipmentBinding` 变化时，两个聚合版本必须在同一事务递增，并由同一次 snapshot 捕获。只有其他角色状态变化时，允许只递增 `character_version`。

跨 Character 的给予或其他转移必须在同一事务推进每个受影响 Character 的 `character_version / inventory_version`；不能只更新请求发起者或最终持有者。

各 Item、ActorSkill、JifaBinding、PrepareBinding 和 EquipmentBinding 的 `state_version` 是对应持久行的乐观并发版本，不替代两个聚合版本。服务端必须从同一数据库一致性视图捕获全部字段和版本；客户端不能跨 snapshot 拼接集合或版本。

`combat.snapshot` 至少包含：

```json
{
  "combat_id": "combat_7001",
  "combat_version": 19,
  "participants": [],
  "target": null,
  "resources": [],
  "short_term_effects": [],
  "action_version": 17,
  "state": "active"
}
```

它覆盖参战方、目标、资源、短期效果和动作版本。进程重启后不得恢复半完成攻击；按 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 安全结束运行时战斗。

`presence.enter`、`presence.takeover`、`session.resume` 和 `presence.recover` 首次绑定成功的结果至少包含 `delivery.status=bound`、`resume_required=false`、`presence_id`、新 `resume_ticket`
以及含 `scene / character / combat / actions` 的 snapshot object。跨连接或绑定不匹配的重放按 4.1 省略 snapshot。
`state.sync` 不旋转 ticket，因此省略 ticket，其他完整性规则相同。

## 9. 稳定错误码

协议：`INVALID_ENVELOPE`、`UNSUPPORTED_PROTOCOL_VERSION`、`REQUEST_ID_INVALID`、`REQUEST_ID_CONFLICT`、`REQUEST_CONTEXT_CHANGED`、`REQUEST_TYPE_UNSUPPORTED`、`PAYLOAD_INVALID`、`RATE_LIMITED`。

认证与 Presence：
`AUTH_REQUIRED`、`ALREADY_AUTHENTICATED`、`TOKEN_INVALID`、`TOKEN_EXPIRED`、`SESSION_REVOKED`、`SESSION_RESUME_FAILED`、
`RESUME_TICKET_INVALID`、`RESUME_TICKET_EXPIRED`、`PRESENCE_REQUIRED`、`PRESENCE_NOT_ACTIVE`、`PRESENCE_ACTIVATION_FAILED`、
`CHARACTER_NOT_FOUND`、`CHARACTER_FORBIDDEN`、`CHARACTER_OCCUPIED`、`TAKEOVER_CONFIRMATION_REQUIRED`。
`PRESENCE_RECOVERY_UNAVAILABLE`。

角色创建：
`CHARACTER_ALREADY_EXISTS`、`CHARACTER_CREATION_UNAVAILABLE`、`CHARACTER_DISPLAY_NAME_INVALID`、`CHARACTER_PROFILE_INVALID`。

动作与领域：
`ACTION_NOT_FOUND`、`ACTION_AMBIGUOUS`、`ACTION_ARGUMENT_INVALID`、`ACTION_FORBIDDEN`、`ACTION_SOURCE_FORBIDDEN`、
`ROOM_EXIT_BLOCKED`、`CHAT_FORBIDDEN`、`CHAT_RATE_LIMITED`、`COMBAT_STATE_CONFLICT`、
`INVENTORY_VERSION_CONFLICT`、`ITEM_NOT_AVAILABLE`、`ENTITY_LOCATION_INVALID`、`ITEM_CONTAINER_NOT_ALLOWED`、
`ITEM_CONTAINER_FULL`、`ITEM_CONTAINER_CYCLE`。

社区治理：
`COMMUNITY_ACTION_FORBIDDEN`、`PLAYER_BLOCK_INVALID`、`CHANNEL_MUTE_INVALID`、`MODERATION_REPORT_INVALID`、
`MODERATION_CASE_NOT_FOUND`、`MODERATION_APPEAL_ALREADY_SUBMITTED`、`MODERATION_APPEAL_FORBIDDEN`。

新增错误码必须先进入协议 schema 与生成类型；不能临时用异常类名、自由文本或 HTTP 状态码。

## 10. 安全与验收

- access token、refresh token 和 resume ticket 在日志、追踪、审计及异常上报中一律脱敏。
- refresh token 不得进入 WebSocket payload。
- 协议 schema、客户端 TypeScript 类型和服务端校验器必须同源生成或通过双向契约测试。
- 契约测试覆盖 request id 正反例、连续 `seq`、终结唯一性、事件无 `request_id`、请求重放、ID 冲突、ticket 安全重放、禁止客户端 `system`、断序同步和完整 snapshot。
- `character.snapshot` 契约测试必须覆盖六个完整集合、空数组、pinned revision、binding 引用、同一一致性视图与三个层级的版本语义。
- `action.invoke` 契约测试必须覆盖 active Presence 缺失/非法版本，以及 `requires_inventory_version` 为 true/false 时对匹配和陈旧版本的不同处理。
- `action.invoke` 契约测试必须覆盖 Sparring 双方确认前不启动战斗、确认后只进入非致命模式、Character-targeted involuntary / lethal 动作返回 `ACTION_FORBIDDEN`、consent / state 竞态返回 `COMBAT_STATE_CONFLICT`，以及 SafeDefeat 的机器结果和零 Character death / Item loss / 不可逆成长回退。
- 状态机测试覆盖 `session.authenticate` 同连接本地重放与跨连接重新绑定、`state.sync` 拒绝非 active Presence，以及绑定型终结跨连接只返回 `resume_required`。
- Presence-required 请求在 generation 改变后重放必须返回 `REQUEST_CONTEXT_CHANGED`；不得返回旧动作结果、action set 或 snapshot。
- `state.sync` 在来源连接改变或 barrier seq 已推进后重放必须省略旧 snapshot，并要求新 request id；同连接未推进 barrier 的受控重放仍建立新 seq 屏障。
- 故障注入覆盖 `pending_enter` 准备、事务提交、原子激活和补偿边界；任何路径都不得交付或重放虚假成功。
