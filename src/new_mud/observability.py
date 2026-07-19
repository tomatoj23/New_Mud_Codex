import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Small structured formatter that deliberately excludes request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))
