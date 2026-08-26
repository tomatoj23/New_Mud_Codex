# Access Token 必须解析到 active AuthSession

Status: accepted

JWT 签名、受众和到期时间只是 Access Token 有效性的必要条件，不是充分条件。每个受保护的 HTTP 或 WebSocket 入口都必须把 token 中的定位信息解析到仍为 `active` 的 AuthSession，并重新确认 User 与适用 GameAccount 没有被禁用、关闭或退休；密码重置、账号重新启用、联系方式换绑、管理员撤销、logout 或 refresh replay 一旦提交，旧 access 与 refresh 凭据都立即失效。注册和成功恢复仍不自动创建 AuthSession。

这让 access token 成为短期会话定位凭据，而不是撤销后仍可独立授权到自然过期的完全无状态 grant。考虑过只撤销 refresh credential 并允许旧 access JWT 存活到15分钟到期；该方案会使“撤销全部认证状态”的用户承诺在最敏感的恢复操作后不成立，因此不采用。
