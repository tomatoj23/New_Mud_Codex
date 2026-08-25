# 17 MUDLib 边界研究（分析层草案）

> 状态：分析层派生设计草案。本文保留为 MUDLib 边界研究记录，但当前权威接口与落地规范已迁移至 `docs/new_engine/02_ARCHITECTURE.md` 与 `docs/new_engine/09_MUDLIB_CONVERTER.md`。若有冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“问题边界 / 综合判断 / 方向摘要”整理。它用于解释 MUDLib 为什么必须存在、边界大致在哪里，不再承担正式接口规范职责。

## 1. 问题边界

根据 `requirements_v6.md`，MUDLib 接口问题至少包含以下约束：

- 一个服务器实例只加载一个 MUDLib
- 启动时绑定，不支持运行时热切换
- 当前主线默认只加载 XKX100 原生内容包，并预留源 LPC MUDLib 向该接口归一化迁移的落点

同时，这里的“不支持热加载”指运行中的服务不切换整个 MUDLib 包，也不热替换其中的 Python 代码；通过 Admin / Blueprint 管理的数据刷新，不等于替换整个 MUDLib。

## 2. 综合判断

### 2.1 为什么必须把引擎和 MUDLib 分开

从账号、会话、对象、命令、内容模板、帮助和后台等分析结果看，引擎层负责的是：

- 连接
- 认证
- 持久化
- 在线状态
- 调度
- API / 后台
- 内容装载基础设施

而 MUDLib 层负责的是：

- 世界内容
- 门派、技能、任务、剧情
- 规则参数与规则注册
- 游戏文案与帮助内容

如果不把两者分开，引擎就会重新退化成“业务规则与基础设施缠在一起”的大工程。

### 2.2 MUDLib 应是受控注册点，不是自由插件系统

从转换器和长期维护角度看，MUDLib 更适合作为：

- 内容模板的标准落点
- 规则注册的受控入口
- 启动计划和文档内容的承载层

它不适合成为一个“可任意改写引擎容器”的自由插件系统。

## 3. 对 New_Mud 的方向摘要

### 3.1 方向摘要

从分析层看，更稳定的边界方向是：

- 启动期绑定单 MUDLib
- MUDLib 通过受控入口暴露内容和规则，而不是任意改写引擎容器
- 引擎只向 MUDLib 暴露稳定 facade，而不是底层容器
- `Blueprint`、帮助、角色创建配置和规则注册更适合作为主要装载面

这些边界在权威设计层已经细化为 manifest、entry、registry 和 facade 等具体形状；本文不再继续规定接口细节。

### 3.2 对应的权威文档

- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/09_MUDLIB_CONVERTER.md`
- `docs/new_engine/10_ROADMAP.md`
- `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`

## 4. 结论

MUDLib 接口问题的重点不是“允许任意代码扩展”，而是“给内容与规则一个稳定、可迁移、可被转换器产出的标准落点”。分析层能确认的是：它应是引擎和游戏内容之间的受控边界，而不是重新造一个插件系统。


