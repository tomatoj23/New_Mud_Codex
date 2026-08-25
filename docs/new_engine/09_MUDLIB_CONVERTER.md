# 09 MUDLib 接口与 LPC 转换器

> 实施约束：本文负责说明 MUDLib 与转换器的职责边界；凡涉及 `manifest.py`、typed registries、`Blueprint` schema、`CompiledBlueprint` 与发布/生效契约，以 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 为准。

> 领域约束：战斗、武学、Condition、物品与运行时落点，以 `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准。

## 1. 目标

引擎与内容分离不是附加特性，而是整个项目的主结构。MUDLib 接口和转换器必须从第一版架构就定下来，否则后续表结构和服务边界都会被反复推翻。

这里的“先定下来”特指：

- 先冻结 MUDLib manifest / entry / registry 契约
- 先冻结 Blueprint 与帮助内容的目标格式
- 先冻结转换器输出边界

完整扫描器与发射器可以后续分阶段推进，但不能等到引擎表结构写完后再反推接口。当前只实现 XKX100 的 `ConversionProfile`；其他源 LPC MUDLib profile 必须经未来范围审批。

## 2. MUDLib 基本原则

- 一个实例只加载一个 MUDLib
- MUDLib 在启动时绑定
- 不支持运行时切换 Python 代码
- 内容数据通过发布批次与安全重载生效，不默认即时生效
- MUDLib 只能使用引擎公开的稳定服务门面
- 包内 `seed/` 与转换器产物只提供导入输入，不是运行时内容真源
- PostgreSQL published revisions 与 exact dependencies 是内容真源；active batch 只为新选择提供当前映射
- pinned 实例继续读取自身 exact historical revision，不回到 active batch 按 key 重解释
- 数据库非空时，普通启动不得用包内 seed 覆盖 draft、published revision 或活动指针
- 转换器输出只能显式导入为 draft 并生成 diff；进入运行时必须另行通过原子发布批次

## 3. 推荐目录结构

```text
mudlibs/
  jinyong_core/
    manifest.py
    mudlib.py
    seed/
      blueprints/
      help/
      startup/
    rules/
    hooks/
    adapters/
    tests/
```

## 4. Manifest

建议最小字段：

- `key`
- `name`
- `version`
- `engine_version_range`
- `dependencies`
- `seed_bundle_id`
- `target_content_release`
- `default_language`
- `default_start_room`
- `entry_class`

## 5. MUDLib 入口接口

建议冻结为分域注册入口：

```python
class MudLib:
    def register_blueprint_seed_providers(self, registry): ...
    def register_help(self, registry): ...
    def register_handlers(self, registry): ...
    def register_rules(self, registry): ...
    def register_permission_policies(self, registry): ...
    def register_hook_sets(self, registry): ...
    def register_action_providers(self, registry): ...
    def register_render_policies(self, registry): ...
    def register_actions(self, registry): ...
    def register_behavior_profiles(self, registry): ...
    def register_character_creation_profiles(self, registry): ...
    def register_effect_types(self, registry): ...
    def register_job_types(self, registry): ...
    def register_world_process_types(self, registry): ...
    def register_startup_plan(self, registry): ...
```

重点：

- 入口负责注册
- 不是拿到 engine container 之后任意扩展
- `register_blueprint_seed_providers()` 只注册 seed loader，不注册运行时 Blueprint 真源
- `BehaviorProfileDefinition`、`CharacterCreationProfileDefinition`、调度类型、效果类型与 `WorldProcess` 类型都必须走受控 registry
- `register_startup_plan()` 只能引用前述已注册类型，不能塞裸 Python 回调

建议按下面的职责拆分理解：

- 内容注册面
  - `register_blueprint_seed_providers`
  - `register_help`
  - `register_handlers`
  - `register_rules`
  - `register_permission_policies`
  - `register_hook_sets`
  - `register_action_providers`
  - `register_render_policies`
  - `register_actions`
- 运行时类型注册面
  - `register_behavior_profiles`
  - `register_character_creation_profiles`
  - `register_effect_types`
  - `register_job_types`
  - `register_world_process_types`
- 启动期声明面
  - `register_startup_plan`

## 6. 引擎对 MUDLib 暴露的服务

只暴露稳定 facade：

- `entity_service`
- `world_service`
- `movement_service`
- `character_service`
- `combat_service`
- `skill_service`
- `inventory_service`
- `quest_service`
- `permission_service`
- `rule_service`
- `chat_service`
- `scheduler_service`
- `help_service`
- `blueprint_service`
- `event_bus`

MUDLib 不能做：

- 改引擎主表结构
- 自己开网络服务
- 自己注册任意后台线程
- 绕过权限和事务直接改库

## 7. 转换器目标

LPC 转换器追求的是“高质量迁移落点”，不是“自动把所有 LPC 逻辑翻成 Python 并可立即运行”。

正确目标：

- 自动迁结构
- 自动迁静态数据
- 自动提取可识别的持久化数据源，包括 `.o` save、SQL dump/schema 与显式数据导出线索
- 半自动迁规则骨架
- 明确输出人工审核清单

## 8. 转换器流水线

### 8.1 Scanner

扫描：

- 文件索引
- inherit 关系
- include 宏
- SQL schema / dump / 数据导出文件
- room/npc/item/skill/daemon/command 文件分类

### 8.2 Parser

解析：

- `set/query/add`
- `create()`
- 房间 `objects`、NPC `map_skill/prepare_skill` 与 `carry_object/wear/wield`
- `add_action()`
- `call_out()`
- `save_object()/restore_object()`
- 常见 SQL schema / INSERT dump / 数据访问 helper 调用

### 8.3 IR

统一成中间表示：

- `RoomIR`
- `ExitIR`
- `NpcIR`
- `ItemIR`
- `SkillIR`
- `MovementIR`
- `CombatIR`
- `QuestIR`
- `ConditionDefinitionIR`
- `DaemonIR`
- `CommandIR`

其中 `RoomIR` 至少应能表达：

- 房间基础标识
- 出口来源位置与不可通行 `external_exit_boundaries`
- 规范化 `spawn_entries` 及每项来源位置、目标 kind/key、数量和映射状态
- 可选坐标 `x/y/z`
- 坐标来源或可信度状态

`ExitIR` 是独立 `kind=exit` Blueprint 的 IR，不是 Room 内嵌的第二种出口 schema。它至少保存稳定 key、`source_room_ref / target_room_ref / direction / aliases`、可选 traversal rule、来源位置与映射状态。

target Room 不在当前转换图时不得产生 `ExitIR`。Normalizer 把它写入 source `RoomIR.external_exit_boundaries`，保留原目标字符串并标记不可通行。

`NpcIR` 至少表达基础属性、来源位置，以及规范化的 `skill_loadout / item_loadout`。

`skill_loadout` 每项保留 `skill_ref / level / jifa_slots / prepare_enable_slot / combine_order`；`item_loadout` 每项保留 `item_ref / quantity / equip_slot`。每项还必须记录源标识、位置、映射状态与复核依据。

ref 只有在目标 Blueprint kind/key 可唯一确定时才能交给 Emitter。不确定的目标、数量、等级、`jifa`、`prepare` 或装备槽必须进入 `manual_review`。

`ItemIR` 至少保留 ItemDefinition 的 `item_type / display_name / stackable / max_stack / container_policy / equip_slot / use_action_key / condition_definition_keys / weight / value / source_ref`，以及每个字段的来源位置和映射状态。

`container_policy` 必须规范化为 `mode / max_slots / accept_rule_key`，并原样进入 Emitter 输出。无法从源数据与 profile 规则唯一判定容器能力、容量或接受规则时，整个 Item 进入 `manual_review`；不得猜测 `none`、默认容量或放宽接受规则，也不得输出可导入 draft。

`MovementIR` 至少表达源/目标房间、方向与别名、移动条件、相关 hook 来源及夹具外边界引用。

`CombatIR` 至少表达 XKX100 动作入口、技能/武器路由、资源消耗、`busy` / condition 语义、受控规则引用与参考快照位置。

`QuestIR` 至少表达任务节点、前置条件、状态迁移、奖励、脚本来源与无法自动迁移的行为。

`ConditionDefinitionIR` 描述候选 `effect_type_key + effect_type_version`、规范化 `parameters`、源码位置与映射诊断。可交给 Emitter 的最终 IR 必须已经从目标 MUDLib 的激活 registry 确认 exact pair，`effect_type_version` 不得为空。

映射不确定、参数无法结构化、找不到受控 EffectType 或 exact version 无法确认时必须进入 `manual_review`，不得猜测默认类型，也不得为该 condition 创建 draft。

IR 不得携带独立的 stacking、tick、persistence、recovery、rule 或 handler 策略。Emitter 把确认后的 exact pair 和 parameters 原样写入 `kind=condition` 的 immutable Blueprint draft。
编译和发布阶段重新解析并复核 exact pair 与 `payload_schema`，但不得补写或修改 draft。所有运行时策略只来自 `EffectTypeDefinition`，运行时挂载结果才是引用 exact ConditionDefinition revision 的 `EffectInstance`。

### 8.4 Normalizer

处理不同 MUDLib 差异：

- 根目录偏移
- skill 路径差异
- npc 基类差异
- mudcore 风格 API
- `.o` 文件、SQL dump 与数据库访问线索差异
- 多层 inherit 差异
- 基于出口方向、种子房间或显式地图文件的坐标推导
- 坐标冲突、缺失和多解检测
- 目标激活 registry 中 EffectType exact pair 的确认与 parameters schema 预校验

### 8.5 Emitter

输出：

- `seed/blueprints/`
- `seed/help/`
- `seed/startup/`
- `manifest.py`
- `mudlib.py`
- `rules/`
- `hooks/`
- `adapters/`
- `tests/`
- `reports/manual_review/`

这些产物只能通过 seed import 服务创建 immutable draft revisions。Emitter 不得创建 published revision、切换 `ContentReleaseHead` 或直接生成运行时对象。

Emitter 输出 condition Blueprint 前必须再次确认 IR 已含目标激活 registry 中的 exact `effect_type_key + effect_type_version`，且 parameters 已通过对应 `payload_schema`。任一条件不满足时只写 `manual_review`，不得输出可导入 draft。

Emitter 输出 Room Blueprint 时，必须写入 `data.spawn_entries / data.external_exit_boundaries`；每个 spawn target 明确 `expected_kind=npc|item`、稳定 `spawn_entry_id`、count 与 `initial_once`。

Emitter 为每个内部有向连接输出独立 `kind=exit` draft，并把 source/target 写成 `expected_kind=room` 的 BlueprintRef。方向与 aliases 在 source Room 范围内规范化后必须与其他 Exit 和 external boundary 全部互斥。

Emitter 输出 NPC Blueprint 时，必须把已确认的 skill 与 item 目标分别写成 `data.skill_loadout` 和 `data.item_loadout` 的 BlueprintRef。空 loadout 显式写 `[]`。

Emitter 输出 Item Blueprint 时，必须保留通过校验的 `data.container_policy`。`bounded` 的容量与可选 rule 必须来自已确认的 ItemIR；`accept_rule_key` 只有可唯一解析到目标 registry definition 时才能写入。

Emitter 不得直接创建 `StaticEntityBinding`、`SpawnMaterialization`、Entity、`ActorSkill` 或 binding。这些运行时状态只在 world init/spawn 时由 pinned compiled refs 原子生成。

坐标相关输出约束：

- 若源数据已有可靠坐标，则原样保留并归一化
- 若可根据拓扑和 profile 规则稳定推导坐标，则输出正式 `x/y/z`
- 若无法稳定推导，则允许输出空坐标，但必须在报告中列出缺失房间、冲突原因和建议补点
- 房间拓扑永远先于坐标可用性完成导出，不能因为坐标未定而阻断区域转换

## 9. `ConversionProfile`（XKX100-only）

当前实现只注册 `xkx100` 的 `ConversionProfile`：

```yaml
mudlib_key: xkx100
source_locator: D:/My_Projects/xkx100-20201118  # 仅用于本机定位候选输入，不是来源身份
room_roots: ["/d/"]
skill_roots: ["/kungfu/", "/daemon/skill/"]
npc_bases: ["/inherit/npc", "/std/npc"]
include_roots: ["/include/"]
path_aliases:
  "/std/room": "room_base"
```

`source_locator` 只是操作员提供的本机路径；转换开始前必须加载并校验不可变 `source_snapshot.json` 的 `source_snapshot_id`、逐文件哈希和聚合哈希。路径不得写入 manifest、`ReleaseManifest` 或其他验收身份，也不能替代来源快照。

若后续出现额外数据源，只补充最小来源识别配置，不在当前首发文档里提前冻结一整套多数据源参数表。

其他源 LPC MUDLib 的 `ConversionProfile` 必须先通过未来范围审批，不得作为 XKX100 首发实现的隐含兼容目标。

对存在地图推导需求的内容包，profile 还可补充可选字段：

- `coordinate_mode`
  - `explicit`、`derived` 或 `mixed`
- `coordinate_seeds`
  - 作为推导起点的房间与初始坐标
- `direction_vectors`
  - 方向名到 `(dx, dy, dz)` 的映射
- `coordinate_conflict_policy`
  - 遇到冲突时是中止、跳过还是写入报告

## 10. LPC 到新引擎映射

### 可直接映射

- `inherit ROOM/NPC/ITEM` -> Blueprint kind
- `set("exits", ...)` 的内部目标 -> 独立 `kind=exit` Blueprint
- `set("exits", ...)` 的范围外目标 -> source Room 的 `data.external_exit_boundaries`
- `set("objects", ...)` -> `kind=room.data.spawn_entries`
- NPC `map_skill/prepare_skill` -> `kind=npc.data.skill_loadout`
- NPC `carry_object(...)->wear()/wield()` -> `kind=npc.data.item_loadout`
- 武功元数据 -> `kind=skill` 与 `kind=skill_move` Blueprint；move、RuleDefinition 与 ActionDefinition 引用必须显式分类

### 需要重构映射

- `daemon` -> `WorldProcessType / JobType / RuleDefinition / adapter stub`
- 非战斗且需跨重启的 `call_out()` -> durable `ScheduledJob`
- 战斗节拍、攻击延迟与短期 `busy` 的 `call_out()` -> `CombatIR`，最终落到 `CombatLoop / RuntimeTimer`
- `main(object me, string arg)` -> `ActionDefinition` 或交互 handler
- `.o` 文件 -> draft seed 或显式领域状态导入计划
- MySQL 表 / SQL dump -> `seed/` 或数据导入计划
- SQL query helper -> repository stub 或人工审核清单

### 需要人工审核

- 复杂战斗公式
- 高动态行为逻辑
- 宏驱动脚本
- 数据库直接操作代码

## 11. 输出目录建议

```text
converted/
  xkx100/
    manifest.py
    mudlib.py
    seed/
      blueprints/
      help/
      startup/
    rules/
    hooks/
    adapters/
    tests/
    reports/
```

## 12. 验收标准

### 12.1 受控输入门禁

受控参考基线与发布门禁以 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` 第 8-10 节为准。任何转换运行开始前都必须：

- 将运行配置中的 `reference_snapshot_id` 解析到版本化 `source_snapshot.json` 的 `source_snapshot_id`，并要求两者完全一致
- 校验 `source_snapshot.json` 记录的逐文件 SHA-256 与文件树 SHA-256
- 按 `16_OPERATIONS_TESTING_CONTRACT.md` 第 8 节的 path normalization、RFC 8785/JCS、UTF-8 与小写 SHA-256 算法校验 source tree 和两个 manifest
- 分别校验两个 manifest 的 `root_files / dependency_files` 分类、互斥性、逐文件哈希与聚合哈希；每个数组都必须按规范化 path 的 UTF-8 字节独立升序排序后再参与 JCS
- 校验 world 的五个 roots 及其完整 include/inherit/static-helper closure；依赖只作解析输入，不生成额外 fixture 定义
- 校验 skill/combat roots 及其完整 dependency closure；两个 manifest 的共享路径必须具有相同 SHA-256
- 校验复合验收 bundle 只引用上述两个 manifest，且两者共享同一 `source_snapshot_id`
- 在任一标识、清单或哈希不一致时，于 Scanner 读取和 Emitter 输出前拒绝运行

本机绝对路径只用于定位候选输入，不构成来源身份或验收依据。CI 与转换制品必须绑定冻结快照和逐文件哈希，不能从路径、文件名或部署环境推断输入身份。

### 12.2 双固定夹具与黄金差分

首发夹具固定为 `xkx100-village-alley-v1`，fixture manifest 必须冻结并校验以下计数：

- 定义计数：2 个 Room、2 条内部有向 Exit、1 条外部边界引用、2 个 NPC、1 个 Item
- 初始运行时计数：2 个 Room、2 个可通行 Exit、2 个 NPC、2 个 Item 实例；两个 Item 实例都来自同一个 `cloth.c` 定义

`alley1.east` 指向夹具外的 `sroad3`，必须作为外部边界引用保留；夹具运行时不得开放该出口，也不得静默删除或伪造目标房间。黄金行为差分必须在相同固定 RNG 种子、冻结时钟、时区和初始状态下运行。必做能力的非允许差异必须阻断验收；只有包络声明的纯展示差异或非必做项可进入有负责人、依据和复核日期的例外清单。

`xkx100-skill-combat-v1` 必须在同一 `source_snapshot_id` 下独立冻结受审 roots 与完整 dependency closure。skill/command 不得进入 world roots；共享支持文件可出现在两边的 dependency_files。

复合验收 bundle 只引用两个 manifest 的名称、版本、`source_snapshot_id` 与聚合哈希。武学 manifest、依赖闭包或 bundle 未冻结时，战斗/武学黄金链只能为 `manual_review` 或 `blocked`，不得计为通过。

### 12.3 通用转换验收

转换后至少自动校验：

- 房间/出口拓扑完整
- 房间坐标要么全部通过校验，要么全部生成缺失/冲突报告
- Blueprint schema 全部通过
- `RoomIR / NpcIR / ItemIR / MovementIR / CombatIR / QuestIR / ConditionDefinitionIR` 均有目标落点或明确 manual review
- 每个已输出 Room/NPC draft 的四个必填数组都通过 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 7.6 节 schema，全部 BlueprintRef 可在候选图中解析
- 每个 Exit draft 的 exact source/target Room refs 可解析，方向与 aliases 不和同 Room 的 Exit 或 external boundary 冲突
- world init 测试按 pinned compiled refs 幂等创建 `StaticEntityBinding`、`SpawnMaterialization`、Entity、`ActorSkill` 与 bindings
- 每个已输出 Condition draft 在创建前已固化 exact EffectType pair 并通过 payload schema，编译与发布再复核同一 pair
- 关键区域 smoke test 可跑
- unresolved symbol 全部记录
- manifest 的依赖、seed bundle 与目标内容发布字段可加载并通过 `12` 的校验
- `register_blueprint_seed_providers()` 与全部 typed registry 入口可完成引用闭包校验
- startup plan 可解析
- seed import 只创建 draft revisions 和 diff，不创建 published revision，也不改变活动 `ContentReleaseBatch`
- 若扫描到 SQL dump、表结构或显式数据库访问线索，则相关可迁移数据必须导出为 `seed/`，无法自动归一化的部分必须进入 `manual_review` 报告

## 13. 最终原则

MUDLib 是 XKX100 内容 seed、受控规则与适配代码的标准接口，转换器是 draft 导入产物的生产工具。新选择消费 PostgreSQL active batch，pinned 实例消费 exact historical revision；两者都使用声明式 registry。

任何运行时路径都不能把包内文件重新提升为事实真源。

## V6 增量：不可变来源与 Village 包络

当前源基线为 `xkx100-20201118-sha256-1b101b7a99c60803`，属于不可变 `SourceSnapshot`。任何来源字节、纳入范围或分类变化都必须创建新的 snapshot、manifest 和 compatibility envelope；转换器不得原地覆盖历史制品，也不得从局部扫描推断全局 XKX100 兼容。

`d/village` 的 Public V1 转换以完整拓扑为 `VillageTopologyEnvelope` 起点，以行为证据创建 `VillageInteractionEnvelope`。未验证的 source interaction 必须生成带来源位置、原因和影响级别的 `UnavailableInteraction`；不得静默跳过、猜测或近似实现。GoldenSkillChain 的日常 Character 状态与确定性测试 Actor 分离。

