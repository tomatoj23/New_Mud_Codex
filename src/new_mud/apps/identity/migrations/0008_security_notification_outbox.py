import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

GUARD_SQL = r"""
CREATE FUNCTION identity_guard_security_notification_outbox()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.contact_method_id IS DISTINCT FROM OLD.contact_method_id
       OR NEW.source_event_id IS DISTINCT FROM OLD.source_event_id
       OR NEW.template_key IS DISTINCT FROM OLD.template_key
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'SecurityNotificationOutbox identity is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_security_notice_identity_immutable';
    END IF;
    IF OLD.state IN ('delivered', 'delivery_failed') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal SecurityNotificationOutbox is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_security_notice_terminal_immutable';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state
       AND NOT (
           (OLD.state = 'pending' AND NEW.state = 'leased')
           OR (OLD.state = 'leased' AND NEW.state IN ('pending', 'delivered', 'delivery_failed'))
       ) THEN
        RAISE EXCEPTION 'SecurityNotificationOutbox state transition is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_security_notice_transition_valid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER identity_security_notification_outbox_guard
BEFORE UPDATE ON identity_securitynotificationoutbox
FOR EACH ROW EXECUTE FUNCTION identity_guard_security_notification_outbox();
"""


REVERSE_GUARD_SQL = r"""
DROP TRIGGER IF EXISTS identity_security_notification_outbox_guard
    ON identity_securitynotificationoutbox;
DROP FUNCTION IF EXISTS identity_guard_security_notification_outbox();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0007_password_reset_cancellation_transitions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityNotificationOutbox",
            fields=[
                (
                    "security_notification_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "template_key",
                    models.CharField(
                        choices=[("password_reset_succeeded", "Password Reset Succeeded")],
                        max_length=64,
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("leased", "Leased"),
                            ("delivered", "Delivered"),
                            ("delivery_failed", "Delivery Failed"),
                        ],
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("lease_owner", models.CharField(blank=True, max_length=128, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("next_attempt_at", models.DateTimeField()),
                ("provider_category", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("terminal_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveBigIntegerField(default=1)),
                (
                    "contact_method",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="security_notification_outbox",
                        to="identity.verifiedcontactmethod",
                    ),
                ),
                (
                    "source_event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="security_notification_outbox",
                        to="identity.securityauditevent",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="security_notification_outbox",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="securitynotificationoutbox",
            index=models.Index(
                fields=["state", "next_attempt_at"],
                name="identity_se_state_81cd52_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="securitynotificationoutbox",
            constraint=models.CheckConstraint(
                condition=models.Q(("version__gte", 1)),
                name="identity_security_notice_version_gte_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="securitynotificationoutbox",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("delivered_at__isnull", True),
                        ("state__in", ("pending", "leased")),
                        ("terminal_at__isnull", True),
                    ),
                    models.Q(
                        ("delivered_at__isnull", False),
                        ("state", "delivered"),
                        ("terminal_at__isnull", False),
                    ),
                    models.Q(
                        ("delivered_at__isnull", True),
                        ("state", "delivery_failed"),
                        ("terminal_at__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="identity_security_notice_state_times",
            ),
        ),
        migrations.AddConstraint(
            model_name="securitynotificationoutbox",
            constraint=models.CheckConstraint(
                condition=~models.Q(("state", "leased"))
                | models.Q(("lease_owner__isnull", False), ("lease_expires_at__isnull", False)),
                name="identity_security_notice_lease_complete",
            ),
        ),
        migrations.RunSQL(GUARD_SQL, REVERSE_GUARD_SQL),
    ]
