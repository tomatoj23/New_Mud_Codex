export interface CharacterCreationProfile {
  key: string;
  version: string;
  definition_hash: string;
  display_name: string;
  gender_options: string[];
  pronoun_options: string[];
}

export interface CharacterCreationInput {
  creation_profile_key: string;
  creation_profile_version: string;
  display_name: string;
  gender: string;
  pronouns: string;
}

export interface CharacterCreationResult {
  character_id: string;
  display_name: string;
  gender: string;
  pronouns: string;
  creation_profile: {
    key: string;
    version: string;
    definition_hash: string;
  };
  initial_state_summary: {
    start_room: { blueprint_key: string; revision_id: string };
    stats: Record<string, unknown>;
    resources: Record<string, unknown>;
    skill_grants: unknown[];
    item_grants: unknown[];
  };
}

export interface CharacterApi {
  listProfiles(accessToken: string): Promise<{ profiles: CharacterCreationProfile[] }>;
  createCharacter(
    accessToken: string,
    input: CharacterCreationInput,
    idempotencyKey: string,
  ): Promise<CharacterCreationResult>;
}

interface ErrorBody {
  error?: { code?: string };
}

export class CharacterApiError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
  ) {
    super(code);
    this.name = "CharacterApiError";
  }
}

async function characterRequest<T>(
  path: string,
  accessToken: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "include",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...options.headers,
      },
    });
  } catch {
    throw new CharacterApiError("CHARACTER_REQUEST_FAILED", 0);
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorBody;
    throw new CharacterApiError(
      payload.error?.code ?? "CHARACTER_REQUEST_FAILED",
      response.status,
    );
  }
  return (await response.json()) as T;
}

export const characterApi: CharacterApi = {
  listProfiles(accessToken) {
    return characterRequest<{ profiles: CharacterCreationProfile[] }>(
      "/api/v1/character-creation-profiles",
      accessToken,
    );
  },
  createCharacter(accessToken, input, idempotencyKey) {
    return characterRequest<CharacterCreationResult>("/api/v1/characters", accessToken, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    });
  },
};
