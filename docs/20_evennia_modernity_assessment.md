# Evennia 6.0 现代性与参考价值评估

> 状态：分析层补充文档。本文只评估本地 `evennia-main/` 6.0.0 快照，不创造产品需求或实施契约；New_Mud 的产品、实施与状态权威仍按 `19_documentation_governance.md` 确定。
>
> 评估日期：2026-08-22。本文未联网核对快照之后的 Evennia 变化。

## 1. 结论

Evennia 6.0 **没有整体落后于时代**，但**不适合作为 New_Mud 的整体架构模板**。

- 它仍是维护活跃、功能完整、工程成熟的传统 MUD/MU* 框架。
- 它的运行时形状由 telnet、多协议、动态脚本、在线建造和长期兼容塑造；对这些目标仍然合理。
- 对 Web-first、PC/移动 H5 双端、结构化协议、强数据约束的 New_Mud，Portal/Server/AMP、WSGI Web 层、内置 WebClient、动态 Typeclass、任意 pickle Attribute 和 Lockstring 已显陈旧或方向不合。
- 命令生命周期、上下文动作合并、对象移动 Hook、外观渲染、Prototype、帮助、频道和会话问题域仍有很高参考价值。

最合适的定位是：**把 Evennia 当作成熟问题清单和领域流程样本，而不是代码或运行时底座。**

## 2. 判断依据

“是否落后”必须区分发布新旧、技术维护、架构目标和项目适配性。

| 维度 | 判断 | 对 New_Mud 的意义 |
| --- | --- | --- |
| Python/Django 与维护状态 | 不落后 | 6.0.0 发布于 2026-02-15，支持 Python 3.12-3.14、Django 6.0 和 Twisted 24 |
| 传统 MUD 协议 | 仍然很强 | telnet、SSL、SSH、WebSocket 等统一接入仍是其核心优势 |
| 运行时进程模型 | 成熟但历史负担重 | Portal/Server/AMP 对单实例 Web-first 项目增加同步和恢复成本 |
| 默认 Web 客户端 | 明显陈旧 | 默认 WebClient 和协议形状不适合现代 H5 状态管理与移动交互；Django Web 整合能力本身仍可用 |
| 数据与领域建模 | 灵活但弱 schema | 动态类与 pickle 便于建造，却不利于数据库约束、迁移、审计和类型检查 |
| 命令、对象与内容抽象 | 仍然优秀 | 值得保留流程和不变量，重新实现接口与持久结构 |

版本与依赖证据见 [`evennia-main/pyproject.toml`](../evennia-main/pyproject.toml) 和 [`CHANGELOG.md`](../evennia-main/CHANGELOG.md)。发布得新并不意味着所有内部设计都面向现代 Web；Evennia 6.0 仍在有意维护传统 MUD 的架构兼容性。

## 3. 已显陈旧或不适合 New_Mud 的部分

### 3.1 Portal / Server / AMP

Evennia 由 Portal 接入网络协议、Server 承载游戏逻辑，两者通过 AMP 同步 Session 和命令流。

相关实现见 [`server/service.py`](../evennia-main/evennia/server/service.py)、[`portal/service.py`](../evennia-main/evennia/server/portal/service.py) 和 [`portalsessionhandler.py`](../evennia-main/evennia/server/portal/portalsessionhandler.py)。

它能隔离网络接入、承载多协议，并支持游戏 Server 重载时尽量保留连接，因此不是错误设计。问题在于 New_Mud 只做单实例、单写者和 H5/WebSocket 主通道，这套形状会额外增加：

- ConnectionSession、AuthSession、Presence 的跨进程同步；
- reconnect、takeover、ticket 和 generation 的一致性难度；
- 数据库提交、运行时激活、旧端失权和事件投递之间的协调成本；
- 日志追踪、停机恢复和故障排查的复杂度。

New_Mud 应保留“接入层与领域层分离”的思想，但用统一 Django ASGI/Channels 生命周期实现。

### 3.2 WSGI Web 层与内部代理

Evennia Server 创建 WSGI WebServer 和线程池，Portal 再提供内部反向代理与独立 WebSocket 接入。它在 Twisted 体系内完整可用，但不如原生 ASGI 适合统一 REST、WebSocket、认证、限流、trace、异常处理和健康检查。

### 3.3 默认 WebClient

默认 WebClient 仍使用 jQuery 3.2.1、Bootstrap 4.0.0 beta、全局 JavaScript 插件和 WebSocket/AJAX 兼容层。

对应证据见 [`webclient/base.html`](../evennia-main/evennia/web/templates/webclient/base.html) 与 [`webclient/js/evennia.js`](../evennia-main/evennia/web/static/webclient/js/evennia.js)。

它适合传统桌面式 MUD 窗口，但不适合 New_Mud 所需的 Vue 3/TypeScript/Pinia、响应式双端布局、结构化 Action/Snapshot、幂等终结、重连屏障、IME、触控和无障碍验收。前端工程形状不应借鉴。

### 3.4 动态 Typeclass 与任意 Attribute

Typeclass 通过数据库中的 Python class path 和运行时改写 `self.__class__`，为同一数据库骨架附加行为，见 [`typeclasses/models.py`](../evennia-main/evennia/typeclasses/models.py)。

Attribute 又允许保存任意可 pickle Python 数据，见 [`typeclasses/attributes.py`](../evennia-main/evennia/typeclasses/attributes.py) 和 [`utils/dbserialize.py`](../evennia-main/evennia/utils/dbserialize.py)。

这对通用框架、在线建造和未知游戏类型非常灵活，但会削弱：

- 静态类型检查和代码导航；
- 数据库约束、索引与可查询性；
- schema 迁移、历史数据恢复与类重命名安全性；
- 领域不变量的可发现性；
- AI 和新开发者理解状态来源的能力。

New_Mud 面向明确的 XKX100 领域，应采用显式 ORM 模型、组合式服务、受控 Registry 和版本化内容引用；JSON 只承担受 schema 约束的扩展数据。

### 3.5 Lockstring 权限 DSL

Evennia 用 `edit:perm(Builder) AND ...` 一类字符串表达权限，见 [`locks/lockhandler.py`](../evennia-main/evennia/locks/lockhandler.py)。它比把权限散落在命令中成熟，但引用和参数藏在字符串里，难以静态检查、重构、跳转、生成权限矩阵和形成审计证据。

New_Mud 应保留“主体、目标、上下文共同求值”的思想，改用显式 PermissionPolicy/Rule 定义、固定 schema 和稳定错误码。

### 3.6 文本命令中心化

Evennia 的主路径是原始字符串、CmdSet 合并、parser 匹配、权限检查、`parse/func` 和前后 Hook，见 [`commands/cmdhandler.py`](../evennia-main/evennia/commands/cmdhandler.py) 与 [`commands/command.py`](../evennia-main/evennia/commands/command.py)。

该模型非常适合 telnet，但 New_Mud 还需处理按钮、菜单、快捷键、移动端控件、并发版本、`request_id` 和幂等重放。结构化操作不应先翻译成文本；文本解析器只应是统一 Action 总线的一种输入适配器。

## 4. 仍然值得借鉴的部分

### 4.1 命令与动作生命周期

应保留输入标准化、上下文动作来源合并、歧义处理、权限先行、`pre/execute/post`、稳定失败反馈和异常隔离。应重写的是协议和数据结构，而不是这些流程经验。

### 4.2 移动、观察与消息 Hook

Evennia 对移动前校验、离开源位置、位置更新、进入目标位置、失败恢复、观察者相关渲染和消息前后处理积累了成熟顺序，见 [`objects/objects.py`](../evennia-main/evennia/objects/objects.py)。New_Mud 可将其转写为领域服务、数据库事务、结构化事件和 RenderPolicy。

### 4.3 连接、账号与角色的问题边界

Evennia 的具体 SessionHandler 不宜照搬，但它长期处理了“连接不等于账号、账号不等于角色、多连接控制、断线与重载”等真实问题。New_Mud 的 ConnectionSession/AuthSession/Presence 三分法可继续吸收这些经验，并以更明确的持久与运行时边界实现。

### 4.4 Prototype、帮助、频道和内容工作流

Prototype 的标准化、继承、合并与 spawn，命令/文件/数据库帮助的统一检索，频道成员与消息广播，以及后台内容制作流程都仍有价值。New_Mud 应在此基础上补上不可变 draft/published revision、完整发布批次、exact dependencies、compiler contract、active batch 与 pinned historical revision 分离，以及可复现回滚。

## 5. 对 New_Mud 的使用原则

Evennia 适合继续承担三种参考角色：

1. **问题清单**：确认成熟 MUD 必须处理的命令歧义、移动失败、断线、重载、消息路由、帮助权限和对象生成等边缘情况。
2. **领域流程样本**：借鉴命令生命周期、移动 Hook、外观渲染、Prototype、频道和帮助系统。
3. **反面边界样本**：识别动态换类、任意 pickle、字符串 DSL、过度通用 Script 和文本命令中心化对强约束工程的代价。

Evennia 不应作为以下领域的现代最佳实践：

- ASGI/WebSocket 服务架构与 H5 前端；
- JWT/Refresh Token、幂等请求与终结重放；
- 强 schema 领域建模和 PostgreSQL 事务不变量；
- 不可变内容发布、exact dependency 与恢复门禁；
- 现代可观测性、安全和移动端验收。

无需因为这些限制删除或替换 6.0.0 快照。固定快照能保证源码审计结论可复查；实际实现时，应同时参考当前 Django/ASGI、数据库、安全和前端资料，而不能从 Evennia 一项来源推导现代实现细节。

## 6. 最终判断

Evennia 6.0 是**现代维护中的传统架构**：在传统 MUD 领域没有失去价值，在 Web-first 游戏后端领域则带有明显历史包袱。

New_Mud 当前“抽象借鉴 Evennia、运行时抛弃 Evennia”的方向正确。继续保留它作为固定参考源码，选择性吸收领域经验，并独立实现 ASGI、结构化协议、显式模型和内容发布系统，是风险最低且最符合项目目标的做法。对应的借鉴/重写边界见 [`new_engine/01_BORROW_REWRITE_MATRIX.md`](new_engine/01_BORROW_REWRITE_MATRIX.md)。
