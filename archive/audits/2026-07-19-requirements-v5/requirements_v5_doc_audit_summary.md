# requirements_v5 文档审查摘要

## 1. 最终结论

两轮全量审查已经覆盖 46 份项目自有 Markdown 文档。审查中发现的结构、引用、术语和跨合同问题已经修正，修改后的最终快照再次通过全量结构、引用与语义复审。

当前文档集可以作为 New_Mud 的现行需求与设计基线。这个结论只表示文档内部收口，不表示代码已经实现、测试已经通过或 XKX100 内容已经获得授权。

## 2. 范围与权威

审查范围包括：

- 5 份需求版本与 1 份现行术语表。
- 3 份审计记录。
- `docs/00-18` 的 19 份 Evennia 分析文档。
- 1 份 `docs/19_documentation_governance.md`。
- `docs/new_engine/00-10` 的 11 份概念设计文档。
- `docs/new_engine/11-16` 的 6 份冻结实施合同。

V1-V4 只保留历史追溯价值。实施权威顺序为 V5、冻结合同 11-16、概念设计 00-10、分析文档 00-18、当前实现。

`UBIQUITOUS_LANGUAGE.md` 是与 V5 配套的术语权威；它统一命名，但不作为覆盖冻结合同的独立实施层。

## 3. 主要修复

### 3.1 需求与范围

- 消除了历史需求与产品版本 V1 的歧义。
- 收紧了首发认证、角色数量、组织玩法、Item 字段和小程序交付边界。
- 区分了需求里程碑 `M0-M6` 与 `Engine Stage Ex`。
- 新增并同步合同 14-16，补齐战斗物品、H5 前端与运维测试合同。

### 3.2 认证、会话与前端

- AuthSession 只能由 login 创建，refresh 不得创建、恢复或复活会话。
- 每个 AuthSession 终身只有一个不可替换 RefreshTokenFamily。
- Refresh Token 只可用于 refresh 轮换或 logout 的受保护 Cookie locator。
- logout 使用 Refresh Cookie 与 access Bearer 双定位，并幂等收敛 Presence 与 ticket。
- 普通 enter 不会隐式 takeover；显式 takeover 具有原子提交和旧端失权语义。
- H5 不持久化 access token、resume ticket、完整终结或 WebSocket request id。

### 3.3 领域、调度与存储

- ItemDefinition、Item instance 与 EquipmentBinding 已分离，穿戴状态只有一个真源。
- 装备槽与 pinned Item revision 强一致，可装备 Item 不允许堆叠。
- `ActorSkill` 固定 Character/NPC 已学武学的 exact head/revision，激发和准备绑定不再按 key 漂移。
- ConditionDefinition、EffectTypeDefinition 与 EffectInstance 已分离。
- Effect 创建区分 active-batch 直接解析与 pinned-source exact dependency。
- Job、Effect operation、幂等、恢复、锁租约和 PostgreSQL 约束已闭合。
- 帮派频道不再被误列为首发聊天闭环。

### 3.4 Blueprint 与发布

- 发布使用 parent、BlueprintRef 与 RegistryRef 的反向依赖传递闭包。
- 依赖变化会产生 `dependency_recompile` published revision。
- `ResolvedBlueprintDependency` 保存 exact target revision；`ResolvedRegistryDependency` 保存 exact kind/key/version/definition hash。
- `CompiledBlueprint` 同时保存两类依赖，兼容目录保留 pinned revision 所需的 transitive registry artifacts。
- pinned 实例只读取自身不可变编译产物和 exact dependencies，不被新 active batch 混写。
- `compiler_contract_version` 精确标识 compiler 实现与全部 kind schema；任一变化必须升版。
- 旧 revision 只有在 raw `content_hash`、精确 `compiler_contract_version` 与两类规范化 dependency 数组均与最终候选上下文完全相同时才可复用。
- `content_hash`、`compiled_hash`、`resolved_dependency_hash` 与 `release_hash` 的覆盖范围已经冻结。
- 发布预检展示派生重编译项，事务锁定并只更新 affected heads。

### 3.5 Fixture、测试与运营

- 世界和武学使用两个独立 manifest，并由复合 bundle 同时引用。
- 源快照与 manifest schema、五文件白名单、外部边界、计数、哈希算法和可复现环境要求已经冻结。
- 实际 source snapshot、两个 manifest、复合 bundle、逐文件哈希和 golden 制品仍待 M0 生成与批准。
- 黄金初始态使用 exact Item revision 和独立 EquipmentBinding。
- RPO/RTO 必须是发布前批准目标，并由恢复演练实测验证。
- 公开部署或分发 XKX100 派生内容前必须通过授权门禁。

## 4. 第二轮验证

最终快照包含 46 份范围内文档。以下问题计数均为 0：

- H1 数量错误与标题级别跳跃。
- 围栏不平衡与 JSON 围栏解析失败。
- Markdown 表格列数错误。
- 尾随空白与超过 240 字符的行。
- UTF-8 读取失败。
- 无法解析的本地 Markdown 或显式 `.md` 引用。

陈旧模式复扫也未再发现版本权威、认证、Presence、Blueprint 复用、active-batch 绝对化、Item/EquipmentBinding 或双 fixture 边界冲突。

## 5. 可依赖范围

- 现行需求：`requirements_v5.md`。
- 现行跨文档术语：`UBIQUITOUS_LANGUAGE.md`。
- 冻结实施合同：`docs/new_engine/11-16`。
- 概念设计：`docs/new_engine/00-10`，不得覆盖 V5 或冻结合同。
- Evennia 6.0 来源分析：`docs/00-18`，引用关键事实时仍应回查本地上游快照。
- 文档分层与变更规则：`docs/19_documentation_governance.md`。
- 历史追溯：`archive/requirements/requirements_v1.md` 至 `archive/requirements/requirements_v4.md`，不得作为现行需求。

## 6. 未消除风险

- 尚无实现和自动化测试证明文档合同已经落地。
- XKX100 内容授权仍未解决。
- 仓库中尚无实际 `source_snapshot.json`、世界/武学 manifest、复合 bundle、逐文件哈希或 golden 制品。
- `xkx100-skill-combat-v1` 的真实依赖闭包与哈希尚未冻结。
- 在真实闭包冻结前，战斗与武学黄金对齐必须保持 `manual_review` 或 `blocked`。
- 合成 fixture 只能验证引擎机制，不能证明 XKX100 行为对齐。

## 7. 判断

文档层面已经完成收口，可以进入按合同实现与测试的阶段。进入公开发布或宣称 XKX100 行为对齐之前，仍必须分别完成实现验证、真实依赖闭包冻结和内容授权。
