# requirements_v5 文档审查进度记录

> 历史声明：本文记录 2026-07-19 的 V5 审查进度；当前产品需求权威为 `requirements_v6.md`。

## 当前状态

- 审查日期：2026-07-19。
- 状态：两轮全量文档审查已完成。
- 范围：46 份项目自有 Markdown 文档。
- 结果：已修正文档内发现的问题，并在最终快照上重新执行结构、引用和语义复扫。
- 边界：这是文档合同收口，不是实现验收或内容授权结论。

当前目录不是 Git 仓库，因此无法提供 `git diff` 或 `git status`。审查结果以文件内容、确定性清单和复验命令为准。

## 范围统计

| 类别 | 数量 | 状态 |
|------|------|------|
| 根需求与术语 | 6 | 已复审 |
| 审计记录 | 3 | 已重写并复审 |
| `docs/00-18` 分析层 | 19 | 已交叉复审 |
| `docs/19_documentation_governance.md` | 1 | 已交叉复审 |
| `docs/new_engine/00-10` 概念设计 | 11 | 已交叉复审 |
| `docs/new_engine/11-16` 冻结合同 | 6 | 已交叉复审 |
| 合计 | 46 | 已完成 |

## 已完成阶段

### 1. 版本与权威基线

- V1-V4 已明确为历史需求，V5 是唯一现行需求。
- 产品版本 V1 与历史文件名已经消歧。
- 根术语表已恢复为现行规范，不再保留临时审查标记。
- 分析层、设计层与需求层的权威方向已经统一。

### 2. 首发范围与阶段

- 首发认证收口为账号密码、JWT Access Token 和轮换 Refresh Token。
- AuthIdentity、手机号、微信身份绑定与实际小程序客户端归入后续阶段。
- 首发每个 GameAccount 最多一个 Character，并保留 CharacterOwnership 扩展点。
- Blueprint 最小发布闭环前移到 Engine Stage E0。
- Character、Room 与 snapshot 最小依赖前移到 E1。
- 路线图不再把 `Engine Stage Ex` 与需求里程碑 `M0-M6` 按数字等同。

### 3. 认证与 Presence 合同

- AuthSession 只由 login 创建；refresh 只轮换 active 会话的 credential。
- 每个 AuthSession 终身固定一个 RefreshTokenFamily，终态不得复活或换绑。
- Refresh Token 只有 refresh 轮换和 logout Cookie locator 两种合法用途。
- logout 同时处理 Refresh Cookie 与内存 access Bearer 能识别的会话集合。
- 普通 enter 不隐式 takeover；显式 takeover 原子替换租约、ticket 和终结记录。
- H5 不持久化 access token、resume ticket、完整终结或 WebSocket request id。

### 4. 领域与持久化合同

- ItemDefinition、Item instance 与 EquipmentBinding 已分离。
- 装备槽必须匹配 pinned Item revision；可装备 Item 不允许堆叠。
- Character/NPC 的已学武学由 `ActorSkill` 固定 exact head/revision，激发和准备绑定引用该记录。
- ConditionDefinition、EffectTypeDefinition 与 EffectInstance 已分离。
- Effect 创建区分 active-batch 直接选择与 pinned-source exact dependency 两条路径。
- Job、Effect operation、幂等、恢复、锁租约和 PostgreSQL 约束已经闭合。
- 帮派频道已移出首发闭环。

### 5. Blueprint 发布合同

- 发布会计算 parent、BlueprintRef 与 RegistryRef 的反向依赖传递闭包。
- raw 未变但依赖变化的引用方创建 `dependency_recompile` revision。
- `ResolvedBlueprintDependency` 持久化 exact target revision。
- `ResolvedRegistryDependency` 持久化 exact kind/key/version/definition hash，并由兼容目录保留 transitive artifacts。
- `CompiledBlueprint` 保存 exact lineage、两类 resolved dependencies、compiler contract 与依赖哈希。
- `compiler_contract_version` 精确标识 compiler 实现与全部 kind schema；任一变化必须升版。
- 旧 revision 只有在 raw `content_hash`、精确 contract version 与两类规范化 dependency 数组均与最终候选上下文完全相同时才可复用。
- `content_hash` 只覆盖 raw，`compiled_hash` 覆盖编译产物与 exact dependencies。
- `release_hash` 同时纳入 `content_hash` 与 `compiled_hash`。
- 发布预检展示派生重编译项，事务锁定并只更新全部 affected heads。
- pinned Entity/Item、durable Effect 和可回滚批次引用的历史 revision 必须保留。

### 6. 转换、测试与运营

- 世界 fixture 与武学 fixture 使用两个独立 manifest。
- 复合验收 bundle 只引用两个 manifest，不合并其文件清单。
- 源快照与 manifest schema、白名单、边界、计数、哈希算法、随机种子、时钟和时区要求已冻结。
- 实际 source snapshot、两个 manifest、复合 bundle 与逐文件哈希尚未生成，必须由 M0 产出并批准。
- 黄金初始态使用 exact Item revision，并以 EquipmentBinding 作为唯一穿戴真源。
- RPO/RTO 是发布前批准目标，必须由恢复演练实测验证。
- XKX100 授权和真实武学依赖闭包仍保留为外部门禁。

## 第二轮复审结果

最终快照检查结果：

| 检查项 | 结果 |
|--------|------|
| 文件数 | 46 |
| H1 数量错误 | 0 |
| 标题级别跳跃 | 0 |
| 围栏不平衡 | 0 |
| JSON 围栏解析失败 | 0 |
| 表格列数错误 | 0 |
| 尾随空白 | 0 |
| 超过 240 字符的行 | 0 |
| UTF-8 读取失败 | 0 |
| 无法解析的本地 Markdown 引用 | 0 |

语义复扫未再发现把 V1-V4 当作现行需求、AuthSession 由 refresh 创建、RefreshTokenFamily 可替换、logout 忽略 Cookie、active batch 覆盖 pinned revision、旧 Blueprint revision 无条件复用或 Item 自带装备真源等残留。

## 剩余风险

- 尚无实现和自动化测试证明合同已落地。
- XKX100 内容授权仍未解决。
- 仓库中尚无实际 `source_snapshot.json`、世界/武学 manifest、复合 bundle、逐文件哈希或 golden 制品。
- `xkx100-skill-combat-v1` 的真实依赖闭包和哈希尚未冻结。
- 在真实闭包冻结前，战斗与武学黄金对齐必须保持 `manual_review` 或 `blocked`。
- 合成 fixture 不能证明 XKX100 对齐。
