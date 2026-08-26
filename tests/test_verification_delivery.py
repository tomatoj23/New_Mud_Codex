from __future__ import annotations

import base64
import io
import json
import smtplib
from collections.abc import Mapping
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.checks import Tags, run_checks
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from new_mud.apps.identity.models import (
    VerificationChallenge,
    VerificationDeliveryOutbox,
    VerificationRateLimitBucket,
    VerificationRequestRecord,
    VerifiedContactMethod,
)
from new_mud.apps.identity.verification import ContactInvalid, normalize_email
from new_mud.apps.identity.verification_config import verification_keyrings
from new_mud.apps.identity.verification_crypto import (
    EncryptedValue,
    KeyRing,
    KeyUnavailable,
    decrypt_value,
    encrypt_value,
    keyed_digest,
    keyed_digest_candidates,
    verification_code_digest,
)
from new_mud.apps.identity.verification_delivery import (
    DeliveryOutcome,
    DeliveryPermanentError,
    ProviderAcceptedCrash,
    VerificationEmail,
    deliver_one_verification,
)

pytestmark = pytest.mark.django_db(transaction=True)


def verification_post(
    client,
    payload: Mapping[str, object],
    *,
    idempotency_key: str,
    remote_addr: str = "192.0.2.10",
    forwarded_for: str | None = None,
):
    headers = {
        "origin": "https://testserver",
        "idempotency-key": idempotency_key,
    }
    if forwarded_for is not None:
        headers["x-forwarded-for"] = forwarded_for
    return client.post(
        reverse("auth-registration-verification-request"),
        payload,
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=remote_addr,
        headers=headers,
    )


def test_email_normalization_supports_idna_without_provider_specific_folding() -> None:
    normalized = normalize_email("Player.Name+news@例子.测试")

    assert normalized.delivery == "Player.Name+news@xn--fsqu00a.xn--0zwm56d"
    assert normalized.comparison == "player.name+news@xn--fsqu00a.xn--0zwm56d"
    assert normalize_email("PLAYER.NAME+NEWS@例子.测试").comparison == normalized.comparison
    assert normalize_email("playername+news@例子.测试").comparison != normalized.comparison
    assert normalize_email("Player.Name@例子.测试").comparison != normalized.comparison


@pytest.mark.parametrize(
    "destination",
    [
        "用户@example.com",
        ".player@example.com",
        "player..name@example.com",
        "player@-example.com",
        "player@example",
        " player@example.com",
    ],
)
def test_email_normalization_rejects_unsupported_or_malformed_mailboxes(
    destination: str,
) -> None:
    with pytest.raises(ContactInvalid):
        normalize_email(destination)


def key_material(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def test_encryption_writes_current_key_and_reads_rotated_ciphertext() -> None:
    old_only = KeyRing(current_key_id="old", encoded_keys={"old": key_material(1)})
    old_ciphertext = encrypt_value("Player@example.com", keyring=old_only, context="contact:email")
    rotated = KeyRing(
        current_key_id="current",
        encoded_keys={"old": key_material(1), "current": key_material(2)},
    )

    current_ciphertext = encrypt_value(
        "Player@example.com",
        keyring=rotated,
        context="contact:email",
    )

    assert old_ciphertext.key_id == "old"
    assert current_ciphertext.key_id == "current"
    assert old_ciphertext.ciphertext != "Player@example.com"
    assert current_ciphertext.ciphertext != old_ciphertext.ciphertext
    assert (
        decrypt_value(old_ciphertext, keyring=rotated, context="contact:email")
        == "Player@example.com"
    )
    with pytest.raises(KeyUnavailable):
        decrypt_value(
            old_ciphertext,
            keyring=KeyRing(
                current_key_id="current",
                encoded_keys={"current": key_material(2)},
            ),
            context="contact:email",
        )


def test_lookup_and_code_digests_use_independent_contexts() -> None:
    lookup = KeyRing(current_key_id="lookup", encoded_keys={"lookup": key_material(3)})
    pepper = KeyRing(current_key_id="pepper", encoded_keys={"pepper": key_material(4)})
    destination = "player@example.com"

    lookup_digest = keyed_digest(destination, keyring=lookup, context="contact:email")
    registration_digest = verification_code_digest(
        "123456",
        keyring=pepper,
        purpose="registration",
        channel="email",
        destination_lookup_digest=lookup_digest.digest,
        user_id=None,
    )
    assert lookup_digest.key_id == "lookup"
    assert registration_digest.key_id == "pepper"
    assert lookup_digest.digest != registration_digest.digest
    assert (
        registration_digest.digest
        != verification_code_digest(
            "123456",
            keyring=pepper,
            purpose="password_reset",
            channel="email",
            destination_lookup_digest=lookup_digest.digest,
            user_id="42",
        ).digest
    )
    assert (
        registration_digest.digest
        != verification_code_digest(
            "123456",
            keyring=pepper,
            purpose="registration",
            channel="sms",
            destination_lookup_digest=lookup_digest.digest,
            user_id=None,
        ).digest
    )


def test_rotated_digest_keyrings_write_current_and_read_old_keys() -> None:
    old_only = KeyRing(current_key_id="old", encoded_keys={"old": key_material(5)})
    old_lookup = keyed_digest("player@example.com", keyring=old_only, context="contact:email")
    old_code = verification_code_digest(
        "123456",
        keyring=old_only,
        purpose="registration",
        channel="email",
        destination_lookup_digest=old_lookup.digest,
        user_id=None,
    )
    rotated = KeyRing(
        current_key_id="current",
        encoded_keys={"old": key_material(5), "current": key_material(6)},
    )

    current_lookup = keyed_digest(
        "player@example.com",
        keyring=rotated,
        context="contact:email",
    )
    restored_lookup = keyed_digest(
        "player@example.com",
        keyring=rotated,
        context="contact:email",
        key_id="old",
    )
    restored_code = verification_code_digest(
        "123456",
        keyring=rotated,
        purpose="registration",
        channel="email",
        destination_lookup_digest=old_lookup.digest,
        user_id=None,
        key_id="old",
    )
    candidates = keyed_digest_candidates(
        "player@example.com",
        keyring=rotated,
        context="contact:email",
    )

    assert current_lookup.key_id == "current"
    assert restored_lookup == old_lookup
    assert restored_code == old_code
    assert {candidate.key_id for candidate in candidates} == {"current", "old"}
    assert old_lookup in candidates


def test_registration_verification_request_persists_only_protected_delivery_state(client) -> None:
    destination = "Player.Name+news@例子.测试"

    response = verification_post(
        client,
        {"channel": "email", "destination": destination},
        idempotency_key="registration-email-1",
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "retry_after": 60}
    assert response.headers["Cache-Control"] == "no-store"
    assert set(response.json()) == {"status", "retry_after"}
    assert mail.outbox == []
    device_cookie = response.cookies["new_mud_verification_device"]
    assert device_cookie["path"] == "/api/v1/auth/"
    assert device_cookie["secure"] is True
    assert device_cookie["httponly"] is True
    assert device_cookie["samesite"] == "Strict"
    assert not device_cookie["domain"]

    assert get_user_model().objects.count() == 0
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get(challenge=challenge)
    terminal = VerificationRequestRecord.objects.get()
    assert challenge.purpose == VerificationChallenge.Purpose.REGISTRATION
    assert challenge.channel == VerificationChallenge.Channel.EMAIL
    assert challenge.user_id is None
    assert challenge.state == VerificationChallenge.State.PENDING_DELIVERY
    assert challenge.code_digest and challenge.pepper_key_id == "verification-code-v1"
    assert outbox.state == VerificationDeliveryOutbox.State.PENDING
    assert outbox.payload_ciphertext and outbox.payload_key_id == "delivery-payload-v1"
    assert terminal.response_status == 202
    assert terminal.response_json == {"status": "accepted", "retry_after": 60}
    assert VerificationRateLimitBucket.objects.count() == 7

    persisted = json.dumps(
        {
            "challenge": list(VerificationChallenge.objects.values())[0],
            "outbox": list(VerificationDeliveryOutbox.objects.values())[0],
            "terminal": list(VerificationRequestRecord.objects.values())[0],
        },
        default=str,
    )
    assert destination not in persisted
    assert "Player.Name+news@xn--fsqu00a.xn--0zwm56d" not in persisted


def test_rate_limited_request_replays_its_terminal_without_consuming_limits_twice(client) -> None:
    payload = {"channel": "email", "destination": "player@example.com"}
    assert verification_post(client, payload, idempotency_key="first-request").status_code == 202

    limited = verification_post(client, payload, idempotency_key="cooldown-request")
    bucket_counts = list(
        VerificationRateLimitBucket.objects.order_by("scope", "window_seconds").values_list(
            "scope", "window_seconds", "request_count"
        )
    )
    replay = verification_post(client, payload, idempotency_key="cooldown-request")

    assert limited.status_code == replay.status_code == 429
    assert limited.json() == replay.json()
    assert limited.json()["error"] == {"code": "VERIFICATION_RATE_LIMITED"}
    assert 1 <= limited.json()["retry_after"] <= 60
    assert VerificationRequestRecord.objects.count() == 2
    assert VerificationChallenge.objects.count() == 1
    assert VerificationDeliveryOutbox.objects.count() == 1
    assert (
        list(
            VerificationRateLimitBucket.objects.order_by("scope", "window_seconds").values_list(
                "scope", "window_seconds", "request_count"
            )
        )
        == bucket_counts
    )
    assert {count for _, _, count in bucket_counts} == {2}


def test_worker_activates_challenge_only_after_provider_acceptance_and_erases_payload(
    client,
) -> None:
    response = verification_post(
        client,
        {"channel": "email", "destination": "Player@例子.测试"},
        idempotency_key="deliver-registration-1",
    )
    assert response.status_code == 202
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get()
    assert challenge.activated_at is None
    assert challenge.expires_at is None
    assert outbox.payload_ciphertext is not None

    outcome = deliver_one_verification(worker_id="test-worker")

    assert outcome == DeliveryOutcome.DELIVERED
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["Player@xn--fsqu00a.xn--0zwm56d"]
    assert message.subject == "[New_Mud] 注册验证码"
    assert "10 分钟" in message.body
    assert "工作人员不会索要验证码" in message.body
    challenge.refresh_from_db()
    outbox.refresh_from_db()
    code = message.body.split("：", 1)[1][:6]
    rings = verification_keyrings()
    expected_digest = verification_code_digest(
        code,
        keyring=rings.code_pepper,
        purpose=challenge.purpose,
        channel=challenge.channel,
        destination_lookup_digest=challenge.destination_lookup_digest,
        user_id=None,
    )
    assert challenge.code_digest == expected_digest.digest
    assert challenge.state == VerificationChallenge.State.ACTIVE
    assert challenge.activated_at is not None
    assert challenge.expires_at is not None
    assert int((challenge.expires_at - challenge.activated_at).total_seconds()) == 600
    assert outbox.state == VerificationDeliveryOutbox.State.DELIVERED
    assert outbox.payload_ciphertext is None
    assert outbox.delivered_at is not None
    assert outbox.terminal_at is not None
    assert outbox.lease_owner is None
    assert outbox.lease_expires_at is None
    assert code not in json.dumps(
        {
            "challenge": list(VerificationChallenge.objects.values())[0],
            "outbox": list(VerificationDeliveryOutbox.objects.values())[0],
        },
        default=str,
    )


def test_same_idempotency_key_replays_and_conflicting_request_is_rejected(client) -> None:
    first = verification_post(
        client,
        {"channel": "email", "destination": "Player@example.com"},
        idempotency_key="registration-replay-1",
    )
    bucket_counts = list(
        VerificationRateLimitBucket.objects.order_by("bucket_id").values_list(
            "bucket_id", "request_count"
        )
    )

    replay = verification_post(
        client,
        {"channel": "email", "destination": "PLAYER@EXAMPLE.COM"},
        idempotency_key="registration-replay-1",
    )
    conflict = verification_post(
        client,
        {"channel": "email", "destination": "other@example.com"},
        idempotency_key="registration-replay-1",
    )

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json() == {"status": "accepted", "retry_after": 60}
    assert conflict.status_code == 409
    assert conflict.json() == {"error": {"code": "CONTACT_INVALID"}}
    assert VerificationChallenge.objects.count() == 1
    assert VerificationDeliveryOutbox.objects.count() == 1
    assert VerificationRequestRecord.objects.count() == 1
    assert (
        list(
            VerificationRateLimitBucket.objects.order_by("bucket_id").values_list(
                "bucket_id", "request_count"
            )
        )
        == bucket_counts
    )


@pytest.mark.parametrize(
    ("payload", "idempotency_key", "error_code"),
    [
        (
            {"channel": "sms", "destination": "+8613800000000"},
            "sms-1",
            "CONTACT_CHANNEL_UNAVAILABLE",
        ),
        ({"channel": "email", "destination": "用户@example.com"}, "utf8-1", "CONTACT_INVALID"),
        ({"channel": "email", "destination": "player@example.com"}, "", "CONTACT_INVALID"),
    ],
)
def test_registration_verification_rejects_unsupported_request_shapes_without_state(
    client,
    payload: dict[str, object],
    idempotency_key: str,
    error_code: str,
) -> None:
    response = verification_post(client, payload, idempotency_key=idempotency_key)

    assert response.status_code == 400
    assert response.json() == {"error": {"code": error_code}}
    assert response.headers["Cache-Control"] == "no-store"
    assert VerificationChallenge.objects.count() == 0
    assert VerificationDeliveryOutbox.objects.count() == 0
    assert VerificationRequestRecord.objects.count() == 0
    assert VerificationRateLimitBucket.objects.count() == 0


@pytest.mark.parametrize(
    ("failure_name", "failure_settings"),
    [
        ("provider_unready", {"AUTH_VERIFICATION_PROVIDER_READY": False}),
        ("worker_unready", {"AUTH_VERIFICATION_WORKER_READY": False}),
        ("missing_key", {"AUTH_CONTACT_LOOKUP_KEYS": {}}),
        (
            "duplicate_key",
            {
                "AUTH_CONTACT_LOOKUP_KEYS": {
                    "contact-lookup-v1": key_material(ord("c")),
                }
            },
        ),
        (
            "token_key_reused",
            {"AUTH_TOKEN_SIGNING_KEY": key_material(ord("c"))},
        ),
        (
            "equivalent_key_material_reused",
            {
                "AUTH_CONTACT_ENCRYPTION_KEYS": {
                    "contact-encryption-v1": base64.urlsafe_b64encode(bytes([251]) * 32).decode(
                        "ascii"
                    )
                },
                "AUTH_CONTACT_LOOKUP_KEYS": {
                    "contact-lookup-v1": base64.b64encode(bytes([251]) * 32).decode("ascii")
                },
            },
        ),
    ],
)
def test_verification_dependency_failure_is_global_while_password_login_remains_available(
    client,
    failure_name: str,
    failure_settings: dict[str, object],
) -> None:
    registration = client.post(
        reverse("auth-register"),
        {"username": failure_name, "password": "safe-example-passphrase-42"},
        content_type="application/json",
        secure=True,
        headers={"origin": "https://testserver"},
    )
    assert registration.status_code == 201

    with override_settings(**failure_settings):
        verification = verification_post(
            client,
            {"channel": "email", "destination": "player@example.com"},
            idempotency_key=f"{failure_name}-1",
        )
        login = client.post(
            reverse("auth-login"),
            {"username": failure_name, "password": "safe-example-passphrase-42"},
            content_type="application/json",
            secure=True,
            headers={"origin": "https://testserver"},
        )

    assert verification.status_code == 503
    assert verification.json() == {"error": {"code": "VERIFICATION_SERVICE_UNAVAILABLE"}}
    assert VerificationChallenge.objects.count() == 0
    assert login.status_code == 200
    assert get_user_model().objects.get(username=failure_name).email == ""


def test_verified_contact_state_requires_matching_lifecycle_time() -> None:
    user = get_user_model().objects.create_user(username="contact_state")
    rings = verification_keyrings()
    normalized = normalize_email("contact@example.com")
    encrypted = encrypt_value(
        normalized.delivery,
        keyring=rings.contact_encryption,
        context="contact:email",
    )
    lookup = keyed_digest(
        normalized.comparison,
        keyring=rings.contact_lookup,
        context="contact:email",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        VerifiedContactMethod.objects.create(
            user=user,
            channel=VerifiedContactMethod.Channel.EMAIL,
            state=VerifiedContactMethod.State.UNREACHABLE,
            destination_ciphertext=encrypted.ciphertext,
            encryption_key_id=encrypted.key_id,
            lookup_digest=lookup.digest,
            lookup_key_id=lookup.key_id,
            verified_at=timezone.now(),
        )


def test_terminal_challenge_and_outbox_require_terminal_times() -> None:
    now = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        VerificationChallenge.objects.create(
            purpose=VerificationChallenge.Purpose.REGISTRATION,
            channel=VerificationChallenge.Channel.EMAIL,
            destination_lookup_digest="a" * 64,
            destination_lookup_key_id="lookup-v1",
            code_digest="b" * 64,
            pepper_key_id="pepper-v1",
            state=VerificationChallenge.State.CONSUMED,
            issued_at=now,
        )

    challenge = VerificationChallenge.objects.create(
        purpose=VerificationChallenge.Purpose.REGISTRATION,
        channel=VerificationChallenge.Channel.EMAIL,
        destination_lookup_digest="c" * 64,
        destination_lookup_key_id="lookup-v1",
        code_digest="d" * 64,
        pepper_key_id="pepper-v1",
        issued_at=now,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        VerificationDeliveryOutbox.objects.create(
            challenge=challenge,
            template_key="registration_verification",
            payload_ciphertext=None,
            payload_key_id="payload-v1",
            state=VerificationDeliveryOutbox.State.DELIVERED,
            next_attempt_at=now + timedelta(seconds=1),
        )


class RecordingSender:
    def __init__(self) -> None:
        self.messages: list[VerificationEmail] = []

    def send(self, message: VerificationEmail) -> None:
        self.messages.append(message)


class PermanentlyFailingSender:
    def send(self, message: VerificationEmail) -> None:
        raise DeliveryPermanentError


def expire_contact_cooldown() -> None:
    VerificationRateLimitBucket.objects.filter(scope="contact", window_seconds=60).update(
        window_started_at=timezone.now() - timedelta(seconds=61)
    )


def test_exhausted_accepted_then_crashed_delivery_is_terminalized_and_erased(client) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": "crash@example.com"},
            idempotency_key="accepted-crash-1",
        ).status_code
        == 202
    )
    sender = RecordingSender()

    with override_settings(AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS=1):
        with pytest.raises(ProviderAcceptedCrash):
            deliver_one_verification(
                worker_id="crashing-worker",
                sender=sender,
                crash_after_provider_accept=True,
            )
        VerificationDeliveryOutbox.objects.update(lease_expires_at=timezone.now())

        outcome = deliver_one_verification(worker_id="recovery-worker", sender=sender)

    assert outcome == DeliveryOutcome.DELIVERY_FAILED
    assert len(sender.messages) == 1
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get()
    assert challenge.state == VerificationChallenge.State.DELIVERY_FAILED
    assert challenge.activated_at is None
    assert challenge.terminal_at is not None
    assert outbox.state == VerificationDeliveryOutbox.State.DELIVERY_FAILED
    assert outbox.payload_ciphertext is None
    assert outbox.terminal_at is not None
    assert outbox.lease_owner is None
    assert outbox.lease_expires_at is None


def test_email_adapter_converts_network_failure_into_bounded_retry(client, monkeypatch) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": "retry@example.com"},
            idempotency_key="provider-retry-1",
        ).status_code
        == 202
    )

    def raise_network_error(*args, **kwargs):
        raise OSError("provider unavailable")

    monkeypatch.setattr(EmailMessage, "send", raise_network_error)

    outcome = deliver_one_verification(worker_id="retry-worker")

    assert outcome == DeliveryOutcome.RETRY_SCHEDULED
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get()
    assert challenge.state == VerificationChallenge.State.PENDING_DELIVERY
    assert challenge.activated_at is None
    assert outbox.state == VerificationDeliveryOutbox.State.PENDING
    assert outbox.payload_ciphertext is not None
    assert outbox.attempt_count == 1
    assert outbox.provider_category == "transient_failure"
    assert outbox.lease_owner is None
    assert outbox.lease_expires_at is None


@pytest.mark.parametrize(
    ("smtp_code", "expected_outcome", "expected_state"),
    [
        (421, DeliveryOutcome.RETRY_SCHEDULED, VerificationDeliveryOutbox.State.PENDING),
        (550, DeliveryOutcome.DELIVERY_FAILED, VerificationDeliveryOutbox.State.DELIVERY_FAILED),
    ],
)
def test_email_adapter_classifies_transient_and_permanent_smtp_failures(
    client,
    monkeypatch,
    smtp_code: int,
    expected_outcome: DeliveryOutcome,
    expected_state: str,
) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": f"smtp-{smtp_code}@example.com"},
            idempotency_key=f"smtp-classification-{smtp_code}",
        ).status_code
        == 202
    )

    def raise_smtp_error(*args, **kwargs):
        raise smtplib.SMTPResponseException(smtp_code, b"provider response")

    monkeypatch.setattr(EmailMessage, "send", raise_smtp_error)

    outcome = deliver_one_verification(worker_id=f"smtp-worker-{smtp_code}")

    assert outcome == expected_outcome
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get()
    assert outbox.state == expected_state
    if smtp_code >= 500:
        assert challenge.state == VerificationChallenge.State.DELIVERY_FAILED
        assert outbox.payload_ciphertext is None
    else:
        assert challenge.state == VerificationChallenge.State.PENDING_DELIVERY
        assert outbox.payload_ciphertext is not None


def test_failed_replacement_preserves_old_active_until_new_delivery_succeeds(client) -> None:
    destination = {"channel": "email", "destination": "replacement@example.com"}
    assert (
        verification_post(client, destination, idempotency_key="replacement-1").status_code == 202
    )
    assert deliver_one_verification(worker_id="first-worker") == DeliveryOutcome.DELIVERED
    first = VerificationChallenge.objects.get(state=VerificationChallenge.State.ACTIVE)

    expire_contact_cooldown()
    assert (
        verification_post(client, destination, idempotency_key="replacement-2").status_code == 202
    )
    assert (
        deliver_one_verification(worker_id="failed-worker", sender=PermanentlyFailingSender())
        == DeliveryOutcome.DELIVERY_FAILED
    )

    first.refresh_from_db()
    failed = VerificationChallenge.objects.get(state=VerificationChallenge.State.DELIVERY_FAILED)
    assert first.state == VerificationChallenge.State.ACTIVE
    assert failed.pk != first.pk
    assert (
        VerificationChallenge.objects.filter(state=VerificationChallenge.State.ACTIVE).count() == 1
    )

    expire_contact_cooldown()
    assert (
        verification_post(client, destination, idempotency_key="replacement-3").status_code == 202
    )
    assert deliver_one_verification(worker_id="replacement-worker") == DeliveryOutcome.DELIVERED

    first.refresh_from_db()
    replacement = VerificationChallenge.objects.get(state=VerificationChallenge.State.ACTIVE)
    assert first.state == VerificationChallenge.State.SUPERSEDED
    assert first.superseded_at is not None
    assert first.terminal_at is not None
    assert replacement.pk not in {first.pk, failed.pk}
    assert (
        VerificationChallenge.objects.filter(state=VerificationChallenge.State.ACTIVE).count() == 1
    )


def test_provider_accepted_crash_retries_exactly_the_same_code(client) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": "duplicate@example.com"},
            idempotency_key="duplicate-code-1",
        ).status_code
        == 202
    )
    sender = RecordingSender()
    with pytest.raises(ProviderAcceptedCrash):
        deliver_one_verification(
            worker_id="first-worker",
            sender=sender,
            crash_after_provider_accept=True,
        )
    VerificationDeliveryOutbox.objects.update(lease_expires_at=timezone.now())

    outcome = deliver_one_verification(worker_id="recovery-worker", sender=sender)

    assert outcome == DeliveryOutcome.DELIVERED
    assert len(sender.messages) == 2
    assert sender.messages[0] == sender.messages[1]
    assert (
        VerificationChallenge.objects.filter(state=VerificationChallenge.State.ACTIVE).count() == 1
    )
    assert VerificationDeliveryOutbox.objects.get().payload_ciphertext is None


def test_delivered_verification_identity_and_terminal_rows_are_immutable(client) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": "immutable@example.com"},
            idempotency_key="immutable-delivery-1",
        ).status_code
        == 202
    )
    assert deliver_one_verification(worker_id="immutable-worker") == DeliveryOutcome.DELIVERED
    challenge = VerificationChallenge.objects.get()
    outbox = VerificationDeliveryOutbox.objects.get()
    terminal = VerificationRequestRecord.objects.get()
    user = get_user_model().objects.create_user(username="illegal_rebind")

    with pytest.raises(DatabaseError), transaction.atomic():
        VerificationChallenge.objects.filter(pk=challenge.pk).update(
            purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
            user=user,
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        VerificationDeliveryOutbox.objects.filter(pk=outbox.pk).update(
            state=VerificationDeliveryOutbox.State.PENDING,
            payload_ciphertext="restored-secret",
            delivered_at=None,
            terminal_at=None,
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        VerificationRequestRecord.objects.filter(pk=terminal.pk).update(
            response_json={"status": "changed"}
        )


def test_delivery_worker_management_command_processes_pending_task(client) -> None:
    assert (
        verification_post(
            client,
            {"channel": "email", "destination": "command@example.com"},
            idempotency_key="command-delivery-1",
        ).status_code
        == 202
    )
    output = io.StringIO()

    call_command(
        "process_verification_deliveries",
        "--once",
        stdout=output,
    )

    assert output.getvalue() == "processed=1 delivered=1 failed=0 retried=0\n"
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.ACTIVE
    assert (
        VerificationDeliveryOutbox.objects.get().state == VerificationDeliveryOutbox.State.DELIVERED
    )


def test_startup_check_rejects_enabled_verification_with_missing_keys() -> None:
    with override_settings(AUTH_CONTACT_LOOKUP_KEYS={}):
        errors = run_checks(tags=[Tags.security])

    verification_errors = [
        error for error in errors if error.id is not None and error.id.startswith("identity.E")
    ]
    assert [error.id for error in verification_errors] == ["identity.E001"]
    assert "secret" not in str(verification_errors[0]).lower()


def test_startup_check_rejects_locmem_provider_outside_explicit_test_mode() -> None:
    with override_settings(AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND=False):
        errors = run_checks(tags=[Tags.security])

    verification_errors = [
        error for error in errors if error.id is not None and error.id.startswith("identity.E")
    ]
    assert [error.id for error in verification_errors] == ["identity.E002"]


def test_persistent_device_limit_survives_a_new_client_process(client) -> None:
    for number in range(10):
        response = verification_post(
            client,
            {"channel": "email", "destination": f"device-{number}@example.com"},
            idempotency_key=f"device-limit-{number}",
        )
        assert response.status_code == 202

    device_id = client.cookies["new_mud_verification_device"].value
    restarted_client = Client()
    restarted_client.cookies["new_mud_verification_device"] = device_id

    limited = verification_post(
        restarted_client,
        {"channel": "email", "destination": "device-10@example.com"},
        idempotency_key="device-limit-10",
    )

    assert limited.status_code == 429
    assert limited.json()["error"] == {"code": "VERIFICATION_RATE_LIMITED"}
    assert list(
        VerificationRateLimitBucket.objects.filter(scope="device")
        .order_by("window_seconds")
        .values_list("window_seconds", "request_count")
    ) == [(900, 11), (86400, 11)]
    assert VerificationChallenge.objects.count() == 10


def test_persistent_ip_limit_combines_distinct_contacts_and_devices() -> None:
    responses = []
    for number in range(21):
        isolated_client = Client()
        responses.append(
            verification_post(
                isolated_client,
                {"channel": "email", "destination": f"ip-{number}@example.com"},
                idempotency_key=f"ip-limit-{number}",
            )
        )

    assert [response.status_code for response in responses[:20]] == [202] * 20
    assert responses[20].status_code == 429
    assert list(
        VerificationRateLimitBucket.objects.filter(scope="ip")
        .order_by("window_seconds")
        .values_list("window_seconds", "request_count")
    ) == [(900, 21), (86400, 21)]
    assert VerificationChallenge.objects.count() == 20


def test_forwarded_ip_is_used_only_for_an_explicitly_trusted_proxy(client) -> None:
    for number, forwarded in enumerate(("198.51.100.1", "198.51.100.2")):
        assert (
            verification_post(
                client,
                {"channel": "email", "destination": f"untrusted-{number}@example.com"},
                idempotency_key=f"untrusted-proxy-{number}",
                forwarded_for=forwarded,
            ).status_code
            == 202
        )
    assert (
        VerificationRateLimitBucket.objects.filter(scope="ip")
        .values("subject_digest")
        .distinct()
        .count()
        == 1
    )

    with override_settings(AUTH_TRUSTED_PROXY_NETWORKS=["192.0.2.0/24"]):
        for number, forwarded in enumerate(("198.51.100.1", "198.51.100.2")):
            assert (
                verification_post(
                    client,
                    {"channel": "email", "destination": f"trusted-{number}@example.com"},
                    idempotency_key=f"trusted-proxy-{number}",
                    forwarded_for=forwarded,
                ).status_code
                == 202
            )
    assert (
        VerificationRateLimitBucket.objects.filter(scope="ip")
        .values("subject_digest")
        .distinct()
        .count()
        == 3
    )


def test_verified_contact_ciphertext_and_partial_uniqueness_release_on_revocation() -> None:
    rings = verification_keyrings()
    normalized = normalize_email("Owner@例子.测试")
    encrypted = encrypt_value(
        normalized.delivery,
        keyring=rings.contact_encryption,
        context="contact:email",
    )
    lookup = keyed_digest(
        normalized.comparison,
        keyring=rings.contact_lookup,
        context="contact:email",
    )
    owner = get_user_model().objects.create_user(username="contact_owner")
    other = get_user_model().objects.create_user(username="contact_other")
    now = timezone.now()
    contact = VerifiedContactMethod.objects.create(
        user=owner,
        channel=VerifiedContactMethod.Channel.EMAIL,
        destination_ciphertext=encrypted.ciphertext,
        encryption_key_id=encrypted.key_id,
        lookup_digest=lookup.digest,
        lookup_key_id=lookup.key_id,
        verified_at=now,
    )

    assert contact.destination_ciphertext != normalized.delivery
    assert (
        decrypt_value(
            EncryptedValue(contact.destination_ciphertext, contact.encryption_key_id),
            keyring=rings.contact_encryption,
            context="contact:email",
        )
        == normalized.delivery
    )
    assert owner.email == ""
    second_address = normalize_email("second-address@example.com")
    second_encrypted = encrypt_value(
        second_address.delivery,
        keyring=rings.contact_encryption,
        context="contact:email",
    )
    second_lookup = keyed_digest(
        second_address.comparison,
        keyring=rings.contact_lookup,
        context="contact:email",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        VerifiedContactMethod.objects.create(
            user=owner,
            channel=VerifiedContactMethod.Channel.EMAIL,
            destination_ciphertext=second_encrypted.ciphertext,
            encryption_key_id=second_encrypted.key_id,
            lookup_digest=second_lookup.digest,
            lookup_key_id=second_lookup.key_id,
            verified_at=now,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        VerifiedContactMethod.objects.create(
            user=other,
            channel=VerifiedContactMethod.Channel.EMAIL,
            state=VerifiedContactMethod.State.UNREACHABLE,
            destination_ciphertext=encrypted.ciphertext,
            encryption_key_id=encrypted.key_id,
            lookup_digest=lookup.digest,
            lookup_key_id=lookup.key_id,
            verified_at=now,
            unreachable_at=now,
        )

    contact.state = VerifiedContactMethod.State.REVOKED
    contact.revoked_at = now
    contact.version += 1
    contact.save(update_fields=("state", "revoked_at", "version"))
    replacement = VerifiedContactMethod.objects.create(
        user=other,
        channel=VerifiedContactMethod.Channel.EMAIL,
        destination_ciphertext=encrypted.ciphertext,
        encryption_key_id=encrypted.key_id,
        lookup_digest=lookup.digest,
        lookup_key_id=lookup.key_id,
        verified_at=now,
    )
    assert replacement.pk != contact.pk


def test_registration_verification_framework_errors_use_stable_no_store_shape(client) -> None:
    path = reverse("auth-registration-verification-request")

    method_error = client.get(
        path,
        secure=True,
        headers={"origin": "https://testserver"},
    )
    parse_error = client.post(
        path,
        b'{"channel":',
        content_type="application/json",
        secure=True,
        headers={
            "origin": "https://testserver",
            "idempotency-key": "malformed-json-1",
        },
    )

    assert method_error.status_code == 405
    assert parse_error.status_code == 400
    for response in (method_error, parse_error):
        assert response.json() == {"error": {"code": "CONTACT_INVALID"}}
        assert response.headers["Cache-Control"] == "no-store"


def test_cross_origin_verification_is_rejected_without_claiming_global_outage(client) -> None:
    response = client.post(
        reverse("auth-registration-verification-request"),
        {"channel": "email", "destination": "origin@example.com"},
        content_type="application/json",
        secure=True,
        headers={
            "origin": "https://attacker.invalid",
            "idempotency-key": "cross-origin-1",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CONTACT_INVALID"}}
    assert response.headers["Cache-Control"] == "no-store"
    assert VerificationChallenge.objects.count() == 0
    assert VerificationRequestRecord.objects.count() == 0


@pytest.mark.parametrize(
    "existing_state",
    [None, VerifiedContactMethod.State.ACTIVE, VerifiedContactMethod.State.UNREACHABLE],
)
def test_unknown_occupied_and_unreachable_contacts_share_response_and_delivery_path(
    client,
    existing_state: str | None,
) -> None:
    destination = "privacy@example.com"
    if existing_state is not None:
        rings = verification_keyrings()
        encrypted = encrypt_value(
            destination,
            keyring=rings.contact_encryption,
            context="contact:email",
        )
        lookup = keyed_digest(
            destination,
            keyring=rings.contact_lookup,
            context="contact:email",
        )
        now = timezone.now()
        VerifiedContactMethod.objects.create(
            user=get_user_model().objects.create_user(username=f"privacy_{existing_state}"),
            channel=VerifiedContactMethod.Channel.EMAIL,
            state=existing_state,
            destination_ciphertext=encrypted.ciphertext,
            encryption_key_id=encrypted.key_id,
            lookup_digest=lookup.digest,
            lookup_key_id=lookup.key_id,
            verified_at=now,
            unreachable_at=(
                now if existing_state == VerifiedContactMethod.State.UNREACHABLE else None
            ),
        )

    response = verification_post(
        client,
        {"channel": "email", "destination": destination},
        idempotency_key=f"privacy-{existing_state or 'unknown'}",
    )
    outcome = deliver_one_verification(worker_id="privacy-worker")

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "retry_after": 60}
    assert set(response.headers) >= {"Cache-Control", "Content-Type"}
    assert outcome == DeliveryOutcome.DELIVERED
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [destination]
