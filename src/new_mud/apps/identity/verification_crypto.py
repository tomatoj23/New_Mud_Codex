from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class KeyUnavailable(RuntimeError):
    pass


class CiphertextInvalid(ValueError):
    pass


def _decode_key(encoded: str) -> bytes:
    try:
        decoded = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise KeyUnavailable("key material is not valid base64") from error
    if len(decoded) != 32:
        raise KeyUnavailable("key material must decode to exactly 32 bytes")
    return decoded


class KeyRing:
    def __init__(self, *, current_key_id: str, encoded_keys: Mapping[str, str]) -> None:
        if not current_key_id or current_key_id not in encoded_keys:
            raise KeyUnavailable("current key identity is unavailable")
        keys = {key_id: _decode_key(encoded) for key_id, encoded in encoded_keys.items()}
        self.current_key_id = current_key_id
        self._keys = MappingProxyType(keys)

    @property
    def current_key(self) -> bytes:
        return self._keys[self.current_key_id]

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def read_key(self, key_id: str) -> bytes:
        try:
            return self._keys[key_id]
        except KeyError as error:
            raise KeyUnavailable(f"key identity {key_id!r} is unavailable") from error


@dataclass(frozen=True)
class EncryptedValue:
    ciphertext: str
    key_id: str


@dataclass(frozen=True)
class DigestedValue:
    digest: str
    key_id: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise CiphertextInvalid from error


def encrypt_value(plaintext: str, *, keyring: KeyRing, context: str) -> EncryptedValue:
    nonce = os.urandom(12)
    ciphertext = AESGCM(keyring.current_key).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        context.encode("utf-8"),
    )
    return EncryptedValue(
        ciphertext=f"v1.{_encode(nonce)}.{_encode(ciphertext)}",
        key_id=keyring.current_key_id,
    )


def decrypt_value(value: EncryptedValue, *, keyring: KeyRing, context: str) -> str:
    try:
        version, encoded_nonce, encoded_ciphertext = value.ciphertext.split(".")
        if version != "v1":
            raise CiphertextInvalid
        plaintext = AESGCM(keyring.read_key(value.key_id)).decrypt(
            _decode(encoded_nonce),
            _decode(encoded_ciphertext),
            context.encode("utf-8"),
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError) as error:
        raise CiphertextInvalid from error


def keyed_digest(
    value: str,
    *,
    keyring: KeyRing,
    context: str,
    key_id: str | None = None,
) -> DigestedValue:
    selected_key_id = key_id or keyring.current_key_id
    payload = f"v1\x1f{context}\x1f{value}".encode()
    return DigestedValue(
        digest=hmac.new(keyring.read_key(selected_key_id), payload, hashlib.sha256).hexdigest(),
        key_id=selected_key_id,
    )


def keyed_digest_candidates(
    value: str,
    *,
    keyring: KeyRing,
    context: str,
) -> tuple[DigestedValue, ...]:
    return tuple(
        keyed_digest(value, keyring=keyring, context=context, key_id=key_id)
        for key_id in keyring.key_ids
    )


def verification_code_digest(
    code: str,
    *,
    keyring: KeyRing,
    purpose: str,
    channel: str,
    destination_lookup_digest: str,
    user_id: str | None,
    key_id: str | None = None,
) -> DigestedValue:
    context = "\x1f".join(
        (
            "verification-code",
            purpose,
            channel,
            destination_lookup_digest,
            user_id or "<unbound>",
        )
    )
    return keyed_digest(code, keyring=keyring, context=context, key_id=key_id)
