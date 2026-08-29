from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model

from new_mud.apps.identity.connection_sessions import ConnectionClientContext
from new_mud.apps.identity.game_session_metrics import game_websocket_metrics
from new_mud.apps.identity.models import GameAccount
from new_mud.apps.identity.services import login, logout
from new_mud.apps.identity.tokens import decode_access_token, encode_access_token
from new_mud.asgi import application

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def _connected():
    communicator = WebsocketCommunicator(application, "/ws/v1/game")
    connected, _ = await communicator.connect()
    assert connected
    return communicator


def _logout_without_runtime_notification(*, refresh_token: str, access_token: str) -> None:
    with patch(
        "new_mud.apps.identity.services.notify_auth_session_invalidated",
        return_value=None,
    ):
        logout(
            refresh_token=refresh_token,
            authorization=f"Bearer {access_token}",
        )


async def test_game_socket_authenticates_access_token_and_sequences_responses():
    user = await get_user_model().objects.acreate_user(
        username="ws_player", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_player", password="safe-pass-42")
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_auth_1",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    result = await communicator.receive_json_from()
    event = await communicator.receive_json_from()
    assert result["type"] == "request.succeeded"
    assert result["seq"] == 1
    assert result["payload"]["request_type"] == "session.authenticate"
    assert result["payload"]["result"]["auth_session_id"] == auth.auth_session_id
    assert event["type"] == "session.ready"
    assert event["seq"] == 2
    await communicator.disconnect()


async def test_game_socket_rejects_presence_before_authentication():
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_enter_1",
            "type": "presence.enter",
            "payload": {"character_id": "x"},
        }
    )
    result = await communicator.receive_json_from()
    assert result["type"] == "request.failed"
    assert result["seq"] == 1
    assert result["payload"]["error"]["code"] == "AUTH_REQUIRED"
    await communicator.disconnect()


async def test_game_socket_authenticate_same_request_replays_but_payload_conflict_fails():
    user = await get_user_model().objects.acreate_user(
        username="ws_replay", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_replay", password="safe-pass-42")
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_same",
        "type": "session.authenticate",
        "payload": {"access_token": auth.access_token},
    }
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    await communicator.receive_json_from()
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()
    assert replay["type"] == "request.succeeded"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == 3
    envelope["payload"] = {"access_token": "different"}
    await communicator.send_json_to(envelope)
    conflict = await communicator.receive_json_from()
    assert conflict["payload"]["error"]["code"] == "REQUEST_ID_CONFLICT"
    await communicator.disconnect()


async def test_game_socket_does_not_replay_auth_success_after_session_revocation():
    user = await get_user_model().objects.acreate_user(
        username="ws_revoked", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_revoked", password="safe-pass-42")
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_revoke",
        "type": "session.authenticate",
        "payload": {"access_token": auth.access_token},
    }
    await communicator.send_json_to(envelope)
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    await database_sync_to_async(_logout_without_runtime_notification)(
        refresh_token=auth.refresh_token,
        access_token=auth.access_token,
    )
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()
    assert replay["type"] == "request.failed"
    assert replay["payload"]["error"]["code"] == "SESSION_REVOKED"
    await communicator.disconnect()


async def test_game_socket_rejects_new_authentication_request_after_session_revocation():
    user = await get_user_model().objects.acreate_user(
        username="ws_revoked_new_request", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_revoked_new_request", password="safe-pass-42"
    )
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_before_revoke",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    await database_sync_to_async(_logout_without_runtime_notification)(
        refresh_token=auth.refresh_token,
        access_token=auth.access_token,
    )
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_after_revoke",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    result = await communicator.receive_json_from()
    assert result["type"] == "request.failed"
    assert result["payload"]["error"]["code"] == "SESSION_REVOKED"
    await communicator.disconnect()


async def test_game_socket_ping_remains_connection_local_after_session_revocation():
    user = await get_user_model().objects.acreate_user(
        username="ws_revoked_ping", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_revoked_ping", password="safe-pass-42")
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_auth_before_revoked_ping",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    await database_sync_to_async(_logout_without_runtime_notification)(
        refresh_token=auth.refresh_token,
        access_token=auth.access_token,
    )
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_ping_after_revoke",
            "type": "session.ping",
            "payload": {},
        }
    )
    result = await communicator.receive_json_from()

    assert result["type"] == "request.succeeded"
    assert result["payload"]["request_type"] == "session.ping"
    await communicator.disconnect()


async def test_game_socket_closes_after_logout_transaction_commits():
    user = await get_user_model().objects.acreate_user(
        username="ws_logout_closes", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_logout_closes", password="safe-pass-42")
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_before_logout",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    await communicator.receive_json_from()
    await communicator.receive_json_from()

    await database_sync_to_async(logout)(
        refresh_token=auth.refresh_token,
        authorization=f"Bearer {auth.access_token}",
    )
    close = await communicator.receive_output()

    assert close == {"type": "websocket.close", "code": 1000}
    await communicator.disconnect()


async def test_game_socket_closes_after_logout_even_when_channel_delivery_fails(settings):
    settings.GAME_WEBSOCKET_AUTH_REVALIDATION_INTERVAL_SECONDS = 0.01
    user = await get_user_model().objects.acreate_user(
        username="ws_logout_channel_failure", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_logout_channel_failure", password="safe-pass-42"
    )
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_before_channel_failure",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    channel_layer = get_channel_layer()
    assert channel_layer is not None

    with patch.object(channel_layer, "group_send", side_effect=RuntimeError("channel full")):
        await database_sync_to_async(logout)(
            refresh_token=auth.refresh_token,
            authorization=f"Bearer {auth.access_token}",
        )
    close = await communicator.receive_output()

    assert close == {"type": "websocket.close", "code": 1000}
    await communicator.disconnect()


async def test_game_socket_revalidates_after_joining_the_revocation_group():
    user = await get_user_model().objects.acreate_user(
        username="ws_revoke_during_binding", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_revoke_during_binding", password="safe-pass-42"
    )
    channel_layer = get_channel_layer()
    assert channel_layer is not None
    original_group_add = channel_layer.group_add
    revoked = False

    async def revoke_before_group_add(group: str, channel: str) -> None:
        nonlocal revoked
        if not revoked:
            revoked = True
            await database_sync_to_async(logout)(
                refresh_token=auth.refresh_token,
                authorization=f"Bearer {auth.access_token}",
            )
        await original_group_add(group, channel)

    communicator = await _connected()
    with patch.object(channel_layer, "group_add", side_effect=revoke_before_group_add):
        await communicator.send_json_to(
            {
                "version": "1",
                "request_id": "req_revoke_during_binding",
                "type": "session.authenticate",
                "payload": {"access_token": auth.access_token},
            }
        )
        terminal = await communicator.receive_json_from()

    assert revoked is True
    assert terminal["type"] == "request.failed"
    assert terminal["payload"]["error"]["code"] == "SESSION_REVOKED"
    assert await communicator.receive_nothing(timeout=0.05)
    await communicator.disconnect()


async def test_game_socket_rejects_active_token_for_a_different_content_instance():
    user = await get_user_model().objects.acreate_user(
        username="ws_cross_instance", password="safe-pass-42"
    )
    account = await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_cross_instance", password="safe-pass-42"
    )
    await database_sync_to_async(GameAccount.objects.filter(pk=account.pk).update)(
        instance_id="another-content-instance"
    )

    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_cross_instance",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    result = await communicator.receive_json_from()
    assert result["type"] == "request.failed"
    assert result["payload"]["error"]["code"] == "TOKEN_INVALID"
    await communicator.disconnect()


async def test_game_socket_does_not_replay_authentication_after_instance_binding_changes():
    user = await get_user_model().objects.acreate_user(
        username="ws_instance_replay", password="safe-pass-42"
    )
    account = await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_instance_replay", password="safe-pass-42"
    )
    envelope = {
        "version": "1",
        "request_id": "req_instance_replay",
        "type": "session.authenticate",
        "payload": {"access_token": auth.access_token},
    }
    communicator = await _connected()
    await communicator.send_json_to(envelope)
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    await database_sync_to_async(GameAccount.objects.filter(pk=account.pk).update)(
        instance_id="another-content-instance"
    )
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert replay["type"] == "request.failed"
    assert replay["payload"]["error"]["code"] == "SESSION_REVOKED"
    await communicator.disconnect()


async def test_game_socket_replays_failed_authentication_terminal_without_rewriting_it():
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_invalid_replay",
        "type": "session.authenticate",
        "payload": {"access_token": "invalid-access-token"},
    }
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert first["payload"]["error"]["code"] == "TOKEN_INVALID"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == first["seq"] + 1
    await communicator.disconnect()


async def test_game_socket_terminalizes_malformed_envelope_with_a_valid_request_id():
    user = await get_user_model().objects.acreate_user(
        username="ws_malformed_terminal", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_malformed_terminal", password="safe-pass-42"
    )
    valid_envelope = {
        "version": "1",
        "request_id": "req_malformed_terminal",
        "type": "session.authenticate",
        "payload": {"access_token": auth.access_token},
    }
    communicator = await _connected()
    await communicator.send_json_to({**valid_envelope, "unexpected": True})
    first = await communicator.receive_json_from()
    await communicator.send_json_to(valid_envelope)
    replay = await communicator.receive_json_from()

    assert first["payload"]["error"]["code"] == "INVALID_ENVELOPE"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == first["seq"] + 1
    await communicator.disconnect()


async def test_game_socket_replays_the_unique_terminal_before_revalidating_envelope_shape():
    user = await get_user_model().objects.acreate_user(
        username="ws_malformed_after_success", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_malformed_after_success", password="safe-pass-42"
    )
    envelope = {
        "version": "1",
        "request_id": "req_malformed_after_success",
        "type": "session.authenticate",
        "payload": {"access_token": auth.access_token},
    }
    communicator = await _connected()
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    assert first["type"] == "request.succeeded"
    await communicator.receive_json_from()

    await communicator.send_json_to({**envelope, "unexpected": True})
    replay = await communicator.receive_json_from()

    assert replay["type"] == "request.succeeded"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == first["seq"] + 2
    await communicator.disconnect()


async def test_game_socket_terminalizes_json_outside_the_jcs_number_domain():
    envelope = {
        "version": "1",
        "request_id": "req_unsafe_jcs_number",
        "type": "future.request",
        "payload": {"value": 2**60},
    }
    communicator = await _connected()
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert first["type"] == "request.failed"
    assert first["payload"]["error"]["code"] == "INVALID_ENVELOPE"
    assert replay["payload"] == first["payload"]
    await communicator.disconnect()


async def test_game_socket_closes_non_json_text_with_a_redacted_protocol_log(caplog):
    marker = "untrusted-payload-marker"
    communicator = await _connected()
    with caplog.at_level(logging.WARNING, logger="new_mud.apps.identity.consumers"):
        await communicator.send_to(text_data=f'{{"payload":{{"access_token":"{marker}"}}')
        close = await communicator.receive_output()

    assert close == {"type": "websocket.close", "code": 4400}
    assert marker not in caplog.text
    assert any(
        getattr(record, "protocol_error_code", None) == "INVALID_JSON_FRAME"
        for record in caplog.records
    )
    await communicator.disconnect()


async def test_game_socket_audits_the_connection_session_lifecycle(caplog):
    with caplog.at_level(logging.INFO, logger="new_mud.apps.identity.consumers"):
        communicator = await _connected()
        await communicator.disconnect()

    lifecycle_records = [
        record for record in caplog.records if getattr(record, "connection_state", None) is not None
    ]
    assert [record.connection_state for record in lifecycle_records] == [
        "opening",
        "active",
        "closing",
        "closed",
    ]
    assert len({record.connection_session_id for record in lifecycle_records}) == 1


async def test_game_socket_closes_json_without_a_request_id_with_a_redacted_log(caplog):
    marker = "untrusted-json-marker"
    communicator = await _connected()
    with caplog.at_level(logging.WARNING, logger="new_mud.apps.identity.consumers"):
        await communicator.send_json_to({"payload": {"access_token": marker}})
        close = await communicator.receive_output()

    assert close == {"type": "websocket.close", "code": 4400}
    assert marker not in caplog.text
    assert any(
        getattr(record, "protocol_error_code", None) == "REQUEST_ID_INVALID"
        for record in caplog.records
    )
    await communicator.disconnect()


async def test_game_socket_marks_unimplemented_presence_entry_as_unsupported():
    user = await get_user_model().objects.acreate_user(
        username="ws_future_presence", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_future_presence", password="safe-pass-42"
    )
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_auth_before_presence",
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    await communicator.receive_json_from()
    await communicator.receive_json_from()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_future_presence",
            "type": "presence.enter",
            "payload": {"character_id": "character-not-yet-supported"},
        }
    )
    result = await communicator.receive_json_from()

    assert result["type"] == "request.failed"
    assert result["payload"]["error"]["code"] == "REQUEST_TYPE_UNSUPPORTED"
    await communicator.disconnect()


async def test_game_socket_rejects_non_string_access_token_as_an_invalid_payload():
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_non_string_token",
            "type": "session.authenticate",
            "payload": {"access_token": None},
        }
    )
    result = await communicator.receive_json_from()

    assert result["type"] == "request.failed"
    assert result["payload"]["error"]["code"] == "PAYLOAD_INVALID"
    await communicator.disconnect()


async def test_game_socket_revalidates_authentication_on_a_different_connection():
    user = await get_user_model().objects.acreate_user(
        username="ws_cross_connection", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="ws_cross_connection", password="safe-pass-42"
    )
    request_id = "req_reused_on_new_connection"
    first = await _connected()
    await first.send_json_to(
        {
            "version": "1",
            "request_id": request_id,
            "type": "session.authenticate",
            "payload": {"access_token": auth.access_token},
        }
    )
    assert (await first.receive_json_from())["type"] == "request.succeeded"
    await first.receive_json_from()

    second = await _connected()
    await second.send_json_to(
        {
            "version": "1",
            "request_id": request_id,
            "type": "session.authenticate",
            "payload": {"access_token": "invalid-access-token"},
        }
    )
    result = await second.receive_json_from()

    assert result["type"] == "request.failed"
    assert result["seq"] == 1
    assert result["payload"]["error"]["code"] == "TOKEN_INVALID"
    await first.disconnect()
    await second.disconnect()


async def test_game_socket_returns_a_stable_expired_token_terminal():
    user = await get_user_model().objects.acreate_user(
        username="ws_expired_token", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_expired_token", password="safe-pass-42")
    claims = decode_access_token(auth.access_token)
    assert claims is not None
    claims["exp"] = 0
    expired_token = encode_access_token(claims)
    envelope = {
        "version": "1",
        "request_id": "req_expired_token",
        "type": "session.authenticate",
        "payload": {"access_token": expired_token},
    }
    communicator = await _connected()
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert first["payload"]["error"]["code"] == "TOKEN_EXPIRED"
    assert replay["payload"] == first["payload"]
    await communicator.disconnect()


async def test_game_socket_does_not_accept_a_refresh_token_for_authentication():
    user = await get_user_model().objects.acreate_user(
        username="ws_refresh_token", password="safe-pass-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(username="ws_refresh_token", password="safe-pass-42")
    communicator = await _connected()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_refresh_token",
            "type": "session.authenticate",
            "payload": {"access_token": auth.refresh_token},
        }
    )
    result = await communicator.receive_json_from()

    assert result["type"] == "request.failed"
    assert result["payload"]["error"]["code"] == "TOKEN_INVALID"
    await communicator.disconnect()


async def test_game_socket_closes_binary_frames_as_protocol_errors(caplog):
    communicator = await _connected()
    with caplog.at_level(logging.WARNING, logger="new_mud.apps.identity.consumers"):
        await communicator.send_to(bytes_data=b"binary-frames-are-not-supported")
        close = await communicator.receive_output()

    assert close == {"type": "websocket.close", "code": 4400}
    assert any(
        getattr(record, "protocol_error_code", None) == "BINARY_FRAME_UNSUPPORTED"
        for record in caplog.records
    )
    await communicator.disconnect()


async def test_game_socket_ping_is_connection_local_and_sequenced():
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_ping",
        "type": "session.ping",
        "payload": {"nonce": "nonce-1"},
    }
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert first["type"] == "request.succeeded"
    assert first["payload"]["result"]["nonce"] == "nonce-1"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == 2
    await communicator.disconnect()


async def test_game_socket_rate_limits_terminal_replays(settings):
    settings.GAME_WEBSOCKET_REQUEST_RATE_LIMIT = 2
    settings.GAME_WEBSOCKET_REQUEST_RATE_WINDOW_SECONDS = 60
    settings.GAME_WEBSOCKET_TERMINAL_LIMIT = 3
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_rate_replay",
        "type": "session.ping",
        "payload": {},
    }

    await communicator.send_json_to(envelope)
    assert (await communicator.receive_json_from())["type"] == "request.succeeded"
    await communicator.send_json_to(envelope)
    assert (await communicator.receive_json_from())["type"] == "request.succeeded"
    await communicator.send_json_to(envelope)

    assert await communicator.receive_output() == {
        "type": "websocket.close",
        "code": 1008,
    }
    await communicator.disconnect()


async def test_game_socket_terminalizes_the_first_rate_limited_request_and_closes(settings):
    settings.GAME_WEBSOCKET_REQUEST_RATE_LIMIT = 2
    settings.GAME_WEBSOCKET_REQUEST_RATE_WINDOW_SECONDS = 60
    settings.GAME_WEBSOCKET_TERMINAL_LIMIT = 3
    communicator = await _connected()
    first_envelope = {
        "version": "1",
        "request_id": "req_rate_first",
        "type": "session.ping",
        "payload": {"nonce": "first"},
    }
    second_envelope = {
        "version": "1",
        "request_id": "req_rate_second",
        "type": "session.ping",
        "payload": {"nonce": "second"},
    }
    await communicator.send_json_to(first_envelope)
    first = await communicator.receive_json_from()
    await communicator.send_json_to(second_envelope)
    second = await communicator.receive_json_from()
    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_rate_third",
            "type": "session.ping",
            "payload": {"nonce": "third"},
        }
    )
    limited = await communicator.receive_json_from()
    close = await communicator.receive_output()

    assert first["type"] == second["type"] == "request.succeeded"
    assert limited["payload"]["error"]["code"] == "RATE_LIMITED"
    assert close == {"type": "websocket.close", "code": 1008}
    await communicator.disconnect()


async def test_game_socket_closes_when_terminal_storage_is_full(settings):
    settings.GAME_WEBSOCKET_REQUEST_RATE_LIMIT = 10
    settings.GAME_WEBSOCKET_REQUEST_RATE_WINDOW_SECONDS = 60
    settings.GAME_WEBSOCKET_TERMINAL_LIMIT = 2
    communicator = await _connected()
    for request_id in ("req_capacity_first", "req_capacity_second"):
        await communicator.send_json_to(
            {
                "version": "1",
                "request_id": request_id,
                "type": "session.ping",
                "payload": {},
            }
        )
        assert (await communicator.receive_json_from())["type"] == "request.succeeded"

    await communicator.send_json_to(
        {
            "version": "1",
            "request_id": "req_rate_capacity",
            "type": "session.ping",
            "payload": {},
        }
    )
    capacity = await communicator.receive_json_from()
    close = await communicator.receive_output()

    assert capacity["payload"]["error"]["code"] == "RATE_LIMITED"
    assert close == {"type": "websocket.close", "code": 1008}
    await communicator.disconnect()


async def test_game_socket_records_redacted_client_context_and_metrics(caplog):
    before = game_websocket_metrics.snapshot()
    with caplog.at_level(logging.INFO, logger="new_mud.apps.identity.consumers"):
        communicator = WebsocketCommunicator(
            application,
            "/ws/v1/game",
            headers=[
                (b"user-agent", b"secret-user-agent-marker"),
                (b"x-forwarded-for", b"203.0.113.42"),
            ],
            subprotocols=["screen-reader", "structured-actions"],
        )
        communicator.scope["client"] = ("198.51.100.17", 12345)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.send_json_to(
            {
                "version": "1",
                "request_id": "req_context_metrics",
                "type": "session.ping",
                "payload": {},
            }
        )
        await communicator.receive_json_from()
        await communicator.disconnect()

    after = game_websocket_metrics.snapshot()
    opening = next(record for record in caplog.records if record.connection_state == "opening")
    request = next(
        record
        for record in caplog.records
        if getattr(record, "request_id", None) == "req_context_metrics"
    )
    assert opening.remote_ip_summary != "198.51.100.17"
    assert opening.user_agent_summary != "secret-user-agent-marker"
    assert opening.client_capability_count == 2
    assert "screen-reader" not in caplog.text
    assert "secret-user-agent-marker" not in caplog.text
    assert request.duration_ms >= 0
    assert after.online_connections == before.online_connections
    assert after.connections_total == before.connections_total + 1
    assert after.requests_total == before.requests_total + 1


async def test_connection_client_context_retains_capabilities_with_a_safe_audit_projection():
    context = ConnectionClientContext.from_scope(
        {
            "headers": [(b"user-agent", b"secret-user-agent-marker")],
            "client": ("198.51.100.17", 12345),
            "subprotocols": ["screen-reader", "structured-actions"],
        }
    )

    assert context.capabilities == ("screen-reader", "structured-actions")
    assert "screen-reader" in context.capabilities
    assert "unknown-capability" not in context.capabilities
    audit = context.audit_fields()
    assert audit["client_capability_count"] == 2
    assert "screen-reader" not in audit.values()
    assert "secret-user-agent-marker" not in audit.values()
    assert "198.51.100.17" not in audit.values()


async def test_game_socket_hashes_equivalent_json_numbers_canonically():
    communicator = await _connected()
    envelope = {
        "version": "1",
        "request_id": "req_canonical_number",
        "type": "future.request",
        "payload": {"value": 1},
    }
    await communicator.send_json_to(envelope)
    first = await communicator.receive_json_from()
    envelope["payload"] = {"value": 1.0}
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()

    assert first["payload"]["error"]["code"] == "AUTH_REQUIRED"
    assert replay["payload"] == first["payload"]
    assert replay["seq"] == 2
    await communicator.disconnect()
