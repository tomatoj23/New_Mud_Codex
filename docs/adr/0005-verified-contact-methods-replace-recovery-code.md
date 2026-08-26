# 已验证联系方式取代 RecoveryCode

Status: accepted

决定：以 User 已证明控制的 `VerifiedContactMethod` 和按用途、渠道、目标及适用 User 隔离的短期单次 `VerificationChallenge` 取代 RecoveryCode；新注册先验证邮箱，未来可独立增加短信，登录仍只使用账号名和密码，RecoveryCode 只保留为已撤销的历史审计事实。

原因与取舍：该模型避免邮寄或并存长期恢复秘密；既有账号均为非生产开发测试数据，因而不承诺旧 code 兼容恢复，也不允许支持人员依据游戏资料重分配所有权。

本 ADR 取代 ADR-0004 的 RecoveryCode 决策，但保留其会话撤销与控角分离边界；具体生命周期、唯一性、恢复和投递规则以 V6、08、13、16 为权威，Character、Presence、PresenceRecovery 和 takeover 不进入本次认证基线修订。
