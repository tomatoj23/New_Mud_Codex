# 08 权限、后台与 API 契约

> 术语说明：本文默认使用 `User / GameAccount / PlatformRole / AuthSession / Presence / ActorRef`。`AccountDB` 仅在比较 Evennia API 设计时作为来源术语出现。

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

## 3. Django Admin 的定位

Evennia 用 Django Admin 扩展做了大量后台能力，这个方向值得保留。

New_Mud 建议：

- 基础数据管理走 Django Admin
- 复杂编辑器走自定义 admin views / management pages
- 不强迫一切内容都在原生表单里编辑

## 4. REST API 边界

### 4.1 版本策略

结合 `requirements_v5.md` 对稳定接口与前后台认证边界分离的约束，对外 REST API 从第一版起必须带显式版本号。

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
| `POST /api/v1/auth/register` | JSON `username / password` | `201` User 与 GameAccount id；不签发 token、不设置 Cookie |
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

注册成功响应只包含 `user_id / game_account_id`。

注册必须把账号名规范为 3-32 位 ASCII 小写字母、数字和下划线，并按规范值执行大小写不敏感唯一校验。

注册事务只创建 `User` 与一对一首发 `GameAccount`。任一步失败整体回滚；不得创建 AuthSession、refresh family、credential、Cookie、Character 或 Presence。

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

active 候选的 lifetime family 和 active credentials 置为 revoked，AuthSession 置为 logged_out，并在同一事务关闭 active/grace PresenceSnapshot、撤销 ticket。连接在提交后关闭或由下一请求拒绝。

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

- `actor_ref`
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

## 10. 最终原则

权限要显式、后台要可审计、API 要面向业务域，而不是面向底层对象库。


