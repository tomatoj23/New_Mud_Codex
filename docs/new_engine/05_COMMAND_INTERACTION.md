# 05 命令系统与交互系统

> 术语说明：本文默认使用 `ConnectionSession / AuthSession / Presence / ActorRef` 等规范术语，不把 `Account` 作为 New_Mud 设计层的默认动作来源名词。

> 实施约束：本文负责说明动作系统的结构与设计方向。`action.invoke`、`ResolvedActionSet`、文本匹配优先级、`ui.actions.resolve`、错误码与事件返回格式以 `docs/new_engine/11_PROTOCOL_CATALOG.md` 为准。
>
> `ActionDefinition / ActionProviderDefinition` schema 与 typed registry 通用字段以 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md` 为唯一权威。

## 1. 目标

New_Mud 必须同时支持两种交互：

- 传统文本输入
- 移动端结构化动作

所以新引擎不应该只有“命令系统”，而应该有“动作系统 + 文本命令适配器”。

## 2. 保留 Evennia 的哪些优点

源码依据：

- `evennia-main/evennia/commands/command.py`
- `evennia-main/evennia/commands/cmdparser.py`
- `evennia-main/evennia/commands/cmdset.py`
- `evennia-main/evennia/commands/cmdhandler.py`

保留内容：

- 命令对象是可测试的执行单元
- 命令有元数据和生命周期
- 动作可来自多个上下文提供者
- 文本匹配支持别名、多词命令与消歧

## 3. 新系统的核心对象

### 3.1 ActionDefinition

定义一个动作的静态信息：

- `key`
- `version`
- `aliases`
- `summary`
- `source_module`
- `tags`（可选）
- `source_scopes`
- `help`
- `argument_schema`
- `permission_policy_key`
- `match_priority`（数值越小越先匹配）
- `handler_key`

补充说明：`ActionDefinition` 首版不冻结通用冷却字段；XKX100 战斗中的 `busy / condition` 与聊天防刷限制属于运行时规则求值。

### 3.2 ActionContext

一次执行所处的上下文：

- `connection`
- `auth_session`
- `presence`
- `actor`
- `room`
- `target_candidates`
- `ui_source`

### 3.3 ActionProviderDefinition

动作来源的 typed registry 定义，替代 Evennia 的 CmdSet provider。它同样包含 `key / version / summary / source_module` 与可选 `tags`，并按 `12` 声明 `source_scopes / action_keys / availability_rule_keys / priority`；首发来源范围包括：

- Connection provider
- AuthSession provider
- Presence provider
- Room provider
- Item provider
- System provider
- Channel provider

## 4. 解析流程

```text
client input
  -> input adapter
  -> ActionContext
  -> collect ActionProviders
  -> resolve available actions
  -> parse args
  -> permission / state / anti-spam checks
  -> execute action
  -> emit events
```

## 5. 文本命令适配器

### 5.1 应保留的 Evennia 经验

- `match_priority` 与 provider priority 相同时，多词命令按最长规范化别名优先
- alias 统一小写化缓存
- `2-ball` 这种多重匹配消歧

### 5.2 不应保留的部分

- 文本命令是唯一动作入口
- nick 替换承担复杂协议层工作
- channel 命令与聊天系统强耦合

## 6. 结构化动作适配器

移动端按钮、菜单、快捷栏不应先拼成字符串再进 parser。

应该直接发送：

```json
{
  "version": "1",
  "request_id": "req_001",
  "type": "action.invoke",
  "payload": {
    "action": "inventory.use_item",
    "args": {"item_id": "item_3001"},
    "expected_inventory_version": 12,
    "source": "ui_button"
  }
}
```

客户端 `payload.source` 只允许 `text_command`、`ui_button`、`ui_menu`、`shortcut`。`source=system` 只允许服务端内部 `NormalizedAction` 使用；客户端尝试发送时，必须以 `request.failed` 和 `ACTION_SOURCE_FORBIDDEN` 终结。

每个可关联请求恰好有一个逻辑终结：成功使用 `request.succeeded`，失败使用 `request.failed`。事务提交后派发的后续领域事件使用外层 `type`，不携带 `request_id`；WebSocket 外层不得使用 `event_type`。

## 7. 动作生命周期

建议保留 Evennia 的生命周期命名：

```text
at_pre_cmd
parse
func
at_post_cmd
```

但含义稍作扩展：

- `at_pre_cmd`
  - 动作级前置校验
- `parse`
  - 文本或结构化 payload 归一化
- `func`
  - 真正修改领域状态
- `at_post_cmd`
  - 记录审计、补发帮助提示、派发统计

## 8. 为什么不保留 CmdSet 原样

Evennia `CmdSet` 很强，但对本项目有三个问题：

1. 合并规则复杂，维护成本高。
2. 房间物体、角色控制上下文、认证会话、连接上下文都能挂命令时，隐式来源会失控。
3. 它天然偏向文本客户端，不天然服务移动端 UI。

替代方案：

- Provider 负责声明动作
- Resolver 负责基于上下文编译当前 `ResolvedActionSet`
- UI 层可以请求“当前可用动作列表”

## 9. 菜单与对话

Evennia 的 `EvMenu` 思想值得保留，但实现应从“命令驱动菜单”升级为“交互流”：

- `DialogueFlow`
- `CharacterCreationFlow`
- `QuestChoiceFlow`

## 10. 自动帮助生成

命令系统必须自带帮助元数据：

- key
- 别名
- 参数说明
- 可见条件
- 用途说明

这样可以同时生成：

- 文本 `help`
- 前端动作说明
- 后台编辑器提示

## 10.1 首批必须冻结的实施项

在真正编码前，以下内容必须视为稳定契约，而不是局部实现细节：

- `ActionDefinition.key` 全局唯一
- Provider 只能暴露/隐藏动作，不重定义同名动作语义
- 解析顺序固定为 `match_priority`（小优先）-> `ActionProviderDefinition.priority`（小优先）-> 最长规范化别名
- 同一 action key 经多个 provider 暴露时先去重，并以最小 provider priority 作为有效优先级；完成全部排序后仍有多个不同 action key 并列，才返回 `ACTION_AMBIGUOUS`
- `ui.actions.resolve` 返回动作卡片 schema 固定
- `ACTION_NOT_FOUND / ACTION_AMBIGUOUS / ACTION_ARGUMENT_INVALID / ACTION_FORBIDDEN` 等错误码固定

## 11. 最终原则

文本命令不是废掉，而是降级为一种入口；动作系统才是新引擎真正的交互核心。

