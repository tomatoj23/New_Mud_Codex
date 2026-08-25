from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .readiness import probe_readiness


class HealthConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        _status_code, readiness = await database_sync_to_async(probe_readiness)()
        await self.send_json(
            {
                "type": "health.ready",
                **readiness,
                "version": "1",
            }
        )
        await self.close(code=1000)
