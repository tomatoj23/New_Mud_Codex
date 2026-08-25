# 14 数据库模型与序列化分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前领域术语，以 `requirements_v6.md` 第八章与根目录 `CONTEXT.md` 为权威；`UBIQUITOUS_LANGUAGE.md` 仅作非权威工程术语索引，`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 核心模型：
  - `evennia-main/evennia/typeclasses/models.py`
  - `evennia-main/evennia/objects/models.py`
  - `evennia-main/evennia/accounts/models.py`
  - `evennia-main/evennia/scripts/models.py`
  - `evennia-main/evennia/comms/models.py`
  - `evennia-main/evennia/help/models.py`
  - `evennia-main/evennia/server/models.py`
- 序列化：
  - `evennia-main/evennia/utils/dbserialize.py`
- 数据库选型文档：
  - `evennia-main/docs/source/Setup/Choosing-a-Database.md`

## 2. Evennia 源码事实

### 2.1 主体策略是薄主表 + 动态扩展

Evennia 的数据库策略不是给每种游戏概念建很多表，而是：

- 核心实体主表尽量薄
- 扩展数据交给 Attribute / Tag
- 行为交给 typeclass

典型例子：

- `ObjectDB` 只保存位置、home、destination、account、sessid 等少量结构字段
- `ScriptDB` 以调度字段为核心，同时保存附着对象/账号与描述
- `AccountDB` 在 `TypedObject + AbstractUser` 基础上补充 `db_is_connected`、`db_is_bot`、`db_cmdset_storage` 等在线与命令相关字段

### 2.2 多个核心表围绕 `TypedObject` 展开

主要的 typed tables 有：

- `AccountDB`
- `ObjectDB`
- `ScriptDB`
- `ChannelDB`

这些表共享统一的：

- key
- typeclass path
- locks
- attributes
- tags

### 2.3 非 typed 内容模型也大量依赖通用存储

还有几类非 typeclass 核心表：

- `Msg`
- `HelpEntry`
- `ServerConfig`
- `Attribute`
- `Tag`

其中 `ServerConfig` 是全局 key-value 存储；`Attribute` 和 `ServerConfig` 都会走 pickle/自定义序列化。

### 2.4 `dbserialize.py` 是属性层关键基础设施

`dbserialize.py` 负责解决：

- 任意 Python 对象如何存进去
- 数据库对象引用如何安全回写
- 嵌套 mutable 修改如何自动保存

为此它引入了 packed object / saver mutable 机制。

### 2.5 SQLite 是默认数据库，但不是固定的开发环境数据库

Evennia 默认配置使用 SQLite，并说明它对许多游戏已经足够。文档同时指出 PostgreSQL 在更高并发和数据规模下更有扩展优势，但没有规定“开发必须用 SQLite、生产必须用 PostgreSQL”的环境划分。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 游戏内容扩展很快，迁移成本低。
- Builder 驱动开发时，不用频繁改表。
- 统一实体模型让接口和管理方式比较一致。
- SQLite 默认开箱即用，而 PostgreSQL 为更高并发和数据规模提供更强的扩展空间。

### 3.2 不适合本项目的点

- 大量核心状态放进 Attribute / pickle 后，可查询性、可约束性和可迁移性都会变差。
- packed / unpacked 机制说明持久化模型与领域模型并不贴合。
- 过多 M2M + 泛属性会让报表、索引优化、数据修复和转换器目标建模更困难。
- 对转换器来说，目标数据模型必须稳定、可验证、可导入，不能过度依赖运行时魔法。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，更合理的数据模型方向是：

- 显式核心表
- JSON 扩展层
- 版本化序列化
- 运行时概念与持久化概念分离
- PostgreSQL 作为开发、测试与生产环境的统一数据库
- SQLite 仅用于个人实验，不进入共享开发、测试或生产基线

`AuthSession` 是数据库持久化实体，其数据库记录是认证会话的事实源。`ConnectionSession` 与 `Presence` 只存在于运行时；`PresenceSnapshot` 仅用于短时持久化恢复，不取代实时 `Presence`。

`Entity`、`Blueprint`、聊天模型、帮助模型等应使用清晰、可查询、可迁移的稳定表结构。

### 4.2 对应的权威文档

- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- `docs/new_engine/09_MUDLIB_CONVERTER.md`
- `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
- `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
- `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`

## 5. 结论

Evennia 的数据库设计适合快速原型和 Builder 驱动内容生产，但不适合作为 New_Mud 的最终生产级数据模型。分析层对应的结论是采用“显式核心表 + JSON 扩展层 + 版本化序列化”的方向，在保留灵活性的同时获得查询、约束和迁移可控性。

