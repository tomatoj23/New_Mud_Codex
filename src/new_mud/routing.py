from django.urls import path

from new_mud.apps.health.consumers import HealthConsumer

# Django's public path() stubs only model HTTP callbacks, while Channels accepts ASGI callables.
websocket_urlpatterns = [
    path("ws/v1/health/", HealthConsumer.as_asgi())  # type: ignore[arg-type]
]
