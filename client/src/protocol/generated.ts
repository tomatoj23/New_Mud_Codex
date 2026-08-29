// Typed projection of contracts/v1/catalogs/protocol.json, guarded by a bidirectional test.
export const PROTOCOL_VERSION = "1" as const;

export const PROTOCOL_CLIENT_ENVELOPE_FIELDS = [
  "payload",
  "request_id",
  "type",
  "version",
] as const;

export const PROTOCOL_SERVER_ENVELOPE_FIELDS = [
  "payload",
  "seq",
  "ts",
  "type",
  "version",
] as const;

export const PROTOCOL_TERMINAL_TYPES = ["request.failed", "request.succeeded"] as const;
export type ProtocolTerminalType = (typeof PROTOCOL_TERMINAL_TYPES)[number];

export const PROTOCOL_EVENT_TYPES = [
  "character.snapshot",
  "chat.channel_message",
  "chat.private_message",
  "combat.snapshot",
  "presence.entered",
  "presence.left",
  "presence.taken_over",
  "room.actor_entered",
  "room.actor_left",
  "room.output",
  "scene.snapshot",
  "session.ready",
  "session.resumed",
  "system.maintenance",
  "system.notice",
  "ui.actions.resolved",
] as const;
export type ProtocolEventType = (typeof PROTOCOL_EVENT_TYPES)[number];

export const PROTOCOL_REQUEST_TYPES = [
  "action.invoke",
  "presence.enter",
  "presence.leave",
  "presence.recover",
  "presence.takeover",
  "session.authenticate",
  "session.ping",
  "session.resume",
  "state.sync",
  "ui.actions.resolve",
] as const;
export type ProtocolRequestType = (typeof PROTOCOL_REQUEST_TYPES)[number];

export const PROTOCOL_ERROR_CODES = [
  "ACTION_AMBIGUOUS",
  "ACTION_ARGUMENT_INVALID",
  "ACTION_FORBIDDEN",
  "ACTION_NOT_FOUND",
  "ACTION_SOURCE_FORBIDDEN",
  "ALREADY_AUTHENTICATED",
  "AUTH_REQUIRED",
  "CHANNEL_MUTE_INVALID",
  "CHARACTER_ALREADY_EXISTS",
  "CHARACTER_CREATION_UNAVAILABLE",
  "CHARACTER_DISPLAY_NAME_INVALID",
  "CHARACTER_FORBIDDEN",
  "CHARACTER_NOT_FOUND",
  "CHARACTER_OCCUPIED",
  "CHARACTER_PROFILE_INVALID",
  "CHAT_FORBIDDEN",
  "CHAT_RATE_LIMITED",
  "COMBAT_STATE_CONFLICT",
  "COMMUNITY_ACTION_FORBIDDEN",
  "ENTITY_LOCATION_INVALID",
  "INVALID_ENVELOPE",
  "INVENTORY_VERSION_CONFLICT",
  "ITEM_CONTAINER_CYCLE",
  "ITEM_CONTAINER_FULL",
  "ITEM_CONTAINER_NOT_ALLOWED",
  "ITEM_NOT_AVAILABLE",
  "MODERATION_APPEAL_ALREADY_SUBMITTED",
  "MODERATION_APPEAL_FORBIDDEN",
  "MODERATION_CASE_NOT_FOUND",
  "MODERATION_REPORT_INVALID",
  "PAYLOAD_INVALID",
  "PLAYER_BLOCK_INVALID",
  "PRESENCE_ACTIVATION_FAILED",
  "PRESENCE_NOT_ACTIVE",
  "PRESENCE_RECOVERY_UNAVAILABLE",
  "PRESENCE_REQUIRED",
  "RATE_LIMITED",
  "REQUEST_CONTEXT_CHANGED",
  "REQUEST_ID_CONFLICT",
  "REQUEST_ID_INVALID",
  "REQUEST_TYPE_UNSUPPORTED",
  "RESUME_TICKET_EXPIRED",
  "RESUME_TICKET_INVALID",
  "ROOM_EXIT_BLOCKED",
  "SESSION_RESUME_FAILED",
  "SESSION_REVOKED",
  "TAKEOVER_CONFIRMATION_REQUIRED",
  "TOKEN_EXPIRED",
  "TOKEN_INVALID",
  "UNSUPPORTED_PROTOCOL_VERSION",
] as const;
export type ProtocolErrorCode = (typeof PROTOCOL_ERROR_CODES)[number];
