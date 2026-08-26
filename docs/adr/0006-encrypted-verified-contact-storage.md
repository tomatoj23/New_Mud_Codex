# 已验证联系方式采用加密值与 keyed lookup digest

Status: accepted

`VerifiedContactMethod` 是邮箱和未来手机号的唯一权威来源；Django `User.email` 保持为空，业务代码不得读取或镜像它。规范化联系方式以应用层加密值保存，并以独立密钥生成的 lookup digest 承担唯一性与精确查询；密文携带 `key_id` 以支持密钥轮换。联系方式加密密钥、lookup 密钥、验证码 pepper、Django SECRET_KEY、SMTP 授权码和 token key 必须彼此独立，日志、审计与普通管理界面只使用遮罩值。

考虑过在 `User.email` 与联系方式表之间双写、只依赖数据库磁盘加密，以及只保存不可逆摘要。双写会产生两个验证状态真源，磁盘加密不能保护被导出的数据库或备份，而不可逆摘要无法支持向权威地址投递，因此不采用。
