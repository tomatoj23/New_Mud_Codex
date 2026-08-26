# 下一会话交接：Auth Baseline Amendment 权威已修订，下一步 Issue #12

> 快照日期：2026-08-26。
>
> 本文件是无会话记忆时的现行启动入口。它汇总继续工作必需的仓库状态、已完成边界、固定决策、未完成证据和启动顺序；不创造需求、合同或正式状态。冲突时按 `docs/19_documentation_governance.md` 回到对应权威来源。

## 1. 新会话先做什么

在仓库根目录依次执行：

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count HEAD...origin/main
git log -8 --decorate --oneline
```

期望结果：

- 分支是 `main`，工作树为空；若不为空，先辨认并保留已有修改。
- Issue #9 的 E1 / Slice 1 历史提交仍可回查；Issue #10 是现行认证修订规格；Issue #11 是权威同步检查点。
- GitHub 原生子票顺序为 #11–#16，阻塞链为 `#11 -> #12 -> #13 -> #14 -> #15 -> #16`。
- #11 关闭后，唯一 frontier 是 #12；不要跳到 Character Slice 2。

若本机 PATH 找不到全局 `gh`，使用 `artifacts\reports\gh-cli\expanded\bin\gh.exe`。当前已验证环境是 Windows 10 `10.0.19045`、仓库 `.venv` 中的 CPython `3.14.2`、PostgreSQL `18.4` 和 `requirements.lock` 的精确依赖。

## 2. 当前结论

### 2.1 已完成并固定

- 产品里程碑 M0 已 `complete`；`MILESTONE-001` 与 `ENGINE-001 / Engine Stage E0` 已 `verified`。
- Issue #9 / Engine Stage E1 / Slice 1 仍是当时注册、普通登录、refresh/logout、RecoveryCode 与 H5 single-flight 的已验证历史事实。
- Issue #10 已批准 `AUTH-005`：VerifiedContactMethod 与 VerificationChallenge 取代 RecoveryCode，当前渠道只启用 email。
- Issue #11 已把 V6、冻结合同、追踪、状态、差异、路线、tracer plan 和本交接统一到新认证权威；本票没有修改数据库、运行配置或业务行为。
- CONTEXT 与 ADR-0005 至 ADR-0008 固定联系方式权威、密文/lookup 分离、持久 outbox 和 Access Token 必须解析 active AuthSession。
- Character Slice 2 被整个 Auth Baseline Amendment 阻塞；只有 Issue #16 完成后才能启动。

### 2.2 Issue 索引

| Issue | 状态/职责 | 阻塞 |
| --- | --- | --- |
| #9 | 已关闭；E1 / Slice 1 历史证据 | — |
| #10 | Open Spec；已验证联系方式注册与账号恢复基线修订 | — |
| #11 | 权威修订；V6/合同/追踪/状态/计划/交接 | 无 |
| #12 | challenge、crypto、持久限流、outbox 与 worker 投递 tracer | #11 |
| #13 | 已验证邮箱最终注册与 H5 | #12 |
| #14 | 邮箱密码重置、即时认证撤销与 H5 | #13 |
| #15 | RecoveryCode 退役与原子切换 | #14 |
| #16 | 分层证据、SMTP opt-in smoke 与双轴复审 | #15 |

## 3. 不得混用的状态

| 命名空间/记录 | 当前值 | 准确含义 |
| --- | --- | --- |
| 产品里程碑 M0 | `complete` | V6 的 M0 产品结果已完成 |
| `MILESTONE-001` | `verified` | 有证据证明 M0 已 complete |
| `ENGINE-001` / E0 | `verified` | Engine Stage E0 实现与验收已关闭 |
| `AUTH-001`、`AUTH-002` | `verified` | Issue #9 的注册零隐式登录和会话生命周期历史证据仍成立 |
| `AUTH-004` | `retired` | RecoveryCode + PresenceRecovery 的旧复合追踪项已拆开，ID 不复用 |
| `IDENTITY-001` | `verified` | 每实例一个 User 永久映射一个 GameAccount 已由 Issue #9 验证 |
| `AUTH-005` | `specified` | 新认证权威已明确，运行实现与最终证据仍待 #12–#16 |
| `AUTH-006` | `specified` | PresenceRecovery 属于未来 Character Slice 2，takeover 仍独立 |
| `CLIENT-001`、`NFR-001`、`NFR-002` | `blocked` | 完整浏览器、容量/soak 与发布级恢复证据未完成 |
| `RELEASE-001` / PublicV1Gate | `blocked` | 尚不具备公开接纳真实玩家的发布证据 |

追踪状态使用 `specified / implemented / verified / blocked / retired`；产品里程碑状态使用 `not_started / in_progress / blocked / complete`。不要把产品 M0 写成 verified，也不要把 `MILESTONE-001` 写成 complete。

## 4. 已冻结、不要重新解释的认证决策

- 登录仍只使用账号名和密码；邮箱、未来手机号不是登录名、passwordless 或 MFA。
- 新注册必须先验证 email，最终事务创建 User、当前实例 GameAccount 与 VerifiedContactMethod，但创建零 AuthSession/token/Character/Presence。
- password reset 只使用 purpose 隔离的短期 VerificationChallenge，成功后撤销 User 跨实例全部 AuthSession/family/credential，不改变 GameAccount lifecycle，也不自动登录。
- RecoveryCode 不再签发、展示或消费。旧 recover/rotate 先返回 `410 RECOVERY_CODE_RETIRED`，Public V1 前删除。
- 完整联系方式只保存应用层密文；精确查询和唯一性只使用独立 keyed lookup digest；Django `User.email` 保持为空。
- HTTP 不同步发送 SMTP。VerificationDeliveryOutbox 与独立 worker 负责投递、同 code 重试、provider 接受后激活和 terminal payload 擦除。
- 格式有效的 request 返回非枚举 202；request 需要 `Idempotency-Key`，限流状态持久化到 PostgreSQL，并合并联系方式、IP 和匿名设备维度。
- 每个受保护 HTTP/WebSocket 入口必须把 access token 解析到仍 active 的 AuthSession；JWT 剩余寿命不能绕过撤销。
- 默认自动测试使用 fake/locmem 邮件适配器且零公网。163 SMTP 只用于显式 opt-in 的开发 smoke；秘密只从 Git 忽略的本地环境文件或部署 secret manager 注入。

## 5. 历史边界

- Issue #9、`AUTH-001/002` 与 E1 / Slice 1 的 134 项真库 pytest、静态门禁和 H5 E2E 证据不被倒写。
- 历史文本中的“独立登录”和 RecoveryCode 描述只说明当时交付，不是当前产品文案或后续实现授权。
- ADR-0004 已由 ADR-0005 取代其中 RecoveryCode 决策；其“不自动恢复 Presence”以及 PresenceRecovery 与显式 takeover 分离的边界继续成立。
- `requirements_v5.md`、归档 handoff 与旧工作日志保持只读历史，不回写新决策。

## 6. 当前明确不实现

- SMS provider、手机号国家规则、短信模板报备、成本、consent 与发送限制。
- 邮箱/手机号作为登录名、passwordless、MFA 或微信登录。
- 联系方式管理页面、自助换绑、24 小时 replacement worker。
- 账号关闭、重新启用、永久退休任务与公开端点。
- Character、CharacterOwnership、ConnectionSession、Presence、PresenceSnapshot、enter、resume、PresenceRecovery 与 takeover。
- CAPTCHA provider、完整发布浏览器矩阵、容量/soak 或 PublicV1Gate 完成声明。

## 7. Issue #12 的唯一合法启动顺序

1. 完成第 1 节仓库与 Issue 检查，确认 #11 已关闭、#12 无其他 open blocker 且未被他人认领。
2. 阅读 Issue #10、#12、`CONTEXT.md`、ADR-0005 至 ADR-0008，以及 V6 第 8 章和 08/13/16 的认证修订段落。
3. 认领 #12；按 `/implement` 内部逐条 `/tdd`，先确认公开 seam：registration-verification REST、PostgreSQL 持久不变量、worker + fake provider。
4. 只实现 #12 的 challenge/crypto/lookup/outbox/limiter/worker tracer，不提前实现最终 register、password reset、RecoveryCode 切换或 H5 页面。
5. PostgreSQL 测试串行运行；默认测试零公网，不使用真实 SMTP 作为必需门禁。
6. 完成受影响测试、全量/静态门禁和 Standards + Spec 双轴复审后提交、回填并关闭 #12；随后 frontier 才是 #13。

## 8. 权威来源

| 问题 | 来源 |
| --- | --- |
| 产品结果、范围、里程碑 | `requirements_v6.md` |
| 领域名称和定义 | `CONTEXT.md` |
| 长期认证决策 | `docs/adr/0005-0008` |
| API、状态机、H5、运维测试机制 | `docs/new_engine/08`、`13`、`15`、`16` |
| 需求证据成熟度 | `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` |
| 当前实现与验证结果 | `docs/new_engine/18_IMPLEMENTATION_STATUS.md` |
| 实施顺序 | `docs/new_engine/10_ROADMAP.md`、`plans/m0-e1-tracer-bullets.md` |
| 完整批准规格 | GitHub Issue #10 |
| 当前 ticket | GitHub Issue #12 |

## 9. 工程与证据边界

- 保留来源不明的已有修改，不执行破坏性还原或清理。
- `evennia-main/` 和 XKX100 来源目录只作为参考/输入，不改写。
- 邮箱授权码、PostgreSQL 凭据及所有密钥不进入仓库、Issue、命令参数、日志、fixture 或合同制品。
- PostgreSQL 测试与全量 pytest 严格串行，避免数据库和临时目录竞争。
- 结构检查、局部测试、内部候选或 163 smoke 都不能提升 PublicV1Gate。
- 现行事实只更新本入口、17/18、计划或对应权威文档；归档只用于历史追溯。
