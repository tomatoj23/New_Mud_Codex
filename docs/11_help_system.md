# 11 帮助系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/help/models.py`
  - `evennia-main/evennia/help/manager.py`
  - `evennia-main/evennia/help/filehelp.py`
  - `evennia-main/evennia/help/utils.py`
  - `evennia-main/evennia/commands/default/help.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Help-System.md`

## 2. Evennia 源码事实

### 2.1 帮助系统汇总三类来源

Evennia 帮助系统会统一处理：

- 数据库帮助条目
- 文件帮助条目
- 命令 docstring 自动帮助

它们最终都由 `help` 命令统一检索和展示。

### 2.2 `HelpEntry` 是轻量内容模型

数据库帮助的核心模型是 `HelpEntry`，字段主要包括：

- `db_key`
- `db_help_category`
- `db_entrytext`
- `db_lock_storage`
- `db_tags`

它不是 typeclass，而是更轻量的内容模型。

### 2.3 文件帮助与搜索工具已经比较成熟

`filehelp.py` 支持从 Python 模块中的 dict 加载帮助条目；`utils.py` 还负责：

- 搜索索引
- suggestion
- 子主题解析

这说明 Evennia 的帮助系统已经不是单纯标题匹配。

### 2.4 命令帮助可自动生成

命令 docstring 可以直接进入帮助系统。开发者改代码时，帮助索引也会同步变化。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 多来源统一检索这个设计很成熟。
- 帮助系统被当作有权限边界的内容系统，而不只是纯文本说明。
- 文件化维护很适合版本控制。
- 搜索、建议和子主题导航对大型游戏很有价值。

### 3.2 不适合本项目的点

- 把命令 docstring 直接当玩家帮助，对多端产品化表达不够稳定。
- 文件帮助采用 Python dict，仍偏开发者内部格式。
- `help` 输出主要围绕纯文本排版设计。
- 玩家帮助、GM 文档、策划文档、世界百科、教程可能需要不同发布链路。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，可保留的核心方向是：

- 多来源统一索引
- 文件内容与数据库内容并存
- 权限控制

对应到权威设计层，后续实现已转向：

- Markdown / 内容中心优先
- 命令帮助只作为辅助来源
- 搜索驱动而不是目录优先
- 玩家端、GM 端、后台端共用同一知识底座

### 4.2 对应的权威文档

- `docs/new_engine/06_CONTENT_CHAT_HELP.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`

## 5. 结论

Evennia 帮助系统最值得借鉴的是“多来源统一检索”和“帮助也是有权限控制的内容”。分析层对应的方向是把它升级为搜索驱动的文档中心，让玩家端、GM 端和后台都能复用同一套知识库。

