# Engine Stage E0 / Slice 2 内容启动闭环工作记录

> 记录起始日期：2026-08-22；实现完成复核：2026-08-25
> 当前状态：`verified`
> 性质：实施过程快照，不是产品需求、冻结合同或阶段完成证明。权威需求、实施机制和状态分别以 `requirements_v6.md`、`docs/new_engine/11_PROTOCOL_CATALOG.md`–`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`、`docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 与 `docs/new_engine/18_IMPLEMENTATION_STATUS.md` 为准。

> 第 1–6 节保留 2026-08-23 的实现中间快照，其中的 `partial` / `pending` / `blocked` 只描述当时状态。第 7 节是 Issues #1–#4 完成后的验收前快照；当前结论由第 8 节的 Issue #5 验收记录取代。

## 1. 本轮目标与起点

本轮按照 `docs/new_engine/NEXT_SESSION_HANDOFF.md`，从 `plans/m0-e1-tracer-bullets.md` 的 Engine Stage E0 / Slice 2“受审计内容启动闭环”开始实施，目标是收口以下三个 E0 阻塞项：

1. 受审计 seed bootstrap。
2. active batch resolver。
3. pinned historical revision resolver。

开始实施前已检查工作树和最近五个提交，确认以下实施基线存在：

| 提交 | 基线 |
| --- | --- |
| `97659ce` | M0 非功能 profile 基线收口 |
| `b4798fb` | 已验证环境与五切片实施计划 |
| `7bd76a3` | M0 工程骨架与可执行合同基线 |
| `e7a3717` | 审计后的正式文档基线 |

同时确认工作树包含 2026-08-22 Evennia 参考边界对齐文档变更。本轮保留了这些用户修改，没有还原或覆盖它们。

## 2. 已完成的代码工作

### 2.1 Seed bundle 与启动服务

新增 `src/new_mud/apps/content/startup.py`，当前包含：

- `SeedBundle`、`ContentReleaseIdentity`、`ContentStartupResult` 与明确的启动状态/错误类型。
- 使用 RFC 8785 canonical JSON 和 SHA-256 计算 seed 内容、revision、依赖与 release 身份。
- 固定并校验 `blueprint-compiler/1` compiler contract。
- 对 Blueprint 按 `blueprint_key` 稳定排序，并拒绝空 key、重复 key、缺失 parent 和继承环。
- 解析 parent 继承，深度合并 parent 与 child 的 `data`，记录精确 parent revision lineage。
- 为 parent 引用生成 `ResolvedBlueprintDependency`，保存依赖路径、类型、序号、target head、target revision、target key 与 expected kind。
- 在单个 PostgreSQL 事务中创建完整首版内容真源：
  - `ContentReleaseHead`
  - `ContentReleaseBatch`
  - `BlueprintHead`
  - `BlueprintRevision`
  - `ResolvedBlueprintDependency`
  - `ContentReleaseItem`
  - published revision 与 active batch 指针
- 首次启动返回 `bootstrapped`；重复启动校验既有 seed 和 active release 后返回 `verified`，不重复导入。
- 对 seed 内容哈希、compiler contract、活动批次和 release hash 执行失败封闭校验。
- 识别 release head 缺失但 namespace 已存在、active batch 缺失、seed 身份不匹配和 release item 被篡改等不完整状态。

实现入口为 `bootstrap_seed_bundle()`；当前实现直接接收内存中的 `SeedBundle`，尚未接入真实服务器启动生命周期或从冻结 seed 制品加载的生产入口。

### 2.2 Active 与 pinned resolver

新增 `src/new_mud/apps/content/resolver.py`，当前包含：

- `ContentResolver.resolve_active()`：按 `instance_id / mudlib_key / target_content_release / blueprint_key` 从当前 active batch 读取精确 published revision。
- `ContentResolver.resolve_pinned()`：按 immutable `revision_id` 读取历史 published revision，不受之后的 active batch 切换影响。
- `ResolvedBlueprint` 与 `ResolvedBlueprintDependencyView`：向调用方返回 revision、batch、compiled payload 和已经持久化的 exact Blueprint dependencies。
- 对不存在的活动 Blueprint 或历史 revision 返回明确的 `ContentResolutionError`。

### 2.3 TDD 场景

新增 `tests/test_content_startup.py`，已写入七个场景：

1. 空实例首次启动创建一个完整 active release。
2. 重复启动保持幂等，不增加 head、revision、batch 或 item。
3. active resolver 读取活动批次固定的 revision。
4. active batch 切换后，pinned resolver 继续读取原历史 revision。
5. seed bundle 内容哈希被篡改时，在初始化前拒绝启动。
6. compiler contract 不受支持时，在初始化前拒绝启动。
7. seed bootstrap 持久化并解析精确 parent revision dependency。

前六个场景在开发过程中经过了多轮 RED→GREEN。第七个 parent exact dependency 场景及对应实现写入后，最初曾被 Skills 检查打断；2026-08-23 的后续证据复核已重新运行七项并得到 `7 passed`。这只证明目标测试当前通过，不等于完整分层验收或 Engine Stage E0 已完成。

## 3. Engine Stage E0 / Slice 2 验收状态

下表的 `evidence_state` 只描述本轮过程证据，不是 `17_REQUIREMENTS_TRACEABILITY.md` 的正式需求状态，也不能直接写入正式需求状态列。正式状态仍以 `17_REQUIREMENTS_TRACEABILITY.md` 和 `18_IMPLEMENTATION_STATUS.md` 为准。

| Engine Stage E0 / Slice 2 验收项 | 当前证据 | `evidence_state`（过程状态，非 17 的需求状态） |
| --- | --- | --- |
| 从通过 schema/哈希校验的 seed 原子创建完整活动批次 | 已有内存 bundle 哈希与 compiler contract 校验及事务创建路径；真实冻结制品加载/schema 接入未完成 | `partial` |
| 重复启动幂等 | 已有实现和测试场景 | `implemented_unverified` |
| 新选择读取 active batch exact revision | 已有 resolver 和测试场景 | `implemented_unverified` |
| pinned 对象在切换后读取历史 revision 及两类 exact dependency | historical revision 与 parent dependency 已实现；registry dependency 未实现 | `partial` |
| 缺少活动批次、哈希不一致、依赖缺失或 compiler contract 不匹配时明确失败 | 已覆盖其中一部分代码路径和测试；失败矩阵未完整 | `partial` |
| PostgreSQL 约束、服务集成和启动级端到端测试 | 只有新增 Django 数据库测试文件，尚未完成完整分层验证 | `pending` |
| Engine Stage E0 / Slices 1-2 全部通过后关闭 E0 | 尚不满足 | `blocked` |

## 4. 已有证据与尚未完成项

截至 2026-08-23，本轮已有以下可复核证据：

- `\.venv\Scripts\python.exe -m pytest tests\test_content_startup.py -q`：`7 passed`。
- `\.venv\Scripts\python.exe -m pytest -q`：`16 passed, 3 skipped`；3 个跳过项是 PostgreSQL 合同测试，因未设置 `RUN_POSTGRES_TESTS=1`。
- `\.venv\Scripts\python.exe scripts\verify_m0.py`：`56,981 checks passed`，无 profile blocker。

这些结果证明当前代码和 M0 机器合同基线的局部事实，不证明 Engine Stage E0 / Slice 2 或任何发布里程碑已完成。

以下事项仍是后续工作，不得从本记录推断为已完成：

- 使用 `RUN_POSTGRES_TESTS=1` 运行 PostgreSQL 合同测试，并在当前工作树重新取得服务集成、启动级 E2E、Ruff、mypy、Django check、迁移漂移和 `pip check` 的证据。
- 实现并验证 registry exact dependency；当前只有 parent/Blueprint dependency。
- 将冻结 seed 制品的 schema、身份与哈希验证接入真实加载路径。
- 将 bootstrap 和 resolver 接入服务器启动生命周期、健康结果和运营可见的失败原因。
- 补齐活动批次缺失、哈希错误、依赖缺失、部分初始化、并发首次启动和数据库回滚等失败/竞争场景。
- 完成服务集成测试和启动级端到端测试。
- 依据最终测试证据更新 `17_REQUIREMENTS_TRACEABILITY.md` 与 `18_IMPLEMENTATION_STATUS.md`。
- 当前三个新增代码/测试文件以及相关文档仍未提交；是否提交由下一会话按工作树审查结果决定。

因此 `MILESTONE-001 / M0` 保持 `implemented`，`ENGINE-001 / Engine Stage E0` 保持 `blocked`；`CONTENT-001` 当前保持 `implemented`，`WORLD-001` 当前保持 `specified`。这些正式状态不得仅因 WIP 文件或局部测试存在而提升。

## 5. 下一次继续顺序

1. 检查工作树并保留现有文档、代码和本记录，不从头重写 Engine Stage E0 / Slice 2。
2. 阅读本记录、`plans/m0-e1-tracer-bullets.md` Engine Stage E0 / Slice 2 和 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 的 exact dependency/release 约束。
3. 若实现有新变化，重新运行 `\.venv\Scripts\python.exe -m pytest tests\test_content_startup.py -q`；当前基线为 `7 passed`。目标测试通过只代表局部行为可用，不代表 E0 完成。
4. 在现有实现上补齐 Registry exact dependency、冻结 seed 制品真实加载（schema/身份/哈希）和完整失败矩阵。
5. 将 bootstrap/resolver 接入服务器启动生命周期、readiness 和运营可见失败结果，并补齐首次并发启动与事务回滚测试。
6. 完成 `RUN_POSTGRES_TESTS=1` 的 PostgreSQL 合同测试、服务集成、启动级端到端及全量质量门禁。
7. 只有在以下 E0 Slice 2 完成标准全部满足后，才同步需求追踪和实施状态：
   - 真实冻结 seed 制品已加载，并校验 schema、身份和哈希。
   - Registry exact dependency 已实现、持久化、解析并通过测试。
   - bootstrap/resolver 已接入真实服务器启动生命周期，readiness 能反映失败原因。
   - 缺失 active batch、哈希错误、依赖缺失、部分初始化、并发首次启动和事务回滚均有测试。
   - PostgreSQL 合同测试、服务集成和启动级 E2E 通过，且当前工作树质量门禁有证据。
   - `17_REQUIREMENTS_TRACEABILITY.md` 与 `18_IMPLEMENTATION_STATUS.md` 已按证据同步，并形成包含完整证据索引的提交检查点。
8. E0 完成前未通过项继续保持过程 `partial` / `pending` / `blocked`，正式需求状态仍按权威状态账本维护；完成提交检查点后，E0 才能进入关闭评审，E0 关闭后才进入 E1。

## 6. 本轮边界

本轮没有修改 `evennia-main/` 或 XKX100 来源目录，没有写入 PostgreSQL 凭据，没有提交代码，也没有把 `ENGINE-001`、`CONTENT-001`、`WORLD-001` 或 `MILESTONE-001` 提前标记为完成。当前工作树仍未提交；权威审查报告只是参考记录，不是阶段完成证据。

## 7. 2026-08-25 实现完成、验收待收口

第 1–6 节之后，E0 / Slice 2 的实现已按四个独立 Issue 提交：

| Issue | 提交 | 交付边界 |
| --- | --- | --- |
| #1 | `31f6c1a` | Registry exact dependencies |
| #2 | `c727fba` | 冻结 seed artifact 与受审计 bootstrap |
| #3 | `2eeb682` | 服务器启动生命周期与只读 readiness |
| #4 | `9401955` | 并发启动、事务失败矩阵与失败审计 |

因此真实冻结制品加载、两类 exact dependency、active/pinned resolver、启动集成、并发收敛、事务回滚和失败审计不再是实现缺口。当前唯一剩余 frontier 是 Issue #5：在已提交的 V6 权威基线上取得 PostgreSQL 合同、服务集成、启动级 E2E、全量 pytest、静态、Django、迁移、依赖、M0 和 Markdown 证据，建立完整证据索引，再按实际结果同步 `ENGINE-001`、`CONTENT-001`、`WORLD-001` 与 `MILESTONE-001`。

在 Issue #5 完成前，`ENGINE-001 / Engine Stage E0` 仍保持 `blocked`，`MILESTONE-001 / M0` 保持 `implemented`；这表示最终验收尚未固定，不否定 Issues #1–#4 已提交的实现。`RELEASE-001 / PublicV1Gate` 未开始，E1 也未开始。

## 8. 2026-08-25 Issue #5 分层验收与状态收口

Issue #5 在 V6 权威基线 `d14ce67` 上执行。环境为 Windows 10 `10.0.19045`、CPython `3.14.2`、PostgreSQL `18.4-2`；数据库测试和全量 pytest 严格串行，统一使用 `--basetemp artifacts\reports\pytest-temp`。未记录或提交数据库凭据。

### 8.1 可执行证据索引

| 层 | 命令 | 结果 | 对应边界 |
| --- | --- | --- | --- |
| PostgreSQL 合同与启动 E2E | `$env:RUN_POSTGRES_TESTS='1'; .\.venv\Scripts\python.exe -m pytest tests\test_postgres_content_contract.py tests\test_postgres_content_startup.py -q --basetemp artifacts\reports\pytest-temp` | 16 passed | `ENGINE-001`；合同 12 第 14 节、16 第 2/8 节 |
| 内容服务集成 | `$env:RUN_POSTGRES_TESTS='1'; .\.venv\Scripts\python.exe -m pytest tests\test_content_registry.py tests\test_content_runtime.py tests\test_content_startup.py tests\test_health.py tests\test_seed_artifact.py tests\test_postgres_content_contract.py tests\test_postgres_content_startup.py -q --basetemp artifacts\reports\pytest-temp` | 66 passed | Registry、seed、startup、runtime、readiness、并发与失败审计 |
| 启用真库的全量测试 | `$env:RUN_POSTGRES_TESTS='1'; .\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\reports\pytest-temp` | 73 passed | E0 / Slice 2 全量回归 |
| 默认全量与跳过边界 | `.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\reports\pytest-temp` | 57 passed、16 skipped | 16 项仅因未设置 `RUN_POSTGRES_TESTS=1` 跳过，已由真库全量覆盖 |
| Ruff lint | `.\.venv\Scripts\ruff.exe check scripts src tests` | All checks passed | 代码质量门禁 |
| Ruff format | `.\.venv\Scripts\ruff.exe format --check scripts src tests` | 52 files already formatted | 格式门禁 |
| mypy | `.\.venv\Scripts\mypy.exe src scripts tests` | 52 source files，0 issues | 类型门禁 |
| Django | `.\.venv\Scripts\python.exe manage.py check` | 0 issues | Django 配置 / 模型门禁 |
| 迁移漂移 | `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --skip-checks` | No changes detected | schema 与 migration 一致性 |
| 依赖 | `.\.venv\Scripts\python.exe -m pip check` | No broken requirements | 锁定环境完整性 |
| M0 合同 | `.\.venv\Scripts\python.exe scripts\verify_m0.py` | 56,981 checks；READY；0 profile blocker | `MILESTONE-001` |
| Markdown | `.\.venv\Scripts\python.exe -c "from pathlib import Path; from scripts.verify_m0 import VerificationResult, validate_documents; result = VerificationResult(); validate_documents(Path.cwd(), result); print(f'{result.checks} Markdown checks, {len(result.errors)} errors'); raise SystemExit(bool(result.errors))"` | 76 checks、0 errors | 文档结构与本地链接 |
| 暂存快照 | `git diff --cached --check` | 通过 | 提交边界与空白错误 |
| 双轴审查 | `code-review`：Standards + Issue #5 Spec | 0 blocking findings / 0 blocking findings | 仓库规范与 Issue 验收一致性 |

### 8.2 失败边界与正式状态

- pytest 仅报告 Daphne 使用的 asyncio policy API 将在 Python 3.16 移除；当前运行时为 Python 3.14.2，属于已记录的上游兼容性观察项，不构成失败。
- 默认测试的 16 个 skip 不是未执行证据：同一工作树随后以 `RUN_POSTGRES_TESTS=1` 取得 73 passed；任何只引用 57 passed 的记录都必须同时保留该边界。
- `ENGINE-001 / Engine Stage E0` 的必做证据已齐备并同步为 `verified`；产品 M0 已 `complete`，对应追踪记录 `MILESTONE-001` 同步为 `verified`。
- `CONTENT-001` 保持 `implemented`：E0 启动闭环已验证，但 M1 完整后台编辑、发布与回滚服务尚未实现。
- `WORLD-001` 保持 `specified`：冻结来源、seed 与启动验证不等于固定小巷世界物化、移动、战斗和战利品 E2E。
- `RELEASE-001` 保持 `blocked`：浏览器实测、容量/soak、五业务范围恢复、公开试运行、ReleaseManifest 与公开资料均未完成；本检查点不宣称 Public V1。

Issue #5 的提交检查点关闭 E0 / Slice 2。E1 在该检查点提交、双轴审查清零并关闭 Issue 后才可从独立 ticket 开始；本轮未实现任何 E1 行为。
