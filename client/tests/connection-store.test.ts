import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useConnectionStore } from "../src/stores/connection";

describe("connection store", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("tracks volatile connection and authentication state", () => {
    const store = useConnectionStore();
    store.connecting();
    expect(store.connectionState).toBe("connecting");
    store.connected();
    store.authenticating();
    store.authenticated({ authSessionId: "session-1", gameAccountId: "account-1" });
    expect(store.isConnected).toBe(true);
    expect(store.isAuthenticated).toBe(true);
    expect(JSON.stringify(store.$state)).not.toContain("access_token");
  });

  it("clears authentication state after a protocol failure", () => {
    const store = useConnectionStore();
    store.connected();
    store.authenticated({ authSessionId: "session-1", gameAccountId: "account-1" });
    store.failed("TOKEN_EXPIRED");
    expect(store.isAuthenticated).toBe(false);
    expect(store.lastErrorCode).toBe("TOKEN_EXPIRED");
  });
});
