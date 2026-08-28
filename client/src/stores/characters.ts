import { defineStore } from "pinia";

import {
  CharacterApiError,
  characterApi,
  type CharacterApi,
  type CharacterCreationInput,
  type CharacterCreationProfile,
  type CharacterCreationResult,
} from "../api/characters";


function canonicalInput(input: CharacterCreationInput): string {
  return JSON.stringify({
    creation_profile_key: input.creation_profile_key,
    creation_profile_version: input.creation_profile_version,
    display_name: input.display_name,
    gender: input.gender,
    pronouns: input.pronouns,
  });
}

export function createCharacterStore(
  api: CharacterApi = characterApi,
  keyFactory: () => string = () => `character-${crypto.randomUUID()}`,
) {
  return defineStore("characters", {
    state: () => ({
      profiles: [] as CharacterCreationProfile[],
      character: null as CharacterCreationResult | null,
      creationBlocked: false,
      pendingCreationHash: null as string | null,
      pendingCreationKey: null as string | null,
    }),
    actions: {
      async loadProfiles(accessToken: string) {
        const result = await api.listProfiles(accessToken);
        this.profiles = result.profiles;
        this.creationBlocked = result.profiles.length === 0;
        return result.profiles;
      },
      async createCharacter(accessToken: string, input: CharacterCreationInput) {
        const inputHash = canonicalInput(input);
        if (this.pendingCreationHash !== inputHash || this.pendingCreationKey === null) {
          this.pendingCreationHash = inputHash;
          this.pendingCreationKey = keyFactory();
        }
        try {
          const result = await api.createCharacter(accessToken, input, this.pendingCreationKey);
          this.character = result;
          this.creationBlocked = true;
          this.clearPendingCreation();
          return result;
        } catch (error) {
          if (error instanceof CharacterApiError && error.status !== 0) {
            if (error.code === "CHARACTER_ALREADY_EXISTS") {
              this.creationBlocked = true;
            }
            this.clearPendingCreation();
          }
          throw error;
        }
      },
      clearPendingCreation() {
        this.pendingCreationHash = null;
        this.pendingCreationKey = null;
      },
      clearCharacterState() {
        this.profiles = [];
        this.character = null;
        this.creationBlocked = false;
        this.clearPendingCreation();
      },
    },
  });
}

export const useCharacterStore = createCharacterStore();
