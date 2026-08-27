from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


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
    state = models.CharField(max_length=16, choices=State.choices, default=State.REVOKED)
    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("game_account", "generation"),
                name="identity_recovery_account_generation_uniq",
            ),
            models.CheckConstraint(
                condition=Q(state__in=("used", "revoked")),
                name="identity_recovery_retired",
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


class VerifiedContactMethod(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email"
        SMS = "sms"

    class State(models.TextChoices):
        ACTIVE = "active"
        UNREACHABLE = "unreachable"
        REVOKED = "revoked"

    contact_method_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_contact_methods",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    destination_ciphertext = models.TextField()
    encryption_key_id = models.CharField(max_length=64)
    lookup_digest = models.CharField(max_length=64)
    lookup_key_id = models.CharField(max_length=64)
    verified_at = models.DateTimeField()
    unreachable_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "channel"),
                condition=Q(state__in=("active", "unreachable")),
                name="identity_contact_one_usable_channel",
            ),
            models.UniqueConstraint(
                fields=("channel", "lookup_digest"),
                condition=Q(state__in=("active", "unreachable")),
                name="identity_contact_usable_destination_uniq",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_contact_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state="active", unreachable_at__isnull=True, revoked_at__isnull=True)
                    | Q(
                        state="unreachable",
                        unreachable_at__isnull=False,
                        revoked_at__isnull=True,
                    )
                    | Q(state="revoked", revoked_at__isnull=False)
                ),
                name="identity_contact_state_times",
            ),
            models.CheckConstraint(
                condition=(
                    Q(unreachable_at__isnull=True) | Q(unreachable_at__gte=models.F("verified_at"))
                )
                & (Q(revoked_at__isnull=True) | Q(revoked_at__gte=models.F("verified_at"))),
                name="identity_contact_times_after_verify",
            ),
        ]


class VerificationChallenge(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = "registration"
        PASSWORD_RESET = "password_reset"

    class Channel(models.TextChoices):
        EMAIL = "email"
        SMS = "sms"

    class State(models.TextChoices):
        PENDING_DELIVERY = "pending_delivery"
        ACTIVE = "active"
        CONSUMED = "consumed"
        SUPERSEDED = "superseded"
        EXPIRED = "expired"
        LOCKED = "locked"
        DELIVERY_FAILED = "delivery_failed"

    challenge_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    destination_lookup_digest = models.CharField(max_length=64)
    destination_lookup_key_id = models.CharField(max_length=64)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="verification_challenges",
    )
    code_digest = models.CharField(max_length=64)
    pepper_key_id = models.CharField(max_length=64)
    state = models.CharField(
        max_length=32,
        choices=State.choices,
        default=State.PENDING_DELIVERY,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    issued_at = models.DateTimeField()
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    terminal_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("purpose", "channel", "destination_lookup_digest"),
                condition=Q(state="active"),
                name="identity_challenge_one_active_destination",
            ),
            models.CheckConstraint(
                condition=(Q(purpose="registration", user__isnull=True))
                | Q(purpose="password_reset", user__isnull=False),
                name="identity_challenge_purpose_user_scope",
            ),
            models.CheckConstraint(
                condition=Q(attempt_count__lte=5),
                name="identity_challenge_attempt_lte_5",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_challenge_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(state="active")
                    | (
                        Q(activated_at__isnull=False)
                        & Q(expires_at__isnull=False)
                        & Q(expires_at__gt=models.F("activated_at"))
                    )
                ),
                name="identity_challenge_active_window",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state__in=("pending_delivery", "active"), terminal_at__isnull=True)
                    | Q(
                        state__in=(
                            "consumed",
                            "superseded",
                            "expired",
                            "locked",
                            "delivery_failed",
                        ),
                        terminal_at__isnull=False,
                    )
                ),
                name="identity_challenge_terminal_time",
            ),
            models.CheckConstraint(
                condition=(~Q(state="consumed") | Q(consumed_at__isnull=False))
                & (~Q(state="superseded") | Q(superseded_at__isnull=False)),
                name="identity_challenge_outcome_times",
            ),
        ]


class VerificationDeliveryOutbox(models.Model):
    class State(models.TextChoices):
        PENDING = "pending"
        LEASED = "leased"
        DELIVERED = "delivered"
        DELIVERY_FAILED = "delivery_failed"

    outbox_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.OneToOneField(
        VerificationChallenge,
        on_delete=models.PROTECT,
        related_name="delivery_outbox",
    )
    template_key = models.CharField(max_length=64)
    payload_ciphertext = models.TextField(null=True, blank=True)
    payload_key_id = models.CharField(max_length=64)
    state = models.CharField(max_length=24, choices=State.choices, default=State.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    lease_owner = models.CharField(max_length=128, null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField()
    provider_category = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    terminal_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=("state", "next_attempt_at"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_delivery_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state__in=("pending", "leased"), payload_ciphertext__isnull=False)
                    | Q(state__in=("delivered", "delivery_failed"), payload_ciphertext__isnull=True)
                ),
                name="identity_delivery_terminal_payload_erased",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(state="leased")
                    | (Q(lease_owner__isnull=False) & Q(lease_expires_at__isnull=False))
                ),
                name="identity_delivery_lease_complete",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state__in=("pending", "leased"),
                        delivered_at__isnull=True,
                        terminal_at__isnull=True,
                    )
                    | Q(
                        state="delivered",
                        delivered_at__isnull=False,
                        terminal_at__isnull=False,
                    )
                    | Q(
                        state="delivery_failed",
                        delivered_at__isnull=True,
                        terminal_at__isnull=False,
                    )
                ),
                name="identity_delivery_state_times",
            ),
        ]


class VerificationRequestRecord(models.Model):
    request_record_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=32, choices=VerificationChallenge.Purpose.choices)
    idempotency_key = models.CharField(max_length=128)
    canonical_request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField()
    response_json = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("purpose", "idempotency_key"),
                name="identity_verification_request_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("created_at")),
                name="identity_verification_request_retention",
            ),
        ]


class VerificationRateLimitBucket(models.Model):
    bucket_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    namespace = models.CharField(max_length=64)
    scope = models.CharField(max_length=16)
    subject_digest = models.CharField(max_length=64)
    window_seconds = models.PositiveIntegerField()
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("namespace", "scope", "subject_digest", "window_seconds"),
                name="identity_verification_limit_bucket_uniq",
            ),
            models.CheckConstraint(
                condition=Q(window_seconds__gte=1),
                name="identity_verification_limit_window_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="identity_verification_limit_version_gte_1",
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


class SecurityNotificationOutbox(models.Model):
    class TemplateKey(models.TextChoices):
        PASSWORD_RESET_SUCCEEDED = "password_reset_succeeded"

    class State(models.TextChoices):
        PENDING = "pending"
        LEASED = "leased"
        DELIVERED = "delivered"
        DELIVERY_FAILED = "delivery_failed"

    security_notification_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="security_notification_outbox",
    )
    contact_method = models.ForeignKey(
        VerifiedContactMethod,
        on_delete=models.PROTECT,
        related_name="security_notification_outbox",
    )
    source_event = models.OneToOneField(
        SecurityAuditEvent,
        on_delete=models.PROTECT,
        related_name="security_notification_outbox",
    )
    template_key = models.CharField(max_length=64, choices=TemplateKey.choices)
    state = models.CharField(max_length=24, choices=State.choices, default=State.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    lease_owner = models.CharField(max_length=128, null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField()
    provider_category = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    terminal_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=("state", "next_attempt_at"))]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="identity_security_notice_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(state="leased")
                    | (
                        models.Q(lease_owner__isnull=False)
                        & models.Q(lease_expires_at__isnull=False)
                    )
                ),
                name="identity_security_notice_lease_complete",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state__in=("pending", "leased"),
                        delivered_at__isnull=True,
                        terminal_at__isnull=True,
                    )
                    | models.Q(
                        state="delivered",
                        delivered_at__isnull=False,
                        terminal_at__isnull=False,
                    )
                    | models.Q(
                        state="delivery_failed",
                        delivered_at__isnull=True,
                        terminal_at__isnull=False,
                    )
                ),
                name="identity_security_notice_state_times",
            ),
        ]


class AuthenticationBaselineRuntimeState(models.Model):
    class ProviderState(models.TextChoices):
        CLOSED = "closed"
        OPEN = "open"
        PROBING = "probing"

    runtime_key = models.CharField(primary_key=True, max_length=32, default="email")
    verification_delivery_heartbeat_at = models.DateTimeField(null=True, blank=True)
    security_notification_heartbeat_at = models.DateTimeField(null=True, blank=True)
    provider_state = models.CharField(
        max_length=16,
        choices=ProviderState.choices,
        default=ProviderState.OPEN,
    )
    provider_retry_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    provider_probe_token = models.UUIDField(null=True, blank=True)
    provider_probe_expires_at = models.DateTimeField(null=True, blank=True)
    provider_version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(runtime_key="email"),
                name="identity_auth_baseline_email_singleton",
            ),
            models.CheckConstraint(
                condition=models.Q(provider_version__gte=1),
                name="identity_auth_baseline_version_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        provider_state="closed",
                        provider_retry_at__isnull=True,
                        provider_probe_token__isnull=True,
                        provider_probe_expires_at__isnull=True,
                    )
                    | models.Q(
                        provider_state="open",
                        provider_retry_at__isnull=False,
                        provider_probe_token__isnull=True,
                        provider_probe_expires_at__isnull=True,
                    )
                    | models.Q(
                        provider_state="probing",
                        provider_retry_at__isnull=True,
                        provider_probe_token__isnull=False,
                        provider_probe_expires_at__isnull=False,
                    )
                ),
                name="identity_auth_baseline_provider_state",
            ),
        ]
