import { defineStore } from "pinia";

import type { ConnectionAuthenticationSummary } from "../protocol/game-connection";

/** Volatile H5 connection state. Secrets and protocol terminal payloads are
 * deliberately absent so Pinia's state cannot be persisted accidentally. */
export type ConnectionState = "disconnected" | "connecting" | "connected";
export type ConnectionAuthenticationState = "unauthenticated" | "authenticating" | "authenticated";

export const useConnectionStore = defineStore("connection", {
  state: () => ({
    connectionState: "disconnected" as ConnectionState,
    authenticationState: "unauthenticated" as ConnectionAuthenticationState,
    authSessionId: null as string | null,
    gameAccountId: null as string | null,
    lastErrorCode: null as string | null,
  }),
  getters: {
    isConnected: (state) => state.connectionState === "connected",
    isAuthenticated: (state) => state.authenticationState === "authenticated",
  },
  actions: {
    connecting() {
      this.connectionState = "connecting";
      this.authenticationState = "unauthenticated";
      this.authSessionId = null;
      this.gameAccountId = null;
      this.lastErrorCode = null;
    },
    connected() {
      this.connectionState = "connected";
    },
    authenticating() {
      this.authenticationState = "authenticating";
      this.lastErrorCode = null;
    },
    authenticated(summary: ConnectionAuthenticationSummary) {
      this.authenticationState = "authenticated";
      this.authSessionId = summary.authSessionId;
      this.gameAccountId = summary.gameAccountId;
      this.lastErrorCode = null;
    },
    failed(code: string) {
      this.lastErrorCode = code;
      this.authenticationState = "unauthenticated";
      this.authSessionId = null;
      this.gameAccountId = null;
    },
    disconnected() {
      this.connectionState = "disconnected";
      this.authenticationState = "unauthenticated";
      this.authSessionId = null;
      this.gameAccountId = null;
      this.lastErrorCode = null;
    },
  },
});
