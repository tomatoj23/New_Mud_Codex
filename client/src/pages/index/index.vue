<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { AuthApiError } from "../../api/auth";
import { CharacterApiError } from "../../api/characters";
import { errorMessage } from "../../features/auth/messages";
import { useAuthStore } from "../../stores/auth";
import { useCharacterStore } from "../../stores/characters";

type Mode = "register" | "login" | "password-reset";

const auth = useAuthStore();
const characters = useCharacterStore();
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
const selectedProfileKey = ref("");
const characterDisplayName = ref("");
const characterGender = ref("unspecified");
const characterPronouns = ref("unspecified");
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
const selectedProfile = computed(
  () =>
    characters.profiles.find((profile) => profile.key === selectedProfileKey.value) ??
    characters.profiles[0] ??
    null,
);
const createdProfileDisplayName = computed(
  () =>
    characters.profiles.find(
      (profile) =>
        profile.key === characters.character?.creation_profile.key &&
        profile.version === characters.character?.creation_profile.version,
    )?.display_name ?? characters.character?.creation_profile.key,
);

const genderLabels: Record<string, string> = {
  unspecified: "不指定",
  female: "女",
  male: "男",
  nonbinary: "非二元",
};
const pronounLabels: Record<string, string> = {
  unspecified: "不指定",
  she: "她",
  he: "他",
  they: "其",
};

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

async function loadCharacterProfiles() {
  if (auth.accessToken === null) return;
  const profiles = await characters.loadProfiles(auth.accessToken);
  const profile = profiles[0];
  if (profile === undefined) return;
  selectedProfileKey.value = profile.key;
  characterGender.value = profile.gender_options.includes("unspecified")
    ? "unspecified"
    : (profile.gender_options[0] ?? "");
  characterPronouns.value = profile.pronoun_options.includes("unspecified")
    ? "unspecified"
    : (profile.pronoun_options[0] ?? "");
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
      await loadCharacterProfiles();
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
    characters.clearCharacterState();
    announcement.value = "已安全退出。";
  } catch (error) {
    captureError(error);
  } finally {
    busy.value = false;
  }
}

async function createCharacter() {
  if (auth.accessToken === null || selectedProfile.value === null) return;
  busy.value = true;
  errorCode.value = null;
  try {
    const result = await characters.createCharacter(auth.accessToken, {
      creation_profile_key: selectedProfile.value.key,
      creation_profile_version: selectedProfile.value.version,
      display_name: characterDisplayName.value,
      gender: characterGender.value,
      pronouns: characterPronouns.value,
    });
    characterDisplayName.value = "";
    announcement.value = `角色“${result.display_name}”已创建。`;
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
      await loadCharacterProfiles();
      announcement.value = "未确认的会话刷新已安全重试。";
    }
  } catch (error) {
    auth.clearAuthentication();
    characters.clearCharacterState();
    captureError(error);
  } finally {
    busy.value = false;
  }
});

onBeforeUnmount(stopCountdown);
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
          <div class="session-actions">
            <button type="button" :disabled="busy" data-testid="refresh" @click="refreshSession">
              刷新会话
            </button>
            <button type="button" :disabled="busy" data-testid="logout" @click="logout">
              安全退出
            </button>
          </div>
        </div>

        <section class="character-panel" aria-labelledby="character-title">
          <p class="section-kicker">江湖身份</p>
          <h3 id="character-title">创建角色</h3>

          <div v-if="characters.character" class="character-result" data-testid="character-result">
            <p class="character-name">{{ characters.character.display_name }}</p>
            <p>创建方案：{{ createdProfileDisplayName }}</p>
            <p>起始地点：襄阳东门</p>
            <p>角色已经固定创建；当前不提供自助改名、删除或重建。</p>
          </div>

          <div
            v-else-if="characters.creationBlocked"
            class="character-result"
            data-testid="character-existing"
          >
            <p class="character-name">当前账号已有角色</p>
            <p>为保护角色身份与历史关系，当前不提供自助重建。</p>
          </div>

          <form
            v-else
            data-testid="character-create-form"
            @submit.prevent="createCharacter"
          >
            <div v-if="selectedProfile" class="profile-card" data-testid="character-profile">
              <strong>{{ selectedProfile.display_name }}</strong>
              <span>
                {{ selectedProfile.key }} · {{ selectedProfile.version }}
              </span>
            </div>
            <p v-else class="verification-hint">当前没有可用的角色创建方案。</p>

            <label for="character-display-name">角色显示名</label>
            <input
              id="character-display-name"
              v-model="characterDisplayName"
              maxlength="12"
              autocomplete="off"
              placeholder="2–12 个中文、Latin、数字或中点"
              data-testid="character-display-name"
              required
            />

            <label for="character-gender">展示性别</label>
            <select
              id="character-gender"
              v-model="characterGender"
              data-testid="character-gender"
            >
              <option
                v-for="option in selectedProfile?.gender_options ?? []"
                :key="option"
                :value="option"
              >
                {{ genderLabels[option] ?? option }}
              </option>
            </select>

            <label for="character-pronouns">展示代词</label>
            <select
              id="character-pronouns"
              v-model="characterPronouns"
              data-testid="character-pronouns"
            >
              <option
                v-for="option in selectedProfile?.pronoun_options ?? []"
                :key="option"
                :value="option"
              >
                {{ pronounLabels[option] ?? option }}
              </option>
            </select>

            <p class="verification-hint">
              性别和代词仅用于展示，不改变属性、成长、资格、门派或武学能力。
            </p>
            <button
              class="primary-action"
              type="button"
              :disabled="busy || selectedProfile === null || characterDisplayName.length === 0"
              data-testid="create-character"
              @click="createCharacter"
            >
              {{ busy ? "创建中…" : "创建角色" }}
            </button>
          </form>
        </section>
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
