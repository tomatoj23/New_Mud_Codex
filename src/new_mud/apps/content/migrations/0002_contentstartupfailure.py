from __future__ import annotations

import uuid

from django.db import migrations, models

CONTENT_STARTUP_FAILURE_IMMUTABILITY_SQL = """
CREATE TRIGGER content_startup_failure_immutable
BEFORE UPDATE OR DELETE ON content_contentstartupfailure
FOR EACH ROW EXECUTE FUNCTION content_reject_immutable_update();
"""

CONTENT_STARTUP_FAILURE_IMMUTABILITY_REVERSE_SQL = """
DROP TRIGGER content_startup_failure_immutable ON content_contentstartupfailure;
"""


class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ContentStartupFailure",
            fields=[
                (
                    "failure_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("instance_id", models.CharField(max_length=128)),
                ("mudlib_key", models.CharField(max_length=128)),
                ("target_content_release", models.CharField(max_length=128)),
                ("seed_bundle_id", models.CharField(max_length=128)),
                ("artifact_hash", models.CharField(blank=True, max_length=64, null=True)),
                ("error_code", models.CharField(max_length=128)),
                ("error_message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=[
                            "instance_id",
                            "mudlib_key",
                            "target_content_release",
                            "created_at",
                        ],
                        name="content_startup_failure_ns_idx",
                    )
                ]
            },
        ),
        migrations.RunSQL(
            sql=CONTENT_STARTUP_FAILURE_IMMUTABILITY_SQL,
            reverse_sql=CONTENT_STARTUP_FAILURE_IMMUTABILITY_REVERSE_SQL,
        ),
    ]
