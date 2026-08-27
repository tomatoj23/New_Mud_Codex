from __future__ import annotations

import os
from datetime import timedelta

import pytest
from django.apps.registry import Apps
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from new_mud.apps.identity.models import (
    SecurityAuditEvent,
    SecurityNotificationOutbox,
    VerificationChallenge,
    VerificationDeliveryOutbox,
    VerifiedContactMethod,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]

VERIFICATION_TABLES = {
    "identity_authenticationbaselineruntimestate",
    "identity_securitynotificationoutbox",
    "identity_verificationchallenge",
    "identity_verificationdeliveryoutbox",
    "identity_verificationratelimitbucket",
    "identity_verificationrequestrecord",
    "identity_verifiedcontactmethod",
}
VERIFICATION_GUARD_TRIGGERS = {
    "identity_security_notification_outbox_guard",
    "identity_verification_challenge_guard_trigger",
    "identity_verification_delivery_guard_trigger",
    "identity_verification_request_guard_trigger",
    "identity_verified_contact_guard_trigger",
    "identity_verification_limit_guard_trigger",
}


def migrate_identity_to(name: str) -> None:
    MigrationExecutor(connection).migrate([("identity", name)])


def verification_guard_triggers() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT trigger_name
              FROM information_schema.triggers
             WHERE trigger_schema = current_schema()
               AND trigger_name LIKE 'identity_verification_%_guard_trigger'
                OR (
                    trigger_schema = current_schema()
                    AND trigger_name IN (
                        'identity_verified_contact_guard_trigger',
                        'identity_security_notification_outbox_guard'
                    )
                )
            """
        )
        return {row[0] for row in cursor.fetchall()}


def migration_apps_at(name: str) -> Apps:
    executor = MigrationExecutor(connection)
    executor.migrate([("identity", name)])
    return executor.loader.project_state([("identity", name)]).apps


def test_recovery_code_retirement_is_irreversible_across_migration_rollback() -> None:
    try:
        old_apps = migration_apps_at("0008_security_notification_outbox")
        User = old_apps.get_model("auth", "User")
        GameAccount = old_apps.get_model("identity", "GameAccount")
        RecoveryCodeCredential = old_apps.get_model("identity", "RecoveryCodeCredential")
        user = User.objects.create(username="migration_recovery_retirement")
        account = GameAccount.objects.create(user=user, instance_id="default")
        active = RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=1,
            code_hash=make_password("active-code"),
        )
        used = RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=2,
            code_hash=make_password("used-code"),
            state="used",
            used_at=timezone.now(),
        )
        revoked = RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=3,
            code_hash=make_password("revoked-code"),
            state="revoked",
            revoked_at=timezone.now(),
        )

        retired_apps = migration_apps_at("0009_retire_recovery_codes")
        RetiredCode = retired_apps.get_model("identity", "RecoveryCodeCredential")
        assert list(RetiredCode.objects.order_by("generation").values_list("state", flat=True)) == [
            "revoked",
            "used",
            "revoked",
        ]
        assert retired_apps.get_model("auth", "User").objects.filter(pk=user.pk).exists()
        assert (
            retired_apps.get_model("identity", "GameAccount").objects.filter(pk=account.pk).exists()
        )
        retired_at = RetiredCode.objects.get(pk=active.pk).revoked_at
        assert retired_at is not None
        assert RetiredCode.objects.get(pk=used.pk).used_at is not None
        assert RetiredCode.objects.get(pk=revoked.pk).revoked_at is not None
        with pytest.raises(IntegrityError), transaction.atomic():
            RetiredCode.objects.create(
                game_account_id=account.pk,
                generation=4,
                code_hash=make_password("new-active-code"),
                state="active",
            )

        migration_apps_at("0008_security_notification_outbox")
        reapplied_apps = migration_apps_at("0009_retire_recovery_codes")
        ReappliedCode = reapplied_apps.get_model("identity", "RecoveryCodeCredential")
        assert ReappliedCode.objects.get(pk=active.pk).state == "revoked"
        assert ReappliedCode.objects.get(pk=active.pk).revoked_at == retired_at
    finally:
        migrate_identity_to("0010_authentication_baseline_runtime_state")


def test_verification_migrations_round_trip_from_0003_to_0010() -> None:
    try:
        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())

        migrate_identity_to("0010_authentication_baseline_runtime_state")
        assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
        assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS

        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())
    finally:
        migrate_identity_to("0010_authentication_baseline_runtime_state")

    assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
    assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS


def test_authentication_runtime_state_migration_round_trip_reinitializes_fail_closed() -> None:
    table_name = "identity_authenticationbaselineruntimestate"
    try:
        migrate_identity_to("0009_retire_recovery_codes")
        assert table_name not in connection.introspection.table_names()

        runtime_apps = migration_apps_at("0010_authentication_baseline_runtime_state")
        RuntimeState = runtime_apps.get_model("identity", "AuthenticationBaselineRuntimeState")
        state = RuntimeState.objects.get(runtime_key="email")
        assert state.verification_delivery_heartbeat_at is None
        assert state.security_notification_heartbeat_at is None
        assert state.provider_state == "open"
        assert state.provider_retry_at is not None
        assert state.provider_probe_token is None
        assert state.provider_probe_expires_at is None

        migrate_identity_to("0009_retire_recovery_codes")
        assert table_name not in connection.introspection.table_names()

        reapplied_apps = migration_apps_at("0010_authentication_baseline_runtime_state")
        ReappliedState = reapplied_apps.get_model("identity", "AuthenticationBaselineRuntimeState")
        reapplied = ReappliedState.objects.get(runtime_key="email")
        assert reapplied.verification_delivery_heartbeat_at is None
        assert reapplied.security_notification_heartbeat_at is None
        assert reapplied.provider_state == "open"
        assert reapplied.provider_retry_at is not None
    finally:
        migrate_identity_to("0010_authentication_baseline_runtime_state")


def test_password_reset_cancellation_and_security_notice_guards_are_one_way() -> None:
    now = timezone.now()
    user = get_user_model().objects.create_user(username="migration_password_reset_guards")
    contact = VerifiedContactMethod.objects.create(
        user=user,
        channel=VerifiedContactMethod.Channel.EMAIL,
        destination_ciphertext="encrypted-contact",
        encryption_key_id="contact-key",
        lookup_digest="a" * 64,
        lookup_key_id="lookup-key",
        verified_at=now,
    )
    challenge = VerificationChallenge.objects.create(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
        channel=VerificationChallenge.Channel.EMAIL,
        destination_lookup_digest=contact.lookup_digest,
        destination_lookup_key_id=contact.lookup_key_id,
        user=user,
        code_digest="b" * 64,
        pepper_key_id="pepper-key",
        issued_at=now,
    )
    delivery = VerificationDeliveryOutbox.objects.create(
        challenge=challenge,
        template_key="password_reset_verification",
        payload_ciphertext="encrypted-payload",
        payload_key_id="payload-key",
        next_attempt_at=now,
    )

    challenge.state = VerificationChallenge.State.SUPERSEDED
    challenge.superseded_at = now
    challenge.terminal_at = now
    challenge.version += 1
    challenge.save(update_fields=("state", "superseded_at", "terminal_at", "version"))
    delivery.state = VerificationDeliveryOutbox.State.DELIVERY_FAILED
    delivery.payload_ciphertext = None
    delivery.provider_category = "canceled_by_password_reset"
    delivery.terminal_at = now
    delivery.version += 1
    delivery.save(
        update_fields=(
            "state",
            "payload_ciphertext",
            "provider_category",
            "terminal_at",
            "version",
        )
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        VerificationChallenge.objects.filter(pk=challenge.pk).update(
            state=VerificationChallenge.State.PENDING_DELIVERY,
            superseded_at=None,
            terminal_at=None,
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        VerificationDeliveryOutbox.objects.filter(pk=delivery.pk).update(
            state=VerificationDeliveryOutbox.State.PENDING,
            payload_ciphertext="restored-payload",
            provider_category=None,
            terminal_at=None,
        )

    event = SecurityAuditEvent.objects.create(
        event_type="auth.password_reset.succeeded",
        user_id_snapshot=str(user.pk),
        reason_code="PASSWORD_RESET",
    )
    notification = SecurityNotificationOutbox.objects.create(
        user=user,
        contact_method=contact,
        source_event=event,
        template_key="password_reset_succeeded",
        next_attempt_at=now,
    )
    notification.state = SecurityNotificationOutbox.State.LEASED
    notification.attempt_count = 1
    notification.lease_owner = "migration-guard-worker"
    notification.lease_expires_at = now + timedelta(minutes=1)
    notification.version += 1
    notification.save(
        update_fields=(
            "state",
            "attempt_count",
            "lease_owner",
            "lease_expires_at",
            "version",
        )
    )
    notification.state = SecurityNotificationOutbox.State.DELIVERY_FAILED
    notification.lease_owner = None
    notification.lease_expires_at = None
    notification.provider_category = "permanent_failure"
    notification.terminal_at = now
    notification.version += 1
    notification.save(
        update_fields=(
            "state",
            "lease_owner",
            "lease_expires_at",
            "provider_category",
            "terminal_at",
            "version",
        )
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        SecurityNotificationOutbox.objects.filter(pk=notification.pk).update(
            state=SecurityNotificationOutbox.State.PENDING,
            provider_category=None,
            terminal_at=None,
        )
    pending_event = SecurityAuditEvent.objects.create(
        event_type="auth.password_reset.succeeded",
        user_id_snapshot=str(user.pk),
        reason_code="PASSWORD_RESET",
    )
    pending_notification = SecurityNotificationOutbox.objects.create(
        user=user,
        contact_method=contact,
        source_event=pending_event,
        template_key="password_reset_succeeded",
        next_attempt_at=now,
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        SecurityNotificationOutbox.objects.filter(pk=pending_notification.pk).update(
            template_key="changed_template"
        )
