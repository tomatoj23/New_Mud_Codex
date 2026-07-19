# 07 调度、状态效果与世界事件

> 实施约束：本文负责解释调度域为什么要拆分；凡涉及 `JobType / EffectType / WorldProcessType / StartupPlan` schema、handler 输入输出与 registry 约束，以 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 为准。

> 战斗约束：`CombatLoop / RuntimeTimer`、`busy` 与 Effect 持久化边界，以 `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准。

## 1. 目标

Evennia 的 `Script` 很灵活，但对 New_Mud 来说太像一个“系统杂物间”。新引擎必须把不同类型的后台行为拆开。

本文默认遵循 `docs/new_engine/02_ARCHITECTURE.md` 的“单逻辑运行时”原则：当前基线按单实例单写者执行世界级调度，不把多进程协调当成首版前提。

## 2. Evennia 的启发

源码依据：

- `evennia-main/evennia/scripts/scripts.py`
- `evennia-main/evennia/scripts/taskhandler.py`
- `evennia-main/evennia/scripts/tickerhandler.py`
- `evennia-main/evennia/scripts/ondemandhandler.py`

真正值得保留的不是 `Script` 本身，而是它背后的问题分解：

- 一次性延迟执行
- 周期性触发
- 可暂停/恢复
- 阶段式推进
- 全局系统任务

## 3. 新引擎拆分

### 3.1 ScheduledJob

一类一次性任务：

- 某 NPC 10 分钟后刷新
- 某公告定时发出
- 某离线修炼阶段在指定时间完成

### 3.2 RecurringJob

一类周期任务：

- 昼夜切换
- 季节推进
- 世界广播
- 帮派周结算

### 3.3 EffectInstance

一类附着到角色、NPC、物品上的状态效果：

- buff / debuff
- `busy` / 行动受限
- 中毒
- 流血 / 点穴等持续状态
- 持续运功状态

每个 `EffectInstance` 都引用精确的 `condition_definition_revision_id`。直接按 condition key 创建时，该 revision 来自请求固定的活动 `ContentReleaseBatch`。

由 pinned Entity/Item 行为创建时，它必须等于来源 Blueprint revision 的 exact resolved dependency。两种路径都要求 `kind=condition` published revision，并以 `effect_type_key + effect_type_version` 解析 `EffectTypeDefinition`。
活动批次以后变化时，已有实例继续引用原 revision，不随发布漂移，也不得任意改选其他历史 revision。

叠加、tick、持久化、恢复、rule 和 handler 只由解析后的 `EffectTypeDefinition` 决定；`ConditionDefinition` 只保存通过其 `payload_schema` 的参数，`EffectInstance` 不得覆盖这些策略。实例可能是 `runtime_only` 或 `durable`，是否建立持久化主记录也只由解析后的 `EffectTypeDefinition.persistence` 决定。

### 3.4 WorldProcess

一类长期存在的系统过程，替代 Evennia “把系统做成 Script/Daemon”：

- 江湖传闻传播
- 世界事件管理器
- 门派比武活动
- 区域动态刷新控制器

### 3.5 `RuntimeTimer / CombatLoop`

以下短周期控制属于单实例运行时，不是 `ScheduledJob`：

- 战斗节拍与回合推进
- 当前攻击动作的延迟结算
- 短期 `busy` 与行动限制
- `runtime_only EffectInstance` 的 tick 与过期

`RuntimeTimer` 与 `CombatLoop` 不建立持久化主记录。进程重启时取消未完成攻击并按安全策略结束战斗，不补执行旧战斗计时器。

## 4. 不允许持久化 Python 回调

Evennia `TaskHandler` / `TickerHandler` 会保存回调目标与参数，这在灵活性上很强，但有几个明显问题：

- 回调路径重构后容易失效
- 参数序列化约束不清晰
- 错误恢复困难
- 安全边界模糊

New_Mud 应改为：

- durable job 持久化精确 `job_type_key + job_type_version`、payload、schedule，以及 occurrence/run/attempt、concurrency 和 lease 状态
- durable effect 持久化精确 `condition_definition_revision_id`、解析后的 EffectType key/version、payload 和生命周期状态
- 执行时通过激活 registry 或只读 recovery/validation catalog 找到精确版本的 schema、rule 与 handler
- handler 必须是显式注册的可审查函数

### 4.1 首批执行语义

为了避免不同模块各自发明调度器，首版先冻结以下约束：

- durable `ScheduledJob / RecurringJob` 必须有任务主记录，并冻结精确 JobType version；每次 occurrence、run 和 attempt 使用不可变记录，字段按 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 落地
- 只有解析后 `persistence = durable` 的 `EffectInstance` 有效果主记录，并保存精确 ConditionDefinition revision 与 EffectType version
- `RuntimeTimer / CombatLoop / runtime_only EffectInstance` 不建立数据库主记录
- `WorldProcess` 由 `StartupPlan` 重建运行时过程；确需跨重启的数据使用显式领域 checkpoint，不复用通用 job 行
- handler 统一走 `handler(ctx, payload) -> HandlerResult`
- `ctx` 由引擎注入服务门面、审计器、事件收集器与当前记录 id
- handler 不直接写 socket，不直接绕过服务层改库

## 5. 状态机与阶段推进

`OnDemandTask` 给出的真正好思路是“阶段式时间推进”，这对本项目很有用。

建议抽成 `ProgressClock`：

- 可定义多个阶段
- 每个阶段有展示名、时长、进入回调
- 支持暂停、加速、跳阶段

适用场景：

- 闭关修炼
- 炼丹
- 制造
- 活动开启倒计时

## 6. 事件总线

调度系统不是直接改数据库就结束，必须产生领域事件：

- `job.completed`
- `effect.expired`
- `world.time.changed`
- `season.changed`
- `event.started`

## 7. 与 MUDLib 的边界

MUDLib 可以声明：

- 通过 `register_job_types(registry)` 注册受控 `job type`
- 通过 `register_effect_types(registry)` 注册受控 `effect type`
- 通过 `register_world_process_types(registry)` 注册受控 `WorldProcess` 类型
- 通过 `register_startup_plan(registry)` 声明启动时要拉起的 world process / recurring job
- 定时活动规则仍应落在上述类型与启动计划之上，而不是临时回调

MUDLib 不应该：

- 直接 new 一个后台线程
- 直接创建任意 asyncio task 常驻
- 直接绕过引擎调度表

## 8. 恢复策略

重启后恢复规则建议：

- durable `ScheduledJob / RecurringJob`
  - 先解析精确 JobType version，再按持久化 occurrence、run/attempt、`next_run_at`、concurrency/lease 与冻结的 misfire/retry/overlap policy 恢复
- durable `EffectInstance`
  - 先校验精确 ConditionDefinition revision、EffectType key/version 和 payload schema，再按 `expires_at` 与 recovery policy 恢复或过期
- `RuntimeTimer / CombatLoop / runtime_only EffectInstance`
  - 不恢复，执行战斗安全回退并丢弃短期状态
- `WorldProcess`
  - 由 `StartupPlan` 幂等重建；显式领域 checkpoint 由对应服务恢复

完整 `ScheduleSpec / MisfirePolicy / RetryPolicy / OverlapPolicy` 与 durable Effect 恢复 schema 由 `12_REGISTRY_BLUEPRINT_CONTRACT.md` 冻结，本文不再定义平行版本。

### 8.1 重试、幂等与事务边界

首版冻结：

- `JobTypeDefinition` 必须声明完整 retry 与 overlap policy
- concurrency key 的并行数、跳过或单项排队行为由 overlap policy 决定，不再一律假定只能有一个执行单元
- handler 若非幂等，必须禁止重试；需要幂等键的 handler 必须持久化去重键
- effect 的 apply 使用不可变 creation/apply key；tick、recover、expire 和 remove 使用 durable occurrence/run，或 `EffectOperationRecord(effect_instance_id, operation_kind, operation_generation)` 唯一记录，不能覆盖一个共享幂等字段
- 领域状态写入、审计记录与事件收集应在同一应用服务事务内提交
- 对外广播必须发生在事务提交之后，不能先发事件再回滚数据库

### 8.2 Durable job 最小状态枚举

首版统一：

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`
- `expired`

## 9. 首批必须支持的任务类型

- 场景/NPC 刷新
- 世界时间推进
- 离线修炼或制造完成通知
- 频道广播与系统公告
- 角色持续状态结算
- 世界事件窗口开启关闭

战斗回合计时属于 `CombatLoop / RuntimeTimer` 的首批运行时能力，不进入 durable job 类型清单。

## 10. 最终原则

调度域由受控注册的 durable 任务框架与进程内运行时时钟组成，不是“任何 Python 回调都能塞进去的万能容器”，也不是所有计时行为都落库的统一大表。


