# 16 总体架构综合判断（分析层草案）

> 状态：分析层派生设计草案。本文基于 Evennia 分析给出早期架构收敛意见，但 New_Mud 当前权威架构规范已迁移至 `docs/new_engine/02_ARCHITECTURE.md` 与 `docs/new_engine/10_ROADMAP.md`。若有冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 权威边界：概念架构与路线以 `docs/new_engine/02_ARCHITECTURE.md`、`docs/new_engine/10_ROADMAP.md` 为准；编码细节由冻结的 `docs/new_engine/11_PROTOCOL_CATALOG.md` 至 `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` 约束。

> 结构说明：本文按“跨模块事实 / 综合评价 / 方向摘要”整理。它是分析层的综合收敛记录，用于说明总体判断从何而来，不再承担正式实施路线和模块拆分规范的职责。

## 1. 本文角色

本文不是当前正式架构文档，而是对 `docs/01-15` 的综合提炼。它回答的是：

- Evennia 各模块里，哪些抽象反复被证明是有价值的
- 哪些实现问题在多个模块里反复出现
- 这些观察最终把 New_Mud 推向什么方向

## 2. 跨模块事实

### 2.1 Evennia 反复证明有效的抽象

在对象、命令、帮助、内容模板等多个模块中，Evennia 持续展现出价值的抽象包括：

- 统一实体视角
- 上下文驱动的命令可见性
- 内容模板继承与标准化
- 帮助、聊天、后台工作流的整合
- 生命周期 hook 和标准处理流水线

这些不是偶然出现在某一个模块里的局部技巧，而是贯穿核心系统的长期设计取向。

### 2.2 Evennia 反复暴露出来的问题

在账号、会话、脚本、数据库、Web 与服务器架构里，反复出现的问题包括：

- `TypedObject / typeclass` 动态魔法过重
- `Attribute / pickle` 过度承载核心状态
- `Script` 抽象承载过多职责
- `lockstring` 作为核心权限语言过于依赖字符串 DSL
- `Portal / Server + AMP + Twisted` 带来额外复杂度
- 文本命令与文本 Webclient 在入口层占据过强中心地位

## 3. 综合评价

Evennia 6.0 应定位为“现代维护中的传统架构”：领域抽象和问题处理经验仍有价值，运行时形状则带有面向传统多协议 MUD 的历史约束。相对 New_Mud 的适配成本，不等同于项目整体落后。

### 3.1 Evennia 值得借鉴的不是整套运行框架

综合各模块后，更可靠的结论是：

- Evennia 的真正价值主要在抽象接口和处理顺序
- 它的运行时实现则深受历史包袱和传统 MUD 场景影响

也就是说，适合借鉴的是“统一实体、上下文命令、内容模板、帮助与制作工作流”，而不是“Twisted、多协议、动态对象魔法、大一统脚本”。

### 3.2 New_Mud 的方向因此被限定

当 `requirements_v6.md` 与这些跨模块观察叠加后，New_Mud 的方向已经比较清楚：

- 单实例
- 单 MUDLib
- `Django + Channels + asyncio`
- WebSocket / REST 主入口
- PC/移动 H5 双端，移动端友好
- 显式模型优先
- 结构化事件优先

## 4. 对 New_Mud 的方向摘要

### 4.1 方向摘要

综合分析层的判断后，更稳定的总体方向可以概括为：

- 引擎层与 MUDLib 层明确分离
- 运行时采用单逻辑运行时下的 ASGI 分层
- 在线与恢复模型区分 `ConnectionSession / AuthSession / Presence / PresenceSnapshot`
- 世界模型以 `Entity` 为统一根，但避免 Attribute 大一统
- 内容模板统一收敛为 `Blueprint`
- 权限、调度、聊天、后台都采用显式子域模型

这些内容在权威设计层已经分别展开；本文不再继续规定接口形状、实施顺序和代码组织细节。

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`
- `docs/new_engine/05_COMMAND_INTERACTION.md`
- `docs/new_engine/06_CONTENT_CHAT_HELP.md`
- `docs/new_engine/07_SCHEDULER_EFFECTS.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- `docs/new_engine/09_MUDLIB_CONVERTER.md`
- `docs/new_engine/10_ROADMAP.md`
- `docs/new_engine/11_PROTOCOL_CATALOG.md`
- `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
- `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
- `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md`
- `docs/new_engine/15_FRONTEND_H5_CONTRACT.md`
- `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`

## 5. 结论

从分析层角度看，New_Mud 的总体方向不是“重建一个 Evennia 克隆”，而是“保留 Evennia 最成熟的抽象，放弃其相对本项目的运行时适配成本，重新落地为更适合 PC/移动 H5 双端、结构化接口和 MUDLib 转换的引擎”。完整边界见 `docs/20_evennia_modernity_assessment.md`。


