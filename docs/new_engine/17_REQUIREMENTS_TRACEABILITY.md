# 17 需求追踪索引

> 状态：现行追踪索引。本文不创造产品需求或实施语义，只连接 `requirements_v5.md`、冻结合同、需求里程碑和验收证据。

## 1. 状态与使用规则

需求状态只允许：

- `specified`：需求和合同已明确，尚无实现证据。
- `implemented`：存在实现，但尚未通过全部验收。
- `verified`：必做验收证据全部通过。
- `blocked`：存在未满足的必做依赖或门禁。
- `retired`：需求已通过有意变更废弃，ID 永不复用。

当前仓库已建立 M0 工程骨架、机器合同、源快照制品和 PostgreSQL 初始迁移。状态按实际证据逐项记录；非功能 profile 的结构已经冻结，但审批与执行报告缺失，因此对应需求和 M0 保持 `blocked`。

带执行日期、环境版本、测试结果和当前阻塞项的证据账本见 `18_IMPLEMENTATION_STATUS.md`；本索引只维护需求状态与必要证据映射，不重复保存运行日志。

## 2. 首发需求映射

| 需求 ID | 状态 | 产品结果 | V5 来源 | 实施权威 | 里程碑 | 必要证据 |
| --- | --- | --- | --- | --- | --- | --- |
| `PROD-001` | `retired` | 已废弃：content release mode 与内容授权不再属于工程门禁 | 2.7 | — | — | 本次有意需求变更记录 |
| `AUTH-001` | `specified` | 新玩家可用用户名密码注册；注册不隐式登录 | 4.1、8.4、11.2 | 08 第 4.2 节、13 第 1/5 节 | M1 | API 契约、事务与 H5 E2E |
| `AUTH-002` | `specified` | login 创建唯一 AuthSession/family，refresh 轮换，logout 幂等收敛 | 8.4-8.5 | 08 第 4.2 节、13 | M1 | 状态机、重放、logout 矩阵 |
| `AUTH-003` | `specified` | 每账号最多一个角色和一个 active/grace Presence | 8.6 | 11、13 | M1 | 数据库约束、并发 enter/takeover E2E |
| `WORLD-001` | `specified` | 固定小巷纵切可进入、查看、移动、生成、战斗和查看战利品 | 7.3、11.4 | 12、14、16 第 8 节 | M1 | fixture、世界物化、端到端测试 |
| `COMBAT-001` | `specified` | 只有兼容包络内 verified 行为可声明与 XKX100 对齐 | 7.2.1、10.4、11.4 | 14、16 第 8 节 | M1、M4 | envelope、golden case、差分报告 |
| `CONTENT-001` | `implemented` | 内容通过不可变 revision、完整批次、冷发布和批次回滚生效 | 5.4、6.13-6.14 | 12 | M0、M1 | `src/new_mud/apps/content/models.py`、`0001_initial.py` 与 PostgreSQL CI 合同测试；发布服务仍待 M1 |
| `ADMIN-001` | `specified` | M1 后台只编辑白名单对象，并实施角色分权和自批禁止 | 12.1-12.4 | 08 第 1-3 节、12 | M1 | 权限矩阵、审计、发布 E2E |
| `CLIENT-001` | `blocked` | PC 与移动 H5 在固定浏览器、视口、中文输入和无障碍矩阵通过 | 9.2.1、9.3-9.5 | 15 | M1 | `browser-matrix.json` 已批准并冻结官方精确目标；实际 `tested_versions`、视觉和交互 E2E 尚未执行 |
| `NFR-001` | `blocked` | 默认 capacity profile 的负载、延迟和稳定运行目标全部达标 | 13.4-13.7 | 16 第 3/7 节 | M0、M1 | `capacity-profile.json` 的 M0 目标已批准；容量报告与两小时 soak 尚未执行 |
| `NFR-002` | `blocked` | 备份保留、RPO、RTO 和隔离恢复演练全部达标 | 13.2、14.4、13.7 | 16 第 5-6 节 | M0、M1 | `recovery-budget.json` 已批准并绑定 M0 基础设施恢复报告；保留/WAL 与五个业务范围的发布级演练尚未完成 |
| `MILESTONE-001` | `blocked` | M0 制品、合同、发布契约和非功能 profile 全部冻结 | 15.0-15.1 | 10 E0、16 | M0 | M0 机器合同与三个 profile 已就绪；seed bootstrap、active batch 与 pinned revision resolver 仍阻断 E0 |
| `MILESTONE-002` | `specified` | M1-A 仅为内部可玩验证，M1-B 才等同 M1 完成 | 15.0、15.2 | 10 E1-E9、16 第 10 节 | M1 | 两阶段门禁与发布候选报告 |
| `CONVERT-001` | `implemented` | 转换和黄金验收绑定不可变 source snapshot、双 manifest 与 bundle | 7.2-7.16 | 09、16 第 8 节 | M0、M4 | `contracts/v1/artifacts/`、`generate_source_contracts.py` 与哈希篡改测试；M4 差分制品仍待实现 |

## 3. 变更规则

- 改变产品结果时，先修改 V5，再同步本索引和对应实施合同。
- 只改变实施机制时，修改对应冻结合同和本索引；产品结果不变时不向 V5 复制字段。
- 一个需求拆成多个独立结果时保留原 ID 作为父项，并为新结果分配新 ID。
- 任一必做需求处于 `blocked` 时，引用它的里程碑不得为 `complete`。
- 例外只适用于纯展示差异或非必做项；必做能力只有 `verified` 才能通过，例外记录不得改变其状态。
- 发布证据必须记录需求 ID、代码版本、测试环境、执行时间和结果摘要。
