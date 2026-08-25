# 10 原型与生成系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v6.md` 第八章、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md` 为准；`requirements_v5.md` 仅作历史对照；`Prototype` 在本文中仅作为 Evennia 来源名词。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/prototypes/prototypes.py`
  - `evennia-main/evennia/prototypes/spawner.py`
  - `evennia-main/evennia/prototypes/menus.py`
  - `evennia-main/evennia/prototypes/protfuncs.py`
  - `evennia-main/evennia/prototypes/README.md`
- 参考文档：
  - `evennia-main/docs/source/Components/Prototypes.md`

## 2. Evennia 源码事实

### 2.1 `Prototype` 是实例模板

Prototype 本质是一个 dict，用来描述对象实例的差异化数据。它不是 typeclass 的替代，而是 typeclass 的补充：

- typeclass 定义行为
- prototype 定义实例差异

### 2.2 Prototype 支持继承和标准键

`prototypes.py` 会对 prototype 做统一规范化，核心键包括：

- `prototype_key`
- `prototype_desc`
- `prototype_tags`
- `prototype_locks`
- `prototype_parent`
- `typeclass`
- `key`
- `location/home/destination`
- `aliases`
- `permissions`
- `locks`
- `tags`
- `attrs`

未保留字默认会被视作 Attribute。

### 2.3 模块原型与数据库原型并存

Evennia 支持两类来源：

- 模块原型：开发者在 Python 模块中定义，只读
- 数据库原型：以 Script 形式存储，可由 Builder 在游戏内编辑

### 2.4 `spawner.py` 负责实例化与差异计算

`spawner.py` 提供：

- prototype flatten
- prototype diff
- object -> prototype 反推
- 批量更新
- `spawn()`

### 2.5 OLC 编辑器围绕原型系统组织

`menus.py` 把 prototype 编辑器做成 EvMenu 式 OLC，说明 Evennia 把原型系统视为 Builder 工作流的核心。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 数据驱动内容生产能力很强。
- 继承机制非常适合房间、怪物、物品模板族。
- 差异对比和批量更新能力，对内容维护价值很高。
- 开发者定义与 Builder 编辑两种来源可以并存。

### 3.2 不适合本项目的点

- dict 结构过于自由，不利于长期 schema 管理。
- 数据库原型借 Script 存储，模型边界不干净。
- prototype value 支持 callable / protfunc / exec，安全边界过宽。
- 设计中心仍是 Object，天然不覆盖技能、任务、门派、剧情节点等更广内容。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，设计层统一不再使用 `Prototype` 作为正式名词，而是收敛到 `Blueprint`。同时：

- 内容模板应有显式 schema
- 生成流程应有校验、合并、规范化与编译阶段
- 不保留任意 Python 执行能力
- 该系统同时服务内容制作、MUDLib 装载与 LPC 转换器输出
- 实例差异更新只能由显式 apply job 执行，并且只写入 Blueprint 声明的 `sync_safe_fields`；其余字段不得自动覆盖

### 4.2 对应的权威文档

- `docs/new_engine/06_CONTENT_CHAT_HELP.md`
- `docs/new_engine/09_MUDLIB_CONVERTER.md`
- `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
- `requirements_v6.md`（第八章术语定义）、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md`

## 5. 结论

Evennia 的 Prototype 系统是内容生产链里最值得借鉴的部分之一。分析层对应的结论是：保留“模板 + 继承 + 实例化 + 受限差异更新”的核心思想，并把实现收敛为更安全、更结构化、可被 MUDLib 与转换器复用的 Blueprint 系统。

这里的差异更新仅指显式 apply job 对 `sync_safe_fields` 的同步，不包含结构字段或运行时状态的自动覆盖。

