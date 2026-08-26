from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .verification_crypto import KeyRing, KeyUnavailable


class VerificationServiceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationKeyRings:
    contact_encryption: KeyRing
    contact_lookup: KeyRing
    code_pepper: KeyRing
    delivery_payload: KeyRing


def _ring(keys_setting: str, current_setting: str) -> KeyRing:
    return KeyRing(
        current_key_id=str(getattr(settings, current_setting, "")),
        encoded_keys=getattr(settings, keys_setting, {}),
    )


def verification_keyrings() -> VerificationKeyRings:
    try:
        rings = VerificationKeyRings(
            contact_encryption=_ring(
                "AUTH_CONTACT_ENCRYPTION_KEYS",
                "AUTH_CONTACT_ENCRYPTION_CURRENT_KEY_ID",
            ),
            contact_lookup=_ring(
                "AUTH_CONTACT_LOOKUP_KEYS",
                "AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID",
            ),
            code_pepper=_ring(
                "AUTH_VERIFICATION_CODE_PEPPER_KEYS",
                "AUTH_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID",
            ),
            delivery_payload=_ring(
                "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS",
                "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID",
            ),
        )
    except (KeyUnavailable, TypeError) as error:
        raise VerificationServiceUnavailable from error

    encoded_material = [
        value
        for setting_name in (
            "AUTH_CONTACT_ENCRYPTION_KEYS",
            "AUTH_CONTACT_LOOKUP_KEYS",
            "AUTH_VERIFICATION_CODE_PEPPER_KEYS",
            "AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS",
        )
        for value in getattr(settings, setting_name, {}).values()
    ]
    ring_material = [
        ring.read_key(key_id)
        for ring in (
            rings.contact_encryption,
            rings.contact_lookup,
            rings.code_pepper,
            rings.delivery_payload,
        )
        for key_id in ring.key_ids
    ]
    external_material = [
        value
        for value in (
            settings.SECRET_KEY,
            getattr(settings, "EMAIL_HOST_PASSWORD", ""),
            getattr(settings, "AUTH_TOKEN_SIGNING_KEY", ""),
        )
        if value
    ]
    external_bytes = [value.encode("utf-8") for value in external_material]
    if (
        not getattr(settings, "AUTH_TOKEN_SIGNING_KEY", "")
        or len(set(encoded_material)) != len(encoded_material)
        or len(set(ring_material)) != len(ring_material)
        or len(set(external_material)) != len(external_material)
        or set(encoded_material).intersection(external_material)
        or set(ring_material).intersection(external_bytes)
    ):
        raise VerificationServiceUnavailable
    return rings


def require_verification_service() -> VerificationKeyRings:
    if not all(
        (
            getattr(settings, "AUTH_VERIFICATION_ENABLED", False),
            getattr(settings, "AUTH_VERIFICATION_WORKER_READY", False),
            getattr(settings, "AUTH_VERIFICATION_PROVIDER_READY", False),
        )
    ):
        raise VerificationServiceUnavailable
    return verification_keyrings()
