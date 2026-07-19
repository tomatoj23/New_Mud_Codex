# 03 账号系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/accounts/models.py`
  - `evennia-main/evennia/accounts/accounts.py`
  - `evennia-main/evennia/accounts/manager.py`
  - `evennia-main/evennia/accounts/bots.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Accounts.md`

## 2. Evennia 源码事实

### 2.1 `AccountDB` 是 `TypedObject + AbstractUser`

`AccountDB` 同时继承：

- `TypedObject`
- `AbstractUser`

因此它既是 Django 认证用户，又同时拥有 Evennia 的：

- Attribute / Tag / Lock
- cmdset
- nicks
- typeclass path

账号因此不只是认证主体，也被建模成可扩展的游戏对象。

### 2.2 账号层承担 OOC 中心职责

Evennia 的账号不是世界中的角色，而是角色的操作者。`DefaultAccount` 负责：

- 登录/登出钩子
- `puppet_object` / `unpuppet_object`
- 当前会话管理
- 可玩角色列表
- OOC / IC 切换

### 2.3 账号层桥接连接态与角色态

Evennia 会用 `AccountSessionHandler` 管理账号关联的连接，用 `CharactersHandler` 维护可控角色集合。源码语义上存在三层状态：

- 未登录 `Session`
- 已登录但未 puppet 的 `Account`
- 已 puppet 角色后的 `Character/Object`

这说明“未登录”本质是会话态，不是账号态；账号主要承接 OOC 逻辑，再通过 puppet 桥接到角色态。

### 2.4 Bot 也走账号继承树

`bots.py` 把 IRC、RSS、Grapevine、Discord 等外部桥接都建模成 `Bot(DefaultAccount)` 子类。Evennia 因此把“玩家账号”和“外部桥接账号”统一放入同一继承树。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 账号不等于角色，这个分层是正确的。
- OOC / IC 切换语义明确，便于支持一号多角。
- 账号层作为“玩家中心”集中承接可玩角色、会话、聊天等能力，工程上比较直观。

### 3.2 不适合本项目的点

- `AccountDB = User + TypedObject` 把认证域和游戏对象域耦合得过紧。
- 在线状态分散在 `AccountDB.db_is_connected`、`ObjectDB.db_account/db_sessid` 与 `ServerSession.account/puppet`，跨持久模型和运行时对象耦合，不利于移动端、多端与断线重连建模。
- Bot 走账号子类会污染主账号模型。
- 对手机号、微信这类多身份源登录来说，认证体系缺少显式边界。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，账号域更合理的拆分方向是：

- `User`：认证主体
- `AuthIdentity`：手机号、微信等外部身份
- `GameAccount`：游戏域账号资料、玩家侧关系与权益
- `CharacterOwnership`：账号与角色拥有关系

在线控制语义则更适合独立成：

- `ConnectionSession`
- `AuthSession`
- `Presence`

外部桥接更适合独立成单独子域，而不是账号继承树的一部分。

### 4.2 对应的权威文档

- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- `requirements_v5.md`（第八章术语定义）与 `UBIQUITOUS_LANGUAGE.md`

## 5. 结论

Evennia 账号系统最值得借鉴的是“账号不等于角色”以及 OOC / IC 分层。最不适合照搬的是认证主体继承 `TypedObject`，且在线标记、会话关联和控角关系分散在 `AccountDB`、`ObjectDB` 与 `ServerSession`。New_Mud 应明确拆分认证、游戏账号、角色归属和在线控制上下文。


