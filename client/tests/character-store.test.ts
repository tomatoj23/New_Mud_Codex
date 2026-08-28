import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CharacterApiError,
  type CharacterApi,
  type CharacterCreationInput,
  type CharacterCreationResult,
} from "../src/api/characters";
import { createCharacterStore } from "../src/stores/characters";


const profile = {
  key: "default-v1",
  version: "1.0.0",
  definition_hash: "a".repeat(64),
  display_name: "江湖新秀",
  gender_options: ["unspecified", "female", "male", "nonbinary"],
  pronoun_options: ["unspecified", "she", "he", "they"],
};

const creationInput: CharacterCreationInput = {
  creation_profile_key: "default-v1",
  creation_profile_version: "1.0.0",
  display_name: "初行客",
  gender: "unspecified",
  pronouns: "unspecified",
};

const creationResult: CharacterCreationResult = {
  character_id: "00000000-0000-4000-8000-000000000017",
  display_name: "初行客",
  gender: "unspecified",
  pronouns: "unspecified",
  creation_profile: {
    key: "default-v1",
    version: "1.0.0",
    definition_hash: "a".repeat(64),
  },
  initial_state_summary: {
    start_room: {
      blueprint_key: "room.xiangyang.east_gate",
      revision_id: "00000000-0000-4000-8000-000000000018",
    },
    stats: {},
    resources: {},
    skill_grants: [],
    item_grants: [],
  },
};


describe("characterStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("loads selectable profiles and keeps only the server creation result", async () => {
    const api: CharacterApi = {
      listProfiles: vi.fn().mockResolvedValue({ profiles: [profile] }),
      createCharacter: vi.fn().mockResolvedValue(creationResult),
    };
    const store = createCharacterStore(api, () => "character-request-1")();

    await store.loadProfiles("access-token");
    await store.createCharacter("access-token", creationInput);

    expect(api.listProfiles).toHaveBeenCalledWith("access-token");
    expect(api.createCharacter).toHaveBeenCalledWith(
      "access-token",
      creationInput,
      "character-request-1",
    );
    expect(store.profiles).toEqual([profile]);
    expect(store.character).toEqual(creationResult);
    expect(JSON.stringify(store.$state)).not.toContain("access-token");
  });

  it("reuses one idempotency key when an unknown network result is retried", async () => {
    const createRequest = vi
      .fn()
      .mockRejectedValueOnce(new CharacterApiError("CHARACTER_REQUEST_FAILED", 0))
      .mockResolvedValueOnce(creationResult);
    const api: CharacterApi = {
      listProfiles: vi.fn(),
      createCharacter: createRequest,
    };
    const keyFactory = vi
      .fn()
      .mockReturnValueOnce("character-request-retry")
      .mockReturnValueOnce("must-not-be-used");
    const store = createCharacterStore(api, keyFactory)();

    await expect(store.createCharacter("access-token", creationInput)).rejects.toMatchObject({
      code: "CHARACTER_REQUEST_FAILED",
    });
    await expect(store.createCharacter("access-token", creationInput)).resolves.toEqual(
      creationResult,
    );

    expect(createRequest).toHaveBeenCalledTimes(2);
    expect(createRequest.mock.calls[0][2]).toBe("character-request-retry");
    expect(createRequest.mock.calls[1][2]).toBe("character-request-retry");
    expect(keyFactory).toHaveBeenCalledTimes(1);
  });

  it("blocks the creation form when the account has no selectable profiles", async () => {
    const api: CharacterApi = {
      listProfiles: vi.fn().mockResolvedValue({ profiles: [] }),
      createCharacter: vi.fn(),
    };
    const store = createCharacterStore(api)();

    await expect(store.loadProfiles("access-token")).resolves.toEqual([]);

    expect(store.creationBlocked).toBe(true);
    expect(store.profiles).toEqual([]);
  });
});
