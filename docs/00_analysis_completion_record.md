# Evennia 源码分析完成记录（分析层入口）

> 状态：分析层入口文档。`docs/00-18` 记录 Evennia 6.0 本地源码事实、模块优缺点与研究过程；`docs/20` 补充现代性与项目适配性评估。它们都不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

## 当前权威说明

- 自 2026-03-20 起，`docs/00-18` 统一归类为分析层文档；2026-08-22 新增 `docs/20_evennia_modernity_assessment.md`，作为现代性与适配性判断入口。
- New_Mud 当前正式设计、模块边界、实施路线与开发顺序，以 `docs/new_engine/` 为准。
- `docs/16-18` 保留为“分析派生的综合判断 / 边界研究 / 问题分析”文档，继续作为研究依据，但不再单独作为权威规范。

## 记录时间

- 原始分析完成日期：2026-03-19
- 现代性复核日期：2026-08-22

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

本轮分析不是停留在“Evennia 如何实现”，而是结合当前需求基线 `requirements_v6.md` 明确了 New_Mud 的取舍方向，结论包括：

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
- 分析层入口文档已统一说明 `docs/00-18`、`docs/20` 与 `docs/new_engine/` 的分层关系

### 4. 2026-08-22 现代性复核

复核结论：Evennia 6.0 是“现代维护中的传统架构”。它没有整体过时，但 Portal/Server/AMP、文本中心 WebClient、动态 Typeclass 与任意 pickle 状态不适合 New_Mud 的 Web-first、PC/移动 H5 双端和强 schema 目标。命令生命周期、移动 Hook、Prototype、帮助、频道与会话问题域仍值得借鉴。完整判断见 `docs/20_evennia_modernity_assessment.md`。

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

## 当前使用说明

原始分析阶段的“下一步建议”已由设计层、冻结合同和实施状态文档承接，不再作为当前待办重复维护。当前应依次参考：

1. `docs/20_evennia_modernity_assessment.md`：确认 Evennia 的参考边界。
2. `docs/new_engine/00_README.md` 到 `docs/new_engine/10_ROADMAP.md`：理解设计与路线。
3. `docs/new_engine/11_PROTOCOL_CATALOG.md` 到 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`：编码前读取冻结合同。
4. `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 与 `docs/new_engine/18_IMPLEMENTATION_STATUS.md`：回查需求、证据和当前阻塞项。



