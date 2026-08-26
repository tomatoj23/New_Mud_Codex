import os

from .base import *  # noqa: F403

AUTH_ALLOWED_ORIGINS = ["http://localhost:5173"]
AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND = (
    os.getenv("NEW_MUD_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND", "0") == "1"
)

DEBUG = True
SECRET_KEY = SECRET_KEY or "unsafe-development-only-key"  # noqa: F405
AUTH_TOKEN_SIGNING_KEY = (  # noqa: F405
    AUTH_TOKEN_SIGNING_KEY or "unsafe-development-only-token-signing-key"  # noqa: F405
)
