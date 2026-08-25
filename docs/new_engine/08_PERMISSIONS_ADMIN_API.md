# 08 权限、后台与 API 契约

> 术语说明：本文默认使用 `User / GameAccount / PlatformRole / AuthSession / Presence`。`AccountDB` 仅在比较 Evennia API 设计时作为来源术语出现；平台操作者和系统任务不得伪装成 `ActorRef`。

> 实施约束：本文负责定义权限、后台与 API 边界；具体实施以对应冻结合同为准：
> - WebSocket 信封、`action.invoke`、错误码与请求终结：`docs/new_engine/11_PROTOCOL_CATALOG.md`
> - 会话认证与 token 生命周期：`docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
> - 安全、审计与发布门禁：`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`

## 1. 权限模型

Evennia 的 `LockHandler` 非常强，但它不适合成为 New_Mud 的核心权限语言。

源码依据：

- `evennia-main/evennia/locks/lockhandler.py`

## 1.1 保留什么

- 权限校验点应分散在对象、动作、频道、帮助条目上
- 权限函数应可复用
- 管理员应有清晰的 bypass 机制

## 1.2 放弃什么

- 以字符串 DSL 作为主权限模型
- 大量运行时拼接 `perm(Admin) or ...`
- 业务规则和权限表达混在一条 lockstring 里

## 1.3 新模型建议

权限由三层组成：

### 平台角色

- `super_admin`
- `ops_admin`
- `content_editor`
- `gm`
- `qa`

首发最小权限矩阵：

| 能力 | super_admin | ops_admin | content_editor | gm | qa |
| --- | --- | --- | --- | --- | --- |
| 授予平台角色 | 是 | 否 | 否 | 否 | 否 |
| 账号封禁与受审计恢复 | 是 | 是 | 否 | 是 | 只读 |
| 创建和编辑内容 draft | 是 | 否 | 是 | 否 | 只读 |
| 批次发布与回滚审批 | 是 | 是 | 可提交、不可自批 | 否 | 只读 |
| 角色数据修正 | 是 | 是 | 否 | 按授权范围 | 只读 |
| 日志、巡检和差异查看 | 是 | 是 | 自有内容 | 按授权范围 | 是 |

同一操作者不得批准自己提交的普通内容批次。紧急超管操作必须记录原因、影响范围和事后复核人。

### 平台角色归属对象

- 平台角色统一挂在 `User` 侧的后台授权关系上，不挂在 `GameAccount` 上
- `GameAccount` 只表达玩家侧身份、角色拥有关系与游戏内关系，不承载后台运营权限
- 后台请求的主体默认是已认证 `User`
- 若 `gm` 同时需要后台工具权限与游戏内裁决能力，两者也应分开建模：后台权限属于 `User`，游戏内裁决属于显式业务规则或专用动作策略

### 领域关系

- `GameAccount` 是否拥有角色
- 角色是否属于某帮派
- 角色是否在某门派职位内
- 是否为房间/区域作者

### 规则谓词

- 是否在线
- 当前 `Presence` 是否处于目标场景
- 是否在安全区
- 是否已加入频道
- 是否满足等级/门派/任务条件

## 2. 后台系统

根据需求，后台至少覆盖两类能力：

### 2.1 内容制作

M1 只提供 Room、Exit、Region 元数据、NPC、Item、Skill、SkillMove 与 ConditionDefinition 的 draft 创建、编辑、校验、diff、批次发布和批次回滚。

Quest、Dialogue、Shop、LootTable、世界事件、定时活动、组织和经济内容的完整编辑器属于 M2-M3。Django Admin 不得被用作绕过该阶段边界的原始表写入口。

### 2.2 账号与运营

- 账号封禁/解封
- M1 受审计的后台密码重置与账号恢复
- 角色查看与修正
- 在线监控
- 日志与异常查看
- 公告发布

手机号、邮箱或微信驱动的玩家自助找回属于 M2/M6，不得阻断 M1 的后台恢复最小流程。

M1 后台恢复只允许权限矩阵中具“账号封禁与受审计恢复”写权限的 PlatformRole：`super_admin / ops_admin / gm`。`super_admin` 负责紧急处置，`ops_admin` 负责常规冻结、撤销和恢复修复，`gm` 只在分配给自己的 support case 与授权范围内执行相同动作；`qa` 只读，`content_editor` 无权访问。允许的写动作只有冻结或撤销可疑恢复流程、撤销账号的全部会话与凭据，以及修复一个玩家仍持有有效 RecoveryCode 的失败流程。

修复必须调用与 `/api/v1/auth/recover` 相同的 code 校验、合并限流、密码策略和原子撤销服务；后台只能查看 code generation / hash 状态与脱敏审计，不能读取明文 code、跳过验证、直接签发所有权证明或依据角色资料和游戏 trivia 重分配账号。密码与 code 都丢失时只能冻结 / 撤销，不能恢复所有权。

每次动作要求重新认证、稳定 reason、关联 support case、目标 User / GameAccount、操作者和复核结果。成功修复仍轮换 RecoveryCode，撤销全部旧 AuthSession、RefreshTokenFamily 与 ticket、终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence，并只经玩家当前受保护响应一次展示新 code；失败不得改变密码、code、账号 lifecycle 或会话状态。

## 3. Django Admin 的定位

Evennia 用 Django Admin 扩展做了大量后台能力，这个方向值得保留。

New_Mud 建议：

- 基础数据管理走 Django Admin
- 复杂编辑器走自定义 admin views / management pages
- 不强迫一切内容都在原生表单里编辑

## 4. REST API 边界

### 4.1 版本策略

结合 `requirements_v6.md` 对稳定接口与前后台认证边界分离的约束，对外 REST API 从第一版起必须带显式版本号。

正式冻结为：

- 面向客户端的业务 REST API 使用 `/api/v1/...`
- 面向后台管理页或 Admin 前端调用的 REST API 使用独立命名空间，如 `/admin/api/v1/...`
- 发生 breaking change 时递增主版本，例如 `/api/v2/...`
- 同一版本内允许加字段、加非破坏性端点，但不允许静默改语义

版本前缀属于 `Engine Stage E0` 需要冻结的契约，不应等实现到后期再补。

REST 负责：

- 用户名密码注册
- 登出
- 登录
- token 刷新
- 角色列表/创建
- 背包、任务、角色资料查询
- 管理后台接口

REST 不负责：

- 高频实时战斗事件
- 房间广播
- 即时聊天流

Refresh Token 仅可作为 REST refresh endpoint 的轮换凭据，或作为 logout endpoint 的受保护 Cookie locator；不得进入 WebSocket payload 或 Authorization header。

每个逻辑 refresh 必须携带安全格式的 `Idempotency-Key`。终结记录、同 key 重放、冲突、superseded 与攻击 replay 语义以 `13_SESSION_AUTH_STATE_MACHINE.md` 为准，本文不另建第二套 schema。

### 4.2 首发 H5 注册与认证端点

首发玩家开户与认证只暴露以下四个端点，不提供无版本别名、GET 变体或把 refresh token 放入 JSON/Authorization header 的兼容路径：

Authorization header 只允许 logout 携带当前 access token；register、login 与 refresh 不接受该兼容入口，refresh token 在任何端点都不得放入 Authorization header。

| 方法与路径 | 请求 | 成功结果 |
| --- | --- | --- |
| `POST /api/v1/auth/register` | JSON `username / password` | `201` User、GameAccount id 与一次性明文 RecoveryCode；不签发 token、不设置 Cookie |
| `POST /api/v1/auth/login` | JSON `username / password` | `200` access token JSON，并设置 refresh Cookie |
| `POST /api/v1/auth/refresh` | JSON `{}`、refresh Cookie、`Idempotency-Key` | `200` 新 access token JSON，并原子轮换 refresh Cookie |
| `POST /api/v1/auth/logout` | JSON `{}`、refresh Cookie（若存在）、内存中若存在则携带当前 access Bearer | `204`，撤销可识别认证会话并清除 Cookie |

注册和登录请求最小结构一致：

```json
{
  "username": "player_name",
  "password": "user-supplied-password"
}
```

注册成功响应包含 `user_id / game_account_id / recovery_code`；明文 RecoveryCode 只在这次响应展示，之后不得再次读取或返回。

注册必须把账号名规范为 3-32 位 ASCII 小写字母、数字和下划线，并按规范值执行大小写不敏感唯一校验。

注册事务只创建 `User`、一对一首发 `GameAccount` 与 RecoveryCode 哈希。任一步失败整体回滚；不得创建 AuthSession、refresh family、credential、Cookie、Character 或 Presence。

密码必须通过 Django 当前部署的密码校验器。重复账号名统一返回 `REGISTRATION_UNAVAILABLE`，格式或密码策略失败返回 `REGISTRATION_INVALID`。

注册响应不得返回候选 User、密码规则内部实现或堆栈。

登录和 refresh 的成功响应最小结构一致：

```json
{
  "access_token": "opaque-jwt",
  "token_type": "Bearer",
  "expires_in": 900,
  "auth_session_id": "auth_session_1001",
  "game_account_id": "game_account_1001"
}
```

`expires_in` 是从响应生成时刻起的整数秒数。access token 只出现在该 JSON 和后续明确需要它的认证位置；refresh token 不得进入响应 JSON。
登录必须在一个认证事务中创建 `AuthSession`、其 lifetime 唯一 refresh family 与首代 credential。`AuthSession.device_id` 由服务端为本次登录生成不可预测的随机 opaque id，
不从 IP、User-Agent、canvas 或其他浏览器指纹推导；首发请求无需客户端提交该字段。refresh 的轮换事务和重放行为由 `13_SESSION_AUTH_STATE_MACHINE.md` 第 9 节冻结。

H5 refresh Cookie 名固定为 `new_mud_refresh`。每次登录或 refresh 成功都必须发送等价于以下属性的 `Set-Cookie`：

```text
new_mud_refresh=<opaque>; Path=/api/v1/auth/; Secure; HttpOnly; SameSite=Strict; Max-Age=<bounded-seconds>
```

Cookie 必须是 host-only（不得设置 `Domain`）；`Max-Age` 不得晚于 refresh family 的绝对截止时间。H5 请求使用同源 `credentials=include`。
register、login、refresh、logout 四个端点都必须校验允许的 `Origin`，跨源 register/login 也要拒绝以防 CSRF/session swapping；不得为任意跨源开放 credentialed CORS。
非浏览器受控客户端的认证传输必须由未来显式版本合同定义，不能绕过该规则。

每个 refresh 必须携带语法为 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` 的 `Idempotency-Key`，网络重试复用同一 key。
缺失或非法 key 在读取/消费 credential 前返回 `REFRESH_IDEMPOTENCY_KEY_INVALID`。register、login、refresh、logout 的全部成功与错误响应都必须发送 `Cache-Control: no-store`，
不得让 access token 或认证错误进入浏览器/中间缓存。

logout 分别解析 refresh Cookie 与正常有效 access Bearer 的 `auth_session_id`。active/used refresh credential 都可作为显式撤销 locator；无效 locator 被忽略，不进入 refresh replay 判定。

服务端按 `auth_session_id` 稳定排序锁定两类 locator 能识别的全部候选。即使 Cookie 与 Bearer 指向不同 AuthSession，也撤销两者，避免同源多标签页留下可用会话。

active 候选的 lifetime family 和 active credentials 置为 revoked，AuthSession 置为 logged_out，并在同一事务关闭 active/grace PresenceSnapshot、撤销 ticket。对应运行时 Presence 与连接在提交后关闭，或由下一请求拒绝。

候选已处于 revoked/expired/logged_out 时保留原终态，只幂等收敛子记录。

Cookie 缺失、损坏或零个 locator 可识别时仍返回 `204`，但此时只能完成客户端清理，不能宣称已定位并撤销服务端会话。所有路径都发送 `Cache-Control: no-store`，并用同名、同 Path/安全属性及 `Max-Age=0` 清除 Cookie；响应不泄露识别出零个、一个或两个会话。

REST 失败 body 只允许稳定 code：

```json
{
  "error": {
    "code": "AUTH_CREDENTIALS_INVALID"
  }
}
```

账号不存在、密码错误或不可登录统一使用 `AUTH_CREDENTIALS_INVALID`。注册只使用 `REGISTRATION_INVALID` 或 `REGISTRATION_UNAVAILABLE`。
refresh 对外只使用 `REFRESH_IDEMPOTENCY_KEY_INVALID`、`REFRESH_IDEMPOTENCY_CONFLICT`、`REFRESH_REQUEST_SUPERSEDED`、`REFRESH_UNAVAILABLE` 或 `SESSION_REVOKED` 等已登记 code；
攻击 replay 的审计原因是 `REFRESH_TOKEN_REPLAYED`，对客户端返回 `SESSION_REVOKED`。
客户端不得按自由文本或仅按 HTTP status 分支；响应不得包含堆栈、凭据、账号存在性、内部对象详情或任意秘密。

微信小程序的授权登录与 token 传输适配属于需求里程碑 M6。首发不得为其增加 refresh body/bearer 回退；后续必须通过显式版本化合同引入平台 adapter。

### 4.3 首发角色创建

角色创建是 REST 业务操作，不在注册事务中隐式发生，也不通过 WebSocket `presence.enter` 伪造创建。首发固定使用：

```text
GET  /api/v1/character-creation-profiles
POST /api/v1/characters
```

`GET` 只返回当前可选择的 profile identity、玩家可见名称以及 gender/pronoun 选项：`key / version / definition_hash / display_name / gender_options / pronoun_options`。它不得返回内部初始 stats、资源、技能、物品授予或来源材料。Profile 的 schema、SemVer、definition hash、兼容目录、内容批次固定和不可变创建记录以 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 5.15 节为准。

请求必须携带合法的 `Idempotency-Key`，并包含：

```json
{
  "creation_profile_key": "default-v1",
  "creation_profile_version": "1.0.0",
  "display_name": "玩家名称",
  "gender": "unspecified",
  "pronouns": "unspecified"
}
```

服务端必须在同一事务中锁定 GameAccount、校验 CharacterOwnership 唯一性、解析 exact `CharacterCreationProfileDefinition` 及其 definition hash、固定活动内容批次和全部初始 Blueprint revision，并按 V6 8.8 执行 `CharacterDisplayName` 的 NFKC、可见字符、保留词、控制字符和实例内唯一校验。性别和代词只影响展示，不得改变属性、成长、资格、门派或武学能力。

成功返回 `201`、Character stable id、display name、完整 profile identity（key/version/definition hash）和初始状态摘要；同一幂等键同一 payload 可安全重放。首发每个 GameAccount 最多一个 Character，因此不另建 `character.choose`。Profile version 不存在、不是当前可选版本、hash/BlueprintRef 无法闭合或初始状态不合法时统一使用 `CHARACTER_PROFILE_INVALID`；其他失败只使用 `CHARACTER_ALREADY_EXISTS`、`CHARACTER_DISPLAY_NAME_INVALID` 或 `CHARACTER_CREATION_UNAVAILABLE`，不得泄露名称是否已被占用。

### 4.4 RecoveryCode 与账号生命周期

首发和 Public V1 固定使用以下端点：

```text
POST /api/v1/auth/recover
POST /api/v1/auth/recovery-code/rotate
POST /api/v1/account/close
POST /api/v1/account/reopen
```

`auth/recover` 接受账号名、RecoveryCode 和新密码；成功时撤销该 User 的全部 AuthSession、RefreshTokenFamily 与 ResumeTicket，终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence，生成新 code 并只在该响应中展示一次。`recovery-code/rotate` 需要当前 active AuthSession，轮换后同样撤销旧 code 和全部旧控角状态。恢复失败按账号、IP、设备合并限流，统一返回 `RECOVERY_CODE_INVALID`、`RECOVERY_RATE_LIMITED` 或 `ACCOUNT_RECOVERY_UNAVAILABLE`，不泄露账号存在性。

`account/close` 立即撤销会话与 ticket、终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence，并将 GameAccount 置为 `cooling_off`；`account/reopen` 只接受冷静期内的有效 RecoveryCode，成功后回到 `active`，但不自动恢复旧 PresenceSnapshot 或运行时 Presence。冷静期结束进入 `retired`，User 数据匿名化/禁用，Character 进入 `RetiredCharacter`。过期和不可恢复路径使用 `ACCOUNT_REOPEN_WINDOW_EXPIRED`、`ACCOUNT_NOT_REOPENABLE` 或 `ACCOUNT_ALREADY_RETIRED`。所有四个端点发送 `Cache-Control: no-store`，恢复和关闭操作均写审计事件。

### 4.5 Public V1 社区治理 API

玩家侧自助操作使用 `/api/v1/community/...`；运营侧案件处置使用 `/admin/api/v1/moderation/...`。WebSocket 只推送结果和通知，不作为 moderation 事实写入入口。

```text
POST   /api/v1/community/blocks
DELETE /api/v1/community/blocks/{actor_id}
POST   /api/v1/community/channel-mutes
DELETE /api/v1/community/channel-mutes/{channel_id}
POST   /api/v1/community/reports
POST   /api/v1/community/cases/{case_id}/appeal
GET    /admin/api/v1/moderation/cases
POST   /admin/api/v1/moderation/cases/{case_id}/decisions
POST   /admin/api/v1/moderation/cases/{case_id}/appeal-review
```

举报请求只携带不可变消息 ID，服务器在受理时重新抓取授权上下文；玩家不能提交原始证据替代服务器取证。`PlayerBlock` 只改变执行者看到的普通公共消息和私聊，`ChannelMute` 只抑制个人订阅，System/Security/GM 通知不可屏蔽。

ModerationCase 的决定使用不可变 UTC `effective_at` / `expires_at` 窗口：`warning` 可无期限，`channel_mute` 和 `suspension` 必须有到期时间，永久 `ban` 使用空 `expires_at` 并通过显式 revoke 终结。状态只允许 `proposed -> active -> expired`、`proposed -> rejected` 或 `active -> revoked`；每案最多一次审计申诉，提交者不得批准自己的案件。稳定错误码为 `COMMUNITY_ACTION_FORBIDDEN`、`PLAYER_BLOCK_INVALID`、`CHANNEL_MUTE_INVALID`、`MODERATION_REPORT_INVALID`、`MODERATION_CASE_NOT_FOUND`、`MODERATION_APPEAL_ALREADY_SUBMITTED` 和 `MODERATION_APPEAL_FORBIDDEN`。

## 5. WebSocket 边界

WebSocket 负责：

- 进入世界
- 动作执行
- 房间广播
- 战斗事件
- 聊天实时推送
- 系统通知

## 6. WebSocket envelope

以下均为严格 JSON 示例；字段约束、事件目录与错误码以 `11_PROTOCOL_CATALOG.md` 为准。

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

服务端成功终结：

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

服务端失败终结：

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

广播领域事件：

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

客户端请求顶层字段固定为 `version / request_id / type / payload`。每个服务端应用信封都必须包含 `version / type / seq / ts / payload`；`request.succeeded` 与 `request.failed` 作为终结响应，再额外包含 `request_id`。广播和后续领域事件不携带 `request_id`。

WebSocket 外层统一使用 `type`，不得使用 `event_type`；运行时内部领域事件对象仍可保留 `event_type`。失败详情放在 `request.failed.payload.error`，不再另造无 `type` 的错误 envelope。

## 7. 为什么不直接暴露 Evennia 式对象 API

Evennia `web/api/views.py` 暴露的是：

- ObjectDB
- Evennia `AccountDB`
- ScriptDB
- HelpEntry
- Attribute 直接写入

这适合作为引擎通用管理接口，不适合作为游戏前端 API。

## 8. 安全要求

必须从第一版就落实：

- HTTPS / WSS only
- REST Refresh Token 轮换与 replay 撤销流程
- Django 标准密码哈希体系
- 手机号等敏感字段加密存储
- 动作频率限制
- WebSocket 鉴权过期处理
- 审计日志
- 服务端权威计算

## 9. 审计日志

建议引擎统一提供：

- `initiator_type`（`user / actor / system`）
- `initiator_id`（系统发起时为空；`actor` 只允许 Character/NPC）
- `action_type`
- `target_ref`
- `payload_snapshot`
- `ip`
- `device`
- `created_at`

尤其需要审计：

- 后台改数
- 封禁解封
- 经济修正
- 稀有物品发放
- Blueprint 发布

## 10. V6 增量与最终原则

在每个游戏实例内，`User` 与 `GameAccount` 是永久一对一映射；`CharacterOwnership` 负责未来多角色扩展。注册成功仍不创建 AuthSession、RefreshTokenFamily、Character、PresenceSnapshot 或运行时 Presence，但会在响应中一次性展示 RecoveryCode；服务端只保存其哈希。RecoveryCode 的恢复 / 轮换必须撤销全部旧 AuthSession、refresh family 和票据、终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence，并采用账号/IP/设备合并限流与统一错误响应。

M1 后台只提供 2.2 冻结的恢复流程冻结 / 撤销与持有效 code 的最小修复，不提供人工身份裁决、明文 code 查看、免验证改密或账号重分配。该后台路径与玩家恢复共用 `13` 的事务和并发边界，并必须进入 `16` 的权限、审计与失败原子性矩阵。

Character 创建必须引用版本化 `CharacterCreationProfile`。`CharacterDisplayName` 按 NFKC 在实例内唯一，GM 改名 / 重置必须审计；Public V1 不提供玩家自助 rename、delete 或 rebuild。公开实例的注册模式为可审计的 `open / paused / invite_only` 三态；初始 superuser 只能由安全的一次性管理命令创建，不得存在默认账号或密码。

同一自然人可以同时承担多个 `PlatformRole`。内容编辑和发布可以由同一人执行，但必须是分开的、重新认证的、带 diff 和确认的审计动作；普通批次仍禁止自批。紧急回滚必须记录原因和受影响 `ContentReleaseBatch`。

权限要显式、后台要可审计、API 要面向业务域，而不是面向底层对象库。


