from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Tags, register

from .verification_config import VerificationServiceUnavailable, require_verification_service


@register(Tags.security)
def check_verification_configuration(app_configs, **kwargs):
    if not getattr(settings, "AUTH_VERIFICATION_ENABLED", False):
        return []
    try:
        require_verification_service()
    except VerificationServiceUnavailable:
        return [
            Error(
                "Enabled verification delivery configuration is incomplete or not independent.",
                id="identity.E001",
            )
        ]
    test_backends = {
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
    }
    if settings.EMAIL_BACKEND in test_backends and not getattr(
        settings, "AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND", False
    ):
        return [
            Error(
                "Enabled verification delivery requires a non-test email backend.",
                id="identity.E002",
            )
        ]
    return []
