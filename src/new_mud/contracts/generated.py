"""Generated from contracts/v1/catalogs; do not edit by hand."""

from enum import IntEnum, StrEnum


class AcceptanceStatesAlignmentStatuses(StrEnum):
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class AcceptanceStatesNonPassingReviewStatuses(StrEnum):
    BLOCKED = "blocked"
    MANUAL_REVIEW = "manual_review"
    UNVERIFIED = "unverified"


class ContentStatesBlueprintDependencyKinds(StrEnum):
    BLUEPRINT_REF = "blueprint_ref"
    PARENT = "parent"


class ContentStatesBlueprintRevisionKinds(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ContentStatesPublicationReasons(StrEnum):
    CONTENT_PUBLISH = "content_publish"
    DEPENDENCY_RECOMPILE = "dependency_recompile"
    ROLLBACK_RECOMPILE = "rollback_recompile"
    SEED_BOOTSTRAP = "seed_bootstrap"


class ProtocolErrorsActionDomain(StrEnum):
    ACTION_AMBIGUOUS = "ACTION_AMBIGUOUS"
    ACTION_ARGUMENT_INVALID = "ACTION_ARGUMENT_INVALID"
    ACTION_FORBIDDEN = "ACTION_FORBIDDEN"
    ACTION_NOT_FOUND = "ACTION_NOT_FOUND"
    ACTION_SOURCE_FORBIDDEN = "ACTION_SOURCE_FORBIDDEN"
    CHAT_FORBIDDEN = "CHAT_FORBIDDEN"
    CHAT_RATE_LIMITED = "CHAT_RATE_LIMITED"
    COMBAT_STATE_CONFLICT = "COMBAT_STATE_CONFLICT"
    ENTITY_LOCATION_INVALID = "ENTITY_LOCATION_INVALID"
    INVENTORY_VERSION_CONFLICT = "INVENTORY_VERSION_CONFLICT"
    ITEM_CONTAINER_CYCLE = "ITEM_CONTAINER_CYCLE"
    ITEM_CONTAINER_FULL = "ITEM_CONTAINER_FULL"
    ITEM_CONTAINER_NOT_ALLOWED = "ITEM_CONTAINER_NOT_ALLOWED"
    ITEM_NOT_AVAILABLE = "ITEM_NOT_AVAILABLE"
    ROOM_EXIT_BLOCKED = "ROOM_EXIT_BLOCKED"


class ProtocolErrorsAuthenticationPresence(StrEnum):
    ALREADY_AUTHENTICATED = "ALREADY_AUTHENTICATED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CHARACTER_FORBIDDEN = "CHARACTER_FORBIDDEN"
    CHARACTER_NOT_FOUND = "CHARACTER_NOT_FOUND"
    CHARACTER_OCCUPIED = "CHARACTER_OCCUPIED"
    PRESENCE_ACTIVATION_FAILED = "PRESENCE_ACTIVATION_FAILED"
    PRESENCE_NOT_ACTIVE = "PRESENCE_NOT_ACTIVE"
    PRESENCE_REQUIRED = "PRESENCE_REQUIRED"
    RESUME_TICKET_EXPIRED = "RESUME_TICKET_EXPIRED"
    RESUME_TICKET_INVALID = "RESUME_TICKET_INVALID"
    SESSION_RESUME_FAILED = "SESSION_RESUME_FAILED"
    SESSION_REVOKED = "SESSION_REVOKED"
    TAKEOVER_CONFIRMATION_REQUIRED = "TAKEOVER_CONFIRMATION_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"


class ProtocolErrorsProtocol(StrEnum):
    INVALID_ENVELOPE = "INVALID_ENVELOPE"
    PAYLOAD_INVALID = "PAYLOAD_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_CONTEXT_CHANGED = "REQUEST_CONTEXT_CHANGED"
    REQUEST_ID_CONFLICT = "REQUEST_ID_CONFLICT"
    REQUEST_ID_INVALID = "REQUEST_ID_INVALID"
    REQUEST_TYPE_UNSUPPORTED = "REQUEST_TYPE_UNSUPPORTED"
    UNSUPPORTED_PROTOCOL_VERSION = "UNSUPPORTED_PROTOCOL_VERSION"


class ProtocolStatesActivationStates(StrEnum):
    ACTIVE = "active"
    ACTIVATION_PENDING = "activation_pending"
    COMPENSATED = "compensated"
    NOT_REQUIRED = "not_required"


class ProtocolStatesDeliveryStatuses(StrEnum):
    BOUND = "bound"
    RESUME_REQUIRED = "resume_required"
    SUPERSEDED = "superseded"


class ProtocolActionSources(StrEnum):
    SHORTCUT = "shortcut"
    TEXT_COMMAND = "text_command"
    UI_BUTTON = "ui_button"
    UI_MENU = "ui_menu"


class ProtocolApplicationCloseCodes(IntEnum):
    VALUE_4400 = 4400


class ProtocolClientEnvelopeFields(StrEnum):
    PAYLOAD = "payload"
    REQUEST_ID = "request_id"
    TYPE = "type"
    VERSION = "version"


class ProtocolEventTypes(StrEnum):
    CHARACTER_SNAPSHOT = "character.snapshot"
    CHAT_CHANNEL_MESSAGE = "chat.channel_message"
    CHAT_PRIVATE_MESSAGE = "chat.private_message"
    COMBAT_SNAPSHOT = "combat.snapshot"
    PRESENCE_ENTERED = "presence.entered"
    PRESENCE_LEFT = "presence.left"
    PRESENCE_TAKEN_OVER = "presence.taken_over"
    ROOM_ACTOR_ENTERED = "room.actor_entered"
    ROOM_ACTOR_LEFT = "room.actor_left"
    ROOM_OUTPUT = "room.output"
    SCENE_SNAPSHOT = "scene.snapshot"
    SESSION_READY = "session.ready"
    SESSION_RESUMED = "session.resumed"
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_NOTICE = "system.notice"
    UI_ACTIONS_RESOLVED = "ui.actions.resolved"


class ProtocolProtocolVersions(StrEnum):
    VALUE_1 = "1"


class ProtocolRequestTypes(StrEnum):
    ACTION_INVOKE = "action.invoke"
    PRESENCE_ENTER = "presence.enter"
    PRESENCE_LEAVE = "presence.leave"
    PRESENCE_TAKEOVER = "presence.takeover"
    SESSION_AUTHENTICATE = "session.authenticate"
    SESSION_PING = "session.ping"
    SESSION_RESUME = "session.resume"
    STATE_SYNC = "state.sync"
    UI_ACTIONS_RESOLVE = "ui.actions.resolve"


class ProtocolServerEnvelopeFields(StrEnum):
    PAYLOAD = "payload"
    SEQ = "seq"
    TS = "ts"
    TYPE = "type"
    VERSION = "version"


class ProtocolTerminalTypes(StrEnum):
    REQUEST_FAILED = "request.failed"
    REQUEST_SUCCEEDED = "request.succeeded"


class RefreshErrorsRefresh(StrEnum):
    REFRESH_IDEMPOTENCY_CONFLICT = "REFRESH_IDEMPOTENCY_CONFLICT"
    REFRESH_IDEMPOTENCY_KEY_INVALID = "REFRESH_IDEMPOTENCY_KEY_INVALID"
    REFRESH_REQUEST_SUPERSEDED = "REFRESH_REQUEST_SUPERSEDED"
    REFRESH_TOKEN_REPLAYED = "REFRESH_TOKEN_REPLAYED"
    REFRESH_UNAVAILABLE = "REFRESH_UNAVAILABLE"


class RegistryErrorsBlueprint(StrEnum):
    BLUEPRINT_DUPLICATE_KEY = "BLUEPRINT_DUPLICATE_KEY"
    BLUEPRINT_EDIT_CONFLICT = "BLUEPRINT_EDIT_CONFLICT"
    BLUEPRINT_INHERITANCE_CYCLE = "BLUEPRINT_INHERITANCE_CYCLE"
    BLUEPRINT_KEY_INVALID = "BLUEPRINT_KEY_INVALID"
    BLUEPRINT_KIND_MISMATCH = "BLUEPRINT_KIND_MISMATCH"
    BLUEPRINT_PARENT_NOT_FOUND = "BLUEPRINT_PARENT_NOT_FOUND"
    BLUEPRINT_PROFILE_NOT_FOUND = "BLUEPRINT_PROFILE_NOT_FOUND"
    BLUEPRINT_REFERENCE_KIND_MISMATCH = "BLUEPRINT_REFERENCE_KIND_MISMATCH"
    BLUEPRINT_REFERENCE_NOT_FOUND = "BLUEPRINT_REFERENCE_NOT_FOUND"
    BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH = "BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH"
    BLUEPRINT_REGISTRY_REFERENCE_NOT_FOUND = "BLUEPRINT_REGISTRY_REFERENCE_NOT_FOUND"
    BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE = "BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE"
    BLUEPRINT_SCHEMA_INVALID = "BLUEPRINT_SCHEMA_INVALID"
    BLUEPRINT_SPAWN_POLICY_INVALID = "BLUEPRINT_SPAWN_POLICY_INVALID"


class RegistryErrorsConditionEffect(StrEnum):
    CONDITION_EFFECT_TYPE_NOT_FOUND = "CONDITION_EFFECT_TYPE_NOT_FOUND"
    CONDITION_EFFECT_TYPE_VERSION_UNAVAILABLE = "CONDITION_EFFECT_TYPE_VERSION_UNAVAILABLE"
    CONDITION_PARAMETERS_INVALID = "CONDITION_PARAMETERS_INVALID"
    EFFECT_CONDITION_REVISION_INVALID = "EFFECT_CONDITION_REVISION_INVALID"
    EFFECT_SOURCE_DEPENDENCY_INVALID = "EFFECT_SOURCE_DEPENDENCY_INVALID"


class RegistryErrorsContentRelease(StrEnum):
    CONTENT_RELEASE_CONFLICT = "CONTENT_RELEASE_CONFLICT"
    CONTENT_RELEASE_SCOPE_MISMATCH = "CONTENT_RELEASE_SCOPE_MISMATCH"
    CONTENT_RELEASE_VALIDATION_FAILED = "CONTENT_RELEASE_VALIDATION_FAILED"


class RegistryErrorsRegistry(StrEnum):
    REGISTRY_COMPAT_DEFINITION_MISSING = "REGISTRY_COMPAT_DEFINITION_MISSING"
    REGISTRY_DUPLICATE_KEY = "REGISTRY_DUPLICATE_KEY"
    REGISTRY_HANDLER_MISSING = "REGISTRY_HANDLER_MISSING"
    REGISTRY_MISSING_DEPENDENCY = "REGISTRY_MISSING_DEPENDENCY"
    REGISTRY_REFERENCE_CYCLE = "REGISTRY_REFERENCE_CYCLE"
    REGISTRY_REFERENCE_NOT_FOUND = "REGISTRY_REFERENCE_NOT_FOUND"
    REGISTRY_SCHEMA_INVALID = "REGISTRY_SCHEMA_INVALID"
    REGISTRY_STARTUP_PLAN_INVALID = "REGISTRY_STARTUP_PLAN_INVALID"
    REGISTRY_VERSION_CONTENT_MISMATCH = "REGISTRY_VERSION_CONTENT_MISMATCH"


class RegistryKinds(StrEnum):
    HANDLER = "handler"
    RULE = "rule"
    PERMISSION_POLICY = "permission_policy"
    HOOK_SET = "hook_set"
    ACTION_PROVIDER = "action_provider"
    RENDER_POLICY = "render_policy"
    BLUEPRINT_SEED_PROVIDER = "blueprint_seed_provider"
    ACTION = "action"
    BEHAVIOR_PROFILE = "behavior_profile"
    EFFECT_TYPE = "effect_type"
    JOB_TYPE = "job_type"
    WORLD_PROCESS_TYPE = "world_process_type"
    STARTUP_PLAN = "startup_plan"


class SessionStatesAuthSessionStates(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    LOGGED_OUT = "logged_out"
    REVOKED = "revoked"


class SessionStatesConnectionSessionStates(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    CLOSING = "closing"
    OPENING = "opening"


class SessionStatesCredentialStates(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"


class SessionStatesDeliveryClasses(StrEnum):
    ACTIVATION_SUCCESS = "activation_success"
    COMMITTED_REVOCATION = "committed_revocation"


class SessionStatesOutboxStates(StrEnum):
    CANCELED = "canceled"
    DELIVERED = "delivered"
    DELIVERING = "delivering"
    PENDING = "pending"


class SessionStatesPresenceRuntimeStates(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    PENDING_ENTER = "pending_enter"
    TAKEN_OVER = "taken_over"


class SessionStatesPresenceSnapshotStates(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    GRACE_DISCONNECTED = "grace_disconnected"
    TAKEN_OVER = "taken_over"


class SessionStatesRefreshFamilyStates(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SessionStatesTerminalKinds(StrEnum):
    FAILED = "failed"
    SUCCEEDED = "succeeded"
