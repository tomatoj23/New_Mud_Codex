# 18 LPC 转换器问题分析（分析层草案）

> 状态：分析层派生设计草案。本文保留为 LPC 转换器问题域分析与早期方案记录，但当前权威转换器规范已迁移至 `docs/new_engine/09_MUDLIB_CONVERTER.md` 与 `docs/new_engine/10_ROADMAP.md`。若有冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“问题边界 / 综合判断 / 方向摘要”整理。它用于说明转换器为什么需要分层、哪些东西可自动迁移、哪些必须人工接管，不再承担正式实施设计职责。

## 1. 问题边界

根据 `requirements_v5.md`，转换器当前只实现 XKX100 的 `ConversionProfile`，将该源 LPC / FluffOS MUDLib 归一化为 New_Mud 可消费的数据、适配入口与审计产物。

其他源 LPC MUDLib 的 `ConversionProfile` 属于未来扩展，必须先通过范围审批，不得作为首发实现的隐含兼容目标。

从问题性质上看，转换目标大体可分为三类：

- 可自动迁移的结构和静态数据
- 可半自动迁移但必须人工复核的逻辑
- 不应自动翻译、而应生成为 stub 或人工重写的复杂行为

## 2. 综合判断

### 2.1 转换器的正确目标不是“翻译全部逻辑”

从 LPC MUDLib 的常见写法看，以下内容通常更适合自动或半自动迁移：

- 房间与出口拓扑
- NPC / 物品基础数据
- 技能元数据
- 帮助文本
- 部分 daemon 配置和启动计划线索

而以下内容通常不适合追求“一键翻译”：

- 复杂战斗公式
- 高度动态的 `call_out`
- 复杂 daemon 交互
- 大量宏驱动行为逻辑
- 安全敏感和权限敏感代码

### 2.2 转换器必须是分阶段流水线

从问题复杂度看，转换器不可能只是一个 parser。它至少隐含以下阶段：

- 扫描
- 解析
- 归一化
- 发射
- 校验
- 报告

如果没有这些分层，转换器要么会过度耦合，要么无法留下可靠的人工审核痕迹。

### 2.3 稳定目标格式比“翻译过程”更重要

转换器最终能否落地，不取决于它是否把 LPC 全翻成 Python，而取决于：

- 是否有稳定的 MUDLib 接口
- 是否有稳定的 `Blueprint` 与帮助内容格式
- 是否能明确生成 unresolved report 和人工补全入口

## 3. 对 New_Mud 的方向摘要

### 3.1 方向摘要

从分析层看，更稳定的落地方向是：

- 转换器输出标准 `Blueprint`、帮助文档、启动计划和规则 stub
- 使用 `ConversionProfile` 承载源 MUDLib 的受控差异；首发只注册 XKX100
- 自动迁移结构与静态数据
- 对复杂逻辑显式生成报告、stub 和人工审核入口

这些内容在权威设计层已经展开为流水线阶段、输出目录和验收标准；本文不再继续规定实施细节。

### 3.2 对应的权威文档

- `docs/new_engine/09_MUDLIB_CONVERTER.md`
- `docs/new_engine/10_ROADMAP.md`
- `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
- `docs/new_engine/14_COMBAT_SKILL_ITEM_CONTRACT.md`
- `docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`

## 4. 结论

MUDLib 转换器不应追求“一键把 LPC 逻辑全部翻成 Python”。分析层能确认的更现实目标是：先把结构、数据和大部分静态规则安全迁移到标准 MUDLib 落点，再把复杂逻辑生成为可审核、可继续开发的 stub 和报告。


