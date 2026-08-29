from __future__ import annotations

import os

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model

from new_mud.apps.identity.models import GameAccount
from new_mud.apps.identity.services import login, logout
from new_mud.asgi import application

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]


async def test_postgres_game_connection_revalidates_each_socket_and_closes_on_logout():
    user = await get_user_model().objects.acreate_user(
        username="pg_ws_contract", password="safe-postgres-ws-passphrase-42"
    )
    await GameAccount.objects.acreate(user=user, instance_id=settings.CONTENT_INSTANCE_ID)
    auth = await database_sync_to_async(login)(
        username="pg_ws_contract",
        password="safe-postgres-ws-passphrase-42",
    )
    sockets = [
        WebsocketCommunicator(application, "/ws/v1/game"),
        WebsocketCommunicator(application, "/ws/v1/game"),
    ]
    for socket in sockets:
        connected, _ = await socket.connect()
        assert connected
        await socket.send_json_to(
            {
                "version": "1",
                "request_id": "req_same_id_new_socket",
                "type": "session.authenticate",
                "payload": {"access_token": auth.access_token},
            }
        )
        terminal = await socket.receive_json_from()
        ready = await socket.receive_json_from()
        assert terminal["type"] == "request.succeeded"
        assert terminal["seq"] == 1
        assert ready["type"] == "session.ready"
        assert ready["seq"] == 2

    await database_sync_to_async(logout)(
        refresh_token=auth.refresh_token,
        authorization=f"Bearer {auth.access_token}",
    )
    for socket in sockets:
        assert await socket.receive_output() == {"type": "websocket.close", "code": 1000}
        await socket.disconnect()
