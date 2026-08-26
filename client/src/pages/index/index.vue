<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { AuthApiError } from "../../api/auth";
import { errorMessage } from "../../features/auth/messages";
import { useAuthStore } from "../../stores/auth";

type Mode = "register" | "login";

const auth = useAuthStore();
const mode = ref<Mode>("register");
const username = ref("");
const password = ref("");
const busy = ref(false);
const errorCode = ref<string | null>(null);
const recoveryCode = ref<string | null>(null);
const announcement = ref("尚未登录");

const title = computed(() => (mode.value === "register" ? "创建江湖账号" : "登录江湖"));
const submitLabel = computed(() => (mode.value === "register" ? "注册账号" : "独立登录"));
const visibleError = computed(() => (errorCode.value ? errorMessage(errorCode.value) : null));

function chooseMode(nextMode: Mode) {
  mode.value = nextMode;
  errorCode.value = null;
}

function captureError(error: unknown) {
  errorCode.value = error instanceof AuthApiError ? error.code : "AUTH_REQUEST_FAILED";
  announcement.value = errorMessage(errorCode.value);
}

async function submit() {
  busy.value = true;
  errorCode.value = null;
  try {
    if (mode.value === "register") {
      const result = await auth.register(username.value, password.value);
      recoveryCode.value = result.recovery_code;
      mode.value = "login";
      announcement.value = "注册成功。请妥善保存恢复码，然后使用独立登录。";
    } else {
      await auth.login(username.value, password.value);
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
    announcement.value = "会话已安全刷新。";
  } catch (error) {
    auth.clearAuthentication();
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
    announcement.value = "已安全退出。";
  } catch (error) {
    captureError(error);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  busy.value = true;
  try {
    if (await auth.retryPendingRefresh()) {
      announcement.value = "未确认的会话刷新已安全重试。";
    }
  } catch (error) {
    auth.clearAuthentication();
    captureError(error);
  } finally {
    busy.value = false;
  }
});
</script>

<template>
  <main class="auth-shell">
    <section class="brand-panel" aria-labelledby="brand-title">
      <p class="eyebrow">NEW_MUD · 武侠文字世界</p>
      <h1 id="brand-title">从一盏灯下，走入江湖。</h1>
      <p class="brand-copy">
        注册不会自动登录。恢复码只展示一次；登录后，访问凭据只停留在当前页面内存。
      </p>
      <dl class="security-notes">
        <div><dt>01</dt><dd>先注册，再独立登录</dd></div>
        <div><dt>02</dt><dd>恢复码离线妥善保存</dd></div>
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

        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          name="password"
          type="password"
          :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
          placeholder="使用足够长且独立的密码"
          data-testid="password"
          required
        />

        <button
          class="primary-action"
          type="button"
          :disabled="busy"
          data-testid="submit"
          @click="submit"
        >
          {{ busy ? "处理中…" : submitLabel }}
        </button>
      </form>

      <div v-else class="session-panel" data-testid="session-panel">
        <p class="session-state">认证会话已建立</p>
        <p>访问凭据仅保存在当前 JavaScript 运行时内存中。</p>
        <div class="session-actions">
          <button type="button" :disabled="busy" data-testid="refresh" @click="refreshSession">
            刷新会话
          </button>
          <button type="button" :disabled="busy" data-testid="logout" @click="logout">
            安全退出
          </button>
        </div>
      </div>

      <aside v-if="recoveryCode" class="recovery-card" data-testid="recovery-code">
        <p class="recovery-label">一次性恢复码</p>
        <code>{{ recoveryCode }}</code>
        <p>现在离线保存。离开本页后，服务端不会再次返回明文。</p>
      </aside>

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
