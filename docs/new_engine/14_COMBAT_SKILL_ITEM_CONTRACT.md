# 14 战斗、武学与物品首发契约

> 状态：M1 内部实施契约。本文承接 `requirements_v6.md` 第十章与第十一章，冻结内部纵切中的战斗、`jifa / prepare`、背包、装备与物品使用边界。任何公式与行为基线都必须引用受控的 XKX100 兼容包络和黄金测试，不能凭近似实现补齐。

## 1. 首发目标

首发必须打通一条端到端链路：

1. 角色进入固定样板区域。
2. 学会至少一门样板武功，完成 `jifa`，并在适用时完成 `prepare`。
3. 与初始穿戴 `cloth.c` 物品实例的敌对 NPC 进入战斗。
4. 完成普通攻击及至少一个 `perform` 或 `exert` 判定，并持久化战斗与死亡掉落结算。
5. 战斗结束后查看战利品，再拾取 NPC 掉落的物品。
6. 装备或使用该物品。
7. 验证角色资源、物品归属、装备状态与结算结果均已持久化。

首发不引入独立技能冷却、公共冷却、技能轮盘或脱离 XKX100 的新战斗模式。

## 2. 权威数据与运行时对象

### 2.1 PostgreSQL 持久化真源

- `SkillDefinition`
- `SkillMoveDefinition`
- `ConditionDefinition`
- 标记为 `durable` 的 `EffectInstance`
- `ActorSkill`
- `JifaBinding`
- `PrepareBinding`
- `Item` 与物品实例状态
- `EquipmentBinding`
- 战斗结束后的角色资源与结算结果

### 2.2 单实例运行时状态

- `CombatInstance`
- `CombatParticipantState`
- 当前攻击目标与行动上下文
- 战斗节拍与短期 `busy`
- 标记为 `runtime_only` 的 `EffectInstance`

进程重启时，运行时战斗状态按安全策略结束。角色位置、物品和已提交结算从 PostgreSQL 重建，不恢复半完成攻击。

## 3. 武学模型

### 3.1 `SkillDefinition`

`SkillDefinition` 是 `kind=skill` Blueprint 的领域语义名，不建立独立定义主表。顶层 `blueprint_key` 是稳定 skill key；`data` 最小字段为：

- `display_name`
- `skill_type`
- `valid_enable_slots`（必填 string[]）
- `valid_enable_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `valid_combine_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `learn_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `practice_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `action_provider_keys`（可选 RegistryRef[] -> `ActionProviderDefinition`）
- `move_refs`（可选 BlueprintRef[]，每项 `expected_kind=skill_move`）
- `source_ref`
- `reference_snapshot_id`

`valid_enable_slots` 是静态允许集合。存在 `valid_enable_rule_key` 时，槽位还必须通过该 exact RuleDefinition；不存在时静态集合就是最终判断。双准备只有存在且通过 `valid_combine_rule_key` 时才允许。

`valid_combine_rule_key` 是有向规则。最终 `PrepareBinding.combine_order=1` 的 Skill 是 primary，order 2 是 combo；服务只调用 primary revision 解析出的 exact rule，并把 primary/combo 的 exact revisions 与 actor state 按固定字段传入。

一次请求指定两门技能时保留输入顺序。已有单准备再增量加入一门时，新技能成为 order 1 primary，原技能移动到 order 2；文本入口与结构化入口必须调用同一 Action 服务并持久化相同顺序。

所有 RegistryRef 在发布时固化 kind/key/version/definition hash；`move_refs` 固化 exact SkillMove revision。pinned Skill 不按裸 key 或 move key 漂移。

### 3.2 `SkillMoveDefinition`

`SkillMoveDefinition` 是 `kind=skill_move` Blueprint 的领域语义名，不建立独立定义主表。其 `data` 最小字段为：

- `display_name`
- `move_type`（`perform / exert / passive`）
- `invoke_action_key`（RegistryRef -> `ActionDefinition`）
- `availability_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `cost_rule_key`（可选 RegistryRef -> `RuleDefinition`）
- `resolution_rule_key`（RegistryRef -> `RuleDefinition`）
- `condition_refs`（可选 BlueprintRef[]，每项 `expected_kind=condition`）
- `parameters`
- `source_ref`
- `reference_snapshot_id`

`move_type` 决定该 move 属于 perform、exert 还是被动路径，不再维护目标类型不明的 `perform_keys / exert_keys`。`invoke_action_key` 必须与 move type 允许的 ActionDefinition source scope 相容。

### 3.3 Actor 武学状态

`ActorSkill` 同时记录 Character 与 NPC 的已学技能。最小字段为：

- `id`
- `actor_entity_id`
- `skill_head_id`
- `skill_blueprint_revision_id`
- `level`
- `state_version`

数据库必须保证 `UNIQUE (actor_entity_id, skill_head_id)`。

deferred trigger 必须校验 actor 是同实例内 `kind=character` 或 `kind=npc` 的 Entity，skill revision 是属于 `skill_head_id` 的 exact published `kind=skill` revision。

`JifaBinding` 的最小字段为 `actor_entity_id / enable_slot / actor_skill_id / state_version`，并保证 `UNIQUE (actor_entity_id, enable_slot)`。

`PrepareBinding` 的最小字段为 `actor_entity_id / enable_slot / combine_order / actor_skill_id / state_version`。`combine_order` 只允许 1 或 2；actor 内 `enable_slot`、combine order 与 skill 分别唯一。

两类 binding 的 deferred trigger 都必须保证 `actor_skill_id` 属于同一 actor。`JifaBinding` 必须按该 `ActorSkill.skill_blueprint_revision_id` 的 immutable `CompiledBlueprint` 校验用途槽位。

`PrepareBinding` 还必须证明同 actor 存在 `enable_slot + actor_skill_id` 完全相同的 `JifaBinding`，并且该 exact Skill revision 允许以该用途槽准备。只给数字顺序或 skill key 都不足以恢复准备状态。

同一 actor 的 combine order 集合只允许 `[] / {1} / {1,2}`。取消 primary 而保留 combo 时，Action 服务必须在同一事务把剩余 binding 压缩为 order 1；不得留下孤立的 order 2。

学习、升级和迁移必须显式写入 exact revision。切换 skill revision 必须锁定 `ActorSkill` 及相关 binding，校验等级和状态兼容并留下审计记录；不得按 skill key 随 active batch 漂移。

NPC 初始武学只来自 pinned NPC `CompiledBlueprint.skill_loadout`。其 schema 与组合约束以 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 7.6 节为准。

spawn 事务使用 loadout 的 exact resolved Skill dependencies 创建 `ActorSkill / JifaBinding / PrepareBinding`。任一引用、等级、槽位或组合校验失败时必须整体回滚。

首发规则：

- `jifa` 先检查 `valid_enable_slots`，再在存在时执行 exact `valid_enable_rule_key`。
- 徒手技能只有在需要时进入 `prepare`。
- 同时最多准备两门徒手技能。
- 双准备必须按 combine order 1 primary -> 2 combo 的方向存在并通过 exact `valid_combine_rule_key`。
- `perform / exert` 必须读取当前武器、`jifa`、`prepare`、资源和状态。
- 客户端不能直接修改任何绑定，只能请求服务端动作。

## 4. 战斗模型

### 4.1 `CombatInstance`

`CombatInstance` 是运行时聚合，至少包含：

- `combat_id`
- 参战 `ActorRef`
- 敌对关系与目标
- 当前节拍
- 运行时效果引用
- 已提交结算版本
- 固定的 `reference_snapshot_id`

同一角色同时最多属于一个活跃 `CombatInstance`。进入、退出、切换目标和结束战斗都必须经过 `CombatService`。

### 4.2 首发动作

- `combat.kill`
- `combat.fight`
- `combat.hit`
- `combat.halt`
- `combat.guard`
- `combat.touxi`
- `combat.ansuan`
- `skill.jifa`
- `skill.prepare`
- `skill.perform`
- `skill.exert`
- `skill.jiali`

文本别名由 `ActionDefinition` 提供；结构化按钮调用相同动作，不另造规则路径。首发冻结 `yong -> skill.perform` 与 `yun -> skill.exert`；`perform`、`exert` 仍是同一路径的规范文本入口，不得实现平行动作语义。

### 4.3 事务与事件

一次结算必须按以下顺序执行：

1. 锁定需要持久化的角色与物品行。
2. 读取当前运行时战斗版本。
3. 调用受控 `RuleDefinition` 计算结果。
4. 写入持久化结算与审计记录。
5. 提交事务。
6. 在提交后发送战斗事件和新的状态摘要。

客户端收到事件前不得本地修改权威气血、内力、装备或物品数量。

## 5. Condition 与 Effect

`ConditionDefinition` 定义 XKX100 状态语义；`EffectInstance` 是一次具体挂载。两者不得混为一个通用 JSON 状态。

每个 immutable `ConditionDefinition` revision 必须引用精确的 `effect_type_key + effect_type_version`，内容参数必须通过该版本 `EffectTypeDefinition.payload_schema`。不得只保存 key 后在运行时漂移到最新 registry version。

每个 `EffectInstance` 必须引用精确的 `condition_definition_revision_id`。`runtime_only` 实例在内存中保留该引用；`durable` 实例把定义 revision、来源、目标、payload、时限、叠层和恢复版本持久化。恢复时任一精确版本缺失都必须阻断相关恢复，不得静默升级。

直接按 condition key 发起的效果从请求固定的 active batch 解析；由 pinned Skill/Item/Entity 行为发起的效果使用来源 Blueprint revision 的 exact resolved dependency。两种路径都禁止任意选择历史 condition revision。

每个 `EffectTypeDefinition` 必须完整遵守 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 5.10 的唯一 schema；本文不复制第二份字段表。
除 `persistence / reference_rule_key / stacking_policy / tick_policy / recovery_policy` 外，尤其必须由它声明 `payload_schema`、`handler_key_apply`、`handler_key_expire`、可选 `handler_key_tick` 与可选 `handler_key_recover`，并遵守 5.10 的组合约束。

上述 payload 校验、叠层、tick、持久化、恢复策略与 handler 选择只归 `EffectTypeDefinition`。
内容侧 `ConditionDefinition` 只定义状态身份、展示/XKX100 语义、精确 EffectType 版本引用和通过其 `payload_schema` 的参数；
不得并行声明或覆盖 `stacking_policy`、`tick_policy`、`persistence`、`recovery_policy` 或任何 apply/expire/tick/recover handler。

`busy`、战斗节拍和无法安全恢复的短期状态使用 `runtime_only`。需要跨重启保留的中毒或长期效果才允许使用 `durable`，并必须有明确恢复测试。

## 6. 物品、背包与装备

本文的 `ItemDefinition` 是 `kind=item` Blueprint 及其 `CompiledBlueprint` 的领域语义名，不是另一张独立持久化主表。除通用 Blueprint 顶层字段外，首发定义的 `data` 最小字段为：

- `item_type`
- `display_name`
- `stackable`
- `max_stack`
- `container_policy`
- `equip_slot`
- `use_action_key`
- `condition_definition_keys`
- `weight`
- `value`
- `source_ref`（必填的定义来源追踪）

`condition_definition_keys` 是可选的 `BlueprintRef[]`，每项必须声明 `expected_kind=condition`。它只属于定义，用来声明物品施加的状态效果，并在候选批次发布时解析到精确 `ConditionDefinition` revision。

published `CompiledBlueprint` 与 Blueprint dependency record 固化 condition exact revision。非状态型效果由 `use_action_key` 进入 ActionDefinition 及其受控 rule/handler，不得塞入该字段。

`use_action_key` 是指向 `ActionDefinition` 的 RegistryRef。发布必须写 exact kind/key/version/definition hash 的 `ResolvedRegistryDependency`；pinned Item 使用该记录，不按裸 key 解析 active registry。

`container_policy` 的唯一结构为：

- `mode`：`none / bounded`
- `max_slots`：`bounded` 时必填的正整数，`none` 时必须为 null
- `accept_rule_key`：可选 RegistryRef -> `RuleDefinition`，`none` 时必须为 null

`bounded` Item 必须 `stackable=false / max_stack=1`。发布把可选 rule 固化为 exact registry dependency；容器接受判断只调用该 pinned rule，不按 active key 漂移。

`source_ref` 记录定义来自哪个源文件与 `source_snapshot_id`，不是某个物品实例的拾取、掉落或获取履历。物品实例首先具有 Entity 的 `id / instance_id / kind / lifecycle_state` 等通用字段；以下是 Item 子域的最小持久状态：

- `id`（实例 id）
- `blueprint_revision_id`（精确引用 `kind=item` 的 published `BlueprintRevision`）
- `quantity`
- `location_entity_id`（Room、Character、NPC 或 policy 允许的容器 Item；首发占有与包含关系的唯一真源）
- `state_version`

定义的 `equip_slot=null` 表示不可装备。若 `equip_slot` 非空，则 `stackable` 必须为 false 且 `max_stack=1`；若 `stackable` 为 true，则 `equip_slot` 必须为空。active Item 的 `quantity` 必须介于 1 与 pinned definition 的 `max_stack` 之间，非堆叠物品固定为 1。

消耗数量小于当前 quantity 时，事务递减 quantity、递增 Item `state_version`，并保持 Entity active 与原 location。消耗最后单位时，事务把 quantity 置 0、删除可能存在的 EquipmentBinding，再把 Entity 置为不可复活的 `retired` 且 `location_entity_id=null`。

耗尽事务必须同时提交 use action 的资源/Effect 结果，并对消耗前占有链最终归属的每个 Character 推进 `character_version / inventory_version`。任一步失败都保留原数量、lifecycle、location、binding、Effect 与版本，且不得发送成功事件。

retired Item 不得再次使用、移动、装备或进入 inventory snapshot。既有 `SpawnMaterialization` 仍保存初始生成事实；Item 耗尽不得删除或改写该记录，也不得触发 `initial_once` 重生。

Item instance 不复制也不允许修改 `source_ref`、`condition_definition_keys`、`use_action_key` 等定义字段。装备关系只由 `EquipmentBinding` 表达，不在 Item instance 上另建装备真源。

Item 只能放入同实例 active Item，且目标 pinned definition 的 `container_policy.mode=bounded`。每个直接子 Item Entity 占一个 slot；数量堆叠不增加 slot，直接子项数不得超过 exact `max_slots`。

容器不得包含自身或任一 ancestor。放入、取出、给予、掉落或移动容器时，服务按 Entity id 排序锁定 item、目标、相关 EquipmentBinding 与目标 ancestor chain，校验 state versions、容量和 exact accept rule。

deferred trigger 必须复核同实例、active target、container policy、直接容量与 containment DAG。失败返回稳定的 `ENTITY_LOCATION_INVALID / ITEM_CONTAINER_NOT_ALLOWED / ITEM_CONTAINER_FULL / ITEM_CONTAINER_CYCLE`，不得部分提交。

`EquipmentBinding` 的最小字段为 `wearer_entity_id / equip_slot / item_instance_id / state_version`。`item_instance_id` 外键引用 Item Entity 的 `id`，不是游戏归属字段 `Entity.instance_id`。

wearer 必须是同实例内 `kind=character` 或 `kind=npc` 的 Entity，item 必须是 `kind=item` 的 Entity。

数据库必须保证 `UNIQUE (wearer_entity_id, equip_slot)` 与 `UNIQUE (item_instance_id)`。deferred trigger 还必须读取 Item 的 exact `blueprint_revision_id`，保证其 compiled `equip_slot` 非空并等于 binding 槽位、`quantity=1`，且 `location_entity_id` 等于 wearer。

装备、卸下、死亡掉落、放入、取出和给予必须锁定 wearer、item、目标容器与相关 binding，并在同一事务中更新 binding 与 `location_entity_id`。

NPC 初始物品只来自 pinned NPC `CompiledBlueprint.item_loadout`。spawn 使用 exact resolved Item dependency 创建 `location_entity_id=NPC` 的 Item Entity；`equip_slot` 非空时在同一事务创建唯一 `EquipmentBinding`。

loadout schema、数量与槽位约束以 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 7.6 节为准。不得按 item key 查询 active batch，也不得以实例字段复制或覆盖 pinned Item definition。

既有 Item 使用时读取其 pinned Item revision 的 exact condition dependency；active batch 更新后不按 key 漂移到新 condition。只有受审计迁移到新 Item revision 后才采用新的 resolved dependencies，迁移前必须校验实例状态兼容；已经创建的 EffectInstance 仍保留原 condition revision。

首发支持拾取、丢弃、放入、给予、装备、卸下、食用、饮用和基础使用。是否消耗及数量由 pinned Item 的 exact action/rule 结果决定，持久化必须遵守上述 active/retired 落点。

Public V1 的 NPC death/drop 在结算事务中创建 30 秒 `LootClaim`；claim 存续时只有声明的领取者可拾取，到期后才公开。拾取锁定 claim 与 Item，竞争者只能有一个事务提交。未被拾取的 NPC loot 在约 15 分钟（策略值 900 秒）后进入 `ItemRetirement`。玩家普通丢弃 Item 使用 60 分钟（3600 秒）退休期限，并在到期前向拥有者发出告警；背包中、已装备或 pinned policy 标记受保护的 Item 不进入自动退休。任何退休都保留 Item identity、source 与审计关系，不硬删除，也不触发死亡 Entity 或 SpawnMaterialization 复活。

样板 `cloth.c` 实例初始由 NPC 穿戴，必须在战斗死亡掉落结算后才能拾取。耐久度、绑定、品质和稀有度不属于首发字段。

背包数量变化和装备切换必须使用数据库事务与行锁。结构性校验失败时返回稳定错误码，不允许先广播成功再回滚。

所有可能改变 Item 位置、数量或 EquipmentBinding 的 ActionDefinition 都必须声明 `requires_inventory_version=true`。active Presence 的请求按 `11_PROTOCOL_CATALOG.md` 携带 `expected_inventory_version`；服务端持锁后比较，冲突时不得继续结构性写入。

## 7. 状态摘要

`scene.snapshot` 只描述场景。服务端还必须提供 `character.snapshot` 与 `combat.snapshot`：

- `character.snapshot`：核心资源及完整 `inventory / equipment / skills / jifa_bindings / prepare_bindings`，并携带可原子核对的角色与背包版本。
- `combat.snapshot`：战斗 id、参战方、目标、资源摘要、短期状态与可用动作版本。

断线重连采用安全重建。客户端不依赖事件补齐恢复权威状态。

## 8. 可复现验收

每个首发战斗用例必须记录：

- `reference_snapshot_id`
- `xkx100-skill-combat-v1` manifest 版本、逐文件哈希与聚合哈希
- 源文件与函数位置
- 固定角色、技能、装备和状态输入
- 固定随机种子与测试时钟
- 预期状态变化、文本要点和错误码
- 新引擎与参考实现的差分结果

世界 manifest 与 `xkx100-skill-combat-v1` 必须引用同一 `source_snapshot_id`，复合验收 bundle 只引用两者。武学 manifest 或依赖闭包未冻结时，相关黄金链必须为 `manual_review` 或 `blocked`，不得标记为通过；合成 fixture 不能替代 XKX100 对齐证据。

战斗验收必须绑定 `compatibility_envelope_id`。包络列出纳入的命令、Action、技能、状态、初始状态、golden case 哈希、允许差异和逐项状态。

无法形成黄金用例的行为必须标记 `blocked` 或 `unverified`。只有包络内 `verified` 行为可声明已对齐，包络外行为不得标记为“已完全对齐”。

M1-A 和 M1 的必做战斗链出现 `manual_review / blocked / unverified` 时，检查点和里程碑都不得完成。

## 9. V6 增量、Public V1 战斗边界与首发验收

M1 的确定性 Actor 与 Public Character 必须分离。Public Character 通过 gameplay 学习技能并成长；GoldenSkillChain 只运行冻结初始态的测试 Actor。首条候选 golden chain 为 `bahuang-gong` 的 `exert powerup` 与 `baihua-cuoquan` 的 `perform cuo`，精确参数和期望差异必须来自冻结来源检查；`benlei-shou` 双准备另列后续用例。

Public V1 只开放互相确认、非致命 `Sparring`；Character-targeted 致命或 involuntary `kill/hit` 返回拒绝。玩家败北按 `SafeDefeat` 处理，保留 Player Item 和不可逆进度；NPC death/drop 仍是权威持久结果。NPC loot 领取、公开化和 `ItemRetirement` 遵循 `LootClaim` 与 V6 需求约束。

PublicV1Gate 的战斗 / 内容证据必须固定到同一个 active `ContentReleaseBatch` 与 ReleaseManifest，并证明至少一条玩家可学习的武学路径、10 个以上具功能或敌对行为的 NPC、20 个以上 Item 定义，以及一条可重复执行的“探索 → 战斗 → 战利品 / 资源 → 成长”PvE 循环。约 30-60 个可连通 Room 由 `06` / `12` 的内容清单负责，首次游玩约 2-4 小时由 `16` 的封闭试运行负责；本合同不得以 Blueprint 数量替代行为证据。

- 普通攻击、`busy` 和战斗结束语义通过黄金测试。
- 至少一门武学完成学习、`jifa`、`prepare` 和 `perform / exert` 链路。
- `guard / touxi / ansuan` 动作入口和 `yong / yun` 文本别名通过协议与来源语义测试。
- 样板 NPC 初始穿戴的 `cloth.c` 实例先完成死亡掉落，再被角色拾取并装备或使用。
- 断线后可通过 snapshot 安全恢复当前战斗摘要。
- 进程重启不会恢复半完成攻击，也不会丢失已提交结算。
- 背包与装备并发操作不会产生负数、重复物品或双重装备。
- LootClaim 在 30 秒内限制领取者、到期后公开，原子竞争只有一个拾取赢家；未拾取 NPC loot 约 900 秒退休，玩家普通丢弃 3600 秒前告警并退休，背包 / 装备 / 受保护 Item 永不被该清理器自动退休。
- Character 间 `combat.fight` 只有双方确认后才进入非致命 Sparring；involuntary / lethal 动作、consent 竞态和 SafeDefeat 按 `11` 的稳定结果 / 错误语义通过协议与事务测试。
- Public V1 的武学路径、功能 / 敌对 NPC、Item 与重复 PvE 循环均绑定 exact revisions、compatibility envelope 和 ReleaseManifest 证据。
- 所有不支持的 XKX100 行为都有带来源位置的未适配记录。
