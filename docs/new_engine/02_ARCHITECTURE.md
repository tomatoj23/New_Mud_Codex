# 02 新引擎总体架构

> 术语说明：本文默认使用 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md` 中的当前术语定义；若两者表述粒度不同或发生冲突，以 `requirements_v5.md` 为准；仅在提及 Evennia 来源时保留 `Prototype`、`AccountDB` 一类源术语。

> 实施约束：本文负责说明总体分层与运行时边界；下列实施细节以对应的六份冻结合同为准：
> - 协议：`docs/new_engine/11_PROTOCOL_CATALOG.md`
> - Registry/Blueprint：`docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
> - 会话：`docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
> - 战斗、技能与物品：`docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md`
> - H5：`docs/new_engine/15_FRONTEND_H5_CONTRACT.md`
> - 运维与测试：`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`

## 1. 设计目标

新引擎的正确方向不是“做一个 Evennia for Django Channels”，而是：

- 用 `Django + DRF + Channels + Daphne + PostgreSQL` 构建单逻辑运行时，并以 ASGI/`asyncio` 承接结构化、移动端友好的 MUD 引擎。
- 保留 Evennia 在实体、命令、原型、帮助、调度上的成熟抽象。
- 从一开始就为 MUDLib 加载与 LPC 转换器留标准落点。

## 2. 进程模型

逻辑上只保留一个“游戏运行时”：

```text
Client
  -> Nginx / HTTPS / WSS
  -> Django ASGI
  -> Channels Consumers
  -> Runtime Services
  -> Domain Services / ORM / Scheduler
```

这里的“单运行时”在当前项目基线下按单实例、单写者来理解。先把一个清晰可验证的世界状态模型做稳，再讨论是否需要额外的进程拆分。

原因：

- 本项目主协议就是 WebSocket，不需要 Portal 负责多协议接入。
- Channels 已经提供连接生命周期、group 广播、异步消息路由。
- 单逻辑运行时模型更适合问题排查、调试、运营与部署。

## 3. 分层

### 3.1 接入层

职责：

- REST API
- WebSocket Consumer
- Admin 后台
- 内部导入接口

### 3.2 应用服务层

职责：

- 连接与认证服务
- 角色进入/离开世界
- 命令解析与分发
- 场景移动
- 聊天与社交
- 调度与事件编排
- 内容装载

### 3.3 领域层

职责：

- 实体不变量
- 规则校验
- 派生状态计算
- 系统行为接口

### 3.4 内容层

职责：

- Blueprint seed 输入；包内文件与转换器产物只用于初始化或显式导入
- PostgreSQL 中不可变的 published revisions 与 exact dependencies；active batch 为新选择提供当前映射，pinned 实例继续读取其历史 revision
- Help 文档
- MUDLib Manifest、`register_blueprint_seed_providers()` 与 typed registry 注册入口
- `HandlerDefinition / RuleDefinition / PermissionPolicyDefinition / HookSetDefinition / ActionProviderDefinition / RenderPolicyDefinition` 等受控 registry
- 内容校验与启动计划

### 3.5 基础设施层

职责：

- Django ORM
- Channels channel layer
- 数据库事务
- 缓存
- 搜索索引
- 定时器驱动
- 审计日志

## 4. 推荐代码组织

```text
apps/
  core/
  runtime/
  accounts/
  characters/
  world/
  commands/
  chat/
  combat/
  scheduler/
  content/
  helpcenter/
  adminops/
  mudlib/
  importer/
```

## 5. 核心总线

新引擎需要两条明确分开的总线：

### 5.1 Action 总线

输入统一转成结构化动作：

```json
{
  "action": "move",
  "actor_ref": "character:1024",
  "args": {"direction": "north"},
  "source": "text_command"
}
```

这里描述的是运行时内部归一化后的动作对象，不等同于客户端外层请求 envelope；外层 WebSocket 传输契约的唯一权威是 `docs/new_engine/11_PROTOCOL_CATALOG.md`。

### 5.2 Event 总线

领域结果统一转成结构化事件：

```json
{
  "event_type": "room.entered",
  "scope": "presence:88",
  "payload": {}
}
```

这是运行时内部领域事件对象，内部模型可以保留 `event_type`。一旦编码为 WebSocket 服务端应用信封，外层必须依照 `11` 使用 `version / type / seq / ts / payload`；终结响应再额外携带 `request_id`，外层永远不得使用 `event_type`。

## 6. 为什么不沿用 Evennia 的运行时形状

### 6.1 不沿用 Portal / Server

Evennia 源码中：

- `server/service.py` 管游戏逻辑
- `server/portal/service.py` 管协议接入
- 中间靠 AMP 同步 session 与命令流

这在本项目中没有必要，因为：

- WebSocket 与 REST 本就可以在一个 ASGI 体系内完成
- 手机端并不需要 Portal 为 telnet、ssh、mccp、mxp 做隔离
- 额外同步层会让 reconnect、presence、故障恢复更复杂

### 6.2 不沿用 TypedObject 魔法层

Evennia 的 `TypedObject` 把“实体类型、属性、锁、标签、命令、脚本”全部挂在一个统一根上，这个方向对，但实现方式不适合长期维护。

New_Mud 需要：

- 统一实体根
- 显式模型优先
- 运行时类型通过 `kind + blueprint + BehaviorProfileDefinition` 决定

## 7. 引擎与 MUDLib 边界

引擎层负责：

- 连接
- 认证
- 在线状态
- 持久化
- 调度
- 聊天基础设施
- 帮助系统
- Blueprint seed 导入、revision 编译、发布批次与运行时读取服务
- Admin 与审计

MUDLib 层负责：

- 通过包内 `seed/` 文件和 `register_blueprint_seed_providers()` 提供 Blueprint 导入输入，而不是运行时内容真源
- 门派、武功、任务、剧情
- NPC 行为配置
- 掉落、经济、成长规则
- 新手流程与帮助文档
- `HandlerDefinition / RuleDefinition / PermissionPolicyDefinition / HookSetDefinition / ActionProviderDefinition / RenderPolicyDefinition` 的声明式注册
- `ActionDefinition / BehaviorProfileDefinition / EffectTypeDefinition / JobTypeDefinition / WorldProcessTypeDefinition` 的声明式注册
- 启动计划与角色创建配置

## 8. 关键架构原则

1. 引擎核心表结构必须先服务于玩法稳定性，再服务于通用性。
2. 内容包只能通过声明式 registry 注册规则、内容与运行时类型，不能获得自由扩展容器的权限。
3. 文本命令永远只是输入适配器之一，不再是主交互协议。
4. ORM 显式字段优先，JSON 扩展字段次之，任意 pickle 最后且尽量不用。
5. 单实例不是低标准，而是允许我们把一致性做得更强。
6. 当前基线按单实例单写者实现；未来若为了部署形态拆分进程，再补显式协调机制。

## 9. 最终架构口号

抽象借鉴 Evennia，运行时抛弃 Evennia，内容接口超越 Evennia。


