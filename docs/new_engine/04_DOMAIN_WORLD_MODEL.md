# 04 领域模型与世界模型

> 术语说明：本页的账号域、世界域、内容域名词，统一以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

> 实施约束：战斗、武学、物品、Condition 与 Effect 的首发模型边界，以 `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准。

## 1. 设计方向

Evennia 的强项是“所有东西都是 Object”，弱项是“所有东西最终都可能退化成一堆 Attribute”。New_Mud 要保留前者的统一性，避免后者的失控。

## 2. 推荐实体总览

### 2.1 账号域

- `User`
- `AuthIdentity`
- `GameAccount`
- `CharacterOwnership`

### 2.2 世界域（持久实体）

- `Entity`
- `Character`
- `Room`
- `Exit`
- `Item`
- `NPC`
- `StaticEntityBinding`
- `SpawnMaterialization`

`Presence` 不属于持久世界实体，而属于运行时控制上下文。概念分层见 `docs/new_engine/03_RUNTIME_SESSIONS.md`，实施状态与恢复边界以 `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md` 为准。

### 2.3 战斗、武学与物品域（PostgreSQL）

- `SkillDefinition`
- `SkillMoveDefinition`
- `ConditionDefinition`
- `ActorSkill`
- `JifaBinding`
- `PrepareBinding`
- `Item` 与物品实例状态
- `EquipmentBinding`
- 标记为 `durable` 的 `EffectInstance`
- 战斗结束后已提交的角色资源与结算结果

`SkillDefinition / SkillMoveDefinition / ConditionDefinition` 是对应 Blueprint kind 的领域语义，持久真源是 immutable Blueprint revisions，不建立平行定义主表。其字段合同以 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准。

`ActorSkill` 同时承载 Character 与 NPC 的已学武学状态，并固定 skill head 与 exact published revision。`JifaBinding / PrepareBinding` 只引用该持久记录，不按活动 Blueprint key 重新解释。

只有解析后 `persistence = durable` 的 `EffectInstance` 才建立主记录，并精确引用 condition revision 与 EffectType；完整恢复规则以 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 为准。

### 2.4 战斗运行时模型

- `CombatInstance`
- `CombatParticipantState`
- 当前攻击目标与行动上下文
- `CombatLoop`
- `RuntimeTimer`
- 战斗节拍与短期 `busy`
- 标记为 `runtime_only` 的 `EffectInstance`

这些状态只存在于单实例运行时，不建立通用持久化主记录。进程重启时安全结束未完成战斗，不恢复半完成攻击或短期 `busy`。

### 2.5 内容域

- `Blueprint`
- `BlueprintRevision`
- `HelpEntry`
- `Region`

### 2.6 系统域

- durable `ScheduledJob`
- durable `RecurringJob`
- `WorldProcess` 启动声明与显式领域 checkpoint
- `QuestState`
- `FactionMembership`
- `ChatChannel`
- `ChatSubscription`
- `ChatMessage`
- `DirectMessage`
- `SystemNotice`

## 3. Entity 统一根

推荐把 `Entity` 作为统一根表，保留 Evennia 统一实体模型的优点：

- 全部对象可被搜索、命名、打标签、做权限校验
- 可复用统一的移动、可见性、渲染、审计逻辑

但不建议把一切字段都放到 `Entity`。

### 3.1 `Entity` 核心字段

- `id`
- `instance_id`
- `kind`
- `key`
- `display_name`
- `blueprint_revision_id`
- `location_entity_id`
- `lifecycle_state`（`active / retired`）
- `state_json`
- `flags_json`
- `created_at`
- `updated_at`

玩家与 `Character` 的拥有关系统一放在 `CharacterOwnership`，不要把 `owner_game_account_id` 作为 `Entity` 通用字段重新塞回根表。其他作者、归属或运营关系，也应按具体子域显式建模。

`blueprint_revision_id` 引用创建实例时使用的 exact published `BlueprintRevision`。实例默认不随活动发布漂移；后续定义变化只影响新实例，或通过受审计的显式 apply/migration job 更新现有实例。

实例行为只消费该 pinned revision 的 immutable `CompiledBlueprint` 与 exact resolved dependencies。活动批次变化不会让既有实例按 key 重新解析依赖；迁移到新 revision 前必须先验证实例状态兼容。

`retired` Entity 是不可复活的 tombstone。只要 `SpawnMaterialization` 仍引用它就不得物理删除；死亡、掉落或退出世界不能级联删除初始刷点的幂等身份。

`instance_id` 必填，所有 Entity 关系、binding 与 materialization 都必须留在同一实例。`INDEX (instance_id, kind)` 是首发必需索引；跨实例 location、装备、技能或 spawn 关系一律拒绝。

`location_entity_id` 是唯一权威字段。active Entity 的合法矩阵为：

| Entity kind | 合法 location | 约束 |
|-------------|---------------|------|
| Room | `null` | static root |
| Exit | Room | 必须等于 pinned Exit exact source Room binding |
| Character/NPC | Room | 同实例且目标为 active |
| Item | Room/Character/NPC/Item | 同实例且目标为 active；Item 目标必须由 exact `container_policy` 允许 |

`retired` Entity 的 location 必须为 `null`。Presence 可以缓存场景订阅信息，但不再另存 canonical room id。

Item 指向 Item 时禁止 self/ancestor containment cycle。移动服务必须按 Entity id 稳定顺序锁定 item、目标容器及目标 ancestor chain，再校验容量和 state versions；deferred trigger 用递归查询复核无环与同实例约束。

### 3.2 专属子模型

- `Room`
  - `region_id`
  - `x, y, z`（可选扩展字段）
  - `terrain`
  - 必填 `spawn_entries` 数组，空值为 `[]`
  - `external_exit_boundaries` 必填，空值为 `[]`；只追踪不可通行的转换边界
- `kind=exit` Blueprint / Compiled definition
  - exact `source_room_ref / target_room_ref`
  - `direction / aliases`
  - 可选 `traversal_rule_key`
- `Exit` instance
  - source Room 复用 `Entity.location_entity_id`
  - `target_room_id`
  - `direction`
  - `aliases`
- `kind=item` Blueprint / Compiled definition
  - 具体字段以 `14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准
  - 包含 `item_type / stackable / max_stack / equip_slot / use_action_key`
  - 可选 `condition_definition_keys`
  - 必填且可追溯的 `source_ref`
- `Item` instance
  - exact `blueprint_revision_id`
  - `quantity`（active 时为 `1..max_stack`，耗尽并 retired 时为 `0`）
  - 位置或容器复用 `Entity.location_entity_id`
  - `state_version`
- `kind=npc` Blueprint / Compiled definition
  - 复用 Blueprint 顶层 `behavior_profile_keys / spawn_policy`
  - `data.skill_loadout / data.item_loadout` 必填，空值为 `[]`
- `Character`
  - 成长、属性、门派、声望等
  - 持久化单调 `character_version`，覆盖完整角色摘要
  - 持久化单调 `inventory_version`，作为背包与装备动作的窄化并发版本

两个 Character 聚合版本的递增和 snapshot 一致性语义以 `11_PROTOCOL_CATALOG.md` 为准。进程重启不得重置或重新推导版本。

`StaticEntityBinding` 保存 `instance_id / blueprint_head_id / blueprint_revision_id / entity_id / state_version`，并在 instance/head 与 entity 两侧唯一。它只服务首发 static Room/Exit。

`SpawnMaterialization` 保存 Room、spawn entry、ordinal、exact target revision 与 spawned Entity 的初始事实。Room/entry/ordinal 和 spawned Entity 两侧都唯一；记录创建后不可修改。

生成目标离开世界时保留 `retired` Entity tombstone 与 materialization，禁止级联删除。完整 INSERT consistency trigger 与删除约束以 12 号合同 7.6 节为准。

`spawn_entries / external_exit_boundaries / skill_loadout / item_loadout` 与 Exit 的唯一字段 schema 以 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 7.6 节为准。

ref 可保留 key 与 expected kind 供审计，但运行时身份只认 exact target revision。不得按裸 key 重解释 Room、Exit、NPC、Skill 或 Item。

Exit instance 的 source、target、direction 与 aliases 都是 pinned `kind=exit` compiled definition 的受约束投影，不是可独立编辑字段；traversal rule 只从 exact registry dependency 读取。

world init 先用 `StaticEntityBinding` 幂等创建 Room，再创建依赖 exact Room revisions 的 Exit，最后按 pinned Room spawn entries 创建 `SpawnMaterialization` 与目标 Entity。

spawn NPC 时，同一事务按 pinned NPC revision 创建 `ActorSkill / JifaBinding / PrepareBinding`、Item Entity 与必要的 `EquipmentBinding`。

定义中的 `condition_definition_keys` 每一项都是 `expected_kind=condition` 的 `BlueprintRef`。发布后的 Item `CompiledBlueprint` 保存每项 exact published target revision。

既有 Item 施加状态时只使用 pinned Item revision 的 resolved dependency，创建的 EffectInstance 保存该 `condition_definition_revision_id`。只有新 Item spawn 才从请求固定的活动批次选择 Item revision。

不产生状态挂载的物品定义效果统一通过 `use_action_key` 进入 `ActionDefinition` 及其受控 rule/handler。Item instance 不复制这些定义字段，也不得声明叠加、tick、持久化和恢复策略。穿戴状态只由 `EquipmentBinding` 表达，不在 Item instance 上另建装备真源。

## 4. 核心原则：显式字段优先

以下数据必须显式建模，不能默认放进通用属性表：

- 角色属性、等级、经验、境界
- 气血、内力、精力
- 房间坐标与区域
- 装备槽位
- 武学定义、招式定义与 Condition 定义
- Actor 已学武学、`jifa` 与 `prepare` 绑定
- 背包数量、容器归属与装备绑定
- 货币余额
- 聊天频道成员关系
- 任务状态
- 世界事件定义与活动排程
- 帮派成员关系

只有这些内容才适合放扩展字段：

- 罕见内容标记
- 临时剧情变量
- 转换器导入过程中尚未结构化的残余数据
- MUDLib 自定义的小块配置

## 4.1 坐标与拓扑策略

`requirements_v5.md` 当前没有把三维坐标、区域动态加载或通用自动寻路冻结为首发正式约束；V5 对地图与移动的基线仍是 XKX100 的房间制世界与 `Room/Exit` 拓扑。

因此当前设计约束调整为：

- `Exit` 拓扑是房间连通性的唯一权威来源
- `Room` 可以保留显式坐标字段作为扩展能力，但首发不要求所有房间都具备 `x/y/z`
- 当源数据提供可靠坐标，或后续工具/地图需要坐标时，可将其作为显式字段导入
- 坐标缺失不能阻断房间加载、移动、展示与首发玩法
- 转换器若发现坐标缺失但又存在地图/寻路依赖，应输出 `manual_review` 或等价报告，而不是把坐标伪造为权威事实

## 5. 房间与移动

建议直接借鉴 Evennia `move_to()` 的 hook 顺序，但改成明确的领域服务：

```text
can_leave(source, actor, move)
can_enter(target, actor, move)
before_leave(source, actor, move)
before_enter(target, actor, move)
perform_move(actor, target)
after_leave(source, actor, move)
after_enter(target, actor, move)
after_move(actor, source, target)
```

这样可以稳定承载：

- 门锁与轻功限制
- 战斗中脱离
- 水域、高地、密林地形修正
- 暗门与特殊出口

## 6. 房间展示

建议保留 Evennia `return_appearance()` 的“模板 + 分块”思想，但输出两层结果：

### 6.1 文本层

用于传统 `look` 命令与日志回放：

- 房间名
- 描述
- 出口
- 在场角色
- 在场物品

### 6.2 结构化层

用于 uni-app：

```json
{
  "title": "襄阳城东门",
  "desc": "...",
  "exits": [],
  "characters": [],
  "things": []
}
```

## 7. 区域活跃度与运行时装载

`requirements_v5.md` 当前没有把“活跃区 / 预加载区 / 休眠区”冻结为首发前置。首发默认以单实例、单写者、显式房间拓扑和按需查询为主，不预先引入 `active / preloaded / hibernated` 三态装载模型。

后续若因为世界规模、后台工具或性能热点需要引入区域活跃度管理，可再单独设计 `RegionRuntimeService`，明确：

- 状态枚举
- 失活与回收条件
- 缓存与订阅边界
- 与战斗、刷新、世界事件的联动规则

## 8. 路径搜索

`requirements_v5.md` 当前把 `PathfindingService` 视为可扩展公共服务，但没有把通用自动寻路冻结为首发基线。因此当前设计只保留接口挂点，不冻结 A*、三维曼哈顿、体力成本模型等具体实现。

当前约束应为：

- 首发不要求提供面向玩家的通用自动寻路
- 若后续为运营工具、测试工具或地图功能提供路径搜索，应优先基于 `Room/Exit` 拓扑保证正确性
- 只有在坐标数据稳定可靠时，才额外引入启发式算法优化
- 寻路策略、成本函数与 UI 暴露方式应在后续专项设计中单独冻结

## 9. Character 与 Presence 分离

New_Mud 必须显式区分：

- `Character`
  - 永久实体
  - 其世界位置以 `Entity.location_entity_id` 为准
- `Presence`
  - 在线控制上下文、场景订阅、当前战斗、临时状态
  - 默认由运行时服务持有
  - 如需持久化，只落重连恢复或审计所需的快照记录

## 10. 建模底线

如果某个状态满足下面三条，就不要放通用属性：

1. 需要经常查询
2. 需要做索引或约束
3. 影响核心玩法逻辑

这条底线用来避免重新走上 Evennia `Attribute` 大一统的老路。


