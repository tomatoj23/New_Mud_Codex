from __future__ import annotations

import re
from dataclasses import dataclass

import idna

from .verification_crypto import DigestedValue, KeyRing, keyed_digest_candidates
from .verification_limits import advisory_transaction_lock

EMAIL_LOCAL_PATTERN = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
)


class ContactInvalid(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedEmail:
    delivery: str
    comparison: str


@dataclass(frozen=True)
class RegistrationEmailScope:
    email: NormalizedEmail
    current_lookup: DigestedValue
    lookup_candidates: tuple[DigestedValue, ...]

    @property
    def lookup_digests(self) -> tuple[str, ...]:
        return tuple(candidate.digest for candidate in self.lookup_candidates)


def normalize_email(destination: object) -> NormalizedEmail:
    if not isinstance(destination, str) or destination != destination.strip():
        raise ContactInvalid
    if destination.count("@") != 1:
        raise ContactInvalid
    local_part, raw_domain = destination.rsplit("@", 1)
    if (
        not EMAIL_LOCAL_PATTERN.fullmatch(local_part)
        or len(local_part.encode("ascii", errors="ignore")) != len(local_part)
        or len(local_part) > 64
    ):
        raise ContactInvalid
    try:
        domain = idna.encode(raw_domain, uts46=True, std3_rules=True).decode("ascii").lower()
    except (idna.IDNAError, UnicodeError) as error:
        raise ContactInvalid from error
    if "." not in domain or len(domain) > 253:
        raise ContactInvalid
    delivery = f"{local_part}@{domain}"
    if len(delivery) > 254:
        raise ContactInvalid
    return NormalizedEmail(delivery=delivery, comparison=delivery.casefold())


def registration_email_scope(
    email: NormalizedEmail,
    *,
    lookup_keyring: KeyRing,
) -> RegistrationEmailScope:
    candidates = keyed_digest_candidates(
        email.comparison,
        keyring=lookup_keyring,
        context="contact:email",
    )
    current_lookup = next(
        candidate for candidate in candidates if candidate.key_id == lookup_keyring.current_key_id
    )
    return RegistrationEmailScope(
        email=email,
        current_lookup=current_lookup,
        lookup_candidates=candidates,
    )


def lock_registration_email_scope(scope: RegistrationEmailScope) -> None:
    advisory_transaction_lock(f"registration:email:{scope.email.comparison}")
