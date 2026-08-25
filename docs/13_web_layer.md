# 13 Web 层分析

> 状态：分析层文档。本文用于记录 Evennia 6.0 源码事实、优缺点与初步判断，不是 New_Mud 当前权威实施规范。若与 `docs/new_engine/` 冲突，以 `docs/new_engine/` 为准。详见 `docs/19_documentation_governance.md`。

> 结构说明：本文按“事实 / 评价 / 设计去向”整理。凡涉及 New_Mud 当前领域术语，以 `requirements_v6.md` 第八章与根目录 `CONTEXT.md` 为权威；`UBIQUITOUS_LANGUAGE.md` 仅作非权威工程术语索引，`requirements_v5.md` 仅作历史对照。

## 1. 分析范围

- 源码入口：
  - `evennia-main/evennia/web/README.md`
  - `evennia-main/evennia/web/urls.py`
  - `evennia-main/evennia/web/website/`
  - `evennia-main/evennia/web/api/`
  - `evennia-main/evennia/web/admin/`
  - `evennia-main/evennia/web/webclient/`
- 参考文档：
  - `evennia-main/docs/source/Components/Website.md`
  - `evennia-main/docs/source/Components/Webserver.md`
  - `evennia-main/docs/source/Components/Webclient.md`
  - `evennia-main/docs/source/Components/Web-API.md`
  - `evennia-main/docs/source/Components/Web-Admin.md`

## 2. Evennia 源码事实

### 2.1 Web 层本质上是 Django 应用

Evennia 的 Web 层包括：

- `website`
- `api`
- `admin`
- `webclient`

但对外托管方式仍然服从 `Portal / Server` 分工：Server 侧起内部 Django WSGI，Portal 侧负责反向代理、AJAX 入口和 WebSocket 端口。

### 2.2 Website 是默认玩家门户

默认网站提供：

- 首页
- 登录 / 注册
- 角色展示
- 频道展示
- 帮助浏览
- 在线游玩入口

### 2.3 Webclient 仍以文本客户端为中心

Webclient 由 Django template、JavaScript 客户端对象、plugin manager、WebSocket / AJAX 通道组成，本质上是“浏览器里的文本 MUD 客户端”。本地快照的默认页面还使用 jQuery 3.2.1、Bootstrap 4.0.0 beta 和全局插件管理器；这说明陈旧点主要在默认客户端工程形状，不等于 Django Web 整合能力失效。

### 2.4 REST API 围绕内部模型设计

`api/views.py` 和 `api/serializers.py` 展示出 Evennia 的 API 设计特点：

- 直接以 `ObjectDB / AccountDB / ScriptDB / HelpEntry` 为 ViewSet 主体
- 以 DRF `ModelViewSet` 为基础
- 暴露 `attributes / nicks / contents / session_ids` 等内部投影
- 对动态属性额外提供自定义动作

### 2.5 Django Admin 是深度定制过的生产工具

Evennia 明确复用了 Django Admin，并为对象、属性、帮助、频道等提供了专门 admin 类。这对世界编辑和内容制作很有帮助。

## 3. 基于源码的评价

### 3.1 值得保留的点

- Django 生态成熟，后台能力强。
- 网站、Admin、API、Webclient 共用同一数据域，整合成本低。
- 管理后台对 Builder 和运营很友好。
- Web 层和游戏数据库天然连通，适合快速做管理工具。

### 3.2 不适合本项目的点

- 本项目主前端是 `uni-app`，不是浏览器文本终端。
- Twisted 内嵌 Web server 与既定 `Django + Channels` 路线不一致。
- REST API 直接暴露内部对象模型，会让前端过度耦合后端实现。
- 玩家站点、运营后台、内容编辑后台需要更清晰的边界。

## 4. 对 New_Mud 的设计去向

### 4.1 方向摘要

从分析层看，Web 层更合理的收敛方向是：

- 面向前端产品的 REST / WebSocket 契约
- 面向内容制作和运营的后台
- 面向导入器和内部工具的开发接口

Webclient 若保留，更适合作为调试或 GM 工具，而不再是产品中心。对外 API 也不适合直接复制 Evennia 的内部模型 CRUD 形态。

### 4.2 对应的权威文档

- `docs/new_engine/02_ARCHITECTURE.md`
- `docs/new_engine/03_RUNTIME_SESSIONS.md`
- `docs/new_engine/06_CONTENT_CHAT_HELP.md`
- `docs/new_engine/08_PERMISSIONS_ADMIN_API.md`
- `docs/new_engine/11_PROTOCOL_CATALOG.md`
- `docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md`
- `docs/new_engine/15_FRONTEND_H5_CONTRACT.md`

## 5. 结论

Evennia Web 层最值得借鉴的是“网站、后台、API 共用同一数据域”的整合方式。分析层对应的结论是：不继承 Twisted 托管和文本 Webclient 中心化，而转向 API-first、PC/移动 H5 双端、后台内容制作优先的 Web 架构。这里的判断是项目适配性取舍，不是认定 Evennia 的 Django 能力过时。

