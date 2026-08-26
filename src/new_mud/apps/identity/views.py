from __future__ import annotations

import re
import secrets

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .rate_limits import RateLimitSubject, consume_rate_limit
from .services import (
    AuthenticationFailed,
    RecoveryFailed,
    RefreshFailed,
    RegistrationInvalid,
    RegistrationUnavailable,
    login,
    logout,
    recover_password_with_code,
    refresh,
    register,
    rotate_recovery_code,
)

RECOVERY_DEVICE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def _response(payload: dict[str, object], *, status: int) -> Response:
    response = Response(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _error(code: str, *, status: int) -> Response:
    return _response({"error": {"code": code}}, status=status)


def _origin_allowed(request) -> bool:
    return request.headers.get("Origin") in settings.AUTH_ALLOWED_ORIGINS


def _account_rate_limit_subject(value: object) -> object:
    return value.lower() if isinstance(value, str) else "<invalid>"


def _client_ip(request) -> str:
    return str(request.META.get("REMOTE_ADDR") or "<unknown>")


def _authentication_request_allowed(
    request,
    *,
    namespace: str,
    account_limit: int,
    ip_limit: int,
) -> bool:
    return consume_rate_limit(
        namespace=namespace,
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        subjects=(
            RateLimitSubject(
                scope="account",
                value=_account_rate_limit_subject(request.data.get("username")),
                limit=account_limit,
            ),
            RateLimitSubject(scope="ip", value=_client_ip(request), limit=ip_limit),
        ),
    )


def _recovery_device_id(request) -> str:
    candidate = request.COOKIES.get("new_mud_recovery_device")
    if isinstance(candidate, str) and RECOVERY_DEVICE_PATTERN.fullmatch(candidate):
        return candidate
    return secrets.token_urlsafe(24)


def _set_recovery_device_cookie(response: Response, device_id: str) -> None:
    response.set_cookie(
        "new_mud_recovery_device",
        device_id,
        max_age=settings.AUTH_RECOVERY_DEVICE_MAX_AGE_SECONDS,
        path="/api/v1/auth/recover",
        secure=True,
        httponly=True,
        samesite="Strict",
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    if not _origin_allowed(request):
        return _error("REGISTRATION_UNAVAILABLE", status=403)
    if request.headers.get("Authorization"):
        return _error("REGISTRATION_INVALID", status=400)
    if not _authentication_request_allowed(
        request,
        namespace="registration",
        account_limit=settings.AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT,
        ip_limit=settings.AUTH_REGISTRATION_RATE_LIMIT_IP,
    ):
        return _error("REGISTRATION_UNAVAILABLE", status=429)
    try:
        result = register(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
    except RegistrationInvalid:
        return _error("REGISTRATION_INVALID", status=400)
    except RegistrationUnavailable:
        return _error("REGISTRATION_UNAVAILABLE", status=409)

    return _response(
        {
            "user_id": result.user_id,
            "game_account_id": result.game_account_id,
            "recovery_code": result.recovery_code,
        },
        status=201,
    )


def _set_refresh_cookie(response: Response, token: str, *, max_age: int) -> None:
    response.set_cookie(
        "new_mud_refresh",
        token,
        max_age=max_age,
        path="/api/v1/auth/",
        secure=True,
        httponly=True,
        samesite="Strict",
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    if not _origin_allowed(request) or request.headers.get("Authorization"):
        return _error("AUTH_CREDENTIALS_INVALID", status=401)
    if not _authentication_request_allowed(
        request,
        namespace="login",
        account_limit=settings.AUTH_LOGIN_RATE_LIMIT_ACCOUNT,
        ip_limit=settings.AUTH_LOGIN_RATE_LIMIT_IP,
    ):
        return _error("AUTH_CREDENTIALS_INVALID", status=429)
    try:
        result = login(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
    except AuthenticationFailed:
        return _error("AUTH_CREDENTIALS_INVALID", status=401)

    response = _response(
        {
            "access_token": result.access_token,
            "token_type": "Bearer",
            "expires_in": result.expires_in,
            "auth_session_id": result.auth_session_id,
            "game_account_id": result.game_account_id,
        },
        status=200,
    )
    _set_refresh_cookie(response, result.refresh_token, max_age=result.refresh_max_age)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_view(request):
    if not _origin_allowed(request):
        return _error("REFRESH_UNAVAILABLE", status=403)
    if request.headers.get("Authorization") or request.data != {}:
        return _error("REFRESH_UNAVAILABLE", status=400)
    try:
        result = refresh(
            refresh_token=request.COOKIES.get("new_mud_refresh"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except RefreshFailed as error:
        status = 400 if error.code == "REFRESH_IDEMPOTENCY_KEY_INVALID" else 401
        if error.code in {
            "REFRESH_IDEMPOTENCY_CONFLICT",
            "REFRESH_REQUEST_SUPERSEDED",
        }:
            status = 409
        return _error(error.code, status=status)

    response = _response(
        {
            "access_token": result.access_token,
            "token_type": "Bearer",
            "expires_in": result.expires_in,
            "auth_session_id": result.auth_session_id,
            "game_account_id": result.game_account_id,
        },
        status=200,
    )
    _set_refresh_cookie(response, result.refresh_token, max_age=result.refresh_max_age)
    return response


def _clear_refresh_cookie(response: Response) -> None:
    response.set_cookie(
        "new_mud_refresh",
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/api/v1/auth/",
        secure=True,
        httponly=True,
        samesite="Strict",
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    if not _origin_allowed(request) or request.data != {}:
        return _error("AUTH_CREDENTIALS_INVALID", status=403)
    logout(
        refresh_token=request.COOKIES.get("new_mud_refresh"),
        authorization=request.headers.get("Authorization"),
    )
    response = Response(status=204)
    response["Cache-Control"] = "no-store"
    _clear_refresh_cookie(response)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def recover_view(request):
    if not _origin_allowed(request) or request.headers.get("Authorization"):
        return _error("ACCOUNT_RECOVERY_UNAVAILABLE", status=403)
    device_id = _recovery_device_id(request)
    allowed = consume_rate_limit(
        namespace="recovery",
        window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        subjects=(
            RateLimitSubject(
                scope="account",
                value=_account_rate_limit_subject(request.data.get("username")),
                limit=settings.AUTH_RECOVERY_RATE_LIMIT_ACCOUNT,
            ),
            RateLimitSubject(
                scope="ip",
                value=_client_ip(request),
                limit=settings.AUTH_RECOVERY_RATE_LIMIT_IP,
            ),
            RateLimitSubject(
                scope="device",
                value=device_id,
                limit=settings.AUTH_RECOVERY_RATE_LIMIT_DEVICE,
            ),
        ),
    )
    if not allowed:
        response = _error("RECOVERY_RATE_LIMITED", status=429)
        _set_recovery_device_cookie(response, device_id)
        return response
    try:
        replacement_code = recover_password_with_code(
            username=request.data.get("username"),
            recovery_code=request.data.get("recovery_code"),
            new_password=request.data.get("new_password"),
        )
    except RecoveryFailed as error:
        response = _error(error.code, status=400)
        _set_recovery_device_cookie(response, device_id)
        return response
    response = _response({"recovery_code": replacement_code}, status=200)
    _set_recovery_device_cookie(response, device_id)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def recovery_code_rotate_view(request):
    if not _origin_allowed(request) or request.data != {}:
        return _error("SESSION_REVOKED", status=403)
    try:
        replacement_code = rotate_recovery_code(authorization=request.headers.get("Authorization"))
    except RecoveryFailed as error:
        return _error(error.code, status=401)
    response = _response({"recovery_code": replacement_code}, status=200)
    _clear_refresh_cookie(response)
    return response
