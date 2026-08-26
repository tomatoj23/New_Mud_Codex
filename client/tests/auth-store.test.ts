import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthApi } from "../src/api/auth";
import { createAuthStore } from "../src/stores/auth";


describe("authStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("keeps registration separate from authenticated state", async () => {
    const api: AuthApi = {
      requestRegistrationVerification: vi.fn().mockResolvedValue({
        status: "accepted",
        retry_after: 60,
      }),
      requestPasswordReset: vi.fn(),
      confirmPasswordReset: vi.fn(),
      register: vi.fn().mockResolvedValue({
        user_id: 7,
        game_account_id: "account-7",
      }),
      login: vi.fn(),
      refresh: vi.fn(),
      retryPendingRefresh: vi.fn(),
      logout: vi.fn(),
    };
    const store = createAuthStore(api)();
    const verification = {
      channel: "email" as const,
      destination: "new.player@example.com",
      code: "123456",
    };

    await expect(
      store.requestRegistrationVerification("new.player@example.com", "request-1"),
    ).resolves.toEqual({ status: "accepted", retry_after: 60 });
    const result = await store.register(
      "New_Player",
      "example-passphrase-42",
      verification,
    );

    expect(result).toEqual({ user_id: 7, game_account_id: "account-7" });
    expect(api.register).toHaveBeenCalledWith(
      "New_Player",
      "example-passphrase-42",
      verification,
    );
    expect(store.accessToken).toBeNull();
    expect(store.authSessionId).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });

  it("keeps the access token in memory and clears it after logout", async () => {
    const api: AuthApi = {
      requestRegistrationVerification: vi.fn(),
      requestPasswordReset: vi.fn(),
      confirmPasswordReset: vi.fn(),
      register: vi.fn(),
      login: vi.fn().mockResolvedValue({
        access_token: "access-secret",
        token_type: "Bearer",
        expires_in: 900,
        auth_session_id: "session-1",
        game_account_id: "account-1",
      }),
      refresh: vi.fn(),
      retryPendingRefresh: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    };
    const store = createAuthStore(api)();

    await store.login("player", "example-passphrase-42");
    expect(store.accessToken).toBe("access-secret");
    expect(store.isAuthenticated).toBe(true);

    await store.logout();
    expect(api.logout).toHaveBeenCalledWith("access-secret");
    expect(store.accessToken).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });

  it("resets a password without retaining recovery inputs and clears authentication", async () => {
    const api = {
      requestRegistrationVerification: vi.fn(),
      requestPasswordReset: vi.fn().mockResolvedValue({
        status: "accepted",
        retry_after: 60,
      }),
      confirmPasswordReset: vi.fn().mockResolvedValue(undefined),
      register: vi.fn(),
      login: vi.fn(),
      refresh: vi.fn(),
      retryPendingRefresh: vi.fn(),
      logout: vi.fn(),
    } as unknown as AuthApi;
    const store = createAuthStore(api)();
    store.acceptAuthentication({
      access_token: "old-access-secret",
      auth_session_id: "old-session",
      game_account_id: "old-account",
    });

    await expect(
      store.requestPasswordReset("owner@example.com", "password-reset-1"),
    ).resolves.toEqual({ status: "accepted", retry_after: 60 });
    await store.confirmPasswordReset(
      "owner@example.com",
      "123456",
      "safe-reset-passphrase-84",
    );

    expect(api.requestPasswordReset).toHaveBeenCalledWith(
      "owner@example.com",
      "password-reset-1",
    );
    expect(api.confirmPasswordReset).toHaveBeenCalledWith(
      "owner@example.com",
      "123456",
      "safe-reset-passphrase-84",
    );
    expect(store.accessToken).toBeNull();
    expect(store.authSessionId).toBeNull();
    expect(store.gameAccountId).toBeNull();
    expect(JSON.stringify(store.$state)).not.toContain("owner@example.com");
    expect(JSON.stringify(store.$state)).not.toContain("123456");
    expect(JSON.stringify(store.$state)).not.toContain("safe-reset-passphrase-84");
  });

  it("accepts a persisted pending refresh result back into memory", async () => {
    const recovered = {
      access_token: "recovered-access-secret",
      token_type: "Bearer" as const,
      expires_in: 900,
      auth_session_id: "session-recovered",
      game_account_id: "account-recovered",
    };
    const api: AuthApi = {
      requestRegistrationVerification: vi.fn(),
      requestPasswordReset: vi.fn(),
      confirmPasswordReset: vi.fn(),
      register: vi.fn(),
      login: vi.fn(),
      refresh: vi.fn(),
      retryPendingRefresh: vi.fn(async (acceptResult) => {
        acceptResult(recovered);
        return true;
      }),
      logout: vi.fn(),
    };
    const store = createAuthStore(api)();

    await expect(store.retryPendingRefresh()).resolves.toBe(true);

    expect(store.accessToken).toBe("recovered-access-secret");
    expect(store.authSessionId).toBe("session-recovered");
    expect(store.isAuthenticated).toBe(true);
  });
});
