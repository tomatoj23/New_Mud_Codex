# 下一会话交接：Issue #18 已完成；下一入口是 #19 `presence.enter`

> 快照日期：2026-08-30（Asia/Shanghai）。
>
> 本文件面向“新会话没有任何历史上下文”的接手场景。它只缓存 Git、工作树、已验证实现、风险和启动顺序；需求冲突时按 `docs/19_documentation_governance.md` 回到权威来源。
>
> **证据规则**：Issue #18 的 GitHub 评论已被项目所有者判定为完全不可信。不得用这些评论证明需求、完成度或测试结果；#18 一律以本地仓库、`CONTEXT.md`、ADR、冻结合同、Git 提交和可复现测试为准。

## 1. 新会话的第一分钟

在仓库根目录运行：

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count HEAD...origin/main
git log -8 --decorate --oneline
git hash-object src/new_mud/apps/characters/models.py
git hash-object src/new_mud/apps/characters/migrations/0005_presencesnapshot_resumeticketcredential_and_more.py
```

预期：

- 分支为 `main`。
- `main` 至少包含 #18 的三个实现提交：
  - `ea05528 feat: add game websocket authentication session`
  - `eb6ce21 fix: harden websocket token replay validation`
  - `59e41a0 fix: close websocket contract gaps (#18)`
- 本交接提交位于 `59e41a0` 之后；本次任务会把这条提交链推送到 `origin/main`。
- 提交后工作树仍故意保留且只应保留下面两个 #19/#20 WIP：

```text
 M src/new_mud/apps/characters/models.py
?? src/new_mud/apps/characters/migrations/0005_presencesnapshot_resumeticketcredential_and_more.py
```

- 两个 WIP 的当前内容哈希必须分别为：

```text
models.py: 29ed90491bb4da4078772306ec137fa81350516f
migration: e6a01d90717032b5dedfb3f7f76e01cbd5c23857
```

状态或哈希不符时先审计来源。使用精确路径操作，保留用户已有修改；不要运行 `git reset --hard`、`git checkout --`、`git clean`，也不要对未审计目录做递归删除、移动或批量格式化。

仓库 skills 已 setup，**跳过 `/setup-matt-pocock-skills`**。先查看 `.agents/skills/` 的实际内容；#19 默认适合使用 `ask-matt`、`tdd`、`codebase-design`，遇到失败再用 `diagnosing-bugs`，收口使用 `code-review`。

## 2. 当前真实状态

### 2.1 已完成的纵向链

- M0 产品结果为 `complete`；`MILESTONE-001` 与 `ENGINE-001 / Engine Stage E0` 为 `verified`。
- Issue #9 的注册、账号名/密码登录、AuthSession、refresh/logout 和 H5 single-flight 是已验证历史事实。
- Auth Baseline Amendment 已完成：Issues #11–#15 交付 VerifiedContactMethod/VerificationChallenge、已验证邮箱注册、邮箱密码重置、即时认证撤销、RecoveryCode 不可逆退役与 worker heartbeat/circuit；Issue #16 完成分层证据和无未解决 hard finding 的正式复审，证据账本见 `docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md`；`AUTH-005=verified`。
- Issue #17 已交付版本化 Character 创建、CharacterOwnership、单角色容量、名称策略、幂等/并发、REST 与 H5；`CHARACTER-001=implemented`。它没有实现 ConnectionSession、Presence、恢复或 takeover。
- Issue #18 已在本地完整实现并提交。代码实现完成不等于本轮已修改 GitHub tracker；远端 issue 状态需要单独读取，但 #18 评论不能作为证据。

### 2.2 #18 实现边界

#18 交付了 ConnectionSession 与 `session.authenticate` 的完整本地纵切：

- `/ws/v1/game` 建立运行时 ConnectionSession；状态为 `opening -> active -> closing -> closed`。
- 认证前只存在 ConnectionSession；`session.authenticate` 以 access token 绑定已有 active AuthSession。
- 每次认证、受保护请求以及五秒周期回查都通过统一 active AuthSession 领域缝；JWT 剩余寿命不能绕过撤销。
- 认证前加入 AuthSession channel group，再回库最终确认 active，关闭“验证成功和加入撤销通知组之间”的竞态。
- logout/reset/replay 等撤销提交后通知在线连接关闭；channel 通知异常或静默丢失时，周期数据库回查在有界时间内 fail closed。
- `session.authenticate` 和 `session.ping` 使用连接本地幂等；跨 ConnectionSession 必须重新校验 token。
- 请求按 RFC 8785/JCS 规范化 `version + type + payload` 后计算 SHA-256；同键同 hash 只重放唯一 terminal，同键不同 hash 返回 `REQUEST_ID_CONFLICT`。
- 畸形信封不会覆盖已存在的逻辑 terminal；JCS 数值域异常被安全终结，consumer 不崩溃。
- 所有消息（包括 terminal replay/conflict）共享 ConnectionSession 限流窗口；首次可关联超限请求返回唯一 `RATE_LIMITED` terminal，随后以 `1008` 关闭。
- terminal map 有界；客户端 capability 原集合由 ConnectionSession 持有。IP、User-Agent 和 capability 只以数量或 HMAC 短摘要进入结构化日志。
- 进程内指标包含在线 ConnectionSession、在线 AuthSession、连接/请求/错误计数和请求延迟；health/observability 只暴露白名单字段。
- H5 建立真实 WebSocket，认证成功只保存安全 AuthSession/GameAccount 摘要；access token、request terminal 和 snapshot 不进入持久客户端存储。
- H5 严格校验版本、完整顶层字段、终结/事件类型、`request_type`、错误结构和冻结错误码；未知服务端错误码收敛为 `INVALID_SERVER_ENVELOPE`。
- `client/src/protocol/generated.ts` 是 `protocol.json` 与 `protocol-errors.json` 的手工 typed projection，由双向契约测试防止漂移。
- `session.ping` 是冻结协议的纯连接级诊断请求；AuthSession 撤销不改变其请求语义，但撤销收敛仍会关闭已绑定连接。它属于 ConnectionSession 能力，不算 #19/#20 scope creep。

关键实现位置：

```text
src/new_mud/apps/identity/consumers.py
src/new_mud/apps/identity/connection_sessions.py
src/new_mud/apps/identity/game_session_metrics.py
src/new_mud/apps/identity/services.py
src/new_mud/apps/identity/tokens.py
src/new_mud/observability.py
src/new_mud/settings/base.py
client/src/protocol/game-connection.ts
client/src/protocol/generated.ts
client/src/stores/connection.ts
tests/test_game_websocket.py
tests/test_postgres_game_websocket_contract.py
client/tests/game-connection.test.ts
client/tests/protocol-catalog.test.ts
```

### 2.3 #18 最终复审

固定审查起点：

```text
97d3eba0fabfc96959e0e19bc51fef0d4ed631b0
```

只基于本地仓库的最终双轴结论：

- Spec：`0 findings`。
- Standards：`0 hard / 5 judgement`。

五个非阻塞 judgement：

1. `consumers.py` 同时承担生命周期、限流、日志/指标、协议、幂等和认证，存在 Divergent Change。
2. 多处重复展开相同 metrics 字段，并与 `observability.py` 白名单同步，存在 Data Clumps/Shotgun Surgery。
3. H5 的本地错误和 connection store 仍有部分裸 `string`，没有全部收敛到 `ProtocolErrorCode`。
4. WebSocket/Python 和 H5 测试 setup 有重复。
5. `generated.ts` 是手工合同投影；双向测试能发现漂移，但没有消除双处维护。

这些不是 #19 的前置 blocker。若 #19 触及相同 seam，优先深化而不是新建平行抽象。

## 3. 已通过的最终证据

`59e41a0` 提交后的最终串行验证：

```text
PostgreSQL 全量 pytest: 348 passed, 1 skipped
```

唯一跳过项是必须显式设置 `RUN_SMTP_TESTS=1` 的开发 SMTP smoke；默认自动测试不得连接公网。

其他证据：

```text
WebSocket + observability 目标集: 32 passed
H5 Vitest: 28 passed
mypy: 89 source files passed
Ruff check/format: passed（仅 #18 Python 文件）
Vue/TypeScript typecheck: passed
H5 build: passed
git diff --check: passed
Playwright desktop-chromium（Edge channel）: 1 passed (7.3s)
```

真实浏览器用例覆盖注册、登录、`/ws/v1/game`、认证状态、refresh 后重连与 logout。最后一次显式 E2E 报告目录：

```text
artifacts/reports/issue18-final-e2e-b04e4deb68fd
```

E2E 使用的两个随机 PostgreSQL 数据库已经删除；8000/5173 没有残留 listener。`new_mud_e2e_clean` 是此前已存在的数据库，不属于本轮临时资源，不要顺手删除。

### 3.1 Windows 本地验证陷阱

- PostgreSQL/pytest 必须串行。两个 pytest 进程会争用默认测试库，造成与代码无关的失败。
- 沙箱不能访问默认的 `C:\Users\023\AppData\Local\Temp\pytest-of-023`。全量测试必须把 `--basetemp` 指到仓库内新的、尚不存在的目录：

```powershell
$env:RUN_POSTGRES_TESTS = '1'
.venv\Scripts\pytest.exe -q --basetemp artifacts\reports\pytest-temp-<unique-name>
```

- 一次未指定 `--basetemp` 的全量结果是 `330 passed / 1 skipped / 18 tmp_path PermissionError`；这 18 项全部是外部临时目录权限错误。改用仓库内 basetemp 后同一代码为 `348 passed / 1 skipped`。
- 全仓 Ruff format 会检查受保护的 #19/#20 migration。除非 #19 已正式接手该文件，否则只格式化本票明确拥有的文件。
- Playwright 在 Windows 上可能通过后卡在托管 server teardown。可靠路径是创建随机隔离数据库，使用隐藏的显式 backend/frontend 进程与 `PLAYWRIGHT_EXTERNAL_SERVERS=1`，记录 PID，测试后按 PID 停止并删除随机数据库；清理前后检查 8000/5173 listener。

## 4. 下一入口：Issue #19

### 4.1 目标与范围

下一 frontier 是 #19：`presence.enter` 与最小完整 snapshot。Character Slice 2 的顺序是：

```text
#17 Character 创建（完成）
  -> #18 ConnectionSession/session.authenticate（完成）
  -> #19 presence.enter + 最小 snapshot（下一入口）
  -> #20 session.resume + presence.recover
  -> Slice 3 presence.takeover
```

#19 的目标：已认证 ConnectionSession 为当前 GameAccount 拥有的 Character 建立运行时 Presence 和持久 PresenceSnapshot，从 E0 active content batch 解析 exact 起始 Room revision，并在成功 terminal 中返回原子、自洽的 `scene / character / combat / actions` snapshot；H5 只有在完整 snapshot 屏障通过后才能替换权威 stores。

#19 不应提前实现：

- `session.resume`、`presence.recover`（#20）。
- 跨 AuthSession `presence.takeover`（Slice 3）。
- 账号关闭/重开/永久退休、联系方式换绑、SMS、MFA、PublicV1Gate、容量/soak。
- 把普通 `presence.enter` 自动升级为 takeover。

### 4.2 接手已有 WIP

工作树里的两个文件是 #19/#20 方向的未完成草稿，不是已验证合同，也没有进入 #18 提交：

```text
src/new_mud/apps/characters/models.py
src/new_mud/apps/characters/migrations/0005_presencesnapshot_resumeticketcredential_and_more.py
```

草稿已有：

- `PresenceSnapshot`，包含 active/grace/taken_over/closed 状态、Presence generation、AuthSession/GameAccount/Character、checkpoint/grace 字段及 active/grace partial unique constraints。
- `ResumeTicketCredential`，包含单活 ticket、generation、hash/key id、used/revoked/expired 状态及 expiry/version constraints。

接手时先写测试和设计判断，再修改草稿。已知必须解决的中风险问题：`ResumeTicketCredential` 重复保存了可以从 `snapshot` 得到的 `auth_session / game_account / character / generation`，但当前没有跨行一致性约束。必须明确选择并验证一种方案：

1. 从 snapshot 派生并删除重复身份字段；或
2. 保留字段并用数据库约束/trigger 保证不可漂移。

不能只靠应用层保存顺序维持一致性。未作出该决定前，不要把 migration `0005` 当作最终 schema。

### 4.3 #19 必须继续满足的冻结不变量

- ConnectionSession、AuthSession、Presence、PresenceSnapshot 是不同概念；用 `CONTEXT.md` 词汇，不用 socket user/persisted Presence 等替代说法。
- Presence 是运行时控制上下文；PostgreSQL 的 PresenceSnapshot 是恢复租约/检查点，不是世界实体或实时 Presence。
- 每个 GameAccount、AuthSession、Character 跨 active/grace 租约各自最多一个；并发 enter 只能有一个赢家。
- `presence.enter` 只能控制当前 GameAccount 通过 CharacterOwnership 拥有的 Character。
- 起始 Room 从 exact active content revision 解析，不能按裸 key 或“最新 revision”重解释。
- 建立 Presence 的路径先准备 inert `pending_enter`；数据库提交前不能接受命令、订阅/broadcast、注册调度或产生外部副作用。
- 连接绑定型 terminal 只有 runtime 激活完成后才能成功；准备、提交、激活、finalization 任一失败都不能留下可重放的虚假成功或占用泄漏。
- `resume_ticket` 是单次使用秘密：只向客户端返回明文，数据库只存不可逆 hash；不进入日志、审计、trace、异常、terminal JSON 或客户端持久存储。
- 成功结果至少包含 `delivery.status=bound`、`resume_required=false`、Presence id、新 ticket，以及完整 `scene / character / combat / actions` snapshot。
- 认证后请求以 `(auth_session_id, request_id)` 持久幂等；#18 的连接本地 terminal map 不能替代 #19 所需的 `RequestTerminalRecord` 和领域写入原子性。
- 同一角色已有 active/grace 租约时普通 enter 返回 `CHARACTER_OCCUPIED`，不泄露其他账号/连接详情，也不隐式接管。

## 5. #19 启动步骤与完成标准

1. 执行第 1 节的 Git/WIP 审计，确认 #18 已在本地和远端，两个 WIP 哈希符合预期。完成标准：只剩明确归属 #19/#20 的工作树变化。
2. 完整阅读下列权威来源，不读取 #18 评论作为事实。完成标准：把 #19 每条验收映射到本地合同的具体章节和测试 seam。
3. 读取 issue tracker 的 #19 **正文、state、blocker、assignee** 以确认实时排程；评论只能作为待核实线索，冻结合同和本地代码优先。若 PATH 没有 `gh`，使用 `artifacts\reports\gh-cli\expanded\bin\gh.exe`。
4. 使用 TDD 从公共 seam 逐条推进：PostgreSQL 真库并发/约束、ASGI WebSocket terminal/激活/故障注入、H5 snapshot 原子替换与真实浏览器。完成标准：每个行为先有可失败的测试，再有最小实现。
5. 修复后使用 `code-review` 做 Standards + Spec 双轴复审；固定点使用 #19 开始前的提交，不把 #20/takeover 混入 #19。完成标准：无 hard finding，所有 judgement 有明确处置或记录。
6. 只暂存 #19 文件；提交前再次列出 staged paths 和两个 WIP/后续 WIP 哈希。完成标准：没有把未归属本票的用户修改带入提交。

权威阅读清单：

```text
AGENTS.md
docs/agents/issue-tracker.md
docs/agents/domain.md
CONTEXT.md
docs/19_documentation_governance.md
docs/adr/0008-access-tokens-require-active-auth-session.md
docs/new_engine/02_ARCHITECTURE.md
docs/new_engine/11_PROTOCOL_CATALOG.md
docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md
docs/new_engine/15_FRONTEND_H5_CONTRACT.md
docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md
docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md
plans/m0-e1-tracer-bullets.md
```

如果任务涉及本地 Ubuntu Server VM 的 provision/deploy/validate/rebuild/rollback，先完整阅读 `plans/ubuntu-server-vm-deployment.md`；只有项目所有者必须亲自执行的步骤才读取 `plans/ubuntu-server-vm-owner-guide.md`。

## 6. 状态名称不要混用

| 对象 | 当前值 | 含义 |
| --- | --- | --- |
| 产品里程碑 M0 | `complete` | 产品结果完成；不是 `verified` |
| `MILESTONE-001` | `verified` | M0 有验证证据；不是 `complete` |
| `ENGINE-001` / E0 | `verified` | Engine Stage E0 已实现并验证 |
| `AUTH-001`、`AUTH-002` | `verified` | Issue #9 的历史注册/会话证据继续成立 |
| `AUTH-004` | `retired` | RecoveryCode + PresenceRecovery 的旧复合 ID 已拆分，不复用 |
| `IDENTITY-001` | `verified` | 每实例 User 永久映射一个 GameAccount |
| `AUTH-005` | `verified` | Auth Baseline Amendment 已完整交付 |
| `AUTH-003` | `specified` | #17/#18 有贡献，但 Presence enter/租约/takeover 证据未齐 |
| `AUTH-006` | `specified` | PresenceRecovery 属于 #20，takeover 仍独立 |
| `CHARACTER-001` | `implemented` | Character 创建已实现；发布级证据未齐，不提升为 verified |
| Character Slice 2 / M1 | 未完成 | 等待 #19/#20 及共同 E2E |
| `CLIENT-001`、`NFR-001`、`NFR-002` | `blocked` | 完整浏览器、容量/soak、恢复证据未齐 |
| `RELEASE-001` / PublicV1Gate | `blocked` | 不具备公开接纳真实玩家的发布证据 |

追踪状态只使用 `specified / implemented / verified / blocked / retired`；产品里程碑只使用 `not_started / in_progress / blocked / complete`。

## 7. 文档债务与权威来源

`plans/m0-e1-tracer-bullets.md` 和 `docs/new_engine/18_IMPLEMENTATION_STATUS.md` 在本快照前仍把 #18 写成下一 frontier、把 ConnectionSession 验收项留作未完成。这是尚未同步的文档债务，不表示 #18 代码缺失；后续更新时必须引用本文件第 2–3 节的本地提交和验证证据，不能引用 #18 评论。

| 问题 | 权威来源 |
| --- | --- |
| 产品范围、里程碑 | `requirements_v6.md` |
| 领域名称 | `CONTEXT.md` |
| 文档权威顺序 | `docs/19_documentation_governance.md` |
| 长期认证决定 | `docs/adr/0005`–`0008` |
| WebSocket 信封、目录、幂等、terminal | `docs/new_engine/11_PROTOCOL_CATALOG.md` |
| ConnectionSession/AuthSession/Presence/恢复状态机 | `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md` |
| H5 权威 store、秘密与重连 | `docs/new_engine/15_FRONTEND_H5_CONTRACT.md` |
| PostgreSQL/并发/故障/可观测性/E2E | `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` |
| 需求成熟度 | `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` |
| 实施顺序 | `docs/new_engine/10_ROADMAP.md`、`plans/m0-e1-tracer-bullets.md` |
| #18 完成事实 | Git `ea05528`、`eb6ce21`、`59e41a0` 与本文件 |
| 下一实现入口 | Issue #19 正文 + 上述冻结合同 |

## 8. 安全边界

- access/refresh/resume ticket、邮箱授权码、PostgreSQL 凭据和密钥不得进入 Git、Issue、命令输出、日志、fixture 或合同制品。
- refresh token 只由受保护 Cookie 进入 REST refresh/logout；不进入 WebSocket payload、Authorization header 或客户端持久存储。
- 保留来源不明的已有修改；暂存前使用显式路径和 `git diff --cached --name-status` 审计。
- `evennia-main/` 与 XKX100 来源目录只作参考输入，不修改。
- PostgreSQL 测试严格串行；全量必须使用仓库内唯一 `--basetemp`。
- 结构检查、目标测试、SMTP smoke 或单视口 E2E 都不能单独提升 PublicV1Gate。
