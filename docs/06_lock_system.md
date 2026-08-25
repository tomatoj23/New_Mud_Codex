# 06 锁与权限系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前领域术语，以 `requirements_v6.md` 第八章与根目录 `CONTEXT.md` 为权威；`UBIQUITOUS_LANGUAGE.md` 仅作非权威工程术语索引，`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/locks/lockhandler.py`
  - `evennia-main/evennia/locks/lockfuncs.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Locks.md`

## 2. Evennia 源码事实

### 2.1 Lock 的基本形态是字符串 DSL

Evennia 的锁本质上是字符串表达式，例如：

```text
edit:perm(Admin)
get:not attr(very_weak) or perm(Admin)
traverse:holds(keycard) and not tag(blocked)
```

一个 lockstring 由：

- `access_type`
- 布尔表达式
- lockfunc 调用

三部分构成。

### 2.2 `LockHandler` 统一管理访问控制

`LockHandler` 负责：

- 解析 lockstring
- 缓存 lockfunc
- 增删查改锁
- 执行 `check()` / `check_lockstring()`

对象、命令、频道、帮助条目、消息等实体都可复用这套接口。

### 2.3 Lock Function 机制可扩展

`lockfuncs.py` 提供大量可组合谓词，例如：

- `all()` / `true()`
- `perm()` / `perm_above()`
- `id()` / `dbref()`
- `attr_*`
- `tag()` / `objtag()`
- `holds()`
- `inside()`
- `serversetting()`

并且 `settings.LOCK_FUNC_MODULES` 允许继续扩展自定义 lockfunc。

### 2.4 `access_type` 更多是一种约定

Evennia 并没有固定的中心权限枚举，而是由调用方约定 `access_type` 的含义，例如：

- `cmd`
- `view`
- `edit`
- `delete`
- `traverse`
- `listen`
- `send`

## 3. 基于源码的评价

### 3.1 值得保留的点

- 表达力极强，尤其适合 Builder 驱动内容系统。
- 同一套机制可以覆盖对象、频道、命令等多类权限。
- 自定义谓词方便，扩展成本低。
- “所有交互统一走权限检查”这个意识非常正确。

### 3.2 不适合本项目的点

- 字符串 DSL 不易静态检查。
- 规则埋在字符串里，重构和全局搜索成本高。
- `access_type` 缺少中心定义，团队协作时容易漂移。
- 移动端 / API 通常需要结构化、可解释的拒绝原因，而不是只返回 True / False。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，“统一权限检查入口”这个思想值得保留；对应到权威设计层，后续实现已转向：

- 显式动作枚举
- 结构化策略对象
- 可组合 predicate
- 结构化拒绝结果

字符串 DSL 即使保留，也更适合作为内容层补充，而不是核心权限语言。

### 4.2 对应的权威文档

- `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`

## 5. 结论

Evennia 的锁系统在 MUD 里很强，但它强在“可配置字符串规则”，不强在“可维护工程化权限架构”。分析层对应的结论是：保留统一权限检查思想，同时把实现改成结构化策略系统，DSL 只作为内容层补充。

