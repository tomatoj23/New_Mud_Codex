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
          const alreadyInRoster = this.roster.some(
            (character) => character.character_id === result.character_id,
          );
          if (!alreadyInRoster) {
            this.roster.push({
              character_id: result.character_id,
              display_name: result.display_name,
              gender: result.gender,
              pronouns: result.pronouns,
              lifecycle: "active",
            });
          }
          if (this.creationCapacity !== null) {
            const used = Math.max(
              this.roster.length,
              this.creationCapacity.used + (alreadyInRoster ? 0 : 1),
            );
            this.creationCapacity = {
              ...this.creationCapacity,
              used,
              remaining: Math.max(0, this.creationCapacity.limit - used),
            };
          }
          this.clearPendingCreation();
          return result;
        } catch (error) {
          if (error instanceof CharacterApiError && error.status !== 0) {
            if (error.code === "CHARACTER_ALREADY_EXISTS") {
              if (this.creationCapacity !== null) {
                this.creationCapacity = {
                  ...this.creationCapacity,
                  used: this.creationCapacity.limit,
                  remaining: 0,
                };
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
