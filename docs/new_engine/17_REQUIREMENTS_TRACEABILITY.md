# 17 需求追踪索引

> 状态：现行追踪索引。本文不创造产品需求或实施语义，只连接 `requirements_v6.md`、V5 历史指针、冻结合同、需求里程碑和验收证据。

## 1. 状态与使用规则

需求状态只允许：

- `specified`：需求和合同已明确，尚无实现证据。
- `implemented`：存在实现，但尚未通过全部验收。
- `verified`：必做验收证据全部通过。
- `blocked`：存在未满足的必做依赖或门禁。
- `retired`：需求已通过有意变更废弃，ID 永不复用。

这些值表示需求追踪记录的证据成熟度，不替代 V6 对产品里程碑规定的 `not_started / in_progress / blocked / complete`。因此 `MILESTONE-001=verified` 表示已有证据证明产品里程碑 `M0=complete`；不得把产品 M0 自身写成 `verified`。

当前仓库已完成 M0 与 Engine Stage E1 / Slice 1 的历史注册/登录闭环。`AUTH-001`、`AUTH-002` 仍保留 Issue #9 的 PostgreSQL、REST、安全属性和 H5 自动端到端证据；2026-08-26 的产品修订不倒写这些事实，但 RecoveryCode 已不再是现行凭据。Issue #10 建立 `AUTH-005` 的 VerifiedContactMethod/VerificationChallenge 认证权威，Issues #11–#14 已交付权威同步、投递基础、已验证邮箱最终注册、邮箱密码重置、跨实例即时认证撤销、安全通知 outbox 与 H5，Issue #15 已交付 RecoveryCode 不可逆退役和认证基线受控切换；仍须由 #16 完成分层总证据后，才能进入 Character Slice 2。`AUTH-004` 的旧复合语义已退役，User/GameAccount 基数与 PresenceRecovery 分别由 `IDENTITY-001`、`AUTH-006` 追踪。

browser、capacity、recovery 三份非功能 profile 已批准，但发布级浏览器矩阵、容量、soak 和五范围恢复证据仍未完成，所以 `CLIENT-001`、`NFR-001`、`NFR-002` 与 `RELEASE-001` 继续保持 `blocked`；`MILESTONE-002` 也不因认证权威修订或单一切片完成而提升。

带执行日期、环境版本、测试结果和当前阻塞项的证据账本见 `18_IMPLEMENTATION_STATUS.md`；本索引只维护需求状态与必要证据映射，不重复保存运行日志。

## 2. 首发需求映射

| 需求 ID | 状态 | 产品结果 | V6 来源（V5 历史） | 实施权威 | 里程碑 | 必要证据 |
| --- | --- | --- | --- | --- | --- | --- |
| `PROD-001` | `retired` | 已废弃：content release mode 与内容授权不再属于工程门禁 | 2.7 | — | — | 本次有意需求变更记录 |
| `AUTH-001` | `verified` | 新玩家以账号名和密码注册；注册不隐式登录 | V6 4.1、8.4、11.2 | 08 第 4.2 节、13 第 1/5 节 | M1 | Issue #9 历史证据：User/GameAccount/RecoveryCode 原子事务、统一错误/限流、普通 login 与 H5 E2E；RecoveryCode 后由 AUTH-005 取代 |
| `AUTH-002` | `verified` | login 创建唯一 AuthSession/family，refresh 轮换，logout 幂等收敛 | 8.4-8.5 | 08 第 4.2 节、13 | M1 | Issue #9：真库约束与并发、refresh terminal/replay、双 locator logout、前端 single-flight 与 H5 E2E |
| `AUTH-003` | `specified` | 每账号最多一个角色和一个 active/grace PresenceSnapshot 租约 | 8.6 | 11、13 | M1 | 数据库约束、并发 enter/takeover E2E |
| `WORLD-001` | `specified` | 固定小巷纵切可进入、查看、移动、生成、战斗和查看战利品 | 7.3、11.4 | 12、14、16 第 8 节 | M1 | fixture、世界物化、端到端测试 |
| `COMBAT-001` | `specified` | 只有兼容包络内 verified 行为可声明与 XKX100 对齐 | 7.2.1、10.4、11.4 | 14、16 第 8 节 | M1、M4 | envelope、golden case、差分报告 |
| `CONTENT-001` | `implemented` | 内容通过不可变 revision、完整批次、冷发布和批次回滚生效 | 5.4、6.13-6.14 | 12 | M0、M1 | Issues #1–#5 已验证两类 exact dependency、冻结 seed bootstrap、active/pinned resolver、启动/readiness 与并发/回滚审计；完整后台发布服务仍待 M1 |
| `ADMIN-001` | `specified` | M1 后台只编辑白名单对象，并实施角色分权和自批禁止 | 12.1-12.4 | 08 第 1-3 节、12 | M1 | 权限矩阵、审计、发布 E2E |
| `CLIENT-001` | `blocked` | PC 与移动 H5 在固定浏览器、视口、中文输入和无障碍矩阵通过 | 9.2.1、9.3-9.5 | 15 | RELEASE-001 | Issue #9 已通过 Slice 1 的桌面、现代移动竖屏和超长比例横屏自动 E2E；`tested_versions`、完整视觉/输入/无障碍发布矩阵仍未执行 |
| `NFR-001` | `blocked` | 默认 capacity profile 的负载、延迟和稳定运行目标全部达标 | 13.4-13.7 | 16 第 3/7 节 | RELEASE-001 | `capacity-profile.json` 的 M0 目标已批准；容量报告与两小时 soak 尚未执行 |
| `NFR-002` | `blocked` | 备份保留、RPO、RTO 和隔离恢复演练全部达标 | 13.2、14.4、13.7 | 16 第 5-6 节 | RELEASE-001 | `recovery-budget.json` 已批准并绑定 M0 基础设施恢复报告；保留/WAL 与五个业务范围的发布级演练尚未完成 |
| `MILESTONE-001` | `verified` | 产品里程碑 M0 已 `complete`：制品、合同、发布契约、非功能 profile 批准与 clean-baseline checklist 已完成 | V6 15.0-15.1 | 10 E0、16 | M0 | V6 基线 `d14ce67`、Issue #5 分层证据、M0 自动检查与 0 个 profile blocker |
| `MILESTONE-002` | `specified` | M1-A 仅为内部可玩验证，M1-B 才等同 M1 完成 | 15.0、15.2 | 10 E1-E9、16 第 10 节 | M1 | 两阶段门禁与发布候选报告 |
| `MILESTONE-003` | `specified` | M2：后台与内容深化，完成白名单内容后台、运营工具和相应验收证据 | 15.3 | 08、12、16 | M2 | 后台权限矩阵、审计、发布/回滚与验收报告 |
| `MILESTONE-004` | `specified` | M3：原版玩法补齐，按兼容包络扩展玩法、经济、任务与社交能力 | 15.4 | 06、07、14、16 | M3 | 兼容包络、golden cases、玩法与恢复测试 |
| `MILESTONE-005` | `specified` | M4：XKX100 导入与适配闭环，完成受控源快照、转换和黄金差分 | 15.5 | 09、14、16 | M4 | source snapshot、双 manifest、bundle、差分报告 |
| `MILESTONE-006` | `specified` | M5：内容与玩法扩展，完成后续可选内容的受控扩展 | 15.6 | 06、07、09、12、14、16 | M5 | 扩展内容制品、发布批次、回滚和验收证据 |
| `MILESTONE-007` | `specified` | M6：微信小程序交付，完成微信 AuthIdentity、授权登录与客户端适配 | 15.7 | 03、08、15、16 | M6 | 小程序 E2E、AuthIdentity、兼容矩阵与发布证据 |
| `CONVERT-001` | `implemented` | 转换和黄金验收绑定不可变 source snapshot、双 manifest 与 bundle | 7.2-7.16 | 09、16 第 8 节 | M0、M4 | `contracts/v1/artifacts/`、`generate_source_contracts.py` 与哈希篡改测试；M4 差分制品仍待实现 |
| `ENGINE-001` | `verified` | Engine Stage E0 readiness：真实 seed loading、Registry exact dependencies、并发、审计和 readiness 集成可执行 | V6 15.0、17 | 06、10、12、16 | Engine Stage E0 | Issues #1–#4 实现提交；Issue #5 的 PostgreSQL、服务集成、启动 E2E、全量与静态门禁全部通过 |
| `AUTH-004` | `retired` | 已退役的复合要求：RecoveryCode 恢复与 PresenceRecovery 曾被放在同一追踪项 | 历史 V6 8.2-8.5、11.13 | ADR-0004（被 ADR-0005 取代） | — | Issue #9 保留 RecoveryCode 哈希/轮换、User 全会话撤销与合并限流的历史证据；ID 不复用 |
| `IDENTITY-001` | `verified` | 每个实例一个 User 永久映射一个 GameAccount | V6 8.2 | 03、08、ADR-0002 | M1 | Issue #9：数据库唯一约束、迁移与并发证据 |
| `AUTH-005` | `implemented` | 新注册验证唯一邮箱且零认证状态；邮箱密码重置即时撤销全部旧认证；RecoveryCode 退役 | V6 8.1-8.7、11.2、15.1-15.2 | 08 第 2.2/4.2/4.4 节、13 第 1/10.1 节、15、16 第 2.1 节、ADR-0005 至 0008 | M1、RELEASE-001 | Issue #10 规格、Issue #11 权威同步、Issue #12 challenge/crypto/limiter/outbox/worker、Issue #13 最终注册/H5、Issue #14 邮箱密码重置/即时认证撤销/安全通知/H5、Issue #15 RecoveryCode 退役/受控切换/生产预检与回滚证据；分层总证据仍待 #16 |
| `AUTH-006` | `specified` | 同一 AuthSession 可恢复自己的 active/grace PresenceSnapshot；跨 AuthSession 必须显式 takeover | V6 8.6 | 11、13 第 6.4/8 节、15 | M1、RELEASE-001 | Character Slice 2 的 PresenceRecovery 与后续 takeover E2E；不得由 AUTH-005 提前实现 |
| `CHARACTER-001` | `specified` | CharacterCreationProfile、CharacterDisplayName 与 RetiredCharacter 生命周期可审计且不自助重建 | V6 8.8 | 08 第 4.3 节、12 第 5.15 节、15 | M1、RELEASE-001 | profile hash/exact revision、NFKC/策略测试、GM 审计、关闭恢复 E2E |
| `WORLD-002` | `specified` | Public V1 完整 Village topology 与逐项交互包络可声明，未验证交互显式不可用 | V6 7.2.1、7.3、11.7 | 04、09、12 | RELEASE-001 | topology / interaction envelope、UnavailableInteraction 报告 |
| `PVP-001` | `specified` | Public V1 只允许非致命 Sparring，玩家失败采用 SafeDefeat | V6 10.4.2、11.11 | 14 | RELEASE-001 | 互认 / 致命拒绝 / SafeDefeat E2E |
| `COMBAT-002` | `specified` | GoldenSkillChain 与日常 Character 状态隔离，首条候选链有冻结来源证据 | V6 7.16、10.3.3 | 14、09、16 | M1、M4 | golden case、source diff、envelope |
| `COMMUNITY-001` | `specified` | Public V1 提供 PlayerBlock、ChannelMute、ModerationCase、申诉与分层保留 | V6 11.10 | 06、08、16 | RELEASE-001 | moderation E2E、审计与 retention 检查 |
| `RELEASE-001` | `blocked` | 独立 PublicV1Gate 允许一个官方实例公开运营 | V6 1.6、11.6-11.11 | 10、16、19 | — | 7-day trial、5 testers、20 loops、ReleaseManifest、五范围恢复、公开资料 |

## 3. 变更规则

- 改变产品结果时，先修改 V6，再同步本索引和对应实施合同；V5 只保留历史。
- 只改变实施机制时，修改对应冻结合同和本索引；产品结果不变时不向 V6 复制字段。
- 一个需求拆成多个独立结果时保留原 ID 作为父项，并为新结果分配新 ID。
- 任一必做需求处于 `blocked` 时，引用它的里程碑不得为 `complete`。
- 例外只适用于纯展示差异或非必做项；必做能力只有 `verified` 才能通过，例外记录不得改变其状态。
- 发布证据必须记录需求 ID、代码版本、测试环境、执行时间和结果摘要。
- V6 的新 ID 代表独立可验证的产品结果，不以文件、端点或内部类数量创建 ID。`RELEASE-001` 不属于 M0-M6，任何公开部署证据必须同时引用它和相关能力 ID。
