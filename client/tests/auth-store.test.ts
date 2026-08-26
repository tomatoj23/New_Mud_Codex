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
      register: vi.fn().mockResolvedValue({
        user_id: 7,
        game_account_id: "account-7",
        recovery_code: "recovery-once",
      }),
      login: vi.fn(),
      refresh: vi.fn(),
      retryPendingRefresh: vi.fn(),
      logout: vi.fn(),
    };
    const store = createAuthStore(api)();

    const result = await store.register("New_Player", "example-passphrase-42");

    expect(result.recovery_code).toBe("recovery-once");
    expect(store.accessToken).toBeNull();
    expect(store.authSessionId).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });

  it("keeps the access token in memory and clears it after logout", async () => {
    const api: AuthApi = {
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

  it("accepts a persisted pending refresh result back into memory", async () => {
    const recovered = {
      access_token: "recovered-access-secret",
      token_type: "Bearer" as const,
      expires_in: 900,
      auth_session_id: "session-recovered",
      game_account_id: "account-recovered",
    };
    const api: AuthApi = {
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
