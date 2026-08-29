from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)


def _short_summary(value: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


@dataclass(frozen=True)
class ConnectionClientContext:
    """Connection-local client facts with a safe structured-log projection."""

    remote_ip_summary: str
    user_agent_summary: str
    capabilities: tuple[str, ...]
    capability_summary: str

    @classmethod
    def from_scope(cls, scope: Mapping[str, Any]) -> ConnectionClientContext:
        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
            if isinstance(key, bytes) and isinstance(value, bytes)
        }
        client = scope.get("client")
        remote_ip = client[0] if isinstance(client, tuple) and client else "unknown"
        user_agent = headers.get(b"user-agent", b"").decode("utf-8", errors="replace")
        subprotocols = scope.get("subprotocols", [])
        capabilities = tuple(
            sorted({value[:64] for value in subprotocols[:32] if isinstance(value, str) and value})
        )
        return cls(
            remote_ip_summary=_short_summary(str(remote_ip)),
            user_agent_summary=_short_summary(user_agent),
            capabilities=capabilities,
            capability_summary=_short_summary("\0".join(capabilities)),
        )

    def audit_fields(self) -> dict[str, str | int]:
        return {
            "remote_ip_summary": self.remote_ip_summary,
            "user_agent_summary": self.user_agent_summary,
            "client_capability_count": len(self.capabilities),
            "client_capability_summary": self.capability_summary,
        }


def auth_session_group_name(auth_session_id: uuid.UUID | str) -> str:
    return f"auth-session.{uuid.UUID(str(auth_session_id)).hex}"


def notify_auth_session_invalidated(
    *,
    auth_session_id: uuid.UUID | str,
    reason_code: str,
) -> None:
    """Close live, in-process ConnectionSessions after an AuthSession commit."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.error(
            "cannot notify live ConnectionSessions without a channel layer",
            extra={
                "auth_session_id": str(auth_session_id),
                "reason_code": reason_code,
            },
        )
        return
    try:
        async_to_sync(channel_layer.group_send)(
            auth_session_group_name(auth_session_id),
            {
                "type": "auth_session.invalidated",
                "reason_code": reason_code,
            },
        )
    except Exception:
        # The database remains authoritative. Every authenticated ConnectionSession
        # also revalidates it on a bounded timer, so channel loss can delay but cannot
        # indefinitely prevent runtime convergence.
        logger.exception(
            "failed to notify live ConnectionSessions after AuthSession invalidation",
            extra={
                "auth_session_id": str(auth_session_id),
                "reason_code": reason_code,
            },
        )
