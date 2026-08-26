from __future__ import annotations

import os
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
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


def test_verification_migrations_round_trip_from_0003_to_0008() -> None:
    try:
        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())

        migrate_identity_to("0008_security_notification_outbox")
        assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
        assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS

        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())
    finally:
        migrate_identity_to("0008_security_notification_outbox")

    assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
    assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS


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
