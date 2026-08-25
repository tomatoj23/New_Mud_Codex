# 07 通信系统分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前领域概念，以根目录 `CONTEXT.md` 为词汇权威；产品范围和产品语义以 `requirements_v6.md` 为权威，其中身份产品语义见第八章；`UBIQUITOUS_LANGUAGE.md` 仅作非权威工程术语索引。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/comms/models.py`
  - `evennia-main/evennia/comms/managers.py`
  - `evennia-main/evennia/comms/comms.py`
  - `evennia-main/evennia/commands/default/comms.py`
- 参考文档：
  - `evennia-main/docs/source/Components/Channels.md`
  - `evennia-main/docs/source/Components/Msg.md`

## 2. Evennia 源码事实

### 2.1 `Msg` 是泛化持久消息模型

`Msg` 模型支持：

- 发送方：账号 / 对象 / 脚本 / 外部字符串
- 接收方：账号 / 对象 / 脚本 / 外部字符串
- `db_header`
- `db_message`
- `db_date_created`
- 隐藏列表
- locks / tags

`Msg` 本身没有 channel receiver 字段；频道实时通信主要走 `ChannelDB + SubscriptionHandler + channel log`。

但在当前 Evennia 6.0 核心里，频道实时发送并不以 `Msg` 作为主存储骨架。`DefaultChannel.msg()` 主要做的是：

- 取订阅者
- 过滤 mute / online 状态
- 实时分发到订阅者
- 追加频道日志

因此更准确的判断是：`Msg` 更接近泛化持久消息模型，适合 page / mail-like 留存与通用消息关系建模；频道系统本身则更偏“订阅分发 + 日志”。

### 2.2 `ChannelDB` 是可 typeclass 的频道

`ChannelDB` 继承 `TypedObject`，对应运行时类 `DefaultChannel`。频道因此拥有：

- key / desc / locks
- typeclass path
- tags / aliases / permissions
- 订阅者集合

### 2.3 订阅关系由处理器托管

订阅关系主要由 `SubscriptionHandler` 管理账号和对象对频道的加入、移除和在线订阅者缓存。`DefaultChannel` 通过公开属性 `mutelist` 访问静音名单，底层数据存放在 `self.db.mute_list`。

### 2.4 文本命令承担聊天入口

新版本 Evennia 已经不再为每个频道自动生成独立命令，而是统一走 `channel` 命令，再借助 nick alias 实现文本快捷方式：

- `channel public hello`
- `public hello`

这本质上仍是“聊天消息通过文本命令路由”。

## 3. 基于源码的评价

### 3.1 值得保留的点

- 频道与订阅关系分离，这个抽象方向是对的。
- 持久消息模型和实时频道分发没有强绑死在一个对象里，这一点反而值得注意。
- 账号和角色都能成为通信主体，符合 MUD 场景。
- 频道具备权限、别名、历史等常见能力，与命令系统、帮助系统衔接顺畅。

### 3.2 不适合本项目的点

- `Msg` 过度通用，后期做审核、未读、索引优化、推送策略会很痛苦。
- 收发件人类型过宽，审计和 UI 语义都不够稳定。
- 入口严重偏向文本命令，不适合 WebSocket / 移动端主交互。
- IC 聊天、OOC 聊天、系统通知、邮件本质上是不同留存策略，继续揉进一个骨架会加剧耦合。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，通信子域更合理的拆分方向是：

- `ChatChannel`
- `ChatSubscription`
- `ChatMessage`
- `DirectMessage`
- `SystemNotice`

通信主体统一收敛到 `ActorRef`，不再并行使用 `SpeakerRef`。聊天入口则更适合以结构化 API / WebSocket 事件为主，文本命令只保留为适配器。

### 4.2 对应的权威文档

- `docs/new_engine/06_CONTENT_CHAT_HELP.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- 领域词汇权威：根目录 `CONTEXT.md`；产品语义权威：`requirements_v6.md`（身份语义见第八章）；工程名称索引：`UBIQUITOUS_LANGUAGE.md`

## 5. 结论

Evennia 通信系统最值得借鉴的是“频道/订阅抽象”和“持久消息模型”这两类能力，而不是把频道实时通信继续等同于 `Msg`。更合理的方向是拆分明确的聊天子域模型，并把结构化事件作为主入口。

