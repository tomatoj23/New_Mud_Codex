# 05 脚本与任务调度系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v6.md` 第八章、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md` 为准；`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/scripts/models.py`
  - `evennia-main/evennia/scripts/scripts.py`
  - `evennia-main/evennia/scripts/scripthandler.py`
  - `evennia-main/evennia/scripts/taskhandler.py`
  - `evennia-main/evennia/scripts/tickerhandler.py`
  - `evennia-main/evennia/scripts/ondemandhandler.py`
  - `evennia-main/evennia/scripts/monitorhandler.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Scripts.md`

## 2. Evennia 源码事实

### 2.1 `ScriptDB` 是持久化系统对象

`ScriptDB` 的核心字段包括：

- `db_obj` / `db_account`
- `db_desc`
- `db_interval`
- `db_start_delay`
- `db_repeats`
- `db_persistent`
- `db_is_active`

这说明 Evennia 把“系统状态”和“定时任务”统一装进了 Script 抽象。

### 2.2 Script 有完整生命周期

`scripts.py` 中的 `ScriptBase` 提供核心生命周期：

- `at_script_creation`
- `at_first_save`
- `at_start`
- `at_repeat`
- `at_stop`
- `at_pause`
- `is_valid`

`DefaultScript` 在此基础上补充 `at_server_reload` 等服务器生命周期 hook。

Script 因而既可以被当作全局服务，也可以被当作对象附着状态机。

### 2.3 实际上存在多套时间能力

Evennia 并不是只有一种任务机制，而是并行提供：

- Script 自带计时器
- `TickerHandler`
- `TaskHandler`
- `OnDemandHandler`
- `MonitorHandler`

它们分别处理周期回调、一次性排程、延迟计算和变化监听。

### 2.4 对象和账号都能挂脚本

对象和账号可以通过 `scripts` handler 挂载 / 卸载脚本。于是脚本既像任务，也像对象附件或运行时行为模块。

## 3. 基于源码的评价

### 3.1 值得保留的点

- Evennia 正确识别了“一次性任务 / 周期任务 / 持续状态 / 变化监听”是不同问题域。
- 生命周期钩子完整，便于快速实现 MUD 玩法。
- `TickerHandler` 对大量重复 tick 的优化有参考价值。
- 持久化恢复能力对世界事件和长期效果很重要。

### 3.2 不适合本项目的点

- “脚本”一个抽象承载了存储、调度、状态、效果、监听多种职责。
- 挂载式脚本容易把关键逻辑藏进难追踪的对象附件。
- Twisted 定时器模型不符合项目既定的 `asyncio + Django Channels` 技术路线。
- 持久化记录与执行器强耦合，不利于观测、重试、告警和运维面板建设。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，单一 `Script` 大抽象不适合继续保留，更合理的拆分方向是：

- 调度任务
- 周期任务
- 状态效果
- 世界进程 / 世界服务
- 观察器或订阅器

同时，持久化层和执行层更适合分开，避免“一个通用脚本对象既是状态记录又是执行容器”。

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/07_SCHEDULER_EFFECTS.md`

## 5. 结论

Evennia 的 Script 系统展示了“任务、状态、效果统一建模”的强大灵活性，但也因此过于宽泛。分析层对应的方向是把它拆成清晰的调度、状态和世界进程系统，并用 `asyncio` 重新落地。


