from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "new_mud.apps.identity"

    def ready(self) -> None:
        from . import verification_checks  # noqa: F401
