from __future__ import annotations

import ipaddress
import re
import secrets

from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import VerificationChallenge
from .rate_limits import RateLimitSubject, consume_rate_limit
from .services import (
    AuthenticationFailed,
    PasswordResetUnavailable,
    RefreshFailed,
    RegistrationInvalid,
    RegistrationUnavailable,
    VerificationCodeInvalid,
    login,
    logout,
    refresh,
    register,
    reset_password_with_verification,
)
from .verification import ContactInvalid
from .verification_config import VerificationServiceUnavailable
from .verification_requests import (
    ContactChannelUnavailable,
    VerificationRequestConflict,
    VerificationRequestInvalid,
    request_password_reset_verification,
    request_registration_verification,
)

ANONYMOUS_DEVICE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


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
    peer = str(request.META.get("REMOTE_ADDR") or "<unknown>")
    try:
        peer_address = ipaddress.ip_address(peer)
        trusted = any(
            peer_address in ipaddress.ip_network(network)
            for network in settings.AUTH_TRUSTED_PROXY_NETWORKS
        )
    except ValueError:
        return "<unknown>"
    if not trusted:
        return peer
    forwarded = [
        value.strip()
        for value in str(request.headers.get("X-Forwarded-For") or "").split(",")
        if value.strip()
    ]
    chain = [*forwarded, peer]
    for candidate in reversed(chain):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            return "<unknown>"
        if not any(
            address in ipaddress.ip_network(network)
            for network in settings.AUTH_TRUSTED_PROXY_NETWORKS
        ):
            return str(address)
    return peer


def _anonymous_device_id(request, *, cookie_name: str) -> str:
    candidate = request.COOKIES.get(cookie_name)
    if isinstance(candidate, str) and ANONYMOUS_DEVICE_PATTERN.fullmatch(candidate):
        return candidate
    return secrets.token_urlsafe(24)


def _set_anonymous_device_cookie(
    response: Response,
    device_id: str,
    *,
    cookie_name: str,
    max_age: int,
    path: str,
) -> None:
    response.set_cookie(
        cookie_name,
        device_id,
        max_age=max_age,
        path=path,
        secure=True,
        httponly=True,
        samesite="Strict",
    )


def _verification_device_id(request) -> str:
    return _anonymous_device_id(request, cookie_name="new_mud_verification_device")


def _set_verification_device_cookie(response: Response, device_id: str) -> None:
    _set_anonymous_device_cookie(
        response,
        device_id,
        cookie_name="new_mud_verification_device",
        max_age=settings.AUTH_VERIFICATION_DEVICE_MAX_AGE_SECONDS,
        path="/api/v1/auth/",
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def registration_verification_request_view(request):
    if not _origin_allowed(request):
        return _error("CONTACT_INVALID", status=403)
    device_id = _verification_device_id(request)
    if request.headers.get("Authorization"):
        response = _error("CONTACT_INVALID", status=400)
        _set_verification_device_cookie(response, device_id)
        return response
    try:
        result = request_registration_verification(
            channel=request.data.get("channel"),
            destination=request.data.get("destination"),
            idempotency_key=request.headers.get("Idempotency-Key"),
            client_ip=_client_ip(request),
            device_id=device_id,
        )
        response = _response(result.payload, status=result.status)
    except ContactChannelUnavailable:
        response = _error("CONTACT_CHANNEL_UNAVAILABLE", status=400)
    except ContactInvalid, VerificationRequestInvalid:
        response = _error("CONTACT_INVALID", status=400)
    except VerificationRequestConflict:
        response = _error("CONTACT_INVALID", status=409)
    except VerificationServiceUnavailable:
        response = _error("VERIFICATION_SERVICE_UNAVAILABLE", status=503)
    _set_verification_device_cookie(response, device_id)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    if not _origin_allowed(request):
        return _error("CONTACT_INVALID", status=403)
    device_id = _verification_device_id(request)
    if request.headers.get("Authorization"):
        response = _error("CONTACT_INVALID", status=400)
        _set_verification_device_cookie(response, device_id)
        return response
    try:
        result = request_password_reset_verification(
            channel=request.data.get("channel"),
            destination=request.data.get("destination"),
            idempotency_key=request.headers.get("Idempotency-Key"),
            client_ip=_client_ip(request),
            device_id=device_id,
        )
        response = _response(result.payload, status=result.status)
    except ContactChannelUnavailable:
        response = _error("CONTACT_CHANNEL_UNAVAILABLE", status=400)
    except ContactInvalid, VerificationRequestInvalid:
        response = _error("CONTACT_INVALID", status=400)
    except VerificationRequestConflict:
        response = _error("CONTACT_INVALID", status=409)
    except VerificationServiceUnavailable:
        response = _error("VERIFICATION_SERVICE_UNAVAILABLE", status=503)
    _set_verification_device_cookie(response, device_id)
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    if not _origin_allowed(request):
        return _error("PASSWORD_RESET_UNAVAILABLE", status=403)
    if request.headers.get("Authorization"):
        return _error("PASSWORD_RESET_UNAVAILABLE", status=400)
    channel = request.data.get("channel")
    if channel != VerificationChallenge.Channel.EMAIL:
        return _error("CONTACT_CHANNEL_UNAVAILABLE", status=400)
    try:
        reset_password_with_verification(
            channel=channel,
            destination=request.data.get("destination"),
            code=request.data.get("code"),
            new_password=request.data.get("new_password"),
        )
    except ContactInvalid:
        return _error("CONTACT_INVALID", status=400)
    except VerificationCodeInvalid:
        return _error("VERIFICATION_CODE_INVALID", status=400)
    except PasswordResetUnavailable:
        return _error("PASSWORD_RESET_UNAVAILABLE", status=400)
    except VerificationServiceUnavailable:
        return _error("VERIFICATION_SERVICE_UNAVAILABLE", status=503)
    response = Response(status=204)
    response["Cache-Control"] = "no-store"
    return response


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
            verification=request.data.get("verification"),
        )
    except RegistrationInvalid:
        return _error("REGISTRATION_INVALID", status=400)
    except VerificationCodeInvalid:
        return _error("VERIFICATION_CODE_INVALID", status=400)
    except RegistrationUnavailable:
        return _error("REGISTRATION_UNAVAILABLE", status=409)
    except VerificationServiceUnavailable:
        return _error("VERIFICATION_SERVICE_UNAVAILABLE", status=503)

    return _response(
        {
            "user_id": result.user_id,
            "game_account_id": result.game_account_id,
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
@authentication_classes([])
@permission_classes([AllowAny])
def recover_view(request):
    return _error("RECOVERY_CODE_RETIRED", status=410)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def recovery_code_rotate_view(request):
    return _error("RECOVERY_CODE_RETIRED", status=410)
