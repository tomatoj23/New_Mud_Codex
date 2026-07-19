# 09 会话管理分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/server/session.py`
  - `evennia-main/evennia/server/serversession.py`
  - `evennia-main/evennia/server/sessionhandler.py`
  - `evennia-main/evennia/server/inputfuncs.py`
  - `evennia-main/evennia/server/portal/portalsessionhandler.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Sessions.md`

## 2. Evennia 源码事实

### 2.1 `Session` 是连接，不是持久实体

Evennia 的基础 `Session` 不是 typeclass，也不持久化到数据库。它代表一次真实连接，核心是：

- `sessid`
- `address`
- `protocol_key`
- `logged_in`
- `uid / uname / puid`
- `protocol_flags / server_data`

游戏逻辑侧再由 `ServerSession` 补上：

- `account`
- `puppet`
- `cmdset`
- 仅内存使用的 `ndb/db`

### 2.2 `PortalSession` 与 `ServerSession` 双边镜像

Evennia 由于是双进程架构，会话也分成：

- `PortalSession`
- `ServerSession`

两者通过 AMP 保持同步，断线、重载、重连时都要搬运状态。

### 2.3 `SessionHandler` 是在线 registry

`SessionHandler` / `ServerSessionHandler` 负责：

- 存储会话
- 获取同步数据
- 清洗 outgoing data
- 分发输入
- 登录/登出流程
- 断线与 idle timeout

它本质上是在线连接的全局 registry。

### 2.4 `inputfuncs` 已经在做输入适配

`inputfuncs.py` 提供一组标准输入函数：

- `text`
- `login`
- `echo`
- `client_options`
- `repeat`
- `monitor`
- `webclient_options`

它本质上是在做“协议输入 -> 游戏内部语义”的适配。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 连接、账号、角色三层概念分得比较清楚。
- 非持久 `Session` 设计符合网络连接本质。
- 统一的在线 registry 很有价值。
- 输入适配层这个思想本身是正确的。

### 3.2 不适合本项目的点

- 双进程镜像会话的复杂度对本项目没有必要。
- `puppet` 概念偏传统 MUD 术语，不完全等同于移动端“当前激活角色”。
- 输入仍主要围绕文本协议组织，而项目主入口应是 WebSocket 结构化事件。
- 多端同步、微信登录、前后台切换等移动端场景不是一等公民。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，在线模型更合理的收敛方向是三层：

- `ConnectionSession`
- `AuthSession`
- `Presence`

输入侧保留“适配层”思想，但更适合改成结构化事件入口；在线状态默认由运行时服务持有，只在必要时补充审计或快照记录。

### 4.2 对应的权威文档

- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `requirements_v5.md`（第八章术语定义）与 `UBIQUITOUS_LANGUAGE.md`

## 5. 结论

Evennia 会话系统最值得借鉴的是“`Session` 对象本身不作为数据库模型”和“连接态 / 账号态 / 角色态分层”。这不等于连接信息完全不入库：`AccountDB.db_is_connected` 与 `ObjectDB.db_sessid` 仍保存在线标记或会话关联元数据。New_Mud 不继承双边镜像，而面向 WebSocket 和移动端重建三层在线模型。

