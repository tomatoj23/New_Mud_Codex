from __future__ import annotations

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model

from new_mud.apps.identity.models import GameAccount
from new_mud.apps.identity.services import login, logout
from new_mud.asgi import application

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def _connected():
    communicator = WebsocketCommunicator(application, "/ws/v1/game")
    connected, _ = await communicator.connect()
    assert connected
    return communicator


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
    await database_sync_to_async(logout)(
        refresh_token=auth.refresh_token,
        authorization=f"Bearer {auth.access_token}",
    )
    await communicator.send_json_to(envelope)
    replay = await communicator.receive_json_from()
    assert replay["type"] == "request.failed"
    assert replay["payload"]["error"]["code"] == "SESSION_REVOKED"
    await communicator.disconnect()
