# 验证消息通过持久投递 outbox 发送

Status: accepted

决定：注册验证、密码重置及后续联系方式操作通过 PostgreSQL 持久 outbox 投递，HTTP 响应路径不连接 SMTP；独立 worker 有界重试同一逻辑 challenge，公开响应保持非枚举，账号名和密码登录不依赖投递服务。

该方案以可恢复投递和 SMTP 隔离换取异步复杂度，并拒绝会泄漏时序或账号资格的同步发信与 provider 结果透传方案。

验证码保护、激活、TTL、幂等、熔断和失败关闭细节以 V6、08、13、16 为权威。
