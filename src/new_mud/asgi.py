import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "new_mud.settings.development")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from new_mud.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        # types-channels models this as a private URLPattern subtype; runtime accepts URLPattern.
        "websocket": URLRouter(websocket_urlpatterns),  # type: ignore[arg-type]
    }
)
