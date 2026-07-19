# requirements_v5 文档全量审查计划

## 1. 目标

以 `requirements_v5.md` 为现行需求基线，全面审查项目自有 Markdown 文档，修正结构、引用、术语、范围、接口与跨合同冲突，并在修改后执行第二轮全量复审。

本任务只验证文档合同的内部一致性和可实施性，不把尚未存在的代码或测试结果写成已经落地。

## 2. 审查范围

| 类别 | 数量 | 范围 |
|------|------|------|
| 根需求与术语 | 6 | 现为 `archive/requirements/requirements_v1.md` 至 `archive/requirements/requirements_v4.md`、根目录 `requirements_v5.md` 与 `UBIQUITOUS_LANGUAGE.md` |
| 审计记录 | 3 | 现为 `archive/audits/2026-07-19-requirements-v5/requirements_v5_doc_audit_*.md` |
| Evennia 分析层 | 19 | `docs/00-18` |
| 文档治理 | 1 | `docs/19_documentation_governance.md` |
| New_Mud 概念设计 | 11 | `docs/new_engine/00-10` |
| 冻结实施合同 | 6 | `docs/new_engine/11-16` |
| 合计 | 46 | 项目自有 Markdown 文档 |

`evennia-main/` 是上游源码快照，只作为事实核对依据，不属于项目文档修订范围。`.agents/` 是代理技能与工作流定义，也不属于产品文档范围。

## 3. 权威顺序

发生冲突时按以下顺序处理：

1. `requirements_v5.md`
2. 冻结实施合同 `docs/new_engine/11-16`
3. 概念设计 `docs/new_engine/00-10`
4. 分析文档 `docs/00-18`
5. 当前实现

`UBIQUITOUS_LANGUAGE.md` 是与 V5 配套的术语权威，不是覆盖冻结合同的独立实施层；发生术语冲突时仍以 V5 为准。

历史需求只能解释演进过程，不能覆盖 V5。`docs/19_documentation_governance.md` 记录并维护上述分层；分析层可以记录 Evennia 事实，但不能覆盖正式设计。

## 4. 工作包

### 4.1 清单、版本与治理

- [x] 建立 46 份文档的确定性清单。
- [x] 将 V1-V4 标记为历史版本，并明确 V5 是唯一现行需求。
- [x] 修复不存在、过时或歧义的本地 Markdown 引用。
- [x] 重建现行术语表并统一权威顺序。

### 4.2 范围与路线图

- [x] 收紧首发认证、角色数量、组织玩法、Item 字段和微信小程序阶段边界。
- [x] 区分需求里程碑 `M0-M6` 与开放式 `Engine Stage Ex`。
- [x] 将最小内容发布能力前移到 Engine Stage E0。
- [x] 将 Character、Room 与 snapshot 最小依赖前移到 E1。
- [x] 新增并同步合同 14-16，补齐战斗物品、前端 H5、运维测试边界。

### 4.3 认证、会话与 Presence

- [x] 固定 login、refresh、logout 三个首发 REST 认证端点。
- [x] 固定 AuthSession 只能由 login 创建，refresh 不得创建、恢复或复活会话。
- [x] 固定一个 AuthSession 终身只关联一个不可替换 RefreshTokenFamily。
- [x] 固定 logout 的 Refresh Cookie 与 access Bearer 双 locator 语义。
- [x] 固定普通 enter 拒绝占用，只有显式授权 takeover 才能替换 Presence。
- [x] 固定 H5 不持久化 access token、resume ticket 或完整请求终结。

### 4.4 领域、调度与内容

- [x] 区分 ItemDefinition、Item instance 与 EquipmentBinding。
- [x] 固定装备槽与 pinned Item revision 匹配，并禁止可装备 Item 堆叠。
- [x] 以 `ActorSkill` 固定 Character/NPC 已学武学的 exact head/revision。
- [x] 区分 ConditionDefinition、EffectTypeDefinition 与 EffectInstance。
- [x] 固定 durable job、effect operation、幂等、恢复和 PostgreSQL 约束。
- [x] 将帮派频道移出首发聊天闭环。
- [x] 固定新选择与 batch-scoped 读取使用 active batch，pinned 实例使用 exact historical revision。

### 4.5 Blueprint 与原子发布

- [x] 固定反向依赖传递闭包和 `dependency_recompile` revision。
- [x] 持久化 `ResolvedBlueprintDependency` 与 exact target revision id。
- [x] 持久化 `ResolvedRegistryDependency` 与 exact kind/key/version/definition hash。
- [x] 在 `CompiledBlueprint` 中冻结 exact lineage、依赖清单和 compiler contract。
- [x] 固定 `content_hash`、`compiled_hash`、`resolved_dependency_hash` 与 `release_hash` 的边界。
- [x] 仅在 raw `content_hash`、精确 `compiler_contract_version` 与两类规范化 dependency 数组均与最终候选上下文完全相同时复用旧 revision。
- [x] 发布预检展示派生重编译项，并锁定全部 affected heads。
- [x] 固定 historical revision 保留和 pinned instance 一致性读取规则。

### 4.6 转换、夹具与运营门禁

- [x] 固定世界与武学两个独立 manifest，以及引用二者的复合 bundle。
- [x] 固定源快照、逐文件哈希、聚合哈希、边界和定义计数。
- [x] 固定 RNG、时钟、时区、初始状态、黄金行为与差分测试输入。
- [x] 在黄金初始态中分离 Item instance 与 EquipmentBinding。
- [x] 将 RPO/RTO 定义为发布前批准目标，并要求恢复演练实测验证。
- [x] 保留 XKX100 授权门禁和未冻结真实依赖闭包的阻断状态。

## 5. 第二轮复审门禁

- [x] 每文件恰好一个 H1。
- [x] 不存在标题级别跳跃。
- [x] Markdown 代码围栏成对闭合。
- [x] 所有 `json` 围栏可解析。
- [x] Markdown 表格列数一致。
- [x] 不存在尾随空白。
- [x] 不存在超过 240 字符的行。
- [x] 所有本地 Markdown 与显式 `.md` 引用可解析。
- [x] 陈旧版本、认证、发布、Item、Effect、fixture 与 active-batch 绝对化模式复扫无残留。

## 6. 完成判定

文档审查在以下条件同时满足时完成：

- 46 份范围内文档均经过首轮审查和修改后复审。
- V5、术语表、设计合同和分析层的权威方向一致。
- 高风险跨合同流程具有单一且可执行的状态、存储和失败语义。
- 自动结构与引用检查全部通过。
- 剩余事项明确标记为实现验证或外部依赖，不伪装成文档已解决的问题。

## 7. 范围外风险

- 尚无实现和自动化测试证明这些合同已经落地。
- XKX100 内容授权仍需项目所有者完成法律或许可确认。
- 实际 `source_snapshot.json`、两个 manifest、复合 bundle、逐文件哈希与 golden 制品仍待 M0 生成和批准。
- `xkx100-skill-combat-v1` 的真实依赖闭包与哈希冻结前，相关黄金对齐必须保持 `manual_review` 或 `blocked`。
- 合成 fixture 只能验证引擎机制，不能证明 XKX100 行为对齐。
