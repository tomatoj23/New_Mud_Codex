# 15 Contrib 精选分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 contrib 中对 New_Mud 有参考价值的样本与判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“样本事实 / 综合评价 / 设计去向”整理。

## 1. 分析范围

- 源码目录：
  - `evennia-main/evennia/contrib/`
- 参考文档：
  - `evennia-main/docs/source/Contribs/Contribs-Overview.md`

Evennia contrib 数量很多，不适合逐个照搬。本文只聚焦对 New_Mud 有启发的样本。

## 2. 样本事实

### 2.1 `components`

这个 contrib 提供了比单纯 typeclass 继承更灵活的组合式思路，适合观察“组件挂载 + 组件槽位”。

### 2.2 `character_creator`

这个 contrib 展示了账号态到角色态的多步骤角色创建流程。

### 2.3 `traits`

这个 contrib 已经体现了数值系统中的 `base / mod / min / max` 与变化追踪思路。

### 2.4 `buffs`

这个 contrib 把持续效果、层数、来源、暂停恢复等问题整理成一套通用模型。

### 2.5 `mail`

这个 contrib 展示了角色内信件与账号外消息分层的做法。

### 2.6 `tree_select`

这个 contrib 只适合简单的分支选择树。

需要复杂跳转或任意输入时，应使用完整 EvMenu；`tree_select` 也不兼容较新的 EvMenu templating。

### 2.7 `custom_gametime`

这个 contrib 展示了自定义游戏时间、历法和时辰机制的可能形态。

### 2.8 `evadventure`

这不是单一工具，而是一个完整示例游戏，适合观察 Evennia 团队如何把对象、命令、脚本和规则拼成可玩系统。

## 3. 综合评价

### 3.1 真正有价值的是中层抽象

对 New_Mud 来说，contrib 最有价值的不是协议兼容层，而是这些中层抽象：

- 组件化
- 数值系统
- Buff / 状态效果
- 角色创建流程
- 后台配置交互
- 信件和消息分层

### 3.2 不适合直接采用的方向

以下类型的 contrib 更适合参考思路，不适合进入当前主线：

- `ingame_python` 这类直接开放 Python 的工具
- `mux_comms_cmds` 这类传统命令兼容层
- `godotwebsocket` 这类与当前前端方向不一致的接入方案
- 各种文本客户端强化组件

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，Contrib 更合理的使用方式不是复制粘贴，而是：

- 借鉴设计抽象
- 提取业务模型
- 用当前技术栈重新实现

优先吸收的样本应集中在组件化、数值系统、Buff、角色创建流程、后台交互和消息分层。

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/05_COMMAND_INTERACTION.md`
- `docs/new_engine/07_SCHEDULER_EFFECTS.md`
- `docs/new_engine/10_ROADMAP.md`
- `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md`

## 5. 结论

Evennia contrib 里真正对 New_Mud 有价值的，不是各种协议 / 命令兼容层，而是组件化、数值系统、Buff 系统、角色创建流程和后台配置交互这几类中层抽象。它们应被当作设计样本，而不是现成依赖。

