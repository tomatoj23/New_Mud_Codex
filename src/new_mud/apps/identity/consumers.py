from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import rfc8785
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from new_mud.contracts.generated import (
    ProtocolApplicationCloseCodes,
    ProtocolProtocolVersions,
)
from new_mud.contracts.generated import (
    SessionStatesConnectionSessionStates as ConnectionSessionState,
)

from .connection_sessions import ConnectionClientContext, auth_session_group_name
from .game_session_metrics import game_websocket_metrics
from .models import AuthSession
from .services import (
    AuthenticationFailed,
    auth_session_is_active,
    resolve_active_auth_session,
)
from .tokens import AccessTokenDecodeStatus, decode_access_token_result

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SUPPORTED_VERSION = ProtocolProtocolVersions.VALUE_1.value
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Terminal:
    request_hash: str
    envelope: dict[str, Any]
    requires_active_auth_binding: bool = False


def _request_hash(message: dict[str, Any]) -> str:
    canonical = rfc8785.dumps(
        cast(
            Any,
            {
                "version": message.get("version"),
                "type": message.get("type"),
                "payload": message.get("payload"),
            },
        )
    )
    return hashlib.sha256(canonical).hexdigest()


def _invalid_request_hash(message: dict[str, Any]) -> str:
    """Keep malformed requests locally replayable even when JCS rejects their values."""
    try:
        serialized = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except ValueError:
        serialized = repr(message)
    return f"invalid:{hashlib.sha256(serialized.encode()).hexdigest()}"


@database_sync_to_async
def _resolve_session(token: object) -> tuple[AuthSession | None, str]:
    if not isinstance(token, str):
        return None, "TOKEN_INVALID"
    decoded = decode_access_token_result(token)
    if decoded.status == AccessTokenDecodeStatus.EXPIRED:
        return None, "TOKEN_EXPIRED"
    claims = decoded.claims
    if decoded.status != AccessTokenDecodeStatus.VALID or claims is None:
        return None, "TOKEN_INVALID"
    try:
        session = resolve_active_auth_session(token)
        if session.game_account.instance_id != settings.CONTENT_INSTANCE_ID:
            return None, "TOKEN_INVALID"
        return session, ""
    except AuthenticationFailed:
        # A signed token can still point to a revoked/expired session. Keep the
        # external distinction stable without exposing session existence.
        try:
            session = AuthSession.objects.select_related("game_account", "user").get(
                pk=uuid.UUID(str(claims["auth_session_id"]))
            )
            if not auth_session_is_active(session):
                return None, "SESSION_REVOKED"
        except AuthSession.DoesNotExist, KeyError, TypeError, ValueError:
            pass
        return None, "TOKEN_INVALID"


class GameConsumer(AsyncJsonWebsocketConsumer):
    """Runtime ConnectionSession and the connection-local protocol boundary."""

    async def connect(self) -> None:
        self.connection_session_id = uuid.uuid4()
        self.auth_session: AuthSession | None = None
        self._auth_session_group: str | None = None
        self._seq = 0
        self._terminals: dict[str, _Terminal] = {}
        self._rate_window_started_at = time.monotonic()
        self._requests_in_window = 0
        self._connection_metric_open = True
        self._metric_auth_session_id: str | None = None
        self._auth_revalidation_task: asyncio.Task[None] | None = None
        self.client_context = ConnectionClientContext.from_scope(self.scope)
        self._client_audit_context = self.client_context.audit_fields()
        metrics = game_websocket_metrics.connection_opened()
        self._transition_connection_state(
            ConnectionSessionState.OPENING,
            reason_code="SOCKET_CONNECTING",
            metric_context={
                "online_connection_count": metrics.online_connections,
                "online_auth_session_count": metrics.online_auth_sessions,
            },
        )
        await self.accept()
        self._transition_connection_state(
            ConnectionSessionState.ACTIVE,
            reason_code="SOCKET_ACCEPTED",
        )

    def _transition_connection_state(
        self,
        state: ConnectionSessionState,
        *,
        reason_code: str,
        metric_context: dict[str, int] | None = None,
    ) -> None:
        previous = getattr(self, "connection_state", None)
        self.connection_state = state
        logger.info(
            "game ConnectionSession state changed",
            extra={
                "connection_session_id": str(self.connection_session_id),
                "connection_state": state.value,
                "previous_connection_state": (
                    previous.value if isinstance(previous, ConnectionSessionState) else None
                ),
                "reason_code": reason_code,
                **getattr(self, "_client_audit_context", {}),
                **(metric_context or {}),
            },
        )

    def _terminal_capacity_available(self) -> bool:
        return len(self._terminals) < settings.GAME_WEBSOCKET_TERMINAL_LIMIT

    def _request_allowed(self) -> bool:
        now = time.monotonic()
        if (
            now - self._rate_window_started_at
            >= settings.GAME_WEBSOCKET_REQUEST_RATE_WINDOW_SECONDS
        ):
            self._rate_window_started_at = now
            self._requests_in_window = 0
        if self._requests_in_window >= settings.GAME_WEBSOCKET_REQUEST_RATE_LIMIT:
            return False
        self._requests_in_window += 1
        return True

    async def _close_rate_limited_connection(
        self,
        *,
        request_id: str,
        request_type: str,
    ) -> None:
        duration_ms = (time.perf_counter() - self._request_started_at) * 1000
        metrics = game_websocket_metrics.request_finished(
            duration_ms=duration_ms,
            failed=True,
        )
        logger.warning(
            "closing game WebSocket after connection request rate limit",
            extra={
                "connection_session_id": str(self.connection_session_id),
                "request_id": request_id,
                "request_type": request_type,
                "duration_ms": round(duration_ms, 3),
                "error_code": "RATE_LIMITED",
                "online_connection_count": metrics.online_connections,
                "online_auth_session_count": metrics.online_auth_sessions,
                "websocket_requests_total": metrics.requests_total,
                "websocket_errors_total": metrics.request_errors_total,
            },
        )
        self._transition_connection_state(
            ConnectionSessionState.CLOSING,
            reason_code="RATE_LIMITED",
        )
        await self.close(code=1008)

    async def _reject_rate_limited_request(
        self,
        *,
        request_id: str,
        request_type: str,
        digest: str,
    ) -> None:
        envelope = await self._failed(
            request_id,
            request_type,
            "RATE_LIMITED",
            retryable=True,
        )
        if self._terminal_capacity_available():
            self._terminals[request_id] = _Terminal(digest, envelope)
        self._transition_connection_state(
            ConnectionSessionState.CLOSING,
            reason_code="RATE_LIMITED",
        )
        await self.close(code=1008)

    def _record_terminal(self, envelope: dict[str, Any]) -> None:
        failed = envelope["type"] == "request.failed"
        duration_ms = (time.perf_counter() - self._request_started_at) * 1000
        payload = envelope["payload"]
        metrics = game_websocket_metrics.request_finished(
            duration_ms=duration_ms,
            failed=failed,
        )
        logger.info(
            "game WebSocket request completed",
            extra={
                "connection_session_id": str(self.connection_session_id),
                "request_id": envelope["request_id"],
                "request_type": payload["request_type"],
                "duration_ms": round(duration_ms, 3),
                "error_code": (payload.get("error", {}).get("code") if failed else None),
                "online_connection_count": metrics.online_connections,
                "online_auth_session_count": metrics.online_auth_sessions,
                "websocket_requests_total": metrics.requests_total,
                "websocket_errors_total": metrics.request_errors_total,
            },
        )

    async def _send_terminal(self, envelope: dict[str, Any]) -> None:
        await self.send_json(envelope)
        self._record_terminal(envelope)

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        if bytes_data is not None:
            await self._close_protocol_error("BINARY_FRAME_UNSUPPORTED")
            return
        if text_data is None:
            await self._close_protocol_error("TEXT_FRAME_REQUIRED")
            return
        try:
            content = await self.decode_json(text_data)
        except json.JSONDecodeError, TypeError, ValueError:
            await self._close_protocol_error("INVALID_JSON_FRAME")
            return
        await self.receive_json(content, **kwargs)

    async def _close_protocol_error(self, error_code: str) -> None:
        if self.connection_state not in {
            ConnectionSessionState.CLOSING,
            ConnectionSessionState.CLOSED,
        }:
            self._transition_connection_state(
                ConnectionSessionState.CLOSING,
                reason_code="PROTOCOL_ERROR",
            )
        metrics = game_websocket_metrics.request_finished(duration_ms=0, failed=True)
        logger.warning(
            "closing game websocket after protocol error",
            extra={
                "protocol_error_code": error_code,
                "connection_session_id": str(self.connection_session_id),
                "online_connection_count": metrics.online_connections,
                "online_auth_session_count": metrics.online_auth_sessions,
                "websocket_requests_total": metrics.requests_total,
                "websocket_errors_total": metrics.request_errors_total,
            },
        )
        await self.close(code=ProtocolApplicationCloseCodes.VALUE_4400)

    async def disconnect(self, close_code: int) -> None:
        if self.connection_state != ConnectionSessionState.CLOSING:
            self._transition_connection_state(
                ConnectionSessionState.CLOSING,
                reason_code="SOCKET_DISCONNECTED",
            )
        self._cancel_auth_revalidation()
        if self._auth_session_group is not None:
            await self.channel_layer.group_discard(
                self._auth_session_group,
                self.channel_name,
            )
            self._auth_session_group = None
        self._unbind_auth_session_metric()
        self.auth_session = None
        self._terminals.clear()
        metrics = game_websocket_metrics.snapshot()
        if self._connection_metric_open:
            self._connection_metric_open = False
            metrics = game_websocket_metrics.connection_closed()
        self._transition_connection_state(
            ConnectionSessionState.CLOSED,
            reason_code=f"SOCKET_CLOSED_{close_code}",
            metric_context={
                "online_connection_count": metrics.online_connections,
                "online_auth_session_count": metrics.online_auth_sessions,
            },
        )

    async def auth_session_invalidated(self, event: dict[str, Any]) -> None:
        reason_code = event.get("reason_code")
        if not isinstance(reason_code, str):
            reason_code = "SESSION_REVOKED"
        if self.connection_state not in {
            ConnectionSessionState.CLOSING,
            ConnectionSessionState.CLOSED,
        }:
            self._transition_connection_state(
                ConnectionSessionState.CLOSING,
                reason_code=reason_code,
            )
        self._cancel_auth_revalidation()
        self._unbind_auth_session_metric()
        self.auth_session = None
        self._terminals.clear()
        await self.close(code=1000)

    def _cancel_auth_revalidation(self) -> None:
        task = self._auth_revalidation_task
        self._auth_revalidation_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _start_auth_revalidation(self) -> None:
        self._cancel_auth_revalidation()
        self._auth_revalidation_task = asyncio.create_task(
            self._revalidate_bound_auth_session(),
            name=f"auth-session-revalidation-{self.connection_session_id}",
        )

    async def _revalidate_bound_auth_session(self) -> None:
        try:
            while self.auth_session is not None:
                await asyncio.sleep(settings.GAME_WEBSOCKET_AUTH_REVALIDATION_INTERVAL_SECONDS)
                if not await self._binding_is_active():
                    await self.auth_session_invalidated({"reason_code": "SESSION_REVOKED"})
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "failed to revalidate a bound game AuthSession; closing fail-safe",
                extra={
                    "connection_session_id": str(self.connection_session_id),
                    "auth_session_id": (
                        str(self.auth_session.pk) if self.auth_session is not None else None
                    ),
                    "reason_code": "AUTH_SESSION_REVALIDATION_FAILED",
                },
            )
            await self.auth_session_invalidated({"reason_code": "AUTH_SESSION_REVALIDATION_FAILED"})

    def _bind_auth_session_metric(self, auth_session_id: uuid.UUID) -> None:
        value = str(auth_session_id)
        if self._metric_auth_session_id != value:
            self._metric_auth_session_id = value
            metrics = game_websocket_metrics.auth_session_bound(value)
            logger.info(
                "game WebSocket AuthSession binding changed",
                extra={
                    "auth_session_id": value,
                    "connection_session_id": str(self.connection_session_id),
                    "online_connection_count": metrics.online_connections,
                    "online_auth_session_count": metrics.online_auth_sessions,
                    "reason_code": "AUTH_SESSION_BOUND",
                },
            )

    def _unbind_auth_session_metric(self) -> None:
        if self._metric_auth_session_id is not None:
            auth_session_id = self._metric_auth_session_id
            metrics = game_websocket_metrics.auth_session_unbound(auth_session_id)
            self._metric_auth_session_id = None
            logger.info(
                "game WebSocket AuthSession binding changed",
                extra={
                    "auth_session_id": auth_session_id,
                    "connection_session_id": str(self.connection_session_id),
                    "online_connection_count": metrics.online_connections,
                    "online_auth_session_count": metrics.online_auth_sessions,
                    "reason_code": "AUTH_SESSION_UNBOUND",
                },
            )

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
        await self._send_terminal(envelope)
        return envelope

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if not isinstance(content, dict):
            await self._close_protocol_error("INVALID_ENVELOPE")
            return
        request_id = content.get("request_id")
        if not isinstance(request_id, str) or REQUEST_ID_PATTERN.fullmatch(request_id) is None:
            await self._close_protocol_error("REQUEST_ID_INVALID")
            return
        request_type_value = content.get("type")
        request_type = request_type_value if isinstance(request_type_value, str) else ""
        self._request_started_at = time.perf_counter()
        canonicalization_failed = False
        try:
            digest = _request_hash(content)
        except rfc8785.CanonicalizationError:
            digest = _invalid_request_hash(content)
            canonicalization_failed = True
        terminal = self._terminals.get(request_id)
        if not self._request_allowed():
            if terminal is not None:
                await self._close_rate_limited_connection(
                    request_id=request_id,
                    request_type=request_type,
                )
            else:
                await self._reject_rate_limited_request(
                    request_id=request_id,
                    request_type=request_type,
                    digest=digest,
                )
            return
        if terminal is not None:
            if terminal.request_hash != digest:
                await self._failed(request_id, request_type, "REQUEST_ID_CONFLICT")
            elif terminal.requires_active_auth_binding and not await self._binding_is_active():
                await self._failed(request_id, request_type, "SESSION_REVOKED")
            else:
                replay = dict(terminal.envelope)
                replay["seq"] = self._seq + 1
                replay["ts"] = (
                    datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                )
                self._seq += 1
                await self._send_terminal(replay)
            return
        if not self._terminal_capacity_available():
            await self._reject_rate_limited_request(
                request_id=request_id,
                request_type=request_type,
                digest=digest,
            )
            return
        if set(content) != {"version", "request_id", "type", "payload"}:
            envelope = await self._failed(request_id, request_type, "INVALID_ENVELOPE")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if canonicalization_failed:
            envelope = await self._failed(request_id, request_type, "INVALID_ENVELOPE")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if content.get("version") != SUPPORTED_VERSION:
            envelope = await self._failed(
                request_id,
                request_type,
                "UNSUPPORTED_PROTOCOL_VERSION",
            )
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if not isinstance(request_type_value, str):
            envelope = await self._failed(request_id, "", "INVALID_ENVELOPE")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        payload = content.get("payload")
        if not isinstance(payload, dict):
            envelope = await self._failed(request_id, request_type, "PAYLOAD_INVALID")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return

        if request_type == "session.authenticate":
            await self._authenticate(request_id, payload, digest)
            return
        if request_type == "session.ping":
            terminal_payload = await self._ping(request_id, payload)
            self._terminals[request_id] = _Terminal(digest, terminal_payload)
            return
        if self.auth_session is not None and not await self._binding_is_active():
            envelope = await self._failed(request_id, request_type, "SESSION_REVOKED")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if self.auth_session is None:
            envelope = await self._failed(request_id, request_type, "AUTH_REQUIRED")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if request_type in {
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
        session = (
            AuthSession.objects.select_related("game_account", "user")
            .filter(pk=self.auth_session.pk)
            .first()
        )
        return bool(
            session
            and auth_session_is_active(
                session,
                instance_id=settings.CONTENT_INSTANCE_ID,
            )
        )

    async def _authenticate(self, request_id: str, payload: dict[str, Any], digest: str) -> None:
        if set(payload) != {"access_token"} or not isinstance(payload["access_token"], str):
            envelope = await self._failed(request_id, "session.authenticate", "PAYLOAD_INVALID")
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        if self.auth_session is not None:
            error_code = (
                "ALREADY_AUTHENTICATED" if await self._binding_is_active() else "SESSION_REVOKED"
            )
            envelope = await self._failed(request_id, "session.authenticate", error_code)
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
        self._auth_session_group = auth_session_group_name(session.pk)
        await self.channel_layer.group_add(
            self._auth_session_group,
            self.channel_name,
        )
        if not await self._binding_is_active():
            await self.channel_layer.group_discard(
                self._auth_session_group,
                self.channel_name,
            )
            self._auth_session_group = None
            self.auth_session = None
            envelope = await self._failed(
                request_id,
                "session.authenticate",
                "SESSION_REVOKED",
            )
            self._terminals[request_id] = _Terminal(digest, envelope)
            return
        self._bind_auth_session_metric(session.pk)
        self._start_auth_revalidation()
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
        self._terminals[request_id] = _Terminal(
            digest,
            envelope,
            requires_active_auth_binding=True,
        )
        await self._send_terminal(envelope)
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
        await self._send_terminal(envelope)
        return envelope
