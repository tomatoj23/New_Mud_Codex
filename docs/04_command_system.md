# 04 命令系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v6.md` 第八章、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md` 为准；`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/commands/command.py`
  - `evennia-main/evennia/commands/cmdhandler.py`
  - `evennia-main/evennia/commands/cmdparser.py`
  - `evennia-main/evennia/commands/cmdset.py`
  - `evennia-main/evennia/commands/cmdsethandler.py`
  - `evennia-main/evennia/commands/default/`
- 参考文档：
  - `evennia-main/docs/source/Components/Commands.md`
  - `evennia-main/docs/source/Components/Command-Sets.md`

## 2. Evennia 源码事实

### 2.1 `Command` 与 `CmdSet` 分层明确

Evennia 把命令系统拆成两层：

- `Command`：单个命令的解析与执行逻辑
- `CmdSet`：命令集合，负责上下文可见性和合并

命令不会只挂在全局注册表，而会随着 `session / account / 当前角色` 及其所在房间、携带物、出口等上下文动态合并。

### 2.2 输入到执行的流水线很完整

`cmdhandler.py` 主流程大体是：

1. 分析 caller 类型，确定当前 provider
2. 收集 `session / account / object` 的 cmdset
3. 在 object 层补充当前位置、携带物、出口等本地对象 cmdset
4. 合并为当前有效 cmdset
5. 由 `cmdparser` 做匹配
6. 处理空输入 / 未匹配 / 多匹配
7. 给命令实例注入 `caller`、`session`、`args`、`cmdstring` 等运行时变量
8. 依次执行 `at_pre_cmd -> parse -> func -> at_post_cmd`

### 2.3 命令类在定义期就会预处理

`command.py` 中的 `CommandMeta` / `_init_command` 会在类定义阶段完成：

- key / alias 归一化
- lock 默认值补齐
- `arg_regex` 编译
- help 索引预处理
- 父类 docstring 继承

### 2.4 `CmdSet` 合并能力很强

`CmdSet` 支持：

- `Union`
- `Intersect`
- `Replace`
- `Remove`

同时还包含：

- `priority`
- `duplicates`
- `no_objs`
- `no_exits`
- `no_channels`

这让命令空间可以随环境、状态和权限动态变化。

### 2.5 命令系统还能承载文本对话流

`cmdhandler.py` 支持命令在 `func()` 中 `yield`，然后通过 `EvMenu / get_input` 接续执行。Evennia 因而可以用命令式方式实现渐进文本交互。

## 3. 基于源码的评价

### 3.1 值得保留的点

- “命令会随上下文变化”这个核心思想非常成熟。
- 输入到执行的流水线清晰，适合沉淀统一 hook 顺序。
- 命令元数据、帮助、权限检查可以围绕同一命令对象组织。
- 文本多重匹配消歧和多词命令匹配是长期打磨过的实战经验。

### 3.2 不适合本项目的点

- 系统严重依赖字符串匹配和别名，类型信息较弱。
- `CmdSet` 合并过强，复杂度和调试成本都高。
- 命令来源过多时，可解释性会迅速下降。
- `yield` + Twisted 风格渐进命令不适合项目既定的 `asyncio` 主线。
- 文本优先模型对传统 Telnet 仍然成熟有效；但对 WebSocket / PC 与移动 H5 双端，很多输入本来就是结构化事件，不必先压回文本命令再解析。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，可保留的核心方向是：

- 命令生命周期
- 多词命令匹配和消歧经验
- 上下文动作可见性

对应到权威设计层，后续实现已转向：

- 结构化动作作为主入口
- 文本命令作为适配器
- 有限层级的 provider / resolver
- 不再复制完整 `CmdSet` 合并 DSL

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/05_COMMAND_INTERACTION.md`
- `requirements_v6.md`（第八章术语定义）、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md`

## 5. 结论

Evennia 命令系统最值得借鉴的是“命令上下文化”和“完整输入处理流水线”。这不是对文本命令的普遍否定，而是对本项目协议边界的选择：不照搬过强的 `CmdSet` 魔法，把文本解析作为适配器，并将输入、授权、执行和结果统一结构化。


