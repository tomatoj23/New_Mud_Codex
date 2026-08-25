# RecoveryCode、PresenceRecovery 与账号关闭边界

Status: accepted

注册事务一次性展示 `RecoveryCode`，服务端只保存不可逆哈希。密码找回、账号恢复和主动轮换都会签发新 code，并撤销该 User 的全部 AuthSession、RefreshTokenFamily 与未使用票据、终止 active/grace PresenceSnapshot 租约、关闭对应运行时 Presence。恢复操作不会恢复旧 Presence；用户必须重新登录并重新进入世界。

同一 AuthSession 可以通过 `presence.recover` 找回自己仍处于 `active` 或 `grace_disconnected` 的 PresenceSnapshot 租约，即使客户端丢失内存中的 `resume_ticket`。恢复成功时创建并绑定新一代运行时 Presence、递增 generation、撤销旧 ticket、签发新 ticket 并返回完整 snapshot；恢复不接受跨 AuthSession locator，也不把其他会话的占用转化为成功。跨会话控制权转移只能使用显式且获授权的 `presence.takeover`。

账号关闭立即撤销会话和控角租约，并将 GameAccount 置为 `cooling_off`。30 天冷静期内只有有效 RecoveryCode 可以回到 `active`；恢复后不自动恢复 PresenceSnapshot 租约或运行时 Presence。冷静期结束后进入 `retired`，User 数据匿名化/禁用，Character 进入 `RetiredCharacter`，稳定 ID 和必要历史关系继续保留。

该边界把“恢复身份”“恢复控角”和“跨设备接管”分成三个不同动作，避免把持有旧票据、同一登录会话和账号所有权混为一谈。

考虑过的选项：把 RecoveryCode 当作长期登录凭据、让恢复自动复活旧运行时 Presence，或允许恢复请求隐式接管其他 AuthSession。它们都会扩大秘密暴露面或破坏单 PresenceSnapshot 租约与审计边界，因此不采用。
