import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("content", "0002_contentstartupfailure"),
        ("identity", "0010_authentication_baseline_runtime_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="Character",
            fields=[
                (
                    "character_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("instance_id", models.CharField(max_length=128)),
                ("display_name", models.CharField(max_length=64)),
                ("normalized_display_name", models.CharField(max_length=64)),
                ("gender", models.CharField(max_length=64)),
                ("pronouns", models.CharField(max_length=64)),
                (
                    "lifecycle",
                    models.CharField(
                        choices=[("active", "Active"), ("retired", "Retired")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("initial_state", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "start_room_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_characters",
                        to="content.blueprintrevision",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("instance_id", "normalized_display_name"),
                        name="characters_instance_display_name_uniq",
                    ),
                    models.CheckConstraint(
                        condition=Q(lifecycle__in=("active", "retired")),
                        name="characters_lifecycle_valid",
                    ),
                ]
            },
        ),
        migrations.CreateModel(
            name="CharacterCreationRecord",
            fields=[
                (
                    "creation_record_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("profile_key", models.CharField(max_length=64)),
                ("profile_version", models.CharField(max_length=32)),
                ("profile_definition_hash", models.CharField(max_length=64)),
                ("normalized_display_name", models.CharField(max_length=64)),
                ("gender", models.CharField(max_length=64)),
                ("pronouns", models.CharField(max_length=64)),
                ("resolved_initial_state", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="creation_record",
                        to="characters.character",
                    ),
                ),
                (
                    "content_release_batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_creation_records",
                        to="content.contentreleasebatch",
                    ),
                ),
                (
                    "game_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_creation_records",
                        to="identity.gameaccount",
                    ),
                ),
                (
                    "start_room_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_creation_records",
                        to="content.blueprintrevision",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CharacterOwnership",
            fields=[
                (
                    "ownership_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ownership",
                        to="characters.character",
                    ),
                ),
                (
                    "game_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_ownerships",
                        to="identity.gameaccount",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("game_account",),
                        name="characters_game_account_one_character_uniq",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="CharacterCreationRequestRecord",
            fields=[
                (
                    "request_record_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("idempotency_key", models.CharField(max_length=128)),
                ("canonical_request_hash", models.CharField(max_length=64)),
                ("response_status", models.PositiveSmallIntegerField(default=201)),
                ("response_json", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="creation_request_records",
                        to="characters.character",
                    ),
                ),
                (
                    "game_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="character_creation_requests",
                        to="identity.gameaccount",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("game_account", "idempotency_key"),
                        name="characters_creation_request_key_uniq",
                    )
                ]
            },
        ),
    ]
