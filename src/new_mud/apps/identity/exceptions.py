from __future__ import annotations

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler as default_exception_handler

AUTH_ENDPOINT_ERROR_CODES = {
    "/api/v1/auth/registration-verification/request": "CONTACT_INVALID",
    "/api/v1/auth/password-reset/request": "CONTACT_INVALID",
    "/api/v1/auth/password-reset/confirm": "PASSWORD_RESET_UNAVAILABLE",
    "/api/v1/auth/register": "REGISTRATION_INVALID",
    "/api/v1/auth/login": "AUTH_CREDENTIALS_INVALID",
    "/api/v1/auth/refresh": "REFRESH_UNAVAILABLE",
    "/api/v1/auth/logout": "AUTH_CREDENTIALS_INVALID",
    "/api/v1/auth/recover": "RECOVERY_CODE_RETIRED",
    "/api/v1/auth/recovery-code/rotate": "RECOVERY_CODE_RETIRED",
}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = default_exception_handler(exc, context)
    request = context.get("request")
    path = getattr(request, "path_info", None)
    if response is not None and response.status_code >= 400 and path in AUTH_ENDPOINT_ERROR_CODES:
        response.data = {"error": {"code": AUTH_ENDPOINT_ERROR_CODES[path]}}
    return response
