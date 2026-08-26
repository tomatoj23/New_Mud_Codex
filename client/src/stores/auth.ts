import { defineStore } from "pinia";

import { authApi, type AuthApi, type EmailVerification } from "../api/auth";

export function createAuthStore(api: AuthApi = authApi) {
  return defineStore("auth", {
    state: () => ({
      accessToken: null as string | null,
      authSessionId: null as string | null,
      gameAccountId: null as string | null,
    }),
    getters: {
      isAuthenticated: (state) => state.accessToken !== null && state.authSessionId !== null,
    },
    actions: {
      requestRegistrationVerification(destination: string, idempotencyKey: string) {
        return api.requestRegistrationVerification(destination, idempotencyKey);
      },
      register(username: string, password: string, verification: EmailVerification) {
        this.clearAuthentication();
        return api.register(username, password, verification);
      },
      async login(username: string, password: string) {
        const result = await api.login(username, password);
        this.acceptAuthentication(result);
      },
      async refresh() {
        await api.refresh((result) => this.acceptAuthentication(result));
      },
      async retryPendingRefresh() {
        return api.retryPendingRefresh((result) => this.acceptAuthentication(result));
      },
      async logout() {
        const accessToken = this.accessToken;
        try {
          await api.logout(accessToken);
        } finally {
          this.clearAuthentication();
        }
      },
      acceptAuthentication(result: {
        access_token: string;
        auth_session_id: string;
        game_account_id: string;
      }) {
        this.accessToken = result.access_token;
        this.authSessionId = result.auth_session_id;
        this.gameAccountId = result.game_account_id;
      },
      clearAuthentication() {
        this.accessToken = null;
        this.authSessionId = null;
        this.gameAccountId = null;
      },
    },
  });
}

export const useAuthStore = createAuthStore();
