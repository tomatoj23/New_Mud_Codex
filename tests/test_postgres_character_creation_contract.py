from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections, connection, transaction

from new_mud.apps.characters.models import (
    Character,
    CharacterCreationRecord,
    CharacterCreationRequestRecord,
    CharacterOwnership,
)
from new_mud.apps.characters.services import (
    CharacterAlreadyExists,
    CharacterCreationUnavailable,
    CharacterDisplayNameInvalid,
    create_character,
)
from new_mud.apps.content.models import ContentReleaseHead
from new_mud.apps.content.runtime import ContentRuntimeStatus, get_content_runtime
from new_mud.apps.identity.models import AuthSession, GameAccount
from new_mud.apps.identity.services import login, resolve_active_auth_session

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]


def start_content() -> None:
    snapshot = get_content_runtime(settings.CONTENT_INSTANCE_ID).start()
    assert snapshot.status is ContentRuntimeStatus.READY


def authenticated_session(*, username: str):
    user = get_user_model().objects.create_user(
        username=username,
        password="safe-character-passphrase-42",
    )
    GameAccount.objects.create(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    result = login(username=username, password="safe-character-passphrase-42")
    return resolve_active_auth_session(result.access_token)


def create_default_character(*, username: str, display_name: str, idempotency_key: str):
    return create_character(
        auth_session=authenticated_session(username=username),
        idempotency_key=idempotency_key,
        creation_profile_key="default-v1",
        creation_profile_version="1.0.0",
        display_name=display_name,
        gender="unspecified",
        pronouns="unspecified",
    )


def force_deferred_constraints() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def create_character_from_thread(
    *,
    auth_session_id,
    idempotency_key: str,
    display_name: str,
    start: Event,
) -> tuple[str, dict[str, object] | None]:
    close_old_connections()
    try:
        assert start.wait(timeout=5)
        auth_session = AuthSession.objects.get(pk=auth_session_id)
        result = create_character(
            auth_session=auth_session,
            idempotency_key=idempotency_key,
            creation_profile_key="default-v1",
            creation_profile_version="1.0.0",
            display_name=display_name,
            gender="unspecified",
            pronouns="unspecified",
        )
        return "created", result
    except CharacterAlreadyExists:
        return "already-exists", None
    except CharacterDisplayNameInvalid:
        return "display-name-invalid", None
    finally:
        close_old_connections()


def test_creation_pins_evidence_and_database_rejects_history_or_ownership_rewrite() -> None:
    start_content()
    result = create_default_character(
        username="immutable_character_player",
        display_name="留痕客",
        idempotency_key="immutable-character-create",
    )

    assert Character.objects.count() == 1
    assert CharacterOwnership.objects.count() == 1
    assert CharacterCreationRecord.objects.count() == 1
    assert CharacterCreationRequestRecord.objects.count() == 1
    character = Character.objects.get(pk=result["character_id"])
    ownership = CharacterOwnership.objects.get(character=character)
    evidence = CharacterCreationRecord.objects.get(character=character)
    request_record = CharacterCreationRequestRecord.objects.get(character=character)
    active_batch_id = ContentReleaseHead.objects.get(
        instance_id=settings.CONTENT_INSTANCE_ID,
        mudlib_key="jinyong.core",
        target_content_release="jinyong.release",
    ).active_batch_id
    assert evidence.game_account_id == ownership.game_account_id
    assert evidence.profile_key == "default-v1"
    assert evidence.profile_version == "1.0.0"
    assert evidence.profile_definition_hash == result["creation_profile"]["definition_hash"]
    assert evidence.content_release_batch_id == active_batch_id
    assert evidence.start_room_revision_id == character.start_room_revision_id
    assert request_record.response_json == result

    for model, primary_key in (
        (CharacterCreationRecord, evidence.pk),
        (CharacterCreationRequestRecord, request_record.pk),
        (CharacterOwnership, ownership.pk),
    ):
        with pytest.raises(DatabaseError):
            model.objects.filter(pk=primary_key).update(created_at=evidence.created_at)
        with pytest.raises(DatabaseError):
            model.objects.filter(pk=primary_key).delete()


def test_database_rejects_creation_evidence_bound_to_another_game_account() -> None:
    start_content()
    owner_session = authenticated_session(username="evidence_owner")
    other_session = authenticated_session(username="evidence_other_account")
    release_head = ContentReleaseHead.objects.get(
        instance_id=settings.CONTENT_INSTANCE_ID,
        mudlib_key="jinyong.core",
        target_content_release="jinyong.release",
    )
    assert release_head.active_batch_id is not None
    existing = create_default_character(
        username="evidence_template",
        display_name="证据样本",
        idempotency_key="evidence-template-create",
    )
    template = Character.objects.get(pk=existing["character_id"])
    character = Character.objects.create(
        instance_id=settings.CONTENT_INSTANCE_ID,
        display_name="错绑客",
        normalized_display_name="错绑客",
        gender="unspecified",
        pronouns="unspecified",
        initial_state=template.initial_state,
        start_room_revision=template.start_room_revision,
    )
    CharacterOwnership.objects.create(
        game_account_id=owner_session.game_account_id,
        character=character,
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        CharacterCreationRecord.objects.create(
            character=character,
            game_account_id=other_session.game_account_id,
            profile_key="default-v1",
            profile_version="1.0.0",
            profile_definition_hash="a" * 64,
            content_release_batch_id=release_head.active_batch_id,
            start_room_revision=template.start_room_revision,
            normalized_display_name=character.normalized_display_name,
            gender=character.gender,
            pronouns=character.pronouns,
            resolved_initial_state=character.initial_state,
        )
        force_deferred_constraints()


def test_database_rejects_idempotency_result_bound_to_another_game_account() -> None:
    start_content()
    first = create_default_character(
        username="request_record_owner",
        display_name="重放甲",
        idempotency_key="request-record-owner-create",
    )
    second = create_default_character(
        username="request_record_other",
        display_name="重放乙",
        idempotency_key="request-record-other-create",
    )
    first_character = Character.objects.get(pk=first["character_id"])
    second_ownership = CharacterOwnership.objects.get(character_id=second["character_id"])

    with pytest.raises(DatabaseError), transaction.atomic():
        CharacterCreationRequestRecord.objects.create(
            game_account_id=second_ownership.game_account_id,
            idempotency_key="request-record-cross-account",
            canonical_request_hash="b" * 64,
            character=first_character,
            response_status=201,
            response_json=first,
        )
        force_deferred_constraints()


def test_concurrent_same_idempotent_request_converges_on_one_character() -> None:
    start_content()
    auth_session = authenticated_session(username="concurrent_idempotent_character")
    start = Event()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                create_character_from_thread,
                auth_session_id=auth_session.pk,
                idempotency_key="concurrent-character-replay",
                display_name="并发重放",
                start=start,
            )
            for _ in range(2)
        ]
        start.set()
        outcomes = [future.result(timeout=10) for future in futures]

    assert outcomes[0][0] == outcomes[1][0] == "created"
    assert outcomes[0][1] == outcomes[1][1]
    assert Character.objects.count() == 1
    assert CharacterOwnership.objects.count() == 1
    assert CharacterCreationRecord.objects.count() == 1
    assert CharacterCreationRequestRecord.objects.count() == 1


def test_concurrent_different_requests_for_one_account_create_at_most_one_character() -> None:
    start_content()
    auth_session = authenticated_session(username="concurrent_single_character")
    start = Event()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                create_character_from_thread,
                auth_session_id=auth_session.pk,
                idempotency_key=f"concurrent-single-account-{index}",
                display_name=f"并发客{index}",
                start=start,
            )
            for index in range(2)
        ]
        start.set()
        outcomes = [future.result(timeout=10)[0] for future in futures]

    assert sorted(outcomes) == ["already-exists", "created"]
    assert Character.objects.count() == 1
    assert CharacterOwnership.objects.count() == 1
    assert CharacterCreationRecord.objects.count() == 1
    assert CharacterCreationRequestRecord.objects.count() == 1


def test_concurrent_nfkc_name_claim_has_one_non_enumerating_loser() -> None:
    start_content()
    sessions = (
        authenticated_session(username="concurrent_name_a"),
        authenticated_session(username="concurrent_name_b"),
    )
    start = Event()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                create_character_from_thread,
                auth_session_id=session.pk,
                idempotency_key=f"concurrent-name-{index}",
                display_name=name,
                start=start,
            )
            for index, (session, name) in enumerate(
                zip(sessions, ("Ａｌｉｃｅ", "Alice"), strict=True)
            )
        ]
        start.set()
        outcomes = [future.result(timeout=10)[0] for future in futures]

    assert sorted(outcomes) == ["created", "display-name-invalid"]
    assert Character.objects.count() == 1
    assert Character.objects.get().normalized_display_name == "Alice"


def test_late_database_failure_rolls_back_all_creation_rows_and_allows_retry() -> None:
    start_content()
    auth_session = authenticated_session(username="rollback_character_player")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE FUNCTION characters_test_fail_creation_evidence()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'test creation evidence failure' USING ERRCODE = '23514';
            END;
            $$
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER characters_test_fail_creation_evidence_trigger
            BEFORE INSERT ON characters_charactercreationrecord
            FOR EACH ROW EXECUTE FUNCTION characters_test_fail_creation_evidence()
            """
        )

    try:
        with pytest.raises(CharacterCreationUnavailable):
            create_character(
                auth_session=auth_session,
                idempotency_key="rollback-character-create",
                creation_profile_key="default-v1",
                creation_profile_version="1.0.0",
                display_name="回滚客",
                gender="unspecified",
                pronouns="unspecified",
            )
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER IF EXISTS characters_test_fail_creation_evidence_trigger "
                "ON characters_charactercreationrecord"
            )
            cursor.execute("DROP FUNCTION IF EXISTS characters_test_fail_creation_evidence()")

    assert Character.objects.count() == 0
    assert CharacterOwnership.objects.count() == 0
    assert CharacterCreationRecord.objects.count() == 0
    assert CharacterCreationRequestRecord.objects.count() == 0

    retry = create_character(
        auth_session=auth_session,
        idempotency_key="rollback-character-create",
        creation_profile_key="default-v1",
        creation_profile_version="1.0.0",
        display_name="回滚客",
        gender="unspecified",
        pronouns="unspecified",
    )
    assert retry["display_name"] == "回滚客"
    assert Character.objects.count() == 1
    assert CharacterOwnership.objects.count() == 1
    assert CharacterCreationRecord.objects.count() == 1
    assert CharacterCreationRequestRecord.objects.count() == 1
