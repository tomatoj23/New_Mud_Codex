import logging
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "new_mud.settings.development")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.core.asgi import get_asgi_application

logger = logging.getLogger(__name__)


def create_application():
    http_application = get_asgi_application()

    from new_mud.apps.content.runtime import ContentRuntimeStatus, get_content_runtime
    from new_mud.process_guard import acquire_single_process_lease
    from new_mud.routing import websocket_urlpatterns

    if settings.CONTENT_STARTUP_ENABLED:
        acquire_single_process_lease()
    runtime = get_content_runtime(settings.CONTENT_INSTANCE_ID)
    if settings.CONTENT_STARTUP_ENABLED:
        startup = runtime.start()
        if startup.status is ContentRuntimeStatus.NOT_READY:
            logger.error(
                "content runtime startup failed",
                extra={
                    "instance_id": settings.CONTENT_INSTANCE_ID,
                    "error_code": startup.error_code,
                    "error_message": startup.error_message,
                },
            )
    return ProtocolTypeRouter(
        {
            "http": http_application,
            # types-channels models this as a private URLPattern subtype; runtime accepts it.
            "websocket": URLRouter(websocket_urlpatterns),  # type: ignore[arg-type]
        }
    )


application = create_application()
