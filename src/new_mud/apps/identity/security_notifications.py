from __future__ import annotations

import logging
import smtplib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.utils import timezone

from .authentication_baseline_operations import (
    EmailDeliveryFailureScope,
    ProviderOutcome,
    WorkerRole,
    classify_email_delivery_failure,
    finish_provider_attempt,
    prepare_worker_poll,
)
from .models import (
    SecurityAuditEvent,
    SecurityNotificationOutbox,
    VerifiedContactMethod,
)
from .verification_config import require_authentication_baseline_configured
from .verification_crypto import EncryptedValue, decrypt_value

logger = logging.getLogger(__name__)


class SecurityNotificationTransientError(RuntimeError):
    pass


class SecurityNotificationMessageTransientError(RuntimeError):
    pass


class SecurityNotificationPermanentError(RuntimeError):
    pass


class SecurityNotificationOutcome(StrEnum):
    NO_WORK = "no_work"
    DELIVERED = "delivered"
    RETRY_SCHEDULED = "retry_scheduled"
    DELIVERY_FAILED = "delivery_failed"
    STALE_CLAIM = "stale_claim"


@dataclass(frozen=True)
class SecurityNotificationEmail:
    destination: str
    subject: str
    body: str


class SecurityNotificationSender(Protocol):
    def send(self, message: SecurityNotificationEmail) -> None: ...


class DjangoSecurityNotificationSender:
    def send(self, message: SecurityNotificationEmail) -> None:
        try:
            delivered = EmailMessage(
                subject=message.subject,
                body=message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[message.destination],
            ).send(fail_silently=False)
        except ValueError as error:
            raise SecurityNotificationPermanentError from error
        except (OSError, smtplib.SMTPException) as error:
            scope = classify_email_delivery_failure(error)
            if scope == EmailDeliveryFailureScope.MESSAGE_PERMANENT:
                raise SecurityNotificationPermanentError from error
            if scope == EmailDeliveryFailureScope.MESSAGE_TRANSIENT:
                raise SecurityNotificationMessageTransientError from error
            raise SecurityNotificationTransientError from error
        if delivered != 1:
            raise SecurityNotificationTransientError


@dataclass(frozen=True)
class ClaimedSecurityNotification:
    notification_id: uuid.UUID
    user_id: int
    worker_id: str
    message: SecurityNotificationEmail
    attempt_count: int


def _message(*, template_key: str, destination: str) -> SecurityNotificationEmail:
    if template_key != SecurityNotificationOutbox.TemplateKey.PASSWORD_RESET_SUCCEEDED:
        raise SecurityNotificationPermanentError
    return SecurityNotificationEmail(
        destination=destination,
        subject="[New_Mud] 密码已重置",
        body=(
            "你的 New_Mud 账号密码已成功重置。\n\n"
            "如果这不是你本人操作，请立即联系支持，并停止使用可能已经泄露的凭据。\n"
            "本通知不包含可执行的恢复链接，工作人员不会索要你的密码。"
        ),
    )


def _audit_terminal_failure(
    *,
    notification: SecurityNotificationOutbox,
    category: str,
) -> None:
    SecurityAuditEvent.objects.create(
        event_type="auth.security_notification.delivery_failed",
        user_id_snapshot=str(notification.user_id),
        reason_code=category,
        metadata_json={"security_notification_id": str(notification.pk)},
    )


def _terminalize_one_exhausted_lease(*, now) -> bool:
    with transaction.atomic():
        notification = (
            SecurityNotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                state=SecurityNotificationOutbox.State.LEASED,
                lease_expires_at__lte=now,
                attempt_count__gte=settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS,
            )
            .order_by("lease_expires_at", "security_notification_id")
            .first()
        )
        if notification is None:
            return False
        notification.state = SecurityNotificationOutbox.State.DELIVERY_FAILED
        notification.lease_owner = None
        notification.lease_expires_at = None
        notification.provider_category = "attempts_exhausted"
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
        _audit_terminal_failure(notification=notification, category="attempts_exhausted")
    logger.error(
        "security notification delivery failed",
        extra={"security_notification_id": str(notification.pk)},
    )
    return True


def _claim_security_notification(
    *,
    worker_id: str,
    now,
) -> ClaimedSecurityNotification | SecurityNotificationOutcome | None:
    keyrings = require_authentication_baseline_configured()
    eligible = models.Q(
        state=SecurityNotificationOutbox.State.PENDING,
        next_attempt_at__lte=now,
    ) | models.Q(
        state=SecurityNotificationOutbox.State.LEASED,
        lease_expires_at__lte=now,
    )
    with transaction.atomic():
        notification = (
            SecurityNotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                eligible,
                attempt_count__lt=settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS,
            )
            .order_by("next_attempt_at", "created_at", "security_notification_id")
            .first()
        )
        if notification is None:
            return None
        notification.state = SecurityNotificationOutbox.State.LEASED
        notification.lease_owner = worker_id
        notification.lease_expires_at = now + timedelta(
            seconds=settings.AUTH_VERIFICATION_LEASE_SECONDS
        )
        notification.attempt_count += 1
        notification.version += 1
        notification.save(
            update_fields=(
                "state",
                "lease_owner",
                "lease_expires_at",
                "attempt_count",
                "version",
            )
        )
        contact = VerifiedContactMethod.objects.select_for_update().get(
            pk=notification.contact_method_id
        )
        if (
            contact.user_id != notification.user_id
            or contact.state != VerifiedContactMethod.State.ACTIVE
        ):
            notification.state = SecurityNotificationOutbox.State.DELIVERY_FAILED
            notification.lease_owner = None
            notification.lease_expires_at = None
            notification.provider_category = "contact_unavailable"
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
            _audit_terminal_failure(
                notification=notification,
                category="contact_unavailable",
            )
            logger.error(
                "security notification delivery failed",
                extra={"security_notification_id": str(notification.pk)},
            )
            return SecurityNotificationOutcome.DELIVERY_FAILED
        destination = decrypt_value(
            EncryptedValue(
                contact.destination_ciphertext,
                contact.encryption_key_id,
            ),
            keyring=keyrings.contact_encryption,
            context="contact:email",
        )
        try:
            message = _message(
                template_key=notification.template_key,
                destination=destination,
            )
        except SecurityNotificationPermanentError:
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
            _audit_terminal_failure(
                notification=notification,
                category="permanent_failure",
            )
            logger.error(
                "security notification delivery failed",
                extra={"security_notification_id": str(notification.pk)},
            )
            return SecurityNotificationOutcome.DELIVERY_FAILED
        return ClaimedSecurityNotification(
            notification_id=notification.pk,
            user_id=notification.user_id,
            worker_id=worker_id,
            message=message,
            attempt_count=notification.attempt_count,
        )


def _finish_security_notification(
    claim: ClaimedSecurityNotification,
    *,
    now,
) -> SecurityNotificationOutcome:
    with transaction.atomic():
        notification = SecurityNotificationOutbox.objects.select_for_update().get(
            pk=claim.notification_id
        )
        if (
            notification.state != SecurityNotificationOutbox.State.LEASED
            or notification.lease_owner != claim.worker_id
        ):
            return SecurityNotificationOutcome.STALE_CLAIM
        notification.state = SecurityNotificationOutbox.State.DELIVERED
        notification.lease_owner = None
        notification.lease_expires_at = None
        notification.provider_category = "accepted"
        notification.delivered_at = now
        notification.terminal_at = now
        notification.version += 1
        notification.save(
            update_fields=(
                "state",
                "lease_owner",
                "lease_expires_at",
                "provider_category",
                "delivered_at",
                "terminal_at",
                "version",
            )
        )
    return SecurityNotificationOutcome.DELIVERED


def _record_security_notification_failure(
    claim: ClaimedSecurityNotification,
    *,
    permanent: bool,
    now,
) -> SecurityNotificationOutcome:
    terminal = False
    with transaction.atomic():
        notification = SecurityNotificationOutbox.objects.select_for_update().get(
            pk=claim.notification_id
        )
        if (
            notification.state != SecurityNotificationOutbox.State.LEASED
            or notification.lease_owner != claim.worker_id
        ):
            return SecurityNotificationOutcome.STALE_CLAIM
        terminal = (
            permanent
            or notification.attempt_count >= settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS
        )
        if terminal:
            category = "permanent_failure" if permanent else "transient_failure"
            notification.state = SecurityNotificationOutbox.State.DELIVERY_FAILED
            notification.terminal_at = now
            _audit_terminal_failure(notification=notification, category=category)
        else:
            category = "transient_failure"
            notification.state = SecurityNotificationOutbox.State.PENDING
            notification.next_attempt_at = now + timedelta(
                seconds=min(300, 2**notification.attempt_count)
            )
        notification.lease_owner = None
        notification.lease_expires_at = None
        notification.provider_category = category
        notification.version += 1
        notification.save(
            update_fields=(
                "state",
                "next_attempt_at",
                "lease_owner",
                "lease_expires_at",
                "provider_category",
                "terminal_at",
                "version",
            )
        )
    if terminal:
        logger.error(
            "security notification delivery failed",
            extra={"security_notification_id": str(claim.notification_id)},
        )
        return SecurityNotificationOutcome.DELIVERY_FAILED
    return SecurityNotificationOutcome.RETRY_SCHEDULED


def deliver_one_security_notification(
    *,
    worker_id: str,
    sender: SecurityNotificationSender | None = None,
    provider_probe: Callable[[], None] | None = None,
) -> SecurityNotificationOutcome:
    provider_permit = prepare_worker_poll(
        role=WorkerRole.SECURITY_NOTIFICATION,
        provider_probe=provider_probe,
    )
    if provider_permit is None:
        return SecurityNotificationOutcome.NO_WORK
    now = timezone.now()
    if _terminalize_one_exhausted_lease(now=now):
        return SecurityNotificationOutcome.DELIVERY_FAILED
    claimed = _claim_security_notification(worker_id=worker_id, now=now)
    if claimed is None:
        return SecurityNotificationOutcome.NO_WORK
    if isinstance(claimed, SecurityNotificationOutcome):
        return claimed
    try:
        (sender or DjangoSecurityNotificationSender()).send(claimed.message)
    except SecurityNotificationPermanentError:
        finish_provider_attempt(
            provider_permit,
            outcome=ProviderOutcome.PERMANENT_FAILURE,
        )
        return _record_security_notification_failure(
            claimed,
            permanent=True,
            now=timezone.now(),
        )
    except SecurityNotificationMessageTransientError:
        finish_provider_attempt(
            provider_permit,
            outcome=ProviderOutcome.MESSAGE_TRANSIENT_FAILURE,
        )
        return _record_security_notification_failure(
            claimed,
            permanent=False,
            now=timezone.now(),
        )
    except SecurityNotificationTransientError:
        finish_provider_attempt(
            provider_permit,
            outcome=ProviderOutcome.TRANSIENT_FAILURE,
        )
        return _record_security_notification_failure(
            claimed,
            permanent=False,
            now=timezone.now(),
        )
    finish_provider_attempt(
        provider_permit,
        outcome=ProviderOutcome.SUCCESS,
    )
    return _finish_security_notification(claimed, now=timezone.now())
