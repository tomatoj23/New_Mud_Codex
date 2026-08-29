<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { useCharacterStore } from "../../stores/characters";
import type { CharacterCreationResult } from "../../api/characters";

const props = defineProps<{
  accessToken: string | null;
  busy: boolean;
}>();

const emit = defineEmits<{
  (event: "busy-change", value: boolean): void;
  (event: "error", error: unknown): void;
  (event: "created", result: CharacterCreationResult): void;
}>();

const characters = useCharacterStore();
const selectedProfileKey = ref("");
const characterDisplayName = ref("");
const characterGender = ref("unspecified");
const characterPronouns = ref("unspecified");

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

function initializeSelection() {
  const profile = selectedProfile.value;
  if (profile === null) return;
  selectedProfileKey.value = profile.key;
  characterGender.value = profile.gender_options.includes("unspecified")
    ? "unspecified"
    : (profile.gender_options[0] ?? "");
  characterPronouns.value = profile.pronoun_options.includes("unspecified")
    ? "unspecified"
    : (profile.pronoun_options[0] ?? "");
}

function limitDisplayNameLength(event: Event) {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  const limited = Array.from(input.value).slice(0, 12).join("");
  if (input.value !== limited) input.value = limited;
  characterDisplayName.value = limited;
}

async function createCharacter() {
  if (props.accessToken === null || selectedProfile.value === null) return;
  emit("busy-change", true);
  try {
    const result = await characters.createCharacter(props.accessToken, {
      creation_profile_key: selectedProfile.value.key,
      creation_profile_version: selectedProfile.value.version,
      display_name: characterDisplayName.value,
      gender: characterGender.value,
      pronouns: characterPronouns.value,
    });
    characterDisplayName.value = "";
    emit("created", result);
  } catch (error) {
    emit("error", error);
  } finally {
    emit("busy-change", false);
  }
}

watch(
  () => characters.profiles,
  (profiles) => {
    if (profiles.length > 0 && selectedProfileKey.value === "") {
      initializeSelection();
    }
  },
  { immediate: true },
);
</script>

<template>
  <section class="character-panel" aria-labelledby="character-title">
    <p class="section-kicker">江湖身份</p>
    <h3 id="character-title">角色</h3>

    <div v-if="characters.character" class="character-result" data-testid="character-result">
      <p class="character-name">{{ characters.character.display_name }}</p>
      <p>创建方案：{{ createdProfileDisplayName }}</p>
      <p>起始地点：襄阳东门</p>
      <p>角色已经固定创建；当前不提供自助改名、删除或重建。</p>
    </div>

    <div
      v-else-if="characters.roster.length > 0"
      class="character-result"
      data-testid="character-existing"
    >
      <p>当前账号已有角色</p>
      <div v-for="character in characters.roster" :key="character.character_id">
        <p class="character-name">{{ character.display_name }}</p>
        <p>状态：{{ character.lifecycle === "retired" ? "已退隐" : "活跃" }}</p>
      </div>
      <p v-if="!characters.canCreate">
        当前账号的自助创建名额已用完；已有角色不会被删除或替换。
      </p>
    </div>

    <form
      v-if="characters.canCreate"
      data-testid="character-create-form"
      @submit.prevent="createCharacter"
    >
      <div v-if="selectedProfile" class="profile-card" data-testid="character-profile">
        <strong>{{ selectedProfile.display_name }}</strong>
        <span>{{ selectedProfile.key }} · {{ selectedProfile.version }}</span>
      </div>
      <p v-else class="verification-hint">当前没有可用的角色创建方案。</p>

      <label for="character-display-name">角色显示名</label>
      <input
        id="character-display-name"
        v-model="characterDisplayName"
        @input="limitDisplayNameLength"
        autocomplete="off"
        placeholder="2–12 个中文、Latin、数字或中点"
        data-testid="character-display-name"
        required
      />

      <label for="character-gender">展示性别</label>
      <select id="character-gender" v-model="characterGender" data-testid="character-gender">
        <option
          v-for="option in selectedProfile?.gender_options ?? []"
          :key="option"
          :value="option"
        >
          {{ genderLabels[option] ?? option }}
        </option>
      </select>

      <label for="character-pronouns">展示代词</label>
      <select id="character-pronouns" v-model="characterPronouns" data-testid="character-pronouns">
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
        :disabled="props.busy || selectedProfile === null || characterDisplayName.length === 0"
        data-testid="create-character"
        @click="createCharacter"
      >
        {{ props.busy ? "创建中…" : "创建角色" }}
      </button>
    </form>
    <p v-else-if="characters.creationCapacity === null" class="verification-hint">
      正在读取角色与创建名额…
    </p>
  </section>
</template>
