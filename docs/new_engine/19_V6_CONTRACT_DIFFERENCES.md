# V6 与冻结合同的差异记录

本文件是 `requirements_v6.md` 相对 `requirements_v5.md` 的实施同步清单。它不取代 11-16 任一合同；每项差异必须在对应合同的 V6 增量段、测试计划和追踪索引中有落点。V5 自 V6 生效起保持历史不变。

## 产品边界

| V6 结果 | 受影响合同 | 同步内容 |
| --- | --- | --- |
| M1-A / M1-B 是内部封闭步骤；PublicV1Gate `RELEASE-001` 独立于 M0-M6 | 10、16、17 | 路线图和发布门禁拆层；公开 gate 证据不计作 M1 完成 |
| 一个 owner-operated 官方单实例；注册 `open / paused / invite_only` | 08、16 | 实例运营模式、初始 superuser、状态与支持入口 |
| `ReleaseManifest` 绑定代码、V6、合同、迁移、批次、来源、包络和报告 | 16、06、12 | 部署和回滚必须协调 code / migration / content |

## 身份与会话

| V6 结果 | 受影响合同 | 同步内容 |
| --- | --- | --- |
| 每实例一个 User 永久映射一个 GameAccount | 03、08、13 | 身份不拆分；CharacterOwnership 只承接未来多角色 |
| `VerifiedContactMethod` 与 `VerificationChallenge` 取代 RecoveryCode | 08、13、15、16、17 | 新注册先验证 email；密码重置使用用途隔离的短期 challenge 并即时撤销全部旧认证；旧 recover/rotate 先统一 410，再于 Public V1 前删除；Issue #16 的验证状态与分层证据见 `20_AUTH_BASELINE_EVIDENCE.md` |
| 联系方式密文与 keyed lookup digest 分离 | 08、13、16、ADR-0006 | Django `User.email` 保持为空；完整目标应用层加密、精确查询独立摘要、密钥隔离与轮换 |
| 验证消息使用 PostgreSQL 持久 outbox | 08、13、16、ADR-0007 | HTTP 不同步发 SMTP；非枚举 202、幂等请求、同 code 重试、provider 接受后激活和 terminal payload 擦除 |
| Access Token 必须解析到 `active` AuthSession | 08、13、16、ADR-0008 | 密码重置提交后旧 access/refresh 跨实例立即失效，注册与重置均不自动登录 |
| ADR-0005 取代 ADR-0004 的 RecoveryCode 决策 | CONTEXT、ADR-0004 至 0008、17 | RecoveryCode 只保留历史 provenance；PresenceRecovery、账号重新启用与 takeover 继续是独立概念和后续切片 |
| `presence.recover` | 11、13、15、16 | 同 AuthSession 恢复自身 active/grace PresenceSnapshot 租约并创建新一代运行时 Presence，递增 generation、旋转 ticket；跨会话仍需 takeover |
| CharacterCreationProfile / CharacterDisplayName / RetiredCharacter | 04、08、12、15 | typed-registry profile definition、精确版本/hash、内容批次与起始 revision 固定、`GET /api/v1/character-creation-profiles`、`POST /api/v1/characters`、NFKC 名称规则、展示性别、幂等创建、GM 审计和不可自助重建 |

## 世界、战斗与物品

| V6 结果 | 受影响合同 | 同步内容 |
| --- | --- | --- |
| `VillageTopologyEnvelope` / `VillageInteractionEnvelope` | 04、09、12、16 | 完整 `d/village` topology 与逐能力行为证据分离；未验证行为返回 `UnavailableInteraction` |
| 日常 Character 与 GoldenSkillChain Actor 分离 | 09、14、16 | 首条候选 `bahuang-gong` / `baihua-cuoquan` 链必须绑定冻结 golden case；`benlei-shou` 后置 |
| Public V1 仅 Sparring，玩家 SafeDefeat | 14、11 | 致命 / involuntary Character combat 拒绝；玩家物品和不可逆进度不丢失 |
| 静态只物化一次、respawn 创建新 Entity、LootClaim、ItemRetirement | 04、12、14、16 | 不复活死亡 Entity；30 秒 claim、约 15 分钟 NPC loot retirement、玩家普通丢弃 60 分钟告警 |
| Public V1 经济和内容规模 | 06、12、14、16 | 约 30-60 Room、10+ NPC、20+ Item、一条 PvE 循环、2-4 小时；无支付 / 真实货币经济 |

## 社区与运维

| V6 结果 | 受影响合同 | 同步内容 |
| --- | --- | --- |
| PlayerBlock、ChannelMute、ModerationCase、申诉和保留期 | 06、08、16 | 玩家 `/api/v1/community/...` 与运营 `/admin/api/v1/moderation/...` 分层 API；不可变消息取证、处罚时间窗、一次申诉、30/180/365 天分层保留；系统 / 安全 / GM 通知不可屏蔽 |
| Public V1 试运行 | 10、16、17 | 7 天、5 名非管理员、20 次核心循环；S0/S1 阻断、受限 S2 记录 |
| 维护、恢复与公开资料 | 16、15 | 24 小时维护公告、drain / health check / incident、公开状态和恢复 / 举报 / 客服入口 |

## 认证修订同步状态

Issue #16 已完成 Auth Baseline Amendment 的分层验证、正式双轴复审及 GitHub 回填关闭，`AUTH-005=verified`；该过程没有改变本差异账本中的 V6 语义。`requirements_v6.md`、`CONTEXT.md`、ADR-0004 至 ADR-0008 和 08/13/15/16 的现行认证权威经复核无需修改；完整结果见 `20_AUTH_BASELINE_EVIDENCE.md`。Character Slice 2 成为下一 frontier，但尚未认领或实现，`RELEASE-001 / PublicV1Gate` 继续为 `blocked`。

## 不在本次实现授权内

Issue #11 只授权 V6、冻结合同、词汇、ADR、需求追踪、状态、计划、差异和交接同步，以及对应文档合同校验；Issues #12–#15 实现认证修订，Issue #16 只完成证据收口。没有任何一票授权公开部署或提前实现 SMS、联系方式换绑、账号关闭/重开、Character、Presence、PresenceRecovery 和 takeover。
