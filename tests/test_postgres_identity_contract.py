from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import timedelta
from threading import Event

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import (
    DatabaseError,
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.utils import timezone

from new_mud.apps.identity.models import (
    AuthSession,
    GameAccount,
    RecoveryCodeCredential,
    RefreshRequestTerminalRecord,
    RefreshTokenCredential,
    RefreshTokenFamily,
)
from new_mud.apps.identity.services import (
    AuthenticationFailed,
    RefreshFailed,
    login,
    refresh,
    register,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]


def force_deferred_constraints() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def create_identity_pair(
    *,
    session_user=None,
    family_expiry_delta: timedelta = timedelta(),
    family_generation: int = 1,
    credential_generation: int = 1,
    credential_expiry_delta: timedelta = timedelta(),
) -> tuple[AuthSession, RefreshTokenFamily, RefreshTokenCredential]:
    account_user = get_user_model().objects.create_user(username=f"account_{uuid.uuid4().hex}")
    account = GameAccount.objects.create(
        user=account_user,
        instance_id=settings.CONTENT_INSTANCE_ID,
    )
    now = timezone.now()
    session_expires_at = now + timedelta(days=30)
    family_expires_at = session_expires_at + family_expiry_delta
    session = AuthSession.objects.create(
        user=session_user or account_user,
        game_account=account,
        device_id=uuid.uuid4().hex,
        issued_at=now,
        last_seen_at=now,
        absolute_expires_at=session_expires_at,
    )
    family = RefreshTokenFamily.objects.create(
        auth_session=session,
        current_generation=family_generation,
        absolute_expires_at=family_expires_at,
    )
    session.refresh_family = family
    session.save(update_fields=("refresh_family",))
    credential = RefreshTokenCredential.objects.create(
        family=family,
        generation=credential_generation,
        token_hash="0" * 64,
        jti_hash="1" * 64,
        issued_at=now,
        expires_at=family_expires_at + credential_expiry_delta,
    )
    return session, family, credential


def test_valid_identity_lifetime_pair_satisfies_all_deferred_contracts() -> None:
    with transaction.atomic():
        create_identity_pair()


def test_refresh_waits_for_account_lifecycle_commit_before_rotating() -> None:
    register(username="lifecycle_refresh", password="safe-example-passphrase-42")
    authentication = login(
        username="lifecycle_refresh",
        password="safe-example-passphrase-42",
    )
    account_id = authentication.game_account_id
    account_locked = Event()
    allow_account_commit = Event()

    def close_account() -> None:
        close_old_connections()
        try:
            with transaction.atomic():
                account = GameAccount.objects.select_for_update().get(pk=account_id)
                account.lifecycle = GameAccount.Lifecycle.COOLING_OFF
                account.lifecycle_version += 1
                account.save(update_fields=("lifecycle", "lifecycle_version"))
                account_locked.set()
                assert allow_account_commit.wait(timeout=5)
        finally:
            close_old_connections()

    def attempt_refresh():
        close_old_connections()
        try:
            return refresh(
                refresh_token=authentication.refresh_token,
                idempotency_key="lifecycle-serialization",
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        close_future = executor.submit(close_account)
        assert account_locked.wait(timeout=5)
        refresh_future = executor.submit(attempt_refresh)
        try:
            with pytest.raises(FutureTimeoutError):
                refresh_future.result(timeout=0.25)
        finally:
            allow_account_commit.set()
        close_future.result(timeout=5)
        with pytest.raises(RefreshFailed, match="SESSION_REVOKED"):
            refresh_future.result(timeout=5)


def test_login_rechecks_password_after_serializing_with_account_recovery() -> None:
    registration = register(
        username="login_recovery_race",
        password="safe-example-passphrase-42",
    )
    account_locked = Event()
    allow_recovery_commit = Event()

    def replace_password() -> None:
        close_old_connections()
        try:
            with transaction.atomic():
                account = GameAccount.objects.select_for_update().get(
                    pk=registration.game_account_id
                )
                user = get_user_model().objects.get(pk=account.user_id)
                user.set_password("replacement-passphrase-73-safe")
                user.save(update_fields=("password",))
                account_locked.set()
                assert allow_recovery_commit.wait(timeout=5)
        finally:
            close_old_connections()

    def attempt_old_password_login():
        close_old_connections()
        try:
            return login(
                username="login_recovery_race",
                password="safe-example-passphrase-42",
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        recovery_future = executor.submit(replace_password)
        assert account_locked.wait(timeout=5)
        login_future = executor.submit(attempt_old_password_login)
        try:
            with pytest.raises(FutureTimeoutError):
                login_future.result(timeout=0.25)
        finally:
            allow_recovery_commit.set()
        recovery_future.result(timeout=5)
        with pytest.raises(AuthenticationFailed):
            login_future.result(timeout=5)

    assert AuthSession.objects.count() == 0


def test_family_and_credential_identity_fields_are_immutable() -> None:
    with transaction.atomic():
        _, family, credential = create_identity_pair()

    with pytest.raises(DatabaseError), transaction.atomic():
        family.absolute_expires_at -= timedelta(seconds=1)
        family.save(update_fields=("absolute_expires_at",))

    family.refresh_from_db()
    credential.refresh_from_db()
    with pytest.raises(DatabaseError), transaction.atomic():
        family.current_generation = 2
        family.save(update_fields=("current_generation",))
        credential.generation = 2
        credential.save(update_fields=("generation",))


def test_refresh_terminal_expiry_cannot_undercut_retry_or_cleanup_floor() -> None:
    with transaction.atomic():
        _, family, credential = create_identity_pair()
    created_at = timezone.now()

    with pytest.raises(DatabaseError), transaction.atomic():
        RefreshRequestTerminalRecord.objects.create(
            family=family,
            idempotency_key="too-short-retention",
            canonical_request_hash="a" * 64,
            predecessor_credential=credential,
            access_claims_json={},
            terminal_kind=RefreshRequestTerminalRecord.TerminalKind.FAILED,
            error_code="SESSION_REVOKED",
            created_at=created_at,
            expires_at=created_at + timedelta(hours=1),
        )
        force_deferred_constraints()


def test_auth_session_user_must_own_its_game_account() -> None:
    other_user = get_user_model().objects.create_user(username="other_session_user")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_identity_pair(session_user=other_user)
        force_deferred_constraints()


def test_refresh_family_cannot_outlive_its_auth_session() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        create_identity_pair(family_expiry_delta=timedelta(seconds=1))
        force_deferred_constraints()


@pytest.mark.parametrize(
    ("family_generation", "credential_generation", "credential_expiry_delta"),
    [
        (2, 1, timedelta()),
        (1, 1, timedelta(seconds=1)),
    ],
)
def test_active_credential_must_match_family_generation_and_lifetime(
    family_generation: int,
    credential_generation: int,
    credential_expiry_delta: timedelta,
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        create_identity_pair(
            family_generation=family_generation,
            credential_generation=credential_generation,
            credential_expiry_delta=credential_expiry_delta,
        )
        force_deferred_constraints()


def test_auth_session_and_family_must_be_a_symmetric_lifetime_pair() -> None:
    user = get_user_model().objects.create_user(username="missing_family_user")
    account = GameAccount.objects.create(
        user=user,
        instance_id=settings.CONTENT_INSTANCE_ID,
    )
    now = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        AuthSession.objects.create(
            user=user,
            game_account=account,
            device_id=uuid.uuid4().hex,
            issued_at=now,
            last_seen_at=now,
            absolute_expires_at=now + timedelta(days=30),
        )
        force_deferred_constraints()


def test_partial_unique_constraints_reject_second_active_recovery_and_refresh_credentials() -> None:
    registration = register(
        username="unique_identity",
        password="safe-example-passphrase-42",
    )
    authentication = login(
        username="unique_identity",
        password="safe-example-passphrase-42",
    )
    account = GameAccount.objects.get(pk=registration.game_account_id)
    family = RefreshTokenFamily.objects.get(
        auth_session_id=uuid.UUID(authentication.auth_session_id)
    )
    now = timezone.now()

    with pytest.raises(IntegrityError), transaction.atomic():
        RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=2,
            code_hash="not-plaintext",
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        RefreshTokenCredential.objects.create(
            family=family,
            generation=2,
            token_hash="2" * 64,
            jti_hash="3" * 64,
            issued_at=now,
            expires_at=family.absolute_expires_at,
        )


def test_terminal_identity_rows_cannot_be_reactivated_or_rebound() -> None:
    register(username="terminal_guard", password="safe-example-passphrase-42")
    authentication = login(
        username="terminal_guard",
        password="safe-example-passphrase-42",
    )
    session = AuthSession.objects.get(pk=authentication.auth_session_id)
    family = RefreshTokenFamily.objects.get(auth_session=session)
    credential = RefreshTokenCredential.objects.get(family=family)

    with transaction.atomic():
        AuthSession.objects.filter(pk=session.pk).update(
            state=AuthSession.State.REVOKED,
            revoked_at=timezone.now(),
        )
        RefreshTokenFamily.objects.filter(pk=family.pk).update(
            state=RefreshTokenFamily.State.REVOKED,
            revoked_at=timezone.now(),
        )
        RefreshTokenCredential.objects.filter(pk=credential.pk).update(
            state=RefreshTokenCredential.State.REVOKED,
        )

    with pytest.raises(DatabaseError):
        AuthSession.objects.filter(pk=session.pk).update(state=AuthSession.State.ACTIVE)
    with pytest.raises(DatabaseError):
        RefreshTokenFamily.objects.filter(pk=family.pk).update(
            auth_session_id=uuid.uuid4(),
        )
    with pytest.raises(DatabaseError):
        RefreshTokenCredential.objects.filter(pk=credential.pk).update(
            state=RefreshTokenCredential.State.ACTIVE,
        )
