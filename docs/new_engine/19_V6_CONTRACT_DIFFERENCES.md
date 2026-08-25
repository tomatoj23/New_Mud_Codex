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
| 一次性可见、服务端只存哈希的 RecoveryCode | 08、13、15、16 | `/auth/recover`、`/auth/recovery-code/rotate`、`/account/close`、`/account/reopen`；恢复轮换 code，并撤销旧 AuthSession/refresh family/tickets、终止 PresenceSnapshot 租约、关闭运行时 Presence；统一错误和合并限流 |
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

## 不在本次实现授权内

本轮只授权文档、词汇、ADR、需求追踪和合同差异同步。没有授权功能代码、数据库迁移、客户端实现或公开部署；现有 E0 seed / resolver WIP 与其他工作树改动必须保留并另行评估。
