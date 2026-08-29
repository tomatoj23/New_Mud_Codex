from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from django.conf import settings


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _signing_key(purpose: str) -> bytes:
    root_key = settings.AUTH_TOKEN_SIGNING_KEY
    if not isinstance(root_key, str) or not root_key:
        raise RuntimeError("token signing key is unavailable")
    return hmac.new(
        root_key.encode("utf-8"),
        f"new-mud:{purpose}:v1".encode(),
        hashlib.sha256,
    ).digest()


def encode_access_token(claims: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _base64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    encoded_claims = _base64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{encoded_header}.{encoded_claims}"
    signature = _base64url(
        hmac.new(_signing_key("access"), signing_input.encode(), hashlib.sha256).digest()
    )
    return f"{signing_input}.{signature}"


class AccessTokenDecodeStatus(StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass(frozen=True)
class AccessTokenDecodeResult:
    status: AccessTokenDecodeStatus
    claims: dict[str, Any] | None = None


def decode_access_token_result(token: str) -> AccessTokenDecodeResult:
    try:
        encoded_header, encoded_claims, provided_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_claims}"
        expected_signature = _base64url(
            hmac.new(_signing_key("access"), signing_input.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(provided_signature, expected_signature):
            return AccessTokenDecodeResult(AccessTokenDecodeStatus.INVALID)
        header_padding = "=" * (-len(encoded_header) % 4)
        header = json.loads(base64.urlsafe_b64decode(encoded_header + header_padding))
        claims_padding = "=" * (-len(encoded_claims) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded_claims + claims_padding))
        if (
            not isinstance(header, dict)
            or header.get("alg") != "HS256"
            or header.get("typ") != "JWT"
            or not isinstance(claims, dict)
        ):
            return AccessTokenDecodeResult(AccessTokenDecodeStatus.INVALID)
        now = int(datetime.now(UTC).timestamp())
        if claims.get("aud") != "new-mud-h5" or not isinstance(claims.get("exp"), int):
            return AccessTokenDecodeResult(AccessTokenDecodeStatus.INVALID)
        if claims["exp"] <= now:
            return AccessTokenDecodeResult(AccessTokenDecodeStatus.EXPIRED, claims)
        return AccessTokenDecodeResult(AccessTokenDecodeStatus.VALID, claims)
    except ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError:
        return AccessTokenDecodeResult(AccessTokenDecodeStatus.INVALID)


def decode_access_token(token: str) -> dict[str, Any] | None:
    result = decode_access_token_result(token)
    if result.status != AccessTokenDecodeStatus.VALID:
        return None
    return result.claims


def materialize_refresh_token(credential_id: uuid.UUID, generation: int) -> str:
    identity = f"{credential_id.hex}:{generation}"
    secret = _base64url(
        hmac.new(_signing_key("refresh"), identity.encode(), hashlib.sha256).digest()
    )
    return f"r1.{credential_id.hex}.{generation}.{secret}"


def refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def parse_refresh_token(token: str) -> tuple[uuid.UUID, int] | None:
    try:
        version, raw_id, raw_generation, _secret = token.split(".")
        if version != "r1":
            return None
        credential_id = uuid.UUID(hex=raw_id)
        generation = int(raw_generation)
        if generation < 1:
            return None
        expected = materialize_refresh_token(credential_id, generation)
        if not hmac.compare_digest(expected, token):
            return None
        return credential_id, generation
    except ValueError, TypeError:
        return None
