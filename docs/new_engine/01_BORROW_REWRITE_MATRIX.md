# 01 Borrow / Rewrite 决策矩阵

> 术语说明：讨论 Evennia 来源时可保留源术语；讨论 New_Mud 设计时，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

> 实施约束：战斗、武学、物品与 Effect 持久化边界，以 `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 为准。

## 1. 结论先行

对 New_Mud 来说，Evennia 不能“整套搬运”，但也绝不是只能参考概念。更准确的做法是：

- 直接照搬少数成熟抽象与 hook 顺序。
- 保留核心思想，但彻底重写运行时与持久化实现。
- 明确放弃那些为 telnet/Twisted/高度动态运行时服务的设计。

## 2. 可直接借鉴，接近照抄

### 2.1 命令生命周期

源码依据：

- `evennia-main/evennia/commands/command.py`
- `evennia-main/evennia/commands/cmdparser.py`

建议直接借鉴的内容：

- `Command` 的生命周期顺序：`at_pre_cmd -> parse -> func -> at_post_cmd`
- 命令元数据：`key / aliases / help_category`
- 多词命令优先匹配、最长命令优先匹配
- 文本多重匹配消歧，例如 `2-ball`

### 2.2 房间移动 hook 顺序

源码依据：

- `evennia-main/evennia/objects/objects.py` 中的 `move_to`

建议直接借鉴的内容：

- 移动前校验顺序
- 离开/进入消息触发顺序
- `at_pre_move / at_object_leave / at_object_receive / at_post_move` 这套 hook 语义

### 2.3 外观渲染流水线

源码依据：

- `evennia-main/evennia/objects/objects.py` 中的 `return_appearance`

建议直接借鉴的内容：

- `appearance_template`
- `get_display_name / desc / exits / characters / things / footer`
- “先分块构造，再统一 format”的渲染方式

### 2.4 File help 的装载思路

源码依据：

- `evennia-main/evennia/help/filehelp.py`

建议直接借鉴的内容：

- 文件帮助条目与数据库帮助条目并行存在
- 文件帮助条目可以走 Python dict 或模块注册
- 帮助系统对象与 Web/命令系统复用同一接口

## 3. 保留思想，重写实现

### 3.1 Typeclass / TypedObject

源码依据：

- `evennia-main/evennia/typeclasses/models.py`
- `evennia-main/evennia/objects/models.py`

保留：

- 统一实体根
- 统一标签、权限、帮助、内容挂载思路

重写：

- 不再通过 `set_class_from_typeclass()` 动态改写 `__class__`
- 不再依赖 Django proxy model 组合 typeclass
- 类型由 `kind + blueprint + BehaviorProfileDefinition` 决定
- `BehaviorProfileDefinition` 必须通过受控 registry 注册，而不是自由引用任意 class path

### 3.2 Attributes / db / ndb

源码依据：

- `evennia-main/evennia/typeclasses/attributes.py`

保留：

- 对象可以有扩展属性槽位

重写：

- 核心状态显式建模
- 扩展状态用 `JSONField/JSONB` 或组件表
- 不允许 Attribute 成为默认主存储

### 3.3 CmdSet 合并

源码依据：

- `evennia-main/evennia/commands/cmdset.py`
- `evennia-main/evennia/commands/cmdhandler.py`

保留：

- 动作可来自连接上下文、角色、房间、物品等多个来源

重写：

- 用 `ActionProvider + ResolvedActionSet` 替代 `CmdSet` 原样合并
- 文本命令只是动作入口之一

### 3.4 Scripts / Tickers / Tasks

源码依据：

- `evennia-main/evennia/scripts/scripts.py`
- `evennia-main/evennia/scripts/taskhandler.py`
- `evennia-main/evennia/scripts/tickerhandler.py`
- `evennia-main/evennia/scripts/ondemandhandler.py`

保留：

- 一次性任务、周期任务、阶段任务三类问题分解

重写：

- `ScheduledJob / RecurringJob` 建立持久任务记录：主记录保存精确的 `job_type_key + job_type_version`、payload、schedule、`next_run_at`、state、concurrency key、lease owner/expiry 与 state version；occurrence、run、attempt 分别保留不可变执行历史
- 只有 `persistence=durable` 的 `EffectInstance` 建立效果主记录：保存精确的 `condition_definition_revision_id`，并校验由该 revision 解析出的 `effect_type_key + effect_type_version`，同时持久化 source、target、payload、timing、stack、state 与 state version
- 两类持久记录都只引用受控 typed definition 与结构化 payload，不持久化 Python callback、lambda 或可执行代码
- `CombatInstance / CombatLoop / RuntimeTimer`、战斗节拍、短期 `busy` 与 `runtime_only EffectInstance` 只存在于单实例运行时
- `WorldProcess` 通过启动计划注册运行时过程；需要跨重启的数据必须另建显式领域状态，不自动获得通用持久化主记录

### 3.5 Session / Puppet

源码依据：

- `evennia-main/evennia/server/session.py`
- `evennia-main/evennia/server/serversession.py`
- `evennia-main/evennia/accounts/accounts.py`

保留：

- 区分连接、认证会话、角色控制关系

重写：

- `ConnectionSession -> AuthSession -> Presence`
- 单逻辑 runtime 统一持有，不做 Portal/Server 双边同步
- 当前基线按单实例单写者实现；若未来确实需要进程拆分，再补显式协调机制

### 3.6 Channel / Msg

源码依据：

- `evennia-main/evennia/comms/models.py`
- `evennia-main/evennia/comms/comms.py`

保留：

- 频道与订阅分离
- 持久消息记录作为独立能力参考

重写：

- 拆分 `ChatChannel / ChatSubscription / ChatMessage / DirectMessage / SystemNotice`
- 聊天入口以结构化 WebSocket 事件为主

## 4. 明确放弃

### 4.1 Portal / Server 双进程

源码依据：

- `evennia-main/evennia/server/service.py`
- `evennia-main/evennia/server/portal/service.py`
- `evennia-main/evennia/server/evennia_launcher.py`

放弃原因：

- 本项目主协议是 WebSocket，不需要 Portal 为 telnet/ssh 做隔离
- 双进程只会放大会话同步、故障恢复、部署与日志复杂度

### 4.2 Lockstring 作为核心权限模型

源码依据：

- `evennia-main/evennia/locks/lockhandler.py`

放弃原因：

- lockstring 很灵活，但太依赖字符串 DSL
- 不适合作为后台角色权限、审计、安全风控的核心表达

### 4.3 DRF 直暴露底层 typeclass 模型

源码依据：

- `evennia-main/evennia/web/api/views.py`
- `evennia-main/evennia/web/api/serializers.py`

放弃原因：

- 游戏前端需要的是业务域 API，不是“底层对象库遥控面板”

## 5. 首批实现时可直接对照的 Evennia 代码

- `commands/command.py`
- `commands/cmdparser.py`
- `objects/objects.py::move_to`
- `objects/objects.py::return_appearance`
- `help/filehelp.py`
- `prototypes/prototypes.py::homogenize_prototype`

## 6. 最终原则

真正应该“照抄”的不是 Evennia 的运行框架，而是它少数经过长期验证的抽象接口和 hook 顺序。真正必须“重写”的，是那些让这些抽象成立的旧运行时实现。


