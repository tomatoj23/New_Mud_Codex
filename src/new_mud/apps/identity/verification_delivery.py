from __future__ import annotations

import json
import smtplib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.utils import timezone

from .models import VerificationChallenge, VerificationDeliveryOutbox
from .verification import (
    email_contact_scope,
    lock_email_contact_scope,
    normalize_email,
)
from .verification_config import require_authentication_baseline
from .verification_crypto import EncryptedValue, decrypt_value


class DeliveryTransientError(RuntimeError):
    pass


class DeliveryPermanentError(RuntimeError):
    pass


class ProviderAcceptedCrash(RuntimeError):
    pass


class DeliveryOutcome(StrEnum):
    NO_WORK = "no_work"
    DELIVERED = "delivered"
    RETRY_SCHEDULED = "retry_scheduled"
    DELIVERY_FAILED = "delivery_failed"
    STALE_CLAIM = "stale_claim"


@dataclass(frozen=True)
class VerificationEmail:
    destination: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: VerificationEmail) -> None: ...


class DjangoEmailSender:
    def send(self, message: VerificationEmail) -> None:
        try:
            delivered = EmailMessage(
                subject=message.subject,
                body=message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[message.destination],
            ).send(fail_silently=False)
        except ValueError as error:
            raise DeliveryPermanentError from error
        except smtplib.SMTPRecipientsRefused as error:
            if error.recipients and all(
                isinstance(details, tuple) and int(details[0]) >= 500
                for details in error.recipients.values()
            ):
                raise DeliveryPermanentError from error
            raise DeliveryTransientError from error
        except smtplib.SMTPResponseException as error:
            if error.smtp_code >= 500:
                raise DeliveryPermanentError from error
            raise DeliveryTransientError from error
        except (OSError, smtplib.SMTPException) as error:
            raise DeliveryTransientError from error
        if delivered != 1:
            raise DeliveryTransientError


@dataclass(frozen=True)
class ClaimedDelivery:
    outbox_id: uuid.UUID
    challenge_id: uuid.UUID
    worker_id: str
    payload: dict[str, str]
    attempt_count: int


def _terminalize_delivery_failure(
    *,
    challenge: VerificationChallenge,
    outbox: VerificationDeliveryOutbox,
    provider_category: str,
    now,
) -> None:
    if challenge.state == VerificationChallenge.State.PENDING_DELIVERY:
        challenge.state = VerificationChallenge.State.DELIVERY_FAILED
        challenge.terminal_at = now
        challenge.version += 1
        challenge.save(update_fields=("state", "terminal_at", "version"))
    outbox.state = VerificationDeliveryOutbox.State.DELIVERY_FAILED
    outbox.payload_ciphertext = None
    outbox.lease_owner = None
    outbox.lease_expires_at = None
    outbox.provider_category = provider_category
    outbox.terminal_at = now
    outbox.version += 1
    outbox.save(
        update_fields=(
            "state",
            "payload_ciphertext",
            "lease_owner",
            "lease_expires_at",
            "provider_category",
            "terminal_at",
            "version",
        )
    )


def _terminalize_one_exhausted_lease(*, now) -> bool:
    with transaction.atomic():
        outbox = (
            VerificationDeliveryOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                state=VerificationDeliveryOutbox.State.LEASED,
                lease_expires_at__lte=now,
                attempt_count__gte=settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS,
            )
            .order_by("lease_expires_at", "outbox_id")
            .first()
        )
        if outbox is None:
            return False
        challenge = VerificationChallenge.objects.select_for_update().get(pk=outbox.challenge_id)
        _terminalize_delivery_failure(
            challenge=challenge,
            outbox=outbox,
            provider_category="attempts_exhausted",
            now=now,
        )
        return True


def _message_from_payload(payload: dict[str, str]) -> VerificationEmail:
    if set(payload) != {"channel", "code", "destination", "purpose"}:
        raise DeliveryPermanentError
    if payload["channel"] != "email" or payload["purpose"] not in {
        VerificationChallenge.Purpose.REGISTRATION,
        VerificationChallenge.Purpose.PASSWORD_RESET,
    }:
        raise DeliveryPermanentError
    code = payload["code"]
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        raise DeliveryPermanentError
    if payload["purpose"] == VerificationChallenge.Purpose.PASSWORD_RESET:
        return VerificationEmail(
            destination=payload["destination"],
            subject="[New_Mud] 密码重置验证码",
            body=(
                f"你的 New_Mud 密码重置验证码是：{code}\n\n"
                "验证码在 10 分钟内有效。如果你没有请求重置密码，请忽略本邮件。\n"
                "工作人员不会索要验证码。"
            ),
        )
    return VerificationEmail(
        destination=payload["destination"],
        subject="[New_Mud] 注册验证码",
        body=(
            f"你的 New_Mud 注册验证码是：{code}\n\n"
            "验证码在 10 分钟内有效。如果你没有请求注册，请忽略本邮件。\n"
            "工作人员不会索要验证码。"
        ),
    )


def _claim_delivery(*, worker_id: str, now) -> ClaimedDelivery | None:
    keyrings = require_authentication_baseline()
    eligible = models.Q(
        state=VerificationDeliveryOutbox.State.PENDING,
        next_attempt_at__lte=now,
    ) | models.Q(
        state=VerificationDeliveryOutbox.State.LEASED,
        lease_expires_at__lte=now,
    )
    with transaction.atomic():
        outbox = (
            VerificationDeliveryOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                eligible,
                attempt_count__lt=settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS,
            )
            .order_by("next_attempt_at", "created_at", "outbox_id")
            .first()
        )
        if outbox is None:
            return None
        if outbox.payload_ciphertext is None:
            raise DeliveryPermanentError
        plaintext = decrypt_value(
            EncryptedValue(outbox.payload_ciphertext, outbox.payload_key_id),
            keyring=keyrings.delivery_payload,
            context=f"verification-delivery:{outbox.challenge_id}",
        )
        try:
            payload = json.loads(plaintext)
        except json.JSONDecodeError as error:
            raise DeliveryPermanentError from error
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
        ):
            raise DeliveryPermanentError
        outbox.state = VerificationDeliveryOutbox.State.LEASED
        outbox.lease_owner = worker_id
        outbox.lease_expires_at = now + timedelta(seconds=settings.AUTH_VERIFICATION_LEASE_SECONDS)
        outbox.attempt_count += 1
        outbox.version += 1
        outbox.save(
            update_fields=(
                "state",
                "lease_owner",
                "lease_expires_at",
                "attempt_count",
                "version",
            )
        )
        return ClaimedDelivery(
            outbox_id=outbox.pk,
            challenge_id=outbox.challenge_id,
            worker_id=worker_id,
            payload=payload,
            attempt_count=outbox.attempt_count,
        )


def _finish_delivery(claim: ClaimedDelivery, *, now) -> DeliveryOutcome:
    normalized = normalize_email(claim.payload["destination"])
    keyrings = require_authentication_baseline()
    email_scope = email_contact_scope(normalized, lookup_keyring=keyrings.contact_lookup)
    with transaction.atomic():
        lock_email_contact_scope(email_scope)
        outbox = VerificationDeliveryOutbox.objects.select_for_update().get(pk=claim.outbox_id)
        if (
            outbox.state != VerificationDeliveryOutbox.State.LEASED
            or outbox.lease_owner != claim.worker_id
        ):
            return DeliveryOutcome.STALE_CLAIM
        challenge = VerificationChallenge.objects.select_for_update().get(pk=claim.challenge_id)
        VerificationChallenge.objects.select_for_update().filter(
            purpose=challenge.purpose,
            channel=challenge.channel,
            destination_lookup_digest__in=email_scope.lookup_digests,
            state=VerificationChallenge.State.ACTIVE,
        ).exclude(pk=challenge.pk).update(
            state=VerificationChallenge.State.SUPERSEDED,
            superseded_at=now,
            terminal_at=now,
            version=models.F("version") + 1,
        )
        challenge.state = VerificationChallenge.State.ACTIVE
        challenge.activated_at = now
        challenge.expires_at = now + timedelta(
            seconds=settings.AUTH_VERIFICATION_CHALLENGE_TTL_SECONDS
        )
        challenge.version += 1
        challenge.save(update_fields=("state", "activated_at", "expires_at", "version"))
        outbox.state = VerificationDeliveryOutbox.State.DELIVERED
        outbox.payload_ciphertext = None
        outbox.lease_owner = None
        outbox.lease_expires_at = None
        outbox.provider_category = "accepted"
        outbox.delivered_at = now
        outbox.terminal_at = now
        outbox.version += 1
        outbox.save(
            update_fields=(
                "state",
                "payload_ciphertext",
                "lease_owner",
                "lease_expires_at",
                "provider_category",
                "delivered_at",
                "terminal_at",
                "version",
            )
        )
    return DeliveryOutcome.DELIVERED


def _record_failure(
    claim: ClaimedDelivery,
    *,
    permanent: bool,
    now,
) -> DeliveryOutcome:
    with transaction.atomic():
        outbox = VerificationDeliveryOutbox.objects.select_for_update().get(pk=claim.outbox_id)
        if (
            outbox.state != VerificationDeliveryOutbox.State.LEASED
            or outbox.lease_owner != claim.worker_id
        ):
            return DeliveryOutcome.STALE_CLAIM
        exhausted = outbox.attempt_count >= settings.AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS
        if permanent or exhausted:
            challenge = VerificationChallenge.objects.select_for_update().get(pk=claim.challenge_id)
            _terminalize_delivery_failure(
                challenge=challenge,
                outbox=outbox,
                provider_category=("permanent_failure" if permanent else "transient_failure"),
                now=now,
            )
            return DeliveryOutcome.DELIVERY_FAILED
        outbox.state = VerificationDeliveryOutbox.State.PENDING
        outbox.next_attempt_at = now + timedelta(seconds=min(300, 2**outbox.attempt_count))
        outbox.lease_owner = None
        outbox.lease_expires_at = None
        outbox.provider_category = "transient_failure"
        outbox.version += 1
        outbox.save(
            update_fields=(
                "state",
                "payload_ciphertext",
                "next_attempt_at",
                "lease_owner",
                "lease_expires_at",
                "provider_category",
                "terminal_at",
                "version",
            )
        )
        return DeliveryOutcome.RETRY_SCHEDULED


def deliver_one_verification(
    *,
    worker_id: str,
    sender: EmailSender | None = None,
    crash_after_provider_accept: bool = False,
) -> DeliveryOutcome:
    now = timezone.now()
    if _terminalize_one_exhausted_lease(now=now):
        return DeliveryOutcome.DELIVERY_FAILED
    claim = _claim_delivery(worker_id=worker_id, now=now)
    if claim is None:
        return DeliveryOutcome.NO_WORK
    try:
        (sender or DjangoEmailSender()).send(_message_from_payload(claim.payload))
    except DeliveryPermanentError:
        return _record_failure(claim, permanent=True, now=timezone.now())
    except DeliveryTransientError:
        return _record_failure(claim, permanent=False, now=timezone.now())
    if crash_after_provider_accept:
        raise ProviderAcceptedCrash
    return _finish_delivery(claim, now=timezone.now())
