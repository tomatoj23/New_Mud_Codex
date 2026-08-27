from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def initialize_fail_closed_state(apps, schema_editor) -> None:
    RuntimeState = apps.get_model("identity", "AuthenticationBaselineRuntimeState")
    RuntimeState.objects.get_or_create(
        runtime_key="email",
        defaults={
            "provider_state": "open",
            "provider_retry_at": timezone.now(),
        },
    )


class Migration(migrations.Migration):
    dependencies = [("identity", "0009_retire_recovery_codes")]

    operations = [
        migrations.CreateModel(
            name="AuthenticationBaselineRuntimeState",
            fields=[
                (
                    "runtime_key",
                    models.CharField(
                        default="email",
                        max_length=32,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("verification_delivery_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("security_notification_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                (
                    "provider_state",
                    models.CharField(
                        choices=[("closed", "Closed"), ("open", "Open"), ("probing", "Probing")],
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "provider_retry_at",
                    models.DateTimeField(blank=True, default=timezone.now, null=True),
                ),
                ("provider_probe_token", models.UUIDField(blank=True, null=True)),
                ("provider_probe_expires_at", models.DateTimeField(blank=True, null=True)),
                ("provider_version", models.PositiveBigIntegerField(default=1)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(runtime_key="email"),
                        name="identity_auth_baseline_email_singleton",
                    ),
                    models.CheckConstraint(
                        condition=Q(provider_version__gte=1),
                        name="identity_auth_baseline_version_gte_1",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(
                                provider_state="closed",
                                provider_retry_at__isnull=True,
                                provider_probe_token__isnull=True,
                                provider_probe_expires_at__isnull=True,
                            )
                            | Q(
                                provider_state="open",
                                provider_retry_at__isnull=False,
                                provider_probe_token__isnull=True,
                                provider_probe_expires_at__isnull=True,
                            )
                            | Q(
                                provider_state="probing",
                                provider_retry_at__isnull=True,
                                provider_probe_token__isnull=False,
                                provider_probe_expires_at__isnull=False,
                            )
                        ),
                        name="identity_auth_baseline_provider_state",
                    ),
                ]
            },
        ),
        migrations.RunPython(initialize_fail_closed_state, migrations.RunPython.noop),
    ]
