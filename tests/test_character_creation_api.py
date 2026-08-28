from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from new_mud.apps.characters.models import Character
from new_mud.apps.content.runtime import ContentRuntimeStatus, get_content_runtime
from new_mud.apps.identity.models import GameAccount
from new_mud.apps.identity.services import login

pytestmark = pytest.mark.django_db(transaction=True)


def authenticated_client(client: Client, *, username: str = "character_player") -> Client:
    user = get_user_model().objects.create_user(
        username=username,
        password="safe-character-passphrase-42",
    )
    GameAccount.objects.create(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    authentication = login(username=username, password="safe-character-passphrase-42")
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {authentication.access_token}"
    client.defaults["HTTP_ORIGIN"] = "https://testserver"
    return client


def start_content() -> None:
    snapshot = get_content_runtime(settings.CONTENT_INSTANCE_ID).start()
    assert snapshot.status is ContentRuntimeStatus.READY


def test_authenticated_player_reads_only_selectable_character_creation_profile_fields(
    client: Client,
) -> None:
    start_content()
    authenticated_client(client)

    response = client.get(reverse("character-creation-profile-list"), secure=True)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "profiles": [
            {
                "key": "default-v1",
                "version": "1.0.0",
                "definition_hash": response.json()["profiles"][0]["definition_hash"],
                "display_name": "江湖新秀",
                "gender_options": ["unspecified", "female", "male", "nonbinary"],
                "pronoun_options": ["unspecified", "she", "he", "they"],
            }
        ]
    }
    assert len(response.json()["profiles"][0]["definition_hash"]) == 64
    serialized = str(response.json())
    for internal_field in (
        "initial_state",
        "stats",
        "resources",
        "skill_grants",
        "item_grants",
        "source_ref",
        "start_room_ref",
    ):
        assert internal_field not in serialized


def test_authenticated_player_creates_character_from_exact_profile(client: Client) -> None:
    start_content()
    authenticated_client(client, username="create_character_player")
    profile_response = client.get(reverse("character-creation-profile-list"), secure=True)
    profile = profile_response.json()["profiles"][0]

    response = client.post(
        reverse("character-list"),
        {
            "creation_profile_key": profile["key"],
            "creation_profile_version": profile["version"],
            "display_name": "侠客甲",
            "gender": "unspecified",
            "pronouns": "unspecified",
        },
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-happy-path"},
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()
    assert len(payload["character_id"]) == 36
    assert payload["display_name"] == "侠客甲"
    assert payload["gender"] == "unspecified"
    assert payload["pronouns"] == "unspecified"
    assert payload["creation_profile"] == {
        "key": profile["key"],
        "version": profile["version"],
        "definition_hash": profile["definition_hash"],
    }
    assert payload["initial_state_summary"] == {
        "start_room": {
            "blueprint_key": "room.xiangyang.east_gate",
            "revision_id": payload["initial_state_summary"]["start_room"]["revision_id"],
        },
        "stats": {},
        "resources": {},
        "skill_grants": [],
        "item_grants": [],
    }
    assert len(payload["initial_state_summary"]["start_room"]["revision_id"]) == 36


def test_character_creation_rejects_client_supplied_initial_state_without_partial_creation(
    client: Client,
) -> None:
    start_content()
    authenticated_client(client, username="injected_state_player")
    profile = client.get(
        reverse("character-creation-profile-list"),
        secure=True,
    ).json()["profiles"][0]
    valid_payload = {
        "creation_profile_key": profile["key"],
        "creation_profile_version": profile["version"],
        "display_name": "守界人",
        "gender": "unspecified",
        "pronouns": "unspecified",
    }

    rejected = client.post(
        reverse("character-list"),
        {**valid_payload, "initial_state": {"stats": {"strength": 9999}}},
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-injected-state"},
    )

    assert rejected.status_code == 400
    assert rejected.json() == {"error": {"code": "CHARACTER_PROFILE_INVALID"}}

    accepted = client.post(
        reverse("character-list"),
        valid_payload,
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-after-rejection"},
    )
    assert accepted.status_code == 201
    assert accepted.json()["initial_state_summary"]["stats"] == {}


@pytest.mark.parametrize(
    "display_name",
    (
        "侠",
        "一二三四五六七八九十甲乙丙",
        "侠 客",
        "侠\n客",
        "侠\u202e客",
        "侠😀客",
        "１２３",
        "ＧＭ",
        "Ж侠",
        "侠_客",
    ),
)
def test_character_display_name_policy_returns_one_stable_error(
    client: Client,
    display_name: str,
) -> None:
    start_content()
    authenticated_client(client, username=f"invalid_name_{abs(hash(display_name))}")

    response = client.post(
        reverse("character-list"),
        {
            "creation_profile_key": "default-v1",
            "creation_profile_version": "1.0.0",
            "display_name": display_name,
            "gender": "unspecified",
            "pronouns": "unspecified",
        },
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-invalid-name"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "CHARACTER_DISPLAY_NAME_INVALID"}}


def test_nfkc_name_occupancy_does_not_reveal_more_than_policy_failure() -> None:
    start_content()
    first_client = authenticated_client(Client(), username="nfkc_name_owner")
    occupied = first_client.post(
        reverse("character-list"),
        {
            "creation_profile_key": "default-v1",
            "creation_profile_version": "1.0.0",
            "display_name": "Ａｌｉｃｅ",
            "gender": "female",
            "pronouns": "she",
        },
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-nfkc-owner"},
    )
    assert occupied.status_code == 201
    assert occupied.json()["display_name"] == "Alice"

    second_client = authenticated_client(Client(), username="nfkc_name_contender")
    collision = second_client.post(
        reverse("character-list"),
        {
            "creation_profile_key": "default-v1",
            "creation_profile_version": "1.0.0",
            "display_name": "Alice",
            "gender": "unspecified",
            "pronouns": "unspecified",
        },
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-nfkc-contender"},
    )
    syntactically_invalid_client = authenticated_client(Client(), username="invalid_name_peer")
    invalid = syntactically_invalid_client.post(
        reverse("character-list"),
        {
            "creation_profile_key": "default-v1",
            "creation_profile_version": "1.0.0",
            "display_name": "Alice Smith",
            "gender": "unspecified",
            "pronouns": "unspecified",
        },
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-invalid-peer"},
    )

    assert collision.status_code == invalid.status_code == 400
    assert (
        collision.json() == invalid.json() == {"error": {"code": "CHARACTER_DISPLAY_NAME_INVALID"}}
    )


def test_character_creation_replays_same_request_and_rejects_rebuild(client: Client) -> None:
    start_content()
    authenticated_client(client, username="idempotent_character_player")
    payload = {
        "creation_profile_key": "default-v1",
        "creation_profile_version": "1.0.0",
        "display_name": "重来客",
        "gender": "nonbinary",
        "pronouns": "they",
    }

    first = client.post(
        reverse("character-list"),
        payload,
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-replay"},
    )
    replay = client.post(
        reverse("character-list"),
        payload,
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-replay"},
    )

    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()

    character = Character.objects.get(pk=first.json()["character_id"])
    Character.objects.filter(pk=character.pk).update(lifecycle=Character.Lifecycle.RETIRED)
    profiles_after_retirement = client.get(
        reverse("character-creation-profile-list"),
        secure=True,
    )
    assert profiles_after_retirement.status_code == 200
    assert profiles_after_retirement.json() == {"profiles": []}
    rebuild = client.post(
        reverse("character-list"),
        {**payload, "display_name": "再来客"},
        content_type="application/json",
        secure=True,
        headers={"idempotency-key": "character-create-rebuild"},
    )
    assert rebuild.status_code == 409
    assert rebuild.json() == {"error": {"code": "CHARACTER_ALREADY_EXISTS"}}


def test_invalid_profile_and_display_options_use_stable_profile_error(client: Client) -> None:
    start_content()
    authenticated_client(client, username="invalid_profile_player")
    base_payload = {
        "creation_profile_key": "default-v1",
        "creation_profile_version": "1.0.0",
        "display_name": "问路人",
        "gender": "unspecified",
        "pronouns": "unspecified",
    }

    for index, invalid_payload in enumerate(
        (
            {**base_payload, "creation_profile_version": "9.9.9"},
            {**base_payload, "gender": "strength-boost"},
            {**base_payload, "pronouns": "unknown"},
        )
    ):
        response = client.post(
            reverse("character-list"),
            invalid_payload,
            content_type="application/json",
            secure=True,
            headers={"idempotency-key": f"character-create-invalid-profile-{index}"},
        )
        assert response.status_code == 400
        assert response.json() == {"error": {"code": "CHARACTER_PROFILE_INVALID"}}
