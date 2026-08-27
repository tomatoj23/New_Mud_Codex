from __future__ import annotations

import smtplib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from django.conf import settings
from django.core.mail import get_connection
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import AuthenticationBaselineRuntimeState
from .verification_config import (
    VerificationServiceUnavailable,
    require_authentication_baseline_configured,
)


class WorkerRole(StrEnum):
    VERIFICATION_DELIVERY = "verification_delivery"
    SECURITY_NOTIFICATION = "security_notification"


class ProviderOutcome(StrEnum):
    SUCCESS = "success"
    TRANSIENT_FAILURE = "transient_failure"
    MESSAGE_TRANSIENT_FAILURE = "message_transient_failure"
    PERMANENT_FAILURE = "permanent_failure"


class EmailDeliveryFailureScope(StrEnum):
    PROVIDER_TRANSIENT = "provider_transient"
    MESSAGE_TRANSIENT = "message_transient"
    MESSAGE_PERMANENT = "message_permanent"


@dataclass(frozen=True)
class ProviderPermit:
    provider_version: int


@dataclass(frozen=True)
class ProviderProbePermit:
    provider_version: int
    token: uuid.UUID


def classify_email_delivery_failure(error: Exception) -> EmailDeliveryFailureScope:
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        if error.recipients and all(
            isinstance(details, tuple) and int(details[0]) >= 500
            for details in error.recipients.values()
        ):
            return EmailDeliveryFailureScope.MESSAGE_PERMANENT
        return EmailDeliveryFailureScope.MESSAGE_TRANSIENT
    if isinstance(error, smtplib.SMTPDataError):
        if error.smtp_code >= 500:
            return EmailDeliveryFailureScope.MESSAGE_PERMANENT
        return EmailDeliveryFailureScope.MESSAGE_TRANSIENT
    if isinstance(
        error,
        (
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPConnectError,
            smtplib.SMTPHeloError,
            smtplib.SMTPNotSupportedError,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPServerDisconnected,
        ),
    ):
        return EmailDeliveryFailureScope.PROVIDER_TRANSIENT
    if isinstance(error, smtplib.SMTPResponseException):
        return EmailDeliveryFailureScope.PROVIDER_TRANSIENT
    return EmailDeliveryFailureScope.PROVIDER_TRANSIENT


def require_authentication_baseline_operational(*, now=None) -> None:
    checked_at = now or timezone.now()
    stale_before = checked_at - timedelta(
        seconds=settings.AUTH_VERIFICATION_HEARTBEAT_MAX_AGE_SECONDS
    )
    try:
        state = AuthenticationBaselineRuntimeState.objects.filter(runtime_key="email").first()
    except DatabaseError as error:
        raise VerificationServiceUnavailable from error
    if (
        state is None
        or state.verification_delivery_heartbeat_at is None
        or state.verification_delivery_heartbeat_at <= stale_before
        or state.security_notification_heartbeat_at is None
        or state.security_notification_heartbeat_at <= stale_before
        or state.provider_state != AuthenticationBaselineRuntimeState.ProviderState.CLOSED
    ):
        raise VerificationServiceUnavailable


def prepare_worker_poll(
    *,
    role: WorkerRole,
    provider_probe: Callable[[], None] | None = None,
    now=None,
) -> ProviderPermit | None:
    require_authentication_baseline_configured()
    checked_at = now or timezone.now()
    heartbeat_field = {
        WorkerRole.VERIFICATION_DELIVERY: "verification_delivery_heartbeat_at",
        WorkerRole.SECURITY_NOTIFICATION: "security_notification_heartbeat_at",
    }[role]
    probe_permit: ProviderProbePermit | None = None
    try:
        with transaction.atomic():
            state = (
                AuthenticationBaselineRuntimeState.objects.select_for_update()
                .filter(runtime_key="email")
                .first()
            )
            if state is None:
                state = AuthenticationBaselineRuntimeState.objects.create(
                    runtime_key="email",
                    provider_state=AuthenticationBaselineRuntimeState.ProviderState.OPEN,
                    provider_retry_at=checked_at,
                )
            setattr(state, heartbeat_field, checked_at)
            update_fields = [heartbeat_field]
            if (
                getattr(settings, "AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND", False)
                and state.provider_state != AuthenticationBaselineRuntimeState.ProviderState.CLOSED
            ):
                state.provider_state = AuthenticationBaselineRuntimeState.ProviderState.CLOSED
                state.provider_retry_at = None
                state.provider_probe_token = None
                state.provider_probe_expires_at = None
                state.provider_version += 1
                update_fields.extend(
                    (
                        "provider_state",
                        "provider_retry_at",
                        "provider_probe_token",
                        "provider_probe_expires_at",
                        "provider_version",
                    )
                )
            if state.provider_state == AuthenticationBaselineRuntimeState.ProviderState.CLOSED:
                state.save(update_fields=update_fields)
                return ProviderPermit(provider_version=state.provider_version)
            probe_due = (
                state.provider_state == AuthenticationBaselineRuntimeState.ProviderState.OPEN
                and state.provider_retry_at is not None
                and state.provider_retry_at <= checked_at
            ) or (
                state.provider_state == AuthenticationBaselineRuntimeState.ProviderState.PROBING
                and state.provider_probe_expires_at is not None
                and state.provider_probe_expires_at <= checked_at
            )
            if probe_due:
                token = uuid.uuid4()
                state.provider_state = AuthenticationBaselineRuntimeState.ProviderState.PROBING
                state.provider_retry_at = None
                state.provider_probe_token = token
                state.provider_probe_expires_at = checked_at + timedelta(
                    seconds=settings.AUTH_VERIFICATION_PROVIDER_PROBE_LEASE_SECONDS
                )
                state.provider_version += 1
                update_fields.extend(
                    (
                        "provider_state",
                        "provider_retry_at",
                        "provider_probe_token",
                        "provider_probe_expires_at",
                        "provider_version",
                    )
                )
                probe_permit = ProviderProbePermit(state.provider_version, token)
            state.save(update_fields=update_fields)
    except DatabaseError as error:
        raise VerificationServiceUnavailable from error
    if probe_permit is None:
        return None
    probe_succeeded = True
    try:
        (provider_probe or probe_email_provider)()
    except Exception:
        probe_succeeded = False
    return _finish_provider_probe(
        probe_permit,
        succeeded=probe_succeeded,
    )


def probe_email_provider() -> None:
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
    finally:
        connection.close()


def _finish_provider_probe(
    permit: ProviderProbePermit,
    *,
    succeeded: bool,
    now=None,
) -> ProviderPermit | None:
    completed_at = now or timezone.now()
    try:
        with transaction.atomic():
            state = AuthenticationBaselineRuntimeState.objects.select_for_update().get(
                runtime_key="email"
            )
            if (
                state.provider_state != AuthenticationBaselineRuntimeState.ProviderState.PROBING
                or state.provider_version != permit.provider_version
                or state.provider_probe_token != permit.token
                or state.provider_probe_expires_at is None
                or state.provider_probe_expires_at <= completed_at
            ):
                return None
            state.provider_probe_token = None
            state.provider_probe_expires_at = None
            state.provider_version += 1
            if succeeded:
                state.provider_state = AuthenticationBaselineRuntimeState.ProviderState.CLOSED
                state.provider_retry_at = None
            else:
                state.provider_state = AuthenticationBaselineRuntimeState.ProviderState.OPEN
                state.provider_retry_at = completed_at + timedelta(
                    seconds=settings.AUTH_VERIFICATION_PROVIDER_RETRY_SECONDS
                )
            state.save(
                update_fields=(
                    "provider_state",
                    "provider_retry_at",
                    "provider_probe_token",
                    "provider_probe_expires_at",
                    "provider_version",
                )
            )
            if succeeded:
                return ProviderPermit(state.provider_version)
            return None
    except DatabaseError as error:
        raise VerificationServiceUnavailable from error


def finish_provider_attempt(
    permit: ProviderPermit,
    *,
    outcome: ProviderOutcome,
    now=None,
) -> None:
    if outcome != ProviderOutcome.TRANSIENT_FAILURE:
        return
    completed_at = now or timezone.now()
    try:
        with transaction.atomic():
            state = AuthenticationBaselineRuntimeState.objects.select_for_update().get(
                runtime_key="email"
            )
            if (
                state.provider_state != AuthenticationBaselineRuntimeState.ProviderState.CLOSED
                or state.provider_version != permit.provider_version
            ):
                return
            state.provider_state = AuthenticationBaselineRuntimeState.ProviderState.OPEN
            state.provider_retry_at = completed_at + timedelta(
                seconds=settings.AUTH_VERIFICATION_PROVIDER_RETRY_SECONDS
            )
            state.provider_probe_token = None
            state.provider_probe_expires_at = None
            state.provider_version += 1
            state.save(
                update_fields=(
                    "provider_state",
                    "provider_retry_at",
                    "provider_probe_token",
                    "provider_probe_expires_at",
                    "provider_version",
                )
            )
    except DatabaseError as error:
        raise VerificationServiceUnavailable from error
