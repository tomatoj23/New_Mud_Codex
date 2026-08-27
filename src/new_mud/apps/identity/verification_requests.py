from __future__ import annotations

import hashlib
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import (
    GameAccount,
    VerificationChallenge,
    VerificationDeliveryOutbox,
    VerificationRequestRecord,
    VerifiedContactMethod,
)
from .verification import normalize_email
from .verification_config import (
    VerificationServiceUnavailable,
    require_authentication_baseline,
)
from .verification_crypto import (
    CiphertextInvalid,
    EncryptedValue,
    KeyUnavailable,
    decrypt_value,
    encrypt_value,
    keyed_digest,
    keyed_digest_candidates,
    verification_code_digest,
)
from .verification_limits import (
    PersistentLimit,
    advisory_transaction_lock,
    consume_persistent_limits,
)

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ACCEPTED_PAYLOAD = {"status": "accepted", "retry_after": 60}


class ContactChannelUnavailable(ValueError):
    pass


class VerificationRequestInvalid(ValueError):
    pass


class VerificationRequestConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationRequestResult:
    status: int
    payload: dict[str, object]


def _request_hash(*, purpose: str, channel: str, comparison: str) -> str:
    canonical = json.dumps(
        {"channel": channel, "destination": comparison, "purpose": purpose},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _rate_limits(
    *, contact: str, ip: str, device: str, lookup_keyring
) -> tuple[PersistentLimit, ...]:
    contact_digest = keyed_digest(
        contact,
        keyring=lookup_keyring,
        context="verification-rate-limit:contact",
    ).digest
    ip_digest = keyed_digest(
        ip,
        keyring=lookup_keyring,
        context="verification-rate-limit:ip",
    ).digest
    device_digest = keyed_digest(
        device,
        keyring=lookup_keyring,
        context="verification-rate-limit:device",
    ).digest
    return (
        PersistentLimit("contact", contact_digest, 60, 1),
        PersistentLimit("contact", contact_digest, 15 * 60, 5),
        PersistentLimit("contact", contact_digest, 24 * 60 * 60, 10),
        PersistentLimit("ip", ip_digest, 15 * 60, 20),
        PersistentLimit("ip", ip_digest, 24 * 60 * 60, 100),
        PersistentLimit("device", device_digest, 15 * 60, 10),
        PersistentLimit("device", device_digest, 24 * 60 * 60, 30),
    )


def _replay_or_conflict(
    *,
    purpose: str,
    idempotency_key: str,
    request_hash: str,
) -> VerificationRequestResult | None:
    existing = VerificationRequestRecord.objects.filter(
        purpose=purpose,
        idempotency_key=idempotency_key,
    ).first()
    if existing is None:
        return None
    if not secrets.compare_digest(existing.canonical_request_hash, request_hash):
        raise VerificationRequestConflict
    return VerificationRequestResult(existing.response_status, existing.response_json)


def request_registration_verification(
    *,
    channel: object,
    destination: object,
    idempotency_key: object,
    client_ip: str,
    device_id: str,
) -> VerificationRequestResult:
    if channel != VerificationChallenge.Channel.EMAIL:
        raise ContactChannelUnavailable
    if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(
        idempotency_key
    ):
        raise VerificationRequestInvalid
    normalized = normalize_email(destination)
    keyrings = require_authentication_baseline()
    request_hash = _request_hash(
        purpose=VerificationChallenge.Purpose.REGISTRATION,
        channel=VerificationChallenge.Channel.EMAIL,
        comparison=normalized.comparison,
    )
    now = timezone.now()
    try:
        with transaction.atomic():
            advisory_transaction_lock("verification-request:registration:" + idempotency_key)
            replay = _replay_or_conflict(
                purpose=VerificationChallenge.Purpose.REGISTRATION,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay

            decision = consume_persistent_limits(
                namespace="registration-verification",
                limits=_rate_limits(
                    contact=normalized.comparison,
                    ip=client_ip,
                    device=device_id,
                    lookup_keyring=keyrings.contact_lookup,
                ),
                now=now,
            )
            if not decision.allowed:
                payload: dict[str, object] = {
                    "error": {"code": "VERIFICATION_RATE_LIMITED"},
                    "retry_after": decision.retry_after,
                }
                VerificationRequestRecord.objects.create(
                    purpose=VerificationChallenge.Purpose.REGISTRATION,
                    idempotency_key=idempotency_key,
                    canonical_request_hash=request_hash,
                    response_status=429,
                    response_json=payload,
                    created_at=now,
                    expires_at=now
                    + timedelta(seconds=settings.AUTH_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS),
                )
                return VerificationRequestResult(429, payload)

            lookup = keyed_digest(
                normalized.comparison,
                keyring=keyrings.contact_lookup,
                context="contact:email",
            )
            code = f"{secrets.randbelow(1_000_000):06d}"
            code_digest = verification_code_digest(
                code,
                keyring=keyrings.code_pepper,
                purpose=VerificationChallenge.Purpose.REGISTRATION,
                channel=VerificationChallenge.Channel.EMAIL,
                destination_lookup_digest=lookup.digest,
                user_id=None,
            )
            challenge_id = uuid.uuid4()
            challenge = VerificationChallenge.objects.create(
                challenge_id=challenge_id,
                purpose=VerificationChallenge.Purpose.REGISTRATION,
                channel=VerificationChallenge.Channel.EMAIL,
                destination_lookup_digest=lookup.digest,
                destination_lookup_key_id=lookup.key_id,
                code_digest=code_digest.digest,
                pepper_key_id=code_digest.key_id,
                issued_at=now,
            )
            delivery_payload = json.dumps(
                {
                    "channel": "email",
                    "code": code,
                    "destination": normalized.delivery,
                    "purpose": "registration",
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            encrypted_payload = encrypt_value(
                delivery_payload,
                keyring=keyrings.delivery_payload,
                context=f"verification-delivery:{challenge_id}",
            )
            VerificationDeliveryOutbox.objects.create(
                challenge=challenge,
                template_key="registration_verification",
                payload_ciphertext=encrypted_payload.ciphertext,
                payload_key_id=encrypted_payload.key_id,
                next_attempt_at=now,
            )
            VerificationRequestRecord.objects.create(
                purpose=VerificationChallenge.Purpose.REGISTRATION,
                idempotency_key=idempotency_key,
                canonical_request_hash=request_hash,
                response_status=202,
                response_json=ACCEPTED_PAYLOAD,
                created_at=now,
                expires_at=now
                + timedelta(seconds=settings.AUTH_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS),
            )
        return VerificationRequestResult(202, ACCEPTED_PAYLOAD)
    except DatabaseError as error:
        raise VerificationServiceUnavailable from error


def request_password_reset_verification(
    *,
    channel: object,
    destination: object,
    idempotency_key: object,
    client_ip: str,
    device_id: str,
) -> VerificationRequestResult:
    if channel != VerificationChallenge.Channel.EMAIL:
        raise ContactChannelUnavailable
    if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(
        idempotency_key
    ):
        raise VerificationRequestInvalid
    normalized = normalize_email(destination)
    keyrings = require_authentication_baseline()
    request_hash = _request_hash(
        purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
        channel=VerificationChallenge.Channel.EMAIL,
        comparison=normalized.comparison,
    )
    now = timezone.now()
    try:
        with transaction.atomic():
            advisory_transaction_lock("verification-request:password-reset:" + idempotency_key)
            replay = _replay_or_conflict(
                purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay

            decision = consume_persistent_limits(
                namespace="password-reset-verification",
                limits=_rate_limits(
                    contact=normalized.comparison,
                    ip=client_ip,
                    device=device_id,
                    lookup_keyring=keyrings.contact_lookup,
                ),
                now=now,
            )
            if not decision.allowed:
                payload: dict[str, object] = {
                    "error": {"code": "VERIFICATION_RATE_LIMITED"},
                    "retry_after": decision.retry_after,
                }
                VerificationRequestRecord.objects.create(
                    purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
                    idempotency_key=idempotency_key,
                    canonical_request_hash=request_hash,
                    response_status=429,
                    response_json=payload,
                    created_at=now,
                    expires_at=now
                    + timedelta(seconds=settings.AUTH_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS),
                )
                return VerificationRequestResult(429, payload)

            lookup_candidates = keyed_digest_candidates(
                normalized.comparison,
                keyring=keyrings.contact_lookup,
                context="contact:email",
            )
            contact = (
                VerifiedContactMethod.objects.select_related("user")
                .filter(
                    channel=VerifiedContactMethod.Channel.EMAIL,
                    state=VerifiedContactMethod.State.ACTIVE,
                    lookup_digest__in=tuple(item.digest for item in lookup_candidates),
                    user__is_active=True,
                )
                .order_by("contact_method_id")
                .first()
            )
            eligible = (
                contact is not None
                and GameAccount.objects.filter(
                    user_id=contact.user_id,
                    lifecycle__in=(
                        GameAccount.Lifecycle.ACTIVE,
                        GameAccount.Lifecycle.COOLING_OFF,
                    ),
                ).exists()
            )
            if eligible and contact is not None:
                delivery_destination = decrypt_value(
                    EncryptedValue(
                        contact.destination_ciphertext,
                        contact.encryption_key_id,
                    ),
                    keyring=keyrings.contact_encryption,
                    context="contact:email",
                )
                code = f"{secrets.randbelow(1_000_000):06d}"
                code_digest = verification_code_digest(
                    code,
                    keyring=keyrings.code_pepper,
                    purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
                    channel=VerificationChallenge.Channel.EMAIL,
                    destination_lookup_digest=contact.lookup_digest,
                    user_id=str(contact.user_id),
                )
                challenge_id = uuid.uuid4()
                challenge = VerificationChallenge.objects.create(
                    challenge_id=challenge_id,
                    purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
                    channel=VerificationChallenge.Channel.EMAIL,
                    destination_lookup_digest=contact.lookup_digest,
                    destination_lookup_key_id=contact.lookup_key_id,
                    user_id=contact.user_id,
                    code_digest=code_digest.digest,
                    pepper_key_id=code_digest.key_id,
                    issued_at=now,
                )
                delivery_payload = json.dumps(
                    {
                        "channel": "email",
                        "code": code,
                        "destination": delivery_destination,
                        "purpose": "password_reset",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                encrypted_payload = encrypt_value(
                    delivery_payload,
                    keyring=keyrings.delivery_payload,
                    context=f"verification-delivery:{challenge_id}",
                )
                VerificationDeliveryOutbox.objects.create(
                    challenge=challenge,
                    template_key="password_reset_verification",
                    payload_ciphertext=encrypted_payload.ciphertext,
                    payload_key_id=encrypted_payload.key_id,
                    next_attempt_at=now,
                )

            VerificationRequestRecord.objects.create(
                purpose=VerificationChallenge.Purpose.PASSWORD_RESET,
                idempotency_key=idempotency_key,
                canonical_request_hash=request_hash,
                response_status=202,
                response_json=ACCEPTED_PAYLOAD,
                created_at=now,
                expires_at=now
                + timedelta(seconds=settings.AUTH_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS),
            )
        return VerificationRequestResult(202, ACCEPTED_PAYLOAD)
    except (DatabaseError, CiphertextInvalid, KeyUnavailable) as error:
        raise VerificationServiceUnavailable from error
