# 18 实施状态与验证记录

> 状态：现行实施证据账本。本文记录代码、环境、验证结果与阻塞项，不创造产品需求或实施语义；发生冲突时，按 `docs/19_documentation_governance.md` 回到对应权威来源处理。

## 1. 目的与边界

本文用于回答三个问题：

- 当前仓库已经实现并验证了什么。
- 哪些结果仍因实现缺口、审批或验收报告而阻塞。
- 某项状态判断可以回查到哪些提交、制品、脚本和测试。

本文不是发布说明，也不把结构检查通过等同于需求里程碑完成。产品结果以冻结的 `requirements_v6.md` 为准（`requirements_v5.md` 仅作历史基线），实施机制仍以 `docs/new_engine/11-16` 为准，需求状态仍以 `17_REQUIREMENTS_TRACEABILITY.md` 为准，实施顺序仍以 `10_ROADMAP.md` 为准。`PublicV1Gate` / `RELEASE-001` 尚未开始执行。

## 2. 当前基线

| 基线 | 身份 | 当前结论 |
| --- | --- | --- |
| V6 前置基线 | Git `d14ce67` | V6 权威、V5 历史边界、CONTEXT/ADR、冻结合同、机器制品与审计记录在同一检查点同步 |
| 现行文档一致性复核 | GitHub Issue #7 检查点（2026-08-26） | 已复核领域词汇、工程索引、V6、ADR、冻结合同、计划与现行项目文档；归档、V5 和上游文档不在修改范围 |
| E0 / Slice 2 验收基线 | GitHub Issue #5 检查点（2026-08-25） | Issues #1–#4 的实现已在 V6 基线上完成真库、服务集成、启动 E2E、全量和静态门禁，`ENGINE-001` 与 `MILESTONE-001` 可验证关闭 |
| E1 / Slice 1 验收基线 | GitHub Issue #9 检查点（2026-08-26） | 注册、独立登录、refresh/logout、RecoveryCode、认证限流、H5 single-flight 与现代移动/桌面自动 E2E 已通过；未实现 Character、Presence、恢复控角或 takeover |
| E1 / Auth Baseline Amendment | GitHub Issues #10–#15（2026-08-27） | VerifiedContactMethod 与 VerificationChallenge 已取代 RecoveryCode 成为现行注册/恢复权威；权威修订、投递基础、已验证邮箱最终注册、邮箱密码重置、即时认证撤销、RecoveryCode 退役与受控切换已交付，分层总证据由 #16 继续交付 |
| M0 工程基线 | Git `7bd76a3` | Django/ASGI 骨架、PostgreSQL 初始迁移、机器合同、来源制品、CI 与自动校验已建立 |
| M0 profile 基线 | Git `97659ce` | browser、capacity、recovery profile 已批准，M0 基础设施恢复报告已绑定 |
| 实施计划基线 | Git `b4798fb` | 已验证环境与 Engine Stage E0/E1 五切片计划已建立；当前计划已改用命名空间化 Slice |
| Python 基线 | CPython `3.14.2` | `.venv` 使用仓库内 `.venv/runtime`，不读取用户级 site-packages |
| PostgreSQL 基线 | PostgreSQL `18.4` | 本机服务、项目角色、项目数据库、迁移往返和数据库合同测试已验证 |
| 依赖基线 | `requirements.lock` | 56 个运行、开发、传递及打包工具依赖精确锁定；在线过时检查为空 |

## 3. 历史基线与后续验证记录

本节保留 2026-07-19 的 M0 历史基线，并在相应表格中追加带日期的后续验证；日期不同的结果不得视为同一次执行。

### 3.1 文档审计与归档

- 两轮全量审查覆盖当时 46 份项目自有 Markdown 文档；这是 2026-07-19 的历史审计快照，不代表当前文档数量。当前审查另行覆盖 V6、CONTEXT、ADR、V6 差异清单和 Engine Stage E0 / Slice 2 工作记录；`evennia-main/` 中的上游源码与上游文档不属于项目文档审核范围。
- 审核覆盖 Markdown 结构、本地引用、术语、需求、协议、状态机、Blueprint、来源制品、测试、运维语义和跨文档冲突；最终结构、引用与陈旧模式复扫均通过。
- 2026-08-26 再次全量复核 56 份现行项目 Markdown，明确排除 `archive/`、`requirements_v5.md` 与上游文档；单 H1、标题层级和本地链接通过，`CONTEXT.md` 的 50 个领域词项与 `UBIQUITOUS_LANGUAGE.md` 的非定义入口一一对应，无缺项或额外领域定义。
- 同轮语义复核统一 Presence/PresenceSnapshot、Actor/ActorRef、RetiredCharacter、CharacterCreationProfileDefinition、工程名称和三套里程碑状态命名空间，并修正后台审计发起者、SystemNotice 与现行分析层的残留边界；带日期的 E0 工作记录保留历史原文，不作为当前状态来源。
- 将 `archive/requirements/requirements_v1.md` 到 `archive/requirements/requirements_v4.md` 移入归档，并保留归档入口与历史审计记录。
- 确立按关注点划分的文档权威：V6 管产品结果，V5 保留历史，11-16 管冻结实施机制，17 管需求追踪，00-10 管概念设计与路线，00-18 与 20 管 Evennia 来源分析和适配性评估。
- 明确 `evennia-main/` 仅为 Evennia 6.0.0 本地参考快照，不是运行时依赖；本轮未修改该目录。
- 审核范围、修复分类、二轮验证和剩余风险的快照记录见 `archive/audits/2026-07-19-requirements-v5/requirements_v5_doc_audit_summary.md`。

### 3.2 Git 基线

- 以 `e7a3717` 建立审计后的正式文档基线。
- 以 `7bd76a3` 建立 M0 可执行合同与工程骨架基线。
- 以 `97659ce` 建立 M0 非功能 profile 基线，以 `b4798fb` 建立已验证环境与五切片实施计划基线。
- 上述四个历史提交保留需求、合同、实现与验收证据之间的追溯关系；`d14ce67` 同步当前 V6 权威、合同、制品和审计记录，E0 / Slice 2 实现由 Issues #1–#4 的提交固定，Issue #5 在其上建立最终验收检查点。

### 3.3 M0 工程骨架与合同制品

- 建立 Django、DRF、Channels、Daphne、ASGI 与 PostgreSQL 工程骨架。
- 建立开发、测试、生产 settings，REST/WebSocket 健康检查和 JSON 日志格式。
- 建立内容发布最小持久模型及 `content.0001_initial` 迁移，覆盖 immutable revision、两类 exact dependency、release head/batch/item 与数据库约束。
- 建立协议、错误码、状态、Registry 和 profile 的机器可读 catalog/schema，以及生成后的 Python 合同常量。
- 建立 `source_snapshot.json`、独立世界/武学 manifest 和复合验收 bundle；来源快照冻结 14,018 个文件，世界 manifest 固定 5 个 roots 与 44 个 dependencies，武学 manifest 固定 14 个 roots 与 11 个 dependencies。
- 建立 `generate_source_contracts.py` 与 `verify_m0.py`，校验 schema、哈希、依赖闭包、需求 ID、生成代码和环境依赖。
- 建立 GitHub Actions M0 工作流和 PostgreSQL 18.4 CI 服务。

### 3.4 Python 与依赖环境

- 将项目虚拟环境重建为自包含结构，`sys.base_prefix` 指向 `.venv/runtime`，`include-system-site-packages=false`。
- 将项目运行、开发、类型检查、测试及打包工具依赖升级并锁定到检查当日可用最新版；完整版本以 `requirements.lock` 为准。
- 当前关键版本包括 Django 6.0.7、Channels 4.3.2、Daphne 4.2.2、DRF 3.17.1、psycopg 3.3.4、mypy 2.3.0、pytest 9.1.1 和 Ruff 0.15.22。
- 在全新临时虚拟环境中仅依据锁文件完成重建，确认 0 个缺失包、0 个锁版本偏差和 0 个依赖冲突；验证后已删除临时环境。
- 本地引导脚本和 CI 的 editable 安装使用 `--no-build-isolation`，直接复用已锁定的 setuptools；CI 缓存键同时覆盖 `pyproject.toml` 与 `requirements.lock`。

### 3.5 PostgreSQL 环境

- 确认 PostgreSQL 18.4 Windows 服务处于自动启动和运行状态，`127.0.0.1:5432` 可用。
- 初始化本地 `new_mud` 开发角色和 `new_mud` 数据库；开发角色具备创建 pytest 临时测试数据库所需的本地权限。
- 完成 Django 全量迁移、`content` 迁移回退到 zero、重新前进到 `0001` 的往返验证。
- 管理员凭据只在初始化进程内临时使用，未写入仓库、环境样例、日志或合同制品。

### 3.6 验证结果

| 检查 | 结果 |
| --- | --- |
| `pip check` | 通过，0 个损坏依赖 |
| 锁文件与当前 `.venv` 对比 | 通过，0 个缺失、0 个版本偏差 |
| PyPI 过时依赖检查 | 通过，结果为空 |
| 空环境锁文件重建 | 通过 |
| Ruff lint / format | 通过，32 个文件格式一致 |
| mypy | 通过，32 个源文件无问题 |
| Django system check | 通过，0 个问题 |
| `makemigrations --check --dry-run` | 通过，无模型漂移 |
| PostgreSQL 迁移往返 | 通过 |
| pytest（2026-07-19 历史基线） | 12 项通过，其中 3 项为 PostgreSQL 合同测试 |
| pytest（2026-08-23 当前工作树） | 16 项通过，3 项 PostgreSQL contract tests 因未设置 `RUN_POSTGRES_TESTS=1` 跳过 |
| M0 合同校验（2026-07-19 历史基线） | 56,883 项通过，profile blocker 为空 |
| M0 合同校验（2026-08-23 当前工作树） | 56,981 项通过，profile blocker 为空；命令为 `.venv\\Scripts\\python.exe scripts/verify_m0.py`（生成代码已先用 `--write-generated` 同步） |
| PostgreSQL 隔离恢复 | 通过；实测 RPO 0.004057 分钟，RTO 0.01816 分钟 |
| pytest（2026-08-25，未启用真库） | 57 passed、16 skipped；跳过项全部显式要求 `RUN_POSTGRES_TESTS=1`，并由下一项覆盖 |
| pytest（2026-08-25，`RUN_POSTGRES_TESTS=1`） | PostgreSQL 合同/启动 E2E 16 passed；内容/seed/startup/runtime/health/真库集合 66 passed；全量 73 passed |
| 静态与 Django（2026-08-25） | Ruff lint 通过；52 files formatted；mypy 52 source files 通过；Django 0 问题；无 migration drift；`pip check` 通过 |
| M0 / Markdown（2026-08-25） | 56,981 项 M0 检查、0 个 profile blocker；76 项 Markdown 检查、0 errors |
| M0 / Markdown（2026-08-26） | 57,055 项 M0 检查、0 个 profile blocker；56 份现行 Markdown 共 135 项单 H1、标题层级和本地链接检查，0 errors |
| 默认全量与合同回归（2026-08-26） | 默认全量 57 passed、16 个 PostgreSQL 项因未设置 `RUN_POSTGRES_TESTS=1` 跳过；`tests/test_contracts.py` 3 passed；仅有已记录的 Daphne / Python 3.16 asyncio policy 弃用警告 |
| E1 / Slice 1 后端（2026-08-26） | `RUN_POSTGRES_TESTS=1` 全量 134 passed；Auth API 与迁移结构 49 passed；身份专项（含 PostgreSQL 合同）61 passed；RecoveryCode 跨实例撤销、登录/账号生命周期并发、refresh terminal 保留和身份字段不可变触发器均由真库覆盖 |
| E1 / Slice 1 前端（2026-08-26） | Vue typecheck 通过；Vitest 11 passed；H5 build 通过；Playwright 10 passed、8 个按项目适用性跳过（含 360×640 最低宽度守卫，以及桌面单次持久 refresh/双标签/泄漏扫描） |
| E1 / Slice 1 静态与迁移（2026-08-26） | Ruff lint 通过、69 files formatted；mypy 69 source files 通过；Django 0 issues；无 migration drift；identity `0003 -> 0002 -> 0003` 往返通过；`pip check` 通过 |
| E1 / Slice 1 安全与合同（2026-08-26） | `verify_m0.py` 57,053 checks、READY；npm critical audit 通过（0 critical），仍有上游 uni-app/Vite 兼容链的 19 项非 critical 风险：9 low、9 moderate、1 high |
| E1 / Auth Baseline Amendment 权威（2026-08-26，Issue #11） | 认证权威合同测试 1 passed；`tests/test_contracts.py` 4 passed；默认全量使用仓库内 `--basetemp` 后 107 passed、28 个 PostgreSQL 条件项跳过；Ruff、70 files format、mypy 69 source files、diff check 通过；`verify_m0.py` 57,152 checks、READY |
| E1 / Auth Baseline Amendment 投递基础（2026-08-26，Issue #12） | `RUN_POSTGRES_TESTS=1` 全量 187 passed；registration-verification REST、PostgreSQL 并发/迁移、worker/fake provider、密钥轮换和 fail-closed 专项通过；Ruff、84 files format、mypy 84 source files、Django 0 issues、无 migration drift、`pip check` 通过；`verify_m0.py` 57,156 checks、READY |
| E1 / Auth Baseline Amendment 最终注册（2026-08-26，Issue #13） | `RUN_POSTGRES_TESTS=1` 全量 200 passed，认证 API、投递与 PostgreSQL 身份专项 122 passed；覆盖最终注册原子消费、并发/回滚、旧读新写密钥轮换及已替代旧码不可复活。Vue typecheck、Vitest 11 passed、H5 build 与 Playwright 10 passed/8 skipped 通过；Ruff、86 files format、mypy 65 source files、Django 0 issues、无 migration drift、`pip check` 通过；`verify_m0.py` 57,156 checks、READY |
| E1 / Auth Baseline Amendment 密码重置（2026-08-27，Issue #14） | `RUN_POSTGRES_TESTS=1` 全量 231 passed；认证 API/投递专项 128 passed，PostgreSQL 身份合同/迁移专项 26 passed；覆盖非枚举 request、purpose 隔离 challenge、原子 confirm、跨实例即时认证撤销、并发/回滚、GameAccount lifecycle 不变和安全通知失败隔离。Vue typecheck、Vitest 12 passed、H5 build 与 Playwright 13 passed/8 skipped 通过；Ruff lint、90 files format、mypy 69 source files、Django 0 issues、无 migration drift、`pip check` 通过；Standards 复审无硬性违规，Spec 复审逐项核对 Issue #14 验收边界 |
| E1 / Auth Baseline Amendment RecoveryCode 退役（2026-08-27，Issue #15） | `RUN_POSTGRES_TESTS=1` 串行全量 239 passed；认证专项 67 passed，生产启动/配置专项 9 passed；覆盖两个旧端点统一 410 且绕过 Basic/Session 凭据解析、旧 code 不可消费、迁移撤销 active code、数据库拒绝新增 active、回滚不复活秘密，以及 cutover/keyring/worker/provider/生产 test-bypass 故障统一 fail closed 且普通登录可用。Vue typecheck、Vitest 12 passed、H5 build 与 Playwright 13 passed/8 skipped 通过；Ruff lint、90 files format、mypy 90 source files、Django 0 issues、无 migration drift、`pip check` 与 npm critical audit 通过；`verify_m0.py` 57,156 checks、READY |

pytest 仍报告 Daphne 对 Python 3.16 将移除的 asyncio policy API 的两条弃用警告。当前运行时为 Python 3.14.2，且检查当日没有可升级的 Daphne 版本，因此该警告记录为上游兼容性观察项，不构成当前失败。

### 3.7 非功能 M0 基线收口

- browser matrix 已由 `project-owner` 批准，基于 Apple、Google、Microsoft 与 Mozilla 官方版本源冻结桌面和移动精确目标组合；iOS Safari 保留在首发目标中。所有 `tested_versions` 仍为空，等待真实 H5 浏览器 E2E 填写。
- capacity profile 已批准首发环境、数据量、负载、采样窗口和阈值；本次没有生成容量或两小时 soak 报告。
- 新增 `recovery-report.schema.json` 与 `run_recovery_drill.py`。最终演练使用 PostgreSQL/pg_dump/pg_restore 18.4，在同一导出快照上生成临时 custom dump，恢复到随机隔离数据库，并验证 schema 哈希、16 张表逐表行数、16 条 Django 迁移历史及工具主版本一致。
- 恢复报告 `m0-recovery-20260719-145739z` 的文件 SHA-256 为 `50335d0cc36d507bcbc5a674f8a0ed6d5b1360dc5d1a4fc2a6a43c5899a3aac9`。临时 dump 与隔离数据库均已删除，报告不含数据库凭据；该值与 `contracts/v1/profiles/recovery-budget.json` 及报告文件一致。
- 账号、角色、世界拓扑、非空内容批次和审计链尚未形成发布样本，因此报告固定为 `release_gate_eligible=false`；它只证明 M0 恢复工具链，不把 `NFR-002` 提前标记为通过。
- CI 已从仅结构检查切换到完整 M0 合同门禁，报告路径、报告 ID、文件哈希、指标、范围集合和内部通过条件均自动复核。

### 3.8 Engine Stage E1 / Slice 1 注册与独立登录

- Issue #9 已实现 `POST /api/v1/auth/register`、`login`、`refresh`、`logout`、`recover` 与 `recovery-code/rotate`。注册原子创建 User、当前实例 GameAccount 与一次性可见 RecoveryCode 哈希，不创建 AuthSession、Character、PresenceSnapshot 或隐式登录状态。
- login 在 GameAccount 行锁后重读密码与账号状态，创建 lifetime 唯一 AuthSession/RefreshTokenFamily；refresh 使用持久 terminal 区分同 key 重试、冲突、superseded 与攻击 replay，并用 PostgreSQL 触发器保护 family/credential 身份不可变和 terminal 保留下限。
- RecoveryCode 恢复和轮换按 GameAccount、code、AuthSession、family/credential 固定锁序处理，撤销该 User 跨实例的全部旧认证状态；账号/IP/服务端 opaque 设备 Cookie 合并限流不影响正常密码登录。未来 Presence/ticket 撤销只保留统一收敛缝，本切片没有创建对应模型。
- H5 access token 只存 Pinia 内存；refresh Cookie 为 Secure、HttpOnly、SameSite=Strict、host-only。IndexedDB 只保存 pending refresh 控制记录，写事务完成后才发送请求；成功时先接受 access token，再清 pending 并用 BroadcastChannel 通知其他标签页。
- 自动浏览器验收以 1280×720 桌面、412×915 CSS / DPR 3 现代移动竖屏、915×412 CSS / DPR 3 超长比例横屏为主；三个主视口均通过注册、独立登录、refresh、logout 和机器错误显示。桌面额外通过提交后响应丢失重载复用 key、双标签 single-flight 与持久存储泄漏扫描。360×640 仅保留无横向溢出最低守卫，不作为主流程设计目标。
- 当前环境没有可供 in-app Browser 使用的浏览器，因此未完成额外人工可见检查；该限制不改写已通过的 Playwright 自动证据，也不填充发布级 `tested_versions`。
- npm audit 的 critical 门禁通过。剩余唯一 high 来自 uni-app 当前 Vue 3 tag 约束的 Vite 5 工具链；升级到 Vite 8.2.2 会越过上游兼容合同，因此记录风险而不在 Slice 1 强制跨大版本。

### 3.9 Engine Stage E1 / Auth Baseline Amendment

- Issue #10 固定已验证邮箱注册、邮箱密码重置、即时认证撤销、RecoveryCode 退役，以及 SMS/换绑/关闭重开/Character/Presence/takeover 禁区；Issue #11 只发布这项权威修订，不修改数据库、运行配置或业务行为。
- `VerifiedContactMethod`、`VerificationChallenge` 与已退役 RecoveryCode 已进入单一领域词汇；ADR-0005 至 ADR-0008 记录联系方式权威、密文/lookup 分离、持久 outbox 和 Access Token 必须解析 active AuthSession。
- `AUTH-004` 的历史复合语义已退役，Issue #9 的实现证据继续保留；`IDENTITY-001`、`AUTH-005` 与 `AUTH-006` 分别追踪 User/GameAccount 基数、现行联系方式认证修订和未来 PresenceRecovery。
- Issue #12 已实现 registration-verification request、加密 challenge/outbox、持久合并限流和独立 worker 投递 tracer；provider 接受后才激活十分钟 challenge，terminal payload 擦除，key/limiter/worker/provider 故障只关闭验证功能而不关闭普通密码登录。
- Issue #13 已实现最终 register 的 PostgreSQL 原子消费与唯一性重验，创建 User、当前实例 GameAccount 和唯一 verified email，保持零 AuthSession/token/RecoveryCode/Character/Presence；H5 完成邮箱发码、验证码注册、手动重发和成功返回登录入口。跨 lookup key 轮换的新投递会在同一逻辑邮箱锁内替代全部旧 active challenge。
- Issue #14 已实现 password-reset request/confirm、独立限流与幂等命名空间、固定锁序的 PostgreSQL 原子密码更新和跨实例 AuthSession/family/credential 即时撤销；成功不自动登录、不改变 GameAccount lifecycle。安全通知使用独立持久 outbox，失败只进入审计和告警，不回滚密码事务；H5 完成邮箱发码、手动重发、六位验证码、新密码和返回普通登录入口的闭环，且不持久化恢复秘密。
- Issue #15 已通过 identity `0009_retire_recovery_codes` 撤销全部 active RecoveryCode，并以数据库约束禁止新增 active；reverse data migration 不复活秘密。旧 recover/rotate 兼容路由不解析 body、Origin 或凭据，统一返回 `410 RECOVERY_CODE_RETIRED`。注册、重置、验证 worker 和安全通知 worker 共用认证基线切换；生产启动拒绝不完整依赖及测试邮件 bypass，普通账号名/密码登录保持独立可用。
- 路线与 tracer plan 在原 E1 / Slice 1 与 Character Slice 2 之间插入 `Auth Baseline Amendment`。#16 是下一 frontier；#16 完成前不得启动 Character Slice 2。
- 新增认证权威文档合同检查，要求 V6、冻结合同、追踪、状态、差异、计划与交接使用同一现行边界，并拒绝旧 RecoveryCode 注册/恢复承诺重新进入活跃权威。

## 4. 当前状态

| 对象 | 状态 | 依据 |
| --- | --- | --- |
| 文档基线 | `verified` | 2026-08-26 现行 Markdown 已通过 UTF-8、单 H1、标题层级、本地链接和认证权威一致性检查；V5 与归档保持历史来源且未改写 |
| M0 机器合同基线 | `verified` | 2026-08-26 `verify_m0.py` 通过 57,152 项检查，profile blocker 为空；历史执行数只保留在第 3 节的带日期证据账本 |
| `CONTENT-001` | `implemented` | Issues #1–#4 已实现两类 exact dependency、冻结 seed bootstrap、active/pinned resolver、启动/readiness、并发/回滚与失败审计；完整后台发布服务仍待 M1 |
| `WORLD-001` | `specified` | 冻结来源与 seed/startup 验证不等于固定小巷世界物化、移动、战斗和战利品 E2E；这些仍待 M1 |
| `CONVERT-001` | `implemented` | 来源快照、双 manifest、bundle、生成器与篡改检查已存在；M4 黄金差分仍未实现 |
| 非功能 M0 profile 基线 | `verified` | browser、capacity、recovery 三份 profile 已批准，恢复报告路径/ID/哈希与指标已纳入自动校验 |
| 产品里程碑 M0 | `complete` | V6 15.0-15.1 的机器合同、profile 批准与 Issue #5 clean-baseline checklist 已全部满足；对应追踪记录 `MILESTONE-001=verified` |
| `ENGINE-001` / Engine Stage E0 | `verified` | Issues #1–#4 完成实现；Issue #5 在 V6 基线上完成 PostgreSQL、服务集成、启动 E2E、全量和静态验收 |
| `AUTH-001` | `verified` | Issue #9 已完成当时的限流注册、User/GameAccount/RecoveryCode 原子事务、普通登录和 H5 端到端证据；RecoveryCode 只保留历史 provenance |
| `AUTH-002` | `verified` | Issue #9 已完成 AuthSession/family、refresh generation/terminal/replay、幂等 logout 与前端 single-flight 证据 |
| `AUTH-004` | `retired` | 原 RecoveryCode + PresenceRecovery 复合追踪项被有意拆开，ID 不复用；Issue #9 历史证据不删除 |
| `IDENTITY-001` | `verified` | Issue #9 已验证每实例一个 User 永久映射一个 GameAccount 的数据库、迁移与并发边界 |
| `AUTH-005` | `implemented` | Issue #10 已批准、Issue #11 已同步权威，Issues #12–#15 已交付投递基础、最终注册、邮箱密码重置、即时认证撤销、安全通知、RecoveryCode 退役、受控切换与 H5；分层总证据仍待 #16 |
| `AUTH-006` | `specified` | PresenceRecovery 继续属于未来 Character Slice 2，跨 AuthSession takeover 仍为后续独立切片 |
| Engine Stage E1 / Slice 1 | `verified` | 8 项切片验收全部通过；范围止于注册与独立登录，不包含 Character、ConnectionSession、Presence、恢复控角或 takeover |
| `RELEASE-001` / PublicV1Gate | `blocked` | V6 gate 已定义，尚无公开试运行、完整恢复、ReleaseManifest 或公开资料证据；不影响 M1/E0 的内部状态 |

M0 机器合同当前通过且没有 profile blocker；产品里程碑 M0 已 `complete`，其追踪记录 `MILESTONE-001` 与 `ENGINE-001 / Engine Stage E0` 均为 `verified`。Issue #9 固定 E1 / Slice 1 的历史注册与登录证据；M1 与 `MILESTONE-002` 仍未完成，下一实现入口是 Auth Baseline Amendment 的 Issue #16。

浏览器完整矩阵、容量/soak 报告与五个业务恢复范围仍是 `RELEASE-001` 的发布候选证据，因此 `CLIENT-001`、`NFR-001` 和 `NFR-002` 保持 `blocked`，不因 M0 目标获批或 M1 内部抽样而提前转为 `verified`。

经确认的下一步纵向实施计划见 `plans/m0-e1-tracer-bullets.md`。两个 E0 切片与 E1 / Slice 1 已完成并保留为可回查记录；Auth Baseline Amendment 仍须由 #16 完成分层证据后，才从 Character Slice 2 的角色、连接、进入与恢复闭环继续，Slice 3 takeover 仍须独立实施。

## 5. 证据映射

| 需求 ID | 当前证据 |
| --- | --- |
| `MILESTONE-001` | `contracts/v1/`、`scripts/verify_m0.py`、`.github/workflows/m0.yml`、本文件第 3.6 节与 Issue #5 clean-baseline checklist |
| `ENGINE-001` | Issues #1–#4 的提交、V6 基线 `d14ce67`、`archive/handoffs/2026-08-26-e0-closeout/PHASE2_CONTENT_STARTUP_WORKLOG.md` 第 8 节与 Issue #5 分层验收 |
| `CONTENT-001` | `src/new_mud/apps/content/models.py`、`migrations/0001_initial.py`–`0002_contentstartupfailure.py`、seed/registry/startup/resolver 实现与 PostgreSQL 合同测试 |
| `AUTH-001`、`AUTH-002` | Issue #9、`src/new_mud/apps/identity/`、`tests/test_auth_api.py`、`tests/test_postgres_identity_contract.py`、`client/` 与 CI 分层门禁 |
| `AUTH-004` | Issue #9 的 RecoveryCode/合并限流/User 全会话撤销历史证据；ADR-0005 与 Issue #10 记录有意退役，ID 不复用 |
| `IDENTITY-001` | Issue #9 的 User/GameAccount 数据库唯一约束、迁移与并发证据 |
| `AUTH-005` | Issue #10、Issue #11、CONTEXT/ADR-0005 至 0008、V6/08/13/15/16 权威与认证文档合同；Issue #12 的 challenge/crypto/limiter/outbox/worker、Issue #13 的最终注册/H5、Issue #14 的邮箱密码重置/即时认证撤销/安全通知/H5、Issue #15 的 RecoveryCode 退役/受控切换/生产预检/回滚实现及测试；分层总证据仍待 #16 |
| `AUTH-006` | 11/13/15 的 PresenceRecovery 与 takeover 分离合同；Character Slice 2 尚未实现 |
| `CONVERT-001` | `contracts/v1/artifacts/`、`scripts/generate_source_contracts.py`、`tests/test_contracts.py` |
| `CLIENT-001` | `browser-matrix.json` 已批准且冻结目标版本；Issue #9 已有 Slice 1 的桌面/现代移动自动 E2E，但实际 `tested_versions` 与完整发布矩阵尚缺 |
| `NFR-001` | `capacity-profile.json` 已批准；容量报告与两小时 soak 尚缺 |
| `NFR-002` | `recovery-budget.json`、`m0-recovery-latest.json` 与 `run_recovery_drill.py`；发布级五范围恢复证据尚缺 |

## 6. 变更边界

- XKX100 源目录只用于读取和生成哈希制品，本轮未改写源文件。
- `evennia-main/` 只用于架构事实回查，本轮未新增或修改其中的文件。
- `.venv`、PostgreSQL 数据目录和本机服务属于本地开发环境，不进入 Git。
- 临时锁文件重建环境已经清理，不构成新的长期环境依赖。
- 恢复演练的 dump 位于系统临时目录并已删除，随机隔离数据库已删除；仓库只保留不含凭据的 JSON 报告。
- 本文记录的本机通过结果不能替代 CI、浏览器、容量、恢复或发布候选环境的独立证据。

## 7. 更新规则

- 每次需求状态变化、Engine Stage 交付、数据库迁移基线变化或正式门禁执行后更新本文。
- 只记录已经发生且可回查的事实；计划中的工作写入 `plans/` 并回链 `10_ROADMAP.md`，不得在本文伪装为已完成结果。
- 状态变化必须同步 `17_REQUIREMENTS_TRACEABILITY.md`；产品或实施语义变化仍按文档治理流程修改对应权威文件。
