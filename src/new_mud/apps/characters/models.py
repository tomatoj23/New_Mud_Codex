from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ImmutableModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f"{type(self).__name__} rows are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{type(self).__name__} rows are immutable")


class Character(models.Model):
    class Lifecycle(models.TextChoices):
        ACTIVE = "active"
        RETIRED = "retired"

    character_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=64)
    normalized_display_name = models.CharField(max_length=64)
    gender = models.CharField(max_length=64)
    pronouns = models.CharField(max_length=64)
    lifecycle = models.CharField(
        max_length=16,
        choices=Lifecycle.choices,
        default=Lifecycle.ACTIVE,
    )
    initial_state = models.JSONField()
    start_room_revision = models.ForeignKey(
        "content.BlueprintRevision",
        on_delete=models.PROTECT,
        related_name="created_characters",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance_id", "normalized_display_name"),
                name="characters_instance_display_name_uniq",
            ),
            models.CheckConstraint(
                condition=Q(lifecycle__in=("active", "retired")),
                name="characters_lifecycle_valid",
            ),
        ]


class CharacterOwnership(models.Model):
    ownership_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game_account = models.ForeignKey(
        "identity.GameAccount",
        on_delete=models.PROTECT,
        related_name="character_ownerships",
    )
    character = models.OneToOneField(
        Character,
        on_delete=models.PROTECT,
        related_name="ownership",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("game_account",),
                name="characters_game_account_one_character_uniq",
            )
        ]


class CharacterCreationRecord(ImmutableModel):
    creation_record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    character = models.OneToOneField(
        Character,
        on_delete=models.PROTECT,
        related_name="creation_record",
    )
    game_account = models.ForeignKey(
        "identity.GameAccount",
        on_delete=models.PROTECT,
        related_name="character_creation_records",
    )
    profile_key = models.CharField(max_length=64)
    profile_version = models.CharField(max_length=32)
    profile_definition_hash = models.CharField(max_length=64)
    content_release_batch = models.ForeignKey(
        "content.ContentReleaseBatch",
        on_delete=models.PROTECT,
        related_name="character_creation_records",
    )
    start_room_revision = models.ForeignKey(
        "content.BlueprintRevision",
        on_delete=models.PROTECT,
        related_name="character_creation_records",
    )
    normalized_display_name = models.CharField(max_length=64)
    gender = models.CharField(max_length=64)
    pronouns = models.CharField(max_length=64)
    resolved_initial_state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class CharacterCreationRequestRecord(ImmutableModel):
    request_record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game_account = models.ForeignKey(
        "identity.GameAccount",
        on_delete=models.PROTECT,
        related_name="character_creation_requests",
    )
    idempotency_key = models.CharField(max_length=128)
    canonical_request_hash = models.CharField(max_length=64)
    character = models.ForeignKey(
        Character,
        on_delete=models.PROTECT,
        related_name="creation_request_records",
    )
    response_status = models.PositiveSmallIntegerField(default=201)
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("game_account", "idempotency_key"),
                name="characters_creation_request_key_uniq",
            )
        ]
