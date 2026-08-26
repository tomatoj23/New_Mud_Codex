# 已验证联系方式采用加密值与 keyed lookup digest

Status: accepted

决定：`VerifiedContactMethod` 是邮箱与未来手机号的唯一权威来源，Django `User.email` 保持为空；规范化值采用应用层加密，并以独立密钥生成的 keyed lookup digest 支持唯一性和精确查询，各类认证、投递和加密密钥彼此独立，界面及日志只使用遮罩值。

该方案避免双写真源与数据库导出泄漏，同时保留向权威地址投递的能力；字段、轮换和运维细节以 V6、08、13、16 为权威。
