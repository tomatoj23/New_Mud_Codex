# 每实例一个 User 对应一个 GameAccount

Status: accepted

在每个游戏实例内，一个 `User` 永久映射一个 `GameAccount`；未来多 Character 通过 `CharacterOwnership` 扩展，不复制 GameAccount。该边界把平台登录主体与游戏域账号稳定连接，简化恢复、审计、PresenceSnapshot 控角租约和账号关闭的责任链，同时仍保留未来一账号多角色的迁移空间。

考虑过的选项：允许一个 User 为同一实例创建多个 GameAccount，或把 GameAccount 直接并入 User。前者会使 RecoveryCode、Presence 和封禁边界产生歧义，后者会锁死未来角色归属和运营关系；两者都不采用。
