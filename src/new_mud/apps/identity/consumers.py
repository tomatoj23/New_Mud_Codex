from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from .models import AuthSession, GameAccount
from .services import AuthenticationFailed, resolve_active_auth_session
from .tokens import decode_access_token

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SUPPORTED_VERSION = "1"


@dataclass(frozen=True)
class _Terminal:
    request_hash: str
    payload: dict[str, Any]


def _request_hash(message: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "version": message.get("version"),
            "type": message.get("type"),
            "payload": message.get("payload"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@database_sync_to_async
def _resolve_session(token: object) -> tuple[AuthSession | None, str]:
    if not isinstance(token, str):
        return None, "TOKEN_INVALID"
    claims = decode_access_token(token)
    if claims is None:
        # Decode separately only to provide the stable expired code; no claims are
        # ever included in a response.
        try:
            encoded_header, encoded_claims, provided_signature = token.split(".")
            header_padding = "=" * (-len(encoded_header) % 4)
            header = json.loads(base64.urlsafe_b64decode(encoded_header + header_padding))
            signing_input = f"{encoded_header}.{encoded_claims}"
            signing_key = hmac.new(
                settings.AUTH_TOKEN_SIGNING_KEY.encode("utf-8"),
                b"new-mud:access:v1",
                hashlib.sha256,
            ).digest()
            expected_signature = base64.urlsafe_b64encode(
                hmac.new(signing_key, signing_input.encode("ascii"), hashlib.sha256).digest()
            ).rstrip(b"=").decode("ascii")
            if not hmac.compare_digest(provided_signature, expected_signature):
                return None, "TOKEN_INVALID"
            padding = "=" * (-len(encoded_claims) % 4)
            parsed = json.loads(base64.urlsafe_b64decode(encoded_claims + padding))
            if (
                isinstance(header, dict)
                and header.get("alg") == "HS256"
                and header.get("typ") == "JWT"
                and isinstance(parsed, dict)
                and isinstance(parsed.get("exp"), int)
                and parsed.get("aud") == "new-mud-h5"
                and parsed["exp"] <= int(datetime.now(UTC).timestamp())
            ):
                return None, "TOKEN_EXPIRED"
        except IndexError, ValueError, TypeError, json.JSONDecodeError:
            pass
        return None, "TOKEN_INVALID"
    try:
        return resolve_active_auth_session(token), ""
    except AuthenticationFailed:
        # A signed token can still point to a revoked/expired session. Keep the
        # external distinction stable without exposing session existence.
        try:
            session = AuthSession.objects.select_related("game_account", "user").get(
                pk=uuid.UUID(str(claims["auth_session_id"]))
            )
            if (
                session.state != AuthSession.State.ACTIVE
                or session.absolute_expires_at
                <= timezone.now()
            ):
                return None, "SESSION_REVOKED"
            if session.game_account.lifecycle != GameAccount.Lifecycle.ACTIVE:
                return None, "SESSION_REVOKED"
        except AuthSession.DoesNotExist, KeyError, TypeError, ValueError:
            pass
        return None, "TOKEN_INVALID"


class GameConsumer(AsyncJsonWebsocketConsumer):
    """Runtime ConnectionSession and the connection-local protocol boundary."""

    async def connect(self) -> None:
        self.connection_session_id = uuid.uuid4()
        self.connection_state = "open"
        self.auth_session: AuthSession | None = None
        self._seq = 0
        self._terminals: dict[str, _Terminal] = {}
        await self.accept()

    def _envelope(
        self, *, message_type: str, payload: dict[str, Any], request_id: str | None = None
    ) -> dict[str, Any]:
        self._seq += 1
        result: dict[str, Any] = {
            "version": SUPPORTED_VERSION,
            "seq": self._seq,
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "type": message_type,
            "payload": payload,
        }
        if request_id is not None:
            result["request_id"] = request_id
        return result

    async def _failed(
        self, request_id: str, request_type: str, code: str, *, retryable: bool = False
    ) -> dict[str, Any]:
        payload = {
            "request_type": request_type,
            "error": {"code": code, "message": code, "retryable": retryable, "details": {}},
        }
        envelope = self._envelope(
            message_type="request.failed", payload=payload, request_id=request_id
        )
        await self.send_json(envelope)
        return envelope

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if not isinstance(content, dict):
            await self.close(code=4400)
            return
        request_id = content.get("request_id")
        request_type = content.get("type")
        if not isinstance(request_id, str) or REQUEST_ID_PATTERN.fullmatch(request_id) is None:
            await self.close(code=4400)
            return
        if set(content) != {"version", "request_id", "type", "payload"}:
            await self._failed(request_id, str(request_type or ""), "INVALID_ENVELOPE")
            return
        if content.get("version") != SUPPORTED_VERSION:
            await self._failed(request_id, str(request_type or ""), "UNSUPPORTED_PROTOCOL_VERSION")
            return
        if not isinstance(request_type, str):
            await self._failed(request_id, "", "INVALID_ENVELOPE")
            return
        payload = content.get("payload")
        if not isinstance(payload, dict):
            await self._failed(request_id, request_type, "PAYLOAD_INVALID")
            return

        digest = _request_hash(content)
        terminal = self._terminals.get(request_id)
        if terminal is not None:
            if terminal.request_hash != digest:
                await self._failed(request_id, request_type, "REQUEST_ID_CONFLICT")
            elif request_type == "session.authenticate" and not await self._binding_is_active():
                envelope = await self._failed(request_id, request_type, "SESSION_REVOKED")
                self._terminals[request_id] = _Terminal(digest, envelope)
            else:
                replay = dict(terminal.payload)
                replay["seq"] = self._seq + 1
                replay["ts"] = (
                    datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                )
                self._seq += 1
                await self.send_json(replay)
            return

        if request_type == "session.authenticate":
            await self._authenticate(request_id, payload, digest)
            return
        if request_type == "session.ping":
            terminal_payload = await self._ping(request_id, payload)
            self._terminals[request_id] = _Terminal(digest, terminal_payload)
            return
        if self.auth_session is None:
            envelope = await self._failed(request_id, request_type, "AUTH_REQUIRED")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if request_type in {
            "presence.enter",
            "presence.resume",
            "presence.recover",
            "presence.takeover",
            "state.sync",
            "action.invoke",
            "ui.actions.resolve",
            "presence.leave",
        }:
            envelope = await self._failed(request_id, request_type, "PRESENCE_REQUIRED")
        else:
            envelope = await self._failed(request_id, request_type, "REQUEST_TYPE_UNSUPPORTED")
        self._terminals[request_id] = _Terminal(digest, envelope)

    @database_sync_to_async
    def _binding_is_active(self) -> bool:
        if self.auth_session is None:
            return False
        session = AuthSession.objects.select_related("game_account", "user").filter(
            pk=self.auth_session.pk
        ).first()
        return bool(
            session
            and session.state == AuthSession.State.ACTIVE
            and session.absolute_expires_at > timezone.now()
            and session.user.is_active
            and session.game_account.lifecycle == GameAccount.Lifecycle.ACTIVE
        )

    async def _authenticate(self, request_id: str, payload: dict[str, Any], digest: str) -> None:
        if set(payload) != {"access_token"}:
            envelope = await self._failed(request_id, "session.authenticate", "PAYLOAD_INVALID")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if self.auth_session is not None:
            envelope = await self._failed(
                request_id, "session.authenticate", "ALREADY_AUTHENTICATED"
            )
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        session, error_code = await _resolve_session(payload.get("access_token"))
        if session is None:
            envelope = await self._failed(
                request_id, "session.authenticate", error_code or "TOKEN_INVALID"
            )
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        self.auth_session = session
        result = {
            "auth_session_id": str(session.pk),
            "game_account_id": str(session.game_account_id),
            "user_id": str(session.user_id),
            "state": "active",
        }
        envelope = self._envelope(
            message_type="request.succeeded",
            payload={"request_type": "session.authenticate", "result": result},
            request_id=request_id,
        )
        self._terminals[request_id] = _Terminal(digest, envelope)
        await self.send_json(envelope)
        await self.send_json(
            self._envelope(
                message_type="session.ready",
                payload={
                    "auth_session_id": str(session.pk),
                    "game_account_id": str(session.game_account_id),
                },
            )
        )

    async def _ping(self, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) - {"nonce"} or (
            "nonce" in payload and not isinstance(payload["nonce"], str)
        ):
            return await self._failed(request_id, "session.ping", "PAYLOAD_INVALID")
        envelope = self._envelope(
            message_type="request.succeeded",
            payload={
                "request_type": "session.ping",
                "result": {
                    "nonce": payload.get("nonce"),
                    "server_time": datetime.now(UTC)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                },
            },
            request_id=request_id,
        )
        await self.send_json(envelope)
        return envelope
