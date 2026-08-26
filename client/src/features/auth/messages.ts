const ERROR_MESSAGES: Record<string, string> = {
  REGISTRATION_INVALID: "账号名或密码不符合要求。账号名须为 3–32 位字母、数字或下划线。",
  REGISTRATION_UNAVAILABLE: "暂时无法完成注册，请稍后再试。",
  AUTH_CREDENTIALS_INVALID: "账号名或密码不正确。",
  REFRESH_IDEMPOTENCY_KEY_INVALID: "会话刷新请求无效，请重新登录。",
  REFRESH_IDEMPOTENCY_CONFLICT: "无法确认会话刷新结果，已安全退出。",
  REFRESH_REQUEST_SUPERSEDED: "会话已在其他页面更新，请重新登录。",
  REFRESH_UNAVAILABLE: "会话已无法刷新，请重新登录。",
  SESSION_REVOKED: "会话已经结束，请重新登录。",
};

export function errorMessage(code: string): string {
  return ERROR_MESSAGES[code] ?? "请求未能完成，请稍后再试。";
}
