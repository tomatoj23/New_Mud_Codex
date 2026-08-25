# 下一会话交接：E0 已关闭，E1 待独立启动

> 快照日期：2026-08-26。
>
> 本文件是无会话记忆时的现行启动入口，汇总继续工作必需的仓库状态、已完成边界、固定决策、未完成证据和启动顺序。它不创造需求、合同或正式状态；冲突时按 `docs/19_documentation_governance.md` 回到对应权威来源。

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

- 分支是 `main`，工作树为空，`HEAD` 与 `origin/main` 相同，ahead/behind 为 `0 0`。
- 历史包含 `bb6deec`（Issue #7：V6 与现行文档一致性审计）以及 Issue #8 的 E0 交接归档检查点。
- GitHub Issues #1–#8 均已关闭。使用仓库内可用的 `gh` CLI 复核 Issue #8 的关闭评论和对应提交；不要只凭本文缓存的状态开始修改。

若工作树不干净，先辨认并保留已有修改；若 `HEAD` 与 `origin/main` 不一致，先确认差异来源。完成这两个检查以前，不创建 ticket、不改文档、不写代码。

当前已验证的开发环境是 Windows 10 `10.0.19045`、仓库私有 `.venv` 中的 CPython `3.14.2`、PostgreSQL `18.4` 和 `requirements.lock` 的精确依赖。若新会话的 PATH 尚未刷新而找不到全局 `gh`，使用 `artifacts\reports\gh-cli\expanded\bin\gh.exe`；先运行 `auth status`，预期 GitHub.com 账号为 `tomatoj23`。

## 2. 当前结论

### 2.1 已完成并固定

- 产品里程碑 M0 已 `complete`；追踪记录 `MILESTONE-001` 已 `verified`。
- `ENGINE-001 / Engine Stage E0` 已 `verified`，E0 的两个切片均已关闭。
- E0 / Slice 2 已实现并验收：Registry 与 Blueprint 两类 exact dependency、冻结 seed artifact、受审计 bootstrap、active/pinned resolver、服务器启动生命周期、只读 readiness、并发收敛、事务回滚和失败审计。
- 2026-08-26 已完成 V6、领域词汇、工程术语索引、冻结合同、计划和全部非历史项目文档的一致性审计。
- E0 工作日志与旧交接入口已原样归档到 `archive/handoffs/2026-08-26-e0-closeout/`；只有回查历史过程时才读取，归档文本不再维护。

### 2.2 Issue 与提交索引

| Issue | 提交 | 已固定边界 |
| --- | --- | --- |
| #1 | `31f6c1a` | Registry exact dependencies |
| #2 | `c727fba` | 冻结 seed artifact 与受审计 bootstrap |
| #3 | `2eeb682` | 启动生命周期与 readiness |
| #4 | `9401955` | 并发启动、事务失败矩阵与失败审计 |
| #5 | `8297c94` | 分层证据、正式状态同步与 E0 关闭 |
| #6 | `4d2fe6b`、`c588c69` | `CONTEXT.md` 与工程术语索引分权及领域词项整理 |
| #7 | `bb6deec` | V6 与全部非历史项目文档一致性审计 |
| #8 | 以 Issue 关闭评论为准 | 归档 E0 交接材料并重建本入口 |

V6、冻结合同和机器制品的审计前置基线是 `d14ce67`。上表用于定位检查点，不代替 `git log`、Issue 关闭证据或现行状态账本。

## 3. 不得混用的当前状态

| 命名空间/记录 | 当前值 | 准确含义 |
| --- | --- | --- |
| 产品里程碑 M0 | `complete` | V6 的 M0 产品结果已完成 |
| `MILESTONE-001` | `verified` | 有证据证明 M0 已 `complete` |
| `ENGINE-001` / E0 | `verified` | Engine Stage E0 实现与验收已关闭 |
| `CONTENT-001` | `implemented` | E0 内容启动闭环已实现；M1 完整后台发布服务未实现 |
| `WORLD-001` | `specified` | 世界物化、移动、战斗和战利品 E2E 尚未实现 |
| `AUTH-001`–`AUTH-003` | `specified` | E1 的注册、认证、角色与 Presence 租约合同已有定义，尚无实现验收 |
| `MILESTONE-002` | `specified` | M1-A/M1-B 门禁已有定义，不能从 E0 推断完成 |
| `CLIENT-001`、`NFR-001`、`NFR-002` | `blocked` | 浏览器、容量/soak 与发布级恢复证据未完成 |
| `RELEASE-001` / `PublicV1Gate` | `blocked` | 尚不具备公开接纳真实玩家的发布证据 |

产品里程碑状态使用 `not_started / in_progress / blocked / complete`；`17_REQUIREMENTS_TRACEABILITY.md` 的追踪记录使用 `specified / implemented / verified / blocked / retired`。不要把产品 M0 写成 `verified`，也不要把 `MILESTONE-001` 写成 `complete`。

## 4. 已冻结、不要重新解释的决策

- `CONTEXT.md` 是领域词汇唯一权威；`UBIQUITOUS_LANGUAGE.md` 只是非权威工程术语、来源名称和合同导航索引。
- `Presence` 是 AuthSession 控制 Character 的运行时控制上下文；`PresenceSnapshot` 是 active/grace 的持久恢复租约与检查点。
- `Actor` / `ActorRef` 只表示 Character 或 NPC，不表示 User、Room、Item、平台操作者或任意 Entity。
- `RetiredCharacter` 只在其 GameAccount 已进入永久 `retired` 后成立；临时 `cooling_off` 不产生 RetiredCharacter。
- 领域概念 `CharacterCreationProfile` 由 typed registry 的 `CharacterCreationProfileDefinition` 表示；不要改回自由字符串或未版本化配置。
- E0 已固定活动批次读取 exact revision、钉定对象读取 historical revision，以及 Blueprint/Registry 两类 exact dependency；E1 只能消费这些边界，不能另造“latest”解析路径。
- `requirements_v5.md` 是不再维护的历史基线。现行工作以 V6 为产品权威，不向 V5 回写。

## 5. 最近一次可复核验证

Issue #8 的 2026-08-26 交接重建证据：

- 原 handoff 与 worklog 的归档 blob 分别和 `bb6deec` 中对应文件完全一致，归档过程没有改写历史文本。
- `scripts/verify_m0.py`：57,053 checks，READY。
- 现行 Markdown：133 checks，0 errors。
- E1 未勾选验收项机器计数为 24。

Issue #5 的 2026-08-25 E0 验收证据：

- PostgreSQL-enabled 全量 pytest：`73 passed`。
- 默认全量 pytest：`57 passed`，另有 16 项仅因未设置 `RUN_POSTGRES_TESTS=1` 跳过；这些项目已由真库全量覆盖。
- Ruff lint 通过；Ruff format 检查为 52 个文件已格式化。
- mypy 检查 52 个源文件，0 issues。
- Django check 0 issues；无 migration drift；`pip check` 通过。

Issue #7 的 2026-08-26 文档审计证据：

- `scripts/verify_m0.py`：57,055 checks，READY，0 profile blocker。
- Markdown：135 checks，0 errors。
- 文档合同测试、差异检查通过；检查点提交后本地与远端同步、工作树干净。

这些是最后一次完整检查点的证据，不是未来修改后的自动保证。开始新实现后必须按受影响范围重新执行门禁。

## 6. 仍未完成的事实

- Engine Stage E1 尚未开始。`plans/m0-e1-tracer-bullets.md` 的三个 E1 切片共有 24 项验收条件，当前全部未勾选：Slice 1 为 8 项、Slice 2 为 9 项、Slice 3 为 7 项。
- 浏览器 profile 已批准，但 `contracts/v1/profiles/browser-matrix.json` 中所有 `tested_versions` 都为空；PC/移动 H5 浏览器 E2E 未形成证据。
- capacity profile 已批准，但容量报告和两小时 soak 报告不存在。
- `contracts/v1/reports/m0-recovery-latest.json` 只证明 M0 基础设施恢复，`release_gate_eligible=false`；accounts、characters、world_topology、content_batches、audit_chain 五个发布级业务范围均为 `not_implemented`。
- 尚无合格的 `ReleaseManifest`、7 天封闭试运行、至少 5 名非管理员测试者、至少 20 次核心循环及完整公开资料证据。
- 完整内容后台发布服务、固定小巷世界物化和玩法 E2E 仍属于后续 M1 工作，不能从 E0 seed/startup 推断完成。

## 7. E1 的唯一合法启动顺序

本交接检查点不启动 E1，也不创建 E1 工作日志。下一会话只有在用户明确要求继续开发时才执行以下顺序：

1. 完成第 1 节仓库和 Issue 检查，确认不需要恢复未提交工作。
2. 阅读 `plans/m0-e1-tracer-bullets.md` 的 E1 / Slice 1，以及 `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`、`11_PROTOCOL_CATALOG.md`、`13_SESSION_AUTH_STATE_MACHINE.md`、`15_FRONTEND_H5_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md` 的注册、认证、Cookie、refresh、logout、浏览器和测试边界。
3. 同时读取 `CONTEXT.md`、`requirements_v6.md` 第八章、`17_REQUIREMENTS_TRACEABILITY.md` 与 `18_IMPLEMENTATION_STATUS.md`，确认术语和状态没有被后来提交改变。
4. 用 `gh issue list` 搜索是否已有 E1 / Slice 1 ticket；没有时创建一个只覆盖“注册与独立登录闭环”的独立 Issue，并在写代码前认领。
5. 在该 ticket 内 test-first 实现 Slice 1；验收范围是计划中的 8 项，不提前混入 Slice 2 的 Character/Presence 或 Slice 3 的 takeover。
6. 只有 ticket 的测试、分层门禁、双轴审查、状态同步和提交证据齐备后才关闭 Slice 1。届时再建立新的阶段工作日志或更新本交接入口。

## 8. 权威来源与读取条件

| 需要回答的问题 | 读取来源 |
| --- | --- |
| 产品目标、M1/Public V1 范围、里程碑和验收结果 | `requirements_v6.md` |
| 领域概念名称和定义 | `CONTEXT.md` |
| 协议、状态机、事务、失败语义与测试机制 | 受影响的 `docs/new_engine/11-16` |
| 当前需求证据成熟度 | `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` |
| 当前实现、环境、验证结果与阻塞项 | `docs/new_engine/18_IMPLEMENTATION_STATUS.md` |
| E0/E1 纵向切片、顺序与验收清单 | `plans/m0-e1-tracer-bullets.md` |
| 文档冲突和归档规则 | `docs/19_documentation_governance.md` |
| E0 历史过程和旧会话状态 | `archive/handoffs/2026-08-26-e0-closeout/`，仅在追溯时读取 |

Issue 与规格统一使用 GitHub Issues 和 `gh` CLI，具体命令见 `docs/agents/issue-tracker.md`。任何交接摘要与权威来源冲突时，先停止状态提升，再按上表修正现行材料。

## 9. 工程与证据边界

- 保留工作树中来源不明的既有修改，不执行破坏性还原或清理。
- `evennia-main/` 和 XKX100 来源目录只作为参考/输入，不在新引擎实现中改写。
- PostgreSQL 凭据只通过进程环境提供，不进入仓库、文档、日志或合同制品。
- PostgreSQL 测试与全量 pytest 严格串行，统一使用 `--basetemp artifacts\reports\pytest-temp`，避免数据库和临时目录竞争。
- 结构检查、局部测试、profile 批准和内部 M1 候选都不能单独提升正式状态或通过 `PublicV1Gate`。
- 归档文件只用于历史追溯；现行事实只更新本入口、17/18、计划或对应权威文档。
