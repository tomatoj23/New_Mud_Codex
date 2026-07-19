# 08 服务器架构分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前正式术语，以 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 为准；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/server/service.py`
  - `evennia-main/evennia/server/server.py`
  - `evennia-main/evennia/server/webserver.py`
  - `evennia-main/evennia/server/portal/`
  - `evennia-main/evennia/server/portal/amp.py`
  - `evennia-main/evennia/server/portal/service.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Portal-And-Server.md`
  - `evennia-main/docs/source/Concepts/Server-Lifecycle.md`

## 2. Evennia 源码事实

### 2.1 核心是 `Portal / Server` 双进程

Evennia 的核心运行形状是：

- `Portal`：协议接入层
- `Server`：游戏逻辑层

`Portal` 负责 Telnet、SSH、WebSocket 以及对外 Web 代理和 bot 协议 session；`Server` 负责对象、命令、脚本、数据库以及内部 Django WSGI 服务。

### 2.2 AMP 是双进程胶水

`server/portal/amp.py` 定义了大量 AMP command，用于：

- Portal -> Server
- Server -> Portal
- launcher -> Portal

其目的之一是让 Server reload 时尽量保住玩家连接。

### 2.3 `EvenniaServerService` 是 Server 侧总装

`EvenniaServerService` 会注册：

- AMP client
- 内部 Django Web server
- server-side services
- 维护循环
- 生命周期 hook

它本质上是 Server 侧的 service container。

### 2.4 Portal 统一处理多协议接入

`portal/` 下挂着：

- telnet
- ssh
- webclient
- websocket
- discord
- grapevine
- rss
- irc

这说明 Evennia 的架构重点之一是“多协议统一接入”。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 协议层和游戏层职责分离很清楚。
- 生命周期边界清晰，便于理解连接、重载和运行时行为。
- 多协议接入和外部桥接能力成熟。
- Server 侧总装服务容器的思路有参考价值。

### 3.2 不适合本项目的点

- 双进程架构高度依赖 Twisted / AMP，而项目技术路线已经固定为 `Django + Channels + asyncio`。
- 本项目主入口是 WebSocket，不是 Telnet / SSH 优先。
- 双进程会放大会话同步、运维、调试、序列化和一致性成本。
- 对移动端优先的客户端来说，协议隔离的收益低于结构化 API 和事件流。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，值得保留的是“职责边界”，而不是“Portal / Server 物理拆分”。对应到权威设计层，后续实现已转向：

- 单逻辑运行时下的 ASGI 分层
- 明确的接入层、运行时层、领域层和后台层
- WebSocket / REST 统一接入
- 外部桥接作为受控适配器，而不是架构中心

### 4.2 对应的权威文档

- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `docs/new_engine/10_ROADMAP.md`

## 5. 结论

Evennia 的双进程架构很适合传统多协议 MUD，但不适合本项目既定技术路线。分析层对应的结论是：借鉴其“边界清晰”和“生命周期清楚”这两点，放弃 Portal / Server 的物理拆分，转向单逻辑运行时下的 ASGI 分层。

