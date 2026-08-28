import { defineStore } from "pinia";

import {
  CharacterApiError,
  characterApi,
  type CharacterApi,
  type CharacterCreationCapacity,
  type CharacterCreationInput,
  type CharacterCreationProfile,
  type CharacterCreationResult,
  type CharacterRosterEntry,
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
      roster: [] as CharacterRosterEntry[],
      creationCapacity: null as CharacterCreationCapacity | null,
      character: null as CharacterCreationResult | null,
      pendingCreationHash: null as string | null,
      pendingCreationKey: null as string | null,
    }),
    getters: {
      canCreate: (state) => (state.creationCapacity?.remaining ?? 0) > 0,
    },
    actions: {
      async loadProfiles(accessToken: string) {
        const result = await api.listProfiles(accessToken);
        this.profiles = result.profiles;
        return result.profiles;
      },
      async loadRoster(accessToken: string) {
        const result = await api.listCharacters(accessToken);
        this.roster = result.characters;
        this.creationCapacity = result.creation_capacity;
        return result;
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
          await this.loadRoster(accessToken);
          this.clearPendingCreation();
          return result;
        } catch (error) {
          if (error instanceof CharacterApiError && error.status !== 0) {
            if (error.code === "CHARACTER_ALREADY_EXISTS") {
              try {
                await this.loadRoster(accessToken);
              } catch {
                // Preserve the stable creation error when the follow-up read is unavailable.
              }
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
        this.roster = [];
        this.creationCapacity = null;
        this.character = null;
        this.clearPendingCreation();
      },
    },
  });
}

export const useCharacterStore = createCharacterStore();
