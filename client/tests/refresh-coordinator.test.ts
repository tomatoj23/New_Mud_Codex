import { describe, expect, it, vi } from "vitest";

import {
  RefreshCoordinationError,
  coordinatedRefresh,
  type PendingRefresh,
  type RefreshCoordinatorEnvironment,
  type RefreshMessage,
  type RefreshResult,
} from "../src/api/refresh-coordinator";

const pending: PendingRefresh = {
  slot: "auth-refresh-v1",
  idempotency_key: "refresh_existing_key",
  endpoint: "/api/v1/auth/refresh",
  state: "pending",
  created_at: "2026-08-26T00:00:00.000Z",
};

const result: RefreshResult = {
  access_token: "access-in-memory-only",
  token_type: "Bearer",
  expires_in: 900,
  auth_session_id: "session-1",
  game_account_id: "account-1",
};

function environment(
  overrides: Partial<RefreshCoordinatorEnvironment> = {},
): RefreshCoordinatorEnvironment & { messages: RefreshMessage[] } {
  const messages: RefreshMessage[] = [];
  return {
    messages,
    openChannel: () => ({
      onmessage: null,
      postMessage: (message) => messages.push(message),
      close: vi.fn(),
    }),
    requestLock: (callback) => callback({}),
    getOrCreatePending: vi.fn().mockResolvedValue(pending),
    clearPending: vi.fn().mockResolvedValue(undefined),
    now: () => Date.parse("2026-08-26T00:00:01.000Z"),
    ownerWaitMs: 0,
    ...overrides,
  };
}

describe("coordinatedRefresh", () => {
  it("reuses the persisted pending key and clears it only after success", async () => {
    const env = environment();
    const send = vi.fn().mockResolvedValue(result);

    await expect(coordinatedRefresh(send, vi.fn(), vi.fn(), env)).resolves.toEqual(result);

    expect(send).toHaveBeenCalledWith("refresh_existing_key");
    expect(env.clearPending).toHaveBeenCalledOnce();
    expect(env.messages).toEqual([{ type: "refresh-completed", result }]);
  });

  it.each(["REFRESH_IDEMPOTENCY_CONFLICT", "REFRESH_REQUEST_SUPERSEDED"])(
    "clears ambiguous state and invokes safe logout for %s",
    async (code) => {
      const env = environment();
      const error = Object.assign(new Error(code), { code });
      const safeLogout = vi.fn().mockResolvedValue(undefined);

      await expect(
        coordinatedRefresh(vi.fn().mockRejectedValue(error), safeLogout, vi.fn(), env),
      ).rejects.toBe(error);

      expect(env.clearPending).toHaveBeenCalledOnce();
      expect(safeLogout).toHaveBeenCalledOnce();
      expect(env.messages).toEqual([{ type: "refresh-failed", errorCode: code }]);
    },
  );

  it("retains the pending key after an uncertain network failure", async () => {
    const env = environment();
    const networkError = new TypeError("network unavailable");
    const safeLogout = vi.fn();

    await expect(
      coordinatedRefresh(vi.fn().mockRejectedValue(networkError), safeLogout, vi.fn(), env),
    ).rejects.toBe(networkError);

    expect(env.clearPending).not.toHaveBeenCalled();
    expect(safeLogout).not.toHaveBeenCalled();
  });

  it("preserves the owner's stable machine error for a waiting tab", async () => {
    const env = environment({
      ownerWaitMs: 100,
      openChannel: () => {
        const channel = {
          onmessage: null as ((event: MessageEvent<RefreshMessage>) => void) | null,
          postMessage: vi.fn(),
          close: vi.fn(),
        };
        queueMicrotask(() =>
          channel.onmessage?.({
            data: { type: "refresh-failed", errorCode: "SESSION_REVOKED" },
          } as MessageEvent<RefreshMessage>),
        );
        return channel;
      },
      requestLock: (callback) => callback(null),
    });

    const rejection = coordinatedRefresh(vi.fn(), vi.fn(), vi.fn(), env);

    await expect(rejection).rejects.toEqual(
      expect.objectContaining<Partial<RefreshCoordinationError>>({
        code: "SESSION_REVOKED",
      }),
    );
  });

  it("retries lock ownership after the previous owner disappears", async () => {
    let attempts = 0;
    const env = environment({
      requestLock: (callback) => callback(attempts++ === 0 ? null : {}),
    });
    const send = vi.fn().mockResolvedValue(result);

    await expect(coordinatedRefresh(send, vi.fn(), vi.fn(), env)).resolves.toEqual(result);

    expect(attempts).toBe(2);
    expect(send).toHaveBeenCalledOnce();
    expect(send).toHaveBeenCalledWith("refresh_existing_key");
  });

  it("stores the access token before clearing pending state and notifying followers", async () => {
    const events: string[] = [];
    const env = environment({
      clearPending: vi.fn(async () => {
        events.push("clear-pending");
      }),
      openChannel: () => ({
        onmessage: null,
        postMessage: () => events.push("broadcast"),
        close: vi.fn(),
      }),
    });
    const send = vi.fn(async () => {
      events.push("response");
      return result;
    });
    const accept = vi.fn(() => events.push("store-access"));

    await coordinatedRefresh(send, vi.fn(), accept, env);

    expect(events).toEqual(["response", "store-access", "clear-pending", "broadcast"]);
    expect(accept).toHaveBeenCalledWith(result);
  });

  it("uses the successor with a new durable key when fixed access claims have expired", async () => {
    const replacementPending = {
      ...pending,
      idempotency_key: "refresh_replacement_key",
      created_at: "2026-08-26T00:00:01.000Z",
    };
    const env = environment({
      getOrCreatePending: vi
        .fn()
        .mockResolvedValueOnce(pending)
        .mockResolvedValueOnce(replacementPending),
    });
    const expired = { ...result, access_token: "expired-access", expires_in: 0 };
    const send = vi.fn().mockResolvedValueOnce(expired).mockResolvedValueOnce(result);
    const accept = vi.fn();

    await expect(coordinatedRefresh(send, vi.fn(), accept, env)).resolves.toEqual(result);

    expect(send).toHaveBeenNthCalledWith(1, "refresh_existing_key");
    expect(send).toHaveBeenNthCalledWith(2, "refresh_replacement_key");
    expect(env.clearPending).toHaveBeenCalledTimes(2);
    expect(accept).toHaveBeenCalledOnce();
    expect(accept).toHaveBeenCalledWith(result);
    expect(env.messages).toEqual([{ type: "refresh-completed", result }]);
  });
});
