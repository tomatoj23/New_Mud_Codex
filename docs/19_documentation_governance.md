# 19 文档体系与勘误说明

## 1. 目的

本文件用于定义 `docs/` 与 `docs/new_engine/` 的文档层级、冲突处理规则与推荐阅读顺序，避免同一主题出现双重权威。

## 2. 当前文档分层

### 2.1 产品需求：`requirements_v5.md`

- 定义产品目标、范围、首发边界、里程碑与验收结果，是这些关注点的权威来源。
- `UBIQUITOUS_LANGUAGE.md` 是术语伴随文档，不得覆盖产品需求。

### 2.2 冻结实施合同：`docs/new_engine/11-16`

- 定义编码、联调、测试必须遵守的协议字段、状态机、持久结构、事务、失败语义和工程门禁。
- 对上述实施关注点，冻结合同是权威来源；V5 中的重复摘要不能覆盖合同细节。
- 合同冻结后，只能通过第 3 节的有意变更流程修改。
- `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` 是首发战斗、技能与物品实施合同。
- `docs/new_engine/15_FRONTEND_H5_CONTRACT.md` 是首发 H5 前端实施合同。
- `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` 是首发运维与测试实施合同。

### 2.3 需求追踪：`docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`

- 维护稳定需求 ID，以及需求、实施合同、里程碑和验收证据之间的映射。
- 它不创造新需求或实施语义；发现缺口时必须回到 V5 或对应合同修改。

### 2.4 概念设计：`docs/new_engine/00-10`

- 记录正式架构、模块边界、借鉴策略与路线图。
- 用于解释“为什么这样设计”，但不得覆盖产品需求或冻结实施合同。

### 2.5 分析层：`docs/00-18`

- 记录 Evennia 6.0 本地源码事实、模块优缺点与需求对照分析。
- 允许保留阶段性设计建议，但这些建议不是当前权威实施规范。

### 2.6 实现层

- 代码、迁移、配置和测试反映当前实现状态，但不能反向成为设计权威。
- 实现必须符合上层需求与合同；偏离时按缺陷或有意变更处理。

## 3. 冲突与变更规则

冲突按关注点判定，不再使用覆盖所有问题的单一文件总排序：

| 关注点 | 权威来源 |
| --- | --- |
| 产品目标、范围、里程碑、发布方式和验收结果 | `requirements_v5.md` |
| 协议字段、状态机、持久结构、事务、失败语义和测试机制 | 对应的 `docs/new_engine/11-16` |
| 术语边界 | V5 第八章；`UBIQUITOUS_LANGUAGE.md` 负责统一表达 |
| 需求到合同和证据的映射 | `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` |
| 架构理由和模块方向 | `docs/new_engine/00-10` |
| Evennia 来源事实 | `docs/00-18` 与本地 `evennia-main` 快照 |

代码偏离上层需求或冻结合同即为缺陷，除非该偏离已经按有意变更流程批准。

不得仅为了使未经批准的代码漂移显得合理而重写设计文档。

改变产品结果时，必须先更新 V5，再同步合同、追踪索引、概念说明、实现和测试。

只改变实施机制且不改变产品结果时，先修改对应冻结合同和追踪索引，再修改实现与测试；不为了形式同步而向 V5 复制字段和流程。

无法判断属于产品还是实施关注点时，变更必须阻断，由需求与合同所有者共同裁决并在同一变更中消除冲突。

如果 `docs/00-18` 内部互相矛盾，应回到更贴近源码事实的模块分析文档；`docs/16-18` 只作为分析派生的综合判断或边界研究。

## 3.1 术语权威来源

- 当前术语权威来源为 `requirements_v5.md` 第八章与 `UBIQUITOUS_LANGUAGE.md`。
- 当两者表述粒度不同或发生冲突时，以 `requirements_v5.md` 为准；`UBIQUITOUS_LANGUAGE.md` 负责跨文档统一命名与边界说明。
- `docs/new_engine/*` 与 `docs/00-18` 若涉及 New_Mud 当前正式术语，应同时对齐 `requirements_v5.md` 与 `UBIQUITOUS_LANGUAGE.md`；若为了描述 Evennia 现状而出现旧词，应在上下文中明确那是来源术语，而不是 New_Mud 设计术语。

## 4. 推荐阅读顺序

- 需要先确认名词边界时，先看 `requirements_v5.md` 第八章，再看 `UBIQUITOUS_LANGUAGE.md`。
- 需要追源码依据时，先看 `docs/01-15`。
- 需要理解分析阶段如何从模块判断收敛到总体方案时，再看 `docs/16-18`。
- 需要理解概念架构与路线时，看 `docs/new_engine/00-10`。
- 需要从需求定位合同和验收证据时，看 `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`。
- 开始编码、联调或验收前，必须读取受影响的冻结合同：
  - `docs/new_engine/11_PROTOCOL_CATALOG.md`：WebSocket 协议名、错误码与事件外壳
  - `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`：Registry、Blueprint 与发布更新
  - `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`：连接、认证、refresh 与在线状态
  - `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md`：战斗、技能与物品
  - `docs/new_engine/15_FRONTEND_H5_CONTRACT.md`：H5 前端交互与状态
  - `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`：运维、可观测性与测试门禁

## 5. 逐篇映射关系

| 分析层文档 | 当前定位 | 主要对应的设计层文档 |
| --- | --- | --- |
| `docs/00_analysis_completion_record.md` | 分析阶段入口与完成记录 | `docs/new_engine/00_README.md` |
| `docs/01_typeclass_system.md` | Typeclass/实体抽象研究 | `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`、`docs/new_engine/04_DOMAIN_WORLD_MODEL.md` |
| `docs/02_object_system.md` | 对象模型与生命周期研究 | `docs/new_engine/04_DOMAIN_WORLD_MODEL.md` |
| `docs/03_account_system.md` | 账号、角色与身份边界研究 | `docs/new_engine/03_RUNTIME_SESSIONS.md`、`docs/new_engine/08_PERMISSIONS_ADMIN_API.md` |
| `docs/04_command_system.md` | 命令解析与执行流程研究 | `docs/new_engine/05_COMMAND_INTERACTION.md` |
| `docs/05_script_system.md` | 调度、任务与效果系统研究 | `docs/new_engine/07_SCHEDULER_EFFECTS.md` |
| `docs/06_lock_system.md` | 权限表达与授权机制研究 | `docs/new_engine/08_PERMISSIONS_ADMIN_API.md` |
| `docs/07_comm_system.md` | 聊天、消息与频道系统研究 | `docs/new_engine/06_CONTENT_CHAT_HELP.md` |
| `docs/08_server_architecture.md` | 运行架构与进程模型研究 | `docs/new_engine/02_ARCHITECTURE.md`、`docs/new_engine/03_RUNTIME_SESSIONS.md` |
| `docs/09_session_management.md` | 会话与连接状态研究 | `docs/new_engine/03_RUNTIME_SESSIONS.md` |
| `docs/10_prototype_system.md` | Prototype/Blueprint 思路研究 | `docs/new_engine/06_CONTENT_CHAT_HELP.md`、`docs/new_engine/09_MUDLIB_CONVERTER.md` |
| `docs/11_help_system.md` | 帮助内容、检索与分类研究 | `docs/new_engine/06_CONTENT_CHAT_HELP.md` |
| `docs/12_utils.md` | 基础工具与可复用组件观察 | `docs/new_engine/01_BORROW_REWRITE_MATRIX.md` |
| `docs/13_web_layer.md` | REST/Web/API 边界研究 | `docs/new_engine/03_RUNTIME_SESSIONS.md`、`docs/new_engine/08_PERMISSIONS_ADMIN_API.md` |
| `docs/14_database_design.md` | ORM、表结构与序列化研究 | `docs/new_engine/04_DOMAIN_WORLD_MODEL.md`、`docs/new_engine/08_PERMISSIONS_ADMIN_API.md` |
| `docs/15_contrib_highlights.md` | Evennia 经验与可借鉴点汇总 | `docs/new_engine/01_BORROW_REWRITE_MATRIX.md`、`docs/new_engine/10_ROADMAP.md` |
| `docs/16_architecture_overview.md` | 分析派生的总体架构综合判断 | `docs/new_engine/02_ARCHITECTURE.md`、`docs/new_engine/10_ROADMAP.md` |
| `docs/17_mudlib_interface.md` | 分析派生的 MUDLib 边界研究 | `docs/new_engine/02_ARCHITECTURE.md`、`docs/new_engine/09_MUDLIB_CONVERTER.md` |
| `docs/18_mudlib_converter.md` | 分析派生的 LPC 转换器问题分析 | `docs/new_engine/09_MUDLIB_CONVERTER.md`、`docs/new_engine/10_ROADMAP.md` |

### 5.1 冻结合同映射

| 冻结合同 | 主要实现范围 |
| --- | --- |
| `docs/new_engine/11_PROTOCOL_CATALOG.md` | WebSocket 请求、终结结果、命令、错误码与结构化事件 |
| `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` | Registry 生命周期、Blueprint 编译、发布与安全更新 |
| `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md` | `ConnectionSession`、`AuthSession`、access/refresh 状态、`Presence` 与恢复流程 |
| `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md` | 首发战斗循环、技能注册与物品状态 |
| `docs/new_engine/15_FRONTEND_H5_CONTRACT.md` | 首发 H5 页面、交互、缓存与重连行为 |
| `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md` | 首发部署、迁移、监控、备份与测试门禁 |

`docs/new_engine/11_PROTOCOL_CATALOG.md` 只冻结 WebSocket 协议，不负责 REST 端点。REST 端点、后台 API 边界与首发 H5 auth 传输归 `docs/new_engine/08_PERMISSIONS_ADMIN_API.md` 4.2；
认证状态、token family、refresh 轮换、幂等保留与 replay 约束归 `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`。

### 5.2 需求追踪映射

| 追踪文档 | 主要职责 |
| --- | --- |
| `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` | 维护稳定需求 ID，并连接 V5 来源、实施权威、需求里程碑和必要证据；不创造产品或实施语义 |

## 6. 持续治理风险与已核验状态

已核验状态：

- 当前权威规则已改为按关注点判定：产品结果归 V5，实施机制归冻结合同，术语和追踪分别由伴随文档负责。
- `docs/00_analysis_completion_record.md` 已明确分析层定位，并已把编码前导航扩展到 `docs/new_engine/11-16` 六份冻结实施合同和 `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`。
- 命令、调度、服务器架构、Web 层及 `docs/16-18` 的高冲突内容已完成第二批分层治理；旧问题不再作为仍待修复的当前缺陷列示。

仍需持续防范：

- 术语漂移：新增或改写 New_Mud 设计名词时，未先对齐 `requirements_v5.md` 与 `UBIQUITOUS_LANGUAGE.md`。
- 实现漂移：代码、迁移或测试偏离冻结合同，却反向修改文档为未经批准的实现背书。
- 分层回退：把实施 schema、协议字段或当前代码细节重新写入分析层，导致分析文档与冻结合同再次形成双重权威。

## 7. 后续整理原则

- 分析层优先保留源码事实、优缺点、问题清单与引用依据。
- 概念设计层负责统一术语、定义边界与维护路线图。
- 冻结合同层负责锁定编码、联调、测试与验收接口。
- 如果未来重写 `docs/00-18`，建议采用“事实 / 评价 / 方向摘要”一类结构，减少层级混写。
- 当前已重构的高冲突分析文档，优先把正式实施细节下沉到 `docs/new_engine/*`，分析层只保留源码事实、评价与方向摘要。
- 当前已完成第二批重构的文档包括命令、调度、服务器架构、Web 层，以及 `16-18` 的综合判断 / 边界研究 / 问题分析文档。
- 当前 `docs/00-18` 已纳入上述分层治理；后续修订必须保持需求、冻结合同、概念设计与分析层的边界，不得把实施细节重新写回分析层。


