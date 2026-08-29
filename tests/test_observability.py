from __future__ import annotations

import json
import logging

from new_mud.observability import JsonFormatter


def test_json_formatter_emits_whitelisted_connection_fields_without_payloads() -> None:
    record = logging.LogRecord(
        name="new_mud.apps.identity.consumers",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="protocol failure",
        args=(),
        exc_info=None,
    )
    record.connection_session_id = "connection-1"
    record.connection_state = "closing"
    record.protocol_error_code = "INVALID_JSON_FRAME"
    record.payload = {"access_token": "must-not-be-formatted"}

    event = json.loads(JsonFormatter().format(record))

    assert event["connection_session_id"] == "connection-1"
    assert event["connection_state"] == "closing"
    assert event["protocol_error_code"] == "INVALID_JSON_FRAME"
    assert "must-not-be-formatted" not in json.dumps(event)
