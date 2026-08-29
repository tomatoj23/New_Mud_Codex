from django.urls import path

from new_mud.apps.health.consumers import HealthConsumer
from new_mud.apps.identity.consumers import GameConsumer

# Django's public path() stubs only model HTTP callbacks, while Channels accepts ASGI callables.
websocket_urlpatterns = [
    path("ws/v1/health/", HealthConsumer.as_asgi()),  # type: ignore[arg-type]
    path("ws/v1/game", GameConsumer.as_asgi()),  # type: ignore[arg-type]
]
