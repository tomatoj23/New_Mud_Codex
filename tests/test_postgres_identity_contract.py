from __future__ import annotations

import base64
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
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from new_mud.apps.identity.models import (
    AuthSession,
    GameAccount,
    RecoveryCodeCredential,
    RefreshRequestTerminalRecord,
    RefreshTokenCredential,
    RefreshTokenFamily,
    VerificationChallenge,
    VerificationDeliveryOutbox,
    VerificationRateLimitBucket,
    VerificationRequestRecord,
    VerifiedContactMethod,
)
from new_mud.apps.identity.services import (
    AuthenticationFailed,
    RefreshFailed,
    RegistrationUnavailable,
    VerificationCodeInvalid,
    login,
    refresh,
    register,
)
from new_mud.apps.identity.verification_delivery import (
    DeliveryOutcome,
    ProviderAcceptedCrash,
    VerificationEmail,
    deliver_one_verification,
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


def request_registration_verification_from_thread(
    *,
    destination: str,
    idempotency_key: str,
    device_id: str,
) -> tuple[int, dict[str, object]]:
    close_old_connections()
    try:
        client = Client()
        client.cookies["new_mud_verification_device"] = device_id
        response = client.post(
            reverse("auth-registration-verification-request"),
            {"channel": "email", "destination": destination},
            content_type="application/json",
            secure=True,
            REMOTE_ADDR="192.0.2.10",
            headers={
                "origin": "https://testserver",
                "idempotency-key": idempotency_key,
            },
        )
        return response.status_code, response.json()
    finally:
        close_old_connections()


def register_verified(*, username: str, password: str):
    suffix = uuid.uuid4().hex[:12]
    destination = f"{username[:32]}-{suffix}@example.com"
    assert request_registration_verification_from_thread(
        destination=destination,
        idempotency_key=f"verified-{suffix}",
        device_id=f"verified-device-{suffix}",
    ) == (202, {"status": "accepted", "retry_after": 60})
    messages: list[VerificationEmail] = []

    class CaptureSender:
        def send(self, message: VerificationEmail) -> None:
            messages.append(message)

    assert (
        deliver_one_verification(worker_id=f"verified-worker-{suffix}", sender=CaptureSender())
        == DeliveryOutcome.DELIVERED
    )
    code = messages[0].body.split("注册验证码是：", maxsplit=1)[1].splitlines()[0]
    return register(
        username=username,
        password=password,
        verification={
            "channel": "email",
            "destination": destination,
            "code": code,
        },
    )


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
    register_verified(username="lifecycle_refresh", password="safe-example-passphrase-42")
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
    registration = register_verified(
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
    registration = register_verified(
        username="unique_identity",
        password="safe-example-passphrase-42",
    )
    authentication = login(
        username="unique_identity",
        password="safe-example-passphrase-42",
    )
    account = GameAccount.objects.get(pk=registration.game_account_id)
    RecoveryCodeCredential.objects.create(
        game_account=account,
        generation=1,
        code_hash="legacy-active-hash",
    )
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
    register_verified(username="terminal_guard", password="safe-example-passphrase-42")
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


def test_concurrent_replay_creates_one_registration_challenge_and_delivery() -> None:
    start = Event()

    def request() -> tuple[int, dict[str, object]]:
        assert start.wait(timeout=5)
        return request_registration_verification_from_thread(
            destination="concurrent-replay@example.com",
            idempotency_key="concurrent-replay-1",
            device_id="concurrent-replay-device",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request) for _ in range(2)]
        start.set()
        responses = [future.result(timeout=10) for future in futures]

    assert responses == [
        (202, {"status": "accepted", "retry_after": 60}),
        (202, {"status": "accepted", "retry_after": 60}),
    ]
    assert VerificationChallenge.objects.count() == 1
    assert VerificationDeliveryOutbox.objects.count() == 1
    assert VerificationRequestRecord.objects.count() == 1
    assert set(VerificationRateLimitBucket.objects.values_list("request_count", flat=True)) == {1}


def test_concurrent_registration_consumes_one_challenge_into_one_complete_identity() -> None:
    destination = "concurrent-register@example.com"
    assert request_registration_verification_from_thread(
        destination=destination,
        idempotency_key="concurrent-register-code",
        device_id="concurrent-register-device",
    ) == (202, {"status": "accepted", "retry_after": 60})
    sender = RecordingEmailSender()
    assert (
        deliver_one_verification(worker_id="concurrent-register-worker", sender=sender)
        == DeliveryOutcome.DELIVERED
    )
    code = sender.messages[0].body.split("注册验证码是：", maxsplit=1)[1].splitlines()[0]
    start = Event()

    def finish_registration(username: str) -> str:
        close_old_connections()
        try:
            assert start.wait(timeout=5)
            register(
                username=username,
                password="safe-example-passphrase-42",
                verification={
                    "channel": "email",
                    "destination": destination,
                    "code": code,
                },
            )
            return "created"
        except VerificationCodeInvalid:
            return "invalid"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(finish_registration, "concurrent_register_a"),
            executor.submit(finish_registration, "concurrent_register_b"),
        ]
        start.set()
        outcomes = [future.result(timeout=10) for future in futures]

    assert sorted(outcomes) == ["created", "invalid"]
    assert get_user_model().objects.count() == 1
    assert GameAccount.objects.count() == 1
    assert VerifiedContactMethod.objects.count() == 1
    assert RecoveryCodeCredential.objects.count() == 0
    assert AuthSession.objects.count() == 0
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.CONSUMED


def test_rotated_lookup_key_cannot_revive_a_superseded_registration_code() -> None:
    destination = "rotated-replacement@example.com"
    assert request_registration_verification_from_thread(
        destination=destination,
        idempotency_key="rotated-replacement-old",
        device_id="rotated-replacement-old-device",
    ) == (202, {"status": "accepted", "retry_after": 60})
    old_sender = RecordingEmailSender()
    assert (
        deliver_one_verification(worker_id="rotated-replacement-old-worker", sender=old_sender)
        == DeliveryOutcome.DELIVERED
    )
    old_code = old_sender.messages[0].body.split("注册验证码是：", maxsplit=1)[1].splitlines()[0]

    VerificationRateLimitBucket.objects.filter(scope="contact", window_seconds=60).update(
        window_started_at=timezone.now() - timedelta(seconds=61)
    )
    rotated_lookup_keys = {
        **settings.AUTH_CONTACT_LOOKUP_KEYS,
        "contact-lookup-v2": base64.urlsafe_b64encode(b"r" * 32).decode("ascii"),
    }
    with override_settings(
        AUTH_CONTACT_LOOKUP_KEYS=rotated_lookup_keys,
        AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID="contact-lookup-v2",
    ):
        assert request_registration_verification_from_thread(
            destination=destination,
            idempotency_key="rotated-replacement-new",
            device_id="rotated-replacement-new-device",
        ) == (202, {"status": "accepted", "retry_after": 60})
        new_sender = RecordingEmailSender()
        assert (
            deliver_one_verification(
                worker_id="rotated-replacement-new-worker",
                sender=new_sender,
            )
            == DeliveryOutcome.DELIVERED
        )

        for _ in range(6):
            with pytest.raises(VerificationCodeInvalid):
                register(
                    username="rotated_replacement",
                    password="safe-example-passphrase-42",
                    verification={
                        "channel": "email",
                        "destination": destination,
                        "code": old_code,
                    },
                )

    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    assert VerifiedContactMethod.objects.count() == 0
    assert sorted(VerificationChallenge.objects.values_list("state", flat=True)) == [
        VerificationChallenge.State.LOCKED,
        VerificationChallenge.State.SUPERSEDED,
    ]


def test_concurrent_registration_with_one_username_leaves_no_partial_loser() -> None:
    prepared: list[tuple[str, str]] = []
    for suffix in ("a", "b"):
        destination = f"concurrent-username-{suffix}@example.com"
        assert request_registration_verification_from_thread(
            destination=destination,
            idempotency_key=f"concurrent-username-{suffix}",
            device_id=f"concurrent-username-device-{suffix}",
        ) == (202, {"status": "accepted", "retry_after": 60})
        sender = RecordingEmailSender()
        assert (
            deliver_one_verification(
                worker_id=f"concurrent-username-worker-{suffix}", sender=sender
            )
            == DeliveryOutcome.DELIVERED
        )
        code = sender.messages[0].body.split("注册验证码是：", maxsplit=1)[1].splitlines()[0]
        prepared.append((destination, code))

    start = Event()

    def finish_registration(destination: str, code: str) -> str:
        close_old_connections()
        try:
            assert start.wait(timeout=5)
            register(
                username="concurrent_shared_username",
                password="safe-example-passphrase-42",
                verification={
                    "channel": "email",
                    "destination": destination,
                    "code": code,
                },
            )
            return "created"
        except RegistrationUnavailable:
            return "unavailable"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(finish_registration, *item) for item in prepared]
        start.set()
        outcomes = [future.result(timeout=10) for future in futures]

    assert sorted(outcomes) == ["created", "unavailable"]
    assert get_user_model().objects.count() == 1
    assert GameAccount.objects.count() == 1
    assert VerifiedContactMethod.objects.count() == 1
    assert sorted(VerificationChallenge.objects.values_list("state", flat=True)) == [
        VerificationChallenge.State.ACTIVE,
        VerificationChallenge.State.CONSUMED,
    ]


def test_registration_database_failure_rolls_back_identity_and_challenge_consumption() -> None:
    destination = "rollback-register@example.com"
    assert request_registration_verification_from_thread(
        destination=destination,
        idempotency_key="rollback-register-code",
        device_id="rollback-register-device",
    ) == (202, {"status": "accepted", "retry_after": 60})
    sender = RecordingEmailSender()
    assert (
        deliver_one_verification(worker_id="rollback-register-worker", sender=sender)
        == DeliveryOutcome.DELIVERED
    )
    code = sender.messages[0].body.split("注册验证码是：", maxsplit=1)[1].splitlines()[0]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE FUNCTION identity_test_fail_contact_insert()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'test contact insert failure' USING ERRCODE = '23514';
            END;
            $$
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER identity_test_fail_contact_insert_trigger
            BEFORE INSERT ON identity_verifiedcontactmethod
            FOR EACH ROW EXECUTE FUNCTION identity_test_fail_contact_insert()
            """
        )

    try:
        with pytest.raises(RegistrationUnavailable):
            register(
                username="rollback_register",
                password="safe-example-passphrase-42",
                verification={
                    "channel": "email",
                    "destination": destination,
                    "code": code,
                },
            )
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER IF EXISTS identity_test_fail_contact_insert_trigger "
                "ON identity_verifiedcontactmethod"
            )
            cursor.execute("DROP FUNCTION IF EXISTS identity_test_fail_contact_insert()")

    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    assert VerifiedContactMethod.objects.count() == 0
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.ACTIVE


def test_concurrent_keys_for_one_contact_allow_only_one_cooldown_winner() -> None:
    start = Event()

    def request(idempotency_key: str) -> tuple[int, dict[str, object]]:
        assert start.wait(timeout=5)
        return request_registration_verification_from_thread(
            destination="concurrent-cooldown@example.com",
            idempotency_key=idempotency_key,
            device_id=f"device-{idempotency_key}",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(request, "concurrent-cooldown-a"),
            executor.submit(request, "concurrent-cooldown-b"),
        ]
        start.set()
        responses = [future.result(timeout=10) for future in futures]

    assert sorted(status for status, _ in responses) == [202, 429]
    assert [payload for status, payload in responses if status == 202] == [
        {"status": "accepted", "retry_after": 60}
    ]
    limited = [payload for status, payload in responses if status == 429]
    assert len(limited) == 1
    assert limited[0]["error"] == {"code": "VERIFICATION_RATE_LIMITED"}
    retry_after = limited[0]["retry_after"]
    assert isinstance(retry_after, int)
    assert 1 <= retry_after <= 60
    assert VerificationChallenge.objects.count() == 1
    assert VerificationDeliveryOutbox.objects.count() == 1
    assert VerificationRequestRecord.objects.count() == 2


class BlockingEmailSender:
    def __init__(self, *, started: Event, release: Event) -> None:
        self.started = started
        self.release = release
        self.messages: list[VerificationEmail] = []

    def send(self, message: VerificationEmail) -> None:
        self.messages.append(message)
        self.started.set()
        assert self.release.wait(timeout=5)


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[VerificationEmail] = []

    def send(self, message: VerificationEmail) -> None:
        self.messages.append(message)


def test_two_workers_cannot_send_the_same_unexpired_delivery_lease() -> None:
    assert request_registration_verification_from_thread(
        destination="concurrent-worker@example.com",
        idempotency_key="concurrent-worker-1",
        device_id="concurrent-worker-device",
    ) == (202, {"status": "accepted", "retry_after": 60})
    provider_started = Event()
    release_provider = Event()
    first_sender = BlockingEmailSender(started=provider_started, release=release_provider)
    second_sender = RecordingEmailSender()

    def deliver_first() -> DeliveryOutcome:
        close_old_connections()
        try:
            return deliver_one_verification(worker_id="worker-a", sender=first_sender)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(deliver_first)
        assert provider_started.wait(timeout=5)
        try:
            second = deliver_one_verification(worker_id="worker-b", sender=second_sender)
        finally:
            release_provider.set()
        assert first.result(timeout=5) == DeliveryOutcome.DELIVERED

    assert second == DeliveryOutcome.NO_WORK
    assert len(first_sender.messages) == 1
    assert second_sender.messages == []
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.ACTIVE
    assert (
        VerificationDeliveryOutbox.objects.get().state == VerificationDeliveryOutbox.State.DELIVERED
    )


def test_expired_delivery_lease_is_reclaimed_with_the_same_payload() -> None:
    assert request_registration_verification_from_thread(
        destination="lease-reclaim@example.com",
        idempotency_key="lease-reclaim-1",
        device_id="lease-reclaim-device",
    ) == (202, {"status": "accepted", "retry_after": 60})
    sender = RecordingEmailSender()

    with pytest.raises(ProviderAcceptedCrash):
        deliver_one_verification(
            worker_id="crashed-worker",
            sender=sender,
            crash_after_provider_accept=True,
        )
    leased = VerificationDeliveryOutbox.objects.get()
    assert leased.state == VerificationDeliveryOutbox.State.LEASED
    assert leased.payload_ciphertext is not None
    VerificationDeliveryOutbox.objects.filter(pk=leased.pk).update(lease_expires_at=timezone.now())

    outcome = deliver_one_verification(worker_id="reclaiming-worker", sender=sender)

    assert outcome == DeliveryOutcome.DELIVERED
    assert len(sender.messages) == 2
    assert sender.messages[0] == sender.messages[1]
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.ACTIVE
    delivered = VerificationDeliveryOutbox.objects.get()
    assert delivered.state == VerificationDeliveryOutbox.State.DELIVERED
    assert delivered.payload_ciphertext is None


def test_limiter_database_failure_is_global_without_disabling_password_login() -> None:
    register_verified(username="limiter_outage", password="safe-example-passphrase-42")
    initial_limit_buckets = VerificationRateLimitBucket.objects.count()
    initial_request_records = VerificationRequestRecord.objects.count()
    initial_challenges = VerificationChallenge.objects.count()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE FUNCTION identity_test_fail_verification_limit_write()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'test limiter unavailable' USING ERRCODE = '58000';
            END;
            $$
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER identity_test_fail_verification_limit_write_trigger
            BEFORE INSERT OR UPDATE ON identity_verificationratelimitbucket
            FOR EACH ROW EXECUTE FUNCTION identity_test_fail_verification_limit_write()
            """
        )

    try:
        verification = request_registration_verification_from_thread(
            destination="limiter-outage@example.com",
            idempotency_key="limiter-outage-1",
            device_id="limiter-outage-device",
        )
        client = Client()
        login_response = client.post(
            reverse("auth-login"),
            {"username": "limiter_outage", "password": "safe-example-passphrase-42"},
            content_type="application/json",
            secure=True,
            REMOTE_ADDR="192.0.2.10",
            headers={"origin": "https://testserver"},
        )
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DROP TRIGGER IF EXISTS identity_test_fail_verification_limit_write_trigger
                    ON identity_verificationratelimitbucket
                """
            )
            cursor.execute("DROP FUNCTION IF EXISTS identity_test_fail_verification_limit_write()")

    assert verification == (503, {"error": {"code": "VERIFICATION_SERVICE_UNAVAILABLE"}})
    assert VerificationRateLimitBucket.objects.count() == initial_limit_buckets
    assert VerificationRequestRecord.objects.count() == initial_request_records
    assert VerificationChallenge.objects.count() == initial_challenges
    assert login_response.status_code == 200
