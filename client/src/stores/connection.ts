import { defineStore } from "pinia";

/** Volatile H5 connection state. Secrets and protocol terminal payloads are
 * deliberately absent so Pinia's state cannot be persisted accidentally. */
export type ConnectionState = "disconnected" | "connecting" | "connected";
export type ConnectionAuthenticationState = "unauthenticated" | "authenticating" | "authenticated";

export const useConnectionStore = defineStore("connection", {
  state: () => ({
    connectionState: "disconnected" as ConnectionState,
    authenticationState: "unauthenticated" as ConnectionAuthenticationState,
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
      this.lastErrorCode = null;
    },
    connected() {
      this.connectionState = "connected";
    },
    authenticating() {
      this.authenticationState = "authenticating";
      this.lastErrorCode = null;
    },
    authenticated() {
      this.authenticationState = "authenticated";
      this.lastErrorCode = null;
    },
    failed(code: string) {
      this.lastErrorCode = code;
      this.authenticationState = "unauthenticated";
    },
    disconnected() {
      this.connectionState = "disconnected";
      this.authenticationState = "unauthenticated";
      this.lastErrorCode = null;
    },
  },
});
