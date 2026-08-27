from django.db import migrations, models
from django.db.models import F
from django.utils import timezone


def retire_active_recovery_codes(apps, schema_editor) -> None:
    RecoveryCodeCredential = apps.get_model("identity", "RecoveryCodeCredential")
    RecoveryCodeCredential.objects.filter(state="active").update(
        state="revoked",
        revoked_at=timezone.now(),
        version=F("version") + 1,
    )


class Migration(migrations.Migration):
    dependencies = [("identity", "0008_security_notification_outbox")]

    operations = [
        migrations.RunPython(
            retire_active_recovery_codes,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="recoverycodecredential",
            name="identity_recovery_one_active",
        ),
        migrations.AlterField(
            model_name="recoverycodecredential",
            name="state",
            field=models.CharField(
                choices=[("used", "Used"), ("revoked", "Revoked")],
                default="revoked",
                max_length=16,
            ),
        ),
        migrations.AddConstraint(
            model_name="recoverycodecredential",
            constraint=models.CheckConstraint(
                condition=models.Q(state__in=("used", "revoked")),
                name="identity_recovery_retired",
            ),
        ),
    ]
