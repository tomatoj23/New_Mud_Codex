# 12 工具库分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

## 1. 分析范围

- 重点源码入口：
  - `evennia-main/evennia/utils/create.py`
  - `evennia-main/evennia/utils/dbserialize.py`
  - `evennia-main/evennia/utils/utils.py`
  - `evennia-main/evennia/utils/search.py`
  - `evennia-main/evennia/utils/evmenu.py`
  - `evennia-main/evennia/utils/eveditor.py`
  - `evennia-main/evennia/utils/evtable.py`
  - `evennia-main/evennia/utils/ansi.py`
  - `evennia-main/evennia/utils/text2html.py`
  - `evennia-main/evennia/utils/gametime.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Coding-Utils.md`

## 2. Evennia 源码事实

### 2.1 `utils/` 实际上是混合基础设施层

Evennia 的 `utils/` 并不是小工具目录，里面同时包含：

- 创建与搜索辅助
- 序列化
- 文本渲染
- 菜单与编辑器
- 时间与调度辅助
- 通用字符串 / 集合工具

### 2.2 create / search 提供统一 facade

`create.py` 和 `search.py` 抽出了高频对象操作，例如：

- `create_object`
- `create_script`
- `create_account`
- `create_channel`
- `search_object`
- `search_script`
- `search_help`

### 2.3 `dbserialize.py` 是 Attribute 体系关键设施

`dbserialize.py` 解决：

- 任意 Python 结构的持久化
- 嵌套 mutable 的自动回写

为此它引入了 packed dbobj / session、saver list / dict / set、pickle 序列化等机制。

### 2.4 文本交互和文本表现工具很成熟

`evmenu.py`、`eveditor.py`、`evtable.py` 提供文本菜单、编辑器和表格渲染；`ansi.py`、`text2html.py` 负责 ANSI 颜色解析与富文本到 HTML 的转换。

### 2.5 还有时间与杂项工具

`gametime.py`、`utils.py`、`validatorfuncs.py` 提供游戏时间换算、delay / repeat、导入辅助、字符串匹配和其他基础能力。

## 3. 基于源码的评价

### 3.1 值得保留的点

- create / search facade 很实用，适合作为引擎 facade 参考。
- 时间工具和部分校验能力具备基础设施价值。
- 文本菜单和编辑器对 GM / 调试工具有借鉴意义。
- Evennia 明确认识到“工具层也是产品力的一部分”。

### 3.2 不适合本项目的点

- `utils/` 范围过宽，容易演变成巨型杂物间。
- `dbserialize` 对 pickle 和对象包装依赖过重。
- 很多工具以文本客户端为中心，不适合作为移动端主方案。
- 如果核心领域逻辑大量沉到 `utils.py`，模块边界会被削弱。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，真正具备基础设施价值的部分包括：

- facade 型 create / search
- 时间与调度辅助
- 校验工具
- 后台 / 调试向文本工具

对应到权威设计层，后续实现应避免把所有辅助能力继续堆进一个 `utils/` 杂项目录，也不应继承 `dbserialize` 的 pickle 路线。

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/07_SCHEDULER_EFFECTS.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`

## 5. 结论

Evennia 的 utils 更像“半个基础设施层”。其中 facade、时间工具和部分校验能力值得保留；pickle 序列化、文本渲染主线和过度集中的工具组织方式不适合直接带入 New_Mud。分析层对应的结论是重构工具边界，让工具服务模块，而不是吞掉模块。

