const ERROR_MESSAGES: Record<string, string> = {
  CONTACT_INVALID: "请输入可用的邮箱地址。",
  CONTACT_CHANNEL_UNAVAILABLE: "当前暂不支持这种验证方式。",
  VERIFICATION_RATE_LIMITED: "请求过于频繁，请在倒计时结束后再试。",
  VERIFICATION_CODE_INVALID: "邮箱验证码无效或已过期，请重新获取。",
  VERIFICATION_SERVICE_UNAVAILABLE: "邮箱验证暂时不可用，请稍后再试。",
  REGISTRATION_INVALID: "账号名或密码不符合要求。账号名须为 3–32 位字母、数字或下划线。",
  REGISTRATION_UNAVAILABLE: "暂时无法完成注册，请稍后再试。",
  PASSWORD_RESET_UNAVAILABLE: "暂时无法重置密码，请重新获取验证码后再试。",
  AUTH_CREDENTIALS_INVALID: "账号名或密码不正确。",
  REFRESH_IDEMPOTENCY_KEY_INVALID: "会话刷新请求无效，请重新登录。",
  REFRESH_IDEMPOTENCY_CONFLICT: "无法确认会话刷新结果，已安全退出。",
  REFRESH_REQUEST_SUPERSEDED: "会话已在其他页面更新，请重新登录。",
  REFRESH_UNAVAILABLE: "会话已无法刷新，请重新登录。",
  SESSION_REVOKED: "会话已经结束，请重新登录。",
  AUTH_REQUIRED: "认证会话已失效，请重新登录。",
  CHARACTER_ALREADY_EXISTS: "当前账号已有角色，不提供自助重建。",
  CHARACTER_DISPLAY_NAME_INVALID:
    "角色名不符合规则或当前不可用，请更换名称后重试。",
  CHARACTER_PROFILE_INVALID: "角色创建方案已失效，请刷新页面后重新选择。",
  CHARACTER_CREATION_UNAVAILABLE: "暂时无法完成角色创建，请稍后重试。",
  CHARACTER_REQUEST_FAILED: "未能确认角色创建结果，请使用原表单安全重试。",
};

export function errorMessage(code: string): string {
  return ERROR_MESSAGES[code] ?? "请求未能完成，请稍后再试。";
}
