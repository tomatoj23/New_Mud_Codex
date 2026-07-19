# Evennia 源码分析完成记录（分析层入口）

> 状态：分析层入口文档。`docs/00-18` 主要用于记录 Evennia 6.0 本地源码事实、模块优缺点与研究过程中的初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

## 当前权威说明

- 自 2026-03-20 起，`docs/00-18` 统一归类为分析层文档。
- New_Mud 当前正式设计、模块边界、实施路线与开发顺序，以 `docs/new_engine/` 为准。
- `docs/16-18` 保留为“分析派生的综合判断 / 边界研究 / 问题分析”文档，继续作为研究依据，但不再单独作为权威规范。

## 记录时间

- 完成日期：2026-03-19

## 已完成范围

本轮共完成 18 个分析模块，并为每个模块产出独立文档：

1. `docs/01_typeclass_system.md`
2. `docs/02_object_system.md`
3. `docs/03_account_system.md`
4. `docs/04_command_system.md`
5. `docs/05_script_system.md`
6. `docs/06_lock_system.md`
7. `docs/07_comm_system.md`
8. `docs/08_server_architecture.md`
9. `docs/09_session_management.md`
10. `docs/10_prototype_system.md`
11. `docs/11_help_system.md`
12. `docs/12_utils.md`
13. `docs/13_web_layer.md`
14. `docs/14_database_design.md`
15. `docs/15_contrib_highlights.md`
16. `docs/16_architecture_overview.md`
17. `docs/17_mudlib_interface.md`
18. `docs/18_mudlib_converter.md`

## 本轮工作产出

### 1. 完成 Evennia 核心模块源码梳理

已覆盖的源码域包括：

- `typeclasses`
- `objects`
- `accounts`
- `commands`
- `scripts`
- `locks`
- `comms`
- `server`
- `prototypes`
- `help`
- `utils`
- `web`
- `contrib`

### 2. 完成面向 New_Mud 的初步架构判断

本轮分析不是停留在“Evennia 如何实现”，而是结合当前需求基线 `requirements_v5.md` 明确了 New_Mud 的取舍方向，结论包括：

- 借鉴 Evennia 的抽象，不照搬其 Twisted/Portal-Server 实现
- 保留统一实体、上下文命令、内容原型、帮助系统等核心思想
- 放弃 pickle-heavy、字符串 DSL 过重、巨型运行时对象等不利于长期维护的部分
- 明确项目应以 `Django + DRF + Channels + Daphne + PostgreSQL` 为核心必选栈，并以 ASGI/`asyncio` 承接实时交互主线

### 3. 完成引擎层与 MUDLib 层的综合判断整理

已在以下文档中形成分析层综合判断：

- `docs/16_architecture_overview.md`：总体架构综合判断
- `docs/17_mudlib_interface.md`：MUDLib 边界研究
- `docs/18_mudlib_converter.md`：LPC 转换器问题分析

这些文档沉淀出的核心判断包括：

- 引擎层负责基础设施与运行时
- MUDLib 层负责世界内容、规则与文档
- 转换器负责把 LPC MUDLib 迁移为标准化 MUDLib 结构

## 已同步归档动作

- 18 个分析模块文档已全部落盘到当前仓库 `docs/`
- 分析层入口文档已统一说明 `docs/00-18` 与 `docs/new_engine/` 的分层关系

## 当前阶段结论

Evennia 6.0 对 New_Mud 最有价值的，不是现成框架代码，而是以下几类成熟抽象：

- 统一实体模型
- 上下文命令系统
- 数据驱动原型/模板系统
- 帮助系统与后台工作流
- 可扩展的调度与状态系统

而 New_Mud 的实现应坚持：

- Django/Channels/asyncio
- 显式核心数据模型
- Blueprint/MUDLib 内容分层
- 面向 uni-app 与 WebSocket 的结构化接口

## 下一步建议

建议从分析阶段切换到实施阶段，优先推进：

1. 基于 `docs/new_engine/10_ROADMAP.md` 拆分第一阶段实现计划
2. 基于 `docs/new_engine/02_ARCHITECTURE.md`、`docs/new_engine/03_RUNTIME_SESSIONS.md` 定稿运行时边界
3. 基于 `docs/new_engine/09_MUDLIB_CONVERTER.md` 冻结 MUDLib 最小接口与转换器输出格式
4. 编码前按顺序精读 `docs/new_engine/11_PROTOCOL_CATALOG.md` 到 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` 六份冻结实施合同，固化协议、Registry/Blueprint、会话状态机、战斗技能物品、H5 与运维测试边界
5. 使用 `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 把需求 ID、受影响合同、里程碑和验收证据连接起来



