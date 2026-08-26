# Access Token 必须解析到 active AuthSession

Status: accepted

决定：每个受保护的 HTTP 或 WebSocket 入口都必须把 Access Token 解析到仍为 `active` 的 AuthSession，并确认 User 与适用 GameAccount 仍可用；安全敏感撤销一经提交，既有 access 与 refresh 凭据立即失效，注册和恢复不自动创建 AuthSession。

该方案把 token 限定为短期会话定位凭据，拒绝让已撤销 access JWT 存活到自然到期；具体撤销事件与入口规则以 V6、08、13、16 为权威。
