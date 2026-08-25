# 01 Typeclass 系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v6.md` 第八章、根目录 `CONTEXT.md` 与 `UBIQUITOUS_LANGUAGE.md` 为准；`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/typeclasses/models.py`
  - `evennia-main/evennia/typeclasses/attributes.py`
  - `evennia-main/evennia/typeclasses/tags.py`
  - `evennia-main/evennia/typeclasses/managers.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Typeclasses.md`

## 2. Evennia 源码事实

### 2.1 `TypedObject` 是统一数据库骨架

Evennia 用 `TypedObject` 作为账号、对象、脚本、频道四类核心实体的共同数据库基类。这个抽象层保留少量稳定字段：

- `db_key`
- `db_typeclass_path`
- `db_date_created`
- `db_lock_storage`
- `db_attributes`
- `db_tags`

核心思想是：数据库保存稳定骨架，行为由 `typeclass_path` 指向的 Python 类决定，扩展数据则通过 Attribute / Tag 体系承载。

### 2.2 `TypeclassBase` 负责行为类与 DB 模型桥接

`TypeclassBase` 会：

- 把 typeclass 伪装成 Django proxy model
- 为类记录 `typename` 和 `path`
- 让代理类指回真实 db model
- 挂接 `post_save` / `pre_delete` 信号
- 在首次保存时调用 `at_first_save()`

### 2.3 Attribute 系统是动态扩展核心

`attributes.py` 提供：

- `Attribute`
- `AttributeHandler`
- `AttributeProperty` / `NAttributeProperty`
- `ModelAttributeBackend`
- `InMemoryAttributeBackend`
- `DbHolder`
- `NickHandler`

Evennia 因而更强调“对象可无限扩展”，而不是“字段显式建模”。

### 2.4 Tag / Alias / Permission 共用统一底层

`tags.py` 使用统一的 `Tag` 模型同时承载：

- 普通标签
- alias
- permission

再通过不同 handler 做语义分层。

### 2.5 Manager 层支持按 typeclass 家族检索

`TypedObjectManager` / `TypeclassManager` 提供：

- family 查询
- typeclass 路径查询
- tag / attr 搜索
- 创建辅助

这让“按 typeclass 家族检索对象”成为一等能力。

## 3. 基于源码的评价

### 3.1 值得保留的点

- “稳定骨架 + 可演化行为”这个方向非常强。
- 四类核心实体共用同一抽象，心智模型统一。
- Attribute / Tag 机制让 Builder 在不改表的情况下持续扩展内容。
- 通过 typeclass path 让旧对象获得新行为，这一点很灵活。

### 3.2 不适合本项目的点

- Django proxy model + 元类 + 信号的组合过重，调试成本高。
- `obj.db.xxx` 这类魔法接口会弱化类型边界。
- Attribute 过度泛化后，核心业务字段难以约束，也不利于查询优化。
- Tag / Alias / Permission 共用同一模型，语义边界偏模糊。
- 动态改写 `__class__`、proxy model 与 pickle 对象包装，并非“版本落后”的单一证据，但不适合稳定 API、转换器和多端前端。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，可保留的核心方向是：

- 统一实体抽象
- 长尾扩展槽位
- 行为与数据骨架分离

对应到权威设计层，后续实现已转向：

- 显式 `Entity` 根模型
- 显式 Attribute / Tag / Alias / Permission 语义边界
- 不复制 proxy-model 魔法
- 核心状态优先显式建模，长尾状态再放扩展层

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`

## 5. 结论

Typeclass 系统是 Evennia 最值得借鉴的内核思想之一，但只应借鉴“稳定骨架与行为分离”的语义，不复制动态换类机制。分析层能成立的结论是：保留“统一实体抽象 + 可扩展属性层”的思路，同时把实现改成“显式模型 + 显式服务 + 可查询扩展层”。详见 `docs/20_evennia_modernity_assessment.md`。


