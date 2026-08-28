from __future__ import annotations

import copy
import re
import unicodedata
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import DatabaseError, IntegrityError, transaction

from new_mud.apps.content.models import (
    BlueprintRevision,
    ContentReleaseHead,
    ContentReleaseItem,
)
from new_mud.apps.content.registry import RegistryError, canonical_sha256
from new_mud.apps.identity.models import AuthSession, GameAccount
from new_mud.mudlibs.jinyong_core.character_creation import build_character_registry_catalog

from .models import (
    Character,
    CharacterCreationRecord,
    CharacterCreationRequestRecord,
    CharacterOwnership,
)

IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
RESERVED_DISPLAY_NAMES = frozenset(
    {
        "admin",
        "administrator",
        "gm",
        "newmud",
        "new_mud",
        "system",
        "公告",
        "官方",
        "客服",
        "管理员",
        "系统",
    }
)


class CharacterProfileInvalid(Exception):
    pass


class CharacterDisplayNameInvalid(Exception):
    pass


class CharacterAlreadyExists(Exception):
    pass


class CharacterCreationUnavailable(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SelectableCharacterCreationProfile:
    key: str
    version: str
    definition_hash: str
    display_name: str
    gender_options: tuple[str, ...]
    pronoun_options: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "version": self.version,
            "definition_hash": self.definition_hash,
            "display_name": self.display_name,
            "gender_options": list(self.gender_options),
            "pronoun_options": list(self.pronoun_options),
        }


def list_selectable_character_creation_profiles(
    *, game_account_id: uuid.UUID
) -> tuple[SelectableCharacterCreationProfile, ...]:
    if CharacterOwnership.objects.filter(game_account_id=game_account_id).exists():
        return ()
    definitions = build_character_registry_catalog().active_definitions(
        "character_creation_profile"
    )
    return tuple(
        SelectableCharacterCreationProfile(
            key=definition.registry_key,
            version=definition.registry_version,
            definition_hash=definition.definition_hash or "",
            display_name=str(definition.declaration["display_name"]),
            gender_options=tuple(definition.declaration["gender_options"]),
            pronoun_options=tuple(definition.declaration["pronoun_options"]),
        )
        for definition in definitions
    )


def _is_cjk(value: str) -> bool:
    codepoint = ord(value)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x3134F
    )


def _is_allowed_display_character(value: str) -> bool:
    if value == "·" or value.isdecimal() or _is_cjk(value):
        return True
    return unicodedata.category(value).startswith("L") and "LATIN" in unicodedata.name(value, "")


def normalize_character_display_name(value: object) -> str:
    if not isinstance(value, str):
        raise CharacterDisplayNameInvalid
    normalized = unicodedata.normalize("NFKC", value)
    if not 2 <= len(normalized) <= 12:
        raise CharacterDisplayNameInvalid
    if not all(_is_allowed_display_character(character) for character in normalized):
        raise CharacterDisplayNameInvalid
    if all(character.isdecimal() for character in normalized):
        raise CharacterDisplayNameInvalid
    if normalized.casefold() in RESERVED_DISPLAY_NAMES:
        raise CharacterDisplayNameInvalid
    return normalized


def _creation_profile(*, key: object, version: object):
    if not isinstance(key, str) or not isinstance(version, str):
        raise CharacterProfileInvalid
    try:
        return build_character_registry_catalog().resolve_active(
            "character_creation_profile",
            key,
            version,
        )
    except RegistryError as error:
        raise CharacterProfileInvalid from error


def _resolve_profile_blueprint(
    *,
    batch_id,
    reference: object,
    expected_kind: str,
) -> tuple[str, BlueprintRevision]:
    if (
        not isinstance(reference, dict)
        or set(reference) != {"blueprint_key", "expected_kind"}
        or reference.get("expected_kind") != expected_kind
        or not isinstance(reference.get("blueprint_key"), str)
    ):
        raise CharacterProfileInvalid
    try:
        item = ContentReleaseItem.objects.select_related("published_revision").get(
            batch_id=batch_id,
            blueprint_key=reference["blueprint_key"],
        )
    except ContentReleaseItem.DoesNotExist as error:
        raise CharacterProfileInvalid from error
    raw_payload = item.published_revision.raw_payload
    if not isinstance(raw_payload, dict) or raw_payload.get("kind") != expected_kind:
        raise CharacterProfileInvalid
    return str(reference["blueprint_key"]), item.published_revision


def _resolved_initial_state(
    *, batch_id, declaration: object
) -> tuple[dict[str, object], BlueprintRevision]:
    if not isinstance(declaration, dict):
        raise CharacterProfileInvalid
    start_room_key, start_room_revision = _resolve_profile_blueprint(
        batch_id=batch_id,
        reference=declaration.get("start_room_ref"),
        expected_kind="room",
    )
    raw_initial_state = declaration.get("initial_state")
    if not isinstance(raw_initial_state, dict):
        raise CharacterProfileInvalid
    initial_state = copy.deepcopy(raw_initial_state)
    resolved_skill_grants: list[dict[str, object]] = []
    for grant in initial_state["skill_grants"]:
        if not isinstance(grant, dict):
            raise CharacterProfileInvalid
        _key, revision = _resolve_profile_blueprint(
            batch_id=batch_id,
            reference=grant.get("skill_ref"),
            expected_kind="skill",
        )
        resolved_skill_grants.append({**grant, "revision_id": str(revision.pk)})
    resolved_item_grants: list[dict[str, object]] = []
    for grant in initial_state["item_grants"]:
        if not isinstance(grant, dict):
            raise CharacterProfileInvalid
        _key, revision = _resolve_profile_blueprint(
            batch_id=batch_id,
            reference=grant.get("item_ref"),
            expected_kind="item",
        )
        resolved_item_grants.append({**grant, "revision_id": str(revision.pk)})
    initial_state["skill_grants"] = resolved_skill_grants
    initial_state["item_grants"] = resolved_item_grants
    initial_state["schema_version"] = declaration["initial_state_schema_version"]
    initial_state["start_room"] = {
        "blueprint_key": start_room_key,
        "revision_id": str(start_room_revision.pk),
    }
    return initial_state, start_room_revision


def _response_payload(
    *,
    character: Character,
    profile,
    initial_state: dict[str, object],
) -> dict[str, object]:
    return {
        "character_id": str(character.pk),
        "display_name": character.display_name,
        "gender": character.gender,
        "pronouns": character.pronouns,
        "creation_profile": {
            "key": profile.registry_key,
            "version": profile.registry_version,
            "definition_hash": profile.definition_hash,
        },
        "initial_state_summary": {
            "start_room": initial_state["start_room"],
            "stats": initial_state["stats"],
            "resources": initial_state["resources"],
            "skill_grants": initial_state["skill_grants"],
            "item_grants": initial_state["item_grants"],
        },
    }


def create_character(
    *,
    auth_session: AuthSession,
    idempotency_key: object,
    creation_profile_key: object,
    creation_profile_version: object,
    display_name: object,
    gender: object,
    pronouns: object,
) -> dict[str, object]:
    if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY.fullmatch(idempotency_key):
        raise CharacterCreationUnavailable
    profile = _creation_profile(key=creation_profile_key, version=creation_profile_version)
    normalized_display_name = normalize_character_display_name(display_name)
    if (
        not isinstance(gender, str)
        or gender not in profile.declaration["gender_options"]
        or not isinstance(pronouns, str)
        or pronouns not in profile.declaration["pronoun_options"]
    ):
        raise CharacterProfileInvalid
    request_payload = {
        "creation_profile_key": creation_profile_key,
        "creation_profile_version": creation_profile_version,
        "display_name": display_name,
        "gender": gender,
        "pronouns": pronouns,
    }
    request_hash = canonical_sha256(request_payload)

    try:
        with transaction.atomic():
            try:
                account = GameAccount.objects.select_for_update().get(
                    pk=auth_session.game_account_id,
                    instance_id=settings.CONTENT_INSTANCE_ID,
                    lifecycle=GameAccount.Lifecycle.ACTIVE,
                )
            except GameAccount.DoesNotExist as error:
                raise CharacterCreationUnavailable from error
            existing_request = CharacterCreationRequestRecord.objects.filter(
                game_account=account,
                idempotency_key=idempotency_key,
            ).first()
            if existing_request is not None:
                if existing_request.canonical_request_hash != request_hash:
                    raise CharacterCreationUnavailable
                return dict(existing_request.response_json)
            if CharacterOwnership.objects.filter(game_account=account).exists():
                raise CharacterAlreadyExists
            try:
                release_head = ContentReleaseHead.objects.select_for_update().get(
                    instance_id=settings.CONTENT_INSTANCE_ID,
                    mudlib_key="jinyong.core",
                    target_content_release="jinyong.release",
                    active_batch__isnull=False,
                )
            except ContentReleaseHead.DoesNotExist as error:
                raise CharacterProfileInvalid from error
            active_batch_id = release_head.active_batch_id
            if active_batch_id is None:
                raise CharacterProfileInvalid
            initial_state, start_room_revision = _resolved_initial_state(
                batch_id=active_batch_id,
                declaration=profile.declaration,
            )
            if Character.objects.filter(
                instance_id=account.instance_id,
                normalized_display_name=normalized_display_name,
            ).exists():
                raise CharacterDisplayNameInvalid
            character = Character.objects.create(
                instance_id=account.instance_id,
                display_name=normalized_display_name,
                normalized_display_name=normalized_display_name,
                gender=gender,
                pronouns=pronouns,
                initial_state=initial_state,
                start_room_revision=start_room_revision,
            )
            CharacterOwnership.objects.create(game_account=account, character=character)
            CharacterCreationRecord.objects.create(
                character=character,
                game_account=account,
                profile_key=profile.registry_key,
                profile_version=profile.registry_version,
                profile_definition_hash=profile.definition_hash,
                content_release_batch_id=active_batch_id,
                start_room_revision=start_room_revision,
                normalized_display_name=normalized_display_name,
                gender=gender,
                pronouns=pronouns,
                resolved_initial_state=initial_state,
            )
            response_payload = _response_payload(
                character=character,
                profile=profile,
                initial_state=initial_state,
            )
            CharacterCreationRequestRecord.objects.create(
                game_account=account,
                idempotency_key=idempotency_key,
                canonical_request_hash=request_hash,
                character=character,
                response_json=response_payload,
            )
            return response_payload
    except IntegrityError as error:
        diagnostic = getattr(getattr(error, "__cause__", None), "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name == "characters_instance_display_name_uniq":
            raise CharacterDisplayNameInvalid from error
        if constraint_name in {
            "characters_game_account_one_character_uniq",
            "characters_characterownership_character_id_key",
        }:
            raise CharacterAlreadyExists from error
        raise CharacterCreationUnavailable from error
    except DatabaseError as error:
        raise CharacterCreationUnavailable from error
