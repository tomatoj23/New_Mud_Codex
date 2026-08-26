from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from new_mud.apps.identity.models import (
    AuthSession,
    GameAccount,
    RecoveryCodeCredential,
    RefreshRequestTerminalRecord,
    RefreshTokenCredential,
    RefreshTokenFamily,
    SecurityAuditEvent,
)

pytestmark = pytest.mark.django_db(transaction=True)


def auth_post(
    client,
    route_name: str,
    payload: dict[str, object],
    *,
    remote_addr: str = "127.0.0.1",
    **headers,
):
    return client.post(
        reverse(route_name),
        payload,
        content_type="application/json",
        secure=True,
        REMOTE_ADDR=remote_addr,
        headers={"origin": "https://testserver", **headers},
    )


@pytest.fixture(autouse=True)
def clear_auth_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


def login_in_additional_instance(client, *, username: str, password: str):
    user = get_user_model().objects.get(username=username)
    GameAccount.objects.create(user=user, instance_id="other-instance")
    with override_settings(CONTENT_INSTANCE_ID="other-instance"):
        return auth_post(
            client,
            "auth-login",
            {"username": username, "password": password},
        )


def test_registration_creates_identity_without_authentication(client) -> None:
    response = auth_post(
        client,
        "auth-register",
        {"username": "New_Player", "password": "safe-example-passphrase-42"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"user_id", "game_account_id", "recovery_code"}
    assert payload["recovery_code"]
    assert response.headers["Cache-Control"] == "no-store"
    assert "new_mud_refresh" not in response.cookies

    user = get_user_model().objects.get(pk=payload["user_id"])
    assert user.username == "new_player"
    assert user.check_password("safe-example-passphrase-42")
    account = GameAccount.objects.get(pk=payload["game_account_id"])
    assert account.user_id == user.pk

    recovery = RecoveryCodeCredential.objects.get(game_account=account)
    assert recovery.code_hash != payload["recovery_code"]
    assert recovery.check_code(payload["recovery_code"])
    assert AuthSession.objects.count() == 0
    assert RefreshTokenFamily.objects.count() == 0
    assert RefreshTokenCredential.objects.count() == 0


def test_login_creates_one_session_family_and_protected_refresh_cookie(client) -> None:
    registration = auth_post(
        client,
        "auth-register",
        {"username": "login_player", "password": "safe-example-passphrase-42"},
    )
    assert registration.status_code == 201

    response = auth_post(
        client,
        "auth-login",
        {"username": "LOGIN_PLAYER", "password": "safe-example-passphrase-42"},
        **{"user-agent": "browser-fingerprint-must-not-be-device-id"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "access_token",
        "token_type",
        "expires_in",
        "auth_session_id",
        "game_account_id",
    }
    assert payload["token_type"] == "Bearer"
    assert payload["expires_in"] == 900
    assert "refresh" not in payload
    assert response.headers["Cache-Control"] == "no-store"

    cookie = response.cookies["new_mud_refresh"]
    assert cookie.value
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["secure"] is True
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert not cookie["domain"]
    assert 0 < int(cookie["max-age"]) <= 30 * 24 * 60 * 60

    session = AuthSession.objects.get(pk=payload["auth_session_id"])
    family = RefreshTokenFamily.objects.get(auth_session=session)
    credential = RefreshTokenCredential.objects.get(family=family)
    assert session.refresh_family_id == family.pk
    assert family.current_generation == credential.generation == 1
    assert session.device_id != "browser-fingerprint-must-not-be-device-id"
    assert cookie.value not in credential.token_hash


def test_login_reports_access_lifetime_from_response_time(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "delayed_login", "password": "safe-example-passphrase-42"},
    )
    issued_at = datetime(2026, 8, 26, 0, 0, tzinfo=UTC)
    response_at = issued_at + timedelta(minutes=5)

    with patch(
        "new_mud.apps.identity.services.timezone.now",
        side_effect=(issued_at, issued_at, issued_at, response_at),
    ):
        response = auth_post(
            client,
            "auth-login",
            {"username": "delayed_login", "password": "safe-example-passphrase-42"},
        )

    assert response.status_code == 200
    assert response.json()["expires_in"] == 600


def test_refresh_rotates_the_same_family_to_the_next_generation(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "refresh_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "refresh_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]

    response = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "refresh-basic-1"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "access_token",
        "token_type",
        "expires_in",
        "auth_session_id",
        "game_account_id",
    }
    assert response.json()["auth_session_id"] == session_id
    assert "refresh" not in response.json()
    assert response.headers["Cache-Control"] == "no-store"
    successor_token = response.cookies["new_mud_refresh"].value
    assert successor_token != predecessor_token

    family = RefreshTokenFamily.objects.get(auth_session_id=session_id)
    assert family.current_generation == 2
    assert list(family.credentials.order_by("generation").values_list("generation", "state")) == [
        (1, "used"),
        (2, "active"),
    ]


def test_refresh_replay_with_a_different_key_revokes_family_and_session(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "replay_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "replay_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]
    first_refresh = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "refresh-logical-1"},
    )
    assert first_refresh.status_code == 200

    client.cookies["new_mud_refresh"] = predecessor_token
    replay = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "attacker-replay-2"},
    )

    assert replay.status_code == 401
    assert replay.json() == {"error": {"code": "SESSION_REVOKED"}}
    session = AuthSession.objects.get(pk=session_id)
    family = RefreshTokenFamily.objects.get(auth_session=session)
    assert session.state == "revoked"
    assert family.state == "revoked"
    assert not family.credentials.filter(state="active").exists()
    audit = SecurityAuditEvent.objects.get(reason_code="REFRESH_TOKEN_REPLAYED")
    assert audit.auth_session_id_snapshot == session_id
    assert predecessor_token not in str(audit.metadata_json)
    failed_terminal = RefreshRequestTerminalRecord.objects.get(idempotency_key="attacker-replay-2")
    assert failed_terminal.terminal_kind == RefreshRequestTerminalRecord.TerminalKind.FAILED
    assert failed_terminal.error_code == "SESSION_REVOKED"
    assert failed_terminal.successor_credential_id is None
    assert failed_terminal.access_claims_json == {}


def test_used_refresh_is_audited_as_replay_even_after_account_lifecycle_changes(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "late_replay", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "late_replay", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    auth_post(client, "auth-refresh", {}, **{"idempotency-key": "late-replay-first"})
    account = GameAccount.objects.get(pk=login_response.json()["game_account_id"])
    account.lifecycle = GameAccount.Lifecycle.COOLING_OFF
    account.lifecycle_version += 1
    account.save(update_fields=("lifecycle", "lifecycle_version"))

    client.cookies["new_mud_refresh"] = predecessor_token
    replay = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "late-replay-attacker"},
    )

    assert replay.status_code == 401
    assert replay.json() == {"error": {"code": "SESSION_REVOKED"}}
    family = RefreshTokenFamily.objects.get()
    assert family.revoke_reason == "REFRESH_TOKEN_REPLAYED"
    assert SecurityAuditEvent.objects.filter(reason_code="REFRESH_TOKEN_REPLAYED").exists()


def test_logout_converges_cookie_and_bearer_sessions_idempotently(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    first_login = auth_post(
        client,
        "auth-login",
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    first_access = first_login.json()["access_token"]
    first_session_id = first_login.json()["auth_session_id"]
    second_login = auth_post(
        client,
        "auth-login",
        {"username": "logout_player", "password": "safe-example-passphrase-42"},
    )
    second_session_id = second_login.json()["auth_session_id"]

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {first_access}",
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    cleared = response.cookies["new_mud_refresh"]
    assert cleared["max-age"] == 0
    assert cleared["path"] == "/api/v1/auth/"
    assert cleared["secure"] is True
    assert cleared["httponly"] is True
    assert cleared["samesite"] == "Strict"
    assert set(
        AuthSession.objects.filter(pk__in=(first_session_id, second_session_id)).values_list(
            "state", flat=True
        )
    ) == {"logged_out"}
    assert not RefreshTokenCredential.objects.filter(state="active").exists()

    repeated = auth_post(client, "auth-logout", {})
    assert repeated.status_code == 204
    assert repeated.cookies["new_mud_refresh"]["max-age"] == 0


def test_recovery_code_replaces_password_and_revokes_all_authentication(client) -> None:
    registration = auth_post(
        client,
        "auth-register",
        {"username": "recover_player", "password": "safe-example-passphrase-42"},
    )
    original_code = registration.json()["recovery_code"]
    for _ in range(2):
        assert (
            auth_post(
                client,
                "auth-login",
                {"username": "recover_player", "password": "safe-example-passphrase-42"},
            ).status_code
            == 200
        )
    assert (
        login_in_additional_instance(
            client,
            username="recover_player",
            password="safe-example-passphrase-42",
        ).status_code
        == 200
    )

    response = auth_post(
        client,
        "auth-recover",
        {
            "username": "RECOVER_PLAYER",
            "recovery_code": original_code,
            "new_password": "replacement-passphrase-73-safe",
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {"recovery_code"}
    replacement_code = response.json()["recovery_code"]
    assert replacement_code != original_code
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])
    assert list(
        account.recovery_codes.order_by("generation").values_list("generation", "state")
    ) == [(1, "used"), (2, "active")]
    assert account.recovery_codes.get(generation=2).check_code(replacement_code)
    assert set(account.auth_sessions.values_list("state", flat=True)) == {"revoked"}
    assert not RefreshTokenFamily.objects.filter(state="active").exists()
    assert not RefreshTokenCredential.objects.filter(state="active").exists()

    old_password = auth_post(
        client,
        "auth-login",
        {"username": "recover_player", "password": "safe-example-passphrase-42"},
    )
    assert old_password.json() == {"error": {"code": "AUTH_CREDENTIALS_INVALID"}}
    new_password = auth_post(
        client,
        "auth-login",
        {"username": "recover_player", "password": "replacement-passphrase-73-safe"},
    )
    assert new_password.status_code == 200


@pytest.mark.parametrize("limited_subject", ["account", "ip", "device"])
def test_recovery_combines_account_ip_and_device_rate_limits(
    client,
    settings,
    limited_subject: str,
) -> None:
    settings.AUTH_RECOVERY_RATE_LIMIT_ACCOUNT = 2 if limited_subject == "account" else 100
    settings.AUTH_RECOVERY_RATE_LIMIT_IP = 2 if limited_subject == "ip" else 100
    settings.AUTH_RECOVERY_RATE_LIMIT_DEVICE = 2 if limited_subject == "device" else 100

    responses = []
    for attempt in range(3):
        username = "same_account" if limited_subject == "account" else f"account_{attempt}"
        remote_addr = "192.0.2.10" if limited_subject == "ip" else f"192.0.2.{attempt + 1}"
        device_id = "same-device" if limited_subject == "device" else f"device-{attempt}"
        client.cookies["new_mud_recovery_device"] = device_id
        responses.append(
            auth_post(
                client,
                "auth-recover",
                {
                    "username": username,
                    "recovery_code": "invalid-code",
                    "new_password": "replacement-passphrase-73-safe",
                },
                remote_addr=remote_addr,
            )
        )

    assert [response.status_code for response in responses] == [400, 400, 429]
    assert responses[-1].json() == {"error": {"code": "RECOVERY_RATE_LIMITED"}}
    device_cookie = responses[0].cookies["new_mud_recovery_device"]
    assert device_cookie["secure"]
    assert device_cookie["httponly"]
    assert device_cookie["samesite"] == "Strict"
    assert device_cookie["domain"] == ""


def test_recovery_rate_limit_does_not_lock_password_login(client, settings) -> None:
    settings.AUTH_RECOVERY_RATE_LIMIT_ACCOUNT = 1
    settings.AUTH_RECOVERY_RATE_LIMIT_IP = 100
    settings.AUTH_RECOVERY_RATE_LIMIT_DEVICE = 100
    registration = auth_post(
        client,
        "auth-register",
        {"username": "rate_limited_recovery", "password": "safe-example-passphrase-42"},
    )
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])

    first = auth_post(
        client,
        "auth-recover",
        {
            "username": "rate_limited_recovery",
            "recovery_code": "invalid-code",
            "new_password": "replacement-passphrase-73-safe",
        },
    )
    limited = auth_post(
        client,
        "auth-recover",
        {
            "username": "rate_limited_recovery",
            "recovery_code": registration.json()["recovery_code"],
            "new_password": "replacement-passphrase-73-safe",
        },
    )

    assert first.status_code == 400
    assert limited.status_code == 429
    assert account.recovery_codes.get().state == RecoveryCodeCredential.State.ACTIVE
    login_response = auth_post(
        client,
        "auth-login",
        {
            "username": "rate_limited_recovery",
            "password": "safe-example-passphrase-42",
        },
    )
    assert login_response.status_code == 200


def test_recovery_does_not_reveal_account_existence_before_code_validation(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "existing_recovery", "password": "safe-example-passphrase-42"},
    )

    existing = auth_post(
        client,
        "auth-recover",
        {
            "username": "existing_recovery",
            "recovery_code": "invalid-code",
            "new_password": "short",
        },
    )
    missing = auth_post(
        client,
        "auth-recover",
        {
            "username": "missing_recovery",
            "recovery_code": "invalid-code",
            "new_password": "short",
        },
    )

    assert existing.status_code == missing.status_code == 400
    assert existing.json() == missing.json() == {"error": {"code": "RECOVERY_CODE_INVALID"}}


def test_registration_and_login_are_rate_limited_with_stable_errors(client, settings) -> None:
    settings.AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT = 100
    settings.AUTH_REGISTRATION_RATE_LIMIT_IP = 1
    settings.AUTH_LOGIN_RATE_LIMIT_ACCOUNT = 1
    settings.AUTH_LOGIN_RATE_LIMIT_IP = 100

    first_registration = auth_post(
        client,
        "auth-register",
        {"username": "limited_login", "password": "safe-example-passphrase-42"},
    )
    limited_registration = auth_post(
        client,
        "auth-register",
        {"username": "other_registration", "password": "safe-example-passphrase-42"},
    )
    failed_login = auth_post(
        client,
        "auth-login",
        {"username": "limited_login", "password": "wrong-password"},
    )
    limited_login = auth_post(
        client,
        "auth-login",
        {"username": "limited_login", "password": "safe-example-passphrase-42"},
    )

    assert first_registration.status_code == 201
    assert limited_registration.status_code == 429
    assert limited_registration.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}
    assert failed_login.status_code == 401
    assert limited_login.status_code == 429
    assert limited_login.json() == {"error": {"code": "AUTH_CREDENTIALS_INVALID"}}
    assert AuthSession.objects.count() == 0


def test_refresh_same_key_is_safe_and_old_result_becomes_superseded(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "retry_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "retry_player", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert first.status_code == 200
    successor_token = first.cookies["new_mud_refresh"].value

    client.cookies["new_mud_refresh"] = predecessor_token
    retry = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert retry.status_code == 200
    assert retry.json()["access_token"] == first.json()["access_token"]
    assert retry.cookies["new_mud_refresh"].value == successor_token
    family = RefreshTokenFamily.objects.get()
    assert family.current_generation == 2

    client.cookies["new_mud_refresh"] = successor_token
    later = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "next-logical-refresh"},
    )
    assert later.status_code == 200
    client.cookies["new_mud_refresh"] = predecessor_token
    superseded = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "same-logical-refresh"},
    )
    assert superseded.status_code == 409
    assert superseded.json() == {"error": {"code": "REFRESH_REQUEST_SUPERSEDED"}}
    family.refresh_from_db()
    assert family.state == "active"
    assert family.current_generation == 3


def test_refresh_retry_reports_access_token_remaining_lifetime(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "remaining_lifetime", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "remaining_lifetime", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "remaining-lifetime-key"},
    )
    claims = RefreshRequestTerminalRecord.objects.get().access_claims_json
    replay_time = datetime.fromtimestamp(int(claims["exp"]) - 37, tz=UTC)

    client.cookies["new_mud_refresh"] = predecessor_token
    with patch("new_mud.apps.identity.services.timezone.now", return_value=replay_time):
        retry = auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "remaining-lifetime-key"},
        )

    assert retry.status_code == 200
    assert retry.json()["access_token"] == first.json()["access_token"]
    assert retry.json()["expires_in"] == 37


def test_refresh_retry_at_family_cutoff_does_not_extend_the_cookie(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "cutoff_retry", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "cutoff_retry", "password": "safe-example-passphrase-42"},
    )
    predecessor_token = login_response.cookies["new_mud_refresh"].value
    auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "cutoff-retry-key"},
    )
    family = RefreshTokenFamily.objects.get()

    client.cookies["new_mud_refresh"] = predecessor_token
    with patch(
        "new_mud.apps.identity.services.timezone.now",
        return_value=family.absolute_expires_at,
    ):
        retry = auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "cutoff-retry-key"},
        )

    assert retry.status_code == 401
    assert retry.json() == {"error": {"code": "SESSION_REVOKED"}}
    assert "new_mud_refresh" not in retry.cookies


def test_refresh_same_key_with_a_different_credential_is_a_conflict(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "conflict_player", "password": "safe-example-passphrase-42"},
    )
    auth_post(
        client,
        "auth-login",
        {"username": "conflict_player", "password": "safe-example-passphrase-42"},
    )
    first = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "reused-key"},
    )
    assert first.status_code == 200

    conflict = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "reused-key"},
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"error": {"code": "REFRESH_IDEMPOTENCY_CONFLICT"}}
    family = RefreshTokenFamily.objects.get()
    assert family.state == "active"
    assert family.current_generation == 2


def test_recovery_code_rotation_revokes_the_calling_session(client) -> None:
    registration = auth_post(
        client,
        "auth-register",
        {"username": "rotate_player", "password": "safe-example-passphrase-42"},
    )
    original_code = registration.json()["recovery_code"]
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "rotate_player", "password": "safe-example-passphrase-42"},
    )
    assert (
        login_in_additional_instance(
            client,
            username="rotate_player",
            password="safe-example-passphrase-42",
        ).status_code
        == 200
    )

    response = auth_post(
        client,
        "auth-recovery-rotate",
        {},
        authorization=f"Bearer {login_response.json()['access_token']}",
    )

    assert response.status_code == 200
    assert set(response.json()) == {"recovery_code"}
    replacement_code = response.json()["recovery_code"]
    assert replacement_code != original_code
    account = GameAccount.objects.get(pk=registration.json()["game_account_id"])
    assert list(
        account.recovery_codes.order_by("generation").values_list("generation", "state")
    ) == [(1, "revoked"), (2, "active")]
    assert account.recovery_codes.get(generation=2).check_code(replacement_code)
    assert set(AuthSession.objects.values_list("state", flat=True)) == {"revoked"}
    assert not RefreshTokenFamily.objects.filter(state="active").exists()
    assert not RefreshTokenCredential.objects.filter(state="active").exists()


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("bad-name", "safe-example-passphrase-42"),
        ("valid_player", "short"),
    ],
)
def test_registration_rejects_invalid_credentials_without_partial_identity(
    client,
    username: str,
    password: str,
) -> None:
    response = auth_post(
        client,
        "auth-register",
        {"username": username, "password": password},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "REGISTRATION_INVALID"}}
    assert response.headers["Cache-Control"] == "no-store"
    assert get_user_model().objects.count() == 0
    assert GameAccount.objects.count() == 0
    assert RecoveryCodeCredential.objects.count() == 0


def test_registration_rejects_case_insensitive_duplicate_without_partial_identity(client) -> None:
    first = auth_post(
        client,
        "auth-register",
        {"username": "Duplicate_Player", "password": "safe-example-passphrase-42"},
    )
    assert first.status_code == 201

    duplicate = auth_post(
        client,
        "auth-register",
        {"username": "DUPLICATE_PLAYER", "password": "another-safe-passphrase-73"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {"error": {"code": "REGISTRATION_UNAVAILABLE"}}
    assert duplicate.headers["Cache-Control"] == "no-store"
    assert get_user_model().objects.count() == 1
    assert GameAccount.objects.count() == 1
    assert RecoveryCodeCredential.objects.count() == 1


@pytest.mark.parametrize(
    ("route_name", "error_code"),
    [
        ("auth-register", "REGISTRATION_INVALID"),
        ("auth-login", "AUTH_CREDENTIALS_INVALID"),
        ("auth-refresh", "REFRESH_UNAVAILABLE"),
        ("auth-logout", "AUTH_CREDENTIALS_INVALID"),
    ],
)
def test_public_auth_routes_are_post_only_and_all_method_errors_are_not_cached(
    client,
    route_name: str,
    error_code: str,
) -> None:
    response = client.get(
        reverse(route_name),
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 405
    assert response.json() == {"error": {"code": error_code}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    ("route_name", "error_code"),
    [
        ("auth-register", "REGISTRATION_INVALID"),
        ("auth-login", "AUTH_CREDENTIALS_INVALID"),
        ("auth-refresh", "REFRESH_UNAVAILABLE"),
        ("auth-logout", "AUTH_CREDENTIALS_INVALID"),
    ],
)
def test_framework_parse_errors_use_stable_endpoint_codes_and_are_not_cached(
    client,
    route_name: str,
    error_code: str,
) -> None:
    response = client.post(
        reverse(route_name),
        data=b'{"broken":',
        content_type="application/json",
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": error_code}}
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        "/auth/login",
        "/api/auth/login",
        "/api/v1/login",
        "/api/v1/auth/login/",
    ],
)
def test_public_auth_routes_have_no_unversioned_or_slash_aliases(client, path: str) -> None:
    response = client.post(
        path,
        {"username": "player", "password": "irrelevant-passphrase-42"},
        content_type="application/json",
        secure=True,
        headers={"origin": "https://testserver"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_auth_endpoints_reject_untrusted_origin_without_authentication_side_effects(
    client,
    origin: str | None,
) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "origin_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "origin_player", "password": "safe-example-passphrase-42"},
    )
    session_id = login_response.json()["auth_session_id"]
    family = RefreshTokenFamily.objects.get(auth_session_id=session_id)

    headers = {} if origin is None else {"origin": origin}
    requests = [
        (
            "auth-register",
            {"username": "cross_origin", "password": "safe-example-passphrase-42"},
            {},
        ),
        (
            "auth-login",
            {"username": "origin_player", "password": "safe-example-passphrase-42"},
            {},
        ),
        ("auth-refresh", {}, {"idempotency-key": "blocked-origin-refresh"}),
        ("auth-logout", {}, {}),
    ]

    for route_name, payload, extra_headers in requests:
        response = client.post(
            reverse(route_name),
            payload,
            content_type="application/json",
            secure=True,
            headers={**headers, **extra_headers},
        )
        assert response.status_code >= 400
        assert response.headers["Cache-Control"] == "no-store"

    assert not get_user_model().objects.filter(username="cross_origin").exists()
    assert AuthSession.objects.count() == 1
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.ACTIVE
    family.refresh_from_db()
    assert family.state == RefreshTokenFamily.State.ACTIVE
    assert family.current_generation == 1


@pytest.mark.parametrize(
    "idempotency_key",
    [None, "", "has space", "_starts-with-punctuation", "非ascii", "a" * 129],
)
def test_invalid_refresh_key_fails_before_the_credential_is_consumed(
    client,
    idempotency_key: str | None,
) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "invalid_key_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "invalid_key_player", "password": "safe-example-passphrase-42"},
    )
    headers = {} if idempotency_key is None else {"idempotency-key": idempotency_key}

    response = auth_post(client, "auth-refresh", {}, **headers)

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "REFRESH_IDEMPOTENCY_KEY_INVALID"}}
    family = RefreshTokenFamily.objects.get(
        auth_session_id=login_response.json()["auth_session_id"]
    )
    assert family.current_generation == 1
    assert list(family.credentials.values_list("generation", "state")) == [(1, "active")]


def test_refresh_rejects_json_and_authorization_transport_without_rotation(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "transport_player", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "transport_player", "password": "safe-example-passphrase-42"},
    )
    refresh_token = login_response.cookies["new_mud_refresh"].value
    family = RefreshTokenFamily.objects.get(
        auth_session_id=login_response.json()["auth_session_id"]
    )

    bearer_response = auth_post(
        client,
        "auth-refresh",
        {},
        authorization=f"Bearer {refresh_token}",
        **{"idempotency-key": "refresh-bearer-forbidden"},
    )
    json_response = auth_post(
        client,
        "auth-refresh",
        {"refresh_token": refresh_token},
        **{"idempotency-key": "refresh-json-forbidden"},
    )

    for response in (bearer_response, json_response):
        assert response.status_code == 400
        assert response.json() == {"error": {"code": "REFRESH_UNAVAILABLE"}}
        assert refresh_token.encode() not in response.content
        assert "new_mud_refresh" not in response.cookies
    family.refresh_from_db()
    assert family.current_generation == 1
    assert list(family.credentials.values_list("generation", "state")) == [(1, "active")]


def test_logout_ignores_a_damaged_cookie_when_valid_bearer_locates_the_session(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "damaged_cookie", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "damaged_cookie", "password": "safe-example-passphrase-42"},
    )
    session_id = login_response.json()["auth_session_id"]
    client.cookies["new_mud_refresh"] = "damaged-cookie-value"

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {login_response.json()['access_token']}",
    )

    assert response.status_code == 204
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.LOGGED_OUT
    assert RefreshTokenFamily.objects.get(auth_session_id=session_id).state == "revoked"
    assert not RefreshTokenCredential.objects.filter(
        family__auth_session_id=session_id,
        state=RefreshTokenCredential.State.ACTIVE,
    ).exists()


def test_logout_preserves_revoked_terminal_state_and_converges_children(client) -> None:
    auth_post(
        client,
        "auth-register",
        {"username": "terminal_logout", "password": "safe-example-passphrase-42"},
    )
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "terminal_logout", "password": "safe-example-passphrase-42"},
    )
    predecessor = login_response.cookies["new_mud_refresh"].value
    session_id = login_response.json()["auth_session_id"]
    assert (
        auth_post(
            client,
            "auth-refresh",
            {},
            **{"idempotency-key": "terminal-logout-first"},
        ).status_code
        == 200
    )
    client.cookies["new_mud_refresh"] = predecessor
    assert auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "terminal-logout-replay"},
    ).json() == {"error": {"code": "SESSION_REVOKED"}}

    response = auth_post(client, "auth-logout", {})

    assert response.status_code == 204
    assert response.content == b""
    assert AuthSession.objects.get(pk=session_id).state == AuthSession.State.REVOKED
    assert RefreshTokenFamily.objects.get(auth_session_id=session_id).state == "revoked"
    assert not RefreshTokenCredential.objects.filter(
        family__auth_session_id=session_id,
        state=RefreshTokenCredential.State.ACTIVE,
    ).exists()


def test_logout_with_zero_recognized_locators_clears_client_without_false_audit(client) -> None:
    client.cookies["new_mud_refresh"] = "not-a-refresh-token"

    response = auth_post(
        client,
        "auth-logout",
        {},
        authorization="Bearer not-an-access-token",
    )

    assert response.status_code == 204
    assert response.headers["Cache-Control"] == "no-store"
    assert response.cookies["new_mud_refresh"]["max-age"] == 0
    assert SecurityAuditEvent.objects.count() == 0


def test_plaintext_authentication_secrets_never_enter_audit_terminal_or_logs(
    client,
    caplog,
) -> None:
    password = "secret-audit-passphrase-42"
    registration = auth_post(
        client,
        "auth-register",
        {"username": "secret_audit", "password": password},
    )
    recovery_code = registration.json()["recovery_code"]
    login_response = auth_post(
        client,
        "auth-login",
        {"username": "secret_audit", "password": password},
    )
    access_token = login_response.json()["access_token"]
    predecessor_refresh = login_response.cookies["new_mud_refresh"].value
    refresh_response = auth_post(
        client,
        "auth-refresh",
        {},
        **{"idempotency-key": "secret-audit-refresh"},
    )
    successor_refresh = refresh_response.cookies["new_mud_refresh"].value
    auth_post(
        client,
        "auth-logout",
        {},
        authorization=f"Bearer {refresh_response.json()['access_token']}",
    )

    persisted_blob = json.dumps(
        {
            "audits": list(
                SecurityAuditEvent.objects.values(
                    "event_type",
                    "reason_code",
                    "metadata_json",
                )
            ),
            "terminals": list(
                RefreshRequestTerminalRecord.objects.values(
                    "canonical_request_hash",
                    "access_claims_json",
                    "error_code",
                )
            ),
        },
        sort_keys=True,
    )
    observable_text = f"{persisted_blob}\n{caplog.text}"
    for secret in (
        password,
        recovery_code,
        access_token,
        predecessor_refresh,
        successor_refresh,
    ):
        assert secret not in observable_text
