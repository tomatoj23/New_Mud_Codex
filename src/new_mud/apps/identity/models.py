from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.db.models import Q


class GameAccount(models.Model):
    class Lifecycle(models.TextChoices):
        ACTIVE = "active"
        COOLING_OFF = "cooling_off"
        RETIRED = "retired"

    game_account_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="game_accounts",
    )
    instance_id = models.CharField(max_length=128)
    lifecycle = models.CharField(
        max_length=16,
        choices=Lifecycle.choices,
        default=Lifecycle.ACTIVE,
    )
    lifecycle_version = models.PositiveBigIntegerField(default=1)
    cooling_off_started_at = models.DateTimeField(null=True, blank=True)
    reopen_deadline_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "instance_id"),
                name="identity_user_instance_account_uniq",
            ),
            models.CheckConstraint(
                condition=Q(lifecycle_version__gte=1),
                name="identity_account_version_gte_1",
            ),
        ]


class RecoveryCodeCredential(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        USED = "used"
        REVOKED = "revoked"

    recovery_code_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game_account = models.ForeignKey(
        GameAccount,
        on_delete=models.PROTECT,
        related_name="recovery_codes",
    )
    generation = models.PositiveIntegerField()
    code_hash = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    def check_code(self, plaintext: str) -> bool:
        return check_password(plaintext, self.code_hash)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("game_account", "generation"),
                name="identity_recovery_account_generation_uniq",
            ),
            models.UniqueConstraint(
                fields=("game_account",),
                condition=Q(state="active"),
                name="identity_recovery_one_active",
            ),
            models.CheckConstraint(
                condition=Q(generation__gte=1),
                name="identity_recovery_generation_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_recovery_version_gte_1",
            ),
        ]


class AuthSession(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        REVOKED = "revoked"
        EXPIRED = "expired"
        LOGGED_OUT = "logged_out"

    auth_session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="auth_sessions",
    )
    game_account = models.ForeignKey(
        GameAccount,
        on_delete=models.PROTECT,
        related_name="auth_sessions",
    )
    device_id = models.CharField(max_length=128)
    refresh_family = models.OneToOneField(
        "RefreshTokenFamily",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bound_auth_session",
    )
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    issued_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    absolute_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=64, null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_session_version_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(absolute_expires_at__gt=models.F("issued_at")),
                name="identity_session_expiry_after_issue",
            ),
        ]


class RefreshTokenFamily(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        REVOKED = "revoked"
        EXPIRED = "expired"

    family_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auth_session = models.OneToOneField(
        AuthSession,
        on_delete=models.PROTECT,
        related_name="lifetime_refresh_family",
    )
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    current_generation = models.PositiveIntegerField(default=1)
    absolute_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=64, null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(current_generation__gte=1),
                name="identity_family_generation_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_family_version_gte_1",
            ),
        ]


class RefreshTokenCredential(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        USED = "used"
        REVOKED = "revoked"
        EXPIRED = "expired"

    credential_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(
        RefreshTokenFamily,
        on_delete=models.PROTECT,
        related_name="credentials",
    )
    generation = models.PositiveIntegerField()
    token_hash = models.CharField(max_length=64)
    jti_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    issued_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    replaced_by = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replaces",
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("family", "generation"),
                name="identity_credential_family_generation_uniq",
            ),
            models.UniqueConstraint(
                fields=("family",),
                condition=Q(state="active"),
                name="identity_credential_one_active",
            ),
            models.CheckConstraint(
                condition=Q(generation__gte=1),
                name="identity_credential_generation_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_credential_version_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("issued_at")),
                name="identity_credential_expiry_after_issue",
            ),
        ]


class RefreshRequestTerminalRecord(models.Model):
    class TerminalKind(models.TextChoices):
        SUCCEEDED = "succeeded"
        FAILED = "failed"

    terminal_record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(
        RefreshTokenFamily,
        on_delete=models.PROTECT,
        related_name="refresh_terminal_records",
    )
    idempotency_key = models.CharField(max_length=128)
    canonical_request_hash = models.CharField(max_length=64)
    predecessor_credential = models.ForeignKey(
        RefreshTokenCredential,
        on_delete=models.PROTECT,
        related_name="predecessor_terminal_records",
    )
    successor_credential = models.ForeignKey(
        RefreshTokenCredential,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_terminal_records",
    )
    access_claims_json = models.JSONField(default=dict)
    terminal_kind = models.CharField(max_length=16, choices=TerminalKind.choices)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("family", "idempotency_key"),
                name="identity_refresh_terminal_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("created_at")),
                name="identity_terminal_expiry_after_create",
            ),
        ]


class SecurityAuditEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=64)
    user_id_snapshot = models.CharField(max_length=128, null=True, blank=True)
    auth_session_id_snapshot = models.CharField(max_length=128, null=True, blank=True)
    reason_code = models.CharField(max_length=64, null=True, blank=True)
    metadata_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("event_type", "created_at"))]
