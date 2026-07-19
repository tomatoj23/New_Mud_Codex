# 15 H5 客户端首发契约

> 状态：首发实施契约。本文冻结 uni-app、Vue 3、Pinia 客户端的工程边界、响应式体验、协议接入和验收要求。首发目标是 PC 浏览器与移动端浏览器；微信小程序只保留适配边界，不进入首发构建。

## 1. 工程边界

客户端使用独立 `client/` 工程：

```text
client/
  src/
    api/
    protocol/
    stores/
    pages/
    components/
    features/
      auth/
      world/
      chat/
      combat/
      inventory/
      help/
```

必选技术：

- uni-app（Vue 3）
- Pinia
- TypeScript
- H5 构建目标
- 与 `11_PROTOCOL_CATALOG.md` 同源生成的协议类型

## 2. 状态边界

Pinia 至少拆分：

- `authStore`
- `connectionStore`
- `presenceStore`
- `sceneStore`
- `characterStore`
- `combatStore`
- `chatStore`
- `inventoryStore`
- `uiStore`

服务端状态与本地 UI 状态必须分开。气血、内力、位置、物品数量、战斗状态和动作可用性只能由服务端 snapshot 或事件更新。

`character.snapshot` 的完整字段以 `11_PROTOCOL_CATALOG.md` 为准。客户端必须先校验同一 snapshot 的角色版本、背包版本、Item/Skill 与 binding 引用。

校验通过后，再把 `resources / inventory / equipment / skills / jifa_bindings / prepare_bindings` 原子提交到 `characterStore` 与 `inventoryStore`；不得跨版本或跨消息拼接。

## 3. 协议客户端

- WebSocket 固定连接 `/ws/v1/game`。
- 每个请求携带协议 `version` 和符合 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` 的唯一 `request_id`。
- 同一 ConnectionSession 上重试 `session.authenticate` 时复用原 request id；建立新 WebSocket 后必须为 authenticate 生成新 request id，并等待该连接自己的绑定结果。
- 断线后先恢复认证，再提交已持有的 `resume_ticket`。
- active Presence 上收到序号缺口时请求 `state.sync`，不自行补算状态；尚无 active Presence 时关闭连接并重新执行认证与 enter/resume，不能调用 `state.sync`。
- `source=system` 永远不能由客户端发送。
- refresh token 只可作为 REST refresh 的轮换凭据，或作为 REST logout 的受保护 Cookie locator；不进入 WebSocket、Authorization header 或日志。

active Presence 的每个文本或结构化 `action.invoke` 都必须把当前 `inventoryStore.inventory_version` 作为 `payload.expected_inventory_version` 发送。客户端不判断动作是否修改背包；服务端按 exact ActionDefinition 的 `requires_inventory_version` 决定是否比较。

收到 `INVENTORY_VERSION_CONFLICT` 后，客户端先保持相关 store stale 并执行当前 Presence 允许的 `state.sync`。同步完成后不得自动重放旧动作；只有新的用户意图才能使用新版本再次提交。

客户端不得把完整 `request.succeeded`、`request.failed`、snapshot 或 `resume_ticket` 持久化到 localStorage、sessionStorage、IndexedDB、Service Worker cache 或日志。
为重复响应去重，当前 JavaScript 运行时内存可保留 `request_id`、终结类型与不含秘密的脱敏摘要。WebSocket `request_id` 与完整终结均不得进入持久存储；唯一例外是 3.2 冻结的最小 pending-refresh 控制记录。

`resume_ticket` 只保存在受控内存，登出、会话撤销、显式离场或页面安全清理时立即清除。页面重载导致 ticket 丢失是允许的安全取舍；客户端必须回到正常认证和占用/接管流程，不能从持久缓存恢复秘密。

### 3.1 绑定型终结与跨连接重放

`presence.enter`、`session.resume` 或 `presence.takeover` 返回 `delivery.status=bound` 且 `resume_required=false` 时，客户端才能把 snapshot 原子写入 Presence/scene/character/combat stores，并把新 ticket 放入受控内存。

收到 `delivery.status=resume_required` 时，客户端必须忽略并不得缓存历史 snapshot，只把服务端本次安全交付的 ticket 暂存在内存，然后以新的 `request_id` 调用 `session.resume`。只有该 resume 返回 `bound` 后才把当前连接标为 active；期间不得调用 `state.sync` 或发送 IC 动作。

收到 `delivery.status=superseded` 时，不得认为当前连接已绑定，也不得尝试使用旧 snapshot/ticket。客户端转入普通 enter/占用提示流程；需要接管时必须显示显式确认并发送新的 `presence.takeover`，不得自动升级。

### 3.2 REST refresh 幂等

H5 只调用 `08_PERMISSIONS_ADMIN_API.md` 4.2 的四个开户/认证端点；refresh token 由浏览器自动携带强制安全 Cookie，JavaScript 不得读取、复制或另行传输。每次逻辑 refresh 生成符合 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` 的 `Idempotency-Key`，同一次网络重试必须复用。

统一 logout helper 必须使用 `credentials=include`；access token 仍在内存时同时携带 Bearer，页面重载后 token 已丢失时只依赖 Cookie。无论网络结果能否确认，helper 随后都关闭 WebSocket，清除 pending refresh、access token、ticket 与领域 stores；不得持久化 Bearer 或把 refresh token 放入 Authorization header。

为覆盖“服务端已提交但响应丢失后页面重载”的窗口，客户端必须在发送前通过 origin-wide single-flight 协调器，在 IndexedDB read-write transaction 中原子获取或创建唯一 pending 记录：

```json
{
  "slot": "auth-refresh-v1",
  "idempotency_key": "refresh_01J2Z7M8",
  "endpoint": "/api/v1/auth/refresh",
  "state": "pending",
  "created_at": "2026-07-19T09:30:00.000Z"
}
```

该记录不是 credential，不得包含 token、Cookie、access claims、账号/会话 id、请求或响应 body。所有标签页共用同一 pending key；只有协调器 owner 可发送网络请求，其他标签页等待完成通知，不能各自创建 key 并并发轮换共享 Cookie。

恢复规则固定为：

1. 网络失败、响应丢失或页面重载后，只要记录仍在 `13` 冻结的 refresh 重试窗口内，就用同一 key 和固定空 JSON body 重试；存在 pending 记录时不得生成新 key。
2. `200` 响应到达后，先把新 access token 放入受控内存，再删除 pending 记录并通知等待标签页；token 和响应 body 不得写入 IndexedDB。
3. pending 记录已超过重试窗口时，不再发送 refresh；调用统一幂等 logout helper 后回到登录。
4. pending 恢复收到 `REFRESH_IDEMPOTENCY_CONFLICT` 或 `REFRESH_REQUEST_SUPERSEDED` 时，说明客户端不能证明当前 HttpOnly Cookie 属于哪一代。不得用该 Cookie 配新 key 再试；必须调用统一幂等 logout helper 后回到登录。该保守登出是客户端解决模糊提交，不把 superseded 解释成服务端已判攻击 replay。
5. 收到 `REFRESH_UNAVAILABLE` 或 `SESSION_REVOKED` 时，清除 pending 记录和全部认证内存，回到登录。

`Idempotency-Key`、pending 内容和 refresh 结果均不得进入日志、遥测或异常上报。协调器 lease、页面崩溃接管和多标签页通知可以选择平台实现，但上述单请求、持久 key 与安全登出语义不得改变。

### 3.3 Presence 上下文变化

收到 `REQUEST_CONTEXT_CHANGED` 时，客户端不得用原 request id 重试，也不得应用该请求对应的旧 snapshot、动作结果或 action set。
`state.sync` 若确认当前连接仍有 active Presence，必须保持 store stale，并生成新 request id 重新同步；若已无 active Presence，则关闭连接并进入认证与 enter/resume 流程。
动作或 UI resolve 请求不得自动换 id 重新执行；客户端先应用当前权威状态、重新解析可用动作，并在仍需执行时等待新的用户意图。

## 4. 首发页面与工作流

首发必须提供：

- 注册
- 登录
- 角色创建与选择
- 世界主界面
- 场景查看与移动
- 文本命令输入
- 当前可用动作
- 公共聊天与私聊
- 战斗状态与动作
- 背包、装备和物品使用
- 帮助检索
- 断线、恢复、占用和被接管状态

角色数量策略由服务端下发。首发每个 `GameAccount` 最多创建一个角色，前端不得硬编码未来上限。

## 5. PC 与移动端

PC H5：

- 保留连续键盘输入焦点。
- 支持历史命令和常用快捷键。
- 场景、聊天、角色状态可并列查看。

移动端 H5：

- 主要动作可通过触控完成。
- 输入法弹出后仍可看到输入框和发送动作。
- 窄屏下不横向溢出。
- 场景、聊天、战斗和背包通过稳定视图切换访问。

两端共享领域状态和协议，不要求像素级一致。

首发最低支持矩阵：

- 桌面 Chrome、Edge、Firefox 和 macOS Safari 最近两个稳定主版本。
- iOS 16 及以上 Safari；Android 10 及以上 Chrome 最近两个稳定主版本。
- 360x640、768x1024、1280x720 与 1920x1080 CSS 像素视口。
- 桌面 200% 页面缩放、键盘焦点可见和 WCAG 2.1 AA 核心文本对比度。
- 主要触控目标不小于 44x44 CSS 像素。

中文输入法 composition 期间，Enter、空格或候选选择不得提交命令。只在 `compositionend` 后按用户明确操作发送。

每个发布候选必须在测试证据中固定实际浏览器与操作系统版本，不能只记录“最新版”。

## 6. 安全与隐私

- Access token 只存放在受控内存状态，不得写入 localStorage、sessionStorage、IndexedDB、Cookie 或容器持久存储。未来若改变该边界，必须先修订本合同与威胁模型。
- H5 Refresh token 必须只使用 `08` 4.2 冻结的 host-only `new_mud_refresh` Cookie，并强制 `Secure / HttpOnly / SameSite=Strict / Path=/api/v1/auth/`；不得降级到 JS 可读存储、JSON body 或 Authorization header。
- 日志和错误报告必须脱敏 token、resume ticket、手机号和聊天私信。
- 客户端不显示服务端堆栈或内部对象 id 之外的敏感实现信息。

## 7. 测试要求

- 协议 schema 契约测试
- 完整 `character.snapshot` 对 `characterStore / inventoryStore` 的原子替换、空数组清空和跨版本拒绝测试
- active Presence 的文本与结构化动作都携带 `expected_inventory_version`，背包写动作冲突后同步且不自动重放的测试
- Pinia store 单元测试
- 注册、登录、进世界、移动、战斗、聊天、物品使用端到端测试
- 断线、token 过期、resume ticket 失效和接管测试
- authenticate 同连接重试与跨连接重新绑定测试
- 绑定型终结跨连接 `resume_required`、旧 snapshot 丢弃和显式 takeover 测试
- Presence generation 改变后的旧 action/ui/sync 终结返回 `REQUEST_CONTEXT_CHANGED`，客户端不应用旧结果
- `state.sync` 跨连接或 barrier 已推进时用新 request id 重建屏障，不把历史 snapshot 设为基线
- register/login/refresh/logout 精确路径、四端点跨源拒绝与 refresh Cookie 强制属性测试
- 注册成功后无 token、Cookie 或 AuthSession，重复账号名与密码策略失败只返回稳定错误码
- logout 覆盖损坏 Cookie + 有效 access、Cookie/Bearer 指向不同会话和零 locator 三种路径；客户端始终完成本地清理
- refresh 提交后响应丢失再重载时复用持久 key，多标签页只发送一个逻辑请求
- pending refresh 的 key 冲突、superseded、过期记录均安全登出，不以新 key 重交不确定 Cookie
- refresh 同 key 安全重试与服务端真实 replay 撤销测试
- localStorage、sessionStorage、IndexedDB、Service Worker cache 与日志的终结 payload/ticket 泄漏扫描
- PC 与窄屏移动端视觉回归
- 精确支持矩阵、200% 缩放、输入法、触控目标、键盘焦点、对比度和长文本溢出测试

## 8. 首发验收

- 新用户可在 H5 注册并使用独立 login 登录；注册成功不能被当成认证成功。
- PC 和移动端 H5 均完成同一条首发纵切。
- 断线恢复不产生重复动作或本地权威状态。
- 跨连接历史终结不会直接激活 Presence，非 active Presence 不能发起 `state.sync` 或 IC 动作。
- Presence/连接/seq 上下文变化不会把旧 snapshot 或动作结果写入当前 stores。
- 完整终结与 `resume_ticket` 不进入任何持久客户端存储。
- WebSocket `request_id` 不跨页面生命周期持久化；页面重载后不得凭旧 id 重新物化 ticket。
- H5 refresh secret 只在强制安全 Cookie 中；IndexedDB 只允许无秘密的单条 pending-refresh 控制记录。
- 最长中文名称、聊天消息和错误文案不遮挡核心操作。
- 支持矩阵中的精确浏览器版本、视口、缩放、中文输入法和触控验收全部通过。
- 客户端构建、类型检查、单元测试和端到端测试进入 CI。
- 微信专用 API 不进入首发业务代码；平台差异通过 adapter 保留。
