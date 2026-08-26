from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, models, transaction
from django.utils import timezone

from .models import (
    AuthSession,
    GameAccount,
    RecoveryCodeCredential,
    RefreshRequestTerminalRecord,
    RefreshTokenCredential,
    RefreshTokenFamily,
    SecurityAuditEvent,
    VerificationChallenge,
    VerifiedContactMethod,
)
from .tokens import (
    decode_access_token,
    encode_access_token,
    materialize_refresh_token,
    parse_refresh_token,
    refresh_token_hash,
)
from .verification import (
    ContactInvalid,
    lock_registration_email_scope,
    normalize_email,
    registration_email_scope,
)
from .verification_config import (
    VerificationServiceUnavailable,
    require_verification_service,
)
from .verification_crypto import (
    KeyUnavailable,
    encrypt_value,
    verification_code_digest,
)
from .verification_limits import advisory_transaction_lock

USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class RegistrationInvalid(Exception):
    pass


class RegistrationUnavailable(Exception):
    pass


class VerificationCodeInvalid(Exception):
    pass


class AuthenticationFailed(Exception):
    pass


class RefreshFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RecoveryFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RegistrationResult:
    user_id: int
    game_account_id: str


@dataclass(frozen=True)
class AuthenticationResult:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_max_age: int
    auth_session_id: str
    game_account_id: str


def register(
    *,
    username: object,
    password: object,
    verification: object,
) -> RegistrationResult:
    if not isinstance(username, str) or not isinstance(password, str):
        raise RegistrationInvalid
    normalized_username = username.lower()
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise RegistrationInvalid
    try:
        if not isinstance(verification, dict):
            raise VerificationCodeInvalid
        if verification.get("channel") != VerificationChallenge.Channel.EMAIL:
            raise VerificationCodeInvalid
        code = verification.get("code")
        if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
            raise VerificationCodeInvalid
        normalized_email = normalize_email(verification.get("destination"))
    except ContactInvalid as error:
        raise VerificationCodeInvalid from error

    keyrings = require_verification_service()
    email_scope = registration_email_scope(
        normalized_email,
        lookup_keyring=keyrings.contact_lookup,
    )
    invalid_code = False
    user_model = get_user_model()
    try:
        with transaction.atomic():
            advisory_transaction_lock(f"registration:username:{normalized_username}")
            lock_registration_email_scope(email_scope)
            now = timezone.now()
            challenge = (
                VerificationChallenge.objects.select_for_update()
                .filter(
                    purpose=VerificationChallenge.Purpose.REGISTRATION,
                    channel=VerificationChallenge.Channel.EMAIL,
                    destination_lookup_digest__in=email_scope.lookup_digests,
                    user__isnull=True,
                    state=VerificationChallenge.State.ACTIVE,
                )
                .order_by("-activated_at", "challenge_id")
                .first()
            )
            if challenge is None:
                invalid_code = True
            elif challenge.expires_at is None or challenge.expires_at <= now:
                challenge.state = VerificationChallenge.State.EXPIRED
                challenge.terminal_at = now
                challenge.version += 1
                challenge.save(update_fields=("state", "terminal_at", "version"))
                invalid_code = True
            else:
                try:
                    submitted_digest = verification_code_digest(
                        code,
                        keyring=keyrings.code_pepper,
                        purpose=challenge.purpose,
                        channel=challenge.channel,
                        destination_lookup_digest=challenge.destination_lookup_digest,
                        user_id=None,
                        key_id=challenge.pepper_key_id,
                    ).digest
                except KeyUnavailable as error:
                    raise VerificationServiceUnavailable from error
                if not hmac.compare_digest(challenge.code_digest, submitted_digest):
                    challenge.attempt_count += 1
                    update_fields = ["attempt_count", "version"]
                    if challenge.attempt_count >= 5:
                        challenge.state = VerificationChallenge.State.LOCKED
                        challenge.terminal_at = now
                        update_fields.extend(("state", "terminal_at"))
                    challenge.version += 1
                    challenge.save(update_fields=update_fields)
                    invalid_code = True

            if invalid_code:
                user = None
                account = None
            else:
                assert challenge is not None
                candidate = user_model(username=normalized_username)
                try:
                    validate_password(password, user=candidate)
                except ValidationError as error:
                    raise RegistrationInvalid from error
                if user_model.objects.filter(username=normalized_username).exists():
                    raise RegistrationUnavailable
                if VerifiedContactMethod.objects.filter(
                    channel=VerifiedContactMethod.Channel.EMAIL,
                    lookup_digest__in=email_scope.lookup_digests,
                    state__in=(
                        VerifiedContactMethod.State.ACTIVE,
                        VerifiedContactMethod.State.UNREACHABLE,
                    ),
                ).exists():
                    raise RegistrationUnavailable

                encrypted_email = encrypt_value(
                    normalized_email.delivery,
                    keyring=keyrings.contact_encryption,
                    context="contact:email",
                )
                user = user_model.objects.create_user(
                    username=normalized_username,
                    password=password,
                )
                account = GameAccount.objects.create(
                    user=user,
                    instance_id=settings.CONTENT_INSTANCE_ID,
                )
                VerifiedContactMethod.objects.create(
                    user=user,
                    channel=VerifiedContactMethod.Channel.EMAIL,
                    destination_ciphertext=encrypted_email.ciphertext,
                    encryption_key_id=encrypted_email.key_id,
                    lookup_digest=email_scope.current_lookup.digest,
                    lookup_key_id=email_scope.current_lookup.key_id,
                    verified_at=now,
                )
                challenge.state = VerificationChallenge.State.CONSUMED
                challenge.consumed_at = now
                challenge.terminal_at = now
                challenge.version += 1
                challenge.save(update_fields=("state", "consumed_at", "terminal_at", "version"))
    except IntegrityError as error:
        raise RegistrationUnavailable from error

    if invalid_code:
        raise VerificationCodeInvalid
    assert user is not None and account is not None

    return RegistrationResult(
        user_id=user.pk,
        game_account_id=str(account.pk),
    )


def _access_claims(session: AuthSession, *, issued_at) -> dict[str, object]:
    expires_in = settings.AUTH_ACCESS_TOKEN_TTL_SECONDS
    return {
        "aud": "new-mud-h5",
        "sub": str(session.user_id),
        "auth_session_id": str(session.pk),
        "game_account_id": str(session.game_account_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + expires_in,
        "jti": uuid.uuid4().hex,
    }


def login(*, username: object, password: object) -> AuthenticationResult:
    if not isinstance(username, str) or not isinstance(password, str):
        raise AuthenticationFailed
    normalized_username = username.lower()
    user_model = get_user_model()
    try:
        user = user_model.objects.get(username=normalized_username)
    except user_model.DoesNotExist as error:
        raise AuthenticationFailed from error

    with transaction.atomic():
        try:
            account = GameAccount.objects.select_for_update().get(
                user=user,
                instance_id=settings.CONTENT_INSTANCE_ID,
                lifecycle=GameAccount.Lifecycle.ACTIVE,
            )
        except GameAccount.DoesNotExist as error:
            raise AuthenticationFailed from error
        user.refresh_from_db(fields=("password", "is_active"))
        if not user.check_password(password) or not user.is_active:
            raise AuthenticationFailed
        now = timezone.now()
        absolute_expires_at = now + timedelta(seconds=settings.AUTH_REFRESH_TOKEN_TTL_SECONDS)
        session = AuthSession.objects.create(
            user=user,
            game_account=account,
            device_id=secrets.token_urlsafe(24),
            issued_at=now,
            last_seen_at=now,
            absolute_expires_at=absolute_expires_at,
        )
        family = RefreshTokenFamily.objects.create(
            auth_session=session,
            current_generation=1,
            absolute_expires_at=absolute_expires_at,
        )
        session.refresh_family = family
        session.save(update_fields=("refresh_family",))

        credential_id = uuid.uuid4()
        refresh_token = materialize_refresh_token(credential_id, 1)
        RefreshTokenCredential.objects.create(
            credential_id=credential_id,
            family=family,
            generation=1,
            token_hash=refresh_token_hash(refresh_token),
            jti_hash=refresh_token_hash(credential_id.hex),
            issued_at=now,
            expires_at=absolute_expires_at,
        )
        claims = _access_claims(session, issued_at=now)
        SecurityAuditEvent.objects.create(
            event_type="auth.login.succeeded",
            user_id_snapshot=str(user.pk),
            auth_session_id_snapshot=str(session.pk),
        )

    response_at = timezone.now()
    return AuthenticationResult(
        access_token=encode_access_token(claims),
        refresh_token=refresh_token,
        expires_in=max(0, int(str(claims["exp"])) - int(response_at.timestamp())),
        refresh_max_age=max(0, int((absolute_expires_at - response_at).total_seconds())),
        auth_session_id=str(session.pk),
        game_account_id=str(account.pk),
    )


def _refresh_request_hash(credential_id: uuid.UUID) -> str:
    canonical = f"POST:/api/v1/auth/refresh:v1:{credential_id.hex}:{{}}"
    return hashlib.sha256(canonical.encode()).hexdigest()


def _authentication_result(
    *,
    session: AuthSession,
    credential: RefreshTokenCredential,
    claims: dict[str, object],
) -> AuthenticationResult:
    token = materialize_refresh_token(credential.pk, credential.generation)
    if not secrets.compare_digest(refresh_token_hash(token), credential.token_hash):
        raise RefreshFailed("REFRESH_UNAVAILABLE")
    try:
        access_expires_at = int(str(claims["exp"]))
    except (KeyError, TypeError, ValueError) as error:
        raise RefreshFailed("REFRESH_UNAVAILABLE") from error
    return AuthenticationResult(
        access_token=encode_access_token(claims),
        refresh_token=token,
        expires_in=max(0, access_expires_at - int(timezone.now().timestamp())),
        refresh_max_age=max(0, int((credential.expires_at - timezone.now()).total_seconds())),
        auth_session_id=str(session.pk),
        game_account_id=str(session.game_account_id),
    )


def _refresh_terminal_expires_at(*, family: RefreshTokenFamily, created_at):
    return max(
        created_at + timedelta(seconds=settings.AUTH_REFRESH_REQUEST_RETRY_WINDOW_SECONDS),
        family.absolute_expires_at
        + timedelta(seconds=settings.AUTH_TERMINAL_SECRET_CLEANUP_GRACE_SECONDS),
    )


def _create_failed_refresh_terminal(
    *,
    family: RefreshTokenFamily,
    idempotency_key: str,
    request_hash: str,
    credential: RefreshTokenCredential,
    error_code: str,
    created_at,
) -> None:
    RefreshRequestTerminalRecord.objects.create(
        family=family,
        idempotency_key=idempotency_key,
        canonical_request_hash=request_hash,
        predecessor_credential=credential,
        access_claims_json={},
        terminal_kind=RefreshRequestTerminalRecord.TerminalKind.FAILED,
        error_code=error_code,
        created_at=created_at,
        expires_at=_refresh_terminal_expires_at(
            family=family,
            created_at=created_at,
        ),
    )


def _converge_authentication_control(
    *,
    family: RefreshTokenFamily,
    session: AuthSession,
    target_session_state: str,
    reason: str,
    now,
) -> bool:
    """Converge terminal authentication state at the future Presence integration seam."""
    RefreshTokenCredential.objects.filter(
        family=family,
        state=RefreshTokenCredential.State.ACTIVE,
    ).update(
        state=RefreshTokenCredential.State.REVOKED,
        version=models.F("version") + 1,
    )
    if family.state == RefreshTokenFamily.State.ACTIVE:
        family.state = RefreshTokenFamily.State.REVOKED
        family.revoked_at = now
        family.revoke_reason = reason
        family.version += 1
        family.save(update_fields=("state", "revoked_at", "revoke_reason", "version"))
    session_changed = session.state == AuthSession.State.ACTIVE
    if session_changed:
        session.state = target_session_state
        session.revoked_at = now
        session.revoke_reason = reason
        session.version += 1
        session.save(update_fields=("state", "revoked_at", "revoke_reason", "version"))
    return session_changed


def _revoke_family_for_replay(*, family: RefreshTokenFamily, session: AuthSession, now) -> None:
    _converge_authentication_control(
        family=family,
        session=session,
        target_session_state=AuthSession.State.REVOKED,
        reason="REFRESH_TOKEN_REPLAYED",
        now=now,
    )
    SecurityAuditEvent.objects.create(
        event_type="auth.refresh.replayed",
        user_id_snapshot=str(session.user_id),
        auth_session_id_snapshot=str(session.pk),
        reason_code="REFRESH_TOKEN_REPLAYED",
        metadata_json={"family_id": str(family.pk)},
    )


def refresh(*, refresh_token: object, idempotency_key: object) -> AuthenticationResult:
    if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(
        idempotency_key
    ):
        raise RefreshFailed("REFRESH_IDEMPOTENCY_KEY_INVALID")
    if not isinstance(refresh_token, str):
        raise RefreshFailed("REFRESH_UNAVAILABLE")
    parsed = parse_refresh_token(refresh_token)
    if parsed is None:
        raise RefreshFailed("REFRESH_UNAVAILABLE")
    credential_id, generation = parsed

    try:
        locator = RefreshTokenCredential.objects.only("family_id").get(
            pk=credential_id,
            generation=generation,
            token_hash=refresh_token_hash(refresh_token),
        )
    except RefreshTokenCredential.DoesNotExist as error:
        raise RefreshFailed("REFRESH_UNAVAILABLE") from error
    try:
        family_locator = RefreshTokenFamily.objects.only("auth_session_id").get(
            pk=locator.family_id
        )
        session_locator = AuthSession.objects.only("game_account_id").get(
            pk=family_locator.auth_session_id
        )
    except (RefreshTokenFamily.DoesNotExist, AuthSession.DoesNotExist) as error:
        raise RefreshFailed("REFRESH_UNAVAILABLE") from error

    request_hash = _refresh_request_hash(credential_id)
    result_credential: RefreshTokenCredential | None = None
    result_claims: dict[str, object] | None = None
    terminal_error: str | None = None
    with transaction.atomic():
        account = GameAccount.objects.select_for_update().get(pk=session_locator.game_account_id)
        session = AuthSession.objects.select_for_update().get(pk=family_locator.auth_session_id)
        family = RefreshTokenFamily.objects.select_for_update().get(pk=locator.family_id)
        terminal = (
            RefreshRequestTerminalRecord.objects.select_for_update()
            .filter(family=family, idempotency_key=idempotency_key)
            .first()
        )
        credential = RefreshTokenCredential.objects.select_for_update().get(pk=credential_id)

        if terminal is not None:
            if terminal.canonical_request_hash != request_hash:
                raise RefreshFailed("REFRESH_IDEMPOTENCY_CONFLICT")
            if terminal.terminal_kind == RefreshRequestTerminalRecord.TerminalKind.FAILED:
                raise RefreshFailed(terminal.error_code or "REFRESH_UNAVAILABLE")
            successor = terminal.successor_credential
            if (
                terminal.terminal_kind == RefreshRequestTerminalRecord.TerminalKind.SUCCEEDED
                and successor is not None
                and successor.state == RefreshTokenCredential.State.ACTIVE
                and successor.generation == family.current_generation
            ):
                now = timezone.now()
                if (
                    account.lifecycle != GameAccount.Lifecycle.ACTIVE
                    or session.state != AuthSession.State.ACTIVE
                    or session.absolute_expires_at <= now
                    or family.absolute_expires_at <= now
                    or successor.expires_at <= now
                ):
                    raise RefreshFailed("SESSION_REVOKED")
                return _authentication_result(
                    session=session,
                    credential=successor,
                    claims=terminal.access_claims_json,
                )
            raise RefreshFailed("REFRESH_REQUEST_SUPERSEDED")

        now = timezone.now()
        if (
            credential.state == RefreshTokenCredential.State.USED
            and credential.generation < family.current_generation
        ):
            _revoke_family_for_replay(family=family, session=session, now=now)
            terminal_error = "SESSION_REVOKED"
        elif (
            session.game_account_id != account.pk
            or family.auth_session_id != session.pk
            or family.state != RefreshTokenFamily.State.ACTIVE
            or session.state != AuthSession.State.ACTIVE
            or session.absolute_expires_at <= now
            or family.absolute_expires_at <= now
            or account.lifecycle != GameAccount.Lifecycle.ACTIVE
            or account.lifecycle_version < 1
        ):
            _converge_authentication_control(
                family=family,
                session=session,
                target_session_state=AuthSession.State.REVOKED,
                reason="SESSION_REVOKED",
                now=now,
            )
            terminal_error = "SESSION_REVOKED"
        elif (
            credential.state != RefreshTokenCredential.State.ACTIVE
            or credential.generation != family.current_generation
        ):
            terminal_error = "SESSION_REVOKED"
        else:
            next_generation = family.current_generation + 1
            successor_id = uuid.uuid4()
            successor_token = materialize_refresh_token(successor_id, next_generation)
            credential.state = RefreshTokenCredential.State.USED
            credential.used_at = now
            credential.version += 1
            credential.save(update_fields=("state", "used_at", "version"))
            successor = RefreshTokenCredential.objects.create(
                credential_id=successor_id,
                family=family,
                generation=next_generation,
                token_hash=refresh_token_hash(successor_token),
                jti_hash=refresh_token_hash(successor_id.hex),
                issued_at=now,
                expires_at=family.absolute_expires_at,
            )
            credential.replaced_by = successor
            credential.save(update_fields=("replaced_by",))
            family.current_generation = next_generation
            family.version += 1
            family.save(update_fields=("current_generation", "version"))
            claims = _access_claims(session, issued_at=now)
            terminal = RefreshRequestTerminalRecord.objects.create(
                family=family,
                idempotency_key=idempotency_key,
                canonical_request_hash=request_hash,
                predecessor_credential=credential,
                successor_credential=successor,
                access_claims_json=claims,
                terminal_kind=RefreshRequestTerminalRecord.TerminalKind.SUCCEEDED,
                created_at=now,
                expires_at=_refresh_terminal_expires_at(
                    family=family,
                    created_at=now,
                ),
            )
            SecurityAuditEvent.objects.create(
                event_type="auth.refresh.succeeded",
                user_id_snapshot=str(session.user_id),
                auth_session_id_snapshot=str(session.pk),
                metadata_json={"generation": next_generation},
            )
            result_credential = successor
            result_claims = terminal.access_claims_json

        if terminal_error is not None:
            _create_failed_refresh_terminal(
                family=family,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                credential=credential,
                error_code=terminal_error,
                created_at=now,
            )

    if terminal_error is not None:
        raise RefreshFailed(terminal_error)
    if result_credential is None or result_claims is None:
        raise RefreshFailed("REFRESH_UNAVAILABLE")

    return _authentication_result(
        session=session,
        credential=result_credential,
        claims=result_claims,
    )


def _session_from_refresh_locator(refresh_token: object) -> uuid.UUID | None:
    if not isinstance(refresh_token, str):
        return None
    parsed = parse_refresh_token(refresh_token)
    if parsed is None:
        return None
    credential_id, generation = parsed
    try:
        credential = RefreshTokenCredential.objects.select_related("family").get(
            pk=credential_id,
            generation=generation,
            token_hash=refresh_token_hash(refresh_token),
        )
    except RefreshTokenCredential.DoesNotExist:
        return None
    return credential.family.auth_session_id


def _session_from_access_locator(authorization: object) -> uuid.UUID | None:
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return None
    claims = decode_access_token(authorization.removeprefix("Bearer "))
    if claims is None:
        return None
    try:
        return uuid.UUID(str(claims["auth_session_id"]))
    except KeyError, ValueError, TypeError:
        return None


def logout(*, refresh_token: object, authorization: object) -> int:
    session_ids = {
        locator
        for locator in (
            _session_from_refresh_locator(refresh_token),
            _session_from_access_locator(authorization),
        )
        if locator is not None
    }
    if not session_ids:
        return 0

    now = timezone.now()
    revoked_count = 0
    with transaction.atomic():
        sessions = list(
            AuthSession.objects.select_for_update()
            .filter(pk__in=session_ids)
            .order_by("auth_session_id")
        )
        for session in sessions:
            try:
                family = RefreshTokenFamily.objects.select_for_update().get(auth_session=session)
            except RefreshTokenFamily.DoesNotExist:
                continue
            session_changed = _converge_authentication_control(
                family=family,
                session=session,
                target_session_state=AuthSession.State.LOGGED_OUT,
                reason="LOGOUT",
                now=now,
            )
            if session_changed:
                revoked_count += 1
            SecurityAuditEvent.objects.create(
                event_type="auth.logout.converged",
                user_id_snapshot=str(session.user_id),
                auth_session_id_snapshot=str(session.pk),
                metadata_json={"server_session_revoked": session_changed},
            )
    return revoked_count


def _lock_user_accounts(*, user_id: int) -> list[GameAccount]:
    return list(
        GameAccount.objects.select_for_update().filter(user_id=user_id).order_by("game_account_id")
    )


def _lock_user_sessions(*, user_id: int) -> list[AuthSession]:
    return list(
        AuthSession.objects.select_for_update().filter(user_id=user_id).order_by("auth_session_id")
    )


def _revoke_locked_user_sessions(*, sessions: list[AuthSession], reason: str, now) -> None:
    for session in sessions:
        try:
            family = RefreshTokenFamily.objects.select_for_update().get(auth_session=session)
        except RefreshTokenFamily.DoesNotExist:
            continue
        _converge_authentication_control(
            family=family,
            session=session,
            target_session_state=AuthSession.State.REVOKED,
            reason=reason,
            now=now,
        )


def _recover_password_with_code(
    *, username: object, recovery_code: object, new_password: object
) -> str:
    if not all(isinstance(value, str) for value in (username, recovery_code, new_password)):
        raise RecoveryFailed("RECOVERY_CODE_INVALID")
    normalized_username = str(username).lower()
    user_model = get_user_model()
    try:
        user = user_model.objects.get(username=normalized_username)
    except user_model.DoesNotExist as error:
        raise RecoveryFailed("RECOVERY_CODE_INVALID") from error

    replacement_code = secrets.token_urlsafe(24)
    now = timezone.now()
    with transaction.atomic():
        try:
            accounts = _lock_user_accounts(user_id=user.pk)
            account = next(
                candidate
                for candidate in accounts
                if candidate.instance_id == settings.CONTENT_INSTANCE_ID
                and candidate.lifecycle == GameAccount.Lifecycle.ACTIVE
            )
            current_code = RecoveryCodeCredential.objects.select_for_update().get(
                game_account=account,
                state=RecoveryCodeCredential.State.ACTIVE,
            )
        except (StopIteration, RecoveryCodeCredential.DoesNotExist) as error:
            raise RecoveryFailed("RECOVERY_CODE_INVALID") from error
        if not current_code.check_code(str(recovery_code)):
            raise RecoveryFailed("RECOVERY_CODE_INVALID")
        try:
            validate_password(str(new_password), user=user)
        except ValidationError as error:
            raise RecoveryFailed("ACCOUNT_RECOVERY_UNAVAILABLE") from error
        sessions = _lock_user_sessions(user_id=user.pk)

        current_code.state = RecoveryCodeCredential.State.USED
        current_code.used_at = now
        current_code.version += 1
        current_code.save(update_fields=("state", "used_at", "version"))
        RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=current_code.generation + 1,
            code_hash=make_password(replacement_code),
        )
        user.set_password(str(new_password))
        user.save(update_fields=("password",))
        _revoke_locked_user_sessions(
            sessions=sessions,
            reason="RECOVERY_CODE_USED",
            now=now,
        )
        SecurityAuditEvent.objects.create(
            event_type="auth.recovery.succeeded",
            user_id_snapshot=str(user.pk),
            reason_code="RECOVERY_CODE_USED",
            metadata_json={"revoked_session_count": len(sessions)},
        )
    return replacement_code


def recover_password_with_code(
    *, username: object, recovery_code: object, new_password: object
) -> str:
    try:
        return _recover_password_with_code(
            username=username,
            recovery_code=recovery_code,
            new_password=new_password,
        )
    except DatabaseError as error:
        raise RecoveryFailed("ACCOUNT_RECOVERY_UNAVAILABLE") from error


def _rotate_recovery_code(*, authorization: object) -> str:
    session_id = _session_from_access_locator(authorization)
    if session_id is None:
        raise RecoveryFailed("SESSION_REVOKED")
    try:
        session_locator = AuthSession.objects.only("user_id", "game_account_id").get(pk=session_id)
    except AuthSession.DoesNotExist as error:
        raise RecoveryFailed("SESSION_REVOKED") from error

    replacement_code = secrets.token_urlsafe(24)
    now = timezone.now()
    with transaction.atomic():
        try:
            accounts = _lock_user_accounts(user_id=session_locator.user_id)
            account = next(
                candidate
                for candidate in accounts
                if candidate.pk == session_locator.game_account_id
                and candidate.lifecycle == GameAccount.Lifecycle.ACTIVE
            )
            current_code = RecoveryCodeCredential.objects.select_for_update().get(
                game_account=account,
                state=RecoveryCodeCredential.State.ACTIVE,
            )
            sessions = _lock_user_sessions(user_id=session_locator.user_id)
            session = next(candidate for candidate in sessions if candidate.pk == session_id)
        except (
            StopIteration,
            RecoveryCodeCredential.DoesNotExist,
        ) as error:
            raise RecoveryFailed("SESSION_REVOKED") from error
        if (
            session.state != AuthSession.State.ACTIVE
            or session.absolute_expires_at <= now
            or session.game_account_id != account.pk
        ):
            raise RecoveryFailed("SESSION_REVOKED")

        current_code.state = RecoveryCodeCredential.State.REVOKED
        current_code.revoked_at = now
        current_code.version += 1
        current_code.save(update_fields=("state", "revoked_at", "version"))
        RecoveryCodeCredential.objects.create(
            game_account=account,
            generation=current_code.generation + 1,
            code_hash=make_password(replacement_code),
        )
        _revoke_locked_user_sessions(
            sessions=sessions,
            reason="RECOVERY_CODE_ROTATED",
            now=now,
        )
        SecurityAuditEvent.objects.create(
            event_type="auth.recovery_code.rotated",
            user_id_snapshot=str(session.user_id),
            auth_session_id_snapshot=str(session.pk),
            reason_code="RECOVERY_CODE_ROTATED",
            metadata_json={"revoked_session_count": len(sessions)},
        )
    return replacement_code


def rotate_recovery_code(*, authorization: object) -> str:
    try:
        return _rotate_recovery_code(authorization=authorization)
    except DatabaseError as error:
        raise RecoveryFailed("SESSION_REVOKED") from error
