# 02 对象系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前领域概念，以根目录 `CONTEXT.md` 为词汇权威；产品范围和产品语义以 `requirements_v6.md` 为权威，其中身份产品语义见第八章；`UBIQUITOUS_LANGUAGE.md` 仅作非权威工程术语索引。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/objects/models.py`
  - `evennia-main/evennia/objects/objects.py`
  - `evennia-main/evennia/objects/manager.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Objects.md`

## 2. Evennia 源码事实

### 2.1 `ObjectDB` 是极简世界骨架

`ObjectDB` 在 `TypedObject` 基础上补充少量世界结构字段：

- `db_account`
- `db_sessid`
- `db_location`
- `db_home`
- `db_destination`

这体现出 Evennia 对世界模型的基本判断：MUD 世界本质上是一个“可定位实体图”。

### 2.2 `ContentsHandler` 负责热点缓存

`models.py` 里的 `ContentsHandler` 会缓存对象 contents，并额外按 content type 建索引。命令系统、房间渲染和移动判定都会高频读取这些数据。

### 2.3 `DefaultObject` 是运行时内核

`objects.py` 里的 `DefaultObject` 承担了大量运行时能力：

- 生命周期钩子
- `search`
- `msg`
- `execute_cmd`
- `move_to`
- `return_appearance`
- contents / exits / aliases / nicks / scripts / cmdset
- 锁检查和感知逻辑

它不只是数据模型，而是一个“游戏对象运行时框架”。

### 2.4 `Character / Room / Exit` 在对象层特化

Evennia 在 `DefaultObject` 上继续派生：

- `DefaultCharacter`
- `DefaultRoom`
- `DefaultExit`

其中 `DefaultExit` 还带有 `ExitCommand`，说明出口在 Evennia 里不只是连接数据，也是命令入口。

### 2.5 展示职责也落在对象层

`look` 最终落在 `return_appearance` 及其辅助 hook 上。对象自己决定名称、描述、出口、角色和物品如何显示。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 世界万物统一建模，心智模型很强。
- `location / home / destination` 这套极简骨架适合房间式 MUD。
- `move_to` 和 `return_appearance` 体现出很成熟的 hook 顺序。
- 高级对象特化方式对 Room / Exit / Character 这些常见实体很自然。

### 3.2 不适合本项目的点

- `DefaultObject` 过于巨大，领域行为、通信、展示、命令入口都堆在一起。
- `db_account / db_sessid` 直接挂在对象上，会把世界实体和在线连接态耦合起来。
- 出口通过命令参与系统，对 Web / API 客户端并不自然。
- 对象层直接生成文本展示，不利于 uni-app 做结构化渲染。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，可保留的核心方向是：

- 统一实体根
- 世界图关系
- 移动与外观的成熟 hook 语义

对应到权威设计层，后续实现已转向：

- `Entity` + 专属子模型
- 连接态从对象层拆出到 `Presence`
- 领域服务负责移动、观察、拾取和交互
- 前端输出优先结构化 view model，而不是对象直接拼文本

### 4.2 对应的权威文档

- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`
- `docs/new_engine/05_COMMAND_INTERACTION.md`

## 5. 结论

Evennia 对象系统最值得保留的是“世界万物统一建模”和“位置关系极简骨架”。最需要替换的是把会话、命令、展示和领域行为都塞进单个巨型对象类的做法。分析层对应的方向摘要是“实体模型 + 关系模型 + 领域服务”三层。


