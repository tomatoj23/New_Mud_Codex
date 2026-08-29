<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { AuthApiError } from "../../api/auth";
import { CharacterApiError, type CharacterCreationResult } from "../../api/characters";
import { errorMessage } from "../../features/auth/messages";
import CharacterCreationPanel from "../../features/characters/CharacterCreationPanel.vue";
import {
  browserGameConnectionEnvironment,
  GameConnection,
} from "../../protocol/game-connection";
import { useAuthStore } from "../../stores/auth";
import { useCharacterStore } from "../../stores/characters";
import { useConnectionStore } from "../../stores/connection";

type Mode = "register" | "login" | "password-reset";

const auth = useAuthStore();
const characters = useCharacterStore();
const connectionState = useConnectionStore();
const gameConnection = new GameConnection(
  connectionState,
  browserGameConnectionEnvironment(),
);
const mode = ref<Mode>("register");
const email = ref("");
const verificationCode = ref("");
const sentDestination = ref<string | null>(null);
const resendRemaining = ref(0);
const username = ref("");
const password = ref("");
const busy = ref(false);
const verificationBusy = ref(false);
const errorCode = ref<string | null>(null);
const announcement = ref("尚未登录");
let resendTimer: ReturnType<typeof setInterval> | null = null;

const title = computed(() => {
  if (mode.value === "register") return "创建江湖账号";
  if (mode.value === "password-reset") return "找回账号密码";
  return "登录江湖";
});
const submitLabel = computed(() => {
  if (mode.value === "register") return "注册账号";
  if (mode.value === "password-reset") return "重置密码";
  return "登录";
});
const visibleError = computed(() => (errorCode.value ? errorMessage(errorCode.value) : null));
const currentEmailWasSent = computed(
  () => sentDestination.value !== null && sentDestination.value === email.value.trim(),
);
const verificationReady = computed(
  () => currentEmailWasSent.value && /^\d{6}$/.test(verificationCode.value),
);
const verificationButtonLabel = computed(() => {
  if (verificationBusy.value) return "发送中…";
  if (resendRemaining.value > 0) return `${resendRemaining.value} 秒后可重发`;
  return sentDestination.value === null ? "发送验证码" : "重新发送验证码";
});
const connectionLabel = computed(
  () =>
    ({
      disconnected: "已断开",
      connecting: "连接中",
      connected: "已连接",
    })[connectionState.connectionState],
);
const connectionAuthenticationLabel = computed(
  () =>
    ({
      unauthenticated: "未认证",
      authenticating: "认证中",
      authenticated: "已认证",
    })[connectionState.authenticationState],
);
function stopCountdown() {
  if (resendTimer !== null) {
    clearInterval(resendTimer);
    resendTimer = null;
  }
}

function startCountdown(seconds: number) {
  stopCountdown();
  resendRemaining.value = Math.max(0, Math.floor(seconds));
  resendTimer = setInterval(() => {
    resendRemaining.value = Math.max(0, resendRemaining.value - 1);
    if (resendRemaining.value === 0) stopCountdown();
  }, 1000);
}

function chooseMode(nextMode: Mode) {
  if (mode.value === "password-reset" || nextMode === "password-reset") {
    email.value = "";
    verificationCode.value = "";
    sentDestination.value = null;
    resendRemaining.value = 0;
    password.value = "";
    stopCountdown();
  }
  mode.value = nextMode;
  errorCode.value = null;
}

function choosePasswordReset() {
  chooseMode("password-reset");
  announcement.value = "请输入已验证邮箱以获取密码重置验证码。";
}

function captureError(error: unknown) {
  errorCode.value =
    error instanceof AuthApiError || error instanceof CharacterApiError
      ? error.code
      : "AUTH_REQUEST_FAILED";
  announcement.value = errorMessage(errorCode.value);
}

function handleCharacterCreated(result: CharacterCreationResult) {
  announcement.value = `角色“${result.display_name}”已创建。`;
}

function handleCharacterBusy(value: boolean) {
  busy.value = value;
}

async function loadCharacterWorkspace() {
  if (auth.accessToken === null) return;
  await Promise.all([
    characters.loadProfiles(auth.accessToken),
    characters.loadRoster(auth.accessToken),
  ]);
}

async function requestVerificationCode() {
  verificationBusy.value = true;
  errorCode.value = null;
  try {
    const destination = email.value.trim();
    const result =
      mode.value === "password-reset"
        ? await auth.requestPasswordReset(
            destination,
            `password-reset-${crypto.randomUUID()}`,
          )
        : await auth.requestRegistrationVerification(
            destination,
            `registration-${crypto.randomUUID()}`,
          );
    sentDestination.value = destination;
    verificationCode.value = "";
    startCountdown(result.retry_after);
    announcement.value =
      mode.value === "password-reset"
        ? "密码重置请求已受理，请查看邮箱。未收到时可在倒计时结束后手动重发。"
        : "验证码请求已受理，请查看邮箱。未收到时可在倒计时结束后手动重发。";
  } catch (error) {
    captureError(error);
  } finally {
    verificationBusy.value = false;
  }
}

async function submit() {
  busy.value = true;
  errorCode.value = null;
  try {
    if (mode.value === "register") {
      if (!verificationReady.value || sentDestination.value === null) {
        errorCode.value = "VERIFICATION_CODE_INVALID";
        announcement.value = errorMessage(errorCode.value);
        return;
      }
      await auth.register(username.value, password.value, {
        channel: "email",
        destination: sentDestination.value,
        code: verificationCode.value,
      });
      mode.value = "login";
      email.value = "";
      verificationCode.value = "";
      sentDestination.value = null;
      resendRemaining.value = 0;
      stopCountdown();
      announcement.value = "注册成功，请登录。";
    } else if (mode.value === "password-reset") {
      if (!verificationReady.value || sentDestination.value === null) {
        errorCode.value = "VERIFICATION_CODE_INVALID";
        announcement.value = errorMessage(errorCode.value);
        return;
      }
      await auth.confirmPasswordReset(
        sentDestination.value,
        verificationCode.value,
        password.value,
      );
      mode.value = "login";
      email.value = "";
      verificationCode.value = "";
      sentDestination.value = null;
      resendRemaining.value = 0;
      stopCountdown();
      announcement.value = "密码已重置，请使用新密码登录。";
    } else {
      characters.clearCharacterState();
      await auth.login(username.value, password.value);
      if (auth.accessToken !== null) gameConnection.connect(auth.accessToken);
      await loadCharacterWorkspace();
      announcement.value = "登录成功。认证会话已建立。";
    }
  } catch (error) {
    captureError(error);
  } finally {
    password.value = "";
    busy.value = false;
  }
}

async function refreshSession() {
  busy.value = true;
  errorCode.value = null;
  try {
    await auth.refresh();
    if (auth.accessToken !== null) gameConnection.connect(auth.accessToken);
    announcement.value = "会话已安全刷新。";
  } catch (error) {
    gameConnection.disconnect();
    auth.clearAuthentication();
    characters.clearCharacterState();
    captureError(error);
  } finally {
    busy.value = false;
  }
}

async function logout() {
  busy.value = true;
  errorCode.value = null;
  try {
    await auth.logout();
    gameConnection.disconnect();
    characters.clearCharacterState();
    announcement.value = "已安全退出。";
  } catch (error) {
    gameConnection.disconnect();
    captureError(error);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  busy.value = true;
  try {
    if (await auth.retryPendingRefresh()) {
      if (auth.accessToken !== null) gameConnection.connect(auth.accessToken);
      await loadCharacterWorkspace();
      announcement.value = "未确认的会话刷新已安全重试。";
    }
  } catch (error) {
    gameConnection.disconnect();
    auth.clearAuthentication();
    characters.clearCharacterState();
    captureError(error);
  } finally {
    busy.value = false;
  }
});

onBeforeUnmount(() => {
  stopCountdown();
  gameConnection.disconnect();
});
</script>

<template>
  <main class="auth-shell">
    <section class="brand-panel" aria-labelledby="brand-title">
      <p class="eyebrow">NEW_MUD · 武侠文字世界</p>
      <h1 id="brand-title">从一盏灯下，走入江湖。</h1>
      <p class="brand-copy">
        先验证可用邮箱，再创建账号。注册完成后请使用账号名和密码登录。
      </p>
      <dl class="security-notes">
        <div><dt>01</dt><dd>邮箱验证码十分钟内有效</dd></div>
        <div><dt>02</dt><dd>注册成功后不会自动登录</dd></div>
        <div><dt>03</dt><dd>退出后清理本地会话</dd></div>
      </dl>
    </section>

    <section class="auth-card" aria-labelledby="auth-title">
      <div class="mode-tabs" aria-label="认证方式">
        <button
          type="button"
          :class="{ active: mode === 'register' }"
          data-testid="register-tab"
          @click="chooseMode('register')"
        >
          注册
        </button>
        <button
          type="button"
          :class="{ active: mode === 'login' }"
          data-testid="login-tab"
          @click="chooseMode('login')"
        >
          登录
        </button>
      </div>

      <div class="card-heading">
        <p class="section-kicker">玩家身份</p>
        <h2 id="auth-title">{{ title }}</h2>
      </div>

      <form v-if="!auth.isAuthenticated" @submit.prevent="submit">
        <template v-if="mode === 'register' || mode === 'password-reset'">
          <label :for="mode === 'password-reset' ? 'reset-email' : 'email'">邮箱</label>
          <div class="verification-request-row">
            <input
              :id="mode === 'password-reset' ? 'reset-email' : 'email'"
              v-model="email"
              name="email"
              type="email"
              autocomplete="email"
              :placeholder="
                mode === 'password-reset' ? '已验证的账号邮箱' : '用于接收注册验证码'
              "
              :data-testid="mode === 'password-reset' ? 'reset-email' : 'email'"
              required
            />
            <button
              class="verification-action"
              type="button"
              :disabled="verificationBusy || resendRemaining > 0 || email.trim().length === 0"
              :data-testid="
                mode === 'password-reset' ? 'request-password-reset' : 'request-verification'
              "
              @click="requestVerificationCode"
            >
              {{ verificationButtonLabel }}
            </button>
          </div>
          <p
            v-if="currentEmailWasSent"
            class="verification-hint"
            :data-testid="
              mode === 'password-reset' ? 'password-reset-hint' : 'verification-hint'
            "
          >
            请求已受理。请输入邮件中的六位验证码。
          </p>

          <label :for="mode === 'password-reset' ? 'password-reset-code' : 'verification-code'">
            邮箱验证码
          </label>
          <input
            :id="mode === 'password-reset' ? 'password-reset-code' : 'verification-code'"
            v-model.trim="verificationCode"
            name="verification-code"
            autocomplete="one-time-code"
            inputmode="numeric"
            maxlength="6"
            pattern="[0-9]{6}"
            placeholder="六位数字"
            :data-testid="
              mode === 'password-reset' ? 'password-reset-code' : 'verification-code'
            "
            required
          />
        </template>

        <template v-if="mode !== 'password-reset'">
          <label for="username">账号名</label>
          <input
            id="username"
            v-model.trim="username"
            name="username"
            autocomplete="username"
            autocapitalize="none"
            spellcheck="false"
            placeholder="3–32 位字母、数字或下划线"
            data-testid="username"
            required
          />
        </template>

        <label :for="mode === 'password-reset' ? 'new-password' : 'password'">
          {{ mode === "password-reset" ? "新密码" : "密码" }}
        </label>
        <input
          :id="mode === 'password-reset' ? 'new-password' : 'password'"
          v-model="password"
          name="password"
          type="password"
          :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          placeholder="使用足够长且独立的密码"
          :data-testid="mode === 'password-reset' ? 'new-password' : 'password'"
          required
        />

        <button
          v-if="mode === 'login'"
          class="text-action"
          type="button"
          data-testid="forgot-password"
          @click="choosePasswordReset"
        >
          忘记密码
        </button>

        <button
          v-if="mode === 'password-reset'"
          class="text-action"
          type="button"
          data-testid="back-to-login"
          @click="chooseMode('login')"
        >
          返回账号登录
        </button>

        <button
          class="primary-action"
          type="button"
          :disabled="busy || (mode !== 'login' && !verificationReady)"
          :data-testid="mode === 'password-reset' ? 'submit-password-reset' : 'submit'"
          @click="submit"
        >
          {{ busy ? "处理中…" : submitLabel }}
        </button>
      </form>

      <div v-else class="authenticated-panel">
        <div class="session-panel" data-testid="session-panel">
          <p class="session-state">认证会话已建立</p>
          <p>访问凭据仅保存在当前 JavaScript 运行时内存中。</p>
          <dl class="connection-status" data-testid="connection-status">
            <div>
              <dt>游戏连接</dt>
              <dd data-testid="connection-state">{{ connectionLabel }}</dd>
            </div>
            <div>
              <dt>连接认证</dt>
              <dd data-testid="connection-authentication-state">
                {{ connectionAuthenticationLabel }}
              </dd>
            </div>
          </dl>
          <p
            v-if="connectionState.lastErrorCode"
            class="connection-error"
            data-testid="connection-error"
          >
            游戏连接错误：{{ connectionState.lastErrorCode }}
          </p>
          <div class="session-actions">
            <button type="button" :disabled="busy" data-testid="refresh" @click="refreshSession">
              刷新会话
            </button>
            <button type="button" :disabled="busy" data-testid="logout" @click="logout">
              安全退出
            </button>
          </div>
        </div>

        <CharacterCreationPanel
          :access-token="auth.accessToken"
          :busy="busy"
          @busy-change="handleCharacterBusy"
          @created="handleCharacterCreated"
          @error="captureError"
        />
      </div>

      <p v-if="visibleError" class="error-message" role="alert" data-testid="error">
        {{ visibleError }}
        <span class="machine-code">{{ errorCode }}</span>
      </p>
      <p class="announcement" aria-live="polite" data-testid="announcement">
        {{ announcement }}
      </p>
    </section>
  </main>
</template>
