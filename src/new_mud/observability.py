import json
import logging
from datetime import UTC, datetime

_SAFE_CONTEXT_FIELDS = (
    "auth_session_id",
    "client_capability_count",
    "client_capability_summary",
    "connection_session_id",
    "connection_state",
    "duration_ms",
    "error_code",
    "game_account_id",
    "instance_id",
    "online_auth_session_count",
    "online_connection_count",
    "previous_connection_state",
    "protocol_error_code",
    "reason_code",
    "remote_ip_summary",
    "request_id",
    "request_type",
    "trace_id",
    "user_agent_summary",
    "websocket_errors_total",
    "websocket_requests_total",
)


class JsonFormatter(logging.Formatter):
    """Small structured formatter that deliberately excludes request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _SAFE_CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, str | int | float | bool):
                event[field] = value
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))
