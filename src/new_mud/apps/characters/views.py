from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from new_mud.apps.identity.services import AuthenticationFailed, resolve_active_auth_session

from .services import (
    CharacterCreationLimitReached,
    CharacterCreationUnavailable,
    CharacterDisplayNameInvalid,
    CharacterProfileInvalid,
    create_character,
    get_character_roster,
    list_active_character_creation_profiles,
)


def _response(payload: dict[str, object], *, status: int) -> Response:
    response = Response(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _authenticated(request):
    authorization = request.headers.get("Authorization")
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise AuthenticationFailed
    return resolve_active_auth_session(authorization.removeprefix("Bearer "))


@api_view(["GET"])
@permission_classes([AllowAny])
def character_creation_profile_list_view(request):
    try:
        _authenticated(request)
    except AuthenticationFailed:
        return _response({"error": {"code": "AUTH_REQUIRED"}}, status=401)
    profiles = list_active_character_creation_profiles()
    return _response({"profiles": [profile.as_payload() for profile in profiles]}, status=200)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def character_list_view(request):
    try:
        auth_session = _authenticated(request)
    except AuthenticationFailed:
        return _response({"error": {"code": "AUTH_REQUIRED"}}, status=401)
    if request.method == "GET":
        roster = get_character_roster(game_account_id=auth_session.game_account_id)
        return _response(roster.as_payload(), status=200)
    if set(request.data) != {
        "creation_profile_key",
        "creation_profile_version",
        "display_name",
        "gender",
        "pronouns",
    }:
        return _response({"error": {"code": "CHARACTER_PROFILE_INVALID"}}, status=400)
    try:
        payload = create_character(
            auth_session=auth_session,
            idempotency_key=request.headers.get("Idempotency-Key"),
            creation_profile_key=request.data.get("creation_profile_key"),
            creation_profile_version=request.data.get("creation_profile_version"),
            display_name=request.data.get("display_name"),
            gender=request.data.get("gender"),
            pronouns=request.data.get("pronouns"),
        )
    except CharacterProfileInvalid:
        return _response({"error": {"code": "CHARACTER_PROFILE_INVALID"}}, status=400)
    except CharacterDisplayNameInvalid:
        return _response({"error": {"code": "CHARACTER_DISPLAY_NAME_INVALID"}}, status=400)
    except CharacterCreationLimitReached:
        return _response({"error": {"code": "CHARACTER_ALREADY_EXISTS"}}, status=409)
    except CharacterCreationUnavailable:
        return _response({"error": {"code": "CHARACTER_CREATION_UNAVAILABLE"}}, status=409)
    return _response(payload, status=201)
