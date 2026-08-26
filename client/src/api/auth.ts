import {
  RefreshCoordinationError,
  clearPendingRefresh,
  coordinatedRefresh,
  hasPendingRefresh,
  type RefreshResult,
} from "./refresh-coordinator";

export interface RegistrationResult {
  user_id: number;
  game_account_id: string;
}

export interface EmailVerification {
  channel: "email";
  destination: string;
  code: string;
}

export interface VerificationRequestResult {
  status: "accepted";
  retry_after: number;
}

export interface AuthApi {
  requestRegistrationVerification(
    destination: string,
    idempotencyKey: string,
  ): Promise<VerificationRequestResult>;
  requestPasswordReset(
    destination: string,
    idempotencyKey: string,
  ): Promise<VerificationRequestResult>;
  confirmPasswordReset(
    destination: string,
    code: string,
    newPassword: string,
  ): Promise<void>;
  register(
    username: string,
    password: string,
    verification: EmailVerification,
  ): Promise<RegistrationResult>;
  login(username: string, password: string): Promise<RefreshResult>;
  refresh(acceptResult: (result: RefreshResult) => void): Promise<RefreshResult>;
  retryPendingRefresh(acceptResult: (result: RefreshResult) => void): Promise<boolean>;
  logout(accessToken: string | null): Promise<void>;
}

interface ErrorBody {
  error?: { code?: string };
}

export class AuthApiError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
  ) {
    super(code);
    this.name = "AuthApiError";
  }
}

async function jsonRequest<T>(
  path: string,
  options: RequestInit & { headers?: Record<string, string> } = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
    body: options.body ?? "{}",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorBody;
    throw new AuthApiError(payload.error?.code ?? "AUTH_REQUEST_FAILED", response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function logoutRequest(accessToken: string | null): Promise<void> {
  try {
    await jsonRequest<void>("/api/v1/auth/logout", {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
  } finally {
    await clearPendingRefresh();
  }
}

async function refreshRequest(
  acceptResult: (result: RefreshResult) => void,
): Promise<RefreshResult> {
  try {
    return await coordinatedRefresh(
      (idempotencyKey) =>
        jsonRequest<RefreshResult>("/api/v1/auth/refresh", {
          headers: { "Idempotency-Key": idempotencyKey },
        }),
      () => logoutRequest(null),
      acceptResult,
    );
  } catch (error) {
    if (error instanceof RefreshCoordinationError) {
      throw new AuthApiError(error.code, 0);
    }
    throw error;
  }
}

export const authApi: AuthApi = {
  requestRegistrationVerification(destination, idempotencyKey) {
    return jsonRequest<VerificationRequestResult>(
      "/api/v1/auth/registration-verification/request",
      {
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ channel: "email", destination }),
      },
    );
  },
  requestPasswordReset(destination, idempotencyKey) {
    return jsonRequest<VerificationRequestResult>("/api/v1/auth/password-reset/request", {
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ channel: "email", destination }),
    });
  },
  confirmPasswordReset(destination, code, newPassword) {
    return jsonRequest<void>("/api/v1/auth/password-reset/confirm", {
      body: JSON.stringify({
        channel: "email",
        destination,
        code,
        new_password: newPassword,
      }),
    });
  },
  register(username, password, verification) {
    return jsonRequest<RegistrationResult>("/api/v1/auth/register", {
      body: JSON.stringify({ username, password, verification }),
    });
  },
  login(username, password) {
    return jsonRequest<RefreshResult>("/api/v1/auth/login", {
      body: JSON.stringify({ username, password }),
    });
  },
  refresh: refreshRequest,
  async retryPendingRefresh(acceptResult) {
    if (!(await hasPendingRefresh())) {
      return false;
    }
    await refreshRequest(acceptResult);
    return true;
  },
  logout: logoutRequest,
};
