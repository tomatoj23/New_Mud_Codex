# 12 Registry、Blueprint 与发布契约

> 状态：`Engine Stage E0` 必须冻结的实施级契约。凡涉及 `manifest.py`、`mudlib.py`、typed registries、`Blueprint` schema、`BlueprintRevision`、发布与生效语义，以本文为准。

## 1. 目标

`06/07/09` 已经说明了 New_Mud 为什么需要 `Blueprint`、受控 registry 与 MUDLib 入口；本文负责把这三者补成真正可编码的稳定契约。

本文覆盖：

- `manifest.py` 最小字段
- `mudlib.py` 注册入口
- typed registry 通用规则
- `Handler / Rule / PermissionPolicy / HookSet / ActionProvider / RenderPolicy` 等 typed registry 最小 schema
- `Action / BehaviorProfile / EffectType / JobType / WorldProcessType / StartupPlan` 最小 schema
- `Blueprint` schema、merge 规则、编译产物与校验错误
- `BlueprintRevision / BlueprintHead / ContentReleaseBatch` 的编辑、发布、回滚与生效语义

## 2. `manifest.py` 最小契约

### 2.1 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | MUDLib 唯一键，实例级唯一 |
| `name` | string | 是 | 展示名 |
| `version` | string | 是 | MUDLib 内容版本，使用 semver |
| `engine_version_range` | string | 是 | 兼容的引擎版本范围 |
| `dependencies` | object[] | 是 | 依赖声明；无依赖时必须是空数组 |
| `seed_bundle_id` | string | 是 | 包内初始内容种子的不可变标识 |
| `target_content_release` | string | 是 | 稳定发布流键；同一流的全部批次共享该值 |
| `default_language` | string | 是 | 默认语言 |
| `default_start_room` | string | 是 | 初始房间 Blueprint key，发布时必须可解析 |
| `entry_class` | string | 是 | `mudlib.py` 入口类路径 |

### 2.2 `dependencies` 元素

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 依赖包唯一键 |
| `version_range` | string | 是 | 允许的依赖版本范围 |

依赖只从实例配置允许的本地包集合解析，不触发联网安装。依赖图必须无环，且不会把单实例单 MUDLib 扩展成运行时可切换的多 MUDLib。

### 2.3 SemVer 与范围语法

`version` 只接受 `MAJOR.MINOR.PATCH`。三个分量都是十进制非负整数；除 `0` 外不得有前导零。不接受 prerelease 或 build metadata。

版本正则为：

```text
^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$
```

`engine_version_range` 与依赖的 `version_range` 使用同一语法。

```text
range      := clause (SP OR SP clause)*
clause     := comparator (SP comparator)*
comparator := operator version
operator   := = | > | >= | < | <=
SP         := U+0020
OR         := ||
```

同一 `clause` 内的单个 ASCII 空格表示 AND，` || ` 表示 OR。操作符按最长匹配解析，版本按三元整数比较。

合法示例：`>=1.6.0 <2.0.0`、`=1.8.2 || >=2.1.0 <3.0.0`。

不支持裸版本、括号、逗号、连字符范围、`^`、`~`、`*`、`x` 或 `X`。范围字符串不得为空，也不得包含多余空白。

### 2.4 启动校验

- `engine_version_range` 不满足时，启动失败
- 任一依赖缺失、版本不满足或依赖图成环时，启动失败
- 缺失 `entry_class` 时，启动失败
- `key` 与实例配置不一致时，启动失败
- `seed_bundle_id` 或 `target_content_release` 不符合 registry key 正则时，启动失败

## 3. `mudlib.py` 入口契约

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
    def register_effect_types(self, registry): ...
    def register_job_types(self, registry): ...
    def register_world_process_types(self, registry): ...
    def register_startup_plan(self, registry): ...
    def get_character_creation_config(self): ...
```

冻结规则：

- 所有注册发生在启动期
- 首版不支持运行时增删 registry entry
- 注册失败必须阻断启动，不允许降级成 warning
- `register_startup_plan()` 只能引用已注册类型键
- `register_blueprint_seed_providers()` 只注册 seed 提供者，不注册运行时 Blueprint 真源

### 3.1 Blueprint seed 与 PostgreSQL 真源

PostgreSQL immutable published revisions 与 exact dependencies 是运行时内容真源。`ContentReleaseHead.active_batch_id` 只为新选择、新 spawn 和 batch-scoped 请求提供当前完整映射。

pinned Entity/Item 与 durable Effect 按自身 exact historical revision 读取。包内文件、seed provider 与 `BlueprintHead.published_revision_id` 只提供导入输入或便利投影，不能覆盖这两类读取入口。

当前 `(instance_id, mudlib_key)` namespace 未初始化，是指其中尚无 `BlueprintHead` 且没有活动 `ContentReleaseBatch`。此时允许执行一次受审计的 seed bootstrap，并以原子批次建立首个发布。

该 namespace 已初始化后，普通启动不得从包内文件或 seed 覆盖任何 draft、published revision 或发布指针。`seed_bundle_id` 变化也不构成自动覆盖授权。

已初始化 namespace 导入新 seed 必须走显式 Admin 或 management command：生成新的不可变 draft revisions，编译并展示 diff，再由有权限的操作者显式发布 `ContentReleaseBatch`。

`target_content_release` 标识实例与 MUDLib 内的稳定发布流，不是单次批次 id。相同发布流的 seed bootstrap、后续导入、普通发布和回滚重发都共享该值；加载 manifest 不会自动切换该流的活动批次。

同一 `seed_bundle_id` 必须绑定稳定内容哈希。相同 id 但内容哈希不同应拒绝导入，并记录审计错误。

## 4. Registry 通用规则

### 4.1 通用字段

首版 typed registry 包括：

- `HandlerDefinition`
- `RuleDefinition`
- `PermissionPolicyDefinition`
- `HookSetDefinition`
- `ActionProviderDefinition`
- `RenderPolicyDefinition`
- `BlueprintSeedProviderDefinition`
- `ActionDefinition`
- `BehaviorProfileDefinition`
- `EffectTypeDefinition`
- `JobTypeDefinition`
- `WorldProcessTypeDefinition`
- `StartupPlanEntry`

每个 typed registry entry 至少包含：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 所属 registry 内唯一键 |
| `version` | string | 是 | 当前条目版本 |
| `definition_hash` | string | 是 | 解析完整引用图后生成的定义 SHA-256 |
| `summary` | string | 是 | 简述 |
| `source_module` | string | 是 | 来源模块 |
| `tags` | string[] | 否 | 标签 |

`definition_hash` 覆盖规范化声明、所有 transitive registry 依赖的 exact kind/key/version/hash，以及 Handler callable 所在构建制品的 SHA-256。registry 构图必须按 DAG 逆拓扑顺序计算它，不能只哈希裸 key 或模块路径。

同一 `(registry_kind, key, version)` 不得对应不同 `definition_hash`。代码或声明变化导致 hash 变化时必须提升 version；否则返回 `REGISTRY_VERSION_CONTENT_MISMATCH` 并阻断启动或发布。

### 4.2 键规则

- 正则：`^[a-z][a-z0-9_.-]{2,63}$`
- `version` 必须符合 2.3 的精确 SemVer 语法
- 同一实例内，同类 registry 的 `key` 唯一
- 同一 `key` 重复注册，直接报错
- 同一 `key` 的不同版本不能同时激活
- 所有注册方法先收集定义，再统一构建引用图；方法排列顺序不是依赖解析顺序
- 引用图校验必须在启动世界前完成，缺失目标或非法环都阻断启动

### 4.2.1 激活版本与只读兼容目录

“不能同时激活”表示每个 registry key 只有一个版本可供新建或修改的内容选择，不表示可以立即删除仍被持久状态引用的旧版本。

存在精确版本持久引用的 registry 必须维护按 `(registry_kind, key, version, definition_hash)` 索引的只读 recovery/validation catalog。兼容目录中的旧定义不参与新内容选择，但必须保留完整解析产物及其 transitive rule、handler 和构建制品，供以下对象校验、恢复和回滚：

- 当前活动批次复用的旧 published revision
- 仍在保留期且允许回滚的历史 `ContentReleaseBatch`
- pinned Entity/Item 引用的 historical Blueprint revision
- `ResolvedRegistryDependency` 引用的 exact registry definition
- durable `ScheduledJob / RecurringJob / EffectInstance` 等精确版本持久状态

新建或修改的内容只能选择当前激活的 registry version；旧 published revision 可以继续从兼容目录解析原版本与 hash。启动世界前必须扫描活动批次、pinned revisions、允许回滚批次及 durable jobs/effects，任一 exact definition 或 transitive artifact 缺失都阻断启动。

移除旧版本前，必须先迁移或清退全部 durable 引用，并让引用它的历史批次退出允许回滚的保留范围。冷部署可以同时携带“一个激活版本 + 若干只读兼容版本”；若部署包不再携带旧版本，则必须在维护窗口先完成上述迁移和清退，不能启动后静默改用最新版。

### 4.3 校验失败

统一输出：

```json
{
  "code": "REGISTRY_DUPLICATE_KEY",
  "registry": "job_type",
  "key": "world.daynight",
  "message": "duplicate key",
  "source_module": "mudlibs.jinyong_core.jobs.daynight"
}
```

常见错误码：

- `REGISTRY_DUPLICATE_KEY`
- `REGISTRY_SCHEMA_INVALID`
- `REGISTRY_MISSING_DEPENDENCY`
- `REGISTRY_HANDLER_MISSING`
- `REGISTRY_REFERENCE_NOT_FOUND`
- `REGISTRY_REFERENCE_CYCLE`
- `REGISTRY_VERSION_CONTENT_MISMATCH`
- `REGISTRY_COMPAT_DEFINITION_MISSING`
- `REGISTRY_STARTUP_PLAN_INVALID`

## 5. Typed Registry 契约

### 5.1 `HandlerDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | handler 键 |
| `callable_path` | string | 是 | 可导入的受控 Python callable 路径 |
| `input_schema` | object | 是 | payload schema |
| `result_schema_version` | string | 是 | `HandlerResult` schema 版本 |
| `idempotency` | string | 是 | `idempotent / requires_idempotency_key / non_idempotent` |

`callable_path` 必须在启动期完成导入与签名校验。业务 registry 只能引用 `handler_key`，不得直接保存 callable、lambda 或任意代码文本。

### 5.2 `RuleDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | rule 键 |
| `handler_key` | string | 是 | 已注册 `HandlerDefinition` |
| `input_schema` | object | 是 | 规则输入 schema |
| `output_schema` | object | 是 | 规则输出 schema |
| `determinism` | string | 是 | `deterministic / seeded` |

Rule 必须无副作用，不直接写数据库或发送事件。`seeded` 规则的随机种子必须由调用上下文显式传入并进入审计。

### 5.3 `PermissionPolicyDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | policy 键 |
| `rule_keys` | string[] | 是 | 已注册 `RuleDefinition` 键 |
| `combine` | string | 是 | `all / any` |
| `default_decision` | string | 是 | `deny / allow` |

权限策略求值失败时一律 fail closed。`rule_keys` 为空时只允许 `default_decision = deny`。

### 5.4 `HookSetDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | hook set 键 |
| `hook_schema_version` | string | 是 | hook 名称与输入输出版本 |
| `hooks` | object | 是 | hook 名到 `handler_key` 的映射 |

`hooks` 的每个值必须引用 `HandlerDefinition`。未在 `hook_schema_version` 中声明的 hook 名启动时拒绝注册。

### 5.5 `ActionProviderDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | provider 键 |
| `source_scopes` | string[] | 是 | provider 可出现的上下文范围 |
| `action_keys` | string[] | 是 | 暴露的 `ActionDefinition` 键 |
| `availability_rule_keys` | string[] | 否 | 可用性 `RuleDefinition` 键 |
| `priority` | int | 是 | provider 合并优先级，数值越小越先处理 |

provider 只决定动作可见性与来源，不绕过 `ActionDefinition.permission_policy_key`。

### 5.6 `RenderPolicyDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | render policy 键 |
| `handler_key` | string | 是 | 已注册 `HandlerDefinition` |
| `input_schema` | object | 是 | 渲染输入 schema |
| `output_schema` | object | 是 | 结构化渲染投影 schema |

Render handler 只能产生结构化投影，不得修改领域状态或直接写 socket。

### 5.7 `BlueprintSeedProviderDefinition`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | seed provider 键 |
| `seed_bundle_id` | string | 是 | 必须与 manifest 一致 |
| `target_content_release` | string | 是 | 必须与 manifest 的稳定发布流键一致 |
| `content_hash` | string | 是 | seed bundle 的稳定 SHA-256 |
| `loader_handler_key` | string | 是 | 返回规范化 Blueprint 输入的 handler |

seed loader 只读取包内资源并返回结构化输入，不得直接写数据库或切换发布指针。

### 5.8 `ActionDefinition`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 全局动作键 |
| `version` | string | 是 | 版本 |
| `aliases` | string[] | 否 | 文本别名 |
| `summary` | string | 是 | 简要描述 |
| `source_scopes` | string[] | 是 | `connection/auth_session/presence/room/item/channel/system` |
| `argument_schema` | object | 是 | 参数 schema |
| `requires_inventory_version` | bool | 是 | 是否在执行前比较 Character 背包聚合版本 |
| `permission_policy_key` | string | 是 | 权限策略键 |
| `match_priority` | int | 否 | 默认 `100`，数值越小越先匹配 |
| `handler_key` | string | 是 | 执行 handler 键 |
| `help` | object | 是 | 帮助元数据 |

规则：

- `key` 全局唯一
- `aliases` 允许跨 action 冲突，但必须由以下解析规则解消
- 同一 action key 经多个 provider 暴露时先去重，并以这些 provider 中最小的 `priority` 作为有效 provider priority
- 不同 action key 的候选依次按 `match_priority`（小优先）、`provider.priority`（小优先）、最长规范化别名排序
- 完成全部排序后仍有多个不同 action key 并列时返回 `ACTION_AMBIGUOUS`
- `handler_key` 必须引用 `HandlerDefinition`
- `permission_policy_key` 必须引用 `PermissionPolicyDefinition`
- 任何可能改变 Item 位置、数量或 EquipmentBinding 的客户端动作都必须声明 `requires_inventory_version=true`；其他动作显式为 false
- XKX100 战斗中的 `busy / condition` 与聊天防刷限制由运行时策略决定，不冻结通用冷却字段

### 5.9 `BehaviorProfileDefinition`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | profile 键 |
| `entity_kinds` | string[] | 是 | 适用实体种类 |
| `hook_set_key` | string | 否 | 移动、渲染等 hook 集 |
| `action_provider_keys` | string[] | 否 | 暴露动作提供者 |
| `render_policy_key` | string | 否 | 外观渲染策略 |
| `state_schema` | object | 否 | profile 需要的状态结构 |

引用闭包规则：

- `hook_set_key` 必须引用 `HookSetDefinition`
- `action_provider_keys` 必须引用 `ActionProviderDefinition`
- `render_policy_key` 必须引用 `RenderPolicyDefinition`
- `ActionProviderDefinition.action_keys` 必须引用 `ActionDefinition`
- 所有间接 `RuleDefinition` 与 `HandlerDefinition` 引用都必须在启动期闭合

### 5.10 `EffectTypeDefinition`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | effect 键 |
| `payload_schema` | object | 是 | 负载结构 |
| `stacking_policy` | string | 是 | `replace / stack / reject` |
| `tick_policy` | object | 是 | tick 模式与间隔 |
| `persistence` | string | 是 | `runtime_only / durable` |
| `reference_rule_key` | string | 是 | 已注册 `RuleDefinition` |
| `recovery_policy` | string | 是 | `discard / expire_if_elapsed / resume` |
| `handler_key_apply` | string | 是 | 应用 handler |
| `handler_key_expire` | string | 是 | 过期 handler |
| `handler_key_tick` | string | 否 | 周期 handler |
| `handler_key_recover` | string | 否 | durable 恢复 handler |
| `max_recovery_catch_up_ticks` | int | 否 | 恢复时最多补算 tick 数 |

`tick_policy` 包含 `mode = none / interval / manual`。只有 `interval` 必须声明正整数 `interval_s`；其他模式不得携带该字段。

`runtime_only` 必须使用 `recovery_policy = discard`，不得建立持久 `EffectInstance` 行，也不得声明 recover handler。进程退出后该效果直接消失。

`durable` 必须使用 `expire_if_elapsed` 或 `resume`，必须声明 `handler_key_recover`。持久字段及 `ConditionDefinition -> EffectTypeDefinition -> EffectInstance` 的唯一解析链以 7.5 节为准。

`expire_if_elapsed` 在重启时只结算已过期实例，未过期实例从剩余期限继续且不补 tick。`resume` 恢复未过期实例，并按显式上限处理遗漏 tick。

durable 恢复必须先校验精确的 ConditionDefinition revision、EffectType key/version 和 payload schema，再以行锁及幂等键执行。缺失任一精确版本时阻断相关效果恢复，不得静默改用活动批次中的最新版。

过期效果只执行一次 expire。`resume + interval` 必须声明非负 `max_recovery_catch_up_ticks`，补算不得超过该值；其他组合不得声明该字段。

所有 handler 字段必须引用 `HandlerDefinition`，`reference_rule_key` 必须引用 `RuleDefinition`。`tick_policy.mode = none` 时不得声明 tick handler。

### 5.11 `JobTypeDefinition`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | job 键 |
| `payload_schema` | object | 是 | 负载结构 |
| `handler_key` | string | 是 | 执行 handler |
| `retry_policy` | object | 是 | 重试策略 |
| `overlap_policy` | object | 是 | 重叠执行策略 |
| `concurrency_key_template` | string | 是 | 并发/去重键模板 |
| `max_runtime_s` | int | 是 | 正整数超时秒数 |
| `emit_event_type` | string | 否 | 完成时默认事件 |

`handler_key` 必须引用 `HandlerDefinition`。`retry_policy` 与 `overlap_policy` 必须分别通过 5.14.3 与 5.14.4 校验。

durable `ScheduledJob / RecurringJob` 必须持久化精确的 `job_type_key + job_type_version`，并用该版本的 `payload_schema`、handler、retry 与 overlap policy 恢复，禁止只按裸 key 漂移到当前激活版本。新建任务只能选择激活版本；旧任务按 4.2.1 节从只读兼容目录解析。

任务主记录至少还要持久化 payload、schedule、`next_run_at`、state、concurrency key、lease owner/expiry 与 state version。每个 occurrence、run 和 attempt 使用不可变记录保存 scheduled time、attempt number、执行状态、租约与稳定错误码；不能用任务主记录上的一个可变幂等字段覆盖历史执行。

### 5.12 `WorldProcessTypeDefinition`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | world process 键 |
| `payload_schema` | object | 是 | 初始化参数 |
| `handler_key` | string | 是 | 主 handler |
| `singleton_scope` | string | 是 | `instance / mudlib / region` |
| `recovery_policy` | string | 是 | `restart / manual / skip` |
| `tick_interval_s` | int | 否 | 轮询间隔 |

`handler_key` 必须引用 `HandlerDefinition`。`tick_interval_s` 若存在必须为正整数。

### 5.13 `StartupPlanEntry`

最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 启动计划项唯一键 |
| `target_kind` | string | 是 | `recurring_job / world_process` |
| `type_key` | string | 是 | 已注册类型键 |
| `type_version` | string | 是 | 精确的激活 registry 版本 |
| `payload` | object | 是 | 初始化负载 |
| `schedule` | object | 否 | recurring job 必填的 `ScheduleSpec` |
| `misfire_policy` | object | 否 | recurring job 必填的 `MisfirePolicy` |
| `enabled` | bool | 是 | 是否启用 |
| `idempotency_key` | string | 是 | 启动幂等键 |

`world_process` 不得声明 `schedule` 或 `misfire_policy`。`recurring_job` 必须同时声明两者，并以 `type_key + type_version` 引用具有完整 retry 与 overlap policy 的激活 `JobTypeDefinition`。

### 5.14 调度策略对象

#### 5.14.1 `ScheduleSpec`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `kind` | string | 是 | `once / interval / cron` |
| `run_at` | datetime | 条件 | `once` 唯一时间，RFC 3339 UTC |
| `interval_s` | int | 条件 | `interval` 的正整数秒数 |
| `cron_expr` | string | 条件 | 五字段 POSIX cron，不含秒字段 |
| `timezone` | string | 条件 | `cron` 使用的 IANA timezone |
| `start_at` | datetime | 否 | 生效下界，RFC 3339 UTC |
| `end_at` | datetime | 否 | 失效上界，RFC 3339 UTC |
| `jitter_s` | int | 是 | 非负抖动秒数，默认显式写 `0` |

三个条件字段只允许与对应 kind 同时出现。StartupPlan 的 `recurring_job` 只允许 `interval` 或 `cron`；一次性任务创建 API 才允许 `once`。

`cron_expr` 只允许十进制数字、`*`、逗号、连字符和斜线，不支持昵称或秒字段。`interval_s` 必须大于 0；interval 的 `jitter_s` 必须小于 `interval_s`。

若同时给出时间边界，`end_at` 必须晚于 `start_at`。jitter 由 job id 与 occurrence 时间确定性生成，且不得把执行时间推过下一 occurrence。

cron 按 IANA timezone 计算后转换成 UTC occurrence。DST 不存在的本地时刻不生成 occurrence；重复的本地时刻按两个不同 UTC occurrence 处理。

#### 5.14.2 `MisfirePolicy`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | `skip / run_once / catch_up` |
| `grace_s` | int | 是 | 非负宽限秒数 |
| `max_catch_up` | int | 条件 | `catch_up` 时必填且大于 0 |

到期延迟不超过 `grace_s` 时正常执行。超过宽限后，`skip` 丢弃过期 occurrence，`run_once` 合并成一次，`catch_up` 按时间顺序补算但不超过 `max_catch_up`。

非 `catch_up` 模式不得携带 `max_catch_up`。处理完成后，`next_run_at` 必须指向下一次未来 occurrence。

#### 5.14.3 `RetryPolicy`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `max_attempts` | int | 是 | 总尝试次数，包含首次执行 |
| `backoff` | string | 是 | `none / fixed / exponential` |
| `initial_delay_s` | int | 是 | 非负首次重试延迟 |
| `max_delay_s` | int | 是 | 非负延迟上限 |
| `multiplier` | number | 条件 | exponential 时必填且大于 1 |
| `jitter_s` | int | 是 | 非负重试抖动秒数 |
| `retryable_error_codes` | string[] | 是 | 精确可重试错误码集合 |

`max_attempts = 1` 时必须使用 `none`，两个 delay 与 jitter 都为 0，错误码列表为空。`fixed` 不得声明 multiplier；所有非 `none` 策略必须满足 `max_delay_s >= initial_delay_s`。

只有列出的错误码可以重试，不支持通配符。非幂等 handler 必须把 `max_attempts` 固定为 1；需要幂等键的 handler 必须在创建 job 时持久化该键。

#### 5.14.4 `OverlapPolicy`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 是 | `skip / queue_one / allow` |
| `max_parallel` | int | 是 | 同一 concurrency key 的最大并行数 |
| `lock_ttl_s` | int | 是 | 正整数锁租约秒数 |

overlap 是同一 `concurrency_key_template` 展开值仍有 active run 时又产生 occurrence。`skip` 丢弃新 occurrence，`queue_one` 最多保留一个待执行 occurrence，`allow` 可并行到 `max_parallel`。

`queue_one` 保留最早待执行 occurrence，并累计 `coalesced_count`；后续重叠只更新合并计数，不再新增排队行。

`skip` 与 `queue_one` 必须使用 `max_parallel = 1`；`allow` 必须大于或等于 2。`lock_ttl_s` 必须大于 `max_runtime_s`，锁续租与失效都必须写审计。

concurrency key 必须在入队前由已校验 payload 展开。缺失模板变量或展开为空时，任务创建失败。

#### 5.14.5 求值顺序

每个 occurrence 固定按 `schedule -> misfire -> schedule jitter -> overlap -> execute -> retry` 处理。retry 不重新计算 schedule，也不生成新的 occurrence。

每次决策必须持久化原始 `scheduled_for`、实际 `run_after`、attempt、concurrency key 与采用的 policy 版本，保证重启后不会改变既有决定。

## 6. Handler 契约

### 6.1 统一输入

所有 registry handler 都接收统一上下文：

```python
handler(ctx, payload) -> HandlerResult
```

其中 `ctx` 至少暴露：

- `services`
- `logger`
- `audit`
- `event_collector`
- `now`
- `request_id` 或 `job_id`

### 6.2 `HandlerResult`

最小结构：

```json
{
  "status": "ok",
  "events": [],
  "audit_entries": [],
  "state_patches": []
}
```

`HandlerResult` 可选携带结构化 `value`。Rule 与 Render handler 的领域输出只能放在 `value`，且其 `events`、`audit_entries`、`state_patches` 必须为空。

规则：

- handler 只返回结构化结果，不直接写 socket
- handler 直接抛未分类异常时，由引擎包装成统一错误
- 领域事件与审计记录由运行时统一提交

## 7. `Blueprint` Schema

### 7.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `blueprint_key` | string | 是 | Blueprint 唯一键 |
| `kind` | string | 是 | `room/exit/item/npc/character_template/...` |
| `version` | string | 是 | 内容版本 |
| `parent_keys` | string[] | 否 | 继承父项，按顺序解析 |
| `source_type` | string | 是 | `file/db/converter` |
| `tags` | string[] | 否 | 标签 |
| `behavior_profile_keys` | string[] | 否 | authoring 阶段选择的行为 profile key |
| `spawn_policy` | object | 是 | 生成与同步策略 |
| `data` | object | 是 | 领域数据 |

### 7.2 约束

- `blueprint_key` 正则为 `^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$`，总长度必须为 3-128 个字符，并在一个实例与 MUDLib 内唯一
- 合法示例为 `room.xiangyang.east_gate`；连续点、首尾点或不满足分段首字母规则时统一返回 `BLUEPRINT_KEY_INVALID`
- `kind` 不允许在继承链中改变
- `behavior_profile_keys` 必须从 active registry 解析到 exact `BehaviorProfileDefinition` version/hash，并写入 `ResolvedRegistryDependency`
- kind schema 中的其他 registry key 字段也必须显式标记 RegistryRef；例如 Item `use_action_key` 与 `container_policy.accept_rule_key` 分别解析 ActionDefinition 与 RuleDefinition
- `spawn_policy` 不允许包含可执行代码
- `data` 必须通过 `kind` 对应 schema 校验
- `parent_keys` 构成的继承图必须是有向无环图
- 环检测必须覆盖候选批次与未变更 published revisions 合成后的完整继承图，并返回完整环路径

### 7.3 跨 Blueprint 引用

kind schema 必须显式标记哪些字段是 `BlueprintRef`。普通字符串即使形似 key，也不得被编译器猜测为引用。

`BlueprintRef` 最小结构：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `blueprint_key` | string | 是 | 符合 Blueprint key 正则的目标键 |
| `expected_kind` | string | 是 | 目标必须具有的 kind |

编译时的声明视图由本次候选 revisions 覆盖当前活动发布得到。引用可以指向同批候选项或候选映射复用的 published revision，但不得指向批次外 draft。

每个引用必须存在且 `kind` 匹配。kind schema 允许的普通 BlueprintRef 环由 SCC 绑定规则处理；只有 `parent_keys` 继承环一律拒绝。

候选映射的初始变更根包含选定 draft、显式删除、回滚造成的映射变化、`compiler_contract_version` 变化，以及规范化 `ResolvedRegistryDependency` 数组变化。

任一 compiler 实现或 kind schema 变化必须先提升 contract version；registry context 只由该 exact dependency 数组表达。

必须在当前与候选图的并集上，沿 parent、BlueprintRef 和 RegistryRef 反向边求传递依赖闭包。

affected closure 决定锁定与指针更新范围，不等于全部新建 revision。对闭包内每个 head，发布服务先选择 draft 或回滚候选 revision，再计算 reuse set 与 recompile set。

候选 published revision 只有在 raw `content_hash`、精确 `compiler_contract_version`、规范化 exact Blueprint dependency 数组与 exact registry dependency 数组均与最终上下文完全相同时，才进入 reuse set。其余保留项进入 recompile set。

raw 未变的派生项使用 `dependency_recompile`；回滚来源因上下文变化重编译时使用 `rollback_recompile`。

显式删除若仍被候选映射引用，发布必须失败。先为 recompile set 预分配 revision id，再按 parent DAG 编译；普通 BlueprintRef 环按强连通分量绑定预分配 id，不递归内联。

### 7.3.1 `ResolvedBlueprintDependency`

每个 published revision 必须为直接 parent 和 merge 后仍有效的全部 BlueprintRef 持久化 exact dependency record：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_revision_id` | UUID | 是 | 来源 published revision |
| `dependency_path` | string | 是 | RFC 6901 path；parent 使用稳定保留路径 |
| `dependency_kind` | string | 是 | `parent / blueprint_ref` |
| `ordinal` | int | 是 | 同一路径的稳定顺序 |
| `target_head_id` | UUID | 是 | 目标 Blueprint head |
| `target_revision_id` | UUID | 是 | 候选映射中的 exact published revision |
| `target_blueprint_key` | string | 是 | 冗余审计键 |
| `expected_kind` | string | 是 | 目标 kind |

source 与 target 都必须是 published revision，并属于同一 instance、MUDLib 与允许的 release scope。`UNIQUE (source_revision_id, dependency_kind, dependency_path, ordinal)` 防止重复；复合外键和 deferred trigger 必须证明 target 正是 source 创建批次候选映射中的 revision。

依赖行使用 `ON DELETE RESTRICT` 或等价约束保护历史 target。Entity、durable Effect、允许回滚批次或其他 published dependency 仍引用 revision 时，不得清理该 revision；必须先迁移或让全部引用退出保留范围。

### 7.3.2 `ResolvedRegistryDependency`

Blueprint schema 必须显式标记 registry key 字段。顶层 `behavior_profile_keys`、condition 的 EffectType 引用和 Item 的 `use_action_key` 都属于 RegistryRef；其他普通字符串不得被猜测为 registry 引用。

每个 published revision 必须为 merge 后仍有效的全部直接 RegistryRef 持久化 exact dependency record：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_revision_id` | UUID | 是 | 来源 published revision |
| `dependency_path` | string | 是 | RegistryRef 的 RFC 6901 path |
| `ordinal` | int | 是 | 同一路径的稳定顺序 |
| `registry_kind` | string | 是 | 目标 typed registry 类型 |
| `registry_key` | string | 是 | 目标 key |
| `registry_version` | string | 是 | 编译时解析的 exact SemVer |
| `definition_hash` | string | 是 | 包含 transitive registry 闭包的 exact hash |

`UNIQUE (source_revision_id, dependency_path, ordinal)` 防止重复。新建或修改内容只从 active registry 解析；历史 revision 按 exact kind/key/version/hash 从兼容目录读取。

发布校验必须证明记录与 compiled payload 逐项一致。`definition_hash` 已覆盖目标的 transitive registry 闭包，因此 rule、handler 或 callable artifact 变化也会改变编译上下文并进入反向依赖闭包。

只读兼容目录在任何 pinned revision、允许回滚批次或 durable 状态仍引用记录时不得移除对应定义及其 transitive artifacts。缺失时阻断启动，不得按裸 key 改用 active version。

### 7.4 Merge 规则

冻结规则如下：

- `parent_keys` 按声明顺序从左到右合并
- 后出现的 parent 覆盖先出现的 parent
- child 最后覆盖合并后的 parent 结果
- `object` 深合并
- `array` 默认整列替换，不做隐式 append
- `null` 只允许清空显式 nullable 字段，否则报错

这条规则要保持刻意保守，避免隐式合并把转换器与后台编辑都搞复杂。

### 7.5 `ConditionDefinition` 与 `EffectInstance`

`ConditionDefinition` 不是 typed registry entry，也不建立独立内容主表。它的内容真源是不可变的 `kind=condition` published `BlueprintRevision`。只读投影必须以 `revision_id` 为键，并可从 revision 完整重建。

活动 `ContentReleaseBatch` 只负责新选择、新 spawn 和 batch-scoped 请求。被 pinned Entity/Item、`EffectInstance`、exact dependency record 或允许回滚批次引用的历史 revision，仍是对应旧上下文的权威定义，不要求存在于当前活动批次。

`kind=condition` 的 Blueprint 使用顶层 `blueprint_key` 作为 condition key，`data` 最小字段如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `effect_type_key` | string | 是 | 已注册 `EffectTypeDefinition.key` |
| `effect_type_version` | string | 是 | 必须精确匹配注册条目的 SemVer |
| `parameters` | object | 是 | 通过对应 `payload_schema` 的完整参数 |
| `source_ref` | object | 否 | 转换来源文件、符号与位置 |

编译和发布 `ConditionDefinition` 时必须用 `effect_type_key + effect_type_version` 解析启动期 registry，并以该精确版本的 `payload_schema` 校验 `parameters`。解析失败、版本不匹配或参数不合法都阻断候选批次发布。

published condition 还必须在 `/data/effect_type_key` 写入 exact `ResolvedRegistryDependency`。运行时从该记录取得 EffectType version/hash 与 transitive handler 闭包，不得只信 raw key/version 后重新解析 active registry。

`ConditionDefinition` 禁止声明 `stacking_policy`、`tick_policy`、`persistence`、`recovery_policy`、rule 或 handler。叠加、tick、持久化、恢复和 handler 只来自解析后的 `EffectTypeDefinition`，不得由 Blueprint、转换器或 `EffectInstance` 覆盖。

每个 `EffectInstance` 必须以 `condition_definition_revision_id` 引用精确的 published `BlueprintRevision`。直接按 condition key 施加时，从当前请求固定的活动批次解析。

由 pinned Item、Skill 或其他 Blueprint revision 触发时，只能使用 source revision 的 exact dependency。不得拿旧 source revision 的 key 到新活动批次重新解析，也不得任意选择历史 revision。

活动批次变化后，已有实例仍保留原 condition revision。由历史 source revision 新触发的效果也继续使用它绑定的历史 condition revision，除非先通过受审计 migration 把 source 实例升级到新 revision。

`runtime_only` 实例只存在于单实例运行时，不建立数据库行。durable `EffectInstance` 的最小持久字段如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `effect_instance_id` | UUID | 是 | 效果实例 id |
| `condition_definition_revision_id` | UUID | 是 | 精确 published condition revision |
| `source_blueprint_revision_id` | UUID | 否 | 由版本化 Blueprint 触发时必填的 source revision |
| `source_dependency_path` | string | 否 | source revision 内触发本效果的 BlueprintRef path |
| `source_dependency_ordinal` | int | 否 | 同一路径依赖的稳定序号 |
| `effect_type_key` | string | 是 | 从 condition revision 复制的解析结果 |
| `effect_type_version` | string | 是 | 从 condition revision 复制的精确版本 |
| `subject_kind` | string | 是 | 挂载主体类型 |
| `subject_id` | string | 是 | 挂载主体 id |
| `source_ref` | object | 否 | 施加来源的稳定引用 |
| `payload_json` | object | 是 | 从 condition parameters 复制的已校验负载 |
| `stack_count` | int | 是 | 当前叠层，至少为 1 |
| `applied_at` | datetime | 是 | 首次应用时间 |
| `expires_at` | datetime | 否 | 无固定期限时为空 |
| `next_tick_at` | datetime | 否 | 无 interval tick 时为空 |
| `state` | string | 是 | `active / expired / removed` |
| `state_version` | int | 是 | 行锁之外的乐观并发版本 |
| `apply_idempotency_key` | string | 是 | 创建和首次 apply 的不可变去重键 |

持久行中的 EffectType key/version 是 condition revision 解析结果的受约束副本，只用于恢复校验和索引，不是第二个可独立修改的规则引用。数据库约束或 deferred constraint trigger 必须核对副本与 `condition_definition_revision_id` 的 compiled payload 一致，并保证 revision 为 `published` 且 `kind=condition`。

三个 source dependency 字段必须同时为空或同时有值。有值时，deferred constraint trigger 必须证明对应 `ResolvedBlueprintDependency` 为 `blueprint_ref`，且 target 正是 `condition_definition_revision_id`；不得只核对可漂移 key。

一个可变 `idempotency_key` 不能覆盖多次 tick、recover、expire 或 remove。每个生命周期操作必须引用 durable occurrence/run，或建立不可变 `EffectOperationRecord`。
该记录最小字段为 `effect_operation_id / effect_instance_id / operation_kind / operation_generation / scheduled_at / state / completed_at`，并具有 `UNIQUE (effect_instance_id, operation_kind, operation_generation)`。
同一操作的重试复用 generation，新 tick 或新一轮 recover 使用新 generation。操作记录与效果状态变化在同一事务提交，历史去重记录不得被后续操作覆盖。

### 7.6 Room/NPC 初始物化引用

`kind=room.data.spawn_entries`、`kind=room.data.external_exit_boundaries`、`kind=npc.data.skill_loadout` 与 `kind=npc.data.item_loadout` 都是必填数组。空集合必须规范化为 `[]`，不得依赖字段缺省值。

| 数组 | 字段 | 类型 | 约束 |
|------|------|------|------|
| `spawn_entries` | `spawn_entry_id` | string | 同一 Room head/Entity 生命周期内跨 revision 永久唯一且不可复用 |
| `spawn_entries` | `target_ref` | BlueprintRef | `expected_kind` 只能是 `npc` 或 `item` |
| `spawn_entries` | `count` | integer | 正整数 |
| `spawn_entries` | `lifecycle` | object | 首发只允许 `mode=initial_once` |
| `external_exit_boundaries` | `boundary_id` | string | 同一 Room revision 内唯一 |
| `external_exit_boundaries` | `direction` | string | 不可通行边界的规范方向 |
| `external_exit_boundaries` | `aliases` | string[] | 无重复方向别名 |
| `external_exit_boundaries` | `source_target_ref` | string | 原 Source LPC MUDLib 目标，仅供追踪 |
| `skill_loadout` | `skill_ref` | BlueprintRef | `expected_kind=skill` |
| `skill_loadout` | `level` | integer | 正整数 |
| `skill_loadout` | `jifa_slots` | string[] | 数组内及整个 loadout 内均不得重复 |
| `skill_loadout` | `prepare_enable_slot` | string/null | 非空时必须是本项 `jifa_slots` 中唯一的可准备用途槽 |
| `skill_loadout` | `combine_order` | integer/null | 只允许 `null / 1 / 2`，非空值不得重复 |
| `item_loadout` | `item_ref` | BlueprintRef | `expected_kind=item` |
| `item_loadout` | `quantity` | integer | 正整数且不得超过 exact Item definition 的 `max_stack` |
| `item_loadout` | `equip_slot` | string/null | 非空时在整个 loadout 内唯一 |

`prepare_enable_slot` 与 `combine_order` 必须同时为空或同时有值。`skill_loadout` 中同一 Skill head 只能出现一次；prepare enable slot 与 combine order 在整个数组内分别唯一。

发布必须按 exact Skill compiled definition 校验 `jifa_slots` 和准备用途，并按 14 号合同固定的 combine order 1 primary -> 2 combo 方向校验组合规则。

同一 actor 的 combine order 集合只允许 `[] / {1} / {1,2}`。删除 primary 而保留 combo 时，必须在同一事务把剩余 binding 压缩为 order 1。

`item_loadout.equip_slot` 非空时，`quantity` 必须为 1，且槽位必须等于 exact Item compiled definition 的非空 `equip_slot`。

上述三个数组中的 BlueprintRef 都进入 `ResolvedBlueprintDependency`。compiled payload 与依赖记录可保留 key 和 expected kind 供审计，但运行时身份只认 exact target head/revision id，禁止仅按 key 重新解析。

`kind=exit.data` 的最小字段为：

- `source_room_ref`：`expected_kind=room` 的 BlueprintRef
- `target_room_ref`：`expected_kind=room` 的 BlueprintRef
- `direction`：规范方向字符串
- `aliases`：无重复的 string[]
- `traversal_rule_key`：可选 RegistryRef -> `RuleDefinition`

Exit 的两个 Room ref 都进入 `ResolvedBlueprintDependency`，可选 rule 进入 `ResolvedRegistryDependency`。目标不在转换范围时不得生成猜测 Exit Blueprint，只记录 manifest 的不可通行 external boundary。

方向 token 统一执行 Unicode NFC、首尾空白去除与 Unicode casefold，并拒绝空值和控制字符。同一 source Room 下全部 Exit direction/aliases 与 `external_exit_boundaries` direction/aliases 必须全局互斥。

`StaticEntityBinding` 最小字段为 `instance_id / blueprint_head_id / blueprint_revision_id / entity_id / state_version`。

首发只允许 `kind=room` 与 `kind=exit` 使用 static binding。数据库必须保证 `UNIQUE (instance_id, blueprint_head_id)` 与 `UNIQUE (entity_id)`，并校验 head、published revision、Entity 的 instance/kind/revision 完全一致。

`StaticEntityBinding.entity_id` 使用 `ON DELETE RESTRICT`。Room/Exit 退出世界时先转为 `retired` tombstone；只有显式 decommission 且全部 Exit、spawn 与审计引用清退后，才能删除 binding 和 Entity，禁止级联。

`SpawnMaterialization` 最小字段为 `instance_id / room_entity_id / room_blueprint_revision_id / spawn_entry_id / ordinal / target_blueprint_revision_id / spawned_entity_id / state_version`。

数据库必须保证 `UNIQUE (room_entity_id, spawn_entry_id, ordinal)` 与 `UNIQUE (spawned_entity_id)`。`ordinal` 取 `0..count-1`；记录在目标死亡或移除后仍保留，因此 `initial_once` 不会在重启或 Room revision 迁移后重复生成。

同一 `spawn_entry_id` 跨 revision 必须保持 target Blueprint head 与 lifecycle 语义；target 身份或生命周期改变时必须使用新 id。某 id 从后续 revision 删除后也不得分配给不同逻辑刷点。count 可调整，但旧 ordinal 的 materialization 永不改写或复用。

`room_entity_id` 与 `spawned_entity_id` 都使用 `ON DELETE RESTRICT`。生成目标退出世界时，Entity 转为不可复活的 `retired` tombstone；只要 materialization 存在就不得物理删除或级联删除幂等记录。

INSERT constraint trigger 必须校验 Room 与 spawned Entity 属于同一 instance。Room 必须是 `kind=room` 且 pinned revision 等于记录值；entry 与 ordinal 必须存在于该 compiled revision，并满足 `ordinal<count`。

同一 trigger 还必须证明 `target_blueprint_revision_id` 是 entry exact dependency，spawned Entity 的 kind/revision 与该 target 完全一致，且其初始 `location_entity_id` 等于 Room。

`SpawnMaterialization` 创建后全部身份字段不可修改。上述 location/revision 一致性只证明初始物化事实；后续 Entity 移动、retire 或受审计迁移不得反向修改历史记录，也不再要求保持初始 location/revision。

world init 固定一次 active batch，先按 head 排序幂等创建缺失的 Room `StaticEntityBinding` 与 Entity，再创建 Exit binding 与 Entity。已有 binding 继续固定自身 revision，不因 active batch 变化移动。

Exit Entity 的 `location_entity_id` 是 exact source Room binding 的 Entity，`target_room_id` 来自 exact target Room binding。任一 Room binding 的 revision 与 Exit dependency 不一致时阻断创建，必须走协调迁移。

数据库必须保证同一 source Room 下 Exit `blueprint_head_id` 唯一，并对规范化 direction/aliases 与 Room external boundaries 执行上述互斥检查。Exit Entity 保存自身 exact Exit revision；external boundary 不创建 Exit Entity。

Exit 的 `location_entity_id / target_room_id / direction / aliases` 都是 pinned Exit compiled definition 的受约束投影，不得独立编辑。traversal rule 直接读取该 revision 的 exact registry dependency，不在 Entity 上建立第二份规则引用。

创建或迁移 Exit 时，deferred trigger 必须同时核对 static binding、exact Room dependencies 与全部投影字段。迁移在一个事务更新 revision 和投影；任一不一致都整体回滚。

Room/Exit 完成后，world init 按 pinned Room compiled `spawn_entries` 创建目标 Entity 与 `SpawnMaterialization`。若目标为 NPC，同一事务还按 pinned NPC loadout 创建 exact `ActorSkill / JifaBinding / PrepareBinding`、Item Entity 与必要的 `EquipmentBinding`。

任一 exact dependency 缺失、槽位冲突、数量非法或嵌套创建失败都必须回滚整个 spawn entry。首发 fixture 的 room materialization 失败必须阻断世界启动，不能回退到 active key 或跳过对象。

## 8. `CompiledBlueprint`

编译后的产物最少包含：

```json
{
  "blueprint_key": "room.xiangyang.east_gate",
  "kind": "room",
  "version": "1.2.0",
  "compiler_contract_version": "blueprint-compiler/1",
  "resolved_data": {
    "spawn_entries": [
      {
        "spawn_entry_id": "east_gate_guard",
        "target_ref": {
          "blueprint_key": "npc.xiangyang.east_gate_guard",
          "expected_kind": "npc",
          "resolved_head_id": "018f0000-0000-7000-8000-000000000003",
          "resolved_revision_id": "018f0000-0000-7000-8000-000000000004"
        },
        "count": 1,
        "lifecycle": {
          "mode": "initial_once"
        }
      }
    ],
    "external_exit_boundaries": []
  },
  "tags": [],
  "resolved_behavior_profiles": [],
  "spawn_policy": {
    "update_mode": "new_only"
  },
  "source_lineage": [
    {
      "blueprint_key": "room.base.city",
      "head_id": "018f0000-0000-7000-8000-000000000001",
      "revision_id": "018f0000-0000-7000-8000-000000000002"
    },
    {
      "blueprint_key": "room.xiangyang.east_gate",
      "head_id": "018f0000-0000-7000-8000-000000000005",
      "revision_id": "018f0000-0000-7000-8000-000000000006"
    }
  ],
  "resolved_dependencies": [
    {
      "source_revision_id": "018f0000-0000-7000-8000-000000000006",
      "dependency_path": "/parent_keys/0",
      "dependency_kind": "parent",
      "ordinal": 0,
      "target_head_id": "018f0000-0000-7000-8000-000000000001",
      "target_revision_id": "018f0000-0000-7000-8000-000000000002",
      "target_blueprint_key": "room.base.city",
      "expected_kind": "room"
    },
    {
      "source_revision_id": "018f0000-0000-7000-8000-000000000006",
      "dependency_path": "/resolved_data/spawn_entries/0/target_ref",
      "dependency_kind": "blueprint_ref",
      "ordinal": 0,
      "target_head_id": "018f0000-0000-7000-8000-000000000003",
      "target_revision_id": "018f0000-0000-7000-8000-000000000004",
      "target_blueprint_key": "npc.xiangyang.east_gate_guard",
      "expected_kind": "npc"
    }
  ],
  "resolved_registry_dependencies": [],
  "resolved_dependency_hash": "c149d5b1ba995d9a2e883e7d0e701255ab0eace1c4eeecc3a2485fa31f7ce7b5"
}
```

规则：

- 编译阶段已经完成 parent resolve、merge、normalize，并把每个有效 `BlueprintRef` 绑定到 exact head/revision id
- `source_lineage` 按实际 merge 顺序记录每个 parent 与当前 revision 的 exact id，不得只记录可漂移 key
- `resolved_dependencies` 与持久化依赖行逐项一致，覆盖直接 parent 和 merge 后仍有效的全部 `BlueprintRef`
- `resolved_behavior_profiles` 保存 exact key/version/definition hash；不得把 raw `behavior_profile_keys` 当运行时绑定
- `resolved_registry_dependencies` 与持久化 RegistryRef 依赖行逐项一致，definition hash 覆盖 transitive registry 闭包
- `resolved_dependency_hash` 对 Blueprint 与 registry 两类规范化 exact dependency 数组的固定对象计算
- `compiler_contract_version` 是 compiler 实现与全部 kind schema 的精确身份，冻结 merge、normalize 与引用绑定语义；任一实现或 schema 变化都必须升版，并重编译完整反向依赖闭包
- published 编译产物创建后不可更新；运行时 spawn、seed 与 pinned Entity/Item 只消费该产物及 exact dependencies
- 运行时不得按 Blueprint 或 registry 裸 key 重解释引用，也不得把 active context 的新 target 混入 pinned revision
- 原始 Blueprint、编译产物、依赖行与对应哈希必须都可审计

## 9. 校验错误模型

统一输出：

```json
{
  "code": "BLUEPRINT_KIND_MISMATCH",
  "severity": "error",
  "path": "parent_keys[1]",
  "blueprint_key": "room.xiangyang.east_gate",
  "source_key": "room.base.city",
  "message": "kind mismatch"
}
```

首批错误码：

- `BLUEPRINT_KEY_INVALID`
- `BLUEPRINT_DUPLICATE_KEY`
- `BLUEPRINT_PARENT_NOT_FOUND`
- `BLUEPRINT_INHERITANCE_CYCLE`
- `BLUEPRINT_KIND_MISMATCH`
- `BLUEPRINT_SCHEMA_INVALID`
- `BLUEPRINT_PROFILE_NOT_FOUND`
- `BLUEPRINT_REFERENCE_NOT_FOUND`
- `BLUEPRINT_REFERENCE_KIND_MISMATCH`
- `BLUEPRINT_REGISTRY_REFERENCE_NOT_FOUND`
- `BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE`
- `BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH`
- `BLUEPRINT_SPAWN_POLICY_INVALID`
- `BLUEPRINT_EDIT_CONFLICT`
- `CONDITION_EFFECT_TYPE_NOT_FOUND`
- `CONDITION_EFFECT_TYPE_VERSION_UNAVAILABLE`
- `CONDITION_PARAMETERS_INVALID`
- `EFFECT_CONDITION_REVISION_INVALID`
- `EFFECT_SOURCE_DEPENDENCY_INVALID`
- `CONTENT_RELEASE_VALIDATION_FAILED`
- `CONTENT_RELEASE_CONFLICT`
- `CONTENT_RELEASE_SCOPE_MISMATCH`

## 10. `BlueprintRevision`、`BlueprintHead` 与并发编辑

### 10.1 不可变 `BlueprintRevision`

draft 与 published revision 都是不可变快照。编辑 draft 不更新原行，而是创建新的 draft revision。发布也不改变 draft 状态，而是从选定 draft 创建新的 published revision。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `revision_id` | UUID | 是 | revision 唯一 id |
| `head_id` | UUID | 是 | 所属 `BlueprintHead` |
| `blueprint_key` | string | 是 | 冗余审计键，必须与 head 一致 |
| `revision_kind` | string | 是 | `draft / published`，创建后不可变 |
| `source_revision_id` | UUID | 否 | 编辑或发布来源 revision |
| `source_seed_bundle_id` | string | 否 | seed 导入来源 |
| `raw_payload` | object | 是 | 原始 Blueprint 快照 |
| `compiled_payload` | object | 否 | 校验通过的 `CompiledBlueprint` 快照 |
| `content_hash` | string | 是 | 仅覆盖规范化 `raw_payload` 的 SHA-256 |
| `compiled_hash` | string | 否 | 编译产物与两类 exact dependency 清单的 SHA-256 |
| `resolved_dependency_hash` | string | 否 | 两类规范化 exact dependency 数组的 SHA-256 |
| `compiler_contract_version` | string | 否 | published revision 必填的编译语义版本 |
| `publication_reason` | string | 否 | `seed_bootstrap / content_publish / dependency_recompile / rollback_recompile` |
| `created_in_batch_id` | UUID | 否 | 首次创建该 published revision 的批次 |
| `created_by` | string | 是 | 操作者或系统主体 |
| `created_at` | datetime | 是 | 创建时间 |

`revision_id` 是主键，`head_id` 是不可变外键。`BlueprintRevision` 还必须提供 `UNIQUE (revision_id, head_id)`，使 head 指针和 `ContentReleaseItem` 可以使用复合外键验证归属。

`(head_id, blueprint_key)` 必须以 deferrable 复合外键引用 `BlueprintHead(head_id, blueprint_key)`。`source_revision_id` 若存在，也必须通过 `(source_revision_id, head_id)` 引用同一 head 的 revision。

draft revision 的 compiled、dependency、compiler、publication 与 batch 字段必须为空。published revision 必须完整填写这些字段；`created_in_batch_id` 只表示首次创建批次，不表示 revision 只属于该批次。

`content_hash` 对 RFC 8785 规范化的 `raw_payload` 计算。Blueprint 依赖先按 kind 固定顺序 `parent / blueprint_ref`，再按 path 与 ordinal 排序；registry 依赖按 kind、key、version、path 与 ordinal 排序。

`resolved_dependency_hash` 对包含 `blueprint_dependencies` 与 `registry_dependencies` 的固定对象计算；两个数组都省略 `source_revision_id`。

`compiled_hash` 对包含完整 `compiled_payload` 与数据库两类 exact dependency 数组的固定 JSON 对象计算。payload 内清单、`resolved_dependency_hash` 与数据库记录必须一致。所有哈希均为小写十六进制 SHA-256。

draft preview 是针对显式 base batch 与 compiler contract 生成的临时产物，不写回 immutable draft。发布时必须在锁内针对候选完整映射重新编译，禁止把 preview 直接提升为 published payload。

后续 batch 只有在 raw `content_hash`、精确 `compiler_contract_version`、规范化 exact Blueprint dependency 数组与 exact registry dependency 数组均与最终候选上下文完全相同时，才可复用旧 published revision。任何 revision 都不得原地修改 payload、kind、hash、dependency、head 或首次创建批次。

Entity、durable Effect、exact dependency record 或允许回滚批次仍引用 historical revision 时，必须保留该 revision、编译产物和依赖行。清理任务不得只依据当前活动批次判断可删除性。

### 10.2 `BlueprintHead`

`BlueprintHead` 是每个 Blueprint 唯一的可变指针行，不承载 Blueprint payload。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `head_id` | UUID | 是 | head 主键 |
| `instance_id` | string | 是 | 实例 id |
| `mudlib_key` | string | 是 | MUDLib key |
| `blueprint_key` | string | 是 | Blueprint key |
| `draft_revision_id` | UUID | 否 | 当前 draft 指针 |
| `published_revision_id` | UUID | 否 | 配置的运行时发布流之活动 revision 便利指针 |
| `edit_version` | int | 是 | 从 1 开始单调递增的并发版本 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 最后指针更新时间 |

`head_id` 是主键；`(instance_id, mudlib_key, blueprint_key)` 必须唯一。为支持复合外键，还必须声明 `UNIQUE (head_id, blueprint_key)`。

`draft_revision_id` 和 `published_revision_id` 分别通过 `(revision_id, head_id)` 复合外键指向同一 head 的 revision。由于 head 与 revision 互相引用，这些外键必须是 `DEFERRABLE INITIALLY DEFERRED`。
提交时执行的 deferred constraint trigger 还必须验证 draft 指针只指向 `revision_kind=draft`，published 指针只指向 `revision_kind=published`。不能只依赖应用层检查。

`published_revision_id` 只镜像实例配置所选稳定发布流的活动 batch，不能作为运行时或 preview 的权威读取入口。若同一实例与 MUDLib 存在其他发布流，它们的映射只能从各自 `ContentReleaseHead.active_batch_id` 读取，且不得覆盖该便利指针。

### 10.3 并发编辑

创建、保存、导入或发布请求都必须携带 `expected_edit_version`。服务在事务内按 `(instance_id, mudlib_key, blueprint_key)` 排序后对 `BlueprintHead` 执行行锁，再比较版本。

版本不相等时返回 `BLUEPRINT_EDIT_CONFLICT`，不得创建 revision 或移动指针。版本相等时创建新 revision、更新相应指针，并把 `edit_version` 加一。

创建新 head 固定使用 `expected_edit_version=0`。服务必须在一个事务中插入 `edit_version=1` 的 head、首个 revision 与指针；若目标 head 已存在或唯一约束冲突，统一返回 `BLUEPRINT_EDIT_CONFLICT`。已有 head 不接受 expected version 0。客户端冲突后必须重新读取 head 与 diff 再提交。

### 10.4 回滚

回滚不是修改旧 revision，而是：

- 选择一个旧 `ContentReleaseBatch` 作为候选来源
- 从其中的 revisions 组成新的发布批次重新发布
- 输出批次级变更清单、校验结果与失败项

旧 revision、旧批次与历史指针记录都不修改。只有 raw `content_hash`、精确 `compiler_contract_version`、规范化 exact Blueprint dependency 数组与 exact registry dependency 数组均与最终候选上下文完全相同时，回滚 batch 才可复用旧 published revision；此前被删除的 head 也可重新指向该 revision。

上下文已变化时，必须以旧 raw payload 为来源执行完整闭包重编译，并创建 `publication_reason=rollback_recompile` 的新 revision。配置的运行时发布流按最终完整映射设置便利指针，不能为追求旧 id 而绕过当前校验。

## 11. 原子 `ContentReleaseBatch`

### 11.1 稳定发布流

`target_content_release` 是稳定发布流键。它存放在 `ContentReleaseHead`，同一流内的全部 batch 共享该值；不得把它用作 batch 唯一键或每次发布生成新值。

`ContentReleaseHead` 最小字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `release_head_id` | UUID | 是 | 发布流主键 |
| `instance_id` | string | 是 | 实例 id |
| `mudlib_key` | string | 是 | MUDLib key |
| `target_content_release` | string | 是 | manifest 声明的稳定发布流键 |
| `active_batch_id` | UUID | 否 | 当前活动批次 |
| `release_version` | int | 是 | 从 0 开始单调递增 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 最后活动指针更新时间 |

`release_head_id` 是主键，`(instance_id, mudlib_key, target_content_release)` 必须唯一。尚无活动批次的新流使用 `release_version=0` 和空 `active_batch_id`；第一次成功发布后版本变为 1。

`active_batch_id` 必须通过 `(active_batch_id, release_head_id)` 复合外键引用同一流的 batch。该外键是 `DEFERRABLE INITIALLY DEFERRED`，以便在同一事务创建首批 batch 并切换活动指针。

`release_version` 必须非负。deferred constraint trigger 必须保证 version 0 时活动指针为空；version 大于 0 时活动 batch 非空，且 batch 的 `release_version` 与 head 完全一致。

### 11.2 `ContentReleaseBatch`

`ContentReleaseBatch` 是某个稳定发布流内不可变的完整 Blueprint 内容快照。批次行只在发布事务提交后可见；失败尝试写审计记录，但不得留下半成品批次。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `batch_id` | UUID | 是 | 批次主键 |
| `release_head_id` | UUID | 是 | 所属稳定发布流 |
| `release_version` | int | 是 | 本流内发布版本，从 1 递增 |
| `parent_batch_id` | UUID | 否 | 发布前的本流活动批次 |
| `manifest_version` | string | 是 | 发布时 MUDLib 版本 |
| `source_seed_bundle_id` | string | 否 | seed 导入来源 |
| `release_hash` | string | 是 | 完整 item 与两类 revision hash 映射的 SHA-256 |
| `created_by` | string | 是 | 发布主体 |
| `created_at` | datetime | 是 | 发布时间 |

`batch_id` 是主键，`release_head_id` 外键指向 `ContentReleaseHead`，`release_version` 必须大于 0。必须声明 `UNIQUE (batch_id, release_head_id)` 与 `UNIQUE (release_head_id, release_version)`。

首批 batch 的 `parent_batch_id` 为空。后续 batch 的 parent 必须是发布事务开始时的活动 batch，并通过 `(parent_batch_id, release_head_id)` 复合外键引用同一发布流；跨流 parent 一律拒绝。batch 的 `release_version` 必须等于锁定的 head `release_version + 1`。

### 11.3 `ContentReleaseItem`

首发 `ContentReleaseItem` 只映射 Blueprint。Skill、Item 和 `ConditionDefinition` 都通过对应 `kind` 的 Blueprint 纳入；Help、公告或其他内容类型在扩展本契约前不得混入同一表。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `release_item_id` | UUID | 是 | 批次项主键 |
| `batch_id` | UUID | 是 | 所属批次 |
| `release_head_id` | UUID | 是 | 冗余发布流 id，用于复合外键 |
| `blueprint_head_id` | UUID | 是 | 所属 Blueprint head |
| `blueprint_key` | string | 是 | 冗余审计键，必须与 Blueprint head 一致 |
| `published_revision_id` | UUID | 是 | 该批次固定的 published revision |

必须建立以下约束：

- `(batch_id, release_head_id)` 复合外键引用 `ContentReleaseBatch`
- `(blueprint_head_id, blueprint_key)` 复合外键引用 `BlueprintHead`
- `(published_revision_id, blueprint_head_id)` 复合外键引用同一 Blueprint head 的 `BlueprintRevision`
- `UNIQUE (batch_id, blueprint_head_id)` 与 `UNIQUE (batch_id, blueprint_key)`
- deferred constraint trigger 校验 revision 为 `published`，且 Blueprint head 的 `instance_id / mudlib_key` 与 ContentReleaseHead 一致

这些约束必须在数据库层阻止跨实例、跨 MUDLib、跨发布流或跨 Blueprint head 串接。`BlueprintRevision.created_in_batch_id` 通过 deferrable 外键引用创建它的 batch。
同一 deferred constraint trigger 校验创建批次与 revision head 属于相同实例和 MUDLib。旧 published revision 可以出现在任意后续同流 batch 的 item 中，其 `created_in_batch_id` 保持不变。

每个 batch 的 items 是候选活动 Blueprint 映射的全集，不是只记录变更项。旧 revision 只有在 raw `content_hash`、精确 `compiler_contract_version`、规范化 exact Blueprint dependency 数组与 exact registry dependency 数组均与最终候选上下文完全相同时才可复用。

显式内容变更和 recompile set 中的派生项都引用本批次创建的新 revision。后者即使 raw payload 未变，也必须使用 `publication_reason=dependency_recompile`，不得复用过期编译产物。
删除内容表现为新批次完整映射中不再出现该 Blueprint，而不是修改旧 item。

### 11.4 `release_hash`

计算 `release_hash` 前，按 `blueprint_key` 的 UTF-8 字节升序排列全部 item。每项只包含 `blueprint_head_id`、`blueprint_key`、`published_revision_id`，以及 revision 的小写十六进制 `content_hash` 与 `compiled_hash`。
将完整数组按 RFC 8785 JSON Canonicalization Scheme 编码为无 BOM 的 UTF-8 字节；`release_hash` 是这些字节的 SHA-256 小写十六进制值。

batch id、发布时间、操作者和数据库行顺序不进入哈希输入。发布事务必须在切换活动指针前重算并核对 item 数量、唯一约束与 `release_hash`。

### 11.5 原子发布流程

发布预检必须分别展示显式变更、删除、affected closure、reuse set 和 recompile set。结果包含候选映射指纹、closure head 清单及其 `expected_edit_version`，不能把 raw 未变的派生重编译项隐藏为“未变更”。

发布请求必须携带稳定 `target_content_release`、`expected_release_version` 与候选映射指纹，并为每个 closure head 携带 `expected_edit_version`。显式内容变更还要携带选定 draft revision id。新发布流固定使用 `expected_release_version=0`。

1. 读取当前活动 batch，以其完整 items、候选 drafts、显式删除和回滚选择构造候选声明映射，不写数据库。
2. 在当前图与候选图的并集上校验 manifest、SemVer、registry definition hashes、schema、merge、继承 DAG 和 BlueprintRef SCC，并计算 affected closure、reuse/recompile sets 与候选指纹。
3. 开启 PostgreSQL 事务，先锁定或以 version 0 创建 `ContentReleaseHead`，再按 `(blueprint_key, head_id)` 排序锁定 affected closure 中的全部 `BlueprintHead`。
4. 在锁内重读活动 batch、声明与 registry catalog，重新计算 closure、reuse/recompile sets 与候选指纹。比较 release/edit versions、draft ids、内容哈希、两类依赖和 compiler contract；任一变化都返回 `CONTENT_RELEASE_CONFLICT`。
5. 为 batch 和 recompile set 中全部新 revision 预分配 id。按 parent DAG 编译；BlueprintRef SCC 只绑定预分配 id。每个 BlueprintRef 与 RegistryRef 必须解析到 exact target revision 或 kind/key/version/hash。
6. 生成每个新 revision 的三类哈希，插入 batch、新 revisions、`ResolvedBlueprintDependency` 与 `ResolvedRegistryDependency`。两类依赖行必须与编译产物逐项一致。

batch 版本使用锁定的 `ContentReleaseHead.release_version + 1`。
7. 为候选完整映射逐项创建 item。只有满足全部复用条件的项引用旧 revision；其余项引用本批次新 revision。计算并核对包含 `content_hash + compiled_hash` 的 `release_hash`。
8. 显式删除也属于 affected head。对实例配置所选运行时发布流，closure 内保留的 head 更新 `published_revision_id`，显式删除的 head 将其置空；只有这些已锁定 affected heads 递增 `edit_version`。

发布当前 draft 时同时清空对应 draft 指针。其他发布流不得覆盖便利指针，也不得更新未锁定 head。
9. 最后把 `ContentReleaseHead.active_batch_id` 切换到新 batch，并把 `ContentReleaseHead.release_version` 更新为 batch 版本。
10. 提交时执行全部 deferrable 外键与 constraint trigger；任一失败都回滚 batch、revision、dependency、item 和所有指针变更。
11. 仅在提交成功后刷新以 `batch_id` 为键的缓存、执行安全重载并发送发布事件。

发布失败审计必须在业务事务回滚后以独立审计事务记录，且不得伪装成成功的 `ContentReleaseBatch`。重试必须重新读取活动 batch 和所有 expected version，不能复用失败事务中的候选行 id。

### 11.6 一致性读取

batch-scoped 请求、job 或 preview 必须先固定 `(release_head_id, active_batch_id)`，再只读取该 batch 的完整 items。禁止逐条读取 `BlueprintHead.published_revision_id` 后拼成跨批次或跨发布流混合视图。

缓存键必须包含 `batch_id`。活动指针切换前预热的新缓存不可见，切换后的旧缓存只能服务已经固定旧 batch 的在途请求。

固定 `blueprint_revision_id` 的 Entity/Item 不重新查询 active context，只读取该 revision 的不可变编译产物、两类 exact dependencies 与兼容 registry catalog。派生读取停留在同一编译上下文，直到显式迁移。

durable Effect 始终读取自己的 `condition_definition_revision_id`。被引用的 historical revisions 必须可按 id 读取，不能因退出活动映射而删除或失效。

## 12. 发布与生效语义

### 12.1 发布后的影响范围

- `Admin preview` 固定明确的 base batch 后临时编译当前 draft，并与该 release head 的活动 revision 对比；临时产物不得回写 immutable draft
- 新 spawn 固定读取请求开始时的 `active_batch_id` 及其 revision 映射
- 已有 pinned Entity/Item 继续消费自身 revision 的不可变编译产物与 exact dependencies
- seed import 不直接进入运行时，只有显式发布成功后才成为活动内容
- 已加载的静态对象不会因发布自动移动 revision；只有显式 apply/migration job 可在安全重载窗口更新
- 玩家角色、活跃战斗对象、交易对象、任务上下文对象默认不自动被改写

### 12.2 `spawn_policy.update_mode`

冻结三档：

- `new_only`
  - 只影响未来新生成实例
- `sync_safe_fields`
  - 允许通过显式 apply job 同步非结构性字段
- `manual`
  - 必须走人工审核或迁移脚本

### 12.3 首版认定为“safe field”的范围

- `display_name`
- `desc`
- 非结构性展示标签
- 明确标记为非关键且不改变玩法逻辑的展示型数值

以下一律视为结构性字段，不在发布时自动改写：

- 房间出口
- 容器关系
- 掉落/刷新配置
- `behavior_profile_keys`
- 任何会影响玩法逻辑的数值或规则键

## 13. 审计要求

下列动作必须生成审计记录：

- seed bootstrap、seed import 与 bundle hash 冲突
- Blueprint 创建
- immutable draft revision 创建与 head 指针更新
- `expected_edit_version` 冲突
- Blueprint 校验
- `ContentReleaseBatch` 发布尝试、成功与失败
- 发布预检产生的反向依赖闭包、复用判定和候选映射指纹
- registry definition hash 冲突、兼容目录缺失与 RegistryRef 迁移
- Blueprint 回滚
- apply job 执行
- durable Effect 恢复、过期与补算截断
- job 重试、misfire、overlap 处理与锁租约失效
- registry 注册失败导致的启动终止

## 14. 实施要求

`Engine Stage E0` 开工前，至少要把以下内容同步成代码 schema、dataclass 或常量：

- manifest schema
- SemVer 与版本范围 parser 及正反测试向量
- typed registry schema
- typed registry 激活版本与只读 recovery/validation catalog
- registry definition hash、引用图闭包校验器与构建制品哈希
- schedule、misfire、retry 与 overlap policy schema
- `Blueprint` schema
- `CompiledBlueprint` schema
- compiler contract version、三类 revision hash 与反向依赖闭包编译器
- `ResolvedBlueprintDependency` schema、复合外键、保留策略与闭包测试
- `ResolvedRegistryDependency` schema、兼容目录、反向索引、保留策略与 pinned runtime 测试
- `kind=condition` schema、精确 EffectType 解析与参数校验
- `BlueprintRevision` 状态枚举
- `BlueprintHead` 主键、deferrable 归属约束、`expected_edit_version` 与行锁编辑服务
- `ContentReleaseBatch / ContentReleaseItem / ContentReleaseHead` 完整约束、派生重编译预检、release hash 与原子发布服务
- seed bootstrap、draft import、diff 与显式发布服务
- durable Effect 精确 revision 恢复、`EffectOperationRecord` 与幂等测试
- registry / blueprint 校验错误码
