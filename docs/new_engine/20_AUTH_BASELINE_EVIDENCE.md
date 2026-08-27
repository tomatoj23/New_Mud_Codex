# 20 认证基线分层证据

> 状态：Issue #16 的现行关闭证据，执行日期为 2026-08-27。本文只记录 `AUTH-005` 的验收结果，不创造认证语义，也不构成 Public V1 发布批准。
>
> 审查固定点：`1e6e930ebab86e724a0a79dbe3ce93875d76adbe`（Issue #15 最终提交）。Issue #16 的交付提交由关闭评论和本文件所在提交共同定位；本轮未 push。

## 1. 结论与范围

| 记录 | 状态 | 结论 |
| --- | --- | --- |
| `AUTH-005` | `verified` | Issues #11–#16 已完成权威同步、持久投递基础、已验证邮箱注册、邮箱密码重置、即时认证撤销、安全通知、RecoveryCode 不可逆退役、受控切换和分层验收 |
| Engine Stage E1 / Auth Baseline Amendment | `completed` | 后续实现可读取现行认证权威；Character Slice 2 成为下一 frontier，但尚未认领或实现 |
| `CLIENT-001`、`NFR-001`、`NFR-002` | `blocked` | 完整浏览器矩阵、容量/soak 和发布级五范围恢复证据仍缺失 |
| `RELEASE-001` / `PublicV1Gate` | `blocked` | 正式邮件运营、公开试运行、ReleaseManifest 和其他发布证据尚未完成 |

本票只新增可重复的证据入口、CI 迁移往返、显式 opt-in SMTP smoke、Windows Playwright 外部服务编排开关、合同校验和状态文档；没有新增认证业务能力。Issue #9 / E1 Slice 1 的历史没有改写，也没有新增 Character、CharacterOwnership、ConnectionSession、Presence、PresenceSnapshot、PresenceRecovery、takeover、SMS、联系方式换绑或账号重开能力。

## 2. 执行环境

| 项目 | 值 |
| --- | --- |
| 日期 / 时区 | 2026-08-27 / Asia/Shanghai |
| 操作系统 | Windows 10 `10.0.19045` |
| Python | CPython `3.14.2`，仓库 `.venv` |
| PostgreSQL | `18.4` |
| Node / npm | Node `v24.13.0`；npm `11.6.2` |
| H5 浏览器 | Microsoft Edge，通过 `PLAYWRIGHT_CHANNEL=msedge` |
| 数据库隔离 | pytest 串行临时测试库；迁移与 Playwright 分别使用随机命名的独立临时数据库，并在结束后删除 |

## 3. PostgreSQL、认证与故障矩阵

所有 PostgreSQL 测试串行执行。最终全量命令把 `TEMP`、`TMP` 和 pytest `--basetemp` 指向 Git 忽略的 `artifacts/reports/`，以避开受限 Windows 用户临时目录；默认 `RUN_SMTP_TESTS=0`：

```powershell
$env:RUN_POSTGRES_TESTS = "1"
$env:RUN_SMTP_TESTS = "0"
$env:TEMP = (Resolve-Path "artifacts/reports/issue16-temp")
$env:TMP = $env:TEMP
.venv\Scripts\python.exe -m pytest -q --basetemp=artifacts/reports/pytest-temp-final
```

| 层 | 结果 | 覆盖 |
| --- | --- | --- |
| PostgreSQL 串行全量 | 285 passed、1 skipped、2 warnings | 注册、重置、即时撤销、challenge/outbox、限流、worker claim、并发、故障回滚、terminal 擦除及全部既有回归；skip 仅为未显式启用的 SMTP smoke |
| 认证 REST | 67 passed | 非枚举 request、最终注册、普通登录、refresh/logout、reset、旧 recover/rotate 410、旧 access/refresh 即时失效 |
| 投递与运行态 | 100 passed | 双 worker heartbeat、共享 provider circuit/probe、keyring、limiter、worker/provider 故障、单消息与全局 SMTP 失败分类、普通登录可用 |
| 生产 health | 20 passed | 生产 test bypass 拒绝、静态 cutover、live worker 与 circuit fail-closed |
| PostgreSQL identity / migrations | 29 passed | 唯一性、并发、触发器、不变量、不可逆 0009 与可逆 0010 边界 |
| 文档合同 | 5 passed、2 warnings | 认证权威、状态和本证据入口 |

首次全量在系统 `%TEMP%` 下得到 267 passed、17 errors；17 项全部是 pytest 创建 `C:\Users\023\AppData\Local\Temp\pytest-of-023` 时的 `PermissionError`，不是断言或产品代码失败。切换到仓库内 Git 忽略的临时目录后通过，因此前一次只作为环境诊断，不计验收结果。

## 4. 迁移与回滚边界

漂移命令：

```powershell
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --skip-checks
```

结果为 `No changes detected`。在随机命名的独立空数据库中执行以下序列并恢复到最新叶节点：

```text
migrate identity 0009
migrate identity 0010
migrate identity 0009
migrate identity 0010
migrate
```

结果为 `ISOLATED_MIGRATION_ROUNDTRIP=PASS`，临时数据库已删除。`0010_authentication_baseline_runtime_state` 的结构按 forward/backward/forward 往返；`0009_retire_recovery_codes` 的 active RecoveryCode 撤销有意不可逆，只通过 PostgreSQL 迁移测试证明回退不会复活秘密。CI 的 identity 往返也已从旧 `0002` 更新到 `0009 -> 0010 -> 0009 -> 0010`，没有把不可逆撤销伪装为结构可逆。

一次直接对 `new_mud_test` 的尝试因 pytest 已删除该临时测试数据库而在连接阶段失败，没有执行迁移或修改数据；正式证据只采用随后创建、验证并删除的独立数据库。

## 5. Python、合同与依赖

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\ruff.exe check scripts src tests` | passed |
| `.venv\Scripts\ruff.exe format --check scripts src tests` | 94 files already formatted |
| `.venv\Scripts\mypy.exe src scripts tests` | Success；94 source files |
| `.venv\Scripts\python.exe manage.py check` | 0 issues |
| `.venv\Scripts\python.exe -m pip check` | passed |
| `.venv\Scripts\python.exe scripts/verify_m0.py` | 57,180 checks、READY |
| `git diff --check` | passed |

pytest 的 2 条 warning 都来自 Daphne 使用将在 Python 3.16 移除的 asyncio policy API；当前 CPython 3.14.2 下不影响测试结论，且执行日没有可用的 Daphne 修复版本。

`npm audit --audit-level=critical` 退出 0：0 critical，仍有既存 9 low、9 moderate、1 high。自动全修要求跨越当前 uni-app 合同升级到 Vite 8，超出 #16 的证据收口范围，因此没有进行破坏性依赖升级；该风险不被写成“无漏洞”。

## 6. H5 与浏览器端到端

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build:h5
$env:PLAYWRIGHT_CHANNEL = "msedge"
$env:PLAYWRIGHT_EXTERNAL_SERVERS = "1"
npm.cmd run test:e2e -- --reporter=line
```

Vue typecheck、Vitest 12 passed、H5 build 均通过。Playwright 使用全新随机临时 PostgreSQL 数据库，并由外部明确管理 backend/frontend PID；最终为 13 passed、8 skipped。覆盖三主视口 1280×720、412×915 CSS/DPR3、915×412 CSS/DPR3，以及 360×640 无横向溢出守卫；流程包括邮箱发码、手动重发、零隐式登录注册、普通“登录”措辞、密码重置、稳定错误和恢复秘密泄漏扫描。服务进程与临时数据库均已停止并删除。

`PLAYWRIGHT_EXTERNAL_SERVERS=1` 只允许测试编排器禁用 Playwright 内建 `webServer`；默认本地与 CI 行为不变。增加该开关是因为 Windows 上内建 `webServer` 两次在全部项目执行后卡于子进程树清理，需 Ctrl+C 才能退出，不能计为正式通过。第一次外部编排误用了开发库，其中持久 24 小时限流桶使 9 项返回 `VERIFICATION_RATE_LIMITED`；没有清空或修改开发限流数据，随后改用全新隔离数据库取得正式结果。

## 7. 秘密与公网边界

自动测试覆盖后端 audit、terminal record、结构化日志、provider 异常与 terminal outbox，以及浏览器 localStorage、sessionStorage、IndexedDB、Cache Storage、Cookie、console 和网络响应；没有发现密码、验证码、完整联系方式、access/refresh 凭据或 RecoveryCode 泄漏。对 `git ls-files` 的高风险 token 形态和硬编码 secret assignment 扫描均为 `none`。CI 继续使用官方 `gitleaks/gitleaks-action@v2`。

本机尝试获取 gitleaks `v8.30.1`，但 `curl`、GitHub release download 与 API asset 下载均在受限网络中途停止或超时；官方 Windows x64 zip 期望 SHA-256 为 `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`，未完成的忽略目录下载从未执行。因此本文件不声称“本机 gitleaks passed”；CI gitleaks 仍是提交进入远端后的独立必经门禁。

`tests/test_smtp_smoke.py` 是显式 opt-in 的开发入口，默认结果为 `1 skipped`：本轮没有 `RUN_SMTP_TESTS=1`、显式收件人和本地 SMTP 秘密授权，所以没有向公网或 163 SMTP 发送邮件。该 smoke 还会强制 Django SMTP backend、`smtp.163.com`、发件账号、密码和 `DEFAULT_FROM_EMAIL`，并抑制收件人与 provider 异常细节。跳过不写成通过，163 也不构成 Public V1 provider 证据。

## 8. 双轴审查

正式 Standards 与 Spec 复审以本文件顶部固定点为基准并覆盖完整 Issue #16 diff。结果在提交前回填；只有两轴均无未解决 hard finding 才允许关闭 #16。

## 9. 仍然缺失的发布证据

以下项目没有因 `AUTH-005=verified` 而完成：

- 正式邮件 provider、受控域名、SPF、DKIM、DMARC、退信处理、配额、告警和基本送达证据。
- 完整发布浏览器/输入/无障碍矩阵与实际 `tested_versions`。
- capacity profile 的容量报告、两小时 soak，以及五个业务范围的发布级恢复演练。
- 7 天、5 名非管理员、20 次核心循环的封闭试运行、ReleaseManifest、公开状态/恢复/举报/客服资料。
- Public V1 前删除两个 RecoveryCode 410 兼容路由。

因此产品 M0 继续是 `complete`，`MILESTONE-001` 与 `ENGINE-001` 继续是 `verified`，M1 / `MILESTONE-002` 仍未完成，`CLIENT-001`、`NFR-001`、`NFR-002` 和 `RELEASE-001 / PublicV1Gate` 继续 `blocked`。

## 10. 最终复验

| 门禁 | 最终结果 |
| --- | --- |
| PostgreSQL 串行全量 | 285 passed、1 skipped、2 warnings；唯一 skip 为未显式 opt-in 的开发 SMTP smoke |
| 迁移 | drift none；隔离数据库 `0009 -> 0010 -> 0009 -> 0010 -> latest` 通过；临时数据库已删除 |
| Python / Django / 合同 | Ruff passed；94 files formatted；mypy 94 source files；Django 0 issues；pip check passed；5 个文档合同 passed；57,180 项 M0 checks READY |
| 前端 | Vue typecheck passed；Vitest 12 passed；H5 build passed；隔离数据库 Playwright 13 passed / 8 skipped |
| 依赖 | npm critical gate 退出 0；0 critical，保留 9 low / 9 moderate / 1 high，未强制破坏性 Vite 8 升级 |
| 秘密 | 行为与浏览器存储/console/network 扫描通过；tracked 高风险 token 形态与 secret assignment 均为 none；本机 gitleaks 未下载完成，CI 官方 gate 保留 |
| 清理 | 8000/5173 无残留 listener；无 `new_mud_issue16_e2e_*` 临时数据库 |
| 双轴审查 | 待固定点到 Issue #16 提交的正式 Standards / Spec 审查回填；未完成前不关闭 Issue |
