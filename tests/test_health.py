import pytest
from channels.testing import WebsocketCommunicator
from django.urls import reverse

from new_mud.asgi import application


def test_liveness(client):
    response = client.get(reverse("health-live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "new-mud", "version": "1"}


@pytest.mark.asyncio
async def test_websocket_health():
    communicator = WebsocketCommunicator(application, "/ws/v1/health/")

    connected, _ = await communicator.connect()
    assert connected
    assert await communicator.receive_json_from() == {
        "type": "health.ready",
        "status": "ok",
        "version": "1",
    }
    await communicator.wait()
