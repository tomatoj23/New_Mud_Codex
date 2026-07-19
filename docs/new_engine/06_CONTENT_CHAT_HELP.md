# 06 内容系统、聊天系统与帮助系统

> 术语说明：New_Mud 设计层统一使用 `Blueprint` 与 `ActorRef`；`Prototype` 仅作为 Evennia 来源名词出现。

> 实施约束：本文负责解释内容、聊天、帮助三域的关系；凡涉及 `Blueprint` schema、`BlueprintRevision`、发布状态、发布/生效边界与 `spawn_policy.update_mode`，以 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 为准。

## 1. 为什么把这三者放在一起

它们在 Evennia 中分别存在于 `prototypes / comms / help`，但对 New_Mud 来说都属于“内容制作与运营交付面”：

- Blueprint 决定世界内容如何生成
- Chat 决定玩家如何交流与接收系统信息
- Help 决定玩家和运营如何理解这些内容

## 2. Blueprint 系统

### 2.1 借鉴来源

- `evennia-main/evennia/prototypes/prototypes.py`
- `evennia-main/evennia/prototypes/spawner.py`

### 2.2 Evennia 值得保留的点

- Evennia 源码中这一层叫 `Prototype`
- 原型可继承
- 原型可标准化 `homogenize_prototype`
- 原型可从代码模块或数据库加载
- 原型可带 meta 信息，例如 tags、locks、desc

### 2.3 New_Mud 改造方向

原型不再叫 prototype，统一叫 `Blueprint`：

- `blueprint_key`
- `kind`
- `parent_keys`
- `source_type`
- `data`
- `tags`
- `behavior_profile_keys`
- `spawn_policy`
- `version`

推荐支持三种编辑或导入输入：

- MUDLib 包内的 Blueprint seed 文件
- 转换器生成的 Blueprint seed 产物
- Admin 写入 PostgreSQL 的 draft revision

包内文件和转换器产物不是运行时内容真源。PostgreSQL 的 immutable published revisions 与 exact dependency records 是内容真源；active batch 只为新选择和 batch-scoped 请求提供映射。

pinned Entity/Item 与 durable Effect 继续按自身 exact revision 读取历史编译上下文，不能被当前 active batch 改写。

### 2.4 Seed provider 与启动边界

MUDLib 通过 `register_blueprint_seed_providers(registry)` 注册受控 seed provider；该入口只产生导入输入，不注册运行时 Blueprint。

仅当精确 `(instance_id, mudlib_key)` namespace 内既无任何 `BlueprintHead`，也无活动 `ContentReleaseBatch` 时，才允许一次受审计的 seed bootstrap 建立首个原子发布批次。该 namespace 非空时，普通启动不得用包内文件或 seed 覆盖 draft、published revision 或活动发布指针；其他实例或 MUDLib 的数据不影响本 namespace 判定。

该 `(instance_id, mudlib_key)` namespace 非空时，导入新 seed 必须创建新的 immutable draft revisions，生成相对当前 active batch published revisions 的 diff，再由有权限的操作者显式发布。

### 2.5 Blueprint 编译流程

```text
seed input / admin edit
  -> immutable draft revision
  -> schema validate
  -> parent resolve
  -> merge
  -> normalize
  -> compile
  -> admin preview / diff
  -> atomic ContentReleaseBatch publish
  -> runtime spawn from active batch CompiledBlueprint
```

### 2.6 `BlueprintRevision` 与发布

首版冻结为：

- immutable `draft revision`
- immutable `published revision`
- mutable `BlueprintHead` 指针
- atomic `ContentReleaseBatch`

补充约束：

- 校验是发布前检查，不单独冻结为持久化状态
- 编辑创建新的 draft revision，并通过并发版本移动 `BlueprintHead.draft_revision_id`
- 发布从选定 draft 创建新的 published revision，不修改原 draft
- draft 只供编辑、预览与发布输入，绝不能直接成为运行时内容
- 新 spawn 与 batch-scoped 读取先固定活动 `ContentReleaseBatch`，再消费其完整 published revision 映射
- pinned 实例只消费自身 revision 的 immutable `CompiledBlueprint` 与 exact dependencies
- 回滚按发布批次进行；若需要恢复旧内容，应基于旧 revision 重新发布新批次，而不是原地改旧记录
- 后台预览可读取当前 draft 编译产物，并可对比当前 published revision
- 现存世界实例默认不因发布而被静默重写

发布顺序冻结为：

1. 开启事务前，以当前活动 batch、选定 drafts 与显式删除构造完整候选映射，计算 parent、BlueprintRef 与 RegistryRef 的反向依赖闭包，并完成 schema、引用、diff、全量校验与编译。

任一失败都不得进入发布事务。
2. 发布预览必须展示显式变更与 dependency-recompile 项。开启 PostgreSQL 事务后先锁定或创建 `ContentReleaseHead`，再按稳定顺序锁定闭包内全部 `BlueprintHead` 行。
3. 持锁重新读取 active batch、expected versions、draft ids、内容哈希、精确 compiler contract、两类 exact dependencies 与 registry definition hash；重建候选映射和闭包，重新校验最终 `release_hash`，冲突时整体失败。
4. 在同一事务内为显式变更与依赖重编译项创建 immutable published revisions 和 exact dependency records，写完整 `ContentReleaseBatch / ContentReleaseItem` 映射；最后切换活动指针与 release version。
5. 提交时校验全部延迟约束；任一步失败都回滚 revision、batch、items 和指针。只有提交成功后才能刷新缓存、安全重载和发送发布事件。

### 2.7 明确不保留

- 原型里的任意 `exec` 代码
- 用 lockstring 保护 Blueprint 编辑权限
- 用 prototype 直接承载大量未结构化业务数据

## 3. 聊天系统

### 3.1 借鉴来源

- `evennia-main/evennia/comms/models.py`
- `evennia-main/evennia/comms/comms.py`

### 3.2 保留的核心抽象

- `Channel`
- `Subscription`
- 持久消息记录

### 3.3 拆分后的子域模型

- `ChatChannel`
  - world / guild / team / system / arena
- `ChatSubscription`
  - 成员、mute、role、last_read
- `ChatMessage`
  - 正常频道消息
- `DirectMessage`
  - 私聊
- `SystemNotice`
  - 公告、系统推送、维护通知

这里要明确区分来源事实与新设计：

- 在 Evennia 6.0 当前核心里，频道发送主路径更接近“订阅分发 + 日志”，不是“频道消息先落 `Msg` 再广播”。
- `Msg` 更适合作为持久消息骨架的参考来源，而不是当前频道系统的真实等价物。
- `ChatMessage` 因而是 New_Mud 的主动设计增强，用来服务未读、审核、检索和移动端留存需求，不应表述成对 Evennia 现状的原样照搬。

### 3.4 统一发言者

不要让账号、对象、脚本、外部字符串都直接成为消息主体。

建议统一成：

- `ActorRef`
  - `game_account`
  - `character`
  - `system`
  - `npc`

`SpeakerRef` 不再作为并行术语保留。

### 3.5 首发与后续边界

- 频道发言频率限制 / 防刷屏策略
- 公共聊天与房间可见消息
- 私聊
- 未读状态
- 消息审核钩子
- 审计日志

帮派频道、队伍消息与 XKX100 完整频道系统属于后续内容扩展，不是首发闭环前置。首发可以保留受控频道类型扩展点，但不得把未实现的帮派或组织消息链标为已支持。

## 4. 帮助系统

### 4.1 借鉴来源

- `evennia-main/evennia/help/models.py`
- `evennia-main/evennia/help/filehelp.py`

### 4.2 三类帮助来源

以下三个名词当前以 `requirements_v5.md` 第八章、`UBIQUITOUS_LANGUAGE.md` 与本目录相关设计文档中的约束为准；其中 `UBIQUITOUS_LANGUAGE.md` 负责术语统一，不单独决定帮助子域分类：

- `CommandHelp`
  - 从动作元数据生成
- `FileHelp`
  - 来自 MUDLib 文档文件
- `DbHelp`
  - 来自后台内容编辑

### 4.3 统一索引

统一搜索索引字段：

- `key`
- `aliases`
- `category`
- `text`
- `tags`
- `visibility_policy`
- `source_type`

### 4.4 帮助权限

帮助系统的权限不应再走通用 lockstring，而应走显式策略：

- 游客可见
- 登录可见
- 门派成员可见
- GM 可见

## 5. 后台内容工作流

后台必须支撑以下流程：

1. 编辑 Blueprint
2. 校验 Blueprint
3. 预览生成结果
4. 显式提交 Blueprint 原子发布批次
5. 生成/更新世界实例
6. 维护帮助条目
7. 管理频道、公告和系统文案

其中第 5 步必须受 `spawn_policy.update_mode` 约束：

- `new_only`
- `sync_safe_fields`
- `manual`

## 6. 内容发布与生效边界

根据 `requirements_v5.md`：

- V1 以冷发布为默认策略
- 代码更新统一通过重启发布
- 不支持整包 MUDLib 热切换
- 已加载活体实例不做实例级自动热同步

因此建议：

- Blueprint、Help、公告都属于“可发布数据”，但首发 `ContentReleaseBatch` 只冻结 Blueprint 的完整 revision 映射
- Help 与公告必须走各自独立的版本化、审计发布流程并通过安全重载生效；只有先在 `12` 扩展 typed `ContentReleaseItem` 契约后，未来才能纳入同一原子批次
- 新选择与 batch-scoped 读取只消费活动批次映射；pinned 实例继续消费自身 published revision 的编译产物
- 两条路径都不直接消费 draft，也不回读包内 seed 文件
- 规则注册代码、MUDLib Python 逻辑始终作为冷更新代码

进一步冻结：

- `Blueprint` 发布默认只影响发布后从活动批次执行的新 spawn
- 首发 `ContentReleaseBatch` 仅对 Blueprint 原子完成全部校验、revision 写入和指针切换，失败时不得部分生效
- 现存实例若要同步，只能执行受审计的显式 apply/migration job；该 job 可以安排在安全重载窗口内，但安全重载本身不得选择、迁移或改写任何实例 revision
- 房间出口、掉落/刷新配置、`behavior_profile_keys` 等结构性字段不在发布时自动改写

## 7. 与转换器的衔接

LPC 转换器输出的第一目标不是 Python 类，而是：

- Blueprint
- Help Markdown
- startup plan
- unresolved report

转换器和 seed provider 只能把 Blueprint 输入导入为 draft revisions；未经显式原子发布，不得进入运行时活动内容。

## 8. 最终原则

内容系统要优先服务“可制作、可审核、可转换”，而不是优先服务运行时魔法。

