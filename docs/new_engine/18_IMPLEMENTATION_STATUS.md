# 18 实施状态与验证记录

> 状态：现行实施证据账本。本文记录代码、环境、验证结果与阻塞项，不创造产品需求或实施语义；发生冲突时，按 `docs/19_documentation_governance.md` 回到对应权威来源处理。

## 1. 目的与边界

本文用于回答三个问题：

- 当前仓库已经实现并验证了什么。
- 哪些结果仍因实现缺口、审批或验收报告而阻塞。
- 某项状态判断可以回查到哪些提交、制品、脚本和测试。

本文不是发布说明，也不把结构检查通过等同于需求里程碑完成。产品结果仍以 `requirements_v5.md` 为准，实施机制仍以 `docs/new_engine/11-16` 为准，需求状态仍以 `17_REQUIREMENTS_TRACEABILITY.md` 为准，实施顺序仍以 `10_ROADMAP.md` 为准。

## 2. 当前基线

| 基线 | 身份 | 当前结论 |
| --- | --- | --- |
| 文档审计基线 | Git `e7a3717` | V1-V4 已归档，V5、术语、文档治理、概念设计、冻结合同和追踪索引已形成现行文档体系 |
| M0 工程基线 | Git `7bd76a3` | Django/ASGI 骨架、PostgreSQL 初始迁移、机器合同、来源制品、CI 与自动校验已建立 |
| Python 基线 | CPython `3.14.2` | `.venv` 使用仓库内 `.venv/runtime`，不读取用户级 site-packages |
| PostgreSQL 基线 | PostgreSQL `18.4` | 本机服务、项目角色、项目数据库、迁移往返和数据库合同测试已验证 |
| 依赖基线 | `requirements.lock` | 56 个运行、开发、传递及打包工具依赖精确锁定；在线过时检查为空 |

## 3. 2026-07-19 工作记录

### 3.1 文档审计与归档

- 两轮全量审查覆盖当时 46 份项目自有 Markdown 文档，并在归档完成后复审全部现行、未归档项目文档；`evennia-main/` 中的上游源码与上游文档不属于项目文档审核范围。
- 审核覆盖 Markdown 结构、本地引用、术语、需求、协议、状态机、Blueprint、来源制品、测试、运维语义和跨文档冲突；最终结构、引用与陈旧模式复扫均通过。
- 将 `requirements_v1.md` 到 `requirements_v4.md` 移入 `archive/requirements/`，并保留归档入口与历史审计记录。
- 确立按关注点划分的文档权威：V5 管产品结果，11-16 管冻结实施机制，17 管需求追踪，00-10 管概念设计与路线，00-18 管 Evennia 来源分析。
- 明确 `evennia-main/` 仅为 Evennia 6.0.0 本地参考快照，不是运行时依赖；本轮未修改该目录。
- 审核范围、修复分类、二轮验证和剩余风险的快照记录见 `archive/audits/2026-07-19-requirements-v5/requirements_v5_doc_audit_summary.md`。

### 3.2 Git 基线

- 以 `e7a3717` 建立审计后的正式文档基线。
- 以 `7bd76a3` 建立 M0 可执行合同与工程骨架基线。
- 两个提交均保留需求、合同、实现与验收证据之间的追溯关系。

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
| pytest | 12 项通过，其中 3 项为 PostgreSQL 合同测试 |
| M0 合同校验 | 56,883 项通过，profile blocker 为空 |
| PostgreSQL 隔离恢复 | 通过；实测 RPO 0.004057 分钟，RTO 0.01816 分钟 |

pytest 仍报告 Daphne 对 Python 3.16 将移除的 asyncio policy API 的两条弃用警告。当前运行时为 Python 3.14.2，且检查当日没有可升级的 Daphne 版本，因此该警告记录为上游兼容性观察项，不构成当前失败。

### 3.7 非功能 M0 基线收口

- browser matrix 已由 `project-owner` 批准，基于 Apple、Google、Microsoft 与 Mozilla 官方版本源冻结桌面和移动精确目标组合；iOS Safari 保留在首发目标中。所有 `tested_versions` 仍为空，等待真实 H5 浏览器 E2E 填写。
- capacity profile 已批准首发环境、数据量、负载、采样窗口和阈值；本次没有生成容量或两小时 soak 报告。
- 新增 `recovery-report.schema.json` 与 `run_recovery_drill.py`。最终演练使用 PostgreSQL/pg_dump/pg_restore 18.4，在同一导出快照上生成临时 custom dump，恢复到随机隔离数据库，并验证 schema 哈希、16 张表逐表行数、16 条 Django 迁移历史及工具主版本一致。
- 恢复报告 `m0-recovery-20260719-145739z` 的文件 SHA-256 为 `7be50190df61aba84507f8f086ba1440bd39343fec585f2526edf633e8748f82`。临时 dump 与隔离数据库均已删除，报告不含数据库凭据。
- 账号、角色、世界拓扑、非空内容批次和审计链尚未形成发布样本，因此报告固定为 `release_gate_eligible=false`；它只证明 M0 恢复工具链，不把 `NFR-002` 提前标记为通过。
- CI 已从仅结构检查切换到完整 M0 合同门禁，报告路径、报告 ID、文件哈希、指标、范围集合和内部通过条件均自动复核。

## 4. 当前状态

| 对象 | 状态 | 依据 |
| --- | --- | --- |
| 文档基线 | `verified` | 审计归档与 Git `e7a3717` |
| M0 机器合同基线 | `verified` | `verify_m0.py` 的 56,883 项检查，profile blocker 为空 |
| `CONTENT-001` | `implemented` | 初始模型、迁移与 PostgreSQL 合同测试已存在；seed bootstrap、resolver 与完整发布服务仍待后续纵切 |
| `CONVERT-001` | `implemented` | 来源快照、双 manifest、bundle、生成器与篡改检查已存在；M4 黄金差分仍未实现 |
| 非功能 M0 profile 基线 | `verified` | browser、capacity、recovery 三份 profile 已批准，恢复报告路径/ID/哈希与指标已纳入自动校验 |
| `MILESTONE-001` / Engine Stage E0 | `blocked` | 非功能 M0 基线已收口；seed bootstrap、active batch resolver 与 pinned historical revision resolver 尚未完成 |

M0 机器合同当前通过且没有 profile blocker。E0 仍有以下实施阻塞项：

- 受审计 seed bootstrap 尚未原子创建完整活动发布批次。
- 新选择读取 active batch 的 resolver 尚未实现。
- 已钉定对象读取 exact historical revision 的 resolver 尚未实现。

浏览器实际执行、容量报告与五个业务恢复范围仍是 M1/发布候选证据，因此 `CLIENT-001`、`NFR-001` 和 `NFR-002` 保持 `blocked`，不因 M0 目标获批而提前转为 `verified`。

经确认的下一步纵向实施计划见 `plans/m0-e1-tracer-bullets.md`。该计划先用两个切片收口 E0，再用三个切片完成 E1 的注册登录、连接恢复和跨设备接管闭环。

## 5. 证据映射

| 需求 ID | 当前证据 |
| --- | --- |
| `MILESTONE-001` | `contracts/v1/`、`scripts/verify_m0.py`、`.github/workflows/m0.yml`、本文件第 3.6 节 |
| `CONTENT-001` | `src/new_mud/apps/content/models.py`、`0001_initial.py`、`tests/test_postgres_content_contract.py` |
| `CONVERT-001` | `contracts/v1/artifacts/`、`scripts/generate_source_contracts.py`、`tests/test_contracts.py` |
| `CLIENT-001` | `browser-matrix.json` 已批准且冻结目标版本；实际 `tested_versions` 与浏览器 E2E 尚缺 |
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
