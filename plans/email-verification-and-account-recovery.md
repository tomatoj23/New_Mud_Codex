# 已验证联系方式注册与账号恢复实施方案

**Status**: `completed`（2026-08-27；Issues #11–#16 工程验收完成，`AUTH-005=verified`；#16 待 GitHub 回填/关闭）

**Delivery unit**: 新建 `Engine Stage E1 / Auth Baseline Amendment`，先于 Character Slice 2

**Current channel**: `email`；`sms` 只保留扩展边界

**Historical boundary**: Issue #9、原 E1 / Slice 1 与 `AUTH-001/002` 保持当时已验证事实

**Published spec**: [GitHub Issue #10](https://github.com/tomatoj23/New_Mud_Codex/issues/10)
**Published tickets**: Issues #11–#16；原生阻塞链为 `#11 -> #12 -> #13 -> #14 -> #15 -> #16`

本文件是交给 `/to-spec`、`/to-tickets` 与后续 `/implement` 的批准计划，不是需求权威。实现前必须先完成第 1 节的权威修订；任何权威来源仍描述 RecoveryCode 注册/恢复时，业务代码保持不变。

## 1. 权威修订

### 决策来源

- [CONTEXT.md](../CONTEXT.md)：`VerifiedContactMethod`、`VerificationChallenge` 与已退役 `RecoveryCode` 的唯一领域词义。
- [ADR-0005](../docs/adr/0005-verified-contact-methods-replace-recovery-code.md)：已验证联系方式取代 RecoveryCode。
- [ADR-0006](../docs/adr/0006-encrypted-verified-contact-storage.md)：联系方式密文与 keyed lookup digest。
- [ADR-0007](../docs/adr/0007-durable-verification-delivery-outbox.md)：持久投递 outbox 与非枚举响应。
- [ADR-0008](../docs/adr/0008-access-tokens-require-active-auth-session.md)：Access Token 必须解析到 active AuthSession。

### 修订顺序

1. 在 GitHub 建立独立的认证基线修订规格，并确认 `AUTH-005` 或下一个可用需求 ID 没有冲突。
2. 修订 `requirements_v6.md` 的注册、恢复、账号关闭、Public V1 公开资料、里程碑和最终确认项；V5 保持历史只读。
3. 同步 `08_PERMISSIONS_ADMIN_API.md`、`13_SESSION_AUTH_STATE_MACHINE.md`、`15_FRONTEND_H5_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md`、`17_REQUIREMENTS_TRACEABILITY.md`、`18_IMPLEMENTATION_STATUS.md`、`19_V6_CONTRACT_DIFFERENCES.md`、tracer plan 与 handoff。
4. 拆开当前 `AUTH-004` 中 RecoveryCode 与 PresenceRecovery 的混合表述：RecoveryCode 只保留历史 provenance；PresenceRecovery 继续属于未来 Character/Presence 切片。
5. 保留 Issue #9 和提交证据，不把已完成的 E1 / Slice 1 改写为未完成，也不复用其 Issue。
6. 运行 `verify_m0.py`、文档合同、Markdown 标题/链接和差异检查；全部通过后才能开始持久层 red test。

**完成条件**：所有现行权威只描述同一已验证联系方式边界；ADR-0004 有 superseded 指针；历史 Issue/提交仍可回查；新追踪记录明确位于 Character Slice 2 之前。

## 2. 产品结果与范围

### 本次交付

- 新注册先验证邮箱，再原子创建 User、当前实例 GameAccount 与 VerifiedContactMethod。
- 注册成功不创建 AuthSession、RefreshTokenFamily、token、Character 或 Presence；用户随后以账号名和密码登录。
- 用户通过已验证邮箱接收短期验证码并设置新密码；成功后全部旧认证凭据立即失效，用户重新登录。
- RecoveryCode 停止签发、展示与消费；现有两个恢复端点进入明确的 410 兼容期。
- H5 只使用“注册”“登录”“邮箱验证码”“找回密码”等产品语言。
- 数据模型和服务接口使用渠道无关词汇，但运行时只接受 `channel=email`。

### 已冻结的后续边界

- 未来短信上线后，注册可以验证邮箱或手机号；登录仍使用账号名和密码。
- 每个 User 每种渠道最多一个 active VerifiedContactMethod；同一规范化联系方式最多属于一个 User。
- `cooling_off -> active` 使用用途独立的 account-reopen challenge，不复用 password-reset challenge。
- 联系方式换绑采用重新认证、验证新渠道、可用旧渠道证明或24小时高风险等待、安全通知和全会话撤销。
- 密码与全部已验证渠道同时丢失时，支持只能冻结账号，不能重分配所有权。
- `cooling_off` 期间保留联系方式以支持重新启用；进入永久 `retired` 后撤销并解绑联系方式、释放唯一性，审计不保留完整地址。
- 单次投递失败不改变所有权；持续明确不可达时标记为 `unreachable`、停止用于恢复并在下次成功登录后提示更换，不自动解绑或转移。

这些后续边界只写入权威和测试禁区；本次不创建对应路由、页面或状态转换。

## 3. 公共 REST 合同

### `POST /api/v1/auth/registration-verification/request`

请求：

```json
{"channel":"email","destination":"player@example.com"}
```

格式有效时统一返回：

```json
{"status":"accepted","retry_after":60}
```

状态为 `202`。响应不包含 challenge ID、User ID、投递状态、占用状态或 provider 结果。

### `POST /api/v1/auth/register`

请求：

```json
{
  "username": "player",
  "password": "...",
  "verification": {
    "channel": "email",
    "destination": "player@example.com",
    "code": "123456"
  }
}
```

成功返回 `201` 与 User/GameAccount identity；不返回 token、Cookie、RecoveryCode 或 AuthSession。

### `POST /api/v1/auth/password-reset/request`

请求为 `{"channel":"email","destination":"player@example.com"}`。格式有效时与未知、不可恢复或不可达联系方式统一返回相同 `202` body。

### `POST /api/v1/auth/password-reset/confirm`

请求：

```json
{
  "channel": "email",
  "destination": "player@example.com",
  "code": "123456",
  "new_password": "..."
}
```

成功返回 `204`；不返回 token，不设置 refresh Cookie，不改变 GameAccount lifecycle。

### 公共错误与幂等

- `CONTACT_INVALID`：格式无法进入非枚举流程。
- `CONTACT_CHANNEL_UNAVAILABLE`：当前未开放的渠道，包括 `sms`。
- `VERIFICATION_RATE_LIMITED`：合并限流，带 `retry_after`。
- `VERIFICATION_CODE_INVALID`：错误、过期、锁定、已消费、已替代或跨用途 code 的统一结果。
- `REGISTRATION_UNAVAILABLE`、`PASSWORD_RESET_UNAVAILABLE`：终局无法提交，但不泄漏内部对象。
- `VERIFICATION_SERVICE_UNAVAILABLE`：只由与具体账号无关的全局 fail-closed 状态返回。
- `RECOVERY_CODE_RETIRED`：旧 RecoveryCode 路由的 `410`。

request 端点要求 `Idempotency-Key`。同 key、同请求安全重放同一终结；同 key、不同请求返回稳定冲突。客户端没有 challenge 状态查询端点，不自动重发；用户在冷却结束后明确重发才创建新的逻辑请求。

所有认证响应使用 `Cache-Control: no-store`、冻结 Origin 策略和稳定 JSON 外形。

**完成条件**：API 合同测试覆盖 method/path/body/status/error、幂等重放/冲突、Origin、no-store、非枚举反例和响应秘密扫描。

## 4. 用户流程

### 邮箱验证注册

1. H5 收集邮箱并提交 registration-verification request。
2. 服务端规范化邮箱，执行联系方式/IP/设备合并限流；符合资格时创建 pending challenge 与 delivery outbox。
3. API 统一返回202；H5 显示“如果信息有效且服务可用，你将收到验证码”并开始60秒手动重发倒计时。
4. Worker 投递验证码。provider 接受后激活新 challenge、替代旧 active challenge，并从激活时刻开始10分钟 TTL。
5. 用户提交账号名、密码、邮箱和验证码。
6. 单一 PostgreSQL 事务验证 challenge，执行 Django 密码策略与唯一约束，创建 User、当前实例 GameAccount、VerifiedContactMethod，并消费 challenge。
7. H5 显示“注册成功，请登录”。

发码阶段不创建 User、不预留账号名。账号名在等待期间被占用时，用户可以更换账号名并继续使用仍有效的同一邮箱 challenge。

### 邮箱密码重置

1. H5 收集邮箱并提交 password-reset request。
2. 只有 active、未禁用且持有可用 VerifiedContactMethod 的 User 才进入投递 outbox；公开响应保持一致。
3. 用户提交邮箱、验证码和符合当前 Django 策略的新密码。
4. 单一事务消费 challenge、修改 User 密码、撤销该 User 跨实例的 AuthSession/RefreshTokenFamily/active credential，取消适用的未完成 challenge/outbox，并写入安全通知任务。
5. 所有旧 access/refresh 定位立即失败；H5 返回登录入口。

Password reset 不把 `cooling_off` GameAccount 改回 `active`，也不创建或恢复 Presence。

### RecoveryCode 退役

- `POST /api/v1/auth/recover` 与 `POST /api/v1/auth/recovery-code/rotate` 同时停止消费 code，并返回 `410 RECOVERY_CODE_RETIRED`。
- 当前数据库的40个 User/GameAccount/active RecoveryCode 均为开发测试数据。数据切换撤销40条 active code，但不把本决定解释为自动删除账号的授权。
- 当前 H5 与合同迁移后创建独立清理项删除旧路由；删除必须在 Public V1 前完成。

## 5. 领域与持久模型

### VerifiedContactMethod

首期字段至少表达：

- UUID identity、User、`channel=email`、state、verified/unreachable/revoked 时间、version。
- 规范化目标的密文、加密 `key_id` 和 keyed lookup digest。
- 每个 User/channel 最多一个 active 或 unreachable 联系方式。
- 每个 channel/lookup digest 最多属于一个未退休 User。

迁移期既有开发 User 可以有0个联系方式；新的自助注册事务结束时必须恰好创建一个 verified email。Django `User.email` 保持为空，业务与管理代码不得把它当作回退来源。

`unreachable` 仍占用 User/channel 与 channel/lookup digest 唯一性，但不能签发恢复 challenge。只有受审计的换绑、账号永久退休或明确的数据保留终结可以释放该联系方式。

### VerificationChallenge

首期 purpose 只启用 `registration` 与 `password_reset`；未来值不产生可调用能力。字段至少表达：

- UUID、purpose、channel、destination lookup digest、可选 User。
- code digest 与 pepper key identity。
- `pending_delivery / active / consumed / superseded / expired / locked / delivery_failed`。
- attempt count、issued/activated/expires/consumed/superseded 时间与 version。

registration 不绑定 User；password_reset 必须绑定 User。purpose、channel、destination 与 User 共同进入摘要上下文，任何跨用途或跨渠道消费都失败。

### VerificationDeliveryOutbox

字段至少表达 challenge、模板 key、临时加密 payload 与 key identity、state、attempt/lease/next-attempt、created/delivered/terminal 时间及脱敏 provider category。

- 每个逻辑 challenge 只有一个投递任务。
- worker claim 使用租约与并发安全终结；进程重启可重入。
- 重试重发同一验证码。
- provider 接受后才激活 challenge；激活事务成功后擦除 outbox payload。
- provider 已接受但本地确认前崩溃可以重复发送同一码，不能产生第二个 active code。
- 投递失败时旧 active challenge 保持原有效期。

### 数据保护

- 完整联系方式只以应用层密文存在；精确查询和唯一性只使用 keyed digest。
- code digest pepper、contact encryption、contact lookup、delivery payload encryption、Django、SMTP 与 token 使用不同密钥。
- 密文携带 key identity，支持 current-write/old-read 轮换；缺少适用密钥时验证功能 fail closed。
- terminal challenge/outbox 立即擦除验证码 payload 和完整目标；非秘密诊断元数据保留30天。
- 脱敏认证审计保留365天，不保存 code、digest、完整联系方式、邮件正文、授权码或 token。

**完成条件**：PostgreSQL 约束、迁移往返、密钥轮换、密文/lookup 分离、terminal 擦除和离线数据库泄漏测试全部通过。

## 6. 邮箱规范化与投递

首期接受 ASCII local-part 与 IDNA domain。比较键对整个 mailbox 大小写折叠；投递使用规范化可投递形式。不执行 Gmail 点号、plus tag、MX 查询、临时邮箱黑名单或其他 provider 专有规则。SMTPUTF8 local-part 等邮件服务验证兼容后另立切片。

邮件模板只使用 UTF-8 纯文本：

- `[New_Mud] 注册验证码`
- `[New_Mud] 密码重置验证码`
- `[New_Mud] 安全操作通知`

验证码正文包含用途、6位 code、10分钟有效期、忽略说明和“工作人员不会索要验证码”。安全通知不包含可执行反向恢复链接。正文不包含用户名、密码、内部 ID、access/refresh token 或 RecoveryCode。

密码重置、未来 account reopen 和联系方式换绑成功后，向所有仍适用的联系方式写入安全通知 outbox。通知投递失败不回滚已提交的安全事务，但必须告警并审计。

## 7. 验证码、限流与秘密

冻结默认值：

- code：6位数字，10分钟 TTL，最多5次校验。
- resend cooldown：60秒；TTL 从成功激活开始，cooldown 从请求接受开始。
- 每联系方式：5次/15分钟、10次/24小时。
- 每 IP：20次/15分钟、100次/24小时。
- 每设备：10次/15分钟、30次/24小时。

请求和确认都参与 PostgreSQL 持久合并限流。服务端只信任显式配置的反向代理链；否则只使用直接 peer address。设备标识是随机、无 PII、host-only、Secure、HttpOnly、SameSite=Strict、仅限认证路径的短期 Cookie。限流存储异常时验证功能 fail closed，普通账号名/密码登录继续使用其独立防护。

当前内部切片不绑定 CAPTCHA 供应商；Public V1 前独立评审隐私、无障碍、成本与滥用证据，并保留可插拔策略。

## 8. 会话与事务边界

### Access Token

每个受保护 HTTP/WS 入口必须验证签名、audience、expiry，并读取对应 AuthSession、User 与适用 GameAccount 的当前状态。AuthSession 非 active、User 禁用或适用 GameAccount 不允许操作时拒绝；JWT 剩余寿命不能绕过撤销。

### 注册事务

事务锁定并重验 active registration challenge，随后依靠 username 与 contact lookup digest 的数据库唯一约束收敛竞争。User、GameAccount、VerifiedContactMethod 和 challenge consumption 要么全部提交，要么全部回滚。两个并发提交最多一个创建身份。

### 密码重置事务

固定顺序为 User → VerifiedContactMethod → VerificationChallenge → 该 User 的 GameAccount（实例与主键排序）→ AuthSession（主键排序）→ family/credential（主键排序）→ 适用 challenge/outbox。提交前重验 User、联系方式、challenge 与 GameAccount lifecycle/version。

成功事务设置 Django 密码哈希、消费 reset challenge、撤销全部认证状态并取消其他未完成恢复任务。未来 Presence/ticket 的撤销仍只保留合同接缝；本次没有对应模型可创建或验收。

**完成条件**：真实 PostgreSQL 竞争测试覆盖登录与 reset、双注册、双 code 消费、幂等请求、worker claim、事务故障与 deadlock/serialization loser；失败路径没有半账号、漏撤销会话或多个 active challenge。

## 9. H5 产品边界

- 删除“独立登录”和 RecoveryCode 卡片/离线保存说明，统一显示“登录”。
- 注册增加邮箱、发送验证码、60秒倒计时、验证码输入和手动重发。
- 增加“忘记密码”：邮箱 → 请求验证码 → code 与新密码 → 成功后返回登录。
- request 的 accepted 文案不宣称地址存在或邮件一定成功。
- 浏览器持久存储不保存密码、验证码、access token、完整联系方式、reset 结果或投递状态。
- 网络层不得自动重发发码请求；同一网络请求只按 Idempotency-Key安全重放。
- 完整联系方式只在当前表单内短暂存在；离开流程后清理，其他页面只显示遮罩值。

主切片自动验收使用：

- 1280×720 CSS 桌面。
- 412×915 CSS / DPR 3 现代移动竖屏。
- 915×412 CSS / DPR 3 长比例横屏。
- 360×640 只作无横向溢出守卫，不作为主流程设计目标。

Public V1 的完整浏览器、中文输入、200%缩放和无障碍矩阵不因本切片缩减；物理1080p、1.5K、2K 与21:9设备通过 CSS viewport/DPR 和后续发布矩阵覆盖。

## 10. 配置与运行

本机 163 SMTP 继续使用被 Git 忽略的 `.env.smtp.local.ps1`；新授权码只填写：

```powershell
$env:EMAIL_HOST_PASSWORD = ""
```

实施 foundation ticket 时，把现有 email-specific pepper 占位符改为渠道无关名称，并增加空的 contact encryption、contact lookup、delivery payload encryption 与 current key-id 占位符。所有值由用户或部署 secret manager 注入，不写入 tracked example、Issue、测试 fixture、命令参数、日志或对话。

默认测试使用 fake/locmem adapter，不连接公网。真实163 smoke 只有 `RUN_SMTP_TESTS=1` 且显式收件人存在时运行；POP3/IMAP 不参与。163 只用于开发；Public V1 开放注册前必须换成受控域名和正式服务，并验证 SPF、DKIM、DMARC、退信、配额、告警和基本送达。

生产启动只有在密钥 keyring、current key IDs、outbox worker health 和 provider circuit 状态全部有效时才允许开启验证注册/密码重置 feature flag。登录不依赖这些开关。

Public V1 的所有可交互人员账号，包括管理员，都必须持有 VerifiedContactMethod。初始 superuser 只能通过安全命令创建，并在开放远程登录前完成验证；测试 bypass 只存在于隔离 test settings，生产配置检测到 bypass 必须拒绝启动。机器身份以后另建概念，不伪装成人类 User。

## 11. Ticket 依赖图

### A. 权威规格（Issue #11）

修订 V6、冻结合同、trace/status、计划索引和 handoff；创建新的认证基线需求与 GitHub tickets。

**完成条件**：第 1 节门禁通过；所有实现 ticket 引用同一规格与 ADR；没有业务 diff。

### B. 密钥、持久层、限流与投递（Issue #12）

test-first 实现 keyring、contact crypto/lookup、VerifiedContactMethod、VerificationChallenge、outbox、持久限流、EmailSender、worker、模板和配置 fail-closed。

**阻塞**：A。

**完成条件**：模型/迁移/crypto/outbox/限流/模板的 PostgreSQL 与 fake adapter 矩阵通过，默认测试零公网。

### C. 邮箱验证注册（Issue #13）

test-first 实现 registration-verification request、register challenge consumption、零认证注册响应和对应 H5 流程。

**阻塞**：B。

**完成条件**：注册 API、事务并发、回滚、H5 三主视口和秘密扫描通过；feature flag 仍关闭。

### D. 密码重置与即时撤销（Issue #14）

test-first 实现 reset request/confirm、受保护入口 AuthSession 状态校验、跨实例全会话撤销、安全通知和 H5 忘记密码。

**阻塞**：C。

**完成条件**：旧 access/refresh 立即失败，reset 不改变 lifecycle、不自动登录，枚举/并发/通知失败矩阵通过。

### E. RecoveryCode 退役与原子切换（Issue #15）

撤销测试数据 active code，两个旧 API 进入410，删除 H5 展示，完成 feature flag/circuit breaker、worker readiness 和 C+D 集成。

**阻塞**：C、D。

**完成条件**：没有 code 消费路径；新注册与 reset 同时可用；账号名/密码登录始终可用；不存在部分开放窗口。

### F. 证据与关闭（Issue #16）

执行全量门禁、真实 SMTP opt-in smoke、Standards + Spec 双轴复审，回填 tickets 和状态账本。

**阻塞**：E。

**完成条件**：已完成。第 12 节各层的日期、环境、命令、结果和例外已记录在 `docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md`；SMTP 开发 smoke 因没有显式 opt-in、收件人和秘密授权而准确记录为 1 skipped，不伪造公网发送。首轮双轴 hard findings 已修复，正式复审无未解决 hard finding；PublicV1Gate 未被提升。

每个实现 ticket 在新上下文运行 `/implement`，由其内部逐条 `/tdd` 并以 `/code-review` 收尾。PostgreSQL 测试串行；独立 ticket 不共享未提交工作。

## 12. 最低测试与证据矩阵

### 数据与密码学

- 邮箱 ASCII/IDNA、大小写比较、无 provider 折叠、非法输入。
- contact 密文不可等于规范值；lookup 唯一、key isolation、current-write/old-read rotation。
- code CSPRNG、digest purpose/channel/destination/User 隔离、pepper rotation。
- terminal payload 擦除、30/365天保留边界和秘密扫描。

### Challenge、outbox 与限流

- pending/active/consumed/superseded/expired/locked/delivery_failed。
- 正确、错误、过期、尝试耗尽、旧码、跨用途、跨渠道和双消费。
- worker 双 claim、lease expiry、provider transient/permanent failure、同码重试、接受后崩溃和 payload wipe。
- 新码投递成功才 supersede；失败保留旧 active。
- 同 key 重放、key conflict、手动 resend、冷却、15分钟/24小时跨重启持久限流。
- 未知/占用/不可恢复地址的 status/body/header 和可比响应路径。

### 注册与恢复

- 注册零 AuthSession/token/Cookie/Character/Presence。
- username/contact 并发唯一、challenge 单消费、任一步故障全回滚。
- reset 的 User/GameAccount lifecycle eligibility、Django 密码策略和并发消费。
- reset 后跨实例 AuthSession/family/credential、旧 access/refresh 和未完成恢复任务全部失效。
- 安全通知成功/失败；通知失败不回滚密码事务。
- RecoveryCode 两路410、40条测试 code revoked、无 rotate/recover 消费路径。

### H5 与运维

- 三主视口注册、登录、错误、reset；360宽度守卫。
- 无“独立登录”或 RecoveryCode 文案。
- localStorage/sessionStorage/IndexedDB/Cache Storage、Cookie、console、network body 的秘密扫描。
- worker/provider/key/limiter 故障时验证功能统一关闭，普通登录可用。
- fake 默认测试与 opt-in 163 smoke；生产 provider readiness 只记录缺口，不伪造 Public V1 证据。
- 全量回归证明 Character、Presence、PresenceRecovery 与 takeover 未提前实现。

最终门禁至少包括 PostgreSQL 全量 pytest、迁移 drift/往返、Ruff、format、mypy、Django check、pip/npm audit、M0/Markdown 合同、Vitest、typecheck、H5 build、Playwright、secret scan 和双轴复审。

## 13. 发布、回滚与监控

开发 ticket 可以逐个合入，但对用户只有一次切换：

1. 部署兼容 schema、crypto、outbox worker、监控和关闭的 feature flags。
2. 验证 fake、163 smoke、worker lease/retry、全局 circuit breaker 与密钥恢复。
3. 部署 C、D、E 前后端与410兼容路由。
4. 在同一受控切换中开启邮箱注册和密码重置、停止 RecoveryCode 消费。
5. 验证注册、reset、旧 code 410、旧 token 撤销和普通登录。

可回滚行为：

- 关闭验证注册/reset，保留普通登录。
- 不回滚已验证联系方式、已修改密码、已撤销会话或已撤销 RecoveryCode。
- 不复活已擦除 payload 或旧 code。
- schema 迁移支持往返；不可逆数据撤销与结构回滚分开演练和记录。

监控至少覆盖 outbox backlog/oldest age、claim lease、attempts、delivery latency/success/failure、provider circuit、challenge activation/consume/lock、persistent rate limit、reset success、security-notice failure和 key lookup failure。指标与告警不含完整联系方式或验证码。

## 14. 当前明确不实现

- SMS provider、手机号国家范围、模板报备、短信成本与 consent。
- 邮箱/手机号作为登录名、passwordless、MFA、微信登录。
- 联系方式绑定管理页、自助换绑及24小时 replacement worker。
- account close/reopen/retirement 路由与任务。
- SMTPUTF8、HTML/营销邮件、订阅、IMAP/POP3、退信 webhook。
- Character、CharacterOwnership、ConnectionSession、Presence、PresenceSnapshot、enter/resume/recover/takeover。
- CAPTCHA provider、容量/soak、完整发布浏览器矩阵或 PublicV1Gate 完成声明。

## 15. 最终验收清单

- [x] V6、ADR、CONTEXT、API/状态机/H5/测试合同和追踪状态一致。
- [x] 新注册必须验证唯一邮箱，且注册后零认证状态。
- [x] 邮箱密码重置用途隔离、短期、单次，只保存摘要与临时加密投递 payload。
- [x] RecoveryCode 不再签发、展示或消费；旧 API 410，测试数据 code 全部撤销。
- [x] 旧 access/refresh 在敏感事务提交后立即失效；普通登录不依赖邮件系统。
- [x] 联系方式单一真源、密文/lookup 分离、key rotation、terminal 擦除和审计保留通过。
- [x] 非枚举202、幂等 request、持久限流、outbox 故障恢复与安全通知通过。
- [x] H5 只显示普通“登录”语言，三主视口流程和持久存储秘密扫描通过。
- [x] 默认测试零公网；真实163 smoke 只可显式启用，本轮准确记录为 1 skipped；Public V1 provider 缺口如实保留。
- [x] PostgreSQL、迁移、静态、单元、集成、E2E、依赖和秘密扫描已通过或按门禁准确记录；本机 gitleaks 下载缺口未伪造为通过，CI gate 保留；正式双轴复审无未解决 hard finding。
- [x] Issue #9/E1 Slice 1 历史未被倒写，新的认证基线 tickets 有阻塞边、证据、风险和回滚记录。
- [x] Character、Presence、PresenceRecovery、takeover、SMS、换绑和 reopen 均未提前实现。
