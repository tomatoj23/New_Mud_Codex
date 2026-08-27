from __future__ import annotations

import base64
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.cache import cache
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
    SecurityAuditEvent,
    SecurityNotificationOutbox,
    VerificationChallenge,
    VerificationDeliveryOutbox,
    VerificationRateLimitBucket,
    VerifiedContactMethod,
)
from new_mud.apps.identity.verification import normalize_email
from new_mud.apps.identity.verification_config import verification_keyrings
from new_mud.apps.identity.verification_crypto import (
    EncryptedValue,
    decrypt_value,
    encrypt_value,
    keyed_digest,
)
from new_mud.apps.identity.verification_delivery import (
    DeliveryOutcome,
    deliver_one_verification,
)

pytestmark = pytest.mark.django_db(transaction=True)


def auth_post(
    client,
    route_name: str,
    payload: dict[str, object],
    *,
    remote_addr: str = "127.0.0.1",
    **headers,
):
    return client.post(
        reverse(route_name),
        payload,
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=remote_addr,
        headers={"origin": "https://testserver", **headers},
    )


@pytest.fixture(autouse=True)
def clear_auth_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


def login_in_additional_instance(client, *, username: str, password: str):
    user = get_user_model().objects.get(username=username)
    GameAccount.objects.create(user=user, instance_id="other-instance")
    with override_settings(CONTENT_INSTANCE_ID="other-instance"):
        return auth_post(
            client,
            "auth-login",
            {"username": username, "password": password},
        )


def request_delivered_verification_code(
    client,
    *,
    route_name: str,
    destination: str,
    idempotency_key: str,
) -> str:
    response = auth_post(
        client,
        route_name,
        {"channel": "email", "destination": destination},
        **{"idempotency-key": idempotency_key},
    )
    assert response.status_code == 202
    assert (
        deliver_one_verification(worker_id=f"test-{idempotency_key}") == DeliveryOutcome.DELIVERED
    )
    match = re.search(r"(?<!\d)\d{6}(?!\d)", str(mail.outbox[-1].body))
    assert match is not None
    return match.group()


def request_delivered_registration_code(
    client,
    *,
    destination: str,
    idempotency_key: str,
) -> str:
    return request_delivered_verification_code(
        client,
        route_name="auth-registration-verification-request",
        destination=destination,
        idempotency_key=idempotency_key,
    )


def request_delivered_password_reset_code(
    client,
    *,
    destination: str,
    idempotency_key: str,
) -> str:
    return request_delivered_verification_code(
        client,
        route_name="auth-password-reset-request",
        destination=destination,
        idempotency_key=idempotency_key,
    )


def post_registration_with_fresh_verified_email(
    client,
    payload: dict[str, object],
    *,
    remote_addr: str = "127.0.0.1",
    **headers,
):
    suffix = uuid.uuid4().hex
    destination = f"test-{suffix}@example.com"
    code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key=f"registration-{suffix}",
    )
    return auth_post(
        client,
        "auth-register",
        {
            **payload,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": code,
            },
        },
        remote_addr=remote_addr,
        **headers,
    )


def create_legacy_recovery_code(*, game_account_id: str) -> str:
    # Historical fixture: Issue #15 permits only already-revoked audit records.
    code = secrets.token_urlsafe(24)
    RecoveryCodeCredential.objects.create(
        game_account_id=game_account_id,
        generation=1,
        code_hash=make_password(code),
        state=RecoveryCodeCredential.State.REVOKED,
        revoked_at=timezone.now(),
    )
    return code


def verification_key(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def test_registration_creates_identity_without_authentication(client) -> None:
    destination = "New.Player@example.com"
    code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="registration-success",
    )
    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    response = auth_post(
        client,
        "auth-register",
        {
            "username": "New_Player",
            "password": "safe-example-passphrase-42",
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": code,
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"user_id", "game_account_id"}
    assert response.headers["Cache-Control"] == "no-store"
    assert "new_mud_refresh" not in response.cookies

    user = get_user_model().objects.get(pk=payload["user_id"])
    assert user.username == "new_player"
    assert user.email == ""
    assert user.check_password("safe-example-passphrase-42")
    account = GameAccount.objects.get(pk=payload["game_account_id"])
    assert account.user_id == user.pk

    contact = VerifiedContactMethod.objects.get(user=user)
    assert contact.channel == VerifiedContactMethod.Channel.EMAIL
    assert contact.state == VerifiedContactMethod.State.ACTIVE
    assert contact.destination_ciphertext != destination
    assert (
        decrypt_value(
            EncryptedValue(contact.destination_ciphertext, contact.encryption_key_id),
            keyring=verification_keyrings().contact_encryption,
            context="contact:email",
        )
        == destination
    )
    challenge = VerificationChallenge.objects.get()
    assert challenge.state == VerificationChallenge.State.CONSUMED
    assert challenge.consumed_at is not None
    assert RecoveryCodeCredential.objects.count() == 0
    assert AuthSession.objects.count() == 0
    assert RefreshTokenFamily.objects.count() == 0
    assert RefreshTokenCredential.objects.count() == 0


def test_password_reset_consumes_challenge_without_authenticating_browser(client) -> None:
    destination = "password-reset@example.com"
    old_password = "safe-old-passphrase-42"
    new_password = "safe-new-passphrase-84"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-registration",
    )
    registration = auth_post(
        client,
        "auth-register",
        {
            "username": "password_reset_player",
            "password": old_password,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-confirm",
    )

    response = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": new_password,
        },
    )

    assert response.status_code == 204
    assert response.content == b""
    assert "new_mud_refresh" not in response.cookies
    user = get_user_model().objects.get(username="password_reset_player")
    assert user.email == ""
    assert not user.check_password(old_password)
    assert user.check_password(new_password)
    reset_challenge = VerificationChallenge.objects.get(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET
    )
    assert reset_challenge.state == VerificationChallenge.State.CONSUMED
    assert reset_challenge.consumed_at is not None
    assert AuthSession.objects.count() == 0
    assert RefreshTokenFamily.objects.count() == 0
    assert RefreshTokenCredential.objects.count() == 0

    old_login = auth_post(
        client,
        "auth-login",
        {"username": "password_reset_player", "password": old_password},
    )
    new_login = auth_post(
        client,
        "auth-login",
        {"username": "password_reset_player", "password": new_password},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_password_reset_immediately_revokes_cross_instance_access_and_refresh() -> None:
    recovery_client = Client()
    first_client = Client()
    second_client = Client()
    destination = "password-reset-sessions@example.com"
    old_password = "safe-session-passphrase-42"
    new_password = "safe-replacement-passphrase-84"
    registration_code = request_delivered_registration_code(
        recovery_client,
        destination=destination,
        idempotency_key="password-reset-sessions-registration",
    )
    registration = auth_post(
        recovery_client,
        "auth-register",
        {
            "username": "password_reset_sessions",
            "password": old_password,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    first_login = auth_post(
        first_client,
        "auth-login",
        {"username": "password_reset_sessions", "password": old_password},
    )
    second_login = login_in_additional_instance(
        second_client,
        username="password_reset_sessions",
        password=old_password,
    )
    assert first_login.status_code == second_login.status_code == 200
    reset_code = request_delivered_password_reset_code(
        recovery_client,
        destination=destination,
        idempotency_key="password-reset-sessions-request",
    )

    reset = auth_post(
        recovery_client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": new_password,
        },
    )

    assert reset.status_code == 204
    assert set(AuthSession.objects.values_list("state", flat=True)) == {AuthSession.State.REVOKED}
    assert set(RefreshTokenFamily.objects.values_list("state", flat=True)) == {
        RefreshTokenFamily.State.REVOKED
    }
    assert not RefreshTokenCredential.objects.filter(
        state=RefreshTokenCredential.State.ACTIVE
    ).exists()
    for index, stale_client in enumerate((first_client, second_client), start=1):
        stale_refresh = auth_post(
            stale_client,
            "auth-refresh",
            {},
            **{"idempotency-key": f"stale-after-password-reset-{index}"},
        )
        assert stale_refresh.status_code == 401
        assert stale_refresh.json() == {"error": {"code": "SESSION_REVOKED"}}


def test_password_reset_cancels_unfinished_reset_deliveries(client) -> None:
    destination = "password-reset-cancel@example.com"
    old_password = "safe-cancel-passphrase-42"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-cancel-registration",
    )
    registration = auth_post(
        client,
        "auth-register",
        {
            "username": "password_reset_cancel",
            "password": old_password,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    active_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-cancel-active",
    )
    VerificationRateLimitBucket.objects.filter(namespace="password-reset-verification").update(
        window_started_at=timezone.now() - timedelta(days=2),
        request_count=0,
    )
    pending_request = auth_post(
        client,
        "auth-password-reset-request",
        {"channel": "email", "destination": destination},
        **{"idempotency-key": "password-reset-cancel-pending"},
    )
    assert pending_request.status_code == 202
    pending_challenge = VerificationChallenge.objects.get(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
        state=VerificationChallenge.State.PENDING_DELIVERY,
    )
    pending_outbox = VerificationDeliveryOutbox.objects.get(challenge=pending_challenge)
    assert pending_outbox.payload_ciphertext is not None

    reset = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": active_code,
            "new_password": "safe-cancel-replacement-84",
        },
    )

    assert reset.status_code == 204
    pending_challenge.refresh_from_db()
    pending_outbox.refresh_from_db()
    assert pending_challenge.state == VerificationChallenge.State.SUPERSEDED
    assert pending_challenge.superseded_at is not None
    assert pending_challenge.terminal_at is not None
    assert pending_outbox.state == VerificationDeliveryOutbox.State.DELIVERY_FAILED
    assert pending_outbox.payload_ciphertext is None
    assert pending_outbox.provider_category == "canceled_by_password_reset"
    assert pending_outbox.terminal_at is not None


def test_password_reset_enqueues_non_secret_security_notification(client) -> None:
    destination = "password-reset-notification@example.com"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notification-registration",
    )
    registration = auth_post(
        client,
        "auth-register",
        {
            "username": "password_reset_notification",
            "password": "safe-notification-passphrase-42",
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notification-request",
    )

    reset = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": "safe-notification-replacement-84",
        },
    )

    assert reset.status_code == 204
    notification_model = apps.get_model("identity", "SecurityNotificationOutbox")
    notification = notification_model.objects.get()
    contact = VerifiedContactMethod.objects.get()
    assert notification.user_id == contact.user_id
    assert notification.contact_method_id == contact.pk
    assert notification.template_key == "password_reset_succeeded"
    assert notification.state == "pending"
    persisted_fields = {field.name for field in notification_model._meta.fields}
    assert not {
        "destination",
        "code",
        "payload",
        "payload_ciphertext",
        "message_body",
        "access_token",
        "refresh_token",
    }.intersection(persisted_fields)


def test_security_notification_worker_sends_non_actionable_password_reset_notice(client) -> None:
    from new_mud.apps.identity.security_notifications import (
        SecurityNotificationOutcome,
        deliver_one_security_notification,
    )

    destination = "password-reset-notice-delivery@example.com"
    username = "password_reset_notice_delivery"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notice-delivery-registration",
    )
    assert (
        auth_post(
            client,
            "auth-register",
            {
                "username": username,
                "password": "safe-notice-passphrase-42",
                "verification": {
                    "channel": "email",
                    "destination": destination,
                    "code": registration_code,
                },
            },
        ).status_code
        == 201
    )
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notice-delivery-request",
    )
    assert (
        auth_post(
            client,
            "auth-password-reset-confirm",
            {
                "channel": "email",
                "destination": destination,
                "code": reset_code,
                "new_password": "safe-notice-replacement-84",
            },
        ).status_code
        == 204
    )

    outcome = deliver_one_security_notification(worker_id="security-notice-worker")

    assert outcome == SecurityNotificationOutcome.DELIVERED
    notice = mail.outbox[-1]
    assert notice.to == [destination]
    assert notice.subject == "[New_Mud] 密码已重置"
    assert "密码已成功重置" in notice.body
    assert "验证码" not in notice.body
    assert "http://" not in notice.body
    assert "https://" not in notice.body
    assert username not in notice.body
    notification_model = apps.get_model("identity", "SecurityNotificationOutbox")
    notification = notification_model.objects.get()
    assert notification.state == "delivered"
    assert notification.delivered_at is not None
    assert notification.terminal_at is not None


def test_security_notification_provider_failure_does_not_roll_back_password_reset(
    client,
    caplog,
) -> None:
    from new_mud.apps.identity.security_notifications import (
        SecurityNotificationOutcome,
        SecurityNotificationPermanentError,
        deliver_one_security_notification,
    )

    class PermanentlyFailingSecurityNotificationSender:
        def send(self, message) -> None:
            raise SecurityNotificationPermanentError

    destination = "password-reset-notice-failure@example.com"
    username = "password_reset_notice_failure"
    old_password = "safe-notice-failure-passphrase-42"
    new_password = "safe-notice-failure-replacement-84"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notice-failure-registration",
    )
    assert (
        auth_post(
            client,
            "auth-register",
            {
                "username": username,
                "password": old_password,
                "verification": {
                    "channel": "email",
                    "destination": destination,
                    "code": registration_code,
                },
            },
        ).status_code
        == 201
    )
    assert (
        auth_post(
            client,
            "auth-login",
            {"username": username, "password": old_password},
        ).status_code
        == 200
    )
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-notice-failure-code",
    )
    assert (
        auth_post(
            client,
            "auth-password-reset-confirm",
            {
                "channel": "email",
                "destination": destination,
                "code": reset_code,
                "new_password": new_password,
            },
        ).status_code
        == 204
    )

    outcome = deliver_one_security_notification(
        worker_id="security-notice-failure-worker",
        sender=PermanentlyFailingSecurityNotificationSender(),
    )

    assert outcome == SecurityNotificationOutcome.DELIVERY_FAILED
    user = get_user_model().objects.get(username=username)
    assert user.check_password(new_password)
    assert not user.check_password(old_password)
    assert set(AuthSession.objects.values_list("state", flat=True)) == {AuthSession.State.REVOKED}
    notification = SecurityNotificationOutbox.objects.get()
    assert notification.state == SecurityNotificationOutbox.State.DELIVERY_FAILED
    assert notification.provider_category == "permanent_failure"
    assert SecurityAuditEvent.objects.filter(
        event_type="auth.security_notification.delivery_failed",
        reason_code="permanent_failure",
    ).exists()
    assert "security notification delivery failed" in caplog.text


def test_password_reset_code_locks_after_five_failures_with_one_stable_error(client) -> None:
    destination = "password-reset-attempts@example.com"
    old_password = "safe-reset-attempt-passphrase-42"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-attempt-registration",
    )
    assert (
        auth_post(
            client,
            "auth-register",
            {
                "username": "password_reset_attempts",
                "password": old_password,
                "verification": {
                    "channel": "email",
                    "destination": destination,
                    "code": registration_code,
                },
            },
        ).status_code
        == 201
    )
    delivered_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-attempt-code",
    )
    incorrect_code = "999999" if delivered_code != "999999" else "000000"
    payload: dict[str, object] = {
        "channel": "email",
        "destination": destination,
        "code": incorrect_code,
        "new_password": "safe-reset-attempt-replacement-84",
    }

    failures = [auth_post(client, "auth-password-reset-confirm", payload) for _ in range(5)]
    after_lock = auth_post(
        client,
        "auth-password-reset-confirm",
        {**payload, "code": delivered_code},
    )

    for response in (*failures, after_lock):
        assert response.status_code == 400
        assert response.json() == {"error": {"code": "VERIFICATION_CODE_INVALID"}}
        assert response.headers["Cache-Control"] == "no-store"
    challenge = VerificationChallenge.objects.get(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET
    )
    assert challenge.state == VerificationChallenge.State.LOCKED
    assert challenge.attempt_count == 5
    assert (
        get_user_model()
        .objects.get(username="password_reset_attempts")
        .check_password(old_password)
    )
    assert SecurityNotificationOutbox.objects.count() == 0


def test_weak_password_does_not_consume_reset_or_revoke_authentication(client) -> None:
    destination = "password-reset-weak@example.com"
    old_password = "safe-reset-weak-passphrase-42"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-weak-registration",
    )
    assert (
        auth_post(
            client,
            "auth-register",
            {
                "username": "password_reset_weak",
                "password": old_password,
                "verification": {
                    "channel": "email",
                    "destination": destination,
                    "code": registration_code,
                },
            },
        ).status_code
        == 201
    )
    assert (
        auth_post(
            client,
            "auth-login",
            {"username": "password_reset_weak", "password": old_password},
        ).status_code
        == 200
    )
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-weak-code",
    )

    response = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": "short",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "PASSWORD_RESET_UNAVAILABLE"}}
    user = get_user_model().objects.get(username="password_reset_weak")
    assert user.check_password(old_password)
    challenge = VerificationChallenge.objects.get(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET
    )
    assert challenge.state == VerificationChallenge.State.ACTIVE
    assert challenge.consumed_at is None
    assert set(AuthSession.objects.values_list("state", flat=True)) == {AuthSession.State.ACTIVE}
    assert set(RefreshTokenFamily.objects.values_list("state", flat=True)) == {
        RefreshTokenFamily.State.ACTIVE
    }
    assert set(RefreshTokenCredential.objects.values_list("state", flat=True)) == {
        RefreshTokenCredential.State.ACTIVE
    }
    assert SecurityNotificationOutbox.objects.count() == 0


def test_password_reset_preserves_cooling_off_lifecycle_and_requires_login(client) -> None:
    destination = "password-reset-cooling-off@example.com"
    old_password = "safe-reset-cooling-passphrase-42"
    new_password = "safe-reset-cooling-replacement-84"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="password-reset-cooling-registration",
    )
    registration = auth_post(
        client,
        "auth-register",
        {
            "username": "password_reset_cooling",
            "password": old_password,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])
    account.lifecycle = GameAccount.Lifecycle.COOLING_OFF
    account.lifecycle_version += 1
    account.save(update_fields=("lifecycle", "lifecycle_version"))
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key="password-reset-cooling-code",
    )

    response = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": new_password,
        },
    )

    assert response.status_code == 204
    assert "new_mud_refresh" not in response.cookies
    account.refresh_from_db()
    assert account.lifecycle == GameAccount.Lifecycle.COOLING_OFF
    assert AuthSession.objects.count() == 0
    assert RefreshTokenFamily.objects.count() == 0
    assert RefreshTokenCredential.objects.count() == 0
    user = get_user_model().objects.get(username="password_reset_cooling")
    assert user.check_password(new_password)
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "password_reset_cooling", "password": new_password},
    )
    assert login_response.status_code == 401


@pytest.mark.parametrize("identity_change", ["disabled", "retired"])
def test_password_reset_does_not_restore_disabled_or_retired_identity(
    client,
    identity_change: str,
) -> None:
    destination = f"password-reset-{identity_change}-confirm@example.com"
    username = f"password_reset_{identity_change}_confirm"
    old_password = "safe-reset-ineligible-passphrase-42"
    registration_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key=f"password-reset-{identity_change}-registration",
    )
    registration = auth_post(
        client,
        "auth-register",
        {
            "username": username,
            "password": old_password,
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": registration_code,
            },
        },
    )
    assert registration.status_code == 201
    reset_code = request_delivered_password_reset_code(
        client,
        destination=destination,
        idempotency_key=f"password-reset-{identity_change}-code",
    )
    user = get_user_model().objects.get(username=username)
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])
    if identity_change == "disabled":
        user.is_active = False
        user.save(update_fields=("is_active",))
    else:
        account.lifecycle = GameAccount.Lifecycle.RETIRED
        account.lifecycle_version += 1
        account.save(update_fields=("lifecycle", "lifecycle_version"))

    response = auth_post(
        client,
        "auth-password-reset-confirm",
        {
            "channel": "email",
            "destination": destination,
            "code": reset_code,
            "new_password": "safe-reset-ineligible-replacement-84",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "VERIFICATION_CODE_INVALID"}}
    user.refresh_from_db()
    account.refresh_from_db()
    assert user.check_password(old_password)
    assert user.is_active is (identity_change != "disabled")
    assert account.lifecycle == (
        GameAccount.Lifecycle.RETIRED
        if identity_change == "retired"
        else GameAccount.Lifecycle.ACTIVE
    )
    assert (
        VerificationChallenge.objects.get(
            purpose=VerificationChallenge.Purpose.PASSWORD_RESET
        ).state
        == VerificationChallenge.State.ACTIVE
    )
    assert SecurityNotificationOutbox.objects.count() == 0


def test_registration_code_locks_after_five_failures_with_one_stable_error(
    client,
    settings,
) -> None:
    settings.AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT = 100
    settings.AUTH_REGISTRATION_RATE_LIMIT_IP = 100
    destination = "attempts@example.com"
    delivered_code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="registration-attempts",
    )
    incorrect_code = "999999" if delivered_code != "999999" else "000000"
    payload: dict[str, object] = {
        "username": "attempt_player",
        "password": "safe-example-passphrase-42",
        "verification": {
            "channel": "email",
            "destination": destination,
            "code": incorrect_code,
        },
    }

    responses = [auth_post(client, "auth-register", payload) for _ in range(6)]

    assert [response.status_code for response in responses] == [400] * 6
    assert all(
        response.json() == {"error": {"code": "VERIFICATION_CODE_INVALID"}}
        for response in responses
    )
    challenge = VerificationChallenge.objects.get()
    assert challenge.state == VerificationChallenge.State.LOCKED
    assert challenge.attempt_count == 5
    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    assert VerifiedContactMethod.objects.count() == 0


def test_registration_expires_an_elapsed_challenge_and_rejects_reuse(client) -> None:
    destination = "expired@example.com"
    code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="registration-expired",
    )
    now = timezone.now()
    VerificationChallenge.objects.update(
        activated_at=now - timedelta(minutes=20),
        expires_at=now - timedelta(minutes=10),
    )
    payload: dict[str, object] = {
        "username": "expired_player",
        "password": "safe-example-passphrase-42",
        "verification": {
            "channel": "email",
            "destination": destination,
            "code": code,
        },
    }

    response = auth_post(client, "auth-register", payload)
    repeated = auth_post(client, "auth-register", payload)

    for result in (response, repeated):
        assert result.status_code == 400
        assert result.json() == {"error": {"code": "VERIFICATION_CODE_INVALID"}}
    challenge = VerificationChallenge.objects.get()
    assert challenge.state == VerificationChallenge.State.EXPIRED
    assert challenge.terminal_at is not None
    assert get_user_model().objects.count() == 0


def test_registration_rejects_an_occupied_verified_email_without_consuming_challenge(
    client,
) -> None:
    destination = "occupied@example.com"
    normalized = normalize_email(destination)
    rings = verification_keyrings()
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
    owner = get_user_model().objects.create_user(username="existing_contact_owner")
    VerifiedContactMethod.objects.create(
        user=owner,
        channel=VerifiedContactMethod.Channel.EMAIL,
        destination_ciphertext=encrypted.ciphertext,
        encryption_key_id=encrypted.key_id,
        lookup_digest=lookup.digest,
        lookup_key_id=lookup.key_id,
        verified_at=timezone.now(),
    )
    code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="registration-occupied-contact",
    )

    response = auth_post(
        client,
        "auth-register",
        {
            "username": "new_contact_claimant",
            "password": "safe-example-passphrase-42",
            "verification": {
                "channel": "email",
                "destination": destination,
                "code": code,
            },
        },
    )

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}
    assert get_user_model().objects.count() == 1
    assert GameAccount.objects.count() == 0
    assert VerifiedContactMethod.objects.count() == 1
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.ACTIVE


def test_registration_reads_a_rotated_challenge_and_writes_current_contact_keys(client) -> None:
    destination = "rotated-registration@example.com"
    old_settings = {
        "AUTH_CONTACT_ENCRYPTION_KEYS": {"old-encryption": verification_key(11)},
        "AUTH_CONTACT_ENCRYPTION_CURRENT_KEY_ID": "old-encryption",
        "AUTH_CONTACT_LOOKUP_KEYS": {"old-lookup": verification_key(12)},
        "AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID": "old-lookup",
        "AUTH_VERIFICATION_CODE_PEPPER_KEYS": {"old-code": verification_key(13)},
        "AUTH_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID": "old-code",
        "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS": {"old-delivery": verification_key(14)},
        "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID": "old-delivery",
    }
    with override_settings(**old_settings):
        code = request_delivered_registration_code(
            client,
            destination=destination,
            idempotency_key="registration-old-keys",
        )

    rotated_settings = {
        "AUTH_CONTACT_ENCRYPTION_KEYS": {
            "old-encryption": verification_key(11),
            "current-encryption": verification_key(21),
        },
        "AUTH_CONTACT_ENCRYPTION_CURRENT_KEY_ID": "current-encryption",
        "AUTH_CONTACT_LOOKUP_KEYS": {
            "old-lookup": verification_key(12),
            "current-lookup": verification_key(22),
        },
        "AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID": "current-lookup",
        "AUTH_VERIFICATION_CODE_PEPPER_KEYS": {
            "old-code": verification_key(13),
            "current-code": verification_key(23),
        },
        "AUTH_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID": "current-code",
        "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS": {
            "old-delivery": verification_key(14),
            "current-delivery": verification_key(24),
        },
        "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID": "current-delivery",
    }
    with override_settings(**rotated_settings):
        response = auth_post(
            client,
            "auth-register",
            {
                "username": "rotated_registration",
                "password": "safe-example-passphrase-42",
                "verification": {
                    "channel": "email",
                    "destination": destination,
                    "code": code,
                },
            },
        )

    assert response.status_code == 201
    contact = VerifiedContactMethod.objects.get()
    assert contact.encryption_key_id == "current-encryption"
    assert contact.lookup_key_id == "current-lookup"
    assert VerificationChallenge.objects.get().state == VerificationChallenge.State.CONSUMED


def test_registration_can_retry_password_and_username_with_the_same_challenge(
    client,
    settings,
) -> None:
    settings.AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT = 100
    settings.AUTH_REGISTRATION_RATE_LIMIT_IP = 100
    waiting_destination = "waiting@example.com"
    waiting_code = request_delivered_registration_code(
        client,
        destination=waiting_destination,
        idempotency_key="registration-waiting",
    )
    waiting_challenge_id = VerificationChallenge.objects.get().pk
    waiting_verification = {
        "channel": "email",
        "destination": waiting_destination,
        "code": waiting_code,
    }

    weak_password = auth_post(
        client,
        "auth-register",
        {
            "username": "waiting_player",
            "password": "short",
            "verification": waiting_verification,
        },
    )
    assert weak_password.status_code == 400
    assert weak_password.json() == {"error": {"code": "REGISTRATION_INVALID"}}
    assert (
        VerificationChallenge.objects.get(pk=waiting_challenge_id).state
        == VerificationChallenge.State.ACTIVE
    )

    competing_destination = "competing@example.com"
    competing_code = request_delivered_registration_code(
        client,
        destination=competing_destination,
        idempotency_key="registration-competing",
    )
    competing = auth_post(
        client,
        "auth-register",
        {
            "username": "waiting_player",
            "password": "safe-example-passphrase-42",
            "verification": {
                "channel": "email",
                "destination": competing_destination,
                "code": competing_code,
            },
        },
    )
    assert competing.status_code == 201

    occupied = auth_post(
        client,
        "auth-register",
        {
            "username": "WAITING_PLAYER",
            "password": "another-safe-passphrase-73",
            "verification": waiting_verification,
        },
    )
    assert occupied.status_code == 409
    assert occupied.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}

    retried = auth_post(
        client,
        "auth-register",
        {
            "username": "available_player",
            "password": "another-safe-passphrase-73",
            "verification": waiting_verification,
        },
    )
    assert retried.status_code == 201
    assert get_user_model().objects.filter(username="available_player").exists()
    assert (
        VerificationChallenge.objects.filter(state=VerificationChallenge.State.CONSUMED).count()
        == 2
    )


@pytest.mark.parametrize(
    "verification_override",
    [
        {"code": "999999"},
        {"channel": "sms"},
        {"destination": "other@example.com"},
    ],
)
def test_registration_verification_mismatches_share_one_error(
    client,
    verification_override: dict[str, str],
) -> None:
    destination = "mismatch@example.com"
    code = request_delivered_registration_code(
        client,
        destination=destination,
        idempotency_key="registration-mismatch",
    )
    verification = {
        "channel": "email",
        "destination": destination,
        "code": code,
        **verification_override,
    }

    response = auth_post(
        client,
        "auth-register",
        {
            "username": "mismatch_player",
            "password": "safe-example-passphrase-42",
            "verification": verification,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "VERIFICATION_CODE_INVALID"}}
    assert get_user_model().objects.count() == 0


def test_login_creates_one_session_family_and_protected_refresh_cookie(client) -> None:
    registration = post_registration_with_fresh_verified_email(
        client,
        {"username": "login_player", "password": "safe-example-passphrase-42"},
    )
    assert registration.status_code == 201

    response = auth_post(
        client,
        "auth-login",
        {"username": "LOGIN_PLAYER", "password": "safe-example-passphrase-42"},
        **{"user-agent": "browser-fingerprint-must-not-be-device-id"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "access_token",
        "token_type",
        "expires_in",
        "auth_session_id",
        "game_account_id",
    }
    assert payload["token_type"] == "Bearer"
    assert 0 < payload["expires_in"] <= 900
    assert "refresh" not in payload
    assert response.headers["Cache-Control"] == "no-store"

    cookie = response.cookies["new_mud_refresh"]
    assert cookie.value
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["secure"] is True
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert not cookie["domain"]
    assert 0 < int(cookie["max-age"]) <= 30 * 24 * 60 * 60

    session = AuthSession.objects.get(pk=payload["auth_session_id"])
    family = RefreshTokenFamily.objects.get(auth_session=session)
    credential = RefreshTokenCredential.objects.get(family=family)
    assert session.refresh_family_id == family.pk
    assert family.current_generation == credential.generation == 1
    assert session.device_id != "browser-fingerprint-must-not-be-device-id"
    assert cookie.value not in credential.token_hash


def test_token_credentials_do_not_use_the_django_framework_secret(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "independent_token_key", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "independent_token_key", "password": "safe-example-passphrase-42"},
    )
    assert login_response.status_code == 200

    with override_settings(SECRET_KEY="changed-framework-secret"):
        refresh_response = auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "independent-token-key-1"},
        )

    assert refresh_response.status_code == 200


def test_login_reports_access_lifetime_from_response_time(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "delayed_login", "password": "safe-example-passphrase-42"},
    )
    issued_at = datetime(2026, 8, 26, 0, 0, tzinfo=UTC)
    response_at = issued_at + timedelta(minutes=5)

    with patch(
        "new_mud.apps.identity.services.timezone.now",
        side_effect=(issued_at, issued_at, issued_at, response_at),
    ):
        response = auth_post(
            client,
            "auth-login",
            {"username": "delayed_login", "password": "safe-example-passphrase-42"},
        )

    assert response.status_code == 200
    assert response.json()["expires_in"] == 600


def test_refresh_rotates_the_same_family_to_the_next_generation(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "refresh_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "refresh_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]

    response = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "refresh-basic-1"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "access_token",
        "token_type",
        "expires_in",
        "auth_session_id",
        "game_account_id",
    }
    assert response.json()["auth_session_id"] == session_id
    assert "refresh" not in response.json()
    assert response.headers["Cache-Control"] == "no-store"
    successor_token = response.cookies["new_mud_refresh"].value
    assert successor_token != predecessor_token

    family = RefreshTokenFamily.objects.get(auth_session_id=session_id)
    assert family.current_generation == 2
    assert list(family.credentials.order_by("generation").values_list("generation", "state")) == [
        (1, "used"),
        (2, "active"),
    ]


def test_refresh_replay_with_a_different_key_revokes_family_and_session(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "replay_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "replay_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]
    first_refresh = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "refresh-logical-1"},
    )
    assert first_refresh.status_code == 200

    client.cookies["new_mud_refresh"] = predecessor_token
    replay = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "attacker-replay-2"},
    )

    assert replay.status_code == 401
    assert replay.json() == {"error": {"code": "SESSION_REVOKED"}}
    session = AuthSession.objects.get(pk=session_id)
    family = RefreshTokenFamily.objects.get(auth_session=session)
    assert session.state == "revoked"
    assert family.state == "revoked"
    assert not family.credentials.filter(state="active").exists()
    audit = SecurityAuditEvent.objects.get(reason_code="REFRESH_TOKEN_REPLAYED")
    assert audit.auth_session_id_snapshot == session_id
    assert predecessor_token not in str(audit.metadata_json)
    failed_terminal = RefreshRequestTerminalRecord.objects.get(idempotency_key="attacker-replay-2")
    assert failed_terminal.terminal_kind == RefreshRequestTerminalRecord.TerminalKind.FAILED
    assert failed_terminal.error_code == "SESSION_REVOKED"
    assert failed_terminal.successor_credential_id is None
    assert failed_terminal.access_claims_json == {}


def test_used_refresh_is_audited_as_replay_even_after_account_lifecycle_changes(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "late_replay", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "late_replay", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    auth_post(client, "auth-refresh", {}, **{"idempotency-key": "late-replay-first"})
    account = GameAccount.objects.get(pk=login_response.json()["game_account_id"])
    account.lifecycle = GameAccount.Lifecycle.COOLING_OFF
    account.lifecycle_version += 1
    account.save(update_fields=("lifecycle", "lifecycle_version"))

    client.cookies["new_mud_refresh"] = predecessor_token
    replay = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "late-replay-attacker"},
    )

    assert replay.status_code == 401
    assert replay.json() == {"error": {"code": "SESSION_REVOKED"}}
    family = RefreshTokenFamily.objects.get()
    assert family.revoke_reason == "REFRESH_TOKEN_REPLAYED"
    assert SecurityAuditEvent.objects.filter(reason_code="REFRESH_TOKEN_REPLAYED").exists()


def test_logout_converges_cookie_and_bearer_sessions_idempotently(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    first_login = auth_post(
        client,
        "auth-login",
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    first_access = first_login.json()["access_token"]
    first_session_id = first_login.json()["auth_session_id"]
    second_login = auth_post(
        client,
        "auth-login",
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    second_session_id = second_login.json()["auth_session_id"]

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {first_access}",
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    cleared = response.cookies["new_mud_refresh"]
    assert cleared["max-age"] == 0
    assert cleared["path"] == "/api/v1/auth/"
    assert cleared["secure"] is True
    assert cleared["httponly"] is True
    assert cleared["samesite"] == "Strict"
    assert set(
        AuthSession.objects.filter(pk__in=(first_session_id, second_session_id)).values_list(
            "state", flat=True
        )
    ) == {"logged_out"}
    assert not RefreshTokenCredential.objects.filter(state="active").exists()

    repeated = auth_post(client, "auth-logout", {})
    assert repeated.status_code == 204
    assert repeated.cookies["new_mud_refresh"]["max-age"] == 0


def test_recovery_code_routes_are_permanently_retired_without_consuming_credentials(client) -> None:
    registration = post_registration_with_fresh_verified_email(
        client,
        {"username": "recover_player", "password": "safe-example-passphrase-42"},
    )
    original_code = create_legacy_recovery_code(
        game_account_id=registration.json()["game_account_id"]
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "recover_player", "password": "safe-example-passphrase-42"},
    )
    assert login_response.status_code == 200

    recover_response = auth_post(
        client,
        "auth-recover",
        {
            "username": "RECOVER_PLAYER",
            "recovery_code": original_code,
            "new_password": "replacement-passphrase-73-safe",
        },
    )
    rotate_response = auth_post(
        client,
        "auth-recovery-rotate",
        {},
        authorization=f"Bearer {login_response.json()['access_token']}",
    )

    for response in (recover_response, rotate_response):
        assert response.status_code == 410
        assert response.json() == {"error": {"code": "RECOVERY_CODE_RETIRED"}}
        assert response.headers["Cache-Control"] == "no-store"
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])
    assert list(account.recovery_codes.values_list("generation", "state")) == [(1, "revoked")]
    assert account.auth_sessions.get().state == AuthSession.State.ACTIVE
    user = get_user_model().objects.get(username="recover_player")
    assert user.check_password("safe-example-passphrase-42")
    assert not user.check_password("replacement-passphrase-73-safe")


@pytest.mark.parametrize("route_name", ["auth-recover", "auth-recovery-rotate"])
def test_retired_recovery_routes_ignore_credentials_origin_and_body(
    client,
    route_name: str,
) -> None:
    response = client.post(
        reverse(route_name),
        data=b'{"broken":',
        content_type="application/json",
        secure=True,
        headers={"authorization": "Bearer invalid-retired-credential"},
    )

    assert response.status_code == 410
    assert response.json() == {"error": {"code": "RECOVERY_CODE_RETIRED"}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("route_name", ["auth-recover", "auth-recovery-rotate"])
def test_retired_recovery_routes_ignore_malformed_basic_authentication(
    client,
    route_name: str,
) -> None:
    response = client.post(
        reverse(route_name),
        {},
        content_type="application/json",
        secure=True,
        headers={"authorization": "Basic !!!"},
    )

    assert response.status_code == 410
    assert response.json() == {"error": {"code": "RECOVERY_CODE_RETIRED"}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("route_name", ["auth-recover", "auth-recovery-rotate"])
def test_retired_recovery_routes_ignore_authenticated_django_sessions(route_name: str) -> None:
    user = get_user_model().objects.create_user(
        username=f"retired_{route_name.replace('-', '_')}",
        password="safe-example-passphrase-42",
    )
    session_client = Client(enforce_csrf_checks=True)
    session_client.force_login(user)

    response = session_client.post(
        reverse(route_name),
        {},
        content_type="application/json",
        secure=True,
    )

    assert response.status_code == 410
    assert response.json() == {"error": {"code": "RECOVERY_CODE_RETIRED"}}
    assert response.headers["Cache-Control"] == "no-store"


def test_registration_and_login_are_rate_limited_with_stable_errors(client, settings) -> None:
    settings.AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT = 100
    settings.AUTH_REGISTRATION_RATE_LIMIT_IP = 1
    settings.AUTH_LOGIN_RATE_LIMIT_ACCOUNT = 1
    settings.AUTH_LOGIN_RATE_LIMIT_IP = 100

    first_registration = post_registration_with_fresh_verified_email(
        client,
        {"username": "limited_login", "password": "safe-example-passphrase-42"},
    )
    limited_registration = post_registration_with_fresh_verified_email(
        client,
        {"username": "other_registration", "password": "safe-example-passphrase-42"},
    )
    failed_login = auth_post(
        client,
        "auth-login",
        {"username": "limited_login", "password": "wrong-password"},
    )
    limited_login = auth_post(
        client,
        "auth-login",
        {"username": "limited_login", "password": "safe-example-passphrase-42"},
    )

    assert first_registration.status_code == 201
    assert limited_registration.status_code == 429
    assert limited_registration.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}
    assert failed_login.status_code == 401
    assert limited_login.status_code == 429
    assert limited_login.json() == {"error": {"code": "AUTH_CREDENTIALS_INVALID"}}
    assert AuthSession.objects.count() == 0


def test_refresh_same_key_is_safe_and_old_result_becomes_superseded(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "retry_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "retry_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert first.status_code == 200
    successor_token = first.cookies["new_mud_refresh"].value

    client.cookies["new_mud_refresh"] = predecessor_token
    retry = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert retry.status_code == 200
    assert retry.json()["access_token"] == first.json()["access_token"]
    assert retry.cookies["new_mud_refresh"].value == successor_token
    family = RefreshTokenFamily.objects.get()
    assert family.current_generation == 2

    client.cookies["new_mud_refresh"] = successor_token
    later = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "next-logical-refresh"},
    )
    assert later.status_code == 200
    client.cookies["new_mud_refresh"] = predecessor_token
    superseded = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert superseded.status_code == 409
    assert superseded.json() == {"error": {"code": "REFRESH_REQUEST_SUPERSEDED"}}
    family.refresh_from_db()
    assert family.state == "active"
    assert family.current_generation == 3


def test_refresh_retry_reports_access_token_remaining_lifetime(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "remaining_lifetime", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "remaining_lifetime", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "remaining-lifetime-key"},
    )
    claims = RefreshRequestTerminalRecord.objects.get().access_claims_json
    replay_time = datetime.fromtimestamp(int(claims["exp"]) - 37, tz=UTC)

    client.cookies["new_mud_refresh"] = predecessor_token
    with patch("new_mud.apps.identity.services.timezone.now", return_value=replay_time):
        retry = auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "remaining-lifetime-key"},
        )

    assert retry.status_code == 200
    assert retry.json()["access_token"] == first.json()["access_token"]
    assert retry.json()["expires_in"] == 37


def test_refresh_retry_at_family_cutoff_does_not_extend_the_cookie(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "cutoff_retry", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "cutoff_retry", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "cutoff-retry-key"},
    )
    family = RefreshTokenFamily.objects.get()

    client.cookies["new_mud_refresh"] = predecessor_token
    with patch(
        "new_mud.apps.identity.services.timezone.now",
        return_value=family.absolute_expires_at,
    ):
        retry = auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "cutoff-retry-key"},
        )

    assert retry.status_code == 401
    assert retry.json() == {"error": {"code": "SESSION_REVOKED"}}
    assert "new_mud_refresh" not in retry.cookies


def test_refresh_same_key_with_a_different_credential_is_a_conflict(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "conflict_player", "password": "safe-example-passphrase-42"},
    )
    auth_post(
        client,
        "auth-login",
        {"username": "conflict_player", "password": "safe-example-passphrase-42"},
    )
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "reused-key"},
    )
    assert first.status_code == 200

    conflict = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "reused-key"},
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"error": {"code": "REFRESH_IDEMPOTENCY_CONFLICT"}}
    family = RefreshTokenFamily.objects.get()
    assert family.state == "active"
    assert family.current_generation == 2


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("bad-name", "safe-example-passphrase-42"),
        ("valid_player", "short"),
    ],
)
def test_registration_rejects_invalid_credentials_without_partial_identity(
    client,
    username: str,
    password: str,
) -> None:
    response = post_registration_with_fresh_verified_email(
        client,
        {"username": username, "password": password},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "REGISTRATION_INVALID"}}
    assert response.headers["Cache-Control"] == "no-store"
    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    assert RecoveryCodeCredential.objects.count() == 0


def test_registration_rejects_case_insensitive_duplicate_without_partial_identity(client) -> None:
    first = post_registration_with_fresh_verified_email(
        client,
        {"username": "Duplicate_Player", "password": "safe-example-passphrase-42"},
    )
    assert first.status_code == 201

    duplicate = post_registration_with_fresh_verified_email(
        client,
        {"username": "DUPLICATE_PLAYER", "password": "another-safe-passphrase-73"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}
    assert duplicate.headers["Cache-Control"] == "no-store"
    assert get_user_model().objects.count() == 1
    assert GameAccount.objects.count() == 1
    assert RecoveryCodeCredential.objects.count() == 0


@pytest.mark.parametrize(
    ("route_name", "error_code"),
    [
        ("auth-register", "REGISTRATION_INVALID"),
        ("auth-login", "AUTH_CREDENTIALS_INVALID"),
        ("auth-refresh", "REFRESH_UNAVAILABLE"),
        ("auth-logout", "AUTH_CREDENTIALS_INVALID"),
    ],
)
def test_public_auth_routes_are_post_only_and_all_method_errors_are_not_cached(
    client,
    route_name: str,
    error_code: str,
) -> None:
    response = client.get(
        reverse(route_name),
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 405
    assert response.json() == {"error": {"code": error_code}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    ("route_name", "error_code"),
    [
        ("auth-register", "REGISTRATION_INVALID"),
        ("auth-login", "AUTH_CREDENTIALS_INVALID"),
        ("auth-refresh", "REFRESH_UNAVAILABLE"),
        ("auth-logout", "AUTH_CREDENTIALS_INVALID"),
    ],
)
def test_framework_parse_errors_use_stable_endpoint_codes_and_are_not_cached(
    client,
    route_name: str,
    error_code: str,
) -> None:
    response = client.post(
        reverse(route_name),
        data=b'{"broken":',
        content_type="application/json",
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": error_code}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        "/auth/login",
        "/api/auth/login",
        "/api/v1/login",
        "/api/v1/auth/login/",
    ],
)
def test_public_auth_routes_have_no_unversioned_or_slash_aliases(client, path: str) -> None:
    response = client.post(
        path,
        {"username": "player", "password": "irrelevant-passphrase-42"},
        content_type="application/json",
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_auth_endpoints_reject_untrusted_origin_without_authentication_side_effects(
    client,
    origin: str | None,
) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "origin_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "origin_player", "password": "safe-example-passphrase-42"},
    )
    session_id = login_response.json()["auth_session_id"]
    family = RefreshTokenFamily.objects.get(auth_session_id=session_id)

    headers = {} if origin is None else {"origin": origin}
    requests = [
        (
            "auth-register",
            {"username": "cross_origin", "password": "safe-example-passphrase-42"},
            {},
        ),
        (
            "auth-login",
            {"username": "origin_player", "password": "safe-example-passphrase-42"},
            {},
        ),
        ("auth-refresh", {}, {"idempotency-key": "blocked-origin-refresh"}),
        ("auth-logout", {}, {}),
    ]

    for route_name, payload, extra_headers in requests:
        response = client.post(
            reverse(route_name),
            payload,
            content_type="application/json",
            secure=True,
            headers={**headers, **extra_headers},
        )
        assert response.status_code >= 400
        assert response.headers["Cache-Control"] == "no-store"

    assert not get_user_model().objects.filter(username="cross_origin").exists()
    assert AuthSession.objects.count() == 1
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.ACTIVE
    family.refresh_from_db()
    assert family.state == RefreshTokenFamily.State.ACTIVE
    assert family.current_generation == 1


@pytest.mark.parametrize(
    "idempotency_key",
    [None, "", "has space", "_starts-with-punctuation", "非ascii", "a" * 129],
)
def test_invalid_refresh_key_fails_before_the_credential_is_consumed(
    client,
    idempotency_key: str | None,
) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "invalid_key_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "invalid_key_player", "password": "safe-example-passphrase-42"},
    )
    headers = {} if idempotency_key is None else {"idempotency-key": idempotency_key}

    response = auth_post(client, "auth-refresh", {}, **headers)

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "REFRESH_IDEMPOTENCY_KEY_INVALID"}}
    family = RefreshTokenFamily.objects.get(
        auth_session_id=login_response.json()["auth_session_id"]
    )
    assert family.current_generation == 1
    assert list(family.credentials.values_list("generation", "state")) == [(1, "active")]


def test_refresh_rejects_json_and_authorization_transport_without_rotation(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "transport_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "transport_player", "password": "safe-example-passphrase-42"},
    )
    refresh_token = login_response.cookies["new_mud_refresh"].value
    family = RefreshTokenFamily.objects.get(
        auth_session_id=login_response.json()["auth_session_id"]
    )

    bearer_response = auth_post(
        client,
        "auth-refresh",
        {},
        authorization=f"Bearer {refresh_token}",
        **{"idempotency-key": "refresh-bearer-forbidden"},
    )
    json_response = auth_post(
        client,
        "auth-refresh",
        {"refresh_token": refresh_token},
        **{"idempotency-key": "refresh-json-forbidden"},
    )

    for response in (bearer_response, json_response):
        assert response.status_code == 400
        assert response.json() == {"error": {"code": "REFRESH_UNAVAILABLE"}}
        assert refresh_token.encode() not in response.content
        assert "new_mud_refresh" not in response.cookies
    family.refresh_from_db()
    assert family.current_generation == 1
    assert list(family.credentials.values_list("generation", "state")) == [(1, "active")]


def test_logout_ignores_a_damaged_cookie_when_valid_bearer_locates_the_session(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "damaged_cookie", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "damaged_cookie", "password": "safe-example-passphrase-42"},
    )
    session_id = login_response.json()["auth_session_id"]
    client.cookies["new_mud_refresh"] = "damaged-cookie-value"

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {login_response.json()['access_token']}",
    )

    assert response.status_code == 204
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.LOGGED_OUT
    assert RefreshTokenFamily.objects.get(auth_session_id=session_id).state == "revoked"
    assert not RefreshTokenCredential.objects.filter(
        family__auth_session_id=session_id,
        state=RefreshTokenCredential.State.ACTIVE,
    ).exists()


def test_logout_preserves_revoked_terminal_state_and_converges_children(client) -> None:
    post_registration_with_fresh_verified_email(
        client,
        {"username": "terminal_logout", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "terminal_logout", "password": "safe-example-passphrase-42"},
    )
    predecessor = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]
    assert (
        auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "terminal-logout-first"},
        ).status_code
        == 200
    )
    client.cookies["new_mud_refresh"] = predecessor
    assert auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "terminal-logout-replay"},
    ).json() == {"error": {"code": "SESSION_REVOKED"}}

    response = auth_post(client, "auth-logout", {})

    assert response.status_code == 204
    assert response.content == b""
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.REVOKED
    assert RefreshTokenFamily.objects.get(auth_session_id=session_id).state == "revoked"
    assert not RefreshTokenCredential.objects.filter(
        family__auth_session_id=session_id,
        state=RefreshTokenCredential.State.ACTIVE,
    ).exists()


def test_logout_with_zero_recognized_locators_clears_client_without_false_audit(client) -> None:
    client.cookies["new_mud_refresh"] = "not-a-refresh-token"

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization="Bearer not-an-access-token",
    )

    assert response.status_code == 204
    assert response.headers["Cache-Control"] == "no-store"
    assert response.cookies["new_mud_refresh"]["max-age"] == 0
    assert SecurityAuditEvent.objects.count() == 0


def test_plaintext_authentication_secrets_never_enter_audit_terminal_or_logs(
    client,
    caplog,
) -> None:
    password = "secret-audit-passphrase-42"
    registration = post_registration_with_fresh_verified_email(
        client,
        {"username": "secret_audit", "password": password},
    )
    recovery_code = create_legacy_recovery_code(
        game_account_id=registration.json()["game_account_id"]
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "secret_audit", "password": password},
    )
    access_token = login_response.json()["access_token"]
    predecessor_refresh = login_response.cookies["new_mud_refresh"].value
    refresh_response = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "secret-audit-refresh"},
    )
    successor_refresh = refresh_response.cookies["new_mud_refresh"].value
    auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {refresh_response.json()['access_token']}",
    )

    persisted_blob = json.dumps(
        {
            "audits": list(
                SecurityAuditEvent.objects.values(
                    "event_type",
                    "reason_code",
                    "metadata_json",
                )
            ),
            "terminals": list(
                RefreshRequestTerminalRecord.objects.values(
                    "canonical_request_hash",
                    "access_claims_json",
                    "error_code",
                )
            ),
        },
        sort_keys=True,
    )
    observable_text = f"{persisted_blob}\n{caplog.text}"
    for secret in (
        password,
        recovery_code,
        access_token,
        predecessor_refresh,
        successor_refresh,
    ):
        assert secret not in observable_text
