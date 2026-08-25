from __future__ import annotations

from django.conf import settings
from django.db import connections
from django.db.utils import DatabaseError

from new_mud.apps.content.runtime import ContentRuntimeStatus, get_content_runtime
from new_mud.contracts.generated import RegistryErrorsContentRelease
from new_mud.process_guard import ProcessLeaseError, acquire_single_process_lease


def probe_readiness() -> tuple[int, dict[str, object]]:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return 503, {"status": "not_ready", "database": "unavailable"}
    try:
        acquire_single_process_lease()
    except ProcessLeaseError as error:
        return 503, {
            "status": "not_ready",
            "database": "ready",
            "process": "lease_unavailable",
            "error": {
                "code": RegistryErrorsContentRelease.CONTENT_RELEASE_CONFLICT,
                "message": str(error),
            },
        }
    content = get_content_runtime(settings.CONTENT_INSTANCE_ID).readiness()
    payload: dict[str, object] = {
        "status": "ok" if content.status is ContentRuntimeStatus.READY else "not_ready",
        "database": "ready",
        "content": content.as_payload(),
    }
    return (200 if content.status is ContentRuntimeStatus.READY else 503), payload
